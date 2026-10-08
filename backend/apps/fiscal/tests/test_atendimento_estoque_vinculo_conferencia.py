"""Fase 3.10 — vínculo conferência NF entrada ↔ AtendimentoEstoque (sem estoque físico)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Fornecedor
from apps.corridas.models import Corrida
from apps.fiscal.atendimento_estoque import (
    desvincular_linha_atendimento,
    sugerir_atendimentos_para_item_conferencia,
    vincular_item_conferencia_a_atendimento,
)
from apps.fiscal.conferencia_pedido import (
    STATUS_ELEGIBILIDADE_APTO,
    STATUS_ELEGIBILIDADE_BLOQUEADO,
    STATUS_ELEGIBILIDADE_NAO_MOVIMENTA,
    avaliar_elegibilidade_estoque_item_conferencia,
)
from apps.fiscal.models import (
    AtendimentoEstoque,
    AtendimentoEstoqueLinha,
    EstoqueCorrida,
    ItemNFeEntradaConferencia,
    ItemNFeEntradaHistoricaImportada,
    NFeEntradaConferencia,
    NFeEntradaHistoricaImportada,
    NFeSaida,
)
from apps.fiscal.serializers import NFeSaidaSerializer
from apps.produtos.models import FamiliaProduto, Produto
from apps.regras_fiscais.entrada_fiscal import avaliar_item_entrada_fiscal, montar_contexto_fiscal_entrada
from apps.regras_fiscais.models import RegraFiscalEntrada


def _cnpj() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


def _setup_vinculo(suffix: str):
    forn = Fornecedor.objects.create(razao_social=f'Forn {suffix}', cnpj=_cnpj())
    cliente = Cliente.objects.create(razao_social=f'Cliente {suffix}', cnpj=_cnpj())
    fam = FamiliaProduto.objects.create(
        codigo_figura=f'FV{suffix}'[:16],
        descricao_base=f'Fam {suffix}',
        tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
        categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
    )
    produto = Produto.objects.create(
        familia=fam,
        descricao=f'Produto {suffix}',
        modo_codigo=Produto.ModoCodigo.MANUAL,
        codigo_completo=f'COD-V-{suffix}',
        unidade='PC',
        ncm='84818099',
    )
    corrida = Corrida.objects.create(
        numero=f'CR-V-{suffix}',
        produto=produto,
        fornecedor=forn,
        data_recebimento=date(2026, 1, 10),
    )
    EstoqueCorrida.objects.create(produto=produto, corrida=corrida, saldo=Decimal('50'))

    ser = NFeSaidaSerializer(
        data={
            'numero': f'NF-ANT-{suffix}',
            'cliente_id': cliente.id,
            'data': '2026-05-16',
            'status': 'Emitida',
            'modo_atendimento_estoque': NFeSaida.ModoAtendimentoEstoque.ANTECIPADO,
            'itens': [{'produto_id': produto.id, 'quantidade': '10.000', 'valor': '1.00'}],
        },
    )
    assert ser.is_valid(), ser.errors
    nf_saida = ser.save()
    atend = AtendimentoEstoque.objects.get(nf_saida=nf_saida)

    nf_ent = NFeEntradaHistoricaImportada.objects.create(
        chave_acesso=('35' + suffix + 'X' * 40)[:44],
        numero=f'NE{suffix}'[:8],
        serie='1',
        modelo='55',
        dh_emissao=datetime(2026, 5, 1, 10, 0),
        valor_total_nf=Decimal('100'),
        fornecedor_emitente=forn,
    )
    item_nf = ItemNFeEntradaHistoricaImportada.objects.create(
        nf=nf_ent,
        n_item=1,
        prod_json={'CFOP': '5102', 'NCM': '84818099', 'qCom': '10.000', 'uCom': 'PC'},
        imposto_json={},
    )
    conf = NFeEntradaConferencia.objects.create(
        nf_entrada_historica=nf_ent,
        status=NFeEntradaConferencia.Status.PREPARADA,
    )
    linha, _ = conf.itens.get_or_create(item_nfe_historico=item_nf)
    linha.produto = produto
    linha.quantidade_nf = Decimal('10.000')
    linha.unidade_nf = 'PC'
    linha.corrida = 'C-ENT'
    linha.lote = 'L-ENT'
    linha.status = ItemNFeEntradaConferencia.Status.CONFERIDO
    linha.save()

    RegraFiscalEntrada.objects.create(
        nome=f'Regra {suffix}',
        ativo=True,
        prioridade=1,
        cfop='5102',
        movimenta_estoque=True,
        severidade=RegraFiscalEntrada.Severidade.INFORMATIVO,
    )

    return {
        'produto': produto,
        'cliente': cliente,
        'atend': atend,
        'linha': linha,
        'conf': conf,
        'corrida_ec': EstoqueCorrida.objects.get(produto=produto, corrida=corrida),
    }


class AtendimentoEstoqueVinculoConferenciaTests(TestCase):
    def setUp(self):
        self.ctx = _setup_vinculo('V1')
        self.client = APIClient()
        user = get_user_model().objects.create_user('vinc', 'vinc@test.com', 'x')
        self.client.force_authenticate(user=user)

    def _eleg(self, linha=None):
        linha = linha or self.ctx['linha']
        conf = linha.conferencia
        ctx = montar_contexto_fiscal_entrada(conf)
        regras = list(RegraFiscalEntrada.objects.filter(ativo=True))
        rf = avaliar_item_entrada_fiscal(linha, ctx, regras)
        return avaliar_elegibilidade_estoque_item_conferencia(
            linha,
            resultado_fiscal=rf,
            divergencias_aceitas=conf.divergencias_aceitas,
        )

    def test_sugestao_retorna_atendimento_mesmo_produto(self):
        sug = sugerir_atendimentos_para_item_conferencia(self.ctx['linha'])
        self.assertEqual(len(sug['sugestoes']), 1)
        self.assertEqual(sug['sugestoes'][0]['atendimento_id'], self.ctx['atend'].id)

    def test_sugestao_nao_retorna_produto_diferente(self):
        fam2 = FamiliaProduto.objects.create(
            codigo_figura='F2',
            descricao_base='F2',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
            tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
            categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
        )
        outro = Produto.objects.create(
            familia=fam2,
            descricao='Outro',
            modo_codigo=Produto.ModoCodigo.MANUAL,
            codigo_completo='OUTRO',
            unidade='PC',
            ncm='84818099',
        )
        ser = NFeSaidaSerializer(
            data={
                'numero': 'NF-OUTRO',
                'cliente_id': self.ctx['cliente'].id,
                'data': '2026-05-16',
                'status': 'Emitida',
                'modo_atendimento_estoque': NFeSaida.ModoAtendimentoEstoque.ANTECIPADO,
                'itens': [{'produto_id': outro.id, 'quantidade': '5.000', 'valor': '1.00'}],
            },
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        ser.save()
        sug = sugerir_atendimentos_para_item_conferencia(self.ctx['linha'])
        ids = {s['atendimento_id'] for s in sug['sugestoes']}
        self.assertIn(self.ctx['atend'].id, ids)
        self.assertEqual(len(ids), 1)

    def test_linha_bloqueada_nao_pode_vincular(self):
        RegraFiscalEntrada.objects.filter(cfop='5102').update(
            severidade=RegraFiscalEntrada.Severidade.BLOQUEIO,
        )
        with self.assertRaises(ValueError) as cm:
            vincular_item_conferencia_a_atendimento(self.ctx['linha'], self.ctx['atend'], '1.000')
        self.assertIn('bloqueada', str(cm.exception).lower())

    def test_linha_nao_movimenta_nao_pode_vincular(self):
        RegraFiscalEntrada.objects.filter(cfop='5102').update(movimenta_estoque=False)
        with self.assertRaises(ValueError) as cm:
            vincular_item_conferencia_a_atendimento(self.ctx['linha'], self.ctx['atend'], '1.000')
        self.assertIn('não movimenta', str(cm.exception).lower())

    def test_vinculo_parcial_deixa_atendimento_parcial(self):
        linha, atend = vincular_item_conferencia_a_atendimento(
            self.ctx['linha'],
            self.ctx['atend'],
            '4.000',
        )
        atend.refresh_from_db()
        self.assertEqual(atend.status, AtendimentoEstoque.Status.PARCIAL)
        self.assertEqual(atend.quantidade_atendida, Decimal('4.000'))
        self.assertIsNotNone(linha.id)

    def test_vinculo_total_deixa_atendimento_atendido(self):
        vincular_item_conferencia_a_atendimento(self.ctx['linha'], self.ctx['atend'], '10.000')
        self.ctx['atend'].refresh_from_db()
        self.assertEqual(self.ctx['atend'].status, AtendimentoEstoque.Status.ATENDIDO)
        self.assertEqual(self.ctx['atend'].quantidade_atendida, Decimal('10.000'))

    def test_nao_vincula_acima_pendente_atendimento(self):
        with self.assertRaises(ValueError):
            vincular_item_conferencia_a_atendimento(self.ctx['linha'], self.ctx['atend'], '11.000')

    def test_nao_aloca_acima_quantidade_linha_conferencia(self):
        vincular_item_conferencia_a_atendimento(self.ctx['linha'], self.ctx['atend'], '6.000')
        with self.assertRaises(ValueError):
            vincular_item_conferencia_a_atendimento(self.ctx['linha'], self.ctx['atend'], '5.000')

    def test_desvincular_recalcula_status(self):
        linha_atend, _ = vincular_item_conferencia_a_atendimento(
            self.ctx['linha'],
            self.ctx['atend'],
            '10.000',
        )
        atend, _ = desvincular_linha_atendimento(linha_atend.id)
        self.assertEqual(atend.status, AtendimentoEstoque.Status.PENDENTE)
        self.assertEqual(atend.quantidade_atendida, Decimal('0'))
        self.assertFalse(AtendimentoEstoqueLinha.objects.filter(pk=linha_atend.id).exists())

    def test_atendimento_cancelado_nao_aceita_vinculo(self):
        self.ctx['atend'].status = AtendimentoEstoque.Status.CANCELADO
        self.ctx['atend'].save()
        with self.assertRaises(ValueError):
            vincular_item_conferencia_a_atendimento(self.ctx['linha'], self.ctx['atend'], '1.000')

    def test_estoque_corrida_nao_muda(self):
        saldo_antes = self.ctx['corrida_ec'].saldo
        vincular_item_conferencia_a_atendimento(self.ctx['linha'], self.ctx['atend'], '3.000')
        self.ctx['corrida_ec'].refresh_from_db()
        self.assertEqual(self.ctx['corrida_ec'].saldo, saldo_antes)

    def test_api_sugestoes(self):
        url = reverse('atendimento-estoque-sugestoes')
        res = self.client.get(url, {'item_conferencia_id': self.ctx['linha'].id})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['sugestoes'][0]['atendimento_id'], self.ctx['atend'].id)

    def test_elegibilidade_apto_na_linha(self):
        self.assertEqual(self._eleg()['status'], STATUS_ELEGIBILIDADE_APTO)
