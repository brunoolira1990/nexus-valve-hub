"""Contingência SEFAZ — NF-e (modelo 55).

Permite continuar emitindo quando a SEFAZ (estadual e virtuais) fica indisponível,
com base nas modalidades previstas no Manual de Operações (MOC) Anexo III:

- tpEmis=2  EPEC   — Evento Prévio de Emissão em Contingência (quando SEFAZ + SVCs caem)
- tpEmis=6  SVC-RS — SEFAZ Virtual de Contingência operada pela SEFAZ-RS
- tpEmis=7  SVC-AN — SEFAZ Virtual de Contingência Ambiente Nacional

Modalidades tpEmis=9 (off-line DFe/NFC-e), tpEmis=4 (DPEC) e tpEmis=5 (FSDA)
são descontinuadas ou exclusivas da NFC-e (rejeição 711 da SEFAZ) e são bloqueadas.

Fluxo de uso:
1. SEFAZ indisponível -> `registrar_contingencia(empresa, motivo, tp_emis)`
2. NF em ERRO_TRANSMISSAO -> `emitir_em_contingencia(nf, usuario)` (EPEC):
   gera XML assinado com tpEmis=2, NÃO transmite; marca XML_ASSINADO.
3. SEFAZ restabelecida -> `transmitir_pendentes_contingencia(empresa, usuario)`
   transmite as NFs pendentes na numeração normal e o status segue para
   AUTORIZADA_HOMOLOGACAO/PRODUCAO ou REJEITADA.
4. Encerrar: `encerrar_contingencia(empresa)`.

Prazo SEFAZ: transmitir a NF-e completa em até 168 horas (7 dias) após a
emissão em contingência; depois disso o número deve ser inutilizado.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

TP_EMIS_NORMAL = '1'
TP_EMIS_EPEC = '2'
TP_EMIS_SVC_RS = '6'
TP_EMIS_SVC_AN = '7'

TP_EMIS_PERMITIDOS_NFE = {
    TP_EMIS_NORMAL: 'Emissão normal',
    TP_EMIS_EPEC: 'EPEC — Contingência',
    TP_EMIS_SVC_RS: 'SVC-RS — Contingência',
    TP_EMIS_SVC_AN: 'SVC-AN — Contingência',
}

TP_EMIS_BLOQUEADOS = {
    '4': 'DPEC (descontinuado)',
    '5': 'FSDA (descontinuado)',
    '9': 'Off-line DFe/NFC-e (rejeição 711 SEFAZ)',
}

PRAZO_CONTINGENCIA_HORAS = 168


class ContingenciaSefazError(RuntimeError):
    """Erro de contingência SEFAZ (registro, emissão ou transmissão)."""


@dataclass(frozen=True)
class StatusContingencia:
    empresa_id: int
    ativa: bool
    tp_emis: str
    motivo: str
    inicio: str | None
    tempo_ativo_horas: float | None
    nfe_pendentes: int


def _empresa_emitente(nfe_saida) -> 'Empresa':
    from apps.fiscal.nfe_emissao.empresa_emitente import resolver_empresa_emitente_nfe

    return resolver_empresa_emitente_nfe(nfe_saida)


def obter_contingencia_ativa(empresa) -> 'ContingenciaSefaz' | None:
    from apps.fiscal.models import ContingenciaSefaz

    return (
        ContingenciaSefaz.objects.filter(empresa=empresa, ativa=True)
        .order_by('-inicio')
        .first()
    )


def registrar_contingencia(empresa, *, motivo: str, tp_emis: str = TP_EMIS_EPEC) -> 'ContingenciaSefaz':
    """Ativa o modo de contingência da empresa. Retorna o registro criado."""
    tp = ''.join(c for c in str(tp_emis) if c.isdigit())[:1] or '1'
    if tp == TP_EMIS_NORMAL:
        raise ContingenciaSefazError(
            'tpEmis=1 não é um modo de contingência. Use 2 (EPEC), 6 (SVC-RS) ou 7 (SVC-AN).',
        )
    if tp in TP_EMIS_BLOQUEADOS:
        raise ContingenciaSefazError(
            f'tpEmis={tp} não é suportado para NF-e modelo 55: {TP_EMIS_BLOQUEADOS[tp]}.',
        )
    if tp not in TP_EMIS_PERMITIDOS_NFE:
        raise ContingenciaSefazError(f'tpEmis={tp} inválido para NF-e.')

    from apps.fiscal.models import ContingenciaSefaz

    with transaction.atomic():
        existente = obter_contingencia_ativa(empresa)
        if existente:
            raise ContingenciaSefazError(
                f'Contingência já ativa desde {existente.inicio:%d/%m/%Y %H:%M} '
                f'({TP_EMIS_PERMITIDOS_NFE.get(existente.tp_emis, existente.tp_emis)}). '
                'Encerre a contingência atual antes de iniciar uma nova.',
            )
        registro = ContingenciaSefaz.objects.create(
            empresa=empresa,
            tp_emis=tp,
            motivo=(motivo or '').strip()[:500],
            inicio=timezone.now(),
            ativa=True,
        )
    logger.warning(
        'CONTINGENCIA_ATIVADA empresa_id=%s tp_emis=%s motivo=%s',
        empresa.pk,
        tp,
        motivo,
    )
    return registro


def encerrar_contingencia(empresa) -> ContingenciaSefaz | None:
    """Encerra a contingência ativa. Retorna o registro encerrado ou None."""
    with transaction.atomic():
        registro = obter_contingencia_ativa(empresa)
        if registro:
            registro.encerrada_em = timezone.now()
            registro.ativa = False
            registro.save(update_fields=['encerrada_em', 'ativa', 'atualizado_em'])
            logger.info('CONTINGENCIA_ENCERRADA empresa_id=%s', empresa.pk)
    return registro


def emitir_em_contingencia(nfe_saida, *, usuario=None) -> dict:
    """Gera o XML assinado da NF-e em contingência (EPEC, tpEmis=2) sem transmitir.

    A chave de acesso é recomputada com o tpEmis de contingência, pois o campo
    compõe a chave oficial da SEFAZ (posições 36-36). O status avança para
    XML_ASSINADO e fica pendente de transmissão via transmitir_pendentes_contingencia.
    """
    from apps.fiscal.models import NFeSaida

    with transaction.atomic():
        nf = NFeSaida.objects.select_for_update().get(pk=nfe_saida.pk)

        empresa = _empresa_emitente(nf)
        registro = obter_contingencia_ativa(empresa)
        if not registro:
            raise ContingenciaSefazError(
                'Nenhuma contingência SEFAZ ativa para a empresa emitente. '
                'Ative a contingência antes de emitir em contingência.',
            )

        if nf.status_emissao_sefaz not in (
            NFeSaida.StatusEmissaoSefaz.NUMERACAO_RESERVADA,
            NFeSaida.StatusEmissaoSefaz.XML_GERADO,
            NFeSaida.StatusEmissaoSefaz.ERRO_TRANSMISSAO,
        ) and not (
            nf.status_emissao_sefaz == NFeSaida.StatusEmissaoSefaz.XML_ASSINADO
            and nf.tipo_emissao != TP_EMIS_NORMAL
        ):
            raise ContingenciaSefazError(
                f'NF-e em status {nf.get_status_emissao_sefaz_display()} não pode entrar em contingência. '
                'Emita em contingência quando a NF estiver com erro de transmissão.',
            )

        if nf.tipo_emissao != TP_EMIS_NORMAL:
            raise ContingenciaSefazError('NF-e já emitida em modo de contingência.')

        if nf.ambiente_emissao != NFeSaida.AmbienteEmissao.HOMOLOGACAO:
            raise ContingenciaSefazError(
                'Emissão em contingência disponível apenas em ambiente de homologação neste módulo.',
            )

        nova_chave = _recomputar_chave_com_tp_emis(nf, registro.tp_emis)
        xml = _gerar_xml_contingencia(nf, tp_emis=registro.tp_emis)

        nf.tipo_emissao = registro.tp_emis
        nf.chave_acesso = nova_chave.chave_44
        nf.digito_verificador = nova_chave.digito_verificador
        nf.xml_assinado = xml
        nf.status_emissao_sefaz = NFeSaida.StatusEmissaoSefaz.XML_ASSINADO
        nf.motivo_autorizacao = (nf.motivo_autorizacao or '') + (
            f' | Contingência: {registro.get_tp_emis_display()} — {registro.motivo}'
        )
        nf.save(
            update_fields=[
                'tipo_emissao',
                'chave_acesso',
                'digito_verificador',
                'xml_assinado',
                'status_emissao_sefaz',
                'motivo_autorizacao',
            ],
        )
        _registrar_evento_contingencia(
            nf,
            tipo='CONTINGENCIA_EPEC_ATIVADA',
            resumo={
                'tp_emis': registro.tp_emis,
                'motivo': registro.motivo,
                'chave_acesso_nova': nova_chave.chave_44,
            },
            observacao=(
                f'Emitida em contingência ({registro.get_tp_emis_display()}). '
                f'Transmitir em até {PRAZO_CONTINGENCIA_HORAS}h.'
            ),
            usuario=usuario,
        )
        logger.warning(
            'CONTINGENCIA_EMITIDA nfe_id=%s tp_emis=%s chave=%s',
            nf.pk,
            registro.tp_emis,
            nova_chave.chave_44,
        )
        return {
            'nfe_id': nf.pk,
            'tp_emis': registro.tp_emis,
            'tp_emis_label': registro.get_tp_emis_display(),
            'chave_acesso': nova_chave.chave_44,
            'prazo_horas': PRAZO_CONTINGENCIA_HORAS,
        }


def transmitir_pendentes_contingencia(empresa, *, usuario=None) -> dict:
    """Transmite as NFs emitidas em contingência ainda não autorizadas.

    Restabelecida a SEFAZ, a NF completa é transmitida na numeração normal.
    Se a SEFAZ ainda estiver fora do ar, a função coleta os erros sem abortar
    as demais NFs e devolve o resumo.
    """
    from apps.fiscal.models import ContingenciaSefaz, NFeSaida

    pendentes = NFeSaida.objects.filter(
        empresa_emitente=empresa,
        tipo_emissao__in=(TP_EMIS_EPEC, TP_EMIS_SVC_RS, TP_EMIS_SVC_AN),
        status_emissao_sefaz__in=(
            NFeSaida.StatusEmissaoSefaz.XML_ASSINADO,
            NFeSaida.StatusEmissaoSefaz.XML_GERADO,
            NFeSaida.StatusEmissaoSefaz.ENVIADA_HOMOLOGACAO,
        ),
    )

    resultados: list[dict] = []
    for nf in pendentes:
        try:
            _transmitir_nf_contingencia(nf, usuario=usuario)
            resultados.append({'nfe_id': nf.pk, 'numero': nf.numero_nfe, 'sucesso': True})
        except Exception as exc:  # noqa: BLE001 — agregar erros por NF
            resultados.append({'nfe_id': nf.pk, 'numero': nf.numero_nfe, 'sucesso': False, 'erro': str(exc)})
            logger.exception('CONTINGENCIA_TRANSMISSAO_FALHOU nfe_id=%s', nf.pk)

    encerradas = not ContingenciaSefaz.objects.filter(empresa=empresa, ativa=True).exists()
    return {
        'empresa_id': empresa.pk,
        'total': len(pendentes),
        'sucesso': [r for r in resultados if r['sucesso']],
        'falhas': [r for r in resultados if not r['sucesso']],
        'contingencia_encerrada': encerradas,
    }


def _recomputar_chave_com_tp_emis(nf, tp_emis: str):
    """Recomputa a chave oficial trocando o tpEmis (composição da chave)."""
    from apps.fiscal.nfe_integracao.nfe_chave_acesso import montar_chave_acesso_nfe

    base = nf.chave_acesso[:43]
    # Posições da chave: cUF(2) aamm(4) cnpj(14) mod(2) serie(3) nnf(9) tpEmis(1) cNF(8)
    # cUF(2) + aamm(4) + CNPJ(14) + mod(2) + serie(3) + nNF(9) = 34 dígitos; tpEmis está na posição 35 (índice 34).
    chave_sem_tpe = base[:34] + base[35:]
    return montar_chave_acesso_nfe(
        cuf=chave_sem_tpe[:2],
        aamm=chave_sem_tpe[2:6],
        cnpj_emitente=chave_sem_tpe[6:20],
        modelo=chave_sem_tpe[20:22],
        serie=chave_sem_tpe[22:25],
        nnf=chave_sem_tpe[25:34],
        tp_emis=tp_emis,
        codigo_numerico=chave_sem_tpe[34:],
    )


def _gerar_xml_contingencia(nf, *, tp_emis: str) -> str:
    """Gera o XML oficial com tpEmis de contingência e assina."""
    from apps.fiscal.nfe_emissao.xml_oficial import montar_tnfe_emissao
    from apps.fiscal.nfe_emissao.xml_serializacao import serializar_tnfe_nfe
    from apps.fiscal.nfe_emissao.assinatura import assinar_xml_nfe
    from apps.fiscal.nfe_integracao.nfe_chave_acesso import ChaveAcessoNFe

    empresa = _empresa_emitente(nf)

    # gerar_xml_oficial_emissao valida a NF para emissão normal; para
    # contingência usamos a montagem direta já validada no fluxo normal e
    # sobrescrevemos o tpEmis no bindings antes de serializar.
    dados = _preparar_dados_emissao_contingencia(nf)
    chave = ChaveAcessoNFe(
        chave_43=nf.chave_acesso[:43],
        digito_verificador=nf.digito_verificador or nf.chave_acesso[-1],
        chave_44=nf.chave_acesso,
        inf_nfe_id=f'NFe{nf.chave_acesso}',
    )
    tp_amb = '2' if nf.ambiente_emissao != 'producao' else '1'

    try:
        tnfe = montar_tnfe_emissao(
            dados,
            nfe_saida=nf,
            chave=chave,
            serie=nf.serie_nfe,
            nnf=nf.numero_nfe,
            codigo_numerico=nf.codigo_numerico,
            tp_amb=tp_amb,
        )
    except Exception as exc:
        raise ContingenciaSefazError(f'Falha ao montar XML de contingência: {exc}') from exc

    tnfe.infNFe.ide.tpEmis = tp_emis
    xml_str = serializar_tnfe_nfe(tnfe)

    try:
        xml_assinado = assinar_xml_nfe(xml_str, empresa, nfe_saida=nf)
    except Exception as exc:
        raise ContingenciaSefazError(f'Falha ao assinar XML de contingência: {exc}') from exc
    return xml_assinado


def _preparar_dados_emissao_contingencia(nf) -> dict:
    from apps.fiscal.nfe_emissao.xml_oficial import _preparar_dados_emissao

    dados = _preparar_dados_emissao(nf, incluir_validacao_emissao=False)
    if dados.get('bloqueado'):
        raise ContingenciaSefazError(dados.get('mensagem') or 'NF-e bloqueada para emissão.')
    if not dados.get('emitente'):
        dados['emitente'] = {}
    return dados


def _transmitir_nf_contingencia(nf, *, usuario=None) -> dict:
    """Transmite uma NF de contingência na numeração normal."""
    from apps.fiscal.models import NFeSaida

    if nf.ambiente_emissao == NFeSaida.AmbienteEmissao.PRODUCAO:
        from apps.fiscal.nfe_emissao.servico_producao import emitir_nfe_producao

        return emitir_nfe_producao(nf, usuario=usuario)
    from apps.fiscal.nfe_emissao.servico import emitir_nfe_homologacao

    return emitir_nfe_homologacao(nf, usuario=usuario)


def _registrar_evento_contingencia(nf, *, tipo: str, resumo: dict, observacao: str, usuario=None) -> None:
    from apps.fiscal.nfe_saida_efeitos import _registrar_evento

    _registrar_evento(
        nf,
        tipo=tipo,
        status_anterior=nf.status_emissao_sefaz or '',
        status_novo=nf.status_emissao_sefaz or '',
        resumo=resumo,
        observacao=observacao,
        usuario=usuario,
    )
