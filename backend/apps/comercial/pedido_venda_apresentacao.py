"""Apresentação amigável de NF-e/faturamento no Pedido de Venda (modal/PDF)."""

from __future__ import annotations

from typing import Any

from apps.fiscal.models import NFeSaida
from apps.fiscal.nfe_saida_apresentacao import montar_apresentacao_nfe_saida

LABELS_FATURAMENTO: dict[str, str] = {
    'RASCUNHO': 'Rascunho',
    'PRONTO_PARA_NFE': 'Pronto para NF-e',
    'GERADO_NFE': 'NF-e gerada',
    'PENDENTE_GERACAO': 'Pendente de geração',
    'ERRO_TRANSMISSAO': 'Erro de transmissão',
    'CANCELADO': 'Cancelado',
}

LABELS_STATUS_ITEM: dict[str, str] = {
    'PENDENTE': 'Pendente',
    'PARCIAL': 'Parcial',
    'FATURADO': 'Faturado',
    'CANCELADO': 'Cancelado',
}

LABELS_STATUS_PEDIDO: dict[str, str] = {
    'FATURADO': 'Faturado',
    'PARCIALMENTE_FATURADO': 'Parcialmente faturado',
    'PARCIAL': 'Parcialmente faturado',
    'EM_FATURAMENTO': 'Em faturamento',
    'ABERTO': 'Aberto',
    'APROVADO': 'Aprovado',
    'CANCELADO': 'Cancelado',
}

LABELS_EMISSAO_SEFAZ: dict[str, str] = {
    'AUTORIZADA_HOMOLOGACAO': 'Autorizada em homologação',
    'AUTORIZADA_PRODUCAO': 'Autorizada em produção',
    'AUTORIZADA': 'Autorizada',
    'REJEITADA_HOMOLOGACAO': 'Rejeitada',
    'REJEITADA': 'Rejeitada',
    'CANCELADA': 'Cancelada',
    'ERRO_TRANSMISSAO': 'Erro de transmissão',
    'RASCUNHO': 'Rascunho',
}

_BADGES_HOMOLOG = (
    'Homologação',
    'Autorizada homologação',
    'Sem valor fiscal',
    'Fora da apuração',
)
_MSG_HOMOLOG_DISCRETA = (
    'NF-e emitida em ambiente de homologação, sem valor fiscal e fora da apuração.'
)


def label_faturamento_status(status: str | None) -> str:
    s = (status or '').strip().upper()
    if not s:
        return '—'
    return LABELS_FATURAMENTO.get(s, s.replace('_', ' ').title())


def label_status_item(status: str | None) -> str:
    s = (status or '').strip().upper()
    if not s:
        return '—'
    return LABELS_STATUS_ITEM.get(s, s.replace('_', ' ').title())


def label_status_pedido(status: str | None) -> str:
    s = (status or '').strip().upper()
    if not s:
        return '—'
    return LABELS_STATUS_PEDIDO.get(s, s.replace('_', ' ').title())


def label_emissao_sefaz(status: str | None) -> str:
    s = (status or '').strip().upper()
    if not s:
        return ''
    return LABELS_EMISSAO_SEFAZ.get(s, label_faturamento_status(s))


def _classificar_caso(linha: dict[str, Any]) -> str:
    if not linha.get('nfe_saida_id'):
        return 'nenhuma'
    sefaz = (linha.get('nfe_status_emissao_sefaz') or '').strip().upper()
    st = (linha.get('nfe_saida_status') or '').strip().upper()
    if sefaz == 'AUTORIZADA_HOMOLOGACAO' or st == 'AUTORIZADA_HOMOLOGACAO':
        return 'autorizada_homolog'
    if sefaz in ('AUTORIZADA_PRODUCAO',) or st == 'AUTORIZADA':
        return 'autorizada_producao'
    if 'CANCEL' in st:
        return 'cancelada'
    if 'REJEIT' in st or 'REJEIT' in sefaz:
        return 'rejeitada'
    if st == 'RASCUNHO' or not sefaz:
        return 'rascunho'
    return 'vinculada'


