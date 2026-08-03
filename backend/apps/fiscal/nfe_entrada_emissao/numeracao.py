"""Reserva de numeração fiscal NF-e entrada própria.

Decisão de produto (confirmada): usa a **mesma sequência da saída**
(``tipo_operacao=saida`` — mesma série e contador ``nNF``).
Só o documento muda para entrada (``tpNF=0``).
"""

from __future__ import annotations

import logging
import secrets

from django.db import transaction
from django.utils import timezone

from apps.fiscal.models import NFeEntrada, NFeNumeracaoConfiguracao
from apps.fiscal.nfe_emissao.numeracao import (
    NFeNumeracaoError,
    NumeracaoReservada,
    _travar_config_numeracao_nfe_saida,
    obter_config_numeracao,
)
from apps.fiscal.nfe_emissao.serie_fiscal import (
    normalizar_serie_xml,
    serie_para_chave,
    validar_serie_autorizacao_normal,
)
from apps.fiscal.nfe_entrada_emissao.validacao import (
    NFeEntradaEmissaoValidationError,
    validar_rascunho_entrada_propria_emitida,
)
from apps.fiscal.nfe_integracao.nfe_chave_acesso import ChaveAcessoNFe, aamm_da_emissao, montar_chave_acesso_nfe

logger = logging.getLogger(__name__)

MSG_SEM_CONFIG_ENTRADA = (
    'Cadastre numeração NF-e (tipo saída) para a empresa/ambiente. '
    'Entrada própria compartilha a mesma sequência da saída.'
)


def _lock_nfe_entrada(nf_id: int) -> NFeEntrada:
    return NFeEntrada.objects.select_for_update().get(pk=nf_id)


def _serie_digits(serie: str) -> str:
    return normalizar_serie_xml(serie)


def _nnf_str(numero: int) -> str:
    return str(int(numero))[:9].zfill(9)


def _codigo_numerico() -> str:
    return f'{secrets.randbelow(100_000_000):08d}'


def _uf_ibge(uf: str) -> str:
    from apps.fiscal.nfe_saida_preview import UF_IBGE

    return UF_IBGE.get((uf or 'SP').strip().upper()[:2], '35')


def obter_config_numeracao_entrada(
    empresa_id: int,
    *,
    ambiente: str = NFeNumeracaoConfiguracao.Ambiente.HOMOLOGACAO,
    modelo: str = '55',
) -> NFeNumeracaoConfiguracao:
    """Resolve a config de numeração compartilhada com a saída."""
    try:
        return obter_config_numeracao(empresa_id, ambiente=ambiente, modelo=modelo)
    except NFeNumeracaoError as exc:
        raise NFeNumeracaoError(MSG_SEM_CONFIG_ENTRADA) from exc


