"""Recuperação pós-transmissão — consulta situação sincroniza status/CR e rejeição 204.

Incidente: a SEFAZ autorizou a NF-e, o ERP deu timeout em transmissão e a nota ficou
RASCUNHO. Estas cobrem o destravamento por «Sincronizar SEFAZ» e a auto-recuperação
de Rejeição 204 (duplicidade).
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils.dateparse import parse_datetime
from rest_framework.test import APIClient

from apps.financeiro.models import TituloFinanceiro
from apps.fiscal.models import NFeNumeracaoConfiguracao, NFeSaida
from apps.fiscal.nfe_emissao.consulta_situacao import (
    MSG_SEFAZ_JA_REGISTROU,
    MSG_SEM_CHAVE,
    MSG_STATUS_INCOMPATIVEL,
    NFeConsultaSituacaoError,
    consultar_situacao_nfe_saida,
    pode_consultar_situacao_sefaz,
    pode_sincronizar_com_sefaz,
)
from apps.fiscal.nfe_emissao.retorno_sefaz import resultado_autorizacao_mock
from apps.fiscal.nfe_emissao.servico_producao import emitir_nfe_producao
from apps.fiscal.nfe_integracao.adapters.consulta_situacao_parser import (
    ResultadoConsultaSituacaoSefaz,
)
from apps.fiscal.tests.nfe_4015_test_support import NFe4015GruposMixin
from apps.fiscal.tests.test_nfe_saida_353_prontidao_conferencia import _regra_84818200_sp_rj
from apps.fiscal.tests.test_nfe_saida_producao_4015 import (
    CONFIRMACAO_PRODUCAO,
    _grant_permissao_producao,
    _pedido_nf,
    _preparar_nf_indicadores,
    _preparar_pronta,
)

CHAVE_PROD = '35261012345678000199550010000000911000000915'
PROTOCOLO_RECUPERADO = '135260000000099'

# XML assinado que o ERP gravou antes da transmissão — é a única fonte do corpo NFe
# quando a resposta se perdeu.
XML_NFE_ASSINADA = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<NFe xmlns="http://www.portalfiscal.inf.br/nfe">'
    f'<infNFe Id="NFe{CHAVE_PROD}" versao="4.00">'
    '<ide><tpAmb>1</tpAmb></ide>'
    '</infNFe></NFe>'
)

# retConsSitNFe de nota autorizada — sem «infNFe» para não ser confundido com procNFe.
XML_RET_CONS_AUTORIZADA = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<retConsSitNFe xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">'
    '<tpAmb>1</tpAmb><verAplic>SP_NFE_00</verAplic><cStat>100</cStat>'
    '<xMotivo>Consulta Autorizada</xMotivo>'
    f'<chNFe>{CHAVE_PROD}</chNFe>'
    '<protNFe versao="4.00"><infProt>'
    f'<tpAmb>1</tpAmb><verAplic>SP_NFE_00</verAplic><chNFe>{CHAVE_PROD}</chNFe>'
    f'<dhRecbto>2026-10-19T10:00:00-03:00</dhRecbto><nProt>{PROTOCOLO_RECUPERADO}</nProt>'
    '<cStat>100</cStat><xMotivo>Autorizado o uso da NF-e</xMotivo>'
    '</infProt></protNFe></retConsSitNFe>'
)

XML_RET_CONS_EM_DIG = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<retConsSitNFe xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">'
    '<tpAmb>1</tpAmb><cStat>100</cStat><xMotivo>Consulta OK</xMotivo>'
    f'<chNFe>{CHAVE_PROD}</chNFe><retPed></retPed></retConsSitNFe>'
)


def _resultado_consulta(*, autorizada: bool, xml_retorno: str) -> ResultadoConsultaSituacaoSefaz:
    if autorizada:
        return ResultadoConsultaSituacaoSefaz(
            ok=True,
            c_stat_consulta='100',
            x_motivo_consulta='Consulta OK',
            c_stat_nfe='100',
            x_motivo_nfe='Autorizado o uso da NF-e',
            protocolo=PROTOCOLO_RECUPERADO,
            chave_acesso=CHAVE_PROD,
            dh_recbto='2026-10-19T10:00:00-03:00',
            tp_amb='1',
            xml_retorno=xml_retorno,
            autorizada=True,
            cancelada=False,
            denegada=False,
        )
    return ResultadoConsultaSituacaoSefaz(
        ok=True,
        c_stat_consulta='100',
        x_motivo_consulta='Consulta OK',
        c_stat_nfe='',
        x_motivo_nfe='',
        protocolo='',
        chave_acesso=CHAVE_PROD,
        dh_recbto='',
        tp_amb='1',
        xml_retorno=xml_retorno,
        autorizada=False,
        cancelada=False,
        denegada=False,
    )


@override_settings(
    USE_CENARIO_FISCAL_SAIDA_FOR_PROPOSTAS=True,
    DANFE_BLOCK_EMISSION_IF_BFR_FAILS=False,
)
class BaseRecuperacaoTeste(NFe4015GruposMixin, TestCase):
    def setUp(self):
        _regra_84818200_sp_rj()
        self.user = get_user_model().objects.create_user('syncsefaz', 'syncsefaz@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.pedido, self.nf = _pedido_nf()
        self.empresa = self.pedido.empresa_emitente
        self.nf = _preparar_nf_indicadores(self.nf)
        _grant_permissao_producao(self.user)
        self.nf = _preparar_pronta(self.nf, self.user)

    def simular_timeout_pos_transmissao(self) -> NFeSaida:
        """Estado real de uma nota que a SEFAZ autorizou e o ERP perdeu a resposta."""
        nf = self.nf
        nf.status = 'RASCUNHO'
        nf.status_emissao_sefaz = NFeSaida.StatusEmissaoSefaz.ERRO_TRANSMISSAO
        nf.ambiente_emissao = NFeSaida.AmbienteEmissao.PRODUCAO
        nf.serie_nfe = '1'
        nf.numero_nfe = '000000091'
        nf.chave_acesso = CHAVE_PROD
        nf.xml_assinado = XML_NFE_ASSINADA
        nf.xml_retorno = ''
        nf.xml_retorno_lote = ''
        nf.xml_protocolo = ''
        nf.xml_autorizado = ''
        nf.protocolo_autorizacao = ''
        nf.cstat_autorizacao = ''
        nf.motivo_autorizacao = 'Timeout ao transmitir NF-e em produção.'
        nf.cstat_lote = ''
        nf.recibo_lote = ''
        nf.save()
        nf.refresh_from_db()
        return nf

    def numeracao_producao(self, serie: str) -> NFeNumeracaoConfiguracao:
        return NFeNumeracaoConfiguracao.objects.get(
            empresa=self.empresa,
            ambiente=NFeNumeracaoConfiguracao.Ambiente.PRODUCAO,
            tipo_operacao=NFeNumeracaoConfiguracao.TipoOperacao.SAIDA,
            serie=serie,
        )

    def patch_consulta_sefaz(self, resultado: ResultadoConsultaSituacaoSefaz):
        """Mocka a cadeia pynfe da consulta; retorna o mock de parse para asserts."""
        certificadopatch = patch(
            'apps.fiscal.nfe_emissao.consulta_situacao.carregar_certificado_empresa',
            return_value=MagicMock(caminho='/tmp/falso.pfx'),
        )
        comunicacaopatch = patch(
            'apps.fiscal.nfe_emissao.consulta_situacao.criar_comunicacao_sefaz',
            return_value=MagicMock(),
        )
        consultrapatch = patch(
            'apps.fiscal.nfe_emissao.consulta_situacao.consulta_situacao_nfe',
            return_value='<consSitNFe/>',
        )
        extracaopatch = patch(
            'apps.fiscal.nfe_emissao.consulta_situacao.extrair_xml_resposta',
            return_value=resultado.xml_retorno,
        )
        parsepatch = patch(
            'apps.fiscal.nfe_emissao.consulta_situacao.parse_consulta_situacao_resposta',
            return_value=resultado,
        )
        for ctx in (
            certificadopatch,
            comunicacaopatch,
            consultrapatch,
            extracaopatch,
            parsepatch,
        ):
            ctx.start()
            self.addCleanup(ctx.stop)
        return parsepatch


class GuardSincronizacaoTests(BaseRecuperacaoTeste):
    def test_guard_sincronizacao_aceita_rascunho_com_chave(self):
        nf = self.simular_timeout_pos_transmissao()
        pode, motivo = pode_sincronizar_com_sefaz(nf)
        self.assertTrue(pode, motivo)
        self.assertEqual(motivo, '')

    def test_guard_sincronizacao_aceita_rejeitada_com_chave(self):
        nf = self.simular_timeout_pos_transmissao()
        nf.status_emissao_sefaz = NFeSaida.StatusEmissaoSefaz.REJEITADA_PRODUCAO
        nf.cstat_autorizacao = '204'
        nf.save(update_fields=['status_emissao_sefaz', 'cstat_autorizacao'])
        nf.refresh_from_db()
        pode, motivo = pode_sincronizar_com_sefaz(nf)
        self.assertTrue(pode, motivo)

    def test_guard_sincronizacao_bloqueia_rascunho_sem_chave(self):
        nf = self.nf
        nf.chave_acesso = ''
        nf.status = 'RASCUNHO'
        nf.status_emissao_sefaz = ''
        nf.save(update_fields=['chave_acesso', 'status', 'status_emissao_sefaz'])
        nf.refresh_from_db()
        pode, motivo = pode_sincronizar_com_sefaz(nf)
        self.assertFalse(pode)
        self.assertEqual(motivo, MSG_SEM_CHAVE)

    def test_guard_sincronizacao_bloqueia_cancelada(self):
        nf = self.simular_timeout_pos_transmissao()
        nf.status = 'CANCELADA'
        nf.save(update_fields=['status'])
        nf.refresh_from_db()
        self.assertEqual(pode_sincronizar_com_sefaz(nf), (False, MSG_STATUS_INCOMPATIVEL))

        nf.status = 'RASCUNHO'
        nf.status_emissao_sefaz = 'CANCELADA_PRODUCAO'
        nf.save(update_fields=['status', 'status_emissao_sefaz'])
        nf.refresh_from_db()
        self.assertEqual(pode_sincronizar_com_sefaz(nf), (False, MSG_STATUS_INCOMPATIVEL))

    def test_guard_estrito_continua_bloqueando_rejeitada_para_cce_e_cancelamento(self):
        nf = self.simular_timeout_pos_transmissao()
        nf.status_emissao_sefaz = NFeSaida.StatusEmissaoSefaz.REJEITADA_PRODUCAO
        nf.cstat_autorizacao = '204'
        nf.save(update_fields=['status_emissao_sefaz', 'cstat_autorizacao'])
        nf.refresh_from_db()
        pode, motivo = pode_consultar_situacao_sefaz(nf)
        self.assertFalse(pode)
        self.assertEqual(motivo, MSG_STATUS_INCOMPATIVEL)


class ConsultaSituacaoSincronizaTests(BaseRecuperacaoTeste):
    def test_consulta_autorizada_sincroniza_status_e_gera_contas_receber(self):
        nf = self.simular_timeout_pos_transmissao()
        self.patch_consulta_sefaz(
            _resultado_consulta(autorizada=True, xml_retorno=XML_RET_CONS_AUTORIZADA)
        )
        res = consultar_situacao_nfe_saida(nf, usuario=self.user)

        self.assertTrue(res['ok'])
        self.assertTrue(res['status_local_atualizado'])
        self.assertEqual(res['status'], 'AUTORIZADA_PRODUCAO')
        self.assertTrue(res['xml_autorizado_recuperado'])

        nf.refresh_from_db()
        self.assertEqual(nf.status, 'AUTORIZADA_PRODUCAO')
        self.assertEqual(nf.status_emissao_sefaz, NFeSaida.StatusEmissaoSefaz.AUTORIZADA_PRODUCAO)
        self.assertEqual(nf.protocolo_autorizacao, PROTOCOLO_RECUPERADO)
        self.assertEqual(nf.cstat_autorizacao, '100')
        self.assertIn('<nProt>', nf.xml_retorno)
        self.assertIn('protNFe', nf.xml_autorizado)
        self.assertEqual(nf.autorizada_em, parse_datetime('2026-10-19T10:00:00-03:00'))

        self.assertTrue(res['financeiro']['gerado'], res['financeiro'])
        self.assertEqual(
            TituloFinanceiro.objects.filter(
                origem_tipo=TituloFinanceiro.OrigemTipo.NFE_SAIDA,
                origem_id=nf.pk,
            ).count(),
            1,
        )

    def test_autorizada_em_nao_e_reescrito_por_consulta_posterior(self):
        nf = self.simular_timeout_pos_transmissao()
        anterior = datetime(2026, 10, 19, 8, 0, 0, tzinfo=timezone.utc)
        nf.autorizada_em = anterior
        nf.save(update_fields=['autorizada_em'])
        self.patch_consulta_sefaz(
            _resultado_consulta(autorizada=True, xml_retorno=XML_RET_CONS_AUTORIZADA)
        )
        consultar_situacao_nfe_saida(nf, usuario=self.user)
        nf.refresh_from_db()
        self.assertEqual(nf.autorizada_em, anterior)

    def test_consulta_sem_situacao_inequivoca_preserva_rascunho(self):
        nf = self.simular_timeout_pos_transmissao()
        self.patch_consulta_sefaz(_resultado_consulta(autorizada=False, xml_retorno=XML_RET_CONS_EM_DIG))
        res = consultar_situacao_nfe_saida(nf, usuario=self.user)

        self.assertFalse(res['status_local_atualizado'])
        self.assertNotIn('financeiro', res)
        nf.refresh_from_db()
        self.assertEqual(nf.status, 'RASCUNHO')
        self.assertEqual(nf.status_emissao_sefaz, NFeSaida.StatusEmissaoSefaz.ERRO_TRANSMISSAO)
        self.assertFalse(TituloFinanceiro.objects.filter(origem_id=nf.pk).exists())

    def test_consulta_idempotente_nao_duplica_contas_receber(self):
        nf = self.simular_timeout_pos_transmissao()
        self.patch_consulta_sefaz(
            _resultado_consulta(autorizada=True, xml_retorno=XML_RET_CONS_AUTORIZADA)
        )
        consultar_situacao_nfe_saida(nf, usuario=self.user)
        segundo = consultar_situacao_nfe_saida(nf, usuario=self.user)

        self.assertTrue(segundo['financeiro']['ja_existente'], segundo['financeiro'])
        self.assertEqual(
            TituloFinanceiro.objects.filter(
                origem_tipo=TituloFinanceiro.OrigemTipo.NFE_SAIDA,
                origem_id=nf.pk,
            ).count(),
            1,
        )

    @override_settings(NFE_PRODUCAO_HABILITADA=True)
    def test_endpoint_consulta_destrava_rascunho_pos_timeout(self):
        nf = self.simular_timeout_pos_transmissao()
        self.patch_consulta_sefaz(
            _resultado_consulta(autorizada=True, xml_retorno=XML_RET_CONS_AUTORIZADA)
        )
        resp = self.client.post(f'/api/nf-saidas/{nf.pk}/consultar-situacao-sefaz/', format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['status_local_atualizado'])
        nf.refresh_from_db()
        self.assertEqual(nf.status, 'AUTORIZADA_PRODUCAO')


class Rejeicao204Tests(BaseRecuperacaoTeste):
    @override_settings(NFE_PRODUCAO_HABILITADA=True)
    @patch('apps.fiscal.nfe_emissao.servico_producao.validar_emissao_completa', return_value={'ok': True, 'erros': []})
    @patch('apps.fiscal.nfe_emissao.servico_producao.assinar_xml_nfe')
    @patch('apps.fiscal.nfe_emissao.servico_producao.transmitir_nfe_producao')
    def test_rejeicao_204_recupera_autorizacao_por_consulta(self, mock_tx, mock_assinar, _mock_valida):
        mock_assinar.side_effect = lambda xml, emp, **kw: xml if isinstance(xml, bytes) else xml.encode()
        mock_tx.return_value = resultado_autorizacao_mock(
            autorizado=False,
            c_stat='204',
            x_motivo='Rejeição 204: NF-e já existente',
            protocolo='',
            xml_retorno='<retEnviNFe><cStat>104</cStat><xMotivo>Lote processado</xMotivo></retEnviNFe>',
        )
        self.patch_consulta_sefaz(
            _resultado_consulta(autorizada=True, xml_retorno=XML_RET_CONS_AUTORIZADA)
        )

        res = emitir_nfe_producao(self.nf, usuario=self.user, confirmacao_payload=CONFIRMACAO_PRODUCAO)

        self.assertTrue(res['ok'])
        self.assertTrue(res['autorizado'])
        self.assertEqual(res['mensagem'], MSG_SEFAZ_JA_REGISTROU)
        self.assertEqual(res['protocolo'], PROTOCOLO_RECUPERADO)
        self.assertIn('sincronizacao_sefaz', res)

        self.nf.refresh_from_db()
        self.assertEqual(self.nf.status, 'AUTORIZADA_PRODUCAO')
        self.assertEqual(self.nf.status_emissao_sefaz, NFeSaida.StatusEmissaoSefaz.AUTORIZADA_PRODUCAO)
        self.assertEqual(self.nf.protocolo_autorizacao, PROTOCOLO_RECUPERADO)
        self.assertEqual(
            TituloFinanceiro.objects.filter(
                origem_tipo=TituloFinanceiro.OrigemTipo.NFE_SAIDA,
                origem_id=self.nf.pk,
            ).count(),
            1,
        )
        cfg = self.numeracao_producao(self.nf.serie_nfe)
        self.assertEqual(cfg.ultimo_numero_autorizado, int(self.nf.numero_nfe))

    @override_settings(NFE_PRODUCAO_HABILITADA=True)
    @patch('apps.fiscal.nfe_emissao.servico_producao.validar_emissao_completa', return_value={'ok': True, 'erros': []})
    @patch('apps.fiscal.nfe_emissao.servico_producao.assinar_xml_nfe')
    @patch('apps.fiscal.nfe_emissao.servico_producao.transmitir_nfe_producao')
    def test_recuperacao_204_nao_retrocede_numero_autorizado(self, mock_tx, mock_assinar, _mock_valida):
        mock_assinar.side_effect = lambda xml, emp, **kw: xml if isinstance(xml, bytes) else xml.encode()
        mock_tx.return_value = resultado_autorizacao_mock(
            autorizado=False,
            c_stat='204',
            x_motivo='Rejeição 204: NF-e já existente',
            protocolo='',
            xml_retorno='<retEnviNFe><cStat>104</cStat></retEnviNFe>',
        )
        self.patch_consulta_sefaz(
            _resultado_consulta(autorizada=True, xml_retorno=XML_RET_CONS_AUTORIZADA)
        )
        serie = self.nf.serie_nfe or '1'
        cfg = self.numeracao_producao(serie)
        cfg.ultimo_numero_autorizado = 900
        cfg.save(update_fields=['ultimo_numero_autorizado'])

        emitir_nfe_producao(self.nf, usuario=self.user, confirmacao_payload=CONFIRMACAO_PRODUCAO)

        self.nf.refresh_from_db()
        self.assertEqual(self.nf.status_emissao_sefaz, NFeSaida.StatusEmissaoSefaz.AUTORIZADA_PRODUCAO)
        self.assertLess(int(self.nf.numero_nfe), 900)
        cfg.refresh_from_db()
        self.assertEqual(cfg.ultimo_numero_autorizado, 900)

    @override_settings(NFE_PRODUCAO_HABILITADA=True)
    @patch('apps.fiscal.nfe_emissao.consulta_situacao.consulta_situacao_nfe')
    @patch('apps.fiscal.nfe_emissao.servico_producao.validar_emissao_completa', return_value={'ok': True, 'erros': []})
    @patch('apps.fiscal.nfe_emissao.servico_producao.assinar_xml_nfe')
    @patch('apps.fiscal.nfe_emissao.servico_producao.transmitir_nfe_producao')
    def test_rejeicao_comum_nao_dispara_consulta(self, mock_tx, mock_assinar, _mock_valida, mock_consulta):
        mock_assinar.side_effect = lambda xml, emp, **kw: xml if isinstance(xml, bytes) else xml.encode()
        mock_tx.return_value = resultado_autorizacao_mock(
            autorizado=False,
            c_stat='539',
            x_motivo='Rejeição 539: IE do destinatário inválida',
            protocolo='',
            xml_retorno='<retEnviNFe><cStat>104</cStat></retEnviNFe>',
        )

        res = emitir_nfe_producao(self.nf, usuario=self.user, confirmacao_payload=CONFIRMACAO_PRODUCAO)

        self.assertFalse(res['autorizado'])
        mock_consulta.assert_not_called()
        self.assertNotIn('sincronizacao_sefaz', res)
        self.nf.refresh_from_db()
        self.assertEqual(self.nf.status_emissao_sefaz, NFeSaida.StatusEmissaoSefaz.REJEITADA_PRODUCAO)
        self.assertNotEqual(self.nf.status, 'AUTORIZADA_PRODUCAO')

    @override_settings(NFE_PRODUCAO_HABILITADA=True)
    @patch('apps.fiscal.nfe_emissao.consulta_situacao.criar_comunicacao_sefaz')
    @patch('apps.fiscal.nfe_emissao.consulta_situacao.carregar_certificado_empresa')
    @patch('apps.fiscal.nfe_emissao.servico_producao.validar_emissao_completa', return_value={'ok': True, 'erros': []})
    @patch('apps.fiscal.nfe_emissao.servico_producao.assinar_xml_nfe')
    @patch('apps.fiscal.nfe_emissao.servico_producao.transmitir_nfe_producao')
    def test_recuperacao_204_falha_nao_invalida_rejeicao(
        self, mock_tx, mock_assinar, _mock_valida, mock_cert, mock_com
    ):
        from apps.fiscal.nfe_integracao.adapters.exceptions import PyNFeComunicacaoError

        mock_assinar.side_effect = lambda xml, emp, **kw: xml if isinstance(xml, bytes) else xml.encode()
        mock_tx.return_value = resultado_autorizacao_mock(
            autorizado=False,
            c_stat='204',
            x_motivo='Rejeição 204: NF-e já existente',
            protocolo='',
            xml_retorno='<retEnviNFe><cStat>104</cStat></retEnviNFe>',
        )
        mock_cert.return_value = MagicMock(caminho='/tmp/falso.pfx')
        mock_com.side_effect = PyNFeComunicacaoError('SEFAZ indisponível')

        res = emitir_nfe_producao(self.nf, usuario=self.user, confirmacao_payload=CONFIRMACAO_PRODUCAO)

        self.assertFalse(res['autorizado'])
        self.nf.refresh_from_db()
        self.assertEqual(self.nf.cstat_autorizacao, '204')
        self.assertEqual(self.nf.status_emissao_sefaz, NFeSaida.StatusEmissaoSefaz.REJEITADA_PRODUCAO)
        self.assertNotEqual(self.nf.status, 'AUTORIZADA_PRODUCAO')


class ConsultaSituacaoGuardTests(BaseRecuperacaoTeste):
    def test_consulta_rascunho_sem_chave_lanca_erro_de_validacao(self):
        nf = self.nf
        nf.chave_acesso = ''
        nf.save(update_fields=['chave_acesso'])
        nf.refresh_from_db()
        with self.assertRaises(NFeConsultaSituacaoError) as ctx:
            consultar_situacao_nfe_saida(nf, usuario=self.user)
        self.assertEqual(ctx.exception.etapa, 'VALIDACAO')
        self.assertEqual(str(ctx.exception), MSG_SEM_CHAVE)
