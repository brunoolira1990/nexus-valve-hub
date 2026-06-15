"""Nomes de arquivo para download XML/DANFE autorizado — read-only."""

from __future__ import annotations

from apps.fiscal.models import NFeSaida


def _somente_digitos(valor: str | None, *, max_len: int | None = None) -> str:
    digits = ''.join(c for c in str(valor or '') if c.isdigit())
    if max_len is not None:
        digits = digits[:max_len]
    return digits


def nome_arquivo_xml_autorizado(nf: NFeSaida) -> str:
    chave = _somente_digitos(nf.chave_acesso, max_len=44)
    if len(chave) == 44:
        return f'NFe_{chave}.xml'
    nnf = _somente_digitos(nf.numero_nfe or nf.numero, max_len=9).zfill(9) or str(nf.pk).zfill(9)
    serie = _somente_digitos(nf.serie_nfe, max_len=3) or '0'
    return f'NFe_{nnf}_Serie_{serie}.xml'


def nome_arquivo_danfe_autorizado(nf: NFeSaida) -> str:
    chave = _somente_digitos(nf.chave_acesso, max_len=44)
    if len(chave) == 44:
        return f'DANFE_NFe_{chave}.pdf'
    nnf = _somente_digitos(nf.numero_nfe or nf.numero, max_len=9).zfill(9) or str(nf.pk).zfill(9)
    serie = _somente_digitos(nf.serie_nfe, max_len=3) or '0'
    return f'DANFE_NFe_{nnf}_Serie_{serie}.pdf'


def content_disposition_attachment(filename: str) -> str:
    safe = filename.replace('"', '').replace('\\', '_')
    return f'attachment; filename="{safe}"'
