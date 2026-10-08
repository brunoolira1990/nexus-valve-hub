"""P1 — registro manual auditável de protestos (zero HTTP externo, zero A1)."""

from __future__ import annotations

import ast
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.comercial.analise_financeira_servico import solicitar_analise
from apps.comercial.integracoes_credito.protesto_manual import (
    AVISO_COBERTURA,
    ORIGEM,
    PROVIDER,
    PRODUTO,
    RESULTADO_COM,
    RESULTADO_INCONCLUSIVA,
    RESULTADO_SEM,
    ProtestoManualError,
    registrar_protesto_manual,
)
from apps.comercial.models import (
    AnaliseFinanceiraPropostaEvento,
    ConsultaExternaAnaliseFinanceira,
    PedidoVenda,
    Proposta,
)
from apps.comercial.tests.test_analise_financeira_proposta import _proposta_prazo, _user
from apps.financeiro.models import TituloFinanceiro


class Migration0039ProtestoManualTests(TestCase):
    def test_choices_cabem_no_max_length(self):
        self.assertLessEqual(len('PROTESTO_MANUAL'), 16)
        self.assertLessEqual(len('PROTESTO_MANUAL_REGISTRADO'), 32)
        tipo_field = ConsultaExternaAnaliseFinanceira._meta.get_field('tipo')
        evento_field = AnaliseFinanceiraPropostaEvento._meta.get_field('tipo')
        self.assertEqual(tipo_field.max_length, 16)
        self.assertEqual(evento_field.max_length, 32)
        self.assertIn(
            ConsultaExternaAnaliseFinanceira.Tipo.PROTESTO_MANUAL,
            dict(ConsultaExternaAnaliseFinanceira.Tipo.choices),
        )
        self.assertIn(
            AnaliseFinanceiraPropostaEvento.Tipo.PROTESTO_MANUAL_REGISTRADO,
            dict(AnaliseFinanceiraPropostaEvento.Tipo.choices),
        )

    def test_meta_permissions_preserva_b2_b3(self):
        ct = ContentType.objects.get_for_model(ConsultaExternaAnaliseFinanceira)
        codes = set(Permission.objects.filter(content_type=ct).values_list('codename', flat=True))
        for code in (
            'view_consultaexternaanalisefinanceira',
            'solicitar_consulta_cadastral_analise',
            'ver_resultado_cadastral_analise',
            'solicitar_consulta_buro_analise',
            'ver_resultado_buro_analise',
            'registrar_protesto_manual_analise',
            'ver_protesto_manual_analise',
        ):
            self.assertIn(code, codes)
        self.assertNotIn('add_consultaexternaanalisefinanceira', codes)
        self.assertNotIn('change_consultaexternaanalisefinanceira', codes)
        self.assertNotIn('delete_consultaexternaanalisefinanceira', codes)

    def test_migration_sem_runpython_runsql(self):
        path = (
            Path(__file__).resolve().parents[1]
            / 'migrations'
            / '0039_protesto_manual_analise_financeira.py'
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

    def test_create_groups_sem_grant_protesto(self):
        path = (
            Path(__file__).resolve().parents[2]
            / 'cadastros'
            / 'management'
            / 'commands'
            / 'create_groups.py'
        )
        texto = path.read_text(encoding='utf-8')
        self.assertNotIn('registrar_protesto_manual_analise', texto)
        self.assertNotIn('ver_protesto_manual_analise', texto)


class ProtestoManualGuardsAstTests(TestCase):
    def test_modulo_sem_http_nem_a1(self):
        path = (
            Path(__file__).resolve().parents[1]
            / 'integracoes_credito'
            / 'protesto_manual.py'
        )
        src = path.read_text(encoding='utf-8')
        tree = ast.parse(src)
        imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or '')
        joined = ' '.join(imports).lower() + '\n' + src.lower()
        for proibido in (
            'requests',
            'httpx',
            'urllib',
            'selenium',
            'playwright',
            'apps.certificados',
            'certificadodigitala1facade',
            'certificado_arquivo',
            'senha_certificado',
        ):
            self.assertNotIn(proibido, joined)


