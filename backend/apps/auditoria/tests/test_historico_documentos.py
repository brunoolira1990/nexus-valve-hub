"""Histórico de auditoria dos documentos (Sprint 3.18-0 — pré-requisito do rail do chatter).

Espelha test_historico_fornecedor.py: o que se prova aqui é que a escrita dos
serializers/views de documento gera o registro com a MESMA chave
(app_label, model_name lowercase da classe) que a consulta de histórico aceita.
"""

from __future__ import annotations

import json
import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.auditoria.models import RegistroAuditoria
from apps.cadastros.models import Cliente, Empresa, Fornecedor
from apps.comercial.cotacao_fornecedor_serializers import CotacaoFornecedorSerializer
from apps.comercial.models import (
    CotacaoFornecedor,
    ItemProposta,
    Proposta,
)
from apps.comercial.serializers import (
    PedidoCompraSerializer,
    PedidoVendaSerializer,
    PropostaSerializer,
)
from apps.fiscal.models import NFeEntrada, NFeSaida
from apps.fiscal.serializers import NFeEntradaSerializer, NFeSaidaSerializer
from apps.produtos.models import FamiliaProduto, Produto

CNPJ_VALIDO = '11222333000181'
TEXTO_MASCARADO = 'ORCAMENTO-SEGREDO-NAO-PODE-APARECER'


def _suf() -> str:
    return uuid.uuid4().hex[:8]


def _familia() -> FamiliaProduto:
    s = _suf()
    return FamiliaProduto.objects.create(
        codigo_figura=f'FT{s}'[:16],
        descricao_base=f'Família teste {s}',
        tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
        categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
    )


def _produto() -> Produto:
    return Produto.objects.create(
        familia=_familia(),
        descricao=f'Válvula teste {_suf()}',
        modo_codigo=Produto.ModoCodigo.MANUAL,
        codigo_completo=f'C-{_suf()}',
        unidade='PC',
        ncm='84818200',
    )


class BaseDocumentoTests(TestCase):
    """Usuário com a permissão de leitura do histórico: mesma do teste de fornecedor."""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(f'hist_{_suf()}', password='secret')
        self.user.user_permissions.add(
            Permission.objects.get(
                content_type=ContentType.objects.get_for_model(RegistroAuditoria),
                codename='view_registroauditoria',
            )
        )
        self.api = APIClient()

    def _registro(self, model_name: str, operacao: str, object_id: int) -> RegistroAuditoria:
        return RegistroAuditoria.objects.get(
            model_name=model_name, operacao=operacao, object_id=object_id
        )

    def _consultar(self, app_label: str, model_name: str, object_id: int):
        self.api.force_authenticate(user=self.user)
        return self.api.get(f'/api/auditoria/objetos/{app_label}/{model_name}/{object_id}/')


