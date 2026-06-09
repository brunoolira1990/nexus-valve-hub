"""Validação e normalização de série fiscal NF-e (faixa 0–889)."""

from __future__ import annotations

SERIE_MIN_AUTORIZACAO = 0
SERIE_MAX_AUTORIZACAO = 889
MSG_SERIE_FORA_FAIXA = (
    'Série fora da faixa permitida para autorização normal da NF-e. Use série entre 0 e 889.'
)


class NFeSerieFiscalError(ValueError):
    pass


def serie_int(serie: str) -> int:
    digits = ''.join(c for c in str(serie or '') if c.isdigit())
    if not digits and str(serie or '').strip() == '0':
        return 0
    if not digits:
        raise NFeSerieFiscalError('Série fiscal inválida.')
    return int(digits)


def normalizar_serie_xml(serie: str) -> str:
    """Série no cadastro e no XML ide (ex.: 0, 1, 889 — sem zeros à esquerda)."""
    n = serie_int(serie)
    return str(n)


def serie_para_chave(serie: str) -> str:
    """Três dígitos na chave de acesso (ex.: série 0 → 000)."""
    return str(serie_int(serie)).zfill(3)


def validar_serie_autorizacao_normal(serie: str) -> None:
    """Bloqueia série 900–999 e fora de 0–889."""
    n = serie_int(serie)
    if n < SERIE_MIN_AUTORIZACAO or n > SERIE_MAX_AUTORIZACAO:
        raise NFeSerieFiscalError(MSG_SERIE_FORA_FAIXA)


def validar_chave_corresponde_numeracao(
    chave_44: str,
    *,
    serie: str,
    nnf: str,
    codigo_numerico: str | None = None,
) -> None:
    """Garante que a chave de 44 dígitos reflete série/número/cNF da NF-e."""
    chave = ''.join(c for c in str(chave_44 or '') if c.isdigit())
    if len(chave) != 44:
        raise NFeSerieFiscalError('Chave de acesso inválida ou incompleta.')
    ser_chave = chave[22:25]
    ser_esperada = serie_para_chave(serie)
    if ser_chave != ser_esperada:
        raise NFeSerieFiscalError(
            'Chave de acesso não corresponde à série fiscal da NF-e. '
            'Recalcule a chave ou corrija a série de homologação.',
        )
    nnf_chave = int(chave[25:34])
    nnf_digits = ''.join(c for c in str(nnf or '') if c.isdigit())
    if not nnf_digits:
        raise NFeSerieFiscalError('Número fiscal inválido para validação da chave.')
    if nnf_chave != int(nnf_digits):
        raise NFeSerieFiscalError('Chave de acesso não corresponde ao número fiscal da NF-e.')
    if codigo_numerico:
        cnf_chave = chave[35:43]
        cnf_esper = ''.join(c for c in str(codigo_numerico) if c.isdigit())[:8].zfill(8)
        if cnf_chave != cnf_esper:
            raise NFeSerieFiscalError('Chave de acesso não corresponde ao código numérico da NF-e.')


def serie_rejeitada_sefaz_266(serie: str | None) -> bool:
    if serie is None:
        return False
    try:
        n = serie_int(serie)
    except NFeSerieFiscalError:
        return True
    return n > SERIE_MAX_AUTORIZACAO
