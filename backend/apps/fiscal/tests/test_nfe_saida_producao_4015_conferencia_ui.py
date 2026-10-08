"""Fase 3C — permissões produção na conferência NF-e Saída."""

from __future__ import annotations

from django.test import TestCase, override_settings

from apps.fiscal.nfe_emissao.conferencia_producao import montar_permissoes_emissao_producao
from apps.fiscal.nfe_emissao.permissoes_producao import usuario_pode_emitir_nfe_producao
from apps.fiscal.nfe_saida_conferencia import montar_conferencia_nfe_saida
from apps.fiscal.tests.nfe_4015_test_support import NFe4015GruposMixin, vincular_grupo_teste
from apps.fiscal.tests.test_nfe_saida_producao_4015 import (
    _pedido_nf,
    _preparar_nf_indicadores,
    _preparar_pronta,
)


class NFe4015ConferenciaProducaoUiTests(NFe4015GruposMixin, TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.fiscal_user = User.objects.create_user('fiscal3c', 'fiscal3c@test.com', 'x')
        vincular_grupo_teste(self.fiscal_user, 'fiscal')

        self.admin_user = User.objects.create_user('admin3c', 'admin3c@test.com', 'x')
        vincular_grupo_teste(self.admin_user, 'admin')

        self.fiscal_prod_user = User.objects.create_user('fiscalprod3c', 'fiscalprod3c@test.com', 'x')
        vincular_grupo_teste(self.fiscal_prod_user, 'fiscal_nfe_producao')

        self.pedido, self.nf = _pedido_nf()
        self.nf = _preparar_nf_indicadores(self.nf)
        self.nf = _preparar_pronta(self.nf, self.admin_user)

    def test_fiscal_nao_pode_emitir_producao(self):
        self.assertFalse(usuario_pode_emitir_nfe_producao(self.fiscal_user))
        self.assertTrue(usuario_pode_emitir_nfe_producao(self.admin_user))
        self.assertTrue(usuario_pode_emitir_nfe_producao(self.fiscal_prod_user))

    @override_settings(NFE_PRODUCAO_HABILITADA=False)
    def test_conferencia_pode_emitir_producao_false_quando_desligada(self):
        conf = montar_conferencia_nfe_saida(self.nf, modo='completo', usuario=self.admin_user)
        self.assertFalse(conf['permissoes']['pode_emitir_producao'])

    @override_settings(NFE_PRODUCAO_HABILITADA=False)
    def test_conferencia_producao_desligada(self):
        conf = montar_conferencia_nfe_saida(self.nf, modo='completo', usuario=self.admin_user)
        self.assertFalse(conf['permissoes']['producao_habilitada'])
        self.assertFalse(conf['permissoes']['pode_emitir_producao'])
        self.assertIn('desabilitada', conf['emissao_producao']['motivo_bloqueio'].lower())

    @override_settings(NFE_PRODUCAO_HABILITADA=True)
    def test_conferencia_admin_pode_emitir_quando_pronta(self):
        conf = montar_conferencia_nfe_saida(self.nf, modo='completo', usuario=self.admin_user)
        self.assertTrue(conf['permissoes']['producao_habilitada'])
        self.assertTrue(conf['permissoes']['usuario_pode_emitir_producao'])
        self.assertTrue(conf['permissoes']['pode_emitir_producao'])
        self.assertTrue(conf['emissao_producao']['pronta'])
        self.assertEqual(conf['emissao_producao']['emitente']['nome'], 'Emitente 4015 prod')

    @override_settings(NFE_PRODUCAO_HABILITADA=True)
    def test_conferencia_fiscal_explicitamente_autorizado(self):
        conf = montar_conferencia_nfe_saida(self.nf, modo='completo', usuario=self.fiscal_prod_user)
        self.assertTrue(conf['permissoes']['usuario_pode_emitir_producao'])
        self.assertTrue(conf['permissoes']['pode_emitir_producao'])

    @override_settings(NFE_PRODUCAO_HABILITADA=True)
    def test_homologacao_nao_implica_producao_fiscal_generico(self):
        conf = montar_conferencia_nfe_saida(self.nf, modo='completo', usuario=self.fiscal_user)
        perm = montar_permissoes_emissao_producao(self.nf, usuario=self.fiscal_user)
        self.assertFalse(conf['permissoes'].get('pode_tentar_emitir_homologacao'))
        self.assertIn('produção', conf['permissoes'].get('motivo_emitir_homologacao_bloqueado', '').lower())
        self.assertFalse(perm['usuario_pode_emitir_producao'])
        self.assertFalse(perm['pode_emitir_producao'])
        self.assertIn('permissão', perm['motivo_emitir_producao_bloqueado'].lower())
        self.assertFalse(conf['permissoes']['pode_emitir_producao'])
