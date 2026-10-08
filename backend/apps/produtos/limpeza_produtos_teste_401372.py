"""Limpeza segura de produtos artificiais de teste — ERP 4.0.13.7.2."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.core.limpeza_dados_teste import LimpezaDadosTesteError, verificar_ambiente_seguro
from apps.produtos.models import FamiliaProduto, Produto

logger = logging.getLogger(__name__)

CONFIRMACAO_TOKEN = 'LIMPAR_PRODUTOS_TESTE_401372'

CODIGOS_ARTIFICIAIS: frozenset[str] = frozenset(
    {
        'N2E3962',
        'N314EC2',
        'N34396F',
        'N3CD209',
        'N569FA5',
        'N5A7BEE',
        'N6FD88A',
        'NC57F41',
        'NCE3685',
    },
)

DESCRICAO_ARTIFICIAL = 'Fam'


@dataclass
class ResultadoCandidatoFamiliaTeste:
    familia_id: int
    codigo: str
    descricao: str
    elegivel: bool
    vinculos: list[str] = field(default_factory=list)
    motivo_elegibilidade: str = ''
    acao_proposta: str = ''

    def to_dict(self) -> dict[str, Any]:
        return {
            'tipo': 'familia',
            'familia_id': self.familia_id,
            'codigo': self.codigo,
            'descricao': self.descricao,
            'elegivel': self.elegivel,
            'vinculos': self.vinculos,
            'motivo_elegibilidade': self.motivo_elegibilidade,
            'acao_proposta': self.acao_proposta,
        }


@dataclass
class ResultadoCandidatoProdutoTeste:
    produto_id: int
    codigo: str
    descricao: str
    criado_em: str | None
    elegivel: bool
    vinculos: list[str] = field(default_factory=list)
    motivo_elegibilidade: str = ''
    acao_proposta: str = ''

    def to_dict(self) -> dict[str, Any]:
        return {
            'tipo': 'produto',
            'produto_id': self.produto_id,
            'codigo': self.codigo,
            'descricao': self.descricao,
            'criado_em': self.criado_em,
            'elegivel': self.elegivel,
            'vinculos': self.vinculos,
            'motivo_elegibilidade': self.motivo_elegibilidade,
            'acao_proposta': self.acao_proposta,
        }


class LimpezaProdutosTesteError(LimpezaDadosTesteError):
    pass


def _norm_codigo(codigo: str | None) -> str:
    return (codigo or '').strip().upper()


def _norm_descricao(descricao: str | None) -> str:
    return (descricao or '').strip()


def codigo_na_lista_artificial(codigo: str | None) -> bool:
    return _norm_codigo(codigo) in CODIGOS_ARTIFICIAIS


def descricao_artificial(descricao: str | None) -> bool:
    return _norm_descricao(descricao) == DESCRICAO_ARTIFICIAL


def listar_vinculos_operacionais(produto_id: int) -> list[str]:
    """Retorna tipos de vínculo que impedem remoção automática."""
    vinculos: list[str] = []

    from apps.comercial.models import (
        ItemFaturamentoPedidoVenda,
        ItemPedidoCompra,
        ItemPedidoVenda,
        ItemProposta,
    )
    from apps.corridas.models import Corrida
    from apps.fiscal.models import (
        AlocacaoAtendimento,
        AtendimentoEstoque,
        EstoqueCorrida,
        ItemNFeEntrada,
        ItemNFeEntradaConferencia,
        ItemNFeSaida,
        NFeEntradaAgrupamentoConferencia,
    )
    from apps.produtos.models_equivalencia import (
        FornecedorComposicaoEquivalencia,
        FornecedorProdutoEquivalencia,
        ProdutoComposicao,
        ProdutoComposicaoItem,
    )
    from apps.qualidade.models import ItemCertificadoFornecedorEntrada, ItemCertificadoQualidade
    from apps.regras_fiscais.models import CenarioFiscalEntradaEscopo, CenarioFiscalSaidaEscopo

    checks: list[tuple[str, bool]] = [
        ('item_pedido_venda', ItemPedidoVenda.objects.filter(produto_id=produto_id).exists()),
        ('item_proposta', ItemProposta.objects.filter(produto_id=produto_id).exists()),
        ('item_pedido_compra', ItemPedidoCompra.objects.filter(produto_id=produto_id).exists()),
        ('item_faturamento', ItemFaturamentoPedidoVenda.objects.filter(produto_id=produto_id).exists()),
        ('item_nfe_entrada', ItemNFeEntrada.objects.filter(produto_id=produto_id).exists()),
        ('item_nfe_saida', ItemNFeSaida.objects.filter(produto_id=produto_id).exists()),
        (
            'conferencia_nfe_entrada',
            ItemNFeEntradaConferencia.objects.filter(produto_id=produto_id).exists(),
        ),
        (
            'agrupamento_equivalencia_confirmado',
            NFeEntradaAgrupamentoConferencia.objects.filter(
                produto_interno_resultante_id=produto_id,
                status='confirmado',
            ).exists(),
        ),
        ('estoque_corrida', EstoqueCorrida.objects.filter(produto_id=produto_id).exists()),
        ('atendimento_estoque', AtendimentoEstoque.objects.filter(produto_id=produto_id).exists()),
        ('alocacao_atendimento', AlocacaoAtendimento.objects.filter(produto_id=produto_id).exists()),
        ('corrida', Corrida.objects.filter(produto_id=produto_id).exists()),
        ('composicao_produto_final', ProdutoComposicao.objects.filter(produto_final_id=produto_id).exists()),
        (
            'composicao_componente',
            ProdutoComposicaoItem.objects.filter(componente_produto_id=produto_id).exists(),
        ),
        (
            'equivalencia_fornecedor_simples',
            FornecedorProdutoEquivalencia.objects.filter(produto_interno_id=produto_id).exists(),
        ),
        (
            'equivalencia_fornecedor_composta_final',
            FornecedorComposicaoEquivalencia.objects.filter(produto_interno_final_id=produto_id).exists(),
        ),
        (
            'equivalencia_fornecedor_composta_componente',
            FornecedorComposicaoEquivalencia.objects.filter(
                itens__produto_componente_interno_id=produto_id,
            ).exists(),
        ),
        (
            'certificado_qualidade',
            ItemCertificadoQualidade.objects.filter(produto_id=produto_id).exists(),
        ),
        (
            'certificado_fornecedor_entrada',
            ItemCertificadoFornecedorEntrada.objects.filter(produto_id=produto_id).exists(),
        ),
        (
            'cenario_fiscal_entrada_escopo',
            CenarioFiscalEntradaEscopo.objects.filter(produto_id=produto_id).exists(),
        ),
        (
            'cenario_fiscal_saida_escopo',
            CenarioFiscalSaidaEscopo.objects.filter(produto_id=produto_id).exists(),
        ),
    ]

    for nome, existe in checks:
        if existe:
            vinculos.append(nome)

    return vinculos


def avaliar_produto_artificial(produto: Produto) -> ResultadoCandidatoProdutoTeste:
    codigo = _norm_codigo(getattr(produto, 'codigo_completo', ''))
    descricao = _norm_descricao(produto.descricao)
    criado = None

    if not codigo_na_lista_artificial(codigo):
        return ResultadoCandidatoProdutoTeste(
            produto_id=produto.pk,
            codigo=codigo,
            descricao=descricao,
            criado_em=criado,
            elegivel=False,
            motivo_elegibilidade='código fora da lista autorizada',
            acao_proposta='preservar',
        )

    if not descricao_artificial(descricao):
        return ResultadoCandidatoProdutoTeste(
            produto_id=produto.pk,
            codigo=codigo,
            descricao=descricao,
            criado_em=criado,
            elegivel=False,
            motivo_elegibilidade='descrição diferente de "Fam"',
            acao_proposta='preservar',
        )

    vinculos = listar_vinculos_operacionais(produto.pk)
    if vinculos:
        return ResultadoCandidatoProdutoTeste(
            produto_id=produto.pk,
            codigo=codigo,
            descricao=descricao,
            criado_em=criado,
            elegivel=False,
            vinculos=vinculos,
            motivo_elegibilidade='possui vínculos operacionais',
            acao_proposta='preservar — análise manual',
        )

    return ResultadoCandidatoProdutoTeste(
        produto_id=produto.pk,
        codigo=codigo,
        descricao=descricao,
        criado_em=criado,
        elegivel=True,
        motivo_elegibilidade='código e descrição artificiais, sem vínculos',
        acao_proposta='remover somente com confirmação explícita',
    )


def listar_vinculos_familia_teste(familia: FamiliaProduto) -> list[str]:
    vinculos: list[str] = []
    if familia.produtos.exists():
        vinculos.append('produtos_vinculados')
    if familia.polegadas_permitidas.exists():
        vinculos.append('polegadas_permitidas')
    if familia.roscas_permitidas.exists():
        vinculos.append('roscas_permitidas')
    if familia.schedules_permitidos.exists():
        vinculos.append('schedules_permitidos')
    return vinculos


def avaliar_familia_artificial(familia: FamiliaProduto) -> ResultadoCandidatoFamiliaTeste:
    codigo = _norm_codigo(familia.codigo_figura)
    descricao = _norm_descricao(familia.descricao_base)

    if not codigo_na_lista_artificial(codigo):
        return ResultadoCandidatoFamiliaTeste(
            familia_id=familia.pk,
            codigo=codigo,
            descricao=descricao,
            elegivel=False,
            motivo_elegibilidade='código fora da lista autorizada',
            acao_proposta='preservar',
        )

    if not descricao_artificial(descricao):
        return ResultadoCandidatoFamiliaTeste(
            familia_id=familia.pk,
            codigo=codigo,
            descricao=descricao,
            elegivel=False,
            motivo_elegibilidade='descrição base diferente de "Fam"',
            acao_proposta='preservar',
        )

    vinculos = listar_vinculos_familia_teste(familia)
    if vinculos:
        return ResultadoCandidatoFamiliaTeste(
            familia_id=familia.pk,
            codigo=codigo,
            descricao=descricao,
            elegivel=False,
            vinculos=vinculos,
            motivo_elegibilidade='possui vínculos ou template',
            acao_proposta='preservar — análise manual',
        )

    return ResultadoCandidatoFamiliaTeste(
        familia_id=familia.pk,
        codigo=codigo,
        descricao=descricao,
        elegivel=True,
        motivo_elegibilidade='família de teste órfã (lista fechada + descricao Fam)',
        acao_proposta='remover somente com confirmação explícita',
    )


def executar_dry_run_produtos_teste() -> dict[str, Any]:
    produtos = Produto.objects.filter(codigo_completo__in=CODIGOS_ARTIFICIAIS).order_by('codigo_completo', 'id')
    avaliados_prod = [avaliar_produto_artificial(p) for p in produtos]

    familias = FamiliaProduto.objects.filter(codigo_figura__in=CODIGOS_ARTIFICIAIS).order_by('codigo_figura', 'id')
    avaliados_fam = [avaliar_familia_artificial(f) for f in familias]

    codigos_prod = {_norm_codigo(a.codigo) for a in avaliados_prod}
    codigos_fam = {_norm_codigo(a.codigo) for a in avaliados_fam}
    codigos_encontrados = codigos_prod | codigos_fam
    codigos_ausentes = sorted(CODIGOS_ARTIFICIAIS - codigos_encontrados)

    candidatos = [a.to_dict() for a in avaliados_prod if a.elegivel] + [a.to_dict() for a in avaliados_fam if a.elegivel]
    protegidos = [a.to_dict() for a in avaliados_prod if not a.elegivel and a.produto_id] + [
        a.to_dict() for a in avaliados_fam if not a.elegivel and a.familia_id
    ]

    return {
        'modo': 'dry_run',
        'executado_em': timezone.now().isoformat(),
        'total_lista': len(CODIGOS_ARTIFICIAIS),
        'total_encontrados': len(avaliados_prod) + len(avaliados_fam),
        'candidatos_elegiveis': candidatos,
        'protegidos': protegidos,
        'codigos_ausentes': codigos_ausentes,
        'avaliados_produtos': [a.to_dict() for a in avaliados_prod],
        'avaliados_familias': [a.to_dict() for a in avaliados_fam],
    }


def imprimir_relatorio_dry_run(relatorio: dict[str, Any], writer) -> None:
    writer('[DRY-RUN] Limpeza produtos artificiais ERP 4.0.13.7.2')
    writer(f"  Lista autorizada: {relatorio.get('total_lista', 0)} código(s)")
    writer(f"  Encontrados no banco: {relatorio.get('total_encontrados', 0)}")
    writer('')

    for item in relatorio.get('candidatos_elegiveis', []):
        tipo = item.get('tipo', 'produto')
        if tipo == 'familia':
            writer(
                f"CANDIDATO (família órfã de teste):\n"
                f"{item['codigo']} — {item['descricao']} — familia_id={item['familia_id']} — "
                f"sem produtos nem templates — será removido somente com confirmação.",
            )
        else:
            writer(
                f"CANDIDATO (produto):\n"
                f"{item['codigo']} — {item['descricao']} — id={item['produto_id']} — "
                f"sem vínculos operacionais — será removido somente com confirmação.",
            )
        if item.get('criado_em'):
            writer(f"  criado_em: {item['criado_em']}")

    for item in relatorio.get('protegidos', []):
        vinc = ', '.join(item.get('vinculos') or []) or item.get('motivo_elegibilidade', 'protegido')
        ref_id = item.get('familia_id') or item.get('produto_id')
        tipo = item.get('tipo', 'produto')
        writer(
            f"NÃO REMOVER ({tipo}):\n"
            f"{item['codigo']} — {item['descricao']} — id={ref_id} — {vinc}.",
        )

    ausentes = relatorio.get('codigos_ausentes') or []
    if ausentes:
        writer('')
        writer('[DRY-RUN] Códigos da lista não encontrados no banco:')
        for cod in ausentes:
            writer(f'  - {cod} (nada a fazer)')


@transaction.atomic
def executar_limpeza_confirmada(relatorio: dict[str, Any]) -> dict[str, Any]:
    verificar_ambiente_seguro()

    removidos: list[dict[str, Any]] = []
    protegidos: list[dict[str, Any]] = []

    for item in relatorio.get('candidatos_elegiveis', []):
        tipo = item.get('tipo', 'produto')
        if tipo == 'familia':
            familia_id = item['familia_id']
            familia = FamiliaProduto.objects.filter(pk=familia_id).first()
            if not familia:
                continue
            reav = avaliar_familia_artificial(familia)
            if not reav.elegivel:
                protegidos.append(reav.to_dict())
                continue
            snapshot = reav.to_dict()
            familia.delete()
            removidos.append(snapshot)
            logger.info(
                'Família de teste removida: id=%s codigo=%s descricao=%s',
                snapshot['familia_id'],
                snapshot['codigo'],
                snapshot['descricao'],
            )
            continue

        produto_id = item['produto_id']
        produto = Produto.objects.filter(pk=produto_id).first()
        if not produto:
            continue
        reav = avaliar_produto_artificial(produto)
        if not reav.elegivel:
            protegidos.append(reav.to_dict())
            continue
        snapshot = reav.to_dict()
        produto.delete()
        removidos.append(snapshot)
        logger.info(
            'Produto artificial removido: id=%s codigo=%s descricao=%s',
            snapshot['produto_id'],
            snapshot['codigo'],
            snapshot['descricao'],
        )

    return {
        'modo': 'confirmado',
        'executado_em': timezone.now().isoformat(),
        'removidos': removidos,
        'protegidos_na_execucao': protegidos,
        'total_removidos': len(removidos),
        'total_produtos_removidos': sum(1 for r in removidos if r.get('tipo') == 'produto'),
        'total_familias_removidas': sum(1 for r in removidos if r.get('tipo') == 'familia'),
    }
