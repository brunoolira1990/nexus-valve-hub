"""NF-e Saída 1 — rascunho a partir de FaturamentoPedidoVenda."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Empresa
from apps.comercial.faturamento_pedido_venda import confirmar_faturamento_pedido, criar_faturamento_pedido
from apps.comercial.models import FaturamentoPedidoVenda, ItemPedidoVenda, PedidoVenda
from apps.fiscal.models import AtendimentoEstoque, ItemNFeSaida, NFeSaida
from apps.fiscal.nfe_saida_from_faturamento import STATUS_NFE_RASCUNHO, gerar_nfe_saida_from_faturamento
from apps.fiscal.serializers import NFeSaidaSerializer
from apps.produtos.models import FamiliaProduto, Produto


def _cnpj() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


def _produto() -> Produto:
    suf = uuid.uuid4().hex[:6].upper()
    fam = FamiliaProduto.objects.create(
        codigo_figura=f'N{suf}',
        descricao_base='Fam',
        tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
        categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
    )
    return Produto.objects.create(
        familia=fam,
        descricao='Prod NF',
        modo_codigo=Produto.ModoCodigo.MANUAL,
        codigo_completo=f'NF-{suf}',
        unidade='PC',
        ncm='84818200',
    )


def _pedido_item(*, qtd=Decimal('10'), preco=Decimal('100')) -> tuple[PedidoVenda, ItemPedidoVenda]:
    emp = Empresa.objects.create(razao_social='Emit', cnpj=_cnpj(), uf='SP')
    cli = Cliente.objects.create(
        razao_social='Cli',
        cnpj=_cnpj(),
        uf='RJ',
        cidade='Rio de Janeiro',
        cep='20040-020',
        logradouro='Rua da Assembleia',
        numero='100',
        bairro='Centro',
    )
    pedido = PedidoVenda.objects.create(
        numero=f'PV-{uuid.uuid4().hex[:6]}',
        empresa_emitente=emp,
        cliente=cli,
        data=date.today(),
        status='ABERTO',
        valor_total=Decimal('1000'),
    )
    prod = _produto()
    item = ItemPedidoVenda.objects.create(
        pedido=pedido,
        produto=prod,
        quantidade=qtd,
        quantidade_negociada=qtd,
        valor_unitario=preco,
        preco_por_unidade_negociada=preco,
        snapshot_fiscal={'origem_regra_fiscal_saida': 'LEGADO', 'ncm': '84818200', 'cfop': '5102'},
    )
    return pedido, item


def _faturamento_pronto(pedido: PedidoVenda, item: ItemPedidoVenda, qtd: str = '4') -> FaturamentoPedidoVenda:
    criado = criar_faturamento_pedido(pedido, {'itens': [{'item_pedido_id': item.pk, 'quantidade': qtd}]})
    confirmar_faturamento_pedido(pedido, criado['faturamento_id'])
    return FaturamentoPedidoVenda.objects.get(pk=criado['faturamento_id'])


class NFeSaidaFaturamentoTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('nfe_fat', 'nfe_fat@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_gerar_nfe_rascunho(self):
        pedido, item = _pedido_item()
        fat = _faturamento_pronto(pedido, item)
        self.assertEqual(fat.status, FaturamentoPedidoVenda.Status.PRONTO_PARA_NFE)

        r = gerar_nfe_saida_from_faturamento(pedido, fat.pk, observacao='Teste')
        self.assertFalse(r['ja_existia'])
        self.assertEqual(r['itens_criados'], 1)
        nf = NFeSaida.objects.get(pk=r['nfe_saida_id'])
        self.assertEqual(nf.status, STATUS_NFE_RASCUNHO)
        self.assertEqual(nf.pedido_venda_id, pedido.pk)
        self.assertEqual(nf.faturamento_pedido_venda_id, fat.pk)

        nf_item = ItemNFeSaida.objects.get(nf=nf)
        self.assertEqual(nf_item.quantidade, Decimal('4'))
        self.assertEqual(nf_item.valor, Decimal('100'))
        self.assertEqual(nf_item.snapshot_fiscal['origem_regra_fiscal_saida'], 'LEGADO')
        self.assertEqual(nf_item.item_faturamento_pedido_id, fat.itens.get().pk)

        fat.refresh_from_db()
        self.assertEqual(fat.status, FaturamentoPedidoVenda.Status.GERADO_NFE)
        self.assertEqual(fat.nfe_saida_id, nf.pk)

    def test_idempotencia(self):
        pedido, item = _pedido_item()
        fat = _faturamento_pronto(pedido, item)
        r1 = gerar_nfe_saida_from_faturamento(pedido, fat.pk)
        r2 = gerar_nfe_saida_from_faturamento(pedido, fat.pk)
        self.assertEqual(r1['nfe_saida_id'], r2['nfe_saida_id'])
        self.assertTrue(r2['ja_existia'])
        self.assertEqual(NFeSaida.objects.filter(faturamento_pedido_venda_id=fat.pk).count(), 1)

    def test_rascunho_nao_gera(self):
        pedido, item = _pedido_item()
        criado = criar_faturamento_pedido(pedido, {'itens': [{'item_pedido_id': item.pk, 'quantidade': '2'}]})
        with self.assertRaises(ValueError) as ctx:
            gerar_nfe_saida_from_faturamento(pedido, criado['faturamento_id'])
        self.assertIn('confirme', str(ctx.exception).lower())

    def test_cancelado_nao_gera(self):
        pedido, item = _pedido_item()
        fat = _faturamento_pronto(pedido, item)
        fat.status = FaturamentoPedidoVenda.Status.CANCELADO
        fat.save(update_fields=['status'])
        with self.assertRaises(ValueError):
            gerar_nfe_saida_from_faturamento(pedido, fat.pk)

    def test_pedido_cancelado_nao_gera(self):
        pedido, item = _pedido_item()
        fat = _faturamento_pronto(pedido, item)
        pedido.status = 'CANCELADO'
        pedido.save(update_fields=['status'])
        with self.assertRaises(ValueError):
            gerar_nfe_saida_from_faturamento(pedido, fat.pk)

    def test_valores_batem(self):
        pedido, item = _pedido_item(qtd=Decimal('5'), preco=Decimal('50'))
        fat = _faturamento_pronto(pedido, item, qtd='5')
        r = gerar_nfe_saida_from_faturamento(pedido, fat.pk)
        nf = NFeSaida.objects.get(pk=r['nfe_saida_id'])
        self.assertEqual(nf.valor_total, Decimal('250.00'))

    def test_sem_estoque_atendimento_financeiro(self):
        pedido, item = _pedido_item()
        fat = _faturamento_pronto(pedido, item)
        nfe_antes = NFeSaida.objects.count()
        atend_antes = AtendimentoEstoque.objects.count()
        gerar_nfe_saida_from_faturamento(pedido, fat.pk)
        nf = NFeSaida.objects.latest('pk')
        self.assertEqual(NFeSaida.objects.count(), nfe_antes + 1)
        self.assertEqual(AtendimentoEstoque.objects.count(), atend_antes)
        self.assertEqual(nf.titulos_receber, [])

    def test_api_gerar_nfe(self):
        pedido, item = _pedido_item()
        fat = _faturamento_pronto(pedido, item)
        url = f'/api/pedidos-venda/{pedido.pk}/faturamentos/{fat.pk}/gerar-nfe-saida/'
        r1 = self.client.post(url, {'observacao': 'API'}, format='json')
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)
        r2 = self.client.post(url, {}, format='json')
        self.assertEqual(r2.status_code, status.HTTP_200_OK)
        self.assertTrue(r2.json()['ja_existia'])

    def test_nfe_manual_rascunho_sem_estoque(self):
        pedido, item = _pedido_item()
        cli = pedido.cliente
        ser = NFeSaidaSerializer(
            data={
                'numero': 'RASCUNHO-MANUAL-1',
                'cliente_id': cli.pk,
                'data': date.today().isoformat(),
                'status': STATUS_NFE_RASCUNHO,
                'modo_atendimento_estoque': NFeSaida.ModoAtendimentoEstoque.IMEDIATO,
                'itens': [
                    {
                        'produto_id': item.produto_id,
                        'quantidade': '1',
                        'valor': '10',
                    },
                ],
            },
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        nf = ser.save()
        self.assertEqual(nf.status, STATUS_NFE_RASCUNHO)
        self.assertEqual(AtendimentoEstoque.objects.filter(nf_saida=nf).count(), 0)

    def test_ibge_entrega_cUF_invalido(self):
        """(a) entrega_cUF="XX" + demais campos do grupo preenchidos -> ValidationError"""
        from rest_framework.exceptions import ValidationError
        pedido, item = _pedido_item()
        cli = pedido.cliente
        ser = NFeSaidaSerializer(
            data={
                'numero': 'RASCUNHO-IBGE-1',
                'cliente_id': cli.pk,
                'data': date.today().isoformat(),
                'status': 'RASCUNHO',
                'modo_atendimento_estoque': NFeSaida.ModoAtendimentoEstoque.IMEDIATO,
                'itens': [
                    {
                        'produto_id': item.produto_id,
                        'quantidade': '1',
                        'valor': '10',
                    },
                ],
                'entrega_xLgr': 'Rua Teste',
                'entrega_nro': '100',
                'entrega_xMun': 'Sao Paulo',
                'entrega_UF': 'SP',
                'entrega_CEP': '01001000',
                'entrega_cMun': '3550308',
                'entrega_cUF': 'XX',  # UF invalida
                'entrega_xNome': 'Cliente Teste',
            },
        )
        with self.assertRaises(ValidationError) as ctx:
            ser.is_valid(raise_exception=True)
        self.assertIn('entrega_cUF', ctx.exception.detail)

    def test_ibge_entrega_cMun_invalido(self):
        """(b) entrega_cMun="abc" + demais campos preenchidos -> ValidationError"""
        from rest_framework.exceptions import ValidationError
        pedido, item = _pedido_item()
        cli = pedido.cliente
        ser = NFeSaidaSerializer(
            data={
                'numero': 'RASCUNHO-IBGE-2',
                'cliente_id': cli.pk,
                'data': date.today().isoformat(),
                'status': 'RASCUNHO',
                'modo_atendimento_estoque': NFeSaida.ModoAtendimentoEstoque.IMEDIATO,
                'itens': [
                    {
                        'produto_id': item.produto_id,
                        'quantidade': '1',
                        'valor': '10',
                    },
                ],
                'entrega_xLgr': 'Rua Teste',
                'entrega_nro': '100',
                'entrega_xMun': 'Sao Paulo',
                'entrega_UF': 'SP',
                'entrega_CEP': '01001000',
                'entrega_cMun': 'abc',  # nao e 7 digitos
                'entrega_cUF': 'SP',  # UF valida
                'entrega_xNome': 'Cliente Teste',
            },
        )
        with self.assertRaises(ValidationError) as ctx:
            ser.is_valid(raise_exception=True)
        self.assertIn('entrega_cMun', ctx.exception.detail)

    def test_ibge_grupo_vazio_passa(self):
        """(c) grupo entrega/retirada totalmente vazio -> passa (nao lanca erro)"""
        from rest_framework.exceptions import ValidationError
        pedido, item = _pedido_item()
        cli = pedido.cliente
        ser = NFeSaidaSerializer(
            data={
                'numero': 'RASCUNHO-IBGE-3',
                'cliente_id': cli.pk,
                'data': date.today().isoformat(),
                'status': 'RASCUNHO',
                'modo_atendimento_estoque': NFeSaida.ModoAtendimentoEstoque.IMEDIATO,
                'itens': [
                    {
                        'produto_id': item.produto_id,
                        'quantidade': '1',
                        'valor': '10',
                    },
                ],
                # Nenhum campo de entrega/retirada preenchido
            },
        )
        # Deve passar sem validacao IBGE (grupo vazio)
        self.assertTrue(ser.is_valid(), msg=f"Expected valid, got: {ser.errors}")

    def test_ibge_entrega_valido(self):
        """(d) entrega_cUF="SP", entrega_cMun="3550308", demais campos validos -> passa"""
        from rest_framework.exceptions import ValidationError
        pedido, item = _pedido_item()
        cli = pedido.cliente
        ser = NFeSaidaSerializer(
            data={
                'numero': 'RASCUNHO-IBGE-4',
                'cliente_id': cli.pk,
                'data': date.today().isoformat(),
                'status': 'RASCUNHO',
                'modo_atendimento_estoque': NFeSaida.ModoAtendimentoEstoque.IMEDIATO,
                'itens': [
                    {
                        'produto_id': item.produto_id,
                        'quantidade': '1',
                        'valor': '10',
                    },
                ],
                'entrega_xLgr': 'Rua Teste',
                'entrega_nro': '100',
                'entrega_xMun': 'Sao Paulo',
                'entrega_UF': 'SP',
                'entrega_CEP': '01001000',
                'entrega_cMun': '3550308',  # IBGE de SP
                'entrega_cUF': 'SP',  # UF valida
                'entrega_xNome': 'Cliente Teste',
                'entrega_cnpj': '12345678000199',
            },
        )
        self.assertTrue(ser.is_valid(), msg=f"Expected valid, got: {ser.errors}")

    def test_ibge_retirada_cUF_invalido(self):
        """(e) retirada_cUF="XX" + demais campos do grupo preenchidos -> ValidationError"""
        from rest_framework.exceptions import ValidationError
        pedido, item = _pedido_item()
        cli = pedido.cliente
        ser = NFeSaidaSerializer(
            data={
                'numero': 'RASCUNHO-IBGE-5',
                'cliente_id': cli.pk,
                'data': date.today().isoformat(),
                'status': 'RASCUNHO',
                'modo_atendimento_estoque': NFeSaida.ModoAtendimentoEstoque.IMEDIATO,
                'itens': [
                    {
                        'produto_id': item.produto_id,
                        'quantidade': '1',
                        'valor': '10',
                    },
                ],
                'retirada_xLgr': 'Rua Teste',
                'retirada_nro': '200',
                'retirada_xMun': 'Campinas',
                'retirada_UF': 'SP',
                'retirada_CEP': '13000000',
                'retirada_cMun': '3509502',
                'retirada_cUF': 'XX',  # UF invalida
                'retirada_xNome': 'Cliente Teste',
            },
        )
        with self.assertRaises(ValidationError) as ctx:
            ser.is_valid(raise_exception=True)
        self.assertIn('retirada_cUF', ctx.exception.detail)

    def test_ibge_retirada_cMun_invalido(self):
        """(f) retirada_cMun="abc" + demais campos preenchidos -> ValidationError"""
        from rest_framework.exceptions import ValidationError
        pedido, item = _pedido_item()
        cli = pedido.cliente
        ser = NFeSaidaSerializer(
            data={
                'numero': 'RASCUNHO-IBGE-6',
                'cliente_id': cli.pk,
                'data': date.today().isoformat(),
                'status': 'RASCUNHO',
                'modo_atendimento_estoque': NFeSaida.ModoAtendimentoEstoque.IMEDIATO,
                'itens': [
                    {
                        'produto_id': item.produto_id,
                        'quantidade': '1',
                        'valor': '10',
                    },
                ],
                'retirada_xLgr': 'Rua Teste',
                'retirada_nro': '200',
                'retirada_xMun': 'Campinas',
                'retirada_UF': 'SP',
                'retirada_CEP': '13000000',
                'retirada_cMun': 'abc',  # nao e 7 digitos
                'retirada_cUF': 'SP',  # UF valida
                'retirada_xNome': 'Cliente Teste',
            },
        )
        with self.assertRaises(ValidationError) as ctx:
            ser.is_valid(raise_exception=True)
        self.assertIn('retirada_cMun', ctx.exception.detail)

    def test_ibge_grupo_retirada_vazio_passa(self):
        """(g) grupo retirada totalmente vazio -> passa (nao lanca erro)"""
        from rest_framework.exceptions import ValidationError
        pedido, item = _pedido_item()
        cli = pedido.cliente
        ser = NFeSaidaSerializer(
            data={
                'numero': 'RASCUNHO-IBGE-7',
                'cliente_id': cli.pk,
                'data': date.today().isoformat(),
                'status': 'RASCUNHO',
                'modo_atendimento_estoque': NFeSaida.ModoAtendimentoEstoque.IMEDIATO,
                'itens': [
                    {
                        'produto_id': item.produto_id,
                        'quantidade': '1',
                        'valor': '10',
                    },
                ],
                # Apenas entrega preenchida, retirada vazia (nenhum campo de retirada)
                'entrega_xLgr': 'Rua Teste',
                'entrega_nro': '100',
                'entrega_xMun': 'Sao Paulo',
                'entrega_UF': 'SP',
                'entrega_CEP': '01001000',
                'entrega_cMun': '3550308',
                'entrega_cUF': 'SP',
                'entrega_xNome': 'Cliente Teste',
                'entrega_cnpj': '12345678000199',
                # Sem campos de retirada preenchidos
            },
        )
        # Deve passar - entrega preenchida com IBGE valido
        self.assertTrue(ser.is_valid(), msg=f"Expected valid, got: {ser.errors}")

    def test_ibge_retirada_valido(self):
        """(h) retirada_cUF="SP", retirada_cMun="3550308", demais campos validos -> passa"""
        from rest_framework.exceptions import ValidationError
        pedido, item = _pedido_item()
        cli = pedido.cliente
        ser = NFeSaidaSerializer(
            data={
                'numero': 'RASCUNHO-IBGE-8',
                'cliente_id': cli.pk,
                'data': date.today().isoformat(),
                'status': 'RASCUNHO',
                'modo_atendimento_estoque': NFeSaida.ModoAtendimentoEstoque.IMEDIATO,
                'itens': [
                    {
                        'produto_id': item.produto_id,
                        'quantidade': '1',
                        'valor': '10',
                    },
                ],
                # Apenas retirada preenchida, entrega vazia
                'retirada_xLgr': 'Rua Teste',
                'retirada_nro': '200',
                'retirada_xMun': 'Campinas',
                'retirada_UF': 'SP',
                'retirada_CEP': '13000000',
                'retirada_cMun': '3550308',  # IBGE de SP
                'retirada_cUF': 'SP',  # UF valida
                'retirada_xNome': 'Cliente Teste',
                'retirada_cnpj': '12345678000199',
                # Sem campos de entrega preenchidos
            },
        )
        self.assertTrue(ser.is_valid(), msg=f"Expected valid, got: {ser.errors}")

    def _payload_entrega(self, **extra):
        pedido, item = _pedido_item()
        data = {
            'numero': f'RASCUNHO-TLOCAL-{uuid.uuid4().hex[:6]}',
            'cliente_id': pedido.cliente.pk,
            'data': date.today().isoformat(),
            'status': 'RASCUNHO',
            'modo_atendimento_estoque': NFeSaida.ModoAtendimentoEstoque.IMEDIATO,
            'itens': [
                {
                    'produto_id': item.produto_id,
                    'quantidade': '1',
                    'valor': '10',
                },
            ],
            'entrega_xLgr': 'Rua Teste',
            'entrega_nro': '100',
            'entrega_xMun': 'Sao Paulo',
            'entrega_UF': 'SP',
            'entrega_CEP': '01001000',
            'entrega_cMun': '3550308',
            'entrega_cUF': 'SP',
            'entrega_xNome': 'Cliente Teste',
        }
        data.update(extra)
        return NFeSaidaSerializer(data=data)

    def test_tlocal_entrega_sem_cnpj_cpf_bloqueia(self):
        """TLocal exige CNPJ|CPF: grupo preenchido sem documento -> ValidationError"""
        from rest_framework.exceptions import ValidationError
        ser = self._payload_entrega()
        with self.assertRaises(ValidationError) as ctx:
            ser.is_valid(raise_exception=True)
        self.assertIn('entrega_cnpj', ctx.exception.detail)

    def test_tlocal_entrega_com_cnpj_e_cpf_bloqueia(self):
        """Choice exclusivo: CNPJ e CPF juntos -> ValidationError"""
        from rest_framework.exceptions import ValidationError
        ser = self._payload_entrega(entrega_cnpj='12345678000199', entrega_cpf='12345678901')
        with self.assertRaises(ValidationError) as ctx:
            ser.is_valid(raise_exception=True)
        self.assertIn('entrega_cnpj', ctx.exception.detail)

    def test_tlocal_entrega_cnpj_13_digitos_bloqueia(self):
        """CNPJ com 13 digitos -> ValidationError"""
        from rest_framework.exceptions import ValidationError
        ser = self._payload_entrega(entrega_cnpj='1234567800019')
        with self.assertRaises(ValidationError) as ctx:
            ser.is_valid(raise_exception=True)
        self.assertIn('entrega_cnpj', ctx.exception.detail)

    def test_tlocal_entrega_cpf_valido(self):
        """CPF com 11 digitos e aceito no grupo"""
        ser = self._payload_entrega(entrega_cpf='12345678901')
        self.assertTrue(ser.is_valid(), msg=f"Expected valid, got: {ser.errors}")
        self.assertEqual(ser.validated_data['entrega_cpf'], '12345678901')