@transaction.atomic
def reservar_numeracao_nfe_entrada(
    nf_entrada: NFeEntrada,
    *,
    usuario=None,
) -> NumeracaoReservada:
    nf = _lock_nfe_entrada(nf_entrada.pk)

    if nf.tipo_origem != NFeEntrada.TipoOrigem.ENTRADA_PROPRIA_EMITIDA:
        raise NFeNumeracaoError('Reserva de numeração disponível apenas para entrada própria emitida.')

    ambiente = nf.ambiente_emissao or NFeEntrada.AmbienteEmissao.HOMOLOGACAO
    if ambiente == NFeEntrada.AmbienteEmissao.PRODUCAO:
        from apps.fiscal.nfe_emissao.config_producao import exigir_producao_habilitada

        try:
            exigir_producao_habilitada()
        except PermissionError as exc:
            raise NFeNumeracaoError(str(exc)) from exc

    try:
        validar_rascunho_entrada_propria_emitida(nf)
    except NFeEntradaEmissaoValidationError as exc:
        raise NFeNumeracaoError(str(exc)) from exc

    if nf.numero_nfe and nf.serie_nfe and nf.chave_acesso:
        logger.info(
            'NUMERACAO_ENTRADA_JA_RESERVADA nf_entrada_id=%s serie=%s numero=%s chave=%s',
            nf.pk,
            nf.serie_nfe,
            nf.numero_nfe,
            nf.chave_acesso,
        )
        chave_44 = nf.chave_acesso
        chave = ChaveAcessoNFe(
            chave_43=chave_44[:43],
            digito_verificador=nf.digito_verificador or chave_44[-1],
            chave_44=chave_44,
            inf_nfe_id=f'NFe{chave_44}',
        )
        return NumeracaoReservada(
            serie=nf.serie_nfe,
            nnf=nf.numero_nfe,
            codigo_numerico=nf.codigo_numerico or '',
            chave=chave,
            ambiente=ambiente,
            config_id=0,
        )

    empresa = nf.empresa_emitente
    if not empresa:
        raise NFeNumeracaoError('Empresa emitente obrigatória para reservar numeração.')

    try:
        cfg = _travar_config_numeracao_nfe_saida(
            empresa.pk,
            ambiente=ambiente,
            serie_nfe=nf.serie_nfe or None,
        )
    except NFeNumeracaoError as exc:
        raise NFeNumeracaoError(MSG_SEM_CONFIG_ENTRADA) from exc

    # Entrada própria consome o contador da saída (sem pool de descarte de NFeSaida).
    nnf_int = int(cfg.proximo_numero)
    if nnf_int < 1 or nnf_int > 999_999_999:
        raise NFeNumeracaoError('Próximo número fiscal fora do intervalo permitido.')

    if ambiente != NFeEntrada.AmbienteEmissao.PRODUCAO:
        validar_serie_autorizacao_normal(cfg.serie)
    serie = _serie_digits(cfg.serie)
    serie_chave = serie_para_chave(cfg.serie)
    nnf = _nnf_str(nnf_int)
    c_nf = _codigo_numerico()
    cnpj = ''.join(c for c in (empresa.cnpj or '') if c.isdigit())[:14]
    if len(cnpj) != 14:
        raise NFeNumeracaoError('CNPJ da empresa emitente inválido para chave de acesso.')

    chave = montar_chave_acesso_nfe(
        cuf=_uf_ibge(empresa.uf),
        aamm=aamm_da_emissao(),
        cnpj_emitente=cnpj,
        modelo=cfg.modelo_documento or '55',
        serie=serie_chave,
        nnf=nnf,
        tp_emis='1',
        codigo_numerico=c_nf,
    )

    nf.ambiente_emissao = ambiente
    nf.serie_nfe = serie
    nf.numero_nfe = nnf
    nf.codigo_numerico = c_nf
    nf.chave_acesso = chave.chave_44
    nf.digito_verificador = chave.digito_verificador
    nf.numero_reservado_em = timezone.now()
    nf.numero_reservado_por = usuario if usuario and getattr(usuario, 'is_authenticated', False) else None
    nf.status_emissao_sefaz = NFeEntrada.StatusEmissaoSefaz.NUMERACAO_RESERVADA
    nf.save(
        update_fields=[
            'ambiente_emissao',
            'serie_nfe',
            'numero_nfe',
            'codigo_numerico',
            'chave_acesso',
            'digito_verificador',
            'numero_reservado_em',
            'numero_reservado_por',
            'status_emissao_sefaz',
        ],
    )

    cfg.proximo_numero = nnf_int + 1
    cfg.ultimo_numero_reservado = nnf_int
    cfg.save(update_fields=['proximo_numero', 'ultimo_numero_reservado', 'atualizado_em'])

    logger.info(
        'NUMERACAO_ENTRADA_RESERVADA_SEQ_SAIDA nf_entrada_id=%s cfg_id=%s serie=%s numero=%s ambiente=%s',
        nf.pk,
        cfg.pk,
        serie,
        nnf,
        ambiente,
    )

    return NumeracaoReservada(
        serie=serie,
        nnf=nnf,
        codigo_numerico=c_nf,
        chave=chave,
        ambiente=ambiente,
        config_id=cfg.pk,
    )
