"""Corridas do Certificado de Fornecedor EXATO para o editor do CQ (hotfix múltiplas corridas).

Fluxo: o item do CQ já possui vínculo real com um CF e um item do CF
(`certificado_fornecedor_origem_id` / `item_certificado_fornecedor_origem_id`).
Este serviço lista somente as corridas desse vínculo exato para o operador
distribuir quantidades e criar itens irmãos no CQ:

- corrida principal do item do CF (dados técnicos herdados desse item);
- corridas adicionais do mesmo item (dados técnicos herdados do principal — A1);

Itens independentes não são inferidos por produto, descrição ou ordem. O modelo
atual não possui agrupamento documental inequívoco entre itens do CF; essa
ampliação pertence à A2.
"""

from __future__ import annotations

from decimal import Decimal

from apps.qualidade.models import ItemCertificadoFornecedorEntrada

MSG_ORIGEM_DOCUMENTAL_NAO_FISICA_CQ = (
    'A origem documental foi identificada. A origem física no estoque/alocação '
    'não é comprovada nesta etapa.'
)
MSG_ADICIONAL_SEM_QUANTIDADE_CF = (
    'Há corrida adicional sem quantidade registrada no Certificado de Fornecedor '
    '(registro histórico). Informe a quantidade manualmente ao distribuir.'
)
MSG_ITEM_CF_SEM_CORRIDAS_ELEGIVEIS = (
    'Nenhuma corrida elegível encontrada para o item vinculado do Certificado de Fornecedor.'
)
MSG_ITEM_CF_VINCULO_INVALIDO = (
    'O item do Certificado de Fornecedor vinculado a este CQ não foi encontrado '
    'ou está inativo (pode ocorrer após regravação do CF). Reaplique os dados do '
    'fornecedor neste item do CQ antes de distribuir corridas.'
)

ORIGEM_TECNICA_ITEM_CF = 'dados_do_item_cf'
ORIGEM_TECNICA_HERDADA = 'herdados_item_principal'

LABEL_ORIGEM_TECNICA = {
    ORIGEM_TECNICA_ITEM_CF: 'Dados técnicos herdados do item principal do CF',
    ORIGEM_TECNICA_HERDADA: 'Dados técnicos herdados do item principal do CF',
}

LIMITACAO_ITENS_INDEPENDENTES_A2 = (
    'Itens independentes do CF não são listados automaticamente: o modelo atual '
    'não comprova um agrupamento documental inequívoco entre eles. Escopo da A2.'
)


class ItemCfNaoEncontradoError(LookupError):
    """Certificado inexistente, ou item existente pertencente a outro certificado."""

