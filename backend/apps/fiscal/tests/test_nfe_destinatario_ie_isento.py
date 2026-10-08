"""Testes do perfil fiscal do destinatário — campo ie_isento no cadastro de Cliente."""

from django.test import TestCase

from apps.cadastros.models import Cliente
from apps.fiscal.nfe_destinatario_fiscal import resolver_perfil_destinatario_cliente
from apps.regras_fiscais.models import RegraFiscalSaida


class ClienteIeIsentoPerfilFiscalTests(TestCase):
    def _cliente(self, **kwargs):
        defaults = {
            'razao_social': 'Cliente IE Teste',
            'cnpj': '11222333000181',
            'uf': 'SP',
        }
        defaults.update(kwargs)
        return Cliente.objects.create(**defaults)

    def test_ie_isento_marca_ind_ie_dest_2(self):
        cliente = self._cliente(ie_isento=True, ie='')
        perfil = resolver_perfil_destinatario_cliente(cliente)
        self.assertEqual(perfil.ind_ie_dest, '2')
        self.assertEqual(
            perfil.destinatario_contribuinte,
            RegraFiscalSaida.DestinatarioContribuinte.NAO_CONTRIBUINTE,
        )

    def test_ie_isento_prevalece_sobre_ie_com_digitos(self):
        cliente = self._cliente(ie_isento=True, ie='123456789012')
        perfil = resolver_perfil_destinatario_cliente(cliente)
        self.assertEqual(perfil.ind_ie_dest, '2')

    def test_texto_isento_legado_sem_flag(self):
        cliente = self._cliente(ie='ISENTO', ie_isento=False)
        perfil = resolver_perfil_destinatario_cliente(cliente)
        self.assertEqual(perfil.ind_ie_dest, '2')

    def test_contribuinte_com_ie_numerica(self):
        cliente = self._cliente(ie='123456789012', ie_isento=False)
        perfil = resolver_perfil_destinatario_cliente(cliente)
        self.assertEqual(perfil.ind_ie_dest, '1')
        self.assertEqual(
            perfil.destinatario_contribuinte,
            RegraFiscalSaida.DestinatarioContribuinte.CONTRIBUINTE,
        )

    def test_sem_ie_nem_isento_e_nao_contribuinte(self):
        cliente = self._cliente(ie='', ie_isento=False)
        perfil = resolver_perfil_destinatario_cliente(cliente)
        self.assertEqual(perfil.ind_ie_dest, '9')
