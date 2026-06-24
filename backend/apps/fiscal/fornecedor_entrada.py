"""ERP 4.0.15.2.31 — Identificação e vínculo de fornecedor em documentos de entrada."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from django.db import transaction

from apps.cadastros.models import Fornecedor
from apps.fiscal.models import CTeHistoricoImportado, NFeEntradaHistoricaImportada
from apps.fiscal.nfe_historica_classificacao import documento_party, norm_digits

MSG_FORNECEDOR_DUPLICIDADE = (
    'Existem vários fornecedores cadastrados com o mesmo CNPJ. '
    'Escolha o cadastro correto ou corrija a duplicidade antes de vincular.'
)
MSG_FORNECEDOR_NAO_ENCONTRADO = 'Fornecedor não identificado. Cadastre ou vincule manualmente.'
MSG_SEM_CNPJ_EMITENTE = 'CNPJ do emitente/remetente não encontrado no XML para identificar fornecedor.'
MSG_FORNECEDOR_CNPJ_DIVERGENTE = (
    'O fornecedor selecionado não possui o mesmo CNPJ do documento de entrada.'
)
MSG_CNPJ_JA_CADASTRADO = 'Já existe fornecedor cadastrado com este CNPJ.'


class StatusIdentificacaoFornecedor(str, Enum):
    VINCULADO = 'vinculado'
    ENCONTRADO_UNICO = 'encontrado_unico'
    NAO_ENCONTRADO = 'nao_encontrado'
    DUPLICIDADE = 'duplicidade'
    SEM_CNPJ = 'sem_cnpj'


@dataclass
class ResultadoIdentificacaoFornecedor:
    status: StatusIdentificacaoFornecedor
    fornecedor_id: int | None = None
    fornecedor_nome: str = ''
    fornecedor_cnpj: str = ''
    cnpj_documento: str = ''
    candidatos: list[dict[str, Any]] | None = None
    mensagem: str = ''
    vinculo_automatico: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            'status': self.status.value,
            'fornecedor_id': self.fornecedor_id,
            'fornecedor_nome': self.fornecedor_nome,
            'fornecedor_cnpj': self.fornecedor_cnpj,
            'cnpj_documento': self.cnpj_documento,
            'candidatos': self.candidatos or [],
            'mensagem': self.mensagem,
            'vinculo_automatico': self.vinculo_automatico,
            'identificado': self.status in {
                StatusIdentificacaoFornecedor.VINCULADO,
                StatusIdentificacaoFornecedor.ENCONTRADO_UNICO,
            },
            'pode_cadastrar': self.status == StatusIdentificacaoFornecedor.NAO_ENCONTRADO,
            'pode_vincular_manual': self.status in {
                StatusIdentificacaoFornecedor.NAO_ENCONTRADO,
                StatusIdentificacaoFornecedor.DUPLICIDADE,
            },
        }


def cnpj_participante_normalizado(party: dict[str, Any] | None) -> str:
    return documento_party(party)


def buscar_fornecedores_por_cnpj(
    cnpj: str | None,
    *,
    apenas_ativos: bool = False,
) -> list[Fornecedor]:
    doc = norm_digits(cnpj)
    if len(doc) != 14:
        return []
    qs = Fornecedor.objects.all()
    if apenas_ativos:
        qs = qs.filter(ativo=True)
    return [f for f in qs if norm_digits(f.cnpj) == doc]


def _candidatos_payload(fornecedores: list[Fornecedor]) -> list[dict[str, Any]]:
    return [
        {
            'id': f.id,
            'razao_social': f.razao_social,
            'cnpj': f.cnpj,
            'ativo': f.ativo,
        }
        for f in fornecedores
    ]


def identificar_fornecedor_por_party(
    party: dict[str, Any] | None,
    *,
    fornecedor_vinculado: Fornecedor | None = None,
) -> ResultadoIdentificacaoFornecedor:
    cnpj_doc = cnpj_participante_normalizado(party)
    if fornecedor_vinculado is not None:
        return ResultadoIdentificacaoFornecedor(
            status=StatusIdentificacaoFornecedor.VINCULADO,
            fornecedor_id=fornecedor_vinculado.id,
            fornecedor_nome=fornecedor_vinculado.razao_social,
            fornecedor_cnpj=fornecedor_vinculado.cnpj,
            cnpj_documento=cnpj_doc,
        )
    if len(cnpj_doc) != 14:
        return ResultadoIdentificacaoFornecedor(
            status=StatusIdentificacaoFornecedor.SEM_CNPJ,
            cnpj_documento=cnpj_doc,
            mensagem=MSG_SEM_CNPJ_EMITENTE,
        )

    ativos = buscar_fornecedores_por_cnpj(cnpj_doc, apenas_ativos=True)
    if len(ativos) == 1:
        forn = ativos[0]
        return ResultadoIdentificacaoFornecedor(
            status=StatusIdentificacaoFornecedor.ENCONTRADO_UNICO,
            fornecedor_id=forn.id,
            fornecedor_nome=forn.razao_social,
            fornecedor_cnpj=forn.cnpj,
            cnpj_documento=cnpj_doc,
        )
    if len(ativos) > 1:
        return ResultadoIdentificacaoFornecedor(
            status=StatusIdentificacaoFornecedor.DUPLICIDADE,
            cnpj_documento=cnpj_doc,
            candidatos=_candidatos_payload(ativos),
            mensagem=MSG_FORNECEDOR_DUPLICIDADE,
        )

    todos = buscar_fornecedores_por_cnpj(cnpj_doc, apenas_ativos=False)
    if len(todos) > 1:
        return ResultadoIdentificacaoFornecedor(
            status=StatusIdentificacaoFornecedor.DUPLICIDADE,
            cnpj_documento=cnpj_doc,
            candidatos=_candidatos_payload(todos),
            mensagem=MSG_FORNECEDOR_DUPLICIDADE,
        )
    if len(todos) == 1:
        forn = todos[0]
        return ResultadoIdentificacaoFornecedor(
            status=StatusIdentificacaoFornecedor.ENCONTRADO_UNICO,
            fornecedor_id=forn.id,
            fornecedor_nome=forn.razao_social,
            fornecedor_cnpj=forn.cnpj,
            cnpj_documento=cnpj_doc,
            mensagem='Fornecedor inativo encontrado. Vincule manualmente ou reative o cadastro.',
        )

    return ResultadoIdentificacaoFornecedor(
        status=StatusIdentificacaoFornecedor.NAO_ENCONTRADO,
        cnpj_documento=cnpj_doc,
        mensagem=MSG_FORNECEDOR_NAO_ENCONTRADO,
    )


def _ender_party(party: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(party, dict):
        return {}
    for key in ('enderEmit', 'enderReme', 'enderDest', 'enderReceb', 'enderExped'):
        ender = party.get(key)
        if isinstance(ender, dict) and ender:
            return ender
    return {}


def extrair_dados_cadastro_fornecedor_party(party: dict[str, Any] | None) -> dict[str, Any]:
    party = party if isinstance(party, dict) else {}
    ender = _ender_party(party)
    cnpj = cnpj_participante_normalizado(party)
    return {
        'razao_social': (party.get('xNome') or party.get('xFant') or '').strip(),
        'nome_fantasia': (party.get('xFant') or '').strip(),
        'cnpj': cnpj,
        'ie': (party.get('IE') or '').strip(),
        'logradouro': (ender.get('xLgr') or '').strip(),
        'numero': (ender.get('nro') or '').strip(),
        'complemento': (ender.get('xCpl') or '').strip(),
        'bairro': (ender.get('xBairro') or '').strip(),
        'cidade': (ender.get('xMun') or '').strip(),
        'uf': (ender.get('UF') or '').strip()[:2],
        'cep': norm_digits(ender.get('CEP')),
        'ativo': True,
    }


def _validar_fornecedor_para_documento(
    fornecedor: Fornecedor,
    cnpj_documento: str,
) -> None:
    if len(cnpj_documento) == 14 and norm_digits(fornecedor.cnpj) != cnpj_documento:
        raise ValueError(MSG_FORNECEDOR_CNPJ_DIVERGENTE)


@transaction.atomic
def tentar_vincular_fornecedor_nfe_entrada(
    nf: NFeEntradaHistoricaImportada,
    *,
    persistir: bool = True,
) -> ResultadoIdentificacaoFornecedor:
    nf = NFeEntradaHistoricaImportada.objects.select_for_update(of=('self',)).get(pk=nf.pk)
    if nf.fornecedor_emitente_id and nf.fornecedor_emitente:
        return identificar_fornecedor_por_party(
            nf.emit_json,
            fornecedor_vinculado=nf.fornecedor_emitente,
        )

    resultado = identificar_fornecedor_por_party(nf.emit_json)
    if resultado.status == StatusIdentificacaoFornecedor.ENCONTRADO_UNICO and resultado.fornecedor_id:
        if persistir:
            nf.fornecedor_emitente_id = resultado.fornecedor_id
            nf.save(update_fields=['fornecedor_emitente'])
        return ResultadoIdentificacaoFornecedor(
            status=StatusIdentificacaoFornecedor.VINCULADO,
            fornecedor_id=resultado.fornecedor_id,
            fornecedor_nome=resultado.fornecedor_nome,
            fornecedor_cnpj=resultado.fornecedor_cnpj,
            cnpj_documento=resultado.cnpj_documento,
            vinculo_automatico=True,
        )
    return resultado


@transaction.atomic
def vincular_fornecedor_nfe_entrada(
    nf: NFeEntradaHistoricaImportada,
    fornecedor_id: int,
) -> NFeEntradaHistoricaImportada:
    nf = NFeEntradaHistoricaImportada.objects.select_for_update(of=('self',)).get(pk=nf.pk)
    fornecedor = Fornecedor.objects.filter(pk=fornecedor_id).first()
    if not fornecedor:
        raise ValueError('Fornecedor não encontrado.')
    cnpj_doc = cnpj_participante_normalizado(nf.emit_json)
    if cnpj_doc:
        _validar_fornecedor_para_documento(fornecedor, cnpj_doc)
    nf.fornecedor_emitente = fornecedor
    nf.save(update_fields=['fornecedor_emitente'])
    return nf


@transaction.atomic
def cadastrar_ou_vincular_fornecedor_nfe_entrada(
    nf: NFeEntradaHistoricaImportada,
    dados: dict[str, Any],
) -> tuple[Fornecedor, bool, NFeEntradaHistoricaImportada]:
    """Retorna (fornecedor, criado, nf_atualizada). Não cria duplicata por CNPJ."""
    nf = NFeEntradaHistoricaImportada.objects.select_for_update(of=('self',)).get(pk=nf.pk)
    sugestao = extrair_dados_cadastro_fornecedor_party(nf.emit_json)
    payload = {**sugestao, **(dados or {})}
    cnpj = norm_digits(payload.get('cnpj') or sugestao.get('cnpj') or cnpj_participante_normalizado(nf.emit_json))
    if len(cnpj) != 14:
        raise ValueError(MSG_SEM_CNPJ_EMITENTE)

    existentes = buscar_fornecedores_por_cnpj(cnpj, apenas_ativos=False)
    if len(existentes) > 1:
        raise ValueError(MSG_FORNECEDOR_DUPLICIDADE)
    if existentes:
        fornecedor = existentes[0]
        nf.fornecedor_emitente = fornecedor
        nf.save(update_fields=['fornecedor_emitente'])
        return fornecedor, False, nf

    razao = (payload.get('razao_social') or '').strip()
    if not razao:
        raise ValueError('Informe a razão social do fornecedor.')

    fornecedor = Fornecedor.objects.create(
        razao_social=razao,
        nome_fantasia=(payload.get('nome_fantasia') or '').strip(),
        cnpj=cnpj,
        ie=(payload.get('ie') or '').strip(),
        logradouro=(payload.get('logradouro') or '').strip(),
        numero=(payload.get('numero') or '').strip(),
        complemento=(payload.get('complemento') or '').strip(),
        bairro=(payload.get('bairro') or '').strip(),
        cidade=(payload.get('cidade') or '').strip(),
        uf=(payload.get('uf') or '').strip()[:2],
        cep=norm_digits(payload.get('cep')),
        ativo=bool(payload.get('ativo', True)),
    )
    nf.fornecedor_emitente = fornecedor
    nf.save(update_fields=['fornecedor_emitente'])
    return fornecedor, True, nf


def montar_status_fornecedor_nfe_entrada(
    nf: NFeEntradaHistoricaImportada,
    *,
    auto_vincular: bool = True,
) -> dict[str, Any]:
    if auto_vincular and not nf.fornecedor_emitente_id:
        resultado = tentar_vincular_fornecedor_nfe_entrada(nf, persistir=True)
    else:
        resultado = identificar_fornecedor_por_party(
            nf.emit_json,
            fornecedor_vinculado=nf.fornecedor_emitente if nf.fornecedor_emitente_id else None,
        )
    data = resultado.as_dict()
    if not data['fornecedor_nome']:
        data['fornecedor_nome'] = (nf.emit_json or {}).get('xNome', '')
    if not data['fornecedor_cnpj']:
        data['fornecedor_cnpj'] = (nf.emit_json or {}).get('CNPJ', '') or data['cnpj_documento']
    data['sugestao_cadastro'] = extrair_dados_cadastro_fornecedor_party(nf.emit_json)
    return data


@transaction.atomic
def tentar_vincular_fornecedor_cte_entrada(
    cte: CTeHistoricoImportado,
    *,
    persistir: bool = True,
) -> ResultadoIdentificacaoFornecedor:
    cte = CTeHistoricoImportado.objects.select_for_update(of=('self',)).get(pk=cte.pk)
    party = cte.rem_json or {}
    if cte.fornecedor_remetente_id and cte.fornecedor_remetente:
        return identificar_fornecedor_por_party(
            party,
            fornecedor_vinculado=cte.fornecedor_remetente,
        )

    resultado = identificar_fornecedor_por_party(party)
    if resultado.status == StatusIdentificacaoFornecedor.ENCONTRADO_UNICO and resultado.fornecedor_id:
        if persistir:
            cte.fornecedor_remetente_id = resultado.fornecedor_id
            cte.save(update_fields=['fornecedor_remetente'])
        return ResultadoIdentificacaoFornecedor(
            status=StatusIdentificacaoFornecedor.VINCULADO,
            fornecedor_id=resultado.fornecedor_id,
            fornecedor_nome=resultado.fornecedor_nome,
            fornecedor_cnpj=resultado.fornecedor_cnpj,
            cnpj_documento=resultado.cnpj_documento,
            vinculo_automatico=True,
        )
    return resultado


@transaction.atomic
def vincular_fornecedor_cte_entrada(
    cte: CTeHistoricoImportado,
    fornecedor_id: int,
) -> CTeHistoricoImportado:
    cte = CTeHistoricoImportado.objects.select_for_update(of=('self',)).get(pk=cte.pk)
    fornecedor = Fornecedor.objects.filter(pk=fornecedor_id).first()
    if not fornecedor:
        raise ValueError('Fornecedor não encontrado.')
    cnpj_doc = cnpj_participante_normalizado(cte.rem_json)
    if cnpj_doc:
        _validar_fornecedor_para_documento(fornecedor, cnpj_doc)
    cte.fornecedor_remetente = fornecedor
    cte.save(update_fields=['fornecedor_remetente'])
    return cte


@transaction.atomic
def cadastrar_ou_vincular_fornecedor_cte_entrada(
    cte: CTeHistoricoImportado,
    dados: dict[str, Any],
) -> tuple[Fornecedor, bool, CTeHistoricoImportado]:
    cte = CTeHistoricoImportado.objects.select_for_update(of=('self',)).get(pk=cte.pk)
    party = cte.rem_json or {}
    sugestao = extrair_dados_cadastro_fornecedor_party(party)
    payload = {**sugestao, **(dados or {})}
    cnpj = norm_digits(payload.get('cnpj') or sugestao.get('cnpj') or cnpj_participante_normalizado(party))
    if len(cnpj) != 14:
        raise ValueError(MSG_SEM_CNPJ_EMITENTE)

    existentes = buscar_fornecedores_por_cnpj(cnpj, apenas_ativos=False)
    if len(existentes) > 1:
        raise ValueError(MSG_FORNECEDOR_DUPLICIDADE)
    if existentes:
        fornecedor = existentes[0]
        cte.fornecedor_remetente = fornecedor
        cte.save(update_fields=['fornecedor_remetente'])
        return fornecedor, False, cte

    razao = (payload.get('razao_social') or '').strip()
    if not razao:
        raise ValueError('Informe a razão social do fornecedor.')

    fornecedor = Fornecedor.objects.create(
        razao_social=razao,
        nome_fantasia=(payload.get('nome_fantasia') or '').strip(),
        cnpj=cnpj,
        ie=(payload.get('ie') or '').strip(),
        logradouro=(payload.get('logradouro') or '').strip(),
        numero=(payload.get('numero') or '').strip(),
        complemento=(payload.get('complemento') or '').strip(),
        bairro=(payload.get('bairro') or '').strip(),
        cidade=(payload.get('cidade') or '').strip(),
        uf=(payload.get('uf') or '').strip()[:2],
        cep=norm_digits(payload.get('cep')),
        ativo=bool(payload.get('ativo', True)),
    )
    cte.fornecedor_remetente = fornecedor
    cte.save(update_fields=['fornecedor_remetente'])
    return fornecedor, True, cte


def montar_status_fornecedor_cte_entrada(
    cte: CTeHistoricoImportado,
    *,
    auto_vincular: bool = True,
) -> dict[str, Any]:
    party = cte.rem_json or {}
    if auto_vincular and not cte.fornecedor_remetente_id:
        resultado = tentar_vincular_fornecedor_cte_entrada(cte, persistir=True)
    else:
        resultado = identificar_fornecedor_por_party(
            party,
            fornecedor_vinculado=cte.fornecedor_remetente if cte.fornecedor_remetente_id else None,
        )
    data = resultado.as_dict()
    if not data['fornecedor_nome']:
        data['fornecedor_nome'] = party.get('xNome', '')
    if not data['fornecedor_cnpj']:
        data['fornecedor_cnpj'] = party.get('CNPJ', '') or data['cnpj_documento']
    data['sugestao_cadastro'] = extrair_dados_cadastro_fornecedor_party(party)
    return data
