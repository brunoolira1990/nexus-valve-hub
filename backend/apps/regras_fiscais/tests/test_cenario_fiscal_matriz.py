"""Sprint 2 — matriz UF×CFOP, duplicar e copiar configurações."""

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
from apps.regras_fiscais.cenario_fiscal_entrada import (
    STATUS_CONFIGURADO,
    STATUS_INCOMPLETO,
    classificar_status_configuracao,
    copiar_configuracao_escopo,
    duplicar_regra_fiscal_entrada,
    montar_matriz_escopo,
    obter_ou_criar_cenario_padrao,
)
from apps.regras_fiscais.entrada_fiscal import (
    ContextoFiscalEntrada,
    avaliar_item_entrada_fiscal,
    carregar_regras_fiscais_entrada_ativas,
)
from apps.regras_fiscais.models import (
    CenarioFiscalEntradaEscopo,
    RegraFiscalEntrada,
)


def _cnpj() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


class MatrizEscopoTests(TestCase):
    def setUp(self):
        self.cenario = obter_ou_criar_cenario_padrao()
        self.escopo_a = CenarioFiscalEntradaEscopo.objects.create(
            cenario=self.cenario,
            tipo_escopo=CenarioFiscalEntradaEscopo.TipoEscopo.NCM,
            ncm='84818095',
        )
        self.escopo_b = CenarioFiscalEntradaEscopo.objects.create(
            cenario=self.cenario,
            tipo_escopo=CenarioFiscalEntradaEscopo.TipoEscopo.NCM,
            ncm='73071100',
        )
        self.regra_a = RegraFiscalEntrada.objects.create(
            nome='A',
            ativo=True,
            escopo=self.escopo_a,
            cenario=self.cenario,
            cfop_origem='5102',
            cfop_entrada='1102',
            uf_origem='SP',
            uf_destino='SP',
            cst_icms_esperado='20',
            aliquota_icms=Decimal('18'),
            severidade=RegraFiscalEntrada.Severidade.ALERTA,
        )

    def test_matriz_retorna_configuracoes_do_escopo(self):
        matriz = montar_matriz_escopo(self.escopo_a)
        self.assertEqual(matriz['escopo']['id'], self.escopo_a.id)
        self.assertEqual(len(matriz['configuracoes']), 1)
        cfg = matriz['configuracoes'][0]
        self.assertEqual(cfg['id'], self.regra_a.id)
        self.assertEqual(cfg['uf_origem'], 'SP')
        self.assertEqual(cfg['cfop_origem'], '5102')
        self.assertIn('icms', cfg['resumo_impostos'])

    def test_matriz_nao_retorna_outro_escopo(self):
        RegraFiscalEntrada.objects.create(
            nome='B',
            ativo=True,
            escopo=self.escopo_b,
            cenario=self.cenario,
            cfop_origem='6102',
            cfop_entrada='2102',
            uf_origem='MG',
            uf_destino='SP',
            cst_pis_esperado='50',
            aliquota_pis=Decimal('1.65'),
        )
        matriz = montar_matriz_escopo(self.escopo_a)
        ids = [c['id'] for c in matriz['configuracoes']]
        self.assertEqual(ids, [self.regra_a.id])

    def test_status_incompleto_sem_cfop_entrada(self):
        regra = RegraFiscalEntrada.objects.create(
            nome='Inc',
            ativo=True,
            escopo=self.escopo_a,
            cenario=self.cenario,
            cfop_origem='5102',
            uf_origem='RJ',
        )
        self.assertEqual(classificar_status_configuracao(regra), STATUS_INCOMPLETO)

    def test_status_configurado(self):
        self.assertEqual(classificar_status_configuracao(self.regra_a), STATUS_CONFIGURADO)


