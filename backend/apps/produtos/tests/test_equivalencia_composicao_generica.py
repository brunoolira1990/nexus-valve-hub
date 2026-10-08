"""ERP 4.0.13.7.1 — testes genéricos de equivalência/composição (dados sintéticos)."""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.comercial.models import ItemPedidoCompra, PedidoCompra
from apps.fiscal.models import (
    ItemNFeEntradaConferencia,
    ItemNFeEntradaHistoricaImportada,
    NFeEntradaConferencia,
    NFeEntradaHistoricaImportada,
)
from apps.produtos.descricao_normalizacao import normalizar_descricao_produto
from apps.produtos.equivalencia_servico import confirmar_agrupamento_equivalencia, rejeitar_sugestao_equivalencia
from apps.produtos.equivalencia_sugestao import sugerir_equivalencias_conferencia
from apps.produtos.models import Produto
from apps.produtos.models_equivalencia import (
    FornecedorComposicaoEquivalencia,
    FornecedorComposicaoEquivalenciaItem,
    FornecedorProdutoEquivalencia,
    ProcessoMontagem,
    ProdutoComposicao,
    ProdutoComposicaoItem,
    TipoComposicaoProduto,
    TipoProcessoMontagem,
)


def _criar_prod(codigo: str, desc: str) -> Produto:
    from apps.produtos.models import FamiliaProduto

    fam = FamiliaProduto.objects.create(
        codigo_figura=f'F{codigo[:4]}',
        descricao_base='Família de teste',
        tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
        categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
    )
    return Produto.objects.create(
        familia=fam,
        descricao=desc,
        modo_codigo=Produto.ModoCodigo.MANUAL,
        codigo_completo=codigo,
        unidade='PC',
    )


class DescricaoNormalizacaoGenericaTests(TestCase):
    def test_normaliza_polegadas_material_classe(self):
        self.assertIn('4P', normalizar_descricao_produto('PRODUTO COMPOSTO A ACO INOX 304 4"'))
        self.assertIn('INOX304', normalizar_descricao_produto('COMPONENTE A INOX 304 4 POL'))
        self.assertIn('ANSI150', normalizar_descricao_produto('FLANGE ANSI 150# RF'))


