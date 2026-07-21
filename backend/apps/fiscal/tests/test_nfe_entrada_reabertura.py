"""Fase 1 — reabertura segura da conferência de entrada de fornecedor."""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from decimal import Decimal
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Empresa, Fornecedor
from apps.comercial.models import ItemPedidoCompra, PedidoCompra
from apps.corridas.models import Corrida
from apps.financeiro.models import TituloFinanceiro
from apps.fiscal.models import (
    AlocacaoAtendimento,
    AtendimentoEstoque,
    AtendimentoEstoqueLinha,
    EstoqueBarra,
    EstoqueCorrida,
    ItemNFeEntradaConferencia,
    ItemNFeEntradaConferenciaCorridaSplit,
    ItemNFeEntradaConferenciaEquivalencia,
    ItemNFeEntradaHistoricaImportada,
    NFeEntrada,
    NFeEntradaConferencia,
    NFeEntradaConferenciaReaberturaEvento,
    NFeEntradaHistoricaImportada,
    NFeDestinadaManifestacao,
    NFeDestinadaManifestacaoEvento,
    NFeSaida,
)
from apps.produtos.models import FamiliaProduto, Produto
from apps.qualidade.models import CertificadoFornecedorEntrada, ItemCertificadoFornecedorEntrada


def _cnpj() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


class NFeEntradaReaberturaTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('reabrir_entrada', 'reabrir@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.empresa = Empresa.objects.create(razao_social='Nexus teste', cnpj=_cnpj())
        self.fornecedor = Fornecedor.objects.create(razao_social='Fornecedor teste', cnpj=_cnpj(), uf='SP')
        self.cliente = Cliente.objects.create(razao_social='Cliente teste', cnpj=_cnpj())
        self.familia = FamiliaProduto.objects.create(
            codigo_figura='F-REABRIR',
            descricao_base='Família reabertura',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
            tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
            categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
        )
        self.produto = Produto.objects.create(
            familia=self.familia,
            descricao='Produto reabertura',
            modo_codigo=Produto.ModoCodigo.MANUAL,
            codigo_completo='PROD-REABRIR',
            unidade='PC',
            ncm='84818099',
        )

    def _entrada(self, suffix: str, *, status=NFeEntradaConferencia.Status.PREPARADA):
        nf = NFeEntradaHistoricaImportada.objects.create(
            chave_acesso=('35' + suffix + '0' * 44)[:44],
            numero=f'NF-{suffix}',
            serie='1',
            modelo='55',
            dh_emissao=timezone.make_aware(datetime(2026, 7, 1, 10, 0)),
            valor_total_nf=Decimal('100.00'),
            empresa_destinataria=self.empresa,
            fornecedor_emitente=self.fornecedor,
            papel_empresa_no_documento='destinatario',
            xml_conteudo=f'<nfe id="{suffix}">original</nfe>',
            prot_json={'nProt': f'PROTO-{suffix}'},
        )
        item_nf = ItemNFeEntradaHistoricaImportada.objects.create(
            nf=nf,
            n_item=1,
            prod_json={'cProd': 'P1', 'xProd': 'Produto', 'qCom': '10', 'uCom': 'PC'},
        )
        conf = NFeEntradaConferencia.objects.create(
            nf_entrada_historica=nf,
            status=status,
            preparado_em=timezone.now() if status == NFeEntradaConferencia.Status.PREPARADA else None,
            data_entrada=date(2026, 7, 2),
        )
        item = ItemNFeEntradaConferencia.objects.create(
            conferencia=conf,
            item_nfe_historico=item_nf,
            produto=self.produto,
            status=ItemNFeEntradaConferencia.Status.PRODUTO_VINCULADO,
            quantidade_nf=Decimal('10'),
            unidade_nf='PC',
            quantidade_estoque_calculada=Decimal('10'),
            unidade_estoque_calculada='PC',
            corrida='CORRIDA-1',
            lote='LOTE-1',
            observacao='Preservar esta observação',
        )
        return nf, conf, item

    @staticmethod
    def _url(nf):
        return reverse('nf-entrada-hist-importada-reabrir-conferencia', kwargs={'pk': nf.id})

    def _post(self, nf, motivo='Correção operacional autorizada'):
        return self.client.post(self._url(nf), {'motivo': motivo}, format='json')

    def test_preparada_reabre_audita_e_preserva_documento_e_vinculos(self):
        nf, conf, item = self._entrada('OK')
        xml_original = nf.xml_conteudo
        chave_original = nf.chave_acesso
        manifestacao = NFeDestinadaManifestacao.objects.create(
            empresa=self.empresa,
            chave_acesso=nf.chave_acesso,
            cnpj_destinatario='00000000000191',
            status_manifestacao=NFeDestinadaManifestacao.StatusManifestacao.CONFIRMADA,
            status_xml=NFeDestinadaManifestacao.StatusXml.BAIXADO,
            nf_entrada_historica=nf,
            manifestado_em=timezone.now(),
            resumo_json={'preservar': True},
        )
        evento_manifestacao = NFeDestinadaManifestacaoEvento.objects.create(
            documento=manifestacao,
            empresa=self.empresa,
            tipo_acao=NFeDestinadaManifestacaoEvento.TipoAcao.MANIFESTACAO,
            codigo_evento='210200',
            descricao='Confirmação da operação',
            cstat='135',
            dados_json={'preservar': True},
        )

        resposta = self._post(nf)

        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.json()['acao_realizada'])
        conf.refresh_from_db()
        nf.refresh_from_db()
        item.refresh_from_db()
        self.assertEqual(conf.status, NFeEntradaConferencia.Status.PENDENTE)
        self.assertIsNone(conf.preparado_em)
        self.assertEqual(nf.xml_conteudo, xml_original)
        self.assertEqual(nf.chave_acesso, chave_original)
        self.assertEqual(item.produto_id, self.produto.id)
        self.assertEqual(item.corrida, 'CORRIDA-1')
        self.assertEqual(item.lote, 'LOTE-1')
        manifestacao.refresh_from_db()
        evento_manifestacao.refresh_from_db()
        self.assertEqual(
            manifestacao.status_manifestacao,
            NFeDestinadaManifestacao.StatusManifestacao.CONFIRMADA,
        )
        self.assertEqual(manifestacao.status_xml, NFeDestinadaManifestacao.StatusXml.BAIXADO)
        self.assertEqual(manifestacao.resumo_json, {'preservar': True})
        self.assertEqual(evento_manifestacao.cstat, '135')
        self.assertEqual(evento_manifestacao.dados_json, {'preservar': True})
        evento = NFeEntradaConferenciaReaberturaEvento.objects.get(conferencia=conf)
        self.assertEqual(evento.usuario, self.user)
        self.assertEqual(evento.motivo, 'Correção operacional autorizada')
        self.assertEqual(evento.estado_anterior, NFeEntradaConferencia.Status.PREPARADA)
        self.assertEqual(evento.estado_posterior, NFeEntradaConferencia.Status.PENDENTE)

    def test_conferida_legado_reabre(self):
        nf, conf, _ = self._entrada('LEG', status=NFeEntradaConferencia.Status.CONFERIDA)
        resposta = self._post(nf)
        self.assertEqual(resposta.status_code, 200)
        conf.refresh_from_db()
        self.assertEqual(conf.status, NFeEntradaConferencia.Status.PENDENTE)
        self.assertEqual(conf.eventos_reabertura.count(), 1)

    def test_pendente_e_idempotente_e_duas_requisicoes_nao_duplicam_evento(self):
        nf, conf, _ = self._entrada('IDEM')
        primeira = self._post(nf)
        segunda = self._post(nf)
        self.assertEqual(primeira.status_code, 200)
        self.assertEqual(segunda.status_code, 200)
        self.assertFalse(segunda.json()['acao_realizada'])
        self.assertTrue(segunda.json()['entrada_ja_aberta'])
        self.assertEqual(conf.eventos_reabertura.count(), 1)

    def test_cancelada_e_motivos_invalidos_bloqueiam_sem_evento(self):
        nf_cancelada, conf_cancelada, _ = self._entrada('CANC', status=NFeEntradaConferencia.Status.CANCELADA)
        bloqueada = self._post(nf_cancelada)
        self.assertEqual(bloqueada.status_code, 400)
        self.assertIn('CONFERENCIA_CANCELADA', [x['codigo'] for x in bloqueada.json()['impedimentos']])
        conf_cancelada.refresh_from_db()
        self.assertEqual(conf_cancelada.status, NFeEntradaConferencia.Status.CANCELADA)
        self.assertEqual(conf_cancelada.eventos_reabertura.count(), 0)

        nf_motivo, conf_motivo, _ = self._entrada('MOT')
        self.assertEqual(self._post(nf_motivo, '').status_code, 400)
        self.assertEqual(self._post(nf_motivo, 'curto').status_code, 400)
        conf_motivo.refresh_from_db()
        self.assertEqual(conf_motivo.status, NFeEntradaConferencia.Status.PREPARADA)
        self.assertEqual(conf_motivo.eventos_reabertura.count(), 0)

    def test_preview_retorna_todos_os_bloqueios_sem_alterar_dados(self):
        nf, conf, item = self._entrada('ALL')
        conf.estoque_aplicado_em = timezone.now()
        conf.pedido_baixa_aplicado_em = timezone.now()
        conf.save(update_fields=['estoque_aplicado_em', 'pedido_baixa_aplicado_em'])
        item.quantidade_pedido_baixada = Decimal('1')
        item.save(update_fields=['quantidade_pedido_baixada'])
        TituloFinanceiro.objects.create(
            tipo=TituloFinanceiro.Tipo.PAGAR,
            numero='CP-ALL',
            fornecedor=self.fornecedor,
            data_emissao=date(2026, 7, 1),
            data_vencimento=date(2026, 8, 1),
            valor_original=Decimal('100'),
            valor_aberto=Decimal('100'),
            origem_tipo=TituloFinanceiro.OrigemTipo.NFE_ENTRADA,
            origem_id=nf.id,
        )
        AlocacaoAtendimento.objects.create(
            produto=self.produto,
            nf_entrada_historica_item=item.item_nfe_historico,
            quantidade_necessaria=Decimal('1'),
        )

        resposta = self.client.get(self._url(nf))

        self.assertEqual(resposta.status_code, 200)
        data = resposta.json()
        self.assertFalse(data['pode_reabrir'])
        codigos = {x['codigo'] for x in data['impedimentos']}
        self.assertTrue(
            {'ESTOQUE_APLICADO', 'PEDIDO_COMPRA_BAIXADO', 'CONTA_PAGAR_VINCULADA', 'ALOCACAO_ENTRADA_VENDA'}
            <= codigos,
        )
        conf.refresh_from_db()
        self.assertEqual(conf.status, NFeEntradaConferencia.Status.PREPARADA)

    def test_estoque_item_split_e_barra_bloqueiam(self):
        nf_item, _, item = self._entrada('STITEM')
        item.estoque_aplicado_em = timezone.now()
        item.save(update_fields=['estoque_aplicado_em'])
        self.assertEqual(self._post(nf_item).status_code, 400)

        nf_split, _, item_split = self._entrada('STSPLIT')
        ItemNFeEntradaConferenciaCorridaSplit.objects.create(
            item_conferencia=item_split,
            ordem=1,
            corrida='C1',
            lote='L1',
            quantidade=Decimal('10'),
            quantidade_aplicada=Decimal('10'),
        )
        self.assertEqual(self._post(nf_split).status_code, 400)

        nf_barra, _, item_barra = self._entrada('STBARRA')
        equiv = ItemNFeEntradaConferenciaEquivalencia.objects.create(
            item_conferencia=item_barra,
            ordem=1,
            metros=Decimal('10'),
        )
        EstoqueBarra.objects.create(
            produto=self.produto,
            item_conferencia=item_barra,
            equivalencia_entrada=equiv,
            nfe_entrada_historica=nf_barra,
            codigo_interno_barra='BARRA-REABRIR',
            quantidade_original=Decimal('10'),
            saldo=Decimal('10'),
            status=EstoqueBarra.Status.DISPONIVEL,
        )
        self.assertEqual(self._post(nf_barra).status_code, 400)

    def test_vinculos_editaveis_sem_efeito_nao_bloqueiam(self):
        nf, conf, item = self._entrada('EDIT')
        pedido = PedidoCompra.objects.create(
            numero='PC-REABRIR',
            fornecedor=self.fornecedor,
            data=date(2026, 7, 1),
        )
        item_pc = ItemPedidoCompra.objects.create(
            pedido=pedido,
            produto=self.produto,
            quantidade=Decimal('10'),
            valor_unitario=Decimal('10'),
        )
        conf.pedido_compra = pedido
        conf.save(update_fields=['pedido_compra'])
        item.item_pedido_compra = item_pc
        item.save(update_fields=['item_pedido_compra'])
        ItemNFeEntradaConferenciaEquivalencia.objects.create(
            item_conferencia=item,
            ordem=1,
            metros=Decimal('5'),
        )
        ItemNFeEntradaConferenciaCorridaSplit.objects.create(
            item_conferencia=item,
            ordem=1,
            corrida='C1',
            lote='L1',
            quantidade=Decimal('10'),
        )
        cf = CertificadoFornecedorEntrada.objects.create(
            fornecedor=self.fornecedor,
            nf_entrada_historica=nf,
            status=CertificadoFornecedorEntrada.Status.REGISTRADO,
        )
        ItemCertificadoFornecedorEntrada.objects.create(
            certificado_fornecedor=cf,
            produto=self.produto,
            item_conferencia=item,
            quantidade=Decimal('10'),
            corrida='C1',
            lote='L1',
        )

        resposta = self._post(nf)

        self.assertEqual(resposta.status_code, 200)
        item.refresh_from_db()
        self.assertEqual(item.item_pedido_compra_id, item_pc.id)
        self.assertEqual(item.equivalencias.count(), 1)
        self.assertEqual(item.corridas_split.count(), 1)
        self.assertEqual(item.itens_certificado_fornecedor.count(), 1)
        self.assertEqual(item_pc.quantidade_recebida, Decimal('0'))

    def test_baixa_pedido_financeiro_e_alocacao_nao_sao_modificados(self):
        nf, conf, item = self._entrada('PRES')
        item.quantidade_pedido_baixada = Decimal('2')
        item.pedido_baixa_aplicada_em = timezone.now()
        item.save(update_fields=['quantidade_pedido_baixada', 'pedido_baixa_aplicada_em'])
        titulo = TituloFinanceiro.objects.create(
            tipo=TituloFinanceiro.Tipo.PAGAR,
            numero='CP-PRES',
            fornecedor=self.fornecedor,
            data_emissao=date(2026, 7, 1),
            data_vencimento=date(2026, 8, 1),
            valor_original=Decimal('100'),
            valor_aberto=Decimal('100'),
            origem_tipo=TituloFinanceiro.OrigemTipo.NFE_ENTRADA,
            origem_id=nf.id,
        )
        alocacao = AlocacaoAtendimento.objects.create(
            produto=self.produto,
            nf_entrada_historica_item=item.item_nfe_historico,
            quantidade_necessaria=Decimal('2'),
        )

        resposta = self._post(nf)

        self.assertEqual(resposta.status_code, 400)
        item.refresh_from_db()
        titulo.refresh_from_db()
        alocacao.refresh_from_db()
        conf.refresh_from_db()
        self.assertEqual(item.quantidade_pedido_baixada, Decimal('2'))
        self.assertEqual(titulo.valor_original, Decimal('100'))
        self.assertEqual(alocacao.quantidade_necessaria, Decimal('2'))
        self.assertEqual(conf.status, NFeEntradaConferencia.Status.PREPARADA)

    def test_atendimento_estoque_linha_bloqueia(self):
        nf, conf, item = self._entrada('ATEND')
        nf_saida = NFeSaida.objects.create(
            numero='NF-SAIDA-ATEND',
            cliente=self.cliente,
            data=date(2026, 7, 1),
        )
        atendimento = AtendimentoEstoque.objects.create(
            nf_saida=nf_saida,
            produto=self.produto,
            quantidade_comprometida=Decimal('10'),
        )
        AtendimentoEstoqueLinha.objects.create(
            atendimento=atendimento,
            item_conferencia=item,
            conferencia=conf,
            quantidade=Decimal('1'),
        )

        resposta = self._post(nf)

        self.assertEqual(resposta.status_code, 400)
        self.assertIn(
            'ATENDIMENTO_ESTOQUE_VINCULADO',
            [x['codigo'] for x in resposta.json()['impedimentos']],
        )
        self.assertTrue(AtendimentoEstoqueLinha.objects.filter(conferencia=conf).exists())

    def test_falha_ao_criar_evento_faz_rollback_total(self):
        nf, conf, _ = self._entrada('ROLL')
        with patch(
            'apps.fiscal.nfe_entrada_reabertura.NFeEntradaConferenciaReaberturaEvento.objects.create',
            side_effect=RuntimeError('falha simulada'),
        ):
            with self.assertRaises(RuntimeError):
                from apps.fiscal.nfe_entrada_reabertura import reabrir_entrada_fornecedor

                reabrir_entrada_fornecedor(nf.id, motivo='Motivo válido para rollback', usuario=self.user)
        conf.refresh_from_db()
        self.assertEqual(conf.status, NFeEntradaConferencia.Status.PREPARADA)
        self.assertIsNotNone(conf.preparado_em)
        self.assertEqual(conf.eventos_reabertura.count(), 0)

    def test_evento_e_imutavel(self):
        nf, conf, _ = self._entrada('IMM')
        self._post(nf)
        evento = conf.eventos_reabertura.get()
        evento.motivo = 'Tentativa de alteração posterior'
        with self.assertRaises(ValidationError):
            evento.save()
        with self.assertRaises(ValidationError):
            evento.delete()

    def test_endpoint_nao_existe_no_fluxo_de_entrada_propria(self):
        entrada_propria = NFeEntrada.objects.create(
            numero='ENTRADA-PROPRIA',
            tipo_origem=NFeEntrada.TipoOrigem.ENTRADA_PROPRIA_EMITIDA,
            empresa_emitente=self.empresa,
            data=date(2026, 7, 1),
        )
        resposta = self.client.post(
            f'/api/nf-entradas/{entrada_propria.id}/conferencia/reabrir/',
            {'motivo': 'Motivo válido não aplicável'},
            format='json',
        )
        self.assertEqual(resposta.status_code, 404)


class NFeEntradaReaberturaConcorrenciaTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        empresa = Empresa.objects.create(razao_social='Nexus concorrência', cnpj=_cnpj())
        fornecedor = Fornecedor.objects.create(razao_social='Fornecedor concorrência', cnpj=_cnpj())
        self.nf = NFeEntradaHistoricaImportada.objects.create(
            chave_acesso='35' + '9' * 42,
            numero='NF-CONCORRENTE',
            serie='1',
            modelo='55',
            dh_emissao=timezone.now(),
            valor_total_nf=Decimal('100'),
            empresa_destinataria=empresa,
            fornecedor_emitente=fornecedor,
            papel_empresa_no_documento='destinatario',
        )
        self.conf = NFeEntradaConferencia.objects.create(
            nf_entrada_historica=self.nf,
            status=NFeEntradaConferencia.Status.PREPARADA,
            preparado_em=timezone.now(),
        )

    def test_duas_execucoes_concorrentes_criam_somente_um_evento(self):
        from apps.fiscal.nfe_entrada_reabertura import reabrir_entrada_fornecedor

        barreira = Barrier(2)

        def executar():
            close_old_connections()
            barreira.wait(timeout=10)
            try:
                return reabrir_entrada_fornecedor(
                    self.nf.id,
                    motivo='Correção concorrente autorizada',
                )['acao_realizada']
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            resultados = list(executor.map(lambda _: executar(), range(2)))

        self.conf.refresh_from_db()
        self.assertEqual(sorted(resultados), [False, True])
        self.assertEqual(self.conf.status, NFeEntradaConferencia.Status.PENDENTE)
        self.assertEqual(self.conf.eventos_reabertura.count(), 1)


class NFeEntradaReaberturaMigrationTests(TransactionTestCase):
    def test_migration_reversa_remove_somente_tabela_de_auditoria(self):
        executor = MigrationExecutor(connection)
        tabelas_com_evento = set(connection.introspection.table_names())
        tabela_evento = NFeEntradaConferenciaReaberturaEvento._meta.db_table
        self.assertIn(tabela_evento, tabelas_com_evento)

        try:
            executor.migrate([('fiscal', '0065_itemnfesaida_valor_preco_unitario_4_casas')])
            tabelas_sem_evento = set(connection.introspection.table_names())
            self.assertEqual(tabelas_com_evento - tabelas_sem_evento, {tabela_evento})
        finally:
            executor = MigrationExecutor(connection)
            executor.migrate([('fiscal', '0066_nfe_entrada_conferencia_reabertura_evento')])

        self.assertIn(tabela_evento, connection.introspection.table_names())
