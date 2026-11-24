"""Chegada explícita na conferência de NF-e de entrada de fornecedor."""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from apps.auditoria.models import RegistroAuditoria
from apps.cadastros.models import Fornecedor
from apps.comercial.models import PedidoCompra
from apps.fiscal.models import (
    ItemNFeEntradaHistoricaImportada,
    NFeEntradaConferencia,
    NFeEntradaHistoricaImportada,
)
from apps.fiscal.serializers import NFeEntradaConferenciaSerializer


class ChegadaConferenciaNFeEntradaTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('chegada_entrada', password='x')
        self.outro_user = get_user_model().objects.create_user('outra_chegada', password='x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.fornecedor = Fornecedor.objects.create(
            razao_social='Fornecedor chegada', cnpj='12.345.678/0001-90',
        )
        self.nf = NFeEntradaHistoricaImportada.objects.create(
            chave_acesso='3' * 44,
            numero='123',
            serie='1',
            modelo='55',
            dh_emissao=timezone.now(),
            valor_total_nf=Decimal('10.00'),
            fornecedor_emitente=self.fornecedor,
            emit_json={'CNPJ': '12345678000190'},
            xml_conteudo='<xml>original</xml>',
        )
        self.item_nf = ItemNFeEntradaHistoricaImportada.objects.create(
            nf=self.nf,
            n_item=1,
            prod_json={'qCom': '2', 'uCom': 'PC', 'vUnCom': '5', 'vProd': '10'},
        )
        self.base = f'/api/nf-entradas-historicas-importadas/{self.nf.pk}/conferencia/'

    def _eventos_chegada(self, conf):
        return RegistroAuditoria.objects.filter(
            app_label='fiscal', model_name='nfeentradaconferencia',
            object_id=conf.pk, acao='chegada_iniciada',
        )

    def test_get_sem_conferencia_nao_cria_nem_grava(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(self.base)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'iniciada': False, 'conferencia': None})
        self.assertFalse(NFeEntradaConferencia.objects.filter(nf_entrada_historica=self.nf).exists())
        self.assertFalse(any(
            query['sql'].lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE'))
            for query in queries.captured_queries
        ))

    def test_get_com_conferencia_nao_vincula_fornecedor_nem_grava(self):
        self.nf.fornecedor_emitente = None
        self.nf.save(update_fields=['fornecedor_emitente'])
        conf = NFeEntradaConferencia.objects.create(nf_entrada_historica=self.nf)

        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(self.base)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['iniciada'])
        self.assertEqual(response.json()['conferencia']['id'], conf.pk)
        self.assertFalse(any(
            query['sql'].lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE'))
            for query in queries.captured_queries
        ))
        self.nf.refresh_from_db()
        self.assertIsNone(self.nf.fornecedor_emitente_id)
        self.assertEqual(conf.itens.count(), 0)

    def test_preview_financeiro_nao_persiste_fornecedor_nem_duplicatas(self):
        self.nf.fornecedor_emitente = None
        self.nf.xml_conteudo = (
            '<NFe><infNFe><cobr><dup><nDup>001</nDup>'
            '<dVenc>2026-12-01</dVenc><vDup>10.00</vDup>'
            '</dup></cobr></infNFe></NFe>'
        )
        self.nf.save(update_fields=['fornecedor_emitente', 'xml_conteudo'])
        original_extra = self.nf.reforma_e_outros_json.copy()
        url = f'/api/nf-entradas-historicas-importadas/{self.nf.pk}/financeiro/preview-contas-pagar/'

        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['fornecedor']['id'], self.fornecedor.pk)
        self.assertEqual(response.json()['origem_parcelas'], 'XML')
        self.assertFalse(any(
            query['sql'].lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE'))
            for query in queries.captured_queries
        ))
        self.nf.refresh_from_db()
        self.assertIsNone(self.nf.fornecedor_emitente_id)
        self.assertEqual(self.nf.reforma_e_outros_json, original_extra)

    def test_iniciar_e_repetir_preserva_chegada_usuario_e_historico(self):
        original_prod = self.item_nf.prod_json.copy()
        primeira = self.client.post(self.base + 'iniciar/', {'local_recebimento': 'Portaria'}, format='json')
        self.assertEqual(primeira.status_code, 200)
        conf = NFeEntradaConferencia.objects.get(nf_entrada_historica=self.nf)
        chegada = conf.chegada_em
        self.assertTrue(primeira.json()['iniciada'])
        self.assertIsNotNone(chegada)
        self.assertEqual(conf.recebido_por_id, self.user.pk)
        self.assertIsNone(conf.pedido_compra_id)
        self.assertEqual(conf.itens.count(), 1)
        self.assertEqual(self._eventos_chegada(conf).count(), 1)

        self.client.force_authenticate(self.outro_user)
        segunda = self.client.post(self.base + 'iniciar/', {'observacao_chegada': 'Recebido'}, format='json')
        self.assertEqual(segunda.status_code, 200)
        conf.refresh_from_db()
        self.nf.refresh_from_db()
        self.item_nf.refresh_from_db()
        self.assertEqual(conf.chegada_em, chegada)
        self.assertEqual(conf.recebido_por_id, self.user.pk)
        self.assertEqual(conf.observacao_chegada, 'Recebido')
        self.assertEqual(conf.itens.count(), 1)
        self.assertEqual(self._eventos_chegada(conf).count(), 1)
        self.assertEqual(self.nf.xml_conteudo, '<xml>original</xml>')
        self.assertEqual(self.item_nf.prod_json, original_prod)

    def test_conferencia_antiga_elegivel_preserva_pedido(self):
        pedido = PedidoCompra.objects.create(
            numero='PC-CHEGADA', fornecedor=self.fornecedor, data=date(2026, 1, 1), status='ABERTO',
        )
        conf = NFeEntradaConferencia.objects.create(nf_entrada_historica=self.nf, pedido_compra=pedido)
        response = self.client.post(self.base + 'iniciar/', {}, format='json')
        conf.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['iniciada'])
        self.assertEqual(conf.pedido_compra_id, pedido.pk)
        self.assertEqual(conf.itens.count(), 1)

    def test_conferencia_antiga_avancada_nao_recebe_chegada(self):
        conf = NFeEntradaConferencia.objects.create(
            nf_entrada_historica=self.nf,
            status=NFeEntradaConferencia.Status.PREPARADA,
            preparado_em=timezone.now(),
        )
        response = self.client.post(self.base + 'iniciar/', {'local_recebimento': 'Portaria'}, format='json')
        conf.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['iniciada'])
        self.assertEqual(response.json()['motivo'], 'CHEGADA_NAO_REGISTRAVEL_PARA_CONFERENCIA_ANTIGA')
        self.assertIsNone(conf.chegada_em)
        self.assertEqual(conf.local_recebimento, '')
        self.assertEqual(conf.itens.count(), 0)
        self.assertFalse(self._eventos_chegada(conf).exists())

    def test_candidatos_vazios_e_pedido_incompativel(self):
        pedido = PedidoCompra.objects.create(
            numero='PC-INVALIDO', fornecedor=self.fornecedor, data=date(2026, 1, 1), status='ABERTO',
        )
        candidatos = self.client.get(self.base + 'candidatos-pedido/')
        self.assertEqual(candidatos.status_code, 200)
        self.assertEqual(candidatos.json(), {
            'candidatos': [], 'motivo': 'EMPRESA_NAO_RESOLVIDA_NO_PEDIDO_COMPRA',
        })
        response = self.client.post(self.base + 'iniciar/', {'pedido_compra_id': pedido.pk}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], 'PEDIDO_COMPRA_NAO_COMPATIVEL')
        self.assertFalse(NFeEntradaConferencia.objects.filter(nf_entrada_historica=self.nf).exists())

    def test_serializer_nao_aceita_chegada_e_usuario_no_post_comum(self):
        conf = NFeEntradaConferencia.objects.create(nf_entrada_historica=self.nf)
        serializer = NFeEntradaConferenciaSerializer(conf, data={
            'chegada_em': timezone.now().isoformat(),
            'recebido_por': self.user.pk,
        }, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertNotIn('chegada_em', serializer.validated_data)
        self.assertNotIn('recebido_por', serializer.validated_data)
