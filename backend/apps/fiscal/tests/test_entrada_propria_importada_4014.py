"""ERP 4.0.14.x — importação NF-e entrada própria já emitida."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from apps.cadastros.models import Empresa, Fornecedor
from apps.financeiro.models import TituloFinanceiro
from apps.fiscal.models import EstoqueCorrida, NFeEntrada, NFeEntradaHistoricaImportada, NFeSaidaHistoricaImportada
from apps.fiscal.nfe_import.service import importar_arquivos
from apps.fiscal.nfe_import.service_entrada import importar_arquivos_entrada
from apps.fiscal.nfe_import.service_entrada_propria import importar_arquivos_entrada_propria_emitida
from apps.fiscal.tests.fixtures_xml_entrada_propria import (
    xml_nfe_compra_fornecedor_sintetico,
    xml_nfe_entrada_propria_sintetico,
)

User = get_user_model()

CHAVE_PROPRIA_1 = '35260612345678000199550010000000011000000010'
CHAVE_PROPRIA_2 = '35260612345678000199550010000000021000000020'
CHAVE_COMPRA = '35260611111111000111550010000000031000000030'


class EntradaPropriaImportada4014Test(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(username='op4014', password='x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.empresa = Empresa.objects.create(
            razao_social='Empresa Teste 4014',
            cnpj='12.345.678/0001-99',
        )
        Fornecedor.objects.create(razao_social='Fornecedor Teste', cnpj='11.111.111/0001-11')

    def test_importacao_entrada_propria_fluxo_operacional(self) -> None:
        xml = xml_nfe_entrada_propria_sintetico(chave=CHAVE_PROPRIA_1)
        out = importar_arquivos_entrada_propria_emitida([('propria.xml', xml)])
        self.assertEqual(out['resumo']['importadas'], 1)
        self.assertEqual(out['resumo']['erros'], 0)
        nf = NFeEntrada.objects.get(chave_acesso=CHAVE_PROPRIA_1)
        self.assertEqual(nf.tipo_origem, NFeEntrada.TipoOrigem.ENTRADA_PROPRIA_IMPORTADA)
        self.assertEqual(
            nf.status_operacional,
            NFeEntrada.StatusOperacional.IMPORTADA_PENDENTE_CONFERENCIA,
        )
        self.assertEqual(nf.empresa_emitente_id, self.empresa.id)
        self.assertTrue(nf.xml_importado)
        self.assertFalse(nf.itens.exists())
        self.assertEqual(EstoqueCorrida.objects.count(), 0)
        self.assertEqual(TituloFinanceiro.objects.count(), 0)

    def test_api_importar_entrada_propria(self) -> None:
        xml = xml_nfe_entrada_propria_sintetico(chave=CHAVE_PROPRIA_2, n_nf='102')
        res = self.client.post(
            '/api/nf-entradas/importar-entrada-propria-emitida/',
            {
                'arquivos': SimpleUploadedFile(
                    'propria.xml',
                    xml,
                    content_type='application/xml',
                ),
            },
            format='multipart',
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['resumo']['importadas'], 1)
        lista = self.client.get('/api/nf-entradas/')
        self.assertEqual(lista.status_code, 200)
        results = lista.json().get('results') or lista.json()
        self.assertTrue(any(r.get('tipo_origem_label') == 'Entrada própria' for r in results))
        self.assertTrue(all('xml_importado' not in r for r in results))

    def test_duplicidade_chave_entrada_propria(self) -> None:
        xml = xml_nfe_entrada_propria_sintetico(chave=CHAVE_PROPRIA_1)
        importar_arquivos_entrada_propria_emitida([('a.xml', xml)])
        out = importar_arquivos_entrada_propria_emitida([('b.xml', xml)])
        self.assertEqual(out['resumo']['duplicadas'], 1)
        self.assertEqual(NFeEntrada.objects.filter(chave_acesso=CHAVE_PROPRIA_1).count(), 1)

    def test_base_saida_rejeita_entrada_propria_com_orientacao(self) -> None:
        xml = xml_nfe_entrada_propria_sintetico(chave='35260612345678000199550010000000041000000040')
        out = importar_arquivos([('propria.xml', xml)])
        self.assertEqual(out['resumo']['importadas'], 0)
        self.assertEqual(out['resumo']['erros'], 1)
        erro = out['erros'][0]
        self.assertIn('entrada própria', erro['mensagem'].lower())
        self.assertIn('Importar entrada própria', erro['acao_sugerida'])

    def test_base_entrada_fornecedor_rejeita_entrada_propria_com_orientacao(self) -> None:
        xml = xml_nfe_entrada_propria_sintetico(chave='35260612345678000199550010000000051000000050')
        out = importar_arquivos_entrada([('propria.xml', xml)])
        self.assertEqual(out['resumo']['importadas'], 0)
        self.assertEqual(out['resumo']['erros'], 1)
        erro = out['erros'][0]
        self.assertIn('entrada própria', erro['mensagem'].lower())
        self.assertIn('Importar entrada própria', erro['acao_sugerida'])

    def test_base_entrada_aceita_compra_fornecedor(self) -> None:
        xml = xml_nfe_compra_fornecedor_sintetico(chave=CHAVE_COMPRA)
        out = importar_arquivos_entrada([('compra.xml', xml)])
        self.assertEqual(out['resumo']['importadas'], 1)
        self.assertTrue(NFeEntradaHistoricaImportada.objects.filter(chave_acesso=CHAVE_COMPRA).exists())

    def test_sem_efeito_financeiro_apos_importacao(self) -> None:
        xml = xml_nfe_entrada_propria_sintetico(chave='35260612345678000199550010000000061000000060')
        importar_arquivos_entrada_propria_emitida([('p.xml', xml)])
        nf = NFeEntrada.objects.get(chave_acesso='35260612345678000199550010000000061000000060')
        self.assertEqual(TituloFinanceiro.objects.filter(origem_id=nf.pk).count(), 0)
