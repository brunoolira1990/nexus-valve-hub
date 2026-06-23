"""Perfil fiscal do destinatário NF-e Saída (contribuinte, consumidor final, indIEDest)."""

from __future__ import annotations

from dataclasses import dataclass, field

from apps.fiscal.nfe_operacao_fiscal_indicadores import normalizar_ind_final
from apps.regras_fiscais.models import RegraFiscalSaida


def _text(val) -> str:
    return (str(val) if val is not None else '').strip()


def _ie_digitos(ie: str) -> str:
    return ''.join(c for c in _text(ie) if c.isdigit())


@dataclass(frozen=True)
class PerfilDestinatarioFiscal:
    destinatario_contribuinte: str
    ind_ie_dest: str
    consumidor_final: bool | None
    inconsistencias: list[str] = field(default_factory=list)

    @property
    def nao_contribuinte(self) -> bool:
        return self.destinatario_contribuinte == RegraFiscalSaida.DestinatarioContribuinte.NAO_CONTRIBUINTE


def resolver_perfil_destinatario_cliente(
    cliente,
    *,
    consumidor_final: bool | None = None,
) -> PerfilDestinatarioFiscal:
    """Deriva contribuinte/IE a partir do cadastro — sem texto livre arbitrário."""
    inconsistencias: list[str] = []
    if cliente is None:
        return PerfilDestinatarioFiscal(
            destinatario_contribuinte='',
            ind_ie_dest='9',
            consumidor_final=consumidor_final,
            inconsistencias=['Cliente não informado.'],
        )

    if not _text(cliente.uf):
        inconsistencias.append('Cliente sem UF de destino.')

    ie = _text(getattr(cliente, 'ie', ''))
    ie_upper = ie.upper()

    if ie_upper in ('ISENTO', 'ISENTA'):
        return PerfilDestinatarioFiscal(
            destinatario_contribuinte=RegraFiscalSaida.DestinatarioContribuinte.NAO_CONTRIBUINTE,
            ind_ie_dest='2',
            consumidor_final=consumidor_final,
            inconsistencias=inconsistencias,
        )

    if _ie_digitos(ie):
        return PerfilDestinatarioFiscal(
            destinatario_contribuinte=RegraFiscalSaida.DestinatarioContribuinte.CONTRIBUINTE,
            ind_ie_dest='1',
            consumidor_final=consumidor_final,
            inconsistencias=inconsistencias,
        )

    if ie and ie_upper not in ('ISENTO', 'ISENTA'):
        inconsistencias.append(
            'Inscrição estadual sem dígitos válidos; confira se o cliente é contribuinte ICMS.',
        )

    return PerfilDestinatarioFiscal(
        destinatario_contribuinte=RegraFiscalSaida.DestinatarioContribuinte.NAO_CONTRIBUINTE,
        ind_ie_dest='9',
        consumidor_final=consumidor_final,
        inconsistencias=inconsistencias,
    )


def resolver_perfil_destinatario_nf(nf) -> PerfilDestinatarioFiscal:
    cliente = None
    if getattr(nf, 'cliente_id', None) and getattr(nf, 'cliente', None):
        cliente = nf.cliente
    else:
        pedido = getattr(nf, 'pedido_venda', None)
        if pedido and getattr(pedido, 'cliente_id', None) and getattr(pedido, 'cliente', None):
            cliente = pedido.cliente
    consumidor_final = normalizar_ind_final(getattr(nf, 'ind_final', None)) == '1'
    return resolver_perfil_destinatario_cliente(cliente, consumidor_final=consumidor_final)


def resolver_ind_ie_dest_destinatario(cliente) -> str:
    return resolver_perfil_destinatario_cliente(cliente).ind_ie_dest
