"""Comercial 2.3 — cenário fiscal padrão em novas propostas."""

from __future__ import annotations

import uuid
from datetime import date

from django.test import TestCase

from apps.cadastros.models import Cliente, Empresa
from apps.comercial.models import Proposta
from apps.comercial.serializers import PropostaSerializer
from apps.produtos.models import FamiliaProduto, Produto


def _cnpj() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


def _produto() -> Produto:
    suf = uuid.uuid4().hex[:6].upper()
    fam = FamiliaProduto.objects.create(
        codigo_figura=f'D{suf}',
        descricao_base='Fam',
        tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
        categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
    )
    return Produto.objects.create(
        familia=fam,
        descricao='P',
        modo_codigo=Produto.ModoCodigo.MANUAL,
        codigo_completo=f'C-{suf}',
        unidade='PC',
        ncm='84818200',
    )


class Comercial23PropostaDefaultsTests(TestCase):
    def setUp(self):
        self.emp = Empresa.objects.create(razao_social='Emit', cnpj=_cnpj(), uf='SP')
        self.cli = Cliente.objects.create(razao_social='Cli', cnpj=_cnpj(), uf='RJ')

    def test_nova_proposta_api_default_cenario_fiscal(self):
        ser = PropostaSerializer(
            data={
                'cliente_id': self.cli.pk,
                'empresa_emitente_id': self.emp.pk,
                'itens': [
                    {
                        'produto_id': _produto().pk,
                        'quantidade': 1,
                        'valor_unitario': 10,
                        'preco_por_unidade_negociada': 10,
                    },
                ],
            },
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        p = ser.save()
        self.assertTrue(p.usar_cenario_fiscal_saida)

    def test_proposta_antiga_legado_preservada(self):
        hoje = date.today()
        p = Proposta.objects.create(
            numero='PROP-LEG-23',
            data=hoje,
            validade=hoje,
            empresa_emitente=self.emp,
            cliente=self.cli,
            usar_cenario_fiscal_saida=False,
            status='PENDENTE',
        )
        data = PropostaSerializer(p).data
        self.assertFalse(data['usar_cenario_fiscal_saida'])
