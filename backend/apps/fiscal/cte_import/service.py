from __future__ import annotations

from typing import Any

from django.db import transaction

from apps.cadastros.models import Empresa, Fornecedor, Transportadora

from ..cte_historico_conferencia import _status_inicial_importacao
from ..models import CTeHistoricoImportado
from ..services.reforma_tributaria import enriquecer_reforma_e_outros_json_cte
from apps.fiscal.xml_armazenamento import ORIGEM_IMPORTACAO_MANUAL, persistir_xml_cte
from .parser import parse_cte_xml


def _norm_digits(val: str) -> str:
    return ''.join(c for c in str(val or '') if c.isdigit())


def _resolve_transportadora(emit: dict[str, Any]) -> Transportadora | None:
    doc = _norm_digits(emit.get('CNPJ') or emit.get('CPF') or '')
    if len(doc) != 14:
        return None
    for t in Transportadora.objects.only('id', 'cnpj'):
        if _norm_digits(t.cnpj) == doc:
            return t
    return None


def _resolve_empresa_tomadora(tomador: dict[str, Any]) -> Empresa | None:
    # tenta achar CNPJ/CPF em chaves comuns do toma4 (CNPJ/CPF) ou campos aninhados (toma)
    doc = _norm_digits(tomador.get('CNPJ') or tomador.get('CPF') or '')
    if len(doc) != 14:
        # tenta estruturas mais profundas (não padronizadas no nosso json simplificado)
        for k in ('toma', 'toma4', 'toma3'):
            node = tomador.get(k)
            if isinstance(node, dict):
                doc = _norm_digits(node.get('CNPJ') or node.get('CPF') or '')
                if len(doc) == 14:
                    break
    if len(doc) != 14:
        return None
    for emp in Empresa.objects.only('id', 'cnpj'):
        if _norm_digits(emp.cnpj) == doc:
            return emp
    return None


def _resolve_empresa_from_party(party: dict[str, Any]) -> Empresa | None:
    doc = _norm_digits(party.get('CNPJ') or party.get('CPF') or '')
    if len(doc) != 14:
        return None
    for emp in Empresa.objects.only('id', 'cnpj'):
        if _norm_digits(emp.cnpj) == doc:
            return emp
    return None


def _resolve_fornecedor_from_party(party: dict[str, Any]) -> Fornecedor | None:
    from apps.fiscal.nfe_historica_classificacao import resolve_fornecedor_from_party

    return resolve_fornecedor_from_party(party)


