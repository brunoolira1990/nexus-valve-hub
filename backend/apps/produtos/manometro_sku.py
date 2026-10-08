from __future__ import annotations

import re

from django.db import IntegrityError, transaction

from apps.produtos.codigo_produto import codigo_interno_valido, montar_codigo_interno


SUFIXO_SKU_RE = re.compile(r'^(?P<base>.+)\.(?P<numero>\d+)$')
MENSAGEM_ALTERACAO_ESTRUTURAL = (
    'Família, rosca ou polegada alteram a identidade estrutural deste SKU. '
    'Cadastre um novo Produto para essa nova configuração.'
)


def familia_e_manometro(familia) -> bool:
    from apps.produtos.models import FamiliaProduto

    return bool(
        familia
        and familia.tipo_dimensional == FamiliaProduto.TipoDimensional.MANOMETRO
    )


def produto_e_manometro_interno(produto) -> bool:
    from apps.produtos.models import Produto

    return bool(
        produto
        and produto.modo_codigo == Produto.ModoCodigo.INTERNO
        and familia_e_manometro(getattr(produto, 'familia', None))
    )


def montar_codigo_base_manometro(produto) -> str:
    if not produto_e_manometro_interno(produto):
        return ''
    codigo = montar_codigo_interno(
        produto.familia,
        rosca=produto.rosca_conexao,
        schedule=produto.schedule_ref,
        polegada_principal=produto.polegada_principal_ref,
        polegada_secundaria=produto.polegada_secundaria_ref,
        od_mm=produto.od_mm,
        espessura_mm=produto.espessura_mm,
        dimensoes=produto.dimensoes_json or {},
    )
    return codigo if codigo_interno_valido(codigo) else ''


def _codigos_do_grupo(codigo_base: str, *, excluir_pk: int | None = None) -> list[str]:
    from apps.produtos.models import Produto

    prefixo = f'{codigo_base}.'
    qs = Produto.objects.filter(codigo_completo__startswith=prefixo)
    if excluir_pk:
        qs = qs.exclude(pk=excluir_pk)
    return list(qs.values_list('codigo_completo', flat=True))


def maior_sufixo_existente(codigo_base: str, *, excluir_pk: int | None = None) -> int:
    maior = 0
    prefixo = f'{codigo_base}.'
    for codigo in _codigos_do_grupo(codigo_base, excluir_pk=excluir_pk):
        codigo = (codigo or '').strip()
        if not codigo.startswith(prefixo):
            continue
        sufixo = codigo[len(prefixo):]
        if sufixo.isdigit():
            maior = max(maior, int(sufixo))
    return maior


def proximo_codigo_manometro_sugerido(codigo_base: str, *, excluir_pk: int | None = None) -> str:
    """Calcula somente uma sugestão; não cria linha nem consome contador."""
    from apps.produtos.models import Produto, ProdutoManometroSkuSequencia

    if not codigo_base:
        return ''
    base_ocupada = Produto.objects.filter(codigo_completo=codigo_base).exclude(pk=excluir_pk).exists()
    if not base_ocupada:
        return codigo_base
    seq = ProdutoManometroSkuSequencia.objects.filter(codigo_base=codigo_base).first()
    proximo = max(
        int(seq.proximo_numero) if seq else 1,
        maior_sufixo_existente(codigo_base, excluir_pk=excluir_pk) + 1,
    )
    while Produto.objects.filter(codigo_completo=f'{codigo_base}.{proximo:02d}').exclude(pk=excluir_pk).exists():
        proximo += 1
    return f'{codigo_base}.{proximo:02d}'


def _obter_ou_criar_linha_locked(codigo_base: str, produto) -> object:
    from apps.produtos.models import ProdutoManometroSkuSequencia

    inicial = max(1, maior_sufixo_existente(codigo_base) + 1)
    try:
        with transaction.atomic():
            ProdutoManometroSkuSequencia.objects.get_or_create(
                codigo_base=codigo_base,
                defaults={
                    'familia': produto.familia,
                    'rosca_conexao': produto.rosca_conexao,
                    'polegada_principal': produto.polegada_principal_ref,
                    'proximo_numero': inicial,
                },
            )
    except IntegrityError:
        # A constraint única de codigo_base resolve a corrida de criação; a
        # transação externa relê a linha e adquire o lock abaixo.
        pass
    seq = ProdutoManometroSkuSequencia.objects.select_for_update().get(codigo_base=codigo_base)
    observado = maior_sufixo_existente(codigo_base, excluir_pk=produto.pk)
    if seq.proximo_numero <= observado:
        seq.proximo_numero = observado + 1
        seq.save(update_fields=['proximo_numero'])
    return seq


@transaction.atomic
def reservar_codigo_manometro(produto) -> str:
    """Reserva base ou próximo SKU técnico dentro de uma transação."""
    from apps.produtos.models import Produto

    if not produto_e_manometro_interno(produto):
        return ''
    codigo_base = montar_codigo_base_manometro(produto)
    if not codigo_base:
        return ''
    seq = _obter_ou_criar_linha_locked(codigo_base, produto)
    qs = Produto.objects.filter(codigo_completo=codigo_base)
    if produto.pk:
        qs = qs.exclude(pk=produto.pk)
    if not qs.exists():
        return codigo_base

    numero = max(1, int(seq.proximo_numero))
    while True:
        candidato = f'{codigo_base}.{numero:02d}'
        ocupado = Produto.objects.filter(codigo_completo=candidato)
        if produto.pk:
            ocupado = ocupado.exclude(pk=produto.pk)
        if not ocupado.exists():
            seq.proximo_numero = numero + 1
            seq.save(update_fields=['proximo_numero'])
            return candidato
        numero += 1


def validar_alteracao_estrutural_manometro(produto, *, familia, rosca, polegada_principal) -> None:
    if not produto or not produto.pk or not familia_e_manometro(getattr(produto, 'familia', None)):
        return
    if (
        familia is not None and familia.pk != produto.familia_id
        or rosca is not None and getattr(rosca, 'pk', None) != produto.rosca_conexao_id
        or polegada_principal is not None
        and getattr(polegada_principal, 'pk', None) != produto.polegada_principal_ref_id
    ):
        raise ValueError(MENSAGEM_ALTERACAO_ESTRUTURAL)
