"""Ambiente e numeração na conferência NF-e Saída."""

from __future__ import annotations

from django.test import TestCase, override_settings

from apps.cadastros.models import Empresa
from apps.fiscal.models import NFeSaida
from apps.fiscal.nfe_emissao.ambiente_emissao_nfe import (
    MSG_AMBIENTE_NAO_DEFINIDO,
    garantir_ambiente_emissao_nfe_saida,
)
from apps.fiscal.nfe_saida_conferencia import montar_conferencia_nfe_saida
from apps.fiscal.tests.nfe_4015_test_support import NFe4015GruposMixin, vincular_grupo_teste
from apps.fiscal.tests.test_nfe_saida_producao_4015 import (
    _pedido_nf,
    _preparar_nf_indicadores,
)


class NFeAmbienteNumeracaoConferenciaTests(NFe4015GruposMixin, TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.admin_user = User.objects.create_user('admamb', 'admamb@test.com', 'x')
        vincular_grupo_teste(self.admin_user, 'admin')
        self.pedido, self.nf = _pedido_nf()
        self.nf = _preparar_nf_indicadores(self.nf)

    def test_geracao_rascunho_herda_ambiente_empresa(self):
        self.assertEqual(self.nf.ambiente_emissao, NFeSaida.AmbienteEmissao.PRODUCAO)

    def test_garantir_ambiente_preenche_rascunho_vazio(self):
        self.nf.ambiente_emissao = ''
        self.nf.save(update_fields=['ambiente_emissao'])
        garantir_ambiente_emissao_nfe_saida(self.nf)
        self.nf.refresh_from_db()
        self.assertEqual(self.nf.ambiente_emissao, NFeSaida.AmbienteEmissao.PRODUCAO)

    @override_settings(NFE_PRODUCAO_HABILITADA=True)
    def test_conferencia_producao_exibe_numeracao_producao(self):
        conf = montar_conferencia_nfe_saida(self.nf, modo='completo', usuario=self.admin_user)
        self.assertEqual(conf['apresentacao']['ambiente_emissao'], 'producao')
        self.assertEqual(conf['emissao_sefaz']['ambiente_emissao'], 'producao')
        self.assertIsNone(conf['emissao_sefaz'].get('numeracao_homologacao'))
        numeracao = conf['emissao_sefaz'].get('numeracao_producao')
        self.assertIsNotNone(numeracao)
        self.assertEqual(numeracao['serie'], '1')
        self.assertTrue(conf['permissoes']['ambiente_emissao_definido'])

    def test_conferencia_homolog_exibe_numeracao_homolog(self):
        emp = self.pedido.empresa_emitente
        emp.nfe_ambiente = Empresa.NfeAmbiente.HOMOLOGACAO
        emp.save(update_fields=['nfe_ambiente'])
        self.nf.ambiente_emissao = NFeSaida.AmbienteEmissao.HOMOLOGACAO
        self.nf.save(update_fields=['ambiente_emissao'])
        conf = montar_conferencia_nfe_saida(self.nf, modo='completo', usuario=self.admin_user)
        self.assertEqual(conf['apresentacao']['ambiente_emissao'], 'homologacao')
        self.assertIsNotNone(conf['emissao_sefaz'].get('numeracao_homologacao'))
        self.assertIsNone(conf['emissao_sefaz'].get('numeracao_producao'))

    def test_marcar_pronta_bloqueada_sem_ambiente(self):
        self.pedido.empresa_emitente_id = None
        self.pedido.save(update_fields=['empresa_emitente_id'])
        self.nf.ambiente_emissao = ''
        self.nf.save(update_fields=['ambiente_emissao'])
        conf = montar_conferencia_nfe_saida(self.nf, modo='completo', usuario=self.admin_user)
        self.assertFalse(conf['permissoes']['ambiente_emissao_definido'])
        self.assertFalse(conf['permissoes']['pode_marcar_pronta'])
        self.assertIn(MSG_AMBIENTE_NAO_DEFINIDO, conf['permissoes']['motivo_marcar_pronta_bloqueado'])

    def test_preliminar_producao_usa_numeracao_e_tpamb_producao(self):
        from apps.fiscal.models import NFeNumeracaoConfiguracao
        from apps.fiscal.nfe_integracao.nfe_numero_fiscal_preliminar import resolver_numero_fiscal_preliminar
        from apps.fiscal.nfe_integracao.nfe_xml_preliminar import gerar_xml_nfe_preliminar

        prod = NFeNumeracaoConfiguracao.objects.get(
            empresa=self.pedido.empresa_emitente,
            ambiente='producao',
            tipo_operacao=NFeNumeracaoConfiguracao.TipoOperacao.SAIDA,
            serie='1',
        )
        hom = NFeNumeracaoConfiguracao.objects.get(
            empresa=self.pedido.empresa_emitente,
            ambiente='homologacao',
            tipo_operacao=NFeNumeracaoConfiguracao.TipoOperacao.SAIDA,
            serie='0',
        )
        num = resolver_numero_fiscal_preliminar(self.nf)
        self.assertEqual(int(num.serie), 1)
        self.assertEqual(int(num.nnf), prod.proximo_numero)
        self.assertNotEqual(int(num.serie), int(hom.serie))
        self.assertNotEqual(int(num.nnf), hom.proximo_numero)

        xml = gerar_xml_nfe_preliminar(self.nf, persistir=False).decode('utf-8')
        self.assertIn('<tpAmb>1</tpAmb>', xml)
        self.assertRegex(xml, rf'<nNF>{prod.proximo_numero}</nNF>')

    def test_preliminar_ambiente_indefinido_bloqueia(self):
        from apps.fiscal.nfe_integracao.nfe_numero_fiscal_preliminar import (
            NumeroFiscalPreliminarError,
            resolver_numero_fiscal_preliminar,
        )
        from apps.fiscal.nfe_integracao.nfe_xml_preliminar import NFeXmlPreliminarError, gerar_xml_nfe_preliminar

        self.nf.ambiente_emissao = ''
        self.nf.save(update_fields=['ambiente_emissao'])
        with self.assertRaises(NumeroFiscalPreliminarError) as ctx_num:
            resolver_numero_fiscal_preliminar(self.nf)
        self.assertIn(MSG_AMBIENTE_NAO_DEFINIDO, str(ctx_num.exception))
        with self.assertRaises(NFeXmlPreliminarError) as ctx_xml:
            gerar_xml_nfe_preliminar(self.nf)
        self.assertIn(MSG_AMBIENTE_NAO_DEFINIDO, str(ctx_xml.exception))
