"""Correção de série homologação após rejeição SEFAZ cStat 266."""

from __future__ import annotations

import logging
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.fiscal.models import NFeSaida
from apps.fiscal.nfe_emissao.empresa_emitente import resolver_empresa_emitente_nfe
from apps.fiscal.nfe_emissao.numeracao import (
    NFeNumeracaoError,
    _codigo_numerico,
    _nnf_str,
    _uf_ibge,
    obter_config_numeracao,
)
from apps.fiscal.nfe_emissao.serie_fiscal import (
    normalizar_serie_xml,
    serie_para_chave,
    validar_serie_autorizacao_normal,
)
from apps.fiscal.nfe_integracao.nfe_chave_acesso import aamm_da_emissao, montar_chave_acesso_nfe
from apps.fiscal.nfe_saida_efeitos import _lock_nfe_saida, _registrar_evento

logger = logging.getLogger(__name__)

CSTAT_SERIE_INVALIDA = '266'


class NFeCorrigirSerieHomologacaoError(ValueError):
    pass


def pode_corrigir_serie_homologacao(nf: NFeSaida) -> tuple[bool, str]:
    if nf.ambiente_emissao == NFeSaida.AmbienteEmissao.PRODUCAO:
        return False, 'Correção disponível apenas em homologação.'
    if nf.status_emissao_sefaz == NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO:
        return False, 'NF-e já autorizada em homologação.'
    if (nf.protocolo_autorizacao or '').strip():
        return False, 'NF-e possui protocolo de autorização.'
    if (nf.xml_autorizado or '').strip():
        return False, 'NF-e possui XML autorizado.'
    if nf.status in ('AUTORIZADA', 'CANCELADA', 'AUTORIZADA_HOMOLOGACAO'):
        return False, f'Status {nf.status} não permite correção de série.'
    cstat = (nf.cstat_autorizacao or '').strip()
    status_ok = nf.status_emissao_sefaz in (
        NFeSaida.StatusEmissaoSefaz.REJEITADA_HOMOLOGACAO,
        NFeSaida.StatusEmissaoSefaz.ERRO_TRANSMISSAO,
        NFeSaida.StatusEmissaoSefaz.NUMERACAO_RESERVADA,
        NFeSaida.StatusEmissaoSefaz.XML_GERADO,
        NFeSaida.StatusEmissaoSefaz.XML_ASSINADO,
        NFeSaida.StatusEmissaoSefaz.ENVIADA_HOMOLOGACAO,
    )
    if not status_ok and cstat != CSTAT_SERIE_INVALIDA:
        return False, 'Correção de série permitida após rejeição 266 ou erro de transmissão.'
    if cstat and cstat not in (CSTAT_SERIE_INVALIDA, '', '104'):
        if nf.status_emissao_sefaz != NFeSaida.StatusEmissaoSefaz.ERRO_TRANSMISSAO:
            return False, f'cStat {cstat} não é correção de série (266).'
    return True, ''


def _invalidar_xmls_emissao(nf: NFeSaida) -> None:
    nf.xml_nfe_gerado = ''
    nf.xml_assinado = ''
    nf.xml_envio = ''
    nf.xml_envio_lote = ''
    nf.xml_retorno = ''
    nf.xml_retorno_lote = ''
    nf.xml_protocolo = ''
    nf.cstat_lote = ''
    nf.xmotivo_lote = ''
    nf.recibo_lote = ''
    nf.cstat_autorizacao = ''
    nf.motivo_autorizacao = ''


