"""Resumo compacto para listagem NF-e Saída (ERP 4.0.13.4)."""

from __future__ import annotations

from typing import Any

from apps.comercial.services.resumo_atendimento_operacional import resumo_enxuto_listagem
from apps.fiscal.models import NFeSaida
from apps.fiscal.nfe_saida_apresentacao import montar_apresentacao_nfe_saida, titulo_homologacao_exibicao
from apps.fiscal.nfe_saida_bloqueio import nf_autorizada_homologacao
from apps.fiscal.reforma_tributaria.config import status_reforma_nfe_documento


def montar_fiscal_resumo_listagem(nf: NFeSaida) -> dict[str, str]:
    ap = montar_apresentacao_nfe_saida(nf)
    sefaz = (nf.status_emissao_sefaz or '').strip()
    cstat = (nf.cstat_autorizacao or '').strip()
    subtexto_parts: list[str] = []

    if nf_autorizada_homologacao(nf):
        if cstat:
            subtexto_parts.append(f'cStat {cstat}')
        subtexto_parts.append('Fora da apuração')
        return {
            'badge': 'Homologação autorizada',
            'variant': 'warning',
            'subtexto': ' · '.join(subtexto_parts),
        }

    if sefaz == NFeSaida.StatusEmissaoSefaz.REJEITADA_HOMOLOGACAO:
        sub = f'cStat {cstat}' if cstat else 'Rejeitada'
        return {'badge': 'Rejeitada homologação', 'variant': 'danger', 'subtexto': sub}

    if sefaz == NFeSaida.StatusEmissaoSefaz.ERRO_TRANSMISSAO:
        return {'badge': 'Erro transmissão', 'variant': 'danger', 'subtexto': ''}

    st = (nf.status or '').strip().upper()
    if st in (
        'CANCELADA_INTERNA',
        'CANCELADA',
        'CANCELADO',
        'CANCELADA_PRODUCAO',
        'CANCELADA_HOMOLOGACAO',
    ):
        sub = (nf.motivo_cancelamento or '').strip()
        if not sub and st == 'CANCELADA_PRODUCAO':
            sub = 'Cancelada na SEFAZ'
        return {'badge': 'Cancelada', 'variant': 'danger', 'subtexto': sub[:80] if sub else 'Sem valor fiscal'}

    if st == 'DESCARTADA_INTERNA':
        return {'badge': 'Rascunho descartado', 'variant': 'neutral', 'subtexto': 'Sem evento SEFAZ'}

    if st == 'RASCUNHO':
        conf = (nf.status_conferencia or '').strip().upper()
        if conf == NFeSaida.StatusConferencia.PRONTA_PARA_EMISSAO:
            badge = 'Pendente de autorização'
        else:
            badge = 'Rascunho'
        sub = (nf.status_conferencia or '').replace('_', ' ').title() if conf and conf != NFeSaida.StatusConferencia.PRONTA_PARA_EMISSAO else ''
        return {'badge': badge, 'variant': 'neutral', 'subtexto': sub}

    if sefaz == 'AUTORIZADA_PRODUCAO' or st in ('AUTORIZADA', 'EMITIDA', 'EMITIDO'):
        sub = f'cStat {cstat}' if cstat else ''
        return {'badge': 'Produção autorizada', 'variant': 'success', 'subtexto': sub}

    badge = (ap.get('badge_principal', {}).get('label') or st or 'Pendente').strip()
    if badge in ('—', '-', ''):
        badge = 'Pendente'
    return {'badge': badge, 'variant': 'neutral', 'subtexto': ''}


def _normalizar_badge_atendimento(raw: Any) -> dict[str, str] | None:
    if isinstance(raw, dict):
        label = str(raw.get('label') or '').strip()
        if not label:
            return None
        return {
            'label': label,
            'variant': str(raw.get('variant') or 'neutral').strip() or 'neutral',
        }
    label = str(raw or '').strip()
    if not label:
        return None
    return {'label': label, 'variant': 'neutral'}


def montar_atendimento_resumo_listagem(nf: NFeSaida) -> dict[str, Any]:
    resumo = resumo_enxuto_listagem(nf, contexto='nfe_saida')
    badges_raw = list(resumo.get('badges') or [])
    badges: list[dict[str, str]] = []
    for raw in badges_raw:
        row = _normalizar_badge_atendimento(raw)
        if row:
            badges.append(row)
    if not badges:
        return {
            'badges': [],
            'ocultos': 0,
            'vazio_label': 'Atendimento não definido',
        }
    max_visiveis = 2
    visiveis = badges[:max_visiveis]
    ocultos = max(0, len(badges) - len(visiveis))
    return {'badges': visiveis, 'ocultos': ocultos}


def _resolver_titulo_listagem(nf: NFeSaida, ap: dict[str, Any]) -> str:
    if nf_autorizada_homologacao(nf):
        return titulo_homologacao_exibicao(
            str(ap.get('numero_fiscal') or ''),
            str(ap.get('serie_fiscal') or ''),
        )

    titulo = (ap.get('listagem_titulo') or ap.get('titulo_exibicao') or '').strip()
    numero_interno = (ap.get('numero_interno') or nf.numero or '').strip()
    numero_fiscal = str(ap.get('numero_fiscal') or '').strip()
    serie_fiscal = str(ap.get('serie_fiscal') or '').strip()

    if numero_fiscal and serie_fiscal:
        return f'NF-e nº {numero_fiscal} — Série {serie_fiscal}'
    if numero_fiscal:
        return f'NF-e nº {numero_fiscal}'

    if titulo and titulo != numero_interno and not numero_interno.upper().startswith('RASCUNHO'):
        return titulo

    if numero_interno.upper().startswith('RASCUNHO') and (nf.status or '').strip().upper() == 'RASCUNHO':
        return 'NF-e em rascunho'

    return titulo or 'NF-e sem número fiscal'


def montar_listagem_resumo_nfe(nf: NFeSaida) -> dict[str, Any]:
    ap = montar_apresentacao_nfe_saida(nf)
    from apps.fiscal.nfe_saida_duplicatas import duplicatas_nfe_para_api

    dups = duplicatas_nfe_para_api(nf)
    titulo = _resolver_titulo_listagem(nf, ap)
    return {
        'titulo': titulo,
        'subtitulo': ap.get('listagem_subtitulo') or '',
        'fiscal_resumo': montar_fiscal_resumo_listagem(nf),
        'atendimento_resumo': montar_atendimento_resumo_listagem(nf),
        'tem_duplicatas': bool(dups),
        'reforma_tributaria_status': status_reforma_nfe_documento(nf),
    }