class PropostaHistoricoTests(BaseDocumentoTests):
    def setUp(self):
        super().setUp()
        self.cliente = Cliente.objects.create(razao_social=f'Cliente {_suf()}', cnpj=CNPJ_VALIDO, uf='RJ')
        self.empresa = Empresa.objects.create(razao_social=f'Emitente {_suf()}', cnpj='22333444000182', uf='SP')
        self.produto = _produto()

    def _payload(self, **kwargs):
        dados = {
            'cliente_id': self.cliente.pk,
            'empresa_emitente_id': self.empresa.pk,
            'itens': [
                {
                    'produto_id': self.produto.pk,
                    'quantidade': 1,
                    'valor_unitario': 100,
                    'preco_por_unidade_negociada': 100,
                },
            ],
        }
        dados.update(kwargs)
        return dados

    def test_create_registra_operacao_create(self):
        serializer = PropostaSerializer(data=self._payload(), context={'request': None})
        serializer.is_valid(raise_exception=True)
        proposta = serializer.save()

        registro = self._registro('proposta', 'CREATE', proposta.pk)
        self.assertEqual(registro.app_label, 'comercial')
        self.assertEqual(registro.alteracoes['numero']['depois'], proposta.numero)
        self.assertEqual(registro.alteracoes['cliente_id']['depois'], self.cliente.pk)

    def test_update_registra_apenas_o_campo_alterado(self):
        serializer = PropostaSerializer(data=self._payload(), context={'request': None})
        serializer.is_valid(raise_exception=True)
        proposta = serializer.save()
        RegistroAuditoria.objects.filter(model_name='proposta').delete()

        update = PropostaSerializer(
            instance=proposta,
            data={'frete_texto': 'FOB'},
            partial=True,
            context={'request': None},
        )
        update.is_valid(raise_exception=True)
        update.save()

        registro = self._registro('proposta', 'UPDATE', proposta.pk)
        self.assertEqual(registro.alteracoes['frete_texto'], {'antes': '', 'depois': 'FOB'})
        self.assertNotIn('numero', registro.alteracoes)
        self.assertNotIn('valor_total', registro.alteracoes)

    def test_texto_livre_mascarado_e_campo_excluido_nao_gravam_valor(self):
        serializer = PropostaSerializer(data=self._payload(), context={'request': None})
        serializer.is_valid(raise_exception=True)
        proposta = serializer.save()
        proposta.dias_parcelas = [30, 60]
        proposta.save()
        RegistroAuditoria.objects.filter(model_name='proposta').delete()

        update = PropostaSerializer(
            instance=proposta,
            data={'mensagem_comercial': TEXTO_MASCARADO, 'validade_dias': 45},
            partial=True,
            context={'request': None},
        )
        update.is_valid(raise_exception=True)
        update.save()

        registro = self._registro('proposta', 'UPDATE', proposta.pk)
        self.assertEqual(
            registro.alteracoes['mensagem_comercial'], {'sensivel': True, 'alterado': True}
        )
        self.assertEqual(registro.alteracoes['validade_dias']['depois'], 45)
        self.assertNotIn('dias_parcelas', registro.alteracoes)
        self.assertNotIn(TEXTO_MASCARADO, json.dumps(registro.alteracoes))
        proposta.refresh_from_db()
        self.assertEqual(proposta.mensagem_comercial, TEXTO_MASCARADO)

    def test_api_de_historico_devolve_200_para_proposta(self):
        serializer = PropostaSerializer(data=self._payload(), context={'request': None})
        serializer.is_valid(raise_exception=True)
        proposta = serializer.save()

        r = self._consultar('comercial', 'proposta', proposta.pk)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['count'], 1)


