"""Checklist de elegibilidade para estoque na conferência NF-e (Fase 3.5)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.cadastros.models import Fornecedor
from apps.fiscal.conferencia_pedido import (
    STATUS_ELEGIBILIDADE_APTO,
    STATUS_ELEGIBILIDADE_APTO_COM_ALERTA,
    STATUS_ELEGIBILIDADE_BLOQUEADO,
    STATUS_ELEGIBILIDADE_NAO_MOVIMENTA,
    avaliar_elegibilidade_estoque_item_conferencia,
    montar_resumo_elegibilidade_estoque,
)
from apps.fiscal.models import (
    ItemNFeEntradaConferencia,
    ItemNFeEntradaHistoricaImportada,
    NFeEntradaConferencia,
    NFeEntradaHistoricaImportada,
)
from apps.produtos.models import FamiliaProduto, Produto
from apps.qualidade.models import CertificadoFornecedorEntrada, ItemCertificadoFornecedorEntrada
from apps.regras_fiscais.entrada_fiscal import avaliar_item_entrada_fiscal, montar_contexto_fiscal_entrada
from apps.regras_fiscais.models import RegraFiscalEntrada


def _cnpj() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


class ElegibilidadeEstoqueMotorTests(TestCase):
    def setUp(self):
        self.forn = Fornecedor.objects.create(razao_social='Forn Eleg', cnpj=_cnpj(), uf='SP')
        fam = FamiliaProduto.objects.create(
            codigo_figura='FE',
            descricao_base='Fam',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
            tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
            categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
        )
        self.prod = Produto.objects.create(
            familia=fam,
            descricao='Prod',
            modo_codigo=Produto.ModoCodigo.MANUAL,
            codigo_completo='EL-1',
            unidade='PC',
            ncm='84818099',
        )
        nf = NFeEntradaHistoricaImportada.objects.create(
            chave_acesso=('35' + 'E' * 42)[:44],
            numero='8001',
            serie='1',
            modelo='55',
            dh_emissao=timezone.make_aware(datetime(2026, 4, 1, 10, 0)),
            valor_total_nf=Decimal('100'),
            fornecedor_emitente=self.forn,
        )
        item_nf = ItemNFeEntradaHistoricaImportada.objects.create(
            nf=nf,
            n_item=1,
            prod_json={'CFOP': '5102', 'NCM': '84818099', 'qCom': '1', 'uCom': 'PC'},
            imposto_json={},
        )
        self.conf = NFeEntradaConferencia.objects.create(nf_entrada_historica=nf)
        self.linha, _ = self.conf.itens.get_or_create(item_nfe_historico=item_nf)
        self.linha.produto = self.prod
        self.linha.corrida = 'C1'
        self.linha.lote = 'L1'
        self.linha.save(update_fields=['produto', 'corrida', 'lote'])
        self.ctx = montar_contexto_fiscal_entrada(self.conf)
        self.regras: list[RegraFiscalEntrada] = []

    def _rf(self, linha=None):
        linha = linha or self.linha
        return avaliar_item_entrada_fiscal(linha, self.ctx, self.regras)

    def _eleg(self, rf, **kwargs):
        return avaliar_elegibilidade_estoque_item_conferencia(
            self.linha,
            resultado_fiscal=rf,
            divergencias_aceitas=self.conf.divergencias_aceitas,
            **kwargs,
        )

    def test_apto_com_regra_ok_movimenta_estoque(self):
        self.regras = [
            RegraFiscalEntrada.objects.create(
                nome='OK 5102',
                ativo=True,
                prioridade=10,
                cfop='5102',
                movimenta_estoque=True,
                severidade=RegraFiscalEntrada.Severidade.INFORMATIVO,
            ),
        ]
        rf = self._rf()
        e = self._eleg(rf)
        self.assertEqual(e['status'], STATUS_ELEGIBILIDADE_APTO)
        self.assertEqual(e['label'], 'Apto para estoque')
        self.assertEqual(e['mensagens'], [])

    def test_ignorado_nao_movimenta(self):
        self.linha.status = ItemNFeEntradaConferencia.Status.IGNORADO
        self.linha.motivo_ignorado = 'N/A'
        self.linha.save(update_fields=['status', 'motivo_ignorado'])
        e = self._eleg(self._rf())
        self.assertEqual(e['status'], STATUS_ELEGIBILIDADE_NAO_MOVIMENTA)
        self.assertIn('ignorada', e['mensagens'][0].lower())

    def test_regra_nao_movimenta_estoque(self):
        self.regras = [
            RegraFiscalEntrada.objects.create(
                nome='Sem estoque',
                ativo=True,
                prioridade=10,
                cfop='5102',
                movimenta_estoque=False,
                severidade=RegraFiscalEntrada.Severidade.INFORMATIVO,
            ),
        ]
        e = self._eleg(self._rf())
        self.assertEqual(e['status'], STATUS_ELEGIBILIDADE_NAO_MOVIMENTA)
        self.assertFalse(e['movimenta_estoque'])

    def test_sem_produto_bloqueado(self):
        self.linha.produto = None
        self.linha.produto_id = None
        self.linha.save(update_fields=['produto'])
        e = self._eleg(self._rf())
        self.assertEqual(e['status'], STATUS_ELEGIBILIDADE_BLOQUEADO)
        self.assertIn('produto', e['mensagens'][0].lower())

    def test_fiscal_bloqueio_bloqueado(self):
        self.regras = [
            RegraFiscalEntrada.objects.create(
                nome='Bloq',
                ativo=True,
                prioridade=10,
                cfop='5102',
                severidade=RegraFiscalEntrada.Severidade.BLOQUEIO,
            ),
        ]
        e = self._eleg(self._rf())
        self.assertEqual(e['status'], STATUS_ELEGIBILIDADE_BLOQUEADO)
        self.assertIn('regra fiscal', e['mensagens'][-1].lower())

    def test_sem_regra_apto_com_alerta(self):
        e = self._eleg(self._rf())
        self.assertEqual(e['status'], STATUS_ELEGIBILIDADE_APTO_COM_ALERTA)
        self.assertIn('sem_regra_fiscal', e['motivos'])

    def test_alerta_fiscal_apto_com_alerta(self):
        self.regras = [
            RegraFiscalEntrada.objects.create(
                nome='Alerta',
                ativo=True,
                prioridade=10,
                cfop='5102',
                severidade=RegraFiscalEntrada.Severidade.ALERTA,
                mensagem_padrao='Revisar tributação',
            ),
        ]
        e = self._eleg(self._rf())
        self.assertEqual(e['status'], STATUS_ELEGIBILIDADE_APTO_COM_ALERTA)
        self.assertIn('Revisar tributação', e['mensagens'])

    def test_exige_cf_sem_vinculo_alerta(self):
        self.regras = [
            RegraFiscalEntrada.objects.create(
                nome='CF',
                ativo=True,
                prioridade=10,
                cfop='5102',
                exige_certificado_fornecedor=True,
                severidade=RegraFiscalEntrada.Severidade.INFORMATIVO,
            ),
        ]
        e = self._eleg(self._rf())
        self.assertEqual(e['status'], STATUS_ELEGIBILIDADE_APTO_COM_ALERTA)
        self.assertFalse(e['tem_certificado_fornecedor'])
        self.assertIn('certificado fornecedor', e['mensagens'][0].lower())

    def test_exige_cf_com_registrado_apto(self):
        self.regras = [
            RegraFiscalEntrada.objects.create(
                nome='CF ok',
                ativo=True,
                prioridade=10,
                cfop='5102',
                exige_certificado_fornecedor=True,
                severidade=RegraFiscalEntrada.Severidade.INFORMATIVO,
            ),
        ]
        cf = CertificadoFornecedorEntrada.objects.create(
            status=CertificadoFornecedorEntrada.Status.REGISTRADO,
            fornecedor=self.forn,
            nf_entrada_historica=self.conf.nf_entrada_historica,
        )
        ItemCertificadoFornecedorEntrada.objects.create(
            certificado_fornecedor=cf,
            item_conferencia=self.linha,
            ordem=1,
        )
        e = self._eleg(
            self._rf(),
            certificado_fornecedor_info={'registrado': True, 'rascunho': False},
        )
        self.assertEqual(e['status'], STATUS_ELEGIBILIDADE_APTO)
        self.assertTrue(e['tem_certificado_fornecedor'])

    def test_sem_corrida_lote_alerta(self):
        self.regras = [
            RegraFiscalEntrada.objects.create(
                nome='OK',
                ativo=True,
                prioridade=10,
                cfop='5102',
                severidade=RegraFiscalEntrada.Severidade.INFORMATIVO,
            ),
        ]
        self.linha.corrida = ''
        self.linha.lote = ''
        self.linha.save(update_fields=['corrida', 'lote'])
        e = self._eleg(self._rf())
        self.assertEqual(e['status'], STATUS_ELEGIBILIDADE_APTO_COM_ALERTA)
        self.assertFalse(e['tem_rastreabilidade_tecnica'])
        self.assertIn('corrida/lote', e['mensagens'][0].lower())

    def test_divergencia_sem_aceite_bloqueado(self):
        self.regras = [
            RegraFiscalEntrada.objects.create(
                nome='OK',
                ativo=True,
                prioridade=10,
                cfop='5102',
                severidade=RegraFiscalEntrada.Severidade.INFORMATIVO,
            ),
        ]
        self.linha.divergencias = ['quantidade_diferente']
        self.linha.status = ItemNFeEntradaConferencia.Status.DIVERGENTE
        self.linha.save(update_fields=['divergencias', 'status'])
        e = self._eleg(self._rf())
        self.assertEqual(e['status'], STATUS_ELEGIBILIDADE_BLOQUEADO)

    def test_montar_resumo_elegibilidade(self):
        resumo = montar_resumo_elegibilidade_estoque(
            [
                {'status': STATUS_ELEGIBILIDADE_APTO},
                {'status': STATUS_ELEGIBILIDADE_APTO_COM_ALERTA},
                {'status': STATUS_ELEGIBILIDADE_BLOQUEADO},
                {'status': STATUS_ELEGIBILIDADE_NAO_MOVIMENTA},
            ],
        )
        self.assertEqual(resumo['aptos'], 1)
        self.assertEqual(resumo['aptos_com_alerta'], 1)
        self.assertEqual(resumo['bloqueados'], 1)
        self.assertEqual(resumo['nao_movimentam'], 1)


class ElegibilidadeEstoqueAPITests(TestCase):
    def setUp(self):
        self.forn = Fornecedor.objects.create(razao_social='API Eleg', cnpj=_cnpj())
        fam = FamiliaProduto.objects.create(
            codigo_figura='AE',
            descricao_base='F',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
            tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
            categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
        )
        prod = Produto.objects.create(
            familia=fam,
            descricao='P',
            modo_codigo=Produto.ModoCodigo.MANUAL,
            codigo_completo='P-EL',
            unidade='PC',
        )
        nf = NFeEntradaHistoricaImportada.objects.create(
            chave_acesso=('35' + 'A' * 42)[:44],
            numero='8002',
            serie='1',
            modelo='55',
            dh_emissao=timezone.make_aware(datetime(2026, 4, 2, 10, 0)),
            valor_total_nf=Decimal('50'),
            fornecedor_emitente=self.forn,
        )
        item_nf = ItemNFeEntradaHistoricaImportada.objects.create(
            nf=nf,
            n_item=1,
            prod_json={'CFOP': '1102', 'NCM': '73071100'},
            imposto_json={},
        )
        self.conf = NFeEntradaConferencia.objects.create(nf_entrada_historica=nf)
        linha, _ = self.conf.itens.get_or_create(item_nfe_historico=item_nf)
        linha.produto = prod
        linha.corrida = 'C-API'
        linha.lote = 'L-API'
        linha.save(update_fields=['produto', 'corrida', 'lote'])
        RegraFiscalEntrada.objects.create(
            nome='Compra 1102',
            ativo=True,
            prioridade=10,
            cfop='1102',
            severidade=RegraFiscalEntrada.Severidade.INFORMATIVO,
        )
        user = get_user_model().objects.create_user('el_api', 'el@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(user)
        self.url = reverse('nf-entrada-hist-importada-conferencia', kwargs={'pk': nf.id})
        self.url_prep = reverse('nf-entrada-hist-importada-preparar-estoque', kwargs={'pk': nf.id})

    def test_api_expoe_elegibilidade_e_resumo(self):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        body = r.json()
        self.assertIn('resumo_elegibilidade_estoque', body)
        item = body['itens'][0]
        self.assertIn('elegibilidade_estoque', item)
        elig = item['elegibilidade_estoque']
        self.assertEqual(elig['status'], STATUS_ELEGIBILIDADE_APTO)
        resumo = body['resumo_elegibilidade_estoque']
        self.assertEqual(resumo['aptos'], 1)

    def test_preparar_bloqueio_fiscal_fase_34_mantido(self):
        RegraFiscalEntrada.objects.filter(cfop='1102').update(
            severidade=RegraFiscalEntrada.Severidade.BLOQUEIO,
        )
        r_prep = self.client.post(self.url_prep, {}, format='json')
        self.assertEqual(r_prep.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(r_prep.json().get('bloqueio_fiscal'))
