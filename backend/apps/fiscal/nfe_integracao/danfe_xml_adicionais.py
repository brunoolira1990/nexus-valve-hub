"""Montagem de infCpl, infAdProd e xPed/nItemPed para XML NF-e / DANFE BFR."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from apps.fiscal.models import ItemNFeSaida, NFeSaida

_MAX_INF_CPL_XML_CHARS = 5000
_MAX_INF_CPL_DANFE_CHARS = 420

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
        f'pedido de compra: {pedido}',
        f'pedido de compra do cliente: {pedido}',
        f'ordem de compra: {pedido}',
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
    return f'PEDIDO DE COMPRA: {ped.upper()}'


def _nitemped_distinto_do_pedido(pc_num: str, pc_item: str) -> str:
    """nItemPed só quando for linha do pedido, não repetição/truncamento do número do pedido."""
    if not pc_item:
        return ''
    num = pc_item.strip()
    ped = pc_num.strip()
    if not ped:
        return num[:6]
    if num == ped:
        return ''
    # linhas curtas (ex.: 1, 10) são válidas — não usar startswith genérico
    if len(num) >= 5 and ped.startswith(num):
        return ''
    if len(num) >= 5 and len(ped) >= 6 and num == ped[:6]:
        return ''
    if len(num) >= 5 and len(ped) >= 6 and ped[:6] == num[:6]:
        return ''
    return num[:6]


def _linhas_pedido_equivalentes(linha_a: str, linha_b: str) -> bool:
    a = (linha_a or '').strip()
    b = (linha_b or '').strip()
    if not a or not b:
        return False
    if a == b:
        return True
    if a.isdigit() and b.isdigit():
        return int(a) == int(b)
    return False


def _resolver_linha_pedido_item(
    pc_num: str,
    pc_item: str,
    *,
    observacao_item: str = '',
) -> str:
    linha = _nitemped_distinto_do_pedido(pc_num, pc_item)
    if linha:
        return linha
    obs = _text(observacao_item)
    if obs and len(obs) <= 6:
        return _nitemped_distinto_do_pedido(pc_num, obs)
    return ''


def _texto_pedido_compra_item(x_ped: str, n_item: str) -> str:
    """Texto legível abaixo do item no DANFE (via infAdProd)."""
    if x_ped and n_item:
        return f'Pedido de compra: {x_ped} — Item: {n_item}'
    if x_ped:
        return f'Pedido de compra: {x_ped}'
    return ''


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
    4. Pedido de compra do cliente (cabeçalho)
    """
    linhas = (dados or {}).get('itens') or []
    regras = _coletar_regras_fiscais_nfe(nfe_saida)

    partes: list[str] = []
    partes.extend(_textos_regra_fiscal(regras))

    ped = _texto_pedido_cliente_cabecalho(nfe_saida, itens_db, linhas)
    if ped and not _pedido_ja_citado(partes, _text(nfe_saida.pedido_cliente_numero)):
        partes.append(ped)

    cli = _texto_cliente_complementar(nfe_saida)
    if cli:
        partes.append(cli)

    manual = _texto_nf_manual(nfe_saida)
    if manual:
        partes.append(manual)

    blocos = deduplicar_textos_inf_cpl(partes)
    from apps.fiscal.nfe_difal_calculo import agregar_totais_difal, texto_difal_inf_complementar
    from apps.fiscal.snapshot_fiscal_helpers import get_difal_snapshot

    difal_totais = agregar_totais_difal(
        [
            get_difal_snapshot(
                (itens_db or {}).get(linha.get('item_id')).snapshot_fiscal
                if itens_db and linha.get('item_id') in itens_db
                else linha.get('snapshot_fiscal')
            )
            for linha in linhas
        ],
    )
    texto_difal = texto_difal_inf_complementar(difal_totais)
    if texto_difal:
        blocos.append(texto_difal)
    blocos = deduplicar_textos_inf_cpl(blocos)
    blocos_xml = [re.sub(r'\s+', ' ', b.replace('\n', ' ')).strip() for b in blocos]
    inf_cpl = ' '.join(b for b in blocos_xml if b)[:_MAX_INF_CPL_XML_CHARS].strip()
    inf_fisco = _para_maiusculas(nfe_saida.informacoes_fisco)[:2000]
    if inf_fisco and len(inf_fisco) > 200:
        inf_fisco = inf_fisco[:197] + '...'
    return inf_cpl, inf_fisco


def _normalizar_n_item_ped_xml(valor: str) -> str:
    """nItemPed XSD: [0-9]{1,6} — preserva dígitos informados pelo usuário."""
    bruto = _text(valor)
    if not bruto:
        return ''
    if bruto.isdigit():
        return bruto[:6]
    digits = ''.join(c for c in bruto if c.isdigit())
    return digits[:6] if digits else ''


