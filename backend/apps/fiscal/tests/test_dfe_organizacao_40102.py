"""ERP 4.0.10.2 — importação/recebimento DF-e: classificação, precificação e conferência segura."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.cadastros.models import Empresa, Fornecedor
from apps.fiscal.dfe_classificacao import (
    CATEGORIA_BASE_DFE_IMPORTADA,
    CATEGORIA_HOMOLOGACAO,
    metadados_classificacao_dfe,
    pode_alimentar_precificacao,
    pode_entrar_apuracao,
    pode_gerar_efeito_operacional,
)
from apps.fiscal.models import (
    EstoqueCorrida,
    ItemNFeEntradaHistoricaImportada,
    NFeEntradaConferencia,
    NFeEntradaHistoricaImportada,
    NFeSaidaHistoricaImportada,
)
from apps.fiscal.nfe_historica_entrada_fiscal import queryset_compras_nf_entrada_historica
from apps.fiscal.nfe_historica_fiscal import queryset_faturamento_nf_saida_historica
from apps.produtos.models import FamiliaProduto, Produto


def _dh() -> datetime:
    return timezone.make_aware(datetime(2026, 4, 10, 12, 0, 0))


class MetadadosClassificacao40102Test(TestCase):
    def test_metadados_base_importada_producao(self) -> None:
        nf = NFeEntradaHistoricaImportada(tp_amb='1', cstat='100')
        meta = metadados_classificacao_dfe(nf, conferencia_status='CONFERIDA')
        self.assertEqual(meta['categoria'], CATEGORIA_BASE_DFE_IMPORTADA)
        self.assertTrue(meta['pode_entrar_apuracao'])
        self.assertTrue(meta['pode_alimentar_precificacao'])
        self.assertFalse(meta['pode_gerar_efeito_operacional'])
        self.assertIn('base_importada', meta['badges'])
        self.assertIn('conferida', meta['badges'])

    def test_metadados_homologacao(self) -> None:
        nf = NFeSaidaHistoricaImportada(tp_amb='2', cstat='100')
        meta = metadados_classificacao_dfe(nf)
        self.assertEqual(meta['categoria'], CATEGORIA_HOMOLOGACAO)
        self.assertFalse(meta['pode_entrar_apuracao'])
        self.assertIn('homologacao', meta['badges'])
        self.assertIn('fora_apuracao', meta['badges'])


class PrecificacaoExclusaoHomolog40102Test(TestCase):
    def setUp(self) -> None:
        self.emp = Empresa.objects.create(razao_social='Emp 40102', cnpj='11.111.111/0001-11')
        self.forn = Fornecedor.objects.create(razao_social='Forn 40102', cnpj='22.222.222/0001-22')
        self.dh = _dh()

    def test_queryset_precificacao_exclui_homologacao(self) -> None:
        NFeEntradaHistoricaImportada.objects.create(
            chave_acesso='1' * 44,
            numero='1',
            serie='1',
            modelo='55',
            dh_emissao=self.dh,
            tp_amb='2',
            cstat='100',
            empresa_destinataria=self.emp,
            fornecedor_emitente=self.forn,
        )
        NFeEntradaHistoricaImportada.objects.create(
            chave_acesso='2' * 44,
            numero='2',
            serie='1',
            modelo='55',
            dh_emissao=self.dh,
            tp_amb='1',
            cstat='100',
            empresa_destinataria=self.emp,
            fornecedor_emitente=self.forn,
        )
        qs = queryset_compras_nf_entrada_historica(NFeEntradaHistoricaImportada.objects.all())
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().chave_acesso, '2' * 44)

    def test_queryset_saida_precificacao_exclui_homolog(self) -> None:
        NFeSaidaHistoricaImportada.objects.create(
            chave_acesso='3' * 44,
            numero='3',
            serie='1',
            dh_emissao=self.dh,
            tp_amb='2',
            cstat='100',
            empresa_emitente=self.emp,
            cancelada=False,
        )
        NFeSaidaHistoricaImportada.objects.create(
            chave_acesso='4' * 44,
            numero='4',
            serie='1',
            dh_emissao=self.dh,
            tp_amb='1',
            cstat='100',
            empresa_emitente=self.emp,
            cancelada=False,
        )
        qs = queryset_faturamento_nf_saida_historica(NFeSaidaHistoricaImportada.objects.all())
        self.assertEqual(qs.count(), 1)


class ApiListagemBaseImportada40102Test(TestCase):
    def setUp(self) -> None:
        User = get_user_model()
        self.user = User.objects.create_user(username='dfe40102', password='test')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.nf = NFeEntradaHistoricaImportada.objects.create(
            chave_acesso='5' * 44,
            numero='5',
            serie='1',
            modelo='55',
            dh_emissao=_dh(),
            tp_amb='1',
            cstat='100',
            valor_total_nf=Decimal('100'),
        )

    def test_listagem_inclui_classificacao_sem_xml_bruto(self) -> None:
        url = reverse('nf-entrada-hist-importada-list')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = resp.data.get('results', resp.data)
        self.assertEqual(len(results), 1)
        row = results[0]
        self.assertIn('classificacao_dfe', row)
        self.assertEqual(row['classificacao_dfe']['categoria'], CATEGORIA_BASE_DFE_IMPORTADA)
        self.assertNotIn('xml', row)
        self.assertNotIn('xml_conteudo', row)


class HomologacaoPrecificacao40102Test(TestCase):
    def test_homologacao_nao_precificacao_oficial(self) -> None:
        nf = NFeEntradaHistoricaImportada(tp_amb='2', cstat='100')
        self.assertFalse(pode_alimentar_precificacao(nf))
        self.assertFalse(pode_entrar_apuracao(nf))
        self.assertFalse(pode_gerar_efeito_operacional(nf))


class ConferenciaSemEfeitoAutomatico40102Test(TestCase):
    def setUp(self) -> None:
        User = get_user_model()
        self.user = User.objects.create_user(username='conf40102', password='test')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.forn = Fornecedor.objects.create(razao_social='Forn conf', cnpj='33.333.333/0001-33')
        fam = FamiliaProduto.objects.create(
            codigo_figura='F40102',
            descricao_base='Fam',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
            tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
            categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
        )
        self.prod = Produto.objects.create(
            familia=fam,
            descricao='Prod conf',
            modo_codigo=Produto.ModoCodigo.MANUAL,
            codigo_completo='PCONF',
            unidade='PC',
            ncm='84818099',
        )
        self.nf = NFeEntradaHistoricaImportada.objects.create(
            chave_acesso='6' * 44,
            numero='6',
            serie='1',
            modelo='55',
            dh_emissao=_dh(),
            valor_total_nf=Decimal('50'),
            fornecedor_emitente=self.forn,
        )
        ItemNFeEntradaHistoricaImportada.objects.create(
            nf=self.nf,
            n_item=1,
            prod_json={'cProd': 'PCONF', 'qCom': '1', 'uCom': 'PC', 'vProd': '50'},
        )
        self.url_conf = reverse('nf-entrada-hist-importada-conferencia', kwargs={'pk': self.nf.id})
        self.estoque_antes = EstoqueCorrida.objects.count()

    def test_salvar_conferencia_nao_aplica_estoque_automatico(self) -> None:
        get_resp = self.client.get(self.url_conf)
        self.assertEqual(get_resp.status_code, status.HTTP_200_OK)
        item_conf_id = get_resp.data['itens'][0]['id']

        post_resp = self.client.post(
            self.url_conf,
            {
                'itens': [
                    {
                        'id': item_conf_id,
                        'produto_id': self.prod.id,
                        'status': 'PRODUTO_VINCULADO',
                    },
                ],
            },
            format='json',
        )
        self.assertEqual(post_resp.status_code, status.HTTP_200_OK, post_resp.content)
        conf = NFeEntradaConferencia.objects.get(nf_entrada_historica=self.nf)
        self.assertIsNone(conf.estoque_aplicado_em)
        self.assertEqual(EstoqueCorrida.objects.count(), self.estoque_antes)
        self.assertFalse(pode_gerar_efeito_operacional(self.nf))
