"""ERP 4.0.13.6.10 — Persistência e validação da aba Transporte na conferência NF-e."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from apps.cadastros.models import Transportadora
from apps.fiscal.models import NFeSaida
from apps.fiscal.nfe_saida_atualizar_impostos import aplicar_atualizacao_impostos_nfe
from apps.fiscal.nfe_saida_conferencia import montar_conferencia_nfe_saida
from apps.fiscal.nfe_saida_from_faturamento import gerar_nfe_saida_from_faturamento
from apps.fiscal.nfe_saida_prontidao import marcar_nfe_pronta_para_emissao, validar_conferencia_nfe
from apps.fiscal.nfe_saida_preview import gerar_dados_preview_nfe_saida
from apps.fiscal.nfe_transp_bindings import aplicar_transp_nfelib, montar_transporte_dados_nfe
from apps.fiscal.nfe_transporte_validacao import validar_coerencia_transporte_nfe
from apps.fiscal.tests.test_nfe_saida_352_atualizar_impostos import _regra_84818200_sp_rj
from apps.fiscal.tests.test_nfe_saida_351_ux import NFeSaida351UxTests
from apps.fiscal.validacao_nfe_saida import validar_nfe_saida_para_emissao


class NFeTransporte4013610Tests(NFeSaida351UxTests):
    def setUp(self):
        super().setUp()
        self.transp = Transportadora.objects.create(
            razao_social='WINNER EXPRESS TRANSPORTES LTDA',
            cnpj='32241095000121',
            ie='1234567890',
        )

    def _payload_transporte(self, **extra):
        base = {
            'transportadora_id': self.transp.pk,
            'modalidade_frete': '0',
            'valor_frete': '150.00',
            'quantidade_volumes': 1,
            'especie_volumes': 'VOLUME',
            'marca_volumes': '',
            'numeracao_volumes': '',
            'peso_bruto': '500',
            'peso_liquido': '500',
            'placa_veiculo': '',
            'uf_veiculo': '',
        }
        base.update(extra)
        return base

    def _salvar_transporte(self, nf: NFeSaida, **extra) -> NFeSaida:
        resp = self.client.patch(
            f'/api/nf-saidas/{nf.pk}/',
            self._payload_transporte(**extra),
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        nf.refresh_from_db()
        return nf

    def test_salvar_persiste_modalidade_diferente_de_9(self):
        nf = self._nf_fat()
        self._salvar_transporte(nf, modalidade_frete='0')
        self.assertEqual(str(nf.modalidade_frete), '0')

    def test_salvar_persiste_transportadora(self):
        nf = self._nf_fat()
        self._salvar_transporte(nf)
        self.assertEqual(nf.transportadora_id, self.transp.pk)

    def test_salvar_persiste_volumes_e_pesos(self):
        nf = self._nf_fat()
        self._salvar_transporte(nf)
        self.assertEqual(nf.quantidade_volumes, 1)
        self.assertEqual(nf.especie_volumes, 'VOLUME')
        self.assertEqual(nf.peso_bruto, Decimal('500'))
        self.assertEqual(nf.peso_liquido, Decimal('500'))

    def test_validar_conferencia_nao_volta_modfrete_para_9(self):
        nf = self._salvar_transporte(self._nf_fat(), modalidade_frete='0')
        validar_conferencia_nfe(nf, usuario=self.user)
        nf.refresh_from_db()
        self.assertEqual(str(nf.modalidade_frete), '0')
        conf = montar_conferencia_nfe_saida(nf)
        self.assertEqual(conf['transporte']['modalidade_frete'], '0')

    @override_settings(USE_CENARIO_FISCAL_SAIDA_FOR_PROPOSTAS=True)
    @patch('apps.cadastros.endereco_fiscal.consultar_cep_viacep')
    def test_atualizar_fiscal_nao_altera_transporte(self, mock_cep):
        _regra_84818200_sp_rj()
        mock_cep.return_value = {
            'cidade': 'Rio de Janeiro',
            'uf': 'RJ',
            'cep': '20040-020',
            'logradouro': 'Rua da Assembleia',
            'bairro': 'Centro',
            'complemento': '',
        }
        nf = self._nf_fat(reforma=False)
        item = nf.itens.first()
        assert item is not None
        item.snapshot_fiscal = {'ncm': '84818200'}
        item.save(update_fields=['snapshot_fiscal'])
        nf = self._salvar_transporte(nf, modalidade_frete='0')
        aplicar_atualizacao_impostos_nfe(nf, usuario=self.user)
        nf.refresh_from_db()
        self.assertEqual(str(nf.modalidade_frete), '0')
        self.assertEqual(nf.transportadora_id, self.transp.pk)
        self.assertEqual(nf.quantidade_volumes, 1)

    def test_marcar_pronta_nao_altera_transporte(self):
        nf = self._salvar_transporte(self._nf_fat(), modalidade_frete='0')
        with patch('apps.fiscal.nfe_saida_prontidao.validar_nfe_saida_para_emissao') as mock_val:
            mock_val.return_value = {'total_pendencias': 0, 'pendencias': [], 'grupos': {}}
            marcar_nfe_pronta_para_emissao(nf, usuario=self.user)
        nf.refresh_from_db()
        self.assertEqual(str(nf.modalidade_frete), '0')
        self.assertEqual(nf.transportadora_id, self.transp.pk)

    def test_preview_xml_usa_modfrete_salvo(self):
        nf = self._salvar_transporte(self._nf_fat(), modalidade_frete='0')
        dados = gerar_dados_preview_nfe_saida(nf, incluir_validacao_emissao=False)
        self.assertEqual(dados['transporte']['mod_frete'], '0')

    def test_mod9_com_transportadora_gera_pendencia(self):
        nf = self._nf_fat()
        nf.transportadora = self.transp
        nf.modalidade_frete = '9'
        nf.save(update_fields=['transportadora', 'modalidade_frete'])
        codigos = [c['codigo'] for c in validar_coerencia_transporte_nfe(nf)]
        self.assertIn('TRANSPORTE_MOD9_INCOERENTE', codigos)
        self.assertIn('TRANSPORTE_MOD9_COM_TRANSPORTADORA', codigos)

    def test_mod9_com_volumes_gera_pendencia(self):
        nf = self._nf_fat()
        nf.modalidade_frete = '9'
        nf.quantidade_volumes = 1
        nf.save(update_fields=['modalidade_frete', 'quantidade_volumes'])
        codigos = [c['codigo'] for c in validar_coerencia_transporte_nfe(nf)]
        self.assertIn('TRANSPORTE_MOD9_COM_VOLUMES', codigos)

    def test_mod9_com_pesos_gera_pendencia(self):
        nf = self._nf_fat()
        nf.modalidade_frete = '9'
        nf.peso_bruto = Decimal('500')
        nf.save(update_fields=['modalidade_frete', 'peso_bruto'])
        codigos = [c['codigo'] for c in validar_coerencia_transporte_nfe(nf)]
        self.assertIn('TRANSPORTE_MOD9_INCOERENTE', codigos)

    def test_mod9_limpo_passa(self):
        nf = self._nf_fat()
        nf.modalidade_frete = '9'
        nf.save(update_fields=['modalidade_frete'])
        pendencias = [c for c in validar_coerencia_transporte_nfe(nf) if c['tipo'] == 'PENDENCIA']
        self.assertEqual(pendencias, [])

    def test_mod_diferente_de_9_com_transportadora_passa_coerencia_mod9(self):
        nf = self._salvar_transporte(self._nf_fat(), modalidade_frete='0')
        incoerentes = [
            c for c in validar_coerencia_transporte_nfe(nf) if c['codigo'].startswith('TRANSPORTE_MOD9')
        ]
        self.assertEqual(incoerentes, [])

    def test_placa_sem_uf_gera_pendencia(self):
        nf = self._nf_fat()
        nf.modalidade_frete = '0'
        nf.placa_veiculo = 'ABC1D23'
        nf.save(update_fields=['modalidade_frete', 'placa_veiculo'])
        codigos = [c['codigo'] for c in validar_coerencia_transporte_nfe(nf)]
        self.assertIn('TRANSPORTE_PLACA_SEM_UF', codigos)

    def test_uf_sem_placa_gera_pendencia(self):
        nf = self._nf_fat()
        nf.modalidade_frete = '0'
        nf.uf_veiculo = 'SP'
        nf.save(update_fields=['modalidade_frete', 'uf_veiculo'])
        codigos = [c['codigo'] for c in validar_coerencia_transporte_nfe(nf)]
        self.assertIn('TRANSPORTE_UF_SEM_PLACA', codigos)

    def test_xml_mod9_nao_envia_transportadora_volumes(self):
        from nfelib.nfe.bindings import v4_0 as nfe

        inf = nfe.Tnfe.InfNfe()
        aplicar_transp_nfelib(
            inf,
            nfe,
            {
                'mod_frete': '9',
                'transportadora_nome': 'WINNER EXPRESS TRANSPORTES LTDA',
                'transportadora_cnpj': '32241095000121',
                'quantidade_volumes': 1,
                'peso_bruto': '500.000',
            },
        )
        self.assertEqual(inf.transp.modFrete, '9')
        self.assertIsNone(getattr(inf.transp, 'transporta', None))
        self.assertFalse(getattr(inf.transp, 'vol', None))

    def test_xml_mod_diferente_de_9_mantem_transportadora_volumes(self):
        from nfelib.nfe.bindings import v4_0 as nfe

        inf = nfe.Tnfe.InfNfe()
        aplicar_transp_nfelib(
            inf,
            nfe,
            montar_transporte_dados_nfe(
                self._salvar_transporte(self._nf_fat(), modalidade_frete='0'),
            ),
        )
        self.assertEqual(inf.transp.modFrete, '0')
        self.assertEqual(inf.transp.transporta.CNPJ, '32241095000121')
        self.assertEqual(inf.transp.vol[0].qVol, '1')

    def test_checklist_bloqueia_inconsistencia_transporte(self):
        nf = self._nf_fat()
        nf.transportadora = self.transp
        nf.modalidade_frete = '9'
        nf.quantidade_volumes = 1
        nf.peso_bruto = Decimal('500')
        nf.save()
        val = validar_nfe_saida_para_emissao(nf)
        codigos = [
            p.get('codigo')
            for g in (val.get('grupos') or {}).values()
            for p in g
        ]
        self.assertIn('TRANSPORTE_MOD9_INCOERENTE', codigos)

    def test_transporte_nao_altera_impostos(self):
        nf = self._nf_fat()
        item = nf.itens.first()
        assert item is not None
        snap_antes = dict(item.snapshot_fiscal or {})
        self._salvar_transporte(nf, modalidade_frete='0')
        item.refresh_from_db()
        self.assertEqual(item.snapshot_fiscal or {}, snap_antes)
