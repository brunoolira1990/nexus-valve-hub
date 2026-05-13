from django.test import TestCase

from apps.produtos.descricao_norm import normalizar_descricao_produto
from apps.produtos.sorting import (
    natural_codigo_completo_key,
    natural_codigo_figura_key,
    schedule_ordenacao_tuple,
)


class SortingDescricaoTests(TestCase):
    def test_natural_codigo_figura_ordem(self):
        cods = ['0101', '0005', '0100L', '0100', '2036BE06', '6119', '6050', '0099']
        self.assertEqual(
            sorted(cods, key=natural_codigo_figura_key),
            [
                '0005',
                '0099',
                '0100',
                '0100L',
                '0101',
                '2036BE06',
                '6050',
                '6119',
            ],
        )

    def test_natural_codigo_completo_segmentos(self):
        cods = ['068840.17', '068840.09', '068840.12', '0075OD.13', '0029BSP.04']
        self.assertEqual(
            sorted(cods, key=natural_codigo_completo_key),
            [
                '0029BSP.04',
                '0075OD.13',
                '068840.09',
                '068840.12',
                '068840.17',
            ],
        )

    def test_schedule_tuple_prioridade_tecnica(self):
        rows = [
            schedule_ordenacao_tuple(ordem=None, codigo_schedule='80', codigo='80'),
            schedule_ordenacao_tuple(ordem=None, codigo_schedule='40', codigo='40'),
            schedule_ordenacao_tuple(ordem=None, codigo_schedule='STD', codigo='STD'),
            schedule_ordenacao_tuple(ordem=None, codigo_schedule='XS', codigo='XS'),
        ]
        sorted_rows = sorted(rows)
        # Ordem na lista técnica: ... 40, 40S, STD, 60, 80, 80S, XS ...
        self.assertEqual(sorted_rows[0][2], '40')
        self.assertEqual(sorted_rows[1][2], 'STD')
        self.assertEqual(sorted_rows[2][2], '80')
        self.assertEqual(sorted_rows[3][2], 'XS')

    def test_normalizar_descricao_sem_acento(self):
        self.assertEqual(
            normalizar_descricao_produto('  Válvula  Aço  3/4"  '),
            'VALVULA ACO 3/4"',
        )
        self.assertEqual(
            normalizar_descricao_produto('LUVA 3000# BSP 1/2"'),
            'LUVA 3000# BSP 1/2"',
        )
