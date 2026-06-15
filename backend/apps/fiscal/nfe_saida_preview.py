"""NF-e Saída 3 — prévia XML/DANFE (rascunho, sem SEFAZ, estoque ou financeiro)."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from decimal import Decimal
from io import BytesIO
from typing import Any
from xml.dom import minidom

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from apps.core.pdf.formatters import dec, endereco_cadastro, fmt_cnpj, format_currency_br, format_date_br
from apps.fiscal.models import ItemNFeSaida, NFeSaida
from apps.fiscal.snapshot_fiscal_helpers import (
    get_reforma_tributaria_snapshot,
    montar_reforma_item_exibicao,
    reforma_configurada_no_snapshot,
)
from apps.fiscal.nfe_saida_from_faturamento import STATUS_NFE_RASCUNHO
from apps.fiscal.validacao_nfe_saida import (
    MODO_VALIDACAO_LEVE,
    STATUS_COM_PENDENCIAS,
    TIPO_ALERTA,
    TIPO_PENDENCIA,
    validar_nfe_saida_para_emissao,
)
from apps.regras_fiscais.recomendacoes_nfe_config import (
    RECOMENDACOES_NFE_KEYS,
    normalizar_recomendacoes_nfe,
)

NS_NFE = 'http://www.portalfiscal.inf.br/nfe'
MSG_XML_PREVIEW = 'XML de prévia gerado sem transmissão para SEFAZ.'
MSG_DANFE_PREVIEW = 'DANFE de prévia gerado sem valor fiscal e sem protocolo SEFAZ.'
MSG_PREVIEW_PENDENCIAS = 'Prévia gerada com pendências. Corrija antes da emissão definitiva.'

UF_IBGE: dict[str, str] = {
    'AC': '12',
    'AL': '27',
    'AP': '16',
    'AM': '13',
    'BA': '29',
    'CE': '23',
    'DF': '53',
    'ES': '32',
    'GO': '52',
    'MA': '21',
    'MT': '51',
    'MS': '50',
    'MG': '31',
    'PA': '15',
    'PB': '25',
    'PR': '41',
    'PE': '26',
    'PI': '22',
    'RJ': '33',
    'RN': '24',
    'RS': '43',
    'RO': '11',
    'RR': '14',
    'SC': '42',
    'SP': '35',
    'SE': '28',
    'TO': '17',
}

RECOMENDACOES_PREPARATORIAS = frozenset(
    {
        'nao_preencher_data_hora_saida',
        'exibir_chave_dfe_referenciado',
        'emitir_etiqueta_danfe_simplificado',
        'enviar_retencoes_como_desconto',
    },
)

LABEL_RECOMENDACAO: dict[str, str] = {
    'danfe_paisagem': 'Layout DANFE em paisagem',
    'ordenar_itens_por_descricao': 'Itens ordenados por descrição',
    'ocultar_destaque_pis_cofins': 'Destaque PIS/COFINS oculto no DANFE',
    'ocultar_destaque_icms_st_itens': 'Destaque ICMS ST oculto nos itens',
    'exibir_email_destinatario': 'E-mail do destinatário exibido',
    'exibir_cest_informacoes_item': 'CEST exibido nos itens',
    'exibir_pedido_compra_item': 'Pedido de compra exibido nos itens',
}


def _norm_status(status: str | None) -> str:
    return (status or '').strip().upper()


def _digits(val: str | None, *, max_len: int | None = None) -> str:
    d = ''.join(c for c in str(val or '') if c.isdigit())
    if max_len is not None:
        return d[:max_len]
    return d


def _text(val: str | None) -> str:
    return (val or '').strip()


def _dec_str(v, places: int = 2) -> str:
    return f'{dec(v):.{places}f}'


def _bloqueio_preview(nf: NFeSaida) -> dict[str, Any] | None:
    from apps.fiscal.nfe_saida_bloqueio import nf_autorizada_homologacao, nf_autorizada_producao

    if nf_autorizada_homologacao(nf) or nf_autorizada_producao(nf):
        return None

    st = _norm_status(nf.status)
    if st in ('CANCELADA', 'CANCELADO', 'CANCELADA_INTERNA'):
        return {
            'preview': False,
            'bloqueado': True,
            'mensagens': ['NF-e cancelada: prévia não disponível nesta fase.'],
        }
    if st in ('EMITIDA', 'EMITIDO'):
        return {
            'preview': False,
            'bloqueado': True,
            'mensagens': ['NF-e já emitida: use o documento autorizado (fase futura).'],
        }
    if st != STATUS_NFE_RASCUNHO and st not in ('', 'PENDENTE'):
        return {
            'preview': False,
            'bloqueado': True,
            'mensagens': [f'Status «{nf.status}»: prévia disponível apenas para rascunho.'],
        }
    return None


def _extrair_pendencias_alertas(validacao: dict[str, Any]) -> tuple[list[dict], list[dict]]:
    pendencias: list[dict] = []
    alertas: list[dict] = []
    for grupo, itens in (validacao.get('grupos') or {}).items():
        for it in itens or []:
            row = {**it, 'grupo': grupo}
            if it.get('tipo') == TIPO_PENDENCIA:
                pendencias.append(row)
            elif it.get('tipo') == TIPO_ALERTA:
                alertas.append(row)
    return pendencias, alertas


def _ncm_item(item: ItemNFeSaida) -> str:
    snap_f = item.snapshot_fiscal or {}
    snap_p = item.snapshot_produto or {}
    return _text(snap_f.get('ncm') or snap_p.get('ncm_codigo_snapshot'))


def _cfop_item(item: ItemNFeSaida) -> str:
    from apps.fiscal.snapshot_fiscal_helpers import cfop_from_snapshot_fiscal

    return cfop_from_snapshot_fiscal(item.snapshot_fiscal)


def _descricao_item(item: ItemNFeSaida) -> str:
    snap_p = item.snapshot_produto or {}
    d = _text(snap_p.get('descricao_produto_snapshot'))
    if d:
        return d
    return _text(item.produto.descricao) if item.produto_id else ''


def _codigo_item(item: ItemNFeSaida) -> str:
    snap_p = item.snapshot_produto or {}
    c = _text(snap_p.get('codigo_completo_snapshot'))
    if c:
        return c
    return _text(getattr(item.produto, 'codigo_completo', '')) if item.produto_id else str(item.pk)


def _unidade_item(item: ItemNFeSaida) -> str:
    snap_f = item.snapshot_fiscal or {}
    snap_p = item.snapshot_produto or {}
    snap_c = item.snapshot_comercial or {}
    u = _text(
        snap_f.get('unidade_negociada')
        or snap_c.get('unidade_negociada')
        or snap_p.get('unidade_snapshot'),
    )
    if u:
        return u
    return _text(getattr(item.produto, 'unidade', '')) if item.produto_id else 'UN'


def _valor_linha(item: ItemNFeSaida) -> Decimal:
    snap_c = item.snapshot_comercial or {}
    if snap_c.get('valor_total') not in (None, ''):
        return dec(snap_c['valor_total'])
    total = dec(item.quantidade) * dec(item.valor)
    if snap_c.get('desconto') not in (None, ''):
        total -= dec(snap_c['desconto'])
    return total


def _codigo_municipio_preview(uf: str, cidade: str = '') -> str:
    from apps.fiscal.nfe_emissao.xml_serializacao import codigo_municipio_ibge

    return codigo_municipio_ibge(uf, cidade=cidade)


def _crt_emitente(regime: str) -> str:
    r = (regime or '').lower()
    if 'simples' in r:
        return '1'
    if 'presumido' in r:
        return '3'
    if 'real' in r:
        return '3'
    return '3'


def obter_recomendacoes_nfe_danfe(nfe_saida: NFeSaida) -> dict[str, Any]:
    """Consolida recomendações do snapshot/regra fiscal (OR entre itens)."""
    from apps.regras_fiscais.models import RegraFiscalSaida

    merged: dict[str, bool] = {k: False for k in RECOMENDACOES_NFE_KEYS}
    fontes: list[str] = []
    regra_ids: set[int] = set()

    for item in nfe_saida.itens.all():
        snap = item.snapshot_fiscal or {}
        snap_rec = normalizar_recomendacoes_nfe(snap.get('recomendacoes_nfe'))
        if snap_rec:
            fontes.append(f'item:{item.pk}:snapshot')
            for k, v in snap_rec.items():
                if v:
                    merged[k] = True
        rid = snap.get('regra_fiscal_saida_id')
        if rid:
            try:
                regra_ids.add(int(rid))
            except (TypeError, ValueError):
                pass

    for rid in regra_ids:
        try:
            regra = RegraFiscalSaida.objects.only('recomendacoes_nfe').get(pk=rid)
        except RegraFiscalSaida.DoesNotExist:
            continue
        norm = normalizar_recomendacoes_nfe(regra.recomendacoes_nfe)
        if not norm:
            continue
        fontes.append(f'regra:{rid}')
        for k, v in norm.items():
            if v:
                merged[k] = True

    aplicadas: list[str] = []
    nao_aplicadas: list[str] = []
    preparatorias: list[str] = []

    for key in RECOMENDACOES_NFE_KEYS:
        if not merged.get(key):
            continue
        label = LABEL_RECOMENDACAO.get(key, key)
        if key in RECOMENDACOES_PREPARATORIAS:
            preparatorias.append(label)
            nao_aplicadas.append(f'{label} (preparatória nesta fase)')
        elif key == 'danfe_paisagem':
            aplicadas.append(label)
        elif key == 'ordenar_itens_por_descricao':
            aplicadas.append(label)
        elif key in ('ocultar_destaque_pis_cofins', 'ocultar_destaque_icms_st_itens'):
            aplicadas.append(label)
        elif key == 'exibir_email_destinatario':
            aplicadas.append(label)
        elif key == 'exibir_cest_informacoes_item':
            aplicadas.append(label)
        elif key == 'exibir_pedido_compra_item':
            nao_aplicadas.append(f'{label} (sem dado de pedido de compra no item)')
        else:
            nao_aplicadas.append(f'{label} (preparatória nesta fase)')

    return {
        'recomendacoes': {k: v for k, v in merged.items() if v},
        'recomendacoes_aplicadas': aplicadas,
        'recomendacoes_nao_aplicadas': nao_aplicadas,
        'recomendacoes_preparatorias': preparatorias,
        'fontes': fontes,
    }


def _ordenar_itens(nf: NFeSaida, itens: list[ItemNFeSaida], recs: dict[str, bool]) -> list[ItemNFeSaida]:
    if recs.get('ordenar_itens_por_descricao'):
        return sorted(itens, key=lambda i: (_descricao_item(i).upper(), i.pk))
    return list(itens)


def gerar_dados_preview_nfe_saida(
    nfe_saida: NFeSaida,
    *,
    incluir_validacao_emissao: bool = True,
) -> dict[str, Any]:
    from apps.fiscal.nfe_saida_xml_nfelib import fone_nfe_digits
    from apps.fiscal.nfe_transp_bindings import montar_transporte_dados_nfe

    nf = nfe_saida
    bloqueio = _bloqueio_preview(nf)
    if bloqueio:
        return {**bloqueio, 'nfe_saida_id': nf.pk, 'numero': nf.numero, 'status': nf.status}

    if incluir_validacao_emissao:
        validacao = validar_nfe_saida_para_emissao(nf)
    else:
        validacao = {
            'status_prontidao': STATUS_COM_PENDENCIAS,
            'pode_emitir': False,
        }
    rec_info = obter_recomendacoes_nfe_danfe(nf)
    recs = rec_info['recomendacoes']

    pedido = nf.pedido_venda
    emp = pedido.empresa_emitente if pedido and pedido.empresa_emitente_id else None
    cli = nf.cliente
    uf_origem = _text(emp.uf) if emp else ''
    uf_destino = _text(cli.uf) if cli else ''
    id_dest = '1'
    if uf_origem and uf_destino:
        id_dest = '1' if uf_origem == uf_destino else '2'

    itens_raw = list(nf.itens.select_related('produto').all())
    itens_ord = _ordenar_itens(nf, itens_raw, recs)

    linhas = []
    soma_prod = Decimal('0')
    soma_desc = Decimal('0')
    for idx, item in enumerate(itens_ord, start=1):
        snap_f = item.snapshot_fiscal or {}
        snap_c = item.snapshot_comercial or {}
        v_prod = _valor_linha(item)
        soma_prod += v_prod
        desconto = dec(snap_c.get('desconto', 0))
        soma_desc += desconto
        pc_num = _text(item.pedido_cliente_numero) or _text(nf.pedido_cliente_numero)
        pc_item = _text(item.pedido_cliente_item)
        pedido_cli = pc_num
        if pc_item:
            pedido_cli = f'{pc_num} / {pc_item}' if pc_num else pc_item
        linhas.append(
            {
                'n_item': idx,
                'item_id': item.pk,
                'c_prod': _codigo_item(item),
                'x_prod': _descricao_item(item),
                'ncm': _ncm_item(item),
                'cfop': _cfop_item(item),
                'u_com': _unidade_item(item),
                'q_com': str(item.quantidade),
                'v_un_com': _dec_str(item.valor),
                'v_prod': _dec_str(v_prod),
                'cest': _text(snap_f.get('cest')),
                'icms': {
                    'cst': _text(snap_f.get('cst_icms')),
                    'aliquota': _text(snap_f.get('aliquota_icms') or snap_f.get('icms_saida_percentual')),
                },
                'ipi': {
                    'cst': _text(snap_f.get('cst_ipi')),
                    'aliquota': _text(snap_f.get('aliquota_ipi') or snap_f.get('ipi_saida_percentual')),
                },
                'pis': {
                    'cst': _text(snap_f.get('cst_pis')),
                    'aliquota': _text(snap_f.get('aliquota_pis') or snap_f.get('pis_saida_percentual')),
                },
                'cofins': {
                    'cst': _text(snap_f.get('cst_cofins')),
                    'aliquota': _text(snap_f.get('aliquota_cofins') or snap_f.get('cofins_saida_percentual')),
                },
                'snapshot_fiscal': snap_f,
                'reforma_tributaria': snap_f.get('reforma_tributaria') or snap_f.get('ibs_cbs'),
                'pedido_compra': _text(snap_c.get('pedido_compra') or snap_c.get('numero_pedido_compra')),
                'pedido_cliente': pedido_cli,
                'pedido_cliente_numero': pc_num,
                'pedido_cliente_item': pc_item,
            },
        )

    avisos = []
    if not emp:
        avisos.append('Emitente não identificado; preencha pedido com empresa emitente.')
    if validacao.get('status_prontidao') == STATUS_COM_PENDENCIAS:
        avisos.append(MSG_PREVIEW_PENDENCIAS)
    if not nf.faturamento_pedido_venda_id:
        avisos.append('NF-e de origem manual; confirme dados comerciais e fiscais.')

    return {
        'preview': True,
        'bloqueado': False,
        'nfe_saida_id': nf.pk,
        'numero': nf.numero,
        'status': nf.status,
        'status_prontidao': validacao.get('status_prontidao'),
        'pode_emitir': validacao.get('pode_emitir'),
        'emitente': {
            'cnpj': _digits(emp.cnpj) if emp else '',
            'x_nome': _text(emp.razao_social) if emp else '',
            'ie': _text(emp.ie) if emp else '',
            'uf': uf_origem,
            'crt': _crt_emitente(emp.regime_tributario if emp else ''),
            'logradouro': _text(emp.logradouro) if emp else '',
            'numero': _text(emp.numero) if emp else '',
            'complemento': _text(emp.complemento) if emp else '',
            'bairro': _text(emp.bairro) if emp else '',
            'cidade': _text(emp.cidade) if emp else '',
            'cep': _text(emp.cep) if emp else '',
            'telefone': _text(emp.telefone) if emp else '',
            'fone': fone_nfe_digits(emp.telefone if emp else '') or '',
            'email': _text(emp.email) if emp else '',
            'site': _text(emp.site) if emp else '',
            'ender': endereco_cadastro(
                emp.logradouro if emp else '',
                emp.numero if emp else '',
                emp.complemento if emp else '',
                emp.bairro if emp else '',
                emp.cidade if emp else '',
                emp.uf if emp else '',
                emp.cep if emp else '',
            ),
        },
        'destinatario': {
            'cnpj': _digits(cli.cnpj) if cli else '',
            'x_nome': _text(cli.razao_social) if cli else '',
            'ie': _text(cli.ie) if cli else '',
            'uf': uf_destino,
            'email': _text(cli.email_nf or cli.email) if cli else '',
            'exibir_email': bool(recs.get('exibir_email_destinatario') and cli),
            'logradouro': _text(cli.logradouro) if cli else '',
            'numero': _text(cli.numero) if cli else '',
            'complemento': _text(cli.complemento) if cli else '',
            'bairro': _text(cli.bairro) if cli else '',
            'cidade': _text(cli.cidade) if cli else '',
            'cep': _text(cli.cep) if cli else '',
            'ender': endereco_cadastro(
                cli.logradouro if cli else '',
                cli.numero if cli else '',
                cli.complemento if cli else '',
                cli.bairro if cli else '',
                cli.cidade if cli else '',
                cli.uf if cli else '',
                cli.cep if cli else '',
            ),
        },
        'ide': {
            'c_uf': UF_IBGE.get(uf_origem, '35'),
            'nat_op': 'Venda de mercadoria',
            'mod': '55',
            'serie': 'PREVIEW',
            'n_nf': nf.numero,
            'dh_emi': timezone.localtime(timezone.now()).isoformat(),
            'tp_nf': '1',
            'id_dest': id_dest,
            'c_mun_fg': _codigo_municipio_preview(uf_origem, emp.cidade if emp else ''),
        },
        'itens': linhas,
        'totais': {
            'v_prod': _dec_str(soma_prod),
            'v_desc': _dec_str(soma_desc),
            'v_nf': _dec_str(nf.valor_total),
        },
        'transporte': montar_transporte_dados_nfe(nf),
        'origem': {
            'pedido_venda_id': nf.pedido_venda_id,
            'faturamento_id': nf.faturamento_pedido_venda_id,
            'manual': not bool(nf.faturamento_pedido_venda_id),
        },
        'observacoes': '\n'.join(
            x
            for x in (
                _text(nf.observacao_origem),
                _text(nf.observacoes_nfe),
                _text(nf.pedido_cliente_observacao),
            )
            if x
        ),
        'informacoes_adicionais': '\n'.join(
            x for x in (_text(nf.informacoes_adicionais), _text(nf.informacoes_fisco)) if x
        ),
        'pedido_cliente_numero': _text(nf.pedido_cliente_numero),
        'modo_atendimento_estoque': nf.modo_atendimento_estoque,
        'recomendacoes': rec_info,
        'validacao_resumo': {
            'total_pendencias': validacao.get('total_pendencias'),
            'total_alertas': validacao.get('total_alertas'),
        },
        'avisos': avisos,
        'marcas_preview': [
            'Prévia sem valor fiscal',
            'Rascunho não autorizado',
            'Não transmitir / sem protocolo SEFAZ',
        ],
    }


def _sub(parent: ET.Element, tag: str, text: str | None = None) -> ET.Element:
    el = ET.SubElement(parent, tag)
    if text is not None and str(text).strip() != '':
        el.text = str(text).strip()
    return el


def _ender(parent: ET.Element, prefix: str, *, logr, nro, compl, bairro, mun, uf, cep, fone=None):
    ender = ET.SubElement(parent, prefix)
    _sub(ender, 'xLgr', logr or 'Não informado')
    _sub(ender, 'nro', nro or 'S/N')
    if compl:
        _sub(ender, 'xCpl', compl)
    if bairro:
        _sub(ender, 'xBairro', bairro)
    _sub(ender, 'xMun', mun or 'Não informado')
    _sub(ender, 'UF', uf or 'SP')
    if cep:
        _sub(ender, 'CEP', _digits(cep))
    if fone:
        _sub(ender, 'fone', _digits(fone, max_len=14))
    return ender


def _build_imposto_det(imposto: ET.Element, snap: dict, linha: dict) -> None:
    icms = ET.SubElement(imposto, 'ICMS')
    icms_grp = ET.SubElement(icms, 'ICMS00')
    _sub(icms_grp, 'CST', linha['icms']['cst'] or '00')
    if linha['icms']['aliquota']:
        _sub(icms_grp, 'pICMS', linha['icms']['aliquota'])

    if linha['ipi']['cst'] or linha['ipi']['aliquota']:
        ipi = ET.SubElement(imposto, 'IPI')
        ipi_sn = ET.SubElement(ipi, 'IPINT' if linha['ipi']['cst'] in ('52', '53', '54', '55') else 'IPITrib')
        if linha['ipi']['cst']:
            _sub(ipi_sn, 'CST', linha['ipi']['cst'])

    pis = ET.SubElement(imposto, 'PIS')
    pis_sn = ET.SubElement(pis, 'PISNT' if linha['pis']['cst'] in ('04', '05', '06', '07', '08', '09') else 'PISAliq')
    if linha['pis']['cst']:
        _sub(pis_sn, 'CST', linha['pis']['cst'])

    cof = ET.SubElement(imposto, 'COFINS')
    cof_sn = ET.SubElement(
        cof,
        'COFINSNT' if linha['cofins']['cst'] in ('04', '05', '06', '07', '08', '09') else 'COFINSAliq',
    )
    if linha['cofins']['cst']:
        _sub(cof_sn, 'CST', linha['cofins']['cst'])

    if snap.get('reforma_tributaria') or snap.get('ibs_cbs'):
        _sub(imposto, 'infAdProd', 'Bloco Reforma Tributária (prévia preparatória)')


def _xml_preview_string(dados: dict[str, Any]) -> str:
    ET.register_namespace('', NS_NFE)
    root = ET.Element('{%s}NFe' % NS_NFE)
    inf = ET.SubElement(root, '{%s}infNFe' % NS_NFE, Id=f'NFePREVIEW{dados["nfe_saida_id"]}', versao='4.00')

    ide = ET.SubElement(inf, 'ide')
    ide_map = dados['ide']
    for tag, key in (
        ('cUF', 'c_uf'),
        ('natOp', None),
        ('mod', 'mod'),
        ('serie', 'serie'),
        ('nNF', None),
        ('dhEmi', 'dh_emi'),
        ('tpNF', 'tp_nf'),
        ('idDest', 'id_dest'),
        ('cMunFG', 'c_mun_fg'),
    ):
        if key is None and tag == 'natOp':
            _sub(ide, tag, ide_map.get('nat_op'))
        elif key is None and tag == 'nNF':
            _sub(ide, tag, dados['numero'])
        else:
            _sub(ide, tag, ide_map.get(key))

    emit = dados['emitente']
    emit_el = ET.SubElement(inf, 'emit')
    _sub(emit_el, 'CNPJ', emit['cnpj'])
    _sub(emit_el, 'xNome', emit['x_nome'])
    _sub(emit_el, 'IE', emit['ie'])
    _sub(emit_el, 'CRT', emit['crt'])
    _ender(
        emit_el,
        'enderEmit',
        logr=emit.get('logradouro'),
        nro=emit.get('numero'),
        compl=emit.get('complemento'),
        bairro=emit.get('bairro'),
        mun=emit.get('cidade'),
        uf=emit['uf'],
        cep=emit.get('cep'),
        fone=emit.get('fone') or emit.get('telefone'),
    )

    dest = dados['destinatario']
    dest_el = ET.SubElement(inf, 'dest')
    if len(dest['cnpj']) == 14:
        _sub(dest_el, 'CNPJ', dest['cnpj'])
    elif dest['cnpj']:
        _sub(dest_el, 'CPF', dest['cnpj'])
    _sub(dest_el, 'xNome', dest['x_nome'])
    _sub(dest_el, 'indIEDest', '1' if dest['ie'] else '9')
    if dest['ie']:
        _sub(dest_el, 'IE', dest['ie'])
    _ender(
        dest_el,
        'enderDest',
        logr=dest.get('logradouro'),
        nro=dest.get('numero'),
        compl=dest.get('complemento'),
        bairro=dest.get('bairro'),
        mun=dest.get('cidade'),
        uf=dest['uf'],
        cep=dest.get('cep'),
    )

    for idx, linha in enumerate(dados['itens'], start=1):
        det = ET.SubElement(inf, 'det', nItem=str(idx))
        prod = ET.SubElement(det, 'prod')
        _sub(prod, 'cProd', linha['c_prod'])
        _sub(prod, 'xProd', linha['x_prod'])
        _sub(prod, 'NCM', linha['ncm'])
        if linha.get('cest'):
            _sub(prod, 'CEST', _digits(linha['cest']))
        _sub(prod, 'CFOP', linha['cfop'])
        _sub(prod, 'uCom', linha['u_com'])
        _sub(prod, 'qCom', linha['q_com'])
        _sub(prod, 'vUnCom', linha['v_un_com'])
        _sub(prod, 'vProd', linha['v_prod'])
        _sub(prod, 'uTrib', linha['u_com'])
        _sub(prod, 'qTrib', linha['q_com'])
        _sub(prod, 'vUnTrib', linha['v_un_com'])
        _sub(prod, 'indTot', '1')
        x_ped = _text(linha.get('x_ped'))
        n_item_ped = _text(linha.get('n_item_ped'))
        if not x_ped and not n_item_ped:
            from apps.fiscal.nfe_integracao.danfe_xml_adicionais import resolver_xped_nitemped_item

            x_ped, n_item_ped = resolver_xped_nitemped_item(None, linha)
        if x_ped:
            _sub(prod, 'xPed', x_ped[:15])
        if n_item_ped:
            _sub(prod, 'nItemPed', n_item_ped[:6])
        imposto = ET.SubElement(det, 'imposto')
        _build_imposto_det(imposto, linha.get('snapshot_fiscal') or {}, linha)
        inf_ad_prod = _text(linha.get('inf_ad_prod'))
        if inf_ad_prod:
            _sub(det, 'infAdProd', inf_ad_prod[:500])

    total = ET.SubElement(inf, 'total')
    icms_tot = ET.SubElement(total, 'ICMSTot')
    _sub(icms_tot, 'vProd', dados['totais']['v_prod'])
    _sub(icms_tot, 'vDesc', dados['totais']['v_desc'])
    _sub(icms_tot, 'vNF', dados['totais']['v_nf'])

    tr = dados.get('transporte') or {}
    transp = ET.SubElement(inf, 'transp')
    _sub(transp, 'modFrete', tr.get('mod_frete', '9'))
    if _text(tr.get('transportadora_nome')):
        transporta = ET.SubElement(transp, 'transporta')
        cnpj = _digits(tr.get('transportadora_cnpj'))
        if len(cnpj) == 14:
            _sub(transporta, 'CNPJ', cnpj)
        _sub(transporta, 'xNome', tr['transportadora_nome'][:60])
        if _text(tr.get('transportadora_ie')):
            _sub(transporta, 'IE', tr['transportadora_ie'][:14])
        if _text(tr.get('transportadora_ender')):
            _sub(transporta, 'xEnder', tr['transportadora_ender'][:60])
        if _text(tr.get('transportadora_mun')):
            _sub(transporta, 'xMun', tr['transportadora_mun'][:60])
        if _text(tr.get('transportadora_uf')):
            _sub(transporta, 'UF', tr['transportadora_uf'][:2])
    q_vol = int(tr.get('quantidade_volumes') or 0)
    if q_vol or tr.get('peso_bruto') or tr.get('peso_liquido'):
        vol = ET.SubElement(transp, 'vol')
        if q_vol:
            _sub(vol, 'qVol', str(q_vol))
        if _text(tr.get('especie_volumes')):
            _sub(vol, 'esp', tr['especie_volumes'][:60])
        if _text(tr.get('marca_volumes')):
            _sub(vol, 'marca', tr['marca_volumes'][:60])
        if _text(tr.get('numeracao_volumes')):
            _sub(vol, 'nVol', tr['numeracao_volumes'][:60])
        if Decimal(str(tr.get('peso_bruto') or 0)) > 0:
            _sub(vol, 'pesoB', tr['peso_bruto'])
        if Decimal(str(tr.get('peso_liquido') or 0)) > 0:
            _sub(vol, 'pesoL', tr['peso_liquido'])

    inf_adic = ET.SubElement(inf, 'infAdic')
    inf_cpl = [
        'XML DE PRÉVIA — NÃO TRANSMITIR',
        'Rascunho não autorizado',
        'Sem protocolo SEFAZ',
    ]
    if dados.get('observacoes'):
        inf_cpl.append(dados['observacoes'])
    for av in dados.get('avisos') or []:
        inf_cpl.append(av)
    _sub(inf_adic, 'infCpl', ' | '.join(inf_cpl))

    rough = ET.tostring(root, encoding='unicode')
    parsed = minidom.parseString(rough)
    body = parsed.toxml()
    comentario = (
        ' XML DE PRÉVIA — NÃO TRANSMITIR. Rascunho não autorizado. Sem protocolo SEFAZ. '
    )
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<!--{comentario}-->\n{body}'


def gerar_preview_xml_nfe_saida(nfe_saida: NFeSaida) -> dict[str, Any]:
    from apps.fiscal.nfe_integracao.adapters.nfelib_adapter import nfelib_disponivel

    if nfelib_disponivel():
        from apps.fiscal.nfe_saida_xml_nfelib import gerar_xml_oficial_nfe_saida

        payload = gerar_xml_oficial_nfe_saida(nfe_saida)
        if payload.get('bloqueado'):
            return payload
        avisos = list(payload.get('avisos') or [])
        if MSG_XML_PREVIEW not in avisos:
            avisos.append(MSG_XML_PREVIEW)
        mensagens = list(payload.get('mensagens') or [])
        if MSG_XML_PREVIEW not in mensagens:
            mensagens.insert(0, MSG_XML_PREVIEW)
        payload['avisos'] = avisos
        payload['mensagens'] = mensagens
        return payload

    dados = gerar_dados_preview_nfe_saida(nfe_saida)
    if dados.get('bloqueado'):
        return dados

    validacao = validar_nfe_saida_para_emissao(nfe_saida)
    pendencias, alertas = _extrair_pendencias_alertas(validacao)
    avisos = list(dados.get('avisos') or [])
    avisos.append(MSG_XML_PREVIEW)

    from apps.fiscal.nfe_integracao.danfe_xml_adicionais import enriquecer_linhas_xml_nfe

    enriquecer_linhas_xml_nfe(nfe_saida, dados)
    xml = _xml_preview_string(dados)
    return {
        'nfe_saida_id': nfe_saida.pk,
        'numero': nfe_saida.numero,
        'status': nfe_saida.status,
        'preview': True,
        'bloqueado': False,
        'xml': xml,
        'status_prontidao': validacao.get('status_prontidao'),
        'pode_emitir': validacao.get('pode_emitir'),
        'pendencias': pendencias,
        'alertas': alertas,
        'avisos': avisos,
        'mensagens': [MSG_XML_PREVIEW]
        + ([MSG_PREVIEW_PENDENCIAS] if validacao.get('status_prontidao') == STATUS_COM_PENDENCIAS else []),
        'recomendacoes_aplicadas': dados['recomendacoes']['recomendacoes_aplicadas'],
        'recomendacoes_nao_aplicadas': dados['recomendacoes']['recomendacoes_nao_aplicadas'],
        'marcas_preview': dados.get('marcas_preview'),
    }


def gerar_preview_danfe_nfe_saida(nfe_saida: NFeSaida) -> tuple[bytes, dict[str, Any]]:
    """NF-e Saída 3.5.4 — DANFE de conferência (rascunho/pré-emissão apenas)."""
    from apps.fiscal.danfe_render import DanfeBfrRenderError
    from apps.fiscal.nfe_saida_bloqueio import nf_autorizada_homologacao, nf_autorizada_producao

    if nf_autorizada_producao(nfe_saida):
        raise DanfeBfrRenderError(
            'NF-e autorizada em produção: use GET /api/nf-saidas/{id}/danfe-autorizado/ para o DANFE final.',
            nfe_saida_id=nfe_saida.pk,
            numero=nfe_saida.numero,
            status=nfe_saida.status,
            ambiente='1',
            erro_tipo='DanfePreviewNaoPermitido',
        )
    if nf_autorizada_homologacao(nfe_saida):
        raise DanfeBfrRenderError(
            'NF-e autorizada em homologação: use GET /api/nf-saidas/{id}/danfe-autorizado/ para o DANFE final.',
            nfe_saida_id=nfe_saida.pk,
            numero=nfe_saida.numero,
            status=nfe_saida.status,
            ambiente='2',
            erro_tipo='DanfePreviewNaoPermitido',
        )

    from apps.fiscal.danfe_conferencia import gerar_danfe_conferencia_pdf

    pdf, meta = gerar_danfe_conferencia_pdf(nfe_saida)
    if meta.get('bloqueado'):
        return pdf, meta
    validacao = validar_nfe_saida_para_emissao(nfe_saida, modo=MODO_VALIDACAO_LEVE)
    pendencias, alertas = _extrair_pendencias_alertas(validacao)
    rec_info = obter_recomendacoes_nfe_danfe(nfe_saida)
    meta.update(
        {
            'status_prontidao': validacao.get('status_prontidao'),
            'pendencias': pendencias,
            'alertas': alertas,
            'mensagens': [MSG_DANFE_PREVIEW]
            + ([MSG_PREVIEW_PENDENCIAS] if validacao.get('status_prontidao') == STATUS_COM_PENDENCIAS else []),
            'recomendacoes_aplicadas': rec_info.get('recomendacoes_aplicadas', []),
            'recomendacoes_nao_aplicadas': rec_info.get('recomendacoes_nao_aplicadas', []),
        },
    )
    return pdf, meta
