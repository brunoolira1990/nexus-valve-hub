"""Rastreabilidade técnica para emissão definitiva do Certificado de Qualidade (Fase 3.12)."""

from __future__ import annotations

from typing import Any, Mapping

from apps.fiscal.models import ItemNFeEntradaConferencia
from apps.qualidade.models import (
    CertificadoFornecedorEntrada,
    ItemCertificadoFornecedorEntrada,
    ItemCertificadoQualidade,
    ItemCertificadoQualidadeComponente,
)

RastreabilidadeStatus = str  # 'COMPLETA' | 'PARCIAL' | 'PENDENTE'

LABEL_POR_STATUS = {
    'COMPLETA': 'Rastreabilidade completa',
    'PARCIAL': 'Rastreabilidade parcial',
    'PENDENTE': 'Rastreabilidade pendente',
}


def _strip(value: Any) -> str:
    return str(value or '').strip()


def _get_attr(item: ItemCertificadoQualidade | Mapping[str, Any], name: str, default=None):
    if isinstance(item, Mapping):
        return item.get(name, default)
    return getattr(item, name, default)


def _json_has_values(data: dict | None) -> bool:
    if not isinstance(data, dict):
        return False
    return any(_strip(v) for v in data.values())


def _tem_corrida_lote(item: ItemCertificadoQualidade | Mapping[str, Any]) -> bool:
    corrida = _strip(_get_attr(item, 'corrida')) or _strip(_get_attr(item, 'corrida_snapshot'))
    lote = _strip(_get_attr(item, 'lote')) or _strip(_get_attr(item, 'lote_snapshot'))
    return bool(corrida or lote)


def _tem_produto(item: ItemCertificadoQualidade | Mapping[str, Any]) -> bool:
    produto = _get_attr(item, 'produto')
    if produto:
        return True
    return bool(_get_attr(item, 'produto_id'))


def _componentes_ativos(
    item: ItemCertificadoQualidade | Mapping[str, Any],
    componentes: list | None = None,
) -> list:
    if componentes is not None:
        return [c for c in componentes if _get_attr(c, 'ativo', True) is not False]
    if isinstance(item, ItemCertificadoQualidade):
        return list(item.componentes.filter(ativo=True))
    comps = _get_attr(item, 'componentes') or []
    return [c for c in comps if _get_attr(c, 'ativo', True) is not False]


def _tem_dados_tecnicos_minimos(
    item: ItemCertificadoQualidade | Mapping[str, Any],
    *,
    componentes: list | None = None,
) -> bool:
    tipo = _get_attr(item, 'tipo_dados_tecnicos') or ItemCertificadoQualidade.TipoDadosTecnicos.PADRAO_ITEM
    if tipo == ItemCertificadoQualidade.TipoDadosTecnicos.VALVULA_COMPONENTES:
        comps = _componentes_ativos(item, componentes)
        if not comps:
            return False
        for comp in comps:
            nome = _strip(_get_attr(comp, 'nome_componente'))
            if not nome:
                continue
            norma = _strip(_get_attr(comp, 'norma'))
            composicao = _get_attr(comp, 'composicao_json')
            tracao = _get_attr(comp, 'ensaio_tracao_json')
            impacto = _get_attr(comp, 'ensaio_impacto_json')
            if norma or _json_has_values(composicao) or _json_has_values(tracao) or _json_has_values(impacto):
                return True
        return False

    norma = _strip(_get_attr(item, 'norma'))
    composicao = _get_attr(item, 'composicao_json')
    tracao = _get_attr(item, 'ensaio_tracao_json')
    impacto = _get_attr(item, 'ensaio_impacto_json')
    return bool(
        norma
        or _json_has_values(composicao)
        or _json_has_values(tracao)
        or _json_has_values(impacto)
    )


