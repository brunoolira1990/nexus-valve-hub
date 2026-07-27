"""Liberação financeira da Proposta Comercial — MVP."""

from __future__ import annotations

import ast
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.comercial.analise_financeira_servico import (
    LiberacaoFinanceiraBloqueio,
    aprovar_como_solicitado,
    aprovar_com_ajuste,
    garantir_liberacao_para_conversao,
    nao_aprovar,
    solicitar_analise,
)
from apps.comercial.converter_proposta_pedido import converter_proposta_em_pedido_venda
from apps.comercial.models import (
    AnaliseFinanceiraProposta,
    AnaliseFinanceiraPropostaEvento,
    PedidoVenda,
    Proposta,
)
from apps.comercial.serializers import recalcular_proposta
from apps.comercial.tests.test_converter_proposta_pedido import _item, _produto, _proposta_aprovada
from apps.financeiro.models import TituloFinanceiro


def _perm(codename: str) -> Permission:
    return Permission.objects.get(codename=codename)


def _user(username: str, *, perms: list[str] | None = None):
    u = get_user_model().objects.create_user(username, f'{username}@test.local', 'secret')
    if perms:
        for codename in perms:
            u.user_permissions.add(_perm(codename))
    return u


def _proposta_prazo(dias: list[int], *, valor: Decimal = Decimal('200')) -> Proposta:
    p = _proposta_aprovada()
    p.condicao_pagamento_texto = '/'.join(str(d) for d in dias)
    p.dias_parcelas = list(dias)
    p.quantidade_parcelas = len(dias)
    p.valor_total = valor
    p.save()
    prod = _produto()
    _item(p, prod)
    recalcular_proposta(p)
    p.refresh_from_db()
    return p


