"""ERP 4.0.10 — Modelo operacional Nexus (venda sob demanda, atendimento flexível).

Helpers e enums para registrar intenção de atendimento sem movimentar estoque,
gerar financeiro ou alterar emissão NF-e nesta fase.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, TypedDict

from django.db import models


class TipoAtendimentoItem(models.TextChoices):
    ESTOQUE_PROPRIO = 'ESTOQUE_PROPRIO', 'Estoque próprio'
    ENTRADA_CONCILIADA = 'ENTRADA_CONCILIADA', 'Entrada conciliada'
    RETIRADA_FORNECEDOR = 'RETIRADA_FORNECEDOR', 'Retirada no fornecedor'
    ENTREGA_DIRETA_FORNECEDOR_CLIENTE = (
        'ENTREGA_DIRETA_FORNECEDOR_CLIENTE',
        'Entrega direta fornecedor → cliente',
    )
    RETIRADA_FORNECEDOR_TRANSPORTADORA = (
        'RETIRADA_FORNECEDOR_TRANSPORTADORA',
        'Retirada fornecedor → transportadora',
    )
    COMPRA_VINCULADA = 'COMPRA_VINCULADA', 'Compra vinculada'
    MISTO = 'MISTO', 'Misto'
    NAO_DEFINIDO = 'NAO_DEFINIDO', 'Não definido'


class StatusEntradaFiscal(models.TextChoices):
    NAO_APLICAVEL = 'NAO_APLICAVEL', 'Não aplicável'
    PENDENTE = 'PENDENTE', 'Pendente'
    RECEBIDA = 'RECEBIDA', 'Recebida'
    CONCILIADA = 'CONCILIADA', 'Conciliada'
    DIVERGENTE = 'DIVERGENTE', 'Divergente'
    CANCELADA = 'CANCELADA', 'Cancelada'


class OrigemFisica(models.TextChoices):
    ESTOQUE_PROPRIO = 'ESTOQUE_PROPRIO', 'Estoque próprio'
    FORNECEDOR = 'FORNECEDOR', 'Fornecedor'
    TRANSPORTADORA = 'TRANSPORTADORA', 'Transportadora'
    CLIENTE = 'CLIENTE', 'Cliente'
    TERCEIRO = 'TERCEIRO', 'Terceiro'
    NAO_DEFINIDA = 'NAO_DEFINIDA', 'Não definida'


class DestinoFisico(models.TextChoices):
    CLIENTE = 'CLIENTE', 'Cliente'
    TRANSPORTADORA = 'TRANSPORTADORA', 'Transportadora'
    ESTOQUE_PROPRIO = 'ESTOQUE_PROPRIO', 'Estoque próprio'
    TERCEIRO = 'TERCEIRO', 'Terceiro'
    NAO_DEFINIDO = 'NAO_DEFINIDO', 'Não definido'


# Mapeamento sugerido por tipo de atendimento (somente intenção; não executa fluxo).
_TIPO_PARA_ORIGEM_DESTINO: dict[str, tuple[str, str, str]] = {
    TipoAtendimentoItem.ESTOQUE_PROPRIO: (
        OrigemFisica.ESTOQUE_PROPRIO,
        DestinoFisico.CLIENTE,
        StatusEntradaFiscal.NAO_APLICAVEL,
    ),
    TipoAtendimentoItem.ENTRADA_CONCILIADA: (
        OrigemFisica.ESTOQUE_PROPRIO,
        DestinoFisico.CLIENTE,
        StatusEntradaFiscal.CONCILIADA,
    ),
    TipoAtendimentoItem.RETIRADA_FORNECEDOR: (
        OrigemFisica.FORNECEDOR,
        DestinoFisico.CLIENTE,
        StatusEntradaFiscal.PENDENTE,
    ),
    TipoAtendimentoItem.ENTREGA_DIRETA_FORNECEDOR_CLIENTE: (
        OrigemFisica.FORNECEDOR,
        DestinoFisico.CLIENTE,
        StatusEntradaFiscal.PENDENTE,
    ),
    TipoAtendimentoItem.RETIRADA_FORNECEDOR_TRANSPORTADORA: (
        OrigemFisica.FORNECEDOR,
        DestinoFisico.TRANSPORTADORA,
        StatusEntradaFiscal.PENDENTE,
    ),
    TipoAtendimentoItem.COMPRA_VINCULADA: (
        OrigemFisica.FORNECEDOR,
        DestinoFisico.NAO_DEFINIDO,
        StatusEntradaFiscal.PENDENTE,
    ),
    TipoAtendimentoItem.MISTO: (
        OrigemFisica.NAO_DEFINIDA,
        DestinoFisico.NAO_DEFINIDO,
        StatusEntradaFiscal.PENDENTE,
    ),
}


class ResumoAtendimentoItem(TypedDict):
    tipo_atendimento: str
    status_entrada_fiscal: str
    origem_fisica: str
    destino_fisico: str
    quantidade_necessaria: str
    quantidade_atendida: str
    quantidade_pendente: str


def _dec(v: Decimal | str | float | int | None) -> Decimal:
    if v is None:
        return Decimal('0')
    return Decimal(str(v))


def resolver_tipo_atendimento_padrao(
    *,
    tipo_atendimento: str | None = None,
) -> str:
    """Retorna tipo seguro quando não informado."""
    if tipo_atendimento and tipo_atendimento in TipoAtendimentoItem.values:
        return tipo_atendimento
    return TipoAtendimentoItem.NAO_DEFINIDO


def resolver_origem_destino_por_tipo(
    tipo_atendimento: str | None,
) -> tuple[str, str, str]:
    """Sugere origem, destino e status de entrada fiscal a partir do tipo."""
    tipo = resolver_tipo_atendimento_padrao(tipo_atendimento=tipo_atendimento)
    return _TIPO_PARA_ORIGEM_DESTINO.get(
        tipo,
        (OrigemFisica.NAO_DEFINIDA, DestinoFisico.NAO_DEFINIDO, StatusEntradaFiscal.NAO_APLICAVEL),
    )


def marcar_entrada_fiscal_pendente(**kwargs: Any) -> dict[str, str]:
    """Indicador operacional — não altera documentos fiscais nesta fase."""
    _ = kwargs
    return {'status_entrada_fiscal': StatusEntradaFiscal.PENDENTE}


def marcar_entrada_fiscal_conciliada(**kwargs: Any) -> dict[str, str]:
    """Indicador operacional — conciliação real será fase futura."""
    _ = kwargs
    return {'status_entrada_fiscal': StatusEntradaFiscal.CONCILIADA}


def obter_resumo_atendimento_item(
    *,
    tipo_atendimento: str | None = None,
    status_entrada_fiscal: str | None = None,
    origem_fisica: str | None = None,
    destino_fisico: str | None = None,
    quantidade_necessaria: Decimal | str | float | int = 0,
    quantidade_atendida: Decimal | str | float | int = 0,
) -> ResumoAtendimentoItem:
    """Monta resumo read-only para BI/UI futura."""
    tipo = resolver_tipo_atendimento_padrao(tipo_atendimento=tipo_atendimento)
    origem_s, destino_s, status_s = resolver_origem_destino_por_tipo(tipo)
    qtd_nec = _dec(quantidade_necessaria)
    qtd_at = _dec(quantidade_atendida)
    qtd_pend = max(qtd_nec - qtd_at, Decimal('0'))
    return {
        'tipo_atendimento': tipo,
        'status_entrada_fiscal': status_entrada_fiscal or status_s,
        'origem_fisica': origem_fisica or origem_s,
        'destino_fisico': destino_fisico or destino_s,
        'quantidade_necessaria': str(qtd_nec),
        'quantidade_atendida': str(qtd_at),
        'quantidade_pendente': str(qtd_pend),
    }
