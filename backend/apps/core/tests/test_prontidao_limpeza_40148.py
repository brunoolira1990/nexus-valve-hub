"""ERP 4.0.14.8 — prontidão e limpeza segura para produção."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from apps.cadastros.models import Cliente, Empresa
from apps.core.preparacao_limpeza_producao import CONFIRMACAO_TOKEN, executar_dry_run_limpeza_producao
from apps.core.prontidao_producao import executar_verificacao_prontidao
from apps.financeiro.models import TituloFinanceiro
from apps.financeiro.services.titulo import criar_titulo_financeiro
from apps.produtos.models import Produto as ProdutoModel

User = get_user_model()


class ProntidaoProducao40148Tests(TestCase):
    def test_comando_somente_leitura(self):
        out = StringIO()
        call_command('verificar_prontidao_producao', stdout=out)
        self.assertIn('PRONTIDÃO', out.getvalue())

    def test_detecta_titulo_sem_numero(self):
        cli = Cliente.objects.create(razao_social='Cli Pront', cnpj='39053344712')
        user = User.objects.create_user('pr40148', 'pr40148@test.com', 'x')
        Empresa.objects.create(razao_social='Empresa Teste', cnpj='59443075000124')
        titulo = criar_titulo_financeiro(
            tipo=TituloFinanceiro.Tipo.RECEBER,
            cliente_id=cli.pk,
            data_emissao=date.today(),
            data_vencimento=date.today(),
            valor_original=Decimal('10'),
            usuario=user,
        )
        TituloFinanceiro.objects.filter(pk=titulo.pk).update(numero='')
        rel = executar_verificacao_prontidao()
        msgs = [x['mensagem'] for x in rel['criticos']]
        self.assertTrue(any('número' in m.lower() or 'numero' in m.lower() for m in msgs))


class LimpezaProducao40148Tests(TestCase):
    @override_settings(DEBUG=True)
    def test_dry_run_nao_altera_dados(self):
        ProdutoModel.objects.create(
            modo_codigo=ProdutoModel.ModoCodigo.MANUAL,
            codigo_completo='P40148',
            descricao='Prod preserve',
            unidade='PC',
        )
        antes = ProdutoModel.objects.count()
        rel = executar_dry_run_limpeza_producao()
        self.assertTrue(rel.get('nenhum_dado_alterado'))
        self.assertEqual(ProdutoModel.objects.count(), antes)
        self.assertGreaterEqual(rel['preservados']['produtos'], 1)

    @override_settings(DEBUG=True)
    def test_execucao_sem_confirmacao_bloqueada(self):
        with self.assertRaises(CommandError):
            call_command('preparar_limpeza_producao', '--executar', stdout=StringIO())

    @override_settings(DEBUG=True)
    def test_execucao_sem_backup_bloqueada(self):
        with self.assertRaises(CommandError) as ctx:
            call_command(
                'preparar_limpeza_producao',
                '--executar',
                f'--confirmar={CONFIRMACAO_TOKEN}',
                stdout=StringIO(),
            )
        self.assertIn('backup', str(ctx.exception).lower())

    @override_settings(DEBUG=True)
    def test_dry_run_lista_candidatos(self):
        out = StringIO()
        call_command('preparar_limpeza_producao', '--dry-run', stdout=out)
        txt = out.getvalue()
        self.assertIn('Preservados', txt)
        self.assertIn('produtos', txt.lower())
        self.assertIn('dry-run', txt.lower())
