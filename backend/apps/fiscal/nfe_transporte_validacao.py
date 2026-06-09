"""Validação de coerência — transporte NF-e Saída (conferência / XML)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from apps.fiscal.models import NFeSaida

MSG_MOD9_INCOERENTE = (
    'Modalidade 9 — Sem ocorrência de transporte não permite transportadora, volumes ou pesos '
    'informados. Altere a modalidade do frete ou limpe os dados de transporte.'
)
MSG_MOD9_COM_TRANSPORTADORA = (
    'Transportadora informada, mas modalidade do frete está como sem ocorrência de transporte.'
)
MSG_MOD9_COM_VOLUMES = (
    'Volumes/pesos informados exigem modalidade de frete diferente de 9.'
)
MSG_PLACA_SEM_UF = 'Informe a UF do veículo quando houver placa.'
MSG_UF_SEM_PLACA = 'Informe a placa do veículo quando houver UF do veículo.'


def _text(val: Any) -> str:
    return (str(val) if val is not None else '').strip()


def _dec(val: Any) -> Decimal:
    if val is None or val == '':
        return Decimal('0')
    try:
        return Decimal(str(val))
    except Exception:
        return Decimal('0')


def _tem_dados_transporte_fisico(nf: NFeSaida) -> bool:
    return (
        bool(nf.transportadora_id)
        or int(nf.quantidade_volumes or 0) > 0
        or _dec(nf.peso_bruto) > 0
        or _dec(nf.peso_liquido) > 0
        or _dec(nf.valor_frete) > 0
        or bool(_text(nf.placa_veiculo))
        or bool(_text(nf.uf_veiculo))
        or bool(_text(nf.especie_volumes))
        or bool(_text(nf.marca_volumes))
        or bool(_text(nf.numeracao_volumes))
    )


def validar_coerencia_transporte_nfe(nf: NFeSaida) -> list[dict[str, str]]:
    """
    Retorna lista de {tipo, codigo, mensagem} para grupo transporte.
    tipo: PENDENCIA | ALERTA | INFO
    """
    mod = _text(nf.modalidade_frete) or '9'
    out: list[dict[str, str]] = []

    has_transp = bool(nf.transportadora_id)
    has_vol = int(nf.quantidade_volumes or 0) > 0
    has_peso = _dec(nf.peso_bruto) > 0 or _dec(nf.peso_liquido) > 0
    has_frete = _dec(nf.valor_frete) > 0
    placa = _text(nf.placa_veiculo)
    uf_veic = _text(nf.uf_veiculo)
    has_vol_meta = bool(
        _text(nf.especie_volumes) or _text(nf.marca_volumes) or _text(nf.numeracao_volumes),
    )

    if mod == '9':
        if has_transp or has_vol or has_peso or has_frete or placa or uf_veic or has_vol_meta:
            out.append(
                {
                    'tipo': 'PENDENCIA',
                    'codigo': 'TRANSPORTE_MOD9_INCOERENTE',
                    'mensagem': MSG_MOD9_INCOERENTE,
                },
            )
            if has_transp:
                out.append(
                    {
                        'tipo': 'PENDENCIA',
                        'codigo': 'TRANSPORTE_MOD9_COM_TRANSPORTADORA',
                        'mensagem': MSG_MOD9_COM_TRANSPORTADORA,
                    },
                )
            if has_vol or has_peso or has_vol_meta:
                out.append(
                    {
                        'tipo': 'PENDENCIA',
                        'codigo': 'TRANSPORTE_MOD9_COM_VOLUMES',
                        'mensagem': MSG_MOD9_COM_VOLUMES,
                    },
                )
    else:
        if placa and not uf_veic:
            out.append(
                {
                    'tipo': 'PENDENCIA',
                    'codigo': 'TRANSPORTE_PLACA_SEM_UF',
                    'mensagem': MSG_PLACA_SEM_UF,
                },
            )
        if uf_veic and not placa:
            out.append(
                {
                    'tipo': 'PENDENCIA',
                    'codigo': 'TRANSPORTE_UF_SEM_PLACA',
                    'mensagem': MSG_UF_SEM_PLACA,
                },
            )
        if not has_transp:
            out.append(
                {
                    'tipo': 'ALERTA',
                    'codigo': 'TRANSPORTE_SEM_TRANSPORTADORA',
                    'mensagem': 'Modalidade de frete informada sem transportadora cadastrada.',
                },
            )
        if mod not in ('9', '') and not has_vol and not has_peso and not has_vol_meta:
            out.append(
                {
                    'tipo': 'ALERTA',
                    'codigo': 'TRANSPORTE_SEM_VOLUMES',
                    'mensagem': 'Volumes ou pesos não informados — recomendado preencher para o DANFE.',
                },
            )

    return out