def importar_arquivos_cte(arquivos: list[tuple[str, bytes]]) -> dict[str, Any]:
    importados: list[dict[str, Any]] = []
    duplicados: list[dict[str, Any]] = []
    erros: list[dict[str, Any]] = []

    for nome, conteudo in arquivos:
        nome = nome or 'sem_nome.xml'
        parsed = parse_cte_xml(conteudo)
        if parsed.erro:
            erros.append({'arquivo': nome, 'mensagem': parsed.erro})
            continue

        if CTeHistoricoImportado.objects.filter(chave_acesso=parsed.chave_acesso).exists():
            existente = CTeHistoricoImportado.objects.get(chave_acesso=parsed.chave_acesso)
            if persistir_xml_cte(
                existente,
                conteudo,
                origem=ORIGEM_IMPORTACAO_MANUAL,
                nome_arquivo=nome,
            ):
                duplicados.append(
                    {
                        'arquivo': nome,
                        'chave_acesso': parsed.chave_acesso,
                        'mensagem': 'XML completo armazenado para registro já existente.',
                    },
                )
            else:
                duplicados.append(
                    {
                        'arquivo': nome,
                        'chave_acesso': parsed.chave_acesso,
                        'mensagem': 'Esta chave de CT-e já foi importada.',
                    },
                )
            continue

        try:
            with transaction.atomic():
                empresa_tomadora = _resolve_empresa_tomadora(parsed.tomador_json)
                if not empresa_tomadora:
                    erros.append(
                        {
                            'arquivo': nome,
                            'chave_acesso': parsed.chave_acesso,
                            'mensagem': (
                                'CT-e não importado: nenhuma Empresa do ERP é tomadora deste frete. '
                                'Só entram CT-e em que você é o tomador.'
                            ),
                        },
                    )
                    continue

                empresa_destinataria = _resolve_empresa_from_party(parsed.dest_json)
                empresa_recebedora = _resolve_empresa_from_party(parsed.receb_json)
                fornecedor_remetente = _resolve_fornecedor_from_party(parsed.rem_json)
                papel_empresa = 'tomador'

                st_conf = _status_inicial_importacao(
                    cancelado=bool(parsed.cancelado),
                    cstat=(parsed.cstat or '')[:8],
                )
                cte = CTeHistoricoImportado.objects.create(
                    chave_acesso=parsed.chave_acesso,
                    numero=(parsed.numero or '')[:16],
                    serie=(parsed.serie or '')[:4],
                    modelo=(parsed.modelo or '')[:4],
                    dh_emissao=parsed.dh_emissao,
                    tp_amb=(parsed.tp_amb or '')[:1],
                    nat_op=(parsed.nat_op or '')[:120],
                    cfop=(parsed.cfop or '')[:8],
                    versao_layout=(parsed.versao_layout or '')[:16],
                    cstat=(parsed.cstat or '')[:8],
                    xmotivo=(parsed.xmotivo or '')[:255],
                    protocolo=(parsed.protocolo or '')[:30],
                    cancelado=bool(parsed.cancelado),
                    status_documento=(parsed.status_documento or 'autorizado')[:32],
                    data_cancelamento=parsed.data_cancelamento,
                    protocolo_cancelamento=(parsed.protocolo_cancelamento or '')[:30],
                    motivo_cancelamento=(parsed.motivo_cancelamento or '')[:255],
                    valor_total_servico=parsed.valor_total_servico,
                    valor_receber=parsed.valor_receber,
                    componentes_frete_json=parsed.componentes_frete,
                    icms_base=parsed.icms_base,
                    icms_aliquota=parsed.icms_aliquota,
                    icms_valor=parsed.icms_valor,
                    modal=(parsed.modal or '')[:16],
                    tipo_servico=(parsed.tipo_servico or '')[:16],
                    municipio_inicio=(parsed.municipio_inicio or '')[:120],
                    uf_inicio=(parsed.uf_inicio or '')[:2],
                    municipio_fim=(parsed.municipio_fim or '')[:120],
                    uf_fim=(parsed.uf_fim or '')[:2],
                    emit_json=parsed.emit_json,
                    rem_json=parsed.rem_json,
                    dest_json=parsed.dest_json,
                    exped_json=parsed.exped_json,
                    receb_json=parsed.receb_json,
                    tomador_json=parsed.tomador_json,
                    totais_json=parsed.totais_json,
                    imposto_json=parsed.imposto_json,
                    prot_json=parsed.prot_json,
                    reforma_e_outros_json=enriquecer_reforma_e_outros_json_cte(
                        parsed.imposto_json, parsed.reforma_e_outros_json
                    ),
                    chaves_nfe_vinculadas=parsed.chaves_nfe_vinculadas,
                    transportadora=_resolve_transportadora(parsed.emit_json),
                    empresa_tomadora=empresa_tomadora,
                    empresa_destinataria=empresa_destinataria,
                    empresa_recebedora=empresa_recebedora,
                    fornecedor_remetente=fornecedor_remetente,
                    papel_empresa_no_documento=papel_empresa,
                    nome_arquivo=nome[:255],
                    status_conferencia=st_conf,
                    apto_operacional=False,
                    ignorado_operacionalmente=False,
                )
                persistir_xml_cte(
                    cte,
                    conteudo,
                    origem=ORIGEM_IMPORTACAO_MANUAL,
                    nome_arquivo=nome,
                    forcar=True,
                )
        except Exception as e:
            erros.append({'arquivo': nome, 'mensagem': f'Falha ao gravar: {e}'})
            continue

        importados.append(
            {
                'arquivo': nome,
                'id': cte.id,
                'chave_acesso': cte.chave_acesso,
                'numero': cte.numero,
                'serie': cte.serie,
            }
        )

    return {
        'importados': importados,
        'duplicados': duplicados,
        'erros': erros,
        'resumo': {
            'total_arquivos': len(arquivos),
            'importados': len(importados),
            'duplicados': len(duplicados),
            'erros': len(erros),
        },
    }

