"""Selector read-only — DF-e recebidos contra o CNPJ da empresa (caixa de entrada fiscal)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone as dt_timezone
from decimal import Decimal
from typing import Any

from django.db.models import Q
from django.utils import timezone

from apps.cadastros.models import Empresa
from apps.fiscal.dfe_classificacao import (
    eh_documento_homologacao,
    q_excluir_homologacao_cte,
    q_excluir_homologacao_historica_entrada,
)
from apps.fiscal.models import (
    CTeHistoricoImportado,
    NFeEntrada,
    NFeEntradaHistoricaImportada,
)

TIPO_NFE_ENTRADA = 'NFE_ENTRADA'
TIPO_CTE = 'CTE'

ROTAS_DETALHE = {
    TIPO_NFE_ENTRADA: '/nfe-entrada-historica-importada',
    TIPO_CTE: '/cte-historico-importado',
}

TIPO_LABELS = {
    TIPO_NFE_ENTRADA: 'NF-e Fornecedor',
    TIPO_CTE: 'CT-e Transportadora',
}

STATUS_ENTRADA_LABELS = {
    'PENDENTE_ENTRADA': 'Pendente de entrada',
    'IMPORTADO_BASE': 'Importado — base DF-e',
    'CONFERIDO': 'Conferido',
    'PREPARADO': 'Preparado',
    'DIVERGENTE': 'Divergente',
    'IGNORADO': 'Ignorado',
    'JA_LANCADO': 'Já lançado no ERP',
}

# Visão principal: fila de entrada — sem lançamento operacional nem tratamento concluído.
VISAO_PADRAO_STATUSES = frozenset({'PENDENTE_ENTRADA', 'IMPORTADO_BASE'})

# Exibidos somente com incluir_tratados=true (status explícito na listagem).
TRATADOS = frozenset({'JA_LANCADO', 'CONFERIDO', 'IGNORADO', 'PREPARADO', 'DIVERGENTE'})


@dataclass
class FiltrosCentralDfe:
    empresa_id: int | None = None
    tipo_documento: str = ''
    status_entrada: str = ''
    incluir_tratados: bool = False
    data_emissao_inicio: date | None = None
    data_emissao_fim: date | None = None
    data_importacao_inicio: date | None = None
    data_importacao_fim: date | None = None
    emitente_cnpj: str = ''
    emitente_nome: str = ''
    chave_acesso: str = ''
    uf: str = ''
    valor_min: Decimal | None = None
    valor_max: Decimal | None = None
    search: str = ''
    ordering: str = '-data_emissao'


@dataclass
class DocumentoCentralDfe:
    id: int
    tipo_documento: str
    chave_resumida: str
    chave_acesso: str
    numero: str
    serie: str
    data_emissao: datetime | date | None
    data_importacao: datetime | None
    emitente_nome: str
    emitente_cnpj: str
    uf: str
    valor_total: Decimal
    status_entrada: str
    status_entrada_label: str
    tipo_label: str
    detalhe_rota: str
    empresa_id: int | None = None
    xml_status: str = 'ARMAZENADO'
    xml_status_label: str = 'XML armazenado'
    xml_armazenado: bool = True
    manifestacao_aplicavel: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            'id': self.id,
            'tipo_documento': self.tipo_documento,
            'chave_resumida': self.chave_resumida,
            'chave_acesso': self.chave_acesso,
            'numero': self.numero,
            'serie': self.serie,
            'data_emissao': self._iso(self.data_emissao),
            'data_importacao': self._iso(self.data_importacao),
            'emitente_nome': self.emitente_nome,
            'emitente_cnpj': self.emitente_cnpj,
            'uf': self.uf,
            'valor_total': str(self.valor_total),
            'status_entrada': self.status_entrada,
            'status_entrada_label': self.status_entrada_label,
            'tipo_label': self.tipo_label,
            'detalhe_rota': self.detalhe_rota,
            'empresa_id': self.empresa_id,
            'xml_status': self.xml_status,
            'xml_status_label': self.xml_status_label,
            'xml_armazenado': self.xml_armazenado,
            'manifestacao_aplicavel': self.manifestacao_aplicavel,
        }

    @staticmethod
    def _iso(value: datetime | date | None) -> str | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.isoformat()
        return value.isoformat()


def normalizar_cnpj(valor: str | None) -> str:
    return ''.join(c for c in str(valor or '') if c.isdigit())


def _scalar_query_param(val: Any, default: str = '') -> str:
    """Normaliza valor de QueryDict (dict() retorna listas por chave)."""
    if val is None:
        return default
    if isinstance(val, list):
        return str(val[0]).strip() if val else default
    return str(val).strip()


def normalizar_params_central_dfe(params: dict[str, Any]) -> dict[str, str]:
    return {str(k): _scalar_query_param(v) for k, v in (params or {}).items()}


class EmpresaCentralDfeError(Exception):
    def __init__(self, mensagem: str, codigo: str = 'EMPRESA_INVALIDA') -> None:
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.codigo = codigo


def resolver_empresa_central(params: dict[str, Any]) -> Empresa | None:
    raw = _scalar_query_param(params.get('empresa_id'))
    if raw:
        try:
            return Empresa.objects.get(pk=int(raw))
        except Empresa.DoesNotExist as exc:
            raise EmpresaCentralDfeError('Empresa não encontrada.') from exc
        except (TypeError, ValueError) as exc:
            raise EmpresaCentralDfeError('empresa_id inválido.') from exc
    return Empresa.objects.order_by('pk').first()


def parse_filtros_central_dfe(params: dict[str, Any]) -> FiltrosCentralDfe:
    p = normalizar_params_central_dfe(params)

    def _date(raw: str | None) -> date | None:
        if not raw:
            return None
        try:
            return date.fromisoformat(str(raw)[:10])
        except ValueError:
            return None

    def _competencia(raw: str | None) -> tuple[date | None, date | None]:
        """Aceita mm/aaaa, mmaaaa, aaaa-mm."""
        if not raw:
            return None, None
        texto = str(raw).strip().replace('/', '').replace('-', '')
        if len(texto) == 6 and texto.isdigit():
            mes = int(texto[:2])
            ano = int(texto[2:])
            if 1 <= mes <= 12:
                inicio = date(ano, mes, 1)
                if mes == 12:
                    fim = date(ano, 12, 31)
                else:
                    fim = date(ano, mes + 1, 1) - timedelta(days=1)
                return inicio, fim
        if len(texto) == 7 and texto[:4].isdigit() and texto[4:].isdigit():
            ano = int(texto[:4])
            mes = int(texto[4:])
            if 1 <= mes <= 12:
                inicio = date(ano, mes, 1)
                if mes == 12:
                    fim = date(ano, 12, 31)
                else:
                    fim = date(ano, mes + 1, 1) - timedelta(days=1)
                return inicio, fim
        return None, None

    def _decimal(raw: str | None) -> Decimal | None:
        if raw in (None, ''):
            return None
        try:
            return Decimal(str(raw).replace(',', '.'))
        except Exception:
            return None

    empresa_id = None
    if p.get('empresa_id'):
        try:
            empresa_id = int(p.get('empresa_id'))
        except (TypeError, ValueError):
            empresa_id = None

    incluir_tratados = p.get('incluir_tratados', '').lower() in {'1', 'true', 'sim'}
    ordering = p.get('ordering') or '-data_emissao'

    emissao_inicio = _date(p.get('data_emissao_inicio'))
    emissao_fim = _date(p.get('data_emissao_fim'))
    if not emissao_inicio and not emissao_fim:
        comp_inicio, comp_fim = _competencia(p.get('competencia_emissao') or p.get('competencia'))
        emissao_inicio = comp_inicio or emissao_inicio
        emissao_fim = comp_fim or emissao_fim

    return FiltrosCentralDfe(
        empresa_id=empresa_id,
        tipo_documento=(p.get('tipo_documento') or '').upper(),
        status_entrada=(p.get('status_entrada') or '').upper(),
        incluir_tratados=incluir_tratados,
        data_emissao_inicio=emissao_inicio,
        data_emissao_fim=emissao_fim,
        data_importacao_inicio=_date(p.get('data_importacao_inicio')),
        data_importacao_fim=_date(p.get('data_importacao_fim')),
        emitente_cnpj=normalizar_cnpj(p.get('emitente_cnpj') or p.get('participante_cnpj')),
        emitente_nome=(p.get('emitente_nome') or p.get('participante_nome') or '').strip(),
        chave_acesso=''.join(c for c in p.get('chave_acesso', '') if c.isdigit()),
        uf=(p.get('uf') or '').upper()[:2],
        valor_min=_decimal(p.get('valor_min')),
        valor_max=_decimal(p.get('valor_max')),
        search=(p.get('search') or '').strip(),
        ordering=ordering,
    )


def chave_resumida(chave: str | None) -> str:
    c = (chave or '').strip()
    if not c:
        return ''
    if len(c) <= 12:
        return c
    return f'{c[:4]}…{c[-4:]}'


def _json_participante(payload: dict | None) -> tuple[str, str]:
    data = payload or {}
    nome = (data.get('xNome') or data.get('xFant') or '').strip()
    doc = normalizar_cnpj(str(data.get('CNPJ') or data.get('CPF') or ''))
    return nome, doc


def _aplica_filtro_data_emissao(qs, campo: str, filtros: FiltrosCentralDfe):
    tz = timezone.get_current_timezone()
    if filtros.data_emissao_inicio:
        inicio = timezone.make_aware(datetime.combine(filtros.data_emissao_inicio, time.min), tz)
        qs = qs.filter(**{f'{campo}__gte': inicio})
    if filtros.data_emissao_fim:
        fim = timezone.make_aware(datetime.combine(filtros.data_emissao_fim, time.max), tz)
        qs = qs.filter(**{f'{campo}__lte': fim})
    return qs


def _filtrar_queryset_fila_dfe_nfe(qs):
    """Fila DF-e recebidos: produção, sem homologação; cStat 100 ou vazio (importação recente)."""
    return qs.filter(q_excluir_homologacao_historica_entrada()).filter(
        Q(cstat='100') | Q(cstat__iexact='100') | Q(cstat=''),
    )


def _filtrar_queryset_fila_dfe_cte(qs):
    return qs.filter(q_excluir_homologacao_cte()).filter(cancelado=False).filter(
        Q(cstat='100') | Q(cstat__iexact='100') | Q(cstat=''),
    )


def _aplica_filtro_data_importacao(qs, filtros: FiltrosCentralDfe):
    if filtros.data_importacao_inicio:
        qs = qs.filter(importado_em__date__gte=filtros.data_importacao_inicio)
    if filtros.data_importacao_fim:
        qs = qs.filter(importado_em__date__lte=filtros.data_importacao_fim)
    return qs


def _chaves_nfe_entrada_lancadas() -> set[str]:
    return {
        c
        for c in NFeEntrada.objects.exclude(chave_acesso='').values_list('chave_acesso', flat=True)
        if c
    }


def _status_entrada_nfe(conf_status: str | None, chave: str, chaves_lancadas: set[str]) -> tuple[str, str]:
    if chave and chave in chaves_lancadas:
        return 'JA_LANCADO', STATUS_ENTRADA_LABELS['JA_LANCADO']
    conf = (conf_status or '').upper()
    if conf == 'CANCELADA':
        return 'IGNORADO', STATUS_ENTRADA_LABELS['IGNORADO']
    if conf == 'PREPARADA':
        return 'PREPARADO', STATUS_ENTRADA_LABELS['PREPARADO']
    if conf == 'CONFERIDA':
        return 'CONFERIDO', STATUS_ENTRADA_LABELS['CONFERIDO']
    if conf == 'PENDENTE' or not conf:
        return 'PENDENTE_ENTRADA', STATUS_ENTRADA_LABELS['PENDENTE_ENTRADA']
    return 'IMPORTADO_BASE', STATUS_ENTRADA_LABELS['IMPORTADO_BASE']


def _status_entrada_cte(status_conf: str | None) -> tuple[str, str]:
    conf = (status_conf or 'IMPORTADO').upper()
    if conf in {'IGNORADO', 'CANCELADO'}:
        return 'IGNORADO', STATUS_ENTRADA_LABELS['IGNORADO']
    if conf == 'DIVERGENTE':
        return 'DIVERGENTE', STATUS_ENTRADA_LABELS['DIVERGENTE']
    if conf == 'CONFERIDO':
        return 'CONFERIDO', STATUS_ENTRADA_LABELS['CONFERIDO']
    if conf == 'PREPARADO':
        return 'PREPARADO', STATUS_ENTRADA_LABELS['PREPARADO']
    if conf in {'IMPORTADO', 'PROCESSADO', ''}:
        return 'PENDENTE_ENTRADA', STATUS_ENTRADA_LABELS['PENDENTE_ENTRADA']
    return 'IMPORTADO_BASE', STATUS_ENTRADA_LABELS['IMPORTADO_BASE']


def _coletar_nfe_entrada_recebida(
    filtros: FiltrosCentralDfe,
    empresa: Empresa,
    chaves_lancadas: set[str],
) -> list[DocumentoCentralDfe]:
    if filtros.tipo_documento and filtros.tipo_documento not in {TIPO_NFE_ENTRADA}:
        return []

    qs = NFeEntradaHistoricaImportada.objects.select_related(
        'fornecedor_emitente',
        'empresa_destinataria',
    ).select_related('conferencia')
    qs = qs.filter(empresa_destinataria_id=empresa.pk)
    qs = _filtrar_queryset_fila_dfe_nfe(qs)
    qs = _aplica_filtro_data_emissao(qs, 'dh_emissao', filtros)
    qs = _aplica_filtro_data_importacao(qs, filtros)
    if filtros.chave_acesso:
        qs = qs.filter(chave_acesso__icontains=filtros.chave_acesso)

    empresa_cnpj = normalizar_cnpj(empresa.cnpj)
    rows: list[DocumentoCentralDfe] = []
    for doc in qs.iterator(chunk_size=200):
        if eh_documento_homologacao(doc):
            continue
        chave = (doc.chave_acesso or '').strip()
        if not filtros.incluir_tratados and chave and chave in chaves_lancadas:
            continue
        conf = getattr(doc, 'conferencia', None)
        conf_status = conf.status if conf else ''
        status_entrada, status_label = _status_entrada_nfe(conf_status, chave, chaves_lancadas)
        if not filtros.incluir_tratados and status_entrada not in VISAO_PADRAO_STATUSES:
            continue
        emit_nome = (
            doc.fornecedor_emitente.razao_social if doc.fornecedor_emitente_id else _json_participante(doc.emit_json)[0]
        )
        emit_cnpj = (
            doc.fornecedor_emitente.cnpj if doc.fornecedor_emitente_id else _json_participante(doc.emit_json)[1]
        )
        emit_cnpj_norm = normalizar_cnpj(emit_cnpj)
        if empresa_cnpj and emit_cnpj_norm == empresa_cnpj:
            continue
        uf = (doc.dest_json or {}).get('UF') or (doc.emit_json or {}).get('UF') or ''
        rows.append(
            DocumentoCentralDfe(
                id=doc.id,
                tipo_documento=TIPO_NFE_ENTRADA,
                chave_resumida=chave_resumida(chave),
                chave_acesso=chave,
                numero=doc.numero,
                serie=doc.serie,
                data_emissao=doc.dh_emissao,
                data_importacao=doc.importado_em,
                emitente_nome=emit_nome,
                emitente_cnpj=normalizar_cnpj(emit_cnpj),
                uf=str(uf or '')[:2].upper(),
                valor_total=doc.valor_total_nf,
                status_entrada=status_entrada,
                status_entrada_label=status_label,
                tipo_label=TIPO_LABELS[TIPO_NFE_ENTRADA],
                detalhe_rota=ROTAS_DETALHE[TIPO_NFE_ENTRADA],
                empresa_id=empresa.pk,
                xml_status='ARMAZENADO',
                xml_status_label='XML armazenado',
                xml_armazenado=True,
                manifestacao_aplicavel=True,
            ),
        )
    return rows


def _coletar_cte_recebido(filtros: FiltrosCentralDfe, empresa: Empresa) -> list[DocumentoCentralDfe]:
    if filtros.tipo_documento and filtros.tipo_documento not in {TIPO_CTE}:
        return []

    qs = CTeHistoricoImportado.objects.select_related(
        'transportadora',
        'empresa_tomadora',
        'empresa_destinataria',
        'empresa_recebedora',
    )
    qs = qs.filter(
        Q(empresa_tomadora_id=empresa.pk)
        | Q(empresa_destinataria_id=empresa.pk)
        | Q(empresa_recebedora_id=empresa.pk),
    )
    qs = _filtrar_queryset_fila_dfe_cte(qs)
    qs = _aplica_filtro_data_emissao(qs, 'dh_emissao', filtros)
    qs = _aplica_filtro_data_importacao(qs, filtros)
    if filtros.chave_acesso:
        qs = qs.filter(chave_acesso__icontains=filtros.chave_acesso)
    if filtros.uf:
        qs = qs.filter(Q(uf_inicio__iexact=filtros.uf) | Q(uf_fim__iexact=filtros.uf))

    empresa_cnpj = normalizar_cnpj(empresa.cnpj)
    rows: list[DocumentoCentralDfe] = []
    for doc in qs.iterator(chunk_size=200):
        if eh_documento_homologacao(doc):
            continue
        status_entrada, status_label = _status_entrada_cte(doc.status_conferencia)
        if not filtros.incluir_tratados and status_entrada not in VISAO_PADRAO_STATUSES:
            continue
        emit_nome = (
            doc.transportadora.razao_social if doc.transportadora_id else _json_participante(doc.emit_json)[0]
        )
        emit_cnpj = doc.transportadora.cnpj if doc.transportadora_id else _json_participante(doc.emit_json)[1]
        emit_cnpj_norm = normalizar_cnpj(emit_cnpj)
        if empresa_cnpj and emit_cnpj_norm == empresa_cnpj:
            continue
        rows.append(
            DocumentoCentralDfe(
                id=doc.id,
                tipo_documento=TIPO_CTE,
                chave_resumida=chave_resumida(doc.chave_acesso),
                chave_acesso=doc.chave_acesso,
                numero=doc.numero,
                serie=doc.serie,
                data_emissao=doc.dh_emissao,
                data_importacao=doc.importado_em,
                emitente_nome=emit_nome,
                emitente_cnpj=normalizar_cnpj(emit_cnpj),
                uf=(doc.uf_fim or doc.uf_inicio or '')[:2].upper(),
                valor_total=doc.valor_total_servico,
                status_entrada=status_entrada,
                status_entrada_label=status_label,
                tipo_label=TIPO_LABELS[TIPO_CTE],
                detalhe_rota=ROTAS_DETALHE[TIPO_CTE],
                empresa_id=empresa.pk,
                xml_status='ARMAZENADO',
                xml_status_label='XML armazenado',
                xml_armazenado=True,
                manifestacao_aplicavel=False,
            ),
        )
    return rows


def _match_filtros_pos_query(row: DocumentoCentralDfe, filtros: FiltrosCentralDfe) -> bool:
    if not filtros.incluir_tratados and row.status_entrada not in VISAO_PADRAO_STATUSES:
        return False
    if filtros.status_entrada and row.status_entrada != filtros.status_entrada:
        return False
    if filtros.uf and row.uf.upper() != filtros.uf:
        return False
    if filtros.valor_min is not None and row.valor_total < filtros.valor_min:
        return False
    if filtros.valor_max is not None and row.valor_total > filtros.valor_max:
        return False
    if filtros.emitente_cnpj and filtros.emitente_cnpj not in row.emitente_cnpj:
        return False
    if filtros.emitente_nome:
        termo = filtros.emitente_nome.lower()
        if termo not in (row.emitente_nome or '').lower():
            return False
    if filtros.search:
        termo = filtros.search.lower()
        blob = ' '.join(
            [
                row.numero or '',
                row.chave_acesso or '',
                row.emitente_nome or '',
                row.tipo_label or '',
                row.status_entrada_label or '',
            ],
        ).lower()
        if termo not in blob:
            return False
    return True


def ordenar_documentos_central(rows: list[DocumentoCentralDfe], ordering: str) -> list[DocumentoCentralDfe]:
    reverse = ordering.startswith('-')
    campo = ordering.lstrip('-')

    def _aware_min(value: datetime | date | None) -> datetime:
        if value is None:
            return datetime.min.replace(tzinfo=dt_timezone.utc)
        if isinstance(value, date) and not isinstance(value, datetime):
            return datetime.combine(value, time.min, tzinfo=dt_timezone.utc)
        if isinstance(value, datetime) and value.tzinfo is None:
            return value.replace(tzinfo=dt_timezone.utc)
        return value

    if campo == 'data_importacao':
        key_fn = lambda r: _aware_min(r.data_importacao)
    elif campo == 'valor_total':
        key_fn = lambda r: r.valor_total
    elif campo == 'tipo_documento':
        key_fn = lambda r: r.tipo_documento
    else:
        key_fn = lambda r: (_aware_min(r.data_emissao), _aware_min(r.data_importacao))

    return sorted(rows, key=key_fn, reverse=reverse)


def calcular_resumo_central(rows: list[DocumentoCentralDfe]) -> dict[str, int]:
    resumo = {
        'total': len(rows),
        'pendentes_entrada': 0,
        'nfe_fornecedores': 0,
        'cte_transportadoras': 0,
        'divergentes': 0,
        'ignorados': 0,
        'ja_tratados': 0,
    }
    for row in rows:
        if row.tipo_documento == TIPO_NFE_ENTRADA:
            resumo['nfe_fornecedores'] += 1
        elif row.tipo_documento == TIPO_CTE:
            resumo['cte_transportadoras'] += 1
        if row.status_entrada == 'PENDENTE_ENTRADA':
            resumo['pendentes_entrada'] += 1
        if row.status_entrada == 'DIVERGENTE':
            resumo['divergentes'] += 1
        if row.status_entrada == 'IGNORADO':
            resumo['ignorados'] += 1
        if row.status_entrada in TRATADOS:
            resumo['ja_tratados'] += 1
    return resumo


def coletar_documentos_central_dfe(
    filtros: FiltrosCentralDfe,
    *,
    empresa: Empresa | None = None,
) -> list[DocumentoCentralDfe]:
    if empresa is None:
        return []
    chaves_lancadas = _chaves_nfe_entrada_lancadas()
    rows: list[DocumentoCentralDfe] = []
    rows.extend(_coletar_nfe_entrada_recebida(filtros, empresa, chaves_lancadas))
    rows.extend(_coletar_cte_recebido(filtros, empresa))
    rows = [r for r in rows if _match_filtros_pos_query(r, filtros)]
    return ordenar_documentos_central(rows, filtros.ordering)


def listar_documentos_central_dfe(
    filtros: FiltrosCentralDfe,
    *,
    empresa: Empresa | None = None,
) -> list[dict[str, Any]]:
    return [r.to_dict() for r in coletar_documentos_central_dfe(filtros, empresa=empresa)]