def formatar_identidade_nfe_pedido(linha: dict[str, Any], *, nf: NFeSaida | None = None) -> dict[str, Any]:
    """Identidade fiscal amigável para linha de faturamento_nfe do resumo."""
    ap: dict[str, Any] = {}
    if nf is not None:
        ap = montar_apresentacao_nfe_saida(nf)
    elif linha.get('nfe_titulo_exibicao'):
        ap = {'titulo_exibicao': linha.get('nfe_titulo_exibicao')}

    caso = _classificar_caso(linha)
    titulo = (ap.get('titulo_exibicao') or '').strip()
    if not titulo:
        n = (linha.get('nfe_numero_fiscal') or '').strip()
        serie = (linha.get('nfe_serie_fiscal') or '').strip()
        sefaz = (linha.get('nfe_status_emissao_sefaz') or '').strip().upper()
        if caso == 'nenhuma':
            titulo = 'Nenhuma NF-e gerada'
        elif caso == 'rascunho':
            titulo = 'NF-e em rascunho'
        elif caso == 'autorizada_homolog' and n:
            titulo = f'NF-e Homologação nº {n}' + (f' — Série {serie}' if serie else '')
        elif caso == 'autorizada_producao' and n:
            titulo = f'NF-e nº {n}' + (f' — Série {serie}' if serie else '')
        elif caso == 'rejeitada':
            titulo = f'NF-e rejeitada nº {n}' if n else 'NF-e rejeitada'
        elif caso == 'cancelada':
            titulo = f'NF-e cancelada nº {n}' if n else 'NF-e cancelada'
        else:
            titulo = (linha.get('nfe_saida_numero') or '').strip() or 'NF-e vinculada'

    status_fiscal = label_emissao_sefaz(linha.get('nfe_status_emissao_sefaz') or linha.get('nfe_saida_status'))
    badges: list[str] = []
    ambiente_label = ''
    msg_homolog = ''
    if caso == 'autorizada_homolog':
        badges = list(_BADGES_HOMOLOG)
        ambiente_label = 'Homologação'
        msg_homolog = _MSG_HOMOLOG_DISCRETA
    elif caso == 'autorizada_producao':
        badges = ['Produção', 'Autorizada', 'Apura']
        ambiente_label = 'Produção'
    elif caso == 'rascunho':
        badges = ['Rascunho']
    elif caso == 'rejeitada':
        badges = ['Rejeitada']
    elif caso == 'cancelada':
        badges = ['Cancelada']

    ref_interna = ''
    num_interno = (linha.get('nfe_saida_numero') or '').strip()
    if num_interno.upper().startswith('RASCUNHO-FAT'):
        ref_interna = num_interno

    return {
        'titulo': titulo,
        'status_fiscal_label': status_fiscal,
        'ambiente_label': ambiente_label,
        'badges': badges,
        'referencia_interna': ref_interna,
        'cstat': (linha.get('nfe_cstat') or '').strip(),
        'numero': (linha.get('nfe_numero_fiscal') or '').strip(),
        'serie': (linha.get('nfe_serie_fiscal') or '').strip(),
        'caso': caso,
        'mensagem_homologacao': msg_homolog,
    }


def linha_faturamento_pdf(linha: dict[str, Any], *, nf: NFeSaida | None = None) -> tuple[str, str]:
    """Retorna (rótulo, valor) para grid do PDF."""
    fat_id = linha.get('faturamento_id')
    num_fat = (linha.get('numero_faturamento') or '').strip() or f'#{fat_id}'
    rotulo = f'Faturamento {num_fat}:'

    if (linha.get('status') or '').strip().upper() == 'GERADO_NFE' and not linha.get('nfe_saida_id'):
        return (
            rotulo,
            'NF-e gerada — vínculo não localizado. Verifique o histórico do pedido/faturamento.',
        )

    if not linha.get('nfe_saida_id'):
        if (linha.get('status') or '').strip().upper() == 'PRONTO_PARA_NFE':
            return (rotulo, 'NF-e ainda não gerada')
        return (rotulo, label_faturamento_status(linha.get('status')))

    idn = formatar_identidade_nfe_pedido(linha, nf=nf)
    partes = [idn['titulo']]
    if idn['status_fiscal_label']:
        partes.append(idn['status_fiscal_label'])
    if idn.get('cstat'):
        partes.append(f'cStat {idn["cstat"]}')
    if idn.get('badges'):
        partes.extend(idn['badges'])
    if idn.get('referencia_interna'):
        partes.append(f'Ref. interna: {idn["referencia_interna"]}')
    return (rotulo, ' · '.join(p for p in partes if p))


def titulo_secao_nfe_pdf(linhas: list[dict[str, Any]]) -> str:
    if not linhas:
        return 'Nenhuma NF-e gerada'
    casos = [_classificar_caso(l) for l in linhas if l.get('nfe_saida_id')]
    if not casos:
        return 'Nenhuma NF-e gerada'
    if all(c == 'rascunho' for c in casos):
        return 'NF-e em rascunho' if len(casos) == 1 else 'NF-e em rascunho'
    if any(c in ('autorizada_homolog', 'autorizada_producao', 'vinculada') for c in casos):
        return 'NF-e vinculada' if len(casos) == 1 else 'NF-e vinculadas'
    return 'NF-e vinculadas'


def prazo_entrega_pdf_amigavel(texto: str | None) -> str:
    t = (texto or '').strip()
    if not t:
        return '—'
    t = t.replace('Uteis', 'úteis').replace('UTEIS', 'úteis').replace('uteis', 'úteis')
    return t


def condicao_pagamento_pdf_amigavel(condicao_texto: str, dias_parcelas: list) -> str:
    dias = list(dias_parcelas or [])
    if dias:
        return ', '.join(f'{int(d)} dias' for d in dias)
    raw = (condicao_texto or '').strip()
    if not raw:
        return '—'
    if raw.isdigit():
        return f'{raw} dias'
    return raw