class DuplicarCopiarTests(TestCase):
    def setUp(self):
        self.cenario = obter_ou_criar_cenario_padrao()
        self.escopo = CenarioFiscalEntradaEscopo.objects.create(
            cenario=self.cenario,
            tipo_escopo=CenarioFiscalEntradaEscopo.TipoEscopo.NCM,
            ncm='84818099',
        )
        self.origem = RegraFiscalEntrada.objects.create(
            nome='Origem',
            ativo=True,
            escopo=self.escopo,
            cenario=self.cenario,
            cfop_origem='5102',
            cfop_entrada='1102',
            uf_origem='SP',
            uf_destino='SP',
            cst_icms_esperado='00',
            aliquota_icms=Decimal('18'),
            cst_ipi_esperado='49',
            aliquota_pis=Decimal('1.65'),
            aliquota_cofins=Decimal('7.6'),
            movimenta_estoque=False,
            exige_certificado_fornecedor=True,
            severidade=RegraFiscalEntrada.Severidade.BLOQUEIO,
        )

    def test_duplicar_mantém_impostos_e_efeitos(self):
        dup = duplicar_regra_fiscal_entrada(
            self.origem.id,
            {'uf_origem': 'MG', 'uf_destino': 'SP', 'cfop_origem': '6102', 'cfop_entrada': '2102'},
        )
        self.assertNotEqual(dup.id, self.origem.id)
        self.assertEqual(dup.uf_origem, 'MG')
        self.assertEqual(dup.cfop_origem, '6102')
        self.assertEqual(dup.cst_icms_esperado, '00')
        self.assertEqual(dup.aliquota_icms, Decimal('18'))
        self.assertEqual(dup.cst_ipi_esperado, '49')
        self.assertEqual(dup.aliquota_cofins, Decimal('7.6'))
        self.assertFalse(dup.movimenta_estoque)
        self.assertTrue(dup.exige_certificado_fornecedor)
        self.assertEqual(dup.severidade, RegraFiscalEntrada.Severidade.BLOQUEIO)
        self.assertEqual(dup.escopo_id, self.escopo.id)

    def test_duplicar_conflito_sem_sobrescrever(self):
        duplicar_regra_fiscal_entrada(
            self.origem.id,
            {'uf_origem': 'MG', 'uf_destino': 'SP', 'cfop_origem': '6102', 'cfop_entrada': '2102'},
        )
        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            duplicar_regra_fiscal_entrada(
                self.origem.id,
                {'uf_origem': 'MG', 'uf_destino': 'SP', 'cfop_origem': '6102', 'cfop_entrada': '2102'},
            )

    def test_copiar_varios_estados(self):
        resultado = copiar_configuracao_escopo(
            self.escopo,
            origem_regra_id=self.origem.id,
            destinos=[
                {'uf_origem': 'RJ', 'uf_destino': 'SP', 'cfop_origem': '6102', 'cfop_entrada': '2102'},
                {'uf_origem': 'PR', 'uf_destino': 'SP', 'cfop_origem': '6102', 'cfop_entrada': '2102'},
            ],
        )
        self.assertEqual(len(resultado['criados']), 2)
        self.assertEqual(len(resultado['ignorados']), 0)

    def test_copiar_sem_sobrescrever_ignora_conflito(self):
        copiar_configuracao_escopo(
            self.escopo,
            origem_regra_id=self.origem.id,
            destinos=[{'uf_origem': 'RJ', 'uf_destino': 'SP'}],
        )
        resultado = copiar_configuracao_escopo(
            self.escopo,
            origem_regra_id=self.origem.id,
            destinos=[{'uf_origem': 'RJ', 'uf_destino': 'SP'}],
        )
        self.assertEqual(len(resultado['criados']), 0)
        self.assertEqual(len(resultado['ignorados']), 1)

    def test_copiar_com_sobrescrever_atualiza(self):
        copiar_configuracao_escopo(
            self.escopo,
            origem_regra_id=self.origem.id,
            destinos=[{'uf_origem': 'RJ', 'uf_destino': 'SP'}],
        )
        existente = RegraFiscalEntrada.objects.get(escopo=self.escopo, uf_origem='RJ')
        existente.cst_icms_esperado = '99'
        existente.save(update_fields=['cst_icms_esperado'])
        resultado = copiar_configuracao_escopo(
            self.escopo,
            origem_regra_id=self.origem.id,
            destinos=[{'uf_origem': 'RJ', 'uf_destino': 'SP'}],
            sobrescrever=True,
        )
        self.assertEqual(len(resultado['atualizados']), 1)
        existente.refresh_from_db()
        self.assertEqual(existente.cst_icms_esperado, '00')


class MatrizMotorAPITests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user('mat_api', 'mat@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(user)
        self.cenario = obter_ou_criar_cenario_padrao()
        self.escopo = CenarioFiscalEntradaEscopo.objects.create(
            cenario=self.cenario,
            tipo_escopo=CenarioFiscalEntradaEscopo.TipoEscopo.NCM,
            ncm='84818099',
        )
        self.regra = RegraFiscalEntrada.objects.create(
            nome='Motor',
            ativo=True,
            escopo=self.escopo,
            cenario=self.cenario,
            cfop='6102',
            cfop_origem='6102',
            ncm='84818099',
            cst_icms_esperado='00',
            severidade=RegraFiscalEntrada.Severidade.INFORMATIVO,
        )
        self.forn = Fornecedor.objects.create(razao_social='F', cnpj=_cnpj(), uf='SP')
        nf = NFeEntradaHistoricaImportada.objects.create(
            chave_acesso=('35' + '3' * 42)[:44],
            numero='9020',
            serie='1',
            modelo='55',
            dh_emissao=timezone.make_aware(datetime(2026, 5, 2, 10, 0)),
            valor_total_nf=Decimal('10'),
            fornecedor_emitente=self.forn,
            emit_json={'UF': 'SP'},
            dest_json={'UF': 'RJ'},
        )
        item_nf = ItemNFeEntradaHistoricaImportada.objects.create(
            nf=nf,
            n_item=1,
            prod_json={'CFOP': '6102', 'NCM': '84818099'},
            imposto_json={},
        )
        self.conf = NFeEntradaConferencia.objects.create(nf_entrada_historica=nf)
        self.linha, _ = self.conf.itens.get_or_create(item_nfe_historico=item_nf)

    def test_get_matriz_api(self):
        url = reverse(
            'cenario-fiscal-entrada-matriz-escopo',
            kwargs={'pk': self.cenario.pk, 'escopo_id': self.escopo.pk},
        )
        r = self.client.get(url)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.json()['escopo']['ncm'], '84818099')
        self.assertTrue(any(c['id'] == self.regra.id for c in r.json()['configuracoes']))

    def test_copia_usada_pelo_motor(self):
        RegraFiscalEntrada.objects.filter(pk=self.regra.pk).update(
            uf_origem='MG',
            uf_destino='MG',
        )
        dup = duplicar_regra_fiscal_entrada(
            self.regra.id,
            {'uf_origem': 'SP', 'uf_destino': 'RJ', 'cfop_origem': '6102', 'cfop_entrada': '1102'},
        )
        ctx = ContextoFiscalEntrada(uf_origem='SP', uf_destino='RJ')
        r = avaliar_item_entrada_fiscal(self.linha, ctx, carregar_regras_fiscais_entrada_ativas())
        self.assertEqual(r['regra_id'], dup.id)

    def test_api_legada_continua(self):
        url = reverse('regrafiscal-entrada-list')
        r = self.client.get(url)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
