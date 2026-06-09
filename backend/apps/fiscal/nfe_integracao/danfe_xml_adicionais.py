"""Montagem de infCpl, infAdProd e xPed/nItemPed para XML NF-e / DANFE BFR."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from apps.fiscal.models import ItemNFeSaida, NFeSaida

_MAX_INF_CPL_CHARS = 420

_TERMOS_STATUS_DANFE = (
    'nf-e de conferência',
    'nfe de conferencia',
    'sem valor fiscal',
    'sem protocolo',
    'sem protocolo de autorização',
    'documento ainda não autorizado',
    'nao autorizado pela sefaz',
    'não autorizado pela sefaz',
)

_TERMOS_EXCLUIR = _TERMOS_STATUS_DANFE + (
    'xml preliminar',
    'não transmitir',
    'nao transmitir',
    'rascunho-fat',
    'ref. interna erp',
    'condição de pagamento',
    'condicao de pagamento',
    'prazo de pagamento',
    'prazo de entrega',
    'secret interno',
    'nao imprimir',
    'não deve sair',
    'nfepreview',
    'nfelib',
    'cst/csosn icms',
    'cst icms',
    'csosn icms',
)


def _text(val: Any) -> str:
    return (str(val) if val is not None else '').strip()


def _normalizar_espacos(texto: str) -> str:
    return re.sub(r'\s+', ' ', _text(texto))


def _para_maiusculas(texto: str) -> str:
    return _normalizar_espacos(texto).upper()


def _normalizar_chave_dedup(texto: str) -> str:
    t = unicodedata.normalize('NFKD', texto)
    t = ''.join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r'\s+', ' ', t.lower().strip())
    return t


def _contem_termo_bloqueado(texto: str) -> bool:
    low = _normalizar_chave_dedup(texto)
    return any(term in low for term in _TERMOS_EXCLUIR)


def _texto_permitido_inf_cpl(texto: str, *, max_len: int = 2000) -> bool:
    t = _text(texto)
    if not t or len(t) > max_len:
        return False
    return not _contem_termo_bloqueado(t)


def deduplicar_textos_inf_cpl(partes: list[str]) -> list[str]:
    """Remove duplicados exatos e por normalização (case/acentos)."""
    vistos: set[str] = set()
    out: list[str] = []
    for raw in partes:
        t = _text(raw)
        if not t:
            continue
        chave = _normalizar_chave_dedup(t)
        if not chave or chave in vistos:
            continue
        vistos.add(chave)
        out.append(t)
    return out


def _coletar_regras_fiscais_nfe(nfe_saida: NFeSaida) -> list[Any]:
    from apps.fiscal.nfe_saida_atualizar_impostos import _buscar_regra_para_item
    from apps.regras_fiscais.models import RegraFiscalSaida

    vistos: dict[int, RegraFiscalSaida] = {}
    for item in nfe_saida.itens.select_related('produto'):
        _busca, regra, _alertas, _filtros = _buscar_regra_para_item(nfe_saida, item)
        if regra and regra.pk not in vistos:
            vistos[regra.pk] = regra
    return list(vistos.values())


def _bloco_inf_cpl(texto: str) -> str:
    """Normaliza, valida e devolve bloco em maiúsculas."""
    t = _para_maiusculas(texto)
    if not t or not _texto_permitido_inf_cpl(t):
        return ''
    return t


def _textos_regra_fiscal(regras: list[Any]) -> list[str]:
    partes: list[str] = []
    for regra in regras:
        bloco = _bloco_inf_cpl(getattr(regra, 'informacoes_complementares', ''))
        if bloco:
            partes.append(bloco)
    return deduplicar_textos_inf_cpl(partes)


def _cliente_nfe(nfe_saida: NFeSaida):
    if not nfe_saida.cliente_id:
        return None
    cliente = getattr(nfe_saida, 'cliente', None)
    if cliente is not None:
        return cliente
    from apps.cadastros.models import Cliente

    return Cliente.objects.filter(pk=nfe_saida.cliente_id).first()


def _texto_cliente_complementar(nfe_saida: NFeSaida) -> str:
    cliente = _cliente_nfe(nfe_saida)
    if not cliente:
        return ''
    return _bloco_inf_cpl(getattr(cliente, 'informacoes_complementares_nfe', ''))


def _texto_nf_manual(nfe_saida: NFeSaida) -> str:
    return _bloco_inf_cpl(nfe_saida.informacoes_adicionais)


def _pedido_ja_citado(textos: list[str], pedido: str) -> bool:
    ped_norm = _normalizar_chave_dedup(pedido)
    if not ped_norm:
        return False
    rotulos = (
        f'pedido do cliente: {pedido}',
        f'pedido do cliente {pedido}',
        pedido,
    )
    for bloco in textos:
        chave = _normalizar_chave_dedup(bloco)
        for rotulo in rotulos:
            if _normalizar_chave_dedup(rotulo) in chave or ped_norm in chave:
                return True
    return False


def _normalizar_itens_db(
    itens_db: dict[int, ItemNFeSaida] | list[ItemNFeSaida] | None,
) -> dict[int, ItemNFeSaida]:
    if not itens_db:
        return {}
    if isinstance(itens_db, dict):
        return itens_db
    return {it.pk: it for it in itens_db}


def _texto_pedido_cliente_cabecalho(
    nfe_saida: NFeSaida,
    itens_db: dict[int, ItemNFeSaida] | list[ItemNFeSaida] | None,
    linhas: list[dict[str, Any]],
) -> str:
    ped = _text(nfe_saida.pedido_cliente_numero)
    if not ped:
        return ''
    itens_map = _normalizar_itens_db(itens_db)
    if itens_map:
        for item in itens_map.values():
            if _text(item.pedido_cliente_numero) or _text(item.pedido_cliente_item):
                return ''
    for linha in linhas:
        if _text(linha.get('pedido_cliente_numero')) or _text(linha.get('pedido_cliente_item')):
            return ''
    return f'PEDIDO DO CLIENTE: {ped.upper()}'


def montar_inf_cpl_nfe(
    nfe_saida: NFeSaida,
    dados: dict[str, Any] | None = None,
    *,
    itens_db: dict[int, ItemNFeSaida] | None = None,
) -> tuple[str, str]:
    """
    infCpl — quatro fontes, nesta ordem, cada uma em linha separada, em maiúsculas:

    1. Informações complementares (NF) da regra fiscal
    2. Informações complementares do cliente (cadastro)
    3. Informações adicionais manuais da NF-e (conferência)
    4. Pedido do cliente (cabeçalho, quando não houver pedido por item)
    """
    linhas = (dados or {}).get('itens') or []
    regras = _coletar_regras_fiscais_nfe(nfe_saida)

    partes: list[str] = []
    partes.extend(_textos_regra_fiscal(regras))

    cli = _texto_cliente_complementar(nfe_saida)
    if cli:
        partes.append(cli)

    manual = _texto_nf_manual(nfe_saida)
    if manual:
        partes.append(manual)

    ped = _texto_pedido_cliente_cabecalho(nfe_saida, itens_db, linhas)
    if ped and not _pedido_ja_citado(partes, _text(nfe_saida.pedido_cliente_numero)):
        partes.append(ped)

    blocos = deduplicar_textos_inf_cpl(partes)
    blocos_xml = [re.sub(r'\s+', ' ', b.replace('\n', ' ')).strip() for b in blocos]
    inf_cpl = ' '.join(b for b in blocos_xml if b)[:_MAX_INF_CPL_CHARS].strip()
    inf_fisco = _para_maiusculas(nfe_saida.informacoes_fisco)[:2000]
    if inf_fisco and len(inf_fisco) > 200:
        inf_fisco = inf_fisco[:197] + '...'
    return inf_cpl, inf_fisco


def resolver_xped_nitemped_item(
    item_db: ItemNFeSaida | None,
    linha: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """xPed/nItemPed somente quando informados no item — não herda pedido do cabeçalho."""
    linha = linha or {}
    pc_num = _text(item_db.pedido_cliente_numero if item_db else '') or _text(
        linha.get('pedido_cliente_numero'),
    )
    pc_item = _text(item_db.pedido_cliente_item if item_db else '') or _text(
        linha.get('pedido_cliente_item'),
    )
    return (pc_num[:15] if pc_num else ''), (pc_item[:6] if pc_item else '')


def montar_inf_ad_prod_item(
    nfe_saida: NFeSaida,
    linha: dict[str, Any],
    item_db: ItemNFeSaida | None = None,
) -> str:
    """infAdProd — apenas complemento específico do item; vazio se não houver dados."""
    partes: list[str] = []

    if item_db:
        if _texto_permitido_inf_cpl(item_db.observacao_item, max_len=500):
            partes.append(_text(item_db.observacao_item))
        if _texto_permitido_inf_cpl(item_db.informacao_adicional_item, max_len=500):
            t = _text(item_db.informacao_adicional_item)
            if t not in partes:
                partes.append(t)

    snap = linha.get('snapshot_fiscal') or {}
    obs_item = _text(snap.get('observacao_item') or snap.get('informacao_adicional_item'))
    if obs_item and _texto_permitido_inf_cpl(obs_item, max_len=500) and obs_item not in partes:
        partes.append(obs_item)

    x_ped, n_item = resolver_xped_nitemped_item(item_db, linha)
    if x_ped and n_item:
        partes.append(f'xPed: {x_ped} · nItemPed: {n_item}')
    elif x_ped:
        partes.append(f'xPed: {x_ped}')
    elif n_item:
        partes.append(f'nItemPed: {n_item}')

    if not partes:
        return ''
    return '\n'.join(deduplicar_textos_inf_cpl(partes))[:500]


def enriquecer_linhas_xml_nfe(
    nfe_saida: NFeSaida,
    dados: dict[str, Any],
) -> dict[int, ItemNFeSaida]:
    linhas = list(dados.get('itens') or [])
    itens_db = {it.pk: it for it in nfe_saida.itens.all()}
    for linha in linhas:
        item_pk = linha.get('item_id')
        item_db = itens_db.get(item_pk) if item_pk else None
        x_ped, n_item = resolver_xped_nitemped_item(item_db, linha)
        linha['x_ped'] = x_ped
        linha['n_item_ped'] = n_item
        linha['inf_ad_prod'] = montar_inf_ad_prod_item(nfe_saida, linha, item_db)
    return itens_db


def montar_informacoes_complementares_danfe(
    nfe_saida: NFeSaida,
    dados: dict[str, Any] | None = None,
    *,
    incluir_cabecalho_conferencia: bool = False,
) -> tuple[str, str]:
    """Monta infCpl para DANFE/XML (status da DANFE só na marca d'água)."""
    itens_db = None
    if dados and dados.get('itens'):
        itens_db = {it.pk: it for it in nfe_saida.itens.all()}
    return montar_inf_cpl_nfe(nfe_saida, dados, itens_db=itens_db)
