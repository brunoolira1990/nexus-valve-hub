"""CT-e só entra no ERP quando alguma Empresa cadastrada é a tomadora."""

from __future__ import annotations

from django.test import SimpleTestCase, TestCase

from apps.cadastros.models import Empresa
from apps.fiscal.cte_import.service import importar_arquivos_cte
from apps.fiscal.dfe_recebidos.captura_sefaz import _cte_elegivel_captura
from apps.fiscal.models import CTeHistoricoImportado

NS = 'http://www.portalfiscal.inf.br/cte'
CNPJ_NEXUS = '03999102000150'
CNPJ_TOMADOR = '79925442000280'
CNPJ_TRANSP = '50593947000121'
CHAVE_BASE = '35240750593947000121570010000000011000000011'


def _cte_xml(*, tomador_cnpj: str, dest_cnpj: str, chave: str = CHAVE_BASE) -> bytes:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<cteProc xmlns="{NS}" versao="4.00">
  <CTe>
    <infCte Id="CTe{chave}" versao="4.00">
      <ide>
        <cUF>35</cUF><mod>57</mod><serie>1</serie><nCT>1</nCT>
        <cCT>00000011</cCT><cDV>1</cDV>
        <dhEmi>2026-07-31T22:13:00-03:00</dhEmi>
        <tpAmb>1</tpAmb><CFOP>5353</CFOP>
        <toma3><toma>0</toma></toma3>
      </ide>
      <emit><CNPJ>{CNPJ_TRANSP}</CNPJ><xNome>Transp</xNome></emit>
      <rem><CNPJ>{tomador_cnpj}</CNPJ><xNome>Remetente Tomador</xNome></rem>
      <dest><CNPJ>{dest_cnpj}</CNPJ><xNome>Destinatario</xNome></dest>
      <receb><CNPJ>{dest_cnpj}</CNPJ><xNome>Recebedor</xNome></receb>
      <vPrest><vTPrest>100.00</vTPrest><vRec>100.00</vRec></vPrest>
    </infCte>
  </CTe>
  <protCTe>
    <infProt><chCTe>{chave}</chCTe><cStat>100</cStat><nProt>1</nProt></infProt>
  </protCTe>
</cteProc>
""".encode()


class CteElegivelCapturaTomadorTests(SimpleTestCase):
    def test_aceita_quando_empresa_e_tomadora(self):
        xml = _cte_xml(tomador_cnpj=CNPJ_NEXUS, dest_cnpj=CNPJ_TOMADOR)
        ok, motivo = _cte_elegivel_captura(xml, CNPJ_NEXUS)
        self.assertTrue(ok, motivo)

    def test_rejeita_quando_empresa_so_destinataria(self):
        xml = _cte_xml(tomador_cnpj=CNPJ_TOMADOR, dest_cnpj=CNPJ_NEXUS)
        ok, motivo = _cte_elegivel_captura(xml, CNPJ_NEXUS)
        self.assertFalse(ok)
        self.assertIn('tomadora', motivo.lower())


class CteImportSomenteTomadorTests(TestCase):
    def setUp(self) -> None:
        self.emp, _ = Empresa.objects.get_or_create(
            cnpj=CNPJ_NEXUS,
            defaults={
                'razao_social': 'Nexus Teste Tomador',
                'nome_fantasia': 'Nexus',
                'ativo': True,
            },
        )

    def test_import_rejeita_sem_empresa_tomadora(self):
        chave = '35240750593947000121570010000000011000000101'
        xml = _cte_xml(tomador_cnpj=CNPJ_TOMADOR, dest_cnpj=CNPJ_NEXUS, chave=chave)
        result = importar_arquivos_cte([('cte.xml', xml)])
        self.assertEqual(result['resumo']['importados'], 0)
        self.assertEqual(result['resumo']['erros'], 1)
        self.assertIn('tomadora', result['erros'][0]['mensagem'].lower())
        self.assertFalse(CTeHistoricoImportado.objects.filter(chave_acesso=chave).exists())

    def test_import_aceita_com_empresa_tomadora(self):
        chave = '35240750593947000121570010000000011000000102'
        xml = _cte_xml(tomador_cnpj=CNPJ_NEXUS, dest_cnpj=CNPJ_TOMADOR, chave=chave)
        result = importar_arquivos_cte([('cte.xml', xml)])
        self.assertEqual(result['resumo']['importados'], 1, result)
        cte = CTeHistoricoImportado.objects.get(chave_acesso=chave)
        self.assertEqual(cte.empresa_tomadora_id, self.emp.id)
        self.assertEqual(cte.papel_empresa_no_documento, 'tomador')
