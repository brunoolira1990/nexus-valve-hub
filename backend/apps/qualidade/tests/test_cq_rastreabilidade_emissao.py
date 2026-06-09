"""Fase 3.12 — rastreabilidade técnica para emissão definitiva do Certificado de Qualidade."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Fornecedor
from apps.fiscal.models import (
    ItemNFeEntradaConferencia,
    ItemNFeEntradaHistoricaImportada,
    NFeEntradaConferencia,
    NFeEntradaHistoricaImportada,
)
from apps.produtos.models import FamiliaProduto, Produto
from apps.qualidade.models import (
    CertificadoFornecedorEntrada,
    CertificadoQualidade,
    ItemCertificadoFornecedorEntrada,
    ItemCertificadoQualidade,
)
from apps.qualidade.rastreabilidade_cq import (
    avaliar_rastreabilidade_item_certificado_qualidade,
    montar_resumo_rastreabilidade_certificado,
)
from apps.qualidade.serializers import CertificadoQualidadeSerializer


def _cnpj() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


def _grant_cq(user):
    ct = ContentType.objects.get_for_model(CertificadoQualidade)
    for codename in ('add_certificadoqualidade', 'change_certificadoqualidade', 'view_certificadoqualidade'):
        user.user_permissions.add(Permission.objects.get(content_type=ct, codename=codename))
    return get_user_model().objects.get(pk=user.pk)


def _item_cq_padrao(**kwargs):
    base = {
        'ordem': 1,
        'codigo_produto': 'COD-1',
        'descricao_material': 'LUVA 3000 BSP INOX 316 1/2',
        'quantidade': '1.000',
        'unidade': 'PC',
        'norma': 'ASTM A105',
        'corrida': 'CR-001',
        'lote': 'L1',
        'tipo_dados_tecnicos': 'PADRAO_ITEM',
        'ncm': '84818099',
        'incluir_no_certificado': True,
        'composicao_json': {'C': '0.25'},
        'ensaio_tracao_json': {'corpo_prova': 'CP1'},
        'ensaio_impacto_json': {},
    }
    base.update(kwargs)
    return base


def _cadeia_rastreabilidade_completa(suffix: str):
    """NF entrada + conferência com estoque aplicado + CF registrado + vínculo."""
    forn = Fornecedor.objects.create(razao_social=f'Forn {suffix}', cnpj=_cnpj())
    fam = FamiliaProduto.objects.create(
        codigo_figura=f'F{suffix}'[:16],
        descricao_base='Fam',
        tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
        categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
    )
    prod = Produto.objects.create(
        familia=fam,
        descricao=f'Prod {suffix}',
        modo_codigo=Produto.ModoCodigo.MANUAL,
        codigo_completo=f'P-{suffix}',
        unidade='PC',
        ncm='84818099',
    )
    nf = NFeEntradaHistoricaImportada.objects.create(
        chave_acesso=('35' + suffix + 'X' * 40)[:44],
        numero=f'NE{suffix}'[:8],
        serie='1',
        modelo='55',
        dh_emissao=timezone.make_aware(datetime(2026, 6, 1, 10, 0)),
        valor_total_nf=Decimal('100'),
        fornecedor_emitente=forn,
    )
    item_nf = ItemNFeEntradaHistoricaImportada.objects.create(
        nf=nf,
        n_item=1,
        prod_json={'CFOP': '5102', 'NCM': '84818099', 'qCom': '10', 'uCom': 'PC'},
        imposto_json={},
    )
    conf = NFeEntradaConferencia.objects.create(
        nf_entrada_historica=nf,
        status=NFeEntradaConferencia.Status.PREPARADA,
        estoque_aplicado_em=timezone.now(),
    )
    item_conf, _ = conf.itens.get_or_create(item_nfe_historico=item_nf)
    item_conf.produto = prod
    item_conf.corrida = '363'
    item_conf.lote = 'L1'
    item_conf.quantidade_nf = Decimal('10')
    item_conf.estoque_aplicado_em = timezone.now()
    item_conf.status = ItemNFeEntradaConferencia.Status.CONFERIDO
    item_conf.save()

    cf = CertificadoFornecedorEntrada.objects.create(
        status=CertificadoFornecedorEntrada.Status.REGISTRADO,
        numero_certificado_fornecedor=f'CF-{suffix}',
        fornecedor=forn,
        fornecedor_nome_snapshot=forn.razao_social,
        nf_entrada_historica=nf,
        numero_nf_entrada=nf.numero,
        serie_nf_entrada=nf.serie,
    )
    item_cf = ItemCertificadoFornecedorEntrada.objects.create(
        certificado_fornecedor=cf,
        ordem=1,
        produto=prod,
        codigo_produto=prod.codigo_completo,
        descricao_material=prod.descricao,
        corrida='363',
        lote='L1',
        norma='ASTM A105',
        composicao_json={'C': '0.25'},
        ensaio_tracao_json={'limite_escoamento': '250'},
        item_conferencia=item_conf,
        ativo=True,
    )
    return {
        'prod': prod,
        'forn': forn,
        'nf': nf,
        'conf': conf,
        'item_conf': item_conf,
        'cf': cf,
        'item_cf': item_cf,
    }


class CQRastreabilidadeAvaliacaoTests(TestCase):
    def test_item_completo(self):
        ctx = _cadeia_rastreabilidade_completa('CMP')
        item = ItemCertificadoQualidade(
            certificado_id=1,
            ordem=1,
            produto=ctx['prod'],
            corrida='363',
            lote='L1',
            norma='ASTM A105',
            composicao_json={'C': '0.25'},
            ensaio_tracao_json={'x': '1'},
            certificado_fornecedor_origem_id=ctx['cf'].id,
            item_certificado_fornecedor_origem_id=ctx['item_cf'].id,
            incluir_no_certificado=True,
        )
        av = avaliar_rastreabilidade_item_certificado_qualidade(item)
        self.assertEqual(av['status'], 'COMPLETA')
        self.assertTrue(av['estoque_aplicado_origem'])

    def test_item_pendente_sem_produto(self):
        av = avaliar_rastreabilidade_item_certificado_qualidade(_item_cq_padrao(produto=None))
        self.assertEqual(av['status'], 'PENDENTE')
        self.assertIn('SEM_PRODUTO', av['motivos'])

    def test_item_parcial_sem_estoque(self):
        ctx = _cadeia_rastreabilidade_completa('PSE')
        ctx['item_conf'].estoque_aplicado_em = None
        ctx['item_conf'].save(update_fields=['estoque_aplicado_em'])
        ctx['conf'].estoque_aplicado_em = None
        ctx['conf'].save(update_fields=['estoque_aplicado_em'])
        item = ItemCertificadoQualidade(
            certificado_id=1,
            produto=ctx['prod'],
            corrida='363',
            norma='ASTM',
            composicao_json={'C': '1'},
            ensaio_tracao_json={'x': '1'},
            certificado_fornecedor_origem_id=ctx['cf'].id,
            item_certificado_fornecedor_origem_id=ctx['item_cf'].id,
        )
        av = avaliar_rastreabilidade_item_certificado_qualidade(item)
        self.assertEqual(av['status'], 'PARCIAL')
        self.assertIn('Estoque físico ainda não aplicado.', av['mensagens'])

    def test_resumo_conta_status(self):
        ctx = _cadeia_rastreabilidade_completa('RES')
        completo = ItemCertificadoQualidade(
            produto=ctx['prod'],
            corrida='363',
            norma='N',
            composicao_json={'C': '1'},
            ensaio_tracao_json={'x': '1'},
            certificado_fornecedor_origem_id=ctx['cf'].id,
            item_certificado_fornecedor_origem_id=ctx['item_cf'].id,
            incluir_no_certificado=True,
        )
        pendente = _item_cq_padrao(produto=None, incluir_no_certificado=True)
        resumo = montar_resumo_rastreabilidade_certificado([completo, pendente])
        self.assertEqual(resumo['completos'], 1)
        self.assertEqual(resumo['pendentes'], 1)
        self.assertFalse(resumo['pode_emitir'])


class CQRastreabilidadeEmissaoSerializerTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(razao_social='Cli CQ', cnpj=_cnpj())
        self.ctx = _cadeia_rastreabilidade_completa('SER')

    def _payload_emitido(self, item_extra=None):
        item = _item_cq_padrao(
            produto=self.ctx['prod'].id,
            corrida='363',
            certificado_fornecedor_origem_id=self.ctx['cf'].id,
            item_certificado_fornecedor_origem_id=self.ctx['item_cf'].id,
        )
        if item_extra:
            item.update(item_extra)
        return {
            'status': CertificadoQualidade.Status.EMITIDO,
            'tipo_certificado': CertificadoQualidade.TipoCertificado.PADRAO_POR_NFE,
            'numero': 'CQ300',
            'serie': '',
            'nota_fiscal_numero': '9001',
            'cliente': self.cliente.id,
            'cliente_nome_snapshot': self.cliente.razao_social,
            'cliente_cnpj_snapshot': self.cliente.cnpj,
            'data_emissao': '2026-06-15',
            'observacoes': '',
            'texto_padrao': 'Texto',
            'itens': [item],
        }

    def test_rascunho_com_rastreabilidade_pendente_passa(self):
        ser = CertificadoQualidadeSerializer(
            data={
                'status': CertificadoQualidade.Status.RASCUNHO,
                'tipo_certificado': CertificadoQualidade.TipoCertificado.PADRAO_POR_NFE,
                'numero': '',
                'serie': '',
                'nota_fiscal_numero': '100',
                'itens': [_item_cq_padrao(produto=None, corrida='')],
            },
        )
        self.assertTrue(ser.is_valid(), ser.errors)

    def test_emitido_sem_corrida_bloqueia(self):
        ser = CertificadoQualidadeSerializer(
            data=self._payload_emitido({'corrida': '', 'lote': '', 'corrida_snapshot': ''}),
        )
        self.assertFalse(ser.is_valid())
        self.assertIn('rastreabilidade', ser.errors)

    def test_emitido_cf_rascunho_bloqueia(self):
        self.ctx['cf'].status = CertificadoFornecedorEntrada.Status.RASCUNHO
        self.ctx['cf'].save(update_fields=['status'])
        ser = CertificadoQualidadeSerializer(data=self._payload_emitido())
        self.assertFalse(ser.is_valid())
        self.assertTrue(any('rascunho' in m.lower() for m in ser.errors['rastreabilidade']))

    def test_emitido_cf_cancelado_bloqueia(self):
        self.ctx['cf'].status = CertificadoFornecedorEntrada.Status.CANCELADO
        self.ctx['cf'].save(update_fields=['status'])
        ser = CertificadoQualidadeSerializer(data=self._payload_emitido())
        self.assertFalse(ser.is_valid())

    def test_emitido_sem_item_conferencia_bloqueia(self):
        self.ctx['item_cf'].item_conferencia = None
        self.ctx['item_cf'].save(update_fields=['item_conferencia'])
        ser = CertificadoQualidadeSerializer(data=self._payload_emitido())
        self.assertFalse(ser.is_valid())
        self.assertTrue(any('conferência' in m.lower() for m in ser.errors['rastreabilidade']))

    def test_emitido_sem_estoque_aplicado_bloqueia(self):
        self.ctx['item_conf'].estoque_aplicado_em = None
        self.ctx['item_conf'].save(update_fields=['estoque_aplicado_em'])
        self.ctx['conf'].estoque_aplicado_em = None
        self.ctx['conf'].save(update_fields=['estoque_aplicado_em'])
        ser = CertificadoQualidadeSerializer(data=self._payload_emitido())
        self.assertFalse(ser.is_valid())
        self.assertTrue(any('estoque físico' in m.lower() for m in ser.errors['rastreabilidade']))

    def test_emitido_rastreabilidade_completa_passa(self):
        ser = CertificadoQualidadeSerializer(data=self._payload_emitido())
        self.assertTrue(ser.is_valid(), ser.errors)

    def test_resumo_na_serializacao(self):
        cert = CertificadoQualidade.objects.create(
            status=CertificadoQualidade.Status.RASCUNHO,
            tipo_certificado=CertificadoQualidade.TipoCertificado.PADRAO_POR_NFE,
            numero='CQ400',
            nota_fiscal_numero='1',
            cliente=self.cliente,
        )
        ItemCertificadoQualidade.objects.create(
            certificado=cert,
            ordem=1,
            produto=self.ctx['prod'],
            corrida='363',
            norma='ASTM',
            composicao_json={'C': '1'},
            ensaio_tracao_json={'x': '1'},
            certificado_fornecedor_origem_id=self.ctx['cf'].id,
            item_certificado_fornecedor_origem_id=self.ctx['item_cf'].id,
        )
        data = CertificadoQualidadeSerializer(cert).data
        self.assertEqual(data['resumo_rastreabilidade']['completos'], 1)
        self.assertTrue(data['resumo_rastreabilidade']['pode_emitir'])
        self.assertEqual(data['itens'][0]['rastreabilidade_status'], 'COMPLETA')


class CQRastreabilidadeEmissaoAPITests(TestCase):
    def setUp(self):
        s = uuid.uuid4().hex[:6]
        self.ctx = _cadeia_rastreabilidade_completa(s)
        self.cliente = Cliente.objects.create(razao_social='Cli API', cnpj=_cnpj())
        u = get_user_model().objects.create_user(f'cq_r_{s}', 'cq@test.com', 'x')
        self.user = _grant_cq(u)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.url = reverse('certificado-qualidade-list')

    def test_api_rascunho_pendente_ok(self):
        r = self.client.post(
            self.url,
            {
                'status': 'rascunho',
                'tipo_certificado': 'PADRAO_POR_NFE',
                'numero': '',
                'serie': '',
                'nota_fiscal_numero': '88',
                'itens': [_item_cq_padrao(produto=None, corrida='')],
            },
            format='json',
            HTTP_HOST='localhost',
        )
        self.assertEqual(r.status_code, 201, r.content)

    def test_api_emitido_bloqueado_retorna_rastreabilidade(self):
        r = self.client.post(
            self.url,
            {
                'status': 'emitido',
                'tipo_certificado': 'PADRAO_POR_NFE',
                'numero': 'CQ500',
                'serie': '',
                'nota_fiscal_numero': '99',
                'cliente': self.cliente.id,
                'cliente_nome_snapshot': self.cliente.razao_social,
                'data_emissao': '2026-06-20',
                'texto_padrao': 'T',
                'itens': [_item_cq_padrao(produto=self.ctx['prod'].id, corrida='', lote='')],
            },
            format='json',
            HTTP_HOST='localhost',
        )
        self.assertEqual(r.status_code, 400, r.content)
        body = r.json()
        self.assertIn('rastreabilidade', body)

    def test_pdf_preview_com_pendente_ok(self):
        cert = CertificadoQualidade.objects.create(
            status=CertificadoQualidade.Status.RASCUNHO,
            tipo_certificado=CertificadoQualidade.TipoCertificado.PADRAO_POR_NFE,
            numero='CQ600',
            nota_fiscal_numero='1',
            cliente=self.cliente,
        )
        ItemCertificadoQualidade.objects.create(
            certificado=cert,
            ordem=1,
            codigo_produto='X',
            descricao_material='Sem rastreio',
            corrida='',
            norma='',
        )
        url = reverse('certificado-qualidade-pdf', kwargs={'pk': cert.pk})
        r = self.client.get(url, {'preview': 'true'}, HTTP_HOST='localhost')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')

    def test_cancelado_mantem_comportamento(self):
        cert = CertificadoQualidade.objects.create(
            status=CertificadoQualidade.Status.EMITIDO,
            tipo_certificado=CertificadoQualidade.TipoCertificado.PADRAO_POR_NFE,
            numero='CQ700',
            nota_fiscal_numero='1',
            cliente=self.cliente,
            data_emissao='2026-01-01',
        )
        url = reverse('certificado-qualidade-detail', kwargs={'pk': cert.pk})
        r = self.client.patch(
            url,
            {'status': 'cancelado'},
            format='json',
            HTTP_HOST='localhost',
        )
        self.assertEqual(r.status_code, 200, r.content)
        cert.refresh_from_db()
        self.assertEqual(cert.status, CertificadoQualidade.Status.CANCELADO)
