"""Orquestração da captura manual DF-e recebidos via SEFAZ."""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from typing import Any

from apps.cadastros.models import Empresa
from apps.fiscal.cte_import.parser import parse_cte_xml
from apps.fiscal.cte_import.service import importar_arquivos_cte
from apps.fiscal.dfe_recebidos.distribuicao_dfe_parser import (
    CSTAT_CONSUMO_INDEVIDO,
    DocumentoDistribuicao,
    parse_distribuicao_dfe_response,
)
from apps.fiscal.dfe_recebidos.nsu_estado import (
    AVISO_NSU_CACHE,
    carregar_estado_nsu,
    salvar_estado_nsu,
)
from apps.fiscal.nfe_historica_classificacao import norm_digits
from apps.fiscal.nfe_import.service_entrada import importar_arquivos_entrada
from apps.fiscal.nfe_integracao.adapters.certificado_a1 import carregar_certificado_empresa
from apps.fiscal.nfe_integracao.adapters.exceptions import CertificadoA1Error, PyNFeComunicacaoError
from apps.fiscal.nfe_integracao.adapters.pynfe_adapter import (
    consulta_distribuicao_dfe_cte,
    consulta_distribuicao_dfe_nfe,
    criar_comunicacao_cte,
    criar_comunicacao_sefaz,
)
from apps.fiscal.nfe_integracao.prontidao_consulta_sefaz import validar_prontidao_consulta_sefaz

logger = logging.getLogger(__name__)

TIPO_NFE = 'NFE'
TIPO_CTE = 'CTE'
CSTAT_AUTORIZADO = frozenset({'100', '150'})
MSG_CERTIFICADO_DFE = 'Certificado digital não disponível/configurado para consulta DF-e.'
MSG_NENHUM_NOVO = 'Nenhum DF-e novo encontrado nesta captura.'
MSG_NSU_PENDENTE = (
    'Ainda existem documentos pendentes na SEFAZ. Execute nova captura para continuar.'
)
MSG_LIMITE_LOTES = (
    'Captura interrompida pelo limite de lotes configurado. Aumente o limite com cautela '
    '(chamadas excessivas podem gerar rejeição/consumo indevido na SEFAZ).'
)


def _local(tag: str) -> str:
    return tag.split('}')[-1] if '}' in tag else tag


def _find_first(root: ET.Element, name: str) -> ET.Element | None:
    for el in root.iter():
        if _local(el.tag) == name:
            return el
    return None


def _party_doc(node: ET.Element | None) -> str:
    if node is None:
        return ''
    for child in node:
        ln = _local(child.tag)
        if ln in {'CNPJ', 'CPF'}:
            return norm_digits(child.text or '')
    return ''


def _nfe_elegivel_captura(xml_bytes: bytes, cnpj_empresa: str) -> tuple[bool, str]:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return False, 'XML NF-e inválido'

    inf = _find_first(root, 'infNFe')
    if inf is None:
        return False, 'XML sem infNFe'

    ide = _find_first(inf, 'ide')
    if ide is not None:
        for child in ide:
            if _local(child.tag) == 'tpAmb' and (child.text or '').strip() != '1':
                return False, 'Ambiente homologação'

    emit = _find_first(inf, 'emit')
    dest = _find_first(inf, 'dest')
    emit_doc = _party_doc(emit)
    dest_doc = _party_doc(dest)
    if dest_doc != cnpj_empresa:
        return False, 'Destinatário diferente da empresa'
    if emit_doc == cnpj_empresa:
        return False, 'Emitente é a própria empresa'

    prot = _find_first(root, 'protNFe')
    if prot is not None:
        inf_prot = _find_first(prot, 'infProt')
        if inf_prot is not None:
            cstat = ''
            for child in inf_prot:
                if _local(child.tag) == 'cStat':
                    cstat = (child.text or '').strip()
            if cstat and cstat not in CSTAT_AUTORIZADO:
                return False, f'Status protocolo {cstat}'

    return True, ''


def _cte_elegivel_captura(xml_bytes: bytes, cnpj_empresa: str) -> tuple[bool, str]:
    parsed = parse_cte_xml(xml_bytes)
    if parsed.erro:
        return False, 'XML CT-e inválido'

    if (parsed.tp_amb or '').strip() != '1':
        return False, 'Ambiente homologação'

    emit_doc = norm_digits(
        str((parsed.emit_json or {}).get('CNPJ') or (parsed.emit_json or {}).get('CPF') or ''),
    )
    if emit_doc == cnpj_empresa:
        return False, 'Emitente é a própria empresa'

    parties = [
        parsed.tomador_json,
        parsed.dest_json,
        parsed.receb_json,
    ]
    participa = any(
        norm_digits(str((p or {}).get('CNPJ') or (p or {}).get('CPF') or '')) == cnpj_empresa
        for p in parties
    )
    if not participa:
        return False, 'Empresa não é tomadora/destinatária/recebedora'

    cstat = (parsed.cstat or '').strip()
    if cstat and cstat not in CSTAT_AUTORIZADO and not parsed.cancelado:
        return False, f'Status {cstat}'

    return True, ''