class LiberacaoFinanceiraGuardTests(TestCase):
    def test_a_vista_converte_sem_analise(self):
        p = _proposta_aprovada()
        prod = _produto()
        _item(p, prod)
        recalcular_proposta(p)
        r = converter_proposta_em_pedido_venda(p)
        self.assertTrue(r['pedido_id'])

    def test_30_ddl_sem_analise_bloqueia(self):
        p = _proposta_prazo([30])
        with self.assertRaises(LiberacaoFinanceiraBloqueio) as ctx:
            garantir_liberacao_para_conversao(p)
        self.assertEqual(ctx.exception.code, 'SEM_APROVACAO')

    def test_30_60_sem_analise_bloqueia(self):
        p = _proposta_prazo([30, 60])
        with self.assertRaises(LiberacaoFinanceiraBloqueio):
            converter_proposta_em_pedido_venda(p)
        self.assertFalse(PedidoVenda.objects.filter(proposta=p).exists())

    def test_entrada_saldo_sem_analise_bloqueia(self):
        p = _proposta_prazo([0, 30])
        with self.assertRaises(LiberacaoFinanceiraBloqueio):
            garantir_liberacao_para_conversao(p)

    def test_ambigua_bloqueia(self):
        p = _proposta_aprovada()
        p.dias_parcelas = []
        p.condicao_pagamento_texto = 'a combinar'
        p.save()
        _item(p, _produto())
        with self.assertRaises(LiberacaoFinanceiraBloqueio) as ctx:
            garantir_liberacao_para_conversao(p)
        self.assertEqual(ctx.exception.code, 'CONDICAO_AMBIGUA')

    def test_aprovacao_permite_conversao(self):
        user = _user('fin_ok')
        p = _proposta_prazo([30, 60])
        analise = solicitar_analise(p, usuario=user, observacao_vendedor='ok')
        aprovar_como_solicitado(analise, usuario=user)
        r = converter_proposta_em_pedido_venda(p)
        self.assertTrue(r['pedido_id'])

    def test_valor_maior_bloqueia(self):
        user = _user('fin_val')
        p = _proposta_prazo([30], valor=Decimal('100'))
        analise = solicitar_analise(p, usuario=user)
        aprovar_como_solicitado(analise, usuario=user, valor_maximo=Decimal('100'))
        p.valor_total = Decimal('150')
        p.save(update_fields=['valor_total'])
        with self.assertRaises(LiberacaoFinanceiraBloqueio) as ctx:
            garantir_liberacao_para_conversao(p)
        self.assertEqual(ctx.exception.code, 'VALOR_EXCEDE')

    def test_valor_menor_mesma_condicao_ok(self):
        user = _user('fin_menor')
        p = _proposta_prazo([30], valor=Decimal('200'))
        analise = solicitar_analise(p, usuario=user)
        aprovar_como_solicitado(analise, usuario=user, valor_maximo=Decimal('200'))
        p.valor_total = Decimal('150')
        p.save(update_fields=['valor_total'])
        garantir_liberacao_para_conversao(p)

    def test_ajuste_so_vale_apos_proposta_bater_dias(self):
        user = _user('fin_aj')
        p = _proposta_prazo([30, 60])
        analise = solicitar_analise(p, usuario=user)
        aprovar_com_ajuste(
            analise,
            usuario=user,
            dias_aprovados=[0, 30],
            justificativa='Entrada obrigatória',
        )
        with self.assertRaises(LiberacaoFinanceiraBloqueio) as ctx:
            garantir_liberacao_para_conversao(p)
        self.assertEqual(ctx.exception.code, 'CONDICAO_DIVERGENTE')
        p.dias_parcelas = [0, 30]
        p.condicao_pagamento_texto = '0/30'
        p.quantidade_parcelas = 2
        p.save()
        garantir_liberacao_para_conversao(p)

    def test_expirada_bloqueia(self):
        user = _user('fin_exp')
        p = _proposta_prazo([30])
        analise = solicitar_analise(p, usuario=user)
        aprovar_como_solicitado(
            analise,
            usuario=user,
            valida_ate=timezone.localdate() - timedelta(days=1),
        )
        with self.assertRaises(LiberacaoFinanceiraBloqueio) as ctx:
            garantir_liberacao_para_conversao(p)
        self.assertEqual(ctx.exception.code, 'EXPIRADA')

    def test_texto_diferente_mesmos_dias_ok(self):
        user = _user('fin_txt')
        p = _proposta_prazo([30, 60])
        analise = solicitar_analise(p, usuario=user)
        aprovar_como_solicitado(analise, usuario=user)
        p.condicao_pagamento_texto = '30/60 DDL'
        p.save(update_fields=['condicao_pagamento_texto'])
        garantir_liberacao_para_conversao(p)

    def test_nao_altera_cliente_nem_cria_cr(self):
        user = _user('fin_side')
        p = _proposta_prazo([30])
        limite_antes = p.cliente.limite_credito
        cr_antes = TituloFinanceiro.objects.count()
        analise = solicitar_analise(p, usuario=user)
        aprovar_como_solicitado(analise, usuario=user)
        p.cliente.refresh_from_db()
        self.assertEqual(p.cliente.limite_credito, limite_antes)
        self.assertEqual(TituloFinanceiro.objects.count(), cr_antes)
        self.assertEqual(p.dias_parcelas, [30])

    def test_analise_pendente_codigo_especifico(self):
        user = _user('fin_pend')
        p = _proposta_prazo([30])
        solicitar_analise(p, usuario=user)
        with self.assertRaises(LiberacaoFinanceiraBloqueio) as ctx:
            garantir_liberacao_para_conversao(p)
        self.assertEqual(ctx.exception.code, 'ANALISE_PENDENTE')
        self.assertIn('code', ctx.exception.as_dict())
        self.assertIn('detail', ctx.exception.as_dict())

    def test_nao_aprovada_codigo_especifico(self):
        user = _user('fin_nao')
        p = _proposta_prazo([30])
        analise = solicitar_analise(p, usuario=user)
        nao_aprovar(analise, usuario=user, justificativa='Risco elevado')
        with self.assertRaises(LiberacaoFinanceiraBloqueio) as ctx:
            garantir_liberacao_para_conversao(p)
        self.assertEqual(ctx.exception.code, 'ANALISE_NAO_APROVADA')


