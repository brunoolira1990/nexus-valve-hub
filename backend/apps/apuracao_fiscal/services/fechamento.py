"""Serviços de criação, fechamento e reabertura de apuração fiscal (F1)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.cadastros.models import Empresa
from apps.fiscal.services.apuracao_fiscal import build_apuracao_fiscal

from ..models import ApuracaoFiscal, ApuracaoItem, ApuracaoReforma, LogsAuditoriaApuracao

# Limite de itens persistidos a partir de agrupamentos (V1)
_MAX_ITENS_AGRUPAMENTO = 500


class ApuracaoFiscalError(Exception):
    """Erro de regra de negócio na apuração persistida."""

    def __init__(self, message: str, *, codigo: str = 'APURACAO_ERRO'):
        super().__init__(message)
        self.codigo = codigo
        self.message = message


def _dec(v: Any) -> Decimal:
    try:
        return Decimal(str(v if v is not None else 0))
    except Exception:
        return Decimal('0')


def _parse_date(val: Any) -> date:
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    s = str(val or '').strip()[:10]
    return date.fromisoformat(s)


def periodo_fiscal_fechado(
    empresa_id: int,
    data_inicio: date | str,
    data_fim: date | str,
    *,
    excluir_apuracao_id: int | None = None,
) -> bool:
    """True se já existe apuração FECHADA para empresa + período exato."""
    di = _parse_date(data_inicio)
    df = _parse_date(data_fim)
    qs = ApuracaoFiscal.objects.filter(
        empresa_id=empresa_id,
        data_inicio=di,
        data_fim=df,
        status=ApuracaoFiscal.Status.FECHADO,
    )
    if excluir_apuracao_id:
        qs = qs.exclude(pk=excluir_apuracao_id)
    return qs.exists()


def _registrar_log(
    apuracao: ApuracaoFiscal,
    *,
    acao: str,
    usuario,
    detalhe: dict[str, Any] | None = None,
) -> LogsAuditoriaApuracao:
    return LogsAuditoriaApuracao.objects.create(
        apuracao=apuracao,
        usuario=usuario if getattr(usuario, 'pk', None) else None,
        acao=acao,
        detalhe=detalhe or {},
    )


def _aplicar_totais_do_payload(apuracao: ApuracaoFiscal, payload: dict[str, Any]) -> None:
    cards = payload.get('cards') or {}
    saldo = (payload.get('resumo') or {}).get('saldo_gerencial_saida_menos_entrada') or {}
    apuracao.valor_entradas = _dec(cards.get('valor_entradas'))
    apuracao.valor_saidas = _dec(cards.get('valor_saidas'))
    apuracao.icms_credito = _dec(cards.get('icms_entrada'))
    apuracao.icms_debito = _dec(cards.get('icms_saida'))
    apuracao.icms_st_debito = _dec(cards.get('icms_st_debito_entrada')) + _dec(
        cards.get('icms_st_debito_saida')
    )
    apuracao.difal_valor = _dec(cards.get('difal_icms_uf_dest'))
    apuracao.ipi_credito = _dec(cards.get('ipi_entrada'))
    apuracao.ipi_debito = _dec(cards.get('ipi_saida'))
    apuracao.pis_credito = _dec(cards.get('pis_credito'))
    apuracao.pis_debito = _dec(cards.get('pis_debito'))
    apuracao.cofins_credito = _dec(cards.get('cofins_credito'))
    apuracao.cofins_debito = _dec(cards.get('cofins_debito'))
    apuracao.saldo_icms = _dec(saldo.get('valor_icms'))
    apuracao.totais_json = {
        'cards': cards,
        'saldo_gerencial': saldo,
        'regime_tributario': payload.get('regime_tributario'),
    }
    apuracao.filtros_json = payload.get('filtros') or {}
    apuracao.payload_snapshot = payload
    meta = payload.get('meta') or {}
    apuracao.versao_api_apuracao = str(meta.get('versao_api_apuracao') or '')[:32]


def _montar_query_params(data: dict[str, Any]) -> dict[str, Any]:
    return {
        'empresa_id': data.get('empresa_id'),
        'data_inicio': data.get('data_inicio'),
        'data_fim': data.get('data_fim'),
        'tipo': data.get('tipo') or 'AMBOS',
        'fonte': data.get('fonte') or 'TODOS',
        'status': data.get('status') or '',
        'cliente_id': data.get('cliente_id') or '',
        'fornecedor_id': data.get('fornecedor_id') or '',
        'cfop': data.get('cfop') or '',
        'ncm': data.get('ncm') or '',
        'modelo_documento': data.get('modelo_documento') or '',
        'incluir_canceladas': data.get('incluir_canceladas') or False,
    }


def _persistir_itens_agrupamento(apuracao: ApuracaoFiscal, payload: dict[str, Any]) -> int:
    """Grava itens a partir de agrupamentos por CFOP (cap V1)."""
    ApuracaoItem.objects.filter(apuracao=apuracao).delete()
    agrup = (payload.get('agrupamentos') or {}).get('por_cfop') or []
    criados = 0
    batch: list[ApuracaoItem] = []
    for row in agrup[:_MAX_ITENS_AGRUPAMENTO]:
        chave = str(row.get('chave') or '')[:128]
        batch.append(
            ApuracaoItem(
                apuracao=apuracao,
                lado=ApuracaoItem.Lado.AMBOS,
                origem_tipo=ApuracaoItem.OrigemTipo.AGRUPAMENTO_CFOP,
                chave=chave,
                cfop=chave[:8] if chave and not chave.startswith('(') else '',
                quantidade_itens=int(row.get('quantidade_itens') or 0),
                valor_produtos=_dec(row.get('valor_produtos')),
                base_icms=_dec(row.get('base_icms')),
                valor_icms=_dec(row.get('valor_icms')),
                base_icms_st=_dec(row.get('base_icms_st')),
                valor_icms_st=_dec(row.get('valor_icms_st')),
                valor_fcp_st=_dec(row.get('valor_fcp_st')),
                valor_icms_uf_dest=_dec(row.get('valor_icms_uf_dest')),
                base_ipi=_dec(row.get('base_ipi')),
                valor_ipi=_dec(row.get('valor_ipi')),
                base_pis=_dec(row.get('base_pis')),
                valor_pis=_dec(row.get('valor_pis')),
                base_cofins=_dec(row.get('base_cofins')),
                valor_cofins=_dec(row.get('valor_cofins')),
                detalhe_json={
                    'valor_pis_credito': row.get('valor_pis_credito'),
                    'valor_cofins_credito': row.get('valor_cofins_credito'),
                },
            )
        )
        criados += 1
    if batch:
        ApuracaoItem.objects.bulk_create(batch)
    return criados


@transaction.atomic
def criar_rascunho(dados: dict[str, Any], *, usuario) -> ApuracaoFiscal:
    """Cria (ou atualiza) rascunho a partir do cálculo on-demand atual."""
    empresa_id = int(dados.get('empresa_id') or 0)
    if not empresa_id:
        raise ApuracaoFiscalError('empresa_id é obrigatório.', codigo='EMPRESA_OBRIGATORIA')
    try:
        Empresa.objects.get(pk=empresa_id)
    except Empresa.DoesNotExist as exc:
        raise ApuracaoFiscalError('Empresa não encontrada.', codigo='EMPRESA_INVALIDA') from exc

    di = _parse_date(dados.get('data_inicio'))
    df = _parse_date(dados.get('data_fim'))
    if df < di:
        raise ApuracaoFiscalError('data_fim anterior a data_inicio.', codigo='PERIODO_INVALIDO')

    if periodo_fiscal_fechado(empresa_id, di, df):
        raise ApuracaoFiscalError(
            'Período já está FECHADO para esta empresa. Reabra (admin) antes de criar novo rascunho.',
            codigo='PERIODO_FECHADO',
        )

    existente = (
        ApuracaoFiscal.objects.select_for_update()
        .filter(empresa_id=empresa_id, data_inicio=di, data_fim=df)
        .first()
    )
    if existente and existente.status == ApuracaoFiscal.Status.FECHADO:
        raise ApuracaoFiscalError(
            'Apuração deste período está FECHADA.',
            codigo='PERIODO_FECHADO',
        )

    query = _montar_query_params({**dados, 'empresa_id': empresa_id, 'data_inicio': di.isoformat(), 'data_fim': df.isoformat()})
    payload = build_apuracao_fiscal(query)

    if existente:
        apuracao = existente
        acao = LogsAuditoriaApuracao.Acao.ATUALIZOU_RASCUNHO
    else:
        apuracao = ApuracaoFiscal(
            empresa_id=empresa_id,
            data_inicio=di,
            data_fim=df,
            status=ApuracaoFiscal.Status.RASCUNHO,
            criado_por=usuario if getattr(usuario, 'pk', None) else None,
        )
        acao = LogsAuditoriaApuracao.Acao.ABRIU

    apuracao.tipo = str(dados.get('tipo') or 'AMBOS')[:16]
    apuracao.fonte = str(dados.get('fonte') or 'TODOS')[:16]
    apuracao.status = ApuracaoFiscal.Status.RASCUNHO
    _aplicar_totais_do_payload(apuracao, payload)
    apuracao.save()
    n_itens = _persistir_itens_agrupamento(apuracao, payload)
    _registrar_log(
        apuracao,
        acao=acao,
        usuario=usuario,
        detalhe={
            'itens_persistidos': n_itens,
            'notas_entrada': (payload.get('cards') or {}).get('notas_entrada'),
            'notas_saida': (payload.get('cards') or {}).get('notas_saida'),
        },
    )
    return apuracao


def _persistir_reforma(apuracao: ApuracaoFiscal, payload: dict[str, Any]) -> ApuracaoReforma:
    """Preenche ApuracaoReforma a partir do bloco reforma_tributaria do snapshot."""
    reforma = payload.get('reforma_tributaria') or {}
    por_doc = reforma.get('por_documento') or {}
    entrada = por_doc.get('entrada') or {}
    saida = por_doc.get('saida') or {}
    cte = por_doc.get('cte') or {}

    def _f(block: dict, *keys: str) -> Decimal:
        for k in keys:
            if block.get(k) is not None:
                return _dec(block.get(k))
        return Decimal('0')

    cbs_credito = _f(entrada, 'valor_cbs')
    cbs_debito = _f(saida, 'valor_cbs') + _f(cte, 'valor_cbs')
    ibs_credito = _f(entrada, 'valor_ibs_total', 'valor_ibs_uf') + _f(entrada, 'valor_ibs_municipio')
    if entrada.get('valor_ibs_total') is not None:
        ibs_credito = _f(entrada, 'valor_ibs_total')
    else:
        ibs_credito = _f(entrada, 'valor_ibs_uf') + _f(entrada, 'valor_ibs_municipio')
    if saida.get('valor_ibs_total') is not None:
        ibs_sai = _f(saida, 'valor_ibs_total')
    else:
        ibs_sai = _f(saida, 'valor_ibs_uf') + _f(saida, 'valor_ibs_municipio')
    if cte.get('valor_ibs_total') is not None:
        ibs_cte = _f(cte, 'valor_ibs_total')
    else:
        ibs_cte = _f(cte, 'valor_ibs_uf') + _f(cte, 'valor_ibs_municipio')
    ibs_debito = ibs_sai + ibs_cte
    is_valor = _f(reforma, 'valor_is')

    obj, _ = ApuracaoReforma.objects.update_or_create(
        apuracao=apuracao,
        defaults={
            'cbs_credito': cbs_credito,
            'cbs_debito': cbs_debito,
            'ibs_credito': ibs_credito,
            'ibs_debito': ibs_debito,
            'is_valor': is_valor,
            'detalhe_json': {
                'consolidado': {
                    'valor_cbs': reforma.get('valor_cbs'),
                    'valor_ibs_total': reforma.get('valor_ibs_total'),
                    'valor_is': reforma.get('valor_is'),
                },
                'por_documento': {
                    'entrada': entrada,
                    'saida': saida,
                    'cte': cte,
                },
            },
        },
    )
    return obj


@transaction.atomic
def fechar_periodo(apuracao_id: int, *, usuario) -> ApuracaoFiscal:
    """Fecha o período: recalcula snapshot, grava itens/reforma e trava status FECHADO."""
    apuracao = ApuracaoFiscal.objects.select_for_update().select_related('empresa').get(pk=apuracao_id)
    if apuracao.status == ApuracaoFiscal.Status.FECHADO:
        raise ApuracaoFiscalError('Apuração já está FECHADA.', codigo='JA_FECHADA')

    if periodo_fiscal_fechado(
        apuracao.empresa_id,
        apuracao.data_inicio,
        apuracao.data_fim,
        excluir_apuracao_id=apuracao.pk,
    ):
        raise ApuracaoFiscalError(
            'Já existe outra apuração FECHADA neste período.',
            codigo='PERIODO_FECHADO',
        )

    query = _montar_query_params(
        {
            **(apuracao.filtros_json or {}),
            'empresa_id': apuracao.empresa_id,
            'data_inicio': apuracao.data_inicio.isoformat(),
            'data_fim': apuracao.data_fim.isoformat(),
            'tipo': apuracao.tipo,
            'fonte': apuracao.fonte,
        }
    )
    payload = build_apuracao_fiscal(query)
    _aplicar_totais_do_payload(apuracao, payload)
    apuracao.status = ApuracaoFiscal.Status.FECHADO
    apuracao.fechado_em = timezone.now()
    apuracao.fechado_por = usuario if getattr(usuario, 'pk', None) else None
    apuracao.save()
    n_itens = _persistir_itens_agrupamento(apuracao, payload)
    reforma = _persistir_reforma(apuracao, payload)
    _registrar_log(
        apuracao,
        acao=LogsAuditoriaApuracao.Acao.FECHOU,
        usuario=usuario,
        detalhe={
            'itens_persistidos': n_itens,
            'fechado_em': apuracao.fechado_em.isoformat(),
            'versao_api_apuracao': apuracao.versao_api_apuracao,
            'reforma_id': reforma.id,
            'cbs_debito': str(reforma.cbs_debito),
            'cbs_credito': str(reforma.cbs_credito),
        },
    )
    return apuracao


def usuario_pode_reabrir(usuario) -> bool:
    """Reabertura restrita a admin (superuser / staff / grupo admin)."""
    if not usuario or not getattr(usuario, 'is_authenticated', False):
        return False
    if getattr(usuario, 'is_superuser', False) or getattr(usuario, 'is_staff', False):
        return True
    return usuario.groups.filter(name__in=('admin', 'administrador')).exists()


@transaction.atomic
def reabrir_periodo(apuracao_id: int, *, usuario, motivo: str = '') -> ApuracaoFiscal:
    """Reabre apuração FECHADA → RASCUNHO (somente admin)."""
    if not usuario_pode_reabrir(usuario):
        raise ApuracaoFiscalError(
            'Somente administrador pode reabrir período fechado.',
            codigo='SEM_PERMISSAO_REABRIR',
        )
    apuracao = ApuracaoFiscal.objects.select_for_update().get(pk=apuracao_id)
    if apuracao.status != ApuracaoFiscal.Status.FECHADO:
        raise ApuracaoFiscalError(
            'Só é possível reabrir apuração com status FECHADO.',
            codigo='NAO_FECHADA',
        )
    motivo_limpo = (motivo or '').strip()
    if len(motivo_limpo) < 5:
        raise ApuracaoFiscalError(
            'Informe um motivo com pelo menos 5 caracteres para reabrir.',
            codigo='MOTIVO_OBRIGATORIO',
        )

    anterior = {
        'fechado_em': apuracao.fechado_em.isoformat() if apuracao.fechado_em else None,
        'fechado_por_id': apuracao.fechado_por_id,
    }
    apuracao.status = ApuracaoFiscal.Status.RASCUNHO
    apuracao.fechado_em = None
    apuracao.fechado_por = None
    apuracao.save(update_fields=['status', 'fechado_em', 'fechado_por', 'atualizado_em'])
    _registrar_log(
        apuracao,
        acao=LogsAuditoriaApuracao.Acao.REABRIU,
        usuario=usuario,
        detalhe={'motivo': motivo_limpo, 'fechamento_anterior': anterior},
    )
    return apuracao
