"""Identidade operacional/fiscal da NF-e Saída para UI e API."""

from __future__ import annotations

from typing import Any

from apps.comercial.faturamento_numero_exibicao import numero_faturamento_exibicao_faturamento
from apps.fiscal.models import NFeSaida
from apps.fiscal.nfe_saida_bloqueio import nf_autorizada_homologacao

_STATUS_CANCELADO = frozenset({
    'CANCELADA_INTERNA',
    'CANCELADA',
    'CANCELADO',
    'CANCELADA_HOMOLOGACAO',
    'CANCELADA_PRODUCAO',
})


def _fmt_nnf(numero: str | None) -> str:
    digits = ''.join(c for c in str(numero or '') if c.isdigit())
    if not digits:
        return str(numero or '').strip()
    return digits.zfill(9)


def _fmt_serie(serie: str | None) -> str:
    digits = ''.join(c for c in str(serie or '') if c.isdigit())
    return str(int(digits)) if digits else str(serie or '').strip()


def _status_cancelado(nf: NFeSaida) -> bool:
    return (nf.status or '').strip().upper() in _STATUS_CANCELADO


def _badge_cancelada(nf: NFeSaida) -> dict[str, str]:
    st = (nf.status or '').strip().upper()
    if st == 'CANCELADA_PRODUCAO':
        return {'label': 'Cancelada (produção SEFAZ)', 'tipo': 'danger'}
    if st == 'CANCELADA_HOMOLOGACAO':
        return {'label': 'Cancelada (homologação SEFAZ)', 'tipo': 'danger'}
    return {'label': 'Cancelada interna', 'tipo': 'danger'}


def titulo_homologacao_exibicao(numero_fiscal: str, serie_fiscal: str) -> str:
    if numero_fiscal and serie_fiscal:
        return f'NF-e Homologação nº {numero_fiscal} — Série {serie_fiscal}'
    if numero_fiscal:
        return f'NF-e Homologação nº {numero_fiscal}'
    return 'NF-e Homologação autorizada'


def _tem_fat_ou_fiscal(numero_faturamento: str, numero_fiscal: str, sefaz: str) -> bool:
    if numero_faturamento:
        return True
    if numero_fiscal:
        return True
    return sefaz in (
        NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO,
        'AUTORIZADA_PRODUCAO',
    )


