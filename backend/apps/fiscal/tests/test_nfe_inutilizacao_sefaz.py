"""NF-e — Inutilização SEFAZ homologação/produção (mock, sem SEFAZ real)."""

from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.fiscal.models import NFeInutilizacaoSefaz, NFeNumeracaoConfiguracao, NFeSaida, NFeSaidaEvento
from apps.fiscal.nfe_emissao.inutilizacao_sefaz import (
    NFeInutilizacaoError,
    emitir_inutilizacao_nfe_saida,
    pode_inutilizar_faixa_numeracao,
    pode_inutilizar_numero_nfe,
    validar_justificativa_inutilizacao,
)
from apps.fiscal.tests.test_nfe_saida_402_emissao_homologacao import _ensure_numeracao_empresa, _pedido_nf


class MagicMockInutResponse:
    text = """<?xml version="1.0"?>
<retInutNFe xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">
  <infInut>
    <tpAmb>2</tpAmb>
    <cStat>102</cStat>
    <xMotivo>Inutilizacao de numero homologado</xMotivo>
    <cUF>35</cUF>
    <ano>26</ano>
    <CNPJ>03999102000150</CNPJ>
    <mod>55</mod>
    <serie>0</serie>
    <nNFIni>88</nNFIni>
    <nNFFin>88</nNFFin>
    <dhRecbto>2026-06-24T12:00:00-03:00</dhRecbto>
    <nProt>311260000000001</nProt>
  </infInut>
</retInutNFe>"""


def _rejeitar_homolog(nf: NFeSaida) -> NFeSaida:
    if nf.empresa_emitente_id is None and nf.pedido_venda_id:
        nf.empresa_emitente = nf.pedido_venda.empresa_emitente
    nf.status_emissao_sefaz = NFeSaida.StatusEmissaoSefaz.REJEITADA_HOMOLOGACAO
    nf.status = 'REJEITADA_HOMOLOGACAO'
    nf.ambiente_emissao = NFeSaida.AmbienteEmissao.HOMOLOGACAO
    nf.serie_nfe = '0'
    nf.numero_nfe = '000000088'
    nf.chave_acesso = '3526050399910200015055000000000881234567890'
    nf.save()
    return nf


class NFeInutilizacaoSefazTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('inut4016', 'inut4016@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.pedido, self.item, self.nf = _pedido_nf()
        self.nf = _rejeitar_homolog(self.nf)
        _ensure_numeracao_empresa(self.nf.empresa_emitente)
        self.cfg = NFeNumeracaoConfiguracao.objects.get(
            empresa=self.nf.empresa_emitente,
            ambiente='homologacao',
            tipo_operacao=NFeNumeracaoConfiguracao.TipoOperacao.SAIDA,
            serie='0',
        )

    def test_justificativa_minima(self):
        with self.assertRaises(NFeInutilizacaoError):
            validar_justificativa_inutilizacao('curta')
        self.assertEqual(
            validar_justificativa_inutilizacao('Justificativa válida com 15+ chars'),
            'Justificativa válida com 15+ chars',
        )

    def test_pode_inutilizar_nfe_rejeitada(self):
        pode, motivo, cfg = pode_inutilizar_numero_nfe(self.nf, usuario=self.user)
        self.assertTrue(pode, motivo)
        self.assertEqual(cfg.pk, self.cfg.pk)

    def test_bloqueia_numero_autorizado(self):
        self.nf.status_emissao_sefaz = NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO
        self.nf.status = 'AUTORIZADA_HOMOLOGACAO'
        self.nf.protocolo_autorizacao = '13526005517408'
        self.nf.save()
        pode, motivo, _ = pode_inutilizar_numero_nfe(self.nf, usuario=self.user)
        self.assertFalse(pode)
        self.assertIn('autorizado', motivo.lower())

    def test_get_inutilizacao_dados_nfe(self):
        res = self.client.get(f'/api/nf-saidas/{self.nf.pk}/inutilizacao/dados/')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['pode_inutilizar'])
        self.assertEqual(res.data['numero_inicial_sugerido'], 88)

    def test_get_inutilizacao_dados_config(self):
        res = self.client.get(
            f'/api/nfe-numeracoes/{self.cfg.pk}/inutilizacao/dados/',
            {'numero_inicial': 88, 'numero_final': 88},
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['pode_inutilizar'])

    @patch('apps.fiscal.nfe_emissao.inutilizacao_sefaz.transmitir_inutilizacao_nfe')
    @patch('apps.fiscal.nfe_emissao.inutilizacao_sefaz.carregar_certificado_empresa')
    def test_emitir_inutilizacao_nfe_mock(self, mock_cert, mock_tx):
        mock_cert.return_value = type('C', (), {'caminho': '/tmp/fake.pfx'})()
        mock_tx.return_value = MagicMockInutResponse()

        payload = emitir_inutilizacao_nfe_saida(
            self.nf,
            justificativa='Numero rejeitado sem uso fiscal na homologacao.',
            usuario=self.user,
        )
        self.assertTrue(payload['ok'])
        self.nf.refresh_from_db()
        self.assertEqual(self.nf.status, 'INUTILIZADA_HOMOLOGACAO')
        self.assertTrue(
            NFeSaidaEvento.objects.filter(
                nfe_saida=self.nf,
                tipo_evento=NFeSaidaEvento.TipoEvento.INUTILIZACAO_SEFAZ_EMITIDA,
            ).exists(),
        )
        self.assertTrue(NFeInutilizacaoSefaz.objects.filter(configuracao=self.cfg, sefaz_ok=True).exists())

    @patch('apps.fiscal.nfe_emissao.inutilizacao_sefaz.transmitir_inutilizacao_nfe')
    @patch('apps.fiscal.nfe_emissao.inutilizacao_sefaz.carregar_certificado_empresa')
    def test_endpoint_inutilizar_config(self, mock_cert, mock_tx):
        mock_cert.return_value = type('C', (), {'caminho': '/tmp/fake.pfx'})()
        mock_tx.return_value = MagicMockInutResponse()

        res = self.client.post(
            f'/api/nfe-numeracoes/{self.cfg.pk}/inutilizar/',
            {
                'numero_inicial': 88,
                'numero_final': 88,
                'justificativa': 'Numero rejeitado sem uso fiscal na homologacao.',
            },
            format='json',
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['ok'])

    def test_faixa_invalida(self):
        pode, motivo, _ = pode_inutilizar_faixa_numeracao(
            self.cfg,
            numero_inicial=10,
            numero_final=5,
            usuario=self.user,
        )
        self.assertFalse(pode)
        self.assertIn('inválida', motivo.lower())
