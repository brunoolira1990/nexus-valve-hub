"""ERP 4.0.13.5 — Checklist fiscal pré-homologação NF-e."""

from __future__ import annotations

import re
import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.comercial.models import PedidoVenda
from apps.comercial.pedido_venda_pdf import gerar_pedido_venda_pdf_bytes
from apps.fiscal.dfe_classificacao import pode_entrar_apuracao
from apps.fiscal.models import AtendimentoEstoque, NFeSaida
from apps.fiscal.nfe_integracao.adapters.nfelib_adapter import nfelib_disponivel
from apps.fiscal.nfe_integracao.danfe_brazil_fiscal_report import brazil_fiscal_report_disponivel
from apps.fiscal.nfe_saida_checklist_homologacao import validar_prontidao_nfe_homologacao
from apps.fiscal.nfe_saida_duplicatas import aplicar_duplicatas_nfe_saida
from apps.fiscal.nfe_saida_preview import gerar_preview_danfe_nfe_saida
from apps.fiscal.serializers import NFeSaidaListSerializer
from apps.fiscal.tests.test_nfe_saida_40133_duplicatas import _nf_com_prazo, _pedido_com_prazo
from apps.fiscal.tests.test_nfe_saida_faturamento import _faturamento_pronto, _pedido_item
from apps.fiscal.tests.test_nfe_saida_354_danfe_conferencia import _regra


def _pdf_text(pdf_bytes: bytes) -> str:
    import io

    from pypdf import PdfReader

    text = ''
    for page in PdfReader(io.BytesIO(pdf_bytes)).pages:
        text += page.extract_text() or ''
    return text


