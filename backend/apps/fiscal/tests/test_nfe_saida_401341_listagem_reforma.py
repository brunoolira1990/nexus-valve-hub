"""ERP 4.0.13.4.1 — listagem compacta e Reforma Tributária na API NF-e Saída."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.fiscal.models import NFeSaida
from apps.fiscal.nfe_saida_listagem import (
    montar_atendimento_resumo_listagem,
    montar_fiscal_resumo_listagem,
    montar_listagem_resumo_nfe,
)
from apps.fiscal.reforma_tributaria.xml import build_reforma_tributaria_item_bindings
from apps.fiscal.serializers import NFeSaidaListSerializer, NFeSaidaSerializer
from apps.comercial.payment_terms import compute_due_dates
from apps.fiscal.nfe_saida_duplicatas import aplicar_duplicatas_nfe_saida
from apps.fiscal.tests.test_nfe_saida_402_emissao_homologacao import _pedido_nf, _preparar_pronta


class NFe401341ListagemReformaTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('nfe401341', 'nfe401341@test.com', 'x')
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
        self.nf.protocolo_autorizacao = '13526005517408'
        self.nf.chave_acesso = '3526050399910200015055000000000212345678901'
        self.nf.condicao_pagamento_texto = '30/60'
        self.nf.dias_parcelas = [30, 60]
        self.nf.quantidade_parcelas = 2
        self.nf.vencimentos_finais = compute_due_dates(self.nf.data, [30, 60])
        self.nf.save()
        aplicar_duplicatas_nfe_saida(self.nf)

    def _list_row(self):
        res = self.client.get('/api/nf-saidas/')
        self.assertEqual(res.status_code, 200)
        rows = res.json() if isinstance(res.json(), list) else res.json().get('results', [])
        return next(r for r in rows if r['id'] == self.nf.pk)

    def test_detalhe_retorna_reforma_tributaria(self):
        res = self.client.get(f'/api/nf-saidas/{self.nf.pk}/')
        self.assertEqual(res.status_code, 200)
        body = res.json()
        rt = body.get('reforma_tributaria') or {}
        self.assertIn('status', rt)
        self.assertIn('status_label', rt)
        self.assertIn('config', rt)
        self.assertIn('itens', rt)
        self.assertIn('totais', rt)

    @override_settings(
        REFORMA_TRIBUTARIA_NFE_ENABLED=False,
        REFORMA_TRIBUTARIA_NFE_MODO='pesquisa',
    )
    def test_flags_desligadas_status_seguro(self):
        data = NFeSaidaSerializer(self.nf).data
        self.assertEqual(data['reforma_tributaria']['status'], 'nao_aplicavel')

    def test_listagem_retorna_listagem_resumo(self):
        row = self._list_row()
        self.assertIn('listagem_resumo', row)
        resumo = row['listagem_resumo']
        self.assertIn('titulo', resumo)
        self.assertIn('fiscal_resumo', resumo)
        self.assertIn('atendimento_resumo', resumo)
        self.assertTrue(resumo['tem_duplicatas'])

    def test_listagem_nao_retorna_xml_nem_itens(self):
        row = self._list_row()
        self.assertNotIn('xml_autorizado', row)
        self.assertNotIn('itens', row)
        self.assertNotIn('apresentacao', row)

    def test_homologacao_fiscal_resumo_agrupado(self):
        fiscal = montar_fiscal_resumo_listagem(self.nf)
        self.assertEqual(fiscal['badge'], 'Homologação autorizada')
        self.assertIn('cStat 100', fiscal['subtexto'])
        self.assertIn('Fora da apuração', fiscal['subtexto'])

    def test_cstat_em_subtexto(self):
        row = self._list_row()
        self.assertIn('cStat 100', row['listagem_resumo']['fiscal_resumo']['subtexto'])

    def test_atendimento_max_dois_badges(self):
        atend = montar_atendimento_resumo_listagem(self.nf)
        self.assertLessEqual(len(atend['badges']), 2)
        for b in atend['badges']:
            self.assertIn('label', b)
            self.assertIn('variant', b)

    def test_atendimento_ocultos_quando_mais_badges(self):
        from unittest.mock import patch

        fake = [{'label': f'B{i}', 'variant': 'warning'} for i in range(5)]
        with patch(
            'apps.fiscal.nfe_saida_listagem.resumo_enxuto_listagem',
            return_value={'badges': fake},
        ):
            atend = montar_atendimento_resumo_listagem(self.nf)
        self.assertEqual(len(atend['badges']), 2)
        self.assertEqual(atend['ocultos'], 3)

    def test_listagem_titulo_nao_e_rascunho_fat(self):
        resumo = montar_listagem_resumo_nfe(self.nf)
        self.assertNotIn('RASCUNHO-FAT', resumo['titulo'])
        self.assertIn('NF-e Homologação', resumo['titulo'])

    def test_status_homolog_sem_emissao_sefaz_ainda_reconhece(self):
        nf2 = NFeSaida.objects.get(pk=self.nf.pk)
        nf2.status_emissao_sefaz = ''
        nf2.status = 'AUTORIZADA_HOMOLOGACAO'
        nf2.save(update_fields=['status_emissao_sefaz', 'status'])
        fiscal = montar_fiscal_resumo_listagem(nf2)
        self.assertEqual(fiscal['badge'], 'Homologação autorizada')

    def test_tem_duplicatas_quando_parcelas(self):
        resumo = montar_listagem_resumo_nfe(self.nf)
        self.assertTrue(resumo['tem_duplicatas'])

    @override_settings(REFORMA_TRIBUTARIA_NFE_MODO='producao', REFORMA_TRIBUTARIA_NFE_ENABLED=True)
    def test_producao_rtc_bloqueada(self):
        from apps.fiscal.reforma_tributaria.config import status_reforma_nfe_documento

        self.assertEqual(status_reforma_nfe_documento(self.nf), 'bloqueada_producao')

    def test_xml_sem_grupos_rtc(self):
        self.assertIsNone(build_reforma_tributaria_item_bindings(None))

    def test_list_serializer_campos_enxutos(self):
        data = NFeSaidaListSerializer(self.nf).data
        self.assertEqual(
            set(data.keys()),
            {
                'id',
                'numero',
                'cliente_id',
                'cliente_nome',
                'data',
                'valor_total',
                'status',
                'status_emissao_sefaz',
                'listagem_resumo',
            },
        )

    def test_rascunho_fiscal_nao_e_traco(self):
        nf_r = NFeSaida.objects.create(
            numero='RASCUNHO-FAT-88',
            cliente=self.nf.cliente,
            data=self.nf.data,
            valor_total=self.nf.valor_total,
            status='RASCUNHO',
        )
        fiscal = montar_fiscal_resumo_listagem(nf_r)
        self.assertEqual(fiscal['badge'], 'Rascunho')
        self.assertNotEqual(fiscal['badge'], '—')

    def test_rascunho_pronto_pendente_autorizacao(self):
        nf_r = NFeSaida.objects.create(
            numero='RASCUNHO-FAT-87',
            cliente=self.nf.cliente,
            data=self.nf.data,
            valor_total=self.nf.valor_total,
            status='RASCUNHO',
            status_conferencia=NFeSaida.StatusConferencia.PRONTA_PARA_EMISSAO,
        )
        fiscal = montar_fiscal_resumo_listagem(nf_r)
        self.assertEqual(fiscal['badge'], 'Pendente de autorização')

    def test_homolog_autorizada_nunca_titulo_rascunho(self):
        resumo = montar_listagem_resumo_nfe(self.nf)
        self.assertNotEqual(resumo['titulo'], 'NF-e em rascunho')
        self.assertIn('Homologação', resumo['titulo'])

    def test_homolog_sem_nnf_ainda_titulo_homolog(self):
        nf2 = NFeSaida.objects.get(pk=self.nf.pk)
        nf2.numero_nfe = ''
        nf2.serie_nfe = ''
        nf2.status_emissao_sefaz = ''
        nf2.status = 'AUTORIZADA_HOMOLOGACAO'
        nf2.save(update_fields=['numero_nfe', 'serie_nfe', 'status_emissao_sefaz', 'status'])
        resumo = montar_listagem_resumo_nfe(nf2)
        self.assertIn('Homologação', resumo['titulo'])
        self.assertEqual(resumo['fiscal_resumo']['badge'], 'Homologação autorizada')

    def test_detalhe_inclui_listagem_resumo_coerente_com_listagem(self):
        row = self._list_row()
        det = self.client.get(f'/api/nf-saidas/{self.nf.pk}/').json()
        self.assertIn('listagem_resumo', det)
        self.assertEqual(
            row['listagem_resumo']['fiscal_resumo']['badge'],
            det['listagem_resumo']['fiscal_resumo']['badge'],
        )
        self.assertEqual(row['listagem_resumo']['titulo'], det['listagem_resumo']['titulo'])

    def test_listagem_paginada_e_permissao(self):
        res = self.client.get('/api/nf-saidas/?page=1')
        self.assertEqual(res.status_code, 200)
        payload = res.json()
        if isinstance(payload, dict):
            self.assertIn('results', payload)
            self.assertIn('count', payload)

    def test_listagem_apresentacao_via_resumo(self):
        row = self._list_row()
        titulo = row['listagem_resumo']['titulo']
        self.assertTrue(titulo)
