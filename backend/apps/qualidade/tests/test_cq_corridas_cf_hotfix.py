"""Hotfix CQ — múltiplas corridas do CF exato como itens irmãos do CQ.

Fixture sanitizada equivalente ao caso urgente: item de CQ com quantidade 14,
CF com corrida principal 3242 e corrida adicional AB337 (6), principal derivada 8.
Sem dados reais; nenhum estoque/documento fiscal é alterado.
"""

from __future__ import annotations

import io
import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from pypdf import PdfReader
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Fornecedor
from apps.fiscal.models import EstoqueCorrida
from apps.produtos.models import FamiliaProduto, Produto
from apps.qualidade.certificado_pdf import gerar_certificado_qualidade_pdf
from apps.qualidade.corridas_cf_para_cq import (
    MSG_ADICIONAL_SEM_QUANTIDADE_CF,
    MSG_ITEM_CF_SEM_CORRIDAS_ELEGIVEIS,
    MSG_ITEM_CF_VINCULO_INVALIDO,
    MSG_ORIGEM_DOCUMENTAL_NAO_FISICA_CQ,
    ItemCfNaoEncontradoError,
    listar_corridas_cf_para_item_cq,
    quantidade_principal_derivada_item_cf,
)
from apps.qualidade.models import (
    CertificadoFornecedorEntrada,
    CertificadoQualidade,
    ItemCertificadoFornecedorCorrida,
    ItemCertificadoFornecedorEntrada,
    ItemCertificadoQualidade,
)


def _cnpj() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


def _criar_produto(suffix: str) -> Produto:
    fam = FamiliaProduto.objects.create(
        codigo_figura=f'F{suffix}'[:16],
        descricao_base='Fam',
        tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
        categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
    )
    return Produto.objects.create(
        familia=fam,
        descricao=f'Prod {suffix}',
        modo_codigo=Produto.ModoCodigo.MANUAL,
        codigo_completo=f'P-{suffix}',
        unidade='PC',
        ncm='84818099',
    )


class CorridasCfParaCqBase(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username=f'u{uuid.uuid4().hex[:8]}', password='x')
        ct = ContentType.objects.get_for_model(CertificadoQualidade)
        for codename in ('add_certificadoqualidade', 'change_certificadoqualidade', 'view_certificadoqualidade'):
            self.user.user_permissions.add(Permission.objects.get(content_type=ct, codename=codename))
        self.user = get_user_model().objects.get(pk=self.user.pk)
        self.client_api = APIClient()
        self.client_api.force_authenticate(user=self.user)

        self.forn = Fornecedor.objects.create(razao_social='Fornecedor Hotfix', cnpj=_cnpj())
        self.prod = _criar_produto(uuid.uuid4().hex[:6])
        self.cf = CertificadoFornecedorEntrada.objects.create(
            status=CertificadoFornecedorEntrada.Status.REGISTRADO,
            numero_certificado_fornecedor=f'CF-{uuid.uuid4().hex[:6]}',
            fornecedor=self.forn,
            fornecedor_nome_snapshot=self.forn.razao_social,
            numero_nf_entrada='777',
        )
        self.item_cf = ItemCertificadoFornecedorEntrada.objects.create(
            certificado_fornecedor=self.cf,
            ordem=1,
            produto=self.prod,
            codigo_produto=self.prod.codigo_completo,
            descricao_material=self.prod.descricao,
            quantidade=Decimal('14'),
            unidade='PC',
            norma='ASTM A105',
            corrida='3242',
            lote='',
            tipo_dados_tecnicos=ItemCertificadoFornecedorEntrada.TipoDadosTecnicos.PADRAO_ITEM,
            composicao_json={'C': '0.20', 'Mn': '0.90'},
            ensaio_tracao_json={'limite_escoamento': '250'},
        )
        self.adicional = ItemCertificadoFornecedorCorrida.objects.create(
            item_certificado=self.item_cf,
            ordem=1,
            corrida='AB337',
            lote='',
            quantidade=Decimal('6'),
        )
        self.url = reverse('certificado-qualidade-corridas-certificado-fornecedor')


