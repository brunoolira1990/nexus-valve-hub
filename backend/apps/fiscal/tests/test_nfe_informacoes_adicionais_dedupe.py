"""Deduplicação idempotente de informações adicionais / infCpl da NF-e Saída.

Cobre composição central, merge de Atualizar fiscal, API de conferência,
XML preliminar e dados do DANFE — sem alterar documento autorizado.
"""

from __future__ import annotations

import re
import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.comercial.faturamento_pedido_venda import confirmar_faturamento_pedido, criar_faturamento_pedido
from apps.comercial.models import ItemPedidoVenda
from apps.fiscal.models import ItemNFeSaida, NFeSaida
from apps.fiscal.nfe_informacoes_adicionais import (
    deduplicar_texto_informacoes_adicionais,
    dividir_blocos_texto,
    mesclar_textos_informacoes_adicionais,
)
from apps.fiscal.nfe_integracao.danfe_xml_adicionais import (
    montar_inf_cpl_nfe,
    montar_inf_cpl_para_danfe,
    montar_linhas_inf_cpl_nfe,
)
from apps.fiscal.nfe_integracao.nfe_xml_preliminar import gerar_xml_nfe_preliminar
from apps.fiscal.nfe_saida_atualizar_impostos import aplicar_atualizacao_impostos_nfe
from apps.fiscal.nfe_saida_conferencia import montar_conferencia_nfe_saida
from apps.fiscal.nfe_saida_from_faturamento import gerar_nfe_saida_from_faturamento
from apps.fiscal.nfe_saida_textos_fiscais import (
    _combinar_textos_de_regras,
    aplicar_textos_fiscais_nf,
    mesclar_texto_campo,
)
from apps.fiscal.tests.test_nfe_saida_401_bfr_preliminar import _nf_pronta, _regra
from apps.fiscal.tests.test_nfe_saida_faturamento import _pedido_item, _produto
from apps.regras_fiscais.cenario_fiscal_saida import garantir_cenario_saida_padrao
from apps.regras_fiscais.models import CenarioFiscalSaidaEscopo, RegraFiscalSaida

TEXTO_DEVOLUCAO = 'NÃO ACEITAREMOS DEVOLUÇÃO APÓS 7 DIAS DA ENTREGA.'
TEXTO_BASE_CALCULO = 'Base de cálculo reduzida conforme Artigo 12.'
TEXTO_FUNDAMENTO_A = 'Operação com redução de base conforme legislação estadual A.'
TEXTO_FUNDAMENTO_B = 'Diferimento parcial do ICMS conforme legislação estadual B.'


def _regra_ncm(ncm: str, *, nome: str, informacoes: str) -> RegraFiscalSaida:
    cenario = garantir_cenario_saida_padrao()
    escopo, _ = CenarioFiscalSaidaEscopo.objects.get_or_create(
        cenario=cenario,
        tipo_escopo=CenarioFiscalSaidaEscopo.TipoEscopo.NCM,
        ncm=ncm,
        defaults={},
    )
    regra, _ = RegraFiscalSaida.objects.update_or_create(
        escopo=escopo,
        cenario=cenario,
        uf_origem='SP',
        uf_destino='RJ',
        destinatario_contribuinte=RegraFiscalSaida.DestinatarioContribuinte.QUALQUER,
        defaults={
            'nome': nome,
            'cfop_venda': '5102',
            'cst_icms': '00',
            'aliquota_icms': Decimal('18'),
            'cst_pis': '01',
            'aliquota_pis': Decimal('1.65'),
            'cst_cofins': '01',
            'aliquota_cofins': Decimal('7.6'),
            'informacoes_complementares': informacoes,
        },
    )
    return regra


def _inf_cpl_xml(nf: NFeSaida) -> str:
    xml = gerar_xml_nfe_preliminar(nf).decode('utf-8')
    m = re.search(r'<[\w:]*infCpl>([^<]*)</[\w:]*infCpl>', xml, flags=re.IGNORECASE)
    return m.group(1) if m else ''


