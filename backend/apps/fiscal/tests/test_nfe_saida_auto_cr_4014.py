"""ERP 4.0.14.x — Geração automática de Contas a Receber após autorização produção."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, TransactionTestCase, override_settings
from rest_framework.test import APIClient

from apps.financeiro.models import TituloFinanceiro
from apps.fiscal.models import AtendimentoEstoque, NFeSaida
from apps.fiscal.nfe_emissao.retorno_sefaz import resultado_autorizacao_mock
from apps.fiscal.nfe_emissao.servico_producao import emitir_nfe_producao
from apps.fiscal.nfe_saida_duplicatas import aplicar_duplicatas_nfe_saida
from apps.fiscal.nfe_saida_financeiro import (
    MSG_ALERTA_NFE_CANCELADA,
    MSG_AUTO_FALHA_CR,
    MSG_CR_GERADO,
    MSG_CR_JA_EXISTENTE,
    gerar_contas_receber_automatico_apos_autorizacao_producao,
    gerar_contas_receber_de_nfe_autorizada,
    montar_parcelas_sugeridas_nfe,
    preview_contas_receber_de_nfe,
)
from apps.fiscal.tests.test_nfe_saida_40143_gerar_contas_receber import (
    _autorizar_nf,
    _autorizar_nf_homologacao,
)
from apps.fiscal.tests.test_nfe_saida_402_emissao_homologacao import _pedido_nf
from apps.fiscal.tests.test_nfe_saida_producao_4015 import (
    CONFIRMACAO_PRODUCAO,
    XML_AUTORIZADO_MOCK_PROD,
    _grant_permissao_producao,
    _pedido_nf as _pedido_nf_producao,
    _preparar_nf_indicadores,
    _preparar_pronta,
)


class NFeAutoContasReceberServiceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('autocr', 'autocr@test.com', 'x')
        self.pedido, self.item, self.nf = _pedido_nf()
        self.nf = _autorizar_nf(self.nf)
        aplicar_duplicatas_nfe_saida(self.nf)

    def test_auto_gera_cr_producao(self):
        res = gerar_contas_receber_automatico_apos_autorizacao_producao(self.nf, usuario=self.user)
        self.assertTrue(res['tentado'])
        self.assertTrue(res['gerado'])
        self.assertFalse(res['erro'])
        self.assertEqual(res['mensagem'], MSG_CR_GERADO)
        titulo = TituloFinanceiro.objects.get(pk=res['titulo_id'])
        self.assertEqual(titulo.origem_tipo, TituloFinanceiro.OrigemTipo.NFE_SAIDA)
        self.assertEqual(titulo.origem_id, self.nf.pk)
        self.assertEqual(titulo.cliente_id, self.nf.cliente_id)
        self.assertAlmostEqual(float(titulo.valor_original), float(self.nf.valor_total), places=2)
        self.assertEqual(titulo.status, TituloFinanceiro.Status.EM_ABERTO)
        self.assertEqual(titulo.valor_baixado, 0)

    def test_homologacao_nao_gera(self):
        nf = _autorizar_nf_homologacao(self.nf)
        res = gerar_contas_receber_automatico_apos_autorizacao_producao(nf, usuario=self.user)
        self.assertFalse(res['tentado'])
        self.assertFalse(res['gerado'])
        self.assertEqual(
            TituloFinanceiro.objects.filter(
                origem_tipo=TituloFinanceiro.OrigemTipo.NFE_SAIDA,
                origem_id=nf.pk,
            ).count(),
            0,
        )

    def test_cstat_nao_autorizado_nao_gera(self):
        self.nf.cstat_autorizacao = '539'
        self.nf.save(update_fields=['cstat_autorizacao'])
        res = gerar_contas_receber_automatico_apos_autorizacao_producao(self.nf, usuario=self.user)
        self.assertFalse(res['tentado'])
        self.assertEqual(
            TituloFinanceiro.objects.filter(
                origem_tipo=TituloFinanceiro.OrigemTipo.NFE_SAIDA,
                origem_id=self.nf.pk,
            ).count(),
            0,
        )

    def test_retry_idempotente(self):
        r1 = gerar_contas_receber_automatico_apos_autorizacao_producao(self.nf, usuario=self.user)
        r2 = gerar_contas_receber_automatico_apos_autorizacao_producao(self.nf, usuario=self.user)
        self.assertTrue(r1['gerado'])
        self.assertTrue(r2['ja_existente'])
        self.assertEqual(r1['titulo_id'], r2['titulo_id'])
        self.assertEqual(r2['mensagem'], MSG_CR_JA_EXISTENTE)
        self.assertEqual(
            TituloFinanceiro.objects.filter(
                origem_tipo=TituloFinanceiro.OrigemTipo.NFE_SAIDA,
                origem_id=self.nf.pk,
            ).count(),
            1,
        )

    def test_parcelas_e_total_conferem(self):
        preview = preview_contas_receber_de_nfe(self.nf)
        res = gerar_contas_receber_automatico_apos_autorizacao_producao(self.nf, usuario=self.user)
        titulo = TituloFinanceiro.objects.get(pk=res['titulo_id'])
        self.assertEqual(titulo.parcelas.count(), len(preview['parcelas']))
        soma = sum(p.valor_original for p in titulo.parcelas.all())
        self.assertAlmostEqual(float(soma), float(titulo.valor_original), places=2)

    def test_falha_financeira_mantem_nfe_autorizada(self):
        with patch(
            'apps.fiscal.nfe_saida_financeiro.gerar_contas_receber_de_nfe_autorizada',
            side_effect=RuntimeError('falha simulada financeiro'),
        ):
            res = gerar_contas_receber_automatico_apos_autorizacao_producao(self.nf, usuario=self.user)
        self.assertTrue(res['erro'])
        self.assertEqual(res['mensagem'], MSG_AUTO_FALHA_CR)
        self.nf.refresh_from_db()
        self.assertEqual(self.nf.status_emissao_sefaz, NFeSaida.StatusEmissaoSefaz.AUTORIZADA_PRODUCAO)
        self.assertTrue((self.nf.xml_autorizado or '').strip())
        self.assertEqual(
            TituloFinanceiro.objects.filter(
                origem_tipo=TituloFinanceiro.OrigemTipo.NFE_SAIDA,
                origem_id=self.nf.pk,
            ).count(),
            0,
        )

    def test_acao_manual_regulariza_apos_falha(self):
        with patch(
            'apps.fiscal.nfe_saida_financeiro.gerar_contas_receber_de_nfe_autorizada',
            side_effect=ValueError('sem categoria'),
        ):
            auto = gerar_contas_receber_automatico_apos_autorizacao_producao(self.nf, usuario=self.user)
        self.assertTrue(auto['erro'])
        parcelas = montar_parcelas_sugeridas_nfe(self.nf)
        titulo = gerar_contas_receber_de_nfe_autorizada(self.nf, parcelas=parcelas, usuario=self.user)
        self.assertEqual(titulo.origem_id, self.nf.pk)

    def test_titulo_ja_existente_nao_duplicado(self):
        parcelas = montar_parcelas_sugeridas_nfe(self.nf)
        titulo = gerar_contas_receber_de_nfe_autorizada(self.nf, parcelas=parcelas, usuario=self.user)
        res = gerar_contas_receber_automatico_apos_autorizacao_producao(self.nf, usuario=self.user)
        self.assertTrue(res['ja_existente'])
        self.assertEqual(res['titulo_id'], titulo.pk)
        self.assertEqual(
            TituloFinanceiro.objects.filter(
                origem_tipo=TituloFinanceiro.OrigemTipo.NFE_SAIDA,
                origem_id=self.nf.pk,
            ).count(),
            1,
        )

    def test_cancelamento_posterior_mantem_titulo_e_alerta(self):
        res = gerar_contas_receber_automatico_apos_autorizacao_producao(self.nf, usuario=self.user)
        titulo_id = res['titulo_id']
        xml_antes = self.nf.xml_autorizado
        self.nf.status = 'CANCELADA'
        self.nf.save(update_fields=['status'])
        self.assertTrue(TituloFinanceiro.objects.filter(pk=titulo_id).exists())
        self.nf.refresh_from_db()
        self.assertEqual(self.nf.xml_autorizado, xml_antes)
        client = APIClient()
        client.force_authenticate(self.user)
        detail = client.get(f'/api/financeiro/contas-receber/{titulo_id}/')
        self.assertEqual(detail.status_code, 200)
        self.assertIn(MSG_ALERTA_NFE_CANCELADA, detail.json()['alerta_origem_cancelada'])


class NFeAutoContasReceberEmissaoProducaoTests(TestCase):
    """Integração com emitir_nfe_producao (mock SEFAZ)."""

    def setUp(self):
        self.user = get_user_model().objects.create_user('autocrprod', 'autocrprod@test.com', 'x')
        self.pedido, self.nf = _pedido_nf_producao()
        self.nf = _preparar_nf_indicadores(self.nf)
        _grant_permissao_producao(self.user)
        self.nf = _preparar_pronta(self.nf, self.user)

    @override_settings(NFE_PRODUCAO_HABILITADA=True)
    @patch('apps.fiscal.nfe_emissao.servico_producao.validar_emissao_completa', return_value={'ok': True, 'erros': []})
    @patch('apps.fiscal.nfe_emissao.servico_producao.transmitir_nfe_producao')
    @patch('apps.fiscal.nfe_emissao.servico_producao.assinar_xml_nfe')
    def test_autorizacao_producao_gera_cr(self, mock_assinar, mock_tx, _mock_xsd):
        mock_assinar.side_effect = lambda xml, emp, **kw: xml if isinstance(xml, bytes) else xml.encode()
        mock_tx.return_value = resultado_autorizacao_mock(
            autorizado=True,
            c_stat='100',
            x_motivo='Autorizado',
            protocolo='135260000000099',
            xml_retorno=XML_AUTORIZADO_MOCK_PROD,
            xml_autorizado=XML_AUTORIZADO_MOCK_PROD,
        )
        antes_estoque = AtendimentoEstoque.objects.count()
        res = emitir_nfe_producao(
            self.nf,
            usuario=self.user,
            confirmacao_payload=CONFIRMACAO_PRODUCAO,
        )
        self.assertTrue(res['autorizado'])
        self.assertIn('financeiro', res)
        self.assertTrue(res['financeiro']['gerado'] or res['financeiro']['ja_existente'])
        self.nf.refresh_from_db()
        self.assertEqual(self.nf.status_emissao_sefaz, 'AUTORIZADA_PRODUCAO')
        self.assertEqual(
            TituloFinanceiro.objects.filter(
                origem_tipo=TituloFinanceiro.OrigemTipo.NFE_SAIDA,
                origem_id=self.nf.pk,
            ).count(),
            1,
        )
        self.assertEqual(AtendimentoEstoque.objects.count(), antes_estoque)

    @override_settings(NFE_PRODUCAO_HABILITADA=True)
    @patch('apps.fiscal.nfe_emissao.servico_producao.validar_emissao_completa', return_value={'ok': True, 'erros': []})
    @patch('apps.fiscal.nfe_emissao.servico_producao.transmitir_nfe_producao')
    @patch('apps.fiscal.nfe_emissao.servico_producao.assinar_xml_nfe')
    def test_falha_cr_na_emissao_mantem_autorizacao(self, mock_assinar, mock_tx, _mock_xsd):
        mock_assinar.side_effect = lambda xml, emp, **kw: xml if isinstance(xml, bytes) else xml.encode()
        mock_tx.return_value = resultado_autorizacao_mock(
            autorizado=True,
            c_stat='100',
            x_motivo='Autorizado',
            protocolo='135260000000099',
            xml_retorno=XML_AUTORIZADO_MOCK_PROD,
            xml_autorizado=XML_AUTORIZADO_MOCK_PROD,
        )
        with patch(
            'apps.fiscal.nfe_saida_financeiro.gerar_contas_receber_de_nfe_autorizada',
            side_effect=RuntimeError('falha CR'),
        ):
            res = emitir_nfe_producao(
                self.nf,
                usuario=self.user,
                confirmacao_payload=CONFIRMACAO_PRODUCAO,
            )
        self.assertTrue(res['autorizado'])
        self.assertTrue(res['financeiro']['erro'])
        self.assertEqual(res['financeiro']['mensagem'], MSG_AUTO_FALHA_CR)
        self.nf.refresh_from_db()
        self.assertEqual(self.nf.status_emissao_sefaz, 'AUTORIZADA_PRODUCAO')
        self.assertTrue((self.nf.xml_autorizado or '').strip())
        self.assertEqual(
            TituloFinanceiro.objects.filter(
                origem_tipo=TituloFinanceiro.OrigemTipo.NFE_SAIDA,
                origem_id=self.nf.pk,
            ).count(),
            0,
        )

    @override_settings(NFE_PRODUCAO_HABILITADA=True)
    @patch('apps.fiscal.nfe_emissao.servico_producao.validar_emissao_completa', return_value={'ok': True, 'erros': []})
    @patch('apps.fiscal.nfe_emissao.servico_producao.transmitir_nfe_producao')
    @patch('apps.fiscal.nfe_emissao.servico_producao.assinar_xml_nfe')
    def test_rejeicao_nao_gera_cr(self, mock_assinar, mock_tx, _mock_xsd):
        mock_assinar.side_effect = lambda xml, emp, **kw: xml if isinstance(xml, bytes) else xml.encode()
        mock_tx.return_value = resultado_autorizacao_mock(
            autorizado=False,
            c_stat='539',
            x_motivo='Rejeição teste',
            protocolo='',
            xml_retorno='<retEnviNFe><cStat>104</cStat></retEnviNFe>',
            xml_autorizado='',
        )
        res = emitir_nfe_producao(
            self.nf,
            usuario=self.user,
            confirmacao_payload=CONFIRMACAO_PRODUCAO,
        )
        self.assertFalse(res['autorizado'])
        self.assertIsNone(res.get('financeiro'))
        self.assertEqual(
            TituloFinanceiro.objects.filter(
                origem_tipo=TituloFinanceiro.OrigemTipo.NFE_SAIDA,
                origem_id=self.nf.pk,
            ).count(),
            0,
        )


class NFeAutoContasReceberConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('autocrconc', 'autocrconc@test.com', 'x')
        self.pedido, self.item, self.nf = _pedido_nf()
        self.nf = _autorizar_nf(self.nf)
        aplicar_duplicatas_nfe_saida(self.nf)

    def test_concorrencia_nao_duplica(self):
        nf_id = self.nf.pk
        user = self.user

        def _run():
            try:
                nf = NFeSaida.objects.get(pk=nf_id)
                return gerar_contas_receber_automatico_apos_autorizacao_producao(nf, usuario=user)
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            resultados = list(pool.map(lambda _: _run(), range(2)))

        gerados = [r for r in resultados if r.get('gerado')]
        existentes = [r for r in resultados if r.get('ja_existente')]
        self.assertEqual(len(gerados) + len(existentes), 2)
        self.assertLessEqual(len(gerados), 1)
        self.assertEqual(
            TituloFinanceiro.objects.filter(
                origem_tipo=TituloFinanceiro.OrigemTipo.NFE_SAIDA,
                origem_id=nf_id,
            ).count(),
            1,
        )