class ProtestoManualServicoTests(TestCase):
    def setUp(self):
        self.user = _user('prot_svc')
        self.proposta = _proposta_prazo([30])
        self.analise = solicitar_analise(self.proposta, usuario=self.user)

    def test_sem_protestos(self):
        reg = registrar_protesto_manual(
            analise=self.analise,
            usuario=self.user,
            payload={'resultado': RESULTADO_SEM},
        )
        self.assertEqual(reg.tipo, ConsultaExternaAnaliseFinanceira.Tipo.PROTESTO_MANUAL)
        self.assertEqual(reg.provider, PROVIDER)
        self.assertEqual(reg.produto, PRODUTO)
        self.assertEqual(reg.status, ConsultaExternaAnaliseFinanceira.Status.CONCLUIDA)
        self.assertIsNone(reg.custo_consulta)
        self.assertEqual(reg.protocolo_mascarado, '')
        self.assertEqual(reg.erro_sanitizado, '')
        self.assertEqual(reg.solicitada_por_id, self.user.pk)
        self.assertIsNotNone(reg.concluida_em)
        rn = reg.resultado_normalizado
        self.assertTrue(rn['registro_manual'])
        self.assertEqual(rn['origem'], ORIGEM)
        self.assertEqual(rn['resultado'], RESULTADO_SEM)
        self.assertIsNone(rn['quantidade_informada'])
        self.assertEqual(rn['aviso'], AVISO_COBERTURA)
        self.assertEqual(rn['registrado_por']['id'], str(self.user.pk))
        self.assertIn('****', reg.cnpj_mascarado)

    def test_com_protestos_e_quantidade_nula(self):
        reg = registrar_protesto_manual(
            analise=self.analise,
            usuario=self.user,
            payload={'resultado': RESULTADO_COM, 'ufs_informadas': ['SP', 'RJ']},
        )
        self.assertEqual(reg.resultado_normalizado['resultado'], RESULTADO_COM)
        self.assertIsNone(reg.resultado_normalizado['quantidade_informada'])
        self.assertEqual(reg.resultado_normalizado['ufs_informadas'], ['SP', 'RJ'])

    def test_inconclusiva_exige_observacao(self):
        with self.assertRaises(ProtestoManualError) as ctx:
            registrar_protesto_manual(
                analise=self.analise,
                usuario=self.user,
                payload={'resultado': RESULTADO_INCONCLUSIVA},
            )
        self.assertEqual(ctx.exception.code, 'OBSERVACAO_OBRIGATORIA')

    def test_quantidade_negativa(self):
        with self.assertRaises(ProtestoManualError) as ctx:
            registrar_protesto_manual(
                analise=self.analise,
                usuario=self.user,
                payload={'resultado': RESULTADO_SEM, 'quantidade_informada': -1},
            )
        self.assertEqual(ctx.exception.code, 'QUANTIDADE_INVALIDA')

    def test_quantidade_zero_com_protestos(self):
        with self.assertRaises(ProtestoManualError) as ctx:
            registrar_protesto_manual(
                analise=self.analise,
                usuario=self.user,
                payload={'resultado': RESULTADO_COM, 'quantidade_informada': 0},
            )
        self.assertEqual(ctx.exception.code, 'QUANTIDADE_INVALIDA')

    def test_ignora_auditoria_do_cliente(self):
        futuro = timezone.now() + timedelta(days=1)
        reg = registrar_protesto_manual(
            analise=self.analise,
            usuario=self.user,
            payload={
                'resultado': RESULTADO_SEM,
                'registrado_por': {'id': '999', 'nome_exibicao': 'Hacker'},
                'registrado_em': futuro.isoformat(),
                'solicitada_por': 999,
                'provider': 'OUTRO',
                'produto': 'X',
                'status': 'PENDENTE',
                'custo_consulta': '99.90',
                'cnpj_mascarado': '11.222.333/0001-81',
                'tipo': 'BURO',
            },
        )
        self.assertEqual(reg.provider, PROVIDER)
        self.assertEqual(reg.produto, PRODUTO)
        self.assertEqual(reg.status, ConsultaExternaAnaliseFinanceira.Status.CONCLUIDA)
        self.assertIsNone(reg.custo_consulta)
        self.assertEqual(reg.solicitada_por_id, self.user.pk)
        self.assertEqual(reg.resultado_normalizado['registrado_por']['id'], str(self.user.pk))
        self.assertNotEqual(reg.resultado_normalizado['registrado_por']['nome_exibicao'], 'Hacker')
        self.assertNotIn('11222333000181', reg.cnpj_mascarado)

    def test_consultado_em_nao_sobrescreve_concluida_em(self):
        consultado = timezone.now() - timedelta(hours=2)
        antes = timezone.now()
        reg = registrar_protesto_manual(
            analise=self.analise,
            usuario=self.user,
            payload={
                'resultado': RESULTADO_SEM,
                'consultado_em': consultado.isoformat(),
            },
        )
        depois = timezone.now()
        self.assertEqual(
            reg.resultado_normalizado['consultado_em'][:19],
            consultado.isoformat()[:19],
        )
        self.assertGreaterEqual(reg.concluida_em, antes)
        self.assertLessEqual(reg.concluida_em, depois)
        self.assertNotEqual(reg.concluida_em.replace(microsecond=0), consultado.replace(microsecond=0))

    def test_correcao_cria_novo_registro(self):
        primeiro = registrar_protesto_manual(
            analise=self.analise,
            usuario=self.user,
            payload={'resultado': RESULTADO_SEM},
        )
        segundo = registrar_protesto_manual(
            analise=self.analise,
            usuario=self.user,
            payload={
                'resultado': RESULTADO_COM,
                'quantidade_informada': 2,
                'registro_anterior_id': primeiro.pk,
                'motivo_correcao': 'Portal mostrou 2 protestos após nova consulta.',
            },
        )
        self.assertEqual(ConsultaExternaAnaliseFinanceira.objects.filter(tipo='PROTESTO_MANUAL').count(), 2)
        primeiro.refresh_from_db()
        self.assertEqual(primeiro.resultado_normalizado['resultado'], RESULTADO_SEM)
        self.assertEqual(segundo.registro_anterior_id, primeiro.pk)
        self.assertEqual(segundo.resultado_normalizado['corrige_registro_id'], primeiro.pk)
        self.assertTrue(segundo.resultado_normalizado['motivo_correcao'])

    def test_motivo_correcao_obrigatorio(self):
        primeiro = registrar_protesto_manual(
            analise=self.analise,
            usuario=self.user,
            payload={'resultado': RESULTADO_SEM},
        )
        with self.assertRaises(ProtestoManualError) as ctx:
            registrar_protesto_manual(
                analise=self.analise,
                usuario=self.user,
                payload={
                    'resultado': RESULTADO_COM,
                    'registro_anterior_id': primeiro.pk,
                },
            )
        self.assertEqual(ctx.exception.code, 'MOTIVO_CORRECAO_OBRIGATORIO')

    def test_correcao_outra_analise(self):
        outro = solicitar_analise(_proposta_prazo([60], valor=Decimal('300')), usuario=self.user)
        alien = registrar_protesto_manual(
            analise=outro,
            usuario=self.user,
            payload={'resultado': RESULTADO_SEM},
        )
        with self.assertRaises(ProtestoManualError) as ctx:
            registrar_protesto_manual(
                analise=self.analise,
                usuario=self.user,
                payload={
                    'resultado': RESULTADO_SEM,
                    'registro_anterior_id': alien.pk,
                    'motivo_correcao': 'tentativa inválida',
                },
            )
        self.assertEqual(ctx.exception.code, 'REGISTRO_ANTERIOR_OUTRA_ANALISE')

    def test_correcao_tipo_buro_rejeitada(self):
        buro = ConsultaExternaAnaliseFinanceira.objects.create(
            analise_financeira=self.analise,
            tipo=ConsultaExternaAnaliseFinanceira.Tipo.BURO,
            provider='x',
            produto='y',
            status=ConsultaExternaAnaliseFinanceira.Status.CONCLUIDA,
            solicitada_por=self.user,
        )
        with self.assertRaises(ProtestoManualError) as ctx:
            registrar_protesto_manual(
                analise=self.analise,
                usuario=self.user,
                payload={
                    'resultado': RESULTADO_SEM,
                    'registro_anterior_id': buro.pk,
                    'motivo_correcao': 'não deve aceitar',
                },
            )
        self.assertEqual(ctx.exception.code, 'REGISTRO_ANTERIOR_TIPO_INVALIDO')

    def test_evento_e_registro_rollback_juntos(self):
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                registrar_protesto_manual(
                    analise=self.analise,
                    usuario=self.user,
                    payload={'resultado': RESULTADO_SEM},
                )
                raise RuntimeError('falha simulada após create')
        self.assertEqual(
            ConsultaExternaAnaliseFinanceira.objects.filter(tipo='PROTESTO_MANUAL').count(),
            0,
        )
        self.assertEqual(
            AnaliseFinanceiraPropostaEvento.objects.filter(
                tipo=AnaliseFinanceiraPropostaEvento.Tipo.PROTESTO_MANUAL_REGISTRADO
            ).count(),
            0,
        )

    def test_evento_criado_somente_no_salvamento(self):
        antes = AnaliseFinanceiraPropostaEvento.objects.filter(
            tipo=AnaliseFinanceiraPropostaEvento.Tipo.PROTESTO_MANUAL_REGISTRADO
        ).count()
        self.assertEqual(
            ConsultaExternaAnaliseFinanceira.objects.filter(tipo='PROTESTO_MANUAL').count(),
            0,
        )
        reg = registrar_protesto_manual(
            analise=self.analise,
            usuario=self.user,
            payload={'resultado': RESULTADO_INCONCLUSIVA, 'observacao': 'Portal indisponível'},
        )
        ev = AnaliseFinanceiraPropostaEvento.objects.filter(
            tipo=AnaliseFinanceiraPropostaEvento.Tipo.PROTESTO_MANUAL_REGISTRADO,
            analise=self.analise,
        ).latest('id')
        self.assertEqual(
            AnaliseFinanceiraPropostaEvento.objects.filter(
                tipo=AnaliseFinanceiraPropostaEvento.Tipo.PROTESTO_MANUAL_REGISTRADO
            ).count(),
            antes + 1,
        )
        self.assertEqual(ev.dados['registro_id'], reg.pk)
        self.assertEqual(ev.dados['fonte'], ORIGEM)
        self.assertEqual(ev.dados['resultado'], RESULTADO_INCONCLUSIVA)
        self.assertNotIn('observacao', ev.dados)
        self.assertNotIn('cnpj', str(ev.dados).lower())

    def test_nao_altera_cliente_proposta_exposicao_cr(self):
        limite = self.proposta.cliente.limite_credito
        valor = self.proposta.valor_total
        n_cr = TituloFinanceiro.objects.count()
        n_ped = PedidoVenda.objects.count()
        n_prop = Proposta.objects.count()
        from apps.comercial.analise_financeira_indicadores import montar_indicadores

        exp_antes = montar_indicadores(
            cliente=self.proposta.cliente,
            valor_proposta=self.proposta.valor_total,
            proposta_id=self.proposta.pk,
        )['indicadores']['exposicao']
        registrar_protesto_manual(
            analise=self.analise,
            usuario=self.user,
            payload={'resultado': RESULTADO_COM, 'quantidade_informada': 1},
        )
        self.proposta.cliente.refresh_from_db()
        self.proposta.refresh_from_db()
        self.assertEqual(self.proposta.cliente.limite_credito, limite)
        self.assertEqual(self.proposta.valor_total, valor)
        self.assertEqual(TituloFinanceiro.objects.count(), n_cr)
        self.assertEqual(PedidoVenda.objects.count(), n_ped)
        self.assertEqual(Proposta.objects.count(), n_prop)
        exp_depois = montar_indicadores(
            cliente=self.proposta.cliente,
            valor_proposta=self.proposta.valor_total,
            proposta_id=self.proposta.pk,
        )['indicadores']['exposicao']
        self.assertEqual(exp_antes, exp_depois)