class ListarCorridasCfParaItemCqTests(CorridasCfParaCqBase):
    def test_retorna_principal_derivada_e_adicional_herdada(self):
        payload = listar_corridas_cf_para_item_cq(
            certificado_fornecedor_id=self.cf.id,
            item_certificado_fornecedor_id=self.item_cf.id,
        )
        linhas = payload['linhas']
        self.assertEqual([l['corrida'] for l in linhas], ['3242', 'AB337'])
        principal, adicional = linhas
        self.assertEqual(principal['tipo_linha'], 'corrida_principal')
        self.assertEqual(principal['quantidade_no_certificado'], '8.000')
        self.assertTrue(principal['dados_tecnicos_herdados'])
        self.assertEqual(adicional['tipo_linha'], 'corrida_adicional')
        self.assertEqual(adicional['quantidade_no_certificado'], '6.000')
        self.assertTrue(adicional['dados_tecnicos_herdados'])
        # Dados técnicos vêm do item exato do CF, para as duas linhas.
        for linha in linhas:
            self.assertEqual(linha['item_certificado_fornecedor_id'], self.item_cf.id)
            self.assertEqual(linha['certificado_fornecedor_id'], self.cf.id)
            self.assertEqual(linha['dados_tecnicos']['composicao_json'], {'C': '0.20', 'Mn': '0.90'})
            self.assertTrue(linha['permite_preenchimento_manual'])
            self.assertEqual(linha['modo_dados_tecnicos_padrao'], 'herdados')
            self.assertEqual(linha['modos_dados_tecnicos_permitidos'], ['herdados', 'manual'])
            self.assertIn('Dados técnicos herdados', linha['origem_tecnica_label'])
            self.assertIn('certificado_fornecedor:', linha['chave_origem'])
            self.assertNotIn('saldo', linha)
            self.assertNotIn('quantidade_disponivel', linha)
        self.assertEqual(payload['avisos'], [])
        self.assertEqual(payload['mensagem_origem_fisica'], MSG_ORIGEM_DOCUMENTAL_NAO_FISICA_CQ)

    def test_item_de_outro_certificado_nao_e_encontrado(self):
        outro_cf = CertificadoFornecedorEntrada.objects.create(
            status=CertificadoFornecedorEntrada.Status.REGISTRADO,
            numero_certificado_fornecedor=f'CF-{uuid.uuid4().hex[:6]}',
            fornecedor=self.forn,
            fornecedor_nome_snapshot=self.forn.razao_social,
        )
        with self.assertRaises(ItemCfNaoEncontradoError):
            listar_corridas_cf_para_item_cq(
                certificado_fornecedor_id=outro_cf.id,
                item_certificado_fornecedor_id=self.item_cf.id,
            )

    def test_item_ausente_em_cf_valido_retorna_colecao_vazia(self):
        """IDs órfãos após regravação do CF não devem virar 404 genérico."""
        payload = listar_corridas_cf_para_item_cq(
            certificado_fornecedor_id=self.cf.id,
            item_certificado_fornecedor_id=99999999,
        )
        self.assertEqual(payload['linhas'], [])
        self.assertIn(MSG_ITEM_CF_VINCULO_INVALIDO, payload['avisos'])

    def test_item_inativo_em_cf_valido_retorna_colecao_vazia(self):
        self.item_cf.ativo = False
        self.item_cf.save(update_fields=['ativo'])
        payload = listar_corridas_cf_para_item_cq(
            certificado_fornecedor_id=self.cf.id,
            item_certificado_fornecedor_id=self.item_cf.id,
        )
        self.assertEqual(payload['linhas'], [])
        self.assertIn(MSG_ITEM_CF_VINCULO_INVALIDO, payload['avisos'])

    def test_item_valido_sem_corridas_retorna_colecao_vazia(self):
        self.item_cf.corrida = ''
        self.item_cf.lote = ''
        self.item_cf.save(update_fields=['corrida', 'lote'])
        self.item_cf.corridas_adicionais.all().delete()
        payload = listar_corridas_cf_para_item_cq(
            certificado_fornecedor_id=self.cf.id,
            item_certificado_fornecedor_id=self.item_cf.id,
        )
        self.assertEqual(payload['linhas'], [])
        self.assertIn(MSG_ITEM_CF_SEM_CORRIDAS_ELEGIVEIS, payload['avisos'])

    def test_certificado_inexistente_continua_erro(self):
        with self.assertRaises(ItemCfNaoEncontradoError):
            listar_corridas_cf_para_item_cq(
                certificado_fornecedor_id=99999999,
                item_certificado_fornecedor_id=99999998,
            )

    def test_item_independente_sem_vinculo_inequivoco_nao_aparece_mesmo_com_mesmo_produto(self):
        ItemCertificadoFornecedorEntrada.objects.create(
            certificado_fornecedor=self.cf,
            ordem=2,
            produto=self.prod,
            codigo_produto=self.prod.codigo_completo,
            descricao_material=self.prod.descricao,
            quantidade=Decimal('5'),
            corrida='CC900',
            composicao_json={'C': '0.30'},
        )
        outro_cf = CertificadoFornecedorEntrada.objects.create(
            status=CertificadoFornecedorEntrada.Status.REGISTRADO,
            fornecedor=self.forn,
            fornecedor_nome_snapshot=self.forn.razao_social,
        )
        ItemCertificadoFornecedorEntrada.objects.create(
            certificado_fornecedor=outro_cf,
            ordem=1,
            produto=self.prod,
            quantidade=Decimal('7'),
            corrida='EE200',
        )
        payload = listar_corridas_cf_para_item_cq(
            certificado_fornecedor_id=self.cf.id,
            item_certificado_fornecedor_id=self.item_cf.id,
        )
        corridas = [l['corrida'] for l in payload['linhas']]
        self.assertEqual(corridas, ['3242', 'AB337'])
        self.assertNotIn('CC900', corridas)  # mesmo CF/produto, mas sem vínculo inequívoco
        self.assertNotIn('EE200', corridas)  # outro certificado
        self.assertIn('A2', payload['limitacao_itens_independentes'])

    def test_adicional_historica_sem_quantidade_gera_aviso_e_nao_deriva_principal(self):
        ItemCertificadoFornecedorCorrida.objects.create(
            item_certificado=self.item_cf,
            ordem=2,
            corrida='HIST1',
            quantidade=None,
        )
        payload = listar_corridas_cf_para_item_cq(
            certificado_fornecedor_id=self.cf.id,
            item_certificado_fornecedor_id=self.item_cf.id,
        )
        self.assertIn(MSG_ADICIONAL_SEM_QUANTIDADE_CF, payload['avisos'])
        principal = payload['linhas'][0]
        self.assertIsNone(principal['quantidade_no_certificado'])
        linha_hist = next(l for l in payload['linhas'] if l['corrida'] == 'HIST1')
        self.assertIsNone(linha_hist['quantidade_no_certificado'])

    def test_quantidade_principal_derivada_regra_a1(self):
        qtd, determinavel = quantidade_principal_derivada_item_cf(self.item_cf)
        self.assertEqual(qtd, Decimal('8'))
        self.assertTrue(determinavel)


