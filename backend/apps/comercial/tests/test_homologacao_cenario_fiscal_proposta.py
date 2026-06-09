"""Fase Saída 3.9 — homologação assistida de proposta com cenário fiscal de saída."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Empresa
from apps.comercial.models import HomologacaoFiscalPropostaEvento, ItemProposta, Proposta
from apps.comercial.serializers import ItemPropostaSerializer
from apps.produtos.models import FamiliaProduto, Produto
from apps.regras_fiscais.cenario_fiscal_saida import garantir_cenario_saida_padrao
from apps.regras_fiscais.models import CenarioFiscalSaidaEscopo, RegraFiscal, RegraFiscalSaida
from apps.regras_fiscais.saida_fiscal import (
    comparar_regra_fiscal_saida_legado_cenario,
    use_cenario_fiscal_saida_for_propostas,
)


def _cnpj() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


def _produto(ncm: str = '84818200') -> Produto:
    suf = uuid.uuid4().hex[:6].upper()
    fam = FamiliaProduto.objects.create(
        codigo_figura=f'H{suf}',
        descricao_base='Fam',
        tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
        categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
    )
    return Produto.objects.create(
        familia=fam,
        descricao='Prod',
        modo_codigo=Produto.ModoCodigo.MANUAL,
        codigo_completo=f'H-{suf}',
        unidade='PC',
        ncm=ncm,
    )


def _proposta(*, usar_cenario: bool = False, cenario=None) -> Proposta:
    emp = Empresa.objects.create(razao_social='Emit', cnpj=_cnpj(), uf='SP')
    cli = Cliente.objects.create(razao_social='Cli', cnpj=_cnpj(), uf='RJ')
    hoje = date.today()
    return Proposta.objects.create(
        numero=f'HOM-{uuid.uuid4().hex[:6]}',
        data=hoje,
        validade=hoje + timedelta(days=30),
        empresa_emitente=emp,
        cliente=cli,
        uf_origem='SP',
        usar_cenario_fiscal_saida=usar_cenario,
        cenario_fiscal_saida=cenario,
    )


def _item(proposta: Proposta, prod: Produto) -> ItemProposta:
    return ItemProposta.objects.create(
        proposta=proposta,
        produto=prod,
        quantidade=Decimal('1'),
        valor_unitario=Decimal('100'),
        custo_utilizado=Decimal('50'),
        modo_preco='sugerido',
    )


class HomologacaoCenarioFiscalSetupMixin:
    def setUp(self):
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create_user('hom_cf', 'hom@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(user)
        self.cenario = garantir_cenario_saida_padrao()
        escopo = CenarioFiscalSaidaEscopo.objects.create(
            cenario=self.cenario,
            tipo_escopo=CenarioFiscalSaidaEscopo.TipoEscopo.NCM,
            ncm='84818200',
        )
        RegraFiscalSaida.objects.create(
            escopo=escopo,
            cenario=self.cenario,
            ativo=True,
            uf_origem='SP',
            uf_destino='RJ',
            cfop_venda='6102',
            tipo_operacao='VENDA',
            cst_icms='00',
            aliquota_icms=Decimal('18'),
        )
        RegraFiscal.objects.create(
            ncm='84818200',
            uf_origem='SP',
            uf_destino='RJ',
            operacao='Saída',
            cfop='5102',
            aliquota_icms=12.0,
        )


@override_settings(USE_CENARIO_FISCAL_SAIDA_FOR_PROPOSTAS=False)
class HomologacaoCenarioFiscalAPITests(HomologacaoCenarioFiscalSetupMixin, TestCase):
    def test_iniciar_ativa_cenario_e_recalcula(self):
        p = _proposta()
        prod = _produto('84818200')
        _item(p, prod)
        r = self.client.post(
            f'/api/propostas/{p.pk}/homologar-cenario-fiscal/iniciar/',
            {'cenario_fiscal_saida_id': self.cenario.pk, 'observacao': 'Teste homologação'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        body = r.json()
        self.assertEqual(body['status'], 'EM_ANALISE')
        p.refresh_from_db()
        self.assertTrue(p.usar_cenario_fiscal_saida)
        self.assertEqual(p.homologacao_fiscal_status, 'EM_ANALISE')
        item = p.itens.first()
        ser = ItemPropostaSerializer(item, context={'proposta_incoming': {'usar_cenario_fiscal_saida': True}})
        self.assertEqual(ser.data['origem_regra_fiscal_saida'], 'CENARIO_SAIDA')
        self.assertEqual(float(item.icms_saida_percentual), 18.0)

    def test_iniciar_fallback_legado_sem_regra_cenario(self):
        RegraFiscal.objects.create(
            ncm='84818201',
            uf_origem='SP',
            uf_destino='RJ',
            operacao='Saída',
            cfop='5102',
            aliquota_icms=12.0,
        )
        p = _proposta()
        prod = _produto('84818201')
        _item(p, prod)
        r = self.client.post(
            f'/api/propostas/{p.pk}/homologar-cenario-fiscal/iniciar/',
            {},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        p.refresh_from_db()
        item = p.itens.first()
        ser = ItemPropostaSerializer(item, context={'proposta_incoming': {'usar_cenario_fiscal_saida': True}})
        self.assertEqual(ser.data['origem_regra_fiscal_saida'], 'LEGADO')

    def test_resumo_conta_divergentes(self):
        escopo2 = CenarioFiscalSaidaEscopo.objects.create(
            cenario=self.cenario,
            tipo_escopo=CenarioFiscalSaidaEscopo.TipoEscopo.NCM,
            ncm='84818202',
        )
        RegraFiscalSaida.objects.create(
            escopo=escopo2,
            cenario=self.cenario,
            ativo=True,
            uf_origem='SP',
            uf_destino='RJ',
            cfop_venda='6102',
            aliquota_icms=Decimal('20'),
        )
        RegraFiscal.objects.create(
            ncm='84818202',
            uf_origem='SP',
            uf_destino='RJ',
            operacao='Saída',
            cfop='5102',
            aliquota_icms=12.0,
        )
        p = _proposta()
        _item(p, _produto('84818202'))
        self.client.post(f'/api/propostas/{p.pk}/homologar-cenario-fiscal/iniciar/', {}, format='json')
        r = self.client.get(f'/api/propostas/{p.pk}/homologar-cenario-fiscal/resumo/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        resumo = r.json()['resumo']
        self.assertEqual(resumo['total_itens'], 1)
        self.assertEqual(resumo['divergentes'], 1)

    def test_aprovar_mantem_cenario(self):
        p = _proposta()
        _item(p, _produto('84818200'))
        self.client.post(f'/api/propostas/{p.pk}/homologar-cenario-fiscal/iniciar/', {}, format='json')
        r = self.client.post(
            f'/api/propostas/{p.pk}/homologar-cenario-fiscal/aprovar/',
            {'observacao': 'OK fiscal'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        p.refresh_from_db()
        self.assertEqual(p.homologacao_fiscal_status, 'APROVADA')
        self.assertTrue(p.usar_cenario_fiscal_saida)

    def test_reprovar_volta_legado(self):
        p = _proposta()
        _item(p, _produto('84818200'))
        self.client.post(f'/api/propostas/{p.pk}/homologar-cenario-fiscal/iniciar/', {}, format='json')
        r = self.client.post(
            f'/api/propostas/{p.pk}/homologar-cenario-fiscal/reprovar/',
            {'observacao': 'Divergência ICMS'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        p.refresh_from_db()
        self.assertEqual(p.homologacao_fiscal_status, 'REPROVADA')
        self.assertFalse(p.usar_cenario_fiscal_saida)
        item = p.itens.first()
        ser = ItemPropostaSerializer(item, context={'proposta_incoming': {'usar_cenario_fiscal_saida': False}})
        self.assertEqual(ser.data['origem_regra_fiscal_saida'], 'LEGADO')
        self.assertEqual(float(item.icms_saida_percentual), 12.0)

    def test_voltar_legado_desativa_cenario(self):
        p = _proposta(usar_cenario=True, cenario=self.cenario)
        _item(p, _produto('84818200'))
        p.homologacao_fiscal_status = Proposta.HomologacaoFiscalStatus.EM_ANALISE
        p.save(update_fields=['homologacao_fiscal_status'])
        r = self.client.post(
            f'/api/propostas/{p.pk}/homologar-cenario-fiscal/voltar-legado/',
            {'observacao': 'Voltando'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        p.refresh_from_db()
        self.assertEqual(p.homologacao_fiscal_status, 'VOLTOU_LEGADO')
        self.assertFalse(p.usar_cenario_fiscal_saida)

    def test_outras_propostas_inalteradas(self):
        p1 = _proposta()
        p2 = _proposta()
        _item(p1, _produto('84818200'))
        self.client.post(f'/api/propostas/{p1.pk}/homologar-cenario-fiscal/iniciar/', {}, format='json')
        p2.refresh_from_db()
        self.assertFalse(p2.usar_cenario_fiscal_saida)
        self.assertEqual(p2.homologacao_fiscal_status, 'NAO_INICIADA')

    def test_proposta_antiga_default_legado(self):
        p = _proposta(usar_cenario=False)
        self.assertFalse(p.usar_cenario_fiscal_saida)
        self.assertEqual(p.homologacao_fiscal_status, 'NAO_INICIADA')

    def test_comparativo_item_continua(self):
        cmp = comparar_regra_fiscal_saida_legado_cenario(
            ncm='84818200',
            uf_origem='SP',
            uf_destino='RJ',
        )
        self.assertIn(cmp['status'], ('IGUAL', 'DIVERGENTE'))

    def test_flag_global_false(self):
        self.assertFalse(use_cenario_fiscal_saida_for_propostas())


@override_settings(USE_CENARIO_FISCAL_SAIDA_FOR_PROPOSTAS=False)
class HomologacaoFiscalHistoricoTests(HomologacaoCenarioFiscalSetupMixin, TestCase):
    def test_iniciar_cria_evento_iniciada(self):
        p = _proposta()
        _item(p, _produto('84818200'))
        self.client.post(
            f'/api/propostas/{p.pk}/homologar-cenario-fiscal/iniciar/',
            {'observacao': 'Homologação inicial'},
            format='json',
        )
        evt = HomologacaoFiscalPropostaEvento.objects.filter(proposta=p, tipo_evento='INICIADA').first()
        self.assertIsNotNone(evt)
        self.assertEqual(evt.status_resultante, 'EM_ANALISE')
        self.assertTrue(evt.usar_cenario_fiscal_saida)
        self.assertEqual(evt.resumo['total_itens'], 1)

    def test_recalcular_cria_evento_recalculada(self):
        p = _proposta()
        _item(p, _produto('84818200'))
        self.client.post(f'/api/propostas/{p.pk}/homologar-cenario-fiscal/iniciar/', {}, format='json')
        self.client.post(f'/api/propostas/{p.pk}/homologar-cenario-fiscal/recalcular/', {}, format='json')
        self.assertTrue(
            HomologacaoFiscalPropostaEvento.objects.filter(proposta=p, tipo_evento='RECALCULADA').exists(),
        )

    def test_aprovar_cria_evento_aprovada(self):
        p = _proposta()
        _item(p, _produto('84818200'))
        self.client.post(f'/api/propostas/{p.pk}/homologar-cenario-fiscal/iniciar/', {}, format='json')
        self.client.post(
            f'/api/propostas/{p.pk}/homologar-cenario-fiscal/aprovar/',
            {'observacao': 'Conferido'},
            format='json',
        )
        evt = HomologacaoFiscalPropostaEvento.objects.filter(proposta=p, tipo_evento='APROVADA').latest('criado_em')
        self.assertEqual(evt.status_resultante, 'APROVADA')
        self.assertEqual(evt.observacao, 'Conferido')
        self.assertIsNotNone(evt.resumo)

    def test_reprovar_cria_evento_reprovada(self):
        p = _proposta()
        _item(p, _produto('84818200'))
        self.client.post(f'/api/propostas/{p.pk}/homologar-cenario-fiscal/iniciar/', {}, format='json')
        self.client.post(
            f'/api/propostas/{p.pk}/homologar-cenario-fiscal/reprovar/',
            {'observacao': 'Divergência'},
            format='json',
        )
        evt = HomologacaoFiscalPropostaEvento.objects.filter(proposta=p, tipo_evento='REPROVADA').first()
        self.assertEqual(evt.status_resultante, 'REPROVADA')
        self.assertFalse(evt.usar_cenario_fiscal_saida)

    def test_voltar_legado_cria_evento(self):
        p = _proposta(usar_cenario=True, cenario=self.cenario)
        _item(p, _produto('84818200'))
        p.homologacao_fiscal_status = Proposta.HomologacaoFiscalStatus.EM_ANALISE
        p.save(update_fields=['homologacao_fiscal_status'])
        self.client.post(
            f'/api/propostas/{p.pk}/homologar-cenario-fiscal/voltar-legado/',
            {'observacao': 'Volta'},
            format='json',
        )
        evt = HomologacaoFiscalPropostaEvento.objects.filter(
            proposta=p,
            tipo_evento='VOLTOU_LEGADO',
        ).first()
        self.assertIsNotNone(evt)
        self.assertEqual(evt.status_resultante, 'VOLTOU_LEGADO')

    def test_evento_guarda_cenario_e_itens(self):
        p = _proposta()
        _item(p, _produto('84818200'))
        self.client.post(
            f'/api/propostas/{p.pk}/homologar-cenario-fiscal/iniciar/',
            {'cenario_fiscal_saida_id': self.cenario.pk},
            format='json',
        )
        evt = HomologacaoFiscalPropostaEvento.objects.filter(proposta=p, tipo_evento='INICIADA').first()
        self.assertEqual(evt.cenario_fiscal_saida_id, self.cenario.pk)
        self.assertTrue(evt.cenario_fiscal_saida_nome)
        self.assertIsInstance(evt.itens, list)
        self.assertGreaterEqual(len(evt.itens), 1)

    def test_endpoint_historico_ordem_e_isolamento(self):
        p1 = _proposta()
        p2 = _proposta()
        _item(p1, _produto('84818200'))
        _item(p2, _produto('84818200'))
        self.client.post(f'/api/propostas/{p1.pk}/homologar-cenario-fiscal/iniciar/', {}, format='json')
        self.client.post(f'/api/propostas/{p1.pk}/homologar-cenario-fiscal/aprovar/', {}, format='json')
        r = self.client.get(f'/api/propostas/{p1.pk}/homologar-cenario-fiscal/historico/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        body = r.json()
        self.assertEqual(body['proposta_id'], p1.pk)
        self.assertEqual(len(body['eventos']), 2)
        tipos = [e['tipo_evento'] for e in body['eventos']]
        self.assertEqual(tipos[0], 'APROVADA')
        self.assertEqual(tipos[1], 'INICIADA')
        r2 = self.client.get(f'/api/propostas/{p2.pk}/homologar-cenario-fiscal/historico/')
        self.assertEqual(r2.json()['eventos'], [])

    def test_proposta_sem_historico_abre(self):
        p = _proposta()
        r = self.client.get(f'/api/propostas/{p.pk}/homologar-cenario-fiscal/historico/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.json()['eventos'], [])

    def test_resumo_inclui_contagem_eventos(self):
        p = _proposta()
        _item(p, _produto('84818200'))
        self.client.post(f'/api/propostas/{p.pk}/homologar-cenario-fiscal/iniciar/', {}, format='json')
        r = self.client.get(f'/api/propostas/{p.pk}/homologar-cenario-fiscal/resumo/')
        body = r.json()
        self.assertGreaterEqual(body['total_eventos_homologacao'], 1)
        self.assertIsNotNone(body['ultimo_evento_homologacao'])

    def test_fluxo_39_continua_apos_historico(self):
        p = _proposta()
        _item(p, _produto('84818200'))
        r = self.client.post(f'/api/propostas/{p.pk}/homologar-cenario-fiscal/iniciar/', {}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.json()['status'], 'EM_ANALISE')
