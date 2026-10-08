"""Fase E.3 — permissões mínimas nos viewsets de Qualidade (403/200 por codename Django)."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Fornecedor
from apps.qualidade.models import Certificado, CertificadoFornecedorEntrada, CertificadoQualidade


def _refetch_user(user):
    return get_user_model().objects.get(pk=user.pk)


def _grant_model_perms(user, model, *codenames: str):
    ct = ContentType.objects.get_for_model(model)
    for codename in codenames:
        user.user_permissions.add(Permission.objects.get(content_type=ct, codename=codename))
    return _refetch_user(user)


class CertificadoQualidadePermissionsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cliente = Cliente.objects.create(
            razao_social='Cliente Perm CQ',
            cnpj='11.111.111/0001-11',
        )
        cls.cq = CertificadoQualidade.objects.create(
            status=CertificadoQualidade.Status.RASCUNHO,
            tipo_certificado=CertificadoQualidade.TipoCertificado.PADRAO_POR_NFE,
            numero='',
            serie='',
            cliente=cls.cliente,
            cliente_nome_snapshot=cls.cliente.razao_social,
            cliente_cnpj_snapshot=cls.cliente.cnpj,
            nota_fiscal_numero='perm-700',
        )

    def setUp(self):
        User = get_user_model()
        self.no_perm = User.objects.create_user('cq_noperm', 'cq_np@test.com', 'x')
        self.view_only = _grant_model_perms(
            User.objects.create_user('cq_view', 'cq_v@test.com', 'x'),
            CertificadoQualidade,
            'view_certificadoqualidade',
        )
        self.add_only = _grant_model_perms(
            User.objects.create_user('cq_add', 'cq_a@test.com', 'x'),
            CertificadoQualidade,
            'add_certificadoqualidade',
        )
        self.change_only = _grant_model_perms(
            User.objects.create_user('cq_change', 'cq_c@test.com', 'x'),
            CertificadoQualidade,
            'change_certificadoqualidade',
        )
        self.delete_only = _grant_model_perms(
            User.objects.create_user('cq_del', 'cq_d@test.com', 'x'),
            CertificadoQualidade,
            'delete_certificadoqualidade',
        )
        self.super = User.objects.create_superuser('cq_su', 'cq_su@test.com', 'x')

    def _payload_rascunho(self, suffix: str):
        return {
            'status': CertificadoQualidade.Status.RASCUNHO,
            'tipo_certificado': CertificadoQualidade.TipoCertificado.PADRAO_POR_NFE,
            'numero': '',
            'serie': '',
            'nota_fiscal_numero': suffix,
            'cliente': self.cliente.id,
            'cliente_nome_snapshot': self.cliente.razao_social,
            'cliente_cnpj_snapshot': self.cliente.cnpj,
            'pedido_cliente': '',
            'data_emissao': None,
            'observacoes': '',
            'texto_padrao': '',
            'itens': [],
        }

    def test_list_retrieve_sem_permissao_403(self):
        c = APIClient()
        c.force_authenticate(self.no_perm)
        self.assertEqual(c.get(reverse('certificado-qualidade-list'), HTTP_HOST='localhost').status_code, 403)
        self.assertEqual(
            c.get(reverse('certificado-qualidade-detail', args=[self.cq.pk]), HTTP_HOST='localhost').status_code,
            403,
        )

    def test_list_retrieve_com_view_200(self):
        c = APIClient()
        c.force_authenticate(self.view_only)
        self.assertEqual(c.get(reverse('certificado-qualidade-list'), HTTP_HOST='localhost').status_code, 200)
        self.assertEqual(
            c.get(reverse('certificado-qualidade-detail', args=[self.cq.pk]), HTTP_HOST='localhost').status_code,
            200,
        )

    def test_create_sem_add_403_com_add_201(self):
        c = APIClient()
        c.force_authenticate(self.view_only)
        r = c.post(
            reverse('certificado-qualidade-list'),
            self._payload_rascunho('perm-701'),
            format='json',
            HTTP_HOST='localhost',
        )
        self.assertEqual(r.status_code, 403)

        c.force_authenticate(self.add_only)
        r2 = c.post(
            reverse('certificado-qualidade-list'),
            self._payload_rascunho('perm-702'),
            format='json',
            HTTP_HOST='localhost',
        )
        self.assertEqual(r2.status_code, 201)

    def test_patch_sem_change_403_com_change_200(self):
        c = APIClient()
        c.force_authenticate(self.view_only)
        r = c.patch(
            reverse('certificado-qualidade-detail', args=[self.cq.pk]),
            {'observacoes': 'x'},
            format='json',
            HTTP_HOST='localhost',
        )
        self.assertEqual(r.status_code, 403)

        c.force_authenticate(self.change_only)
        r2 = c.patch(
            reverse('certificado-qualidade-detail', args=[self.cq.pk]),
            {'observacoes': 'perm ok'},
            format='json',
            HTTP_HOST='localhost',
        )
        self.assertEqual(r2.status_code, 200)

    def test_destroy_sem_delete_403_com_delete_204(self):
        cq2 = CertificadoQualidade.objects.create(
            status=CertificadoQualidade.Status.RASCUNHO,
            tipo_certificado=CertificadoQualidade.TipoCertificado.PADRAO_POR_NFE,
            numero='',
            serie='',
            nota_fiscal_numero='perm-703',
        )
        c = APIClient()
        c.force_authenticate(self.change_only)
        r = c.delete(reverse('certificado-qualidade-detail', args=[cq2.pk]), HTTP_HOST='localhost')
        self.assertEqual(r.status_code, 403)

        c.force_authenticate(self.delete_only)
        r2 = c.delete(reverse('certificado-qualidade-detail', args=[cq2.pk]), HTTP_HOST='localhost')
        self.assertEqual(r2.status_code, 204)

    def test_pdf_view_200_sem_permissao_403(self):
        c = APIClient()
        c.force_authenticate(self.no_perm)
        url = reverse('certificado-qualidade-pdf', kwargs={'pk': self.cq.pk})
        self.assertEqual(c.get(url, HTTP_HOST='localhost').status_code, 403)

        c.force_authenticate(self.view_only)
        self.assertEqual(c.get(url, HTTP_HOST='localhost').status_code, 200)

    def test_corridas_disponiveis_exige_change(self):
        c = APIClient()
        url = reverse('certificado-qualidade-corridas-disponiveis')
        c.force_authenticate(self.view_only)
        self.assertEqual(c.get(url, {'produto_id': '1'}, HTTP_HOST='localhost').status_code, 403)
        c.force_authenticate(self.change_only)
        self.assertEqual(c.get(url, {'produto_id': '1'}, HTTP_HOST='localhost').status_code, 200)

    def test_preencher_por_nfe_exige_change(self):
        c = APIClient()
        url = reverse('certificado-qualidade-preencher-por-nfe')
        c.force_authenticate(self.view_only)
        self.assertEqual(c.post(url, {}, format='json', HTTP_HOST='localhost').status_code, 403)
        c.force_authenticate(self.change_only)
        self.assertEqual(c.post(url, {}, format='json', HTTP_HOST='localhost').status_code, 400)

    def test_superuser_list_200(self):
        c = APIClient()
        c.force_authenticate(self.super)
        self.assertEqual(c.get(reverse('certificado-qualidade-list'), HTTP_HOST='localhost').status_code, 200)

    def test_staff_sem_permissao_explicita_403(self):
        User = get_user_model()
        staff = User.objects.create_user('cq_staff', 'cq_st@test.com', 'x', is_staff=True)
        c = APIClient()
        c.force_authenticate(staff)
        self.assertEqual(c.get(reverse('certificado-qualidade-list'), HTTP_HOST='localhost').status_code, 403)


class CertificadoFornecedorEntradaPermissionsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.forn = Fornecedor.objects.create(
            razao_social='Forn Perm CF',
            cnpj='22.222.222/0001-22',
        )
        cls.cf = CertificadoFornecedorEntrada.objects.create(
            status=CertificadoFornecedorEntrada.Status.RASCUNHO,
            numero_certificado_fornecedor='',
            fornecedor=cls.forn,
            fornecedor_nome_snapshot=cls.forn.razao_social,
            fornecedor_cnpj_snapshot=cls.forn.cnpj,
            numero_nf_entrada='',
        )

    def setUp(self):
        User = get_user_model()
        self.no_perm = User.objects.create_user('cf_noperm', 'cf_np@test.com', 'x')
        self.view_only = _grant_model_perms(
            User.objects.create_user('cf_view', 'cf_v@test.com', 'x'),
            CertificadoFornecedorEntrada,
            'view_certificadofornecedorentrada',
        )
        self.add_only = _grant_model_perms(
            User.objects.create_user('cf_add', 'cf_a@test.com', 'x'),
            CertificadoFornecedorEntrada,
            'add_certificadofornecedorentrada',
        )
        self.change_only = _grant_model_perms(
            User.objects.create_user('cf_change', 'cf_c@test.com', 'x'),
            CertificadoFornecedorEntrada,
            'change_certificadofornecedorentrada',
        )
        self.delete_only = _grant_model_perms(
            User.objects.create_user('cf_del', 'cf_d@test.com', 'x'),
            CertificadoFornecedorEntrada,
            'delete_certificadofornecedorentrada',
        )
        self.super = User.objects.create_superuser('cf_su', 'cf_su@test.com', 'x')

    def _payload_rascunho(self, nf_num: str):
        return {
            'status': CertificadoFornecedorEntrada.Status.RASCUNHO,
            'numero_certificado_fornecedor': '',
            'fornecedor': None,
            'fornecedor_nome_snapshot': '',
            'fornecedor_cnpj_snapshot': '',
            'numero_nf_entrada': nf_num,
            'itens': [],
        }

    def test_list_retrieve_sem_permissao_403_com_view_200(self):
        c = APIClient()
        c.force_authenticate(self.no_perm)
        self.assertEqual(c.get(reverse('certificado-fornecedor-list'), HTTP_HOST='localhost').status_code, 403)
        c.force_authenticate(self.view_only)
        self.assertEqual(c.get(reverse('certificado-fornecedor-list'), HTTP_HOST='localhost').status_code, 200)
        self.assertEqual(
            c.get(reverse('certificado-fornecedor-detail', args=[self.cf.pk]), HTTP_HOST='localhost').status_code,
            200,
        )

    def test_create_add_destroy_delete(self):
        c = APIClient()
        c.force_authenticate(self.view_only)
        self.assertEqual(
            c.post(
                reverse('certificado-fornecedor-list'),
                self._payload_rascunho('800'),
                format='json',
                HTTP_HOST='localhost',
            ).status_code,
            403,
        )
        c.force_authenticate(self.add_only)
        r = c.post(
            reverse('certificado-fornecedor-list'),
            self._payload_rascunho('801'),
            format='json',
            HTTP_HOST='localhost',
        )
        self.assertEqual(r.status_code, 201)
        new_id = r.json()['id']

        c.force_authenticate(self.change_only)
        self.assertEqual(
            c.patch(
                reverse('certificado-fornecedor-detail', args=[new_id]),
                {'observacoes': 'y'},
                format='json',
                HTTP_HOST='localhost',
            ).status_code,
            200,
        )

        c.force_authenticate(self.delete_only)
        self.assertEqual(
            c.delete(reverse('certificado-fornecedor-detail', args=[new_id]), HTTP_HOST='localhost').status_code,
            204,
        )

    def test_buscar_dados_tecnicos_e_preencher_exigem_change(self):
        c = APIClient()
        u_busca = reverse('certificado-fornecedor-buscar-dados-tecnicos')
        u_pre = reverse('certificado-fornecedor-preencher-por-nfe-entrada')
        c.force_authenticate(self.view_only)
        self.assertEqual(c.get(u_busca, HTTP_HOST='localhost').status_code, 403)
        self.assertEqual(c.post(u_pre, {}, format='json', HTTP_HOST='localhost').status_code, 403)
        c.force_authenticate(self.change_only)
        self.assertEqual(c.get(u_busca, HTTP_HOST='localhost').status_code, 200)
        self.assertEqual(c.post(u_pre, {}, format='json', HTTP_HOST='localhost').status_code, 400)


class CertificadoLegacyPermissionsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.no_perm = User.objects.create_user('leg_nop', 'leg_np@test.com', 'x')
        self.view_only = _grant_model_perms(
            User.objects.create_user('leg_v', 'leg_v@test.com', 'x'),
            Certificado,
            'view_certificado',
        )
        self.super = User.objects.create_superuser('leg_su', 'leg_su@test.com', 'x')

    def test_list_sem_permissao_403_com_view_ou_super_200(self):
        c = APIClient()
        c.force_authenticate(self.no_perm)
        self.assertEqual(c.get(reverse('certificado-list'), HTTP_HOST='localhost').status_code, 403)
        c.force_authenticate(self.view_only)
        self.assertEqual(c.get(reverse('certificado-list'), HTTP_HOST='localhost').status_code, 200)
        c.force_authenticate(self.super)
        self.assertEqual(c.get(reverse('certificado-list'), HTTP_HOST='localhost').status_code, 200)