def montar_apresentacao_nfe_saida(nf: NFeSaida) -> dict[str, Any]:
    fat = getattr(nf, 'faturamento_pedido_venda', None)
    pedido = getattr(nf, 'pedido_venda', None)
    numero_interno = (nf.numero or '').strip()
    numero_faturamento = numero_faturamento_exibicao_faturamento(fat) if fat else ''
    numero_pedido_venda = (pedido.numero if pedido else '') or ''
    numero_pedido_cliente = (nf.pedido_cliente_numero or '').strip()
    serie_fiscal = _fmt_serie(nf.serie_nfe) if nf.serie_nfe else ''
    numero_fiscal = _fmt_nnf(nf.numero_nfe) if nf.numero_nfe else ''
    sefaz = (nf.status_emissao_sefaz or '').strip()
    autorizada_homolog = nf_autorizada_homologacao(nf)
    cancelada = _status_cancelado(nf)
    tem_fat_fiscal = _tem_fat_ou_fiscal(numero_faturamento, numero_fiscal, sefaz)

    homolog_status = (
        sefaz == NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO
        or (nf.status or '').strip().upper() == 'AUTORIZADA_HOMOLOGACAO'
    )
    if autorizada_homolog or homolog_status:
        titulo_exibicao = titulo_homologacao_exibicao(numero_fiscal, serie_fiscal)
    elif sefaz == 'AUTORIZADA_PRODUCAO' and numero_fiscal and serie_fiscal:
        titulo_exibicao = f'NF-e nº {numero_fiscal} — Série {serie_fiscal}'
    elif numero_fiscal and serie_fiscal:
        titulo_exibicao = f'NF-e Conferência nº {numero_fiscal} — Série {serie_fiscal}'
    elif tem_fat_fiscal and numero_interno:
        titulo_exibicao = f'Conferência NF-e {numero_interno}'
    else:
        titulo_exibicao = f'Conferência NF-e {numero_interno or nf.pk}'

    linhas_subtitulo: list[str] = []
    if numero_faturamento:
        linhas_subtitulo.append(f'Faturamento: {numero_faturamento}')
    if numero_pedido_venda:
        linhas_subtitulo.append(f'Pedido de venda: {numero_pedido_venda}')
    if numero_pedido_cliente:
        linhas_subtitulo.append(f'Pedido do cliente: {numero_pedido_cliente}')

    subtitulo_exibicao = ' · '.join(linhas_subtitulo)

    listagem_subtitulo = ' · '.join(p for p in [numero_faturamento, numero_pedido_venda] if p)

    if autorizada_homolog:
        badge_principal = {'label': 'Autorizada homologação', 'tipo': 'success'}
    elif sefaz == NFeSaida.StatusEmissaoSefaz.REJEITADA_HOMOLOGACAO:
        badge_principal = {'label': 'Rejeitada homologação', 'tipo': 'danger'}
    elif sefaz == NFeSaida.StatusEmissaoSefaz.ERRO_TRANSMISSAO:
        badge_principal = {'label': 'Erro transmissão', 'tipo': 'danger'}
    elif cancelada:
        badge_principal = _badge_cancelada(nf)
    elif (nf.status or '').upper() == 'RASCUNHO':
        badge_principal = {'label': 'Rascunho', 'tipo': 'warning'}
    else:
        badge_principal = {'label': (nf.status or '—'), 'tipo': 'warning'}

    badges_secundarios: list[dict[str, str]] = []
    if autorizada_homolog and (nf.cstat_autorizacao or '').strip():
        badges_secundarios.append({'label': f'cStat {nf.cstat_autorizacao}', 'tipo': 'success'})
    elif cancelada and not sefaz:
        badges_secundarios.append({'label': 'Sem autorização SEFAZ', 'tipo': 'muted'})

    if autorizada_homolog or homolog_status:
        listagem_titulo = titulo_homologacao_exibicao(numero_fiscal, serie_fiscal)
    elif numero_fiscal:
        listagem_titulo = titulo_exibicao
    elif numero_interno.upper().startswith('RASCUNHO') and (nf.status or '').strip().upper() == 'RASCUNHO':
        listagem_titulo = 'NF-e em rascunho'
    elif not tem_fat_fiscal and numero_interno:
        listagem_titulo = 'NF-e sem número fiscal'
    else:
        listagem_titulo = titulo_exibicao

    ocultar_conferencia_listagem = autorizada_homolog or cancelada

    return {
        'numero_interno': numero_interno,
        'origem_operacional': 'FATURAMENTO_PEDIDO' if fat else ('PEDIDO_VENDA' if pedido else 'MANUAL'),
        'numero_faturamento': numero_faturamento,
        'numero_pedido_venda': numero_pedido_venda,
        'numero_pedido_cliente': numero_pedido_cliente,
        'numero_fiscal': numero_fiscal,
        'serie_fiscal': serie_fiscal,
        'chave_acesso': nf.chave_acesso or '',
        'protocolo_autorizacao': nf.protocolo_autorizacao or '',
        'ambiente_emissao': nf.ambiente_emissao or '',
        'status_emissao_sefaz': sefaz,
        'status_conferencia': nf.status_conferencia or '',
        'titulo_exibicao': titulo_exibicao,
        'subtitulo_exibicao': subtitulo_exibicao,
        'linhas_subtitulo': linhas_subtitulo,
        'badge_principal': badge_principal,
        'badges_secundarios': badges_secundarios,
        'autorizada_homologacao': autorizada_homolog,
        'cancelada_interna': cancelada,
        'modo_leitura': autorizada_homolog,
        'listagem_titulo': listagem_titulo,
        'listagem_subtitulo': listagem_subtitulo,
        'ocultar_status_conferencia_listagem': ocultar_conferencia_listagem,
    }