class EquivalenciaCompostaGenericaTests(TestCase):
    """Cenário A — equivalência composta com fornecedor e componentes sintéticos."""

    def setUp(self):
        self.user = get_user_model().objects.create_user('eq_test', 'eq_test@test.com', 'x')
        self.prod_final = _criar_prod('PRD-FINAL-A', 'PRODUTO COMPOSTO A COMPLETO 4 POL')
        self.comp_a = _criar_prod('CMP-A', 'COMPONENTE A INOX 304 4 POL')
        self.comp_b = _criar_prod('CMP-B', 'COMPONENTE B INOX 304 4 POL')
        self.comp_c = _criar_prod('CMP-C', 'COMPONENTE C VEDACAO 4 POL')

        from apps.cadastros.models import Empresa, Fornecedor

        self.forn = Fornecedor.objects.create(razao_social='Fornecedor Exemplo A', cnpj='12345678000199')
        self.emp = Empresa.objects.create(razao_social='Empresa Destino Teste', cnpj='98765432000188')

        self.regra = FornecedorComposicaoEquivalencia.objects.create(
            fornecedor=self.forn,
            produto_interno_final=self.prod_final,
            descricao='Equivalência composta de teste',
            tolerancia_valor_absoluto=Decimal('0.10'),
        )
        for cod, desc in (
            ('COD-CMP-A', 'COMPONENTE A INOX 304 4 POL'),
            ('COD-CMP-B', 'COMPONENTE B INOX 304 4 POL'),
            ('COD-CMP-C', 'COMPONENTE C VEDACAO 4 POL'),
        ):
            FornecedorComposicaoEquivalenciaItem.objects.create(
                equivalencia_composta=self.regra,
                codigo_fornecedor=cod,
                descricao_fornecedor_normalizada=normalizar_descricao_produto(desc),
                obrigatorio=True,
            )

        self.pedido = PedidoCompra.objects.create(
            numero='PC-TEST-001',
            fornecedor=self.forn,
            data='2026-05-27',
            valor_total=Decimal('300.00'),
        )
        self.item_pedido = ItemPedidoCompra.objects.create(
            pedido=self.pedido,
            produto=self.prod_final,
            quantidade=Decimal('3'),
            valor_unitario=Decimal('100.00'),
            snapshot_produto={'codigo_completo': 'PRD-FINAL-A', 'descricao': self.prod_final.descricao},
        )

        self.nf_hist = NFeEntradaHistoricaImportada.objects.create(
            chave_acesso='35260512345678000199550010000000011000000001',
            numero='NF-TEST-001',
            serie='1',
            valor_total_nf=Decimal('300.00'),
            fornecedor_emitente=self.forn,
            empresa_destinataria=self.emp,
            emit_json={'CNPJ': '12345678000199', 'xNome': 'Fornecedor Exemplo A'},
        )
        self.conf = NFeEntradaConferencia.objects.create(
            nf_entrada_historica=self.nf_hist,
            pedido_compra=self.pedido,
        )

        for n, (cod, desc, qtd, val) in enumerate(
            [
                ('COD-CMP-A', 'COMPONENTE A INOX 304 4 POL', '3', '100.00'),
                ('COD-CMP-B', 'COMPONENTE B INOX 304 4 POL', '3', '150.00'),
                ('COD-CMP-C', 'COMPONENTE C VEDACAO 4 POL', '3', '50.00'),
            ],
            start=1,
        ):
            item_nf = ItemNFeEntradaHistoricaImportada.objects.create(
                nf=self.nf_hist,
                n_item=n,
                prod_json={'cProd': cod, 'xProd': desc, 'NCM': '73079100'},
            )
            ItemNFeEntradaConferencia.objects.create(
                conferencia=self.conf,
                item_nfe_historico=item_nf,
                quantidade_nf=Decimal(qtd),
                valor_total_nf=Decimal(val),
            )

    def test_sugestao_composta_por_regra_cadastrada(self):
        sugs = sugerir_equivalencias_conferencia(self.conf)
        alvo = [s for s in sugs if s.get('produto_interno_codigo') == 'PRD-FINAL-A']
        self.assertTrue(alvo, sugs)
        s = alvo[0]
        self.assertEqual(s['tipo'], 'equivalencia_composta')
        self.assertEqual(len(s['itens_nfe_conferencia_ids']), 3)
        self.assertTrue(s['dentro_tolerancia'])

    def test_confirmar_registra_rastreabilidade_sem_estoque(self):
        sugs = sugerir_equivalencias_conferencia(self.conf)
        s = next(x for x in sugs if x.get('produto_interno_codigo') == 'PRD-FINAL-A')
        agr = confirmar_agrupamento_equivalencia(
            self.conf,
            produto_interno_id=self.prod_final.id,
            item_pedido_compra_id=self.item_pedido.id,
            itens_nfe_conferencia_ids=s['itens_nfe_conferencia_ids'],
            tipo_agrupamento='equivalencia_composta',
            quantidade_equivalente='3',
            confianca=s['confianca'],
            salvar_regra_fornecedor=False,
            usuario=self.user,
        )
        self.assertEqual(agr.status, 'confirmado')
        self.assertIn('chave_acesso', agr.snapshot_rastreabilidade)
        self.conf.refresh_from_db()
        self.assertIsNone(self.conf.estoque_aplicado_em)

    def test_rejeicao_registra_historico(self):
        sugs = sugerir_equivalencias_conferencia(self.conf)
        s = next(x for x in sugs if x.get('produto_interno_codigo') == 'PRD-FINAL-A')
        rej = rejeitar_sugestao_equivalencia(
            self.conf,
            itens_nfe_conferencia_ids=s['itens_nfe_conferencia_ids'],
            produto_interno_id=self.prod_final.id,
            motivo='Divergência de teste',
            usuario=self.user,
        )
        self.assertEqual(rej.status, 'rejeitado')


