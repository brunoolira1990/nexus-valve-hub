"""Testes NF-e 4.0.4 — apresentação limpa e limpeza Cursor."""

from __future__ import annotations

import json
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.cadastros.models import Cliente, Empresa
from apps.comercial.faturamento_numero_exibicao import normalizar_numero_faturamento_exibicao
from apps.comercial.models import FaturamentoPedidoVenda, PedidoVenda
from apps.fiscal.limpeza_cursor.auditoria import executar_auditoria_limpeza_cursor
from apps.fiscal.limpeza_cursor.backup import exportar_backup_limpeza_cursor
from apps.fiscal.limpeza_cursor.criterios import (
    avaliar_cliente,
    avaliar_empresa,
    avaliar_nfe,
    avaliar_pedido,
    classificar_produto,
)
from apps.fiscal.limpeza_cursor.limpeza import LimpezaCursorError, executar_limpeza_cursor
from apps.fiscal.models import NFeSaida
from apps.fiscal.nfe_saida_apresentacao import montar_apresentacao_nfe_saida
from apps.produtos.models import FamiliaProduto, Produto


class ApresentacaoLimpa404Tests(TestCase):
    def test_fat_legado_normalizado_exibicao(self):
        self.assertEqual(
            normalizar_numero_faturamento_exibicao('FAT-LEGADO-20260522-0002'),
            'FAT-20260522-0002',
        )

    def test_apresentacao_sem_origem_interna(self):
        emp = Empresa.objects.create(
            razao_social='E',
            cnpj='11222333000199',
            uf='SP',
            cidade='SP',
            logradouro='R',
            numero='1',
            bairro='B',
            cep='01001000',
        )
        cli = Cliente.objects.create(
            razao_social='C',
            cnpj='99888777000166',
            uf='SP',
            cidade='SP',
            logradouro='R',
            numero='1',
            bairro='B',
            cep='01001000',
        )
        pv = PedidoVenda.objects.create(
            numero='PV-20260521-0002',
            empresa_emitente=emp,
            cliente=cli,
            data=date.today(),
            valor_total=Decimal('100'),
        )
        fat = FaturamentoPedidoVenda.objects.create(
            pedido=pv,
            numero_faturamento='FAT-LEGADO-20260522-0002',
            status=FaturamentoPedidoVenda.Status.GERADO_NFE,
        )
        nf = NFeSaida.objects.create(
            numero='RASCUNHO-FAT-2',
            cliente=cli,
            pedido_venda=pv,
            faturamento_pedido_venda=fat,
            data=date.today(),
            valor_total=Decimal('100'),
            status='AUTORIZADA_HOMOLOGACAO',
            status_emissao_sefaz=NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO,
            serie_nfe='0',
            numero_nfe='2',
            cstat_autorizacao='100',
            protocolo_autorizacao='13526005517408',
            xml_autorizado='<?xml?><nfeProc/>',
            chave_acesso='3526050399910200015055000000000212345678901',
        )
        ap = montar_apresentacao_nfe_saida(nf)
        self.assertIn('NF-e Homologação', ap['titulo_exibicao'])
        self.assertNotIn('Origem interna', ap['subtitulo_exibicao'])
        self.assertNotIn('LEGADO', ap['numero_faturamento'])
        self.assertEqual(ap['listagem_subtitulo'], 'FAT-20260522-0002 · PV-20260521-0002')
        self.assertTrue(ap['ocultar_status_conferencia_listagem'])

    def test_rascunho_pode_mostrar_numero_interno_listagem(self):
        cli = Cliente.objects.create(
            razao_social='C',
            cnpj='55443322110055',
            uf='SP',
            cidade='SP',
            logradouro='R',
            numero='1',
            bairro='B',
            cep='01001000',
        )
        nf = NFeSaida.objects.create(
            numero='RASCUNHO-FAT-99',
            cliente=cli,
            data=date.today(),
            valor_total=Decimal('1'),
            status='RASCUNHO',
        )
        ap = montar_apresentacao_nfe_saida(nf)
        self.assertEqual(ap['listagem_titulo'], 'RASCUNHO-FAT-99')


