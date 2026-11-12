"""DIFAL — resolução jurídica do destino tributário (local de entrega ≠ destinatário).

Alínea "b" do art. 11, V da LC 87/96: não contribuinte consumidor final — o DIFAL é
devido à UF do local de entrada física da mercadoria, que pode divergir da UF
cadastral do destinatário jurídico.

Este módulo é PURO: só lê atributos de ``nf`` e do perfil do destinatário. Não
consulta banco, não calcula imposto e não altera a NF. A confirmação do local de
entrada física é ato humano (checkbox na conferência) — nunca escolha automática.

Regras duras respeitadas aqui:
- R1: nunca substituir a UF cadastral pela UF de entrega sem confirmação.
- R2: endereço de entrega completo + confirmação explícita.
- R3: três UFs independentes (emitente, destinatário cadastral, entrega).
- R4: o destinatário jurídico continua sendo o comprador.
- R6: sem UF resolvida não se presume nada — devolve pendência/bloqueio.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from apps.fiscal.models import NFeSaida
from apps.regras_fiscais.models import RegraFiscalSaida

ALINEA_A = 'ALINEA_A'
ALINEA_B = 'ALINEA_B'

ORIGEM_CADASTRO = 'CADASTRO'
ORIGEM_ENTREGA = 'ENTREGA'
ORIGEM_MANUAL = 'MANUAL'
ORIGEM_BLOQUEADO = 'BLOQUEADO'

MSG_PARTILHA_NAO_IMPLEMENTADA = (
    'Partilha (alínea "a", destinatário contribuinte) não implementada — FASE 1.1.'
)
MSG_ENTREGA_SEM_CONFIRMACAO = (
    'entrega em UF divergente sem confirmação de local de entrada física'
)
MSG_ENDERECO_ENTREGA_INCOMPLETO = 'endereço de entrega incompleto'
MSG_UF_CADASTRAL_AUSENTE = 'UF cadastral do destinatário não informada'


def _text(val: Any) -> str:
    return (str(val) if val is not None else '').strip()


def _norm_uf(uf: Any) -> str:
    return _text(uf).upper()[:2]


@dataclass(frozen=True)
class ResultadoDestino:
    """UF de destino tributário do DIFAL e a evidência usada para elegê-la."""

    uf: str
    fundamento: str
    origem: str
    confirmado: bool
    bloqueado: bool
    pendencias: tuple[str, ...] = field(default_factory=tuple)
    uf_cadastral: str = ''
    uf_entrega: str = ''

    @property
    def aplica_difal_na_entrega(self) -> bool:
        return self.origem == ORIGEM_ENTREGA and not self.bloqueado

    def to_dict(self) -> dict[str, Any]:
        return {
            'uf': self.uf,
            'fundamento': self.fundamento,
            'origem': self.origem,
            'confirmado': self.confirmado,
            'bloqueado': self.bloqueado,
            'pendencias': list(self.pendencias),
            'uf_cadastral': self.uf_cadastral,
            'uf_entrega': self.uf_entrega,
        }


def endereco_entrega_completo(nf: Any) -> bool:
    """TLocal mínimo para identificar o local de entrada física (R2)."""
    return all(
        (
            _norm_uf(getattr(nf, 'entrega_cUF', '')),
            _text(getattr(nf, 'entrega_cMun', '')),
            _text(getattr(nf, 'entrega_xLgr', '')),
        ),
    )


def resolver_destino_tributario(
    nf: NFeSaida,
    perfil: Any,
    *,
    uf_cadastral: str | None = None,
) -> ResultadoDestino:
    """Resolve a UF do DIFAL segundo a alínea aplicável — sem escolha automática.

    ``uf_cadastral`` evita recalcular ``_uf_destino_nf`` quando o chamador já tem o
    valor (ex.: serviço de atualização de impostos). A assinatura pública segue
    ``resolver_destino_tributario(nf, perfil)``.
    """
    from apps.fiscal.nfe_saida_atualizar_impostos import _uf_destino_nf

    cadastral = _norm_uf(uf_cadastral) if uf_cadastral is not None else _norm_uf(_uf_destino_nf(nf))
    entrega = _norm_uf(getattr(nf, 'entrega_UF', ''))
    confirmado = bool(getattr(nf, 'difal_endereco_entrada_fisica_confirmado', False))
    contribuinte = _text(getattr(perfil, 'destinatario_contribuinte', ''))
    consumidor_final = getattr(perfil, 'consumidor_final', None)

    def _resultado(
        uf: str,
        origem: str,
        *,
        fundamento: str = ALINEA_B,
        bloqueado: bool = False,
        pendencias: tuple[str, ...] = (),
    ) -> ResultadoDestino:
        return ResultadoDestino(
            uf=uf,
            fundamento=fundamento,
            origem=origem,
            confirmado=confirmado,
            bloqueado=bloqueado,
            pendencias=pendencias,
            uf_cadastral=cadastral,
            uf_entrega=entrega,
        )

    # 1) Contribuinte ICMS: alínea "a" (partilha) — fora do escopo desta fase.
    if contribuinte == RegraFiscalSaida.DestinatarioContribuinte.CONTRIBUINTE:
        return _resultado(
            cadastral,
            ORIGEM_BLOQUEADO,
            fundamento=ALINEA_A,
            bloqueado=True,
            pendencias=(MSG_PARTILHA_NAO_IMPLEMENTADA,),
        )

    # 2) Não contribuinte que não é consumidor final: o gate do DIFAL já não aplica.
    if consumidor_final is not True:
        return _resultado(cadastral, ORIGEM_CADASTRO)

    if not cadastral:
        return _resultado(
            '',
            ORIGEM_BLOQUEADO,
            bloqueado=True,
            pendencias=(MSG_UF_CADASTRAL_AUSENTE,),
        )

    # 3) Sem grupo <entrega> ou mesma UF cadastral: destino = cadastro (R7).
    if not entrega or entrega == cadastral:
        return _resultado(cadastral, ORIGEM_CADASTRO)

    # 4) UF de entrega divergente da cadastral.
    completo = endereco_entrega_completo(nf)
    if not confirmado:
        return _resultado(
            cadastral,
            ORIGEM_BLOQUEADO,
            bloqueado=True,
            pendencias=(MSG_ENTREGA_SEM_CONFIRMACAO,),
        )
    if not completo:
        return _resultado(
            cadastral,
            ORIGEM_BLOQUEADO,
            bloqueado=True,
            pendencias=(MSG_ENDERECO_ENTREGA_INCOMPLETO,),
        )
    return _resultado(entrega, ORIGEM_ENTREGA)
