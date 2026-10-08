"""NF-e 4.0.2 — série homologação 0–889, correção cStat 266."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Empresa
from apps.comercial.models import PedidoVenda
from apps.comercial.faturamento_pedido_venda import confirmar_faturamento_pedido, criar_faturamento_pedido
from apps.fiscal.nfe_saida_from_faturamento import gerar_nfe_saida_from_faturamento
from apps.fiscal.models import NFeNumeracaoConfiguracao, NFeSaida, NFeSaidaEvento
from apps.fiscal.nfe_emissao.corrigir_serie_homologacao import (
    corrigir_serie_homologacao_nfe,
    pode_corrigir_serie_homologacao,
)
from apps.fiscal.nfe_emissao.numeracao import NFeNumeracaoError, obter_config_numeracao, reservar_numeracao_nfe
from apps.fiscal.nfe_emissao.numeracao_defaults import ensure_numeracao_padrao_nfe
from apps.fiscal.nfe_emissao.serie_fiscal import (
    MSG_SERIE_FORA_FAIXA,
    NFeSerieFiscalError,
    serie_para_chave,
    validar_chave_corresponde_numeracao,
    validar_serie_autorizacao_normal,
)
from apps.fiscal.nfe_saida_conferencia import montar_conferencia_nfe_saida
from apps.fiscal.nfe_saida_prontidao import marcar_nfe_pronta_para_emissao, validar_conferencia_nfe
from apps.fiscal.serializers import NFeNumeracaoConfiguracaoSerializer
from apps.produtos.models import FamiliaProduto, Produto


def _cnpj() -> str:
    h = abs(hash(uuid.uuid4())) % 10_000_000_000_000
    return f'{h:014d}'[:14]


def _empresa() -> Empresa:
    return Empresa.objects.create(
        razao_social='Emitente Série',
        cnpj='03999102000150',
        uf='SP',
        cidade='São Paulo',
        logradouro='Rua A',
        numero='1',
        bairro='Centro',
        cep='01001000',
        ie='123456789012',
    )


def _produto() -> Produto:
    suf = uuid.uuid4().hex[:6].upper()
    fam = FamiliaProduto.objects.create(
        codigo_figura=f'S{suf}',
        descricao_base='Fam',
        tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
        categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
    )
    return Produto.objects.create(
        familia=fam,
        descricao='Prod',
        modo_codigo=Produto.ModoCodigo.MANUAL,
        codigo_completo=f'P-{suf}',
        unidade='PC',
        ncm='84818200',
    )


class NFe402SerieHomologacaoTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('serie402', 'serie402@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.empresa = _empresa()
        ensure_numeracao_padrao_nfe(self.empresa)
        self.hom = NFeNumeracaoConfiguracao.objects.get(
            empresa=self.empresa,
            ambiente='homologacao',
            serie='0',
        )
        self.prod_cfg = NFeNumeracaoConfiguracao.objects.get(
            empresa=self.empresa,
            ambiente='producao',
            serie='1',
        )

    def test_config_homolog_serie_0(self):
        self.assertEqual(self.hom.serie, '0')
        self.assertEqual(self.hom.modelo_documento, '55')

    def test_config_producao_serie_1(self):
        self.assertEqual(self.prod_cfg.serie, '1')
        self.assertEqual(self.prod_cfg.proximo_numero, 1)

    def test_bloqueia_serie_900_config(self):
        ser = NFeNumeracaoConfiguracaoSerializer(
            instance=self.hom,
            data={'serie': '900', 'proximo_numero': 2},
            partial=True,
        )
        self.assertFalse(ser.is_valid())
        self.assertIn(MSG_SERIE_FORA_FAIXA, str(ser.errors.get('serie', '')))

    def test_aceita_serie_0_e_889(self):
        validar_serie_autorizacao_normal('0')
        validar_serie_autorizacao_normal('889')

    def test_chave_muda_serie_900_para_0(self):
        from apps.fiscal.nfe_integracao.nfe_chave_acesso import montar_chave_acesso_nfe

        base = dict(
            cuf='35',
            aamm='2605',
            cnpj_emitente='03999102000150',
            modelo='55',
            nnf='000000002',
            tp_emis='1',
            codigo_numerico='12345678',
        )
        ch900 = montar_chave_acesso_nfe(serie='900', **base).chave_44
        ch0 = montar_chave_acesso_nfe(serie=serie_para_chave('0'), **base).chave_44
        self.assertNotEqual(ch900, ch0)
        self.assertEqual(ch900[22:25], '900')
        self.assertEqual(ch0[22:25], '000')

    def _nf_rejeitada_266(self) -> NFeSaida:
        cli = Cliente.objects.create(
            razao_social='Cli',
            cnpj=_cnpj(),
            uf='RJ',
            cidade='Rio',
            logradouro='Rua B',
            numero='2',
            bairro='Centro',
            cep='20040002',
        )
        pedido = PedidoVenda.objects.create(
            numero=f'PV-S-{uuid.uuid4().hex[:4]}',
            empresa_emitente=self.empresa,
            cliente=cli,
            data=date(2026, 5, 23),
            status='ABERTO',
            valor_total=Decimal('100'),
        )
        from apps.comercial.models import ItemPedidoVenda

        item = ItemPedidoVenda.objects.create(
            pedido=pedido,
            produto=_produto(),
            quantidade=Decimal('1'),
            quantidade_negociada=Decimal('1'),
            valor_unitario=Decimal('100'),
            preco_por_unidade_negociada=Decimal('100'),
            snapshot_fiscal={
                'origem_regra_fiscal_saida': 'LEGADO',
                'ncm': '84818200',
                'cfop': '5102',
                'icms': {'cst_icms': '00', 'base': '100', 'aliquota': '18', 'valor': '18'},
                'pis': {'cst': '08'},
                'cofins': {'cst': '08'},
            },
        )
        from apps.comercial.models import FaturamentoPedidoVenda

        criado = criar_faturamento_pedido(pedido, {'itens': [{'item_pedido_id': item.pk, 'quantidade': '1'}]})
        confirmar_faturamento_pedido(pedido, criado['faturamento_id'])
        fat = FaturamentoPedidoVenda.objects.get(pk=criado['faturamento_id'])
        r = gerar_nfe_saida_from_faturamento(pedido, fat.pk)
        nf = NFeSaida.objects.get(pk=r['nfe_saida_id'])
        validar_conferencia_nfe(nf, usuario=self.user)
        marcar_nfe_pronta_para_emissao(nf, usuario=self.user)
        reservar_numeracao_nfe(nf, usuario=self.user)
        nf.refresh_from_db()
        nf.serie_nfe = '900'
        nf.chave_acesso = '35260503999102000150559000000000212323217760'
        nf.status_emissao_sefaz = NFeSaida.StatusEmissaoSefaz.REJEITADA_HOMOLOGACAO
        nf.cstat_autorizacao = '266'
        nf.motivo_autorizacao = 'Rejeição: Série utilizada fora da faixa permitida'
        nf.xml_assinado = '<NFe><serie>900</serie></NFe>'
        nf.xml_envio_lote = '<enviNFe/>'
        nf.save()
        return nf

    def test_pode_corrigir_cstat_266(self):
        nf = self._nf_rejeitada_266()
        ok, _ = pode_corrigir_serie_homologacao(nf)
        self.assertTrue(ok)

    def test_corrigir_recalcula_chave_e_invalida_xml(self):
        nf = self._nf_rejeitada_266()
        chave_ant = nf.chave_acesso
        res = corrigir_serie_homologacao_nfe(nf, usuario=self.user)
        nf.refresh_from_db()
        self.assertEqual(res['serie_anterior'], '900')
        self.assertEqual(res['serie_nova'], '0')
        self.assertNotEqual(res['chave_nova'], chave_ant)
        self.assertEqual(nf.serie_nfe, '0')
        self.assertFalse((nf.xml_assinado or '').strip())
        self.assertFalse((nf.xml_envio_lote or '').strip())
        self.assertFalse(nf.cstat_autorizacao)
        ev = NFeSaidaEvento.objects.filter(
            nfe_saida=nf,
            tipo_evento='SERIE_HOMOLOGACAO_CORRIGIDA',
        ).first()
        self.assertIsNotNone(ev)

    def test_autorizada_nao_corrigir(self):
        nf = self._nf_rejeitada_266()
        nf.status_emissao_sefaz = NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO
        nf.protocolo_autorizacao = '135'
        nf.save()
        ok, msg = pode_corrigir_serie_homologacao(nf)
        self.assertFalse(ok)
        self.assertIn('autorizada', msg.lower())

    def test_api_corrigir_serie(self):
        nf = self._nf_rejeitada_266()
        res = self.client.post(f'/api/nf-saidas/{nf.pk}/corrigir-serie-homologacao/')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data.get('ok'))
        self.assertEqual(res.data.get('serie_nova'), '0')

    def test_conferencia_cstat_serie_invalida(self):
        nf = self._nf_rejeitada_266()
        payload = montar_conferencia_nfe_saida(nf)
        em = payload.get('emissao_sefaz') or {}
        self.assertTrue(em.get('cstat_serie_invalida'))
        self.assertTrue(em.get('pode_corrigir_serie_homologacao'))

    def test_reserva_idempotente_nao_incrementa_producao(self):
        nf = self._nf_rejeitada_266()
        prod_antes = self.prod_cfg.proximo_numero
        corrigir_serie_homologacao_nfe(nf, usuario=self.user)
        nf.refresh_from_db()
        reservar_numeracao_nfe(nf, usuario=self.user)
        self.prod_cfg.refresh_from_db()
        self.assertEqual(self.prod_cfg.proximo_numero, prod_antes)

    def test_obter_config_rejeita_serie_900(self):
        NFeNumeracaoConfiguracao.objects.filter(
            empresa=self.empresa,
            ambiente='homologacao',
        ).update(ativo=False)
        cfg_antiga = NFeNumeracaoConfiguracao.objects.create(
            empresa=self.empresa,
            modelo_documento='55',
            ambiente='homologacao',
            serie='900',
            proximo_numero=99,
            ativo=True,
        )
        with self.assertRaises(NFeNumeracaoError):
            obter_config_numeracao(self.empresa.pk, ambiente='homologacao')
        cfg_antiga.delete()
        NFeNumeracaoConfiguracao.objects.filter(
            empresa=self.empresa,
            ambiente='homologacao',
            serie='0',
        ).update(ativo=True)

    def test_validar_chave_consistente(self):
        nf = self._nf_rejeitada_266()
        corrigir_serie_homologacao_nfe(nf, usuario=self.user)
        nf.refresh_from_db()
        validar_chave_corresponde_numeracao(
            nf.chave_acesso,
            serie=nf.serie_nfe,
            nnf=nf.numero_nfe,
            codigo_numerico=nf.codigo_numerico,
        )
        with self.assertRaises(NFeSerieFiscalError):
            validar_chave_corresponde_numeracao(
                nf.chave_acesso,
                serie='900',
                nnf=nf.numero_nfe,
            )
