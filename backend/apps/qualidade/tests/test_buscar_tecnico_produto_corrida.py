"""Busca técnica em certificado de fornecedor por produto + corrida (API usada pelo CQ)."""

from __future__ import annotations

import uuid

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.cadastros.models import Fornecedor
from apps.produtos.models import FamiliaProduto, Produto
from apps.qualidade.models import (
    CertificadoFornecedorEntrada,
    ComponenteCertificadoFornecedorEntrada,
    ItemCertificadoFornecedorEntrada,
)


def _grant_cf_change(user):
    ct = ContentType.objects.get_for_model(CertificadoFornecedorEntrada)
    user.user_permissions.add(
        Permission.objects.get(content_type=ct, codename='change_certificadofornecedorentrada'),
    )
    return get_user_model().objects.get(pk=user.pk)


def _payload_buscar_tecnicos(response):
    data = response.json()
    if isinstance(data, dict):
        return data['resultados'], list(data.get('dicas_busca') or []), data.get('diagnostico')
    return data, [], None


def _cnpj_unico() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


class BuscarDadosTecnicosPorProdutoCorridaTests(TestCase):
    def setUp(self):
        s = uuid.uuid4().hex[:8]
        self.forn = Fornecedor.objects.create(
            razao_social=f'Forn BT {s}',
            cnpj=_cnpj_unico(),
        )
        self.fam = FamiliaProduto.objects.create(
            codigo_figura=f'F{s}'[:16],
            descricao_base=f'Fam BT {s}',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
            tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
            categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
        )
        self.prod = Produto.objects.create(
            familia=self.fam,
            descricao=f'Prod BT {s}',
            modo_codigo=Produto.ModoCodigo.MANUAL,
            codigo_completo=f'PR-BT-{s}',
            unidade='PC',
        )
        self.cf = CertificadoFornecedorEntrada.objects.create(
            status=CertificadoFornecedorEntrada.Status.REGISTRADO,
            numero_certificado_fornecedor=f'CF-BT-{s}',
            fornecedor=self.forn,
            fornecedor_nome_snapshot=self.forn.razao_social,
            fornecedor_cnpj_snapshot=self.forn.cnpj,
            numero_nf_entrada='555',
        )
        self.item_cf = ItemCertificadoFornecedorEntrada.objects.create(
            certificado_fornecedor=self.cf,
            ordem=1,
            produto=self.prod,
            codigo_produto=self.prod.codigo_completo,
            descricao_material=self.prod.descricao,
            corrida='HEN-001',
            lote='L1',
            norma='ASTM A105',
            composicao_json={'C': '0.22'},
            ensaio_tracao_json={'limite_escoamento': '250'},
            ensaio_impacto_json={},
            tipo_dados_tecnicos=ItemCertificadoFornecedorEntrada.TipoDadosTecnicos.PADRAO_ITEM,
        )
        u = get_user_model().objects.create_user(f'bt_{s}', 'bt@test.com', 'x')
        self.user_change = _grant_cf_change(u)

    def test_buscar_com_produto_e_corrida_retorna_item(self):
        c = APIClient()
        c.force_authenticate(self.user_change)
        url = reverse('certificado-fornecedor-buscar-dados-tecnicos')
        r = c.get(url, {'produto': self.prod.id, 'corrida': 'hen 001'}, HTTP_HOST='localhost')
        self.assertEqual(r.status_code, 200)
        data, _, _ = _payload_buscar_tecnicos(r)
        self.assertGreaterEqual(len(data), 1)
        row = next(x for x in data if x.get('id') == self.item_cf.id)
        self.assertEqual(row['corrida'], 'HEN-001')
        self.assertEqual(row['produto'], self.prod.id)
        self.assertEqual(row['produto_match_tipo'], 'vinculado')
        self.assertTrue(row['produto_vinculado'])
        self.assertEqual(row.get('aviso_sem_vinculo_produto') or '', '')

    def test_buscar_inclui_item_sem_produto_mesma_corrida(self):
        s3 = uuid.uuid4().hex[:8]
        cf3 = CertificadoFornecedorEntrada.objects.create(
            status=CertificadoFornecedorEntrada.Status.REGISTRADO,
            numero_certificado_fornecedor=f'CF-NP-{s3}',
            fornecedor=self.forn,
            fornecedor_nome_snapshot=self.forn.razao_social,
            fornecedor_cnpj_snapshot=self.forn.cnpj,
            numero_nf_entrada='557',
        )
        item_sem = ItemCertificadoFornecedorEntrada.objects.create(
            certificado_fornecedor=cf3,
            ordem=1,
            produto=None,
            codigo_produto=self.prod.codigo_completo,
            descricao_material=self.prod.descricao,
            corrida='HEN-001',
            lote='',
            norma='ASTM B16',
            composicao_json={'Mn': '1'},
            ensaio_tracao_json={},
            ensaio_impacto_json={},
            tipo_dados_tecnicos=ItemCertificadoFornecedorEntrada.TipoDadosTecnicos.PADRAO_ITEM,
        )
        c = APIClient()
        c.force_authenticate(self.user_change)
        url = reverse('certificado-fornecedor-buscar-dados-tecnicos')
        r = c.get(
            url,
            {
                'produto': self.prod.id,
                'corrida': 'HEN-001',
                'codigo_produto': self.prod.codigo_completo,
                'descricao': self.prod.descricao,
            },
            HTTP_HOST='localhost',
        )
        self.assertEqual(r.status_code, 200)
        row = next(x for x in _payload_buscar_tecnicos(r)[0] if x.get('id') == item_sem.id)
        self.assertIsNone(row['produto'])
        self.assertEqual(row['produto_match_tipo'], 'sem_vinculo')
        self.assertFalse(row['produto_vinculado'])
        self.assertIn('sem produto vinculado', (row.get('aviso_sem_vinculo_produto') or '').lower())

    def test_filtro_produto_exclui_item_de_outro_produto(self):
        s2 = uuid.uuid4().hex[:8]
        fam2 = FamiliaProduto.objects.create(
            codigo_figura=f'F2{s2}'[:16],
            descricao_base=f'Fam2 {s2}',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
            tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
            categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
        )
        prod2 = Produto.objects.create(
            familia=fam2,
            descricao=f'P2 {s2}',
            modo_codigo=Produto.ModoCodigo.MANUAL,
            codigo_completo=f'PX-{s2}',
            unidade='PC',
        )
        cf2 = CertificadoFornecedorEntrada.objects.create(
            status=CertificadoFornecedorEntrada.Status.REGISTRADO,
            numero_certificado_fornecedor=f'CF2-{s2}',
            fornecedor=self.forn,
            fornecedor_nome_snapshot=self.forn.razao_social,
            fornecedor_cnpj_snapshot=self.forn.cnpj,
            numero_nf_entrada='556',
        )
        prod2_item = ItemCertificadoFornecedorEntrada.objects.create(
            certificado_fornecedor=cf2,
            ordem=1,
            produto=prod2,
            codigo_produto=prod2.codigo_completo,
            descricao_material=prod2.descricao,
            corrida='HEN-001',
            lote='',
            norma='X',
            composicao_json={},
            tipo_dados_tecnicos=ItemCertificadoFornecedorEntrada.TipoDadosTecnicos.PADRAO_ITEM,
        )
        c = APIClient()
        c.force_authenticate(self.user_change)
        url = reverse('certificado-fornecedor-buscar-dados-tecnicos')
        r = c.get(url, {'produto': self.prod.id, 'corrida': 'HEN-001'}, HTTP_HOST='localhost')
        self.assertEqual(r.status_code, 200)
        data, _, _ = _payload_buscar_tecnicos(r)
        ids = {row['id'] for row in data}
        self.assertIn(self.item_cf.id, ids)
        self.assertNotIn(prod2_item.id, ids)
        for row in data:
            pid = row.get('produto')
            self.assertTrue(pid is None or pid == self.prod.id)

    def test_buscar_sem_permissao_403(self):
        u = get_user_model().objects.create_user('btv', 'btv@test.com', 'x')
        c = APIClient()
        c.force_authenticate(u)
        url = reverse('certificado-fornecedor-buscar-dados-tecnicos')
        r = c.get(url, {'produto': self.prod.id, 'corrida': 'HEN-001'}, HTTP_HOST='localhost')
        self.assertEqual(r.status_code, 403)

    def test_sem_vinculo_corrida_s31_cq_envia_lote_nf_item_sem_lote_retorna(self):
        """CQ pode trazer lote da NF; item CF sem produto e sem lote não deve ser descartado após match de corrida."""
        s4 = uuid.uuid4().hex[:8]
        cf4 = CertificadoFornecedorEntrada.objects.create(
            status=CertificadoFornecedorEntrada.Status.REGISTRADO,
            numero_certificado_fornecedor=f'CF-S31-{s4}',
            fornecedor=self.forn,
            fornecedor_nome_snapshot=self.forn.razao_social,
            fornecedor_cnpj_snapshot=self.forn.cnpj,
            numero_nf_entrada='558',
        )
        item_s31 = ItemCertificadoFornecedorEntrada.objects.create(
            certificado_fornecedor=cf4,
            ordem=1,
            produto=None,
            codigo_produto=self.prod.codigo_completo,
            descricao_material=self.prod.descricao,
            corrida='S31',
            lote='',
            norma='ASTM A105',
            composicao_json={'C': '0.20'},
            ensaio_tracao_json={},
            ensaio_impacto_json={},
            tipo_dados_tecnicos=ItemCertificadoFornecedorEntrada.TipoDadosTecnicos.PADRAO_ITEM,
        )
        c = APIClient()
        c.force_authenticate(self.user_change)
        url = reverse('certificado-fornecedor-buscar-dados-tecnicos')
        r = c.get(
            url,
            {
                'produto': self.prod.id,
                'corrida': 'S31',
                'lote': 'LOTE-NF-SAIDA-99',
                'codigo_produto': self.prod.codigo_completo,
                'descricao': self.prod.descricao,
            },
            HTTP_HOST='localhost',
        )
        self.assertEqual(r.status_code, 200)
        row = next(x for x in _payload_buscar_tecnicos(r)[0] if x.get('id') == item_s31.id)
        self.assertEqual(row['produto_match_tipo'], 'sem_vinculo')
        self.assertFalse(row['produto_vinculado'])
        self.assertIn('sem produto vinculado', (row.get('aviso_sem_vinculo_produto') or '').lower())

    def test_sem_vinculo_com_lote_divergente_excluido_quando_cq_filtra_lote(self):
        """Item sem vínculo com lote próprio que não casa com o lote enviado pelo CQ deve ser excluído."""
        s5 = uuid.uuid4().hex[:8]
        cf5 = CertificadoFornecedorEntrada.objects.create(
            status=CertificadoFornecedorEntrada.Status.REGISTRADO,
            numero_certificado_fornecedor=f'CF-LD-{s5}',
            fornecedor=self.forn,
            fornecedor_nome_snapshot=self.forn.razao_social,
            fornecedor_cnpj_snapshot=self.forn.cnpj,
            numero_nf_entrada='559',
        )
        item_div = ItemCertificadoFornecedorEntrada.objects.create(
            certificado_fornecedor=cf5,
            ordem=1,
            produto=None,
            codigo_produto=self.prod.codigo_completo,
            descricao_material=self.prod.descricao,
            corrida='S31',
            lote='L-FORN-2',
            norma='ASTM A105',
            composicao_json={},
            tipo_dados_tecnicos=ItemCertificadoFornecedorEntrada.TipoDadosTecnicos.PADRAO_ITEM,
        )
        c = APIClient()
        c.force_authenticate(self.user_change)
        url = reverse('certificado-fornecedor-buscar-dados-tecnicos')
        r = c.get(
            url,
            {
                'produto': self.prod.id,
                'corrida': 'S31',
                'lote': 'L-FORN-1',
                'codigo_produto': self.prod.codigo_completo,
                'descricao': self.prod.descricao,
            },
            HTTP_HOST='localhost',
        )
        self.assertEqual(r.status_code, 200)
        rows, dicas, _ = _payload_buscar_tecnicos(r)
        ids = {x.get('id') for x in rows}
        self.assertNotIn(item_div.id, ids)
        self.assertIn('LOTE_DIVERGENTE', dicas)

    def test_buscar_corrida_numerica_363_certificado_registrado_retorna_item(self):
        s6 = uuid.uuid4().hex[:8]
        cf363 = CertificadoFornecedorEntrada.objects.create(
            status=CertificadoFornecedorEntrada.Status.REGISTRADO,
            numero_certificado_fornecedor=f'CF-363-{s6}',
            fornecedor=self.forn,
            fornecedor_nome_snapshot=self.forn.razao_social,
            fornecedor_cnpj_snapshot=self.forn.cnpj,
            numero_nf_entrada='560',
        )
        item_363 = ItemCertificadoFornecedorEntrada.objects.create(
            certificado_fornecedor=cf363,
            ordem=1,
            produto=self.prod,
            codigo_produto=self.prod.codigo_completo,
            descricao_material=self.prod.descricao,
            corrida='363',
            lote='',
            norma='ASTM A105',
            composicao_json={'Ni': '0.5'},
            ensaio_tracao_json={'limite_escoamento': '200'},
            ensaio_impacto_json={},
            tipo_dados_tecnicos=ItemCertificadoFornecedorEntrada.TipoDadosTecnicos.PADRAO_ITEM,
        )
        c = APIClient()
        c.force_authenticate(self.user_change)
        url = reverse('certificado-fornecedor-buscar-dados-tecnicos')
        r = c.get(
            url,
            {'produto': self.prod.id, 'corrida': '363', 'codigo_produto': self.prod.codigo_completo},
            HTTP_HOST='localhost',
        )
        self.assertEqual(r.status_code, 200)
        row = next(x for x in _payload_buscar_tecnicos(r)[0] if x.get('id') == item_363.id)
        self.assertEqual(row['corrida'], '363')
        self.assertEqual(row['produto_match_tipo'], 'vinculado')
        self.assertTrue(row['produto_vinculado'])

    def test_buscar_corrida_363_somente_em_componente_retorna(self):
        s7 = uuid.uuid4().hex[:8]
        cf_comp = CertificadoFornecedorEntrada.objects.create(
            status=CertificadoFornecedorEntrada.Status.REGISTRADO,
            numero_certificado_fornecedor=f'CF-COMP-{s7}',
            fornecedor=self.forn,
            fornecedor_nome_snapshot=self.forn.razao_social,
            fornecedor_cnpj_snapshot=self.forn.cnpj,
            numero_nf_entrada='561',
        )
        item_pai = ItemCertificadoFornecedorEntrada.objects.create(
            certificado_fornecedor=cf_comp,
            ordem=1,
            produto=self.prod,
            codigo_produto=self.prod.codigo_completo,
            descricao_material=self.prod.descricao,
            corrida='',
            lote='',
            norma='',
            composicao_json={},
            tipo_dados_tecnicos=ItemCertificadoFornecedorEntrada.TipoDadosTecnicos.VALVULA_COMPONENTES,
        )
        ComponenteCertificadoFornecedorEntrada.objects.create(
            item_certificado_fornecedor=item_pai,
            ordem=1,
            nome_componente='Corpo',
            corrida='363',
            lote='',
            composicao_json={},
        )
        c = APIClient()
        c.force_authenticate(self.user_change)
        url = reverse('certificado-fornecedor-buscar-dados-tecnicos')
        r = c.get(
            url,
            {
                'produto': self.prod.id,
                'corrida': '363',
                'tipo_dados_tecnicos': 'VALVULA_COMPONENTES',
                'codigo_produto': self.prod.codigo_completo,
            },
            HTTP_HOST='localhost',
        )
        self.assertEqual(r.status_code, 200)
        rows, _, _ = _payload_buscar_tecnicos(r)
        ids = {x.get('id') for x in rows}
        self.assertIn(item_pai.id, ids)
        row = next(x for x in rows if x.get('id') == item_pai.id)
        self.assertEqual(row.get('corrida'), '363')

    def test_busca_padrao_exclui_certificado_rascunho_mesma_corrida_363(self):
        s8 = uuid.uuid4().hex[:8]
        cf_rasc = CertificadoFornecedorEntrada.objects.create(
            status=CertificadoFornecedorEntrada.Status.RASCUNHO,
            numero_certificado_fornecedor=f'CF-RAS-{s8}',
            fornecedor=self.forn,
            fornecedor_nome_snapshot=self.forn.razao_social,
            fornecedor_cnpj_snapshot=self.forn.cnpj,
            numero_nf_entrada='562',
        )
        item_r = ItemCertificadoFornecedorEntrada.objects.create(
            certificado_fornecedor=cf_rasc,
            ordem=1,
            produto=self.prod,
            codigo_produto=self.prod.codigo_completo,
            descricao_material=self.prod.descricao,
            corrida='363',
            lote='',
            composicao_json={},
            tipo_dados_tecnicos=ItemCertificadoFornecedorEntrada.TipoDadosTecnicos.PADRAO_ITEM,
        )
        c = APIClient()
        c.force_authenticate(self.user_change)
        url = reverse('certificado-fornecedor-buscar-dados-tecnicos')
        r = c.get(url, {'produto': self.prod.id, 'corrida': '363'}, HTTP_HOST='localhost')
        self.assertEqual(r.status_code, 200)
        rows, _, _ = _payload_buscar_tecnicos(r)
        ids = {x.get('id') for x in rows}
        self.assertNotIn(item_r.id, ids)

    def test_dicas_certificado_rascunho_quando_busca_padrao_sem_resultado(self):
        sx = uuid.uuid4().hex[:8]
        cf_only = CertificadoFornecedorEntrada.objects.create(
            status=CertificadoFornecedorEntrada.Status.RASCUNHO,
            numero_certificado_fornecedor=f'CF-R-DICA-{sx}',
            fornecedor=self.forn,
            fornecedor_nome_snapshot=self.forn.razao_social,
            fornecedor_cnpj_snapshot=self.forn.cnpj,
            numero_nf_entrada='564',
        )
        ItemCertificadoFornecedorEntrada.objects.create(
            certificado_fornecedor=cf_only,
            ordem=1,
            produto=self.prod,
            codigo_produto=self.prod.codigo_completo,
            descricao_material=self.prod.descricao,
            corrida='CORRIDA-SO-RASCUNHO-999',
            lote='',
            composicao_json={},
            tipo_dados_tecnicos=ItemCertificadoFornecedorEntrada.TipoDadosTecnicos.PADRAO_ITEM,
        )
        c = APIClient()
        c.force_authenticate(self.user_change)
        url = reverse('certificado-fornecedor-buscar-dados-tecnicos')
        r = c.get(url, {'produto': self.prod.id, 'corrida': 'CORRIDA-SO-RASCUNHO-999'}, HTTP_HOST='localhost')
        self.assertEqual(r.status_code, 200)
        rows, dicas, _ = _payload_buscar_tecnicos(r)
        self.assertEqual(rows, [])
        self.assertIn('CERTIFICADO_RASCUNHO', dicas)

    def test_include_rascunho_permite_item_corrida_363_em_certificado_rascunho(self):
        s9 = uuid.uuid4().hex[:8]
        cf_r2 = CertificadoFornecedorEntrada.objects.create(
            status=CertificadoFornecedorEntrada.Status.RASCUNHO,
            numero_certificado_fornecedor=f'CF-R2-{s9}',
            fornecedor=self.forn,
            fornecedor_nome_snapshot=self.forn.razao_social,
            fornecedor_cnpj_snapshot=self.forn.cnpj,
            numero_nf_entrada='563',
        )
        item_r2 = ItemCertificadoFornecedorEntrada.objects.create(
            certificado_fornecedor=cf_r2,
            ordem=1,
            produto=self.prod,
            codigo_produto=self.prod.codigo_completo,
            descricao_material=self.prod.descricao,
            corrida='363',
            lote='',
            composicao_json={'C': '0.1'},
            tipo_dados_tecnicos=ItemCertificadoFornecedorEntrada.TipoDadosTecnicos.PADRAO_ITEM,
        )
        c = APIClient()
        c.force_authenticate(self.user_change)
        url = reverse('certificado-fornecedor-buscar-dados-tecnicos')
        r = c.get(
            url,
            {'produto': self.prod.id, 'corrida': '363', 'include_rascunho': 'true'},
            HTTP_HOST='localhost',
        )
        self.assertEqual(r.status_code, 200)
        rows, _, _ = _payload_buscar_tecnicos(r)
        ids = {x.get('id') for x in rows}
        self.assertIn(item_r2.id, ids)
        row = next(x for x in rows if x.get('id') == item_r2.id)
        self.assertEqual(row['status_certificado_fornecedor'], 'rascunho')

    def test_dicas_sem_resultado_produto_diferente_mesma_corrida(self):
        s = uuid.uuid4().hex[:8]
        famx = FamiliaProduto.objects.create(
            codigo_figura=f'FX{s}'[:16],
            descricao_base=f'FamX {s}',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
            tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
            categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
        )
        prodx = Produto.objects.create(
            familia=famx,
            descricao=f'PX {s}',
            modo_codigo=Produto.ModoCodigo.MANUAL,
            codigo_completo=f'PX-ONLY-{s}',
            unidade='PC',
        )
        cfx = CertificadoFornecedorEntrada.objects.create(
            status=CertificadoFornecedorEntrada.Status.REGISTRADO,
            numero_certificado_fornecedor=f'CFX-{s}',
            fornecedor=self.forn,
            fornecedor_nome_snapshot=self.forn.razao_social,
            fornecedor_cnpj_snapshot=self.forn.cnpj,
            numero_nf_entrada='900',
        )
        ItemCertificadoFornecedorEntrada.objects.create(
            certificado_fornecedor=cfx,
            ordem=1,
            produto=prodx,
            codigo_produto=prodx.codigo_completo,
            descricao_material=prodx.descricao,
            corrida='ZZ-UNIQUE-999',
            lote='',
            norma='X',
            composicao_json={},
            tipo_dados_tecnicos=ItemCertificadoFornecedorEntrada.TipoDadosTecnicos.PADRAO_ITEM,
        )
        c = APIClient()
        c.force_authenticate(self.user_change)
        url = reverse('certificado-fornecedor-buscar-dados-tecnicos')
        r = c.get(url, {'produto': self.prod.id, 'corrida': 'ZZ-UNIQUE-999'}, HTTP_HOST='localhost')
        self.assertEqual(r.status_code, 200)
        rows, dicas, _ = _payload_buscar_tecnicos(r)
        self.assertEqual(rows, [])
        self.assertIn('PRODUTO_VINCULADO_DIFERENTE', dicas)

    def test_debug_diagnostico_somente_superuser(self):
        User = get_user_model()
        sup = User.objects.create_superuser(f'su_{uuid.uuid4().hex[:8]}', 'su@test.com', 'x')
        c = APIClient()
        c.force_authenticate(sup)
        url = reverse('certificado-fornecedor-buscar-dados-tecnicos')
        r = c.get(url, {'produto': self.prod.id, 'corrida': 'HEN-001', 'debug': '1'}, HTTP_HOST='localhost')
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIsInstance(body, dict)
        self.assertIn('diagnostico', body)
        self.assertIn('amostra', body['diagnostico'])

    def test_debug_sem_diagnostico_usuario_comum_mesmo_com_param(self):
        c = APIClient()
        c.force_authenticate(self.user_change)
        url = reverse('certificado-fornecedor-buscar-dados-tecnicos')
        r = c.get(url, {'produto': self.prod.id, 'corrida': 'HEN-001', 'debug': '1'}, HTTP_HOST='localhost')
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIsInstance(body, dict)
        self.assertNotIn('diagnostico', body)

    def test_caso_real_363_status_maiusculo_sem_produto_retorna_sem_vinculo(self):
        """Reproduz certificado fornecedor real: status REGISTRADO legado, item sem produto, corrida 363."""
        s = uuid.uuid4().hex[:8]
        cf = CertificadoFornecedorEntrada.objects.create(
            status='REGISTRADO',
            numero_certificado_fornecedor=f'CF-REAL-363-{s}',
            fornecedor=self.forn,
            fornecedor_nome_snapshot=self.forn.razao_social,
            fornecedor_cnpj_snapshot=self.forn.cnpj,
            numero_nf_entrada='43363',
        )
        item_363 = ItemCertificadoFornecedorEntrada.objects.create(
            certificado_fornecedor=cf,
            ordem=1,
            produto=None,
            codigo_produto='6LV3MRB1/2',
            descricao_material='LUVA 3000 BSP INOX 316 1/2',
            corrida='363',
            lote='',
            norma='ASTM A182',
            composicao_json={'C': '0.03', 'Cr': '16.5', 'Ni': '10.2'},
            ensaio_tracao_json={'limite_escoamento': '250', 'limite_resistencia': '520'},
            ensaio_impacto_json={'media': '45'},
            tipo_dados_tecnicos=ItemCertificadoFornecedorEntrada.TipoDadosTecnicos.PADRAO_ITEM,
        )
        c = APIClient()
        c.force_authenticate(self.user_change)
        url = reverse('certificado-fornecedor-buscar-dados-tecnicos')
        r = c.get(
            url,
            {
                'corrida': '363',
                'status': 'registrado',
                'codigo_produto': '6LV3MRB1/2',
            },
            HTTP_HOST='localhost',
        )
        self.assertEqual(r.status_code, 200)
        rows, _, _ = _payload_buscar_tecnicos(r)
        self.assertGreaterEqual(len(rows), 1)
        row = next(x for x in rows if x.get('id') == item_363.id)
        self.assertEqual(row['corrida'], '363')
        self.assertEqual(row['produto_match_tipo'], 'sem_vinculo')
        self.assertFalse(row['produto_vinculado'])
        self.assertTrue(row['composicao_json'])
        self.assertTrue(row['ensaio_tracao_json'])

    def test_caso_real_363_com_produto_cq_e_lote_nf_nao_bloqueia(self):
        """Item fornecedor sem lote: CQ pode enviar lote da NF sem excluir corrida 363."""
        s = uuid.uuid4().hex[:8]
        cf = CertificadoFornecedorEntrada.objects.create(
            status='REGISTRADO',
            numero_certificado_fornecedor=f'CF-363-LNF-{s}',
            fornecedor=self.forn,
            fornecedor_nome_snapshot=self.forn.razao_social,
            fornecedor_cnpj_snapshot=self.forn.cnpj,
            numero_nf_entrada='900',
        )
        item_363 = ItemCertificadoFornecedorEntrada.objects.create(
            certificado_fornecedor=cf,
            ordem=1,
            produto=None,
            codigo_produto=self.prod.codigo_completo,
            descricao_material=self.prod.descricao,
            corrida='363',
            lote='',
            composicao_json={'Mn': '1.2'},
            ensaio_tracao_json={'alongamento': '22'},
            ensaio_impacto_json={},
            tipo_dados_tecnicos=ItemCertificadoFornecedorEntrada.TipoDadosTecnicos.PADRAO_ITEM,
        )
        c = APIClient()
        c.force_authenticate(self.user_change)
        url = reverse('certificado-fornecedor-buscar-dados-tecnicos')
        r = c.get(
            url,
            {
                'produto': self.prod.id,
                'corrida': '363',
                'lote': 'LOTE-NF-XYZ',
                'status': 'registrado',
            },
            HTTP_HOST='localhost',
        )
        self.assertEqual(r.status_code, 200)
        rows, _, _ = _payload_buscar_tecnicos(r)
        ids = {x.get('id') for x in rows}
        self.assertIn(item_363.id, ids)
