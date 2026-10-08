"""Estado consolidado do Inbox Fiscal — derivação read-only a partir de status existentes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apps.fiscal.models import (
    CTeHistoricoImportado,
    ItemNFeEntradaConferencia,
    NFeDestinadaManifestacao,
    NFeEntradaConferencia,
    NFeEntradaHistoricaImportada,
)

# --- NF-e fornecedor ---
ESTADO_NFE_RECEBIDO = 'RECEBIDO'
ESTADO_NFE_PRECISA_MANIFESTAR = 'PRECISA_MANIFESTAR'
ESTADO_NFE_XML_DISPONIVEL = 'XML_DISPONIVEL'
ESTADO_NFE_EM_CONFERENCIA = 'EM_CONFERENCIA'
ESTADO_NFE_CONFERIDO = 'CONFERIDO'
ESTADO_NFE_ESTOQUE_APLICADO = 'ESTOQUE_APLICADO'
ESTADO_NFE_CONCLUIDO = 'CONCLUIDO'

# --- CT-e ---
ESTADO_CTE_RECEBIDO = 'RECEBIDO'
ESTADO_CTE_XML_DISPONIVEL = 'XML_DISPONIVEL'
ESTADO_CTE_EM_CONFERENCIA = 'EM_CONFERENCIA'
ESTADO_CTE_CONFERIDO = 'CONFERIDO'
ESTADO_CTE_CONCLUIDO = 'CONCLUIDO'

# --- Exceções (ambos tipos) ---
ESTADO_DIVERGENTE = 'DIVERGENTE'
ESTADO_BLOQUEADO = 'BLOQUEADO'

ESTADOS_NFE_FORNECEDOR = frozenset({
    ESTADO_NFE_RECEBIDO,
    ESTADO_NFE_PRECISA_MANIFESTAR,
    ESTADO_NFE_XML_DISPONIVEL,
    ESTADO_NFE_EM_CONFERENCIA,
    ESTADO_NFE_CONFERIDO,
    ESTADO_NFE_ESTOQUE_APLICADO,
    ESTADO_NFE_CONCLUIDO,
    ESTADO_DIVERGENTE,
    ESTADO_BLOQUEADO,
})

ESTADOS_CTE = frozenset({
    ESTADO_CTE_RECEBIDO,
    ESTADO_CTE_XML_DISPONIVEL,
    ESTADO_CTE_EM_CONFERENCIA,
    ESTADO_CTE_CONFERIDO,
    ESTADO_CTE_CONCLUIDO,
    ESTADO_DIVERGENTE,
    ESTADO_BLOQUEADO,
})

ESTADOS_INBOX = ESTADOS_NFE_FORNECEDOR | ESTADOS_CTE

LABELS_ESTADO: dict[str, str] = {
    ESTADO_NFE_RECEBIDO: 'Recebido',
    ESTADO_NFE_PRECISA_MANIFESTAR: 'Precisa manifestar',
    ESTADO_NFE_XML_DISPONIVEL: 'XML disponível',
    ESTADO_NFE_EM_CONFERENCIA: 'Em conferência',
    ESTADO_NFE_CONFERIDO: 'Conferido',
    ESTADO_NFE_ESTOQUE_APLICADO: 'Estoque aplicado',
    ESTADO_NFE_CONCLUIDO: 'Concluído',
    ESTADO_CTE_RECEBIDO: 'Recebido',
    ESTADO_CTE_XML_DISPONIVEL: 'XML disponível',
    ESTADO_CTE_EM_CONFERENCIA: 'Em conferência',
    ESTADO_CTE_CONFERIDO: 'Conferido',
    ESTADO_CTE_CONCLUIDO: 'Concluído',
    ESTADO_DIVERGENTE: 'Divergente',
    ESTADO_BLOQUEADO: 'Bloqueado',
}

MANIFESTACAO_EVENTOS_REGISTRADOS = frozenset({
    NFeDestinadaManifestacao.StatusManifestacao.CIENTE,
    NFeDestinadaManifestacao.StatusManifestacao.CONFIRMADA,
    NFeDestinadaManifestacao.StatusManifestacao.DESCONHECIDA,
    NFeDestinadaManifestacao.StatusManifestacao.NAO_REALIZADA,
})


@dataclass(frozen=True)
class EstadoConsolidadoInbox:
    estado: str
    label: str
    motivo: str = ''
    detalhes: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            'estado_consolidado': self.estado,
            'estado_consolidado_label': self.label,
        }
        if self.motivo:
            out['estado_consolidado_motivo'] = self.motivo
        if self.detalhes:
            out['estado_consolidado_detalhes'] = self.detalhes
        return out


def _label(estado: str) -> str:
    return LABELS_ESTADO.get(estado, estado.replace('_', ' ').title())


def _resultado(estado: str, *, motivo: str = '', detalhes: dict[str, Any] | None = None) -> EstadoConsolidadoInbox:
    return EstadoConsolidadoInbox(estado=estado, label=_label(estado), motivo=motivo, detalhes=detalhes)


def _xml_armazenado_nfe(nf: NFeEntradaHistoricaImportada) -> bool:
    return bool((getattr(nf, 'xml_conteudo', None) or '').strip())


def _conferencia_nfe_em_andamento(conf: NFeEntradaConferencia | None) -> bool:
    if conf is None:
        return False
    if conf.status != NFeEntradaConferencia.Status.PENDENTE:
        return False
    if conf.pedido_compra_id:
        return True
    return conf.itens.exclude(status=ItemNFeEntradaConferencia.Status.PENDENTE_PRODUTO).exists()


def _motivo_divergencia_nfe(conf: NFeEntradaConferencia | None) -> str:
    if conf is None:
        return ''
    if conf.divergencias_aceitas:
        return ''
    itens_div = list(
        conf.itens.filter(status=ItemNFeEntradaConferencia.Status.DIVERGENTE).values_list('id', flat=True),
    )
    if itens_div:
        obs = (conf.observacao_divergencias or '').strip()
        base = f'{len(itens_div)} item(ns) divergente(s) na conferência.'
        return f'{base} {obs}'.strip() if obs else base
    return ''


def financeiro_gerado_nfe(nf: NFeEntradaHistoricaImportada) -> bool:
    """Indica se já existe título de contas a pagar vinculado à NF-e histórica."""
    from apps.fiscal.nfe_entrada_financeiro import titulos_vinculados_nfe_entrada

    return bool(titulos_vinculados_nfe_entrada(nf))


def derivar_estado_nfe_fornecedor_resumo(
    manifestacao: NFeDestinadaManifestacao,
) -> EstadoConsolidadoInbox:
    """NF-e destinada ainda sem registro na base importada (somente resumo DF-e)."""
    st_manifest = (manifestacao.status_manifestacao or '').upper()
    st_xml = (manifestacao.status_xml or '').upper()

    if st_manifest == NFeDestinadaManifestacao.StatusManifestacao.ERRO:
        motivo = (manifestacao.ultimo_xmotivo or 'Erro na manifestação ou consulta SEFAZ.').strip()
        return _resultado(
            ESTADO_BLOQUEADO,
            motivo=motivo,
            detalhes={'status_manifestacao': st_manifest, 'ultimo_cstat': manifestacao.ultimo_cstat},
        )

    if st_manifest == NFeDestinadaManifestacao.StatusManifestacao.DESCONHECIDA:
        return _resultado(
            ESTADO_NFE_CONCLUIDO,
            detalhes={'status_manifestacao': st_manifest, 'evento': 'DESCONHECIMENTO'},
        )

    if st_manifest == NFeDestinadaManifestacao.StatusManifestacao.NAO_REALIZADA:
        detalhes: dict[str, Any] = {'status_manifestacao': st_manifest, 'evento': 'OPERACAO_NAO_REALIZADA'}
        return _resultado(ESTADO_NFE_CONCLUIDO, detalhes=detalhes)

    if st_manifest in MANIFESTACAO_EVENTOS_REGISTRADOS and st_xml in {
        NFeDestinadaManifestacao.StatusXml.DISPONIVEL,
        NFeDestinadaManifestacao.StatusXml.PENDENTE,
    }:
        return _resultado(
            ESTADO_NFE_XML_DISPONIVEL,
            detalhes={'status_manifestacao': st_manifest, 'status_xml': st_xml},
        )

    if st_manifest == NFeDestinadaManifestacao.StatusManifestacao.PENDENTE:
        return _resultado(
            ESTADO_NFE_PRECISA_MANIFESTAR,
            detalhes={'status_manifestacao': st_manifest, 'status_xml': st_xml},
        )

    return _resultado(
        ESTADO_NFE_RECEBIDO,
        detalhes={'status_manifestacao': st_manifest, 'status_xml': st_xml},
    )


def derivar_estado_nfe_fornecedor_historica(
    nf: NFeEntradaHistoricaImportada,
    *,
    conferencia: NFeEntradaConferencia | None = None,
    ja_lancado_operacional: bool = False,
    manifestacao: NFeDestinadaManifestacao | None = None,
) -> EstadoConsolidadoInbox:
    """NF-e fornecedor persistida na base importada."""
    conf = conferencia if conferencia is not None else getattr(nf, 'conferencia', None)

    if conf and conf.status == NFeEntradaConferencia.Status.CANCELADA:
        return _resultado(
            ESTADO_BLOQUEADO,
            motivo='Conferência cancelada ou revertida.',
            detalhes={'status_conferencia': conf.status},
        )

    motivo_div = _motivo_divergencia_nfe(conf)
    if motivo_div:
        return _resultado(
            ESTADO_DIVERGENTE,
            motivo=motivo_div,
            detalhes={
                'observacao_divergencias': (conf.observacao_divergencias or '').strip() if conf else '',
            },
        )

    def _finalizar(
        estado: str,
        *,
        motivo: str = '',
        detalhes: dict[str, Any] | None = None,
    ) -> EstadoConsolidadoInbox:
        meta = dict(detalhes or {})
        if ja_lancado_operacional:
            meta['chave_em_nfe_entrada_operacional'] = True
            if not (conf and conf.estoque_aplicado_em):
                meta.setdefault(
                    'observacao',
                    'Chave também registrada em NF-e Entrada operacional; '
                    'conferência/estoque da base importada ainda não concluídos.',
                )
        return _resultado(estado, motivo=motivo, detalhes=meta or None)

    if conf and conf.estoque_aplicado_em:
        if financeiro_gerado_nfe(nf):
            return _finalizar(
                ESTADO_NFE_CONCLUIDO,
                detalhes={
                    'estoque_aplicado_em': conf.estoque_aplicado_em.isoformat(),
                    'financeiro_gerado': True,
                },
            )
        return _finalizar(
            ESTADO_NFE_ESTOQUE_APLICADO,
            detalhes={'estoque_aplicado_em': conf.estoque_aplicado_em.isoformat()},
        )

    if conf and conf.status == NFeEntradaConferencia.Status.PREPARADA:
        return _finalizar(
            ESTADO_NFE_CONFERIDO,
            detalhes={'preparado_em': conf.preparado_em.isoformat() if conf.preparado_em else None},
        )

    if conf and _conferencia_nfe_em_andamento(conf):
        return _finalizar(ESTADO_NFE_EM_CONFERENCIA, detalhes={'status_conferencia': conf.status})

    if _xml_armazenado_nfe(nf):
        if manifestacao and (manifestacao.status_manifestacao or '').upper() == (
            NFeDestinadaManifestacao.StatusManifestacao.PENDENTE
        ):
            return _finalizar(
                ESTADO_NFE_XML_DISPONIVEL,
                detalhes={
                    'status_manifestacao': manifestacao.status_manifestacao,
                    'observacao': 'XML armazenado; manifestação ainda pendente.',
                },
            )
        return _finalizar(ESTADO_NFE_XML_DISPONIVEL)

    if manifestacao:
        base = derivar_estado_nfe_fornecedor_resumo(manifestacao)
        if ja_lancado_operacional:
            detalhes_resumo = dict(base.detalhes or {})
            detalhes_resumo['chave_em_nfe_entrada_operacional'] = True
            return _resultado(base.estado, motivo=base.motivo, detalhes=detalhes_resumo)
        return base

    return _finalizar(ESTADO_NFE_RECEBIDO, detalhes={'xml_armazenado': False})


def derivar_estado_cte(
    cte: CTeHistoricoImportado,
) -> EstadoConsolidadoInbox:
    """CT-e importado na base histórica."""
    st = (cte.status_conferencia or CTeHistoricoImportado.StatusConferencia.IMPORTADO).upper()

    if cte.cancelado or st == CTeHistoricoImportado.StatusConferencia.CANCELADO:
        motivo = (cte.motivo_cancelamento or 'CT-e cancelado.').strip()
        return _resultado(ESTADO_BLOQUEADO, motivo=motivo, detalhes={'status_conferencia': st})

    if cte.ignorado_operacionalmente or st == CTeHistoricoImportado.StatusConferencia.IGNORADO:
        motivo = (cte.divergencia_motivo or cte.observacao_conferencia or 'Ignorado operacionalmente.').strip()
        return _resultado(ESTADO_BLOQUEADO, motivo=motivo, detalhes={'status_conferencia': st})

    if st == CTeHistoricoImportado.StatusConferencia.DIVERGENTE:
        motivo = (cte.divergencia_motivo or cte.observacao_conferencia or 'CT-e marcado como divergente.').strip()
        return _resultado(ESTADO_DIVERGENTE, motivo=motivo, detalhes={'status_conferencia': st})

    if cte.apto_operacional and st in {
        CTeHistoricoImportado.StatusConferencia.CONFERIDO,
        CTeHistoricoImportado.StatusConferencia.PREPARADO,
    }:
        return _resultado(
            ESTADO_CTE_CONCLUIDO,
            detalhes={
                'status_conferencia': st,
                'conferido_em': cte.conferido_em.isoformat() if cte.conferido_em else None,
            },
        )

    if st in {
        CTeHistoricoImportado.StatusConferencia.CONFERIDO,
        CTeHistoricoImportado.StatusConferencia.PREPARADO,
    }:
        return _resultado(ESTADO_CTE_CONFERIDO, detalhes={'status_conferencia': st})

    if st == CTeHistoricoImportado.StatusConferencia.PREPARADO:
        return _resultado(ESTADO_CTE_EM_CONFERENCIA, detalhes={'status_conferencia': st})

    xml_ok = bool((cte.xml_conteudo or '').strip())
    if xml_ok and st in {
        CTeHistoricoImportado.StatusConferencia.IMPORTADO,
        CTeHistoricoImportado.StatusConferencia.PROCESSADO,
    }:
        return _resultado(ESTADO_CTE_XML_DISPONIVEL, detalhes={'status_conferencia': st})

    if xml_ok:
        return _resultado(ESTADO_CTE_RECEBIDO, detalhes={'status_conferencia': st})

    return _resultado(ESTADO_CTE_RECEBIDO, detalhes={'status_conferencia': st, 'xml_armazenado': False})
