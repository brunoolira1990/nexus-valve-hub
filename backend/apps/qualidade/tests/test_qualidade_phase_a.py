"""Fase A — Qualidade: serializers, PDF e política de cancelado (sem estoque/NF fiscal)."""

from __future__ import annotations

import io

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Empresa, Fornecedor
from apps.qualidade.certificado_pdf import gerar_certificado_qualidade_pdf
from apps.qualidade.models import (
    CertificadoFornecedorEntrada,
    CertificadoQualidade,
    ItemCertificadoQualidade,
)
from apps.qualidade.serializers import CertificadoFornecedorEntradaSerializer, CertificadoQualidadeSerializer
from pypdf import PdfReader


def _item_padrao(**kwargs):
    base = {
        'ordem': 1,
        'codigo_produto': 'COD-1',
        'descricao_material': 'Material teste',
        'quantidade': '1.000',
        'unidade': 'PC',
        'norma': 'ASTM A105',
        'corrida': 'CR-001',
        'lote': '',
        'tipo_dados_tecnicos': 'PADRAO_ITEM',
        'ncm': '84818099',
        'incluir_no_certificado': True,
        'composicao_json': {'C': '0.25'},
        'ensaio_tracao_json': {'corpo_prova': 'CP1'},
        'ensaio_impacto_json': {},
    }
    base.update(kwargs)
    return base


