"""
Apuração fiscal gerencial on-demand (NF-e histórica/XML + NF interna operacional).

Separa regras de consolidação das views. Não gera SPED oficial.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Exists, OuterRef, Prefetch, Q
from django.utils import timezone as django_timezone

from apps.cadastros.models import Empresa
from apps.fiscal.models import (
    CTeHistoricoImportado,
    EventoNFeSaidaHistoricaPendente,
    ItemNFeEntradaHistoricaImportada,
    ItemNFeSaidaHistoricaImportada,
    NFeEntrada,
    NFeEntradaHistoricaImportada,
    NFeSaida,
    NFeSaidaHistoricaImportada,
)
from apps.fiscal.dfe_classificacao import (
    filtrar_queryset_apuracao_cte,
    filtrar_queryset_apuracao_historica_entrada,
    filtrar_queryset_apuracao_historica_saida,
    filtrar_queryset_apuracao_nfe_saida,
    pode_entrar_apuracao,
)
from apps.fiscal.nfe_historica_fiscal import extrair_totais_fiscais_documento

from .imposto_item_xml import dec, extrair_produto_item, extrair_tributos_item
from .reforma_tributaria import (
    TotaisReformaTributaria,
    coercer_imposto_item_json,
    merge_stats_reforma_cte,
    merge_stats_reforma_ibscbs,
    merge_totais_reforma,
    processar_reforma_cte_imposto,
    processar_reforma_nfe_historica,
)
from .sped_map import modelo_mapeado_sped_nfe, montar_base_efd_contribuicoes, montar_base_efd_icms_ipi

IMPOSTO_KEYS_PADRAO = frozenset(
    {
        'ICMS',
        'IPI',
        'PIS',
        'COFINS',
        'II',
        'ICMSUFDest',
        'ISSQN',
        'PISST',
        'COFINSST',
        'IBSCBS',
        'IS',
        # Chaves irmãs no nó imposto do XML (não são “reforma” extra)
        'vTotTrib',
    }
)


def _money_float(d: Decimal) -> float:
    return float(d.quantize(Decimal('0.01')))


def _parse_date(v: Any) -> date | None:
    """Aceita str, lista (ex.: dict(QueryDict)) ou vazio; falha silenciosa → None (evita cair no default do mês atual por engano)."""
    raw = _first_query_value(v)
    if raw in (None, '', False):
        return None
    s = str(raw).strip()
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def _range_datetime_emissao(di: date, df: date) -> tuple[datetime, datetime]:
    """Intervalo inclusivo no fuso configurado (evita perda por comparação só de date em DateTimeField)."""
    tz = django_timezone.get_current_timezone()
    start = django_timezone.make_aware(datetime.combine(di, time.min), tz)
    end = django_timezone.make_aware(datetime.combine(df, time.max), tz)
    return start, end


def _first_query_value(v: Any) -> Any:
    if isinstance(v, (list, tuple)) and v:
        return v[0]
    return v


def _optional_int(q: dict[str, Any], key: str) -> int | None:
    raw = _first_query_value(q.get(key))
    if raw in (None, '', False):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _optional_status(q: dict[str, Any]) -> str | None:
    raw = _first_query_value(q.get('status'))
    if raw in (None, '', False):
        return None
    s = str(raw).strip()
    return s or None


def _fonte_normalizada(q: dict[str, Any]) -> str:
    raw = str(_first_query_value(q.get('fonte')) or 'TODOS').strip().upper().replace('Ó', 'O')
    if raw in {'TODOS', 'OPERACIONAIS', 'HISTORICOS'}:
        return raw
    return 'TODOS'


def _q_autorizada_saida_historica() -> Q:
    """Autorização SEFAZ (cStat 100) ou status_documento autorizada/autorizado."""
    return (
        Q(cstat='100')
        | Q(cstat__iexact='100')
        | Q(status_documento__iexact='autorizada')
        | Q(status_documento__iexact='autorizado')
        | Q(status_documento__iexact='AUTORIZADA')
        | Q(status_documento__iexact='AUTORIZADO')
    )


def _q_autorizada_entrada_historica() -> Q:
    """NF entrada histórica: só cstat (modelo sem status_documento/cancelada)."""
    return Q(cstat='100') | Q(cstat__iexact='100')


def _aplica_filtro_status_saida_historica(qs, status_raw: str):
    """Filtra por status_documento e/ou cStat; cancelada é tratada separadamente (cancelada + incluir_canceladas)."""
    s = status_raw.strip().lower()
    raw = status_raw.strip()
    if raw == '100' or s == '100':
        return qs.filter(_q_autorizada_saida_historica())
    if s in ('autorizada', 'autorizado', 'autorizado(a)', 'autoriz.'):
        return qs.filter(_q_autorizada_saida_historica())
    if s in ('cancelada', 'cancelado', 'cancel'):
        return qs.filter(Q(cancelada=True) | Q(status_documento__icontains='cancel'))
    return qs.filter(status_documento__iexact=raw)


def _cnpj_somente_digitos(val: Any) -> str:
    return ''.join(c for c in str(val or '') if c.isdigit())


def _filtro_empresa_saida_historica(qs, f: 'FiltrosApuracao'):
    """
    empresa_emitente_id = FK; se NF sem FK, tenta CNPJ do emitente no emit_json (14 dígitos da Empresa).
    """
    if not f.empresa_id:
        return qs
    try:
        emp = Empresa.objects.get(pk=f.empresa_id)
    except Empresa.DoesNotExist:
        return qs.none()
    cnpj = _cnpj_somente_digitos(emp.cnpj)
    q_fk = Q(empresa_emitente_id=f.empresa_id)
    if len(cnpj) >= 14:
        c14 = cnpj[:14]
        q_xml = Q(empresa_emitente_id__isnull=True) & Q(emit_json__icontains=c14)
        return qs.filter(q_fk | q_xml)
    return qs.filter(q_fk)


def _filtro_empresa_entrada_historica(qs, f: 'FiltrosApuracao'):
    """empresa_destinataria_id = FK; se NF sem FK, tenta CNPJ do destinatário no dest_json."""
    if not f.empresa_id:
        return qs
    try:
        emp = Empresa.objects.get(pk=f.empresa_id)
    except Empresa.DoesNotExist:
        return qs.none()
    cnpj = _cnpj_somente_digitos(emp.cnpj)
    q_fk = Q(empresa_destinataria_id=f.empresa_id)
    if len(cnpj) >= 14:
        c14 = cnpj[:14]
        q_xml = Q(empresa_destinataria_id__isnull=True) & Q(dest_json__icontains=c14)
        return qs.filter(q_fk | q_xml)
    return qs.filter(q_fk)


def _filtro_empresa_cte_historico(qs, f: 'FiltrosApuracao'):
    """Tomador / destinatário / recebedor vinculados à empresa ou CNPJ nos JSONs de participante."""
    if not f.empresa_id:
        return qs
    try:
        emp = Empresa.objects.get(pk=f.empresa_id)
    except Empresa.DoesNotExist:
        return qs.none()
    cnpj = _cnpj_somente_digitos(emp.cnpj)
    q_fk = (
        Q(empresa_tomadora_id=f.empresa_id)
        | Q(empresa_destinataria_id=f.empresa_id)
        | Q(empresa_recebedora_id=f.empresa_id)
    )
    if len(cnpj) >= 14:
        c14 = cnpj[:14]
        q_xml = (
            Q(tomador_json__icontains=c14)
            | Q(dest_json__icontains=c14)
            | Q(receb_json__icontains=c14)
            | Q(emit_json__icontains=c14)
        )
        return qs.filter(q_fk | q_xml)
    return qs.filter(q_fk)


def _impostos_json_lista_itens(itens: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for it in itens:
        imp = getattr(it, 'imposto_json', None)
        out.append(coercer_imposto_item_json(imp))
    return out


def _aplicar_reforma_nfe_historica(ctx: ContextoApuracao, nf: Any, itens: list[Any], lado: str) -> None:
    rtot, ralerts, rstats = processar_reforma_nfe_historica(
        getattr(nf, 'totais_json', None),
        getattr(nf, 'reforma_e_outros_json', None),
        _impostos_json_lista_itens(itens),
    )
    for a in ralerts:
        _alert(
            ctx,
            codigo='REFORMA_DOC',
            mensagem=a,
            severidade='info',
            documento_tipo=type(nf).__name__,
            documento_id=nf.id,
        )
    rj = getattr(nf, 'reforma_e_outros_json', None)
    tem_sinal = bool(rstats.get('itens_com_tags_ibscbs') or rstats.get('nota_com_ibscbstot') or (isinstance(rj, dict) and rj))
    acum_lado = ctx.reforma_entrada if lado == 'ENTRADA' else ctx.reforma_saida
    if tem_sinal:
        ctx.reforma.notas_com_bloco_extra += 1
        acum_lado.notas_com_bloco_extra += 1
    merge_totais_reforma(ctx.reforma, rtot)
    merge_stats_reforma_ibscbs(ctx.reforma, rstats)
    merge_totais_reforma(acum_lado, rtot)
    merge_stats_reforma_ibscbs(acum_lado, rstats)


def _apuracao_escaneia_cte_reforma(f: FiltrosApuracao) -> bool:
    if f.fonte not in {'TODOS', 'HISTORICOS'}:
        return False
    mod = (f.modelo_documento or '').strip()
    if mod and mod != '57':
        return False
    return True


# --- Adaptadores NFeSaidaHistoricaImportada (evita uso acidental de nomes de campos de outros models) ---


def historica_saida_data(nota: NFeSaidaHistoricaImportada) -> datetime:
    return nota.dh_emissao


def historica_saida_valor_total(nota: NFeSaidaHistoricaImportada) -> Decimal:
    return nota.valor_total_nf or Decimal('0')


def historica_saida_valor_produtos(nota: NFeSaidaHistoricaImportada) -> Decimal:
    return nota.valor_produtos or Decimal('0')


def historica_saida_status(nota: NFeSaidaHistoricaImportada) -> str:
    return str(nota.status_documento or '')


def historica_saida_empresa_id(nota: NFeSaidaHistoricaImportada) -> int | None:
    return nota.empresa_emitente_id


def historica_saida_cancelada(nota: NFeSaidaHistoricaImportada) -> bool:
    return bool(nota.cancelada)


def _diagnostico_fontes_saida_historica(f: 'FiltrosApuracao', em_ini: datetime, em_fim: datetime) -> dict[str, Any]:
    """Contagens progressivas na saída histórica (campos reais do model)."""
    saidas_historicas_total_banco = NFeSaidaHistoricaImportada.objects.count()

    q_periodo = NFeSaidaHistoricaImportada.objects.filter(dh_emissao__gte=em_ini, dh_emissao__lte=em_fim)
    saidas_historicas_no_periodo = q_periodo.count()

    q_emp = _filtro_empresa_saida_historica(q_periodo, f)
    saidas_historicas_apos_empresa = q_emp.count()

    q_cli = q_emp
    if f.cliente_id:
        q_cli = q_cli.filter(cliente_id=f.cliente_id)

    q_stat = q_cli
    if f.status:
        q_stat = _aplica_filtro_status_saida_historica(q_stat, f.status)
    saidas_historicas_apos_status = q_stat.count()

    q_can = q_stat
    if not f.incluir_canceladas:
        q_can = q_can.filter(cancelada=False)
    saidas_historicas_apos_canceladas = q_can.count()

    q_final = q_can
    if f.cfop:
        q_final = q_final.filter(
            Exists(ItemNFeSaidaHistoricaImportada.objects.filter(nf_id=OuterRef('pk'), prod_json__CFOP=f.cfop))
        )
    if f.ncm:
        q_final = q_final.filter(
            Exists(ItemNFeSaidaHistoricaImportada.objects.filter(nf_id=OuterRef('pk'), prod_json__NCM=f.ncm))
        )
    saidas_historicas_incluidas = q_final.count()

    return {
        'saidas_historicas_total_banco': saidas_historicas_total_banco,
        'saidas_historicas_no_periodo': saidas_historicas_no_periodo,
        'saidas_historicas_apos_empresa': saidas_historicas_apos_empresa,
        'saidas_historicas_apos_status': saidas_historicas_apos_status,
        'saidas_historicas_apos_canceladas': saidas_historicas_apos_canceladas,
        'saidas_historicas_incluidas': saidas_historicas_incluidas,
        'campo_data_usado': 'dh_emissao',
        'campo_valor_usado': 'valor_total_nf',
        'campo_status_usado': 'status_documento',
        'campo_empresa_usado': 'empresa_emitente_id (+ emit_json CNPJ se FK nulo)',
        'campo_cancelada_usado': 'cancelada',
    }


def _diagnostico_fontes_entrada_historica(f: 'FiltrosApuracao', em_ini: datetime, em_fim: datetime) -> dict[str, Any]:
    entradas_historicas_total_banco = NFeEntradaHistoricaImportada.objects.count()
    q_periodo = NFeEntradaHistoricaImportada.objects.filter(dh_emissao__gte=em_ini, dh_emissao__lte=em_fim)
    entradas_historicas_no_periodo = q_periodo.count()
    q_emp = _filtro_empresa_entrada_historica(q_periodo, f)
    entradas_historicas_apos_empresa = q_emp.count()
    q_for = q_emp
    if f.fornecedor_id:
        q_for = q_for.filter(fornecedor_emitente_id=f.fornecedor_id)
    entradas_historicas_apos_status = q_for.count()
    q_final = q_for
    if f.cfop:
        q_final = q_final.filter(
            Exists(ItemNFeEntradaHistoricaImportada.objects.filter(nf_id=OuterRef('pk'), prod_json__CFOP=f.cfop))
        )
    if f.ncm:
        q_final = q_final.filter(
            Exists(ItemNFeEntradaHistoricaImportada.objects.filter(nf_id=OuterRef('pk'), prod_json__NCM=f.ncm))
        )
    entradas_historicas_incluidas = q_final.count()
    return {
        'entradas_historicas_total_banco': entradas_historicas_total_banco,
        'entradas_historicas_no_periodo': entradas_historicas_no_periodo,
        'entradas_historicas_apos_empresa': entradas_historicas_apos_empresa,
        'entradas_historicas_apos_status': entradas_historicas_apos_status,
        'entradas_historicas_incluidas': entradas_historicas_incluidas,
        'entrada_campo_data_usado': 'dh_emissao',
        'entrada_campo_valor_usado': 'valor_total_nf',
        'entrada_campo_empresa_usado': 'empresa_destinataria_id (+ dest_json CNPJ se FK nulo)',
    }


@dataclass
class FiltrosApuracao:
    empresa_id: int | None
    data_inicio: date
    data_fim: date
    tipo: str
    fonte: str
    status: str | None
    cliente_id: int | None
    fornecedor_id: int | None
    cfop: str | None
    ncm: str | None
    modelo_documento: str | None
    incluir_canceladas: bool

    @classmethod
    def from_querydict(cls, q: dict[str, Any]) -> FiltrosApuracao:
        di = _parse_date(q.get('data_inicio'))
        df = _parse_date(q.get('data_fim'))
        mes, ano = q.get('mes'), q.get('ano')
        if di is None and mes and ano:
            try:
                m, y = int(mes), int(ano)
                di = date(y, m, 1)
                if m == 12:
                    df = date(y, 12, 31)
                else:
                    df = date(y, m + 1, 1) - timedelta(days=1)
            except (ValueError, TypeError):
                di = date.today().replace(day=1)
                df = date.today()
        if di is None:
            di = date.today().replace(day=1)
        if df is None:
            df = date.today()

        emp = _first_query_value(q.get('empresa_id'))
        empresa_id = int(emp) if emp not in (None, '') else None

        def truthy(v: Any) -> bool:
            v = _first_query_value(v)
            return str(v).lower() in {'1', 'true', 'sim', 'yes'}

        return cls(
            empresa_id=empresa_id,
            data_inicio=di,
            data_fim=df,
            tipo=(str(_first_query_value(q.get('tipo')) or 'AMBOS').strip().upper() or 'AMBOS'),
            fonte=_fonte_normalizada(q),
            status=_optional_status(q),
            cliente_id=_optional_int(q, 'cliente_id'),
            fornecedor_id=_optional_int(q, 'fornecedor_id'),
            cfop=str(q.get('cfop') or '').strip() or None,
            ncm=str(q.get('ncm') or '').strip() or None,
            modelo_documento=str(q.get('modelo_documento') or '').strip() or None,
            incluir_canceladas=truthy(q.get('incluir_canceladas')),
        )


@dataclass
class AcumuloLado:
    quantidade_notas: int = 0
    quantidade_itens: int = 0
    valor_documentos: Decimal = Decimal('0')
    valor_produtos: Decimal = Decimal('0')
    base_icms: Decimal = Decimal('0')
    valor_icms: Decimal = Decimal('0')
    base_ipi: Decimal = Decimal('0')
    valor_ipi: Decimal = Decimal('0')
    base_pis: Decimal = Decimal('0')
    valor_pis: Decimal = Decimal('0')
    base_cofins: Decimal = Decimal('0')
    valor_cofins: Decimal = Decimal('0')

    def add_item_tributos(self, trib: dict[str, Any], valor_prod: Decimal) -> None:
        self.quantidade_itens += 1
        self.valor_produtos += valor_prod
        self.base_icms += trib['base_icms']
        self.valor_icms += trib['valor_icms']
        self.base_ipi += trib['base_ipi']
        self.valor_ipi += trib['valor_ipi']
        self.base_pis += trib['base_pis']
        self.valor_pis += trib['valor_pis']
        self.base_cofins += trib['base_cofins']
        self.valor_cofins += trib['valor_cofins']


@dataclass
class ContextoApuracao:
    entrada: AcumuloLado = field(default_factory=AcumuloLado)
    saida: AcumuloLado = field(default_factory=AcumuloLado)
    reforma: TotaisReformaTributaria = field(default_factory=TotaisReformaTributaria)
    reforma_entrada: TotaisReformaTributaria = field(default_factory=TotaisReformaTributaria)
    reforma_saida: TotaisReformaTributaria = field(default_factory=TotaisReformaTributaria)
    reforma_cte: TotaisReformaTributaria = field(default_factory=TotaisReformaTributaria)
    alertas: list[dict[str, Any]] = field(default_factory=list)
    agrup_cfop: dict[str, AcumuloLado] = field(default_factory=lambda: defaultdict(AcumuloLado))
    agrup_ncm: dict[str, AcumuloLado] = field(default_factory=lambda: defaultdict(AcumuloLado))
    agrup_cst_icms: dict[str, AcumuloLado] = field(default_factory=lambda: defaultdict(AcumuloLado))
    agrup_cst_pis: dict[str, AcumuloLado] = field(default_factory=lambda: defaultdict(AcumuloLado))
    agrup_cst_cofins: dict[str, AcumuloLado] = field(default_factory=lambda: defaultdict(AcumuloLado))
    agrup_participante: dict[str, AcumuloLado] = field(default_factory=lambda: defaultdict(AcumuloLado))
    agrup_produto: dict[str, AcumuloLado] = field(default_factory=lambda: defaultdict(AcumuloLado))
    agrup_modelo: dict[str, AcumuloLado] = field(default_factory=lambda: defaultdict(AcumuloLado))
    agrup_uf: dict[str, AcumuloLado] = field(default_factory=lambda: defaultdict(AcumuloLado))
    notas_c100_ok: int = 0
    notas_sem_chave: int = 0
    notas_modelo_sped: int = 0
    itens_c170: int = 0
    itens_sem_ncm: int = 0
    c190_chaves: set[tuple[str, str, str]] = field(default_factory=set)
    notas_icmstot_pis_cofins: int = 0
    itens_cst_pis: int = 0
    itens_cst_cofins: int = 0
    itens_base_pis: int = 0
    itens_base_cofins: int = 0
    credito_entrada_itens: int = 0
    debito_saida_itens: int = 0


def _alert(
    ctx: ContextoApuracao,
    *,
    codigo: str,
    mensagem: str,
    severidade: str = 'warning',
    documento_tipo: str | None = None,
    documento_id: int | None = None,
    item_id: int | None = None,
    acao_sugerida: str | None = None,
) -> None:
    ctx.alertas.append(
        {
            'codigo': codigo,
            'severidade': severidade,
            'mensagem': mensagem,
            'documento_tipo': documento_tipo,
            'documento_id': documento_id,
            'item_id': item_id,
            'acao_sugerida': acao_sugerida,
        }
    )


def _uf_party(party: dict[str, Any] | None) -> str:
    if not party:
        return ''
    return str(party.get('UF') or party.get('uf') or '').strip().upper()[:2]


def _cnpj_party(party: dict[str, Any] | None) -> str:
    if not party:
        return ''
    for k in ('CNPJ', 'CPF', 'cNPJ', 'cPF'):
        if party.get(k):
            return ''.join(c for c in str(party[k]) if c.isdigit())
    return ''


def _filtra_itens_historicos(
    itens: list[Any],
    cfop: str | None,
    ncm: str | None,
) -> list[Any]:
    out = []
    for it in itens:
        pj = it.prod_json if isinstance(it.prod_json, dict) else {}
        if cfop and str(pj.get('CFOP') or '').strip() != cfop:
            continue
        if ncm and str(pj.get('NCM') or '').strip() != ncm:
            continue
        out.append(it)
    return out


def _agrupa_item(
    ctx: ContextoApuracao,
    *,
    cfop_k: str,
    ncm_k: str,
    cst_i: str,
    cst_p: str,
    cst_c: str,
    participante: str,
    prod_k: str,
    mod_k: str,
    uf_k: str,
    trib: dict[str, Any],
    valor_prod: Decimal,
) -> None:
    for bucket, key in (
        (ctx.agrup_cfop, cfop_k),
        (ctx.agrup_ncm, ncm_k),
        (ctx.agrup_cst_icms, cst_i),
        (ctx.agrup_cst_pis, cst_p),
        (ctx.agrup_cst_cofins, cst_c),
        (ctx.agrup_participante, participante),
        (ctx.agrup_produto, prod_k),
        (ctx.agrup_modelo, mod_k),
        (ctx.agrup_uf, uf_k),
    ):
        bucket[key].add_item_tributos(trib, valor_prod)


def _process_item_historico(
    ctx: ContextoApuracao,
    *,
    lado: str,
    nf: Any,
    it: Any,
    participante_label: str,
    party_uf: str,
    modelo: str,
    ac: AcumuloLado,
) -> None:
    pj = it.prod_json if isinstance(it.prod_json, dict) else {}
    ij = coercer_imposto_item_json(getattr(it, 'imposto_json', None))
    prod = extrair_produto_item(pj)
    trib = extrair_tributos_item(pj, ij)
    valor_prod = prod['valor_prod']
    ac.add_item_tributos(trib, valor_prod)

    cfop_k = prod['cfop'] or '(sem CFOP)'
    ncm_k = prod['ncm'] or '(sem NCM)'
    cst_i = trib['cst_icms'] or trib.get('csosn') or '(sem CST ICMS)'
    cst_p = trib['cst_pis'] or '(sem CST PIS)'
    cst_c = trib['cst_cofins'] or '(sem CST COFINS)'
    prod_k = prod['c_prod'] or prod['x_prod'] or '(sem código produto XML)'
    uf_k = party_uf or '(UF?)'
    mod_k = modelo or '(sem modelo)'

    _agrupa_item(
        ctx,
        cfop_k=cfop_k,
        ncm_k=ncm_k,
        cst_i=cst_i,
        cst_p=cst_p,
        cst_c=cst_c,
        participante=participante_label,
        prod_k=prod_k,
        mod_k=mod_k,
        uf_k=uf_k,
        trib=trib,
        valor_prod=valor_prod,
    )

    ctx.itens_c170 += 1
    if not prod['ncm']:
        ctx.itens_sem_ncm += 1
    ctx.c190_chaves.add((cfop_k, cst_i, mod_k))
    if trib['cst_pis']:
        ctx.itens_cst_pis += 1
    if trib['cst_cofins']:
        ctx.itens_cst_cofins += 1
    if trib['base_pis'] > 0:
        ctx.itens_base_pis += 1
    if trib['base_cofins'] > 0:
        ctx.itens_base_cofins += 1
    if lado == 'ENTRADA' and (trib['valor_pis'] > 0 or trib['valor_cofins'] > 0):
        ctx.credito_entrada_itens += 1
    if lado == 'SAIDA' and (trib['valor_pis'] > 0 or trib['valor_cofins'] > 0):
        ctx.debito_saida_itens += 1

    extras = [k for k in ij.keys() if k not in IMPOSTO_KEYS_PADRAO]
    if extras:
        ctx.reforma.itens_com_imposto_extra += 1
        if lado == 'ENTRADA':
            ctx.reforma_entrada.itens_com_imposto_extra += 1
        elif lado == 'SAIDA':
            ctx.reforma_saida.itens_com_imposto_extra += 1

    if not prod['ncm']:
        _alert(
            ctx,
            codigo='ITEM_SEM_NCM',
            mensagem='Item sem NCM no XML.',
            documento_tipo=type(nf).__name__,
            documento_id=nf.id,
            item_id=it.id,
        )
    if not prod['cfop']:
        _alert(
            ctx,
            codigo='ITEM_SEM_CFOP',
            mensagem='Item sem CFOP no XML.',
            documento_tipo=type(nf).__name__,
            documento_id=nf.id,
            item_id=it.id,
        )
    if not trib['cst_icms'] and not trib.get('csosn'):
        _alert(
            ctx,
            codigo='ITEM_SEM_CST_ICMS',
            mensagem='Item sem CST/CSOSN ICMS inferido do imposto_json.',
            documento_tipo=type(nf).__name__,
            documento_id=nf.id,
            item_id=it.id,
        )
    if not trib['cst_pis']:
        _alert(
            ctx,
            codigo='ITEM_SEM_CST_PIS',
            mensagem='Item sem CST PIS.',
            documento_tipo=type(nf).__name__,
            documento_id=nf.id,
            item_id=it.id,
        )
    if not trib['cst_cofins']:
        _alert(
            ctx,
            codigo='ITEM_SEM_CST_COFINS',
            mensagem='Item sem CST COFINS.',
            documento_tipo=type(nf).__name__,
            documento_id=nf.id,
            item_id=it.id,
        )


def _sped_doc_checks(ctx: ContextoApuracao, nf: Any, modelo: str) -> None:
    chave = (nf.chave_acesso or '').strip()
    if len(chave) != 44:
        ctx.notas_sem_chave += 1
        _alert(
            ctx,
            codigo='NOTA_SEM_CHAVE',
            mensagem='NF-e sem chave de acesso válida (44 dígitos).',
            documento_tipo=type(nf).__name__,
            documento_id=nf.id,
        )
    if modelo and not modelo_mapeado_sped_nfe(modelo):
        ctx.notas_modelo_sped += 1
        _alert(
            ctx,
            codigo='MODELO_SPED',
            mensagem=f'Modelo {modelo} não mapeado para SPED NFe (esperado 55/65).',
            documento_tipo=type(nf).__name__,
            documento_id=nf.id,
        )
    if len(chave) == 44 and modelo_mapeado_sped_nfe(modelo):
        ctx.notas_c100_ok += 1


def _process_nota_historica_saida(ctx: ContextoApuracao, nf: NFeSaidaHistoricaImportada, f: FiltrosApuracao) -> None:
    if not pode_entrar_apuracao(nf, incluir_canceladas=f.incluir_canceladas):
        return
    itens = list(nf.itens.all())
    itens = _filtra_itens_historicos(itens, f.cfop, f.ncm)
    if (f.cfop or f.ncm) and not itens:
        return
    modelo = str(nf.modelo or '').strip()
    if f.modelo_documento and modelo != f.modelo_documento.strip():
        return

    party = nf.dest_json if isinstance(nf.dest_json, dict) else {}
    participante = f'Cliente#{nf.cliente_id}' if nf.cliente_id else _cnpj_party(party) or 'Destinatário não vinculado'

    ctx.saida.quantidade_notas += 1
    ctx.saida.valor_documentos += historica_saida_valor_total(nf)

    ext_doc = extrair_totais_fiscais_documento(nf.totais_json)
    if ext_doc['pis_valor'] > 0 or ext_doc['cofins_valor'] > 0:
        ctx.notas_icmstot_pis_cofins += 1

    _aplicar_reforma_nfe_historica(ctx, nf, itens, 'SAIDA')

    _sped_doc_checks(ctx, nf, modelo)

    if nf.cancelada and f.incluir_canceladas:
        _alert(
            ctx,
            codigo='NOTA_CANCELADA_INCLUSA',
            mensagem='Nota cancelada incluída no período (filtro incluir_canceladas).',
            documento_tipo='NFeSaidaHistoricaImportada',
            documento_id=nf.id,
        )

    if not itens:
        _alert(
            ctx,
            codigo='NF_SEM_ITENS',
            mensagem='NF-e sem itens após filtros.',
            documento_tipo='NFeSaidaHistoricaImportada',
            documento_id=nf.id,
        )

    if nf.cliente_id:
        cli = nf.cliente
        doc_cnpj = ''.join(c for c in (cli.cnpj or '') if c.isdigit())
        if len(doc_cnpj) < 14:
            _alert(
                ctx,
                codigo='PARTICIPANTE_SEM_CNPJ',
                mensagem='Cliente vinculado sem CNPJ completo no cadastro.',
                documento_tipo='NFeSaidaHistoricaImportada',
                documento_id=nf.id,
            )
    elif not _cnpj_party(party):
        _alert(
            ctx,
            codigo='PARTICIPANTE_SEM_CNPJ',
            mensagem='Destinatário XML sem CPF/CNPJ e sem cliente vinculado.',
            documento_tipo='NFeSaidaHistoricaImportada',
            documento_id=nf.id,
        )

    uf = _uf_party(party)
    for it in itens:
        _process_item_historico(
            ctx,
            lado='SAIDA',
            nf=nf,
            it=it,
            participante_label=participante,
            party_uf=uf,
            modelo=modelo,
            ac=ctx.saida,
        )


def _process_nota_historica_entrada(ctx: ContextoApuracao, nf: NFeEntradaHistoricaImportada, f: FiltrosApuracao) -> None:
    if not pode_entrar_apuracao(nf, incluir_canceladas=f.incluir_canceladas):
        return
    itens = list(nf.itens.all())
    itens = _filtra_itens_historicos(itens, f.cfop, f.ncm)
    if (f.cfop or f.ncm) and not itens:
        return
    modelo = str(nf.modelo or '').strip()
    if f.modelo_documento and modelo != f.modelo_documento.strip():
        return

    party = nf.emit_json if isinstance(nf.emit_json, dict) else {}
    participante = f'Fornecedor#{nf.fornecedor_emitente_id}' if nf.fornecedor_emitente_id else _cnpj_party(party) or 'Emitente não vinculado'

    ctx.entrada.quantidade_notas += 1
    ctx.entrada.valor_documentos += nf.valor_total_nf or Decimal('0')

    ext_doc = extrair_totais_fiscais_documento(nf.totais_json)
    if ext_doc['pis_valor'] > 0 or ext_doc['cofins_valor'] > 0:
        ctx.notas_icmstot_pis_cofins += 1

    _aplicar_reforma_nfe_historica(ctx, nf, itens, 'ENTRADA')

    _sped_doc_checks(ctx, nf, modelo)

    if not itens:
        _alert(
            ctx,
            codigo='NF_SEM_ITENS',
            mensagem='NF-e sem itens após filtros.',
            documento_tipo='NFeEntradaHistoricaImportada',
            documento_id=nf.id,
        )

    if nf.fornecedor_emitente_id:
        forn = nf.fornecedor_emitente
        doc_cnpj = ''.join(c for c in (forn.cnpj or '') if c.isdigit())
        if len(doc_cnpj) < 14:
            _alert(
                ctx,
                codigo='PARTICIPANTE_SEM_CNPJ',
                mensagem='Fornecedor vinculado sem CNPJ completo no cadastro.',
                documento_tipo='NFeEntradaHistoricaImportada',
                documento_id=nf.id,
            )
    elif not _cnpj_party(party):
        _alert(
            ctx,
            codigo='PARTICIPANTE_SEM_CNPJ',
            mensagem='Emitente XML sem CPF/CNPJ e sem fornecedor vinculado.',
            documento_tipo='NFeEntradaHistoricaImportada',
            documento_id=nf.id,
        )

    uf = _uf_party(party)
    for it in itens:
        _process_item_historico(
            ctx,
            lado='ENTRADA',
            nf=nf,
            it=it,
            participante_label=participante,
            party_uf=uf,
            modelo=modelo,
            ac=ctx.entrada,
        )


def _process_nfe_interna_saida(ctx: ContextoApuracao, nf: NFeSaida, f: FiltrosApuracao) -> None:
    if not pode_entrar_apuracao(nf, incluir_canceladas=f.incluir_canceladas):
        return
    if f.cfop:
        return
    if f.modelo_documento and f.modelo_documento.upper() != 'INTERNA':
        return
    itens = list(nf.itens.all())
    itens_filtrados = []
    for it in itens:
        snap = it.snapshot_produto if isinstance(it.snapshot_produto, dict) else {}
        ncm_snap = str(snap.get('ncm_codigo_snapshot') or '').strip()
        if f.ncm and ncm_snap != f.ncm:
            continue
        itens_filtrados.append(it)
    if f.ncm and not itens_filtrados:
        return

    if f.status and f.status.strip().lower() not in (nf.status or '').lower():
        return

    ctx.saida.quantidade_notas += 1
    ctx.saida.valor_documentos += nf.valor_total or Decimal('0')
    total = sum((it.valor or Decimal('0')) * (it.quantidade or Decimal('0')) for it in itens_filtrados)
    ctx.saida.quantidade_itens += len(itens_filtrados)
    ctx.saida.valor_produtos += total

    _alert(
        ctx,
        codigo='NF_INTERNA_FISCAL',
        mensagem='NF-e interna do ERP sem XML: tributos ICMS/IPI/PIS/COFINS não extraídos automaticamente.',
        documento_tipo='NFeSaida',
        documento_id=nf.id,
        severidade='info',
    )

    if not itens_filtrados:
        _alert(ctx, codigo='NF_SEM_ITENS', mensagem='NF interna sem itens.', documento_tipo='NFeSaida', documento_id=nf.id)

    if nf.cliente_id:
        c = nf.cliente
        doc_cnpj = ''.join(c for c in (c.cnpj or '') if c.isdigit())
        if len(doc_cnpj) < 14:
            _alert(ctx, codigo='PARTICIPANTE_SEM_CNPJ', mensagem='Cliente sem CNPJ completo.', documento_tipo='NFeSaida', documento_id=nf.id)

    uf = (nf.cliente.uf or '').upper()[:2] if nf.cliente_id else ''
    cli_label = f'Cliente#{nf.cliente_id}'
    if itens_filtrados:
        _alert(
            ctx,
            codigo='ITEM_SEM_CFOP',
            mensagem='NF interna não possui CFOP por item no modelo atual (conferência por XML/histórico quando aplicável).',
            documento_tipo='NFeSaida',
            documento_id=nf.id,
            severidade='info',
        )
    for it in itens_filtrados:
        snap = it.snapshot_produto if isinstance(it.snapshot_produto, dict) else {}
        ncm_k = str(snap.get('ncm_codigo_snapshot') or '').strip() or '(sem NCM)'
        val = (it.valor or Decimal('0')) * (it.quantidade or Decimal('0'))
        if not str(snap.get('ncm_codigo_snapshot') or '').strip():
            _alert(ctx, codigo='ITEM_SEM_NCM', mensagem='Produto sem NCM efetivo no snapshot.', documento_tipo='NFeSaida', documento_id=nf.id, item_id=it.id)
        zt = {
            'base_icms': Decimal('0'),
            'valor_icms': Decimal('0'),
            'base_ipi': Decimal('0'),
            'valor_ipi': Decimal('0'),
            'base_pis': Decimal('0'),
            'valor_pis': Decimal('0'),
            'base_cofins': Decimal('0'),
            'valor_cofins': Decimal('0'),
        }
        _agrupa_item(
            ctx,
            cfop_k='(interna)',
            ncm_k=ncm_k,
            cst_i='(interna)',
            cst_p='(interna)',
            cst_c='(interna)',
            participante=cli_label,
            prod_k=str(snap.get('codigo_completo_snapshot') or it.produto_id),
            mod_k='INTERNA',
            uf_k=uf or '(UF?)',
            trib=zt,
            valor_prod=val,
        )


def _process_nfe_interna_entrada(ctx: ContextoApuracao, nf: NFeEntrada, f: FiltrosApuracao) -> None:
    if f.cfop:
        return
    if f.modelo_documento and f.modelo_documento.upper() != 'INTERNA':
        return
    itens = list(nf.itens.all())
    itens_filtrados = []
    for it in itens:
        snap = it.snapshot_produto if isinstance(it.snapshot_produto, dict) else {}
        ncm_snap = str(snap.get('ncm_codigo_snapshot') or '').strip()
        if f.ncm and ncm_snap != f.ncm:
            continue
        itens_filtrados.append(it)
    if f.ncm and not itens_filtrados:
        return

    ctx.entrada.quantidade_notas += 1
    ctx.entrada.valor_documentos += nf.valor_total or Decimal('0')
    total = sum((it.valor or Decimal('0')) * (it.quantidade or Decimal('0')) for it in itens_filtrados)
    ctx.entrada.quantidade_itens += len(itens_filtrados)
    ctx.entrada.valor_produtos += total

    _alert(
        ctx,
        codigo='NF_INTERNA_FISCAL',
        mensagem='NF-e interna do ERP sem XML: tributos não extraídos automaticamente.',
        documento_tipo='NFeEntrada',
        documento_id=nf.id,
        severidade='info',
    )

    if nf.fornecedor_id:
        fo = nf.fornecedor
        doc_cnpj = ''.join(c for c in (fo.cnpj or '') if c.isdigit())
        if len(doc_cnpj) < 14:
            _alert(ctx, codigo='PARTICIPANTE_SEM_CNPJ', mensagem='Fornecedor sem CNPJ completo.', documento_tipo='NFeEntrada', documento_id=nf.id)

    uf = (nf.fornecedor.uf or '').upper()[:2] if nf.fornecedor_id else ''
    forn_label = f'Fornecedor#{nf.fornecedor_id}'
    zt = {
        'base_icms': Decimal('0'),
        'valor_icms': Decimal('0'),
        'base_ipi': Decimal('0'),
        'valor_ipi': Decimal('0'),
        'base_pis': Decimal('0'),
        'valor_pis': Decimal('0'),
        'base_cofins': Decimal('0'),
        'valor_cofins': Decimal('0'),
    }
    for it in itens_filtrados:
        snap = it.snapshot_produto if isinstance(it.snapshot_produto, dict) else {}
        ncm_k = str(snap.get('ncm_codigo_snapshot') or '').strip() or '(sem NCM)'
        val = (it.valor or Decimal('0')) * (it.quantidade or Decimal('0'))
        if not str(snap.get('ncm_codigo_snapshot') or '').strip():
            _alert(ctx, codigo='ITEM_SEM_NCM', mensagem='Produto sem NCM efetivo no snapshot.', documento_tipo='NFeEntrada', documento_id=nf.id, item_id=it.id)
        _agrupa_item(
            ctx,
            cfop_k='(interna)',
            ncm_k=ncm_k,
            cst_i='(interna)',
            cst_p='(interna)',
            cst_c='(interna)',
            participante=forn_label,
            prod_k=str(snap.get('codigo_completo_snapshot') or it.produto_id),
            mod_k='INTERNA',
            uf_k=uf or '(UF?)',
            trib=zt,
            valor_prod=val,
        )


def _serialize_acumulo(a: AcumuloLado) -> dict[str, Any]:
    return {
        'quantidade_notas': a.quantidade_notas,
        'quantidade_itens': a.quantidade_itens,
        'valor_documentos': _money_float(a.valor_documentos),
        'valor_produtos': _money_float(a.valor_produtos),
        'base_icms': _money_float(a.base_icms),
        'valor_icms': _money_float(a.valor_icms),
        'base_ipi': _money_float(a.base_ipi),
        'valor_ipi': _money_float(a.valor_ipi),
        'base_pis': _money_float(a.base_pis),
        'valor_pis': _money_float(a.valor_pis),
        'base_cofins': _money_float(a.base_cofins),
        'valor_cofins': _money_float(a.valor_cofins),
    }


def _saldo_gerencial(e: AcumuloLado, s: AcumuloLado) -> dict[str, Any]:
    return {
        'valor_documentos': _money_float(s.valor_documentos - e.valor_documentos),
        'valor_produtos': _money_float(s.valor_produtos - e.valor_produtos),
        'base_icms': _money_float(s.base_icms - e.base_icms),
        'valor_icms': _money_float(s.valor_icms - e.valor_icms),
        'base_ipi': _money_float(s.base_ipi - e.base_ipi),
        'valor_ipi': _money_float(s.valor_ipi - e.valor_ipi),
        'base_pis': _money_float(s.base_pis - e.base_pis),
        'valor_pis': _money_float(s.valor_pis - e.valor_pis),
        'base_cofins': _money_float(s.base_cofins - e.base_cofins),
        'valor_cofins': _money_float(s.valor_cofins - e.valor_cofins),
    }


def _serialize_agrupamentos(d: dict[str, AcumuloLado]) -> list[dict[str, Any]]:
    return [{'chave': k, **_serialize_acumulo(v)} for k, v in sorted(d.items(), key=lambda x: x[0])]


def _icms_ipi_documento_vs_itens(_ctx: ContextoApuracao) -> dict[str, Any]:
    """Comparativo opcional: totais documento ICMSTot não somados no acumulo de itens (evita duplicidade)."""
    return {
        'observacao': 'Totais ICMS/IPI/PIS/COFINS da aba principal são somados por item (XML). Totais por documento (ICMSTot) podem divergir por arredondamento.',
    }


def _montar_payload_reforma(ctx: ContextoApuracao) -> dict[str, Any]:
    """Totais consolidados (NF-e + CT-e) e detalhamento por NF entrada, NF saída e CT-e."""
    out = ctx.reforma.to_serializable()
    out['por_documento'] = {
        'entrada': ctx.reforma_entrada.to_serializable(),
        'saida': ctx.reforma_saida.to_serializable(),
        'cte': ctx.reforma_cte.to_serializable(),
    }
    return out


def _diagnostico_reforma_resumo(
    ctx: ContextoApuracao,
    *,
    candidatas_entrada_historica: int,
    candidatas_saida_historica: int,
) -> dict[str, Any]:
    """Resumo enxuto para conferência (CBS/IBS por lado + candidatas históricas)."""

    def _fatia(ac: TotaisReformaTributaria) -> dict[str, Any]:
        s = ac.to_serializable()
        return {
            'valor_cbs': s.get('valor_cbs'),
            'valor_ibs_total': s.get('valor_ibs_total'),
            'valor_ibs_uf': s.get('valor_ibs_uf'),
            'valor_ibs_municipio': s.get('valor_ibs_municipio'),
            'base_cbs': s.get('base_cbs'),
            'itens_com_tags_ibscbs': s.get('itens_com_tags_ibscbs'),
            'itens_com_valores_ibscbs': s.get('itens_com_valores_ibscbs'),
            'notas_com_ibscbstot': s.get('notas_com_ibscbstot'),
        }

    return {
        'candidatas_entrada_historica': candidatas_entrada_historica,
        'candidatas_saida_historica': candidatas_saida_historica,
        'entrada': _fatia(ctx.reforma_entrada),
        'saida': _fatia(ctx.reforma_saida),
        'cte': _fatia(ctx.reforma_cte),
        'consolidado': _fatia(ctx.reforma),
    }


def build_apuracao_fiscal(query_params: dict[str, Any]) -> dict[str, Any]:
    f = FiltrosApuracao.from_querydict(query_params)
    ctx = ContextoApuracao()
    tipo = f.tipo if f.tipo in {'ENTRADA', 'SAIDA', 'AMBOS'} else 'AMBOS'
    fonte = f.fonte if f.fonte in {'TODOS', 'OPERACIONAIS', 'HISTORICOS'} else 'TODOS'

    if f.empresa_id:
        try:
            emp = Empresa.objects.get(pk=f.empresa_id)
            if not (emp.ie or '').strip():
                _alert(ctx, codigo='EMPRESA_SEM_IE', mensagem=f'Empresa {emp.id} sem inscrição estadual cadastrada.', severidade='warning')
        except Empresa.DoesNotExist:
            _alert(ctx, codigo='EMPRESA_INVALIDA', mensagem='empresa_id não encontrado.', severidade='error')

    em_ini, em_fim = _range_datetime_emissao(f.data_inicio, f.data_fim)
    diag_saida = _diagnostico_fontes_saida_historica(f, em_ini, em_fim)
    diag_entrada = _diagnostico_fontes_entrada_historica(f, em_ini, em_fim)
    diagnostico_fontes = {**diag_saida, **diag_entrada}

    qs_saida_hist = NFeSaidaHistoricaImportada.objects.select_related('cliente', 'empresa_emitente').prefetch_related(
        Prefetch('itens', queryset=ItemNFeSaidaHistoricaImportada.objects.order_by('n_item'))
    )
    qs_entrada_hist = NFeEntradaHistoricaImportada.objects.select_related('fornecedor_emitente', 'empresa_destinataria').prefetch_related(
        Prefetch('itens', queryset=ItemNFeEntradaHistoricaImportada.objects.order_by('n_item'))
    )

    qs_saida_hist = _filtro_empresa_saida_historica(qs_saida_hist, f)
    qs_entrada_hist = _filtro_empresa_entrada_historica(qs_entrada_hist, f)

    qs_saida_hist = filtrar_queryset_apuracao_historica_saida(qs_saida_hist)
    qs_entrada_hist = filtrar_queryset_apuracao_historica_entrada(qs_entrada_hist)

    qs_saida_hist = qs_saida_hist.filter(dh_emissao__gte=em_ini, dh_emissao__lte=em_fim)
    qs_entrada_hist = qs_entrada_hist.filter(dh_emissao__gte=em_ini, dh_emissao__lte=em_fim)

    # Sem filtro de status explícito: só documentos autorizados em produção (homologação sempre fora).
    if not f.status:
        qs_saida_hist = qs_saida_hist.filter(_q_autorizada_saida_historica())
        qs_entrada_hist = qs_entrada_hist.filter(_q_autorizada_entrada_historica())

    if f.cliente_id:
        qs_saida_hist = qs_saida_hist.filter(cliente_id=f.cliente_id)
    if f.fornecedor_id:
        qs_entrada_hist = qs_entrada_hist.filter(fornecedor_emitente_id=f.fornecedor_id)

    if f.status:
        qs_saida_hist = _aplica_filtro_status_saida_historica(qs_saida_hist, f.status)

    if not f.incluir_canceladas:
        qs_saida_hist = qs_saida_hist.filter(cancelada=False)

    if f.cfop:
        qs_saida_hist = qs_saida_hist.filter(
            Exists(ItemNFeSaidaHistoricaImportada.objects.filter(nf_id=OuterRef('pk'), prod_json__CFOP=f.cfop))
        )
        qs_entrada_hist = qs_entrada_hist.filter(
            Exists(ItemNFeEntradaHistoricaImportada.objects.filter(nf_id=OuterRef('pk'), prod_json__CFOP=f.cfop))
        )
    if f.ncm:
        qs_saida_hist = qs_saida_hist.filter(Exists(ItemNFeSaidaHistoricaImportada.objects.filter(nf_id=OuterRef('pk'), prod_json__NCM=f.ncm)))
        qs_entrada_hist = qs_entrada_hist.filter(
            Exists(ItemNFeEntradaHistoricaImportada.objects.filter(nf_id=OuterRef('pk'), prod_json__NCM=f.ncm))
        )

    qs_hist_saida_sem_empresa = NFeSaidaHistoricaImportada.objects.filter(dh_emissao__gte=em_ini, dh_emissao__lte=em_fim)
    if not f.incluir_canceladas:
        qs_hist_saida_sem_empresa = qs_hist_saida_sem_empresa.filter(cancelada=False)
    saidas_historicas_periodo_sem_filtro_empresa = qs_hist_saida_sem_empresa.count()

    qs_hist_entrada_sem_empresa = NFeEntradaHistoricaImportada.objects.filter(dh_emissao__gte=em_ini, dh_emissao__lte=em_fim)
    entradas_historicas_periodo_sem_filtro_empresa = qs_hist_entrada_sem_empresa.count()

    candidatas_saida_historica = qs_saida_hist.count()
    candidatas_entrada_historica = qs_entrada_hist.count()

    # Não usar .iterator() aqui: com prefetch_related o iterator ignora o cache de prefetch no Django
    # e pode deixar de materializar itens em alguns cenários; o loop normal usa o prefetch de `itens`.
    if tipo in {'SAIDA', 'AMBOS'} and fonte in {'TODOS', 'HISTORICOS'}:
        for nf in qs_saida_hist:
            _process_nota_historica_saida(ctx, nf, f)

    if tipo in {'ENTRADA', 'AMBOS'} and fonte in {'TODOS', 'HISTORICOS'}:
        for nf in qs_entrada_hist:
            _process_nota_historica_entrada(ctx, nf, f)

    ctes_escaneados_reforma = 0
    if _apuracao_escaneia_cte_reforma(f):
        qs_cte = CTeHistoricoImportado.objects.filter(dh_emissao__gte=em_ini, dh_emissao__lte=em_fim)
        qs_cte = filtrar_queryset_apuracao_cte(qs_cte)
        if not f.incluir_canceladas:
            qs_cte = qs_cte.filter(cancelado=False)
        qs_cte = _filtro_empresa_cte_historico(qs_cte, f)
        for cte in qs_cte.only('id', 'imposto_json').iterator(chunk_size=200):
            ctes_escaneados_reforma += 1
            ctot, _cal, cstats = processar_reforma_cte_imposto(cte.imposto_json)
            merge_totais_reforma(ctx.reforma, ctot)
            merge_totais_reforma(ctx.reforma_cte, ctot)
            merge_stats_reforma_cte(ctx.reforma, cstats)
            merge_stats_reforma_cte(ctx.reforma_cte, cstats)

    qs_ns = NFeSaida.objects.select_related('cliente', 'pedido_venda').prefetch_related('itens')
    qs_ne = NFeEntrada.objects.select_related('fornecedor').prefetch_related('itens')
    qs_ns = filtrar_queryset_apuracao_nfe_saida(qs_ns)
    qs_ns = qs_ns.filter(data__gte=f.data_inicio, data__lte=f.data_fim)
    qs_ne = qs_ne.filter(data__gte=f.data_inicio, data__lte=f.data_fim)
    if f.empresa_id:
        qs_ns = qs_ns.filter(pedido_venda__empresa_emitente_id=f.empresa_id)
        qs_ne = NFeEntrada.objects.none()
        if tipo in {'ENTRADA', 'AMBOS'}:
            _alert(
                ctx,
                codigo='NF_INTERNA_ENTRADA_EMPRESA',
                mensagem='NF-e de entrada interna (ERP) omitida quando filtro empresa_id está ativo; use NF entrada histórica/XML vinculada à empresa destinatária.',
                severidade='info',
            )
    if f.cliente_id:
        qs_ns = qs_ns.filter(cliente_id=f.cliente_id)
    if f.fornecedor_id:
        qs_ne = qs_ne.filter(fornecedor_id=f.fornecedor_id)
    if f.status:
        qs_ns = qs_ns.filter(status__icontains=f.status.strip())

    candidatas_saida_operacional = qs_ns.count()
    candidatas_entrada_operacional = qs_ne.count()

    h_s = candidatas_saida_historica if fonte in {'TODOS', 'HISTORICOS'} else 0
    h_e = candidatas_entrada_historica if fonte in {'TODOS', 'HISTORICOS'} else 0
    o_s = candidatas_saida_operacional if fonte in {'TODOS', 'OPERACIONAIS'} else 0
    o_e = candidatas_entrada_operacional if fonte in {'TODOS', 'OPERACIONAIS'} else 0
    if tipo == 'ENTRADA':
        candidatas_aplicaveis_tipo = h_e + o_e
    elif tipo == 'SAIDA':
        candidatas_aplicaveis_tipo = h_s + o_s
    else:
        candidatas_aplicaveis_tipo = h_s + h_e + o_s + o_e

    if tipo in {'SAIDA', 'AMBOS'} and fonte in {'TODOS', 'OPERACIONAIS'}:
        for nf in qs_ns.iterator(chunk_size=200):
            _process_nfe_interna_saida(ctx, nf, f)
    if tipo in {'ENTRADA', 'AMBOS'} and fonte in {'TODOS', 'OPERACIONAIS'}:
        for nf in qs_ne.iterator(chunk_size=200):
            _process_nfe_interna_entrada(ctx, nf, f)

    tem_saida_hist_periodo = int(diagnostico_fontes.get('saidas_historicas_no_periodo') or 0) > 0
    tem_entrada_hist_periodo = int(diagnostico_fontes.get('entradas_historicas_no_periodo') or 0) > 0
    tem_hist_periodo_por_tipo = (tipo != 'ENTRADA' and tem_saida_hist_periodo) or (tipo != 'SAIDA' and tem_entrada_hist_periodo)

    if (
        ctx.entrada.quantidade_notas == 0
        and ctx.saida.quantidade_notas == 0
        and candidatas_aplicaveis_tipo == 0
        and not any(a.get('codigo') == 'EMPRESA_INVALIDA' for a in ctx.alertas)
    ):
        if tem_hist_periodo_por_tipo and fonte in {'TODOS', 'HISTORICOS'}:
            _alert(
                ctx,
                codigo='NF_HISTORICAS_FILTRO',
                mensagem=(
                    'Existem NF-e(s) importada(s) no período (XML/histórico), mas nenhuma corresponde aos filtros '
                    'selecionados (empresa, status, CFOP/NCM, tipo, fonte ou exclusão de canceladas).'
                ),
                severidade='warning',
            )
        else:
            _alert(
                ctx,
                codigo='NENHUMA_NF',
                mensagem='Nenhuma NF-e encontrada no período com os filtros aplicados.',
                severidade='info',
            )

    if (
        f.empresa_id
        and candidatas_saida_historica == 0
        and candidatas_entrada_historica == 0
        and (saidas_historicas_periodo_sem_filtro_empresa > 0 or entradas_historicas_periodo_sem_filtro_empresa > 0)
    ):
        _alert(
            ctx,
            codigo='EMPRESA_EXCLUI_TODAS_NF_HIST',
            mensagem=(
                f'Existem NF-e importadas no período (saída hist.: {saidas_historicas_periodo_sem_filtro_empresa}, '
                f'entrada hist.: {entradas_historicas_periodo_sem_filtro_empresa}), mas nenhuma vinculada à empresa '
                f'selecionada (emitente/destinatário). Use Empresa = Todas ou ajuste o cadastro da NF.'
            ),
            severidade='warning',
        )

    hist_analisadas = candidatas_saida_historica + candidatas_entrada_historica
    reforma_sem_valor_nem_tag = (
        ctx.reforma.valor_cbs == 0
        and ctx.reforma.valor_ibs_uf == 0
        and ctx.reforma.valor_ibs_municipio == 0
        and ctx.reforma.valor_is == 0
        and ctx.reforma.itens_com_tags_ibscbs == 0
        and ctx.reforma.notas_com_ibscbstot == 0
        and ctx.reforma.cte_com_ibscbs_tags == 0
    )
    if hist_analisadas > 0 and fonte in {'TODOS', 'HISTORICOS'} and reforma_sem_valor_nem_tag:
        _alert(
            ctx,
            codigo='REFORMA_SEM_TAGS_XML',
            mensagem=(
                'NF-e histórica (XML) entrou na apuração, porém nenhum valor CBS/IBS/IS foi somado: o JSON importado '
                'não contém os blocos mapeados (item det/imposto/IBSCBS com gIBSCBS, ou total/IBSCBSTot). '
                'Isso é esperado enquanto a SEFAZ não emitir NF-e com o layout da Reforma Tributária; '
                'ICMS/PIS/COFINS continuam vindo dos campos atuais do XML.'
            ),
            severidade='info',
        )

    eventos_cancel_pendentes = EventoNFeSaidaHistoricaPendente.objects.filter(
        status=EventoNFeSaidaHistoricaPendente.Status.PENDENTE,
        tipo_evento='110111',
    ).count()
    if eventos_cancel_pendentes:
        _alert(
            ctx,
            codigo='EVENTO_CANCEL_PENDENTE',
            mensagem='Existe evento de cancelamento pendente sem NF-e correspondente na base.',
            severidade='warning',
            acao_sugerida=(
                'Importe o XML completo da NF-e correspondente ou mantenha o evento pendente para conciliação.'
            ),
        )

    reforma_payload = _montar_payload_reforma(ctx)
    diagnostico_reforma = _diagnostico_reforma_resumo(
        ctx,
        candidatas_entrada_historica=candidatas_entrada_historica,
        candidatas_saida_historica=candidatas_saida_historica,
    )
    efd_icms = montar_base_efd_icms_ipi(
        notas_c100_candidatas=ctx.notas_c100_ok,
        notas_sem_chave=ctx.notas_sem_chave,
        notas_modelo_nao_mapeado=ctx.notas_modelo_sped,
        itens_c170_candidatos=ctx.itens_c170,
        itens_sem_produto_0150=0,
        itens_sem_ncm_0200=ctx.itens_sem_ncm,
        grupamentos_c190_possiveis=len(ctx.c190_chaves),
        alertas=[
            '0150: cadastro de participante depende de vínculo Cliente/Fornecedor ou dados emit/dest do XML.',
            '0200: produto SPED requer NCM consistente nos itens.',
        ],
    )
    efd_contrib = montar_base_efd_contribuicoes(
        notas_com_pis_cofins_doc=ctx.notas_icmstot_pis_cofins,
        itens_com_cst_pis=ctx.itens_cst_pis,
        itens_com_cst_cofins=ctx.itens_cst_cofins,
        itens_base_pis_preenchida=ctx.itens_base_pis,
        itens_base_cofins_preenchida=ctx.itens_base_cofins,
        creditos_entrada_possiveis=ctx.credito_entrada_itens,
        debitos_saida_possiveis=ctx.debito_saida_itens,
        alertas=[
            'Créditos de entrada e débitos de saída são contagem gerencial por item com valor PIS/COFINS > 0.',
            'Regime tributário e apropriação de crédito não parametrizados nesta versão.',
        ],
    )

    cards = {
        'notas_entrada': ctx.entrada.quantidade_notas,
        'notas_saida': ctx.saida.quantidade_notas,
        'valor_entradas': _money_float(ctx.entrada.valor_documentos),
        'valor_saidas': _money_float(ctx.saida.valor_documentos),
        'icms_entrada': _money_float(ctx.entrada.valor_icms),
        'icms_saida': _money_float(ctx.saida.valor_icms),
        'ipi_entrada': _money_float(ctx.entrada.valor_ipi),
        'ipi_saida': _money_float(ctx.saida.valor_ipi),
        'pis_entrada': _money_float(ctx.entrada.valor_pis),
        'pis_saida': _money_float(ctx.saida.valor_pis),
        'cofins_entrada': _money_float(ctx.entrada.valor_cofins),
        'cofins_saida': _money_float(ctx.saida.valor_cofins),
        'cbs': _money_float(ctx.reforma.valor_cbs),
        'ibs_uf': _money_float(ctx.reforma.valor_ibs_uf),
        'ibs_municipio': _money_float(ctx.reforma.valor_ibs_municipio),
        'ibs': _money_float(ctx.reforma.valor_ibs_uf + ctx.reforma.valor_ibs_municipio),
        'ibs_total': _money_float(ctx.reforma.valor_ibs_uf + ctx.reforma.valor_ibs_municipio),
        'is': _money_float(ctx.reforma.valor_is),
        'cbs_entrada': _money_float(ctx.reforma_entrada.valor_cbs),
        'cbs_saida': _money_float(ctx.reforma_saida.valor_cbs),
        'cbs_cte': _money_float(ctx.reforma_cte.valor_cbs),
        'ibs_total_entrada': _money_float(ctx.reforma_entrada.valor_ibs_uf + ctx.reforma_entrada.valor_ibs_municipio),
        'ibs_total_saida': _money_float(ctx.reforma_saida.valor_ibs_uf + ctx.reforma_saida.valor_ibs_municipio),
        'ibs_total_cte': _money_float(ctx.reforma_cte.valor_ibs_uf + ctx.reforma_cte.valor_ibs_municipio),
        'base_cbs_entrada': _money_float(ctx.reforma_entrada.base_cbs),
        'base_cbs_saida': _money_float(ctx.reforma_saida.base_cbs),
        'base_cbs_cte': _money_float(ctx.reforma_cte.base_cbs),
        'alertas': len(ctx.alertas),
        'eventos_pendentes': eventos_cancel_pendentes,
    }

    fontes = {
        'saidas_historicas_candidatas': candidatas_saida_historica,
        'entradas_historicas_candidatas': candidatas_entrada_historica,
        'saidas_operacionais_candidatas': candidatas_saida_operacional,
        'entradas_operacionais_candidatas': candidatas_entrada_operacional,
        'saidas_historicas_periodo_sem_filtro_empresa': saidas_historicas_periodo_sem_filtro_empresa,
        'entradas_historicas_periodo_sem_filtro_empresa': entradas_historicas_periodo_sem_filtro_empresa,
        'candidatas_aplicaveis_tipo': candidatas_aplicaveis_tipo,
        'ctes_historicos_escaneados_reforma': ctes_escaneados_reforma,
    }

    diagnostico = {
        'models_utilizados': [
            'NFeEntradaHistoricaImportada / ItemNFeEntradaHistoricaImportada (XML)',
            'NFeSaidaHistoricaImportada / ItemNFeSaidaHistoricaImportada (XML)',
            'CTeHistoricoImportado (XML; CBS/IBS somados no total consolidado e em por_documento.cte)',
            'NFeEntrada / ItemNFeEntrada (operacional, sem tributos por item)',
            'NFeSaida / ItemNFeSaida (operacional, sem tributos por item)',
            'Empresa (ie, regime_tributario parcial)',
        ],
        'campos_fiscais_xml': [
            'NF saída histórica: dh_emissao, valor_total_nf, valor_produtos, status_documento, cstat, cancelada, empresa_emitente_id, emit_json, dest_json, totais_json, itens (prod_json, imposto_json)',
            'Chave, modelo, série, número, totais_json.ICMSTot, prod_json (NCM, CFOP), imposto_json (ICMS, IPI, PIS, COFINS)',
            'reforma_e_outros_json: tags extras do infNFe + snapshot ibscbs_total (IBSCBSTot) quando existir; CT-e: ibscbs em imposto_json',
        ],
        'campos_ausentes_sped_reforma': [
            'CST/valores CBS/IBS/IS em colunas dedicadas por item (hoje consolidados a partir de imposto_json / totais_json)',
            'Apuração persistente, fechamento de período, perfil SPED, indicadores de apropriação',
            'Totais CBS/IBS de CT-e somados ao total geral da Reforma (detalhe em reforma_tributaria.por_documento.cte)',
        ],
        'impacto': 'SPED exige consistência NCM/CFOP/CST e cadastros 0150/0200; reforma exige layout de tributos no XML.',
    }

    return {
        'meta': {
            'versao_api_apuracao': '2026.1',
            'pre_validacao': True,
            'sped_txt_oficial': False,
            'calculo': 'on_demand',
            'parametros_fiscais_futuros': {
                'regime_tributario': 'Cadastro Empresa.regime_tributario (texto livre; sem perfil SPED amarrado)',
                'perfil_sped': None,
                'indicador_tipo_atividade': None,
                'indicador_apropriacao_credito': None,
                'indicador_metodo_apropriacao_credito': None,
                'contador_responsavel': None,
            },
        },
        'filtros': {
            'empresa_id': f.empresa_id,
            'data_inicio': f.data_inicio.isoformat(),
            'data_fim': f.data_fim.isoformat(),
            'tipo': tipo,
            'fonte': fonte,
            'status': f.status,
            'cliente_id': f.cliente_id,
            'fornecedor_id': f.fornecedor_id,
            'cfop': f.cfop,
            'ncm': f.ncm,
            'modelo_documento': f.modelo_documento,
            'incluir_canceladas': f.incluir_canceladas,
        },
        'diagnostico_fontes': diagnostico_fontes,
        'fontes': fontes,
        'cards': cards,
        'resumo': {
            'entrada': _serialize_acumulo(ctx.entrada),
            'saida': _serialize_acumulo(ctx.saida),
            'saldo_gerencial_saida_menos_entrada': _saldo_gerencial(ctx.entrada, ctx.saida),
        },
        'icms_ipi': {
            'entrada': _serialize_acumulo(ctx.entrada),
            'saida': _serialize_acumulo(ctx.saida),
            'comparativo_documento': _icms_ipi_documento_vs_itens(ctx),
        },
        'pis_cofins': {
            'entrada': _serialize_acumulo(ctx.entrada),
            'saida': _serialize_acumulo(ctx.saida),
        },
        'reforma_tributaria': reforma_payload,
        'diagnostico_reforma': diagnostico_reforma,
        'efd_icms_ipi': efd_icms,
        'efd_contribuicoes': efd_contrib,
        'agrupamentos': {
            'por_cfop': _serialize_agrupamentos(ctx.agrup_cfop),
            'por_ncm': _serialize_agrupamentos(ctx.agrup_ncm),
            'por_cst_icms': _serialize_agrupamentos(ctx.agrup_cst_icms),
            'por_cst_pis': _serialize_agrupamentos(ctx.agrup_cst_pis),
            'por_cst_cofins': _serialize_agrupamentos(ctx.agrup_cst_cofins),
            'por_participante': _serialize_agrupamentos(ctx.agrup_participante),
            'por_produto': _serialize_agrupamentos(ctx.agrup_produto),
            'por_modelo_documento': _serialize_agrupamentos(ctx.agrup_modelo),
            'por_uf': _serialize_agrupamentos(ctx.agrup_uf),
        },
        'alertas': ctx.alertas,
        'diagnostico': diagnostico,
    }
