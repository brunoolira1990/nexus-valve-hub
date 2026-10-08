"""Preview de fechamento mensal — manifestação destinatário."""

from __future__ import annotations

from datetime import date, datetime, time

from django.db.models import Count, Q
from django.utils import timezone

from apps.fiscal.models import CTeHistoricoImportado, NFeDestinadaManifestacao, NFeEntradaHistoricaImportada
from apps.fiscal.dfe_classificacao import q_excluir_homologacao_cte, q_excluir_homologacao_historica_entrada


def _parse_data(val: str | None) -> date | None:
    if not val:
        return None
    try:
        return date.fromisoformat(str(val).strip()[:10])
    except ValueError:
        return None


def fechamento_preview_manifestacao(
    *,
    empresa_id: int | None = None,
    data_inicio: str | None = None,
    data_fim: str | None = None,
) -> dict:
    ini = _parse_data(data_inicio)
    fim = _parse_data(data_fim)
    if not ini or not fim:
        raise ValueError('Informe data_inicio e data_fim válidas (YYYY-MM-DD).')
    if fim < ini:
        raise ValueError('data_fim deve ser maior ou igual a data_inicio.')

    dt_ini = timezone.make_aware(datetime.combine(ini, time.min))
    dt_fim = timezone.make_aware(datetime.combine(fim, time.max))

    qs = NFeDestinadaManifestacao.objects.filter(
        ambiente=NFeDestinadaManifestacao.Ambiente.PRODUCAO,
        dh_emissao__gte=dt_ini,
        dh_emissao__lte=dt_fim,
    )
    if empresa_id:
        qs = qs.filter(empresa_id=empresa_id)

    agreg = qs.aggregate(
        total=Count('id'),
        xml_baixados=Count('id', filter=Q(status_xml=NFeDestinadaManifestacao.StatusXml.BAIXADO)),
        xml_pendentes=Count(
            'id',
            filter=Q(
                status_xml__in=[
                    NFeDestinadaManifestacao.StatusXml.RESUMO,
                    NFeDestinadaManifestacao.StatusXml.PENDENTE,
                    NFeDestinadaManifestacao.StatusXml.DISPONIVEL,
                ],
            ),
        ),
        sem_manifestacao=Count(
            'id',
            filter=Q(status_manifestacao=NFeDestinadaManifestacao.StatusManifestacao.PENDENTE),
        ),
        erros=Count(
            'id',
            filter=Q(
                Q(status_manifestacao=NFeDestinadaManifestacao.StatusManifestacao.ERRO)
                | Q(status_xml=NFeDestinadaManifestacao.StatusXml.ERRO),
            ),
        ),
    )

    nfe_base_qs = NFeEntradaHistoricaImportada.objects.filter(
        q_excluir_homologacao_historica_entrada(),
        dh_emissao__gte=dt_ini,
        dh_emissao__lte=dt_fim,
    )
    if empresa_id:
        nfe_base_qs = nfe_base_qs.filter(empresa_destinataria_id=empresa_id)

    cte_base_qs = CTeHistoricoImportado.objects.filter(
        q_excluir_homologacao_cte(),
        cancelado=False,
        dh_emissao__gte=dt_ini,
        dh_emissao__lte=dt_fim,
    )
    if empresa_id:
        cte_base_qs = cte_base_qs.filter(
            Q(empresa_tomadora_id=empresa_id)
            | Q(empresa_destinataria_id=empresa_id)
            | Q(empresa_recebedora_id=empresa_id),
        )

    nfe_xml_armazenados = nfe_base_qs.count()
    cte_xml_armazenados = cte_base_qs.count()

    return {
        'empresa_id': empresa_id,
        'data_inicio': ini.isoformat(),
        'data_fim': fim.isoformat(),
        'total_documentos': agreg['total'] or 0,
        'xml_baixados': agreg['xml_baixados'] or 0,
        'xml_pendentes': agreg['xml_pendentes'] or 0,
        'sem_manifestacao': agreg['sem_manifestacao'] or 0,
        'erros': agreg['erros'] or 0,
        'nfe_xml_armazenados': nfe_xml_armazenados,
        'cte_xml_armazenados': cte_xml_armazenados,
        'nfe_xml_pendentes_manifestacao': agreg['xml_pendentes'] or 0,
        'cte_xml_pendentes': 0,
        'erros_armazenamento': agreg['erros'] or 0,
    }
