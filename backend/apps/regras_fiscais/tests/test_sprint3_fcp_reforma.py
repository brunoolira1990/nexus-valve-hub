"""Sprint 3 — FCP opcional e Reforma Tributária (JSON preparatório)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.cadastros.models import Fornecedor
from apps.fiscal.models import (
    ItemNFeEntradaHistoricaImportada,
    NFeEntradaConferencia,
    NFeEntradaHistoricaImportada,
)
from apps.produtos.models import FamiliaProduto, Produto
from apps.regras_fiscais.cenario_fiscal_entrada import serializar_configuracao_matriz
from apps.regras_fiscais.entrada_fiscal import (
    ContextoFiscalEntrada,
    avaliar_item_entrada_fiscal,
    validar_bloqueio_fiscal_preparar_conferencia,
)
from apps.regras_fiscais.models import CenarioFiscalEntrada, CenarioFiscalEntradaEscopo, RegraFiscalEntrada
from apps.regras_fiscais.reforma_tributaria_config import REFORMA_TRIBUTARIA_KEYS


def _cnpj() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


class Sprint3FcpReformaTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user('s3_fcp', 's3@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(user)
        self.forn = Fornecedor.objects.create(razao_social='Forn S3', cnpj=_cnpj(), uf='SP')
        fam = FamiliaProduto.objects.create(
            codigo_figura='FS3',
            descricao_base='Fam',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
            tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
            categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
        )
        self.prod = Produto.objects.create(
            familia=fam,
            descricao='Prod S3',
            modo_codigo=Produto.ModoCodigo.MANUAL,
            codigo_completo='S3-001',
            unidade='PC',
            ncm='84818099',
        )
        self.cenario = CenarioFiscalEntrada.objects.create(
            nome='Cenário S3',
            regime_tributario='SIMPLES',
            ativo=True,
            padrao=True,
        )
        self.escopo = CenarioFiscalEntradaEscopo.objects.create(
            cenario=self.cenario,
            tipo_escopo=CenarioFiscalEntradaEscopo.TipoEscopo.GERAL,
            ativo=True,
        )
        nf = NFeEntradaHistoricaImportada.objects.create(
            chave_acesso=('35' + '2' * 42)[:44],
            numero='9002',
            serie='1',
            modelo='55',
            dh_emissao=timezone.make_aware(datetime(2026, 3, 2, 10, 0)),
            valor_total_nf=Decimal('100'),
            fornecedor_emitente=self.forn,
            emit_json={'enderEmit': {'UF': 'SP'}},
            dest_json={'enderDest': {'UF': 'RJ'}},
        )
        item_nf = ItemNFeEntradaHistoricaImportada.objects.create(
            nf=nf,
            n_item=1,
            prod_json={'CFOP': '6102', 'NCM': '84818099', 'qCom': '1', 'uCom': 'PC'},
            imposto_json={'ICMS': {'ICMS00': {'CST': '00', 'vBC': '100', 'vICMS': '18', 'pICMS': '18'}}},
        )
        self.conf = NFeEntradaConferencia.objects.create(nf_entrada_historica=nf)
        self.item_conf, _ = self.conf.itens.get_or_create(item_nfe_historico=item_nf)
        self.item_conf.produto = self.prod
        self.item_conf.save(update_fields=['produto'])
        self.ctx = ContextoFiscalEntrada(uf_origem='SP', uf_destino='RJ')

    def _regra_base(self, **kwargs) -> RegraFiscalEntrada:
        defaults = dict(
            cenario=self.cenario,
            escopo=self.escopo,
            nome='Regra S3',
            ativo=True,
            cfop_origem='6102',
            cfop_entrada='1102',
            cst_icms_esperado='00',
            aliquota_icms=Decimal('18'),
            severidade=RegraFiscalEntrada.Severidade.INFORMATIVO,
        )
        defaults.update(kwargs)
        return RegraFiscalEntrada.objects.create(**defaults)

    def test_regra_antiga_sem_fcp_reforma_continua_ok(self):
        regra = self._regra_base()
        resultado = avaliar_item_entrada_fiscal(self.item_conf, self.ctx, [regra])
        self.assertEqual(resultado['status'], 'OK')
        self.assertNotIn('tem_reforma_configurada', resultado)

    def test_fcp_vazio_nao_gera_divergencia(self):
        regra = self._regra_base()
        resultado = avaliar_item_entrada_fiscal(self.item_conf, self.ctx, [regra])
        campos = [d['campo'] for d in resultado['divergencias']]
        self.assertNotIn('aliquota_fcp', campos)

    def test_fcp_igual_xml_ok(self):
        hist = self.item_conf.item_nfe_historico
        hist.imposto_json = {
            'ICMS': {'ICMS00': {'CST': '00', 'pICMS': '18', 'pFCP': '2.00'}},
        }
        hist.save(update_fields=['imposto_json'])
        regra = self._regra_base(aliquota_fcp=Decimal('2'))
        resultado = avaliar_item_entrada_fiscal(self.item_conf, self.ctx, [regra])
        self.assertEqual(resultado['status'], 'OK')

    def test_fcp_divergente_gera_alerta(self):
        hist = self.item_conf.item_nfe_historico
        hist.imposto_json = {
            'ICMS': {'ICMS00': {'CST': '00', 'pICMS': '18', 'pFCP': '1.00'}},
        }
        hist.save(update_fields=['imposto_json'])
        regra = self._regra_base(aliquota_fcp=Decimal('2'))
        resultado = avaliar_item_entrada_fiscal(self.item_conf, self.ctx, [regra])
        self.assertEqual(resultado['status'], 'ALERTA')
        self.assertTrue(any(d['campo'] == 'aliquota_fcp' for d in resultado['divergencias']))

    def test_fcp_regra_preenchida_xml_sem_fcp_alerta(self):
        regra = self._regra_base(aliquota_fcp=Decimal('2'))
        resultado = avaliar_item_entrada_fiscal(self.item_conf, self.ctx, [regra])
        self.assertEqual(resultado['status'], 'ALERTA')
        div = next(d for d in resultado['divergencias'] if d['campo'] == 'aliquota_fcp')
        self.assertIn('não informa FCP', div['mensagem'])

    def test_reforma_json_salva_e_api(self):
        payload = {
            'cenario_id': self.cenario.id,
            'escopo_id': self.escopo.id,
            'nome': 'Com reforma',
            'cfop_origem': '6102',
            'cfop_entrada': '1102',
            'reforma_tributaria': {'cst_ibs_cbs': '000', 'aliquota_cbs': '0.9'},
        }
        url = reverse('regrafiscal-entrada-list')
        resp = self.client.post(url, payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.content)
        self.assertEqual(resp.data['reforma_tributaria']['cst_ibs_cbs'], '000')

    def test_reforma_preenchida_no_resultado_sem_divergir(self):
        regra = self._regra_base(reforma_tributaria={'aliquota_cbs': '1.5'})
        resultado = avaliar_item_entrada_fiscal(self.item_conf, self.ctx, [regra])
        self.assertTrue(resultado.get('tem_reforma_configurada'))
        self.assertEqual(resultado['status'], 'OK')

    def test_reforma_nao_bloqueia_preparar(self):
        regra = self._regra_base(reforma_tributaria={'aliquota_ibs_estadual': '5'})
        resultado = avaliar_item_entrada_fiscal(self.item_conf, self.ctx, [regra])
        self.assertEqual(resultado['status'], 'OK')
        bloqueios = validar_bloqueio_fiscal_preparar_conferencia(self.conf, [self.item_conf])
        self.assertEqual(bloqueios, [])

    def test_resumo_matriz_indica_fcp(self):
        regra = self._regra_base(cst_icms_esperado='20', aliquota_icms=Decimal('18'), aliquota_fcp=Decimal('2'))
        cfg = serializar_configuracao_matriz(regra)
        self.assertIn('FCP 2.00%', cfg['resumo_impostos']['icms'])

    def test_matriz_tem_reforma_flag(self):
        regra = self._regra_base(reforma_tributaria={'observacoes': 'prep'})
        cfg = serializar_configuracao_matriz(regra)
        self.assertTrue(cfg['tem_reforma'])

    def test_reforma_keys_contrato(self):
        self.assertIn('cst_ibs_cbs', REFORMA_TRIBUTARIA_KEYS)
