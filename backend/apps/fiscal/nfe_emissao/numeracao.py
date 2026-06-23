"""Reserva de numeração fiscal NF-e por empresa/ambiente."""

from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass
from django.db import transaction
from django.utils import timezone

from apps.fiscal.models import NFeNumeracaoConfiguracao, NFeNumeracaoNumeroLiberado, NFeSaida
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


def _configs_numeracao_saida_qs(
    empresa_id: int,
    *,
    ambiente: str,
    modelo: str = '55',
):
    return NFeNumeracaoConfiguracao.objects.filter(
        empresa_id=empresa_id,
        ambiente=ambiente,
        modelo_documento=modelo,
        tipo_operacao=NFeNumeracaoConfiguracao.TipoOperacao.SAIDA,
        ativo=True,
    )


def _config_por_serie(configs, serie: str) -> NFeNumeracaoConfiguracao | None:
    serie_norm = _serie_digits(serie)
    for cfg in configs:
        if _serie_digits(cfg.serie) == serie_norm:
            return cfg
    return None


def resolver_config_numeracao_nfe_saida(
    empresa_id: int,
    *,
    ambiente: str,
    modelo: str = '55',
    serie_nfe: str | None = None,
) -> NFeNumeracaoConfiguracao:
    """
    Resolve a configuração de numeração por empresa/ambiente/modelo/série.
    Sem série na NF-e: prioriza config com número no pool (menor nNF primeiro).
    """
    configs = list(_configs_numeracao_saida_qs(empresa_id, ambiente=ambiente, modelo=modelo).order_by('serie'))
    if not configs:
        raise NFeNumeracaoError(
            f'Configuração de numeração NF-e não encontrada para empresa #{empresa_id} '
            f'(ambiente={ambiente}, modelo={modelo}). Cadastre em Fiscal / NF-e / Numeração.',
        )

    if serie_nfe:
        cfg = _config_por_serie(configs, serie_nfe)
        if cfg is None:
            raise NFeNumeracaoError(
                f'Configuração de numeração não encontrada para empresa #{empresa_id}, '
                f'série {_serie_digits(serie_nfe)}, ambiente {ambiente}.',
            )
        return cfg

    if len(configs) == 1:
        return configs[0]

    cfg_ids = [c.pk for c in configs]
    pool_row = (
        NFeNumeracaoNumeroLiberado.objects.filter(
            configuracao_id__in=cfg_ids,
            consumido_em__isnull=True,
        )
        .order_by('numero', 'pk')
        .select_related('configuracao')
        .first()
    )
    if pool_row is not None:
        return pool_row.configuracao

    return configs[0]


def obter_config_numeracao(
    empresa_id: int,
    *,
    ambiente: str = NFeNumeracaoConfiguracao.Ambiente.HOMOLOGACAO,
    modelo: str = '55',
    serie: str | None = None,
) -> NFeNumeracaoConfiguracao:
    if serie is not None:
        cfg = resolver_config_numeracao_nfe_saida(
            empresa_id,
            ambiente=ambiente,
            modelo=modelo,
            serie_nfe=serie,
        )
    else:
        cfg = resolver_config_numeracao_nfe_saida(
            empresa_id,
            ambiente=ambiente,
            modelo=modelo,
        )
    if ambiente != 'producao':
        try:
            validar_serie_autorizacao_normal(cfg.serie)
        except Exception as exc:
            raise NFeNumeracaoError(str(exc)) from exc
    return cfg


def _travar_config_numeracao_nfe_saida(
    empresa_id: int,
    *,
    ambiente: str,
    modelo: str = '55',
    serie_nfe: str | None = None,
) -> NFeNumeracaoConfiguracao:
    cfg = resolver_config_numeracao_nfe_saida(
        empresa_id,
        ambiente=ambiente,
        modelo=modelo,
        serie_nfe=serie_nfe,
    )
    locked = (
        NFeNumeracaoConfiguracao.objects.select_for_update()
        .filter(pk=cfg.pk)
        .first()
    )
    if locked is None:
        raise NFeNumeracaoError('Configuração de numeração indisponível.')
    return locked


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
    cfg = _travar_config_numeracao_nfe_saida(
        empresa.pk,
        ambiente=ambiente,
        serie_nfe=nf.serie_nfe or None,
    )

    from apps.fiscal.nfe_emissao.numeracao_liberacao import reservar_numero_liberado_disponivel

    nnf_int, numero_liberado = reservar_numero_liberado_disponivel(cfg, nfe_saida=nf, usuario=usuario)
    if numero_liberado is not None:
        logger.info(
            'NUMERACAO_POOL_CONSUMIDA nfe_id=%s cfg_id=%s numero=%s pool_id=%s',
            nf.pk,
            cfg.pk,
            nnf_int,
            numero_liberado.pk,
        )
    if numero_liberado is None and (nnf_int < 1 or nnf_int > 999_999_999):
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

    cfg.ultimo_numero_reservado = nnf_int
    if numero_liberado is None:
        cfg.proximo_numero = nnf_int + 1
    cfg.save(update_fields=['proximo_numero', 'ultimo_numero_reservado', 'atualizado_em'])

    resumo_evento: dict = {
        'serie': serie,
        'numero_nfe': nnf,
        'chave_acesso': chave.chave_44,
        'ambiente': ambiente,
    }
    if numero_liberado is not None:
        resumo_evento['numero_reutilizado'] = True
        resumo_evento['nfe_saida_origem_id'] = numero_liberado.nfe_saida_origem_id
        resumo_evento['reutilizacao_id'] = numero_liberado.pk
    _registrar_evento(
        nf,
        tipo='NUMERACAO_RESERVADA',
        status_novo=nf.status_emissao_sefaz,
        resumo=resumo_evento,
        observacao=(
            f'Numeração reservada: série {serie}, nNF {nnf}'
            + (' (reutilizada de descarte local).' if numero_liberado else '.')
        ),
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
