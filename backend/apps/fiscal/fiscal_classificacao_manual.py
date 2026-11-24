"""Classificação fiscal manual por item da conferência de entrada.

Sobrepõe o XML da NF-e com os campos ``*_efetivo`` do item, produz um snapshot
comparativo (XML x efetivo) para preview e grava a trilha de auditoria em
``ItemConferenciaFiscalOverride``. Não movimenta estoque nem persiste custo.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from django.db import transaction

from apps.fiscal.models import ItemConferenciaFiscalOverride, ItemNFeEntradaConferencia
from apps.fiscal.services.imposto_item_xml import extrair_tributos_item
from apps.regras_fiscais.entrada_fiscal import (
    CAMPOS_EFETIVOS_FISCAIS,
    _montar_impostos_nf,
    aplicar_overrides_fiscais_entrada,
    avaliar_item_entrada_fiscal,
    carregar_regras_fiscais_entrada_ativas,
    fmt_valor_efetivo,
    montar_contexto_fiscal_entrada,
    valores_efetivos_iguais,
)


class AjusteFiscalErro(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


def _dec(valor: Any, default: str = '0') -> Decimal:
    if valor in (None, ''):
        return Decimal(default)
    try:
        return Decimal(str(valor))
    except (InvalidOperation, ValueError):
        return Decimal(default)


def _valor_na_fonte(campo, trib: dict[str, Any], prod: dict[str, Any]) -> Any:
    fonte = prod if campo.destino == 'produto' else trib
    return fonte.get(campo.chave)


def _fontes_efetivas(item: ItemNFeEntradaConferencia):
    prod_xml = item.item_nfe_historico.prod_json or {}
    trib_xml = extrair_tributos_item(prod_xml, item.item_nfe_historico.imposto_json or {})
    trib_ef, prod_ef, _ = aplicar_overrides_fiscais_entrada(item, trib_xml, prod_xml)
    return trib_xml, prod_xml, trib_ef, prod_ef


def _snapshot_regra(resultado: dict[str, Any]) -> dict[str, Any]:
    divergencias = resultado.get('divergencias') or []
    return {
        'regra_id': resultado.get('regra_id'),
        'regra_codigo': resultado.get('regra_codigo') or '',
        'regra_nome': resultado.get('regra_nome') or '',
        'status_fiscal': resultado.get('status') or '',
        'total_divergencias': len(divergencias),
        'campos_divergentes': [d.get('campo') for d in divergencias if d.get('campo')],
    }


def montar_diferencas_fiscais(item: ItemNFeEntradaConferencia) -> list[dict[str, Any]]:
    trib_xml, prod_xml, trib_ef, prod_ef = _fontes_efetivas(item)
    diferencas: list[dict[str, Any]] = []
    for campo in CAMPOS_EFETIVOS_FISCAIS:
        valor_xml = _valor_na_fonte(campo, trib_xml, prod_xml)
        valor_efetivo = _valor_na_fonte(campo, trib_ef, prod_ef)
        if valores_efetivos_iguais(valor_xml, valor_efetivo, campo.tipo):
            continue
        diferenca = ''
        if campo.tipo == 'decimal':
            diferenca = f'{_dec(valor_efetivo) - _dec(valor_xml)}'
        diferencas.append({
            'campo_modelo': campo.campo_modelo,
            'campo': campo.chave,
            'rotulo': campo.label,
            'valor_xml': fmt_valor_efetivo(valor_xml, campo.tipo),
            'valor_efetivo': fmt_valor_efetivo(valor_efetivo, campo.tipo),
            'diferenca': diferenca,
            'origem': 'OVERRIDE_MANUAL',
        })
    return diferencas


def montar_snapshot_custo_efetivo(
    item: ItemNFeEntradaConferencia,
    trib_efetivo: dict[str, Any],
) -> dict[str, Any]:
    quantidade = item.quantidade_nf or Decimal('0')
    mercadoria = item.valor_total_nf or Decimal('0')
    ipi = _dec(trib_efetivo.get('valor_ipi'))
    icms_st = _dec(trib_efetivo.get('valor_icms_st'))
    fcp = _dec(trib_efetivo.get('valor_fcp'))
    fcp_st = _dec(trib_efetivo.get('valor_fcp_st'))
    custo_bruto = mercadoria + ipi + icms_st + fcp + fcp_st
    icms = _dec(trib_efetivo.get('valor_icms'))
    pis = _dec(trib_efetivo.get('valor_pis'))
    cofins = _dec(trib_efetivo.get('valor_cofins'))

    def unitario(valor: Decimal) -> str:
        if not quantidade:
            return ''
        return str((valor / quantidade).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP))

    return {
        'quantidade_nf': str(quantidade),
        'valor_mercadoria': str(mercadoria),
        'componentes': {
            'ipi': str(ipi),
            'icms_st': str(icms_st),
            'fcp': str(fcp),
            'fcp_st': str(fcp_st),
        },
        'creditos_fiscais_potenciais': {
            'icms': str(icms),
            'pis': str(pis),
            'cofins': str(cofins),
        },
        'custo_bruto': str(custo_bruto),
        'custo_unitario_mercadoria': unitario(mercadoria),
        'custo_unitario_base': unitario(custo_bruto),
        'base_media_ponderada': {
            'quantidade': str(quantidade),
            'custo_unitario': unitario(custo_bruto),
        },
        'somente_leitura': True,
        'observacao': (
            'Snapshot informativo para custo contábil/média ponderada. '
            'Não persiste custo nem movimenta estoque.'
        ),
    }


def recalcular_tributos_item_efetivos(
    item: ItemNFeEntradaConferencia,
    contexto,
    regras,
) -> dict[str, Any]:
    prod_xml = item.item_nfe_historico.prod_json or {}
    trib_xml = extrair_tributos_item(prod_xml, item.item_nfe_historico.imposto_json or {})
    trib_efetivo, prod_efetivo, ajustes = aplicar_overrides_fiscais_entrada(
        item,
        trib_xml,
        prod_xml,
    )
    resultado = avaliar_item_entrada_fiscal(item, contexto, regras)
    return {
        'item_id': item.id,
        'conferencia_id': item.conferencia_id,
        'ncm_xml': str(prod_xml.get('NCM') or '').strip(),
        'ncm_efetivo': str(prod_efetivo.get('NCM') or '').strip(),
        'cfop_entrada_xml': str(prod_xml.get('CFOP') or '').strip(),
        'cfop_entrada_efetivo': str(prod_efetivo.get('CFOP') or '').strip(),
        'impostos_xml': _montar_impostos_nf(trib_xml),
        'impostos_efetivos': resultado.get('impostos_nf') or {},
        'impostos_esperados': resultado.get('impostos_esperados') or {},
        'diferencas': montar_diferencas_fiscais(item),
        'ajustes_ativos': ajustes,
        'total_ajustes': len(ajustes),
        'status_fiscal': resultado.get('status') or '',
        'regra': {
            'id': resultado.get('regra_id'),
            'codigo': resultado.get('regra_codigo') or '',
            'nome': resultado.get('regra_nome') or '',
            'descricao_cenario': resultado.get('descricao_cenario') or '',
        },
        'divergencias': resultado.get('divergencias') or [],
        'custo_contabil': montar_snapshot_custo_efetivo(item, trib_efetivo),
        'estoque_ja_aplicado': item.estoque_aplicado_em is not None,
        'motivo_ajuste_fiscal': item.motivo_ajuste_fiscal or '',
        'somente_leitura': True,
    }


def montar_preview_fiscal_item(item: ItemNFeEntradaConferencia) -> dict[str, Any]:
    contexto = montar_contexto_fiscal_entrada(item.conferencia)
    regras = carregar_regras_fiscais_entrada_ativas()
    return recalcular_tributos_item_efetivos(item, contexto, regras)


def alteracoes_fiscais_solicitadas(
    item: ItemNFeEntradaConferencia,
    dados: dict[str, Any],
) -> list[str]:
    """Campos *_efetivo cujo valor enviado difere do efetivo atual do item."""
    _, _, trib_efetivo, prod_efetivo = _fontes_efetivas(item)
    alterados: list[str] = []
    for campo in CAMPOS_EFETIVOS_FISCAIS:
        if campo.campo_modelo not in dados:
            continue
        valor_atual = _valor_na_fonte(campo, trib_efetivo, prod_efetivo)
        if valores_efetivos_iguais(valor_atual, dados[campo.campo_modelo], campo.tipo):
            continue
        alterados.append(campo.campo_modelo)
    return alterados


def aplicar_ajuste_fiscal_item(
    item: ItemNFeEntradaConferencia,
    dados: dict[str, Any],
    usuario,
) -> dict[str, Any]:
    contexto = montar_contexto_fiscal_entrada(item.conferencia)
    regras = carregar_regras_fiscais_entrada_ativas()
    resultado_antes = avaliar_item_entrada_fiscal(item, contexto, regras)
    trib_xml, prod_xml, trib_efetivo, prod_efetivo = _fontes_efetivas(item)
    motivo = (dados.get('motivo_ajuste_fiscal') or '').strip()

    alteracoes: list[tuple[Any, Any, Any, Any]] = []
    for campo in CAMPOS_EFETIVOS_FISCAIS:
        if campo.campo_modelo not in dados:
            continue
        valor_novo = dados.get(campo.campo_modelo)
        valor_atual = _valor_na_fonte(campo, trib_efetivo, prod_efetivo)
        if valores_efetivos_iguais(valor_atual, valor_novo, campo.tipo):
            continue
        valor_xml = _valor_na_fonte(campo, trib_xml, prod_xml)
        alteracoes.append((campo, valor_novo, valor_atual, valor_xml))

    if not alteracoes:
        raise AjusteFiscalErro(
            'NENHUM_AJUSTE',
            'Nenhuma alteração fiscal em relação ao XML/regra atual.',
        )
    if not motivo:
        raise AjusteFiscalErro(
            'MOTIVO_OBRIGATORIO',
            'Informe a justificativa do ajuste fiscal.',
        )

    snapshot = _snapshot_regra(resultado_antes)
    usuario_nome = ''
    if usuario is not None:
        usuario_nome = (usuario.get_full_name() or usuario.get_username() or '').strip()

    update_fields: set[str] = set()
    auditorias: list[ItemConferenciaFiscalOverride] = []
    with transaction.atomic():
        for campo, valor_novo, valor_atual, valor_xml in alteracoes:
            if valor_novo in (None, ''):
                setattr(item, campo.campo_modelo, None if campo.tipo == 'decimal' else '')
                valor_novo_texto = fmt_valor_efetivo(valor_xml, campo.tipo)
            else:
                setattr(item, campo.campo_modelo, valor_novo)
                valor_novo_texto = fmt_valor_efetivo(valor_novo, campo.tipo)
            update_fields.add(campo.campo_modelo)
            auditorias.append(
                ItemConferenciaFiscalOverride(
                    item_conferencia=item,
                    campo=campo.campo_modelo,
                    valor_anterior=fmt_valor_efetivo(valor_atual, campo.tipo),
                    valor_novo=valor_novo_texto,
                    motivo=motivo,
                    usuario=usuario if getattr(usuario, 'pk', None) else None,
                    usuario_nome=usuario_nome,
                    snapshot_regra=snapshot,
                ),
            )
        item.motivo_ajuste_fiscal = motivo
        update_fields.update({'motivo_ajuste_fiscal', 'atualizado_em'})
        item.save(update_fields=sorted(update_fields))
        ItemConferenciaFiscalOverride.objects.bulk_create(auditorias)

    item.refresh_from_db()
    return {
        'total_alteracoes': len(alteracoes),
        'ajustes': [
            {
                'campo': campo.campo_modelo,
                'rotulo': campo.label,
                'valor_anterior': fmt_valor_efetivo(valor_atual, campo.tipo),
                'valor_novo': fmt_valor_efetivo(
                    valor_novo if valor_novo not in (None, '') else valor_xml,
                    campo.tipo,
                ),
            }
            for campo, valor_novo, valor_atual, valor_xml in alteracoes
        ],
        'preview': recalcular_tributos_item_efetivos(item, contexto, regras),
    }