@override_settings(USE_CENARIO_FISCAL_SAIDA_FOR_PROPOSTAS=True)
class DeduplicacaoInformacoesAdicionaisUnitTests(TestCase):
    def test_uma_fonte_com_texto_uma_vez(self):
        self.assertEqual(
            deduplicar_texto_informacoes_adicionais(TEXTO_DEVOLUCAO),
            TEXTO_DEVOLUCAO,
        )

    def test_duas_fontes_mesmo_texto(self):
        entrada = f'{TEXTO_DEVOLUCAO}\n\n{TEXTO_DEVOLUCAO}'
        self.assertEqual(deduplicar_texto_informacoes_adicionais(entrada), TEXTO_DEVOLUCAO)

    def test_mesmo_texto_com_espacos_diferentes(self):
        a = '  NÃO ACEITAREMOS DEVOLUÇÃO APÓS 7 DIAS DA ENTREGA.  '
        b = 'NÃO ACEITAREMOS   DEVOLUÇÃO APÓS 7 DIAS DA ENTREGA.'
        resultado = deduplicar_texto_informacoes_adicionais(f'{a}\n\n{b}')
        self.assertEqual(resultado.count('NÃO ACEITAREMOS'), 1)

    def test_mesmo_texto_com_quebras_diferentes(self):
        b = TEXTO_DEVOLUCAO
        repetido_crlf = b + '\r\n\r\n' + b
        self.assertEqual(deduplicar_texto_informacoes_adicionais(repetido_crlf), b)
        misto = b.replace(' ', '  ') + '\r\n\r\n' + b
        self.assertEqual(deduplicar_texto_informacoes_adicionais(misto).count('NÃO ACEITAREMOS'), 1)

    def test_textos_parcialmente_semelhantes_permanecem(self):
        a = 'NÃO ACEITAREMOS DEVOLUÇÃO APÓS 7 DIAS DA ENTREGA.'
        b = 'NÃO ACEITAREMOS DEVOLUÇÃO APÓS 15 DIAS DA ENTREGA.'
        resultado = deduplicar_texto_informacoes_adicionais(f'{a}\n\n{b}')
        self.assertIn(a, resultado)
        self.assertIn(b, resultado)

    def test_fundamentos_legais_distintos_permanecem(self):
        resultado = deduplicar_texto_informacoes_adicionais(
            f'{TEXTO_FUNDAMENTO_A}\n\n{TEXTO_FUNDAMENTO_B}',
        )
        self.assertIn(TEXTO_FUNDAMENTO_A, resultado)
        self.assertIn(TEXTO_FUNDAMENTO_B, resultado)

    def test_mesclar_nao_reanexa_bloco_ja_presente_em_sugestao_composta(self):
        """Causa raiz: atual=A e novo=A\\n\\nB não pode virar A + sep + A + B."""
        depois, mudou = mesclar_texto_campo(
            TEXTO_DEVOLUCAO,
            f'{TEXTO_DEVOLUCAO}\n\n{TEXTO_BASE_CALCULO}',
        )
        self.assertTrue(mudou)
        self.assertEqual(depois.count(TEXTO_DEVOLUCAO), 1)
        self.assertIn(TEXTO_BASE_CALCULO, depois)

    def test_idempotencia_processar_duas_vezes(self):
        entrada = f'{TEXTO_DEVOLUCAO}\n\n{TEXTO_DEVOLUCAO}\n\n{TEXTO_BASE_CALCULO}'
        uma = deduplicar_texto_informacoes_adicionais(entrada)
        duas = deduplicar_texto_informacoes_adicionais(uma)
        self.assertEqual(uma, duas)
        self.assertEqual(uma.count(TEXTO_DEVOLUCAO), 1)
        mescla1, _ = mesclar_textos_informacoes_adicionais(uma, TEXTO_DEVOLUCAO)
        mescla2, mudou2 = mesclar_textos_informacoes_adicionais(mescla1, TEXTO_DEVOLUCAO)
        self.assertFalse(mudou2)
        self.assertEqual(mescla1, mescla2)

    def test_combinar_regras_mesmo_texto_com_espacos(self):
        r1 = _regra_ncm('84818200', nome='R1', informacoes=TEXTO_DEVOLUCAO)
        r2 = _regra_ncm(
            '84818099',
            nome='R2',
            informacoes=f'  {TEXTO_DEVOLUCAO}  ',
        )
        combinado = _combinar_textos_de_regras([r1, r2], 'informacoes_complementares')
        self.assertEqual(combinado.count('NÃO ACEITAREMOS'), 1)