class EquivalenciaSimplesGenericaTests(TestCase):
    def setUp(self):
        from apps.cadastros.models import Empresa, Fornecedor

        self.prod = _criar_prod('PRD-SIMP-A', 'PRODUTO SIMPLES A')
        self.forn = Fornecedor.objects.create(razao_social='Fornecedor Exemplo B', cnpj='11111111000111')
        self.emp = Empresa.objects.create(razao_social='Empresa Teste', cnpj='22222222000122')
        FornecedorProdutoEquivalencia.objects.create(
            fornecedor=self.forn,
            produto_interno=self.prod,
            codigo_fornecedor='COD-SIMP-01',
            confianca_padrao=92,
        )
        nf = NFeEntradaHistoricaImportada.objects.create(
            chave_acesso='35260511111111000111550010000000022000000002',
            numero='NF-TEST-002',
            serie='1',
            valor_total_nf=Decimal('50.00'),
            fornecedor_emitente=self.forn,
            empresa_destinataria=self.emp,
            emit_json={'CNPJ': '11111111000111'},
        )
        self.conf = NFeEntradaConferencia.objects.create(nf_entrada_historica=nf)
        item_nf = ItemNFeEntradaHistoricaImportada.objects.create(
            nf=nf,
            n_item=1,
            prod_json={'cProd': 'COD-SIMP-01', 'xProd': 'ITEM FORNECEDOR SIMPLES'},
        )
        ItemNFeEntradaConferencia.objects.create(
            conferencia=self.conf,
            item_nfe_historico=item_nf,
            quantidade_nf=Decimal('1'),
            valor_total_nf=Decimal('50.00'),
        )

    def test_equivalencia_simples_por_codigo(self):
        sugs = sugerir_equivalencias_conferencia(self.conf)
        self.assertTrue(any(s['tipo'] == 'equivalencia_simples' for s in sugs))


class MontagemRoscaGenericaTests(TestCase):
    """Cenário B — montagem roscada não exige solda/serviço externo."""

    def test_montagem_roscada_nao_exige_servico(self):
        prod = _criar_prod('PRD-MONT-A', 'PRODUTO MONTADO A 4 POL')
        comp_a = _criar_prod('CMP-M-A', 'COMPONENTE MONTAGEM A')
        comp_b = _criar_prod('CMP-M-B', 'COMPONENTE MONTAGEM B')
        composicao = ProdutoComposicao.objects.create(
            produto_final=prod,
            nome='Montagem roscada padrão',
            tipo_composicao=TipoComposicaoProduto.MONTAGEM_ROSCADA,
            padrao=True,
            exige_servico=False,
        )
        ProdutoComposicaoItem.objects.create(composicao=composicao, componente_produto=comp_a, ordem=1)
        ProdutoComposicaoItem.objects.create(composicao=composicao, componente_produto=comp_b, ordem=2)
        ProcessoMontagem.objects.create(
            composicao=composicao,
            tipo=TipoProcessoMontagem.ROSCA,
            exige_servico=False,
            baixa_componentes=False,
        )
        self.assertFalse(composicao.exige_servico)
        self.assertEqual(composicao.tipo_composicao, TipoComposicaoProduto.MONTAGEM_ROSCADA)
        proc = composicao.processos.first()
        self.assertEqual(proc.tipo, TipoProcessoMontagem.ROSCA)
        self.assertFalse(proc.exige_servico)


class ProdutoMultiplasOrigensTests(TestCase):
    """Cenário C — produto pode ser comprado pronto ou montado."""

    def test_produto_aceita_comprar_pronto_e_montar(self):
        prod = _criar_prod('PRD-DUAL-A', 'PRODUTO DUAL ORIGEM A')
        comp = ProdutoComposicao.objects.create(
            produto_final=prod,
            tipo_composicao=TipoComposicaoProduto.MONTAGEM_SIMPLES,
            permite_comprar_pronto=True,
            permite_montar=True,
            padrao=True,
        )
        self.assertTrue(comp.permite_comprar_pronto)
        self.assertTrue(comp.permite_montar)
        alt = ProdutoComposicao.objects.create(
            produto_final=prod,
            nome='Alternativa kit',
            tipo_composicao=TipoComposicaoProduto.KIT_COMERCIAL,
            padrao=False,
            permite_alternativa=True,
        )
        self.assertTrue(alt.permite_alternativa)
        self.assertEqual(prod.composicoes.count(), 2)

    def test_composicao_nao_cria_produto_automaticamente(self):
        antes = Produto.objects.count()
        prod = _criar_prod('PRD-NEW-A', 'PRODUTO NOVO A')
        ProdutoComposicao.objects.create(
            produto_final=prod,
            tipo_composicao=TipoComposicaoProduto.MONTAGEM_SOLDADA,
        )
        self.assertEqual(Produto.objects.count(), antes + 1)
