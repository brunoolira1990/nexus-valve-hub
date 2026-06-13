"""Reserva de numeração fiscal NF-e por empresa/ambiente."""

from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass
from django.db import transaction
from django.utils import timezone

from apps.fiscal.models import NFeNumeracaoConfiguracao, NFeSaida
from apps.fiscal.nfe_emissao.empresa_emitente import resolver_empresa_emitente_nfe
from apps.fiscal.nfe_emissao.serie_fiscal import (
    normalizar_serie_xml,
    serie_para_chave,
    validar_serie_autorizacao_normal,
)
from apps.fiscal.nfe_integracao.nfe_chave_acesso import ChaveAcessoNFe, aamm_da_emissao, montar_chave_acesso_nfe
from apps.fiscal.nfe_saida_efeitos import _lock_nfe_saida, _registrar_evento

logger = logging.getLogger(__name__)


class NFeNumeracaoError(ValueError):
    pass


@dataclass(frozen=True)
class NumeracaoReservada:
    serie: str
    nnf: str
    codigo_numerico: str
    chave: ChaveAcessoNFe
    ambiente: str
    config_id: int


def _serie_digits(serie: str) -> str:
    """Série para persistência/XML (ex.: 0, 1)."""
    return normalizar_serie_xml(serie)


def _nnf_str(numero: int) -> str:
    return str(int(numero))[:9].zfill(9)


def _codigo_numerico() -> str:
    return f'{secrets.randbelow(100_000_000):08d}'


def obter_config_numeracao(
    empresa_id: int,
    *,
    ambiente: str = NFeNumeracaoConfiguracao.Ambiente.HOMOLOGACAO,
    modelo: str = '55',
) -> NFeNumeracaoConfiguracao:
    cfg = (
        NFeNumeracaoConfiguracao.objects.filter(
            empresa_id=empresa_id,
            ambiente=ambiente,
            modelo_documento=modelo,
            tipo_operacao=NFeNumeracaoConfiguracao.TipoOperacao.SAIDA,
            ativo=True,
        )
        .order_by('serie')
        .first()
    )
    if not cfg:
        raise NFeNumeracaoError(
            f'Configuração de numeração NF-e não encontrada para empresa #{empresa_id} '
            f'(ambiente={ambiente}, modelo={modelo}). Cadastre em Fiscal / NF-e / Numeração.',
        )
    if ambiente != 'producao':
        try:
            validar_serie_autorizacao_normal(cfg.serie)
        except Exception as exc:
            raise NFeNumeracaoError(str(exc)) from exc
    return cfg


@transaction.atomic
def reservar_numeracao_nfe(
    nfe_saida: NFeSaida,
    *,
    ambiente: str = NFeSaida.AmbienteEmissao.HOMOLOGACAO,
    usuario=None,
) -> NumeracaoReservada:
    if ambiente == NFeSaida.AmbienteEmissao.PRODUCAO:
        from apps.fiscal.nfe_emissao.config_producao import exigir_producao_habilitada

        try:
            exigir_producao_habilitada()
        except PermissionError as exc:
            raise NFeNumeracaoError(str(exc)) from exc

    nf = _lock_nfe_saida(nfe_saida.pk)
    if nf.numero_nfe and nf.serie_nfe and nf.chave_acesso:
        logger.info(
            'NUMERACAO_JA_RESERVADA nfe_id=%s serie=%s numero=%s chave=%s',
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
            ambiente=nf.ambiente_emissao or ambiente,
            config_id=0,
        )

    empresa = resolver_empresa_emitente_nfe(nf)
    cfg = (
        NFeNumeracaoConfiguracao.objects.select_for_update()
        .filter(pk=obter_config_numeracao(empresa.pk, ambiente=ambiente).pk)
        .first()
    )
    if not cfg:
        raise NFeNumeracaoError('Configuração de numeração indisponível.')

    nnf_int = int(cfg.proximo_numero)
    if nnf_int < 1 or nnf_int > 999_999_999:
        raise NFeNumeracaoError('Próximo número fiscal fora do intervalo permitido.')

    if ambiente != NFeSaida.AmbienteEmissao.PRODUCAO:
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

    nf.empresa_emitente = empresa
    nf.ambiente_emissao = ambiente
    nf.serie_nfe = serie
    nf.numero_nfe = nnf
    nf.codigo_numerico = c_nf
    nf.chave_acesso = chave.chave_44
    nf.digito_verificador = chave.digito_verificador
    nf.numero_reservado_em = timezone.now()
    nf.numero_reservado_por = usuario if usuario and getattr(usuario, 'is_authenticated', False) else None
    nf.status_emissao_sefaz = NFeSaida.StatusEmissaoSefaz.NUMERACAO_RESERVADA
    nf.save(
        update_fields=[
            'empresa_emitente',
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

    _registrar_evento(
        nf,
        tipo='NUMERACAO_RESERVADA',
        status_novo=nf.status_emissao_sefaz,
        resumo={
            'serie': serie,
            'numero_nfe': nnf,
            'chave_acesso': chave.chave_44,
            'ambiente': ambiente,
        },
        observacao=f'Numeração reservada: série {serie}, nNF {nnf}.',
        usuario=usuario,
    )
    return NumeracaoReservada(
        serie=serie,
        nnf=nnf,
        codigo_numerico=c_nf,
        chave=chave,
        ambiente=ambiente,
        config_id=cfg.pk,
    )


def _uf_ibge(uf: str) -> str:
    from apps.fiscal.nfe_saida_preview import UF_IBGE

    return UF_IBGE.get((uf or 'SP').strip().upper()[:2], '35')
