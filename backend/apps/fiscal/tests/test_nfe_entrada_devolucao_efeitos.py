"""Sprint 3.9 — efeitos ERP de uma NF-e de devolução (finNFe=4) autorizada na SEFAZ.

Cobre o incidente de produção: nota autorizada, pedido travado como faturado, título em
aberto e estoque sem as mercadorias de volta — e o isolamento que impede que um erro
nesses efeitos reverta uma autorização irreversível da SEFAZ.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import TestCase

from apps.cadastros.models import Fornecedor
from apps.comercial.faturamento_pedido_venda import recalcular_status_pedido
from apps.comercial.models import FaturamentoPedidoVenda, ItemPedidoVenda
from apps.corridas.models import Corrida
from apps.financeiro.constants import FormaPagamentoCodigo, TipoMovimentoFinanceiro
from apps.financeiro.models import BaixaFinanceira, CreditoFinanceiro, TituloFinanceiro
from apps.financeiro.services.baixa import registrar_baixa_financeira
from apps.financeiro.services.titulo import criar_titulo_financeiro
from apps.fiscal.models import EstoqueCorrida, NFeEntrada
from apps.fiscal.nfe_entrada_devolucao_efeitos import (
    aplicar_efeitos_devolucao_pos_autorizacao,
    listar_devolucoes_com_efeitos_pendentes,
)
from apps.fiscal.nfe_entrada_emissao.aplicar_resultado import (
    aplicar_resultado_sefaz_producao_entrada,
)
from apps.fiscal.nfe_entrada_from_saida_devolucao import gerar_entrada_devolucao_from_nfe_saida
from apps.fiscal.nfe_emissao.retorno_sefaz import (
    DadosLoteSefaz,
    DadosProtocoloNFe,
    ResultadoAutorizacaoSefaz,
)
from apps.fiscal.tests.test_nfe_saida_402_emissao_homologacao import _pedido_nf
from apps.fiscal.tests.test_nfe_saida_cancelamento_sefaz import _autorizar_homolog

# O fixture _pedido_nf() fatura 4 un x R$ 100.
VALOR_NOTA = Decimal('400.00')
# A devolução exige chave de acesso íntegra (44 dígitos); a do _autorizar_homolog tem 43.
CHAVE_AUTORIZADA = '35260503999102000150550000000009912345678901'
# Número fiscal que a entrada recebe na emissão, antes da autorização.
ENTRADA_NUMERO_NFE = '000000101'
_QUANTADOR_CNPJ = [0]


def _fornecedor(razao: str) -> Fornecedor:
    _QUANTADOR_CNPJ[0] += 1
    return Fornecedor.objects.create(
        razao_social=razao,
        cnpj=f'97.123.450/0001-{_QUANTADOR_CNPJ[0]:02d}',
    )


def _resultado_autorizado(nf: NFeEntrada) -> ResultadoAutorizacaoSefaz:
    """O objeto que `transmitir_nfe_producao` devolve numa autorização concedida."""
    return ResultadoAutorizacaoSefaz(
        status_final='AUTORIZADA',
        autorizado=True,
        rejeitado=False,
        lote=DadosLoteSefaz(c_stat='104', x_motivo='Lote processado'),
        nfe=DadosProtocoloNFe(
            c_stat='100',
            x_motivo='Autorizado o uso da NF-e',
            protocolo='1352600000000001',
            ch_nfe=nf.chave_acesso,
            dh_recbto='2026-10-05T10:00:00-03:00',
        ),
        xml_retorno_lote='<retEnviNFe/>',
        xml_protocolo='<nfeProc/>',
        xml_autorizado='<nfeProc><NFe/></nfeProc>',
    )


class _DevolucaoBaseTests(TestCase):
    """Fixture comum: pedido faturado → nota autorizada → rascunho de devolução."""

    def setUp(self):
        self.user = get_user_model().objects.create_user('dev39', 'dev39@test.com', 'x')
        self.pedido, self.item_pedido, self.nf_saida = _pedido_nf()
        self.nf_saida = _autorizar_homolog(self.nf_saida)
        self.nf_saida.chave_acesso = CHAVE_AUTORIZADA
        self.nf_saida.save(update_fields=['chave_acesso'])
        # Saída autorizada e ainda sem devolução é 'ativa': o status fiscal empurra o pedido.
        recalcular_status_pedido(self.pedido)
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.status, 'FATURADO')
        self.produto = self.item_pedido.produto

    # ------------------------------------------------------------------ helpers

    def _entrada_autorizada(self) -> NFeEntrada:
        """Rascunho de devolução gerado da saída e autorizado, como faria o fluxo SEFAZ."""
        entrada = self._entrada_rascunho()
        entrada.numero_nfe = ENTRADA_NUMERO_NFE
        entrada.status_emissao_sefaz = NFeEntrada.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO
        entrada.status_operacional = NFeEntrada.StatusOperacional.AUTORIZADA_HOMOLOGACAO
        entrada.save(update_fields=['numero_nfe', 'status_emissao_sefaz', 'status_operacional'])
        return entrada

    def _entrada_rascunho(self) -> NFeEntrada:
        res = gerar_entrada_devolucao_from_nfe_saida(self.nf_saida, usuario=self.user)
        return NFeEntrada.objects.get(pk=res['nf_entrada_id'])

    def _autorizar_pelo_servico(self, entrada: NFeEntrada) -> NFeEntrada:
        """Aplica o retorno pela função real, no mesmo `atomic` de servico_producao.py:230."""
        with self.captureOnCommitCallbacks(execute=True):
            with transaction.atomic():
                aplicar_resultado_sefaz_producao_entrada(
                    entrada,
                    _resultado_autorizado(entrada),
                    empresa=entrada.empresa_emitente,
                    usuario=self.user,
                )
        return NFeEntrada.objects.get(pk=entrada.pk)

    def _corrida_original(self, saldo: Decimal) -> Corrida:
        """Lote de origem do material, com estoque, vinculado ao item da saída."""
        corrida = self._corrida(f'LOT-AUTORIZADA-{self.produto.pk}', com_estoque=saldo)
        item_saida = self.nf_saida.itens.first()
        item_saida.corrida = corrida
        item_saida.save(update_fields=['corrida'])
        return corrida

    def _titulo(self, valor: Decimal) -> TituloFinanceiro:
        return criar_titulo_financeiro(
            tipo=TituloFinanceiro.Tipo.RECEBER,
            cliente_id=self.nf_saida.cliente_id,
            data_emissao=self.nf_saida.data,
            data_vencimento=self.nf_saida.data,
            valor_original=valor,
            origem_tipo=TituloFinanceiro.OrigemTipo.NFE_SAIDA,
            origem_id=self.nf_saida.pk,
            origem_numero=str(self.nf_saida.numero_nfe),
            usuario=self.user,
        )

    def _corrida(self, numero: str, *, com_estoque: Decimal | None = None) -> Corrida:
        corrida = Corrida.objects.create(
            numero=numero,
            produto=self.produto,
            fornecedor=_fornecedor(f'Fundição {numero}'),
            data_recebimento=date(2026, 9, 1),
        )
        if com_estoque is not None:
            EstoqueCorrida.objects.create(produto=self.produto, corrida=corrida, saldo=com_estoque)
        return corrida

    def _saldo(self, corrida: Corrida) -> Decimal:
        ec = EstoqueCorrida.objects.filter(produto=self.produto, corrida=corrida).first()
        return Decimal(str(ec.saldo)) if ec else Decimal('0')

    def _faturamento(self) -> FaturamentoPedidoVenda:
        return FaturamentoPedidoVenda.objects.get(pk=self.nf_saida.faturamento_pedido_venda_id)


class DevolucaoVendaEfeitosTests(_DevolucaoBaseTests):
    """Os três efeitos do ciclo: pedido liberado, título abatido, estoque creditado."""

    # ------------------------------------------------------- 1. Pedido de Venda

    def test_pedido_volta_para_aberto_e_item_para_pendente(self):
        entrada = self._entrada_autorizada()
        self.item_pedido.refresh_from_db()
        self.assertEqual(self.item_pedido.status_item, ItemPedidoVenda.StatusItem.FATURADO)
        self.assertEqual(self.pedido.status, 'FATURADO')

        res = aplicar_efeitos_devolucao_pos_autorizacao(entrada, usuario=self.user)

        self.assertTrue(res['aplicado'], res.get('motivo'))
        self.assertEqual(res['pedidos_afetados'], [self.pedido.pk])
        self.item_pedido.refresh_from_db()
        self.pedido.refresh_from_db()
        self.assertEqual(self.item_pedido.quantidade_faturada, Decimal('0.000'))
        self.assertEqual(self.item_pedido.status_item, ItemPedidoVenda.StatusItem.PENDENTE)
        self.assertEqual(self.pedido.status, 'ABERTO')

    def test_libera_faturamento_sem_apagar_vinculos(self):
        entrada = self._entrada_autorizada()
        item_fat_id = self.nf_saida.itens.first().item_faturamento_pedido_id
        self.assertIsNotNone(item_fat_id)

        aplicar_efeitos_devolucao_pos_autorizacao(entrada, usuario=self.user)

        fat = self._faturamento()
        self.assertEqual(fat.status, FaturamentoPedidoVenda.Status.PRONTO_PARA_NFE)
        self.assertIsNone(fat.nfe_saida_id)
        # A trilha fiscal da nota autorizada permanece: nada foi apagado.
        self.assertTrue(fat.itens.filter(pk=item_fat_id).exists())
        self.nf_saida.itens.first().refresh_from_db()
        self.assertEqual(self.nf_saida.itens.first().item_faturamento_pedido_id, item_fat_id)

    def test_pedido_reabre_porque_a_devolucao_ja_esta_autorizada(self):
        """Ordem importa: com a entrada ainda em rascunho a saída segue 'ativa' e o override fiscal mantém FATURADO."""
        res = gerar_entrada_devolucao_from_nfe_saida(self.nf_saida, usuario=self.user)
        entrada_rascunho = NFeEntrada.objects.get(pk=res['nf_entrada_id'])

        aplicar_efeitos_devolucao_pos_autorizacao(entrada_rascunho, usuario=self.user)

        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.status, 'FATURADO')

    # -------------------------------------------------------------- 2. Financeiro

    def test_titulo_recebe_abatimento_e_fica_com_saldo_zero(self):
        entrada = self._entrada_autorizada()
        titulo = self._titulo(VALOR_NOTA)

        res = aplicar_efeitos_devolucao_pos_autorizacao(entrada, usuario=self.user)

        titulo.refresh_from_db()
        self.assertEqual(res['financeiro']['status'], 'aplicado')
        self.assertEqual(res['financeiro']['abatido'], '400.00')
        self.assertEqual(titulo.valor_aberto, Decimal('0.00'))
        self.assertEqual(titulo.status, TituloFinanceiro.Status.RECEBIDO)
        baixas = BaixaFinanceira.objects.filter(
            titulo=titulo,
            tipo_movimento=TipoMovimentoFinanceiro.ABATIMENTO_DEVOLUCAO,
        )
        self.assertEqual(baixas.count(), 1)
        self.assertEqual(baixas.first().valor, VALOR_NOTA)
        self.assertIsNone(res['financeiro']['credito_id'])

    def test_titulo_ja_recebido_vira_credito_do_cliente(self):
        entrada = self._entrada_autorizada()
        titulo = self._titulo(VALOR_NOTA)
        registrar_baixa_financeira(
            titulo,
            data_baixa=date.today(),
            valor=VALOR_NOTA,
            forma_pagamento_codigo=FormaPagamentoCodigo.SEM_MOVIMENTACAO_FINANCEIRA,
            usuario=self.user,
        )
        titulo.refresh_from_db()
        self.assertFalse(titulo.pode_baixar)

        res = aplicar_efeitos_devolucao_pos_autorizacao(entrada, usuario=self.user)

        self.assertEqual(res['financeiro']['abatido'], '0')
        self.assertEqual(res['financeiro']['credito_valor'], '400.00')
        credito = CreditoFinanceiro.objects.get(pk=res['financeiro']['credito_id'])
        self.assertEqual(credito.tipo, CreditoFinanceiro.Tipo.CLIENTE)
        self.assertEqual(credito.cliente_id, self.nf_saida.cliente_id)
        self.assertEqual(credito.origem_tipo, CreditoFinanceiro.OrigemTipo.DEVOLUCAO)
        self.assertEqual(credito.saldo, VALOR_NOTA)
        self.assertEqual(credito.status, CreditoFinanceiro.Status.DISPONIVEL)

    def test_abate_ate_o_saldo_e_converte_a_sobra_em_credito(self):
        entrada = self._entrada_autorizada()
        titulo = self._titulo(Decimal('250.00'))

        res = aplicar_efeitos_devolucao_pos_autorizacao(entrada, usuario=self.user)

        titulo.refresh_from_db()
        self.assertEqual(res['financeiro']['abatido'], '250.00')
        self.assertEqual(res['financeiro']['credito_valor'], '150.00')
        self.assertEqual(titulo.valor_aberto, Decimal('0.00'))
        credito = CreditoFinanceiro.objects.get(pk=res['financeiro']['credito_id'])
        self.assertEqual(credito.valor_original, Decimal('150.00'))

    def test_saida_sem_titulos_nao_fabrica_credito(self):
        """Homologação não gera contas a receber: sem título, o financeiro fica intocado."""
        entrada = self._entrada_autorizada()

        res = aplicar_efeitos_devolucao_pos_autorizacao(entrada, usuario=self.user)

        self.assertEqual(res['financeiro']['status'], 'sem_titulo')
        self.assertIsNone(res['financeiro']['credito_id'])
        self.assertFalse(CreditoFinanceiro.objects.exists())

    def test_distribui_devolucao_entre_dois_titulos(self):
        entrada = self._entrada_autorizada()
        primeiro = self._titulo(Decimal('150.00'))
        segundo = self._titulo(Decimal('250.00'))

        res = aplicar_efeitos_devolucao_pos_autorizacao(entrada, usuario=self.user)

        primeiro.refresh_from_db()
        segundo.refresh_from_db()
        self.assertEqual(res['financeiro']['abatido'], '400.00')
        self.assertEqual(primeiro.valor_aberto, Decimal('0.00'))
        self.assertEqual(segundo.valor_aberto, Decimal('0.00'))
        self.assertIsNone(res['financeiro']['credito_id'])

    # ----------------------------------------------------------------- 3. Estoque

    def test_estoque_credita_na_corrida_original(self):
        corrida = self._corrida('LOT-ORIG-01', com_estoque=Decimal('2.000'))
        item_saida = self.nf_saida.itens.first()
        item_saida.corrida = corrida
        item_saida.save(update_fields=['corrida'])
        entrada = self._entrada_autorizada()

        res = aplicar_efeitos_devolucao_pos_autorizacao(entrada, usuario=self.user)

        self.assertEqual(self._saldo(corrida), Decimal('6.000'))
        creditado = res['estoque']['creditados'][0]
        self.assertEqual(creditado['corrida_id'], corrida.pk)
        self.assertFalse(creditado['creditado_sem_corrida_original'])
        self.assertEqual(res['estoque']['pendentes'], [])

    def test_sem_corrida_original_abre_corrida_de_devolucao(self):
        fornecedor_base = self._corrida('LOT-SEM-VINCO-01').fornecedor
        entrada = self._entrada_autorizada()
        self.assertIsNone(entrada.itens.first().corrida_id)

        res = aplicar_efeitos_devolucao_pos_autorizacao(entrada, usuario=self.user)

        creditado = res['estoque']['creditados'][0]
        self.assertTrue(creditado['creditado_sem_corrida_original'])
        self.assertEqual(creditado['fornecedor_origem'], 'corrida_do_produto')
        nova = Corrida.objects.get(pk=creditado['corrida_id'])
        self.assertEqual(nova.numero, f'DEV-{ENTRADA_NUMERO_NFE}-{self.produto.pk}')
        self.assertEqual(nova.nf_entrada, ENTRADA_NUMERO_NFE)
        self.assertEqual(nova.fornecedor_id, fornecedor_base.pk)
        self.assertEqual(nova.produto_id, self.produto.pk)
        self.assertEqual(nova.data_recebimento, date.today())
        self.assertEqual(self._saldo(nova), Decimal('4.000'))

    def test_sem_fornecedor_resolvivel_item_fica_pendente_sem_travar_o_resto(self):
        entrada = self._entrada_autorizada()
        titulo = self._titulo(VALOR_NOTA)

        res = aplicar_efeitos_devolucao_pos_autorizacao(entrada, usuario=self.user)

        self.assertEqual(res['estoque']['creditados'], [])
        self.assertEqual(len(res['estoque']['pendentes']), 1)
        self.assertIn('fornecedor', res['estoque']['pendentes'][0]['motivo'].lower())
        # Os outros efeitos continuam valendo mesmo sem rastreabilidade de lote.
        self.pedido.refresh_from_db()
        titulo.refresh_from_db()
        self.assertEqual(self.pedido.status, 'ABERTO')
        self.assertEqual(titulo.valor_aberto, Decimal('0.00'))

    # ---------------------------------------------------------- 4. Guarda/guarda

    def test_nao_aplica_em_entrada_que_nao_e_devolucao(self):
        entrada = self._entrada_autorizada()
        entrada.fin_nfe = '1'
        entrada.save(update_fields=['fin_nfe'])

        res = aplicar_efeitos_devolucao_pos_autorizacao(entrada, usuario=self.user)

        self.assertFalse(res['aplicado'])
        self.assertIn('finNFe', res['motivo'])
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.status, 'FATURADO')

    def test_nao_aplica_sem_saida_de_origem(self):
        entrada = self._entrada_autorizada()
        entrada.nfe_saida_origem_id = None
        entrada.save(update_fields=['nfe_saida_origem'])

        res = aplicar_efeitos_devolucao_pos_autorizacao(entrada, usuario=self.user)

        self.assertFalse(res['aplicado'])
        self.assertEqual(res['motivo'], 'Sem nfe_saida_origem.')

    def test_idempotente_reprocessar_nao_dobra_nada(self):
        """Um reprocessamento do mesmo retorno SEFAZ não pode creditar estoque duas vezes."""
        corrida = self._corrida('LOT-IDEMP-01', com_estoque=Decimal('2.000'))
        item_saida = self.nf_saida.itens.first()
        item_saida.corrida = corrida
        item_saida.save(update_fields=['corrida'])
        entrada = self._entrada_autorizada()
        titulo = self._titulo(VALOR_NOTA)

        primeiro = aplicar_efeitos_devolucao_pos_autorizacao(entrada, usuario=self.user)
        saldo_uma_vez = self._saldo(corrida)
        segundo = aplicar_efeitos_devolucao_pos_autorizacao(
            NFeEntrada.objects.get(pk=entrada.pk),
            usuario=self.user,
        )

        self.assertTrue(primeiro['aplicado'])
        self.assertEqual(saldo_uma_vez, Decimal('6.000'))
        self.assertFalse(segundo['aplicado'])
        self.assertEqual(segundo['motivo'], 'Já aplicado antes.')
        self.assertEqual(self._saldo(corrida), Decimal('6.000'))
        titulo.refresh_from_db()
        self.assertEqual(titulo.valor_aberto, Decimal('0.00'))
        self.assertEqual(
            BaixaFinanceira.objects.filter(
                tipo_movimento=TipoMovimentoFinanceiro.ABATIMENTO_DEVOLUCAO,
            ).count(),
            1,
        )
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.status, 'ABERTO')
        self.assertEqual(CreditoFinanceiro.objects.count(), 0)


class DevolucaoEfeitosIsoladosDaAutorizacaoTests(_DevolucaoBaseTests):
    """A autorização SEFAZ é irreversível: erro em pedido/estoque/financeiro não a desfaz.

    `servico_producao.py:230` embrulha a aplicação do retorno num `transaction.atomic()`.
    Se os efeitos corressem ali dentro, uma falha de estoque ou financeiro rollbackaria o
    status "Autorizada" — o ERP divergiria da SEFAZ, que é a classe do incidente.
    """

    def test_autorizacao_em_producao_aplica_efeitos_apos_o_commit(self):
        # A corrida precisa estar no item da SAÍDA antes de o rascunho ser gerado.
        corrida = self._corrida_original(Decimal('2.000'))
        entrada = self._entrada_rascunho()
        titulo = self._titulo(VALOR_NOTA)

        autorizada = self._autorizar_pelo_servico(entrada)

        self.assertEqual(
            autorizada.status_emissao_sefaz,
            NFeEntrada.StatusEmissaoSefaz.AUTORIZADA_PRODUCAO,
        )
        self.assertEqual(
            autorizada.status_operacional,
            NFeEntrada.StatusOperacional.AUTORIZADA_PRODUCAO,
        )
        self.assertEqual(autorizada.protocolo_autorizacao, '1352600000000001')
        # Efeitos aplicados depois do commit da autorização.
        self.pedido.refresh_from_db()
        self.item_pedido.refresh_from_db()
        titulo.refresh_from_db()
        self.assertIsNotNone(autorizada.efeitos_devolucao_aplicados_em)
        self.assertEqual(autorizada.efeitos_devolucao_por_id, self.user.pk)
        self.assertEqual(self.pedido.status, 'ABERTO')
        self.assertEqual(self.item_pedido.quantidade_faturada, Decimal('0.000'))
        self.assertEqual(titulo.valor_aberto, Decimal('0.00'))
        self.assertEqual(self._saldo(corrida), Decimal('6.000'))
        self.assertNotIn(autorizada, listar_devolucoes_com_efeitos_pendentes())

    def test_efeitos_rodam_somente_depois_do_commit_da_autorizacao(self):
        corrida = self._corrida_original(Decimal('2.000'))
        entrada = self._entrada_rascunho()

        with self.captureOnCommitCallbacks() as callbacks:
            with transaction.atomic():
                aplicar_resultado_sefaz_producao_entrada(
                    entrada,
                    _resultado_autorizado(entrada),
                    empresa=entrada.empresa_emitente,
                    usuario=self.user,
                )
                # Dentro da transação: status gravado, nenhum efeito aplicado ainda.
                self.assertEqual(
                    entrada.status_emissao_sefaz,
                    NFeEntrada.StatusEmissaoSefaz.AUTORIZADA_PRODUCAO,
                )
                self.assertEqual(self._saldo(corrida), Decimal('2.000'))
                self.pedido.refresh_from_db()
                self.assertEqual(self.pedido.status, 'FATURADO')

        # O callback só é capturado ao sair do bloco: nada rodou junto com a autorização.
        self.assertEqual(len(callbacks), 1)
        callbacks[0]()

        self.assertEqual(self._saldo(corrida), Decimal('6.000'))
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.status, 'ABERTO')

    def test_falha_no_estoque_mantem_autorizada_e_marca_pendencia(self):
        corrida = self._corrida_original(Decimal('2.000'))
        entrada = self._entrada_rascunho()
        titulo = self._titulo(VALOR_NOTA)

        with self.assertLogs(
            'apps.fiscal.nfe_entrada_emissao.aplicar_resultado',
            level='ERROR',
        ) as logs:
            with patch(
                'apps.fiscal.estoque_services.aplicar_entrada_item',
                side_effect=RuntimeError('boom no estoque'),
            ):
                autorizada = self._autorizar_pelo_servico(entrada)

        # A nota não volta para rascunho nem perde o protocolo.
        self.assertEqual(
            autorizada.status_emissao_sefaz,
            NFeEntrada.StatusEmissaoSefaz.AUTORIZADA_PRODUCAO,
        )
        self.assertEqual(
            autorizada.status_operacional,
            NFeEntrada.StatusOperacional.AUTORIZADA_PRODUCAO,
        )
        self.assertTrue(autorizada.xml_autorizado)
        self.assertEqual(autorizada.protocolo_autorizacao, '1352600000000001')
        self.assertIn('DEVOLUCAO_EFEITOS_FALHARAM', logs.output[0])
        # Nada ficou pela metade: o estorno do mesmo atomic foi desfeito.
        self.assertIsNone(autorizada.efeitos_devolucao_aplicados_em)
        self.item_pedido.refresh_from_db()
        self.pedido.refresh_from_db()
        titulo.refresh_from_db()
        self.assertEqual(self.item_pedido.quantidade_faturada, Decimal('4.000'))
        self.assertEqual(self.pedido.status, 'FATURADO')
        self.assertEqual(self._faturamento().nfe_saida_id, self.nf_saida.pk)
        self.assertEqual(self._saldo(corrida), Decimal('2.000'))
        self.assertEqual(titulo.valor_aberto, VALOR_NOTA)
        # Fica na fila de reparo.
        self.assertIn(
            autorizada.pk,
            list(listar_devolucoes_com_efeitos_pendentes().values_list('pk', flat=True)),
        )

    def test_falha_no_financeiro_desfaz_o_credito_de_estoque_ja_feito(self):
        corrida = self._corrida_original(Decimal('2.000'))
        entrada = self._entrada_rascunho()
        self._titulo(VALOR_NOTA)

        with self.assertLogs(
            'apps.fiscal.nfe_entrada_emissao.aplicar_resultado',
            level='ERROR',
        ):
            with patch(
                'apps.financeiro.services.movimento.registrar_abatimento_devolucao',
                side_effect=RuntimeError('boom no financeiro'),
            ):
                autorizada = self._autorizar_pelo_servico(entrada)

        self.assertEqual(
            autorizada.status_emissao_sefaz,
            NFeEntrada.StatusEmissaoSefaz.AUTORIZADA_PRODUCAO,
        )
        self.assertIsNone(autorizada.efeitos_devolucao_aplicados_em)
        # O estoque creditou antes de a exceção subir; o atomic do orquestrador desfez.
        self.assertEqual(self._saldo(corrida), Decimal('2.000'))
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.status, 'FATURADO')

    def test_replicar_efeitos_da_fila_apos_conserto_aplica_tudo(self):
        """A fila é acionável: reprocessar a nota travada fecha o ciclo sem duplicar nada."""
        corrida = self._corrida_original(Decimal('2.000'))
        entrada = self._entrada_rascunho()
        self._titulo(VALOR_NOTA)

        with self.assertLogs(
            'apps.fiscal.nfe_entrada_emissao.aplicar_resultado',
            level='ERROR',
        ):
            with patch(
                'apps.fiscal.estoque_services.aplicar_entrada_item',
                side_effect=RuntimeError('boom no estoque'),
            ):
                travada = self._autorizar_pelo_servico(entrada)

        fila = list(listar_devolucoes_com_efeitos_pendentes())
        self.assertEqual([nf.pk for nf in fila], [travada.pk])

        res = aplicar_efeitos_devolucao_pos_autorizacao(fila[0], usuario=self.user)

        self.assertTrue(res['aplicado'])
        self.assertEqual(self._saldo(corrida), Decimal('6.000'))
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.status, 'ABERTO')
        self.assertEqual(BaixaFinanceira.objects.count(), 1)
        self.assertEqual(list(listar_devolucoes_com_efeitos_pendentes()), [])

    def test_entrada_que_nao_e_devolucao_nao_agenda_efeitos(self):
        entrada = self._entrada_rascunho()
        entrada.fin_nfe = '1'
        entrada.save(update_fields=['fin_nfe'])

        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            autorizada = aplicar_resultado_sefaz_producao_entrada(
                entrada,
                _resultado_autorizado(entrada),
                empresa=entrada.empresa_emitente,
                usuario=self.user,
            )

        self.assertEqual(callbacks, [])
        self.assertEqual(
            autorizada.status_emissao_sefaz,
            NFeEntrada.StatusEmissaoSefaz.AUTORIZADA_PRODUCAO,
        )
        self.assertIsNone(autorizada.efeitos_devolucao_aplicados_em)
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.status, 'FATURADO')