class PedidoVendaHistoricoTests(BaseDocumentoTests):
    def setUp(self):
        super().setUp()
        self.cliente = Cliente.objects.create(razao_social=f'Cliente {_suf()}', cnpj=CNPJ_VALIDO, uf='RJ')
        self.empresa = Empresa.objects.create(razao_social=f'Emitente {_suf()}', cnpj='22333444000182', uf='SP')
        self.produto = _produto()

    def _payload(self):
        return {
            'cliente_id': self.cliente.pk,
            'empresa_emitente_id': self.empresa.pk,
            'itens': [
                {
                    'produto_id': self.produto.pk,
                    'quantidade': 2,
                    'valor_unitario': 50,
                    'preco_por_unidade_negociada': 50,
                },
            ],
        }

    def test_create_registra_operacao_create(self):
        serializer = PedidoVendaSerializer(data=self._payload(), context={'request': None})
        serializer.is_valid(raise_exception=True)
        pedido = serializer.save()

        registro = self._registro('pedidovenda', 'CREATE', pedido.pk)
        self.assertEqual(registro.app_label, 'comercial')
        self.assertEqual(registro.alteracoes['status']['depois'], pedido.status)
        self.assertEqual(registro.alteracoes['cliente_id']['depois'], self.cliente.pk)

    def test_update_registra_apenas_o_campo_alterado(self):
        serializer = PedidoVendaSerializer(data=self._payload(), context={'request': None})
        serializer.is_valid(raise_exception=True)
        pedido = serializer.save()
        RegistroAuditoria.objects.filter(model_name='pedidovenda').delete()

        update = PedidoVendaSerializer(
            instance=pedido,
            data={'prazo_entrega_texto': '15 dias úteis'},
            partial=True,
            context={'request': None},
        )
        update.is_valid(raise_exception=True)
        update.save()

        registro = self._registro('pedidovenda', 'UPDATE', pedido.pk)
        self.assertEqual(
            registro.alteracoes['prazo_entrega_texto'],
            {'antes': '', 'depois': '15 dias úteis'},
        )
        self.assertNotIn('numero', registro.alteracoes)

    def test_texto_livre_mascarado_e_campo_excluido_nao_gravam_valor(self):
        serializer = PedidoVendaSerializer(data=self._payload(), context={'request': None})
        serializer.is_valid(raise_exception=True)
        pedido = serializer.save()
        pedido.snapshot_conversao = {'origem': 'wizard'}
        pedido.vencimentos_previstos = [date(2026, 12, 1)]
        pedido.save()
        RegistroAuditoria.objects.filter(model_name='pedidovenda').delete()

        update = PedidoVendaSerializer(
            instance=pedido,
            data={'observacoes_internas': TEXTO_MASCARADO, 'valor_frete': '30.00'},
            partial=True,
            context={'request': None},
        )
        update.is_valid(raise_exception=True)
        update.save()

        registro = self._registro('pedidovenda', 'UPDATE', pedido.pk)
        self.assertEqual(
            registro.alteracoes['observacoes_internas'], {'sensivel': True, 'alterado': True}
        )
        self.assertEqual(registro.alteracoes['valor_frete']['depois'], '30.00')
        self.assertNotIn('snapshot_conversao', registro.alteracoes)
        self.assertNotIn('vencimentos_previstos', registro.alteracoes)
        self.assertNotIn(TEXTO_MASCARADO, json.dumps(registro.alteracoes))

    def test_update_sem_diff_nao_grava_registro(self):
        serializer = PedidoVendaSerializer(data=self._payload(), context={'request': None})
        serializer.is_valid(raise_exception=True)
        pedido = serializer.save()

        # O validate() recalcula quantidade_parcelas em toda escrita, então o primeiro
        # PATCH já tem diff (0 → 1). O estado estável é o segundo PATCH com o mesmo valor:
        # aí o cabeçalho não muda e a auditoria não pode gravar nada.
        primeiro = PedidoVendaSerializer(
            instance=pedido,
            data={'prazo_entrega_texto': '10 dias'},
            partial=True,
            context={'request': None},
        )
        primeiro.is_valid(raise_exception=True)
        primeiro.save()
        RegistroAuditoria.objects.filter(model_name='pedidovenda').delete()

        segundo = PedidoVendaSerializer(
            instance=pedido,
            data={'prazo_entrega_texto': '10 dias'},
            partial=True,
            context={'request': None},
        )
        segundo.is_valid(raise_exception=True)
        segundo.save()

        self.assertEqual(
            list(
                RegistroAuditoria.objects.filter(model_name='pedidovenda').values_list(
                    'alteracoes', flat=True
                )
            ),
            [],
            'diff vazio não pode produzir registro de auditoria',
        )

    def test_api_de_historico_devolve_200_para_pedido_venda(self):
        serializer = PedidoVendaSerializer(data=self._payload(), context={'request': None})
        serializer.is_valid(raise_exception=True)
        pedido = serializer.save()

        r = self._consultar('comercial', 'pedidovenda', pedido.pk)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['count'], 1)


