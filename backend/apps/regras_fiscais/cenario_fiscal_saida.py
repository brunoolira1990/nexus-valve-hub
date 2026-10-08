"""Cenário fiscal de saída: escopos, vínculo de folhas, rótulos e resumos (sem motor de cálculo)."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from apps.regras_fiscais.models import (
        CenarioFiscalSaida,
        CenarioFiscalSaidaEscopo,
        RegraFiscalSaida,
    )

NOME_CENARIO_PADRAO_SAIDA = 'Cenário Padrão de Saída'

STATUS_CONFIGURADO = 'CONFIGURADO'
STATUS_INCOMPLETO = 'INCOMPLETO'
STATUS_SEM_CONFIGURACAO = 'SEM_CONFIGURACAO'

DESTINATARIO_LABEL = {
    'CONTRIBUINTE': 'Contribuinte',
    'NAO_CONTRIBUINTE': 'Não contribuinte',
    'QUALQUER': 'Qualquer destinatário',
}

TIPO_OPERACAO_LABEL = {
    'VENDA': 'Venda',
    'DEVOLUCAO': 'Devolução',
    'REMESSA': 'Remessa',
    'BONIFICACAO': 'Bonificação',
    'INDUSTRIALIZACAO': 'Industrialização',
    'OUTROS': 'Outros',
}


def _only_digits_cfop(value: str) -> str:
    return ''.join(c for c in (value or '') if c.isdigit())


def _norm_uf(value: str | None) -> str:
    return (value or '').strip().upper()[:2]


def label_escopo_saida(escopo: CenarioFiscalSaidaEscopo) -> str:
    from apps.regras_fiscais.models import CenarioFiscalSaidaEscopo as EscopoModel

    if escopo.tipo_escopo == EscopoModel.TipoEscopo.GERAL:
        return 'Regra geral'
    if escopo.tipo_escopo == EscopoModel.TipoEscopo.PRODUTO:
        return f'Produto {escopo.produto_id or 0}'
    ncm = (escopo.ncm or '').strip()
    if escopo.tipo_escopo == EscopoModel.TipoEscopo.NCM_PREFIXO:
        return f'NCM {ncm} (prefixo)' if ncm else 'NCM prefixo'
    return f'NCM {ncm}' if ncm else 'NCM'


def garantir_cenario_saida_padrao() -> CenarioFiscalSaida:
    from apps.regras_fiscais.models import CenarioFiscalSaida

    existente = (
        CenarioFiscalSaida.objects.filter(padrao=True)
        .order_by('-ativo', 'id')
        .first()
    )
    if existente:
        updates: list[str] = []
        if not existente.ativo:
            existente.ativo = True
            updates.append('ativo')
        if not (existente.nome or '').strip():
            existente.nome = NOME_CENARIO_PADRAO_SAIDA
            updates.append('nome')
        if updates:
            existente.save(update_fields=updates)
        return existente
    return CenarioFiscalSaida.objects.create(
        nome=NOME_CENARIO_PADRAO_SAIDA,
        ativo=True,
        padrao=True,
        observacoes='Cenário criado automaticamente para configurações fiscais de saída.',
    )


def garantir_cenarios_saida_para_api() -> None:
    garantir_cenario_saida_padrao()


def inferir_tipo_escopo_regra_saida(regra: RegraFiscalSaida) -> str:
    from apps.regras_fiscais.models import CenarioFiscalSaidaEscopo

    escopo = regra.escopo
    if escopo:
        return escopo.tipo_escopo
    return CenarioFiscalSaidaEscopo.TipoEscopo.GERAL


def obter_ou_criar_escopo_saida(
    cenario: CenarioFiscalSaida,
    *,
    tipo_escopo: str,
    ncm: str = '',
    produto_id: int | None = None,
) -> CenarioFiscalSaidaEscopo:
    from apps.regras_fiscais.models import CenarioFiscalSaidaEscopo

    escopo, _ = CenarioFiscalSaidaEscopo.objects.get_or_create(
        cenario=cenario,
        tipo_escopo=tipo_escopo,
        ncm=(ncm or '').strip(),
        produto_id=produto_id if tipo_escopo == CenarioFiscalSaidaEscopo.TipoEscopo.PRODUTO else None,
        defaults={'ativo': True, 'prioridade_escopo': 10},
    )
    return escopo


def criar_escopo_saida_para_regra(
    regra: RegraFiscalSaida,
    cenario: CenarioFiscalSaida | None = None,
) -> CenarioFiscalSaidaEscopo:
    """Cria ou reutiliza escopo GERAL no cenário (fase 1 — escopos NCM via API)."""
    cenario = cenario or regra.cenario or garantir_cenario_saida_padrao()
    return obter_ou_criar_escopo_saida(cenario, tipo_escopo='GERAL')


def gerar_label_regra_fiscal_saida(
    regra: RegraFiscalSaida,
    escopo: CenarioFiscalSaidaEscopo | None = None,
) -> str:
    escopo = escopo or getattr(regra, 'escopo', None)
    if escopo is None and regra.escopo_id:
        from apps.regras_fiscais.models import CenarioFiscalSaidaEscopo

        escopo = CenarioFiscalSaidaEscopo.objects.filter(pk=regra.escopo_id).first()

    if escopo:
        escopo_label = label_escopo_saida(escopo)
    else:
        escopo_label = 'Regra geral'

    ufo = _norm_uf(regra.uf_origem) or '*'
    ufd = _norm_uf(regra.uf_destino) or '*'
    cfop = _only_digits_cfop(regra.cfop_venda) or '?'
    dest = DESTINATARIO_LABEL.get(regra.destinatario_contribuinte or 'QUALQUER', 'Qualquer')
    return f'{escopo_label} · {ufo}→{ufd} · CFOP {cfop} · {dest}'


def aplicar_rotulo_automatico_regra_saida(regra: RegraFiscalSaida) -> None:
    if (regra.descricao_cenario or '').strip():
        return
    label = gerar_label_regra_fiscal_saida(regra)
    regra.descricao_cenario = label
    if not (regra.nome or '').strip():
        regra.nome = label[:120]


def associar_cenario_e_escopo_regra_saida(regra: RegraFiscalSaida) -> None:
    from apps.regras_fiscais.models import CenarioFiscalSaidaEscopo

    if not regra.cenario_id:
        regra.cenario = garantir_cenario_saida_padrao()
    if regra.escopo_id:
        if regra.escopo is None:
            regra.escopo = CenarioFiscalSaidaEscopo.objects.filter(pk=regra.escopo_id).first()
        if regra.escopo and not regra.cenario_id:
            regra.cenario_id = regra.escopo.cenario_id
    else:
        regra.escopo = criar_escopo_saida_para_regra(regra, cenario=regra.cenario)
    aplicar_rotulo_automatico_regra_saida(regra)


def _str_preenchido(val: str | None) -> bool:
    return bool((val or '').strip())


def _dec_preenchido(val: Decimal | None) -> bool:
    return val is not None


def regra_saida_tem_bloco_fiscal(regra: RegraFiscalSaida) -> bool:
    return any(
        [
            _str_preenchido(regra.cst_icms),
            _str_preenchido(regra.csosn),
            _dec_preenchido(regra.aliquota_icms),
            _str_preenchido(regra.cst_ipi),
            _dec_preenchido(regra.aliquota_ipi),
            _str_preenchido(regra.cst_pis),
            _dec_preenchido(regra.aliquota_pis),
            _str_preenchido(regra.cst_cofins),
            _dec_preenchido(regra.aliquota_cofins),
            regra.icms_st_aplicavel is not None,
            regra.fcp_aplicavel is not None,
        ],
    )


def status_configuracao_saida(regra: RegraFiscalSaida) -> str:
    cfop = _only_digits_cfop(regra.cfop_venda)
    if cfop and regra_saida_tem_bloco_fiscal(regra):
        return STATUS_CONFIGURADO
    if cfop or _norm_uf(regra.uf_origem) or _norm_uf(regra.uf_destino):
        return STATUS_INCOMPLETO
    return STATUS_SEM_CONFIGURACAO


def _fmt_pct(val: Decimal | None) -> str:
    if val is None:
        return ''
    return f'{val:.4f}'.rstrip('0').rstrip('.')


def resumo_impostos_saida(regra: RegraFiscalSaida) -> dict[str, str]:
    def icms() -> str:
        if not _str_preenchido(regra.cst_icms) and not _str_preenchido(regra.csosn):
            if regra.fcp_aplicavel and not _dec_preenchido(regra.aliquota_fcp):
                return 'FCP'
            return ''
        cst = (regra.cst_icms or regra.csosn or '').strip()
        s = f'CST {cst}' if cst else 'ICMS'
        if _dec_preenchido(regra.aliquota_icms):
            s += f' · {_fmt_pct(regra.aliquota_icms)}%'
        if _dec_preenchido(regra.aliquota_fcp):
            s += f' · FCP {_fmt_pct(regra.aliquota_fcp)}%'
        elif regra.fcp_aplicavel:
            s += ' · FCP'
        return s

    def ipi() -> str:
        if not _str_preenchido(regra.cst_ipi):
            return ''
        s = f'CST {regra.cst_ipi.strip()}'
        if _dec_preenchido(regra.aliquota_ipi):
            s += f' · {_fmt_pct(regra.aliquota_ipi)}%'
        return s

    def pis() -> str:
        if not _str_preenchido(regra.cst_pis):
            return ''
        s = f'CST {regra.cst_pis.strip()}'
        if _dec_preenchido(regra.aliquota_pis):
            s += f' · {_fmt_pct(regra.aliquota_pis)}%'
        if regra.deduzir_icms_base_pis:
            s += ' · Base sem ICMS'
        return s

    def cofins() -> str:
        if not _str_preenchido(regra.cst_cofins):
            return ''
        s = f'CST {regra.cst_cofins.strip()}'
        if _dec_preenchido(regra.aliquota_cofins):
            s += f' · {_fmt_pct(regra.aliquota_cofins)}%'
        if regra.deduzir_icms_base_cofins:
            s += ' · Base sem ICMS'
        return s

    return {'icms': icms(), 'ipi': ipi(), 'pis': pis(), 'cofins': cofins()}


def serializar_configuracao_matriz_saida(regra: RegraFiscalSaida) -> dict[str, Any]:
    from apps.regras_fiscais.recomendacoes_nfe_config import (
        contar_recomendacoes_nfe,
        recomendacoes_nfe_preenchidas,
    )
    from apps.regras_fiscais.reforma_tributaria_config import (
        reforma_tributaria_preenchida,
        resumo_reforma_tributaria,
    )

    return {
        'id': regra.id,
        'uf_origem': _norm_uf(regra.uf_origem) or '',
        'uf_destino': _norm_uf(regra.uf_destino) or '',
        'cfop_venda': _only_digits_cfop(regra.cfop_venda),
        'cfop_venda_st': _only_digits_cfop(regra.cfop_venda_st),
        'destinatario_contribuinte': regra.destinatario_contribuinte,
        'tipo_operacao': regra.tipo_operacao or '',
        'status_configuracao': status_configuracao_saida(regra),
        'label_configuracao': gerar_label_regra_fiscal_saida(regra),
        'resumo_impostos': resumo_impostos_saida(regra),
        'tem_reforma': reforma_tributaria_preenchida(regra.reforma_tributaria),
        'resumo_reforma': resumo_reforma_tributaria(regra.reforma_tributaria),
        'tem_recomendacoes_nfe': recomendacoes_nfe_preenchidas(regra.recomendacoes_nfe),
        'qtd_recomendacoes_nfe': contar_recomendacoes_nfe(regra.recomendacoes_nfe),
        'efeitos': {
            'movimenta_estoque': regra.movimenta_estoque,
            'gera_financeiro': regra.gera_financeiro,
        },
        'ativo': regra.ativo,
    }


UFS_BRASIL = (
    'AC',
    'AL',
    'AP',
    'AM',
    'BA',
    'CE',
    'DF',
    'ES',
    'GO',
    'MA',
    'MT',
    'MS',
    'MG',
    'PA',
    'PB',
    'PR',
    'PE',
    'PI',
    'RJ',
    'RN',
    'RS',
    'RO',
    'RR',
    'SC',
    'SP',
    'SE',
    'TO',
)


def montar_matriz_escopo_saida(escopo: CenarioFiscalSaidaEscopo) -> dict[str, Any]:
    from apps.regras_fiscais.models import RegraFiscalSaida

    regras = list(
        RegraFiscalSaida.objects.filter(escopo=escopo)
        .select_related('escopo', 'cenario')
        .order_by('uf_origem', 'uf_destino', 'cfop_venda', 'id'),
    )
    ufs_presentes: set[str] = set()
    configuracoes = []
    for regra in regras:
        if _norm_uf(regra.uf_origem):
            ufs_presentes.add(_norm_uf(regra.uf_origem))
        if _norm_uf(regra.uf_destino):
            ufs_presentes.add(_norm_uf(regra.uf_destino))
        configuracoes.append(serializar_configuracao_matriz_saida(regra))

    ufs_sem = sorted(u for u in UFS_BRASIL if u not in ufs_presentes)
    return {
        'escopo': {
            'id': escopo.id,
            'tipo_escopo': escopo.tipo_escopo,
            'ncm': (escopo.ncm or '').strip(),
            'produto_id': escopo.produto_id,
            'label': label_escopo_saida(escopo),
        },
        'configuracoes': configuracoes,
        'ufs_sem_configuracao': ufs_sem,
    }
