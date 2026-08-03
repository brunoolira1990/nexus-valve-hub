"""Dados normalizados para preview/XML NF-e entrada própria emitida (tpNF=0)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from apps.fiscal.models import ItemNFeEntrada, NFeEntrada
from apps.fiscal.nfe_saida_preview import UF_IBGE, _digits, _text


def _dec(val: Any) -> Decimal:
    if val is None or val == '':
        return Decimal('0')
    try:
        return Decimal(str(val).replace(',', '.'))
    except Exception:
        return Decimal('0')


def _participante_endereco(obj) -> dict[str, Any]:
    return {
        'logradouro': _text(getattr(obj, 'logradouro', None)),
        'numero': _text(getattr(obj, 'numero', None)),
        'complemento': _text(getattr(obj, 'complemento', None)),
        'bairro': _text(getattr(obj, 'bairro', None)),
        'cidade': _text(getattr(obj, 'cidade', None)),
        'uf': _text(getattr(obj, 'uf', None))[:2],
        'cep': _digits(getattr(obj, 'cep', None), max_len=8),
        'c_mun': _digits(getattr(obj, 'codigo_municipio', None), max_len=7),
    }


def _empresa_emitente_dict(emp) -> dict[str, Any]:
    end = _participante_endereco(emp)
    return {
        'cnpj': _digits(emp.cnpj, max_len=14),
        'x_nome': _text(emp.razao_social) or _text(emp.nome_fantasia),
        'x_fant': _text(emp.nome_fantasia) or None,
        'ie': _text(emp.ie),
        'crt': _resolver_crt_empresa(emp),
        'fone': _digits(getattr(emp, 'telefone', None), max_len=14) or None,
        **end,
    }


def _resolver_crt_empresa(emp) -> str:
    regime = _text(getattr(emp, 'regime_tributario', None)).lower()
    if 'simples' in regime:
        return '1'
    if regime:
        return '3'
    return ''


def _cliente_dest_dict(cli) -> dict[str, Any]:
    end = _participante_endereco(cli)
    doc = _digits(cli.cnpj, max_len=14)
    return {
        'tipo': 'cliente',
        'cnpj': doc if len(doc) == 14 else '',
        'cpf': doc if len(doc) == 11 else '',
        'x_nome': _text(cli.razao_social) or _text(cli.nome_fantasia),
        'ie': _text(cli.ie),
        **end,
    }


def _ie_from_origem(nf: NFeEntrada) -> str:
    """Fallback da IE do destinatário a partir da NF-e de origem / dest_json."""
    # 1) Snapshot gravado na entrada
    dest_snap = nf.dest_json if isinstance(nf.dest_json, dict) else {}
    ie = _text(dest_snap.get('ie') or dest_snap.get('IE'))
    if ie:
        return ie

    # 2) NF-e saída operacional vinculada
    origem = getattr(nf, 'nfe_saida_origem', None)
    if origem is not None:
        cli = getattr(origem, 'cliente', None)
        if cli is not None and _text(cli.ie):
            return _text(cli.ie)
        for attr in ('xml_autorizado', 'xml_nfe_gerado'):
            xml = _text(getattr(origem, attr, None))
            if not xml:
                continue
            import re

            m = re.search(
                r'<dest\b[^>]*>.*?<IE>([^<]+)</IE>',
                xml,
                flags=re.IGNORECASE | re.DOTALL,
            )
            if m:
                return _text(m.group(1))

    # 3) NF-e histórica vinculada
    hist = getattr(nf, 'nfe_saida_historica_origem', None)
    if hist is not None:
        dj = hist.dest_json if isinstance(getattr(hist, 'dest_json', None), dict) else {}
        ie_h = _text(dj.get('ie') or dj.get('IE'))
        if ie_h:
            return ie_h
        cli_h = getattr(hist, 'cliente', None)
        if cli_h is not None and _text(cli_h.ie):
            return _text(cli_h.ie)

    return ''


def _fornecedor_dest_dict(forn) -> dict[str, Any]:
    end = _participante_endereco(forn)
    doc = _digits(forn.cnpj, max_len=14)
    return {
        'tipo': 'fornecedor',
        'cnpj': doc if len(doc) == 14 else '',
        'cpf': doc if len(doc) == 11 else '',
        'x_nome': _text(forn.razao_social) or _text(forn.nome_fantasia),
        'ie': _text(forn.ie),
        **end,
    }


def _id_dest_from_cfop(cfop: str) -> str:
    cf = _digits(cfop, max_len=4)
    if not cf:
        return '1'
    return {'1': '1', '2': '2', '3': '3', '5': '2', '6': '3', '7': '3'}.get(cf[0], '1')


def _linha_item(item: ItemNFeEntrada, *, n_item: int) -> dict[str, Any]:
    q = _dec(item.quantidade)
    v_un = _dec(item.valor)
    v_prod = (q * v_un).quantize(Decimal('0.01'))
    snap = item.snapshot_produto or {}
    desc = _text(item.descricao_xml) or _text(snap.get('descricao')) or _text(getattr(item.produto, 'descricao', None))
    cod = _text(snap.get('codigo_completo')) or _text(getattr(item.produto, 'codigo_completo', None)) or str(item.pk)
    return {
        'item_id': item.pk,
        'n_item': n_item,
        'c_prod': cod[:60],
        'x_prod': desc[:120] or 'Item',
        'ncm': _digits(item.ncm, max_len=8),
        'cfop': _digits(item.cfop, max_len=4),
        'u_com': _text(item.unidade)[:6],
        'q_com': q,
        'v_un_com': v_un,
        'v_prod': v_prod,
        'impostos_json': dict(item.impostos_json or {}),
    }


def gerar_dados_preview_nfe_entrada(nf: NFeEntrada) -> dict[str, Any]:
    """Monta payload interno para validação e XML oficial de entrada própria."""
    if nf.tipo_origem != NFeEntrada.TipoOrigem.ENTRADA_PROPRIA_EMITIDA:
        return {
            'bloqueado': True,
            'mensagem': 'Preview disponível apenas para NF-e entrada própria emitida.',
        }

    emp = nf.empresa_emitente
    if not emp:
        return {'bloqueado': True, 'mensagem': 'Empresa emitente obrigatória.'}

    if nf.cliente_destinatario_id:
        dest = _cliente_dest_dict(nf.cliente_destinatario)
    elif nf.fornecedor_id:
        dest = _fornecedor_dest_dict(nf.fornecedor)
    else:
        dest = {}

    # Devolução: se o cadastro do cliente veio sem IE, tenta a origem (saída/XML).
    if not _text(dest.get('ie')):
        ie_origem = _ie_from_origem(nf)
        if ie_origem:
            dest['ie'] = ie_origem
            dest['ie_origem'] = 'nfe_origem'

    itens_db = list(nf.itens.select_related('produto').order_by('id'))
    itens = [_linha_item(it, n_item=idx) for idx, it in enumerate(itens_db, start=1)]
    cfop_ref = itens[0]['cfop'] if itens else ''
    uf_emit = _text(emp.uf)[:2].upper()
    c_uf = UF_IBGE.get(uf_emit, '35')

    ide = {
        'tp_nf': '0',
        'tp_amb': '2' if nf.ambiente_emissao != NFeEntrada.AmbienteEmissao.PRODUCAO else '1',
        'fin_nfe': _text(nf.fin_nfe) or '',
        'nat_op': _text(nf.nat_op),
        'id_dest': _id_dest_from_cfop(cfop_ref),
        'c_uf': c_uf,
        'dh_emi': nf.data.isoformat() if nf.data else '',
        'serie_nfe': _text(nf.serie_nfe),
        'numero_nfe': _text(nf.numero_nfe),
        'codigo_numerico': _text(nf.codigo_numerico),
        'chave_nfe_referenciada': _digits(nf.chave_nfe_referenciada, max_len=44),
    }

    totais = _calcular_totais(itens)

    return {
        'bloqueado': False,
        'nf_entrada_id': nf.pk,
        'numero': nf.numero,
        'tipo_origem': nf.tipo_origem,
        'ambiente_emissao': nf.ambiente_emissao or NFeEntrada.AmbienteEmissao.HOMOLOGACAO,
        'chave_acesso': _text(nf.chave_acesso),
        'emitente': _empresa_emitente_dict(emp),
        'destinatario': dest,
        'ide': ide,
        'itens': itens,
        'totais': totais,
        'avisos': ['XML de entrada própria — homologação, sem transmissão SEFAZ.'],
    }


def _calcular_totais(itens: list[dict[str, Any]]) -> dict[str, str]:
    v_prod = Decimal('0')
    v_icms = Decimal('0')
    v_pis = Decimal('0')
    v_cofins = Decimal('0')
    v_ipi = Decimal('0')
    v_ipi_devol = Decimal('0')
    v_bc = Decimal('0')

    for linha in itens:
        v_prod += _dec(linha.get('v_prod'))
        imp = linha.get('impostos_json') or {}
        icms = imp.get('icms') or {}
        pis = imp.get('pis') or {}
        cof = imp.get('cofins') or {}
        ipi = imp.get('ipi') or {}
        devol = imp.get('imposto_devol') if isinstance(imp.get('imposto_devol'), dict) else {}
        v_icms += _dec(icms.get('valor'))
        v_pis += _dec(pis.get('valor'))
        v_cofins += _dec(cof.get('valor'))
        # Em devolução, IPI destacado via vIPIDevol (não soma em vIPI).
        v_ipi_devol += _dec(devol.get('v_ipi_devol') or devol.get('vIPIDevol'))
        if not devol:
            v_ipi += _dec(ipi.get('valor'))
        v_bc += _dec(icms.get('base'))

    q = Decimal('0.01')
    return {
        'v_prod': f'{v_prod.quantize(q)}',
        'v_nf': f'{v_prod.quantize(q)}',
        'v_icms': f'{v_icms.quantize(q)}',
        'v_pis': f'{v_pis.quantize(q)}',
        'v_cofins': f'{v_cofins.quantize(q)}',
        'v_ipi': f'{v_ipi.quantize(q)}',
        'v_ipi_devol': f'{v_ipi_devol.quantize(q)}',
        'v_bc': f'{v_bc.quantize(q)}',
        'v_desc': '0.00',
    }