class PedidoCompraHistoricoTests(BaseDocumentoTests):
    def setUp(self):
        super().setUp()
        self.fornecedor = Fornecedor.objects.create(razao_social=f'Fornecedor {_suf()}', cnpj=CNPJ_VALIDO)
        self.produto = _produto()

    def _payload(self):
        return {
            'fornecedor_id': self.fornecedor.pk,
            'data': '2026-05-13',
            'status': 'Pendente',
            'condicao_pagamento_texto': '30',
            'itens': [
                {
                    'produto_id': self.produto.pk,
                    'quantidade': '10',
                    'quantidade_negociada': '10',
                    'valor_unitario': '50.00',
                    'preco_por_unidade_negociada': '50.00',
                    'unidade_negociada': 'PC',
                },
            ],
        }

    def test_create_registra_operacao_create(self):
        serializer = PedidoCompraSerializer(data=self._payload(), context={'request': None})
        serializer.is_valid(raise_exception=True)
        pedido = serializer.save()

        registro = self._registro('pedidocompra', 'CREATE', pedido.pk)
        self.assertEqual(registro.app_label, 'comercial')
        self.assertEqual(registro.alteracoes['fornecedor_id']['depois'], self.fornecedor.pk)
        self.assertEqual(registro.alteracoes['data']['depois'], '2026-05-13')

    def test_update_registra_apenas_o_campo_alterado(self):
        serializer = PedidoCompraSerializer(data=self._payload(), context={'request': None})
        serializer.is_valid(raise_exception=True)
        pedido = serializer.save()
        RegistroAuditoria.objects.filter(model_name='pedidocompra').delete()

        update = PedidoCompraSerializer(
            instance=pedido,
            data={'data_prevista_entrega': '2026-06-01'},
            partial=True,
            context={'request': None},
        )
        update.is_valid(raise_exception=True)
        update.save()

        registro = self._registro('pedidocompra', 'UPDATE', pedido.pk)
        self.assertEqual(
            registro.alteracoes['data_prevista_entrega'],
            {'antes': None, 'depois': '2026-06-01'},
        )
        self.assertNotIn('numero', registro.alteracoes)

    def test_texto_livre_mascarado_e_campo_excluido_nao_gravam_valor(self):
        serializer = PedidoCompraSerializer(data=self._payload(), context={'request': None})
        serializer.is_valid(raise_exception=True)
        pedido = serializer.save()
        pedido.vencimentos_previstos = [date(2026, 6, 12)]
        pedido.save()
        RegistroAuditoria.objects.filter(model_name='pedidocompra').delete()

        update = PedidoCompraSerializer(
            instance=pedido,
            data={'observacoes': TEXTO_MASCARADO, 'prazo_entrega_texto': '20 dias'},
            partial=True,
            context={'request': None},
        )
        update.is_valid(raise_exception=True)
        update.save()

        registro = self._registro('pedidocompra', 'UPDATE', pedido.pk)
        self.assertEqual(
            registro.alteracoes['observacoes'], {'sensivel': True, 'alterado': True}
        )
        self.assertEqual(registro.alteracoes['prazo_entrega_texto']['depois'], '20 DIAS')
        self.assertNotIn('vencimentos_previstos', registro.alteracoes)
        self.assertNotIn(TEXTO_MASCARADO, json.dumps(registro.alteracoes))

    def test_api_de_historico_devolve_200_para_pedido_compra(self):
        serializer = PedidoCompraSerializer(data=self._payload(), context={'request': None})
        serializer.is_valid(raise_exception=True)
        pedido = serializer.save()

        r = self._consultar('comercial', 'pedidocompra', pedido.pk)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['count'], 1)


