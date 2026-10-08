"""Fase 1: rastreabilidade Item CF ↔ ItemNFeEntradaConferencia (NF entrada histórica)."""

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

from apps.cadastros.models import Fornecedor
from apps.fiscal.models import (
    ItemNFeEntradaConferencia,
    ItemNFeEntradaHistoricaImportada,
    NFeEntradaConferencia,
    NFeEntradaHistoricaImportada,
)
from apps.produtos.models import FamiliaProduto, Produto
from apps.qualidade.models import CertificadoFornecedorEntrada, ItemCertificadoFornecedorEntrada


def _cnpj_unico() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


def _grant_cf(user, *, add=False, change=True):
    ct = ContentType.objects.get_for_model(CertificadoFornecedorEntrada)
    if add:
        user.user_permissions.add(
            Permission.objects.get(content_type=ct, codename='add_certificadofornecedorentrada'),
        )
    if change:
        user.user_permissions.add(
            Permission.objects.get(content_type=ct, codename='change_certificadofornecedorentrada'),
        )
    return get_user_model().objects.get(pk=user.pk)


def _nf_hist_com_itens(suffix: str, *, fornecedor: Fornecedor | None = None) -> tuple[NFeEntradaHistoricaImportada, list[ItemNFeEntradaHistoricaImportada]]:
    dh = timezone.make_aware(datetime(2026, 3, 1, 10, 0, 0))
    nf = NFeEntradaHistoricaImportada.objects.create(
        chave_acesso=f'35{suffix}'[:44].ljust(44, '0'),
        numero=f'NF{suffix}'[:8],
        serie='1',
        modelo='55',
        dh_emissao=dh,
        valor_total_nf=Decimal('100.00'),
        fornecedor_emitente=fornecedor,
    )
    itens = []
    for n in (1, 2):
        itens.append(
            ItemNFeEntradaHistoricaImportada.objects.create(
                nf=nf,
                n_item=n,
                prod_json={
                    'cProd': f'C{n}-{suffix}',
                    'xProd': f'Desc {n}',
                    'qCom': str(n),
                    'uCom': 'PC',
                    'NCM': '84818099',
                },
            ),
        )
    return nf, itens


def _conferencia_com_itens(
    nf: NFeEntradaHistoricaImportada,
    itens_nf: list[ItemNFeEntradaHistoricaImportada],
    *,
    produto_por_n_item: dict[int, Produto | None] | None = None,
    corrida_por_n_item: dict[int, str] | None = None,
    lote_por_n_item: dict[int, str] | None = None,
) -> NFeEntradaConferencia:
    conf, _ = NFeEntradaConferencia.objects.get_or_create(nf_entrada_historica=nf)
    produto_por_n_item = produto_por_n_item or {}
    corrida_por_n_item = corrida_por_n_item or {}
    lote_por_n_item = lote_por_n_item or {}
    for it_nf in itens_nf:
        ic, _ = conf.itens.get_or_create(item_nfe_historico=it_nf)
        prod = produto_por_n_item.get(it_nf.n_item)
        if prod is not None:
            ic.produto = prod
            ic.status = ItemNFeEntradaConferencia.Status.PRODUTO_VINCULADO
        if it_nf.n_item in corrida_por_n_item:
            ic.corrida = corrida_por_n_item[it_nf.n_item]
        if it_nf.n_item in lote_por_n_item:
            ic.lote = lote_por_n_item[it_nf.n_item]
        ic.save()
    return conf


