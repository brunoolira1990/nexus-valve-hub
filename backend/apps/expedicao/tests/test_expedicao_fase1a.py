"""Expedição/Logística Fase 1A — CRUD manual sem efeitos colaterais."""

from __future__ import annotations

import uuid
from datetime import date
from io import BytesIO

from django.contrib.auth import get_user_model
from django.test import TestCase
from reportlab.graphics.barcode import code128
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from pypdf import PdfReader
from rest_framework import status
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Empresa, Fornecedor
from apps.expedicao.etiquetas import _quebrar_texto, _texto_na_largura
from apps.expedicao.models import Expedicao, StatusExpedicao, TipoOperacaoExpedicao
from apps.fiscal.models import AtendimentoEstoque, EstoqueCorrida, NFeSaida


def _cnpj() -> str:
    h = uuid.uuid4().hex[:12]
    return f'{int(h[:2], 16) % 90 + 10:02d}.{int(h[2:5], 16) % 900 + 100:03d}.{int(h[5:8], 16) % 900 + 100:03d}/0001-{int(h[8:10], 16) % 97:02d}'


class ExpedicaoFase1aTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('exp_user', 'exp@test.com', 'secret')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.cliente = Cliente.objects.create(razao_social='CLIENTE EXP TEST', cnpj=_cnpj())
        self.fornecedor = Fornecedor.objects.create(razao_social='FORN EXP TEST', cnpj=_cnpj())

    def _payload(self, **extra):
        base = {
            'tipo_operacao': TipoOperacaoExpedicao.RETIRADA_FORNECEDOR,
            'status': StatusExpedicao.RASCUNHO,
            'cliente': self.cliente.pk,
            'fornecedor': self.fornecedor.pk,
            'motorista_nome': 'João Motorista',
            'placa_veiculo': 'ABC1D23',
            'volumes': 2,
            'data_prevista_retirada': '2026-06-20',
            'data_prevista_entrega': '2026-06-22',
            'observacoes': 'Teste expedição',
        }
        base.update(extra)
        return base

    def test_criar_expedicao(self):
        r = self.client.post('/api/expedicoes/', self._payload(), format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        data = r.json()
        self.assertTrue(str(data['codigo']).startswith('EXP-'))
        self.assertEqual(data['status'], StatusExpedicao.RASCUNHO)

    def test_listar_com_filtro_status(self):
        self.client.post('/api/expedicoes/', self._payload(), format='json')
        r = self.client.get('/api/expedicoes/', {'status': StatusExpedicao.RASCUNHO})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(r.json()['count'], 1)
        self.assertIn('resumo', r.json())

    def test_editar_expedicao(self):
        cri = self.client.post('/api/expedicoes/', self._payload(), format='json').json()
        r = self.client.patch(
            f"/api/expedicoes/{cri['id']}/",
            {'motorista_nome': 'Maria Motorista', 'volumes': 3},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.json()['motorista_nome'], 'Maria Motorista')
        self.assertEqual(r.json()['volumes'], 3)

    def test_alterar_status(self):
        cri = self.client.post('/api/expedicoes/', self._payload(), format='json').json()
        r = self.client.post(
            f"/api/expedicoes/{cri['id']}/alterar-status/",
            {'status': StatusExpedicao.MOTORISTA_ENVIADO},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.json()['status'], StatusExpedicao.MOTORISTA_ENVIADO)

    def test_cancelar_expedicao(self):
        cri = self.client.post('/api/expedicoes/', self._payload(), format='json').json()
        r = self.client.post(
            f"/api/expedicoes/{cri['id']}/cancelar/",
            {'motivo': 'Cliente desistiu'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.json()['status'], StatusExpedicao.CANCELADO)

    def test_requer_autenticacao(self):
        anon = APIClient()
        r = anon.get('/api/expedicoes/')
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_nao_gera_financeiro(self):
        from apps.financeiro.models import TituloFinanceiro

        antes = TituloFinanceiro.objects.count()
        self.client.post('/api/expedicoes/', self._payload(), format='json')
        self.assertEqual(TituloFinanceiro.objects.count(), antes)

    def test_nao_movimenta_estoque(self):
        antes = EstoqueCorrida.objects.count()
        antes_ae = AtendimentoEstoque.objects.count()
        cri = self.client.post('/api/expedicoes/', self._payload(), format='json').json()
        self.client.post(
            f"/api/expedicoes/{cri['id']}/alterar-status/",
            {'status': StatusExpedicao.ENTREGUE_CLIENTE},
            format='json',
        )
        self.assertEqual(EstoqueCorrida.objects.count(), antes)
        self.assertEqual(AtendimentoEstoque.objects.count(), antes_ae)

    def test_nao_altera_nfe(self):
        nf = NFeSaida.objects.create(
            numero='999001',
            data=date(2026, 6, 1),
            cliente=self.cliente,
            status='AUTORIZADA',
        )
        status_antes = nf.status
        chave_antes = nf.chave_acesso
        cri = self.client.post(
            '/api/expedicoes/',
            self._payload(nfe_saida=nf.pk),
            format='json',
        ).json()
        self.assertEqual(cri['nfe_saida'], nf.pk)
        nf.refresh_from_db()
        self.assertEqual(nf.status, status_antes)
        self.assertEqual(nf.chave_acesso, chave_antes)
        self.assertEqual(Expedicao.objects.filter(nfe_saida=nf).count(), 1)

    def test_etiquetas_pdf_nfe_autorizada_sem_alterar_nfe(self):
        numeracao_antes = '07140012'
        empresa = Empresa.objects.create(
            razao_social='NEXUS VALVULAS E CONEXOES INDUSTRIAIS LTDA',
            nome_fantasia='NEXUS VALVULAS',
            cnpj=_cnpj(),
            telefone='(11) 4000-0000',
            email='contato@nexusvalvulas.com.br',
            site='www.nexusvalvulas.com.br',
        )
        nf = NFeSaida.objects.create(
            numero='410',
            data=date(2026, 8, 18),
            cliente=self.cliente,
            status='AUTORIZADA',
            status_emissao_sefaz=NFeSaida.StatusEmissaoSefaz.AUTORIZADA_PRODUCAO,
            empresa_emitente=empresa,
            quantidade_volumes=1,
            numeracao_volumes=numeracao_antes,
        )
        resposta = self.client.post(
            '/api/expedicoes/',
            self._payload(fornecedor=None, nfe_saida=nf.pk, volumes=1),
            format='json',
        )
        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED)
        dados_expedicao = resposta.json()
        expedicao_id = dados_expedicao['id']
        codigo_expedicao = dados_expedicao['codigo']

        pdf_resposta = self.client.post(f'/api/expedicoes/{expedicao_id}/etiquetas-pdf/')
        self.assertEqual(pdf_resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(pdf_resposta['Content-Type'], 'application/pdf')
        self.assertTrue(pdf_resposta.content.startswith(b'%PDF'))
        texto_pdf = '\\n'.join(
            pagina.extract_text() or ''
            for pagina in PdfReader(BytesIO(pdf_resposta.content)).pages
        )
        self.assertIn('Numeração', texto_pdf)
        self.assertIn('Tel.', texto_pdf)
        self.assertIn('4000-0000', texto_pdf)
        self.assertIn('E-mail contato@nexusvalvulas.com.br', texto_pdf)
        self.assertIn('Site www.nexusvalvulas.com.br', texto_pdf)
        self.assertNotIn('Vol. NF-e', texto_pdf)
        self.assertIn(numeracao_antes, texto_pdf)
        self.assertNotIn(codigo_expedicao, texto_pdf)

        nf.refresh_from_db()
        self.assertEqual(nf.numeracao_volumes, numeracao_antes)

    def test_numeracao_gerada_na_expedicao_vai_para_nfe_rascunho(self):
        empresa = Empresa.objects.create(
            razao_social='NEXUS VALVULAS E CONEXOES INDUSTRIAIS LTDA',
            nome_fantasia='NEXUS VALVULAS',
            cnpj=_cnpj(),
            telefone='(11) 4000-0000',
            email='contato@nexusvalvulas.com.br',
            site='www.nexusvalvulas.com.br',
        )
        nf = NFeSaida.objects.create(
            numero='411',
            data=date(2026, 8, 18),
            cliente=self.cliente,
            status='RASCUNHO',
            empresa_emitente=empresa,
            quantidade_volumes=1,
        )
        resposta = self.client.post(
            '/api/expedicoes/',
            self._payload(fornecedor=None, nfe_saida=nf.pk, volumes=1),
            format='json',
        )
        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED)
        codigo_expedicao = resposta.json()['codigo']
        nf.refresh_from_db()
        self.assertEqual(nf.numeracao_volumes, codigo_expedicao)

    def test_etiquetas_contem_textos_longos_na_largura_util(self):
        fonte_valor = 'Helvetica'
        tamanho_valor = 7.6
        largura_valor = 62 * mm - 29 * mm - 5 * mm
        valor = _texto_na_largura(
            'PETROBRAS TRANSPORTES E LOGISTICA INDUSTRIAL S.A.',
            fonte_valor,
            tamanho_valor,
            largura_valor,
        )
        self.assertLessEqual(stringWidth(valor, fonte_valor, tamanho_valor), largura_valor)

        barcode = code128.Code128(
            'EXP-20260818-0001',
            barHeight=8 * mm,
            barWidth=0.25 * mm,
            quiet=False,
            humanReadable=False,
        )
        self.assertLessEqual(barcode.width, 52 * mm)

        fonte_cabecalho = 'Helvetica-Bold'
        tamanho_cabecalho = 5.3
        largura_cabecalho = 62 * mm - 28 * mm
        linhas = _quebrar_texto(
            'NEXUS VALVULAS E CONEXOES INDUSTRIAIS LTDA',
            fonte_cabecalho,
            tamanho_cabecalho,
            largura_cabecalho,
            max_linhas=2,
        )
        self.assertLessEqual(len(linhas), 2)
        for linha in linhas:
            self.assertLessEqual(
                stringWidth(linha, fonte_cabecalho, tamanho_cabecalho),
                largura_cabecalho,
            )

    def test_resumo_endpoint(self):
        self.client.post('/api/expedicoes/', self._payload(), format='json')
        r = self.client.get('/api/expedicoes/resumo/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn('total', r.json())
        self.assertIn('aguardando_separacao', r.json())
