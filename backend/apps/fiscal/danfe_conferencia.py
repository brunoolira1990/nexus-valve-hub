"""NF-e Saída 3.5.4 — DANFE de conferência (layout real, sem valor fiscal / sem SEFAZ)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.utils import timezone

from apps.core.pdf.formatters import dec, endereco_cadastro, fmt_cnpj, format_currency_br, format_date_br
from apps.fiscal.models import NFeSaida
from apps.fiscal.nfe_saida_bloqueio import nf_autorizada_homologacao
from apps.fiscal.nfe_saida_preview import gerar_dados_preview_nfe_saida
from apps.fiscal.snapshot_fiscal_helpers import (
    get_cofins_snapshot,
    get_icms_snapshot,
    get_ipi_snapshot,
    get_pis_snapshot,
    get_reforma_tributaria_snapshot,
    montar_reforma_item_exibicao,
    reforma_configurada_no_snapshot,
)

MSG_CHAVE_NAO_GERADA = 'CHAVE DE ACESSO NÃO GERADA — NF-e ainda não autorizada'
MSG_CONSULTA_PORTAL = (
    'Consulta de autenticidade no portal nacional da NF-e '
    'www.nfe.fazenda.gov.br/portal ou no site da Sefaz Autorizadora'
)
MSG_AVISO_TOPO = 'DANFE de conferência — sem valor fiscal. Não transmitir. Sem protocolo SEFAZ.'

MODALIDADE_FRETE_LABEL = {
    '0': '0 - Contratação do Frete por conta do Remetente (CIF)',
    '1': '1 - Contratação do Frete por conta do Destinatário (FOB)',
    '2': '2 - Contratação do Frete por conta de Terceiros',
    '3': '3 - Transporte Próprio por conta do Remetente',
    '4': '4 - Transporte Próprio por conta do Destinatário',
    '9': '9 - Sem Ocorrência de Transporte',
}



def _text(val: str | None) -> str:
    return (str(val) if val is not None else '').strip()


def _fmt_serie_local(serie: str | None) -> str:
    digits = ''.join(c for c in str(serie or '') if c.isdigit())
    return str(int(digits)) if digits else str(serie or '').strip()


def _money(v) -> str:
    return format_currency_br(v)


def _qty(v) -> str:
    d = dec(v)
    if d == d.to_integral_value():
        return str(int(d))
    return f'{d:.3f}'.replace('.', ',')


def formatar_chave_acesso(chave: str | None) -> str:
    digits = ''.join(c for c in str(chave or '') if c.isdigit())
    if len(digits) != 44:
        return ''
    return ' '.join(digits[i : i + 4] for i in range(0, 44, 4))


def _serie_numero(dados: dict[str, Any], nf: NFeSaida) -> tuple[str, str]:
    ide = dados.get('ide') or {}
    serie = _text(ide.get('serie')) or 'RASCUNHO'
    numero = _text(ide.get('n_nf')) or _text(nf.numero) or str(nf.pk)
    return serie, numero


def _calcular_totais_imposto(linhas: list[dict], nf: NFeSaida) -> dict[str, str]:
    base_icms = val_icms = base_st = val_st = val_ipi = val_pis = val_cofins = Decimal('0')
    for linha in linhas:
        snap = linha.get('snapshot_fiscal') or {}
        icms = get_icms_snapshot(snap)
        ipi = get_ipi_snapshot(snap)
        pis = get_pis_snapshot(snap)
        cof = get_cofins_snapshot(snap)
        base_icms += dec(icms.get('base') or 0)
        val_icms += dec(icms.get('valor') or 0)
        base_st += dec(icms.get('base_icms_st') or 0)
        val_st += dec(icms.get('valor_icms_st') or 0)
        val_ipi += dec(ipi.get('valor') or 0)
        val_pis += dec(pis.get('valor') or 0)
        val_cofins += dec(cof.get('valor') or 0)
    totais = dados_totais_comerciais(linhas, nf)
    return {
        'base_icms': _money(base_icms),
        'valor_icms': _money(val_icms),
        'base_icms_st': _money(base_st),
        'valor_icms_st': _money(val_st),
        'valor_importacao': _money(0),
        'valor_pis': _money(val_pis),
        'valor_produtos': totais['valor_produtos'],
        'valor_frete': _money(nf.valor_frete),
        'valor_seguro': _money(0),
        'desconto': totais['desconto'],
        'outras_despesas': _money(0),
        'valor_ipi': _money(val_ipi),
        'valor_cofins': _money(val_cofins),
        'valor_total_nota': _money(nf.valor_total),
    }


def dados_totais_comerciais(linhas: list[dict], nf: NFeSaida) -> dict[str, str]:
    soma = sum(dec(l.get('v_prod', 0)) for l in linhas)
    desc_total = Decimal('0')
    for item in nf.itens.all():
        snap_c = item.snapshot_comercial or {}
        desc_total += dec(snap_c.get('desconto', 0))
    return {
        'valor_produtos': _money(soma or nf.valor_total),
        'desconto': _money(desc_total),
    }


def _montar_fatura_resumo(nf: NFeSaida, totais_imp: dict[str, str]) -> dict[str, str]:
    from apps.fiscal.nfe_saida_duplicatas import numero_fatura_nfe

    v_nf = _money(nf.valor_total)
    return {
        'numero': numero_fatura_nfe(nf),
        'valor_original': totais_imp.get('valor_produtos') or v_nf,
        'desconto': totais_imp.get('desconto') or _money(0),
        'valor_liquido': v_nf,
    }


def _montar_duplicatas(nf: NFeSaida) -> list[dict[str, str]]:
    from apps.fiscal.nfe_saida_duplicatas import (
        assegurar_duplicatas_nfe_saida,
        formatar_numero_duplicata_exibicao,
        formatar_vencimento_duplicata_exibicao,
    )

    assegurar_duplicatas_nfe_saida(nf, save=bool(nf.pk))
    rows: list[dict[str, str]] = []
    titulos = nf.titulos_receber or []
    for idx, t in enumerate(titulos, start=1):
        if not isinstance(t, dict):
            continue
        valor = dec(t.get('valor', 0))
        if valor <= 0:
            continue
        rows.append(
            {
                'numero': formatar_numero_duplicata_exibicao(t.get('parcela'), fallback=idx),
                'vencimento': formatar_vencimento_duplicata_exibicao(t.get('vencimento')),
                'valor': _money(valor),
            },
        )
    return rows


def _montar_informacoes_complementares(nf: NFeSaida, dados: dict[str, Any]) -> str:
    from apps.fiscal.nfe_integracao.danfe_xml_adicionais import montar_inf_cpl_para_danfe

    itens_db = {it.pk: it for it in nf.itens.all()}
    return montar_inf_cpl_para_danfe(nf, dados, itens_db=itens_db)


def _resumo_reforma_linhas(linhas: list[dict]) -> str:
    tot_cbs = tot_uf = tot_mun = Decimal('0')
    for linha in linhas:
        snap = linha.get('snapshot_fiscal') or {}
        if not reforma_configurada_no_snapshot(snap):
            continue
        raw = get_reforma_tributaria_snapshot(snap) or linha.get('reforma_tributaria')
        ex = montar_reforma_item_exibicao(raw, valor_produto=dec(linha.get('v_prod', 0)))
        tot_cbs += dec(ex.get('valor_cbs', 0))
        tot_uf += dec(ex.get('valor_ibs_estadual', 0))
        tot_mun += dec(ex.get('valor_ibs_municipal', 0))
    if tot_cbs == tot_uf == tot_mun == 0:
        return ''
    return (
        'Reforma Tributária — conferência: '
        f'CBS {_money(tot_cbs)} · IBS estadual {_money(tot_uf)} · IBS municipal {_money(tot_mun)}'
    )


def montar_dados_danfe_conferencia(nfe_saida: NFeSaida) -> dict[str, Any]:
    """Dados normalizados para o PDF DANFE de conferência."""
    nf = (
        NFeSaida.objects.select_related(
            'cliente',
            'transportadora',
            'pedido_venda__empresa_emitente',
        )
        .prefetch_related('itens__produto')
        .get(pk=nfe_saida.pk)
    )
    dados = gerar_dados_preview_nfe_saida(nf, incluir_validacao_emissao=False)
    if dados.get('bloqueado'):
        return dados

    linhas = list(dados.get('itens') or [])
    from apps.fiscal.nfe_integracao.danfe_xml_adicionais import (
        enriquecer_linhas_xml_nfe,
        resolver_xped_nitemped_item,
    )

    itens_db = enriquecer_linhas_xml_nfe(nf, {**dados, 'itens': linhas})
    for linha in linhas:
        item_pk = linha.get('item_id')
        item_db = itens_db.get(item_pk) if item_pk else None
        snap_c = (item_db.snapshot_comercial or {}) if item_db else {}
        x_ped, n_item = resolver_xped_nitemped_item(item_db, linha)
        linha['x_ped'] = x_ped
        linha['n_item_ped'] = n_item
        linha['desconto_item'] = snap_c.get('desconto', 0)
    serie, numero = _serie_numero(dados, nf)
    st_fiscal = (nf.status or '').strip().upper()
    autorizada_homolog = nf_autorizada_homologacao(nf)
    chave_raw = _text(
        getattr(nf, 'chave_acesso', '')
        or getattr(nf, 'chave_acesso_preliminar', '')
        or '',
    )
    if autorizada_homolog and nf.numero_nfe:
        nnf_digits = ''.join(c for c in str(nf.numero_nfe) if c.isdigit())
        numero = nnf_digits.zfill(9) if nnf_digits else numero
    if autorizada_homolog and nf.serie_nfe:
        serie = _fmt_serie_local(nf.serie_nfe) or serie
    rascunho_conferencia = (
        st_fiscal == 'RASCUNHO' and not autorizada_homolog
    ) or (not chave_raw and not autorizada_homolog)
    serie_exibicao = 'Homologação' if autorizada_homolog else ('Conferência' if rascunho_conferencia else serie)
    numero_exibicao = (
        f'{numero} (homologação)'
        if autorizada_homolog
        else (f'{numero} (rascunho)' if st_fiscal == 'RASCUNHO' else numero)
    )
    numero_canhoto = (
        f'Nº {numero_exibicao}'
        if autorizada_homolog
        else (f'Nº interno: {numero}' if rascunho_conferencia else f'Nº {numero_exibicao}')
    )
    chave_fmt = formatar_chave_acesso(chave_raw) if chave_raw else ''

    transp = dados.get('transporte') or {}
    tr = nf.transportadora
    emit = dados.get('emitente') or {}
    dest = dados.get('destinatario') or {}

    totais_imp = _calcular_totais_imposto(linhas, nf)
    dados.update(
        {
            'serie': serie,
            'serie_exibicao': serie_exibicao,
            'numero_canhoto': numero_canhoto,
            'numero_nf': numero,
            'natureza_operacao': _text(dados.get('ide', {}).get('nat_op')) or 'Venda de mercadoria',
            'protocolo': _text(getattr(nf, 'protocolo_autorizacao', '')) if autorizada_homolog else '',
            'protocolo_display': (
                _text(getattr(nf, 'protocolo_autorizacao', '')) or '—'
                if autorizada_homolog
                else ('' if rascunho_conferencia else _text(getattr(nf, 'protocolo_autorizacao', '')))
            ),
            'consulta_autenticidade': MSG_CONSULTA_PORTAL,
            'numero_exibicao': numero_exibicao,
            'autorizada_sefaz': autorizada_homolog,
            'homologacao': autorizada_homolog,
            'informacoes_fisco': _text(nf.informacoes_fisco),
            'chave_acesso': chave_raw,
            'chave_formatada': chave_fmt,
            'chave_display': (
                chave_fmt
                if chave_fmt
                else (
                    'Pendente — será gerada na autorização SEFAZ'
                    if rascunho_conferencia
                    else MSG_CHAVE_NAO_GERADA
                )
            ),
            'chave_placeholder_barcode': bool(not chave_fmt),
            'chave_e_preliminar': bool(chave_fmt and chave_raw),
            'tipo_operacao_saida': True,
            'duplicatas': _montar_duplicatas(nf),
            'fatura_resumo': _montar_fatura_resumo(nf, totais_imp),
            'totais_imposto': totais_imp,
            'informacoes_complementares': _montar_informacoes_complementares(nf, dados),
            'itens': linhas,
            'reforma_conferencia_texto': _resumo_reforma_linhas(linhas),
            'transporte_detalhe': {
                'nome': _text(transp.get('transportadora_nome')) or (_text(tr.razao_social) if tr else ''),
                'cnpj': fmt_cnpj(tr.cnpj) if tr else '—',
                'ie': _text(tr.ie) if tr else '—',
                'endereco': endereco_cadastro(
                    tr.logradouro if tr else '',
                    tr.numero if tr else '',
                    tr.complemento if tr else '',
                    tr.bairro if tr else '',
                    tr.cidade if tr else '',
                    tr.uf if tr else '',
                    tr.cep if tr else '',
                )
                if tr
                else '—',
                'municipio': _text(tr.cidade) if tr else '—',
                'uf': _text(tr.uf) if tr else '—',
                'frete_conta': MODALIDADE_FRETE_LABEL.get(
                    _text(nf.modalidade_frete) or '9',
                    MODALIDADE_FRETE_LABEL['9'],
                ),
                'codigo_antt': '—',
                'placa': _text(nf.placa_veiculo) or '—',
                'uf_veiculo': _text(nf.uf_veiculo) or '—',
                'quantidade': str(nf.quantidade_volumes or 0),
                'especie': _text(nf.especie_volumes) or '—',
                'marca': _text(nf.marca_volumes) or '—',
                'numeracao': _text(nf.numeracao_volumes) or '—',
                'peso_bruto': _qty(nf.peso_bruto),
                'peso_liquido': _qty(nf.peso_liquido),
                'valor_frete': _money(nf.valor_frete),
            },
            'emitente_detalhe': {
                **emit,
                'telefone': _text(getattr(nf.pedido_venda.empresa_emitente, 'telefone', ''))
                if nf.pedido_venda and nf.pedido_venda.empresa_emitente_id
                else '—',
            },
            'destinatario_detalhe': {
                **dest,
                'data_emissao': format_date_br(nf.data),
                'data_saida': '—',
                'hora_saida': '—',
            },
            'impresso_em': timezone.localtime(timezone.now()).strftime('%d/%m/%Y às %H:%M:%S'),
            'sistema': 'Nexus APP',
            'filename': f'danfe-conferencia-nfe-{_text(numero) or nf.pk}.pdf',
            'content_type': 'application/pdf',
            'conferencia': True,
            'mensagens': (
                [
                    'DANFE homologação — SEM VALOR FISCAL.',
                    'Protocolo SEFAZ de homologação.',
                ]
                if autorizada_homolog
                else [
                    MSG_AVISO_TOPO,
                    'DANFE de conferência — sem transmissão SEFAZ.',
                ]
            ),
        },
    )
    from apps.fiscal.danfe_conferencia_layout import aplicar_layout_em_dados_danfe

    aplicar_layout_em_dados_danfe(dados, nf)
    return dados



def gerar_danfe_conferencia_pdf(nfe_saida: NFeSaida) -> tuple[bytes, dict[str, Any]]:
    """Gera PDF DANFE modelo 55 de conferência via renderer oficial BFR."""
    from apps.fiscal.danfe_render import gerar_danfe_bfr_oficial

    return gerar_danfe_bfr_oficial(nfe_saida)
