"""UF autorizadora da NF-e a partir da chave de acesso (cUF)."""

from __future__ import annotations

from apps.fiscal.nfe_saida_preview import UF_IBGE

IBGE_PARA_UF: dict[str, str] = {codigo: uf for uf, codigo in UF_IBGE.items()}


def uf_autorizadora_por_chave(chave_acesso: str) -> str:
    """
    Retorna a sigla da UF autorizadora (cUF) com base nos 2 primeiros dígitos da chave.

    Manifestação do destinatário exige cOrgao alinhado ao órgão autorizador da NF-e.
    Usar empresa.uf pode gerar cStat 657 quando a NF-e é de outra UF.
    """
    chave = (chave_acesso or '').strip()
    if len(chave) != 44 or not chave.isdigit():
        raise ValueError(MSG_CHAVE_UF_INVALIDA)
    cuf = chave[:2]
    uf = IBGE_PARA_UF.get(cuf)
    if not uf:
        raise ValueError(f'cUF {cuf} da chave não reconhecido para manifestação.')
    return uf


MSG_CHAVE_UF_INVALIDA = 'Chave de acesso inválida para identificar a UF autorizadora.'
