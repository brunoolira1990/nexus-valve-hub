"""ERP 4.0.14.3 — Geração manual de Contas a Receber a partir de NF-e autorizada."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.comercial.models import FaturamentoPedidoVenda
from apps.financeiro.models import TituloFinanceiro
from apps.financeiro.services.titulo import excluir_titulo_financeiro
from apps.fiscal.models import NFeSaida
from apps.fiscal.nfe_saida_duplicatas import aplicar_duplicatas_nfe_saida
from apps.fiscal.nfe_saida_financeiro import (
    MSG_ALERTA_NFE_CANCELADA,
    MSG_JA_GERADO,
    MSG_NAO_AUTORIZADA,
    montar_flags_financeiro_nfe,
    preview_contas_receber_de_nfe,
)
from apps.fiscal.tests.test_nfe_saida_40133_duplicatas import _pedido_multi_parcelas
from apps.fiscal.tests.test_nfe_saida_402_emissao_homologacao import _pedido_nf


def _autorizar_nf(nf: NFeSaida) -> NFeSaida:
    """Autoriza em produção — único ambiente elegível a Contas a Receber."""
    nf.status_emissao_sefaz = NFeSaida.StatusEmissaoSefaz.AUTORIZADA_PRODUCAO
    nf.status = 'AUTORIZADA_PRODUCAO'
    nf.ambiente_emissao = NFeSaida.AmbienteEmissao.PRODUCAO
    nf.serie_nfe = '1'
    nf.numero_nfe = '000000003'
    nf.cstat_autorizacao = '100'
    nf.motivo_autorizacao = 'Autorizado o uso da NF-e'
    nf.protocolo_autorizacao = '13526005517408'
    nf.chave_acesso = '35260503999102000150550010000000003123456789'
    nf.xml_autorizado = '<?xml version="1.0"?><nfeProc><NFe/></nfeProc>'
    nf.save()
    if nf.faturamento_pedido_venda_id:
        fat = FaturamentoPedidoVenda.objects.get(pk=nf.faturamento_pedido_venda_id)
        if not (fat.numero_faturamento or '').strip():
            fat.numero_faturamento = 'FAT-20260523-0003'
            fat.save(update_fields=['numero_faturamento'])
    return nf


def _autorizar_nf_homologacao(nf: NFeSaida) -> NFeSaida:
    nf.status_emissao_sefaz = NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO
    nf.status = 'AUTORIZADA_HOMOLOGACAO'
    nf.ambiente_emissao = NFeSaida.AmbienteEmissao.HOMOLOGACAO
    nf.serie_nfe = '0'
    nf.numero_nfe = '000000003'
    nf.cstat_autorizacao = '100'
    nf.motivo_autorizacao = 'Autorizado o uso da NF-e'
    nf.protocolo_autorizacao = '13526005517408'
    nf.chave_acesso = '35260503999102000150550000000000312345678901'
    nf.xml_autorizado = '<?xml version="1.0"?><nfeProc><NFe/></nfeProc>'
    nf.save()
    return nf


class NFe40143GerarContasReceberTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('fin40143', 'fin40143@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.pedido, self.item, self.nf = _pedido_nf()
        self.nf = _autorizar_nf(self.nf)
        aplicar_duplicatas_nfe_saida(self.nf)

    def test_preview_nfe_autorizada(self):
        payload = preview_contas_receber_de_nfe(self.nf)
        self.assertTrue(payload['pode_gerar_contas_receber'])
        self.assertFalse(payload['financeiro_gerado'])
        self.assertEqual(payload['cliente']['id'], self.nf.cliente_id)
        self.assertGreaterEqual(len(payload['parcelas']), 1)
        self.assertEqual(payload['origem']['tipo'], TituloFinanceiro.OrigemTipo.NFE_SAIDA)

    def test_bloqueia_preview_nfe_nao_autorizada(self):
        self.nf.status_emissao_sefaz = 'RASCUNHO'
        self.nf.status = 'RASCUNHO'
        self.nf.cstat_autorizacao = ''
        self.nf.save()
        with self.assertRaises(ValueError) as ctx:
            preview_contas_receber_de_nfe(self.nf)
        self.assertIn(MSG_NAO_AUTORIZADA, str(ctx.exception))

    def test_bloqueia_geracao_nfe_cancelada(self):
        self.nf.status = 'CANCELADA'
        self.nf.save()
        res = self.client.post(f'/api/nf-saidas/{self.nf.pk}/financeiro/gerar-contas-receber/', {
            'parcelas': [{'numero_parcela': 1, 'vencimento': date.today().isoformat(), 'valor': '400.00'}],
        }, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertIn('cancelada', res.json()['detail'].lower())

    def test_gerar_titulo_com_parcelas_duplicatas(self):
        preview = self.client.get(f'/api/nf-saidas/{self.nf.pk}/financeiro/preview-contas-receber/')
        self.assertEqual(preview.status_code, 200)
        parcelas = preview.json()['parcelas']
        res = self.client.post(
            f'/api/nf-saidas/{self.nf.pk}/financeiro/gerar-contas-receber/',
            {'parcelas': parcelas},
            format='json',
        )
        self.assertEqual(res.status_code, 201)
        titulo_id = res.json()['titulo']['id']
        titulo = TituloFinanceiro.objects.get(pk=titulo_id)
        self.assertEqual(titulo.tipo, TituloFinanceiro.Tipo.RECEBER)
        self.assertEqual(titulo.origem_tipo, TituloFinanceiro.OrigemTipo.NFE_SAIDA)
        self.assertEqual(titulo.origem_id, self.nf.pk)
        self.assertEqual(titulo.parcelas.count(), len(parcelas))

    def test_soma_parcelas_bate_total(self):
        preview = preview_contas_receber_de_nfe(self.nf)
        res = self.client.post(
            f'/api/nf-saidas/{self.nf.pk}/financeiro/gerar-contas-receber/',
            {'parcelas': preview['parcelas']},
            format='json',
        )
        self.assertEqual(res.status_code, 201)
        titulo = TituloFinanceiro.objects.get(pk=res.json()['titulo']['id'])
        soma = sum(p.valor_original for p in titulo.parcelas.all())
        self.assertAlmostEqual(float(soma), float(titulo.valor_original), places=2)

    def test_frete_ja_incluso_no_total_nao_e_somado_novamente(self):
        total_original = self.nf.valor_total
        self.nf.valor_frete = Decimal('12.34')
        self.nf.valor_total = total_original + self.nf.valor_frete
        self.nf.save(update_fields=['valor_frete', 'valor_total'])
        aplicar_duplicatas_nfe_saida(self.nf)

        preview = preview_contas_receber_de_nfe(self.nf)
        soma_preview = sum(Decimal(str(parcela['valor'])) for parcela in preview['parcelas'])
        self.assertEqual(soma_preview, self.nf.valor_total)

        resposta = self.client.post(
            f'/api/nf-saidas/{self.nf.pk}/financeiro/gerar-contas-receber/',
            {'parcelas': preview['parcelas']},
            format='json',
        )
        self.assertEqual(resposta.status_code, 201, resposta.json())
        titulo = TituloFinanceiro.objects.get(pk=resposta.json()['titulo']['id'])
        self.assertEqual(titulo.valor_original, self.nf.valor_total)

    def test_nao_permite_geracao_duplicada(self):
        preview = preview_contas_receber_de_nfe(self.nf)
        res1 = self.client.post(
            f'/api/nf-saidas/{self.nf.pk}/financeiro/gerar-contas-receber/',
            {'parcelas': preview['parcelas']},
            format='json',
        )
        self.assertEqual(res1.status_code, 201)
        res2 = self.client.post(
            f'/api/nf-saidas/{self.nf.pk}/financeiro/gerar-contas-receber/',
            {'parcelas': preview['parcelas']},
            format='json',
        )
        self.assertEqual(res2.status_code, 400)
        self.assertIn(MSG_JA_GERADO, res2.json()['detail'])

    def test_endpoint_contas_receber_vinculadas(self):
        preview = preview_contas_receber_de_nfe(self.nf)
        self.client.post(
            f'/api/nf-saidas/{self.nf.pk}/financeiro/gerar-contas-receber/',
            {'parcelas': preview['parcelas']},
            format='json',
        )
        res = self.client.get(f'/api/nf-saidas/{self.nf.pk}/financeiro/contas-receber/')
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body['financeiro_gerado'])
        self.assertEqual(len(body['contas_receber']), 1)

    def test_titulo_nfe_nao_pode_ser_excluido(self):
        preview = preview_contas_receber_de_nfe(self.nf)
        res = self.client.post(
            f'/api/nf-saidas/{self.nf.pk}/financeiro/gerar-contas-receber/',
            {'parcelas': preview['parcelas']},
            format='json',
        )
        titulo = TituloFinanceiro.objects.get(pk=res.json()['titulo']['id'])
        with self.assertRaises(ValueError):
            excluir_titulo_financeiro(titulo, motivo='Tentativa', usuario=self.user)

    def test_nfe_cancelada_depois_nao_apaga_financeiro(self):
        preview = preview_contas_receber_de_nfe(self.nf)
        res = self.client.post(
            f'/api/nf-saidas/{self.nf.pk}/financeiro/gerar-contas-receber/',
            {'parcelas': preview['parcelas']},
            format='json',
        )
        titulo_id = res.json()['titulo']['id']
        xml_antes = self.nf.xml_autorizado
        self.nf.status = 'CANCELADA'
        self.nf.save(update_fields=['status'])
        self.assertTrue(TituloFinanceiro.objects.filter(pk=titulo_id).exists())
        self.nf.refresh_from_db()
        self.assertEqual(self.nf.xml_autorizado, xml_antes)

    def test_nfe_cancelada_depois_alerta_no_titulo(self):
        preview = preview_contas_receber_de_nfe(self.nf)
        res = self.client.post(
            f'/api/nf-saidas/{self.nf.pk}/financeiro/gerar-contas-receber/',
            {'parcelas': preview['parcelas']},
            format='json',
        )
        titulo_id = res.json()['titulo']['id']
        self.nf.status = 'CANCELADA'
        self.nf.save(update_fields=['status'])
        detail = self.client.get(f'/api/financeiro/contas-receber/{titulo_id}/')
        self.assertEqual(detail.status_code, 200)
        self.assertIn(MSG_ALERTA_NFE_CANCELADA, detail.json()['alerta_origem_cancelada'])

    def test_nao_altera_xml_nfe_ao_gerar(self):
        xml_antes = self.nf.xml_autorizado
        dup_antes = list(self.nf.titulos_receber or [])
        preview = preview_contas_receber_de_nfe(self.nf)
        self.client.post(
            f'/api/nf-saidas/{self.nf.pk}/financeiro/gerar-contas-receber/',
            {'parcelas': preview['parcelas']},
            format='json',
        )
        self.nf.refresh_from_db()
        self.assertEqual(self.nf.xml_autorizado, xml_antes)
        self.assertEqual(self.nf.titulos_receber, dup_antes)

    def test_homologacao_nao_permite_financeiro(self):
        from apps.fiscal.nfe_saida_financeiro import MSG_HOMOLOG_SEM_FINANCEIRO

        nf = _autorizar_nf_homologacao(self.nf)
        flags = montar_flags_financeiro_nfe(nf)
        self.assertFalse(flags['pode_gerar_contas_receber'])
        self.assertIn(MSG_HOMOLOG_SEM_FINANCEIRO, flags['motivo_bloqueio_financeiro'])
        with self.assertRaises(ValueError) as ctx:
            preview_contas_receber_de_nfe(nf)
        self.assertIn(MSG_HOMOLOG_SEM_FINANCEIRO, str(ctx.exception))

    def test_autorizacao_persistida_sem_disparo_manual_ainda_sem_titulo(self):
        """Persistir status autorizado sozinho (sem passar pelo emitir_nfe_producao) não cria CR."""
        antes = TituloFinanceiro.objects.filter(
            origem_tipo=TituloFinanceiro.OrigemTipo.NFE_SAIDA,
            origem_id=self.nf.pk,
        ).count()
        self.assertEqual(antes, 0)
        flags = montar_flags_financeiro_nfe(self.nf)
        self.assertFalse(flags['financeiro_gerado'])
        self.assertTrue(flags['pode_gerar_contas_receber'])

    def test_multi_parcelas_duplicatas(self):
        pedido, item = _pedido_multi_parcelas()
        from apps.fiscal.tests.test_nfe_saida_40133_duplicatas import _fiscal_snapshot_item
        from apps.fiscal.tests.test_nfe_saida_40133_duplicatas import _ensure_numeracao_empresa
        from apps.comercial.faturamento_pedido_venda import confirmar_faturamento_pedido, criar_faturamento_pedido
        from apps.fiscal.nfe_saida_from_faturamento import gerar_nfe_saida_from_faturamento

        _fiscal_snapshot_item(item)
        _ensure_numeracao_empresa(pedido.empresa_emitente)
        criado = criar_faturamento_pedido(pedido, {'itens': [{'item_pedido_id': item.pk, 'quantidade': '3'}]})
        confirmar_faturamento_pedido(pedido, criado['faturamento_id'])
        fat = FaturamentoPedidoVenda.objects.get(pk=criado['faturamento_id'])
        r = gerar_nfe_saida_from_faturamento(pedido, fat.pk)
        nf = NFeSaida.objects.get(pk=r['nfe_saida_id'])
        nf = _autorizar_nf(nf)
        nf.numero_nfe = '000000099'
        nf.valor_total = Decimal('300')
        nf.save(update_fields=['numero_nfe', 'valor_total'])
        aplicar_duplicatas_nfe_saida(nf)
        preview = preview_contas_receber_de_nfe(nf)
        self.assertEqual(len(preview['parcelas']), 3)
        res = self.client.post(
            f'/api/nf-saidas/{nf.pk}/financeiro/gerar-contas-receber/',
            {'parcelas': preview['parcelas']},
            format='json',
        )
        self.assertEqual(res.status_code, 201)
        titulo = TituloFinanceiro.objects.get(pk=res.json()['titulo']['id'])
        self.assertEqual(titulo.parcelas.count(), 3)

    def test_soma_invalida_bloqueia(self):
        res = self.client.post(
            f'/api/nf-saidas/{self.nf.pk}/financeiro/gerar-contas-receber/',
            {
                'parcelas': [
                    {
                        'numero_parcela': 1,
                        'vencimento': date.today().isoformat(),
                        'valor': '100.00',
                    },
                ],
            },
            format='json',
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn('soma', res.json()['detail'].lower())

    def test_flags_serializer_nfe(self):
        from apps.fiscal.serializers import NFeSaidaSerializer

        data = NFeSaidaSerializer(self.nf).data
        self.assertTrue(data['pode_gerar_contas_receber'])
        self.assertFalse(data['financeiro_gerado'])
