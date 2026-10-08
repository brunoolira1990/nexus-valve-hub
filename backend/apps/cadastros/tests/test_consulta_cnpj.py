"""Testes da consulta cadastral básica por CNPJ (sem IE)."""

from __future__ import annotations

from unittest.mock import patch

from django.test import SimpleTestCase

from apps.cadastros.consulta_cnpj import AVISO_IE_FONTE_ATUAL, consultar_cnpj_cadastral


class ConsultaCnpjCadastralTests(SimpleTestCase):
    def test_rejeita_cnpj_invalido(self):
        data, erro = consultar_cnpj_cadastral('11.111.111/1111-11')
        self.assertIsNone(data)
        self.assertIn('inválido', erro.lower())

    @patch('apps.cadastros.consulta_cnpj._get_json')
    def test_retorna_dados_basicos_sem_ie(self, mock_get):
        mock_get.return_value = {
            'status': 'OK',
            'cnpj': '00000000000191',
            'nome': 'Empresa Teste LTDA',
            'fantasia': 'Empresa Teste',
            'logradouro': 'Rua B',
            'numero': '20',
            'bairro': 'Centro',
            'municipio': 'São Paulo',
            'uf': 'SP',
            'cep': '01001000',
            'telefone': '(11) 3333-4444',
            'atividade_principal': [{'code': '2511000'}],
            'simples': 'Sim',
        }

        data, erro = consultar_cnpj_cadastral('00.000.000/0001-91')
        self.assertEqual(erro, '')
        assert data is not None
        self.assertEqual(data['razao_social'], 'Empresa Teste LTDA')
        self.assertEqual(data['uf'], 'SP')
        self.assertEqual(data['cnae'], '2511000')
        self.assertEqual(data['inscricao_estadual'], '')
        self.assertFalse(data['inscricao_estadual_disponivel'])
        self.assertTrue(data['consulta_ie_pendente'])
        self.assertEqual(data['aviso_ie'], AVISO_IE_FONTE_ATUAL)

    @patch('apps.cadastros.consulta_cnpj._get_json')
    def test_consulta_cnpj_alfanumerico(self, mock_get):
        mock_get.return_value = {
            'status': 'OK',
            'cnpj': '00.000.000/E08G-12',
            'nome': 'BANCO DO BRASIL SA',
            'fantasia': '',
            'logradouro': 'Q 201',
            'numero': 'S/N',
            'bairro': 'ASA NORTE',
            'municipio': 'BRASILIA',
            'uf': 'DF',
            'cep': '70832540',
            'telefone': '(61) 3493-9525',
            'email': 'age1606@bb.com.br',
            'atividade_principal': [{'code': '6422100'}],
            'simples': False,
        }

        data, erro = consultar_cnpj_cadastral('00.000.000/E08G-12')

        self.assertEqual(erro, '')
        assert data is not None
        self.assertEqual(data['cnpj'], '00.000.000/E08G-12')
        self.assertEqual(data['razao_social'], 'BANCO DO BRASIL SA')
        self.assertEqual(data['uf'], 'DF')
        mock_get.assert_called_once_with(
            'https://receitaws.com.br/v1/cnpj/00000000E08G12',
            timeout=10.0,
        )

    @patch('apps.cadastros.consulta_cnpj._get_json', side_effect=TimeoutError('fora'))
    def test_indisponivel_retorna_mensagem_amigavel(self, _mock_get):
        data, erro = consultar_cnpj_cadastral('00.000.000/0001-91')
        self.assertIsNone(data)
        self.assertIn('não foi possível consultar', erro.lower())