def _nome_arquivo_distrib(doc: DocumentoDistribuicao) -> str:
    return f'sefaz_distrib_{doc.tipo.lower()}_nsu_{doc.nsu or "0"}.xml'


def _processar_lote_importacao(
    documentos: list[DocumentoDistribuicao],
    *,
    tipo: str,
    cnpj_empresa: str,
) -> tuple[list[tuple[str, bytes]], int, list[str]]:
    arquivos: list[tuple[str, bytes]] = []
    ignorados = 0
    avisos: list[str] = []
    elegivel_fn = _nfe_elegivel_captura if tipo == TIPO_NFE else _cte_elegivel_captura

    for doc in documentos:
        if doc.tipo != tipo:
            continue
        ok, motivo = elegivel_fn(doc.conteudo_xml, cnpj_empresa)
        if not ok:
            ignorados += 1
            if motivo and motivo not in avisos:
                avisos.append(motivo)
            continue
        arquivos.append((_nome_arquivo_distrib(doc), doc.conteudo_xml))

    return arquivos, ignorados, avisos


def _capturar_tipo(
    *,
    empresa: Empresa,
    tipo: str,
    comunicacao: Any,
    consulta_fn: Any,
    cnpj_empresa: str,
    limite_lotes: int,
) -> dict[str, Any]:
    estado = carregar_estado_nsu(empresa.pk, tipo)
    ult_nsu_inicial = estado.ultimo_nsu
    ult_nsu_consulta = estado.ultimo_nsu
    encontrados = 0
    encontrados_resumo = 0
    novos = 0
    duplicados = 0
    ignorados = 0
    mensagens: list[str] = []
    avisos: list[str] = [AVISO_NSU_CACHE]
    erros: list[str] = []
    ult_nsu_final = estado.ultimo_nsu
    max_nsu_final = estado.max_nsu
    bloqueado = False
    sefaz_consultada = False
    lotes_consultados = 0
    cstat_final = ''
    limite_efetivo = max(1, min(limite_lotes, 20))

    for _ in range(limite_efetivo):
        logger.info(
            'Iniciando consulta distribuição DF-e SEFAZ empresa=%s tipo=%s ult_nsu=%s',
            empresa.pk,
            tipo,
            ult_nsu_consulta,
        )
        try:
            resposta = consulta_fn(comunicacao, cnpj_empresa, nsu=ult_nsu_consulta)
        except PyNFeComunicacaoError as exc:
            erros.append(str(exc))
            salvar_estado_nsu(
                empresa.pk,
                tipo,
                ultimo_nsu=ult_nsu_final,
                max_nsu=max_nsu_final,
                status='ERRO',
                mensagem=str(exc),
            )
            break

        sefaz_consultada = True
        lotes_consultados += 1
        parsed = parse_distribuicao_dfe_response(resposta)
        cstat_final = parsed.cstat or cstat_final
        ult_nsu_final = max(ult_nsu_final, parsed.ult_nsu)
        max_nsu_final = max(max_nsu_final, parsed.max_nsu)

        if parsed.documentos_resumo:
            encontrados_resumo += parsed.documentos_resumo
            aviso_resumo = (
                f'{parsed.documentos_resumo} resumo(s) SEFAZ ({tipo}) sem XML completo — '
                'não importável nesta fase.'
            )
            if aviso_resumo not in avisos:
                avisos.append(aviso_resumo)

        if parsed.cstat in CSTAT_CONSUMO_INDEVIDO:
            bloqueado = True
            mensagens.append(parsed.mensagem_usuario)
            salvar_estado_nsu(
                empresa.pk,
                tipo,
                ultimo_nsu=ult_nsu_final,
                max_nsu=max_nsu_final,
                status=parsed.cstat,
                mensagem=parsed.mensagem_usuario,
            )
            break

        if parsed.mensagem_usuario:
            mensagens.append(f'SEFAZ ({tipo}) cStat {parsed.cstat}: {parsed.mensagem_usuario}')

        docs_tipo = [d for d in parsed.documentos if d.tipo == tipo]
        encontrados += len(docs_tipo)

        arquivos, ign, avs = _processar_lote_importacao(docs_tipo, tipo=tipo, cnpj_empresa=cnpj_empresa)
        ignorados += ign
        for a in avs:
            if a not in avisos:
                avisos.append(a)

        if arquivos:
            if tipo == TIPO_NFE:
                resultado = importar_arquivos_entrada(arquivos)
                novos += len(resultado.get('importadas') or [])
                duplicados += len(resultado.get('duplicadas') or [])
                for item in resultado.get('erros') or []:
                    msg = item.get('mensagem_completa') or item.get('mensagem') or 'Erro na importação NF-e'
                    erros.append(str(msg)[:200])
            else:
                resultado = importar_arquivos_cte(arquivos)
                novos += len(resultado.get('importados') or [])
                duplicados += len(resultado.get('duplicados') or [])
                for item in resultado.get('erros') or []:
                    msg = item.get('mensagem') or 'Erro na importação CT-e'
                    erros.append(str(msg)[:200])

        salvar_estado_nsu(
            empresa.pk,
            tipo,
            ultimo_nsu=ult_nsu_final,
            max_nsu=max_nsu_final,
            status=parsed.cstat,
            mensagem=parsed.xmotivo or parsed.mensagem_usuario,
        )

        logger.info(
            'Resposta distribuição DF-e SEFAZ empresa=%s tipo=%s cStat=%s ultNSU=%s maxNSU=%s docs=%s resumos=%s',
            empresa.pk,
            tipo,
            parsed.cstat,
            parsed.ult_nsu,
            parsed.max_nsu,
            len(docs_tipo),
            parsed.documentos_resumo,
        )

        ainda_pendente = parsed.max_nsu > 0 and parsed.ult_nsu < parsed.max_nsu

        if parsed.cstat in CSTAT_CONSUMO_INDEVIDO:
            break
        if parsed.aguardar_proxima_consulta:
            break
        if not ainda_pendente:
            break

        ult_nsu_consulta = parsed.ult_nsu

    ainda_tem_nsu_pendente = (
        max_nsu_final > 0
        and ult_nsu_final < max_nsu_final
        and not bloqueado
    )
    parou_por_limite_lotes = lotes_consultados >= limite_efetivo and ainda_tem_nsu_pendente

    if ainda_tem_nsu_pendente:
        avisos.append(f'{MSG_NSU_PENDENTE} ({tipo})')
    if parou_por_limite_lotes:
        avisos.append(f'{MSG_LIMITE_LOTES} ({tipo})')

    logger.info(
        'Captura DF-e SEFAZ empresa=%s tipo=%s sefaz_consultada=%s cStat=%s encontrados=%s '
        'resumos=%s novos=%s duplicados=%s ignorados=%s ultNSU_inicial=%s ultNSU_final=%s '
        'maxNSU=%s lotes=%s nsu_pendente=%s limite_lotes=%s',
        empresa.pk,
        tipo,
        sefaz_consultada,
        cstat_final,
        encontrados,
        encontrados_resumo,
        novos,
        duplicados,
        ignorados,
        ult_nsu_inicial,
        ult_nsu_final,
        max_nsu_final,
        lotes_consultados,
        ainda_tem_nsu_pendente,
        parou_por_limite_lotes,
    )

    return {
        'sefaz_consultada': sefaz_consultada,
        'cstat': cstat_final,
        'lotes_consultados': lotes_consultados,
        'lotes_processados': lotes_consultados,
        'limite_lotes': limite_efetivo,
        'ultimo_nsu_inicial': ult_nsu_inicial,
        'ultimo_nsu_final': ult_nsu_final,
        'ultimo_nsu': ult_nsu_final,
        'max_nsu': max_nsu_final,
        'ainda_tem_nsu_pendente': ainda_tem_nsu_pendente,
        'parou_por_limite_lotes': parou_por_limite_lotes,
        'encontrados': encontrados,
        'encontrados_resumo': encontrados_resumo,
        'novos': novos,
        'duplicados': duplicados,
        'ignorados': ignorados,
        'mensagens': mensagens,
        'avisos': avisos,
        'erros': erros,
        'bloqueado_consumo_indevido': bloqueado,
    }