class CotacaoFornecedorHistoricoTests(BaseDocumentoTests):
    """CREATE da cotação acontece na view (CotacaoFornecedorViewSet.create), não no serializer."""

    def setUp(self):
        super().setUp()
        perms = Permission.objects.filter(
            content_type__app_label='comercial',
            codename__in=('view_cotacaofornecedor', 'add_cotacaofornecedor', 'change_cotacaofornecedor'),
        )
        self.user.user_permissions.add(*perms)
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.cliente = Cliente.objects.create(razao_social=f'Cliente {_suf()}', cnpj=CNPJ_VALIDO)
        self.proposta = Proposta.objects.create(
            numero=f'P-{_suf()}',
            cliente=self.cliente,
            data=date.today(),
            validade=date.today() + timedelta(days=30),
            status='RASCUNHO',
        )
        ItemProposta.objects.create(
            proposta=self.proposta,
            descricao_avulsa='Item A',
            quantidade=Decimal('10'),
            quantidade_negociada=Decimal('10'),
            valor_unitario=Decimal('100'),
            preco_por_unidade_negociada=Decimal('100'),
        )

    def _criar_pela_api(self, observacao: str = '') -> CotacaoFornecedor:
        response = self.api.post(
            '/api/cotacoes-fornecedores/',
            {
                'proposta': self.proposta.pk,
                'data': date.today().isoformat(),
                'observacao': observacao,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        return CotacaoFornecedor.objects.get(pk=response.data['id'])

    def test_create_pela_api_registra_operacao_create(self):
        cotacao = self._criar_pela_api()

        registro = self._registro('cotacaofornecedor', 'CREATE', cotacao.pk)
        self.assertEqual(registro.app_label, 'comercial')
        self.assertEqual(registro.alteracoes['numero']['depois'], cotacao.numero)
        self.assertEqual(registro.alteracoes['proposta_id']['depois'], self.proposta.pk)
        self.assertEqual(registro.alteracoes['responsavel_id']['depois'], self.user.pk)

    def test_create_pela_api_mascara_a_observacao(self):
        cotacao = self._criar_pela_api(observacao=TEXTO_MASCARADO)

        registro = self._registro('cotacaofornecedor', 'CREATE', cotacao.pk)
        self.assertEqual(
            registro.alteracoes['observacao'], {'sensivel': True, 'alterado': True}
        )
        self.assertNotIn(TEXTO_MASCARADO, json.dumps(registro.alteracoes))

    def test_update_registra_diff_do_campo_alterado_sem_carimbo_de_tabela(self):
        cotacao = self._criar_pela_api()
        RegistroAuditoria.objects.filter(model_name='cotacaofornecedor').delete()
        prazo = date.today() + timedelta(days=7)

        update = CotacaoFornecedorSerializer(
            instance=cotacao,
            data={'prazo_resposta': prazo.isoformat()},
            partial=True,
            context={'request': None},
        )
        update.is_valid(raise_exception=True)
        update.save()

        registro = self._registro('cotacaofornecedor', 'UPDATE', cotacao.pk)
        self.assertEqual(
            registro.alteracoes['prazo_resposta'],
            {'antes': None, 'depois': prazo.isoformat()},
        )
        self.assertNotIn('atualizado_em', registro.alteracoes)
        self.assertNotIn('criado_em', registro.alteracoes)

    def test_update_sem_diff_nao_grava_registro(self):
        cotacao = self._criar_pela_api()
        RegistroAuditoria.objects.filter(model_name='cotacaofornecedor').delete()

        update = CotacaoFornecedorSerializer(
            instance=cotacao,
            data={'data': cotacao.data.isoformat()},
            partial=True,
            context={'request': None},
        )
        update.is_valid(raise_exception=True)
        update.save()

        self.assertFalse(
            RegistroAuditoria.objects.filter(model_name='cotacaofornecedor').exists(),
            'diff vazio não pode produzir registro de auditoria',
        )

    def test_api_de_historico_devolve_200_para_cotacao(self):
        cotacao = self._criar_pela_api()

        r = self._consultar('comercial', 'cotacaofornecedor', cotacao.pk)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['count'], 1)


class NFeSaidaHistoricoTests(BaseDocumentoTests):
    def setUp(self):
        super().setUp()
        self.cliente = Cliente.objects.create(razao_social=f'Cliente {_suf()}', cnpj=CNPJ_VALIDO, uf='RJ')
        self.produto = _produto()

    def _payload(self):
        return {
            'numero': f'NF-{_suf()}',
            'cliente_id': self.cliente.pk,
            'data': date.today().isoformat(),
            'status': 'RASCUNHO',
            'itens': [
                {'produto_id': self.produto.pk, 'quantidade': '5', 'valor': '40.00'},
            ],
        }

    def _criar(self) -> NFeSaida:
        serializer = NFeSaidaSerializer(data=self._payload(), context={'request': None})
        serializer.is_valid(raise_exception=True)
        return serializer.save()

    def test_create_registra_operacao_create(self):
        nf = self._criar()

        registro = self._registro('nfesaida', 'CREATE', nf.pk)
        self.assertEqual(registro.app_label, 'fiscal')
        self.assertEqual(registro.alteracoes['numero']['depois'], nf.numero)
        self.assertEqual(registro.alteracoes['cliente_id']['depois'], self.cliente.pk)
        self.assertEqual(Decimal(registro.alteracoes['valor_total']['depois']), Decimal('200'))

    def test_update_registra_apenas_o_campo_alterado(self):
        nf = self._criar()
        RegistroAuditoria.objects.filter(model_name='nfesaida').delete()

        update = NFeSaidaSerializer(
            instance=nf,
            data={'pedido_cliente_numero': 'PED-CLI-9'},
            partial=True,
            context={'request': None},
        )
        update.is_valid(raise_exception=True)
        update.save()

        registro = self._registro('nfesaida', 'UPDATE', nf.pk)
        self.assertEqual(
            registro.alteracoes['pedido_cliente_numero'],
            {'antes': '', 'depois': 'PED-CLI-9'},
        )
        self.assertNotIn('valor_total', registro.alteracoes)

    def test_texto_livre_mascarado_e_blob_de_xml_nao_gravam_valor(self):
        nf = self._criar()
        nf.xml_preliminar = '<nfe>' + TEXTO_MASCARADO + '</nfe>'
        nf.save()
        RegistroAuditoria.objects.filter(model_name='nfesaida').delete()

        update = NFeSaidaSerializer(
            instance=nf,
            data={'observacoes_nfe': TEXTO_MASCARADO, 'placa_veiculo': 'XYZ9A88'},
            partial=True,
            context={'request': None},
        )
        update.is_valid(raise_exception=True)
        update.save()

        registro = self._registro('nfesaida', 'UPDATE', nf.pk)
        self.assertEqual(
            registro.alteracoes['observacoes_nfe'], {'sensivel': True, 'alterado': True}
        )
        self.assertEqual(registro.alteracoes['placa_veiculo']['depois'], 'XYZ9A88')
        self.assertNotIn('xml_preliminar', registro.alteracoes)
        self.assertNotIn(TEXTO_MASCARADO, json.dumps(registro.alteracoes))

    def test_api_de_historico_devolve_200_para_nfe_saida(self):
        nf = self._criar()

        r = self._consultar('fiscal', 'nfesaida', nf.pk)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['count'], 1)


