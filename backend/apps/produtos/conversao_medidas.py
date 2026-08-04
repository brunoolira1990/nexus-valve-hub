from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from apps.produtos.models import Produto


QTY_QUANT = Decimal("0.001")
WEIGHT_QUANT = Decimal("0.001")


class ConversaoErro(ValueError):
    pass


def _dec(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _qtd(value: Decimal) -> Decimal:
    return value.quantize(QTY_QUANT, rounding=ROUND_HALF_UP)


def _peso(value: Decimal) -> Decimal:
    return value.quantize(WEIGHT_QUANT, rounding=ROUND_HALF_UP)


@dataclass
class ResultadoConversao:
    quantidade_origem: Decimal
    unidade_origem: str
    quantidade_destino: Decimal
    unidade_destino: str
    metros: Decimal | None = None
    barras: Decimal | None = None
    peso_kg: Decimal | None = None
    mensagem: str = ""


def _to_kg(produto: Produto, quantidade: Decimal, unidade_origem: str) -> Decimal:
    unidade = (unidade_origem or "").upper()
    peso_por_metro = produto.get_peso_por_metro_kg_efetivo()
    comprimento_barra = produto.get_comprimento_padrao_barra_m_efetivo()
    peso_por_peca = produto.get_peso_por_peca_kg_efetivo()
    peso_por_chapa = produto.get_peso_por_chapa_kg_efetivo()
    if unidade == "KG":
        return quantidade
    if unidade == "TON":
        return quantidade * Decimal("1000")
    if unidade == "M":
        if not peso_por_metro:
            raise ConversaoErro("Não foi possível converter. Informe peso por metro no cadastro do produto/família.")
        return quantidade * _dec(peso_por_metro)
    if unidade == "BR":
        if not comprimento_barra or not peso_por_metro:
            raise ConversaoErro(
                "Não foi possível converter. Informe peso por metro e comprimento padrão da barra no cadastro do produto/família."
            )
        return quantidade * _dec(comprimento_barra) * _dec(peso_por_metro)
    if unidade == "PC":
        if not peso_por_peca:
            raise ConversaoErro("Não foi possível converter. Informe peso por peça no cadastro do produto/família.")
        return quantidade * _dec(peso_por_peca)
    if unidade == "CH":
        if not peso_por_chapa:
            raise ConversaoErro("Não foi possível converter. Informe peso por chapa no cadastro do produto/família.")
        return quantidade * _dec(peso_por_chapa)
    raise ConversaoErro(f"Unidade de origem '{unidade_origem}' ainda não suportada.")


def _from_kg(produto: Produto, quantidade_kg: Decimal, unidade_destino: str) -> Decimal:
    unidade = (unidade_destino or "").upper()
    peso_por_metro = produto.get_peso_por_metro_kg_efetivo()
    comprimento_barra = produto.get_comprimento_padrao_barra_m_efetivo()
    peso_por_peca = produto.get_peso_por_peca_kg_efetivo()
    peso_por_chapa = produto.get_peso_por_chapa_kg_efetivo()
    if unidade == "KG":
        return quantidade_kg
    if unidade == "TON":
        return quantidade_kg / Decimal("1000")
    if unidade == "M":
        if not peso_por_metro:
            raise ConversaoErro("Não foi possível converter. Informe peso por metro no cadastro do produto/família.")
        return quantidade_kg / _dec(peso_por_metro)
    if unidade == "BR":
        if not comprimento_barra or not peso_por_metro:
            raise ConversaoErro(
                "Não foi possível converter. Informe peso por metro e comprimento padrão da barra no cadastro do produto/família."
            )
        return quantidade_kg / (_dec(comprimento_barra) * _dec(peso_por_metro))
    if unidade == "PC":
        if not peso_por_peca:
            raise ConversaoErro("Não foi possível converter. Informe peso por peça no cadastro do produto/família.")
        return quantidade_kg / _dec(peso_por_peca)
    if unidade == "CH":
        if not peso_por_chapa:
            raise ConversaoErro("Não foi possível converter. Informe peso por chapa no cadastro do produto/família.")
        return quantidade_kg / _dec(peso_por_chapa)
    raise ConversaoErro(f"Unidade de destino '{unidade_destino}' ainda não suportada.")


def converter_quantidade_produto(
    produto: Produto,
    quantidade,
    unidade_origem: str,
    unidade_destino: str,
) -> ResultadoConversao:
    qtd = _dec(quantidade)
    uo = (unidade_origem or "").upper()
    ud = (unidade_destino or "").upper()
    if qtd < 0:
        raise ConversaoErro("Quantidade deve ser maior ou igual a zero.")
    if not produto.get_usa_conversao_dimensional_efetivo() and uo != ud:
        raise ConversaoErro(
            "Produto sem conversão dimensional habilitada. "
            "No cadastro do produto, marque «Usa conversão dimensional?» "
            "e preencha os fatores (peso por peça/metro etc.). "
            f"Unidade da NF: {uo}; estoque: {ud}."
        )

    if uo == ud:
        quantidade_destino = qtd
        if uo == "KG":
            peso_kg = qtd
        elif uo == "TON":
            peso_kg = qtd * Decimal("1000")
        elif uo in {"M", "BR", "PC", "CH"}:
            try:
                peso_kg = _to_kg(produto, qtd, uo)
            except ConversaoErro:
                peso_kg = None
        else:
            peso_kg = None
    else:
        kg = _to_kg(produto, qtd, uo)
        quantidade_destino = _from_kg(produto, kg, ud)
        peso_kg = kg

    metros = None
    barras = None
    try:
        metros = _from_kg(produto, _to_kg(produto, qtd, uo), "M")
    except ConversaoErro:
        pass
    try:
        barras = _from_kg(produto, _to_kg(produto, qtd, uo), "BR")
    except ConversaoErro:
        pass

    return ResultadoConversao(
        quantidade_origem=_qtd(qtd),
        unidade_origem=uo,
        quantidade_destino=_qtd(quantidade_destino),
        unidade_destino=ud,
        peso_kg=_peso(peso_kg) if peso_kg is not None else None,
        metros=_qtd(metros) if metros is not None else None,
        barras=_qtd(barras) if barras is not None else None,
        mensagem="Conversão calculada com parâmetros de cadastro do produto/família.",
    )