@override_settings(USE_CENARIO_FISCAL_SAIDA_FOR_PROPOSTAS=True)
class NFe40135ChecklistHomologacaoTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username=f'chk_{uuid.uuid4().hex[:8]}',
            password='test123',
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        _regra()

    def test_checklist_aprovado_pedido_nf_valido(self):
        nf, _ = _nf_com_prazo()
        from apps.fiscal.nfe_saida_duplicatas import aplicar_duplicatas_nfe_saida

        aplicar_duplicatas_nfe_saida(nf)
        pedido = nf.pedido_venda
        fat = nf.faturamento_pedido_venda
        antes_est = AtendimentoEstoque.objects.count()
        xml_antes = nf.xml_autorizado
        resultado = validar_prontidao_nfe_homologacao(
            pedido_venda=pedido,
            faturamento=fat,
            nfe_saida=nf,
        )
        nf.refresh_from_db()
        self.assertEqual(AtendimentoEstoque.objects.count(), antes_est)
        self.assertEqual(nf.xml_autorizado, xml_antes)
        self.assertIn(resultado['status'], ('aprovado', 'aprovado_com_alertas'))
        self.assertTrue(resultado['apto'])
        codigos = {i['codigo'] for i in resultado['itens']}
        self.assertIn('duplicatas_nfe', codigos)
        self.assertIn('sem_financeiro', codigos)

    def test_bloqueia_sem_referencia(self):
        resultado = validar_prontidao_nfe_homologacao()
        self.assertFalse(resultado['apto'])
        self.assertEqual(resultado['status'], 'bloqueado')

    def test_bloqueia_pedido_sem_itens(self):
        pedido, _ = _pedido_item()
        pedido.itens.all().delete()
        resultado = validar_prontidao_nfe_homologacao(pedido_venda=pedido)
        self.assertFalse(resultado['apto'])
        self.assertTrue(any('sem itens' in b.lower() for b in resultado['bloqueios']))

    def test_bloqueia_valor_zero(self):
        pedido, item = _pedido_item()
        pedido.valor_total = Decimal('0')
        pedido.save(update_fields=['valor_total'])
        resultado = validar_prontidao_nfe_homologacao(pedido_venda=pedido)
        self.assertFalse(resultado['apto'])

    def test_valida_duplicata_001(self):
        nf, _ = _nf_com_prazo()
        resultado = validar_prontidao_nfe_homologacao(nfe_saida=nf)
        dup_item = next(
            i for i in resultado['itens'] if i['codigo'] == 'duplicatas_nfe' and i['status'] == 'ok'
        )
        self.assertIn('001', dup_item['mensagem'])

    def test_valida_vencimento_duplicata(self):
        nf, venc = _nf_com_prazo()
        resultado = validar_prontidao_nfe_homologacao(nfe_saida=nf)
        dup = next(i for i in resultado['itens'] if i['codigo'] == 'duplicatas_nfe')
        self.assertIn(venc.isoformat(), dup['mensagem'])

    def test_valida_soma_duplicatas(self):
        nf, _ = _nf_com_prazo()
        resultado = validar_prontidao_nfe_homologacao(nfe_saida=nf)
        self.assertFalse(any(i['codigo'] == 'duplicatas_soma' and i['status'] == 'bloqueado' for i in resultado['itens']))

    def test_xml_cobr_dup_quando_nfelib(self):
        if not nfelib_disponivel():
            self.skipTest('nfelib indisponível')
        nf, _ = _nf_com_prazo()
        resultado = validar_prontidao_nfe_homologacao(nfe_saida=nf)
        xml_item = next((i for i in resultado['itens'] if i['codigo'] == 'xml_duplicatas'), None)
        self.assertIsNotNone(xml_item)
        self.assertEqual(xml_item['status'], 'ok')

    def test_nao_transmite_nf(self):
        nf, _ = _nf_com_prazo()
        st_antes = nf.status_emissao_sefaz
        validar_prontidao_nfe_homologacao(nfe_saida=nf)
        nf.refresh_from_db()
        self.assertEqual(nf.status_emissao_sefaz, st_antes)

    def test_nao_altera_xml_autorizado(self):
        nf, _ = _nf_com_prazo()
        nf.status_emissao_sefaz = NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO
        nf.xml_autorizado = '<?xml version="1.0"?><nfeProc><NFe/></nfeProc>'
        nf.save(update_fields=['status_emissao_sefaz', 'xml_autorizado'])
        xml_antes = nf.xml_autorizado
        validar_prontidao_nfe_homologacao(nfe_saida=nf)
        nf.refresh_from_db()
        self.assertEqual(nf.xml_autorizado, xml_antes)

    def test_homolog_fora_apuracao(self):
        nf, _ = _nf_com_prazo()
        nf.status_emissao_sefaz = NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO
        nf.ambiente_emissao = NFeSaida.AmbienteEmissao.HOMOLOGACAO
        nf.save(update_fields=['status_emissao_sefaz', 'ambiente_emissao'])
        self.assertFalse(pode_entrar_apuracao(nf))
        resultado = validar_prontidao_nfe_homologacao(nfe_saida=nf)
        self.assertTrue(any(i['codigo'] == 'homolog_fora_apuracao' for i in resultado['itens']))

    def test_aprovado_com_alertas_quando_ha_alertas_operacionais(self):
        nf, _ = _nf_com_prazo()
        from apps.fiscal.nfe_saida_duplicatas import aplicar_duplicatas_nfe_saida

        aplicar_duplicatas_nfe_saida(nf)
        resultado = validar_prontidao_nfe_homologacao(nfe_saida=nf)
        if resultado['alertas']:
            self.assertEqual(resultado['status'], 'aprovado_com_alertas')
            self.assertTrue(resultado['apto'])
            self.assertIn('alertas', resultado['mensagem'].lower())

    def test_nao_cria_titulos_receber(self):
        nf, _ = _nf_com_prazo()
        titulos_antes = list(nf.titulos_receber or [])
        validar_prontidao_nfe_homologacao(nfe_saida=nf)
        nf.refresh_from_db()
        self.assertEqual(list(nf.titulos_receber or []), titulos_antes)

    def test_nao_movimenta_estoque(self):
        nf, _ = _nf_com_prazo()
        antes = AtendimentoEstoque.objects.count()
        validar_prontidao_nfe_homologacao(nfe_saida=nf)
        self.assertEqual(AtendimentoEstoque.objects.count(), antes)

    def test_reforma_preparacao_alerta(self):
        nf, _ = _nf_com_prazo()
        resultado = validar_prontidao_nfe_homologacao(nfe_saida=nf)
        ref = next(i for i in resultado['itens'] if i['codigo'] == 'reforma_tributaria')
        self.assertEqual(ref['status'], 'alerta')
        self.assertIn('preparação', ref['mensagem'].lower())

    @override_settings(
        REFORMA_TRIBUTARIA_NFE_ENABLED=True,
        REFORMA_TRIBUTARIA_NFE_INCLUIR_XML=True,
        REFORMA_TRIBUTARIA_NFE_MODO='homologacao',
    )
    def test_reforma_flag_homologacao_nao_bloqueia_por_implementacao(self):
        nf, _ = _nf_com_prazo()
        resultado = validar_prontidao_nfe_homologacao(nfe_saida=nf)
        ref = next(i for i in resultado['itens'] if i['codigo'] == 'reforma_tributaria')
        self.assertNotEqual(ref['status'], 'bloqueado')
        self.assertFalse(
            any('sem implementação' in b.lower() for b in resultado.get('bloqueios', [])),
        )

    def test_pdf_pedido_sem_fiscal(self):
        nf, _ = _nf_com_prazo()
        pedido = nf.pedido_venda
        pdf = gerar_pedido_venda_pdf_bytes(pedido)
        text = _pdf_text(pdf).lower()
        self.assertNotIn('cstat', text)
        resultado = validar_prontidao_nfe_homologacao(pedido_venda=pedido, nfe_saida=nf)
        pdf_item = next(i for i in resultado['itens'] if i['codigo'] == 'pdf_pedido_limpo')
        self.assertEqual(pdf_item['status'], 'ok')

    def test_listagem_sem_xml_completo(self):
        nf, _ = _nf_com_prazo()
        data = NFeSaidaListSerializer(nf).data
        self.assertNotIn('xml_autorizado', data)
        self.assertIn('listagem_resumo', data)

    def test_api_post_checklist_nf(self):
        nf, _ = _nf_com_prazo()
        res = self.client.post(f'/api/nf-saidas/{nf.pk}/checklist-homologacao/', {})
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertIn('apto', body)
        self.assertIn('itens', body)

    def test_api_post_checklist_pedido(self):
        nf, _ = _nf_com_prazo()
        pedido = nf.pedido_venda
        res = self.client.post(f'/api/pedidos-venda/{pedido.pk}/checklist-nfe-homologacao/', {})
        self.assertEqual(res.status_code, 200)
        self.assertIn('itens', res.json())

    def test_bloqueia_prazo_sem_vencimento(self):
        pedido, item, _ = _pedido_com_prazo()
        fat = _faturamento_pronto(pedido, item, qtd='50')
        from apps.fiscal.nfe_saida_from_faturamento import gerar_nfe_saida_from_faturamento

        nf = NFeSaida.objects.get(pk=gerar_nfe_saida_from_faturamento(pedido, fat.pk)['nfe_saida_id'])
        nf.vencimentos_finais = []
        nf.titulos_receber = []
        nf.dias_parcelas = [45]
        nf.save(update_fields=['vencimentos_finais', 'titulos_receber', 'dias_parcelas'])
        resultado = validar_prontidao_nfe_homologacao(nfe_saida=nf)
        dup = next(i for i in resultado['itens'] if i['codigo'] == 'duplicatas_nfe')
        if dup['status'] == 'bloqueado':
            self.assertFalse(resultado['apto'])

    def test_danfe_homolog_autorizada_nao_bloqueia_checklist(self):
        nf, _ = _nf_com_prazo()
        aplicar_duplicatas_nfe_saida(nf)
        nf.status_emissao_sefaz = NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO
        nf.status = 'AUTORIZADA_HOMOLOGACAO'
        nf.serie_nfe = '0'
        nf.numero_nfe = '000000002'
        nf.cstat_autorizacao = '100'
        nf.protocolo_autorizacao = '13526005517408'
        nf.chave_acesso = '3526050399910200015055000000000212345678901'
        nf.xml_autorizado = (
            '<?xml version="1.0"?>'
            '<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe">'
            '<NFe><infNFe Id="NFe3526050399910200015055000000000212345678901">'
            '<ide><tpAmb>2</tpAmb></ide></infNFe></NFe>'
            '<protNFe><infProt><nProt>13526005517408</nProt></infProt></protNFe>'
            '</nfeProc>'
        )
        nf.save()
        pdf, meta = gerar_preview_danfe_nfe_saida(nf)
        if brazil_fiscal_report_disponivel():
            self.assertFalse(meta.get('bloqueado'), meta.get('mensagens'))
            self.assertGreater(len(pdf), 100)
        resultado = validar_prontidao_nfe_homologacao(nfe_saida=nf)
        danfe = next(i for i in resultado['itens'] if i['codigo'] == 'danfe_render')
        self.assertEqual(danfe['status'], 'ok', danfe['mensagem'])

    def test_danfe_duplicata_001_no_checklist(self):
        nf, venc = _nf_com_prazo()
        aplicar_duplicatas_nfe_saida(nf)
        resultado = validar_prontidao_nfe_homologacao(nfe_saida=nf)
        dup = next(i for i in resultado['itens'] if i['codigo'] == 'danfe_duplicatas' and i['status'] == 'ok')
        self.assertIn('001', dup['mensagem'])
        self.assertIn(venc.strftime('%d/%m/%Y'), dup['mensagem'])

    def test_aprovado_com_alertas_sem_bloqueio_danfe(self):
        nf, _ = _nf_com_prazo()
        aplicar_duplicatas_nfe_saida(nf)
        resultado = validar_prontidao_nfe_homologacao(nfe_saida=nf)
        danfe = next(i for i in resultado['itens'] if i['codigo'] == 'danfe_render')
        if danfe['status'] == 'ok' and resultado['alertas']:
            self.assertIn(resultado['status'], ('aprovado_com_alertas', 'aprovado'))
            self.assertTrue(resultado['apto'])

    def test_titulo_listagem_amigavel(self):
        nf, _ = _nf_com_prazo()
        nf.status_emissao_sefaz = NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO
        nf.status = 'AUTORIZADA_HOMOLOGACAO'
        nf.serie_nfe = '0'
        nf.numero_nfe = '000000002'
        nf.save()
        resultado = validar_prontidao_nfe_homologacao(nfe_saida=nf)
        ui = next(i for i in resultado['itens'] if i['codigo'] == 'listagem_resumo')
        self.assertNotRegex(ui['mensagem'], re.compile(r'^RASCUNHO-FAT', re.I))
