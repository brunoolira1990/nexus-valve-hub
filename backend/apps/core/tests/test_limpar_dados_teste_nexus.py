"""ERP 4.0.13.5.2 — comando limpar_dados_teste_nexus."""

from datetime import date
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from apps.cadastros.models import Cliente, Empresa
from apps.comercial.models import ItemPedidoVenda, PedidoVenda
from apps.core.limpeza_dados_teste import CONFIRMACAO_TOKEN, ambiente_permite_limpeza_teste
from apps.fiscal.limpeza_cursor.criterios import RE_PV_HASH, avaliar_cliente, avaliar_pedido, avaliar_produto
from apps.fiscal.limpeza_cursor.auditoria import executar_auditoria_limpeza_cursor
from apps.produtos.models import Produto


class LimpezaAmbienteTests(TestCase):
    @override_settings(DEBUG=True)
    def test_ambiente_debug_permite(self):
        self.assertTrue(ambiente_permite_limpeza_teste())

    @override_settings(DEBUG=False)
    def test_debug_false_bloqueia_sem_env_seguro(self):
        self.assertFalse(ambiente_permite_limpeza_teste())


class LimpezaCriterios401352Tests(TestCase):
    def setUp(self):
        self.cli = Cliente.objects.create(
            razao_social='Cli',
            cnpj='99888777000166',
            uf='SP',
            cidade='',
            logradouro='',
            numero='',
            bairro='',
            cep='',
        )
        self.pv_hash = PedidoVenda.objects.create(
            numero='PV-3c6d60',
            cliente=self.cli,
            data=date.today(),
            valor_total=Decimal('1'),
        )
        self.pv_oficial = PedidoVenda.objects.create(
            numero='PV-20260523-0001',
            cliente=self.cli,
            data=date.today(),
            valor_total=Decimal('2'),
        )
        self.prod_nf = Produto.objects.create(
            modo_codigo=Produto.ModoCodigo.MANUAL,
            descricao='PROD NF',
            codigo_completo='NF-PROD',
            preco_venda=Decimal('1'),
        )

    def test_pv_hash_e_candidato(self):
        self.assertTrue(RE_PV_HASH.match('PV-3c6d60'))
        av = avaliar_pedido(self.pv_hash)
        self.assertTrue(av['candidato'])

    def test_pv_oficial_nao_e_candidato_por_padrao(self):
        av = avaliar_pedido(self.pv_oficial)
        self.assertFalse(av['candidato'])

    def test_cliente_cli_candidato(self):
        av = avaliar_cliente(self.cli)
        self.assertTrue(av['candidato'])

    def test_produto_nf_candidato_sem_vinculo(self):
        av = avaliar_produto(self.prod_nf)
        self.assertTrue(av['candidato'])

    def test_produto_real_sem_material_nao_removido_por_material(self):
        real = Produto.objects.create(
            modo_codigo=Produto.ModoCodigo.MANUAL,
            descricao='CURVA 90 RL ACO CARBONO',
            material='',
            codigo_completo='018840.06',
            preco_venda=Decimal('10'),
        )
        av = avaliar_produto(real)
        self.assertFalse(av['candidato'])

    def test_produto_em_pedido_oficial_nao_candidato(self):
        ItemPedidoVenda.objects.create(
            pedido=self.pv_oficial,
            produto=self.prod_nf,
            quantidade=Decimal('1'),
            valor_unitario=Decimal('1'),
        )
        av = avaliar_produto(self.prod_nf)
        self.assertFalse(av['candidato'])


class LimparDadosTesteNexusCommandTests(TestCase):
    @override_settings(DEBUG=True)
    def test_dry_run_nao_remove(self):
        PedidoVenda.objects.create(
            numero='PV-8e09df',
            cliente=Cliente.objects.create(
                razao_social='Cli2',
                cnpj='55443322110055',
                uf='SP',
                cidade='SP',
                logradouro='R',
                numero='1',
                bairro='B',
                cep='01001000',
            ),
            data=date.today(),
            valor_total=Decimal('1'),
        )
        antes = PedidoVenda.objects.count()
        out = StringIO()
        call_command('limpar_dados_teste_nexus', '--dry-run', stdout=out)
        self.assertEqual(PedidoVenda.objects.count(), antes)
        self.assertIn('[DRY-RUN]', out.getvalue())

    @override_settings(DEBUG=False)
    def test_bloqueia_producao(self):
        with self.assertRaises(CommandError) as ctx:
            call_command('limpar_dados_teste_nexus')
        self.assertIn('produção', str(ctx.exception).lower())

    @override_settings(DEBUG=True)
    def test_exige_token_confirmacao(self):
        with self.assertRaises(CommandError):
            call_command('limpar_dados_teste_nexus', confirmar='INVALIDO')

    @override_settings(DEBUG=True)
    def test_auditoria_dry_run_estrutura(self):
        rel = executar_auditoria_limpeza_cursor()
        self.assertEqual(rel['modo'], 'dry_run')
        self.assertIn('produtos_candidatos', rel)