def resolver_xped_nitemped_item(
    item_db: ItemNFeSaida | None,
    linha: dict[str, Any] | None = None,
    *,
    pedido_cabecalho: str = '',
) -> tuple[str, str]:
    """
    xPed: número do pedido de compra do cliente (item ou cabeçalho da NF-e).
    nItemPed: linha do pedido no item — não herda do cabeçalho.
    """
    linha = linha or {}
    pc_num = (
        _text(item_db.pedido_cliente_numero if item_db else '')
        or _text(linha.get('pedido_cliente_numero'))
        or _text(pedido_cabecalho)
    )
    pc_item_raw = _text(item_db.pedido_cliente_item if item_db else '') or _text(
        linha.get('pedido_cliente_item'),
    )
    obs_item = _text(item_db.observacao_item if item_db else '') or _text(
        linha.get('observacao_item'),
    )
    n_item = _resolver_linha_pedido_item(pc_num, pc_item_raw, observacao_item=obs_item)
    n_item = _normalizar_n_item_ped_xml(n_item)
    return (pc_num[:15] if pc_num else ''), n_item


def montar_inf_ad_prod_item(
    nfe_saida: NFeSaida,
    linha: dict[str, Any],
    item_db: ItemNFeSaida | None = None,
    *,
    pedido_cabecalho: str = '',
) -> str:
    """infAdProd — pedido de compra primeiro; depois observações do item."""
    partes: list[str] = []
    pedido_cab = pedido_cabecalho or _text(nfe_saida.pedido_cliente_numero)

    x_ped, n_item = resolver_xped_nitemped_item(
        item_db,
        linha,
        pedido_cabecalho=pedido_cab,
    )
    pedido_txt = _texto_pedido_compra_item(x_ped, n_item)
    if pedido_txt:
        partes.append(pedido_txt)

    obs_usada_como_item = n_item and item_db and _linhas_pedido_equivalentes(
        _text(item_db.observacao_item),
        n_item,
    )

    if item_db:
        if _texto_permitido_inf_cpl(item_db.observacao_item, max_len=500) and not obs_usada_como_item:
            t = _text(item_db.observacao_item)
            if t not in partes:
                partes.append(t)
        if _texto_permitido_inf_cpl(item_db.informacao_adicional_item, max_len=500):
            t = _text(item_db.informacao_adicional_item)
            if t not in partes:
                partes.append(t)

    snap = linha.get('snapshot_fiscal') or {}
    obs_item = _text(snap.get('observacao_item') or snap.get('informacao_adicional_item'))
    if obs_item and _texto_permitido_inf_cpl(obs_item, max_len=500) and obs_item not in partes:
        partes.append(obs_item)

    if not partes:
        return ''
    return '\n'.join(deduplicar_textos_inf_cpl(partes))[:500]


def enriquecer_linhas_xml_nfe(
    nfe_saida: NFeSaida,
    dados: dict[str, Any],
) -> dict[int, ItemNFeSaida]:
    linhas = list(dados.get('itens') or [])
    itens_db = {it.pk: it for it in nfe_saida.itens.all()}
    pedido_cab = _text(nfe_saida.pedido_cliente_numero)
    for linha in linhas:
        item_pk = linha.get('item_id')
        item_db = itens_db.get(item_pk) if item_pk else None
        if not _text(linha.get('pedido_cliente_numero')):
            linha['pedido_cliente_numero'] = (
                _text(item_db.pedido_cliente_numero if item_db else '')
                or pedido_cab
            )
        if not _text(linha.get('pedido_cliente_item')) and item_db:
            linha['pedido_cliente_item'] = _text(item_db.pedido_cliente_item)
        x_ped, n_item = resolver_xped_nitemped_item(
            item_db,
            linha,
            pedido_cabecalho=pedido_cab,
        )
        linha['x_ped'] = x_ped
        linha['n_item_ped'] = n_item
        linha['inf_ad_prod'] = montar_inf_ad_prod_item(
            nfe_saida,
            linha,
            item_db,
            pedido_cabecalho=pedido_cab,
        )
    return itens_db


def inf_cpl_prioriza_pedido_para_danfe(
    inf_cpl: str,
    *,
    max_len: int | None = None,
) -> str:
    """
    Normaliza infCpl para exibição no DANFE.

    Por padrão não trunca o XML. No PDF (DANFE), o bloco Dados Adicionais usa auto-shrink
    e clip visual na 1ª página — sem alterar o infCpl transmitido.
    Use max_len apenas em cenários legados que exijam limite explícito.
    """
    texto = _normalizar_espacos(inf_cpl)
    if not texto:
        return ''
    limite = max_len if max_len is not None else _MAX_INF_CPL_XML_CHARS
    if len(texto) <= limite:
        return texto
    m = re.search(
        r'(PEDIDO DE COMPRA(?: DO CLIENTE)?:\s*[^.]+(?:\.|$))',
        texto,
        flags=re.IGNORECASE,
    )
    if not m:
        return texto[: limite - 3].rstrip() + '...'
    pedido_bloco = m.group(1).strip()
    resto = (texto[: m.start()] + ' ' + texto[m.end() :]).strip()
    espaco_resto = limite - len(pedido_bloco) - 1
    if espaco_resto <= 0:
        return pedido_bloco[:limite]
    prefixo = resto[:espaco_resto].rstrip()
    return f'{prefixo} {pedido_bloco}'.strip()[:limite]


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
