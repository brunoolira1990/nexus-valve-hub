"""ERP 4.0.15.2.19 — NF-e Entrada: duplicatas XML, baixa pedido de compra e idempotência."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.cadastros.models import Fornecedor
from apps.comercial.models import ItemPedidoCompra, PedidoCompra
from apps.fiscal.aplicacao_estoque_conferencia import aplicar_estoque_fisico_conferencia
from apps.fiscal.models import (
    ItemNFeEntradaConferencia,
    ItemNFeEntradaHistoricaImportada,
    NFeEntradaConferencia,
    NFeEntradaHistoricaImportada,
)
from apps.fiscal.nfe_entrada_duplicatas import (
    ORIGEM_PARCELAS_XML,
    extrair_duplicatas_xml_nf_entrada,
    montar_parcelas_sugeridas_nf_entrada,
)
from apps.fiscal.nfe_entrada_financeiro import preview_contas_pagar_de_nfe_entrada
from apps.corridas.models import Corrida
from apps.fiscal.pedido_compra_baixa import MSG_JA_BAIXADO, aplicar_baixa_pedido_compra_conferencia
from apps.fiscal.nfe_entrada_data_entrada import (
    MSG_DATA_ENTRADA_OBRIGATORIA,
    data_competencia_entrada_nf,
)
from apps.fiscal.conferencia_pedido import validar_preparar_estoque_conferencia
from apps.produtos.models import FamiliaProduto, Produto
from apps.regras_fiscais.models import RegraFiscalEntrada


def _cnpj() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


XML_COM_DUP = """<?xml version="1.0" encoding="UTF-8"?>
<nfeProc versao="4.00">
  <NFe>
    <infNFe Id="NFe35260600000000000000550010000000011000000001">
      <ide><dhEmi>2026-06-01T10:00:00-03:00</dhEmi></ide>
      <emit><CNPJ>00000000000191</CNPJ></emit>
      <cobr>
        <fat><nFat>001</nFat><vOrig>300.00</vOrig><vLiq>300.00</vLiq></fat>
        <dup><nDup>001</nDup><dVenc>2026-04-01</dVenc><vDup>100.00</vDup></dup>
        <dup><nDup>002</nDup><dVenc>2026-05-01</dVenc><vDup>100.00</vDup></dup>
        <dup><nDup>003</nDup><dVenc>2026-06-01</dVenc><vDup>100.00</vDup></dup>
      </cobr>
    </infNFe>
  </NFe>
