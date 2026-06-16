"""NF-e 4.0.15 — Cancelamento SEFAZ homologação/produção (mock, sem SEFAZ real)."""

from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.financeiro.models import TituloFinanceiro
from apps.financeiro.services.titulo import criar_titulo_financeiro
from apps.fiscal.models import NFeSaida
from apps.fiscal.nfe_emissao.carta_correcao import pode_emitir_carta_correcao
from apps.fiscal.nfe_emissao.cancelamento_sefaz import (
    MSG_JA_CANCELADA,
    NFeCancelamentoError,
    cancelamento_sefaz_ja_registrado,
    emitir_cancelamento_nfe_saida,
    pode_cancelar_nfe_sefaz,
    validar_justificativa_cancelamento,
)
from apps.fiscal.nfe_saida_financeiro import montar_flags_financeiro_nfe
from apps.fiscal.tests.test_nfe_saida_40143_gerar_contas_receber import _autorizar_nf_producao
from apps.fiscal.tests.test_nfe_saida_402_emissao_homologacao import _pedido_nf


def _autorizar_homolog(nf: NFeSaida) -> NFeSaida:
    nf.status_emissao_sefaz = NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO
    nf.status = 'AUTORIZADA_HOMOLOGACAO'
    nf.ambiente_emissao = NFeSaida.AmbienteEmissao.HOMOLOGACAO
    nf.serie_nfe = '0'
    nf.numero_nfe = '000000099'
    nf.cstat_autorizacao = '100'
    nf.protocolo_autorizacao = '13526005517408'
    nf.chave_acesso = '3526050399910200015055000000000991234567890'
    nf.xml_autorizado = '<?xml version="1.0"?><nfeProc><NFe/></nfeProc>'
    nf.save()
    return nf


class MagicMockResponse:
    text = """<?xml version="1.0"?>
<retEnvEvento xmlns="http://www.portalfiscal.inf.br/nfe" versao="1.00">
  <cStat>128</cStat>
  <xMotivo>Lote processado</xMotivo>
  <retEvento versao="1.00">
    <infEvento>
      <cStat>135</cStat>
      <xMotivo>Evento registrado</xMotivo>
      <nProt>135999999999999</nProt>
      <chNFe>3526050399910200015055000000000991234567890</chNFe>
      <tpEvento>110111</tpEvento>
      <nSeqEvento>1</nSeqEvento>
    </infEvento>
  </retEvento>
</retEnvEvento>"""


class NFeCancelamentoSefazTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('canc4015', 'canc4015@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.pedido, self.item, self.nf_homolog = _pedido_nf()
        self.nf_homolog = _autorizar_homolog(self.nf_homolog)
        _, _, self.nf_prod = _pedido_nf()
        self.nf_prod = _autorizar_nf_producao(self.nf_prod)

    def test_justificativa_minima(self):
        with self.assertRaises(NFeCancelamentoError):
            validar_justificativa_cancelamento('curta')
        self.assertEqual(
            validar_justificativa_cancelamento('Justificativa válida com 15+ chars'),
            'Justificativa válida com 15+ chars',
        )

    def test_pode_cancelar_homolog(self):
        pode, motivo = pode_cancelar_nfe_sefaz(self.nf_homolog, usuario=self.user)
        self.assertTrue(pode, motivo)

    def test_pode_cancelar_producao_sem_permissao(self):
        pode, motivo = pode_cancelar_nfe_sefaz(self.nf_prod, usuario=self.user)
        self.assertFalse(pode)
        self.assertIn('permissão', motivo.lower())

    def test_bloqueia_sem_chave(self):
        self.nf_homolog.chave_acesso = ''
        self.nf_homolog.save(update_fields=['chave_acesso'])
        pode, _ = pode_cancelar_nfe_sefaz(self.nf_homolog, usuario=self.user)
        self.assertFalse(pode)

    def test_bloqueia_ja_cancelada(self):
        self.nf_homolog.status = 'CANCELADA_HOMOLOGACAO'
        self.nf_homolog.save(update_fields=['status'])
        pode, motivo = pode_cancelar_nfe_sefaz(self.nf_homolog, usuario=self.user)
        self.assertFalse(pode)
        self.assertIn(MSG_JA_CANCELADA, motivo)

    def test_cce_bloqueada_apos_cancelamento(self):
        self.nf_homolog.status = 'CANCELADA_HOMOLOGACAO'
        self.nf_homolog.save(update_fields=['status'])
        pode, motivo = pode_emitir_carta_correcao(self.nf_homolog)
        self.assertFalse(pode)
        self.assertIn('cancelada', motivo.lower())

    def test_financeiro_bloqueado_apos_cancelamento(self):
        self.nf_prod.status = 'CANCELADA_PRODUCAO'
        self.nf_prod.save(update_fields=['status'])
        flags = montar_flags_financeiro_nfe(self.nf_prod)
        self.assertFalse(flags['pode_gerar_contas_receber'])

    @patch('apps.fiscal.nfe_emissao.cancelamento_sefaz.transmitir_evento_nfe')
    @patch('apps.fiscal.nfe_emissao.cancelamento_sefaz._montar_assinar_evento_cancelamento')
    @patch('apps.fiscal.nfe_emissao.cancelamento_sefaz.carregar_certificado_empresa')
    def test_emitir_mock_homolog_atualiza_status(self, mock_cert, mock_assinar, mock_transmit):
        mock_cert.return_value = type('C', (), {'caminho': '/tmp/fake.pfx'})()
        mock_assinar.return_value = '<evento/>'
        mock_transmit.return_value = MagicMockResponse()

        xml_antes = self.nf_homolog.xml_autorizado
        res = emitir_cancelamento_nfe_saida(
            self.nf_homolog,
            justificativa='Cancelamento de teste homologação com justificativa.',
            usuario=self.user,
        )
        self.assertTrue(res['ok'])
        self.nf_homolog.refresh_from_db()
        self.assertEqual(self.nf_homolog.status, 'CANCELADA_HOMOLOGACAO')
        self.assertEqual(self.nf_homolog.xml_autorizado, xml_antes)
        self.assertTrue(cancelamento_sefaz_ja_registrado(self.nf_homolog))

    def test_financeiro_nao_alterado_apos_cancelamento(self):
        nf = self.nf_homolog
        titulo = criar_titulo_financeiro(
            tipo=TituloFinanceiro.Tipo.RECEBER,
            cliente_id=nf.cliente_id,
            data_emissao=nf.data,
            data_vencimento=nf.data,
            valor_original=nf.valor_total,
            origem_tipo=TituloFinanceiro.OrigemTipo.NFE_SAIDA,
            origem_id=nf.pk,
            origem_numero='99',
            usuario=self.user,
        )
        nf.status = 'CANCELADA_HOMOLOGACAO'
        nf.save(update_fields=['status'])
        titulo.refresh_from_db()
        self.assertFalse(titulo.cancelado)
        self.assertTrue(TituloFinanceiro.objects.filter(pk=titulo.pk).exists())

    def test_endpoint_dados_homolog(self):
        res = self.client.get(f'/api/nf-saidas/{self.nf_homolog.pk}/cancelamento/dados/')
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body['pode_cancelar'])
        self.assertEqual(body['ambiente'], 'homologacao')
