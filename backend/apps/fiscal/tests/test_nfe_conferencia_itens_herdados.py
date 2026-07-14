"""NF-e herdada: falsa alteração de itens no salvar-conferencia (precisão Decimal)."""

from __future__ import annotations

from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.cadastros.models import Transportadora
from apps.fiscal.models import ItemNFeSaida, NFeSaida
from apps.fiscal.nfe_saida_bloqueio import item_comercial_semanticamente_igual
from apps.fiscal.nfe_saida_from_faturamento import gerar_nfe_saida_from_faturamento
from apps.fiscal.serializers import NFeSaidaSerializer
from apps.fiscal.tests.test_nfe_saida_faturamento import _faturamento_pronto, _pedido_item
from apps.produtos.models import Produto


class ItemComercialSemanticoTests(TestCase):
    def test_decimal_com_zeros_finais_e_igual(self):
        pedido, item = _pedido_item()
        fat = _faturamento_pronto(pedido, item)
        r = gerar_nfe_saida_from_faturamento(pedido, fat.pk)
        nf_item = ItemNFeSaida.objects.get(nf_id=r['nfe_saida_id'])
        nf_item.valor = Decimal('1128.1250')
        nf_item.save(update_fields=['valor'])
        nf_item.refresh_from_db()
        self.assertTrue(
            item_comercial_semanticamente_igual(
                nf_item,
                {
                    'id': nf_item.id,
                    'produto_id': nf_item.produto_id,
                    'quantidade': str(nf_item.quantidade),
                    'valor': '1128.125',
                },
            ),
        )
        self.assertTrue(
            item_comercial_semanticamente_igual(
                nf_item,
                {'id': nf_item.id, 'valor': '1128.1250'},
            ),
        )


class SalvarConferenciaItensHerdadosTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('nfe_conf_herd', 'nfe_conf_herd@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _nf_herdada_com_preco(self, valor: Decimal = Decimal('1128.125')) -> tuple[NFeSaida, ItemNFeSaida]:
        pedido, item = _pedido_item()
        fat = _faturamento_pronto(pedido, item)
        r = gerar_nfe_saida_from_faturamento(pedido, fat.pk)
        nf = NFeSaida.objects.prefetch_related('itens__produto').get(pk=r['nfe_saida_id'])
        nf_item = nf.itens.first()
        assert nf_item is not None
        nf_item.valor = valor
        nf_item.save(update_fields=['valor'])
        nf_item.refresh_from_db()
        return nf, nf_item

    def test_salvar_conferencia_sem_mudanca_itens_retorna_200(self):
        nf, nf_item = self._nf_herdada_com_preco()
        res = self.client.post(
            f'/api/nf-saidas/{nf.pk}/salvar-conferencia/',
            {
                'observacoes_internas': 'ok',
                'itens': [
                    {
                        'id': nf_item.id,
                        'pedido_cliente_numero': '',
                        'pedido_cliente_item': '',
                        'observacao_item': '',
                        'informacao_adicional_item': '',
                    },
                ],
            },
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        self.assertIn('conferencia', res.data)

    def test_mesmo_valor_com_zeros_finais_nao_bloqueia(self):
        nf, nf_item = self._nf_herdada_com_preco(Decimal('1128.1250'))
        ser = NFeSaidaSerializer(
            nf,
            data={
                'itens': [
                    {
                        'id': nf_item.id,
                        'produto_id': nf_item.produto_id,
                        'quantidade': str(nf_item.quantidade),
                        'valor': '1128.125',
                    },
                ],
            },
            partial=True,
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        ser.save()
        nf_item.refresh_from_db()
        self.assertEqual(nf_item.valor, Decimal('1128.1250'))

    def test_alterar_produto_retorna_400(self):
        nf, nf_item = self._nf_herdada_com_preco()
        outro = Produto.objects.create(
            familia=nf_item.produto.familia,
            descricao='Outro produto herdado',
            modo_codigo=Produto.ModoCodigo.MANUAL,
            codigo_completo='HERD-OUTRO',
            unidade='PC',
            ncm='84818200',
        )
        res = self.client.post(
            f'/api/nf-saidas/{nf.pk}/salvar-conferencia/',
            {
                'itens': [
                    {
                        'id': nf_item.id,
                        'produto_id': outro.pk,
                        'quantidade': str(nf_item.quantidade),
                        'valor': str(nf_item.valor),
                    },
                ],
            },
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('itens', res.data)

    def test_alterar_quantidade_retorna_400(self):
        nf, nf_item = self._nf_herdada_com_preco()
        res = self.client.post(
            f'/api/nf-saidas/{nf.pk}/salvar-conferencia/',
            {
                'itens': [
                    {
                        'id': nf_item.id,
                        'produto_id': nf_item.produto_id,
                        'quantidade': str(Decimal(nf_item.quantidade) + 1),
                        'valor': str(nf_item.valor),
                    },
                ],
            },
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('itens', res.data)

    def test_alterar_preco_retorna_400(self):
        nf, nf_item = self._nf_herdada_com_preco()
        res = self.client.post(
            f'/api/nf-saidas/{nf.pk}/salvar-conferencia/',
            {
                'itens': [
                    {
                        'id': nf_item.id,
                        'produto_id': nf_item.produto_id,
                        'quantidade': str(nf_item.quantidade),
                        'valor': str(Decimal(nf_item.valor) + Decimal('0.001')),
                    },
                ],
            },
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('itens', res.data)

    def test_alterar_apenas_transportadora_salva(self):
        nf, _ = self._nf_herdada_com_preco()
        transp = Transportadora.objects.create(razao_social='Transp Herdada', cnpj='12.345.678/0001-90')
        res = self.client.post(
            f'/api/nf-saidas/{nf.pk}/salvar-conferencia/',
            {'transportadora_id': transp.pk},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        nf.refresh_from_db()
        self.assertEqual(nf.transportadora_id, transp.pk)

    def test_alterar_apenas_volumes_salva(self):
        nf, _ = self._nf_herdada_com_preco()
        res = self.client.post(
            f'/api/nf-saidas/{nf.pk}/salvar-conferencia/',
            {
                'quantidade_volumes': 3,
                'peso_bruto': '12.500',
                'peso_liquido': '12.000',
                'especie_volumes': 'CAIXA',
            },
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        nf.refresh_from_db()
        self.assertEqual(nf.quantidade_volumes, 3)
        self.assertEqual(nf.peso_bruto, Decimal('12.500'))
        self.assertEqual(nf.especie_volumes, 'CAIXA')

    def test_alterar_apenas_informacoes_adicionais_salva(self):
        nf, _ = self._nf_herdada_com_preco()
        res = self.client.post(
            f'/api/nf-saidas/{nf.pk}/salvar-conferencia/',
            {
                'informacoes_adicionais': 'Info complementar teste',
                'observacoes_nfe': 'Obs NF',
            },
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        nf.refresh_from_db()
        self.assertEqual(nf.informacoes_adicionais, 'Info complementar teste')
        self.assertEqual(nf.observacoes_nfe, 'Obs NF')

    @mock.patch('apps.fiscal.nfe_saida_prontidao.validar_conferencia_nfe')
    def test_salvar_e_validar_conferencia_retorna_200(self, mock_validar):
        nf, nf_item = self._nf_herdada_com_preco()
        mock_validar.return_value = {
            'mensagem': 'ok',
            'conferencia': {'nfe': {'id': nf.pk}},
            'validacao': {'aprovado': True, 'itens': []},
            'prontidao': {},
        }
        res = self.client.post(
            f'/api/nf-saidas/{nf.pk}/salvar-e-validar-conferencia/',
            {
                'observacoes_internas': 'validar',
                'itens': [
                    {
                        'id': nf_item.id,
                        'produto_id': nf_item.produto_id,
                        'quantidade': str(nf_item.quantidade),
                        'valor': '1128.1250',
                    },
                ],
            },
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        mock_validar.assert_called_once()