class NFeEntradaHistoricoTests(BaseDocumentoTests):
    def setUp(self):
        super().setUp()
        self.fornecedor = Fornecedor.objects.create(razao_social=f'Fornecedor {_suf()}', cnpj=CNPJ_VALIDO)
        self.produto = _produto()

    def _payload(self):
        return {
            'numero': f'NFE-{_suf()}',
            'fornecedor_id': self.fornecedor.pk,
            'data': date.today().isoformat(),
            'itens': [
                {'produto_id': self.produto.pk, 'quantidade': '4', 'valor': '25.00'},
            ],
        }

    def _criar(self) -> NFeEntrada:
        serializer = NFeEntradaSerializer(data=self._payload(), context={'request': None})
        serializer.is_valid(raise_exception=True)
        return serializer.save()

    def test_create_registra_operacao_create(self):
        nf = self._criar()

        registro = self._registro('nfeentrada', 'CREATE', nf.pk)
        self.assertEqual(registro.app_label, 'fiscal')
        self.assertEqual(registro.alteracoes['numero']['depois'], nf.numero)
        self.assertEqual(registro.alteracoes['fornecedor_id']['depois'], self.fornecedor.pk)
        self.assertEqual(Decimal(registro.alteracoes['valor_total']['depois']), Decimal('100'))

    def test_update_registra_apenas_o_campo_alterado(self):
        nf = self._criar()
        RegistroAuditoria.objects.filter(model_name='nfeentrada').delete()

        update = NFeEntradaSerializer(
            instance=nf,
            data={'nat_op': '1.556'},
            partial=True,
            context={'request': None},
        )
        update.is_valid(raise_exception=True)
        update.save()

        registro = self._registro('nfeentrada', 'UPDATE', nf.pk)
        self.assertEqual(registro.alteracoes['nat_op']['depois'], '1.556')
        self.assertNotIn('numero', registro.alteracoes)

    def test_texto_livre_mascarado_e_json_importado_nao_gravam_valor(self):
        nf = self._criar()
        nf.itens_json = [{'x': TEXTO_MASCARADO}]
        nf.nome_arquivo = f'{TEXTO_MASCARADO}.xml'
        nf.save()
        RegistroAuditoria.objects.filter(model_name='nfeentrada').delete()

        update = NFeEntradaSerializer(
            instance=nf,
            data={'motivo_autorizacao': TEXTO_MASCARADO, 'protocolo_autorizacao': 'PROTO-1'},
            partial=True,
            context={'request': None},
        )
        update.is_valid(raise_exception=True)
        update.save()

        registro = self._registro('nfeentrada', 'UPDATE', nf.pk)
        self.assertEqual(
            registro.alteracoes['motivo_autorizacao'], {'sensivel': True, 'alterado': True}
        )
        self.assertEqual(registro.alteracoes['protocolo_autorizacao']['depois'], 'PROTO-1')
        self.assertNotIn('itens_json', registro.alteracoes)
        self.assertNotIn('nome_arquivo', registro.alteracoes)
        self.assertNotIn(TEXTO_MASCARADO, json.dumps(registro.alteracoes))

    def test_api_de_historico_devolve_200_para_nfe_entrada(self):
        nf = self._criar()

        r = self._consultar('fiscal', 'nfeentrada', nf.pk)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['count'], 1)
