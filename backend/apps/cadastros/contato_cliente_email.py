"""Normalização e unicidade de e-mail em ContatoCliente (case-insensitive)."""

from __future__ import annotations

from typing import Any


MSG_EMAIL_FISCAL_OBRIGATORIO = 'Informe um e-mail para o contato que recebe documentos fiscais.'
MSG_EMAIL_DUPLICADO = 'Este e-mail já está cadastrado nos contatos deste cliente.'
MSG_EMAIL_INVALIDO = 'Informe um endereço de e-mail válido.'


def normalizar_email_contato(email: str | None) -> str:
    """Trim seguro; não altera capitalização além das bordas."""
    return (email or '').strip()


def chave_email_contato(email: str | None) -> str:
    """Chave de comparação case-insensitive (após trim). Vazio = sem e-mail."""
    return normalizar_email_contato(email).casefold()


def validar_unicidade_emails_contatos_payload(
    contatos: list[dict[str, Any]],
) -> list[dict[str, list[str]]]:
    """
    Retorna lista de erros por índice (mesmo tamanho de contatos).
    Entradas vazias nos dicts indicam ausência de erro naquele item.
    """
    erros: list[dict[str, list[str]]] = [{} for _ in contatos]
    visto: dict[str, int] = {}

    for i, item in enumerate(contatos):
        chave = chave_email_contato(item.get('email'))
        if not chave:
            continue
        if chave in visto:
            erros[i]['email'] = [MSG_EMAIL_DUPLICADO]
            # Marca também o primeiro ocorrente se ainda não tiver erro de e-mail
            primeiro = visto[chave]
            if 'email' not in erros[primeiro]:
                erros[primeiro]['email'] = [MSG_EMAIL_DUPLICADO]
        else:
            visto[chave] = i

    return erros


def tem_erros_por_contato(erros: list[dict[str, list[str]]]) -> bool:
    return any(bool(e) for e in erros)
