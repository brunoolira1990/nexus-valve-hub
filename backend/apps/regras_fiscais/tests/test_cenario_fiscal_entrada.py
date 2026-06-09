"""Sprint 1 — Cenário Fiscal de Entrada (modelos, API, migração, motor)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.cadastros.models import Fornecedor
from apps.fiscal.models import (
    ItemNFeEntradaHistoricaImportada,
    NFeEntradaConferencia,
    NFeEntradaHistoricaImportada,
)
from apps.produtos.models import FamiliaProduto, Produto
from apps.regras_fiscais.cenario_fiscal_entrada import (
    NOME_CENARIO_PADRAO,
    gerar_label_configuracao_fiscal,
    obter_ou_criar_cenario_padrao,
)
from apps.regras_fiscais.entrada_fiscal import avaliar_item_entrada_fiscal, carregar_regras_fiscais_entrada_ativas
from apps.regras_fiscais.models import (
    CenarioFiscalEntrada,
    CenarioFiscalEntradaEscopo,
    RegraFiscalEntrada,
)


def _cnpj() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


class CenarioFiscalEntradaMigrationTests(TestCase):
    def test_cenario_padrao_existe_apos_migracao(self):
        cenario = CenarioFiscalEntrada.objects.filter(padrao=True, ativo=True).first()
        self.assertIsNotNone(cenario)
        self.assertEqual(cenario.nome, NOME_CENARIO_PADRAO)

    def test_regra_criada_recebe_cenario_e_escopo(self):
        regra = RegraFiscalEntrada.objects.create(
            nome='Teste escopo',
            ativo=True,
            prioridade=1,
            cfop='5102',
            ncm='84818095',
            severidade=RegraFiscalEntrada.Severidade.INFORMATIVO,
        )
        regra.refresh_from_db()
        self.assertIsNotNone(regra.cenario_id)
        self.assertTrue(regra.cenario.padrao)
        self.assertIsNotNone(regra.escopo_id)
        self.assertEqual(regra.escopo.tipo_escopo, CenarioFiscalEntradaEscopo.TipoEscopo.NCM)
        self.assertEqual(regra.escopo.ncm, '84818095')

    def test_agrupamento_escopo_geral(self):
        regra = RegraFiscalEntrada.objects.create(
            nome='Geral',
            ativo=True,
            cfop='5102',
            severidade=RegraFiscalEntrada.Severidade.INFORMATIVO,
        )
        regra.refresh_from_db()
        self.assertEqual(regra.escopo.tipo_escopo, CenarioFiscalEntradaEscopo.TipoEscopo.GERAL)


class CenarioFiscalEntradaLabelTests(TestCase):
    def test_label_automatico_formato(self):
        escopo = CenarioFiscalEntradaEscopo.objects.create(
            cenario=obter_ou_criar_cenario_padrao(),
            tipo_escopo=CenarioFiscalEntradaEscopo.TipoEscopo.NCM,
            ncm='84818095',
        )
        regra = RegraFiscalEntrada(
            escopo=escopo,
            cenario=escopo.cenario,
            nome='x',
            cfop_origem='5102',
            cfop_entrada='1102',
            uf_origem='SP',
            uf_destino='SP',
            ncm='84818095',
        )
        label = gerar_label_configuracao_fiscal(regra, escopo)
        self.assertIn('NCM 84818095', label)
        self.assertIn('SP→SP', label)
        self.assertIn('5102→1102', label)


class CenarioFiscalEntradaMotorTests(TestCase):
    def setUp(self):
        self.forn = Fornecedor.objects.create(razao_social='Forn Cen', cnpj=_cnpj(), uf='SP')
        nf = NFeEntradaHistoricaImportada.objects.create(
            chave_acesso=('35' + '9' * 42)[:44],
            numero='9010',
            serie='1',
            modelo='55',
            dh_emissao=timezone.make_aware(datetime(2026, 4, 1, 10, 0)),
            valor_total_nf=Decimal('100'),
            fornecedor_emitente=self.forn,
            emit_json={'enderEmit': {'UF': 'SP'}},
            dest_json={'enderDest': {'UF': 'RJ'}},
        )
        item_nf = ItemNFeEntradaHistoricaImportada.objects.create(
            nf=nf,
            n_item=1,
            prod_json={'CFOP': '6102', 'NCM': '84818099'},
            imposto_json={},
        )
        self.conf = NFeEntradaConferencia.objects.create(nf_entrada_historica=nf)
        self.linha, _ = self.conf.itens.get_or_create(item_nfe_historico=item_nf)

    def test_motor_usa_cenario_padrao(self):
        regra = RegraFiscalEntrada.objects.create(
            nome='R6102',
            ativo=True,
            cfop='6102',
            ncm='84818099',
            severidade=RegraFiscalEntrada.Severidade.INFORMATIVO,
        )
        carregadas = carregar_regras_fiscais_entrada_ativas()
        self.assertTrue(any(r.id == regra.id for r in carregadas))
        from apps.regras_fiscais.entrada_fiscal import ContextoFiscalEntrada, montar_contexto_fiscal_entrada

        ctx = montar_contexto_fiscal_entrada(self.conf)
        r = avaliar_item_entrada_fiscal(self.linha, ctx, carregadas)
        self.assertEqual(r['status'], 'OK')
        self.assertEqual(r['regra_id'], regra.id)

    def test_regra_id_continua_sendo_folha(self):
        regra = RegraFiscalEntrada.objects.create(
            nome='Id folha',
            ativo=True,
            cfop='6102',
            severidade=RegraFiscalEntrada.Severidade.INFORMATIVO,
        )
        from apps.regras_fiscais.entrada_fiscal import ContextoFiscalEntrada

        ctx = ContextoFiscalEntrada(uf_origem='SP', uf_destino='RJ')
        r = avaliar_item_entrada_fiscal(
            self.linha,
            ctx,
            carregar_regras_fiscais_entrada_ativas(),
        )
        self.assertEqual(r['regra_id'], regra.id)


class CenarioFiscalEntradaAPITests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user('cen_api', 'cen@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(user)
        self.cenario = obter_ou_criar_cenario_padrao()

    def test_lista_cenarios(self):
        url = reverse('cenario-fiscal-entrada-list')
        r = self.client.get(url, HTTP_HOST='localhost')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        body = r.json()
        self.assertTrue(any(c['padrao'] for c in body))
        padrao = next(c for c in body if c['padrao'])
        self.assertIn('total_escopos', padrao)
        self.assertIn('total_configuracoes', padrao)

    def test_lista_cria_cenario_padrao_se_vazio(self):
        CenarioFiscalEntrada.objects.all().delete()
        url = reverse('cenario-fiscal-entrada-list')
        r = self.client.get(url, HTTP_HOST='localhost')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(len(r.json()), 1)
        self.assertTrue(r.json()[0]['padrao'])

    def test_detalhe_cenario_com_escopos_e_contagem(self):
        RegraFiscalEntrada.objects.create(
            nome='R1',
            ativo=True,
            cfop='1102',
            ncm='73071100',
            severidade=RegraFiscalEntrada.Severidade.INFORMATIVO,
        )
        url = reverse('cenario-fiscal-entrada-detail', kwargs={'pk': self.cenario.pk})
        r = self.client.get(url)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        body = r.json()
        self.assertIn('escopos', body)
        escopo_ncm = next((e for e in body['escopos'] if e['ncm'] == '73071100'), None)
        self.assertIsNotNone(escopo_ncm)
        self.assertGreaterEqual(escopo_ncm['configuracoes_count'], 1)

    def test_api_legada_cria_com_cenario_padrao(self):
        url = reverse('regrafiscal-entrada-list')
        r = self.client.post(
            url,
            {
                'nome': 'Via API legada',
                'ativo': True,
                'prioridade': 5,
                'cfop_origem': '5102',
                'ncm': '12345678',
                'severidade': 'INFORMATIVO',
            },
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        regra = RegraFiscalEntrada.objects.get(pk=r.json()['id'])
        self.assertIsNotNone(regra.cenario_id)
        self.assertTrue(regra.cenario.padrao)
        self.assertIsNotNone(regra.escopo_id)

    def test_criar_escopo_ncm(self):
        url = reverse('cenario-fiscal-entrada-escopos', kwargs={'pk': self.cenario.pk})
        r = self.client.post(
            url,
            {'tipo_escopo': 'NCM', 'ncm': '84811000', 'ativo': True},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.json()['tipo_escopo'], 'NCM')
        self.assertEqual(r.json()['ncm'], '84811000')

    def test_lista_configuracoes_por_escopo(self):
        regra = RegraFiscalEntrada.objects.create(
            nome='Cfg',
            ativo=True,
            cfop='6102',
            uf_origem='SP',
            uf_destino='RJ',
            ncm='99998877',
            severidade=RegraFiscalEntrada.Severidade.INFORMATIVO,
        )
        url = reverse(
            'cenario-fiscal-entrada-configuracoes-escopo',
            kwargs={'pk': self.cenario.pk, 'escopo_id': regra.escopo_id},
        )
        r = self.client.get(url)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertTrue(any(c['id'] == regra.id for c in r.json()))
