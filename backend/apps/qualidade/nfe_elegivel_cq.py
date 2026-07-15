"""Elegibilidade de NF-e Saída para Certificado de Qualidade.

Somente NF-e com autorização fiscal SEFAZ válida (produção ou homologação).
Não inclui rascunho, conferência, descartada, cancelada ou autorização apenas interna.
"""

from __future__ import annotations

from typing import Any

from django.db.models import Q, QuerySet

from apps.fiscal.models import NFeSaida
from apps.fiscal.nfe_emissao.retorno_sefaz import CSTAT_AUTORIZADO
from apps.fiscal.nfe_saida_bloqueio import (
    nf_autorizada_homologacao,
    nf_autorizada_producao,
    nf_cancelada_operacional,
    nf_tem_xml_autorizado_resolvido,
)

MSG_NFE_INELEGIVEL_CQ = (
    'Selecione uma NF-e de saída autorizada para gerar o Certificado de Qualidade.'
)


def _fmt_nnf(numero: str | None) -> str:
    digits = ''.join(c for c in str(numero or '') if c.isdigit())
    if not digits:
        return str(numero or '').strip()
    return digits.zfill(9)


def _fmt_serie(serie: str | None) -> str:
    digits = ''.join(c for c in str(serie or '') if c.isdigit())
    return str(int(digits)) if digits else str(serie or '').strip()


def _tem_identidade_fiscal(nf: NFeSaida) -> bool:
    return bool((nf.numero_nfe or '').strip()) and (nf.serie_nfe is not None and str(nf.serie_nfe).strip() != '')


def _cstat_autorizacao_ok(nf: NFeSaida) -> bool:
    cstat = (nf.cstat_autorizacao or '').strip()
    if not cstat:
        return False
    return cstat in CSTAT_AUTORIZADO


def nfe_elegivel_para_certificado_qualidade(nf: NFeSaida) -> bool:
    """
    Critérios alinhados aos helpers fiscais existentes:
    - autorizada em produção OU homologação (status_emissao_sefaz / status legado);
    - não cancelada;
    - não descartada internamente;
    - número e série fiscais preenchidos;
    - cStat de autorização 100/150;
    - protocolo de autorização;
    - XML autorizado disponível (campo ou montável).
    """
    if nf_cancelada_operacional(nf):
        return False
    if (nf.status or '').strip().upper() == 'DESCARTADA_INTERNA':
        return False
    if not (nf_autorizada_producao(nf) or nf_autorizada_homologacao(nf)):
        return False
    if not _tem_identidade_fiscal(nf):
        return False
    if not _cstat_autorizacao_ok(nf):
        return False
    if not (nf.protocolo_autorizacao or '').strip():
        return False
    if not nf_tem_xml_autorizado_resolvido(nf):
        return False
    return True


def queryset_nfes_elegiveis_cq(qs: QuerySet[NFeSaida] | None = None) -> QuerySet[NFeSaida]:
    """Filtro server-side aproximado; elegibilidade fina via nfe_elegivel_para_certificado_qualidade."""
    base = qs if qs is not None else NFeSaida.objects.all()
    return (
        base.filter(
            Q(status_emissao_sefaz=NFeSaida.StatusEmissaoSefaz.AUTORIZADA_PRODUCAO)
            | Q(status_emissao_sefaz=NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO)
            | Q(status__iexact='AUTORIZADA_PRODUCAO')
            | Q(status__iexact='AUTORIZADA_HOMOLOGACAO'),
        )
        .exclude(
            Q(status__iexact='DESCARTADA_INTERNA')
            | Q(status__icontains='CANCEL')
            | Q(status_emissao_sefaz__icontains='CANCEL'),
        )
        .exclude(numero_nfe='')
        .exclude(serie_nfe='')
        .exclude(protocolo_autorizacao='')
        .filter(cstat_autorizacao__in=sorted(CSTAT_AUTORIZADO))
        .select_related('cliente')
    )


def label_principal_nfe_cq(nf: NFeSaida) -> str:
    numero = _fmt_nnf(nf.numero_nfe) if (nf.numero_nfe or '').strip() else ''
    serie = _fmt_serie(nf.serie_nfe) if nf.serie_nfe is not None and str(nf.serie_nfe).strip() != '' else ''
    if numero and serie != '':
        return f'NF-e nº {numero} — Série {serie}'
    if numero:
        return f'NF-e nº {numero}'
    return 'NF-e sem número fiscal'


def label_secundario_nfe_cq(nf: NFeSaida) -> str:
    cliente = ''
    if nf.cliente_id and nf.cliente:
        cliente = (nf.cliente.razao_social or nf.cliente.nome_fantasia or '').strip()
    data = ''
    if nf.data:
        data = nf.data.strftime('%d/%m/%Y')
    parts = [p for p in (cliente, f'Emissão {data}' if data else '') if p]
    return ' · '.join(parts)


def ambiente_badge_nfe_cq(nf: NFeSaida) -> str | None:
    if nf_autorizada_producao(nf):
        return 'Produção'
    if nf_autorizada_homologacao(nf):
        return 'Homologação'
    return None


def numero_fiscal_snapshot_cq(nf: NFeSaida) -> str:
    """Snapshot textual para nota_fiscal_numero — nunca RASCUNHO-FAT."""
    numero = _fmt_nnf(nf.numero_nfe) if (nf.numero_nfe or '').strip() else ''
    serie = _fmt_serie(nf.serie_nfe) if nf.serie_nfe is not None and str(nf.serie_nfe).strip() != '' else ''
    if numero and serie != '':
        return f'{numero}/{serie}'
    return numero or (nf.numero or '').strip()


def serializar_nfe_opcao_cq(nf: NFeSaida, *, elegivel: bool | None = None) -> dict[str, Any]:
    if elegivel is None:
        elegivel = nfe_elegivel_para_certificado_qualidade(nf)
    return {
        'id': nf.pk,
        'label_principal': label_principal_nfe_cq(nf),
        'label_secundario': label_secundario_nfe_cq(nf),
        'ambiente_badge': ambiente_badge_nfe_cq(nf),
        'numero_nfe': (nf.numero_nfe or '').strip(),
        'serie_nfe': (nf.serie_nfe or '').strip(),
        'cliente_nome': (
            (nf.cliente.razao_social or '').strip() if nf.cliente_id and nf.cliente else ''
        ),
        'data_emissao': nf.data.isoformat() if nf.data else None,
        'status_emissao_sefaz': (nf.status_emissao_sefaz or '').strip(),
        'elegivel': elegivel,
    }


def buscar_nfes_elegiveis_cq(*, search: str = '', limit: int = 20) -> list[dict[str, Any]]:
    qs = queryset_nfes_elegiveis_cq()
    term = (search or '').strip()
    if term:
        qs = qs.filter(
            Q(numero_nfe__icontains=term)
            | Q(serie_nfe__icontains=term)
            | Q(cliente__razao_social__icontains=term)
            | Q(cliente__nome_fantasia__icontains=term)
            | Q(chave_acesso__icontains=term)
            | Q(numero__icontains=term),
        )
    qs = qs.order_by('-autorizada_em', '-id')[: max(1, min(limit, 100))]
    resultados: list[dict[str, Any]] = []
    for nf in qs:
        if nfe_elegivel_para_certificado_qualidade(nf):
            resultados.append(serializar_nfe_opcao_cq(nf, elegivel=True))
    return resultados
