"""Prontidão da empresa para consulta status SEFAZ (sem emissão NF-e)."""

from __future__ import annotations

import re
from typing import Any

from apps.fiscal.limpeza_cursor.criterios import RE_RAZAO_EMIT_TESTE

MSG_EMPRESA_TESTE = 'Empresa de teste ou sem certificado válido para consulta SEFAZ.'
TIPO_ERRO_CERTIFICADO_LOCAL = 'CERTIFICADO_ERROR'
TIPO_ERRO_EMPRESA_BLOQUEADA_LOCAL = 'EMPRESA_BLOQUEADA'

CNPJS_FIXTURE_TESTE = frozenset(
    {
        '12345678000199',  # Emitente 402 e suítes NF-e mock
        '00000000000191',
    },
)

RE_EMITENTE_NUMERO = re.compile(r'^Emitente\s+\d+', re.I)
RE_CERT_TITULAR_TESTE = re.compile(r'empresa\s+teste|emitente\s+\d+|nexus-test', re.I)


def _norm_cnpj(val: str | None) -> str:
    return ''.join(c for c in (val or '') if c.isdigit())


def empresa_eh_fixture_teste(empresa: Any) -> bool:
    """Empresa residual de teste automatizado (ex.: Emitente 402)."""
    razao = (getattr(empresa, 'razao_social', '') or '').strip()
    if RE_RAZAO_EMIT_TESTE.match(razao) or RE_EMITENTE_NUMERO.match(razao):
        return True

    cnpj = _norm_cnpj(getattr(empresa, 'cnpj', ''))
    if cnpj in CNPJS_FIXTURE_TESTE:
        return True

    return False


def certificado_parece_fixture_teste(cert_titular: str | None) -> bool:
    titular = (cert_titular or '').strip()
    if not titular:
        return False
    return bool(RE_CERT_TITULAR_TESTE.search(titular))


def validar_prontidao_consulta_sefaz(empresa: Any) -> tuple[bool, str, str]:
    """
    Valida se a empresa pode consultar SEFAZ externa.

    Retorna (pode_consultar, motivo, tipo_erro).
    """
    if empresa_eh_fixture_teste(empresa):
        return False, MSG_EMPRESA_TESTE, TIPO_ERRO_EMPRESA_BLOQUEADA_LOCAL

    if not getattr(empresa, 'certificado_arquivo', None):
        return (
            False,
            'Certificado A1 não cadastrado na empresa. Configure antes de consultar a SEFAZ.',
            TIPO_ERRO_CERTIFICADO_LOCAL,
        )

    if not (getattr(empresa, 'senha_certificado', '') or '').strip():
        return (
            False,
            'Senha do certificado não cadastrada na empresa.',
            TIPO_ERRO_CERTIFICADO_LOCAL,
        )

    cnpj = _norm_cnpj(getattr(empresa, 'cnpj', ''))
    if len(cnpj) != 14:
        return (
            False,
            'CNPJ da empresa inválido ou incompleto para consulta SEFAZ.',
            TIPO_ERRO_CERTIFICADO_LOCAL,
        )

    uf = (getattr(empresa, 'uf', '') or '').strip().upper()
    if len(uf) != 2:
        return (
            False,
            'UF da empresa não configurada. Informe a UF no cadastro da empresa.',
            TIPO_ERRO_CERTIFICADO_LOCAL,
        )

    return True, '', ''


def prioridade_empresa_sefaz(empresa: Any) -> int:
    """Menor valor = melhor candidata para seleção padrão na UI."""
    if empresa_eh_fixture_teste(empresa):
        return 100
    if not getattr(empresa, 'certificado_arquivo', None):
        return 50
    return 0


def metadados_empresa_consulta_sefaz(empresa: Any) -> dict[str, Any]:
    pode, motivo, tipo = validar_prontidao_consulta_sefaz(empresa)
    return {
        'empresa_fixture_teste': empresa_eh_fixture_teste(empresa),
        'consulta_sefaz_permitida': pode,
        'consulta_sefaz_motivo': motivo,
        'consulta_sefaz_tipo_erro': tipo,
    }
