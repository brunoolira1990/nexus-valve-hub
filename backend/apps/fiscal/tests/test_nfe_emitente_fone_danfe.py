"""DANFE/XML — telefone do emitente no enderEmit."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.fiscal.nfe_integracao.danfe_bfr_emit import montar_emit_extras_nfe_saida
from apps.fiscal.nfe_saida_from_faturamento import gerar_nfe_saida_from_faturamento
from apps.fiscal.nfe_saida_xml_nfelib import fone_nfe_digits
from apps.fiscal.models import NFeSaida
from apps.fiscal.nfe_saida_preview import gerar_dados_preview_nfe_saida
from apps.fiscal.tests.test_nfe_saida_354_danfe_conferencia import _regra
from apps.fiscal.tests.test_nfe_saida_faturamento import _faturamento_pronto, _pedido_item


class NfeEmitenteFoneDanfeTests(TestCase):
    def setUp(self):
        get_user_model().objects.create_user('fone1', 'f1@test.com', 'x')
        _regra()

    def test_fone_nfe_digits(self):
        self.assertEqual(fone_nfe_digits('(11) 3456-7890'), '1134567890')
        self.assertIsNone(fone_nfe_digits('123'))

    def test_preview_emitente_tem_fone(self):
        pedido, item = _pedido_item()
        emp = pedido.empresa_emitente
        emp.telefone = '(11) 3456-7890'
        emp.save(update_fields=['telefone'])
        item.snapshot_fiscal = {'ncm': '84818200', 'cfop': '5102', 'cst_icms': '00'}
        item.save(update_fields=['snapshot_fiscal'])
        fat = _faturamento_pronto(pedido, item, qtd='1')
        nf = NFeSaida.objects.get(pk=gerar_nfe_saida_from_faturamento(pedido, fat.pk)['nfe_saida_id'])
        dados = gerar_dados_preview_nfe_saida(nf)
        self.assertEqual(dados['emitente']['fone'], '1134567890')
        extras = montar_emit_extras_nfe_saida(nf)
        self.assertIn('3456', extras.get('telefone', ''))