class CertificadoQualidadeSerializerPhaseATests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            razao_social='Cliente Cert Ltda',
            cnpj='11.222.333/0001-81',
        )

    def test_rascunho_com_numero_nf_sem_cliente_passa(self):
        ser = CertificadoQualidadeSerializer(
            data={
                'status': CertificadoQualidade.Status.RASCUNHO,
                'tipo_certificado': CertificadoQualidade.TipoCertificado.PADRAO_POR_NFE,
                'numero': '',
                'serie': '',
                'nota_fiscal_numero': '98765',
                'cliente': None,
                'cliente_nome_snapshot': '',
                'cliente_cnpj_snapshot': '',
                'pedido_cliente': '',
                'data_emissao': None,
                'observacoes': '',
                'texto_padrao': '',
                'itens': [],
            }
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        obj = ser.save()
        self.assertEqual(obj.status, CertificadoQualidade.Status.RASCUNHO)
        self.assertEqual(obj.nota_fiscal_numero, '98765')

    def test_emissao_sem_numero_gera_automatico(self):
        ser = CertificadoQualidadeSerializer(
            data={
                'status': CertificadoQualidade.Status.EMITIDO,
                'tipo_certificado': CertificadoQualidade.TipoCertificado.PADRAO_POR_NFE,
                'numero': '',
                'serie': '',
                'nota_fiscal_numero': '500',
                'cliente': self.cliente.id,
                'cliente_nome_snapshot': self.cliente.razao_social,
                'cliente_cnpj_snapshot': self.cliente.cnpj,
                'data_emissao': '2026-03-10',
                'observacoes': '',
                'texto_padrao': 'Texto',
                'itens': [_item_padrao()],
            }
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        obj = ser.save()
        self.assertTrue(obj.numero.startswith('CQ-'))

    def test_emissao_sem_item_incluido_falha(self):
        ser = CertificadoQualidadeSerializer(
            data={
                'status': CertificadoQualidade.Status.EMITIDO,
                'tipo_certificado': CertificadoQualidade.TipoCertificado.PADRAO_POR_NFE,
                'numero': 'CQ100',
                'serie': '',
                'nota_fiscal_numero': '500',
                'cliente': self.cliente.id,
                'cliente_nome_snapshot': self.cliente.razao_social,
                'cliente_cnpj_snapshot': self.cliente.cnpj,
                'data_emissao': '2026-03-10',
                'observacoes': '',
                'texto_padrao': 'Texto',
                'itens': [_item_padrao(incluir_no_certificado=False)],
            }
        )
        self.assertFalse(ser.is_valid())
        self.assertIn('itens', ser.errors)

    def test_emissao_valida_passa(self):
        from apps.qualidade.tests.test_cq_rastreabilidade_emissao import _cadeia_rastreabilidade_completa

        ctx = _cadeia_rastreabilidade_completa('PHA')
        ser = CertificadoQualidadeSerializer(
            data={
                'status': CertificadoQualidade.Status.EMITIDO,
                'tipo_certificado': CertificadoQualidade.TipoCertificado.PADRAO_POR_NFE,
                'numero': 'CQ200',
                'serie': '',
                'nota_fiscal_numero': '501',
                'cliente': self.cliente.id,
                'cliente_nome_snapshot': self.cliente.razao_social,
                'cliente_cnpj_snapshot': self.cliente.cnpj,
                'data_emissao': '2026-03-11',
                'observacoes': '',
                'texto_padrao': 'Texto padrão teste.',
                'itens': [
                    _item_padrao(
                        produto=ctx['prod'].id,
                        corrida='363',
                        certificado_fornecedor_origem_id=ctx['cf'].id,
                        item_certificado_fornecedor_origem_id=ctx['item_cf'].id,
                    ),
                ],
            }
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        obj = ser.save()
        self.assertEqual(obj.status, CertificadoQualidade.Status.EMITIDO.value)
        self.assertTrue(ItemCertificadoQualidade.objects.filter(certificado=obj).exists())


class CertificadoFornecedorEntradaSerializerPhaseATests(TestCase):
    def setUp(self):
        self.forn = Fornecedor.objects.create(
            razao_social='Forn Cert Ltda',
            cnpj='47.616.434/0001-03',
        )

    def test_registrado_sem_fornecedor_falha(self):
        ser = CertificadoFornecedorEntradaSerializer(
            data={
                'status': CertificadoFornecedorEntrada.Status.REGISTRADO,
                'numero_certificado_fornecedor': 'CF-1',
                'fornecedor': None,
                'fornecedor_nome_snapshot': '',
                'fornecedor_cnpj_snapshot': '',
                'numero_nf_entrada': '100',
                'itens': [_item_padrao()],
            }
        )
        self.assertFalse(ser.is_valid())
        self.assertIn('fornecedor_nome_snapshot', ser.errors)

    def test_registrado_item_padrao_sem_corrida_falha(self):
        ser = CertificadoFornecedorEntradaSerializer(
            data={
                'status': CertificadoFornecedorEntrada.Status.REGISTRADO,
                'numero_certificado_fornecedor': 'CF-2',
                'fornecedor': self.forn.id,
                'fornecedor_nome_snapshot': self.forn.razao_social,
                'fornecedor_cnpj_snapshot': self.forn.cnpj,
                'numero_nf_entrada': '101',
                'itens': [_item_padrao(corrida='')],
            }
        )
        self.assertFalse(ser.is_valid())
        self.assertIn('itens', ser.errors)
        err_itens = ser.errors['itens']
        self.assertIsInstance(err_itens, list)
        self.assertTrue(any('corrida' in (e or {}) for e in err_itens if isinstance(e, dict)))

    def test_rascunho_incompleto_passa(self):
        ser = CertificadoFornecedorEntradaSerializer(
            data={
                'status': CertificadoFornecedorEntrada.Status.RASCUNHO,
                'numero_certificado_fornecedor': '',
                'fornecedor': None,
                'fornecedor_nome_snapshot': '',
                'numero_nf_entrada': '',
                'itens': [],
            }
        )
        self.assertTrue(ser.is_valid(), ser.errors)


class CertificadoQualidadePdfPhaseATests(TestCase):
    def setUp(self):
        Empresa.objects.create(
            razao_social='Empresa PDF Teste',
            cnpj='29.228.024/0001-41',
        )
        self.user = get_user_model().objects.create_user('cq_pdf', 'cq@test.com', 'secret123')
        ct_cq = ContentType.objects.get_for_model(CertificadoQualidade)
        self.user.user_permissions.add(
            Permission.objects.get(content_type=ct_cq, codename='view_certificadoqualidade')
        )
        self.user = get_user_model().objects.get(pk=self.user.pk)
        self.cliente = Cliente.objects.create(
            razao_social='Cliente PDF Ltda',
            cnpj='33.333.444/0001-09',
        )
        self.cert_emitido = CertificadoQualidade.objects.create(
            status=CertificadoQualidade.Status.EMITIDO,
            tipo_certificado=CertificadoQualidade.TipoCertificado.PADRAO_POR_NFE,
            numero='CQPDF1',
            serie='',
            cliente=self.cliente,
            cliente_nome_snapshot=self.cliente.razao_social,
            cliente_cnpj_snapshot=self.cliente.cnpj,
            nota_fiscal_numero='600',
            data_emissao='2026-04-01',
            texto_padrao='Rodapé teste.',
        )
        ItemCertificadoQualidade.objects.create(
            certificado=self.cert_emitido,
            ordem=1,
            codigo_produto='P-1',
            descricao_material='Peça',
            quantidade=1,
            unidade='PC',
            norma='DIN',
            corrida='R1',
            tipo_dados_tecnicos=ItemCertificadoQualidade.TipoDadosTecnicos.PADRAO_ITEM,
            incluir_no_certificado=True,
            composicao_json={'Fe': '98'},
            ensaio_tracao_json={'corpo_prova': 'A'},
            ensaio_impacto_json={},
        )
        self.cert_cancelado = CertificadoQualidade.objects.create(
            status=CertificadoQualidade.Status.CANCELADO,
            tipo_certificado=CertificadoQualidade.TipoCertificado.PADRAO_POR_NFE,
            numero='CQPDF2',
            serie='',
            cliente=self.cliente,
            cliente_nome_snapshot=self.cliente.razao_social,
            cliente_cnpj_snapshot=self.cliente.cnpj,
            nota_fiscal_numero='601',
            data_emissao='2026-04-02',
            texto_padrao='Rodapé cancelado.',
        )
        ItemCertificadoQualidade.objects.create(
            certificado=self.cert_cancelado,
            ordem=1,
            codigo_produto='P-2',
            descricao_material='Peça 2',
            quantidade=2,
            unidade='PC',
            norma='DIN',
            corrida='R2',
            tipo_dados_tecnicos=ItemCertificadoQualidade.TipoDadosTecnicos.PADRAO_ITEM,
            incluir_no_certificado=True,
            composicao_json={'Fe': '99'},
            ensaio_tracao_json={'corpo_prova': 'B'},
            ensaio_impacto_json={},
        )

    def test_gerar_pdf_bytes_validos(self):
        pdf = gerar_certificado_qualidade_pdf(self.cert_emitido, preview=False)
        self.assertTrue(pdf.startswith(b'%PDF'), pdf[:12])

    def test_preview_true_ainda_valido(self):
        pdf = gerar_certificado_qualidade_pdf(self.cert_emitido, preview=True)
        self.assertTrue(pdf.startswith(b'%PDF'))

    def test_cancelado_marca_agua_na_pagina(self):
        pdf = gerar_certificado_qualidade_pdf(self.cert_cancelado, preview=False)
        self.assertTrue(pdf.startswith(b'%PDF'))
        reader = PdfReader(io.BytesIO(pdf))
        texto = ''.join(page.extract_text() or '' for page in reader.pages)
        self.assertIn('CANCELADO', texto)
        self.assertIn('cancelado', texto.lower())

    def test_endpoint_pdf_200_e_content_type(self):
        c = APIClient()
        c.force_authenticate(user=self.user)
        url = reverse('certificado-qualidade-pdf', kwargs={'pk': self.cert_emitido.pk})
        resp = c.get(url, HTTP_HOST='localhost')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get('Content-Type'), 'application/pdf')
        self.assertTrue(resp.content.startswith(b'%PDF'))

    def test_endpoint_pdf_preview_query(self):
        c = APIClient()
        c.force_authenticate(user=self.user)
        url = reverse('certificado-qualidade-pdf', kwargs={'pk': self.cert_emitido.pk})
        resp = c.get(url, {'preview': 'true'}, HTTP_HOST='localhost')
        self.assertEqual(resp.status_code, 200)
        reader = PdfReader(io.BytesIO(resp.content))
        texto = ''.join(page.extract_text() or '' for page in reader.pages)
        self.assertIn('PRÉVIA', texto)
