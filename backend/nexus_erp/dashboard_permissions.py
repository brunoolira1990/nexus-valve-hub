"""Permissões do BI modular por módulo (ERP 4.0.8)."""

from __future__ import annotations

MODULOS_BI = ('comercial', 'fiscal', 'estoque', 'compras', 'qualidade', 'financeiro')

# Qualquer uma das permissões do módulo concede acesso ao painel correspondente.
MODULO_PERMISSOES: dict[str, list[str]] = {
    'comercial': [
        'comercial.view_pedidovenda',
        'comercial.view_proposta',
        'comercial.add_pedidovenda',
        'comercial.change_pedidovenda',
    ],
    'fiscal': [
        'fiscal.view_nfesaida',
        'fiscal.view_nfeentrada',
        'regras_fiscais.view_regrafiscal',
        'fiscal.add_nfesaida',
        'fiscal.change_nfesaida',
    ],
    'estoque': [
        'fiscal.view_atendimentoestoque',
        'produtos.view_produto',
        'produtos.change_produto',
    ],
    'compras': [
        'comercial.view_pedidocompra',
        'fiscal.view_nfeentrada',
        'comercial.add_pedidocompra',
        'comercial.change_pedidocompra',
    ],
    'qualidade': [
        'qualidade.view_certificadoqualidade',
        'qualidade.view_certificado',
        'qualidade.view_certificadofornecedorentrada',
        'corridas.view_corrida',
    ],
    'financeiro': [
        'contabil.view_contacontabil',
        'contabil.view_lancamentocontabil',
    ],
}


def _usuario_admin(user) -> bool:
    if user.is_superuser:
        return True
    return user.groups.filter(name='admin').exists()


def usuario_pode_ver_dashboard_modulo(user, modulo: str) -> bool:
    """Retorna True se o usuário pode ver o painel BI do módulo."""
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if _usuario_admin(user):
        return True
    permissoes = MODULO_PERMISSOES.get(modulo, [])
    if not permissoes:
        return False
    return any(user.has_perm(p) for p in permissoes)


def permissoes_dashboard(user) -> dict[str, bool]:
    """Mapa de permissões por módulo para resposta da API."""
    return {
        'pode_ver_comercial': usuario_pode_ver_dashboard_modulo(user, 'comercial'),
        'pode_ver_fiscal': usuario_pode_ver_dashboard_modulo(user, 'fiscal'),
        'pode_ver_estoque': usuario_pode_ver_dashboard_modulo(user, 'estoque'),
        'pode_ver_compras': usuario_pode_ver_dashboard_modulo(user, 'compras'),
        'pode_ver_qualidade': usuario_pode_ver_dashboard_modulo(user, 'qualidade'),
        'pode_ver_financeiro': usuario_pode_ver_dashboard_modulo(user, 'financeiro'),
        'pode_ver_consolidado': _usuario_admin(user),
    }


def modulos_permitidos(user) -> list[str]:
    return [m for m in MODULOS_BI if usuario_pode_ver_dashboard_modulo(user, m)]


def exigir_modulo(user, modulo: str) -> bool:
    """True se autorizado; False se negado."""
    return usuario_pode_ver_dashboard_modulo(user, modulo)
