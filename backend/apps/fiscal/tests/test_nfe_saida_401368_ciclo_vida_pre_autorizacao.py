"""ERP 4.0.13.6.8 — Estorno faturamento e descarte NF-e rascunho (pré-autorização SEFAZ)."""

from __future__ import annotations

from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.comercial.faturamento_pedido_venda import (
    confirmar_faturamento_pedido,
    criar_faturamento_pedido,
    estornar_faturamento_pedido,
)
from apps.comercial.models import FaturamentoPedidoVenda, PedidoVenda
from apps.fiscal.models import NFeSaida, NFeSaidaEvento
from apps.fiscal.nfe_saida_ciclo_vida import (
    STATUS_NFE_DESCARTADA_INTERNA,
    descartar_nfe_rascunho,
    validar_motivo_estorno_ou_descarte,
)
from apps.fiscal.nfe_saida_from_faturamento import gerar_nfe_saida_from_faturamento
from apps.fiscal.tests.test_nfe_saida_faturamento import _pedido_item


def _motivo() -> str:
    return 'Erro de teste de homologação antes da emissão'


class CicloVidaPreAutorizacao401368Tests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('401368', '401368@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _pedido_faturado_com_nfe(self):
        pedido, item = _pedido_item(qtd=Decimal('2'), preco=Decimal('250'))
        criado = criar_faturamento_pedido(pedido, {'itens': [{'item_pedido_id': item.pk, 'quantidade': '2'}]})
        confirmar_faturamento_pedido(pedido, criado['faturamento_id'])
        nf = gerar_nfe_saida_from_faturamento(pedido, criado['faturamento_id'])
        pedido.refresh_from_db()
        item.refresh_from_db()
        return pedido, item, criado['faturamento_id'], nf['nfe_saida_id']

    def test_motivo_obrigatorio_minimo_10(self):
        with self.assertRaises(ValueError):
            validar_motivo_estorno_ou_descarte('curto')
        self.assertEqual(len(validar_motivo_estorno_ou_descarte(_motivo())), len(_motivo()))

    def test_estornar_reabre_pedido_e_descarta_nfe(self):
        pedido, item, fat_id, nf_id = self._pedido_faturado_com_nfe()
        r = estornar_faturamento_pedido(pedido, fat_id, motivo=_motivo(), usuario=self.user)
        pedido.refresh_from_db()
        item.refresh_from_db()
        fat = FaturamentoPedidoVenda.objects.get(pk=fat_id)
        nf = NFeSaida.objects.get(pk=nf_id)
        self.assertEqual(fat.status, FaturamentoPedidoVenda.Status.CANCELADO)
        self.assertEqual(nf.status, STATUS_NFE_DESCARTADA_INTERNA)
        self.assertEqual(pedido.status, 'ABERTO')
        self.assertEqual(item.quantidade_faturada, Decimal('0'))
        self.assertEqual(r.get('nfe_descartada_id'), nf_id)
        self.assertTrue(
            NFeSaidaEvento.objects.filter(
                nfe_saida_id=nf_id,
                tipo_evento=NFeSaidaEvento.TipoEvento.ESTORNO_FATURAMENTO_PRE_AUTORIZACAO_NFE,
            ).exists(),
        )

    def test_api_estornar_exige_motivo(self):
        pedido, _, fat_id, _ = self._pedido_faturado_com_nfe()
        res = self.client.post(
            f'/api/pedidos-venda/{pedido.pk}/faturamentos/{fat_id}/estornar/',
            {},
            format='json',
        )
        self.assertEqual(res.status_code, 400)

    def test_api_estornar_com_motivo(self):
        pedido, _, fat_id, _ = self._pedido_faturado_com_nfe()
        res = self.client.post(
            f'/api/pedidos-venda/{pedido.pk}/faturamentos/{fat_id}/estornar/',
            {'motivo': _motivo()},
            format='json',
        )
        self.assertEqual(res.status_code, 200)
        pedido.refresh_from_db()
        self.assertEqual(pedido.status, 'ABERTO')

    def test_segundo_estorno_retorna_idempotente(self):
        pedido, _, fat_id, _ = self._pedido_faturado_com_nfe()
        estornar_faturamento_pedido(pedido, fat_id, motivo=_motivo())
        r = estornar_faturamento_pedido(pedido, fat_id, motivo=_motivo())
        self.assertTrue(r.get('ja_estava_estornado'))
        self.assertIn('já foi estornado', (r.get('mensagens') or [''])[0].lower())

    def test_descartar_nfe_rascunho(self):
        _, _, _, nf_id = self._pedido_faturado_com_nfe()
        r = descartar_nfe_rascunho(NFeSaida.objects.get(pk=nf_id), motivo=_motivo(), usuario=self.user)
        nf = NFeSaida.objects.get(pk=nf_id)
        self.assertEqual(nf.status, STATUS_NFE_DESCARTADA_INTERNA)
        self.assertIn('SEFAZ', r['mensagem'])
        self.assertTrue(
            NFeSaidaEvento.objects.filter(
                nfe_saida_id=nf_id,
                tipo_evento=NFeSaidaEvento.TipoEvento.DESCARTE_RASCUNHO_NFE,
            ).exists(),
        )

    def test_api_descartar_rascunho(self):
        _, _, _, nf_id = self._pedido_faturado_com_nfe()
        res = self.client.post(
            f'/api/nf-saidas/{nf_id}/descartar-rascunho/',
            {'motivo': _motivo()},
            format='json',
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(NFeSaida.objects.get(pk=nf_id).status, STATUS_NFE_DESCARTADA_INTERNA)

    def test_nfe_autorizada_homolog_bloqueia_descarte(self):
        _, _, _, nf_id = self._pedido_faturado_com_nfe()
        nf = NFeSaida.objects.get(pk=nf_id)
        nf.status = 'AUTORIZADA_HOMOLOGACAO'
        nf.protocolo_autorizacao = '123456789012345'
        nf.cstat_autorizacao = '100'
        nf.save(update_fields=['status', 'protocolo_autorizacao', 'cstat_autorizacao'])
        with self.assertRaisesMessage(ValueError, 'autorização'):
            descartar_nfe_rascunho(nf, motivo=_motivo())

    def test_gerar_nova_nfe_apos_descarte(self):
        pedido, item, fat_id, nf_id = self._pedido_faturado_com_nfe()
        descartar_nfe_rascunho(NFeSaida.objects.get(pk=nf_id), motivo=_motivo())
        fat = FaturamentoPedidoVenda.objects.get(pk=fat_id)
        self.assertEqual(fat.status, FaturamentoPedidoVenda.Status.PRONTO_PARA_NFE)
        r = gerar_nfe_saida_from_faturamento(pedido, fat_id)
        self.assertNotEqual(r['nfe_saida_id'], nf_id)
        self.assertTrue(r['nfe_saida_id'] > 0)