def _fmt_decimal(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return f'{value:.3f}'


def _normalizar_origem(value: str | None) -> str:
    return ''.join(str(value or '').upper().split())


def _chave_origem_documental(item_id: int, corrida: str, lote: str) -> str:
    """Identidade estável da origem; não depende de índice ou ordem do array."""
    return (
        f'certificado_fornecedor:{item_id}:'
        f'{_normalizar_origem(corrida)}:{_normalizar_origem(lote)}'
    )


def _dados_tecnicos_item_cf(item: ItemCertificadoFornecedorEntrada) -> dict:
    return {
        'norma': item.norma or '',
        'ncm': item.ncm or '',
        'tipo_dados_tecnicos': item.tipo_dados_tecnicos,
        'composicao_json': item.composicao_json or {},
        'ensaio_tracao_json': item.ensaio_tracao_json or {},
        'ensaio_impacto_json': item.ensaio_impacto_json or {},
    }


def quantidade_principal_derivada_item_cf(
    item: ItemCertificadoFornecedorEntrada,
) -> tuple[Decimal | None, bool]:
    """Quantidade da corrida principal derivada (regra A1: total − soma das adicionais).

    Retorna (quantidade, determinavel). Indeterminável quando o total do item é
    inválido ou alguma corrida adicional histórica está sem quantidade.
    """
    total = item.quantidade
    if total is None or total <= 0:
        return None, False
    soma = Decimal('0')
    for ca in item.corridas_adicionais.all():
        if ca.quantidade is None:
            return None, False
        soma += ca.quantidade
    saldo = total - soma
    if saldo <= 0:
        return None, True
    return saldo, True


def _linha_base(
    item: ItemCertificadoFornecedorEntrada,
    *,
    tipo_linha: str,
    corrida: str,
    lote: str,
    quantidade_no_certificado: Decimal | None,
    origem_tecnica: str,
) -> dict:
    cert = item.certificado_fornecedor
    return {
        'chave_origem': _chave_origem_documental(item.id, corrida, lote),
        'tipo_linha': tipo_linha,
        'corrida': corrida,
        'lote': lote,
        'quantidade_no_certificado': _fmt_decimal(quantidade_no_certificado),
        'unidade': item.unidade or '',
        'origem_tecnica': origem_tecnica,
        'origem_tecnica_label': LABEL_ORIGEM_TECNICA[origem_tecnica],
        'dados_tecnicos_herdados': True,
        'permite_preenchimento_manual': True,
        'modo_dados_tecnicos_padrao': 'herdados',
        'modos_dados_tecnicos_permitidos': ['herdados', 'manual'],
        'certificado_fornecedor_id': cert.id,
        'item_certificado_fornecedor_id': item.id,
        'codigo_produto': item.codigo_produto or '',
        'descricao_material': item.descricao_material or '',
        'fornecedor_nome': cert.fornecedor_nome_snapshot or '',
        'numero_nf_entrada': cert.numero_nf_entrada or '',
        'numero_certificado_fornecedor': (
            item.numero_certificado_fornecedor_item or cert.numero_certificado_fornecedor or ''
        ),
        'status_certificado_fornecedor': str(cert.status or '').strip().lower(),
        'dados_tecnicos': _dados_tecnicos_item_cf(item),
    }


def _payload_colecao(
    *,
    linhas: list[dict] | None = None,
    avisos: list[str] | None = None,
) -> dict:
    return {
        'linhas': list(linhas or []),
        'avisos': list(dict.fromkeys(avisos or [])),
        'mensagem_origem_fisica': MSG_ORIGEM_DOCUMENTAL_NAO_FISICA_CQ,
        'limitacao_itens_independentes': LIMITACAO_ITENS_INDEPENDENTES_A2,
    }


def listar_corridas_cf_para_item_cq(
    *,
    certificado_fornecedor_id: int,
    item_certificado_fornecedor_id: int,
) -> dict:
    """Linhas de corrida do CF/item exatos, para seleção pelo operador no CQ.

    Contrato:
    - CF inexistente → ItemCfNaoEncontradoError (HTTP 404).
    - Item existente ligado a outro CF → ItemCfNaoEncontradoError (HTTP 404).
    - CF válido com item ausente/inativo ou sem corridas → coleção vazia (HTTP 200).
    - Permissão continua a cargo da view (401/403 não são mascarados aqui).
    """
    from apps.qualidade.models import CertificadoFornecedorEntrada

    item = (
        ItemCertificadoFornecedorEntrada.objects
        .select_related('certificado_fornecedor')
        .prefetch_related('corridas_adicionais')
        .filter(
            pk=item_certificado_fornecedor_id,
            certificado_fornecedor_id=certificado_fornecedor_id,
            ativo=True,
        )
        .first()
    )
    if item is None:
        if not CertificadoFornecedorEntrada.objects.filter(pk=certificado_fornecedor_id).exists():
            raise ItemCfNaoEncontradoError('Certificado de Fornecedor não encontrado.')
        item_qualquer = (
            ItemCertificadoFornecedorEntrada.objects
            .filter(pk=item_certificado_fornecedor_id)
            .only('id', 'certificado_fornecedor_id', 'ativo')
            .first()
        )
        if (
            item_qualquer is not None
            and item_qualquer.certificado_fornecedor_id != certificado_fornecedor_id
        ):
            raise ItemCfNaoEncontradoError(
                'Item do Certificado de Fornecedor não encontrado para este certificado.'
            )
        # CF válido: item órfão (ex.: regravação do CF), inativo ou inexistente → coleção vazia.
        return _payload_colecao(avisos=[MSG_ITEM_CF_VINCULO_INVALIDO])

    linhas: list[dict] = []
    avisos: list[str] = []

    corrida_principal = (item.corrida or '').strip()
    lote_principal = (item.lote or '').strip()
    if corrida_principal or lote_principal:
        qtd_principal, determinavel = quantidade_principal_derivada_item_cf(item)
        if not determinavel:
            avisos.append(MSG_ADICIONAL_SEM_QUANTIDADE_CF)
        linhas.append(
            _linha_base(
                item,
                tipo_linha='corrida_principal',
                corrida=corrida_principal,
                lote=lote_principal,
                quantidade_no_certificado=qtd_principal,
                origem_tecnica=ORIGEM_TECNICA_ITEM_CF,
            )
        )

    for ca in item.corridas_adicionais.all():
        corrida_extra = (ca.corrida or '').strip()
        lote_extra = (ca.lote or '').strip()
        if not corrida_extra and not lote_extra:
            continue
        if ca.quantidade is None:
            avisos.append(MSG_ADICIONAL_SEM_QUANTIDADE_CF)
        linhas.append(
            _linha_base(
                item,
                tipo_linha='corrida_adicional',
                corrida=corrida_extra,
                lote=lote_extra,
                quantidade_no_certificado=ca.quantidade,
                origem_tecnica=ORIGEM_TECNICA_HERDADA,
            )
        )

    if not linhas and MSG_ITEM_CF_SEM_CORRIDAS_ELEGIVEIS not in avisos:
        avisos.append(MSG_ITEM_CF_SEM_CORRIDAS_ELEGIVEIS)

    return _payload_colecao(linhas=linhas, avisos=avisos)
