"""Testes do serviço e políticas de auditoria (sem HTTP)."""

from decimal import Decimal
from datetime import date

from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import TestCase

from apps.auditoria.models import RegistroAuditoria
from apps.auditoria.politicas import STRING_MAX_LEN
from apps.auditoria.servico import (
    montar_alteracoes,
    registrar_auditoria,
    serializar_valor_seguro,
)
from apps.auditoria.politicas import CLIENTE_ALLOWLIST, CLIENTE_CAMPOS_MASCARADOS


class AuditoriaServicoTests(TestCase):
    def test_serializa_decimal_e_data(self):
        self.assertEqual(serializar_valor_seguro(Decimal('10.50')), '10.50')
        self.assertEqual(serializar_valor_seguro(date(2026, 7, 24)), '2026-07-24')

    def test_limita_strings_longas(self):
        longo = 'x' * (STRING_MAX_LEN + 20)
        out = serializar_valor_seguro(longo)
        self.assertTrue(out.endswith('…'))
        self.assertEqual(len(out), STRING_MAX_LEN + 1)

    def test_campo_mascarado_sem_valor(self):
        alt = montar_alteracoes(
            {'email': 'a@test.local', 'nome_fantasia': 'A'},
            {'email': 'b@test.local', 'nome_fantasia': 'B'},
            allowlist=CLIENTE_ALLOWLIST,
            mascarados=CLIENTE_CAMPOS_MASCARADOS,
        )
        self.assertEqual(alt['email'], {'sensivel': True, 'alterado': True})
        self.assertNotIn('a@test.local', str(alt))
        self.assertEqual(alt['nome_fantasia']['antes'], 'A')
        self.assertEqual(alt['nome_fantasia']['depois'], 'B')

    def test_sem_diff_nao_persiste(self):
        reg = registrar_auditoria(
            usuario=None,
            app_label='cadastros',
            model_name='cliente',
            object_id=1,
            operacao='UPDATE',
            estado_anterior={'nome_fantasia': 'X'},
            estado_posterior={'nome_fantasia': 'X'},
            allowlist=CLIENTE_ALLOWLIST,
            mascarados=CLIENTE_CAMPOS_MASCARADOS,
        )
        self.assertIsNone(reg)
        self.assertEqual(RegistroAuditoria.objects.count(), 0)

    def test_rollback_nao_gera_evento(self):
        user = get_user_model().objects.create_user('aud_rb', 'aud_rb@test.local', 'x')
        try:
            with transaction.atomic():
                registrar_auditoria(
                    usuario=user,
                    app_label='cadastros',
                    model_name='cliente',
                    object_id=99,
                    operacao='UPDATE',
                    estado_anterior={'nome_fantasia': 'A'},
                    estado_posterior={'nome_fantasia': 'B'},
                    allowlist=CLIENTE_ALLOWLIST,
                    mascarados=CLIENTE_CAMPOS_MASCARADOS,
                )
                raise RuntimeError('force rollback')
        except RuntimeError:
            pass
        self.assertEqual(RegistroAuditoria.objects.count(), 0)

    def test_ator_removido_nao_apaga_historico(self):
        user = get_user_model().objects.create_user('aud_del', 'aud_del@test.local', 'x')
        registrar_auditoria(
            usuario=user,
            app_label='cadastros',
            model_name='cliente',
            object_id=7,
            operacao='CREATE',
            estado_anterior={},
            estado_posterior={'razao_social': 'Cli'},
            allowlist=CLIENTE_ALLOWLIST,
            mascarados=CLIENTE_CAMPOS_MASCARADOS,
        )
        user.delete()
        reg = RegistroAuditoria.objects.get()
        self.assertIsNone(reg.ator_id)
        self.assertEqual(reg.alteracoes['razao_social']['depois'], 'Cli')