@transaction.atomic
def corrigir_serie_homologacao_nfe(nfe_saida: NFeSaida, *, usuario=None) -> dict[str, Any]:
    nf = _lock_nfe_saida(nfe_saida.pk)
    ok, msg = pode_corrigir_serie_homologacao(nf)
    if not ok:
        raise NFeCorrigirSerieHomologacaoError(msg)

    empresa = resolver_empresa_emitente_nfe(nf)
    try:
        cfg = obter_config_numeracao(empresa.pk, ambiente='homologacao')
    except NFeNumeracaoError as exc:
        raise NFeCorrigirSerieHomologacaoError(str(exc)) from exc

    try:
        validar_serie_autorizacao_normal(cfg.serie)
    except Exception as exc:
        raise NFeCorrigirSerieHomologacaoError(str(exc)) from exc

    serie_anterior = nf.serie_nfe or ''
    chave_anterior = nf.chave_acesso or ''
    numero_anterior = nf.numero_nfe or ''

    serie_nova = normalizar_serie_xml(cfg.serie)
    if numero_anterior:
        nnf = numero_anterior
    else:
        nnf = _nnf_str(int(cfg.proximo_numero))

    c_nf = _codigo_numerico()
    cnpj = ''.join(c for c in (empresa.cnpj or '') if c.isdigit())[:14]
    if len(cnpj) != 14:
        raise NFeCorrigirSerieHomologacaoError('CNPJ da empresa emitente inválido.')

    chave = montar_chave_acesso_nfe(
        cuf=_uf_ibge(empresa.uf),
        aamm=aamm_da_emissao(),
        cnpj_emitente=cnpj,
        modelo=cfg.modelo_documento or '55',
        serie=serie_para_chave(serie_nova),
        nnf=nnf,
        tp_emis='1',
        codigo_numerico=c_nf,
    )

    _invalidar_xmls_emissao(nf)
    nf.empresa_emitente = empresa
    nf.ambiente_emissao = NFeSaida.AmbienteEmissao.HOMOLOGACAO
    nf.serie_nfe = serie_nova
    nf.numero_nfe = nnf
    nf.codigo_numerico = c_nf
    nf.chave_acesso = chave.chave_44
    nf.digito_verificador = chave.digito_verificador
    nf.protocolo_autorizacao = ''
    nf.xml_autorizado = ''
    nf.autorizada_em = None
    nf.status_emissao_sefaz = NFeSaida.StatusEmissaoSefaz.NUMERACAO_RESERVADA
    nf.numero_reservado_em = timezone.now()
    nf.numero_reservado_por = usuario if usuario and getattr(usuario, 'is_authenticated', False) else None

    nf.save(
        update_fields=[
            'empresa_emitente',
            'ambiente_emissao',
            'serie_nfe',
            'numero_nfe',
            'codigo_numerico',
            'chave_acesso',
            'digito_verificador',
            'protocolo_autorizacao',
            'xml_autorizado',
            'autorizada_em',
            'status_emissao_sefaz',
            'numero_reservado_em',
            'numero_reservado_por',
            'xml_nfe_gerado',
            'xml_assinado',
            'xml_envio',
            'xml_envio_lote',
            'xml_retorno',
            'xml_retorno_lote',
            'xml_protocolo',
            'cstat_lote',
            'xmotivo_lote',
            'recibo_lote',
            'cstat_autorizacao',
            'motivo_autorizacao',
        ],
    )

    _registrar_evento(
        nf,
        tipo='SERIE_HOMOLOGACAO_CORRIGIDA',
        status_novo=nf.status_emissao_sefaz,
        resumo={
            'serie_anterior': serie_anterior,
            'serie_nova': serie_nova,
            'chave_anterior': chave_anterior,
            'chave_nova': chave.chave_44,
            'numero_nfe': nnf,
            'cstat_rejeicao_anterior': CSTAT_SERIE_INVALIDA,
        },
        observacao=(
            f'Série homologação corrigida: {serie_anterior or "—"} → {serie_nova}. '
            f'Chave recalculada. XMLs anteriores invalidados.'
        ),
        usuario=usuario,
    )

    logger.info(
        'SERIE_HOMOLOGACAO_CORRIGIDA nfe_id=%s serie %s→%s chave %s→%s',
        nf.pk,
        serie_anterior,
        serie_nova,
        chave_anterior,
        chave.chave_44,
    )

    return {
        'nfe_saida_id': nf.pk,
        'serie_anterior': serie_anterior,
        'serie_nova': serie_nova,
        'chave_anterior': chave_anterior,
        'chave_nova': chave.chave_44,
        'numero_nfe': nnf,
        'status_emissao_sefaz': nf.status_emissao_sefaz,
    }
