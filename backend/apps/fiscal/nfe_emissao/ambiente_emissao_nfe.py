"""Ambiente de emissão NF-e Saída — resolução e sincronização com cadastro da empresa."""

from __future__ import annotations

from apps.cadastros.models import Empresa
from apps.cadastros.nfe_ambiente import obter_nfe_ambiente_empresa
from apps.fiscal.models import NFeSaida
from apps.fiscal.nfe_saida_bloqueio import STATUS_NFE_RASCUNHO

MSG_AMBIENTE_NAO_DEFINIDO = (
    'Ambiente de emissão da NF-e não definido. Revise o ambiente fiscal antes de preparar emissão.'
)

_AMBIENTES_VALIDOS = frozenset(
    {
        NFeSaida.AmbienteEmissao.HOMOLOGACAO,
        NFeSaida.AmbienteEmissao.PRODUCAO,
    },
)


def ambiente_emissao_nfe_definido(nf: NFeSaida) -> bool:
    return (nf.ambiente_emissao or '').strip() in _AMBIENTES_VALIDOS


def _empresa_emitente_para_ambiente(nf: NFeSaida) -> Empresa | None:
    if nf.empresa_emitente_id:
        if getattr(nf, 'empresa_emitente', None):
            return nf.empresa_emitente
        return Empresa.objects.filter(pk=nf.empresa_emitente_id).first()
    pedido = getattr(nf, 'pedido_venda', None)
    if pedido and pedido.empresa_emitente_id:
        if getattr(pedido, 'empresa_emitente', None):
            return pedido.empresa_emitente
        return Empresa.objects.filter(pk=pedido.empresa_emitente_id).first()
    return None


def garantir_ambiente_emissao_nfe_saida(nf: NFeSaida) -> NFeSaida:
    """Preenche ambiente_emissao a partir da empresa emitente quando vazio (rascunho)."""
    if ambiente_emissao_nfe_definido(nf):
        return nf
    if (nf.status or '').strip().upper() != STATUS_NFE_RASCUNHO:
        return nf
    empresa = _empresa_emitente_para_ambiente(nf)
    if not empresa:
        return nf
    ambiente = obter_nfe_ambiente_empresa(empresa)
    if ambiente in _AMBIENTES_VALIDOS:
        nf.ambiente_emissao = ambiente
        nf.save(update_fields=['ambiente_emissao'])
    return nf
