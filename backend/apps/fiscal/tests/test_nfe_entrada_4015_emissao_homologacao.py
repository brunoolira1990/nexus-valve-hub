"""ERP 4.0.15.0 — Entrada Própria 1 Parte 2A: fundação backend e numeração separada."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.cadastros.models import Cliente, Empresa, Fornecedor
from apps.fiscal.models import EstoqueCorrida, ItemNFeEntrada, NFeEntrada, NFeNumeracaoConfiguracao
from apps.fiscal.nfe_emissao.numeracao import NFeNumeracaoError, reservar_numeracao_nfe
from apps.fiscal.nfe_emissao.numeracao_defaults import ensure_numeracao_padrao_nfe
from apps.fiscal.nfe_entrada_emissao.numeracao import (
    MSG_SEM_CONFIG_ENTRADA,
    obter_config_numeracao_entrada,
    reservar_numeracao_nfe_entrada,
)
from apps.fiscal.nfe_entrada_emissao.validacao import (
    NFeEntradaEmissaoValidationError,
    validar_destinatario_entrada_propria_emitida,
    validar_itens_entrada_propria_emitida,
)
from apps.produtos.models import FamiliaProduto, Produto

User = get_user_model()


def _empresa() -> Empresa:
    return Empresa.objects.create(
        razao_social='Emitente Entrada 4015',
        cnpj='12345678000199',
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
        codigo_figura=f'E{suf}',
        descricao_base='Fam',
        tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
        categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
    )
    return Produto.objects.create(
        familia=fam,
        descricao='Prod Entrada 4015',
        modo_codigo=Produto.ModoCodigo.MANUAL,
        codigo_completo=f'EP4015-{suf}',
        unidade='PC',
        ncm='84818200',
    )


def _config_entrada(empresa: Empresa, *, proximo: int = 100) -> NFeNumeracaoConfiguracao:
    return NFeNumeracaoConfiguracao.objects.create(
        empresa=empresa,
        modelo_documento='55',
        ambiente=NFeNumeracaoConfiguracao.Ambiente.HOMOLOGACAO,
        tipo_operacao=NFeNumeracaoConfiguracao.TipoOperacao.ENTRADA_PROPRIA,
        serie='0',
        proximo_numero=proximo,
        ativo=True,
    )


def _rascunho_emitida(
    empresa: Empresa,
    *,
    cliente: Cliente | None = None,
    fornecedor: Fornecedor | None = None,
    com_item: bool = True,
) -> NFeEntrada:
    nf = NFeEntrada.objects.create(
        numero=f'RASCUNHO-EP-{uuid.uuid4().hex[:8]}',
        data=date.today(),
        tipo_origem=NFeEntrada.TipoOrigem.ENTRADA_PROPRIA_EMITIDA,
        status_operacional=NFeEntrada.StatusOperacional.RASCUNHO,
        ambiente_emissao=NFeEntrada.AmbienteEmissao.HOMOLOGACAO,
        empresa_emitente=empresa,
        cliente_destinatario=cliente,
        fornecedor=fornecedor,
        valor_total=Decimal('0'),
    )
    if com_item:
        prod = _produto()
        ItemNFeEntrada.objects.create(
            nf=nf,
            produto=prod,
            quantidade=Decimal('1'),
            valor=Decimal('100'),
            ncm='84818200',
            cfop='1102',
            unidade='PC',
        )
        nf.valor_total = Decimal('100')
        nf.save(update_fields=['valor_total'])
    return nf


class NFeEntrada4015EmissaoHomologacaoTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(username='ep4015', password='x')
        self.empresa = _empresa()
        self.cliente = Cliente.objects.create(
            razao_social='Cliente Dest 4015',
            cnpj='98765432000188',
            uf='SP',
            cidade='São Paulo',
            logradouro='Rua C',
            numero='3',
            bairro='Centro',
            cep='01001000',
        )
        self.fornecedor = Fornecedor.objects.create(
            razao_social='Fornecedor Dest 4015',
            cnpj='11111111000111',
        )

    def test_criar_rascunho_entrada_propria_emitida(self) -> None:
        nf = _rascunho_emitida(self.empresa, cliente=self.cliente)
        self.assertEqual(nf.tipo_origem, NFeEntrada.TipoOrigem.ENTRADA_PROPRIA_EMITIDA)
        self.assertEqual(nf.status_operacional, NFeEntrada.StatusOperacional.RASCUNHO)
        self.assertEqual(nf.ambiente_emissao, NFeEntrada.AmbienteEmissao.HOMOLOGACAO)
        self.assertFalse(nf.serie_nfe)
        self.assertFalse(nf.numero_nfe)
        self.assertEqual(EstoqueCorrida.objects.count(), 0)

    def test_reservar_numeracao_entrada_propria(self) -> None:
        cfg = _config_entrada(self.empresa, proximo=501)
        nf = _rascunho_emitida(self.empresa, fornecedor=self.fornecedor)
        num = reservar_numeracao_nfe_entrada(nf, usuario=self.user)
        nf.refresh_from_db()
        cfg.refresh_from_db()
        self.assertEqual(num.nnf, '000000501')
        self.assertEqual(nf.serie_nfe, '0')
        self.assertEqual(nf.numero_nfe, '000000501')
        self.assertTrue(nf.chave_acesso)
        self.assertEqual(nf.status_emissao_sefaz, NFeEntrada.StatusEmissaoSefaz.NUMERACAO_RESERVADA)
        self.assertEqual(cfg.proximo_numero, 502)
        self.assertEqual(cfg.ultimo_numero_reservado, 501)

    def test_reserva_entrada_nao_altera_contador_saida(self) -> None:
        ensure_numeracao_padrao_nfe(self.empresa)
        cfg_saida = NFeNumeracaoConfiguracao.objects.get(
            empresa=self.empresa,
            ambiente='homologacao',
            tipo_operacao=NFeNumeracaoConfiguracao.TipoOperacao.SAIDA,
            serie='0',
        )
        proximo_saida_antes = cfg_saida.proximo_numero
        _config_entrada(self.empresa, proximo=10)
        nf = _rascunho_emitida(self.empresa, cliente=self.cliente)
        reservar_numeracao_nfe_entrada(nf, usuario=self.user)
        cfg_saida.refresh_from_db()
        self.assertEqual(cfg_saida.proximo_numero, proximo_saida_antes)

    def test_falha_reserva_sem_config_entrada(self) -> None:
        nf = _rascunho_emitida(self.empresa, cliente=self.cliente)
        with self.assertRaises(NFeNumeracaoError) as ctx:
            reservar_numeracao_nfe_entrada(nf, usuario=self.user)
        self.assertIn(MSG_SEM_CONFIG_ENTRADA, str(ctx.exception))

    def test_falha_reserva_ambiente_producao(self) -> None:
        _config_entrada(self.empresa)
        nf = _rascunho_emitida(self.empresa, cliente=self.cliente)
        nf.ambiente_emissao = NFeEntrada.AmbienteEmissao.PRODUCAO
        nf.save(update_fields=['ambiente_emissao'])
        with self.assertRaises(NFeNumeracaoError) as ctx:
            reservar_numeracao_nfe_entrada(nf, usuario=self.user)
        self.assertIn('produção', str(ctx.exception).lower())

    def test_validar_destinatario_cliente_ou_fornecedor(self) -> None:
        nf = _rascunho_emitida(self.empresa, cliente=self.cliente, com_item=False)
        validar_destinatario_entrada_propria_emitida(nf)

        nf2 = NFeEntrada.objects.create(
            numero='X',
            data=date.today(),
            tipo_origem=NFeEntrada.TipoOrigem.ENTRADA_PROPRIA_EMITIDA,
            empresa_emitente=self.empresa,
            valor_total=Decimal('0'),
        )
        with self.assertRaises(NFeEntradaEmissaoValidationError):
            validar_destinatario_entrada_propria_emitida(nf2)

        nf3 = _rascunho_emitida(self.empresa, cliente=self.cliente, com_item=False)
        nf3.fornecedor = self.fornecedor
        with self.assertRaises(NFeEntradaEmissaoValidationError):
            validar_destinatario_entrada_propria_emitida(nf3)

    def test_validar_item_ncm_cfop_unidade(self) -> None:
        nf = _rascunho_emitida(self.empresa, cliente=self.cliente)
        validar_itens_entrada_propria_emitida(nf)

        item = nf.itens.first()
        item.cfop = ''
        item.save(update_fields=['cfop'])
        with self.assertRaises(NFeEntradaEmissaoValidationError) as ctx:
            validar_itens_entrada_propria_emitida(nf)
        self.assertIn('CFOP', str(ctx.exception))

    def test_obter_config_entrada_usa_tipo_operacao_entrada_propria(self) -> None:
        ensure_numeracao_padrao_nfe(self.empresa)
        cfg_entrada = _config_entrada(self.empresa, proximo=77)
        obtida = obter_config_numeracao_entrada(self.empresa.pk)
        self.assertEqual(obtida.pk, cfg_entrada.pk)
        self.assertEqual(obtida.tipo_operacao, NFeNumeracaoConfiguracao.TipoOperacao.ENTRADA_PROPRIA)

    def test_tipo_origem_manual_e_importada_preservados(self) -> None:
        nf_manual = NFeEntrada.objects.create(
            numero='M1',
            data=date.today(),
            fornecedor=self.fornecedor,
            valor_total=Decimal('0'),
            tipo_origem=NFeEntrada.TipoOrigem.MANUAL,
        )
        self.assertEqual(nf_manual.tipo_origem, NFeEntrada.TipoOrigem.MANUAL)

        nf_imp = NFeEntrada.objects.create(
            numero='I1',
            data=date.today(),
            chave_acesso='35260612345678000199550010000000991000000099',
            tipo_origem=NFeEntrada.TipoOrigem.ENTRADA_PROPRIA_IMPORTADA,
            status_operacional=NFeEntrada.StatusOperacional.IMPORTADA_PENDENTE_CONFERENCIA,
            valor_total=Decimal('0'),
        )
        self.assertEqual(
            nf_imp.status_operacional,
            NFeEntrada.StatusOperacional.IMPORTADA_PENDENTE_CONFERENCIA,
        )

    def test_numeracao_config_tipo_operacao_default_saida(self) -> None:
        ensure_numeracao_padrao_nfe(self.empresa)
        cfg = NFeNumeracaoConfiguracao.objects.filter(empresa=self.empresa).first()
        self.assertEqual(cfg.tipo_operacao, NFeNumeracaoConfiguracao.TipoOperacao.SAIDA)

    def test_smoke_saida_numeracao_inalterada(self) -> None:
        """Regressão: reserva de saída continua usando tipo_operacao=saida."""
        from apps.cadastros.models import Cliente as Cli
        from apps.fiscal.models import NFeSaida

        ensure_numeracao_padrao_nfe(self.empresa)
        cli = Cli.objects.create(
            razao_social='Cli Smoke',
            cnpj='22222222000122',
            uf='SP',
            cidade='São Paulo',
            logradouro='R',
            numero='1',
            bairro='C',
            cep='01001000',
        )
        nf_saida = NFeSaida.objects.create(
            numero='SMK-4015',
            cliente=cli,
            data=date.today(),
            empresa_emitente=self.empresa,
            valor_total=Decimal('1'),
        )
        cfg_antes = NFeNumeracaoConfiguracao.objects.get(
            empresa=self.empresa,
            ambiente='homologacao',
            tipo_operacao=NFeNumeracaoConfiguracao.TipoOperacao.SAIDA,
            serie='0',
        )
        prox_antes = cfg_antes.proximo_numero
        reservar_numeracao_nfe(nf_saida, ambiente='homologacao', usuario=self.user)
        cfg_antes.refresh_from_db()
        self.assertEqual(cfg_antes.proximo_numero, prox_antes + 1)
