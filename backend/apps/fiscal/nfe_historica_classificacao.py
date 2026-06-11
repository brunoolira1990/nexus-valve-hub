from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.db import transaction

from apps.cadastros.models import Cliente, Empresa, Fornecedor

from .models import (
    ItemNFeEntradaHistoricaImportada,
    ItemNFeSaidaHistoricaImportada,
    NFeEntradaHistoricaImportada,
    NFeSaidaHistoricaImportada,
)


def norm_digits(value: str | None) -> str:
    return ''.join(c for c in str(value or '') if c.isdigit())


def documento_party(party: dict[str, Any] | None) -> str:
    if not isinstance(party, dict):
        return ''
    return norm_digits(str(party.get('CNPJ') or party.get('CPF') or ''))


def resolve_empresa_from_party(party: dict[str, Any] | None) -> Empresa | None:
    doc = documento_party(party)
    if len(doc) != 14:
        return None
    for emp in Empresa.objects.only('id', 'cnpj'):
        if norm_digits(emp.cnpj) == doc:
            return emp
    return None


ACAO_IMPORTAR_ENTRADA_PROPRIA_EMITIDA = (
    'Em NF-e Entrada, use a ação «Importar entrada própria já emitida».'
)

MSG_ENTRADA_PROPRIA_JA_EMITIDA = (
    'NF-e de entrada própria já emitida pela Empresa (ex.: devolução ou recusa de cliente). '
    'Não use a base histórica de saída nem a de entrada de fornecedor.'
)


def resolve_cliente_from_party(party: dict[str, Any] | None) -> Cliente | None:
    doc = documento_party(party)
    if len(doc) != 14:
        return None
    for cli in Cliente.objects.only('id', 'cnpj'):
        if norm_digits(cli.cnpj) == doc:
            return cli
    return None


def resolve_fornecedor_from_party(party: dict[str, Any] | None) -> Fornecedor | None:
    doc = documento_party(party)
    if len(doc) != 14:
        return None
    for forn in Fornecedor.objects.only('id', 'cnpj'):
        if norm_digits(forn.cnpj) == doc:
            return forn
    return None


@dataclass
class ClassificacaoNFe:
    empresa_emitente: Empresa | None
    empresa_destinataria: Empresa | None
    tipo_fluxo: str


def eh_entrada_propria_ja_emitida(
    emit_json: dict[str, Any],
    dest_json: dict[str, Any],
    *,
    tp_nf: str | None,
) -> tuple[bool, Empresa | None]:
    """Emitente = Empresa cadastrada e tpNF=0 (entrada própria já emitida, não venda histórica)."""
    empresa_emitente = resolve_empresa_from_party(emit_json)
    if not empresa_emitente:
        return False, None
    if str(tp_nf or '').strip() != '0':
        return False, empresa_emitente
    return True, empresa_emitente


def classificar_por_empresa(emit_json: dict[str, Any], dest_json: dict[str, Any]) -> ClassificacaoNFe:
    empresa_emitente = resolve_empresa_from_party(emit_json)
    empresa_destinataria = resolve_empresa_from_party(dest_json)
    if empresa_emitente:
        return ClassificacaoNFe(
            empresa_emitente=empresa_emitente,
            empresa_destinataria=empresa_destinataria,
            tipo_fluxo='saida',
        )
    if empresa_destinataria:
        return ClassificacaoNFe(
            empresa_emitente=empresa_emitente,
            empresa_destinataria=empresa_destinataria,
            tipo_fluxo='entrada',
        )
    return ClassificacaoNFe(empresa_emitente=None, empresa_destinataria=None, tipo_fluxo='indefinido')


def saida_esta_classificada_como_entrada(nf_saida: NFeSaidaHistoricaImportada) -> tuple[bool, Empresa | None]:
    empresa_dest = resolve_empresa_from_party(nf_saida.dest_json)
    empresa_emit = resolve_empresa_from_party(nf_saida.emit_json)
    return bool(empresa_dest and not empresa_emit), empresa_dest


@transaction.atomic
def reclassificar_saida_para_entrada(nf_saida: NFeSaidaHistoricaImportada) -> str:
    is_entrada, empresa_dest = saida_esta_classificada_como_entrada(nf_saida)
    if not is_entrada or not empresa_dest:
        return 'nao_reclassificada'

    existente = NFeEntradaHistoricaImportada.objects.filter(chave_acesso=nf_saida.chave_acesso).first()
    if existente:
        nf_saida.delete()
        return 'removida_saida_duplicada_entrada'

    fornecedor = resolve_fornecedor_from_party(nf_saida.emit_json)
    nf_entrada = NFeEntradaHistoricaImportada.objects.create(
        chave_acesso=nf_saida.chave_acesso,
        numero=nf_saida.numero,
        serie=nf_saida.serie,
        modelo=nf_saida.modelo,
        dh_emissao=nf_saida.dh_emissao,
        tp_amb=nf_saida.tp_amb,
        tp_nf=nf_saida.tp_nf,
        nat_op=nf_saida.nat_op,
        versao_layout=nf_saida.versao_layout,
        cstat=nf_saida.cstat,
        xmotivo=nf_saida.xmotivo,
        protocolo=nf_saida.protocolo,
        valor_produtos=nf_saida.valor_produtos,
        valor_total_nf=nf_saida.valor_total_nf,
        v_frete=nf_saida.v_frete,
        v_seg=nf_saida.v_seg,
        v_desc=nf_saida.v_desc,
        v_outro=nf_saida.v_outro,
        emit_json=nf_saida.emit_json,
        dest_json=nf_saida.dest_json,
        totais_json=nf_saida.totais_json,
        reforma_e_outros_json=nf_saida.reforma_e_outros_json,
        prot_json=nf_saida.prot_json,
        empresa_destinataria=empresa_dest,
        fornecedor_emitente=fornecedor,
        papel_empresa_no_documento='destinatario',
        importada=nf_saida.importada,
        origem_externa=nf_saida.origem_externa,
        historica=nf_saida.historica,
        nome_arquivo=nf_saida.nome_arquivo,
    )
    itens_saida = ItemNFeSaidaHistoricaImportada.objects.filter(nf=nf_saida).order_by('n_item')
    ItemNFeEntradaHistoricaImportada.objects.bulk_create(
        [
            ItemNFeEntradaHistoricaImportada(
                nf=nf_entrada,
                n_item=item.n_item,
                prod_json=item.prod_json,
                imposto_json=item.imposto_json,
            )
            for item in itens_saida
        ]
    )
    nf_saida.delete()
    return 'reclassificada'
