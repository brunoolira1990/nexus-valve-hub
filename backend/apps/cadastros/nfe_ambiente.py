"""Ambiente NF-e configurado por empresa (homologação / produção)."""

from __future__ import annotations

from apps.cadastros.models import Empresa


def obter_nfe_ambiente_empresa(empresa: Empresa) -> str:
    """Retorna homologacao ou producao conforme cadastro da empresa."""
    valor = (getattr(empresa, 'nfe_ambiente', None) or Empresa.NfeAmbiente.HOMOLOGACAO).strip().lower()
    if valor not in (Empresa.NfeAmbiente.HOMOLOGACAO, Empresa.NfeAmbiente.PRODUCAO):
        return Empresa.NfeAmbiente.HOMOLOGACAO
    return valor


def empresa_configurada_para_producao(empresa: Empresa) -> bool:
    return obter_nfe_ambiente_empresa(empresa) == Empresa.NfeAmbiente.PRODUCAO
