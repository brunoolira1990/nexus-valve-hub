"""Regressão — erro técnico PyNFe (3 valores), retry idempotente e listagem."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from lxml import etree
from rest_framework.test import APIClient

from apps.fiscal.models import NFeNumeracaoConfiguracao, NFeSaida
from apps.fiscal.nfe_emissao.numeracao import reservar_numeracao_nfe
from apps.fiscal.nfe_emissao.pynfe_retorno import desempacotar_retorno_autorizacao_pynfe
from apps.fiscal.nfe_emissao.retorno_sefaz import resultado_autorizacao_mock
from apps.fiscal.nfe_emissao.resposta import montar_resposta_emissao_homologacao
from apps.fiscal.nfe_emissao.servico import emitir_nfe_homologacao
from apps.fiscal.nfe_emissao.transmissao import transmitir_nfe_homologacao
from apps.fiscal.serializers import NFeSaidaSerializer
from apps.fiscal.tests.test_nfe_saida_402_emissao_homologacao import (
    XML_AUTORIZADO_MOCK,
    _pedido_nf,
    _preparar_pronta,
)


class NFe402ErroTransmissaoTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('nfe402err', 'err@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.pedido, self.item, self.nf = _pedido_nf()
        self.empresa = self.pedido.empresa_emitente
        self.nf = _preparar_pronta(self.nf, self.user)

    def test_pynfe_retorno_tres_valores_nao_quebra_unpack(self):
        parsed = desempacotar_retorno_autorizacao_pynfe((1, MagicMock(text='<cStat>225</cStat>'), MagicMock()))
        self.assertEqual(parsed.codigo, 1)
        self.assertIsNotNone(parsed.resultado)
        self.assertIsNotNone(parsed.nota_enviada)

    @patch('apps.fiscal.nfe_emissao.transmissao.criar_comunicacao_sefaz')
    def test_transmissao_pynfe_erro_tres_valores(self, mock_criar):
        reservar_numeracao_nfe(self.nf, usuario=self.user)
        self.nf.refresh_from_db()
        mock_com = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = '<retEnviNFe><cStat>225</cStat><xMotivo>Rejeicao teste</xMotivo></retEnviNFe>'
        nfe_el = etree.Element('{http://www.portalfiscal.inf.br/nfe}NFe')
        mock_com.autorizacao.return_value = (1, mock_resp, nfe_el)
        mock_criar.return_value = mock_com
        resultado = transmitir_nfe_homologacao(
            self.nf,
            b'<NFe xmlns="http://www.portalfiscal.inf.br/nfe"/>',
            self.empresa,
        )
        self.assertFalse(resultado.autorizado)
        self.assertEqual(resultado.lote.c_stat, '225')

    @patch('apps.fiscal.nfe_emissao.servico.validar_emissao_completa', return_value={'ok': True, 'erros': []})
    @patch('apps.fiscal.nfe_emissao.servico.transmitir_nfe_homologacao')
    @patch('apps.fiscal.nfe_emissao.servico.assinar_xml_nfe')
    def test_erro_tecnico_salva_status_e_json(self, mock_assinar, mock_tx, _mock_xsd):
        from apps.fiscal.nfe_emissao.transmissao import NFeTransmissaoError

        from apps.fiscal.nfe_emissao.servico import NFeEmissaoHomologacaoError

        mock_assinar.side_effect = lambda xml, emp, **kw: xml if isinstance(xml, bytes) else xml.encode()
        reservar_numeracao_nfe(self.nf, usuario=self.user)
        self.nf.refresh_from_db()
        numero = self.nf.numero_nfe
        mock_tx.side_effect = NFeTransmissaoError('too many values to unpack (expected 2)', etapa='TRANSMISSAO_SEFAZ')

        with self.assertRaises(NFeEmissaoHomologacaoError):
            emitir_nfe_homologacao(self.nf, usuario=self.user)

        self.nf.refresh_from_db()
        self.assertEqual(self.nf.status_emissao_sefaz, NFeSaida.StatusEmissaoSefaz.ERRO_TRANSMISSAO)
        self.assertEqual(self.nf.numero_nfe, numero)
        self.assertFalse(self.nf.protocolo_autorizacao)
        self.assertNotEqual(self.nf.status, 'AUTORIZADA_HOMOLOGACAO')

        url = f'/api/nf-saidas/{self.nf.pk}/emitir-homologacao/'
        mock_tx.side_effect = NFeTransmissaoError('too many values to unpack (expected 2)', etapa='TRANSMISSAO_SEFAZ')
        res = self.client.post(url, {}, format='json')
        self.assertIn(res.status_code, (400, 422))
        body = res.json()
        self.assertFalse(body['ok'])
        self.assertEqual(body['status'], 'ERRO_TRANSMISSAO')
        self.assertEqual(body['numero_nfe'], numero)
        self.assertIn('too many values', ' '.join(body.get('erros') or []))
        self.assertEqual(body.get('etapa'), 'TRANSMISSAO_SEFAZ')

    @patch('apps.fiscal.nfe_emissao.servico.validar_emissao_completa', return_value={'ok': True, 'erros': []})
    @patch('apps.fiscal.nfe_emissao.servico.transmitir_nfe_homologacao')
    @patch('apps.fiscal.nfe_emissao.servico.assinar_xml_nfe')
    def test_retry_reutiliza_numero_sem_incrementar(self, mock_assinar, mock_tx, _mock_xsd):
        from apps.fiscal.nfe_emissao.retorno_sefaz import ResultadoAutorizacaoSefaz
        from apps.fiscal.nfe_emissao.servico import NFeEmissaoHomologacaoError
        from apps.fiscal.nfe_emissao.transmissao import NFeTransmissaoError

        mock_assinar.side_effect = lambda xml, emp, **kw: xml if isinstance(xml, bytes) else xml.encode()
        hom = NFeNumeracaoConfiguracao.objects.get(
            empresa=self.empresa,
            ambiente='homologacao',
            serie='0',
        )
        proximo_antes = hom.proximo_numero

        mock_tx.side_effect = NFeTransmissaoError('falha rede', etapa='TRANSMISSAO_SEFAZ')
        with self.assertRaises(NFeEmissaoHomologacaoError):
            emitir_nfe_homologacao(self.nf, usuario=self.user)
        self.nf.refresh_from_db()
        numero1 = self.nf.numero_nfe
        hom.refresh_from_db()
        proximo_apos_primeira = hom.proximo_numero
        self.assertGreater(proximo_apos_primeira, proximo_antes)

        mock_tx.side_effect = None
        mock_tx.return_value = resultado_autorizacao_mock(
            autorizado=True,
            c_stat='100',
            x_motivo='OK',
            protocolo='135260000000001',
            xml_retorno=XML_AUTORIZADO_MOCK,
            xml_autorizado=XML_AUTORIZADO_MOCK,
        )
        emitir_nfe_homologacao(self.nf, usuario=self.user)
        self.nf.refresh_from_db()
        hom.refresh_from_db()
        self.assertEqual(self.nf.numero_nfe, numero1)
        self.assertEqual(hom.proximo_numero, proximo_apos_primeira)

    def test_listagem_nf_erro_transmissao_200(self):
        self.nf.status_emissao_sefaz = NFeSaida.StatusEmissaoSefaz.ERRO_TRANSMISSAO
        self.nf.serie_nfe = '900'
        self.nf.numero_nfe = '000000002'
        self.nf.chave_acesso = '35260503999102000150559000000000212323217760'
        self.nf.motivo_autorizacao = 'Falha na transmissão: too many values to unpack (expected 2)'
        self.nf.ambiente_emissao = 'homologacao'
        self.nf.save()

        res = self.client.get('/api/nf-saidas/')
        self.assertEqual(res.status_code, 200)
        payload = res.json()
        rows = payload if isinstance(payload, list) else payload.get('results', payload)
        row = next(r for r in rows if r['id'] == self.nf.pk)
        resumo = row.get('resumo_emissao_sefaz') or {}
        self.assertEqual(resumo.get('status_emissao_sefaz'), 'ERRO_TRANSMISSAO')
        self.assertEqual(resumo.get('serie_nfe'), '900')
        self.assertNotIn('xml_retorno', row)
        self.assertNotIn('xml_autorizado', row)

    def test_resposta_padronizada_erro_tecnico(self):
        self.nf.status_emissao_sefaz = NFeSaida.StatusEmissaoSefaz.ERRO_TRANSMISSAO
        res = montar_resposta_emissao_homologacao(
            self.nf,
            ok=False,
            mensagem='Falha técnica ao transmitir NF-e em homologação.',
            erros=['too many values to unpack (expected 2)'],
            etapa='TRANSMISSAO_SEFAZ',
        )
        self.assertFalse(res['ok'])
        self.assertEqual(res['etapa'], 'TRANSMISSAO_SEFAZ')
        self.assertEqual(res['ambiente'], 'homologacao')

    def test_serializer_lista_resumo_sem_xml(self):
        self.nf.status_emissao_sefaz = NFeSaida.StatusEmissaoSefaz.ERRO_TRANSMISSAO
        self.nf.serie_nfe = '900'
        self.nf.numero_nfe = '000000002'
        self.nf.chave_acesso = '35260503999102000150559000000212323217760'
        self.nf.xml_retorno = '<xml>...</xml>' * 100
        self.nf.save()
        data = NFeSaidaSerializer(self.nf).data
        self.assertIn('resumo_emissao_sefaz', data)
        self.assertNotIn('xml_retorno', data)
