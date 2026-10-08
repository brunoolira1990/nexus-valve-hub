"""Tarefa A1 — corridas adicionais com os mesmos dados técnicos no Certificado de Fornecedor.

Cobre: validação de quantidades (soma derivada da principal), duplicidade corrida/lote,
compatibilidade com registros históricos sem quantidade e busca de dados técnicos
reconhecendo corridas adicionais (dados herdados do item principal), sem escolha automática
em caso de ambiguidade.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.cadastros.models import Fornecedor
from apps.fiscal.models import EstoqueCorrida
from apps.produtos.models import FamiliaProduto, Produto
from apps.qualidade.models import (
    CertificadoFornecedorEntrada,
    ItemCertificadoFornecedorCorrida,
    ItemCertificadoFornecedorEntrada,
)
from apps.qualidade.serializers import (
    MSG_CORRIDA_LOTE_DUPLICADA_ITEM_CF,
    MSG_PRINCIPAL_SEM_QUANTIDADE_ITEM_CF,
    MSG_QUANTIDADE_CORRIDA_ADICIONAL_INVALIDA,
    MSG_SOMA_CORRIDAS_EXCEDE_ITEM_CF,
    validar_corridas_adicionais_item_cf,
)


def _cnpj_unico() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


def _grant_cf_perms(user):
    ct = ContentType.objects.get_for_model(CertificadoFornecedorEntrada)
    for codename in (
        'add_certificadofornecedorentrada',
        'change_certificadofornecedorentrada',
        'view_certificadofornecedorentrada',
    ):
        user.user_permissions.add(Permission.objects.get(content_type=ct, codename=codename))
    return get_user_model().objects.get(pk=user.pk)


class ValidarCorridasAdicionaisItemCfTests(TestCase):
    """Regra final da soma: quantidade da principal é derivada (total − adicionais)."""

    def test_total_14_adicional_6_aceita_principal_derivada_8(self):
        erros = validar_corridas_adicionais_item_cf(
            quantidade_item=Decimal('14'),
            corrida_principal='3242',
            lote_principal='',
            corridas_adicionais=[{'corrida': 'AB337', 'lote': '', 'quantidade': Decimal('6')}],
        )
        self.assertEqual(erros, [])

    def test_total_14_adicionais_6_e_3_aceita_principal_derivada_5(self):
        erros = validar_corridas_adicionais_item_cf(
            quantidade_item=Decimal('14'),
            corrida_principal='3242',
            lote_principal='',
            corridas_adicionais=[
                {'corrida': 'AB337', 'lote': '', 'quantidade': Decimal('6')},
                {'corrida': 'CC001', 'lote': '', 'quantidade': Decimal('3')},
            ],
        )
        self.assertEqual(erros, [])

    def test_soma_igual_ao_total_rejeita_principal_sem_quantidade(self):
        erros = validar_corridas_adicionais_item_cf(
            quantidade_item=Decimal('14'),
            corrida_principal='3242',
            lote_principal='',
            corridas_adicionais=[{'corrida': 'AB337', 'lote': '', 'quantidade': Decimal('14')}],
        )
        self.assertIn(MSG_PRINCIPAL_SEM_QUANTIDADE_ITEM_CF, erros)
        self.assertNotIn(MSG_SOMA_CORRIDAS_EXCEDE_ITEM_CF, erros)

    def test_soma_maior_que_total_rejeita(self):
        erros = validar_corridas_adicionais_item_cf(
            quantidade_item=Decimal('14'),
            corrida_principal='3242',
            lote_principal='',
            corridas_adicionais=[{'corrida': 'AB337', 'lote': '', 'quantidade': Decimal('15')}],
        )
        self.assertIn(MSG_SOMA_CORRIDAS_EXCEDE_ITEM_CF, erros)
        self.assertNotIn(MSG_PRINCIPAL_SEM_QUANTIDADE_ITEM_CF, erros)

    def test_soma_menor_permitida_principal_recebe_saldo(self):
        erros = validar_corridas_adicionais_item_cf(
            quantidade_item=Decimal('14'),
            corrida_principal='3242',
            lote_principal='',
            corridas_adicionais=[{'corrida': 'AB337', 'lote': '', 'quantidade': Decimal('3')}],
        )
        self.assertEqual(erros, [])

    def test_quantidade_zero_ou_negativa_rejeita(self):
        for quantidade in (Decimal('0'), Decimal('-1')):
            erros = validar_corridas_adicionais_item_cf(
                quantidade_item=Decimal('14'),
                corrida_principal='3242',
                lote_principal='',
                corridas_adicionais=[{'corrida': 'AB337', 'lote': '', 'quantidade': quantidade}],
            )
            self.assertIn(MSG_QUANTIDADE_CORRIDA_ADICIONAL_INVALIDA, erros)

    def test_quantidade_vazia_sem_certificado_rejeita_linha_nova(self):
        """Sem CF em edição não existe legado possível: quantidade vazia é linha nova."""
        erros = validar_corridas_adicionais_item_cf(
            quantidade_item=Decimal('14'),
            corrida_principal='3242',
            lote_principal='',
            corridas_adicionais=[{'corrida': 'AB337', 'lote': '', 'quantidade': None}],
        )
        self.assertIn(MSG_QUANTIDADE_CORRIDA_ADICIONAL_INVALIDA, erros)

    def test_duplicidade_corrida_lote_normalizada_rejeita(self):
        erros = validar_corridas_adicionais_item_cf(
            quantidade_item=Decimal('14'),
            corrida_principal='3242',
            lote_principal='',
            corridas_adicionais=[
                {'corrida': 'AB 337', 'lote': 'L1', 'quantidade': Decimal('3')},
                {'corrida': 'ab  337', 'lote': 'l1', 'quantidade': Decimal('3')},
            ],
        )
        self.assertIn(MSG_CORRIDA_LOTE_DUPLICADA_ITEM_CF, erros)

    def test_adicional_igual_a_principal_rejeita(self):
        erros = validar_corridas_adicionais_item_cf(
            quantidade_item=Decimal('14'),
            corrida_principal='3242',
            lote_principal='L1',
            corridas_adicionais=[{'corrida': '3242', 'lote': 'L1', 'quantidade': Decimal('6')}],
        )
        self.assertIn(MSG_CORRIDA_LOTE_DUPLICADA_ITEM_CF, erros)

    def test_lotes_diferentes_da_mesma_corrida_permitidos(self):
        erros = validar_corridas_adicionais_item_cf(
            quantidade_item=Decimal('14'),
            corrida_principal='3242',
            lote_principal='L1',
            corridas_adicionais=[{'corrida': '3242', 'lote': 'L2', 'quantidade': Decimal('6')}],
        )
        self.assertEqual(erros, [])


class CorridasAdicionaisApiTests(TestCase):
    def setUp(self):
        s = uuid.uuid4().hex[:8]
        self.forn = Fornecedor.objects.create(razao_social=f'Forn A1 {s}', cnpj=_cnpj_unico())
        self.fam = FamiliaProduto.objects.create(
            codigo_figura=f'FA1{s}'[:16],
            descricao_base=f'Fam A1 {s}',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
            tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
            categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
        )
        self.prod = Produto.objects.create(
            familia=self.fam,
            descricao=f'Prod A1 {s}',
            modo_codigo=Produto.ModoCodigo.MANUAL,
            codigo_completo=f'PR-A1-{s}',
            unidade='PC',
        )
        u = get_user_model().objects.create_user(f'a1_{s}', 'a1@test.com', 'x')
        self.user = _grant_cf_perms(u)
        self.client_api = APIClient()
        self.client_api.force_authenticate(self.user)
        self.url_list = reverse('certificado-fornecedor-list')

    def _payload_base(self, itens):
        return {
            'status': 'rascunho',
            'numero_certificado_fornecedor': f'CF-A1-{uuid.uuid4().hex[:6]}',
            'fornecedor': self.forn.id,
            'fornecedor_nome_snapshot': self.forn.razao_social,
            'numero_nf_entrada': '777',
            'itens': itens,
        }

    def _item_base(self, **overrides):
        item = {
            'ordem': 1,
            'produto': self.prod.id,
            'codigo_produto': self.prod.codigo_completo,
            'descricao_material': self.prod.descricao,
            'quantidade': '14.000',
            'unidade': 'PC',
            'corrida': '3242',
            'lote': '',
            'norma': 'ASTM A105',
            'tipo_dados_tecnicos': 'PADRAO_ITEM',
            'composicao_json': {'C': '0.20'},
            'ensaio_tracao_json': {'limite_escoamento': '250'},
            'ensaio_impacto_json': {},
            'componentes': [],
            'corridas_adicionais': [],
        }
        item.update(overrides)
        return item

    def test_item_sem_adicionais_continua_funcionando(self):
        r = self.client_api.post(self.url_list, self._payload_base([self._item_base()]), format='json')
        self.assertEqual(r.status_code, 201, r.content)
        cert = CertificadoFornecedorEntrada.objects.get(pk=r.json()['id'])
        self.assertEqual(cert.itens.count(), 1)
        self.assertEqual(cert.itens.first().corridas_adicionais.count(), 0)

    def test_principal_mais_uma_adicional_salva_e_serializa(self):
        item = self._item_base(
            corridas_adicionais=[{'ordem': 1, 'corrida': 'AB337', 'lote': '', 'quantidade': '6.000'}],
        )
        r = self.client_api.post(self.url_list, self._payload_base([item]), format='json')
        self.assertEqual(r.status_code, 201, r.content)
        body = r.json()
        adicionais = body['itens'][0]['corridas_adicionais']
        self.assertEqual(len(adicionais), 1)
        self.assertEqual(adicionais[0]['corrida'], 'AB337')
        self.assertEqual(Decimal(adicionais[0]['quantidade']), Decimal('6.000'))

    def test_principal_mais_duas_adicionais_ordem_estavel(self):
        item = self._item_base(
            quantidade='20.000',
            corridas_adicionais=[
                {'ordem': 1, 'corrida': 'AB337', 'lote': '', 'quantidade': '6.000'},
                {'ordem': 2, 'corrida': 'CC001', 'lote': 'L2', 'quantidade': '4.000'},
            ],
        )
        r = self.client_api.post(self.url_list, self._payload_base([item]), format='json')
        self.assertEqual(r.status_code, 201, r.content)
        adicionais = r.json()['itens'][0]['corridas_adicionais']
        self.assertEqual([a['corrida'] for a in adicionais], ['AB337', 'CC001'])
        self.assertEqual([a['ordem'] for a in adicionais], [1, 2])

    def test_soma_maior_que_quantidade_do_item_rejeita(self):
        item = self._item_base(
            corridas_adicionais=[
                {'ordem': 1, 'corrida': 'AB337', 'lote': '', 'quantidade': '8.000'},
                {'ordem': 2, 'corrida': 'CC001', 'lote': '', 'quantidade': '7.000'},
            ],
        )
        r = self.client_api.post(self.url_list, self._payload_base([item]), format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('excede a quantidade do item', str(r.json()))
        self.assertEqual(CertificadoFornecedorEntrada.objects.count(), 0)

    def test_duplicidade_corrida_lote_rejeita(self):
        item = self._item_base(
            corridas_adicionais=[
                {'ordem': 1, 'corrida': 'AB337', 'lote': 'L1', 'quantidade': '3.000'},
                {'ordem': 2, 'corrida': 'ab 337', 'lote': 'l1', 'quantidade': '3.000'},
            ],
        )
        r = self.client_api.post(self.url_list, self._payload_base([item]), format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('já está vinculada a este item', str(r.json()))

    def test_quantidade_zero_rejeita(self):
        item = self._item_base(
            corridas_adicionais=[{'ordem': 1, 'corrida': 'AB337', 'lote': '', 'quantidade': '0'}],
        )
        r = self.client_api.post(self.url_list, self._payload_base([item]), format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('maior que zero', str(r.json()))

    def _criar_cf_historico_sem_quantidade(self, corrida_adicional='AB337', quantidade=None):
        cert = CertificadoFornecedorEntrada.objects.create(
            status=CertificadoFornecedorEntrada.Status.RASCUNHO,
            numero_certificado_fornecedor=f'CF-HIST-{uuid.uuid4().hex[:6]}',
            fornecedor=self.forn,
            fornecedor_nome_snapshot=self.forn.razao_social,
            numero_nf_entrada='888',
        )
        item = ItemCertificadoFornecedorEntrada.objects.create(
            certificado_fornecedor=cert,
            ordem=1,
            produto=self.prod,
            codigo_produto=self.prod.codigo_completo,
            descricao_material=self.prod.descricao,
            quantidade=Decimal('14'),
            corrida='3242',
            tipo_dados_tecnicos=ItemCertificadoFornecedorEntrada.TipoDadosTecnicos.PADRAO_ITEM,
        )
        linha = ItemCertificadoFornecedorCorrida.objects.create(
            item_certificado=item,
            ordem=1,
            corrida=corrida_adicional,
            lote='',
            quantidade=quantidade,
        )
        return cert, item, linha

    def test_registro_historico_sem_quantidade_abre_e_salva_sem_backfill(self):
        cert, _item, _linha = self._criar_cf_historico_sem_quantidade()
        url = reverse('certificado-fornecedor-detail', args=[cert.id])
        r_get = self.client_api.get(url)
        self.assertEqual(r_get.status_code, 200)
        payload = r_get.json()
        self.assertIsNone(payload['itens'][0]['corridas_adicionais'][0]['quantidade'])

        r_patch = self.client_api.patch(url, {'itens': payload['itens']}, format='json')
        self.assertEqual(r_patch.status_code, 200, r_patch.content)
        adicional = r_patch.json()['itens'][0]['corridas_adicionais'][0]
        self.assertIsNone(adicional['quantidade'])

    def test_historico_salvar_recarregar_e_salvar_de_novo_apos_upsert_recriar_ids(self):
        """`_upsert_itens` apaga e recria: a compatibilidade deve valer com os IDs novos."""
        cert, _item, linha_original = self._criar_cf_historico_sem_quantidade()
        url = reverse('certificado-fornecedor-detail', args=[cert.id])
        payload1 = self.client_api.get(url).json()
        r1 = self.client_api.patch(url, {'itens': payload1['itens']}, format='json')
        self.assertEqual(r1.status_code, 200, r1.content)

        payload2 = self.client_api.get(url).json()
        novo_id = payload2['itens'][0]['corridas_adicionais'][0]['id']
        self.assertNotEqual(novo_id, linha_original.id)
        r2 = self.client_api.patch(url, {'itens': payload2['itens']}, format='json')
        self.assertEqual(r2.status_code, 200, r2.content)
        self.assertIsNone(r2.json()['itens'][0]['corridas_adicionais'][0]['quantidade'])

    def test_nova_corrida_sem_quantidade_rejeita_no_create(self):
        item = self._item_base(
            corridas_adicionais=[{'ordem': 1, 'corrida': 'AB337', 'lote': '', 'quantidade': None}],
        )
        r = self.client_api.post(self.url_list, self._payload_base([item]), format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('maior que zero', str(r.json()))

    def test_nova_corrida_com_id_inventado_rejeita(self):
        cert, _item, _linha = self._criar_cf_historico_sem_quantidade()
        url = reverse('certificado-fornecedor-detail', args=[cert.id])
        payload = self.client_api.get(url).json()
        payload['itens'][0]['corridas_adicionais'].append(
            {'id': 99999999, 'ordem': 2, 'corrida': 'NOVA-X', 'lote': '', 'quantidade': None},
        )
        r = self.client_api.patch(url, {'itens': payload['itens']}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('maior que zero', str(r.json()))

    def test_nova_corrida_com_id_de_outro_cf_rejeita(self):
        cert, _item, _linha = self._criar_cf_historico_sem_quantidade()
        _cert2, _item2, linha_outro_cf = self._criar_cf_historico_sem_quantidade(corrida_adicional='ZZ999')
        url = reverse('certificado-fornecedor-detail', args=[cert.id])
        payload = self.client_api.get(url).json()
        payload['itens'][0]['corridas_adicionais'].append(
            {'id': linha_outro_cf.id, 'ordem': 2, 'corrida': 'ZZ999', 'lote': '', 'quantidade': None},
        )
        r = self.client_api.patch(url, {'itens': payload['itens']}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('maior que zero', str(r.json()))

    def test_nova_corrida_com_id_de_outra_linha_rejeita(self):
        """Reusar o id de uma linha legada com OUTRA corrida não burla a exigência de quantidade."""
        cert, item, linha = self._criar_cf_historico_sem_quantidade()
        url = reverse('certificado-fornecedor-detail', args=[cert.id])
        payload = self.client_api.get(url).json()
        payload['itens'][0]['corridas_adicionais'] = [
            {'id': linha.id, 'ordem': 1, 'corrida': 'OUTRA-CORRIDA', 'lote': '', 'quantidade': None},
        ]
        r = self.client_api.patch(url, {'itens': payload['itens']}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('maior que zero', str(r.json()))

    def test_id_de_linha_persistida_com_quantidade_nao_vira_legado_sem_quantidade(self):
        cert, _item, linha = self._criar_cf_historico_sem_quantidade(quantidade=Decimal('6'))
        url = reverse('certificado-fornecedor-detail', args=[cert.id])
        payload = self.client_api.get(url).json()
        payload['itens'][0]['corridas_adicionais'][0]['quantidade'] = None
        r = self.client_api.patch(url, {'itens': payload['itens']}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('maior que zero', str(r.json()))

    def test_historico_linha_antiga_sem_quantidade_e_linha_nova_sem_quantidade(self):
        cert, _item, _linha = self._criar_cf_historico_sem_quantidade()
        url = reverse('certificado-fornecedor-detail', args=[cert.id])
        payload = self.client_api.get(url).json()
        payload['itens'][0]['corridas_adicionais'].append(
            {'ordem': 2, 'corrida': 'NOVA-Y', 'lote': '', 'quantidade': None},
        )
        r = self.client_api.patch(url, {'itens': payload['itens']}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('maior que zero', str(r.json()))

        # A mesma linha nova com quantidade válida passa; a antiga segue sem backfill.
        payload['itens'][0]['corridas_adicionais'][-1]['quantidade'] = '4.000'
        r_ok = self.client_api.patch(url, {'itens': payload['itens']}, format='json')
        self.assertEqual(r_ok.status_code, 200, r_ok.content)
        adicionais = r_ok.json()['itens'][0]['corridas_adicionais']
        self.assertIsNone(adicionais[0]['quantidade'])
        self.assertEqual(Decimal(adicionais[1]['quantidade']), Decimal('4.000'))

    def test_soma_igual_ao_total_rejeita_via_api(self):
        item = self._item_base(
            corridas_adicionais=[{'ordem': 1, 'corrida': 'AB337', 'lote': '', 'quantidade': '14.000'}],
        )
        r = self.client_api.post(self.url_list, self._payload_base([item]), format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('deixa a corrida principal sem quantidade', str(r.json()))

    def test_salvar_nao_altera_estoque(self):
        antes = EstoqueCorrida.objects.count()
        item = self._item_base(
            corridas_adicionais=[{'ordem': 1, 'corrida': 'AB337', 'lote': '', 'quantidade': '6.000'}],
        )
        r = self.client_api.post(self.url_list, self._payload_base([item]), format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(EstoqueCorrida.objects.count(), antes)


class BuscaDadosTecnicosCorridasAdicionaisTests(TestCase):
    def setUp(self):
        s = uuid.uuid4().hex[:8]
        self.forn = Fornecedor.objects.create(razao_social=f'Forn BA1 {s}', cnpj=_cnpj_unico())
        self.fam = FamiliaProduto.objects.create(
            codigo_figura=f'FB1{s}'[:16],
            descricao_base=f'Fam BA1 {s}',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
            tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
            categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
        )
        self.prod = Produto.objects.create(
            familia=self.fam,
            descricao=f'Prod BA1 {s}',
            modo_codigo=Produto.ModoCodigo.MANUAL,
            codigo_completo=f'PR-BA1-{s}',
            unidade='PC',
        )
        self.cf = CertificadoFornecedorEntrada.objects.create(
            status=CertificadoFornecedorEntrada.Status.REGISTRADO,
            numero_certificado_fornecedor=f'CF-BA1-{s}',
            fornecedor=self.forn,
            fornecedor_nome_snapshot=self.forn.razao_social,
            numero_nf_entrada='901',
        )
        self.item = ItemCertificadoFornecedorEntrada.objects.create(
            certificado_fornecedor=self.cf,
            ordem=1,
            produto=self.prod,
            codigo_produto=self.prod.codigo_completo,
            descricao_material=self.prod.descricao,
            quantidade=Decimal('14'),
            corrida='3242',
            lote='',
            norma='ASTM A105',
            composicao_json={'C': '0.20'},
            ensaio_tracao_json={'limite_escoamento': '250'},
            tipo_dados_tecnicos=ItemCertificadoFornecedorEntrada.TipoDadosTecnicos.PADRAO_ITEM,
        )
        self.adicional = ItemCertificadoFornecedorCorrida.objects.create(
            item_certificado=self.item,
            ordem=1,
            corrida='AB337',
            lote='LB1',
            quantidade=Decimal('6'),
        )
        u = get_user_model().objects.create_user(f'ba1_{s}', 'ba1@test.com', 'x')
        self.user = _grant_cf_perms(u)
        self.client_api = APIClient()
        self.client_api.force_authenticate(self.user)
        self.url = reverse('certificado-fornecedor-buscar-dados-tecnicos')

    def _buscar(self, **params):
        r = self.client_api.get(self.url, params, HTTP_HOST='localhost')
        self.assertEqual(r.status_code, 200, r.content)
        body = r.json()
        return body['resultados'] if isinstance(body, dict) else body

    def test_busca_pela_corrida_principal_sem_flag_herdado(self):
        rows = self._buscar(produto=self.prod.id, corrida='3242')
        row = next(x for x in rows if x['id'] == self.item.id)
        self.assertFalse(row['dados_tecnicos_herdados'])
        self.assertEqual(row['origem_dados_tecnicos'], 'item_principal')
        self.assertEqual(row['corrida_encontrada'], '3242')

    def test_busca_pela_corrida_adicional_retorna_item_principal_herdado(self):
        rows = self._buscar(produto=self.prod.id, corrida='AB337')
        row = next(x for x in rows if x['id'] == self.item.id)
        self.assertTrue(row['dados_tecnicos_herdados'])
        self.assertEqual(row['origem_dados_tecnicos'], 'item_principal_corrida_adicional')
        self.assertEqual(row['corrida_encontrada'], 'AB337')
        self.assertEqual(row['lote_encontrado'], 'LB1')
        self.assertEqual(row['quantidade_corrida_encontrada'], 6.0)
        self.assertIn('compartilha os dados técnicos do item principal', row['mensagem_corrida_adicional'])
        # Dados técnicos vêm do item principal (herdados, não próprios da adicional).
        self.assertEqual(row['composicao_json'], {'C': '0.20'})
        self.assertEqual(row['corrida'], '3242')

    def test_busca_somente_por_produto_nao_usa_corridas_adicionais(self):
        rows = self._buscar(produto=self.prod.id)
        for row in rows:
            self.assertFalse(row.get('dados_tecnicos_herdados'))

    def test_ambiguidade_dois_cf_mesma_corrida_adicional_retorna_ambos(self):
        s = uuid.uuid4().hex[:8]
        cf2 = CertificadoFornecedorEntrada.objects.create(
            status=CertificadoFornecedorEntrada.Status.REGISTRADO,
            numero_certificado_fornecedor=f'CF-BA2-{s}',
            fornecedor=self.forn,
            fornecedor_nome_snapshot=self.forn.razao_social,
            numero_nf_entrada='902',
        )
        item2 = ItemCertificadoFornecedorEntrada.objects.create(
            certificado_fornecedor=cf2,
            ordem=1,
            produto=self.prod,
            codigo_produto=self.prod.codigo_completo,
            descricao_material=self.prod.descricao,
            quantidade=Decimal('10'),
            corrida='9999',
            norma='ASTM A105',
            composicao_json={'C': '0.30'},
            tipo_dados_tecnicos=ItemCertificadoFornecedorEntrada.TipoDadosTecnicos.PADRAO_ITEM,
        )
        ItemCertificadoFornecedorCorrida.objects.create(
            item_certificado=item2,
            ordem=1,
            corrida='AB337',
            lote='',
            quantidade=Decimal('4'),
        )
        rows = self._buscar(produto=self.prod.id, corrida='AB337')
        ids = {x['id'] for x in rows}
        self.assertIn(self.item.id, ids)
        self.assertIn(item2.id, ids)

    def test_nao_mistura_cf_de_outro_fornecedor_por_filtro(self):
        s = uuid.uuid4().hex[:8]
        forn2 = Fornecedor.objects.create(razao_social=f'Forn OUT {s}', cnpj=_cnpj_unico())
        cf_out = CertificadoFornecedorEntrada.objects.create(
            status=CertificadoFornecedorEntrada.Status.REGISTRADO,
            numero_certificado_fornecedor=f'CF-OUT-{s}',
            fornecedor=forn2,
            fornecedor_nome_snapshot=forn2.razao_social,
            numero_nf_entrada='903',
        )
        item_out = ItemCertificadoFornecedorEntrada.objects.create(
            certificado_fornecedor=cf_out,
            ordem=1,
            produto=self.prod,
            codigo_produto=self.prod.codigo_completo,
            descricao_material=self.prod.descricao,
            quantidade=Decimal('5'),
            corrida='8888',
            tipo_dados_tecnicos=ItemCertificadoFornecedorEntrada.TipoDadosTecnicos.PADRAO_ITEM,
        )
        ItemCertificadoFornecedorCorrida.objects.create(
            item_certificado=item_out,
            ordem=1,
            corrida='AB337',
            lote='',
            quantidade=Decimal('2'),
        )
        rows = self._buscar(produto=self.prod.id, corrida='AB337', fornecedor=self.forn.id)
        ids = {x['id'] for x in rows}
        self.assertIn(self.item.id, ids)
        self.assertNotIn(item_out.id, ids)
