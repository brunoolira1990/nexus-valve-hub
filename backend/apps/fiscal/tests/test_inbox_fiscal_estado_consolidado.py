"""Inbox Fiscal — estado consolidado derivado (read-only)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.cadastros.models import Empresa, Fornecedor
from apps.fiscal.inbox_fiscal.estado_consolidado import (
    ESTADO_BLOQUEADO,
    ESTADO_CTE_CONCLUIDO,
    ESTADO_CTE_XML_DISPONIVEL,
    ESTADO_DIVERGENTE,
    ESTADO_NFE_CONCLUIDO,
    ESTADO_NFE_CONFERIDO,
    ESTADO_NFE_EM_CONFERENCIA,
    ESTADO_NFE_ESTOQUE_APLICADO,
    ESTADO_NFE_PRECISA_MANIFESTAR,
    ESTADO_NFE_RECEBIDO,
    ESTADO_NFE_XML_DISPONIVEL,
    derivar_estado_cte,
    derivar_estado_nfe_fornecedor_historica,
    derivar_estado_nfe_fornecedor_resumo,
)
from apps.fiscal.models import (
    CTeHistoricoImportado,
    ItemNFeEntradaConferencia,
    ItemNFeEntradaHistoricaImportada,
    NFeDestinadaManifestacao,
    NFeEntrada,
    NFeEntradaConferencia,
    NFeEntradaHistoricaImportada,
)


def _dh() -> datetime:
    return timezone.make_aware(datetime(2026, 5, 10, 12, 0, 0))


class EstadoConsolidadoDerivacaoTest(TestCase):
    def setUp(self) -> None:
        self.emp = Empresa.objects.create(razao_social='Emp Inbox', cnpj='11.111.111/0001-11')
        self.forn = Fornecedor.objects.create(razao_social='Forn Inbox', cnpj='22.222.222/0001-22')
        self.dh = _dh()

    def test_resumo_pendente_manifestacao(self) -> None:
        man = NFeDestinadaManifestacao.objects.create(
            empresa=self.emp,
            chave_acesso='9' * 44,
            cnpj_destinatario='11111111000111',
            status_manifestacao=NFeDestinadaManifestacao.StatusManifestacao.PENDENTE,
            status_xml=NFeDestinadaManifestacao.StatusXml.RESUMO,
        )
        estado = derivar_estado_nfe_fornecedor_resumo(man)
        self.assertEqual(estado.estado, ESTADO_NFE_PRECISA_MANIFESTAR)

    def test_resumo_pos_ciencia_xml_disponivel(self) -> None:
        man = NFeDestinadaManifestacao.objects.create(
            empresa=self.emp,
            chave_acesso='8' * 44,
            cnpj_destinatario='11111111000111',
            status_manifestacao=NFeDestinadaManifestacao.StatusManifestacao.CIENTE,
            status_xml=NFeDestinadaManifestacao.StatusXml.DISPONIVEL,
        )
        estado = derivar_estado_nfe_fornecedor_resumo(man)
        self.assertEqual(estado.estado, ESTADO_NFE_XML_DISPONIVEL)

    def test_historica_sem_xml_recebido(self) -> None:
        nf = NFeEntradaHistoricaImportada.objects.create(
            chave_acesso='1' * 44,
            numero='10',
            serie='1',
            dh_emissao=self.dh,
            tp_amb='1',
            cstat='100',
            valor_total_nf=Decimal('100'),
            fornecedor_emitente=self.forn,
            empresa_destinataria=self.emp,
        )
        estado = derivar_estado_nfe_fornecedor_historica(nf)
        self.assertEqual(estado.estado, ESTADO_NFE_RECEBIDO)

    def test_historica_com_xml_disponivel(self) -> None:
        nf = NFeEntradaHistoricaImportada.objects.create(
            chave_acesso='2' * 44,
            numero='20',
            serie='1',
            dh_emissao=self.dh,
            tp_amb='1',
            cstat='100',
            valor_total_nf=Decimal('200'),
            xml_conteudo='<nfeProc/>',
            fornecedor_emitente=self.forn,
            empresa_destinataria=self.emp,
        )
        estado = derivar_estado_nfe_fornecedor_historica(nf)
        self.assertEqual(estado.estado, ESTADO_NFE_XML_DISPONIVEL)

    def test_historica_em_conferencia(self) -> None:
        nf = NFeEntradaHistoricaImportada.objects.create(
            chave_acesso='3' * 44,
            numero='30',
            serie='1',
            dh_emissao=self.dh,
            tp_amb='1',
            cstat='100',
            valor_total_nf=Decimal('300'),
            xml_conteudo='<nfeProc/>',
            fornecedor_emitente=self.forn,
            empresa_destinataria=self.emp,
        )
        item_nf = ItemNFeEntradaHistoricaImportada.objects.create(nf=nf, n_item=1)
        conf = NFeEntradaConferencia.objects.create(nf_entrada_historica=nf)
        ItemNFeEntradaConferencia.objects.create(
            conferencia=conf,
            item_nfe_historico=item_nf,
            status=ItemNFeEntradaConferencia.Status.PRODUTO_VINCULADO,
            produto_id=None,
        )
        estado = derivar_estado_nfe_fornecedor_historica(nf, conferencia=conf)
        self.assertEqual(estado.estado, ESTADO_NFE_EM_CONFERENCIA)

    def test_historica_preparada_conferido(self) -> None:
        nf = NFeEntradaHistoricaImportada.objects.create(
            chave_acesso='4' * 44,
            numero='40',
            serie='1',
            dh_emissao=self.dh,
            tp_amb='1',
            cstat='100',
            valor_total_nf=Decimal('400'),
            xml_conteudo='<nfeProc/>',
            fornecedor_emitente=self.forn,
            empresa_destinataria=self.emp,
        )
        conf = NFeEntradaConferencia.objects.create(
            nf_entrada_historica=nf,
            status=NFeEntradaConferencia.Status.PREPARADA,
            preparado_em=self.dh,
        )
        estado = derivar_estado_nfe_fornecedor_historica(nf, conferencia=conf)
        self.assertEqual(estado.estado, ESTADO_NFE_CONFERIDO)

    def test_historica_estoque_aplicado(self) -> None:
        nf = NFeEntradaHistoricaImportada.objects.create(
            chave_acesso='5' * 44,
            numero='50',
            serie='1',
            dh_emissao=self.dh,
            tp_amb='1',
            cstat='100',
            valor_total_nf=Decimal('500'),
            xml_conteudo='<nfeProc/>',
            fornecedor_emitente=self.forn,
            empresa_destinataria=self.emp,
        )
        conf = NFeEntradaConferencia.objects.create(
            nf_entrada_historica=nf,
            status=NFeEntradaConferencia.Status.PREPARADA,
            estoque_aplicado_em=self.dh,
        )
        estado = derivar_estado_nfe_fornecedor_historica(nf, conferencia=conf)
        self.assertEqual(estado.estado, ESTADO_NFE_ESTOQUE_APLICADO)

    def test_chave_operacional_sem_estoque_base_nao_conclui(self) -> None:
        """Mesma chave em NFeEntrada operacional não deve mascarar pendência de estoque na base."""
        nf = NFeEntradaHistoricaImportada.objects.create(
            chave_acesso='6' * 44,
            numero='60',
            serie='1',
            dh_emissao=self.dh,
            tp_amb='1',
            cstat='100',
            valor_total_nf=Decimal('600'),
            xml_conteudo='<nfeProc/>',
            fornecedor_emitente=self.forn,
            empresa_destinataria=self.emp,
        )
        NFeEntrada.objects.create(
            numero='60',
            serie='1',
            chave_acesso='6' * 44,
            fornecedor=self.forn,
            data=self.dh.date(),
            valor_total=Decimal('600'),
        )
        estado = derivar_estado_nfe_fornecedor_historica(nf, ja_lancado_operacional=True)
        self.assertEqual(estado.estado, ESTADO_NFE_XML_DISPONIVEL)
        self.assertNotEqual(estado.estado, ESTADO_NFE_CONCLUIDO)
        self.assertTrue(estado.detalhes.get('chave_em_nfe_entrada_operacional'))
        self.assertIn('base importada', (estado.detalhes.get('observacao') or '').lower())

    def test_chave_operacional_com_estoque_base_aplicado(self) -> None:
        nf = NFeEntradaHistoricaImportada.objects.create(
            chave_acesso='8' * 44,
            numero='80',
            serie='1',
            dh_emissao=self.dh,
            tp_amb='1',
            cstat='100',
            valor_total_nf=Decimal('800'),
            xml_conteudo='<nfeProc/>',
            fornecedor_emitente=self.forn,
            empresa_destinataria=self.emp,
        )
        NFeEntradaConferencia.objects.create(
            nf_entrada_historica=nf,
            status=NFeEntradaConferencia.Status.PREPARADA,
            estoque_aplicado_em=self.dh,
        )
        NFeEntrada.objects.create(
            numero='80',
            serie='1',
            chave_acesso='8' * 44,
            fornecedor=self.forn,
            data=self.dh.date(),
            valor_total=Decimal('800'),
        )
        estado = derivar_estado_nfe_fornecedor_historica(nf, ja_lancado_operacional=True)
        self.assertEqual(estado.estado, ESTADO_NFE_ESTOQUE_APLICADO)

    def test_historica_divergente(self) -> None:
        nf = NFeEntradaHistoricaImportada.objects.create(
            chave_acesso='7' * 44,
            numero='70',
            serie='1',
            dh_emissao=self.dh,
            tp_amb='1',
            cstat='100',
            valor_total_nf=Decimal('700'),
            xml_conteudo='<nfeProc/>',
            fornecedor_emitente=self.forn,
            empresa_destinataria=self.emp,
        )
        item_nf = ItemNFeEntradaHistoricaImportada.objects.create(nf=nf, n_item=1)
        conf = NFeEntradaConferencia.objects.create(nf_entrada_historica=nf, divergencias_aceitas=False)
        ItemNFeEntradaConferencia.objects.create(
            conferencia=conf,
            item_nfe_historico=item_nf,
            status=ItemNFeEntradaConferencia.Status.DIVERGENTE,
        )
        estado = derivar_estado_nfe_fornecedor_historica(nf, conferencia=conf)
        self.assertEqual(estado.estado, ESTADO_DIVERGENTE)
        self.assertTrue(estado.motivo)

    def test_cte_xml_disponivel(self) -> None:
        cte = CTeHistoricoImportado.objects.create(
            chave_acesso='4' * 44,
            numero='400',
            serie='1',
            dh_emissao=self.dh,
            tp_amb='1',
            cstat='100',
            xml_conteudo='<cteProc/>',
            valor_total_servico=Decimal('90'),
            empresa_tomadora=self.emp,
            status_conferencia='IMPORTADO',
        )
        estado = derivar_estado_cte(cte)
        self.assertEqual(estado.estado, ESTADO_CTE_XML_DISPONIVEL)

    def test_cte_conferido_concluido(self) -> None:
        User = get_user_model()
        user = User.objects.create_user(username='cte_conf', password='x')
        cte = CTeHistoricoImportado.objects.create(
            chave_acesso='5' * 44,
            numero='500',
            serie='1',
            dh_emissao=self.dh,
            tp_amb='1',
            cstat='100',
            xml_conteudo='<cteProc/>',
            valor_total_servico=Decimal('120'),
            empresa_tomadora=self.emp,
            status_conferencia='CONFERIDO',
            apto_operacional=True,
            conferido_em=self.dh,
            conferido_por=user,
        )
        estado = derivar_estado_cte(cte)
        self.assertEqual(estado.estado, ESTADO_CTE_CONCLUIDO)

    def test_cte_divergente(self) -> None:
        cte = CTeHistoricoImportado.objects.create(
            chave_acesso='6' * 44,
            numero='600',
            serie='1',
            dh_emissao=self.dh,
            tp_amb='1',
            cstat='100',
            xml_conteudo='<cteProc/>',
            valor_total_servico=Decimal('80'),
            empresa_tomadora=self.emp,
            status_conferencia='DIVERGENTE',
            divergencia_motivo='Valor divergente',
        )
        estado = derivar_estado_cte(cte)
        self.assertEqual(estado.estado, ESTADO_DIVERGENTE)
        self.assertIn('Valor divergente', estado.motivo)

    def test_cte_bloqueado_ignorado(self) -> None:
        cte = CTeHistoricoImportado.objects.create(
            chave_acesso='7' * 44,
            numero='700',
            serie='1',
            dh_emissao=self.dh,
            tp_amb='1',
            cstat='100',
            xml_conteudo='<cteProc/>',
            valor_total_servico=Decimal('50'),
            empresa_tomadora=self.emp,
            status_conferencia='IGNORADO',
            ignorado_operacionalmente=True,
            divergencia_motivo='Sem uso operacional',
        )
        estado = derivar_estado_cte(cte)
        self.assertEqual(estado.estado, ESTADO_BLOQUEADO)


class CentralDfeEstadoConsolidadoApiTest(TestCase):
    def setUp(self) -> None:
        User = get_user_model()
        self.user = User.objects.create_user(username='inbox_api', password='test')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.url = reverse('central-dfe-list')
        self.dh = _dh()
        self.emp = Empresa.objects.create(razao_social='Emp API', cnpj='11.111.111/0001-11')
        self.forn = Fornecedor.objects.create(razao_social='Forn API', cnpj='22.222.222/0001-22')
        NFeEntradaHistoricaImportada.objects.create(
            chave_acesso='1' * 44,
            numero='100',
            serie='1',
            dh_emissao=self.dh,
            tp_amb='1',
            cstat='100',
            valor_total_nf=Decimal('150'),
            xml_conteudo='<nfe/>',
            fornecedor_emitente=self.forn,
            empresa_destinataria=self.emp,
        )
        CTeHistoricoImportado.objects.create(
            chave_acesso='4' * 44,
            numero='400',
            serie='1',
            dh_emissao=self.dh,
            tp_amb='1',
            cstat='100',
            xml_conteudo='<cte/>',
            valor_total_servico=Decimal('90'),
            empresa_tomadora=self.emp,
            status_conferencia='IMPORTADO',
        )

    def test_listagem_expoe_estado_consolidado(self) -> None:
        resp = self.client.get(self.url, {'empresa_id': self.emp.pk})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for row in resp.data['results']:
            self.assertIn('estado_consolidado', row)
            self.assertIn('estado_consolidado_label', row)
            self.assertTrue(row['estado_consolidado'])

    def test_filtro_estado_consolidado(self) -> None:
        resp = self.client.get(
            self.url,
            {
                'empresa_id': self.emp.pk,
                'tipo_documento': 'CTE',
                'estado_consolidado': ESTADO_CTE_XML_DISPONIVEL,
            },
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['count'], 1)
        self.assertEqual(resp.data['results'][0]['tipo_documento'], 'CTE')
        self.assertEqual(resp.data['results'][0]['estado_consolidado'], ESTADO_CTE_XML_DISPONIVEL)

    def test_resumo_manifestacao_na_api(self) -> None:
        chave = '5' * 44
        NFeDestinadaManifestacao.objects.create(
            empresa=self.emp,
            chave_acesso=chave,
            cnpj_destinatario='11111111000111',
            dh_emissao=self.dh,
            valor_nf=Decimal('99'),
            ambiente=NFeDestinadaManifestacao.Ambiente.PRODUCAO,
            status_manifestacao=NFeDestinadaManifestacao.StatusManifestacao.PENDENTE,
            status_xml=NFeDestinadaManifestacao.StatusXml.RESUMO,
        )
        resp = self.client.get(self.url, {'empresa_id': self.emp.pk})
        row = next(r for r in resp.data['results'] if r['chave_acesso'] == chave)
        self.assertEqual(row['estado_consolidado'], ESTADO_NFE_PRECISA_MANIFESTAR)
        self.assertEqual(row['manifestacao_id'], row['id'])