class CFRastreabilidadeConferenciaTests(TestCase):
    def setUp(self):
        s = uuid.uuid4().hex[:8]
        self.suffix = s
        self.forn = Fornecedor.objects.create(razao_social=f'Forn CF {s}', cnpj=_cnpj_unico())
        self.fam = FamiliaProduto.objects.create(
            codigo_figura=f'F{s}'[:16],
            descricao_base=f'Fam {s}',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
            tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
            categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
        )
        self.prod = Produto.objects.create(
            familia=self.fam,
            descricao=f'Prod {s}',
            modo_codigo=Produto.ModoCodigo.MANUAL,
            codigo_completo=f'PR-{s}',
            unidade='PC',
        )
        u = get_user_model().objects.create_user(f'cf_r_{s}', 'cf_r@test.com', 'x')
        self.user = _grant_cf(u, add=True, change=True)
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.url_preencher = reverse('certificado-fornecedor-preencher-por-nfe-entrada')
        self.url_list = reverse('certificado-fornecedor-list')

    def test_preencher_com_conferencia_existente_vincula_item_conferencia(self):
        nf, itens_nf = _nf_hist_com_itens(self.suffix, fornecedor=self.forn)
        conf = _conferencia_com_itens(nf, itens_nf)
        ic1 = conf.itens.get(item_nfe_historico=itens_nf[0])

        r = self.client.post(self.url_preencher, {'nf_entrada_historica_id': nf.id}, HTTP_HOST='localhost')
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(len(data['itens']), 2)
        self.assertEqual(data['itens'][0]['item_conferencia_id'], ic1.id)
        self.assertEqual(data['itens'][0]['origem_nfe_item_numero'], 1)

    def test_conferencia_com_produto_corrida_lote_herda_no_preencher(self):
        nf, itens_nf = _nf_hist_com_itens(f'{self.suffix}b', fornecedor=self.forn)
        _conferencia_com_itens(
            nf,
            itens_nf,
            produto_por_n_item={1: self.prod},
            corrida_por_n_item={1: '363'},
            lote_por_n_item={1: 'LT-A'},
        )
        r = self.client.post(self.url_preencher, {'nf_entrada_historica_id': nf.id}, HTTP_HOST='localhost')
        row = r.json()['itens'][0]
        self.assertEqual(row['produto'], self.prod.id)
        self.assertEqual(row['corrida'], '363')
        self.assertEqual(row['lote'], 'LT-A')
        self.assertTrue(row['origem_produto_vinculado'])

    def test_conferencia_sem_produto_mantem_produto_null_com_vinculo(self):
        nf, itens_nf = _nf_hist_com_itens(f'{self.suffix}c', fornecedor=self.forn)
        conf = _conferencia_com_itens(nf, itens_nf, corrida_por_n_item={1: 'CR-X'})
        ic1 = conf.itens.get(item_nfe_historico=itens_nf[0])
        self.assertIsNone(ic1.produto_id)

        r = self.client.post(self.url_preencher, {'nf_entrada_historica_id': nf.id}, HTTP_HOST='localhost')
        row = r.json()['itens'][0]
        self.assertIsNone(row['produto'])
        self.assertEqual(row['item_conferencia_id'], ic1.id)
        self.assertEqual(row['corrida'], 'CR-X')
        self.assertFalse(row['origem_produto_vinculado'])

    def test_nf_sem_conferencia_previa_cria_e_vincula(self):
        nf, _ = _nf_hist_com_itens(f'{self.suffix}d', fornecedor=self.forn)
        self.assertFalse(NFeEntradaConferencia.objects.filter(nf_entrada_historica=nf).exists())

        r = self.client.post(self.url_preencher, {'nf_entrada_historica_id': nf.id}, HTTP_HOST='localhost')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(NFeEntradaConferencia.objects.filter(nf_entrada_historica=nf).exists())
        self.assertIsNotNone(r.json()['itens'][0]['item_conferencia_id'])

    def test_cf_manual_salva_sem_item_conferencia(self):
        payload = {
            'status': 'rascunho',
            'numero_certificado_fornecedor': f'MAN-{self.suffix}',
            'fornecedor': self.forn.id,
            'fornecedor_nome_snapshot': self.forn.razao_social,
            'numero_nf_entrada': '999',
            'itens': [
                {
                    'ordem': 1,
                    'codigo_produto': 'X1',
                    'descricao_material': 'Manual',
                    'quantidade': '1',
                    'unidade': 'PC',
                    'corrida': 'MAN-CR',
                    'norma': 'ASTM',
                    'tipo_dados_tecnicos': 'PADRAO_ITEM',
                    'composicao_json': {},
                    'ensaio_tracao_json': {},
                    'ensaio_impacto_json': {},
                },
            ],
        }
        r = self.client.post(self.url_list, payload, format='json', HTTP_HOST='localhost')
        self.assertEqual(r.status_code, 201, r.content)
        item = ItemCertificadoFornecedorEntrada.objects.get(certificado_fornecedor_id=r.json()['id'])
        self.assertIsNone(item.item_conferencia_id)

    def test_nao_permite_dois_itens_cf_mesma_conferencia(self):
        nf, itens_nf = _nf_hist_com_itens(f'{self.suffix}e', fornecedor=self.forn)
        conf = _conferencia_com_itens(nf, itens_nf)
        ic1 = conf.itens.get(item_nfe_historico=itens_nf[0])

        payload = {
            'status': 'rascunho',
            'numero_certificado_fornecedor': f'DUP-{self.suffix}',
            'fornecedor': self.forn.id,
            'fornecedor_nome_snapshot': self.forn.razao_social,
            'nf_entrada_historica': nf.id,
            'numero_nf_entrada': nf.numero,
            'serie_nf_entrada': nf.serie,
            'itens': [
                {
                    'ordem': 1,
                    'codigo_produto': 'A',
                    'descricao_material': 'A',
                    'quantidade': '1',
                    'unidade': 'PC',
                    'corrida': 'C1',
                    'norma': 'N',
                    'tipo_dados_tecnicos': 'PADRAO_ITEM',
                    'item_conferencia_id': ic1.id,
                    'composicao_json': {},
                    'ensaio_tracao_json': {},
                    'ensaio_impacto_json': {},
                },
                {
                    'ordem': 2,
                    'codigo_produto': 'B',
                    'descricao_material': 'B',
                    'quantidade': '1',
                    'unidade': 'PC',
                    'corrida': 'C2',
                    'norma': 'N',
                    'tipo_dados_tecnicos': 'PADRAO_ITEM',
                    'item_conferencia_id': ic1.id,
                    'composicao_json': {},
                    'ensaio_tracao_json': {},
                    'ensaio_impacto_json': {},
                },
            ],
        }
        r = self.client.post(self.url_list, payload, format='json', HTTP_HOST='localhost')
        self.assertEqual(r.status_code, 400)

    def test_nao_permite_item_conferencia_de_outra_nf(self):
        nf1, itens1 = _nf_hist_com_itens(f'{self.suffix}f1', fornecedor=self.forn)
        conf1 = _conferencia_com_itens(nf1, itens1)
        ic_outra = conf1.itens.get(item_nfe_historico=itens1[0])

        nf2, _ = _nf_hist_com_itens(f'{self.suffix}f2', fornecedor=self.forn)

        payload = {
            'status': 'rascunho',
            'numero_certificado_fornecedor': f'OUT-{self.suffix}',
            'fornecedor': self.forn.id,
            'fornecedor_nome_snapshot': self.forn.razao_social,
            'nf_entrada_historica': nf2.id,
            'numero_nf_entrada': nf2.numero,
            'serie_nf_entrada': nf2.serie,
            'itens': [
                {
                    'ordem': 1,
                    'codigo_produto': 'A',
                    'descricao_material': 'A',
                    'quantidade': '1',
                    'unidade': 'PC',
                    'corrida': 'C1',
                    'norma': 'N',
                    'tipo_dados_tecnicos': 'PADRAO_ITEM',
                    'item_conferencia_id': ic_outra.id,
                    'composicao_json': {},
                    'ensaio_tracao_json': {},
                    'ensaio_impacto_json': {},
                },
            ],
        }
        r = self.client.post(self.url_list, payload, format='json', HTTP_HOST='localhost')
        self.assertEqual(r.status_code, 400)
        self.assertIn('item_conferencia', str(r.content).lower())

    def test_busca_corrida_363_continua_funcionando(self):
        s = self.suffix
        cf = CertificadoFornecedorEntrada.objects.create(
            status=CertificadoFornecedorEntrada.Status.REGISTRADO,
            numero_certificado_fornecedor=f'CF363-{s}',
            fornecedor=self.forn,
            fornecedor_nome_snapshot=self.forn.razao_social,
            numero_nf_entrada='100',
        )
        ItemCertificadoFornecedorEntrada.objects.create(
            certificado_fornecedor=cf,
            ordem=1,
            produto=None,
            codigo_produto='COD',
            descricao_material='Desc',
            corrida='363',
            norma='ASTM',
            composicao_json={'C': '0.2'},
            ensaio_tracao_json={'limite_escoamento': '250'},
            tipo_dados_tecnicos=ItemCertificadoFornecedorEntrada.TipoDadosTecnicos.PADRAO_ITEM,
        )
        url = reverse('certificado-fornecedor-buscar-dados-tecnicos')
        r = self.client.get(url, {'corrida': '363'}, HTTP_HOST='localhost')
        self.assertEqual(r.status_code, 200)
        data = r.json()
        resultados = data['resultados'] if isinstance(data, dict) else data
        self.assertTrue(any(x.get('corrida') == '363' for x in resultados))

    def test_salvar_com_vinculo_preenche_origem_vinculada_em(self):
        nf, itens_nf = _nf_hist_com_itens(f'{self.suffix}g', fornecedor=self.forn)
        conf = _conferencia_com_itens(nf, itens_nf)
        ic1 = conf.itens.get(item_nfe_historico=itens_nf[0])

        payload = {
            'status': 'rascunho',
            'numero_certificado_fornecedor': f'VIN-{self.suffix}',
            'fornecedor': self.forn.id,
            'fornecedor_nome_snapshot': self.forn.razao_social,
            'nf_entrada_historica': nf.id,
            'numero_nf_entrada': nf.numero,
            'serie_nf_entrada': nf.serie,
            'itens': [
                {
                    'ordem': 1,
                    'codigo_produto': 'C1',
                    'descricao_material': 'D1',
                    'quantidade': '1',
                    'unidade': 'PC',
                    'corrida': '',
                    'norma': '',
                    'tipo_dados_tecnicos': 'PADRAO_ITEM',
                    'item_conferencia_id': ic1.id,
                    'composicao_json': {},
                    'ensaio_tracao_json': {},
                    'ensaio_impacto_json': {},
                },
            ],
        }
        r = self.client.post(self.url_list, payload, format='json', HTTP_HOST='localhost')
        self.assertEqual(r.status_code, 201, r.content)
        item = ItemCertificadoFornecedorEntrada.objects.get(certificado_fornecedor_id=r.json()['id'])
        self.assertEqual(item.item_conferencia_id, ic1.id)
        self.assertEqual(item.origem_nfe_item_numero, 1)
        self.assertIsNotNone(item.origem_vinculada_em)
