"""Testes — armazenar XML NF-e na Central DF-e (colisão de PK entre tabelas)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.cadastros.models import Empresa, Fornecedor
from apps.fiscal.central_dfe.armazenar_xml_service import (
    ArmazenarXmlCentralError,
    _resolver_contexto_nfe_central,
)
from apps.fiscal.models import NFeDestinadaManifestacao, NFeEntradaHistoricaImportada
from apps.fiscal.nfe_integracao.nfe_chave_acesso import montar_chave_acesso_nfe


class CentralDfeArmazenarXmlNfeTest(TestCase):
    def setUp(self) -> None:
        User = get_user_model()
        self.user = User.objects.create_superuser('armazenar', 'a@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.emp = Empresa.objects.create(razao_social='Empresa Teste', cnpj='11.111.111/0001-11')
        self.forn = Fornecedor.objects.create(razao_social='Forn', cnpj='22.222.222/0001-22')
        self.dh = timezone.make_aware(datetime(2026, 6, 20, 10, 0, 0))

        self.chave_manifestacao = montar_chave_acesso_nfe(
            cuf='35',
            aamm='2606',
            cnpj_emitente='22222222000122',
            modelo='55',
            serie='1',
            nnf='25730',
            tp_emis='1',
            codigo_numerico='12345678',
        ).chave_44

        self.chave_outra = montar_chave_acesso_nfe(
            cuf='35',
            aamm='2606',
            cnpj_emitente='33333333000133',
            modelo='55',
            serie='1',
            nnf='99999',
            tp_emis='1',
            codigo_numerico='87654321',
        ).chave_44

        self.pk_compartilhado = 90001

        NFeEntradaHistoricaImportada.objects.create(
            pk=self.pk_compartilhado,
            chave_acesso=self.chave_outra,
            numero='99999',
            serie='1',
            modelo='55',
            dh_emissao=self.dh,
            tp_amb='1',
            cstat='100',
            valor_total_nf=Decimal('50'),
            fornecedor_emitente=self.forn,
            empresa_destinataria=self.emp,
        )
        self.manifestacao = NFeDestinadaManifestacao.objects.create(
            pk=self.pk_compartilhado,
            empresa=self.emp,
            chave_acesso=self.chave_manifestacao,
            nsu='123456789012345',
            cnpj_destinatario='11111111000111',
            cnpj_emitente='22222222000122',
            razao_social_emitente='CONEFLANG',
            dh_emissao=self.dh,
            valor_nf=Decimal('1000'),
            ambiente=NFeDestinadaManifestacao.Ambiente.PRODUCAO,
            status_xml=NFeDestinadaManifestacao.StatusXml.DISPONIVEL,
        )

    def test_resolver_prioriza_chave_com_pk_compartilhado(self) -> None:
        ctx = _resolver_contexto_nfe_central(
            self.emp,
            documento_id=self.manifestacao.pk,
            chave_acesso=self.chave_manifestacao,
        )
        self.assertEqual(ctx.chave, self.chave_manifestacao)
        self.assertEqual(ctx.manifestacao.pk, self.manifestacao.pk)
        self.assertIsNone(ctx.nf)

    def test_api_nao_retorna_400_por_colisao_de_pk(self) -> None:
        nf_importada = NFeEntradaHistoricaImportada.objects.create(
            chave_acesso=self.chave_manifestacao,
            numero='25730',
            serie='1',
            modelo='55',
            dh_emissao=self.dh,
            tp_amb='1',
            cstat='100',
            valor_total_nf=Decimal('1000'),
            fornecedor_emitente=self.forn,
            empresa_destinataria=self.emp,
            xml_conteudo='<nfe>importado</nfe>',
        )
        url = reverse('central-dfe-armazenar-xml-nfe-explicit', args=[self.manifestacao.pk])
        with patch(
            'apps.fiscal.central_dfe.armazenar_xml_service.baixar_xml_documento_destinatario',
        ) as mock_baixar:
            mock_baixar.return_value = {
                'nf_entrada_historica_id': nf_importada.pk,
                'duplicado': False,
            }
            resp = self.client.post(
                url,
                {
                    'empresa_id': self.emp.pk,
                    'confirmacao_explicita': True,
                    'chave_acesso': self.chave_manifestacao,
                },
                format='json',
            )

        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        self.assertTrue(resp.data.get('xml_armazenado'))

    def test_id_incompativel_com_chave_retorna_erro_claro(self) -> None:
        with self.assertRaises(ArmazenarXmlCentralError):
            _resolver_contexto_nfe_central(
                self.emp,
                documento_id=999999,
                chave_acesso=self.chave_manifestacao,
            )