class CorridasCfEndpointTests(CorridasCfParaCqBase):
    def test_endpoint_retorna_corridas_do_cf_exato(self):
        r = self.client_api.get(
            self.url,
            {'certificado_fornecedor_id': self.cf.id, 'item_certificado_fornecedor_id': self.item_cf.id},
        )
        self.assertEqual(r.status_code, 200, r.content)
        body = r.json()
        self.assertEqual([l['corrida'] for l in body['linhas']], ['3242', 'AB337'])

    def test_endpoint_exige_ids_nao_busca_por_produto(self):
        r_sem_nada = self.client_api.get(self.url)
        self.assertEqual(r_sem_nada.status_code, 400)
        r_so_produto = self.client_api.get(self.url, {'produto_id': self.prod.id})
        self.assertEqual(r_so_produto.status_code, 400)

    def test_endpoint_404_para_item_de_outro_certificado(self):
        outro_cf = CertificadoFornecedorEntrada.objects.create(
            status=CertificadoFornecedorEntrada.Status.REGISTRADO,
            fornecedor=self.forn,
            fornecedor_nome_snapshot=self.forn.razao_social,
        )
        r = self.client_api.get(
            self.url,
            {'certificado_fornecedor_id': outro_cf.id, 'item_certificado_fornecedor_id': self.item_cf.id},
        )
        self.assertEqual(r.status_code, 404)

    def test_endpoint_colecao_vazia_para_item_inexistente_em_cf_valido(self):
        r = self.client_api.get(
            self.url,
            {'certificado_fornecedor_id': self.cf.id, 'item_certificado_fornecedor_id': 99999999},
        )
        self.assertEqual(r.status_code, 200, r.content)
        body = r.json()
        self.assertEqual(body['linhas'], [])
        self.assertIn(MSG_ITEM_CF_VINCULO_INVALIDO, body['avisos'])

    def test_endpoint_404_para_certificado_inexistente(self):
        r = self.client_api.get(
            self.url,
            {'certificado_fornecedor_id': 99999999, 'item_certificado_fornecedor_id': 99999998},
        )
        self.assertEqual(r.status_code, 404)

    def test_endpoint_exige_autenticacao(self):
        anonimo = APIClient()
        r = anonimo.get(
            self.url,
            {'certificado_fornecedor_id': self.cf.id, 'item_certificado_fornecedor_id': self.item_cf.id},
        )
        self.assertIn(r.status_code, (401, 403))

    def test_endpoint_exige_permissao_de_alteracao_do_cq(self):
        sem_permissao = get_user_model().objects.create_user(
            username=f'sp{uuid.uuid4().hex[:8]}', password='x'
        )
        client = APIClient()
        client.force_authenticate(user=sem_permissao)
        r = client.get(
            self.url,
            {'certificado_fornecedor_id': self.cf.id, 'item_certificado_fornecedor_id': self.item_cf.id},
        )
        self.assertEqual(r.status_code, 403)


