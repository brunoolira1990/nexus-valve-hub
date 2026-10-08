"""Reparo de status comercial de proposta após exclusão de pedido pré-hotfix."""

from __future__ import annotations

from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.comercial.commercial_defaults import (
    STATUS_ITEM_CONVERTIDO,
    STATUS_ITEM_PENDENTE,
    STATUS_PROPOSTA_CONVERTIDA,
)
from apps.comercial.converter_proposta_pedido import (
    converter_proposta_em_pedido_venda,
    gerar_pedido_venda_de_proposta,
)
from apps.comercial.faturamento_pedido_venda import criar_faturamento_pedido
from apps.comercial.models import PedidoVenda, PropostaComercialHistorico
from apps.comercial.pedido_venda_exclusao import excluir_pedido_venda
from apps.comercial.proposta_comercial_status import item_pode_converter, status_item_proposta
from apps.comercial.reparar_status_comercial_proposta import (
    CONFIRMACAO_TOKEN,
    analisar_reparo_status_comercial_proposta,
    executar_reparo_status_comercial_proposta,
)
from apps.comercial.tests.test_converter_proposta_pedido import (
    _item,
    _produto,
    _proposta_aprovada,
)


def _simular_exclusao_pre_hotfix(pedido: PedidoVenda) -> None:
    """Exclui pedido sem reverter itens da proposta (cenário anterior ao hotfix)."""
    pedido.delete()


class RepararStatusComercialPropostaTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('rep_prop', 'rep@test.com', 'x')

    def _proposta_com_item_preso(self):
        p = _proposta_aprovada()
        prod = _produto()
        item = _item(p, prod)
        item.snapshot_produto = {'fiscal_teste': {'icms': '18'}}
        item.save(update_fields=['snapshot_produto'])
        r = converter_proposta_em_pedido_venda(p)
        pedido = PedidoVenda.objects.get(pk=r['pedido_id'])
        pedido_id = pedido.pk
        pedido_numero = pedido.numero
        _simular_exclusao_pre_hotfix(pedido)
        item.refresh_from_db()
        p.refresh_from_db()
        self.assertEqual(item.status_comercial, STATUS_ITEM_CONVERTIDO)
        self.assertIsNone(item.pedido_venda_gerado_id)
        return p, item, pedido_id, pedido_numero

    def _proposta_convertida_com_itens_pendentes(self):
        """Simula proposta presa: status CONVERTIDA, itens já PENDENTES, sem pedidos."""
        p = _proposta_aprovada()
        item1 = _item(p, _produto())
        item2 = _item(p, _produto())
        r = converter_proposta_em_pedido_venda(p)
        excluir_pedido_venda(PedidoVenda.objects.get(pk=r['pedido_id']), usuario=self.user)
        item1.refresh_from_db()
        item2.refresh_from_db()
        p.refresh_from_db()
        self.assertEqual(item1.status_comercial, STATUS_ITEM_PENDENTE)
        self.assertEqual(item2.status_comercial, STATUS_ITEM_PENDENTE)
        p.status = STATUS_PROPOSTA_CONVERTIDA
        p.save(update_fields=['status'])
        return p, item1, item2

    def test_dry_run_repara_status_proposta_convertida_sem_itens_convertidos(self):
        p, item1, item2 = self._proposta_convertida_com_itens_pendentes()

        relatorio = analisar_reparo_status_comercial_proposta(p)

        self.assertTrue(relatorio.reparar_status_proposta)
        self.assertEqual(relatorio.status_novo_previsto, 'Aprovada')
        self.assertNotIn(item1.pk, relatorio.itens_reparaveis)
        self.assertNotIn(item2.pk, relatorio.itens_reparaveis)

    def test_reparo_status_proposta_convertida_sem_itens_convertidos(self):
        p, item1, item2 = self._proposta_convertida_com_itens_pendentes()

        resultado = executar_reparo_status_comercial_proposta(p, usuario=self.user)

        p.refresh_from_db()
        item1.refresh_from_db()
        item2.refresh_from_db()
        self.assertTrue(resultado['status_proposta_reparado'])
        self.assertEqual(resultado['itens_reparados'], [])
        self.assertEqual(p.status, 'Aprovada')
        self.assertEqual(item1.status_comercial, STATUS_ITEM_PENDENTE)
        self.assertEqual(item2.status_comercial, STATUS_ITEM_PENDENTE)

        evt = PropostaComercialHistorico.objects.filter(
            proposta=p,
            tipo_evento=PropostaComercialHistorico.TipoEvento.REPARO_STATUS_COMERCIAL_PEDIDO,
        ).first()
        self.assertIsNotNone(evt)
        self.assertTrue(evt.dados_json['status_proposta_reparado'])

        r2 = converter_proposta_em_pedido_venda(p)
        self.assertTrue(PedidoVenda.objects.filter(pk=r2['pedido_id']).exists())

    def test_management_command_repara_apenas_status_proposta(self):
        p, _, _ = self._proposta_convertida_com_itens_pendentes()
        out = StringIO()

        call_command(
            'reparar_status_comercial_proposta',
            proposta_id=p.pk,
            confirmar=CONFIRMACAO_TOKEN,
            stdout=out,
        )

        p.refresh_from_db()
        self.assertEqual(p.status, 'Aprovada')
        output = out.getvalue()
        self.assertIn('Status da proposta recalculado', output)
        self.assertIn('Reparo concluído', output)

    def test_dry_run_lista_item_orfao(self):
        p, item, pedido_id, pedido_numero = self._proposta_com_item_preso()

        relatorio = analisar_reparo_status_comercial_proposta(p)

        self.assertIn(item.pk, relatorio.itens_reparaveis)
        self.assertEqual(relatorio.status_novo_previsto, 'Aprovada')
        linha = next(l for l in relatorio.linhas if l.item_id == item.pk)
        self.assertEqual(linha.acao, 'reparar')
        self.assertEqual(linha.pedido_id_ref, pedido_id)
        self.assertEqual(linha.pedido_numero_ref, pedido_numero)

    def test_reparo_reverte_item_orfao_e_permite_novo_pedido(self):
        p, item, _, _ = self._proposta_com_item_preso()

        resultado = executar_reparo_status_comercial_proposta(p, usuario=self.user)

        item.refresh_from_db()
        p.refresh_from_db()
        self.assertEqual(len(resultado['itens_reparados']), 1)
        self.assertEqual(item.status_comercial, STATUS_ITEM_PENDENTE)
        self.assertTrue(item_pode_converter(item))
        self.assertEqual((item.snapshot_produto or {}).get('fiscal_teste'), {'icms': '18'})
        self.assertEqual(p.status, 'Aprovada')

        evt = PropostaComercialHistorico.objects.filter(
            proposta=p,
            tipo_evento=PropostaComercialHistorico.TipoEvento.REPARO_STATUS_COMERCIAL_PEDIDO,
        ).first()
        self.assertIsNotNone(evt)
        self.assertEqual(len(evt.dados_json['itens_reparados']), 1)

        r2 = converter_proposta_em_pedido_venda(p)
        self.assertTrue(PedidoVenda.objects.filter(pk=r2['pedido_id']).exists())

    def test_nao_repara_item_com_pedido_vivo(self):
        p = _proposta_aprovada()
        item = _item(p, _produto())
        converter_proposta_em_pedido_venda(p)
        item.refresh_from_db()

        relatorio = analisar_reparo_status_comercial_proposta(p)

        self.assertNotIn(item.pk, relatorio.itens_reparaveis)
        linha = next(l for l in relatorio.linhas if l.item_id == item.pk)
        self.assertEqual(linha.acao, 'ignorar')

    def test_bloqueia_reparo_com_faturamento_no_pedido_vivo(self):
        p = _proposta_aprovada()
        item = _item(p, _produto())
        r = converter_proposta_em_pedido_venda(p)
        pedido = PedidoVenda.objects.get(pk=r['pedido_id'])
        pv_item = pedido.itens.get()
        criar_faturamento_pedido(
            pedido,
            {'itens': [{'item_pedido_id': pv_item.id, 'quantidade': '1'}]},
            usuario=self.user,
        )
        item.refresh_from_db()

        relatorio = analisar_reparo_status_comercial_proposta(p)

        self.assertIn(item.pk, relatorio.itens_bloqueados)
        with self.assertRaises(ValueError):
            executar_reparo_status_comercial_proposta(p, usuario=self.user)

    def test_reparo_parcial_apenas_item_orfao(self):
        p = _proposta_aprovada()
        item1 = _item(p, _produto())
        item2 = _item(p, _produto())
        r1 = gerar_pedido_venda_de_proposta(
            p,
            itens_payload=[{'proposta_item_id': item1.pk}],
            acao_itens_nao_selecionados='MANTER_PENDENTE',
        )
        gerar_pedido_venda_de_proposta(
            p,
            itens_payload=[{'proposta_item_id': item2.pk}],
            acao_itens_nao_selecionados='MANTER_PENDENTE',
        )
        _simular_exclusao_pre_hotfix(PedidoVenda.objects.get(pk=r1['pedido_id']))
        item1.refresh_from_db()
        item2.refresh_from_db()

        executar_reparo_status_comercial_proposta(p, usuario=self.user)

        item1.refresh_from_db()
        item2.refresh_from_db()
        self.assertEqual(status_item_proposta(item1), STATUS_ITEM_PENDENTE)
        self.assertEqual(status_item_proposta(item2), STATUS_ITEM_CONVERTIDO)

    def test_management_command_dry_run(self):
        p, item, _, _ = self._proposta_com_item_preso()
        out = StringIO()

        call_command('reparar_status_comercial_proposta', proposta_id=p.pk, dry_run=True, stdout=out)

        output = out.getvalue()
        self.assertIn('Dry-run', output)
        self.assertIn(str(item.pk), output)
        item.refresh_from_db()
        self.assertEqual(item.status_comercial, STATUS_ITEM_CONVERTIDO)

    def test_management_command_confirmar_executa_reparo(self):
        p, item, _, _ = self._proposta_com_item_preso()
        out = StringIO()

        call_command(
            'reparar_status_comercial_proposta',
            proposta_id=p.pk,
            confirmar=CONFIRMACAO_TOKEN,
            stdout=out,
        )

        item.refresh_from_db()
        self.assertEqual(item.status_comercial, STATUS_ITEM_PENDENTE)
        self.assertIn('Reparo concluído', out.getvalue())

    def test_management_command_token_invalido(self):
        p, _, _, _ = self._proposta_com_item_preso()
        with self.assertRaises(CommandError):
            call_command('reparar_status_comercial_proposta', proposta_id=p.pk, confirmar='INVALIDO')
