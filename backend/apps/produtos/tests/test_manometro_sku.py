from __future__ import annotations

import threading
from decimal import Decimal

from django.db import close_old_connections, transaction
from django.test import TestCase, TransactionTestCase

from apps.produtos.models import (
    FamiliaProduto,
    Polegada,
    Produto,
    ProdutoManometroSkuSequencia,
    RoscaConexao,
)
from apps.produtos.serializers import PreviewCodigoSerializer, ProdutoSerializer


class ManometroSkuBaseTests(TestCase):
    def setUp(self):
        self.polegada_half = Polegada.objects.create(
            id=910001,
            tipo_medida=Polegada.TipoMedida.NPS,
            codigo='04',
            codigo_oficial='04',
            descricao='1/2"',
            valor_decimal=Decimal('0.5'),
        )
        self.polegada_three_quarter = Polegada.objects.create(
            id=910002,
            tipo_medida=Polegada.TipoMedida.NPS,
            codigo='06',
            codigo_oficial='06',
            descricao='3/4"',
            valor_decimal=Decimal('0.75'),
        )
        self.rosca_bsp, _ = RoscaConexao.objects.get_or_create(codigo='', defaults={'id': 910001, 'descricao': 'BSP padrão'})
        self.rosca_npt, _ = RoscaConexao.objects.get_or_create(codigo='N', defaults={'id': 910002, 'descricao': 'NPT'})
        self.familia = FamiliaProduto.objects.create(
            id=910001,
            codigo_figura='9920',
            descricao_base='MANOMETRO 100MM INOX',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_ROSCA_POLEGADA,
            tipo_dimensional=FamiliaProduto.TipoDimensional.MANOMETRO,
        )

    def produto_serializer(self, *, rosca, polegada, escala='0 A 4', fluido='AR'):
        serializer = ProdutoSerializer(
            data={
                'modo_codigo': Produto.ModoCodigo.INTERNO,
                'familia_id': self.familia.id,
                'rosca_conexao_id': rosca.id,
                'polegada_principal_ref_id': polegada.id,
                'descricao': f'MANOMETRO {escala} {fluido}',
                'dimensoes_json': {
                    'escala': escala,
                    'unidade_escala': 'BAR',
                    'fluido': fluido,
                },
                'preco_custo': '0',
                'preco_venda': '0',
                'estoque_minimo': '0',
            },
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        return serializer

    def test_base_sequencia_por_grupo_e_atributos_nao_codificados(self):
        primeiro = self.produto_serializer(rosca=self.rosca_bsp, polegada=self.polegada_half, escala='0 A 4').save()
        segundo = self.produto_serializer(rosca=self.rosca_bsp, polegada=self.polegada_half, escala='0 A 16').save()
        terceiro = self.produto_serializer(rosca=self.rosca_bsp, polegada=self.polegada_half, escala='0 A 25', fluido='GLICERINA').save()
        outro_grupo = self.produto_serializer(rosca=self.rosca_bsp, polegada=self.polegada_three_quarter).save()
        npt = self.produto_serializer(rosca=self.rosca_npt, polegada=self.polegada_half).save()

        self.assertEqual(primeiro.codigo_completo, '9920.04')
        self.assertEqual(segundo.codigo_completo, '9920.04.01')
        self.assertEqual(terceiro.codigo_completo, '9920.04.02')
        self.assertEqual(outro_grupo.codigo_completo, '9920.06')
        self.assertEqual(npt.codigo_completo, '9920N.04')

    def test_preview_sugere_sem_consumir_contador(self):
        primeiro = self.produto_serializer(rosca=self.rosca_npt, polegada=self.polegada_half).save()
        seq_antes = ProdutoManometroSkuSequencia.objects.get(codigo_base='9920N.04').proximo_numero
        preview = PreviewCodigoSerializer(
            data={
                'familia_id': self.familia.id,
                'rosca_conexao_id': self.rosca_npt.id,
                'polegada_principal_ref_id': self.polegada_half.id,
                'dimensoes_json': {'escala': '0 A 16', 'unidade_escala': 'BAR'},
            },
        )
        self.assertTrue(preview.is_valid(), preview.errors)
        self.assertEqual(preview.validated_data['_codigo'], '9920N.04.01')
        self.assertEqual(preview.validated_data['_codigo_base'], '9920N.04')
        self.assertTrue(preview.validated_data['_sequencia_tecnica'])
        self.assertEqual(
            ProdutoManometroSkuSequencia.objects.get(codigo_base='9920N.04').proximo_numero,
            seq_antes,
        )
        self.assertEqual(primeiro.codigo_completo, '9920N.04')

    def test_edicao_tecnica_preserva_codigo_e_estrutural_e_bloqueada(self):
        produto = self.produto_serializer(rosca=self.rosca_npt, polegada=self.polegada_half).save()
        codigo = produto.codigo_completo
        produto.dimensoes_json = {'escala': '0 A 16', 'unidade_escala': 'BAR', 'fluido': 'GLICERINA'}
        produto.save()
        self.assertEqual(Produto.objects.get(pk=produto.pk).codigo_completo, codigo)

        serializer = ProdutoSerializer(
            produto,
            data={'rosca_conexao_id': self.rosca_bsp.id},
            partial=True,
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('identidade estrutural', str(serializer.errors).lower())


class ManometroSkuConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.polegada = Polegada.objects.create(
            id=920001,
            tipo_medida=Polegada.TipoMedida.NPS,
            codigo='04',
            codigo_oficial='04',
            descricao='1/2"',
            valor_decimal=Decimal('0.5'),
        )
        self.rosca = RoscaConexao.objects.create(id=920001, codigo='N2', descricao='NPT')
        self.familia = FamiliaProduto.objects.create(
            id=920001,
            codigo_figura='9930',
            descricao_base='MANOMETRO CONCORRENCIA',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_ROSCA_POLEGADA,
            tipo_dimensional=FamiliaProduto.TipoDimensional.MANOMETRO,
        )

    def test_preview_simultaneo_nao_cria_linha(self):
        barrier = threading.Barrier(2)
        resultados = []
        erros = []

        def worker():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                preview = PreviewCodigoSerializer(
                    data={
                        'familia_id': self.familia.id,
                        'rosca_conexao_id': self.rosca.id,
                        'polegada_principal_ref_id': self.polegada.id,
                    },
                )
                if not preview.is_valid():
                    erros.append(preview.errors)
                else:
                    resultados.append(preview.validated_data['_codigo'])
            except Exception as exc:  # noqa: BLE001
                erros.append(repr(exc))
            finally:
                close_old_connections()

        threads = [threading.Thread(target=worker), threading.Thread(target=worker)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
        self.assertFalse(erros, erros)
        self.assertEqual(resultados, ['9930N2.04', '9930N2.04'])
        self.assertFalse(ProdutoManometroSkuSequencia.objects.exists())

    def test_rollback_de_criacao_nao_consumo_sequencia(self):
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                produto = Produto(
                    modo_codigo=Produto.ModoCodigo.INTERNO,
                    familia_id=self.familia.id,
                    rosca_conexao_id=self.rosca.id,
                    polegada_principal_ref_id=self.polegada.id,
                    descricao='MANOMETRO ROLLBACK',
                    dimensoes_json={'escala': '0 A 4', 'unidade_escala': 'BAR'},
                )
                produto.save()
                self.assertEqual(produto.codigo_completo, '9930N2.04')
                raise RuntimeError('rollback de teste')
        self.assertFalse(Produto.objects.exists())
        self.assertFalse(ProdutoManometroSkuSequencia.objects.exists())
        produto = Produto(
            modo_codigo=Produto.ModoCodigo.INTERNO,
            familia_id=self.familia.id,
            rosca_conexao_id=self.rosca.id,
            polegada_principal_ref_id=self.polegada.id,
            descricao='MANOMETRO APOS ROLLBACK',
            dimensoes_json={'escala': '0 A 4', 'unidade_escala': 'BAR'},
        )
        produto.save()
        self.assertEqual(produto.codigo_completo, '9930N2.04')

    def test_duas_criacoes_concorrentes_recebem_codigos_distintos(self):
        preview = PreviewCodigoSerializer(
            data={
                'familia_id': self.familia.id,
                'rosca_conexao_id': self.rosca.id,
                'polegada_principal_ref_id': self.polegada.id,
            },
        )
        self.assertTrue(preview.is_valid(), preview.errors)
        self.assertEqual(preview.validated_data['_codigo'], '9930N2.04')
        barrier = threading.Barrier(2)
        resultados = []
        erros = []

        def worker(escala):
            close_old_connections()
            try:
                produto = Produto(
                    modo_codigo=Produto.ModoCodigo.INTERNO,
                    familia_id=self.familia.id,
                    rosca_conexao_id=self.rosca.id,
                    polegada_principal_ref_id=self.polegada.id,
                    descricao=f'MANOMETRO {escala}',
                    dimensoes_json={'escala': escala, 'unidade_escala': 'BAR'},
                )
                barrier.wait(timeout=10)
                produto.save()
                resultados.append(produto.codigo_completo)
            except Exception as exc:  # noqa: BLE001 - o teste deve capturar exceções concorrentes
                erros.append(repr(exc))
            finally:
                close_old_connections()

        threads = [
            threading.Thread(target=worker, args=('0 A 4',)),
            threading.Thread(target=worker, args=('0 A 16',)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)

        self.assertFalse(erros, erros)
        self.assertEqual(len(resultados), 2)
        self.assertEqual(len(set(resultados)), 2)
        self.assertIn('9930N2.04', resultados)
        self.assertIn('9930N2.04.01', resultados)
        self.assertEqual(Produto.objects.filter(codigo_completo__in=resultados).count(), 2)
        self.assertEqual(
            ProdutoManometroSkuSequencia.objects.get(codigo_base='9930N2.04').proximo_numero,
            2,
        )
