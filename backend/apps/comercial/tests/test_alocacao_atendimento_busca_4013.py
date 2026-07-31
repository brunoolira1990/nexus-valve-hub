"""ERP 4.0.13 — busca assistida e validação de vínculos em AlocacaoAtendimento."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Fornecedor, Transportadora
from apps.comercial.models import ItemPedidoCompra, ItemPedidoVenda, PedidoCompra, PedidoVenda
from apps.comercial.services.alocacao_atendimento_busca import (
    buscar_cte_conferido_opcoes,
    buscar_fornecedores_opcoes,
    buscar_nfe_entrada_importada_opcoes,
    buscar_pedidos_compra_opcoes,
)
from apps.comercial.services.alocacao_atendimento_service import (
    AlocacaoAtendimentoErro,
    criar_alocacao_atendimento,
)
from apps.comercial.services.alocacao_atendimento_vinculos import montar_vinculos_exibicao
from apps.fiscal.cte_historico_conferencia import conferir_cte_importado
from apps.fiscal.modelo_operacional import StatusEntradaFiscal, TipoAtendimentoItem
from apps.fiscal.models import (
    AlocacaoAtendimento,
    CTeHistoricoImportado,
    ItemNFeEntradaConferencia,
    ItemNFeEntradaHistoricaImportada,
    NFeEntradaConferencia,
    NFeEntradaHistoricaImportada,
)
from apps.fiscal.models import AtendimentoEstoque, EstoqueCorrida
from apps.produtos.models import FamiliaProduto, Produto


def _produto(suf: str | None = None) -> Produto:
    s = suf or uuid.uuid4().hex[:6]
    fam = FamiliaProduto.objects.create(
        codigo_figura=f'F{s}'[:16],
        descricao_base='Fam',
        tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
        categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
    )
    return Produto.objects.create(
        familia=fam,
        descricao=f'Prod {s}',
        modo_codigo=Produto.ModoCodigo.MANUAL,
        codigo_completo=f'P-{s}',
        unidade='PC',
        ncm='84818099',
    )


class AlocacaoAtendimentoBusca4013Tests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('busca4013', 'b@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.produto = _produto('4013')
        self.produto_b = _produto('4013b')
        self.fornecedor = Fornecedor.objects.create(
            razao_social='Fornecedor Busca 4013',
            nome_fantasia='Forn 4013',
            cnpj='33.333.333/0001-33',
            cidade='São Paulo',
            uf='SP',
        )
        self.cliente = Cliente.objects.create(razao_social='Cli 4013', cnpj='44.444.444/0001-44')
        self.pv = PedidoVenda.objects.create(numero='PV-4013', cliente=self.cliente, data=date.today())
        self.item_pv = ItemPedidoVenda.objects.create(
            pedido=self.pv,
            produto=self.produto,
            quantidade=Decimal('10'),
            valor_unitario=Decimal('50'),
        )
        self.pc = PedidoCompra.objects.create(
            numero='PC-4013-001',
            fornecedor=self.fornecedor,
            data=date.today(),
            valor_total=Decimal('500'),
        )
        self.item_pc = ItemPedidoCompra.objects.create(
            pedido=self.pc,
            produto=self.produto,
            quantidade=Decimal('10'),
            valor_unitario=Decimal('50'),
        )

    def test_buscar_fornecedores_por_nome(self):
        rows = buscar_fornecedores_opcoes({'search': 'Busca 4013'})
        self.assertTrue(any(r['id'] == self.fornecedor.pk for r in rows))

    def test_buscar_pedido_compra_por_numero(self):
        rows = buscar_pedidos_compra_opcoes({'search': 'PC-4013'})
        self.assertEqual(rows[0]['id'], self.pc.pk)
        self.assertIn('Forn 4013', rows[0]['label'])

    def test_endpoint_buscar_fornecedores(self):
        r = self.client.get('/api/alocacoes-atendimento/opcoes/fornecedores/', {'search': 'Busca'})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertTrue(isinstance(r.data, list))

    def _chave_unica(self) -> str:
        return ('35' + uuid.uuid4().hex.replace('-', ''))[:44].ljust(44, '0')

    def _nf_producao(self, *, tp_amb='1', numero='100') -> NFeEntradaHistoricaImportada:
        nf = NFeEntradaHistoricaImportada.objects.create(
            chave_acesso=self._chave_unica(),
            numero=numero,
            serie='1',
            dh_emissao=timezone.now(),
            tp_amb=tp_amb,
            cstat='100',
            valor_total_nf=Decimal('288'),
            fornecedor_emitente=self.fornecedor,
        )
        NFeEntradaConferencia.objects.create(
            nf_entrada_historica=nf,
            status=NFeEntradaConferencia.Status.CONFERIDA,
        )
        return nf

    def _item_conferencia_para_historico(
        self,
        item_nf: ItemNFeEntradaHistoricaImportada,
        *,
        quantidade: Decimal | str = '10',
        item_pedido_compra: ItemPedidoCompra | None = None,
    ) -> ItemNFeEntradaConferencia:
        """Fixture mínima exigida pela Fase 1 (histórica × PV)."""
        conf = NFeEntradaConferencia.objects.get(nf_entrada_historica_id=item_nf.nf_id)
        qtd = Decimal(str(quantidade))
        linha, _ = conf.itens.get_or_create(item_nfe_historico=item_nf)
        linha.produto = self.produto
        linha.quantidade_nf = qtd
        linha.unidade_nf = 'PC'
        linha.quantidade_estoque_calculada = qtd
        linha.unidade_estoque_calculada = 'PC'
        linha.status = ItemNFeEntradaConferencia.Status.CONFERIDO
        if item_pedido_compra is not None:
            linha.item_pedido_compra = item_pedido_compra
        linha.save()
        return linha

    def test_nao_retorna_nfe_homologacao_na_busca(self):
        self._nf_producao(tp_amb='2', numero='999')
        rows = buscar_nfe_entrada_importada_opcoes({'search': '999'})
        self.assertEqual(len(rows), 0)

    def test_buscar_nfe_entrada_producao(self):
        nf = self._nf_producao(numero='12345')
        rows = buscar_nfe_entrada_importada_opcoes({'search': '12345'})
        self.assertEqual(rows[0]['id'], nf.pk)
        self.assertNotIn('xml', str(rows[0]).lower())

    def _payload_conferir_cte(self) -> dict:
        return {
            'observacao': 'Conferido teste 4013',
            'confirmar_tomador': True,
            'confirmar_transportadora': True,
            'confirmar_valores': True,
            'confirmar_documentos_referenciados': True,
        }

    def _cte_conferido(self) -> CTeHistoricoImportado:
        transp = Transportadora.objects.create(
            razao_social='Transp 4013',
            cnpj='55.555.555/0001-55',
        )
        cte = CTeHistoricoImportado.objects.create(
            chave_acesso=self._chave_unica(),
            numero='15708883',
            serie='1',
            dh_emissao=timezone.now(),
            tp_amb='1',
            cstat='100',
            valor_total_servico=Decimal('879.31'),
            transportadora=transp,
            status_conferencia=CTeHistoricoImportado.StatusConferencia.PROCESSADO,
        )
        conferir_cte_importado(cte, self.user, self._payload_conferir_cte())
        cte.refresh_from_db()
        return cte

    def test_buscar_cte_conferido(self):
        cte = self._cte_conferido()
        rows = buscar_cte_conferido_opcoes({'search': '15708883'})
        self.assertTrue(any(r['id'] == cte.pk for r in rows))

    def test_nao_retorna_cte_homologacao(self):
        transp = Transportadora.objects.create(razao_social='T2', cnpj='66.666.666/0001-66')
        CTeHistoricoImportado.objects.create(
            chave_acesso=self._chave_unica(),
            numero='HOMOL',
            serie='1',
            dh_emissao=timezone.now(),
            tp_amb='2',
            cstat='100',
            valor_total_servico=Decimal('1'),
            transportadora=transp,
            status_conferencia=CTeHistoricoImportado.StatusConferencia.CONFERIDO,
            apto_operacional=True,
        )
        rows = buscar_cte_conferido_opcoes({'search': 'HOMOL'})
        self.assertEqual(len(rows), 0)

    def test_criar_alocacao_com_vinculos(self):
        nf = self._nf_producao(numero='777')
        item_nf = ItemNFeEntradaHistoricaImportada.objects.create(
            nf=nf,
            n_item=1,
            prod_json={'xProd': 'Prod 4013', 'qCom': '5', 'uCom': 'PC'},
        )
        # Fase 1 exige item de conferência; PC entra via conferência (payload CRUD não é repassado).
        self._item_conferencia_para_historico(
            item_nf,
            quantidade='5',
            item_pedido_compra=self.item_pc,
        )
        cte = self._cte_conferido()
        estoque_antes = EstoqueCorrida.objects.count()
        qtd_rec_pc_antes = self.item_pc.quantidade_recebida
        aloc = criar_alocacao_atendimento(
            {
                'pedido_venda_item': self.item_pv,
                'produto': self.produto,
                'quantidade_necessaria': Decimal('2'),
                'quantidade_pendente': Decimal('2'),
                'tipo_atendimento': TipoAtendimentoItem.COMPRA_VINCULADA,
                'status_entrada_fiscal': StatusEntradaFiscal.PENDENTE,
                'fornecedor': self.fornecedor,
                'pedido_compra_item': self.item_pc,
                'nf_entrada_historica_item': item_nf,
                'cte_historico_importado': cte,
            },
        )
        # CTE não faz parte do payload Fase 1; vínculo complementar pós-alocação (sem reentrada no upsert).
        AlocacaoAtendimento.objects.filter(pk=aloc.pk).update(cte_historico_importado=cte)
        aloc.refresh_from_db()
        self.assertEqual(aloc.pedido_compra_item_id, self.item_pc.pk)
        v = montar_vinculos_exibicao(aloc)
        self.assertIn('PC-4013', v['pedido_compra_label'] or '')
        self.assertTrue(v['tem_cte_vinculado'])
        self.assertEqual(EstoqueCorrida.objects.count(), estoque_antes)
        self.item_pc.refresh_from_db()
        self.assertEqual(self.item_pc.quantidade_recebida, qtd_rec_pc_antes)

    def test_bloqueia_nfe_homologacao_no_vinculo(self):
        nf = self._nf_producao(tp_amb='2')
        item_nf = ItemNFeEntradaHistoricaImportada.objects.create(nf=nf, n_item=1, prod_json={})
        # Conferência mínima para o fluxo chegar à validação de ambiente (não ao erro de ausência).
        self._item_conferencia_para_historico(item_nf, quantidade='1')
        with self.assertRaises(AlocacaoAtendimentoErro) as ctx:
            criar_alocacao_atendimento(
                {
                    'pedido_venda_item': self.item_pv,
                    'produto': self.produto,
                    'quantidade_necessaria': Decimal('1'),
                    'nf_entrada_historica_item': item_nf,
                    'tipo_atendimento': TipoAtendimentoItem.NAO_DEFINIDO,
                },
            )
        self.assertIn('homologação', str(ctx.exception).lower())
        self.assertNotIn('conferência não encontrado', str(ctx.exception).lower())

    def test_bloqueia_produto_incompativel_pc(self):
        item_pc_outro = ItemPedidoCompra.objects.create(
            pedido=self.pc,
            produto=self.produto_b,
            quantidade=Decimal('1'),
            valor_unitario=Decimal('1'),
        )
        with self.assertRaises(AlocacaoAtendimentoErro):
            criar_alocacao_atendimento(
                {
                    'pedido_venda_item': self.item_pv,
                    'produto': self.produto,
                    'quantidade_necessaria': Decimal('1'),
                    'pedido_compra_item': item_pc_outro,
                    'tipo_atendimento': TipoAtendimentoItem.NAO_DEFINIDO,
                },
            )

    def test_vinculo_nao_movimenta_estoque(self):
        estoque_antes = EstoqueCorrida.objects.count()
        atend_antes = AtendimentoEstoque.objects.count()
        criar_alocacao_atendimento(
            {
                'pedido_venda_item': self.item_pv,
                'produto': self.produto,
                'quantidade_necessaria': Decimal('1'),
                'fornecedor': self.fornecedor,
                'pedido_compra_item': self.item_pc,
                'tipo_atendimento': TipoAtendimentoItem.RETIRADA_FORNECEDOR,
            },
        )
        self.assertEqual(EstoqueCorrida.objects.count(), estoque_antes)
        self.assertEqual(AtendimentoEstoque.objects.count(), atend_antes)

    def test_resumo_api_inclui_vinculos_legiveis(self):
        criar_alocacao_atendimento(
            {
                'pedido_venda_item': self.item_pv,
                'produto': self.produto,
                'quantidade_necessaria': Decimal('1'),
                'fornecedor': self.fornecedor,
                'pedido_compra_item': self.item_pc,
                'tipo_atendimento': TipoAtendimentoItem.RETIRADA_FORNECEDOR,
            },
        )
        r = self.client.get(f'/api/pedidos-venda/{self.pv.pk}/alocacoes-atendimento/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        aloc = r.data['alocacoes'][0]
        self.assertIn('vinculos', aloc)
        self.assertTrue(aloc['vinculos']['tem_compra_vinculada'])
