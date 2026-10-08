"""NF-e 4.0.2 — UI/estado após autorização homologação (cStat 100)."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.comercial.models import FaturamentoPedidoVenda
from apps.fiscal.models import NFeSaida, NFeSaidaEvento
from apps.fiscal.nfe_saida_apresentacao import montar_apresentacao_nfe_saida
from apps.fiscal.nfe_saida_bloqueio import (
    dados_complementares_editaveis,
    itens_comerciais_editaveis,
    nf_autorizada_homologacao,
    pode_atualizar_impostos_nfe,
)
from apps.fiscal.nfe_saida_conferencia import montar_conferencia_nfe_saida
from apps.fiscal.serializers import NFeSaidaSerializer
from apps.fiscal.validacao_nfe_saida import validar_nfe_saida_para_emissao
from apps.fiscal.tests.test_nfe_saida_402_emissao_homologacao import _pedido_nf, _preparar_pronta


class NFe402PosAutorizacaoHomologTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('pos402', 'pos402@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.pedido, self.item, self.nf = _pedido_nf()
        self.nf = _preparar_pronta(self.nf, self.user)
        self.nf.status_emissao_sefaz = NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO
        self.nf.status = 'AUTORIZADA_HOMOLOGACAO'
        self.nf.ambiente_emissao = NFeSaida.AmbienteEmissao.HOMOLOGACAO
        self.nf.serie_nfe = '0'
        self.nf.numero_nfe = '000000002'
        self.nf.cstat_autorizacao = '100'
        self.nf.motivo_autorizacao = 'Autorizado o uso da NF-e'
        self.nf.protocolo_autorizacao = '13526005517408'
        self.nf.cstat_lote = '104'
        self.nf.xmotivo_lote = 'Lote processado'
        self.nf.chave_acesso = '3526050399910200015055000000000212345678901'
        self.nf.xml_autorizado = '<?xml version="1.0"?><nfeProc><NFe/></nfeProc>'
        self.nf.save()
        if self.nf.faturamento_pedido_venda_id:
            fat = FaturamentoPedidoVenda.objects.get(pk=self.nf.faturamento_pedido_venda_id)
            if not (fat.numero_faturamento or '').strip():
                fat.numero_faturamento = 'FAT-20260523-0001'
                fat.save(update_fields=['numero_faturamento'])

    def test_apresentacao_titulo_fiscal(self):
        ap = montar_apresentacao_nfe_saida(self.nf)
        self.assertIn('NF-e Homologação nº 000000002', ap['titulo_exibicao'])
        self.assertIn('Série 0', ap['titulo_exibicao'])
        self.assertNotIn('RASCUNHO-FAT-2', ap['titulo_exibicao'])

    def test_apresentacao_origens_separadas(self):
        ap = montar_apresentacao_nfe_saida(self.nf)
        fat = FaturamentoPedidoVenda.objects.filter(pk=self.nf.faturamento_pedido_venda_id).first()
        if fat and fat.numero_faturamento:
            self.assertIn(fat.numero_faturamento, ap['subtitulo_exibicao'])
        self.assertIn(self.pedido.numero, ap['subtitulo_exibicao'])
        self.assertNotIn('Origem interna', ap['subtitulo_exibicao'])

    def test_serializer_apresentacao(self):
        data = NFeSaidaSerializer(self.nf).data
        ap = data.get('apresentacao') or {}
        self.assertIn('NF-e Homologação', ap.get('titulo_exibicao', ''))
        self.assertTrue(ap.get('modo_leitura'))

    def test_conferencia_apresentacao(self):
        conf = montar_conferencia_nfe_saida(self.nf)
        ap = conf.get('apresentacao') or {}
        self.assertIn('NF-e Homologação', ap.get('titulo_exibicao', ''))

    def test_listagem_apresentacao(self):
        res = self.client.get('/api/nf-saidas/')
        rows = res.json() if isinstance(res.json(), list) else res.json().get('results', [])
        row = next(r for r in rows if r['id'] == self.nf.pk)
        resumo = row.get('listagem_resumo') or {}
        self.assertIn('NF-e Homologação', resumo.get('titulo', ''))
        self.assertEqual(resumo.get('fiscal_resumo', {}).get('badge'), 'Homologação autorizada')
        self.assertIn('cStat 100', resumo.get('fiscal_resumo', {}).get('subtexto', ''))

    def test_rascunho_mantem_titulo_interno(self):
        nf_r = NFeSaida.objects.create(
            numero='RASCUNHO-FAT-99',
            cliente=self.nf.cliente,
            data=self.nf.data,
            valor_total=self.nf.valor_total,
            status='RASCUNHO',
        )
        ap = montar_apresentacao_nfe_saida(nf_r)
        self.assertIn('RASCUNHO-FAT-99', ap['titulo_exibicao'])

    def test_status_emissao_autorizada_homologacao(self):
        self.assertEqual(self.nf.status_emissao_sefaz, 'AUTORIZADA_HOMOLOGACAO')
        self.assertTrue(nf_autorizada_homologacao(self.nf))

    def test_mantem_protocolo_e_xml_autorizado(self):
        self.nf.refresh_from_db()
        self.assertEqual(self.nf.protocolo_autorizacao, '13526005517408')
        self.assertIn('nfeProc', self.nf.xml_autorizado)

    def test_conferencia_bloqueia_emissao_e_edicao(self):
        conf = montar_conferencia_nfe_saida(self.nf)
        perm = conf['permissoes']
        self.assertFalse(perm['pode_emitir_homologacao'])
        self.assertFalse(perm['pode_tentar_emitir_homologacao'])
        self.assertFalse(perm['pode_marcar_pronta'])
        self.assertFalse(perm['pode_validar_conferencia'])
        self.assertFalse(perm['dados_complementares_editaveis'])
        self.assertFalse(perm['pode_atualizar_impostos'])
        em = conf['emissao_sefaz']
        self.assertTrue(em['autorizada_homologacao'])
        self.assertIn('homologação', em['mensagem_status_homologacao'].lower())

    def test_validacao_nao_mostra_legado(self):
        val = validar_nfe_saida_para_emissao(self.nf)
        codigos = [it.get('codigo') for g in val.get('grupos', {}).values() for it in g]
        self.assertNotIn('STATUS_LEGADO', codigos)
        self.assertIn('NFE_AUTORIZADA_HOMOLOG', codigos)
        self.assertFalse(val['pode_emitir'])

    def test_listagem_resumo_emissao_sefaz(self):
        data = NFeSaidaSerializer(self.nf).data
        resumo = data.get('resumo_emissao_sefaz') or {}
        self.assertEqual(resumo.get('status_emissao_sefaz'), 'AUTORIZADA_HOMOLOGACAO')
        self.assertEqual(resumo.get('nfe', {}).get('cstat'), '100')
        self.assertEqual(resumo.get('nfe', {}).get('protocolo'), '13526005517408')
        self.assertNotIn('xml_autorizado', data)

    def test_campos_bloqueados_pos_autorizacao(self):
        self.assertFalse(dados_complementares_editaveis(self.nf))
        self.assertFalse(itens_comerciais_editaveis(self.nf))
        self.assertFalse(pode_atualizar_impostos_nfe(self.nf))

    def test_api_listagem_ok(self):
        res = self.client.get('/api/nf-saidas/')
        self.assertEqual(res.status_code, 200)
        rows = res.json() if isinstance(res.json(), list) else res.json().get('results', [])
        row = next(r for r in rows if r['id'] == self.nf.pk)
        self.assertIn('listagem_resumo', row)
        det = self.client.get(f'/api/nf-saidas/{self.nf.pk}/')
        self.assertEqual(
            (det.json().get('resumo_emissao_sefaz') or {}).get('status_emissao_sefaz'),
            'AUTORIZADA_HOMOLOGACAO',
        )

    def test_evento_autorizacao_homologacao(self):
        NFeSaidaEvento.objects.create(
            nfe_saida=self.nf,
            tipo_evento='NFE_AUTORIZADA_HOMOLOGACAO',
            resumo={
                'protocolo': '13526005517408',
                'cStat_nfe': '100',
                'serie_nfe': '0',
                'numero_nfe': '000000002',
            },
            observacao='Teste',
        )
        evt = NFeSaidaEvento.objects.filter(
            nfe_saida=self.nf,
            tipo_evento='NFE_AUTORIZADA_HOMOLOGACAO',
        ).first()
        self.assertIsNotNone(evt)
        self.assertEqual(evt.resumo.get('cStat_nfe'), '100')