def _carregar_item_cf(
    item: ItemCertificadoQualidade | Mapping[str, Any],
    item_cf: ItemCertificadoFornecedorEntrada | None,
) -> ItemCertificadoFornecedorEntrada | None:
    if item_cf is not None:
        return item_cf
    item_cf_id = _get_attr(item, 'item_certificado_fornecedor_origem_id')
    if not item_cf_id:
        return None
    return (
        ItemCertificadoFornecedorEntrada.objects.select_related(
            'certificado_fornecedor',
            'item_conferencia__conferencia',
        )
        .filter(pk=item_cf_id)
        .first()
    )


def _carregar_cert_cf(
    item: ItemCertificadoQualidade | Mapping[str, Any],
    *,
    item_cf: ItemCertificadoFornecedorEntrada | None,
    cert_cf: CertificadoFornecedorEntrada | None,
) -> CertificadoFornecedorEntrada | None:
    if cert_cf is not None:
        return cert_cf
    if item_cf is not None:
        return item_cf.certificado_fornecedor
    cert_id = _get_attr(item, 'certificado_fornecedor_origem_id')
    if cert_id:
        return CertificadoFornecedorEntrada.objects.filter(pk=cert_id).first()
    return None


def _status_cf_normalizado(cert_cf: CertificadoFornecedorEntrada | None) -> str:
    if not cert_cf:
        return ''
    return str(cert_cf.status or '').strip().lower()


def _estoque_aplicado_origem(item_conf: ItemNFeEntradaConferencia | None) -> bool:
    if not item_conf:
        return False
    if item_conf.estoque_aplicado_em:
        return True
    conf = item_conf.conferencia
    return bool(conf and conf.estoque_aplicado_em)


def _item_label(item: ItemCertificadoQualidade | Mapping[str, Any], ordem: int) -> str:
    codigo = _strip(_get_attr(item, 'codigo_produto'))
    descricao = _strip(_get_attr(item, 'descricao_material'))
    if codigo and descricao:
        return f'Item {ordem} — {codigo} {descricao}'
    if descricao:
        return f'Item {ordem} — {descricao}'
    if codigo:
        return f'Item {ordem} — {codigo}'
    return f'Item {ordem}'


