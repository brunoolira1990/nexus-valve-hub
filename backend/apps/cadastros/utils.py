import re

from django.core.exceptions import ValidationError


def normalizar_cnpj(valor: str) -> str:
    """Normaliza CNPJ numérico ou alfanumérico para 14 posições maiúsculas."""
    return re.sub(r"[^0-9A-Za-z]", "", valor or "").upper()


def _apenas_digitos(valor: str) -> str:
    """Mantém compatibilidade com integrações legadas que exigem somente dígitos."""
    return re.sub(r"\D", "", valor or "")


def _valor_cnpj(caractere: str) -> int:
    """Converte o caractere conforme a regra oficial: ASCII menos 48."""
    return ord(caractere) - 48


def validar_cnpj(cnpj: str) -> bool:
    cnpj = normalizar_cnpj(cnpj)
    if len(cnpj) != 14 or not re.fullmatch(r"[0-9A-Z]{12}[0-9]{2}", cnpj):
        return False
    if len(set(cnpj)) == 1:
        return False

    def calcular_digito(parcial: str, pesos: list[int]) -> str:
        total = sum(_valor_cnpj(caractere) * peso for caractere, peso in zip(parcial, pesos))
        resto = total % 11
        return "0" if resto < 2 else str(11 - resto)

    d1 = calcular_digito(cnpj[:12], [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    d2 = calcular_digito(cnpj[:12] + d1, [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    return cnpj[-2:] == f"{d1}{d2}"


def validar_cnpj_django(cnpj: str) -> None:
    if not validar_cnpj(cnpj):
        raise ValidationError("CNPJ inválido.")
