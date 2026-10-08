"""ERP 4.0.13.7.2 — limpeza segura de produtos artificiais de teste."""

from __future__ import annotations

from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from apps.comercial.models import ItemPedidoVenda, PedidoVenda
from apps.produtos.limpeza_produtos_teste_401372 import (
    CODIGOS_ARTIFICIAIS,
    CONFIRMACAO_TOKEN,
    avaliar_produto_artificial,
    executar_dry_run_produtos_teste,
    executar_limpeza_confirmada,
)
from apps.produtos.models import Produto


def _criar_artificial(codigo: str, descricao: str = 'Fam') -> Produto:
    return Produto.objects.create(
        modo_codigo=Produto.ModoCodigo.MANUAL,
        codigo_completo=codigo,
        descricao=descricao,
        unidade='PC',
    )


class LimpezaProdutosTeste401372Tests(TestCase):
    def test_dry_run_identifica_candidato_sem_vinculo(self):
        p = _criar_artificial('N2E3962')
        rel = executar_dry_run_produtos_teste()
        ids = [c['produto_id'] for c in rel['candidatos_elegiveis']]
        self.assertIn(p.id, ids)

    def test_produto_real_mesmo_codigo_descricao_diferente_nao_elegivel(self):
        _criar_artificial('N314EC2', descricao='PRODUTO REAL A')
        rel = executar_dry_run_produtos_teste()
        self.assertFalse(any(c['codigo'] == 'N314EC2' for c in rel['candidatos_elegiveis']))

    def test_produto_com_vinculo_pedido_venda_protegido(self):
        from apps.cadastros.models import Cliente
        from datetime import date
        from decimal import Decimal

        p = _criar_artificial('N34396F')
        cli = Cliente.objects.create(
            razao_social='Cliente Teste Isolado',
            cnpj='12345678000199',
            uf='SP',
            cidade='São Paulo',
            logradouro='Rua',
            numero='1',
            bairro='B',
            cep='01001000',
        )
        pv = PedidoVenda.objects.create(
            numero='PV-TEST-ISOLADO-001',
            cliente=cli,
            data=date.today(),
            valor_total=Decimal('1'),
        )
        ItemPedidoVenda.objects.create(
            pedido=pv,
            produto=p,
            quantidade=Decimal('1'),
            valor_unitario=Decimal('1'),
        )
        av = avaliar_produto_artificial(p)
        self.assertFalse(av.elegivel)
        self.assertIn('item_pedido_venda', av.vinculos)

    @override_settings(DEBUG=True)
    def test_comando_dry_run_nao_remove(self):
        _criar_artificial('N3CD209')
        antes = Produto.objects.filter(codigo_completo='N3CD209').count()
        out = StringIO()
        call_command('limpar_produtos_teste_401372', stdout=out)
        self.assertEqual(Produto.objects.filter(codigo_completo='N3CD209').count(), antes)
        self.assertIn('CANDIDATO', out.getvalue())

    @override_settings(DEBUG=True)
    def test_comando_confirmacao_remove_apenas_elegiveis(self):
        p = _criar_artificial('N569FA5')
        rel = executar_dry_run_produtos_teste()
        resultado = executar_limpeza_confirmada(rel)
        self.assertEqual(resultado['total_removidos'], 1)
        self.assertFalse(Produto.objects.filter(pk=p.id).exists())

    @override_settings(DEBUG=True)
    def test_comando_exige_token(self):
        with self.assertRaises(CommandError):
            call_command('limpar_produtos_teste_401372', confirmar='INVALIDO')

    @override_settings(DEBUG=False)
    def test_bloqueia_producao(self):
        with self.assertRaises(CommandError):
            call_command('limpar_produtos_teste_401372')

    def test_lista_codigos_oficial_completa(self):
        self.assertEqual(len(CODIGOS_ARTIFICIAIS), 9)

    @override_settings(DEBUG=True)
    def test_confirmacao_via_comando(self):
        _criar_artificial('N5A7BEE')
        out = StringIO()
        call_command(
            'limpar_produtos_teste_401372',
            confirmar=CONFIRMACAO_TOKEN,
            stdout=out,
        )
        self.assertFalse(Produto.objects.filter(codigo_completo='N5A7BEE').exists())
        self.assertIn('Limpeza concluída', out.getvalue())
