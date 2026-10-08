"""Testes — geração automática de codigo_figura (ERP 4.0.14.x)."""

from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.test import TransactionTestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase, APIClient

from apps.produtos.codigo_produto import montar_codigo_interno
from apps.produtos.familia_codigo import (
    ENV_POLITICA,
    FamiliaCodigoConfigError,
    FamiliaCodigoEsgotadoError,
    MAX_CODIGO_FIGURA_AUTO,
    PoliticaPrefixoCodigoFigura,
    calcular_proximo_numero_inicial,
    classificar_codigo_figura_contextual,
    codigo_figura_valido,
    piso_contador_para_politica,
    prefixos_globalmente_ocupados,
    prefixos_numericos_ocupados,
    prefixos_produtos_ocupados,
    recalibrar_proximo_numero_sequencial,
    reservar_codigo_figura,
    resolver_config_politica_codigo_figura,
    template_acrescenta_od,
)
from apps.produtos.familia_duplicidade import (
    INT32_MAX,
    INT32_MIN,
    advisory_lock_keys_para_par,
    chave_descricao_duplicidade_familia,
)
from apps.produtos.models import FamiliaProduto, FamiliaProdutoCodigoSequencia, Polegada, Produto


def _payload_familia(**overrides):
    base = {
        'descricao_base': 'FAMILIA TESTE AUTO',
        'tipo_regra_codigo': FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        'tipo_dimensional': FamiliaProduto.TipoDimensional.SIMPLES,
        'categoria_produto': FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
        'separador_base_medidas': '.',
        'ativo': True,
    }
    base.update(overrides)
    return base


def _familia_min(codigo: str, **kwargs):
    return FamiliaProduto.objects.create(
        codigo_figura=codigo,
        descricao_base=kwargs.pop('descricao_base', 'T'),
        tipo_regra_codigo=kwargs.pop(
            'tipo_regra_codigo',
            FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        ),
        **kwargs,
    )