def avaliar_rastreabilidade_item_certificado_qualidade(
    item: ItemCertificadoQualidade | Mapping[str, Any],
    *,
    item_cf: ItemCertificadoFornecedorEntrada | None = None,
    cert_cf: CertificadoFornecedorEntrada | None = None,
    componentes: list | None = None,
) -> dict[str, Any]:
    """Avalia rastreabilidade de um item do CQ (modelo ou dict do payload)."""
    mensagens: list[str] = []
    motivos: list[str] = []
    pendente = False
    parcial = False

    tem_produto = _tem_produto(item)
    tem_corrida_lote = _tem_corrida_lote(item)
    tem_dados_tecnicos = _tem_dados_tecnicos_minimos(item, componentes=componentes)

    item_cf = _carregar_item_cf(item, item_cf)
    cert_cf = _carregar_cert_cf(item, item_cf=item_cf, cert_cf=cert_cf)

    tem_certificado_fornecedor = bool(item_cf or cert_cf or _get_attr(item, 'certificado_fornecedor_origem_id'))
    certificado_fornecedor_status = _status_cf_normalizado(cert_cf) if cert_cf else ''
    certificado_fornecedor_registrado = certificado_fornecedor_status == CertificadoFornecedorEntrada.Status.REGISTRADO

    item_conf = item_cf.item_conferencia if item_cf and item_cf.item_conferencia_id else None
    tem_conferencia_origem = bool(item_conf)
    estoque_aplicado = _estoque_aplicado_origem(item_conf)

    if not tem_produto:
        pendente = True
        mensagens.append('Produto não vinculado.')
        motivos.append('SEM_PRODUTO')

    if not tem_corrida_lote:
        pendente = True
        mensagens.append('Sem corrida/lote.')
        motivos.append('SEM_CORRIDA_LOTE')

    if not tem_dados_tecnicos:
        pendente = True
        mensagens.append('Dados técnicos mínimos não preenchidos.')
        motivos.append('SEM_DADOS_TECNICOS')

    if not tem_certificado_fornecedor:
        pendente = True
        mensagens.append('Sem certificado fornecedor registrado.')
        motivos.append('SEM_CERTIFICADO_FORNECEDOR')
    elif cert_cf:
        if certificado_fornecedor_status == CertificadoFornecedorEntrada.Status.CANCELADO:
            pendente = True
            mensagens.append('Certificado fornecedor cancelado.')
            motivos.append('CF_CANCELADO')
        elif certificado_fornecedor_status == CertificadoFornecedorEntrada.Status.RASCUNHO:
            parcial = True
            mensagens.append('Certificado fornecedor ainda em rascunho.')
            motivos.append('CF_RASCUNHO')
        elif not certificado_fornecedor_registrado:
            pendente = True
            mensagens.append('Certificado fornecedor não registrado.')
            motivos.append('CF_NAO_REGISTRADO')

    if item_cf is not None and not item_cf.ativo:
        pendente = True
        mensagens.append('Item do certificado fornecedor inativo.')
        motivos.append('ITEM_CF_INATIVO')

    if tem_certificado_fornecedor and cert_cf and not item_cf:
        parcial = True
        mensagens.append('Vínculo com item do certificado fornecedor não informado.')
        motivos.append('SEM_ITEM_CF')

    if item_cf is not None and not item_conf:
        parcial = True
        mensagens.append('Origem da conferência não vinculada.')
        motivos.append('SEM_CONFERENCIA_ORIGEM')

    if item_conf is not None and not estoque_aplicado:
        parcial = True
        mensagens.append('Estoque físico ainda não aplicado.')
        motivos.append('ESTOQUE_NAO_APLICADO')

    if pendente:
        status: RastreabilidadeStatus = 'PENDENTE'
    elif parcial:
        status = 'PARCIAL'
    else:
        status = 'COMPLETA'

    return {
        'status': status,
        'label': LABEL_POR_STATUS[status],
        'mensagens': list(dict.fromkeys(mensagens)),
        'motivos': list(dict.fromkeys(motivos)),
        'tem_produto': tem_produto,
        'tem_corrida_lote': tem_corrida_lote,
        'tem_certificado_fornecedor': tem_certificado_fornecedor,
        'certificado_fornecedor_registrado': certificado_fornecedor_registrado,
        'certificado_fornecedor_status': certificado_fornecedor_status or None,
        'tem_conferencia_origem': tem_conferencia_origem,
        'estoque_aplicado_origem': estoque_aplicado,
        'tem_dados_tecnicos': tem_dados_tecnicos,
    }


def montar_resumo_rastreabilidade_certificado(
    itens: list[ItemCertificadoQualidade | Mapping[str, Any]],
) -> dict[str, Any]:
    incluidos = [
        it
        for it in itens
        if bool(_get_attr(it, 'incluir_no_certificado', True))
    ]
    completos = parciais = pendentes = 0
    for it in incluidos:
        st = avaliar_rastreabilidade_item_certificado_qualidade(it)['status']
        if st == 'COMPLETA':
            completos += 1
        elif st == 'PARCIAL':
            parciais += 1
        else:
            pendentes += 1
    return {
        'completos': completos,
        'parciais': parciais,
        'pendentes': pendentes,
        'pode_emitir': bool(incluidos) and parciais == 0 and pendentes == 0,
    }


def validar_rastreabilidade_emissao_certificado_qualidade(
    itens: list[ItemCertificadoQualidade | Mapping[str, Any]],
) -> list[str]:
    """Retorna mensagens de erro por item para emissão definitiva (status emitido)."""
    erros: list[str] = []
    ordem = 0
    for it in itens:
        if not bool(_get_attr(it, 'incluir_no_certificado', True)):
            continue
        ordem += 1
        av = avaliar_rastreabilidade_item_certificado_qualidade(it)
        if av['status'] == 'COMPLETA':
            continue
        label = _item_label(it, ordem)
        for msg in av['mensagens']:
            erros.append(f'{label}: {msg}')
    return erros
