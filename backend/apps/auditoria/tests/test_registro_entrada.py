"""Testes dos registradores de auditoria da entrada de terceiros (Fase 1).

Cobrem o contrato fixado pelo PO: diff real com estado_anterior, snapshot
fallback sob '_snapshot' sem ele, chaves reservadas, coluna `acao`, 2x = 2
eventos e não-propagação de falha. Nenhum callsite em views/serializers ainda
usa estas funções (PR 3 fará isso); aqui elas são exercitadas direto.
"""

from __future__ import annotations

from datetime import datetime, timezone

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.auditoria.models import RegistroAuditoria
from apps.fiscal.auditoria_entrada import (
    registrar_conferencia_nfe,
    registrar_devolucao_nfe,
    registrar_estoque_nfe,
    registrar_financeiro_cte,
    registrar_financeiro_nfe,
)
from apps.fiscal.models import (
    CTeHistoricoImportado,
    NFeEntradaConferencia,
    NFeEntradaHistoricaImportada,
)


def _nova_historica(chave: str) -> NFeEntradaHistoricaImportada:
    return NFeEntradaHistoricaImportada.objects.create(
        chave_acesso=chave,
        numero='1',
        dh_emissao=datetime(2026, 11, 1, 12, 0, 0, tzinfo=timezone.utc),
        valor_total_nf='100.00',
    )


def _novo_cte(chave: str) -> CTeHistoricoImportado:
    return CTeHistoricoImportado.objects.create(
        chave_acesso=chave,
        numero='9',
        dh_emissao=datetime(2026, 11, 1, 12, 0, 0, tzinfo=timezone.utc),
        valor_total_servico='50.00',
    )


class RegistrarEntradaTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            'aud_entrada', 'aud_entrada@test.local', 'x'
        )
        self.nfe = _nova_historica('5' * 44)
        self.conferencia = NFeEntradaConferencia.objects.create(
            nf_entrada_historica=self.nfe,
            status=NFeEntradaConferencia.Status.PENDENTE,
        )

    # ---- 1) registrar_conferencia_nfe: diff real com estado_anterior ----

    def test_conferencia_diff_registra_registroauditoria(self):
        antes = {
            'status': NFeEntradaConferencia.Status.PENDENTE,
            'estoque_aplicado_por_id': None,
        }
        self.conferencia.status = NFeEntradaConferencia.Status.CONFERIDA
        self.conferencia.save()

        registro = registrar_conferencia_nfe(self.conferencia, self.usuario, 'conferir', estado_anterior=antes)

        self.assertIsNotNone(registro)
        assert registro is not None
        self.assertEqual(registro.app_label, 'fiscal')
        self.assertEqual(registro.model_name, 'nfeentradaconferencia')
        self.assertEqual(registro.object_id, self.conferencia.pk)
        self.assertEqual(registro.operacao, 'UPDATE')
        self.assertEqual(registro.acao, 'conferir')
        self.assertEqual(registro.ator_id, self.usuario.pk)
        # formato before/after idêntico ao de registrar_nfe_entrada (um parser só)
        self.assertEqual(
            registro.alteracoes['status'],
            {'antes': 'PENDENTE', 'depois': 'CONFERIDA'},
        )
        self.assertNotIn('_snapshot', registro.alteracoes)
        self.assertEqual(RegistroAuditoria.objects.count(), 1)

    # ---- 2) registrar_estoque_nfe: snapshot fallback sem estado_anterior ----

    def test_estoque_sem_estado_anterior_grava_snapshot_e_detalhes(self):
        self.conferencia.estoque_aplicado_por = self.usuario
        self.conferencia.save()

        registro = registrar_estoque_nfe(
            self.conferencia,
            self.usuario,
            'aplicar_estoque',
            detalhes={'itens': 3, 'corridas': ['2026-11']},
        )

        self.assertIsNotNone(registro)
        assert registro is not None
        self.assertEqual(registro.acao, 'aplicar_estoque')
        # evento puro: sem diff de campos; estado no momento da ação sob chave reservada
        self.assertIn('_snapshot', registro.alteracoes)
        snapshot = registro.alteracoes['_snapshot']
        self.assertEqual(snapshot['estoque_aplicado_por_id'], self.usuario.pk)
        self.assertEqual(snapshot['status'], self.conferencia.status)
        # snapshot respeita a allowlist: nada de campos fora dela (ex.: atualizado_em)
        self.assertNotIn('atualizado_em', snapshot)
        self.assertNotIn('criado_em', snapshot)
        self.assertEqual(registro.alteracoes['_detalhes'], {'itens': 3, 'corridas': ['2026-11']})

    # ---- 3) registrar_financeiro_nfe ----

    def test_financeiro_nfe_registra_na_historica_com_acao(self):
        registro = registrar_financeiro_nfe(self.nfe, self.usuario, 'gerar_contas_pagar')

        self.assertIsNotNone(registro)
        assert registro is not None
        self.assertEqual(registro.model_name, 'nfeentradahistoricaimportada')
        self.assertEqual(registro.object_id, self.nfe.pk)
        self.assertEqual(registro.acao, 'gerar_contas_pagar')
        snapshot = registro.alteracoes['_snapshot']
        self.assertEqual(snapshot['chave_acesso'], self.nfe.chave_acesso)
        self.assertEqual(snapshot['valor_total_nf'], '100.00')
        # corpo JSON/xml nunca entra no snapshot
        self.assertNotIn('xml_conteudo', snapshot)
        self.assertNotIn('emit_json', snapshot)

    # ---- 4) registrar_financeiro_cte ----

    def test_financeiro_cte_grava_campos_prioritarios_no_snapshot(self):
        cte = _novo_cte('7' * 44)
        cte.conferido_por = self.usuario
        cte.rateado_por = self.usuario
        cte.situacao_financeira_por = self.usuario
        cte.situacao_financeira_frete = CTeHistoricoImportado.SituacaoFinanceiraFrete.CP_GERADO
        cte.save()

        registro = registrar_financeiro_cte(cte, self.usuario, 'gerar_contas_pagar')

        self.assertIsNotNone(registro)
        assert registro is not None
        self.assertEqual(registro.model_name, 'ctehistoricoimportado')
        self.assertEqual(registro.acao, 'gerar_contas_pagar')
        snapshot = registro.alteracoes['_snapshot']
        # campos críticos pedidos pelo PO presentes
        for campo in (
            'conferido_por_id',
            'rateado_por_id',
            'situacao_financeira_por_id',
            'situacao_financeira_frete',
            'status_conferencia',
        ):
            self.assertIn(campo, snapshot)

    # ---- 5) registrar_devolucao_nfe: acao default do contrato ----

    def test_devolucao_usa_acao_default_e_2_chamadas_sao_2_eventos(self):
        primeiro = registrar_devolucao_nfe(self.conferencia, self.usuario)
        segundo = registrar_devolucao_nfe(self.conferencia, self.usuario)

        self.assertIsNotNone(primeiro)
        self.assertIsNotNone(segundo)
        assert primeiro is not None and segundo is not None
        self.assertEqual(primeiro.acao, 'gerar_saida_devolucao_compra')
        # idempotência recusada por contrato: fato histórico, não upsert
        self.assertNotEqual(primeiro.id, segundo.id)
        self.assertEqual(
            RegistroAuditoria.objects.filter(acao='gerar_saida_devolucao_compra').count(),
            2,
        )

    # ---- robustez: falha nunca propaga; entidade fora do escopo não grava ----

    def test_entidade_fora_do_escopo_devolve_none_sem_gravar(self):
        class _Nada:
            class _meta:
                app_label = 'fiscal'
                model_name = 'algumacoisa'

            pk = 1

        antes = RegistroAuditoria.objects.count()
        self.assertIsNone(registrar_conferencia_nfe(_Nada(), self.usuario, 'conferir'))
        self.assertEqual(RegistroAuditoria.objects.count(), antes)

    def test_erro_interno_e_engolido_e_logado(self):
        class _Explosiva:
            class _meta:
                app_label = 'fiscal'
                model_name = 'nfeentradahistoricaimportada'

            pk = 1
            chave_acesso = property(lambda self: (_ for _ in ()).throw(RuntimeError('boom')))

        antes = RegistroAuditoria.objects.count()
        # capturar_snapshot vai estourar em getattr -> try/except deve engolir
        self.assertIsNone(registrar_financeiro_nfe(_Explosiva(), self.usuario, 'gerar_contas_pagar'))
        self.assertEqual(RegistroAuditoria.objects.count(), antes)