class FamiliaCodigoPoliticaConfigTests(TransactionTestCase):
    @override_settings(DEBUG=True)
    def test_fallback_documentado_em_dev(self):
        with patch.dict(os.environ, {}, clear=True):
            if ENV_POLITICA in os.environ:
                del os.environ[ENV_POLITICA]
            cfg = resolver_config_politica_codigo_figura()
            self.assertEqual(cfg.politica, PoliticaPrefixoCodigoFigura.VALOR_COMPLETO)
            self.assertEqual(cfg.origem, 'fallback')
            self.assertIsNotNone(cfg.alerta_fallback)

    @override_settings(DEBUG=False)
    def test_producao_sem_env_bloqueia(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop(ENV_POLITICA, None)
            with patch('apps.produtos.familia_codigo.resolver_ambiente_app', return_value='producao'):
                cfg = resolver_config_politica_codigo_figura()
                self.assertIsNotNone(cfg.bloqueio_producao)
                with self.assertRaises(FamiliaCodigoConfigError):
                    reservar_codigo_figura()

    @override_settings(DEBUG=False)
    def test_producao_com_env_explicita_ok(self):
        with patch.dict(os.environ, {ENV_POLITICA: PoliticaPrefixoCodigoFigura.VALOR_COMPLETO}):
            with patch('apps.produtos.familia_codigo.resolver_ambiente_app', return_value='producao'):
                cfg = resolver_config_politica_codigo_figura()
                self.assertEqual(cfg.origem, 'explicita')
                self.assertIsNone(cfg.bloqueio_producao)


class FamiliaCodigoAutomaticoUnitTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        os.environ[ENV_POLITICA] = PoliticaPrefixoCodigoFigura.VALOR_COMPLETO

    def tearDown(self):
        os.environ.pop(ENV_POLITICA, None)

    def test_banco_vazio_recebe_0001(self):
        FamiliaProdutoCodigoSequencia.objects.update_or_create(pk=1, defaults={'proximo_numero': 52})
        self.assertEqual(reservar_codigo_figura(), '0001')

    def test_0001_ocupado_recebe_0002(self):
        _familia_min('0001')
        FamiliaProdutoCodigoSequencia.objects.update_or_create(pk=1, defaults={'proximo_numero': 99})
        self.assertEqual(reservar_codigo_figura(), '0002')

    def test_buraco_escolhe_menor_livre(self):
        _familia_min('0001')
        _familia_min('0003')
        FamiliaProdutoCodigoSequencia.objects.update_or_create(pk=1, defaults={'proximo_numero': 8000})
        self.assertEqual(reservar_codigo_figura(), '0002')

    def test_varios_ocupados_preenche_lacuna(self):
        for n in (1, 2, 4):
            _familia_min(f'{n:04d}')
        self.assertEqual(reservar_codigo_figura(), '0003')

    def test_criacao_manual_alta_nao_impede_lacuna_baixa(self):
        _familia_min('7500')
        FamiliaProdutoCodigoSequencia.objects.update_or_create(pk=1, defaults={'proximo_numero': 7500})
        self.assertEqual(reservar_codigo_figura(), '0001')

    def test_reserva_concorrente_postgresql(self):
        FamiliaProdutoCodigoSequencia.objects.update_or_create(pk=1, defaults={'proximo_numero': 8100})
        barrier = threading.Barrier(2)
        resultados: list[str] = []
        erros: list[Exception] = []

        def worker(suf: str):
            close_old_connections()
            try:
                barrier.wait(timeout=5)
                # Mesmo fluxo da API: reserva + INSERT sob a mesma TX (lock até commit).
                with transaction.atomic():
                    codigo = reservar_codigo_figura()
                    FamiliaProduto.objects.create(
                        codigo_figura=codigo,
                        descricao_base=f'CONC {suf}',
                        tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
                    )
                    resultados.append(codigo)
            except Exception as exc:  # pragma: no cover
                erros.append(exc)
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            for fut in [pool.submit(worker, 'A'), pool.submit(worker, 'B')]:
                fut.result()
        self.assertEqual(erros, [])
        self.assertEqual(len(set(resultados)), 2)
        self.assertEqual(sorted(resultados), ['0001', '0002'])

    def test_nunca_escolhe_0000(self):
        codigo = reservar_codigo_figura()
        self.assertEqual(len(codigo), 4)
        self.assertNotEqual(codigo, '0000')
        self.assertTrue(codigo.isdigit())

    def test_faixa_esgotada_quando_tudo_ocupado(self):
        FamiliaProdutoCodigoSequencia.objects.update_or_create(pk=1, defaults={'proximo_numero': 1})
        ocupados = set(range(1, 10000))
        with patch(
            'apps.produtos.familia_codigo.prefixos_globalmente_ocupados',
            return_value=ocupados,
        ), patch(
            'apps.produtos.familia_codigo.codigos_nnnn_ocupados',
            return_value={f'{n:04d}' for n in ocupados},
        ):
            with self.assertRaises(FamiliaCodigoEsgotadoError):
                reservar_codigo_figura()

    def test_marca_dagua_10000_nao_bloqueia_lacuna(self):
        """proximo_numero alto era bloqueio; com lacunas a busca recomeça em 0001."""
        FamiliaProdutoCodigoSequencia.objects.update_or_create(pk=1, defaults={'proximo_numero': 10000})
        self.assertEqual(reservar_codigo_figura(), '0001')

    @override_settings(FAMILIA_CODIGO_POLITICA_PREFIXO=PoliticaPrefixoCodigoFigura.VALOR_COMPLETO)
    def test_politica_b_6119od_nao_bloqueia_6119(self):
        os.environ[ENV_POLITICA] = PoliticaPrefixoCodigoFigura.VALOR_COMPLETO
        _familia_min('6119OD', tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_OD_MM_ESPESSURA)
        # Prefixo 6119 de produto/especial: sob VALOR_COMPLETO o NNNN 6119 ainda é livre,
        # mas a busca preenche lacunas — menor livre é 0001.
        self.assertEqual(reservar_codigo_figura(), '0001')
        # Ocupando 0001, o próximo ainda pode ser 6119 (OD especial não bloqueia NNNN).
        _familia_min('0001', descricao_base='T1')
        # Após 0001, ainda há buracos; forçar ocupação 2..6118 via patch local no próximo teste.

    @override_settings(FAMILIA_CODIGO_POLITICA_PREFIXO=PoliticaPrefixoCodigoFigura.VALOR_COMPLETO)
    def test_valor_completo_permite_nnnn_com_especial_od(self):
        os.environ[ENV_POLITICA] = PoliticaPrefixoCodigoFigura.VALOR_COMPLETO
        _familia_min('6119OD', tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_OD_MM_ESPESSURA)
        with patch(
            'apps.produtos.familia_codigo.prefixos_globalmente_ocupados',
            return_value=set(range(1, 6119)),
        ), patch(
            'apps.produtos.familia_codigo.codigos_nnnn_ocupados',
            return_value={f'{n:04d}' for n in range(1, 6119)},
        ):
            self.assertEqual(reservar_codigo_figura(), '6119')

    @override_settings(FAMILIA_CODIGO_POLITICA_PREFIXO=PoliticaPrefixoCodigoFigura.PREFIXO_GLOBAL_UNICIDADE)
    def test_politica_unicidade_6119od_bloqueia_6119(self):
        os.environ[ENV_POLITICA] = PoliticaPrefixoCodigoFigura.PREFIXO_GLOBAL_UNICIDADE
        _familia_min('6119OD', tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_OD_MM_ESPESSURA)
        with patch(
            'apps.produtos.familia_codigo.prefixos_globalmente_ocupados',
            return_value=set(range(1, 6120)),
        ):
            self.assertEqual(reservar_codigo_figura(), '6120')

    @override_settings(FAMILIA_CODIGO_POLITICA_PREFIXO=PoliticaPrefixoCodigoFigura.PREFIXO_GLOBAL_SEQUENCIAL)
    def test_politica_sequencial_piso_maior_prefixo(self):
        os.environ[ENV_POLITICA] = PoliticaPrefixoCodigoFigura.PREFIXO_GLOBAL_SEQUENCIAL
        _familia_min('9000OD', tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_OD_MM_ESPESSURA)
        FamiliaProdutoCodigoSequencia.objects.update_or_create(pk=1, defaults={'proximo_numero': 100})
        self.assertEqual(reservar_codigo_figura(), '9001')

    def test_recalibrar_sequencial_nunca_reduz(self):
        self.assertEqual(
            recalibrar_proximo_numero_sequencial(
                contador_atual=9500,
                politica=PoliticaPrefixoCodigoFigura.PREFIXO_GLOBAL_SEQUENCIAL,
            ),
            9500,
        )

    def test_piso_politicas(self):
        _familia_min('9000OD', tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_OD_MM_ESPESSURA)
        _familia_min('0199')
        self.assertEqual(
            piso_contador_para_politica(PoliticaPrefixoCodigoFigura.VALOR_COMPLETO),
            1,
        )
        self.assertEqual(
            piso_contador_para_politica(PoliticaPrefixoCodigoFigura.PREFIXO_GLOBAL_UNICIDADE),
            1,
        )
        self.assertEqual(
            piso_contador_para_politica(PoliticaPrefixoCodigoFigura.PREFIXO_GLOBAL_SEQUENCIAL),
            9001,
        )


class FamiliaCodigoAutomaticoApiTests(APITestCase):
    def setUp(self):
        os.environ[ENV_POLITICA] = PoliticaPrefixoCodigoFigura.VALOR_COMPLETO
        user_model = __import__('django.contrib.auth', fromlist=['get_user_model']).get_user_model()
        self.user = user_model.objects.create_user(username='fam_auto', password='x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        FamiliaProdutoCodigoSequencia.objects.update_or_create(pk=1, defaults={'proximo_numero': 7000})
        self.url = reverse('familiaproduto-list')

    def tearDown(self):
        os.environ.pop(ENV_POLITICA, None)

    def test_criar_sem_codigo_recebe_automatico(self):
        """Fallback legado: sem modo_codigo e sem código → AUTOMATICO."""
        resp = self.client.post(self.url, _payload_familia(), format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['codigo_figura'], '0001')

    def test_post_automatico_explicito_sem_codigo(self):
        resp = self.client.post(
            self.url,
            _payload_familia(modo_codigo='AUTOMATICO'),
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['codigo_figura'], '0001')
        self.assertNotIn('modo_codigo', resp.data)

    def test_post_automatico_ignora_codigo_enviado(self):
        resp = self.client.post(
            self.url,
            _payload_familia(modo_codigo='AUTOMATICO', codigo_figura='6119OD'),
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['codigo_figura'], '0001')

    def test_post_manual_nnnn(self):
        resp = self.client.post(
            self.url,
            _payload_familia(modo_codigo='MANUAL', codigo_figura='7500'),
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['codigo_figura'], '7500')
        seq = FamiliaProdutoCodigoSequencia.objects.get(pk=1)
        self.assertEqual(seq.proximo_numero, 7000)

    def test_post_manual_especial_6119od(self):
        resp = self.client.post(
            self.url,
            _payload_familia(
                modo_codigo='MANUAL',
                codigo_figura='6119OD',
                tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_OD_MM_ESPESSURA,
            ),
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['codigo_figura'], '6119OD')
        seq = FamiliaProdutoCodigoSequencia.objects.get(pk=1)
        self.assertEqual(seq.proximo_numero, 7000)

    def test_post_manual_sem_codigo(self):
        resp = self.client.post(
            self.url,
            _payload_familia(modo_codigo='MANUAL'),
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('codigo_figura', resp.data)

    def test_post_manual_duplicado(self):
        _familia_min('6119OD', tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_OD_MM_ESPESSURA)
        resp = self.client.post(
            self.url,
            _payload_familia(
                modo_codigo='MANUAL',
                codigo_figura='6119OD',
                tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_OD_MM_ESPESSURA,
            ),
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Já existe', str(resp.data['codigo_figura']))
        self.assertNotIn('IntegrityError', str(resp.data))

    def test_nnnn_manual_seguido_de_automatico(self):
        resp_m = self.client.post(
            self.url,
            _payload_familia(modo_codigo='MANUAL', codigo_figura='7000'),
            format='json',
        )
        self.assertEqual(resp_m.status_code, status.HTTP_201_CREATED)
        resp_a = self.client.post(
            self.url,
            _payload_familia(modo_codigo='AUTOMATICO', descricao_base='AUTO APOS MANUAL'),
            format='json',
        )
        self.assertEqual(resp_a.status_code, status.HTTP_201_CREATED)
        # Lacuna: menor livre a partir de 0001 (7000 já ocupado manualmente).
        self.assertEqual(resp_a.data['codigo_figura'], '0001')

    def test_especial_manual_nao_incrementa_contador(self):
        antes = FamiliaProdutoCodigoSequencia.objects.get(pk=1).proximo_numero
        resp = self.client.post(
            self.url,
            _payload_familia(
                modo_codigo='MANUAL',
                codigo_figura='0075OD',
                tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_OD_MM_ESPESSURA,
            ),
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            FamiliaProdutoCodigoSequencia.objects.get(pk=1).proximo_numero,
            antes,
        )

    def test_codigo_sem_modo_rejeitado(self):
        resp = self.client.post(
            self.url,
            _payload_familia(codigo_figura='8800'),
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('modo_codigo', resp.data)

    def test_editar_preserva_codigo(self):
        create = self.client.post(
            self.url,
            _payload_familia(modo_codigo='AUTOMATICO'),
            format='json',
        )
        fam_id = create.data['id']
        codigo = create.data['codigo_figura']
        patch = self.client.patch(
            reverse('familiaproduto-detail', args=[fam_id]),
            {'descricao_base': 'NOVA DESC', 'codigo_figura': '9999'},
            format='json',
        )
        self.assertEqual(patch.data['codigo_figura'], codigo)

    def test_put_preserva_codigo(self):
        create = self.client.post(
            self.url,
            _payload_familia(modo_codigo='MANUAL', codigo_figura='7600'),
            format='json',
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        fam_id = create.data['id']
        detail = reverse('familiaproduto-detail', args=[fam_id])
        put = self.client.put(
            detail,
            _payload_familia(
                descricao_base='PUT DESC',
                codigo_figura='9999',
                tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
                tipo_dimensional=FamiliaProduto.TipoDimensional.SIMPLES,
            ),
            format='json',
        )
        self.assertEqual(put.status_code, status.HTTP_200_OK)
        self.assertEqual(put.data['codigo_figura'], '7600')
        self.assertEqual(FamiliaProduto.objects.get(pk=fam_id).codigo_figura, '7600')

    def test_manual_ocupado_api_pula(self):
        _familia_min('0001')
        FamiliaProdutoCodigoSequencia.objects.filter(pk=1).update(proximo_numero=7000)
        resp = self.client.post(
            self.url,
            _payload_familia(modo_codigo='AUTOMATICO', descricao_base='AUTO'),
            format='json',
        )
        self.assertEqual(resp.data['codigo_figura'], '0002')

    def test_faixa_esgotada_retorna_400_amigavel(self):
        ocupados = set(range(1, 10000))
        with patch(
            'apps.produtos.familia_codigo.prefixos_globalmente_ocupados',
            return_value=ocupados,
        ), patch(
            'apps.produtos.familia_codigo.codigos_nnnn_ocupados',
            return_value={f'{n:04d}' for n in ocupados},
        ):
            resp = self.client.post(
                self.url,
                _payload_familia(modo_codigo='AUTOMATICO'),
                format='json',
            )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('esgotada', str(resp.data).lower())

    def test_produto_vinculado_formacao_codigo_intacta(self):
        Polegada.objects.create(
            tipo_medida=Polegada.TipoMedida.NPS,
            codigo='05',
            codigo_oficial='05',
            descricao='3/4"',
            valor_decimal=Decimal('0.75'),
        )
        create = self.client.post(
            self.url,
            _payload_familia(
                modo_codigo='MANUAL',
                codigo_figura='7700',
                tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
                tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
            ),
            format='json',
        )
        familia = FamiliaProduto.objects.get(pk=create.data['id'])
        pol = Polegada.objects.get(codigo='05')
        cod = montar_codigo_interno(
            familia,
            rosca=None,
            schedule=None,
            polegada_principal=pol,
            polegada_secundaria=None,
        )
        self.assertEqual(cod, '7700.05')


class FamiliaCodigoNormalizacaoManualTests(APITestCase):
    """Código manual é normalizado (strip + upper), não salvo byte a byte."""

    def setUp(self):
        os.environ[ENV_POLITICA] = PoliticaPrefixoCodigoFigura.VALOR_COMPLETO
        user_model = __import__('django.contrib.auth', fromlist=['get_user_model']).get_user_model()
        self.user = user_model.objects.create_user(username='fam_norm', password='x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        FamiliaProdutoCodigoSequencia.objects.update_or_create(pk=1, defaults={'proximo_numero': 7100})
        self.url = reverse('familiaproduto-list')

    def tearDown(self):
        os.environ.pop(ENV_POLITICA, None)

    def test_trim_e_maiusculas(self):
        resp = self.client.post(
            self.url,
            _payload_familia(modo_codigo='MANUAL', codigo_figura='  6119od  '),
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['codigo_figura'], '6119OD')

    def test_vazio_apos_trim_rejeitado(self):
        resp = self.client.post(
            self.url,
            _payload_familia(modo_codigo='MANUAL', codigo_figura='   '),
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('codigo_figura', resp.data)

    def test_limite_32_caracteres(self):
        ok = self.client.post(
            self.url,
            _payload_familia(modo_codigo='MANUAL', codigo_figura='A' * 32),
            format='json',
        )
        self.assertEqual(ok.status_code, status.HTTP_201_CREATED)
        bad = self.client.post(
            self.url,
            _payload_familia(modo_codigo='MANUAL', codigo_figura='B' * 33),
            format='json',
        )
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('32', str(bad.data['codigo_figura']))

    def test_duplicidade_apos_normalizacao(self):
        self.client.post(
            self.url,
            _payload_familia(modo_codigo='MANUAL', codigo_figura='7120XY'),
            format='json',
        )
        dup = self.client.post(
            self.url,
            _payload_familia(modo_codigo='MANUAL', codigo_figura=' 7120xy '),
            format='json',
        )
        self.assertEqual(dup.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Já existe', str(dup.data['codigo_figura']))

    def test_quebra_de_linha_rejeitada(self):
        resp = self.client.post(
            self.url,
            _payload_familia(modo_codigo='MANUAL', codigo_figura='6119\nOD'),
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('controle', str(resp.data['codigo_figura']).lower())

    def test_tab_interna_rejeitada(self):
        resp = self.client.post(
            self.url,
            _payload_familia(modo_codigo='MANUAL', codigo_figura='6119\tOD'),
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('controle', str(resp.data['codigo_figura']).lower())


class FamiliaCodigoManualConcorrenciaTests(TransactionTestCase):
    """Concorrência real com conexões PostgreSQL independentes (não sequencial)."""

    reset_sequences = True

    def setUp(self):
        os.environ[ENV_POLITICA] = PoliticaPrefixoCodigoFigura.VALOR_COMPLETO
        FamiliaProdutoCodigoSequencia.objects.update_or_create(pk=1, defaults={'proximo_numero': 8200})
        user_model = __import__('django.contrib.auth', fromlist=['get_user_model']).get_user_model()
        self.user = user_model.objects.create_user(username='fam_conc', password='x')

    def tearDown(self):
        os.environ.pop(ENV_POLITICA, None)

    def test_concorrencia_manual_e_automatico_mesmo_nnnn(self):
        barrier = threading.Barrier(2)
        statuses: list[tuple[str, int, object]] = []

        def worker(modo: str, payload: dict):
            close_old_connections()
            try:
                client = APIClient()
                client.force_authenticate(self.user)
                barrier.wait(timeout=5)
                resp = client.post(reverse('familiaproduto-list'), payload, format='json')
                statuses.append((modo, resp.status_code, resp.data))
            finally:
                connection.close()

        payload_manual = _payload_familia(
            modo_codigo='MANUAL',
            codigo_figura='8200',
            descricao_base='MANUAL CONC',
        )
        payload_auto = _payload_familia(
            modo_codigo='AUTOMATICO',
            descricao_base='AUTO CONC',
        )

        with ThreadPoolExecutor(max_workers=2) as pool:
            futs = [
                pool.submit(worker, 'MANUAL', payload_manual),
                pool.submit(worker, 'AUTO', payload_auto),
            ]
            for fut in futs:
                fut.result()

        self.assertEqual(len(statuses), 2)
        for modo, code, data in statuses:
            self.assertNotEqual(code, 500, f'{modo} não deve retornar HTTP 500: {data}')
            self.assertNotIn('IntegrityError', str(data))
            self.assertNotIn('traceback', str(data).lower())

        ok = [(m, c, d) for m, c, d in statuses if c == 201]
        fail = [(m, c, d) for m, c, d in statuses if c != 201]
        codigos_ok = [d.get('codigo_figura') for _, _, d in ok]
        self.assertEqual(len(set(codigos_ok)), len(codigos_ok))
        self.assertEqual(
            FamiliaProduto.objects.filter(codigo_figura='8200').count(),
            1 if '8200' in codigos_ok else 0,
        )
        # No máximo uma família com o NNNN disputado
        self.assertLessEqual(FamiliaProduto.objects.filter(codigo_figura='8200').count(), 1)

        auto = next(((c, d) for m, c, d in statuses if m == 'AUTO'), None)
        manual = next(((c, d) for m, c, d in statuses if m == 'MANUAL'), None)
        self.assertIsNotNone(auto)
        self.assertIsNotNone(manual)
        auto_code, auto_data = auto
        manual_code, manual_data = manual

        # Automático preenche lacuna (0001); manual disputa 8200 — códigos distintos.
        self.assertEqual(auto_code, 201, auto_data)
        self.assertEqual(auto_data['codigo_figura'], '0001')

        if manual_code == 201:
            self.assertEqual(manual_data['codigo_figura'], '8200')
        else:
            self.assertEqual(manual_code, 400)
            self.assertIn('Já existe', str(manual_data.get('codigo_figura', manual_data)))
        self.assertEqual(len(fail) + len(ok), 2)
        self.assertEqual(len(set(codigos_ok)), len(codigos_ok))


class FamiliaCodigoCompatibilidadeOrmTests(TransactionTestCase):
    def test_objects_create_com_codigo_manual(self):
        fam = FamiliaProduto.objects.create(
            codigo_figura='8301',
            descricao_base='ORM CREATE',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        )
        self.assertEqual(fam.codigo_figura, '8301')

    def test_update_or_create_com_codigo_manual(self):
        fam, created = FamiliaProduto.objects.update_or_create(
            codigo_figura='8302',
            defaults={
                'descricao_base': 'ORM UOC',
                'tipo_regra_codigo': FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
            },
        )
        self.assertTrue(created)
        self.assertEqual(fam.codigo_figura, '8302')
        fam2, created2 = FamiliaProduto.objects.update_or_create(
            codigo_figura='8302',
            defaults={'descricao_base': 'ORM UOC 2'},
        )
        self.assertFalse(created2)
        self.assertEqual(fam2.descricao_base, 'ORM UOC 2')


class FamiliaCodigoManualPoliticasTests(TransactionTestCase):
    """Código especial manual sob as três políticas — contador intacto; ocupação conforme política."""

    def setUp(self):
        FamiliaProdutoCodigoSequencia.objects.update_or_create(pk=1, defaults={'proximo_numero': 6119})

    def tearDown(self):
        os.environ.pop(ENV_POLITICA, None)

    def _client(self, username: str):
        user_model = __import__('django.contrib.auth', fromlist=['get_user_model']).get_user_model()
        user = user_model.objects.create_user(username=username, password='x')
        client = APIClient()
        client.force_authenticate(user)
        return client

    def test_valor_completo_especial_permite_nnnn_igual(self):
        os.environ[ENV_POLITICA] = PoliticaPrefixoCodigoFigura.VALOR_COMPLETO
        client = self._client('pol_vc')
        r = client.post(
            reverse('familiaproduto-list'),
            _payload_familia(
                modo_codigo='MANUAL',
                codigo_figura='6119OD',
                tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_OD_MM_ESPESSURA,
            ),
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        antes = FamiliaProdutoCodigoSequencia.objects.get(pk=1).proximo_numero
        self.assertEqual(antes, 6119)
        auto = client.post(
            reverse('familiaproduto-list'),
            _payload_familia(modo_codigo='AUTOMATICO', descricao_base='AUTO VC'),
            format='json',
        )
        self.assertEqual(auto.status_code, status.HTTP_201_CREATED)
        # Lacunas: menor livre é 0001; 6119 permanece disponível (VALOR_COMPLETO).
        self.assertEqual(auto.data['codigo_figura'], '0001')
        self.assertFalse(FamiliaProduto.objects.filter(codigo_figura='6119').exists())

    def test_unicidade_especial_impede_nnnn_igual(self):
        os.environ[ENV_POLITICA] = PoliticaPrefixoCodigoFigura.PREFIXO_GLOBAL_UNICIDADE
        client = self._client('pol_uni')
        r = client.post(
            reverse('familiaproduto-list'),
            _payload_familia(
                modo_codigo='MANUAL',
                codigo_figura='6119OD',
                tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_OD_MM_ESPESSURA,
            ),
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(FamiliaProdutoCodigoSequencia.objects.get(pk=1).proximo_numero, 6119)
        auto = client.post(
            reverse('familiaproduto-list'),
            _payload_familia(modo_codigo='AUTOMATICO', descricao_base='AUTO UNI'),
            format='json',
        )
        self.assertEqual(auto.status_code, status.HTTP_201_CREATED)
        self.assertNotEqual(auto.data['codigo_figura'], '6119')
        # Lacuna: menor livre é 0001 (6119 ocupado pelo especial).
        self.assertEqual(auto.data['codigo_figura'], '0001')

    def test_sequencial_especial_piso_minimo_e_nao_reduz_contador(self):
        os.environ[ENV_POLITICA] = PoliticaPrefixoCodigoFigura.PREFIXO_GLOBAL_SEQUENCIAL
        FamiliaProdutoCodigoSequencia.objects.filter(pk=1).update(proximo_numero=100)
        client = self._client('pol_seq')
        r = client.post(
            reverse('familiaproduto-list'),
            _payload_familia(
                modo_codigo='MANUAL',
                codigo_figura='9000OD',
                tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_OD_MM_ESPESSURA,
            ),
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        # Contador persistido não é reduzido nem incrementado pelo manual
        self.assertEqual(FamiliaProdutoCodigoSequencia.objects.get(pk=1).proximo_numero, 100)
        auto = client.post(
            reverse('familiaproduto-list'),
            _payload_familia(modo_codigo='AUTOMATICO', descricao_base='AUTO SEQ'),
            format='json',
        )
        self.assertEqual(auto.status_code, status.HTTP_201_CREATED)
        self.assertGreaterEqual(int(auto.data['codigo_figura']), 9001)
        self.assertEqual(auto.data['codigo_figura'], '9001')
        # Após reserva automática, contador não cai abaixo do piso
        self.assertGreaterEqual(
            FamiliaProdutoCodigoSequencia.objects.get(pk=1).proximo_numero,
            9002,
        )


class AuditarCodigoFiguraReadOnlyTests(TransactionTestCase):
    def test_auditoria_sem_tabela_sequencia(self):
        out = StringIO()
        with patch(
            'apps.produtos.management.commands.auditar_codigo_figura_familia._tabela_sequencia_existe',
            return_value=False,
        ):
            call_command('auditar_codigo_figura_familia', stdout=out)
        texto = out.getvalue()
        self.assertIn('somente leitura', texto.lower())
        self.assertIn('ainda não existe', texto.lower())
        self.assertIn('PREFIXO_GLOBAL_UNICIDADE', texto)
        self.assertIn('decisão do operador', texto.lower())
        self.assertIn('0028 NÃO necessária', texto)
        self.assertIn('técnicos manuais com sufixo', texto.lower())
        self.assertNotIn('Diagnóstico legado', texto)

    def test_auditoria_nao_reserva_nem_escreve_sequencia(self):
        with patch('apps.produtos.familia_codigo.reservar_codigo_figura') as mock_res:
            with patch.object(FamiliaProdutoCodigoSequencia.objects, 'create') as mock_seq_create:
                call_command('auditar_codigo_figura_familia', stdout=StringIO())
        mock_res.assert_not_called()
        mock_seq_create.assert_not_called()

    def test_calcular_proximo_sem_hardcode(self):
        _familia_min('8010')
        self.assertEqual(
            calcular_proximo_numero_inicial(politica=PoliticaPrefixoCodigoFigura.VALOR_COMPLETO),
            1,
        )


class FamiliaCodigoClassificacaoContextualTests(TransactionTestCase):
    """Sufixos são válidos conforme o template; MANUAL_FABRICANTE fora do prefixo."""

    def test_template_acrescenta_od_somente_regras_od(self):
        self.assertTrue(template_acrescenta_od(FamiliaProduto.TipoRegraCodigo.BASE_OD_MM_ESPESSURA))
        self.assertTrue(template_acrescenta_od(FamiliaProduto.TipoRegraCodigo.BASE_OD_POLEGADA_ESPESSURA))
        self.assertFalse(template_acrescenta_od(FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA))
        self.assertFalse(template_acrescenta_od(FamiliaProduto.TipoRegraCodigo.BASE_ROSCA_DUAS_POLEGADAS))

    def test_classifica_0023od_como_tecnico_valido(self):
        self.assertEqual(
            classificar_codigo_figura_contextual(
                codigo='0023OD',
                tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_ROSCA_DUAS_POLEGADAS,
            ),
            'TECNICO_SUFIXO_VALIDO',
        )

    def test_classifica_0075od_como_tecnico_valido(self):
        self.assertEqual(
            classificar_codigo_figura_contextual(
                codigo='0075OD',
                tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
            ),
            'TECNICO_SUFIXO_VALIDO',
        )

    def test_classifica_6119_como_nnnn(self):
        self.assertEqual(
            classificar_codigo_figura_contextual(
                codigo='6119',
                tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_OD_MM_ESPESSURA,
            ),
            'NNNN',
        )

    def test_classifica_6119od_com_template_od_como_possivel_repeticao(self):
        self.assertEqual(
            classificar_codigo_figura_contextual(
                codigo='6119OD',
                tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_OD_MM_ESPESSURA,
            ),
            'POSSIVEL_REPETICAO_TEMPLATE',
        )

    def test_classifica_manual_fabricante(self):
        self.assertEqual(
            classificar_codigo_figura_contextual(
                codigo='18900001-04DC',
                tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.MANUAL_FABRICANTE,
            ),
            'MANUAL_FABRICANTE',
        )

    def test_manual_fabricante_nao_ocupa_prefixo_figura(self):
        FamiliaProduto.objects.create(
            codigo_figura='18900001-04DC',
            descricao_base='FAB',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.MANUAL_FABRICANTE,
            tipo_dimensional=FamiliaProduto.TipoDimensional.MANUAL,
            categoria_produto=FamiliaProduto.CategoriaProduto.MANUAL_FABRICANTE,
        )
        _familia_min('0075OD', tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA)
        prefixos = prefixos_numericos_ocupados()
        self.assertIn(75, prefixos)
        self.assertNotIn(1890, prefixos)

    def test_auditoria_classifica_contexto_sem_legado_generico(self):
        _familia_min('0023OD', tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_ROSCA_DUAS_POLEGADAS)
        _familia_min('6119', tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_OD_MM_ESPESSURA)
        FamiliaProduto.objects.create(
            codigo_figura='18900001-04DC',
            descricao_base='FAB',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.MANUAL_FABRICANTE,
            tipo_dimensional=FamiliaProduto.TipoDimensional.MANUAL,
            categoria_produto=FamiliaProduto.CategoriaProduto.MANUAL_FABRICANTE,
        )
        out = StringIO()
        call_command('auditar_codigo_figura_familia', stdout=out)
        texto = out.getvalue()
        self.assertIn('0023OD', texto)
        self.assertIn('6119', texto)
        self.assertIn('18900001-04DC', texto)
        self.assertIn('Manual/fabricante', texto)
        self.assertNotIn('Diagnóstico legado', texto)
        self.assertIn('classe=TECNICO_SUFIXO_VALIDO', texto)
        self.assertIn('classe=NNNN', texto)
        self.assertIn('classe=MANUAL_FABRICANTE', texto)
        self.assertIn('técnicos manuais com sufixo', texto.lower())


def _erro_campo(data, chave: str):
    """DRF empacota valores de ValidationError em listas de ErrorDetail."""
    val = data.get(chave)
    if isinstance(val, (list, tuple)):
        return str(val[0]) if val else ''
    return '' if val is None else str(val)


class FamiliaDuplicidadeDescricaoModeloTests(APITestCase):
    """Duplicidade por descrição base + tipo_regra_codigo (sem migration)."""

    def setUp(self):
        os.environ[ENV_POLITICA] = PoliticaPrefixoCodigoFigura.PREFIXO_GLOBAL_UNICIDADE
        user_model = __import__('django.contrib.auth', fromlist=['get_user_model']).get_user_model()
        self.user = user_model.objects.create_user(username='dup_fam', password='x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        FamiliaProdutoCodigoSequencia.objects.update_or_create(pk=1, defaults={'proximo_numero': 9000})
        self.url = reverse('familiaproduto-list')

    def tearDown(self):
        os.environ.pop(ENV_POLITICA, None)

    def test_criar_nova_sem_duplicidade(self):
        resp = self.client.post(
            self.url,
            _payload_familia(modo_codigo='AUTOMATICO', descricao_base='CURVA 90 UNICA'),
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['codigo_figura'], '0001')

    def test_criar_mesma_descricao_mesmo_modelo(self):
        _familia_min(
            '0114',
            descricao_base='REDUCAO EXCENTRICA ACO CARBONO',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_SCHEDULE_DUAS_POLEGADAS,
        )
        antes = FamiliaProdutoCodigoSequencia.objects.get(pk=1).proximo_numero
        total_antes = FamiliaProduto.objects.count()
        resp = self.client.post(
            self.url,
            _payload_familia(
                modo_codigo='AUTOMATICO',
                descricao_base='REDUCAO EXCENTRICA ACO CARBONO',
                tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_SCHEDULE_DUAS_POLEGADAS,
            ),
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('0114', _erro_campo(resp.data, 'descricao_base'))
        self.assertIn('mesmo modelo', _erro_campo(resp.data, 'descricao_base').lower())
        self.assertEqual(_erro_campo(resp.data, 'familia_existente_codigo'), '0114')
        self.assertEqual(FamiliaProduto.objects.count(), total_antes)
        self.assertEqual(FamiliaProdutoCodigoSequencia.objects.get(pk=1).proximo_numero, antes)

    def test_ignora_maiusculas_minusculas(self):
        _familia_min(
            '0114',
            descricao_base='REDUCAO EXCENTRICA ACO CARBONO',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_SCHEDULE_DUAS_POLEGADAS,
        )
        resp = self.client.post(
            self.url,
            _payload_familia(
                modo_codigo='AUTOMATICO',
                descricao_base='reducao excentrica aco carbono',
                tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_SCHEDULE_DUAS_POLEGADAS,
            ),
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(_erro_campo(resp.data, 'familia_existente_codigo'), '0114')

    def test_ignora_espacos_externos_e_repetidos(self):
        _familia_min(
            '0114',
            descricao_base='REDUCAO EXCENTRICA ACO CARBONO',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_SCHEDULE_DUAS_POLEGADAS,
        )
        resp = self.client.post(
            self.url,
            _payload_familia(
                modo_codigo='AUTOMATICO',
                descricao_base='  REDUCAO   EXCENTRICA  ACO CARBONO  ',
                tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_SCHEDULE_DUAS_POLEGADAS,
            ),
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(_erro_campo(resp.data, 'familia_existente_codigo'), '0114')

    def test_mesma_descricao_modelo_diferente_permitido(self):
        _familia_min(
            '0114',
            descricao_base='REDUCAO EXCENTRICA ACO CARBONO',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_SCHEDULE_DUAS_POLEGADAS,
        )
        resp = self.client.post(
            self.url,
            _payload_familia(
                modo_codigo='AUTOMATICO',
                descricao_base='REDUCAO EXCENTRICA ACO CARBONO',
                tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
            ),
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_patch_proprio_sem_alteracao(self):
        fam = _familia_min(
            '0114',
            descricao_base='REDUCAO EXCENTRICA ACO CARBONO',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_SCHEDULE_DUAS_POLEGADAS,
        )
        url = reverse('familiaproduto-detail', args=[fam.id])
        resp = self.client.patch(
            url,
            {'descricao_base': 'REDUCAO EXCENTRICA ACO CARBONO'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['codigo_figura'], '0114')

    def test_patch_colisao_com_outra(self):
        a = _familia_min(
            '0114',
            descricao_base='REDUCAO EXCENTRICA ACO CARBONO',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_SCHEDULE_DUAS_POLEGADAS,
        )
        b = _familia_min(
            '9607',
            descricao_base='OUTRA DESC',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        )
        url = reverse('familiaproduto-detail', args=[b.id])
        resp = self.client.patch(
            url,
            {
                'descricao_base': 'REDUCAO EXCENTRICA ACO CARBONO',
                'tipo_regra_codigo': FamiliaProduto.TipoRegraCodigo.BASE_SCHEDULE_DUAS_POLEGADAS,
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(_erro_campo(resp.data, 'familia_existente_codigo'), '0114')
        b.refresh_from_db()
        self.assertEqual(b.descricao_base, 'OUTRA DESC')
        self.assertEqual(a.codigo_figura, '0114')

    def test_contador_inalterado_apos_bloqueio_automatico(self):
        _familia_min(
            '0114',
            descricao_base='DESC BLOQUEIO CONTADOR',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        )
        FamiliaProdutoCodigoSequencia.objects.update_or_create(pk=1, defaults={'proximo_numero': 9010})
        resp = self.client.post(
            self.url,
            _payload_familia(
                modo_codigo='AUTOMATICO',
                descricao_base='DESC BLOQUEIO CONTADOR',
                tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
            ),
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(FamiliaProdutoCodigoSequencia.objects.get(pk=1).proximo_numero, 9010)

    def test_manual_mesma_validacao_duplicidade(self):
        _familia_min(
            '0114',
            descricao_base='DESC MANUAL DUP',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        )
        resp = self.client.post(
            self.url,
            _payload_familia(
                modo_codigo='MANUAL',
                codigo_figura='8801',
                descricao_base='DESC MANUAL DUP',
                tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
            ),
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(_erro_campo(resp.data, 'familia_existente_codigo'), '0114')
        self.assertFalse(FamiliaProduto.objects.filter(codigo_figura='8801').exists())


class FamiliaDuplicidadeConcorrenciaTests(TransactionTestCase):
    """Corrida descrição+modelo com conexões PostgreSQL independentes."""

    reset_sequences = True

    def setUp(self):
        os.environ[ENV_POLITICA] = PoliticaPrefixoCodigoFigura.PREFIXO_GLOBAL_UNICIDADE
        user_model = __import__('django.contrib.auth', fromlist=['get_user_model']).get_user_model()
        self.user = user_model.objects.create_user(username='dup_conc', password='x')
        FamiliaProdutoCodigoSequencia.objects.update_or_create(pk=1, defaults={'proximo_numero': 9300})
        self.url = reverse('familiaproduto-list')

    def tearDown(self):
        os.environ.pop(ENV_POLITICA, None)

    def _post_parallel(self, payloads: list[dict]) -> list[tuple[int, object]]:
        barrier = threading.Barrier(len(payloads))
        results: list[tuple[int, object]] = []

        def worker(payload: dict):
            close_old_connections()
            try:
                client = APIClient()
                client.force_authenticate(self.user)
                barrier.wait(timeout=8)
                resp = client.post(self.url, payload, format='json')
                results.append((resp.status_code, resp.data))
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=len(payloads)) as pool:
            futs = [pool.submit(worker, p) for p in payloads]
            for fut in futs:
                fut.result(timeout=30)
        return results

    def test_duas_criacoes_automaticas_mesma_descricao_modelo(self):
        desc = 'CONC AUTO MESMO MODELO A'
        results = self._post_parallel(
            [
                _payload_familia(
                    modo_codigo='AUTOMATICO',
                    descricao_base=desc,
                    tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
                ),
                _payload_familia(
                    modo_codigo='AUTOMATICO',
                    descricao_base=desc,
                    tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
                ),
            ],
        )
        self.assertEqual(len(results), 2)
        for code, data in results:
            self.assertNotEqual(code, 500, data)
            self.assertNotIn('IntegrityError', str(data))
        oks = [d for c, d in results if c == 201]
        fails = [d for c, d in results if c == 400]
        self.assertEqual(len(oks), 1, results)
        self.assertEqual(len(fails), 1, results)
        self.assertIn('mesmo modelo', _erro_campo(fails[0], 'descricao_base').lower())
        self.assertEqual(
            FamiliaProduto.objects.filter(descricao_base=desc, tipo_regra_codigo='BASE_POLEGADA').count(),
            1,
        )
        # Marca d'água não reduz (max(9300, 0001+1) = 9300); um código foi reservado.
        self.assertEqual(FamiliaProdutoCodigoSequencia.objects.get(pk=1).proximo_numero, 9300)
        self.assertEqual(oks[0]['codigo_figura'], '0001')

    def test_duas_criacoes_mesma_descricao_modelos_diferentes(self):
        desc = 'CONC MESMA DESC MODELOS DIF'
        results = self._post_parallel(
            [
                _payload_familia(
                    modo_codigo='AUTOMATICO',
                    descricao_base=desc,
                    tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
                ),
                _payload_familia(
                    modo_codigo='AUTOMATICO',
                    descricao_base=desc,
                    tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_SCHEDULE_DUAS_POLEGADAS,
                ),
            ],
        )
        oks = [d for c, d in results if c == 201]
        self.assertEqual(len(oks), 2, results)
        self.assertEqual(
            FamiliaProduto.objects.filter(descricao_base=desc).count(),
            2,
        )

    def test_manual_concorrente_duplicado(self):
        desc = 'CONC MANUAL DUP DESC'
        results = self._post_parallel(
            [
                _payload_familia(
                    modo_codigo='MANUAL',
                    codigo_figura='930A',
                    descricao_base=desc,
                    tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
                ),
                _payload_familia(
                    modo_codigo='MANUAL',
                    codigo_figura='930B',
                    descricao_base=desc,
                    tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
                ),
            ],
        )
        oks = [(c, d) for c, d in results if c == 201]
        fails = [(c, d) for c, d in results if c == 400]
        self.assertEqual(len(oks), 1, results)
        self.assertEqual(len(fails), 1, results)
        self.assertEqual(
            FamiliaProduto.objects.filter(descricao_base=desc, tipo_regra_codigo='BASE_POLEGADA').count(),
            1,
        )
        # Contador automático intocado (ambos manuais).
        self.assertEqual(FamiliaProdutoCodigoSequencia.objects.get(pk=1).proximo_numero, 9300)

    def test_patch_concorrente_colisao(self):
        alvo = _familia_min(
            '93T1',
            descricao_base='CONC PATCH ALVO',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        )
        a = _familia_min(
            '93T2',
            descricao_base='CONC PATCH A',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        )
        b = _familia_min(
            '93T3',
            descricao_base='CONC PATCH B',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        )
        barrier = threading.Barrier(2)
        results: list[tuple[int, object]] = []

        def worker(fam_id: int):
            close_old_connections()
            try:
                client = APIClient()
                client.force_authenticate(self.user)
                barrier.wait(timeout=8)
                resp = client.patch(
                    reverse('familiaproduto-detail', args=[fam_id]),
                    {
                        'descricao_base': 'CONC PATCH ALVO',
                        'tipo_regra_codigo': FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
                    },
                    format='json',
                )
                results.append((resp.status_code, resp.data))
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futs = [pool.submit(worker, a.id), pool.submit(worker, b.id)]
            for fut in futs:
                fut.result(timeout=30)

        fails = [d for c, d in results if c == 400]
        self.assertGreaterEqual(len(fails), 1, results)
        for code, data in results:
            self.assertNotEqual(code, 500, data)
            self.assertNotIn('IntegrityError', str(data))
        # Alvo original permanece; no máximo um dos dois venceu? Ambos colidem com alvo → preferível 2x 400.
        self.assertEqual(
            FamiliaProduto.objects.filter(
                descricao_base='CONC PATCH ALVO',
                tipo_regra_codigo='BASE_POLEGADA',
            ).count(),
            1,
        )
        alvo.refresh_from_db()
        self.assertEqual(alvo.codigo_figura, '93T1')


class FamiliaAdvisoryLockKeysTests(TransactionTestCase):
    """Segurança/estabilidade das chaves pg_advisory_xact_lock."""

    def test_nao_usa_hash_nativo_python(self):
        import apps.produtos.familia_duplicidade as mod
        import inspect
        import re

        src = inspect.getsource(mod._advisory_lock_keys_from_normalized)
        self.assertIn('hashlib.sha256', src)
        # Remove docstring — só o corpo executável importa.
        body = re.sub(r'""".*?"""', '', src, flags=re.S)
        self.assertNotRegex(body, r'(?<![\w.])hash\(')

    def test_chaves_deterministicas_e_faixa_int32(self):
        import hashlib
        import subprocess
        import sys
        import ast

        desc = 'REDUCAO EXCENTRICA ACO CARBONO'
        tipo = 'BASE_SCHEDULE_DUAS_POLEGADAS'
        local = advisory_lock_keys_para_par(desc, tipo)
        self.assertIsNotNone(local)
        k1, k2 = local
        self.assertTrue(INT32_MIN <= k1 <= INT32_MAX)
        self.assertTrue(INT32_MIN <= k2 <= INT32_MAX)

        chave = chave_descricao_duplicidade_familia(desc)
        material = f'familia-dup|{tipo}|{chave}'.encode('utf-8')
        digest = hashlib.sha256(material).digest()
        expected = (
            int.from_bytes(digest[0:4], 'big', signed=True),
            int.from_bytes(digest[4:8], 'big', signed=True),
        )
        self.assertEqual(local, expected)

        # Outro processo Python (restart semântico): mesmos valores.
        code = (
            'import django, os; os.environ.setdefault("DJANGO_SETTINGS_MODULE","nexus_erp.settings"); '
            'django.setup(); '
            'from apps.produtos.familia_duplicidade import advisory_lock_keys_para_par; '
            f'print(advisory_lock_keys_para_par({desc!r}, {tipo!r}))'
        )
        proc = subprocess.run(
            [sys.executable, '-c', code],
            capture_output=True,
            text=True,
            check=True,
            cwd='/app',
        )
        remote = ast.literal_eval(proc.stdout.strip())
        self.assertEqual(remote, local)

        # Threads distintas: mesmos valores.
        barrier = threading.Barrier(2)
        outs: list[tuple[int, int]] = []

        def worker():
            barrier.wait(timeout=5)
            outs.append(advisory_lock_keys_para_par(desc, tipo))

        with ThreadPoolExecutor(max_workers=2) as pool:
            futs = [pool.submit(worker), pool.submit(worker)]
            for fut in futs:
                fut.result(timeout=10)
        self.assertEqual(outs[0], outs[1])
        self.assertEqual(outs[0], local)

    def test_pares_diferentes_nao_compartilham_lock(self):
        a = advisory_lock_keys_para_par(
            'PAR LOCK A',
            FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        )
        b = advisory_lock_keys_para_par(
            'PAR LOCK B',
            FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        )
        c = advisory_lock_keys_para_par(
            'PAR LOCK A',
            FamiliaProduto.TipoRegraCodigo.BASE_SCHEDULE_DUAS_POLEGADAS,
        )
        self.assertNotEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertNotEqual(b, c)


class FamiliaUpdateCruzadoAdvisoryTests(TransactionTestCase):
    """Updates cruzados: locks em ordem determinística — sem deadlock."""

    reset_sequences = True

    def setUp(self):
        os.environ[ENV_POLITICA] = PoliticaPrefixoCodigoFigura.PREFIXO_GLOBAL_UNICIDADE
        user_model = __import__('django.contrib.auth', fromlist=['get_user_model']).get_user_model()
        self.user = user_model.objects.create_user(username='dup_xlock', password='x')

    def tearDown(self):
        os.environ.pop(ENV_POLITICA, None)

    def test_updates_cruzados_sem_deadlock(self):
        a = _familia_min(
            '94XA',
            descricao_base='CRUZ LOCK A',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        )
        b = _familia_min(
            '94XB',
            descricao_base='CRUZ LOCK B',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_SCHEDULE_DUAS_POLEGADAS,
        )
        barrier = threading.Barrier(2)
        results: list[tuple[int, object]] = []

        def worker(fam_id: int, desc: str, tipo: str):
            close_old_connections()
            try:
                client = APIClient()
                client.force_authenticate(self.user)
                barrier.wait(timeout=8)
                resp = client.patch(
                    reverse('familiaproduto-detail', args=[fam_id]),
                    {'descricao_base': desc, 'tipo_regra_codigo': tipo},
                    format='json',
                )
                results.append((resp.status_code, resp.data))
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            # A → par de B; B → par de A (cruzado).
            futs = [
                pool.submit(
                    worker,
                    a.id,
                    'CRUZ LOCK B',
                    FamiliaProduto.TipoRegraCodigo.BASE_SCHEDULE_DUAS_POLEGADAS,
                ),
                pool.submit(
                    worker,
                    b.id,
                    'CRUZ LOCK A',
                    FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
                ),
            ]
            for fut in futs:
                fut.result(timeout=20)

        self.assertEqual(len(results), 2, results)
        for code, data in results:
            self.assertNotEqual(code, 500, data)
            self.assertNotIn('deadlock', str(data).lower())
            self.assertNotIn('IntegrityError', str(data))


class FamiliaMenorPrefixoLivreAcceptanceTests(TransactionTestCase):
    """Aceite: menor NNNN livre (família + produto + inativa)."""

    reset_sequences = True

    def setUp(self):
        os.environ[ENV_POLITICA] = PoliticaPrefixoCodigoFigura.PREFIXO_GLOBAL_UNICIDADE
        FamiliaProdutoCodigoSequencia.objects.update_or_create(pk=1, defaults={'proximo_numero': 5000})

    def tearDown(self):
        os.environ.pop(ENV_POLITICA, None)

    def test_0001_e_0003_ocupados_cria_0002(self):
        _familia_min('0001')
        _familia_min('0003')
        self.assertEqual(reservar_codigo_figura(), '0002')

    def test_prefixo_somente_produto_pula(self):
        _familia_min('0001')
        Produto.objects.create(
            modo_codigo=Produto.ModoCodigo.MANUAL,
            descricao='PROD PREFIXO 0002',
            codigo_completo='0002.99',
        )
        self.assertIn(2, prefixos_produtos_ocupados())
        self.assertIn(2, prefixos_globalmente_ocupados())
        self.assertEqual(reservar_codigo_figura(), '0003')

    def test_familia_inativa_nao_reutiliza(self):
        fam = _familia_min('0001')
        FamiliaProduto.objects.filter(pk=fam.pk).update(ativo=False)
        self.assertEqual(reservar_codigo_figura(), '0002')

    def test_codigo_fora_padrao_nao_quebra_busca(self):
        _familia_min('XYZ')
        self.assertEqual(reservar_codigo_figura(), '0001')

    def test_quatro_digitos_sempre(self):
        for esperado in ('0001', '0002', '0003'):
            with transaction.atomic():
                codigo = reservar_codigo_figura()
                FamiliaProduto.objects.create(
                    codigo_figura=codigo,
                    descricao_base=f'SEQ {esperado}',
                    tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
                )
            self.assertEqual(codigo, esperado)
            self.assertEqual(len(codigo), 4)
            self.assertTrue(codigo.isdigit())
            self.assertNotEqual(codigo, '0000')

    def test_familias_e_produtos_existentes_inalterados(self):
        fam = _familia_min('0812')
        prod = Produto.objects.create(
            modo_codigo=Produto.ModoCodigo.MANUAL,
            familia=fam,
            descricao='PROD EXISTENTE',
            codigo_completo='0812.01',
        )
        codigo_fam = fam.codigo_figura
        codigo_prod = prod.codigo_completo
        self.assertEqual(reservar_codigo_figura(), '0001')
        fam.refresh_from_db()
        prod.refresh_from_db()
        self.assertEqual(fam.codigo_figura, codigo_fam)
        self.assertEqual(prod.codigo_completo, codigo_prod)
