"""Numeração NF-e padrão ao cadastrar nova empresa."""

from __future__ import annotations

from apps.cadastros.models import Empresa
from apps.fiscal.models import NFeNumeracaoConfiguracao


def ensure_numeracao_padrao_nfe(empresa: Empresa | int) -> None:
    emp_id = empresa.pk if isinstance(empresa, Empresa) else int(empresa)
    NFeNumeracaoConfiguracao.objects.get_or_create(
        empresa_id=emp_id,
        modelo_documento='55',
        ambiente=NFeNumeracaoConfiguracao.Ambiente.HOMOLOGACAO,
        serie='0',
        defaults={'proximo_numero': 2, 'ativo': True},
    )
    NFeNumeracaoConfiguracao.objects.get_or_create(
        empresa_id=emp_id,
        modelo_documento='55',
        ambiente=NFeNumeracaoConfiguracao.Ambiente.PRODUCAO,
        serie='1',
        defaults={'proximo_numero': 1, 'ativo': True},
    )