class ProtestoManualAPITests(APITestCase):
    def setUp(self):
        self.proposta = _proposta_prazo([30])
        self.fin = _user(
            'fin_prot',
            perms=[
                'view_analisefinanceiraproposta',
                'registrar_protesto_manual_analise',
                'ver_protesto_manual_analise',
            ],
        )
        self.ver_only = _user(
            'ver_prot',
            perms=['view_analisefinanceiraproposta', 'ver_protesto_manual_analise'],
        )
        self.sem_perm = _user('nop_prot', perms=['view_analisefinanceiraproposta'])
        self.buro_only = _user(
            'buro_prot',
            perms=[
                'view_analisefinanceiraproposta',
                'solicitar_consulta_buro_analise',
                'ver_resultado_buro_analise',
            ],
        )
        self.analise = solicitar_analise(self.proposta, usuario=self.fin)

    def _url_list(self):
        return f'/api/analises-financeiras/{self.analise.pk}/protestos-manuais/'

    def _url_post(self):
        return f'/api/analises-financeiras/{self.analise.pk}/protestos-manuais/registrar/'

    def test_nao_autenticado_401(self):
        r = self.client.get(self._url_list())
        self.assertIn(r.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))
        r2 = self.client.post(self._url_post(), {'resultado': RESULTADO_SEM}, format='json')
        self.assertIn(r2.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_sem_permissao_403(self):
        self.client.force_authenticate(self.sem_perm)
        self.assertEqual(self.client.get(self._url_list()).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            self.client.post(self._url_post(), {'resultado': RESULTADO_SEM}, format='json').status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_perm_buro_nao_autoriza_protesto(self):
        self.client.force_authenticate(self.buro_only)
        self.assertEqual(self.client.get(self._url_list()).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            self.client.post(self._url_post(), {'resultado': RESULTADO_SEM}, format='json').status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_change_proposta_nao_e_fallback(self):
        u = _user('chg_prop', perms=['view_analisefinanceiraproposta', 'change_proposta'])
        self.client.force_authenticate(u)
        self.assertEqual(
            self.client.post(self._url_post(), {'resultado': RESULTADO_SEM}, format='json').status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_decidir_nao_e_unico_fallback(self):
        u = _user(
            'dec_only',
            perms=['view_analisefinanceiraproposta', 'decidir_analisefinanceiraproposta'],
        )
        self.client.force_authenticate(u)
        self.assertEqual(
            self.client.post(self._url_post(), {'resultado': RESULTADO_SEM}, format='json').status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_ver_nao_registra(self):
        self.client.force_authenticate(self.ver_only)
        self.assertEqual(self.client.get(self._url_list()).status_code, status.HTTP_200_OK)
        self.assertEqual(
            self.client.post(self._url_post(), {'resultado': RESULTADO_SEM}, format='json').status_code,
            status.HTTP_403_FORBIDDEN,
        )

    @patch('urllib.request.urlopen')
    @patch('apps.cadastros.consulta_externa._get_json')
    def test_post_sem_http_externo(self, mock_json, mock_urlopen):
        self.client.force_authenticate(self.fin)
        r = self.client.post(
            self._url_post(),
            {
                'resultado': RESULTADO_COM,
                'quantidade_informada': 3,
                'ufs_informadas': ['MG'],
                'cartorios_informados': '1º Ofício',
                'observacao': 'Conferido no portal',
            },
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(r.data['tipo'], 'PROTESTO_MANUAL')
        self.assertEqual(r.data['provider'], PROVIDER)
        self.assertIsNone(r.data['custo_consulta'])
        self.assertTrue(r.data['resultado_normalizado']['registro_manual'])
        mock_json.assert_not_called()
        mock_urlopen.assert_not_called()

    def test_historico_ordenado_e_sem_mistura(self):
        self.client.force_authenticate(self.fin)
        ConsultaExternaAnaliseFinanceira.objects.create(
            analise_financeira=self.analise,
            tipo=ConsultaExternaAnaliseFinanceira.Tipo.CADASTRAL,
            status=ConsultaExternaAnaliseFinanceira.Status.CONCLUIDA,
        )
        a = self.client.post(self._url_post(), {'resultado': RESULTADO_SEM}, format='json').data
        b = self.client.post(
            self._url_post(),
            {
                'resultado': RESULTADO_COM,
                'quantidade_informada': 1,
                'registro_anterior_id': a['id'],
                'motivo_correcao': 'Atualização após nova consulta',
            },
            format='json',
        ).data
        r = self.client.get(self._url_list())
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        results = r.data['results'] if isinstance(r.data, dict) and 'results' in r.data else r.data
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['id'], b['id'])
        self.assertEqual(results[1]['id'], a['id'])
        self.assertTrue(all(item['tipo'] == 'PROTESTO_MANUAL' for item in results))

    def test_sem_put_patch_delete(self):
        self.client.force_authenticate(self.fin)
        criado = self.client.post(self._url_post(), {'resultado': RESULTADO_SEM}, format='json').data
        detail = f"{self._url_list()}{criado['id']}/"
        self.assertEqual(self.client.put(detail, {'resultado': RESULTADO_COM}, format='json').status_code, 404)
        self.assertEqual(self.client.patch(detail, {'resultado': RESULTADO_COM}, format='json').status_code, 404)
        self.assertEqual(self.client.delete(detail).status_code, 404)

    def test_permissoes_no_serializer_analise(self):
        self.client.force_authenticate(self.fin)
        r = self.client.get(f'/api/analises-financeiras/{self.analise.pk}/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertTrue(r.data['permissoes']['pode_registrar_protesto_manual'])
        self.assertTrue(r.data['permissoes']['pode_ver_protesto_manual'])


class ProtestoManualImpactoZeroTests(TestCase):
    def test_indicadores_e_guard_sem_diff_de_import(self):
        ind = Path(__file__).resolve().parents[1] / 'analise_financeira_indicadores.py'
        conv = Path(__file__).resolve().parents[1] / 'converter_proposta_pedido.py'
        for path in (ind, conv):
            src = path.read_text(encoding='utf-8').lower()
            self.assertNotIn('protesto_manual', src)
            self.assertNotIn('pesquisaprotesto', src)
            self.assertNotIn('apps.certificados', src)
