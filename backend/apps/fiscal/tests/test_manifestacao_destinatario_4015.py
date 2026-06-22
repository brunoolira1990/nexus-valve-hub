"""ERP 4.0.15 — Manifestação do Destinatário / Monitor NF-e Destinada."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.cadastros.models import Empresa
from apps.fiscal.dfe_recebidos.distribuicao_dfe_parser import DocumentoDistribuicao, ResultadoDistribuicaoDfe
from apps.fiscal.manifestacao_destinatario.constants import (
    EVENTO_CIENCIA,
    EVENTO_NAO_REALIZADA,
)
from apps.fiscal.manifestacao_destinatario.resnfe_parser import parse_resnfe_xml
from apps.fiscal.manifestacao_destinatario.uf_chave import uf_autorizadora_por_chave
from apps.fiscal.models import NFeDestinadaManifestacao, NFeDestinadaManifestacaoEvento


RESNFE_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<resNFe xmlns="http://www.portalfiscal.inf.br/nfe" versao="1.01">
  <chNFe>35260622222222222222550010000001234567890123</chNFe>
  <CNPJ>22222222000122</CNPJ>
  <xNome>Fornecedor Manifest Teste</xNome>
  <IE>123456789</IE>
  <dhEmi>2026-06-10T10:00:00-03:00</dhEmi>
  <vNF>1500.00</vNF>
  <tpAmb>1</tpAmb>
</resNFe>"""


class ManifestacaoDestinatarioTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user('manifest_user', password='test')
        Group.objects.get_or_create(name='fiscal')
        self.user.groups.add(Group.objects.get(name='fiscal'))
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.emp = Empresa.objects.create(
            razao_social='Empresa Manifest',
            cnpj='11.111.111/0001-11',
            uf='SP',
        )
        self.base = '/api/fiscal/manifestacao-destinatario/'
        self.dh = timezone.make_aware(datetime(2026, 6, 10, 10, 0, 0))

    def _doc(self, **kwargs) -> NFeDestinadaManifestacao:
        defaults = {
            'empresa': self.emp,
            'chave_acesso': '35260622222222222222550010000001234567890123',
            'cnpj_destinatario': '11111111000111',
            'cnpj_emitente': '22222222000122',
            'razao_social_emitente': 'Fornecedor Manifest Teste',
            'dh_emissao': self.dh,
            'valor_nf': Decimal('1500.00'),
            'ambiente': NFeDestinadaManifestacao.Ambiente.PRODUCAO,
            'status_manifestacao': NFeDestinadaManifestacao.StatusManifestacao.PENDENTE,
            'status_xml': NFeDestinadaManifestacao.StatusXml.RESUMO,
        }
        defaults.update(kwargs)
        return NFeDestinadaManifestacao.objects.create(**defaults)

    def test_parse_resnfe(self):
        parsed = parse_resnfe_xml(RESNFE_XML)
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(len(parsed.chave_acesso), 44)
        self.assertEqual(parsed.tp_amb, '1')

    def test_uf_autorizadora_por_chave(self):
        self.assertEqual(
            uf_autorizadora_por_chave('35260622222222222222550010000001234567890123'),
            'SP',
        )
        self.assertEqual(
            uf_autorizadora_por_chave('31260622222222222222550010000001234567890123'),
            'MG',
        )

    @patch('apps.fiscal.manifestacao_destinatario.manifestacao_service._montar_assinar_evento_manifestacao')
    @patch('apps.fiscal.manifestacao_destinatario.manifestacao_service.transmitir_evento_nfe')
    @patch('apps.fiscal.manifestacao_destinatario.manifestacao_service.carregar_certificado_empresa')
    @patch('apps.fiscal.manifestacao_destinatario.manifestacao_service.criar_comunicacao_sefaz')
    def test_manifestacao_usa_uf_da_chave_nao_da_empresa(self, mock_comm, mock_cert, mock_tx, mock_assinar):
        from apps.fiscal.nfe_integracao.adapters.certificado_a1 import CertificadoA1Info

        mock_cert.return_value = CertificadoA1Info(
            valido=True,
            caminho='/tmp/fake.pfx',
            senha_configurada=True,
            cnpj='11111111000111',
        )
        mock_assinar.return_value = b'<evento/>'
        mock_tx.return_value = (
            b'<retEvento><infEvento><cStat>135</cStat>'
            b'<xMotivo>Evento registrado</xMotivo><nProt>123</nProt></infEvento></retEvento>'
        )

        doc = self._doc(
            chave_acesso='31260622222222222222550010000001234567890123',
        )
        resp = self.client.post(
            f'{self.base}{doc.pk}/manifestar/',
            {'evento': EVENTO_CIENCIA, 'confirmacao_explicita': True},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        mock_assinar.assert_called_once()
        self.assertEqual(mock_assinar.call_args.kwargs['uf'], 'MG')
        mock_comm.assert_called_once()
        self.assertEqual(mock_comm.call_args.args[0], 'MG')

    def test_listagem_sem_xml_completo(self):
        doc = self._doc()
        resp = self.client.get(self.base, {'empresa_id': self.emp.pk})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        row = resp.data['results'][0]
        self.assertEqual(row['id'], doc.pk)
        self.assertNotIn('resumo_json', row)

    def test_detalhe_com_historico(self):
        doc = self._doc()
        NFeDestinadaManifestacaoEvento.objects.create(
            documento=doc,
            empresa=self.emp,
            tipo_acao=NFeDestinadaManifestacaoEvento.TipoAcao.CONSULTA,
            descricao='Consulta teste',
            ambiente='1',
        )
        resp = self.client.get(f'{self.base}{doc.pk}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data['eventos']), 1)

    @patch('apps.fiscal.manifestacao_destinatario.manifestacao_service._montar_assinar_evento_manifestacao')
    @patch('apps.fiscal.manifestacao_destinatario.manifestacao_service.transmitir_evento_nfe')
    @patch('apps.fiscal.manifestacao_destinatario.manifestacao_service.carregar_certificado_empresa')
    @patch('apps.fiscal.manifestacao_destinatario.manifestacao_service.criar_comunicacao_sefaz')
    def test_manifestacao_manual_ciencia(self, _comm, mock_cert, mock_tx, mock_assinar):
        from apps.fiscal.nfe_integracao.adapters.certificado_a1 import CertificadoA1Info

        mock_cert.return_value = CertificadoA1Info(
            valido=True,
            caminho='/tmp/fake.pfx',
            senha_configurada=True,
            cnpj='11111111000111',
        )
        mock_assinar.return_value = b'<evento/>'
        mock_tx.return_value = (
            b'<retEnvEvento xmlns="http://www.portalfiscal.inf.br/nfe" versao="1.00">'
            b'<cStat>128</cStat><xMotivo>Lote de evento processado</xMotivo>'
            b'<retEvento versao="1.00"><infEvento>'
            b'<cStat>135</cStat><xMotivo>Evento registrado e vinculado a NF-e</xMotivo>'
            b'<nProt>123</nProt><tpEvento>210210</tpEvento>'
            b'</infEvento></retEvento></retEnvEvento>'
        )

        doc = self._doc()
        resp = self.client.post(
            f'{self.base}{doc.pk}/manifestar/',
            {'evento': EVENTO_CIENCIA, 'confirmacao_explicita': True},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        doc.refresh_from_db()
        self.assertEqual(doc.status_manifestacao, NFeDestinadaManifestacao.StatusManifestacao.CIENTE)
        self.assertEqual(doc.eventos.filter(tipo_acao='MANIFESTACAO').count(), 1)

    @patch('apps.fiscal.manifestacao_destinatario.manifestacao_service._montar_assinar_evento_manifestacao')
    @patch('apps.fiscal.manifestacao_destinatario.manifestacao_service.transmitir_evento_nfe')
    @patch('apps.fiscal.manifestacao_destinatario.manifestacao_service.carregar_certificado_empresa')
    @patch('apps.fiscal.manifestacao_destinatario.manifestacao_service.criar_comunicacao_sefaz')
    def test_manifestacao_lote_128_sem_evento_nao_atualiza_status(self, _comm, mock_cert, mock_tx, mock_assinar):
        from apps.fiscal.nfe_integracao.adapters.certificado_a1 import CertificadoA1Info

        mock_cert.return_value = CertificadoA1Info(
            valido=True,
            caminho='/tmp/fake.pfx',
            senha_configurada=True,
            cnpj='11111111000111',
        )
        mock_assinar.return_value = b'<evento/>'
        mock_tx.return_value = (
            b'<retEnvEvento xmlns="http://www.portalfiscal.inf.br/nfe" versao="1.00">'
            b'<cStat>128</cStat><xMotivo>Lote de evento processado</xMotivo>'
            b'</retEnvEvento>'
        )

        doc = self._doc()
        resp = self.client.post(
            f'{self.base}{doc.pk}/manifestar/',
            {'evento': EVENTO_CIENCIA, 'confirmacao_explicita': True},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT, resp.content)
        doc.refresh_from_db()
        self.assertEqual(doc.status_manifestacao, NFeDestinadaManifestacao.StatusManifestacao.ERRO)
        self.assertEqual(doc.eventos.filter(tipo_acao='MANIFESTACAO').count(), 1)

    @patch('apps.fiscal.manifestacao_destinatario.manifestacao_service._montar_assinar_evento_manifestacao')
    @patch('apps.fiscal.manifestacao_destinatario.manifestacao_service.transmitir_evento_nfe')
    @patch('apps.fiscal.manifestacao_destinatario.manifestacao_service.carregar_certificado_empresa')
    @patch('apps.fiscal.manifestacao_destinatario.manifestacao_service.criar_comunicacao_sefaz')
    def test_manifestacao_manual_ciencia_ret_evento_simples(self, _comm, mock_cert, mock_tx, mock_assinar):
        from apps.fiscal.nfe_integracao.adapters.certificado_a1 import CertificadoA1Info

        mock_cert.return_value = CertificadoA1Info(
            valido=True,
            caminho='/tmp/fake.pfx',
            senha_configurada=True,
            cnpj='11111111000111',
        )
        mock_assinar.return_value = b'<evento/>'
        mock_tx.return_value = (
            b'<retEvento><infEvento><cStat>135</cStat>'
            b'<xMotivo>Evento registrado</xMotivo><nProt>123</nProt></infEvento></retEvento>'
        )

        doc = self._doc()
        resp = self.client.post(
            f'{self.base}{doc.pk}/manifestar/',
            {'evento': EVENTO_CIENCIA, 'confirmacao_explicita': True},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        doc.refresh_from_db()
        self.assertEqual(doc.status_manifestacao, NFeDestinadaManifestacao.StatusManifestacao.CIENTE)

    def test_manifestacao_exige_confirmacao(self):
        doc = self._doc()
        resp = self.client.post(
            f'{self.base}{doc.pk}/manifestar/',
            {'evento': EVENTO_CIENCIA, 'confirmacao_explicita': False},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_manifestacao_nao_realizada_exige_justificativa(self):
        doc = self._doc()
        resp = self.client.post(
            f'{self.base}{doc.pk}/manifestar/',
            {
                'evento': EVENTO_NAO_REALIZADA,
                'confirmacao_explicita': True,
                'justificativa': 'curta',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('apps.fiscal.manifestacao_destinatario.baixar_xml_service.importar_arquivos_entrada')
    @patch('apps.fiscal.manifestacao_destinatario.baixar_xml_service.carregar_certificado_empresa')
    @patch('apps.fiscal.manifestacao_destinatario.baixar_xml_service.criar_comunicacao_sefaz')
    def test_baixar_xml_nao_gera_financeiro(self, _comm, mock_cert, mock_import):
        from apps.fiscal.nfe_integracao.adapters.certificado_a1 import CertificadoA1Info

        mock_cert.return_value = CertificadoA1Info(
            valido=True,
            caminho='/tmp/fake.pfx',
            senha_configurada=True,
            cnpj='11111111000111',
        )
        mock_import.return_value = {'importadas': [{'id': 99}], 'duplicadas': [], 'erros': []}
        parsed = ResultadoDistribuicaoDfe(
            sucesso_parse=True,
            cstat='138',
            documentos=[
                DocumentoDistribuicao(
                    nsu='1',
                    schema='procNFe',
                    conteudo_xml=b'<nfeProc/>',
                    tipo='NFE',
                ),
            ],
        )
        doc = self._doc(status_xml=NFeDestinadaManifestacao.StatusXml.DISPONIVEL)
        with patch(
            'apps.fiscal.manifestacao_destinatario.baixar_xml_service.parse_distribuicao_dfe_response',
            return_value=parsed,
        ), patch(
            'apps.fiscal.manifestacao_destinatario.baixar_xml_service._validar_destinatario_xml',
        ):
            resp = self.client.post(
                f'{self.base}{doc.pk}/baixar-xml/',
                {'confirmacao_explicita': True},
                format='json',
            )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        from apps.financeiro.models import ContaPagar, ContaReceber
        from apps.expedicao.models import Expedicao

        self.assertEqual(ContaPagar.objects.count(), 0)
        self.assertEqual(ContaReceber.objects.count(), 0)
        self.assertEqual(Expedicao.objects.count(), 0)

    def test_fechamento_preview(self):
        self._doc()
        self._doc(
            chave_acesso='35260622222222222222550010000001234567890124',
            status_manifestacao=NFeDestinadaManifestacao.StatusManifestacao.CIENTE,
            status_xml=NFeDestinadaManifestacao.StatusXml.BAIXADO,
        )
        resp = self.client.get(
            f'{self.base}fechamento-preview/',
            {
                'empresa_id': self.emp.pk,
                'data_inicio': '2026-06-01',
                'data_fim': '2026-06-30',
            },
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['total_documentos'], 2)

    def test_sem_permissao_fiscal(self):
        User = get_user_model()
        user = User.objects.create_user('sem_fiscal', password='x')
        client = APIClient()
        client.force_authenticate(user)
        resp = client.post(f'{self.base}consultar/', {'empresa_id': self.emp.pk}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