def capturar_dfe_recebidos_sefaz(
    *,
    empresa_id: int,
    tipos: list[str] | None = None,
    modo: str = 'incremental',
    limite_lotes: int = 3,
) -> dict[str, Any]:
    """
    Captura manual NF-e/CT-e recebidos via distribuição DF-e SEFAZ (produção).
    Alimenta apenas base importada — sem efeitos operacionais.
    """
    tipos_norm = [t.upper() for t in (tipos or [TIPO_NFE, TIPO_CTE]) if t]
    tipos_validos = [t for t in tipos_norm if t in {TIPO_NFE, TIPO_CTE}]
    if not tipos_validos:
        return {
            'sucesso': False,
            'erros': ['Informe ao menos um tipo válido: NFE ou CTE.'],
        }

    try:
        empresa = Empresa.objects.get(pk=empresa_id)
    except Empresa.DoesNotExist:
        return {'sucesso': False, 'erros': ['Empresa não encontrada.']}

    cnpj_empresa = norm_digits(empresa.cnpj)
    if len(cnpj_empresa) != 14:
        return {'sucesso': False, 'erros': ['CNPJ da empresa inválido para captura SEFAZ.']}

    pode, motivo, _tipo = validar_prontidao_consulta_sefaz(empresa)
    if not pode:
        return {
            'sucesso': False,
            'sefaz_consultada': False,
            'erros': [MSG_CERTIFICADO_DFE if 'certificado' in (motivo or '').lower() else (motivo or MSG_CERTIFICADO_DFE)],
        }

    try:
        cert_info = carregar_certificado_empresa(empresa)
    except CertificadoA1Error:
        return {'sucesso': False, 'sefaz_consultada': False, 'erros': [MSG_CERTIFICADO_DFE]}
    if not cert_info.valido:
        return {'sucesso': False, 'sefaz_consultada': False, 'erros': [MSG_CERTIFICADO_DFE]}

    cert_cnpj = norm_digits(cert_info.cnpj or '')
    if cert_cnpj and cert_cnpj != cnpj_empresa:
        return {
            'sucesso': False,
            'sefaz_consultada': False,
            'erros': [
                'CNPJ do certificado A1 não corresponde ao CNPJ da empresa ativa. '
                'Ajuste o certificado no cadastro da empresa.',
            ],
        }

    uf = (empresa.uf or 'SP').strip().upper()
    senha = (empresa.senha_certificado or '').strip()
    limite = max(1, min(int(limite_lotes or 3), 20))

    resumo: dict[str, Any] = {
        'nfe_encontradas': 0,
        'nfe_encontradas_resumo': 0,
        'nfe_novas': 0,
        'nfe_duplicadas': 0,
        'cte_encontrados': 0,
        'cte_encontrados_resumo': 0,
        'cte_novos': 0,
        'cte_duplicados': 0,
        'pendentes_total': 0,
    }
    mensagens: list[str] = []
    avisos: list[str] = []
    erros: list[str] = []
    nsu_por_tipo: dict[str, dict[str, int | str | bool]] = {}
    sefaz_por_tipo: dict[str, dict[str, Any]] = {}
    tipos_processados: list[str] = []
    sefaz_consultada = False
    ainda_tem_nsu_pendente = False
    parou_por_limite_lotes = False
    lotes_processados_total = 0

    if modo != 'incremental':
        avisos.append('Modo não incremental tratado como incremental (único modo suportado nesta fase).')

    def _registrar_tipo(tipo: str, r: dict[str, Any]) -> None:
        nonlocal sefaz_consultada, ainda_tem_nsu_pendente, parou_por_limite_lotes, lotes_processados_total
        sefaz_consultada = sefaz_consultada or bool(r['sefaz_consultada'])
        ainda_tem_nsu_pendente = ainda_tem_nsu_pendente or bool(r['ainda_tem_nsu_pendente'])
        parou_por_limite_lotes = parou_por_limite_lotes or bool(r['parou_por_limite_lotes'])
        lotes_processados_total += int(r.get('lotes_processados') or 0)
        tipos_processados.append(tipo)
        nsu_por_tipo[tipo] = {
            'ultimo_nsu_inicial': r['ultimo_nsu_inicial'],
            'ultimo_nsu_final': r['ultimo_nsu_final'],
            'ultimo_nsu': r['ultimo_nsu_final'],
            'max_nsu': r['max_nsu'],
            'ainda_tem_nsu_pendente': r['ainda_tem_nsu_pendente'],
            'parou_por_limite_lotes': r['parou_por_limite_lotes'],
            'lotes_processados': r['lotes_processados'],
        }
        sefaz_por_tipo[tipo] = {
            'consultada': r['sefaz_consultada'],
            'cstat': r['cstat'],
            'lotes_consultados': r['lotes_consultados'],
            'lotes_processados': r['lotes_processados'],
            'limite_lotes': r['limite_lotes'],
            'encontrados_xml': r['encontrados'],
            'encontrados_resumo': r['encontrados_resumo'],
            'novos': r['novos'],
            'duplicados': r['duplicados'],
            'ultimo_nsu_inicial': r['ultimo_nsu_inicial'],
            'ultimo_nsu_final': r['ultimo_nsu_final'],
            'max_nsu': r['max_nsu'],
            'ainda_tem_nsu_pendente': r['ainda_tem_nsu_pendente'],
            'parou_por_limite_lotes': r['parou_por_limite_lotes'],
        }

    try:
        if TIPO_NFE in tipos_validos:
            comm_nfe = criar_comunicacao_sefaz(
                uf,
                cert_info.caminho,
                senha,
                homologacao=False,
            )
            r = _capturar_tipo(
                empresa=empresa,
                tipo=TIPO_NFE,
                comunicacao=comm_nfe,
                consulta_fn=consulta_distribuicao_dfe_nfe,
                cnpj_empresa=cnpj_empresa,
                limite_lotes=limite,
            )
            _registrar_tipo(TIPO_NFE, r)
            resumo['nfe_encontradas'] = r['encontrados']
            resumo['nfe_encontradas_resumo'] = r['encontrados_resumo']
            resumo['nfe_novas'] = r['novos']
            resumo['nfe_duplicadas'] = r['duplicados']
            mensagens.extend(r['mensagens'])
            avisos.extend(r['avisos'])
            erros.extend(r['erros'])

        if TIPO_CTE in tipos_validos:
            comm_cte = criar_comunicacao_cte(
                uf,
                cert_info.caminho,
                senha,
                homologacao=False,
            )
            r = _capturar_tipo(
                empresa=empresa,
                tipo=TIPO_CTE,
                comunicacao=comm_cte,
                consulta_fn=consulta_distribuicao_dfe_cte,
                cnpj_empresa=cnpj_empresa,
                limite_lotes=limite,
            )
            _registrar_tipo(TIPO_CTE, r)
            resumo['cte_encontrados'] = r['encontrados']
            resumo['cte_encontrados_resumo'] = r['encontrados_resumo']
            resumo['cte_novos'] = r['novos']
            resumo['cte_duplicados'] = r['duplicados']
            mensagens.extend(r['mensagens'])
            avisos.extend(r['avisos'])
            erros.extend(r['erros'])
    except PyNFeComunicacaoError as exc:
        return {
            'sucesso': False,
            'sefaz_consultada': sefaz_consultada,
            'ainda_tem_nsu_pendente': ainda_tem_nsu_pendente,
            'parou_por_limite_lotes': parou_por_limite_lotes,
            'lotes_processados': lotes_processados_total,
            'limite_lotes': limite,
            'empresa': {'id': empresa.pk, 'razao_social': empresa.razao_social, 'cnpj': empresa.cnpj},
            'tipos_processados': tipos_processados,
            'resumo': resumo,
            'mensagens': mensagens,
            'avisos': avisos,
            'erros': [str(exc)],
            'nsu_por_tipo': nsu_por_tipo,
            'sefaz_por_tipo': sefaz_por_tipo,
        }

    resumo['pendentes_total'] = resumo['nfe_novas'] + resumo['cte_novos']

    if sefaz_consultada and resumo['pendentes_total'] == 0 and not resumo['nfe_duplicadas'] and not resumo['cte_duplicados']:
        mensagens.append(MSG_NENHUM_NOVO)

    if ainda_tem_nsu_pendente and MSG_NSU_PENDENTE not in mensagens:
        mensagens.append(MSG_NSU_PENDENTE)

    # Deduplica listas preservando ordem
    def _uniq(seq: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for item in seq:
            if item not in seen:
                seen.add(item)
                out.append(item)
        return out

    sucesso = sefaz_consultada and (
        not erros
        or (resumo['nfe_novas'] + resumo['cte_novos'] + resumo['nfe_duplicadas'] + resumo['cte_duplicados']) > 0
    )

    return {
        'sucesso': sucesso,
        'sefaz_consultada': sefaz_consultada,
        'ainda_tem_nsu_pendente': ainda_tem_nsu_pendente,
        'parou_por_limite_lotes': parou_por_limite_lotes,
        'lotes_processados': lotes_processados_total,
        'limite_lotes': limite,
        'empresa': {'id': empresa.pk, 'razao_social': empresa.razao_social, 'cnpj': empresa.cnpj},
        'tipos_processados': tipos_processados,
        'resumo': resumo,
        'mensagens': _uniq(mensagens),
        'avisos': _uniq(avisos),
        'erros': _uniq(erros),
        'nsu_por_tipo': nsu_por_tipo,
        'sefaz_por_tipo': sefaz_por_tipo,
    }