class LimpezaCursor404Tests(TestCase):
    def setUp(self):
        self.nexus = Empresa.objects.create(
            razao_social='NEXUS VALVULAS E CONEXOES INDUSTRIAIS LTDA',
            cnpj='03999102000150',
            uf='SP',
            cidade='São Paulo',
            logradouro='Rua',
            numero='1',
            bairro='Centro',
            cep='01001000',
            certificado_arquivo=None,
        )
        self.emit = Empresa.objects.create(
            razao_social='Emit',
            cnpj='12345678000199',
            uf='SP',
            cidade='/SP',
            logradouro='',
            numero='',
            bairro='',
            cep='',
        )
        self.dynatech = Cliente.objects.create(
            razao_social='DYNATECH INDUSTRIAS QUIMICAS LTDA',
            cnpj='11222333444455',
            uf='SP',
            cidade='São Paulo',
            logradouro='R',
            numero='1',
            bairro='B',
            cep='01001000',
            telefone='1199999999',
        )
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
        self.pv_real = PedidoVenda.objects.create(
            numero='PV-20260521-0002',
            empresa_emitente=self.nexus,
            cliente=self.dynatech,
            data=date.today(),
            valor_total=Decimal('100'),
        )
        self.pv_hash = PedidoVenda.objects.create(
            numero='PV-ac0499',
            empresa_emitente=self.emit,
            cliente=self.cli,
            data=date.today(),
            valor_total=Decimal('50'),
        )
        self.nf_real = NFeSaida.objects.create(
            numero='RASCUNHO-FAT-2',
            cliente=self.dynatech,
            pedido_venda=self.pv_real,
            data=date.today(),
            valor_total=Decimal('100'),
            status='AUTORIZADA_HOMOLOGACAO',
            status_emissao_sefaz=NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO,
            cstat_autorizacao='100',
            protocolo_autorizacao='13526005517408',
            xml_autorizado='<?xml?><nfeProc/>',
        )
        self.nf_fake = NFeSaida.objects.create(
            numero='RASCUNHO-FAT-99',
            cliente=self.cli,
            pedido_venda=self.pv_hash,
            data=date.today(),
            valor_total=Decimal('50'),
            status='RASCUNHO',
        )

    def test_auditoria_preserva_nexus_dynatech_pv_real_nfe_auth(self):
        rel = executar_auditoria_limpeza_cursor()
        ids_nfe_pres = {r['id'] for r in rel['preservados']['nfes']}
        self.assertIn(self.nf_real.pk, ids_nfe_pres)
        ids_emp_cand = {r['id'] for r in rel['empresas_candidatas']}
        self.assertIn(self.emit.pk, ids_emp_cand)
        self.assertNotIn(self.nexus.pk, ids_emp_cand)
        ids_cli_cand = {r['id'] for r in rel['clientes_candidatos']}
        self.assertIn(self.cli.pk, ids_cli_cand)
        self.assertNotIn(self.dynatech.pk, ids_cli_cand)
        ids_pv_cand = {r['id'] for r in rel['pedidos_candidatos']}
        self.assertIn(self.pv_hash.pk, ids_pv_cand)
        self.assertNotIn(self.pv_real.pk, ids_pv_cand)
        ids_nfe_cand = {r['id'] for r in rel['nfe_candidatas']}
        self.assertIn(self.nf_fake.pk, ids_nfe_cand)
        self.assertNotIn(self.nf_real.pk, ids_nfe_cand)

    def test_produtos_nao_candidatos_exclusao(self):
        fam = FamiliaProduto.objects.create(
            codigo_figura='T1',
            descricao_base='Fam',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
            tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
            categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
        )
        p = Produto.objects.create(
            familia=fam,
            descricao='Prod NF 402',
            modo_codigo=Produto.ModoCodigo.MANUAL,
            codigo_completo='NF402-XYZ',
            unidade='PC',
        )
        cls = classificar_produto(p)
        self.assertFalse(cls['candidato_exclusao'])
        self.assertEqual(cls['acao_recomendada'], 'revisar_manualmente')

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_backup_export_gera_arquivos(self):
        rel = executar_auditoria_limpeza_cursor()
        dest = exportar_backup_limpeza_cursor(rel)
        self.assertTrue((dest / 'resumo.json').exists())
        self.assertTrue((dest / 'nfe_candidatas.csv').exists())

    def test_limpeza_nao_apaga_nfe_autorizada(self):
        rel = executar_auditoria_limpeza_cursor()
        rel['nfe_candidatas'].append({'id': self.nf_real.pk, 'candidato': True, 'motivos': ['teste']})
        with self.assertRaises(LimpezaCursorError):
            executar_limpeza_cursor(rel)

    def test_limpeza_remove_nfe_fake(self):
        rel = executar_auditoria_limpeza_cursor()
        fake_id = self.nf_fake.pk
        removidos = executar_limpeza_cursor(rel)
        self.assertGreaterEqual(removidos['nfe'], 1)
        self.assertFalse(NFeSaida.objects.filter(pk=fake_id).exists())
        self.assertTrue(NFeSaida.objects.filter(pk=self.nf_real.pk).exists())