class LiberacaoFinanceiraApiTests(APITestCase):
    def setUp(self):
        self.vendedor = _user(
            'vend_af',
            perms=['view_analisefinanceiraproposta', 'solicitar_analisefinanceiraproposta'],
        )
        self.financeiro = _user(
            'fin_af',
            perms=[
                'view_analisefinanceiraproposta',
                'decidir_analisefinanceiraproposta',
                'ver_detalhe_financeiro_analisefinanceiraproposta',
            ],
        )

    def test_solicitar_e_aprovar_fluxo(self):
        p = _proposta_prazo([30, 60])
        self.client.force_authenticate(self.vendedor)
        r = self.client.post(
            f'/api/propostas/{p.pk}/analise-financeira/solicitar/',
            {'observacao_vendedor': 'Cliente pediu 30/60'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        analise_id = r.data['id']
        self.assertEqual(r.data['status'], 'PENDENTE')
        self.assertEqual(r.data['condicao_solicitada']['dias'], [30, 60])

        # vendedor não decide
        r_deny = self.client.post(f'/api/analises-financeiras/{analise_id}/aprovar/', {}, format='json')
        self.assertEqual(r_deny.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(self.financeiro)
        r2 = self.client.post(f'/api/analises-financeiras/{analise_id}/aprovar/', {}, format='json')
        self.assertEqual(r2.status_code, status.HTTP_200_OK, r2.data)
        self.assertEqual(r2.data['status'], 'APROVADA')

        r3 = self.client.post(f'/api/propostas/{p.pk}/converter-pedido/', {}, format='json')
        self.assertEqual(r3.status_code, status.HTTP_201_CREATED, r3.data)

    def test_ajuste_exige_justificativa(self):
        p = _proposta_prazo([30])
        self.client.force_authenticate(self.vendedor)
        analise_id = self.client.post(
            f'/api/propostas/{p.pk}/analise-financeira/solicitar/',
            {},
            format='json',
        ).data['id']
        self.client.force_authenticate(self.financeiro)
        r = self.client.post(
            f'/api/analises-financeiras/{analise_id}/aprovar-com-ajuste/',
            {'dias_aprovados': [0], 'justificativa': ''},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_indicadores_nao_viram_zero_quando_indisponiveis(self):
        p = _proposta_prazo([30])
        self.client.force_authenticate(self.vendedor)
        r = self.client.post(f'/api/propostas/{p.pk}/analise-financeira/solicitar/', {}, format='json')
        # vendedor sem detalhe: resumo restrito
        ind = r.data['snapshot_indicadores']
        self.assertTrue(ind.get('resumo_restrito'))

        self.client.force_authenticate(self.financeiro)
        detalhe = self.client.get(f'/api/analises-financeiras/{r.data["id"]}/').data
        ind_f = detalhe['snapshot_indicadores']
        self.assertEqual(ind_f['qualidade_dados'], 'PARCIAL')
        self.assertFalse(ind_f['percentual_pontualidade']['disponivel'])
        self.assertIsNone(ind_f['percentual_pontualidade']['valor'])
        self.assertTrue(ind_f['contas_receber']['disponivel'])
        self.assertEqual(ind_f['contas_receber']['saldo_aberto'], '0')

    def test_401(self):
        p = _proposta_prazo([30])
        r = self.client.get(f'/api/propostas/{p.pk}/analise-financeira/')
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_change_proposta_nao_decide_nem_solicita(self):
        only_change = _user('only_chg_prop', perms=['change_proposta'])
        p = _proposta_prazo([30])
        self.client.force_authenticate(only_change)
        r_sol = self.client.post(f'/api/propostas/{p.pk}/analise-financeira/solicitar/', {}, format='json')
        self.assertEqual(r_sol.status_code, status.HTTP_403_FORBIDDEN)

        vendedor = self.vendedor
        self.client.force_authenticate(vendedor)
        analise_id = self.client.post(
            f'/api/propostas/{p.pk}/analise-financeira/solicitar/', {}, format='json'
        ).data['id']
        self.client.force_authenticate(only_change)
        r_dec = self.client.post(f'/api/analises-financeiras/{analise_id}/aprovar/', {}, format='json')
        self.assertEqual(r_dec.status_code, status.HTTP_403_FORBIDDEN)

    def test_change_titulo_nao_decide(self):
        only_titulo = _user('only_titulo', perms=['change_titulofinanceiro', 'view_titulofinanceiro'])
        p = _proposta_prazo([30])
        self.client.force_authenticate(self.vendedor)
        analise_id = self.client.post(
            f'/api/propostas/{p.pk}/analise-financeira/solicitar/', {}, format='json'
        ).data['id']
        self.client.force_authenticate(only_titulo)
        r = self.client.post(f'/api/analises-financeiras/{analise_id}/aprovar/', {}, format='json')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_decidir_com_permissao_especifica(self):
        decisor = _user(
            'decisor_esp',
            perms=['view_analisefinanceiraproposta', 'decidir_analisefinanceiraproposta'],
        )
        p = _proposta_prazo([30])
        self.client.force_authenticate(self.vendedor)
        analise_id = self.client.post(
            f'/api/propostas/{p.pk}/analise-financeira/solicitar/', {}, format='json'
        ).data['id']
        self.client.force_authenticate(decisor)
        r = self.client.post(f'/api/analises-financeiras/{analise_id}/aprovar/', {}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)

    def test_sem_detalhe_nao_ve_indicadores_restritos(self):
        vendedor = self.vendedor
        p = _proposta_prazo([30])
        self.client.force_authenticate(vendedor)
        analise_id = self.client.post(
            f'/api/propostas/{p.pk}/analise-financeira/solicitar/', {}, format='json'
        ).data['id']
        r = self.client.get(f'/api/analises-financeiras/{analise_id}/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        ind = r.data['snapshot_indicadores']
        self.assertTrue(ind.get('resumo_restrito'))
        self.assertNotIn('contas_receber', ind)
        self.assertNotIn('exposicao', ind)
        self.assertFalse(r.data['permissoes']['pode_ver_detalhe_financeiro'])

    def test_vendedor_ve_resumo_situacao(self):
        p = _proposta_prazo([30])
        self.client.force_authenticate(self.vendedor)
        r = self.client.get(f'/api/propostas/{p.pk}/analise-financeira/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn('situacao', r.data)
        self.assertTrue(r.data['situacao']['permissoes']['pode_solicitar'])
        self.assertFalse(r.data['situacao']['permissoes']['pode_decidir'])

    def test_autenticado_sem_permissao_403(self):
        sem = _user('sem_perm_af')
        p = _proposta_prazo([30])
        self.client.force_authenticate(sem)
        r = self.client.get(f'/api/propostas/{p.pk}/analise-financeira/')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_conversao_bloqueada_retorna_contrato(self):
        p = _proposta_prazo([30])
        self.client.force_authenticate(self.financeiro)
        # financeiro precisa change_proposta para converter — simula via superuser path:
        # autentica vendedor com change se necessário; helper da conversão usa get_object.
        # Usa force_authenticate com usuário que tem permissão de proposta.
        conv = _user(
            'conv_af',
            perms=['change_proposta', 'view_analisefinanceiraproposta'],
        )
        self.client.force_authenticate(conv)
        pedidos_antes = PedidoVenda.objects.count()
        r = self.client.post(f'/api/propostas/{p.pk}/converter-pedido/', {}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.data.get('code'), 'SEM_APROVACAO')
        self.assertTrue(r.data.get('detail'))
        self.assertEqual(PedidoVenda.objects.count(), pedidos_antes)
        p.refresh_from_db()
        self.assertEqual(p.status, 'Aprovada')

    def test_nao_existe_endpoint_escrita_evento(self):
        self.client.force_authenticate(self.financeiro)
        for method in ('post', 'put', 'patch', 'delete'):
            r = getattr(self.client, method)('/api/analises-financeiras-eventos/', {}, format='json')
            self.assertIn(r.status_code, (404, 405))


class LiberacaoFinanceiraEventoPoliticaTests(TestCase):
    def test_evento_somente_permissao_view(self):
        ct = ContentType.objects.get_for_model(AnaliseFinanceiraPropostaEvento)
        codenames = set(Permission.objects.filter(content_type=ct).values_list('codename', flat=True))
        self.assertEqual(codenames, {'view_analisefinanceirapropostaevento'})
        self.assertNotIn('add_analisefinanceirapropostaevento', codenames)
        self.assertNotIn('change_analisefinanceirapropostaevento', codenames)
        self.assertNotIn('delete_analisefinanceirapropostaevento', codenames)

    def test_analise_tem_permissoes_customizadas(self):
        ct = ContentType.objects.get_for_model(AnaliseFinanceiraProposta)
        codenames = set(Permission.objects.filter(content_type=ct).values_list('codename', flat=True))
        for expected in (
            'view_analisefinanceiraproposta',
            'add_analisefinanceiraproposta',
            'change_analisefinanceiraproposta',
            'delete_analisefinanceiraproposta',
            'solicitar_analisefinanceiraproposta',
            'decidir_analisefinanceiraproposta',
            'ver_detalhe_financeiro_analisefinanceiraproposta',
        ):
            self.assertIn(expected, codenames)

    def test_falha_ao_criar_evento_reverte_decisao(self):
        user = _user('evt_fail')
        p = _proposta_prazo([30])
        analise = solicitar_analise(p, usuario=user)
        with patch(
            'apps.comercial.analise_financeira_servico.AnaliseFinanceiraPropostaEvento.objects.create',
            side_effect=RuntimeError('falha evento'),
        ):
            with self.assertRaises(RuntimeError):
                aprovar_como_solicitado(analise, usuario=user)
        analise.refresh_from_db()
        self.assertEqual(analise.status, AnaliseFinanceiraProposta.Status.PENDENTE)
        self.assertFalse(
            AnaliseFinanceiraPropostaEvento.objects.filter(
                analise=analise, tipo=AnaliseFinanceiraPropostaEvento.Tipo.APROVADA
            ).exists()
        )

    def test_aprovacao_e_evento_mesma_transacao(self):
        user = _user('evt_ok')
        p = _proposta_prazo([30])
        analise = solicitar_analise(p, usuario=user)
        aprovar_como_solicitado(analise, usuario=user)
        analise.refresh_from_db()
        self.assertEqual(analise.status, AnaliseFinanceiraProposta.Status.APROVADA)
        self.assertTrue(
            AnaliseFinanceiraPropostaEvento.objects.filter(
                analise=analise, tipo=AnaliseFinanceiraPropostaEvento.Tipo.APROVADA
            ).exists()
        )

    def test_exclusao_usuario_nao_apaga_evento(self):
        user = _user('evt_user')
        p = _proposta_prazo([30])
        analise = solicitar_analise(p, usuario=user)
        aprovar_como_solicitado(analise, usuario=user)
        evento = AnaliseFinanceiraPropostaEvento.objects.filter(analise=analise).latest('id')
        evento_id = evento.pk
        user.delete()
        evento = AnaliseFinanceiraPropostaEvento.objects.get(pk=evento_id)
        self.assertIsNone(evento.ator_id)


class LiberacaoFinanceiraMigrationTests(TestCase):
    def test_migration_0037_sem_backfill(self):
        path = Path(__file__).resolve().parents[1] / 'migrations' / '0037_analise_financeira_proposta_mvp.py'
        source = path.read_text(encoding='utf-8')
        tree = ast.parse(source)
        names = [n.id for n in ast.walk(tree) if isinstance(n, ast.Name)]
        self.assertNotIn('RunPython', names)
        self.assertNotIn('RunSQL', names)
        self.assertIn("default_permissions': ('view',)", source.replace('"', "'"))
