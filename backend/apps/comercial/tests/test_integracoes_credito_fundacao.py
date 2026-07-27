"""Fundação B2/B3 — integrações de crédito (zero HTTP externo)."""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from apps.comercial.integracoes_credito.capabilities import montar_capability_integracoes
from apps.comercial.integracoes_credito.exceptions import (
    CODE_BURO_NAO_CONTRATADO,
    CODE_PROVIDER_DESCONHECIDO,
    CODE_PROVIDER_NAO_CONFIGURADO,
    IntegracaoCreditoError,
)
from apps.comercial.integracoes_credito.registry import (
    CreditIntegrationRegistry,
    get_default_registry,
    reset_default_registry_for_tests,
)
from apps.comercial.integracoes_credito.sanitizacao import (
    hash_requisicao,
    mascarar_cnpj,
    sanitizar_mensagem_erro,
    validar_resultado_normalizado,
)
from apps.comercial.integracoes_credito.servico import (
    executar_provider_buro_somente_teste,
    executar_provider_cadastral_somente_teste,
    tentar_consulta_buro,
    tentar_consulta_cadastral,
)
from apps.comercial.models import (
    AnaliseFinanceiraProposta,
    AnaliseFinanceiraPropostaEvento,
    ConsultaExternaAnaliseFinanceira,
    PedidoVenda,
    Proposta,
)
from apps.comercial.serializers import recalcular_proposta
from apps.comercial.tests.test_analise_financeira_proposta import _proposta_prazo, _user
from apps.comercial.tests.test_converter_proposta_pedido import _item, _produto
from apps.financeiro.models import TituloFinanceiro


def _perm(codename: str) -> Permission:
    return Permission.objects.get(codename=codename)


class SanitizacaoIntegracoesTests(TestCase):
    def test_mascara_cnpj(self):
        self.assertEqual(mascarar_cnpj('11222333000181'), '**.***.***/****-81')
        self.assertNotIn('11222333000181', mascarar_cnpj('11222333000181'))

    def test_sanitiza_url_e_token(self):
        msg = sanitizar_mensagem_erro(
            'falha https://api.exemplo.com/v1?token=abc Authorization: Bearer xyz'
        )
        self.assertNotIn('https://', msg)
        self.assertNotIn('Bearer xyz', msg)
        self.assertNotIn('token=abc', msg.lower().replace('[redacted]', ''))

    def test_hash_estavel(self):
        a = hash_requisicao(
            analise_id=1, cnpj='11.222.333/0001-81', tipo='CADASTRAL', provider='x', produto='y'
        )
        b = hash_requisicao(
            analise_id=1, cnpj='11222333000181', tipo='cadastral', provider='X', produto='Y'
        )
        self.assertEqual(a, b)
        self.assertEqual(len(a), 64)

    def test_validar_remove_campos_proibidos(self):
        limpo = validar_resultado_normalizado({'razao': 'A', 'raw': {'x': 1}, 'token': 'sec'})
        self.assertEqual(limpo.get('razao'), 'A')
        self.assertNotIn('raw', limpo)
        self.assertNotIn('token', limpo)


