import re

from django.core.exceptions import ValidationError


def _apenas_digitos(valor: str) -> str:
    return re.sub(r"\D", "", valor or "")


def validar_cnpj(cnpj: str) -> bool:
    cnpj = _apenas_digitos(cnpj)
    if len(cnpj) != 14:
        return False
    if cnpj == cnpj[0] * 14:
        return False

    def calcular_digito(parcial: str, pesos: list[int]) -> str:
        total = sum(int(digito) * peso for digito, peso in zip(parcial, pesos))
        resto = total % 11
        return "0" if resto < 2 else str(11 - resto)

    d1 = calcular_digito(cnpj[:12], [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    d2 = calcular_digito(cnpj[:12] + d1, [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    return cnpj[-2:] == f"{d1}{d2}"


def validar_cnpj_django(cnpj: str) -> None:
    if not validar_cnpj(cnpj):
        raise ValidationError("CNPJ inválido.")