</nfeProc>"""


def _setup_pedido_conferencia(suffix: str, *, qty='10.000', vincular=True, data_entrada=None):
    forn = Fornecedor.objects.create(razao_social=f'Forn {suffix}', cnpj=_cnpj(), uf='SP')
    fam = FamiliaProduto.objects.create(
        codigo_figura=f'F{suffix}'[:16],
        descricao_base='Fam',
        tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
        categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
    )
    prod = Produto.objects.create(
        familia=fam,
        descricao='Produto teste',
        modo_codigo=Produto.ModoCodigo.MANUAL,
        codigo_completo=f'C{suffix}',
        unidade='PC',
        ncm='84818099',
    )
    pedido = PedidoCompra.objects.create(
        numero=f'PC-{suffix}',
        fornecedor=forn,
        data=date(2026, 1, 15),
        valor_total=Decimal('300.00'),
        status='Aprovado',
    )
    item_pc = ItemPedidoCompra.objects.create(
        pedido=pedido,
        produto=prod,
        quantidade=Decimal('20'),
        quantidade_negociada=Decimal('20'),
        valor_unitario=Decimal('15'),
        valor_total_item=Decimal('300'),
    )
    nf = NFeEntradaHistoricaImportada.objects.create(
        chave_acesso=('35' + suffix + 'Z' * 40)[:44],
        numero=f'NE{suffix}'[:8],
        serie='1',
        modelo='55',
        dh_emissao=timezone.make_aware(datetime(2026, 6, 1, 10, 0)),
        valor_total_nf=Decimal('300.00'),
        fornecedor_emitente=forn,
        reforma_e_outros_json={},
    )
    item_nf = ItemNFeEntradaHistoricaImportada.objects.create(
        nf=nf,
        n_item=1,
        prod_json={'CFOP': '5102', 'NCM': '84818099', 'qCom': qty, 'uCom': 'PC'},
        imposto_json={},
    )
    conf = NFeEntradaConferencia.objects.create(
        nf_entrada_historica=nf,
        pedido_compra=pedido,
        status=NFeEntradaConferencia.Status.PREPARADA,
        preparado_em=timezone.now(),
        data_entrada=data_entrada or date(2026, 6, 5),
    )
    linha, _ = conf.itens.get_or_create(item_nfe_historico=item_nf)
    linha.produto = prod
    linha.quantidade_nf = Decimal(qty)
    linha.unidade_nf = 'PC'
    linha.quantidade_estoque_calculada = Decimal(qty)
    linha.corrida = f'C-{suffix}'
    linha.lote = 'L1'
    linha.status = ItemNFeEntradaConferencia.Status.CONFERIDO
    if vincular:
        linha.item_pedido_compra = item_pc
    linha.save()

    RegraFiscalEntrada.objects.create(
        nome=f'R-{suffix}',
        ativo=True,
        prioridade=1,
        cfop='5102',
        movimenta_estoque=True,
        severidade=RegraFiscalEntrada.Severidade.INFORMATIVO,
    )
    return {'nf': nf, 'conf': conf, 'linha': linha, 'pedido': pedido, 'item_pc': item_pc, 'forn': forn}


class NFeEntradaDuplicatasXmlConteudoTests(TestCase):
    def test_extrai_duplicatas_de_xml_conteudo_sem_reforma(self):
        ctx = _setup_pedido_conferencia('dupxml', vincular=False)
        nf = ctx['nf']
        nf.xml_conteudo = XML_COM_DUP
        nf.save(update_fields=['xml_conteudo'])

        dups = extrair_duplicatas_xml_nf_entrada(nf)
        self.assertEqual(len(dups), 3)
        self.assertEqual(dups[0]['vencimento'], '2026-04-01')
        self.assertEqual(str(dups[0]['valor']), '100.00')

        parcelas, origem, aviso = montar_parcelas_sugeridas_nf_entrada(nf, ctx['conf'])
        self.assertEqual(origem, ORIGEM_PARCELAS_XML)
        self.assertEqual(len(parcelas), 3)
        self.assertEqual(parcelas[1]['vencimento'], '2026-05-01')
        self.assertFalse(aviso)

        nf.refresh_from_db()
        self.assertIn('cobr', nf.reforma_e_outros_json)


class NFeEntradaPedidoBaixaTests(TestCase):
    def test_baixa_parcial_atualiza_quantidade_recebida_e_status(self):
        ctx = _setup_pedido_conferencia('baixap')
        res = aplicar_baixa_pedido_compra_conferencia(ctx['conf'])
        self.assertTrue(res['aplicado'])
        ctx['item_pc'].refresh_from_db()
        ctx['pedido'].refresh_from_db()
        self.assertEqual(ctx['item_pc'].quantidade_recebida, Decimal('10'))
        self.assertEqual(ctx['pedido'].status, 'Parcialmente recebido')

    def test_baixa_idempotente(self):
        ctx = _setup_pedido_conferencia('baixaidem')
        aplicar_baixa_pedido_compra_conferencia(ctx['conf'])
        res2 = aplicar_baixa_pedido_compra_conferencia(ctx['conf'])
        self.assertFalse(res2['aplicado'])
        self.assertTrue(res2['ja_baixado'])
        self.assertIn(MSG_JA_BAIXADO, res2['mensagem'])
        ctx['item_pc'].refresh_from_db()
        self.assertEqual(ctx['item_pc'].quantidade_recebida, Decimal('10'))

    def test_aplicar_estoque_baixa_pedido_vinculado(self):
        ctx = _setup_pedido_conferencia('estbaixa')
        res = aplicar_estoque_fisico_conferencia(ctx['conf'], confirmar_alertas=True)
        self.assertTrue(res['aplicado'])
        self.assertTrue(res['pedido_compra_baixa']['aplicado'])
        ctx['item_pc'].refresh_from_db()
        self.assertEqual(ctx['item_pc'].quantidade_recebida, Decimal('10'))

    def test_gerar_cp_nao_baixa_pedido(self):
        ctx = _setup_pedido_conferencia('cpnobx')
        User = get_user_model()
        user = User.objects.create_user(username='fin', password='x')
        client = APIClient()
        client.force_authenticate(user=user)
        preview = preview_contas_pagar_de_nfe_entrada(ctx['nf'])
        status_antes = ctx['pedido'].status
        client.post(
            f'/api/nf-entradas-historicas-importadas/{ctx["nf"].pk}/financeiro/gerar-contas-pagar/',
            {'parcelas': preview['parcelas'], 'confirmar_pendencias_operacionais': True},
            format='json',
        )
        ctx['pedido'].refresh_from_db()
        ctx['item_pc'].refresh_from_db()
        self.assertEqual(ctx['pedido'].status, status_antes)
        self.assertEqual(ctx['item_pc'].quantidade_recebida, Decimal('0'))
        self.assertEqual(preview['parcelas'][1]['vencimento'], '2026-05-01')

    def test_preparar_exige_data_entrada(self):
        ctx = _setup_pedido_conferencia('semdata')
        ctx['conf'].data_entrada = None
        ctx['conf'].save(update_fields=['data_entrada'])
        itens = list(ctx['conf'].itens.all())
        pendencias, _ = validar_preparar_estoque_conferencia(ctx['conf'], itens)
        self.assertTrue(any(MSG_DATA_ENTRADA_OBRIGATORIA in p for p in pendencias))

    def test_competencia_entrada_virada_mes(self):
        ctx = _setup_pedido_conferencia(
            'virada',
            data_entrada=date(2026, 7, 5),
        )
        ctx['nf'].dh_emissao = timezone.make_aware(datetime(2026, 6, 30, 18, 0))
        ctx['nf'].save(update_fields=['dh_emissao'])
        self.assertEqual(data_competencia_entrada_nf(ctx['nf']), date(2026, 7, 5))
        self.assertNotEqual(ctx['nf'].dh_emissao.date(), date(2026, 7, 5))

    def test_aplicar_estoque_usa_data_entrada_corrida(self):
        ctx = _setup_pedido_conferencia('datacorr', data_entrada=date(2026, 7, 5))
        ctx['nf'].dh_emissao = timezone.make_aware(datetime(2026, 6, 30, 18, 0))
        ctx['nf'].save(update_fields=['dh_emissao'])
        res = aplicar_estoque_fisico_conferencia(ctx['conf'], confirmar_alertas=True)
        self.assertTrue(res['aplicado'])
        corrida = Corrida.objects.get(numero=ctx['linha'].corrida)
        self.assertEqual(corrida.data_recebimento, date(2026, 7, 5))