class RegistryEProvidersNulosTests(TestCase):
    def tearDown(self):
        reset_default_registry_for_tests()

    def test_registry_inicia_sem_providers_reais(self):
        reset_default_registry_for_tests()
        cap = montar_capability_integracoes()
        self.assertFalse(cap['cadastral']['configurado'])
        self.assertFalse(cap['cadastral']['disponivel'])
        self.assertFalse(cap['cadastral']['permite_consulta'])
        self.assertEqual(cap['cadastral']['motivo'], CODE_PROVIDER_NAO_CONFIGURADO)
        self.assertIsNone(cap['cadastral']['provider'])
        self.assertFalse(cap['buro']['configurado'])
        self.assertEqual(cap['buro']['motivo'], CODE_BURO_NAO_CONTRATADO)
        self.assertEqual(cap['decisao_financeira'], 'MANUAL')

    def test_provider_desconhecido_rejeitado(self):
        reg = CreditIntegrationRegistry()
        with self.assertRaises(IntegracaoCreditoError) as ctx:
            reg.resolver_cadastral('serasa')
        self.assertEqual(ctx.exception.code, CODE_PROVIDER_DESCONHECIDO)

    def test_nao_registra_receitaws_como_nome(self):
        reg = CreditIntegrationRegistry()

        class Fake:
            def nome_provider(self):
                return 'x'

            def versao_contrato(self):
                return '1'

            def validar_configuracao(self):
                return True

            def capability(self):
                from apps.comercial.integracoes_credito.contratos import ProviderCapability

                return ProviderCapability(True, True, 'x', None, True, 'OK')

            def consultar(self, cnpj, contexto):
                raise AssertionError('não deve consultar')

        with self.assertRaises(IntegracaoCreditoError):
            reg.register_cadastral('receitaws', Fake())

    def test_null_nao_retorna_dados(self):
        with self.assertRaises(IntegracaoCreditoError) as ctx:
            executar_provider_cadastral_somente_teste('11222333000181')
        self.assertEqual(ctx.exception.code, CODE_PROVIDER_NAO_CONFIGURADO)
        with self.assertRaises(IntegracaoCreditoError) as ctx2:
            executar_provider_buro_somente_teste('11222333000181')
        self.assertEqual(ctx2.exception.code, CODE_BURO_NAO_CONTRATADO)

    @patch('urllib.request.urlopen')
    @patch('apps.cadastros.consulta_externa._get_json')
    def test_tentativa_sem_provider_nao_abre_http(self, mock_json, mock_urlopen):
        with self.assertRaises(IntegracaoCreditoError):
            tentar_consulta_cadastral(cnpj='11222333000181', analise_id=1)
        with self.assertRaises(IntegracaoCreditoError):
            tentar_consulta_buro(cnpj='11222333000181', analise_id=1)
        mock_json.assert_not_called()
        mock_urlopen.assert_not_called()
        self.assertEqual(ConsultaExternaAnaliseFinanceira.objects.count(), 0)
        self.assertFalse(
            ConsultaExternaAnaliseFinanceira.objects.filter(
                status=ConsultaExternaAnaliseFinanceira.Status.CONCLUIDA
            ).exists()
        )