class ItensIrmaosCqIndependentesTests(CorridasCfParaCqBase):
    """Cenários 1 e 2 do caso urgente: 3242 (8) + AB337 (6) no mesmo CQ."""

    def _payload_cq_duas_corridas(self, composicao_ab337: dict | None = None) -> dict:
        item_base = {
            'produto': self.prod.id,
            'codigo_produto': self.prod.codigo_completo,
            'descricao_material': self.prod.descricao,
            'unidade': 'PC',
            'tipo_dados_tecnicos': 'PADRAO_ITEM',
            'incluir_no_certificado': True,
            'certificado_fornecedor_origem_id': self.cf.id,
            'item_certificado_fornecedor_origem_id': self.item_cf.id,
            'fornecedor_nome_snapshot': self.forn.razao_social,
        }
        return {
            'numero': '',
            'serie': '',
            'cliente_nome_snapshot': 'Cliente Hotfix',
            'status': 'rascunho',
            'itens': [
                {
                    **item_base,
                    'ordem': 1,
                    'quantidade': '8.000',
                    'corrida': '3242',
                    'norma': 'ASTM A105',
                    'composicao_json': {'C': '0.20', 'Mn': '0.90'},
                    'ensaio_tracao_json': {'limite_escoamento': '250'},
                    'ensaio_impacto_json': {},
                    'componentes': [],
                },
                {
                    **item_base,
                    'ordem': 2,
                    'quantidade': '6.000',
                    'corrida': 'AB337',
                    'norma': 'ASTM A105' if composicao_ab337 is None else 'ASTM A350 LF2',
                    'composicao_json': composicao_ab337 if composicao_ab337 is not None else {'C': '0.20', 'Mn': '0.90'},
                    'ensaio_tracao_json': {},
                    'ensaio_impacto_json': {},
                    'componentes': [],
                },
            ],
        }

    def test_cenario_1_dados_herdados_cria_dois_itens_soma_14(self):
        r = self.client_api.post(
            reverse('certificado-qualidade-list'),
            self._payload_cq_duas_corridas(),
            format='json',
        )
        self.assertEqual(r.status_code, 201, r.content)
        itens = r.json()['itens']
        self.assertEqual(len(itens), 2)
        self.assertEqual([it['corrida'] for it in itens], ['3242', 'AB337'])
        soma = sum(Decimal(it['quantidade']) for it in itens)
        self.assertEqual(soma, Decimal('14'))
        for it in itens:
            self.assertEqual(it['certificado_fornecedor_origem_id'], self.cf.id)
            self.assertEqual(it['item_certificado_fornecedor_origem_id'], self.item_cf.id)

    def test_cenario_2_dados_proprios_editar_ab337_nao_altera_3242(self):
        r = self.client_api.post(
            reverse('certificado-qualidade-list'),
            self._payload_cq_duas_corridas(composicao_ab337={'C': '0.35', 'Cr': '1.10'}),
            format='json',
        )
        self.assertEqual(r.status_code, 201, r.content)
        cq_id = r.json()['id']
        payload = r.json()

        # Editar somente a AB337 (composição diferente) e salvar de novo.
        payload['itens'][1]['composicao_json'] = {'C': '0.40', 'Cr': '1.50'}
        r2 = self.client_api.patch(
            reverse('certificado-qualidade-detail', args=[cq_id]),
            {'itens': payload['itens']},
            format='json',
        )
        self.assertEqual(r2.status_code, 200, r2.content)
        itens = r2.json()['itens']
        self.assertEqual(itens[0]['composicao_json'], {'C': '0.20', 'Mn': '0.90'})
        self.assertEqual(itens[1]['composicao_json'], {'C': '0.40', 'Cr': '1.50'})
        self.assertEqual(itens[0]['norma'], 'ASTM A105')
        self.assertEqual(itens[1]['norma'], 'ASTM A350 LF2')

    def test_save_reload_reaplicar_preserva_dois_itens_e_dados_separados(self):
        """Fluxo completo do portão: salvar, recarregar, salvar de novo, recarregar.

        Confirma que a divisão 8 + 6 = 14 sobrevive ao _upsert_itens em dois ciclos
        de save, que os dados técnicos manuais da AB337 não são sobrescritos, que a
        origem documental permanece correta e que um item não relacionado do CQ é
        preservado.
        """
        outro_prod = _criar_produto(uuid.uuid4().hex[:6])
        payload = self._payload_cq_duas_corridas(composicao_ab337={'C': '0.35', 'Cr': '1.10'})
        payload['itens'][0]['origem_status_tecnico'] = 'dados_tecnicos_herdados_cf'
        payload['itens'][1]['origem_status_tecnico'] = 'dados_tecnicos_manuais_pendentes'
        payload['itens'].append({
            'ordem': 3,
            'produto': outro_prod.id,
            'codigo_produto': outro_prod.codigo_completo,
            'descricao_material': outro_prod.descricao,
            'unidade': 'PC',
            'quantidade': '3.000',
            'corrida': 'ZZ999',
            'norma': 'DIN 3202',
            'tipo_dados_tecnicos': 'PADRAO_ITEM',
            'incluir_no_certificado': True,
            'composicao_json': {'Fe': '99'},
            'ensaio_tracao_json': {},
            'ensaio_impacto_json': {},
            'componentes': [],
        })
        r = self.client_api.post(reverse('certificado-qualidade-list'), payload, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        cq_id = r.json()['id']

        def _reload() -> dict:
            resp = self.client_api.get(reverse('certificado-qualidade-detail', args=[cq_id]))
            self.assertEqual(resp.status_code, 200, resp.content)
            return resp.json()

        def _verificar(body: dict) -> None:
            itens = body['itens']
            self.assertEqual(len(itens), 3)
            por_corrida = {it['corrida']: it for it in itens}
            self.assertEqual(set(por_corrida), {'3242', 'AB337', 'ZZ999'})
            self.assertEqual(Decimal(por_corrida['3242']['quantidade']), Decimal('8'))
            self.assertEqual(Decimal(por_corrida['AB337']['quantidade']), Decimal('6'))
            self.assertEqual(
                Decimal(por_corrida['3242']['quantidade']) + Decimal(por_corrida['AB337']['quantidade']),
                Decimal('14'),
            )
            # Dados técnicos A permanecem na 3242, B na AB337 (não trocados).
            self.assertEqual(por_corrida['3242']['composicao_json'], {'C': '0.20', 'Mn': '0.90'})
            self.assertEqual(por_corrida['AB337']['composicao_json'], {'C': '0.35', 'Cr': '1.10'})
            # O backend normaliza campos operacionais para maiúsculas; o que importa
            # é a classificação (herdado × manual) sobreviver aos ciclos de save.
            self.assertEqual(
                (por_corrida['3242']['origem_status_tecnico'] or '').lower(),
                'dados_tecnicos_herdados_cf',
            )
            self.assertEqual(
                (por_corrida['AB337']['origem_status_tecnico'] or '').lower(),
                'dados_tecnicos_manuais_pendentes',
            )
            # Origem documental estável nas duas corridas do grupo.
            for corrida in ('3242', 'AB337'):
                self.assertEqual(por_corrida[corrida]['certificado_fornecedor_origem_id'], self.cf.id)
                self.assertEqual(por_corrida[corrida]['item_certificado_fornecedor_origem_id'], self.item_cf.id)
            # Item não relacionado preservado, sem herdar origem do grupo.
            self.assertIsNone(por_corrida['ZZ999']['item_certificado_fornecedor_origem_id'])
            self.assertEqual(por_corrida['ZZ999']['composicao_json'], {'Fe': '99'})

        recarregado = _reload()
        _verificar(recarregado)

        # Reaplicar/salvar de novo: mesmo conjunto de itens (com ids do servidor),
        # equivalente a reabrir o modal e aplicar sem mudanças. Não pode duplicar.
        r2 = self.client_api.patch(
            reverse('certificado-qualidade-detail', args=[cq_id]),
            {'itens': recarregado['itens']},
            format='json',
        )
        self.assertEqual(r2.status_code, 200, r2.content)
        _verificar(_reload())

    def test_nenhum_estoque_alterado(self):
        antes = EstoqueCorrida.objects.count()
        self.client_api.get(
            self.url,
            {'certificado_fornecedor_id': self.cf.id, 'item_certificado_fornecedor_id': self.item_cf.id},
        )
        r = self.client_api.post(
            reverse('certificado-qualidade-list'),
            self._payload_cq_duas_corridas(),
            format='json',
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(EstoqueCorrida.objects.count(), antes)


class PdfDuasCorridasRegressaoTests(CorridasCfParaCqBase):
    def _criar_cq_duas_corridas(self, composicao_ab337: dict) -> CertificadoQualidade:
        cliente = Cliente.objects.create(razao_social='Cliente PDF', cnpj=_cnpj())
        cq = CertificadoQualidade.objects.create(
            numero=f'CQ-{uuid.uuid4().hex[:8].upper()}',
            cliente=cliente,
            cliente_nome_snapshot=cliente.razao_social,
            status=CertificadoQualidade.Status.EMITIDO,
        )
        ItemCertificadoQualidade.objects.create(
            certificado=cq,
            ordem=1,
            produto=self.prod,
            codigo_produto=self.prod.codigo_completo,
            descricao_material=self.prod.descricao,
            quantidade=Decimal('8'),
            unidade='PC',
            norma='ASTM A105',
            corrida='3242',
            composicao_json={'C': '0.20', 'Mn': '0.90'},
            ensaio_tracao_json={'limite_escoamento': '250'},
        )
        ItemCertificadoQualidade.objects.create(
            certificado=cq,
            ordem=2,
            produto=self.prod,
            codigo_produto=self.prod.codigo_completo,
            descricao_material=self.prod.descricao,
            quantidade=Decimal('6'),
            unidade='PC',
            norma='ASTM A350 LF2',
            corrida='AB337',
            composicao_json=composicao_ab337,
            ensaio_tracao_json={},
        )
        return cq

    def _texto_pdf(self, cq: CertificadoQualidade) -> str:
        pdf = gerar_certificado_qualidade_pdf(cq, preview=False)
        self.assertTrue(pdf.startswith(b'%PDF'))
        reader = PdfReader(io.BytesIO(pdf))
        return ''.join(page.extract_text() or '' for page in reader.pages)

    def test_pdf_mostra_duas_corridas_quantidades_e_dados_separados(self):
        cq = self._criar_cq_duas_corridas(composicao_ab337={'C': '0.35', 'Cr': '1.10'})
        texto = self._texto_pdf(cq)
        self.assertIn('3242', texto)
        self.assertIn('AB337', texto)
        self.assertIn('8', texto)
        self.assertIn('6', texto)
        # Dados técnicos não são concatenados: valores distintos de C aparecem separados.
        self.assertIn('0.20', texto)
        self.assertIn('0.35', texto)
        self.assertIn('ASTM A105', texto)
        self.assertIn('ASTM A350 LF2', texto)

    def test_pdf_dados_iguais_ainda_gera_um_bloco_por_item(self):
        cq = self._criar_cq_duas_corridas(composicao_ab337={'C': '0.20', 'Mn': '0.90'})
        texto = self._texto_pdf(cq)
        self.assertIn('3242', texto)
        self.assertIn('AB337', texto)

    def test_cq_antigo_um_item_continua_gerando_pdf(self):
        cliente = Cliente.objects.create(razao_social='Cliente Antigo', cnpj=_cnpj())
        cq = CertificadoQualidade.objects.create(
            numero=f'CQ-{uuid.uuid4().hex[:8].upper()}',
            cliente=cliente,
            cliente_nome_snapshot=cliente.razao_social,
            status=CertificadoQualidade.Status.EMITIDO,
        )
        ItemCertificadoQualidade.objects.create(
            certificado=cq,
            ordem=1,
            codigo_produto='COD-ANTIGO',
            descricao_material='Item antigo',
            quantidade=Decimal('1'),
            unidade='PC',
            norma='DIN',
            corrida='R1',
            composicao_json={'Fe': '99'},
        )
        pdf = gerar_certificado_qualidade_pdf(cq, preview=False)
        self.assertTrue(pdf.startswith(b'%PDF'))
