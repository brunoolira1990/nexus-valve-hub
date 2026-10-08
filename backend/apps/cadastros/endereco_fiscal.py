"""Validação de consistência do endereço fiscal para uso em NF-e."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from typing import Any, Protocol

from apps.cadastros.consulta_externa import consultar_cep_viacep, normalizar_cep_digitos

MSG_ENDERECO_INCONSISTENTE = (
    'Endereço fiscal inconsistente: o CEP/cidade consultado não corresponde à UF informada. '
    'Revise antes de usar em NF-e.'
)


class EnderecoFiscalLike(Protocol):
    cep: str
    cidade: str
    uf: str
    logradouro: str
    bairro: str
    numero: str


def _text(val) -> str:
    return (str(val) if val is not None else '').strip()


def _norm_uf(uf: str | None) -> str:
    return _text(uf).upper()[:2]


def _norm_localidade(val: str | None) -> str:
    raw = _text(val)
    if not raw:
        return ''
    decomposed = unicodedata.normalize('NFKD', raw)
    ascii_only = decomposed.encode('ascii', 'ignore').decode('ascii')
    return ' '.join(ascii_only.upper().split())


@dataclass
class EnderecoFiscalResult:
    consistente: bool = True
    bloqueio_fiscal: bool = False
    alertas: list[str] = field(default_factory=list)
    pendencias: list[str] = field(default_factory=list)
    uf_destino: str = ''
    cidade_destino: str = ''
    cep_consultado: dict[str, str] | None = None
    campos_faltantes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            'consistente': self.consistente,
            'bloqueio_fiscal': self.bloqueio_fiscal,
            'alertas': list(self.alertas),
            'pendencias': list(self.pendencias),
            'uf_destino': self.uf_destino,
            'cidade_destino': self.cidade_destino,
            'cep_consultado': self.cep_consultado,
            'campos_faltantes': list(self.campos_faltantes),
        }


def _campos_fiscais_obrigatorios(obj: EnderecoFiscalLike, *, exigir_endereco_completo: bool = False) -> list[str]:
    faltantes: list[str] = []
    if not _norm_uf(obj.uf):
        faltantes.append('uf')
    if not _norm_localidade(obj.cidade):
        faltantes.append('cidade')
    if not exigir_endereco_completo:
        return faltantes
    if len(normalizar_cep_digitos(obj.cep)) != 8:
        faltantes.append('cep')
    if not _text(obj.logradouro):
        faltantes.append('logradouro')
    if not _text(obj.bairro):
        faltantes.append('bairro')
    if not _text(obj.numero):
        faltantes.append('numero')
    return faltantes


def validar_endereco_fiscal(
    obj: EnderecoFiscalLike,
    *,
    consultar_cep: bool = False,
    cep_cache: dict[str, dict[str, str] | None] | None = None,
    exigir_endereco_completo: bool = False,
) -> EnderecoFiscalResult:
    """
    Valida endereço fiscal para NF-e.
    Permite cadastro comercial incompleto, mas sinaliza bloqueio fiscal quando inconsistente.
    """
    result = EnderecoFiscalResult(
        uf_destino=_norm_uf(obj.uf),
        cidade_destino=_text(obj.cidade),
    )
    cep_digitos = normalizar_cep_digitos(obj.cep)
    cep_ref: dict[str, str] | None = None
    if consultar_cep and len(cep_digitos) == 8:
        if cep_cache is not None and cep_digitos in cep_cache:
            cep_ref = cep_cache[cep_digitos]
        else:
            cep_ref = consultar_cep_viacep(cep_digitos)
            if cep_cache is not None:
                cep_cache[cep_digitos] = cep_ref
        result.cep_consultado = cep_ref

    result.campos_faltantes = _campos_fiscais_obrigatorios(
        obj,
        exigir_endereco_completo=exigir_endereco_completo,
    )

    if 'uf' in result.campos_faltantes and not cep_ref:
        result.pendencias.append('UF do endereço fiscal não informada.')
        result.bloqueio_fiscal = True
        result.consistente = False
    if 'cidade' in result.campos_faltantes and not cep_ref:
        result.pendencias.append('Cidade do endereço fiscal não informada.')
        result.bloqueio_fiscal = True
        result.consistente = False

    if cep_ref:
        uf_cep = _norm_uf(cep_ref.get('uf'))
        cidade_cep = _norm_localidade(cep_ref.get('cidade'))
        cidade_cad = _norm_localidade(obj.cidade)
        uf_cad = _norm_uf(obj.uf)

        if uf_cad and uf_cep and uf_cad != uf_cep:
            msg = (
                f'Endereço fiscal inconsistente: CEP {_text(obj.cep)} / cidade {_text(obj.cidade)} '
                f'não correspondem à UF {uf_cad} informada no cadastro. '
                f'UF retornada pelo CEP: {uf_cep}. Corrija o cadastro do cliente antes de aplicar a regra fiscal.'
            )
            result.alertas.append(msg)
            result.consistente = False
            result.bloqueio_fiscal = True
            result.uf_destino = ''

        if cidade_cad and cidade_cep and cidade_cad != cidade_cep:
            msg = (
                f'Endereço fiscal inconsistente: cidade cadastrada «{_text(obj.cidade)}» '
                f'diverge da cidade retornada pelo CEP «{cep_ref.get("cidade", "")}».'
            )
            if msg not in result.alertas:
                result.alertas.append(msg)
            result.consistente = False
            result.bloqueio_fiscal = True

        if result.consistente and uf_cep:
            result.uf_destino = uf_cep
        if result.consistente and cep_ref.get('cidade'):
            result.cidade_destino = _text(cep_ref.get('cidade'))

    elif cep_ref and result.consistente:
        result.uf_destino = _norm_uf(cep_ref.get('uf')) or result.uf_destino
        result.cidade_destino = _text(cep_ref.get('cidade')) or result.cidade_destino

    elif not result.bloqueio_fiscal:
        result.uf_destino = _norm_uf(obj.uf)
        result.cidade_destino = _text(obj.cidade)

    if not result.consistente and not result.alertas and not result.pendencias:
        result.alertas.append(MSG_ENDERECO_INCONSISTENTE)
        result.bloqueio_fiscal = True

    return result


def serializar_endereco_fiscal_cliente(
    cliente,
    *,
    consultar_cep: bool = False,
    cep_cache: dict[str, dict[str, str] | None] | None = None,
) -> dict[str, Any]:
    result = validar_endereco_fiscal(cliente, consultar_cep=consultar_cep, cep_cache=cep_cache)
    return result.to_dict()


def mensagem_endereco_inconsistente_nf(cliente, result: EnderecoFiscalResult) -> str:
    if result.alertas:
        return result.alertas[0]
    if result.pendencias:
        return result.pendencias[0]
    cidade = _text(cliente.cidade)
    cep = _text(cliente.cep)
    uf = _norm_uf(cliente.uf)
    return (
        f'Cliente com endereço fiscal inconsistente: cidade {cidade} e CEP {cep} '
        f'não correspondem à UF {uf}. Corrija o cadastro do cliente.'
    )
