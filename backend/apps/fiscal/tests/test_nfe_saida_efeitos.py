"""NF-e Saída 3.1 — política de efeitos (autorização/cancelamento interno, sem SEFAZ)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Empresa
from apps.comercial.faturamento_pedido_venda import (
    confirmar_faturamento_pedido,
    criar_faturamento_pedido,
    montar_resumo_faturamento,
)
from apps.comercial.models import FaturamentoPedidoVenda, ItemPedidoVenda, PedidoVenda
from apps.fiscal.models import AtendimentoEstoque, EstoqueCorrida, ItemNFeSaida, NFeSaida, NFeSaidaEvento
from apps.fiscal.nfe_saida_efeitos import (
    STATUS_NFE_AUTORIZADA_INTERNA,
    STATUS_NFE_CANCELADA_INTERNA,
    aplicar_efeitos_autorizacao_nfe_saida,
    aplicar_efeitos_cancelamento_nfe_saida,
    avaliar_efeitos_nfe_saida,
)
from apps.fiscal.nfe_saida_from_faturamento import STATUS_NFE_RASCUNHO, gerar_nfe_saida_from_faturamento
from apps.fiscal.nfe_saida_preview import gerar_preview_xml_nfe_saida
from apps.fiscal.validacao_nfe_saida import validar_nfe_saida_para_emissao
from apps.produtos.models import FamiliaProduto, Produto


def _cnpj() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


def _produto() -> Produto:
    suf = uuid.uuid4().hex[:6].upper()
    fam = FamiliaProduto.objects.create(
        codigo_figura=f'E{suf}',
        descricao_base='Fam',
        tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
        categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
    )
    return Produto.objects.create(
        familia=fam,
        descricao='Prod Efeitos',
        modo_codigo=Produto.ModoCodigo.MANUAL,
        codigo_completo=f'EF-{suf}',
        unidade='PC',
        ncm='84818200',
    )


def _pedido_item(*, qtd=Decimal('10'), preco=Decimal('100')) -> tuple[PedidoVenda, ItemPedidoVenda]:
    emp = Empresa.objects.create(razao_social='Emit', cnpj=_cnpj(), uf='SP')
    cli = Cliente.objects.create(razao_social='Cli', cnpj=_cnpj(), uf='RJ')
    pedido = PedidoVenda.objects.create(
        numero=f'PV-{uuid.uuid4().hex[:6]}',
        empresa_emitente=emp,
        cliente=cli,
        data=date.today(),
        status='ABERTO',
        valor_total=qtd * preco,
    )
    prod = _produto()
    item = ItemPedidoVenda.objects.create(
        pedido=pedido,
        produto=prod,
        quantidade=qtd,
        quantidade_negociada=qtd,
        valor_unitario=preco,
        preco_por_unidade_negociada=preco,
        snapshot_fiscal={'origem_regra_fiscal_saida': 'LEGADO', 'ncm': '84818200', 'cfop': '5102'},
    )
    return pedido, item


def _faturamento_total(pedido: PedidoVenda, item: ItemPedidoVenda, qtd: str = '10') -> FaturamentoPedidoVenda:
    criado = criar_faturamento_pedido(pedido, {'itens': [{'item_pedido_id': item.pk, 'quantidade': qtd}]})
    confirmar_faturamento_pedido(pedido, criado['faturamento_id'])
    return FaturamentoPedidoVenda.objects.get(pk=criado['faturamento_id'])


def _nf_rascunho(pedido: PedidoVenda, fat: FaturamentoPedidoVenda) -> NFeSaida:
    r = gerar_nfe_saida_from_faturamento(pedido, fat.pk)
    return NFeSaida.objects.get(pk=r['nfe_saida_id'])


class NFeSaidaEfeitosTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('nfe_ef', 'nfe_ef@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _fluxo_base(self) -> tuple[PedidoVenda, ItemPedidoVenda, FaturamentoPedidoVenda, NFeSaida]:
        pedido, item = _pedido_item()
        fat = _faturamento_total(pedido, item)
        nf = _nf_rascunho(pedido, fat)
        return pedido, item, fat, nf

    def test_get_efeitos_emissao_rascunho(self):
        pedido, _item, fat, nf = self._fluxo_base()
        url = f'/api/nf-saidas/{nf.pk}/efeitos-emissao/'
        r = self.client.get(url)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        data = r.json()
        self.assertEqual(data['nfe_saida_id'], nf.pk)
        self.assertEqual(data['status'], STATUS_NFE_RASCUNHO)
        self.assertEqual(data['pedido_id'], pedido.pk)
        self.assertEqual(data['faturamento_id'], fat.pk)
        self.assertTrue(data['pode_aplicar_autorizacao'])
        self.assertFalse(data['pode_cancelar'])
        self.assertFalse(data['estoque']['aplicacao_real'])
        self.assertFalse(data['financeiro']['aplicacao_real'])

    def test_autorizacao_interna_registra_evento(self):
        _pedido, _item, _fat, nf = self._fluxo_base()
        aplicar_efeitos_autorizacao_nfe_saida(nf, usuario=self.user, observacao='Teste')
        tipos = list(
            NFeSaidaEvento.objects.filter(nfe_saida=nf).values_list('tipo_evento', flat=True),
        )
        self.assertIn(NFeSaidaEvento.TipoEvento.AUTORIZACAO_EFEITOS_APLICADOS, tipos)

    def test_autorizacao_nao_duplica_quantidade_faturada(self):
        pedido, item, _fat, nf = self._fluxo_base()
        item.refresh_from_db()
        qtd_antes = item.quantidade_faturada
        aplicar_efeitos_autorizacao_nfe_saida(nf, usuario=self.user)
        item.refresh_from_db()
        self.assertEqual(item.quantidade_faturada, qtd_antes)

    def test_autorizacao_mantem_vinculos(self):
        pedido, _item, fat, nf = self._fluxo_base()
        aplicar_efeitos_autorizacao_nfe_saida(nf, usuario=self.user)
        nf.refresh_from_db()
        fat.refresh_from_db()
        self.assertEqual(nf.pedido_venda_id, pedido.pk)
        self.assertEqual(nf.faturamento_pedido_venda_id, fat.pk)
        self.assertEqual(fat.nfe_saida_id, nf.pk)
        self.assertEqual(fat.status, FaturamentoPedidoVenda.Status.GERADO_NFE)

    def test_cancelamento_exige_motivo(self):
        _pedido, _item, _fat, nf = self._fluxo_base()
        aplicar_efeitos_autorizacao_nfe_saida(nf, usuario=self.user)
        url = f'/api/nf-saidas/{nf.pk}/cancelar-interno/'
        r = self.client.post(url, {}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cancelamento_marca_status_interno(self):
        _pedido, _item, _fat, nf = self._fluxo_base()
        aplicar_efeitos_autorizacao_nfe_saida(nf, usuario=self.user)
        aplicar_efeitos_cancelamento_nfe_saida(nf, 'Dados incorretos', usuario=self.user)
        nf.refresh_from_db()
        self.assertEqual(nf.status, STATUS_NFE_CANCELADA_INTERNA)
        self.assertEqual(nf.motivo_cancelamento, 'Dados incorretos')
        self.assertIsNotNone(nf.cancelada_em)

    def test_cancelamento_estorna_quantidade_faturada(self):
        pedido, item, _fat, nf = self._fluxo_base()
        aplicar_efeitos_autorizacao_nfe_saida(nf, usuario=self.user)
        aplicar_efeitos_cancelamento_nfe_saida(nf, 'Estorno teste', usuario=self.user)
        item.refresh_from_db()
        self.assertEqual(item.quantidade_faturada, Decimal('0'))

    def test_cancelamento_recalcula_status_item(self):
        _pedido, item, _fat, nf = self._fluxo_base()
        aplicar_efeitos_autorizacao_nfe_saida(nf, usuario=self.user)
        aplicar_efeitos_cancelamento_nfe_saida(nf, 'Estorno', usuario=self.user)
        item.refresh_from_db()
        self.assertEqual(item.status_item, ItemPedidoVenda.StatusItem.PENDENTE)

    def test_cancelamento_recalcula_status_pedido(self):
        pedido, _item, _fat, nf = self._fluxo_base()
        aplicar_efeitos_autorizacao_nfe_saida(nf, usuario=self.user)
        pedido.refresh_from_db()
        self.assertEqual(pedido.status, 'FATURADO')
        aplicar_efeitos_cancelamento_nfe_saida(nf, 'Estorno', usuario=self.user)
        pedido.refresh_from_db()
        self.assertEqual(pedido.status, 'ABERTO')

    def test_apos_cancelamento_pode_faturar_novamente(self):
        pedido, item, _fat, nf = self._fluxo_base()
        aplicar_efeitos_autorizacao_nfe_saida(nf, usuario=self.user)
        aplicar_efeitos_cancelamento_nfe_saida(nf, 'Liberar saldo', usuario=self.user)
        criado = criar_faturamento_pedido(pedido, {'itens': [{'item_pedido_id': item.pk, 'quantidade': '10'}]})
        self.assertIn('faturamento_id', criado)
        confirmar_faturamento_pedido(pedido, criado['faturamento_id'])
        item.refresh_from_db()
        self.assertEqual(item.quantidade_faturada, Decimal('10'))

    def test_nfe_cancelada_permanece_historico(self):
        pedido, _item, _fat, nf = self._fluxo_base()
        aplicar_efeitos_autorizacao_nfe_saida(nf, usuario=self.user)
        aplicar_efeitos_cancelamento_nfe_saida(nf, 'Histórico', usuario=self.user)
        self.assertTrue(NFeSaida.objects.filter(pk=nf.pk).exists())
        resumo = montar_resumo_faturamento(pedido)
        ids = [h['nfe_saida_id'] for h in resumo['historico_nfe_saida']]
        self.assertIn(nf.pk, ids)
        canceladas = [h for h in resumo['historico_nfe_saida'] if h['status'] == STATUS_NFE_CANCELADA_INTERNA]
        self.assertEqual(len(canceladas), 1)

    def test_segundo_cancelamento_bloqueia(self):
        _pedido, _item, _fat, nf = self._fluxo_base()
        aplicar_efeitos_autorizacao_nfe_saida(nf, usuario=self.user)
        aplicar_efeitos_cancelamento_nfe_saida(nf, 'Primeiro', usuario=self.user)
        with self.assertRaises(ValueError):
            aplicar_efeitos_cancelamento_nfe_saida(nf, 'Segundo', usuario=self.user)

    def test_nao_movimenta_estoque_corrida(self):
        _pedido, _item, _fat, nf = self._fluxo_base()
        antes = EstoqueCorrida.objects.count()
        aplicar_efeitos_autorizacao_nfe_saida(nf, usuario=self.user)
        aplicar_efeitos_cancelamento_nfe_saida(nf, 'Sem estoque', usuario=self.user)
        self.assertEqual(EstoqueCorrida.objects.count(), antes)

    def test_nao_cria_atendimento_estoque(self):
        _pedido, _item, _fat, nf = self._fluxo_base()
        antes = AtendimentoEstoque.objects.count()
        aplicar_efeitos_autorizacao_nfe_saida(nf, usuario=self.user)
        aplicar_efeitos_cancelamento_nfe_saida(nf, 'Sem atendimento', usuario=self.user)
        self.assertEqual(AtendimentoEstoque.objects.count(), antes)

    def test_nao_cria_financeiro(self):
        _pedido, _item, _fat, nf = self._fluxo_base()
        aplicar_efeitos_autorizacao_nfe_saida(nf, usuario=self.user)
        aplicar_efeitos_cancelamento_nfe_saida(nf, 'Sem financeiro', usuario=self.user)
        nf.refresh_from_db()
        self.assertEqual(nf.titulos_receber, [])

    def test_preview_xml_continua_rascunho(self):
        _pedido, _item, _fat, nf = self._fluxo_base()
        prev = gerar_preview_xml_nfe_saida(nf)
        self.assertFalse(prev.get('bloqueado'))
        self.assertTrue(prev.get('xml'))

    def test_validacao_pre_emissao_continua(self):
        _pedido, _item, _fat, nf = self._fluxo_base()
        val = validar_nfe_saida_para_emissao(nf)
        self.assertIn('status_prontidao', val)
        self.assertEqual(val['nfe_saida_id'], nf.pk)

    def test_api_aplicar_autorizacao_interna(self):
        _pedido, _item, _fat, nf = self._fluxo_base()
        url = f'/api/nf-saidas/{nf.pk}/aplicar-efeitos-autorizacao-interna/'
        r = self.client.post(url, {'observacao': 'API sim'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.json()['status'], STATUS_NFE_AUTORIZADA_INTERNA)

    def test_get_eventos_vazio(self):
        _pedido, _item, _fat, nf = self._fluxo_base()
        r = self.client.get(f'/api/nf-saidas/{nf.pk}/eventos/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        data = r.json()
        self.assertEqual(data['nfe_saida_id'], nf.pk)
        self.assertEqual(data['eventos'], [])

    def test_get_eventos_apos_autorizacao_e_cancelamento(self):
        _pedido, _item, _fat, nf = self._fluxo_base()
        aplicar_efeitos_autorizacao_nfe_saida(nf, usuario=self.user, observacao='Auth')
        nf.refresh_from_db()
        aplicar_efeitos_cancelamento_nfe_saida(nf, 'Motivo teste eventos', usuario=self.user)
        r = self.client.get(f'/api/nf-saidas/{nf.pk}/eventos/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        eventos = r.json()['eventos']
        self.assertGreaterEqual(len(eventos), 2)
        tipos = {e['tipo_evento'] for e in eventos}
        self.assertIn(NFeSaidaEvento.TipoEvento.AUTORIZACAO_EFEITOS_APLICADOS, tipos)
        self.assertIn(NFeSaidaEvento.TipoEvento.CANCELAMENTO_EFEITOS_APLICADOS, tipos)
        self.assertTrue(eventos[0]['criado_em'] >= eventos[-1]['criado_em'])

    def test_historico_pedido_inclui_motivo_cancelamento(self):
        pedido, item, _fat, nf = self._fluxo_base()
        aplicar_efeitos_autorizacao_nfe_saida(nf, usuario=self.user)
        nf.refresh_from_db()
        aplicar_efeitos_cancelamento_nfe_saida(nf, 'Erro de digitação', usuario=self.user)
        resumo = montar_resumo_faturamento(pedido)
        row = next(h for h in resumo['historico_nfe_saida'] if h['nfe_saida_id'] == nf.pk)
        self.assertEqual(row['motivo_cancelamento'], 'Erro de digitação')
        self.assertIsNotNone(row['efeitos_cancelamento_aplicados_em'])
        item.refresh_from_db()
        self.assertEqual(item.quantidade_faturada, Decimal('0'))

    def test_avaliar_apos_autorizacao_pode_cancelar(self):
        _pedido, _item, _fat, nf = self._fluxo_base()
        aplicar_efeitos_autorizacao_nfe_saida(nf, usuario=self.user)
        nf.refresh_from_db()
        pol = avaliar_efeitos_nfe_saida(nf)
        self.assertFalse(pol['pode_aplicar_autorizacao'])
        self.assertTrue(pol['pode_cancelar'])
