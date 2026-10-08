"""NF-e Saída 3.5.2 — atualizar impostos do rascunho a partir da regra fiscal atual."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from apps.fiscal.models import ItemNFeSaida, NFeSaida, NFeSaidaEvento
from apps.fiscal.nfe_saida_atualizar_impostos import (
    MSG_BLOQUEIO_STATUS,
    aplicar_atualizacao_impostos_nfe,
    preparar_atualizacao_impostos_nfe,
)
from apps.fiscal.nfe_saida_bloqueio import origem_comercial_travada, pode_atualizar_impostos_nfe
from apps.fiscal.nfe_saida_conferencia import montar_conferencia_nfe_saida
from apps.fiscal.nfe_saida_from_faturamento import gerar_nfe_saida_from_faturamento
from apps.fiscal.nfe_saida_preview import gerar_dados_preview_nfe_saida
from apps.fiscal.tests.test_nfe_saida_faturamento import _faturamento_pronto, _pedido_item
from apps.fiscal.validacao_nfe_saida import validar_nfe_saida_para_emissao
from apps.regras_fiscais.cenario_fiscal_saida import garantir_cenario_saida_padrao
from apps.regras_fiscais.models import CenarioFiscalSaidaEscopo, RegraFiscalSaida


def _regra_84818200_sp_rj() -> RegraFiscalSaida:
    cenario = garantir_cenario_saida_padrao()
    escopo, _ = CenarioFiscalSaidaEscopo.objects.get_or_create(
        cenario=cenario,
        tipo_escopo=CenarioFiscalSaidaEscopo.TipoEscopo.NCM,
        ncm='84818200',
        defaults={},
    )
    regra, _ = RegraFiscalSaida.objects.update_or_create(
        escopo=escopo,
        cenario=cenario,
        uf_origem='SP',
        uf_destino='RJ',
        destinatario_contribuinte=RegraFiscalSaida.DestinatarioContribuinte.QUALQUER,
        defaults={
            'nome': 'Venda SP - contribuinte',
            'cfop_venda': '5102',
            'cst_icms': '00',
            'aliquota_icms': Decimal('18'),
            'cst_pis': '01',
            'aliquota_pis': Decimal('1.65'),
            'cst_cofins': '01',
            'aliquota_cofins': Decimal('7.6'),
            'deduzir_icms_base_pis': True,
            'deduzir_icms_base_cofins': True,
            'reforma_tributaria': {
                'cst_ibs_cbs': '000',
                'classificacao_tributaria': '000001',
                'aliquota_cbs': '0.9',
                'aliquota_ibs_estadual': '0.1',
            },
        },
    )
    return regra


@override_settings(USE_CENARIO_FISCAL_SAIDA_FOR_PROPOSTAS=True)
class NFeSaida352AtualizarImpostosTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('nfe352', 'nfe352@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        _regra_84818200_sp_rj()

    def _nf_rascunho_snapshot_vazio(self) -> tuple[NFeSaida, ItemNFeSaida]:
        pedido, item = _pedido_item()
        item.snapshot_fiscal = {'ncm': '84818200'}
        item.save(update_fields=['snapshot_fiscal'])
        fat = _faturamento_pronto(pedido, item)
        r = gerar_nfe_saida_from_faturamento(pedido, fat.pk)
        nf = NFeSaida.objects.prefetch_related('itens__produto').get(pk=r['nfe_saida_id'])
        nf_item = nf.itens.first()
        assert nf_item is not None
        nf_item.snapshot_fiscal = {}
        nf_item.save(update_fields=['snapshot_fiscal'])
        nf.observacoes_nfe = 'Obs transporte intacta'
        nf.pedido_cliente_numero = 'PC-352'
        nf.save(update_fields=['observacoes_nfe', 'pedido_cliente_numero'])
        nf_item.pedido_cliente_item = 'LIN-1'
        nf_item.observacao_item = 'Obs item preservada'
        nf_item.save(update_fields=['pedido_cliente_item', 'observacao_item'])
        return nf, nf_item

    def test_preview_nao_altera_banco(self):
        nf, nf_item = self._nf_rascunho_snapshot_vazio()
        snap_antes = dict(nf_item.snapshot_fiscal or {})
        qtd_antes = nf_item.quantidade
        prev = preparar_atualizacao_impostos_nfe(nf)
        nf_item.refresh_from_db()
        self.assertEqual(nf_item.snapshot_fiscal, snap_antes)
        self.assertEqual(nf_item.quantidade, qtd_antes)
        self.assertTrue(prev['pode_aplicar'])
        self.assertGreater(prev['resumo']['itens_com_alteracao'], 0)

    def test_aplicar_preenche_cfop_e_icms(self):
        nf, nf_item = self._nf_rascunho_snapshot_vazio()
        aplicar_atualizacao_impostos_nfe(nf, usuario=self.user, motivo='Regra cadastrada depois')
        nf_item.refresh_from_db()
        snap = nf_item.snapshot_fiscal
        self.assertEqual(snap.get('cfop') or snap.get('cfop_venda'), '5102')
        self.assertEqual(snap.get('cst_icms'), '00')
        self.assertIn(str(snap.get('aliquota_icms')), ('18', '18.00'))
        self.assertTrue(Decimal(str(snap.get('valor_icms') or 0)) > 0)

    def test_aplicar_nao_altera_comercial(self):
        nf, nf_item = self._nf_rascunho_snapshot_vazio()
        pedido_id = nf.pedido_venda_id
        fat_id = nf.faturamento_pedido_venda_id
        cliente_id = nf.cliente_id
        qtd = nf_item.quantidade
        valor = nf_item.valor
        prod_id = nf_item.produto_id
        aplicar_atualizacao_impostos_nfe(nf, usuario=self.user)
        nf.refresh_from_db()
        nf_item.refresh_from_db()
        self.assertEqual(nf.pedido_venda_id, pedido_id)
        self.assertEqual(nf.faturamento_pedido_venda_id, fat_id)
        self.assertEqual(nf.cliente_id, cliente_id)
        self.assertEqual(nf_item.quantidade, qtd)
        self.assertEqual(nf_item.valor, valor)
        self.assertEqual(nf_item.produto_id, prod_id)
        self.assertEqual(nf.observacoes_nfe, 'Obs transporte intacta')
        self.assertEqual(nf.pedido_cliente_numero, 'PC-352')
        self.assertEqual(nf_item.pedido_cliente_item, 'LIN-1')
        self.assertEqual(nf_item.observacao_item, 'Obs item preservada')

    def test_aplicar_reforma_tributaria(self):
        nf, nf_item = self._nf_rascunho_snapshot_vazio()
        aplicar_atualizacao_impostos_nfe(nf, usuario=self.user)
        nf_item.refresh_from_db()
        ref = nf_item.snapshot_fiscal.get('reforma_tributaria') or {}
        self.assertEqual(ref.get('cst_ibs_cbs'), '000')
        self.assertEqual(ref.get('classificacao_tributaria'), '000001')

    def test_item_sem_regra_nao_quebra(self):
        nf, nf_item = self._nf_rascunho_snapshot_vazio()
        RegraFiscalSaida.objects.filter(escopo__ncm='84818200').delete()
        prev = preparar_atualizacao_impostos_nfe(nf)
        self.assertFalse(prev['pode_aplicar'])
        self.assertEqual(prev['resumo']['itens_sem_regra'], 1)
        self.assertIn('regra fiscal de saída', prev['itens'][0]['alertas'][0].lower())

    def test_bloqueio_autorizada_interna(self):
        nf, _ = self._nf_rascunho_snapshot_vazio()
        nf.status = 'AUTORIZADA_INTERNA'
        nf.save(update_fields=['status'])
        prev = preparar_atualizacao_impostos_nfe(nf)
        self.assertTrue(prev['bloqueado'])
        self.assertEqual(prev['mensagem'], MSG_BLOQUEIO_STATUS)

    def test_bloqueio_cancelada_interna(self):
        nf, _ = self._nf_rascunho_snapshot_vazio()
        nf.status = 'CANCELADA_INTERNA'
        nf.save(update_fields=['status'])
        prev = preparar_atualizacao_impostos_nfe(nf)
        self.assertTrue(prev['bloqueado'])

    def test_evento_impostos_atualizados(self):
        nf, _ = self._nf_rascunho_snapshot_vazio()
        aplicar_atualizacao_impostos_nfe(nf, usuario=self.user, motivo='Teste evento')
        evt = NFeSaidaEvento.objects.filter(
            nfe_saida=nf,
            tipo_evento=NFeSaidaEvento.TipoEvento.IMPOSTOS_ATUALIZADOS,
        ).first()
        self.assertIsNotNone(evt)
        self.assertIn('Teste evento', evt.observacao)
        self.assertGreater(evt.resumo.get('itens_com_alteracao', 0), 0)

    def test_conferencia_e_validacao_apos_aplicar(self):
        nf, _ = self._nf_rascunho_snapshot_vazio()
        aplicar_atualizacao_impostos_nfe(nf, usuario=self.user)
        nf.refresh_from_db()
        conf = montar_conferencia_nfe_saida(nf)
        self.assertEqual(conf['itens'][0]['cfop'], '5102')
        val = validar_nfe_saida_para_emissao(nf)
        cfop_pend = [p for p in val.get('pendencias', []) if p.get('codigo') == 'ITEM_SEM_CFOP']
        self.assertEqual(len(cfop_pend), 0)

    def test_preview_dados_usa_novo_cfop(self):
        nf, _ = self._nf_rascunho_snapshot_vazio()
        aplicar_atualizacao_impostos_nfe(nf, usuario=self.user)
        nf.refresh_from_db()
        dados = gerar_dados_preview_nfe_saida(nf)
        self.assertEqual(dados['itens'][0].get('cfop'), '5102')

    def test_endpoints_preview_e_aplicar(self):
        nf, _ = self._nf_rascunho_snapshot_vazio()
        r_prev = self.client.get(f'/api/nf-saidas/{nf.pk}/atualizar-impostos/preview/')
        self.assertEqual(r_prev.status_code, status.HTTP_200_OK)
        self.assertTrue(r_prev.json()['pode_aplicar'])
        r_app = self.client.post(
            f'/api/nf-saidas/{nf.pk}/atualizar-impostos/aplicar/',
            {'motivo': 'Via API'},
            format='json',
        )
        self.assertEqual(r_app.status_code, status.HTTP_200_OK, r_app.content)
        self.assertTrue(r_app.json()['aplicado'])
        self.assertEqual(r_app.json()['conferencia']['itens'][0]['cfop'], '5102')

    def test_conferencia_permite_atualizar_impostos(self):
        nf, _ = self._nf_rascunho_snapshot_vazio()
        conf = self.client.get(f'/api/nf-saidas/{nf.pk}/conferencia/').json()
        self.assertTrue(conf['permissoes']['pode_atualizar_impostos'])

    def test_conferencia_faturamento_origem_travada_permite_atualizar_impostos(self):
        nf, _ = self._nf_rascunho_snapshot_vazio()
        conf = montar_conferencia_nfe_saida(nf)
        self.assertTrue(origem_comercial_travada(nf))
        self.assertTrue(conf['permissoes']['origem_comercial_travada'])
        self.assertFalse(conf['permissoes']['itens_comerciais_editaveis'])
        self.assertTrue(conf['permissoes']['pode_atualizar_impostos'])

    def test_conferencia_reforma_nao_configurada_permite_atualizar_impostos(self):
        nf, _ = self._nf_rascunho_snapshot_vazio()
        conf = montar_conferencia_nfe_saida(nf)
        self.assertEqual(conf['reforma_tributaria']['resumo']['status'], 'NAO_CONFIGURADA')
        self.assertTrue(conf['permissoes']['pode_atualizar_impostos'])

    def test_preview_sem_regra_nao_bloqueia_rascunho(self):
        nf, _ = self._nf_rascunho_snapshot_vazio()
        RegraFiscalSaida.objects.filter(escopo__ncm='84818200').delete()
        resp = self.client.get(f'/api/nf-saidas/{nf.pk}/atualizar-impostos/preview/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        body = resp.json()
        self.assertFalse(body['bloqueado'])
        self.assertFalse(body['pode_aplicar'])
        self.assertFalse(body['itens'][0]['regra_encontrada'])

    def test_nf_sem_itens_pode_atualizar_impostos_false(self):
        nf, nf_item = self._nf_rascunho_snapshot_vazio()
        nf_item.delete()
        self.assertFalse(pode_atualizar_impostos_nfe(nf, itens_count=0))
        resp = self.client.get(f'/api/nf-saidas/{nf.pk}/conferencia/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.json()['permissoes']['pode_atualizar_impostos'])
        prev = preparar_atualizacao_impostos_nfe(nf)
        self.assertTrue(prev['bloqueado'])

    def test_aplicar_sem_alteracao_retorna_400(self):
        nf, _ = self._nf_rascunho_snapshot_vazio()
        RegraFiscalSaida.objects.filter(escopo__ncm='84818200').delete()
        resp = self.client.post(
            f'/api/nf-saidas/{nf.pk}/atualizar-impostos/aplicar/',
            {'motivo': 'Sem regra'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('mensagem', resp.json())

    def test_aplicar_status_alterado_entre_preview_bloqueia(self):
        nf, _ = self._nf_rascunho_snapshot_vazio()
        preparar_atualizacao_impostos_nfe(nf)

        def _lock_e_muda_status(pk):
            locked = NFeSaida.objects.select_for_update().get(pk=pk)
            locked.status = 'AUTORIZADA_INTERNA'
            locked.save(update_fields=['status'])
            return locked

        with patch(
            'apps.fiscal.nfe_saida_atualizar_impostos._lock_nfe_saida',
            side_effect=_lock_e_muda_status,
        ):
            with self.assertRaises(ValueError) as ctx:
                aplicar_atualizacao_impostos_nfe(nf, usuario=self.user)
            self.assertIn('rascunho', str(ctx.exception).lower())

    def test_preview_inclui_textos_fiscais_da_regra(self):
        nf, _ = self._nf_rascunho_snapshot_vazio()
        regra = RegraFiscalSaida.objects.filter(escopo__ncm='84818200').first()
        self.assertIsNotNone(regra)
        regra.informacoes_complementares = 'Operação tributada conforme CFOP 5102.'
        regra.observacoes = 'Entrega conforme condições da regra.'
        regra.recomendacoes_nfe = {'danfe_paisagem': True, 'ordenar_itens_por_descricao': True}
        regra.save(
            update_fields=['informacoes_complementares', 'observacoes', 'recomendacoes_nfe'],
        )
        prev = preparar_atualizacao_impostos_nfe(nf)
        self.assertTrue(prev['pode_aplicar'])
        self.assertGreaterEqual(prev['resumo']['textos_fiscais_sugeridos'], 1)
        campos = {a['campo'] for a in prev['textos_fiscais']['alteracoes']}
        self.assertIn('informacoes_adicionais', campos)
        self.assertGreater(len(prev['textos_fiscais']['recomendacoes']), 0)

    def test_aplicar_preenche_informacoes_adicionais_vazio(self):
        nf, _ = self._nf_rascunho_snapshot_vazio()
        regra = RegraFiscalSaida.objects.filter(escopo__ncm='84818200').first()
        regra.informacoes_complementares = 'Texto complementar da regra.'
        regra.save(update_fields=['informacoes_complementares'])
        aplicar_atualizacao_impostos_nfe(nf, usuario=self.user)
        nf.refresh_from_db()
        self.assertIn('Texto complementar da regra', nf.informacoes_adicionais)

    def test_aplicar_merge_informacoes_adicionais_existente(self):
        nf, _ = self._nf_rascunho_snapshot_vazio()
        nf.informacoes_adicionais = 'Texto do usuário na NF-e.'
        nf.save(update_fields=['informacoes_adicionais'])
        regra = RegraFiscalSaida.objects.filter(escopo__ncm='84818200').first()
        regra.informacoes_complementares = 'Texto da regra fiscal.'
        regra.save(update_fields=['informacoes_complementares'])
        aplicar_atualizacao_impostos_nfe(nf, usuario=self.user)
        nf.refresh_from_db()
        self.assertIn('Texto do usuário', nf.informacoes_adicionais)
        self.assertIn('Texto da regra fiscal', nf.informacoes_adicionais)
        self.assertIn('Observações fiscais da regra', nf.informacoes_adicionais)

    def test_aplicar_nao_duplica_texto_regra(self):
        nf, _ = self._nf_rascunho_snapshot_vazio()
        texto = 'Operação tributada conforme CFOP 5102.'
        nf.informacoes_adicionais = texto
        nf.save(update_fields=['informacoes_adicionais'])
        regra = RegraFiscalSaida.objects.filter(escopo__ncm='84818200').first()
        regra.informacoes_complementares = texto
        regra.save(update_fields=['informacoes_complementares'])
        aplicar_atualizacao_impostos_nfe(nf, usuario=self.user)
        nf.refresh_from_db()
        self.assertEqual(nf.informacoes_adicionais.count(texto), 1)

    def test_preview_danfe_com_informacoes_adicionais(self):
        nf, _ = self._nf_rascunho_snapshot_vazio()
        regra = RegraFiscalSaida.objects.filter(escopo__ncm='84818200').first()
        regra.informacoes_complementares = 'Info adicional preview DANFE.'
        regra.save(update_fields=['informacoes_complementares'])
        aplicar_atualizacao_impostos_nfe(nf, usuario=self.user)
        nf.refresh_from_db()
        dados = gerar_dados_preview_nfe_saida(nf)
        self.assertIn('Info adicional preview DANFE', dados['informacoes_adicionais'])

    def test_patch_conferencia_item_com_id_ok(self):
        nf, nf_item = self._nf_rascunho_snapshot_vazio()
        resp = self.client.patch(
            f'/api/nf-saidas/{nf.pk}/',
            {
                'pedido_cliente_numero': 'PC-352-OK',
                'itens': [{'id': nf_item.pk, 'pedido_cliente_item': 'LIN-99'}],
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        nf_item.refresh_from_db()
        self.assertEqual(nf_item.pedido_cliente_item, 'LIN-99')

    def test_patch_conferencia_item_sem_id_bloqueia(self):
        nf, _ = self._nf_rascunho_snapshot_vazio()
        resp = self.client.patch(
            f'/api/nf-saidas/{nf.pk}/',
            {'itens': [{'pedido_cliente_item': 'sem-id'}]},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('complementos', resp.json()['itens'][0])