class CapabilityAPITests(APITestCase):
    def tearDown(self):
        reset_default_registry_for_tests()

    def test_capability_exige_autenticacao(self):
        r = self.client.get('/api/analises-financeiras/integracoes/capacidade/')
        self.assertIn(r.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_capability_sem_perm_403(self):
        u = _user('cap_noperm')
        self.client.force_authenticate(u)
        r = self.client.get('/api/analises-financeiras/integracoes/capacidade/')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    @patch('urllib.request.urlopen')
    @patch('apps.cadastros.consulta_cnpj.consultar_cnpj_cadastral')
    def test_capability_ok_sem_http_sem_registro(self, mock_cnpj, mock_urlopen):
        u = _user('cap_ok', perms=['view_analisefinanceiraproposta'])
        self.client.force_authenticate(u)
        antes = ConsultaExternaAnaliseFinanceira.objects.count()
        r = self.client.get('/api/analises-financeiras/integracoes/capacidade/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        body = r.data
        self.assertFalse(body['cadastral']['configurado'])
        self.assertFalse(body['buro']['permite_consulta'])
        self.assertEqual(body['decisao_financeira'], 'MANUAL')
        texto = str(body).lower()
        for proibido in ('secret', 'token', 'api_key', 'receitaws', 'http://', 'https://', '.env'):
            self.assertNotIn(proibido, texto)
        self.assertEqual(ConsultaExternaAnaliseFinanceira.objects.count(), antes)
        mock_cnpj.assert_not_called()
        mock_urlopen.assert_not_called()


class ConsultaEndpointsFundacaoTests(APITestCase):
    def setUp(self):
        reset_default_registry_for_tests()
        self.proposta = _proposta_prazo([30])
        self.fin = _user(
            'fin_b23',
            perms=[
                'view_analisefinanceiraproposta',
                'solicitar_analisefinanceiraproposta',
                'decidir_analisefinanceiraproposta',
                'ver_detalhe_financeiro_analisefinanceiraproposta',
                'solicitar_consulta_cadastral_analise',
                'solicitar_consulta_buro_analise',
                'ver_resultado_cadastral_analise',
                'ver_resultado_buro_analise',
            ],
        )
        self.client.force_authenticate(self.fin)
        from apps.comercial.analise_financeira_servico import solicitar_analise

        self.analise = solicitar_analise(self.proposta, usuario=self.fin)

    def tearDown(self):
        reset_default_registry_for_tests()

    def _contagens(self) -> dict:
        return {
            'consultas': ConsultaExternaAnaliseFinanceira.objects.count(),
            'consultas_por_status': {
                st: ConsultaExternaAnaliseFinanceira.objects.filter(status=st).count()
                for st in ConsultaExternaAnaliseFinanceira.Status.values
            },
            'eventos': AnaliseFinanceiraPropostaEvento.objects.filter(
                analise_id=self.analise.pk
            ).count(),
            'eventos_total': AnaliseFinanceiraPropostaEvento.objects.count(),
            'analise_atualizada_em': AnaliseFinanceiraProposta.objects.get(
                pk=self.analise.pk
            ).atualizada_em,
            'analise_status': AnaliseFinanceiraProposta.objects.get(pk=self.analise.pk).status,
            'custo_nao_nulo': ConsultaExternaAnaliseFinanceira.objects.exclude(
                custo_consulta__isnull=True
            ).count(),
        }

    def test_lista_vazia(self):
        r = self.client.get(f'/api/analises-financeiras/{self.analise.pk}/consultas-externas/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        results = r.data.get('results', r.data)
        self.assertEqual(results, [])

    @patch('urllib.request.urlopen')
    @patch('apps.cadastros.consulta_cnpj.consultar_cnpj_cadastral')
    @patch('apps.cadastros.consulta_externa._get_json')
    def test_post_cadastral_zero_persistencia_antes_depois(
        self, mock_json, mock_cnpj, mock_urlopen
    ):
        antes = self._contagens()
        r = self.client.post(
            f'/api/analises-financeiras/{self.analise.pk}/consultas-externas/cadastral/',
            {'cnpj': '11222333000181'},
            format='json',
        )
        depois = self._contagens()
        self.assertEqual(r.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(r.data['code'], CODE_PROVIDER_NAO_CONFIGURADO)
        self.assertIn('não está configurada', r.data['detail'].lower())
        self.assertNotIn('http', r.data['detail'].lower())
        self.assertNotIn('token', r.data['detail'].lower())
        self.assertEqual(depois, antes)
        self.assertEqual(depois['consultas'], 0)
        for st in ConsultaExternaAnaliseFinanceira.Status.values:
            self.assertEqual(depois['consultas_por_status'][st], 0, msg=st)
        mock_json.assert_not_called()
        mock_cnpj.assert_not_called()
        mock_urlopen.assert_not_called()

    @patch('urllib.request.urlopen')
    @patch('apps.cadastros.consulta_cnpj.consultar_cnpj_cadastral')
    def test_post_buro_zero_persistencia_antes_depois(self, mock_cnpj, mock_urlopen):
        antes = self._contagens()
        r = self.client.post(
            f'/api/analises-financeiras/{self.analise.pk}/consultas-externas/buro/',
            {'cnpj': '11222333000181', 'finalidade': 'credito'},
            format='json',
        )
        depois = self._contagens()
        self.assertEqual(r.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(r.data['code'], CODE_BURO_NAO_CONTRATADO)
        self.assertEqual(depois, antes)
        self.assertEqual(depois['custo_nao_nulo'], 0)
        mock_cnpj.assert_not_called()
        mock_urlopen.assert_not_called()

    def test_post_cadastral_sem_perm_403(self):
        u = _user('sem_cad', perms=['view_analisefinanceiraproposta'])
        self.client.force_authenticate(u)
        antes = ConsultaExternaAnaliseFinanceira.objects.count()
        r = self.client.post(
            f'/api/analises-financeiras/{self.analise.pk}/consultas-externas/cadastral/',
            {},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(ConsultaExternaAnaliseFinanceira.objects.count(), antes)

    def test_post_cadastral_change_proposta_nao_e_fallback(self):
        u = _user('prop_only', perms=['view_analisefinanceiraproposta', 'change_proposta'])
        self.client.force_authenticate(u)
        r = self.client.post(
            f'/api/analises-financeiras/{self.analise.pk}/consultas-externas/cadastral/',
            {'cnpj': '11222333000181'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_capability_e_lista_nao_criam_consulta_nem_evento(self):
        eventos_antes = AnaliseFinanceiraPropostaEvento.objects.count()
        consultas_antes = ConsultaExternaAnaliseFinanceira.objects.count()
        with patch('urllib.request.urlopen') as mock_url:
            with patch('apps.cadastros.consulta_cnpj.consultar_cnpj_cadastral') as mock_cnpj:
                r1 = self.client.get('/api/analises-financeiras/integracoes/capacidade/')
                r2 = self.client.get(
                    f'/api/analises-financeiras/{self.analise.pk}/consultas-externas/'
                )
        self.assertEqual(r1.status_code, status.HTTP_200_OK)
        self.assertEqual(r2.status_code, status.HTTP_200_OK)
        self.assertEqual(r2.data.get('results', r2.data), [])
        self.assertEqual(ConsultaExternaAnaliseFinanceira.objects.count(), consultas_antes)
        self.assertEqual(AnaliseFinanceiraPropostaEvento.objects.count(), eventos_antes)
        mock_url.assert_not_called()
        mock_cnpj.assert_not_called()

    def test_nao_cria_concluida_nem_ficticio(self):
        self.client.post(
            f'/api/analises-financeiras/{self.analise.pk}/consultas-externas/cadastral/',
            {'cnpj': '11222333000181'},
            format='json',
        )
        self.assertFalse(
            ConsultaExternaAnaliseFinanceira.objects.filter(
                status=ConsultaExternaAnaliseFinanceira.Status.CONCLUIDA
            ).exists()
        )
        self.assertFalse(
            ConsultaExternaAnaliseFinanceira.objects.exclude(resultado_normalizado={}).exists()
        )


class ModelPermissoesMigrationTests(TestCase):
    def test_permissoes_existem_sem_add_change_delete(self):
        ct = ContentType.objects.get_for_model(ConsultaExternaAnaliseFinanceira)
        codes = set(Permission.objects.filter(content_type=ct).values_list('codename', flat=True))
        self.assertIn('view_consultaexternaanalisefinanceira', codes)
        self.assertIn('solicitar_consulta_cadastral_analise', codes)
        self.assertIn('ver_resultado_cadastral_analise', codes)
        self.assertIn('solicitar_consulta_buro_analise', codes)
        self.assertIn('ver_resultado_buro_analise', codes)
        self.assertNotIn('add_consultaexternaanalisefinanceira', codes)
        self.assertNotIn('change_consultaexternaanalisefinanceira', codes)
        self.assertNotIn('delete_consultaexternaanalisefinanceira', codes)

    def test_migration_sem_runpython_runsql(self):
        path = (
            Path(__file__).resolve().parents[1]
            / 'migrations'
            / '0038_consulta_externa_analise_financeira_fundacao.py'
        )
        tree = ast.parse(path.read_text(encoding='utf-8'))
        names = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                names.append(node.attr)
            elif isinstance(node, ast.Name):
                names.append(node.id)
        self.assertNotIn('RunPython', names)
        self.assertNotIn('RunSQL', names)

    def test_create_groups_nao_alterado_nesta_entrega(self):
        path = (
            Path(__file__).resolve().parents[2]
            / 'cadastros'
            / 'management'
            / 'commands'
            / 'create_groups.py'
        )
        self.assertTrue(path.exists(), str(path))
        texto = path.read_text(encoding='utf-8')
        self.assertNotIn('solicitar_consulta_cadastral_analise', texto)
        self.assertNotIn('solicitar_consulta_buro_analise', texto)
        self.assertNotIn('ConsultaExternaAnaliseFinanceira', texto)

    def test_model_append_nao_altera_entidades(self):
        p = _proposta_prazo([30])
        cliente_id = p.cliente_id
        valor = p.valor_total
        n_titulos = TituloFinanceiro.objects.count()
        n_pedidos = PedidoVenda.objects.count()
        n_props = Proposta.objects.count()
        montar_capability_integracoes()
        p.refresh_from_db()
        self.assertEqual(p.cliente_id, cliente_id)
        self.assertEqual(p.valor_total, valor)
        self.assertEqual(TituloFinanceiro.objects.count(), n_titulos)
        self.assertEqual(PedidoVenda.objects.count(), n_pedidos)
        self.assertEqual(Proposta.objects.count(), n_props)


class B1GuardIntactosComFundacaoTests(TestCase):
    def test_exposicao_formula_inalterada(self):
        from apps.comercial.analise_financeira_indicadores import SCHEMA_VERSAO, montar_indicadores

        self.assertEqual(SCHEMA_VERSAO, 2)
        p = _proposta_prazo([30], valor=__import__('decimal').Decimal('200'))
        ind = montar_indicadores(cliente=p.cliente, valor_proposta=p.valor_total, proposta_id=p.pk)
        exp = ind['indicadores']['exposicao']
        self.assertIn('atual', exp)
        self.assertIn('projetada', exp)
        self.assertNotIn('divida_externa', exp)

    def test_guard_arquivo_presente(self):
        path = Path(__file__).resolve().parents[1] / 'converter_proposta_pedido.py'
        self.assertTrue(path.exists())