@override_settings(USE_CENARIO_FISCAL_SAIDA_FOR_PROPOSTAS=True)
class DeduplicacaoInformacoesAdicionaisIntegracaoTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('nfeinfcpl', 'nfeinfcpl@test.com', 'x')
        self.client_api = APIClient()
        self.client_api.force_authenticate(self.user)
        _regra()
        _regra_ncm('84818200', nome='Venda flanges', informacoes=TEXTO_DEVOLUCAO)

    def _nf_rascunho_para_atualizar(self) -> tuple[NFeSaida, ItemNFeSaida]:
        """NF com snapshot vazio — permite Aplicar Atualizar fiscal (padrão 3.5.2)."""
        pedido, item = _pedido_item(qtd=Decimal('2'), preco=Decimal('100'))
        item.snapshot_fiscal = {'ncm': '84818200'}
        item.save(update_fields=['snapshot_fiscal'])
        criado = criar_faturamento_pedido(
            pedido,
            {'itens': [{'item_pedido_id': item.pk, 'quantidade': '2'}]},
        )
        confirmar_faturamento_pedido(pedido, criado['faturamento_id'])
        r = gerar_nfe_saida_from_faturamento(pedido, criado['faturamento_id'])
        nf = NFeSaida.objects.prefetch_related('itens__produto').get(pk=r['nfe_saida_id'])
        nf_item = nf.itens.first()
        assert nf_item is not None
        nf_item.snapshot_fiscal = {}
        nf_item.save(update_fields=['snapshot_fiscal'])
        return nf, nf_item

    def _nf_dois_ncms_rascunho(self) -> NFeSaida:
        _regra_ncm('84818099', nome='Venda valvulas', informacoes=TEXTO_DEVOLUCAO)
        pedido, item1 = _pedido_item(qtd=Decimal('10'), preco=Decimal('100'))
        item1.snapshot_fiscal = {'ncm': '84818200'}
        item1.save(update_fields=['snapshot_fiscal'])

        prod2 = _produto()
        prod2.ncm = '84818099'
        prod2.codigo_completo = f'NF2-{uuid.uuid4().hex[:6].upper()}'
        prod2.save(update_fields=['ncm', 'codigo_completo'])
        item2 = ItemPedidoVenda.objects.create(
            pedido=pedido,
            produto=prod2,
            quantidade=Decimal('5'),
            quantidade_negociada=Decimal('5'),
            valor_unitario=Decimal('50'),
            preco_por_unidade_negociada=Decimal('50'),
            snapshot_fiscal={'ncm': '84818099'},
        )
        criado = criar_faturamento_pedido(
            pedido,
            {
                'itens': [
                    {'item_pedido_id': item1.pk, 'quantidade': '2'},
                    {'item_pedido_id': item2.pk, 'quantidade': '3'},
                ],
            },
        )
        confirmar_faturamento_pedido(pedido, criado['faturamento_id'])
        r = gerar_nfe_saida_from_faturamento(pedido, criado['faturamento_id'])
        nf = NFeSaida.objects.prefetch_related('itens__produto').get(pk=r['nfe_saida_id'])
        for it in nf.itens.all():
            it.snapshot_fiscal = {'ncm': (it.snapshot_fiscal or {}).get('ncm') or it.produto.ncm}
            it.save(update_fields=['snapshot_fiscal'])
        return nf

    def test_nfe_dois_ncms_geral_igual_e_fundamentos_distintos_sem_alterar_fiscal(self):
        """Um cenário: info geral idêntica + fundamentos distintos; impostos intactos."""
        nf = self._nf_dois_ncms_rascunho()
        self.assertGreaterEqual(nf.itens.count(), 2)
        # Snapshot fiscal “congelado” para provar que a dedupe não o altera.
        for it in nf.itens.all():
            ncm = (it.snapshot_fiscal or {}).get('ncm') or it.produto.ncm
            it.snapshot_fiscal = {
                'ncm': ncm,
                'cfop': '5102',
                'cst_icms': '00',
                'aliquota_icms': '18',
                'valor_icms': '10.00',
            }
            it.save(update_fields=['snapshot_fiscal'])
        snaps_antes = {
            it.pk: dict(it.snapshot_fiscal or {})
            for it in nf.itens.all()
        }
        r_a = _regra_ncm(
            '84818200',
            nome='Venda flanges',
            informacoes=f'{TEXTO_DEVOLUCAO}\n\n{TEXTO_FUNDAMENTO_A}',
        )
        r_b = _regra_ncm(
            '84818099',
            nome='Venda valvulas',
            informacoes=f'{TEXTO_DEVOLUCAO}\n\n{TEXTO_FUNDAMENTO_B}',
        )
        campos, _, _ = aplicar_textos_fiscais_nf(nf, [r_a, r_b])
        self.assertTrue(campos)
        nf.save(update_fields=list(campos.keys()))
        nf.refresh_from_db()
        self.assertEqual(nf.informacoes_adicionais.count(TEXTO_DEVOLUCAO), 1)
        self.assertIn(TEXTO_FUNDAMENTO_A, nf.informacoes_adicionais)
        self.assertIn(TEXTO_FUNDAMENTO_B, nf.informacoes_adicionais)
        for it in nf.itens.all():
            it.refresh_from_db()
            self.assertEqual(it.snapshot_fiscal, snaps_antes[it.pk])
            self.assertEqual(it.snapshot_fiscal.get('cfop'), '5102')
            self.assertEqual(it.snapshot_fiscal.get('cst_icms'), '00')
            self.assertEqual(str(it.snapshot_fiscal.get('ncm')), snaps_antes[it.pk]['ncm'])

    def test_nfe_multiplos_ncms_texto_geral_duplicado_uma_ocorrencia(self):
        _regra_ncm('84818200', nome='Venda flanges', informacoes=TEXTO_DEVOLUCAO)
        _regra_ncm('84818099', nome='Venda valvulas', informacoes=TEXTO_DEVOLUCAO)
        nf = self._nf_dois_ncms_rascunho()
        self.assertGreaterEqual(nf.itens.count(), 2)
        regras = [
            RegraFiscalSaida.objects.get(escopo__ncm='84818200', uf_destino='RJ'),
            RegraFiscalSaida.objects.get(escopo__ncm='84818099', uf_destino='RJ'),
        ]
        for _ in range(2):
            campos, _, _ = aplicar_textos_fiscais_nf(nf, regras)
            if campos:
                nf.save(update_fields=list(campos.keys()))
            nf.refresh_from_db()
        self.assertEqual(nf.informacoes_adicionais.count(TEXTO_DEVOLUCAO), 1)

    def test_nfe_multiplos_ncms_textos_fiscais_diferentes_preservados(self):
        nf = self._nf_dois_ncms_rascunho()
        r_a = _regra_ncm('84818200', nome='Venda flanges', informacoes=TEXTO_FUNDAMENTO_A)
        r_b = _regra_ncm('84818099', nome='Venda valvulas', informacoes=TEXTO_FUNDAMENTO_B)
        campos, _, _ = aplicar_textos_fiscais_nf(nf, [r_a, r_b])
        self.assertTrue(campos)
        nf.save(update_fields=list(campos.keys()))
        nf.refresh_from_db()
        self.assertIn(TEXTO_FUNDAMENTO_A, nf.informacoes_adicionais)
        self.assertIn(TEXTO_FUNDAMENTO_B, nf.informacoes_adicionais)
        self.assertEqual(nf.informacoes_adicionais.count(TEXTO_FUNDAMENTO_A), 1)
        self.assertEqual(nf.informacoes_adicionais.count(TEXTO_FUNDAMENTO_B), 1)
        # Reaplicar não duplica.
        campos2, _, _ = aplicar_textos_fiscais_nf(nf, [r_a, r_b])
        if campos2:
            nf.save(update_fields=list(campos2.keys()))
        nf.refresh_from_db()
        self.assertEqual(nf.informacoes_adicionais.count(TEXTO_FUNDAMENTO_A), 1)
        self.assertEqual(nf.informacoes_adicionais.count(TEXTO_FUNDAMENTO_B), 1)

    def test_atualizar_fiscal_repetido_nao_duplica(self):
        nf, _ = self._nf_rascunho_para_atualizar()
        for _ in range(3):
            # Após a 1ª aplicação, impostos já batem — força só textos via helper idempotente.
            regras = list(RegraFiscalSaida.objects.filter(escopo__ncm='84818200'))
            campos, _, _ = aplicar_textos_fiscais_nf(nf, regras)
            if campos:
                nf.save(update_fields=list(campos.keys()))
            nf.refresh_from_db()
        # Primeira rodada com Atualizar fiscal completo.
        nf2, _ = self._nf_rascunho_para_atualizar()
        aplicar_atualizacao_impostos_nfe(nf2, usuario=self.user)
        nf2.refresh_from_db()
        self.assertEqual(nf2.informacoes_adicionais.count(TEXTO_DEVOLUCAO), 1)
        regras = list(RegraFiscalSaida.objects.filter(escopo__ncm='84818200'))
        for _ in range(2):
            campos, _, _ = aplicar_textos_fiscais_nf(nf2, regras)
            if campos:
                nf2.save(update_fields=list(campos.keys()))
            nf2.refresh_from_db()
        self.assertEqual(nf2.informacoes_adicionais.count(TEXTO_DEVOLUCAO), 1)
        self.assertEqual(nf.informacoes_adicionais.count(TEXTO_DEVOLUCAO), 1)

    def test_api_conferencia_retorna_unica_ocorrencia(self):
        nf, _ = self._nf_rascunho_para_atualizar()
        nf.informacoes_adicionais = f'{TEXTO_DEVOLUCAO}\n\n{TEXTO_DEVOLUCAO}'
        nf.save(update_fields=['informacoes_adicionais'])
        regras = list(RegraFiscalSaida.objects.filter(escopo__ncm='84818200'))
        campos, _, _ = aplicar_textos_fiscais_nf(nf, regras)
        if campos:
            nf.save(update_fields=list(campos.keys()))
        nf.refresh_from_db()
        conf = montar_conferencia_nfe_saida(nf)
        texto = conf['observacoes']['informacoes_adicionais']
        self.assertEqual(texto.count(TEXTO_DEVOLUCAO), 1)

    def test_salvar_conferencia_deduplica_campo(self):
        nf, _ = self._nf_rascunho_para_atualizar()
        duplicado = f'{TEXTO_DEVOLUCAO}\n\n{TEXTO_DEVOLUCAO}'
        resp = self.client_api.post(
            f'/api/nf-saidas/{nf.pk}/salvar-conferencia/',
            {'informacoes_adicionais': duplicado},
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        nf.refresh_from_db()
        self.assertEqual(nf.informacoes_adicionais.count(TEXTO_DEVOLUCAO), 1)
        conf = montar_conferencia_nfe_saida(nf)
        self.assertEqual(conf['observacoes']['informacoes_adicionais'].count(TEXTO_DEVOLUCAO), 1)

    def test_xml_preliminar_unica_ocorrencia(self):
        """infCpl do XML usa montar_inf_cpl_nfe — mesma composição do gerador preliminar."""
        from apps.fiscal.nfe_integracao.nfe_xml_preliminar import NFeXmlPreliminarError

        regra = _regra()
        regra.informacoes_complementares = TEXTO_DEVOLUCAO
        regra.save(update_fields=['informacoes_complementares'])
        nf = _nf_pronta()
        nf.informacoes_adicionais = TEXTO_DEVOLUCAO
        nf.save(update_fields=['informacoes_adicionais'])
        inf_cpl, _ = montar_inf_cpl_nfe(nf)
        self.assertEqual(inf_cpl.upper().count(TEXTO_DEVOLUCAO.upper()), 1)
        try:
            inf_cpl_xml = _inf_cpl_xml(nf)
        except NFeXmlPreliminarError:
            return
        self.assertEqual(inf_cpl_xml.upper().count(TEXTO_DEVOLUCAO.upper()), 1)

    def test_danfe_dados_unica_ocorrencia(self):
        regra = _regra()
        regra.informacoes_complementares = TEXTO_DEVOLUCAO
        regra.save(update_fields=['informacoes_complementares'])
        nf = _nf_pronta()
        nf.informacoes_adicionais = TEXTO_DEVOLUCAO
        nf.save(update_fields=['informacoes_adicionais'])
        danfe = montar_inf_cpl_para_danfe(nf)
        self.assertEqual(danfe.upper().count(TEXTO_DEVOLUCAO.upper()), 1)
        xml_txt, _ = montar_inf_cpl_nfe(nf)
        self.assertEqual(xml_txt.upper().count(TEXTO_DEVOLUCAO.upper()), 1)

    def test_documento_autorizado_nao_e_modificado(self):
        nf, _ = self._nf_rascunho_para_atualizar()
        duplicado = f'{TEXTO_DEVOLUCAO}\n\n{TEXTO_DEVOLUCAO}'
        xml_aut = '<nfeProc>XML-AUTORIZADO-NAO-ALTERAR</nfeProc>'
        nf.informacoes_adicionais = duplicado
        nf.xml_autorizado = xml_aut
        nf.protocolo_autorizacao = '135250000000001'
        nf.status = 'AUTORIZADA_INTERNA'
        nf.save(update_fields=[
            'informacoes_adicionais',
            'xml_autorizado',
            'protocolo_autorizacao',
            'status',
        ])
        antes_info = nf.informacoes_adicionais
        antes_xml = nf.xml_autorizado

        resp = self.client_api.post(
            f'/api/nf-saidas/{nf.pk}/salvar-conferencia/',
            {'informacoes_adicionais': f'{duplicado}\n\nEXTRA'},
            format='json',
        )
        self.assertIn(resp.status_code, (400, 403), resp.content)

        with self.assertRaises(ValueError):
            aplicar_atualizacao_impostos_nfe(nf, usuario=self.user)

        nf.refresh_from_db()
        self.assertEqual(nf.informacoes_adicionais, antes_info)
        self.assertEqual(nf.informacoes_adicionais.count(TEXTO_DEVOLUCAO), 2)
        self.assertEqual(nf.xml_autorizado, antes_xml)
        self.assertEqual(nf.protocolo_autorizacao, '135250000000001')

    def test_salvar_reabrir_nao_reintroduz_duplicata(self):
        nf, _ = self._nf_rascunho_para_atualizar()
        duplicado = f'{TEXTO_DEVOLUCAO}\n\n{TEXTO_DEVOLUCAO}'
        resp = self.client_api.post(
            f'/api/nf-saidas/{nf.pk}/salvar-conferencia/',
            {'informacoes_adicionais': duplicado},
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        nf.refresh_from_db()
        self.assertEqual(nf.informacoes_adicionais.count(TEXTO_DEVOLUCAO), 1)
        # Reabrir conferência (GET) e salvar de novo sem alteração.
        conf1 = montar_conferencia_nfe_saida(nf)
        texto1 = conf1['observacoes']['informacoes_adicionais']
        resp2 = self.client_api.post(
            f'/api/nf-saidas/{nf.pk}/salvar-conferencia/',
            {'informacoes_adicionais': texto1},
            format='json',
        )
        self.assertEqual(resp2.status_code, 200, resp2.content)
        nf.refresh_from_db()
        conf2 = montar_conferencia_nfe_saida(nf)
        self.assertEqual(conf2['observacoes']['informacoes_adicionais'], texto1)
        self.assertEqual(conf2['observacoes']['informacoes_adicionais'].count(TEXTO_DEVOLUCAO), 1)

    def test_primeira_ocorrencia_e_ordem_preservadas(self):
        entrada = f'{TEXTO_FUNDAMENTO_A}\n\n{TEXTO_DEVOLUCAO}\n\n{TEXTO_FUNDAMENTO_A}'
        resultado = deduplicar_texto_informacoes_adicionais(entrada)
        partes = [p for p in resultado.split('\n\n') if p.strip()]
        self.assertEqual(partes[0], TEXTO_FUNDAMENTO_A)
        self.assertEqual(partes[1], TEXTO_DEVOLUCAO)
        self.assertEqual(len(partes), 2)

    def test_paragrafos_com_linha_apenas_semelhante_nao_sao_fundidos(self):
        a = 'Base de cálculo reduzida conforme Artigo 12.'
        b = 'Base de cálculo reduzida conforme Artigo 13.'
        resultado = deduplicar_texto_informacoes_adicionais(f'{a}\n\n{b}')
        self.assertIn(a, resultado)
        self.assertIn(b, resultado)

    def test_dois_blocos_distintos_compartilhando_linha_identica_comportamento_atual(self):
        """
        Informações distintas usam linha em branco; linha idêntica repetida é removida.

        Blocos fiscais distintos NÃO são fundidos num único fundamento — apenas a
        linha duplicada deixa de repetir.
        """
        bloco_a = (
            'Fundamento fiscal do NCM A\n\n'
            'Linha comum legítima\n\n'
            'Complemento exclusivo A'
        )
        bloco_b = (
            'Fundamento fiscal do NCM B\n\n'
            'Linha comum legítima\n\n'
            'Complemento exclusivo B'
        )
        resultado = deduplicar_texto_informacoes_adicionais(f'{bloco_a}\n\n{bloco_b}')
        self.assertIn('Fundamento fiscal do NCM A', resultado)
        self.assertIn('Fundamento fiscal do NCM B', resultado)
        self.assertIn('Complemento exclusivo A', resultado)
        self.assertIn('Complemento exclusivo B', resultado)
        self.assertEqual(resultado.count('Linha comum legítima'), 1)
        partes = [p for p in resultado.split('\n\n') if p.strip()]
        self.assertEqual(partes[0], 'Fundamento fiscal do NCM A')
        self.assertEqual(partes[1], 'Linha comum legítima')
        self.assertEqual(partes[2], 'Complemento exclusivo A')
        self.assertEqual(partes[3], 'Fundamento fiscal do NCM B')
        self.assertEqual(partes[4], 'Complemento exclusivo B')

    def test_clausula_comercial_soft_wrap_mediante_preserva_paragrafo(self):
        """Soft wrap após MEDIANTE não vira linha vazia; cláusula fica contínua."""
        clausula_quebrada = (
            'NÃO ACEITAREMOS DEVOLUÇÃO APÓS 7 DIAS DA ENTREGA. A DEVOLUÇÃO SÓ PODERÁ '
            'OCORRER MEDIANTE\n'
            'COMUNICAÇÃO PRÉVIA E AUTORIZAÇÃO DO DEPARTAMENTO COMERCIAL. '
            'NOSSOS PRODUTOS NÃO SE DESTINAM A MATERIAIS DE CONSTRUÇÃO E CONGÊNERES DO '
            'ARTIGO 313-Y DO RICMS/SP.'
        )
        clausula_ja_partida = (
            'NÃO ACEITAREMOS DEVOLUÇÃO APÓS 7 DIAS DA ENTREGA. A DEVOLUÇÃO SÓ PODERÁ '
            'OCORRER MEDIANTE\n\n'
            'COMUNICAÇÃO PRÉVIA E AUTORIZAÇÃO DO DEPARTAMENTO COMERCIAL. '
            'NOSSOS PRODUTOS NÃO SE DESTINAM A MATERIAIS DE CONSTRUÇÃO E CONGÊNERES DO '
            'ARTIGO 313-Y DO RICMS/SP.'
        )
        fundamento = (
            'Base de cálculo reduzida conforme Artigo 12 do Anexo II do RICMS/SP '
            'e Convênio ICMS 52/91.'
        )
        clausula_continua = (
            'NÃO ACEITAREMOS DEVOLUÇÃO APÓS 7 DIAS DA ENTREGA. A DEVOLUÇÃO SÓ PODERÁ '
            'OCORRER MEDIANTE COMUNICAÇÃO PRÉVIA E AUTORIZAÇÃO DO DEPARTAMENTO '
            'COMERCIAL. NOSSOS PRODUTOS NÃO SE DESTINAM A MATERIAIS DE CONSTRUÇÃO E '
            'CONGÊNERES DO ARTIGO 313-Y DO RICMS/SP.'
        )
        for entrada_base in (clausula_quebrada, clausula_ja_partida):
            entrada = f'{entrada_base}\n\n{fundamento}\n\n{clausula_quebrada}'
            resultado = deduplicar_texto_informacoes_adicionais(entrada)

            self.assertEqual(resultado.count('NÃO ACEITAREMOS DEVOLUÇÃO'), 1)
            self.assertEqual(resultado.count('313-Y DO RICMS/SP.'), 1)
            self.assertIn(clausula_continua, resultado)
            self.assertIn(fundamento, resultado)
            self.assertNotIn('MEDIANTE\n\nCOMUNICAÇÃO', resultado)
            self.assertNotIn('MEDIANTE\nCOMUNICAÇÃO', resultado)
            partes = [p for p in resultado.split('\n\n') if p.strip()]
            self.assertEqual(len(partes), 2)
            self.assertEqual(partes[0], clausula_continua)
            self.assertEqual(partes[1], fundamento)
            self.assertEqual(deduplicar_texto_informacoes_adicionais(resultado), resultado)

            # Mesma estrutura deve chegar ao compositor do DANFE/infCpl.
            from apps.fiscal.nfe_integracao.danfe_xml_adicionais import deduplicar_textos_inf_cpl
            blocos_danfe = deduplicar_textos_inf_cpl([entrada_base, fundamento, clausula_quebrada])
            self.assertEqual(len(blocos_danfe), 2)
            self.assertEqual(blocos_danfe[0], clausula_continua)
            self.assertEqual(blocos_danfe[1], fundamento)

    def test_igualdade_caixa_acentos_espacos_pontuacao(self):
        """Decisão funcional registrada: o que conta como duplicata na chave."""
        # Caixa: duplicata (chave casefold) — preserva a primeira ocorrência original.
        r = deduplicar_texto_informacoes_adicionais('Texto Fiscal\n\nTEXTO FISCAL')
        self.assertEqual(r, 'Texto Fiscal')
        # Acentos: duplicata na chave (NFKD) — preserva a primeira com acento.
        r = deduplicar_texto_informacoes_adicionais('Operação tributada\n\nOperacao tributada')
        self.assertEqual(r, 'Operação tributada')
        # Espaços: duplicata — preserva normalização de espaços da primeira.
        r = deduplicar_texto_informacoes_adicionais(
            '  NÃO ACEITAREMOS DEVOLUÇÃO.  \n\nNÃO ACEITAREMOS   DEVOLUÇÃO.',
        )
        self.assertEqual(r.count('NÃO ACEITAREMOS'), 1)
        # Pontuação diferente: NÃO é duplicata.
        r = deduplicar_texto_informacoes_adicionais(
            'Não aceitaremos devolução\n\nNão aceitaremos devolução.',
        )
        self.assertIn('Não aceitaremos devolução', r)
        self.assertIn('Não aceitaremos devolução.', r)

    def test_fontes_regra_manual_cliente_pedido_sem_duplicar_unidades(self):
        """
        Reprodução do DANFE pós-3d8d731: regra cola fundamento+cláusula;
        manual já tem a cláusula; cliente tem horário; pedido no cabeçalho;
        variação R.ICMS × RICMS não deve duplicar a base.
        """
        clausula = (
            'NÃO ACEITAREMOS DEVOLUÇÃO APÓS 7 DIAS DA ENTREGA. A DEVOLUÇÃO SÓ PODERÁ '
            'OCORRER MEDIANTE COMUNICAÇÃO PRÉVIA E AUTORIZAÇÃO DO DEPARTAMENTO '
            'COMERCIAL. NOSSOS PRODUTOS NÃO SE DESTINAM A MATERIAIS DE CONSTRUÇÃO E '
            'CONGÊNERES DO ARTIGO 313-Y DO RICMS/SP.'
        )
        base_ricms = (
            'Base de cálculo reduzida conforme Artigo 12 do Anexo II do RICMS/SP '
            'e Convênio ICMS 52/91.'
        )
        base_r_icms = (
            'Base de cálculo reduzida conforme Artigo 12 do Anexo II do R.ICMS/SP '
            'e Convênio ICMS 52/91.'
        )
        # Regra: fundamento + cláusula colados com quebra simples após o ponto.
        texto_regra = f'{base_r_icms}\n{clausula}'
        horario = (
            'Endereço de entrega Rua Miguel Langone 341 - '
            'Horário de entrega da 7:00 as 15:00 horas'
        )
        # Persistido: cláusula (já deduplicada) + base com RICMS sem ponto.
        persistido = f'{clausula}\n\n{base_ricms}'

        # 1) Separação estrutural da regra colada.
        unidades_regra = dividir_blocos_texto(texto_regra)
        self.assertEqual(len(unidades_regra), 2)
        self.assertEqual(unidades_regra[0], base_r_icms)
        self.assertEqual(unidades_regra[1], clausula)
        # Cláusula comercial permanece uma unidade (não parte após COMERCIAL.).
        self.assertEqual(clausula.count('NOSSOS PRODUTOS'), 1)

        # 2) Composição multi-fonte como no DANFE/XML.
        _regra()
        nf = _nf_pronta()
        regra = RegraFiscalSaida.objects.filter(cfop_venda='5102').first()
        self.assertIsNotNone(regra)
        regra.informacoes_complementares = texto_regra
        regra.save(update_fields=['informacoes_complementares'])
        nf.cliente.informacoes_complementares_nfe = horario
        nf.cliente.save(update_fields=['informacoes_complementares_nfe'])
        nf.informacoes_adicionais = persistido
        nf.pedido_cliente_numero = '5050'
        nf.save(update_fields=['informacoes_adicionais', 'pedido_cliente_numero'])

        # Garante item apontando à regra 5102 (NCM da fixture).
        item = nf.itens.first()
        snap = dict(item.snapshot_fiscal or {})
        snap['ncm'] = snap.get('ncm') or '84818000'
        item.snapshot_fiscal = snap
        item.save(update_fields=['snapshot_fiscal'])

        linhas = montar_linhas_inf_cpl_nfe(nf)
        danfe = montar_inf_cpl_para_danfe(nf)
        texto_danfe = '\n'.join(linhas)

        self.assertEqual(texto_danfe.upper().count('NÃO ACEITAREMOS DEVOLUÇÃO'), 1)
        self.assertEqual(texto_danfe.upper().count('BASE DE CÁLCULO REDUZIDA'), 1)
        self.assertEqual(sum(1 for ln in linhas if 'PEDIDO DE COMPRA: 5050' in ln), 1)
        self.assertEqual(sum(1 for ln in linhas if 'HORÁRIO DE ENTREGA' in ln or 'HORARIO DE ENTREGA' in ln), 1)
        self.assertNotIn('MEDIANTE\n\nCOMUNICAÇÃO', danfe)
        self.assertNotIn('MEDIANTE\nCOMUNICAÇÃO', danfe)
        # Preserva a primeira ocorrência da base (R.ICMS da regra), sem duplicar RICMS.
        self.assertTrue(
            any('R.ICMS/SP' in ln or 'RICMS/SP' in ln for ln in linhas),
        )
        self.assertEqual(
            sum(1 for ln in linhas if 'BASE DE CÁLCULO REDUZIDA' in ln.upper()),
            1,
        )
        # Fundamentos fiscais distintos (outros) não são removidos por engano.
        distinto = 'Fundamento fiscal exclusivo NCM Z — art. 99.'
        r = deduplicar_texto_informacoes_adicionais(f'{base_ricms}\n\n{distinto}\n\n{base_r_icms}')
        self.assertEqual(r.count('Base de cálculo reduzida'), 1)
        self.assertIn(distinto, r)
        self.assertEqual(deduplicar_texto_informacoes_adicionais(r), r)
