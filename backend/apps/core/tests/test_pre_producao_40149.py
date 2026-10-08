"""ERP 4.0.14.9 — pré-produção, limpeza segura e checklist final."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from apps.cadastros.models import Cliente, Empresa
from apps.core.pre_producao import gerar_relatorio_pre_producao, salvar_relatorio_pre_producao
from apps.core.preparacao_limpeza_producao import (
    CONFIRMACAO_TOKEN,
    MSG_PRODUTOS_BLOQUEIO,
    executar_dry_run_limpeza_producao,
    validar_execucao_limpeza_permitida,
)
from apps.core.prontidao_producao import executar_verificacao_prontidao
from apps.financeiro.models import TituloFinanceiro
from apps.financeiro.services.titulo import criar_titulo_financeiro
from apps.produtos.models import Produto as ProdutoModel

User = get_user_model()


class PreProducao40149Tests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('pre40149', 'pre40149@test.com', 'x', is_superuser=True)
        Empresa.objects.create(razao_social='Empresa 40149', cnpj='59443075000130')

    def test_verificar_prontidao_nao_altera_dados(self):
        ProdutoModel.objects.create(
            modo_codigo=ProdutoModel.ModoCodigo.MANUAL,
            codigo_completo='PRE40149',
            descricao='Prod',
            unidade='PC',
        )
        antes = ProdutoModel.objects.count()
        executar_verificacao_prontidao()
        self.assertEqual(ProdutoModel.objects.count(), antes)

    def test_dry_run_nao_altera_dados(self):
        antes = TituloFinanceiro.objects.count()
        rel = executar_dry_run_limpeza_producao()
        self.assertTrue(rel['nenhum_dado_alterado'])
        self.assertEqual(TituloFinanceiro.objects.count(), antes)

    def test_produtos_preservados_no_dry_run(self):
        ProdutoModel.objects.create(
            modo_codigo=ProdutoModel.ModoCodigo.MANUAL,
            codigo_completo='PRES40149',
            descricao='Preservar',
            unidade='PC',
        )
        rel = executar_dry_run_limpeza_producao()
        self.assertGreaterEqual(rel['preservados']['produtos'], 1)
        self.assertTrue(rel['produtos_protegidos']['nunca_removidos'])
        self.assertNotIn('produtos', rel['candidatos_limpeza'])

    def test_produtos_nunca_candidatos_limpeza(self):
        rel = executar_dry_run_limpeza_producao()
        self.assertEqual(rel['candidatos_limpeza'].get('produtos', 0), 0)

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
    def test_execucao_frase_errada_bloqueada(self):
        with self.assertRaises(CommandError):
            call_command(
                'preparar_limpeza_producao',
                '--executar',
                '--backup-confirmado',
                '--confirmar=FRASE_ERRADA',
                stdout=StringIO(),
            )

    def test_usuario_ativo_sem_perfil_critico(self):
        User.objects.create_user('semperfil', 'semperfil@test.com', 'x', is_active=True)
        rel = executar_verificacao_prontidao()
        msgs = ' '.join(c['mensagem'] for c in rel['criticos']).lower()
        self.assertIn('sem perfil', msgs)

    def test_ausencia_admin_critico(self):
        User.objects.filter(is_superuser=True).update(is_superuser=False, is_active=False)
        rel = executar_verificacao_prontidao()
        msgs = ' '.join(c['mensagem'] for c in rel['criticos']).lower()
        self.assertIn('administrador', msgs)

    def test_cr_duplicado_critico(self):
        cli = Cliente.objects.create(razao_social='Cli Dup', cnpj='39053344720')
        t1 = criar_titulo_financeiro(
            tipo=TituloFinanceiro.Tipo.RECEBER,
            cliente_id=cli.pk,
            data_emissao=date.today(),
            data_vencimento=date.today(),
            valor_original=Decimal('10'),
            usuario=self.user,
        )
        t2 = criar_titulo_financeiro(
            tipo=TituloFinanceiro.Tipo.RECEBER,
            cliente_id=cli.pk,
            data_emissao=date.today(),
            data_vencimento=date.today(),
            valor_original=Decimal('20'),
            usuario=self.user,
        )
        TituloFinanceiro.objects.filter(pk=t2.pk).update(numero=t1.numero)
        rel = executar_verificacao_prontidao()
        msgs = ' '.join(c['mensagem'] for c in rel['criticos']).lower()
        self.assertIn('duplicado', msgs)

    def test_parcela_sem_vencimento_impossivel_no_model(self):
        """Campo NOT NULL — prontidão verifica contagem zero quando íntegro."""
        rel = executar_verificacao_prontidao()
        msgs = ' '.join(c['mensagem'] for c in rel['criticos']).lower()
        self.assertNotIn('parcela(s) sem vencimento', msgs)

    def test_relatorio_sem_dados_sensiveis(self):
        rel = gerar_relatorio_pre_producao(usuario_executor='tester')
        raw = json.dumps(rel).lower()
        self.assertNotIn('password', raw)
        self.assertNotIn('senha_certificado', raw)
        self.assertNotIn('token', raw)

    def test_gerar_relatorio_comando(self):
        out = StringIO()
        call_command('gerar_relatorio_pre_producao', '--usuario=tester', stdout=out)
        self.assertIn('RELATÓRIO DE PRÉ-PRODUÇÃO', out.getvalue())
        self.assertIn('Nenhum dado foi alterado', out.getvalue())

    def test_produtos_candidatos_bloqueiam_execucao(self):
        dry = {
            'bloqueios': {'documentos_possivelmente_reais': []},
            'produtos_protegidos': {'candidatos_auditoria': 2},
        }
        pront = {'criticos': []}
        ok, motivo = validar_execucao_limpeza_permitida(
            dry,
            pront,
            backup_confirmado=True,
            confirmacao=CONFIRMACAO_TOKEN,
        )
        self.assertFalse(ok)
        self.assertEqual(motivo, MSG_PRODUTOS_BLOQUEIO)

    def test_prontidao_critico_bloqueia_execucao(self):
        dry = {
            'bloqueios': {'documentos_possivelmente_reais': []},
            'produtos_protegidos': {'candidatos_auditoria': 0},
        }
        pront = {'criticos': [{'mensagem': 'Erro'}]}
        ok, motivo = validar_execucao_limpeza_permitida(
            dry,
            pront,
            backup_confirmado=True,
            confirmacao=CONFIRMACAO_TOKEN,
        )
        self.assertFalse(ok)
        self.assertIn('críticos', motivo.lower())

    @override_settings(DEBUG=True)
    def test_email_duplicado_critico(self):
        User.objects.create_user('dupa', 'dup@test.com', 'x', is_active=True)
        User.objects.create_user('dupb', 'dup@test.com', 'x', is_active=True)
        rel = executar_verificacao_prontidao()
        msgs = ' '.join(c['mensagem'] for c in rel['criticos']).lower()
        self.assertIn('duplicado', msgs)

    def test_salvar_relatorio_cria_arquivo(self):
        import tempfile
        from pathlib import Path

        rel = gerar_relatorio_pre_producao()
        with tempfile.TemporaryDirectory() as tmp:
            path = salvar_relatorio_pre_producao(rel, base_dir=Path(tmp))
            self.assertTrue(path.exists())
            data = json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(data['versao'], 'ERP 4.0.14.10.1')

    @override_settings(DEBUG=True)
    def test_limpeza_preserva_produtos_execucao_mock(self):
        """Dry-run antes/depois — produtos intactos (execução real não roda aqui)."""
        p = ProdutoModel.objects.create(
            modo_codigo=ProdutoModel.ModoCodigo.MANUAL,
            codigo_completo='KEEP40149',
            descricao='Keep',
            unidade='PC',
        )
        antes = ProdutoModel.objects.count()
        executar_dry_run_limpeza_producao()
        self.assertEqual(ProdutoModel.objects.count(), antes)
        self.assertTrue(ProdutoModel.objects.filter(pk=p.pk).exists())
