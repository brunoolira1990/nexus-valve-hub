"""
Prévia estrutural de TXT EFD ICMS/IPI a partir de ApuracaoFiscal FECHADA.

NÃO é arquivo oficial para entrega no PVA/SEFAZ. Gera blocos mínimos
(0000, C100, C170, C190, E110, E111) com dados do snapshot + itens + ajustes.
A validação no PVA permanece responsabilidade do contador.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from apps.apuracao_fiscal.models import ApuracaoAjusteManual, ApuracaoFiscal, ApuracaoItem
from apps.apuracao_fiscal.services.fechamento import ApuracaoFiscalError


def _pipe(*campos: Any) -> str:
    parts = ['' if c is None else str(c) for c in campos]
    return '|' + '|'.join(parts) + '|'


def _d(v: Any) -> str:
    try:
        return f'{Decimal(str(v or 0)).quantize(Decimal("0.01"))}'
    except Exception:
        return '0.00'


def _date_br(d: date | str | None) -> str:
    if d is None:
        return ''
    if isinstance(d, date):
        return d.strftime('%d%m%Y')
    s = str(d)[:10]
    try:
        y, m, day = s.split('-')
        return f'{day}{m}{y}'
    except Exception:
        return s.replace('-', '')


def _cnpj_digits(val: Any) -> str:
    return ''.join(c for c in str(val or '') if c.isdigit())[:14]


def gerar_sped_efd_icms_ipi_txt(apuracao: ApuracaoFiscal) -> str:
    """
    Monta TXT prévia a partir de apuração FECHADA.

    Raises ApuracaoFiscalError se não estiver FECHADA.
    """
    if apuracao.status != ApuracaoFiscal.Status.FECHADO:
        raise ApuracaoFiscalError(
            'SPED prévia só pode ser gerada para apuração FECHADA.',
            codigo='APURACAO_NAO_FECHADA_SPED',
        )

    emp = apuracao.empresa
    snap = apuracao.payload_snapshot if isinstance(apuracao.payload_snapshot, dict) else {}
    cards = snap.get('cards') or {}
    filtros = apuracao.filtros_json or {}
    di = apuracao.data_inicio
    df = apuracao.data_fim
    cnpj = _cnpj_digits(emp.cnpj)
    ie = (emp.ie or '').strip() or 'ISENTO'
    nome = (emp.razao_social or '')[:100]
    uf = (emp.uf or 'SP').upper()[:2]

    linhas: list[str] = []

    # 0000 — abertura do arquivo (campos simplificados / prévia)
    # COD_VER|COD_FIN|DT_INI|DT_FIN|NOME|CNPJ|UF|IE|COD_MUN|IND_PERFIL|IND_ATIV
    linhas.append(
        _pipe(
            '0000',
            '019',  # versão layout simplificada / placeholder
            '0',  # remessa original
            _date_br(di),
            _date_br(df),
            nome,
            cnpj,
            uf,
            ie,
            '3550308',  # mun. placeholder se não houver no cadastro
            'A',
            '1',
        )
    )
    linhas.append(_pipe('0001', '0'))  # bloco 0 com dados

    # Bloco C
    linhas.append(_pipe('C001', '0'))
    itens = list(
        ApuracaoItem.objects.filter(apuracao=apuracao).order_by('id')[:500]
    )
    # C100 sintético por documento agregado do período (prévia: 1 linha resumo saída + 1 entrada)
    valor_sai = _d(cards.get('valor_saidas') or apuracao.valor_saidas)
    valor_ent = _d(cards.get('valor_entradas') or apuracao.valor_entradas)
    icms_sai = _d(cards.get('icms_saida') or apuracao.icms_debito)
    icms_ent = _d(cards.get('icms_entrada') or apuracao.icms_credito)

    # IND_OPER 0=entrada 1=saída | IND_EMIT 0=própria | COD_SIT 00
    linhas.append(
        _pipe(
            'C100',
            '1',
            '0',
            '00',
            '55',
            '000',
            '1',
            cnpj or '00000000000000',
            _date_br(di),
            _date_br(di),
            valor_sai,
            '0',
            '0',
            valor_sai,
            '0',
            '0.00',
            icms_sai,
            '0.00',
            '0.00',
            '0.00',
            '0.00',
            '0.00',
            '0.00',
            '0.00',
            '0.00',
            '0.00',
        )
    )
    linhas.append(
        _pipe(
            'C100',
            '0',
            '1',
            '00',
            '55',
            '000',
            '2',
            cnpj or '00000000000000',
            _date_br(di),
            _date_br(di),
            valor_ent,
            '0',
            '0',
            valor_ent,
            '0',
            '0.00',
            icms_ent,
            '0.00',
            '0.00',
            '0.00',
            '0.00',
            '0.00',
            '0.00',
            '0.00',
            '0.00',
            '0.00',
        )
    )

    # C170 a partir dos itens de agrupamento persistidos
    if not itens:
        linhas.append(
            _pipe(
                'C170',
                '1',
                'SEM_ITEM',
                '',
                '1',
                'UN',
                _d(0),
                '0.00',
                '0',
                '00',
                '5102',
                '0',
                '0.00',
                '0.00',
                '0.00',
                '0.00',
                '0.00',
                '0.00',
                '0.00',
                '0.00',
                '01',
                '0.00',
                '0.00',
                '0.00',
                '01',
                '0.00',
                '0.00',
                '0.00',
            )
        )
    for i, it in enumerate(itens, start=1):
        linhas.append(
            _pipe(
                'C170',
                str(i),
                (it.chave or it.cfop or f'ITEM{i}')[:60],
                '',
                _d(it.quantidade_itens or 1),
                'UN',
                _d(it.valor_produtos),
                '0.00',
                '0',
                (it.cst_icms or '00')[:3],
                (it.cfop or '5102')[:4],
                '0',
                _d(it.base_icms),
                '0.00',
                _d(it.valor_icms),
                '0.00',
                '0.00',
                _d(it.base_ipi),
                '0.00',
                _d(it.valor_ipi),
                (it.cst_pis or '01')[:2],
                _d(it.base_pis),
                '0.00',
                _d(it.valor_pis),
                (it.cst_cofins or '01')[:2],
                _d(it.base_cofins),
                '0.00',
                _d(it.valor_cofins),
            )
        )

    # C190 — consolidação por CFOP (itens)
    by_cfop: dict[str, dict[str, Decimal]] = {}
    for it in itens:
        cf = (it.cfop or it.chave or '0000')[:4]
        bucket = by_cfop.setdefault(
            cf,
            {
                'vl_opr': Decimal('0'),
                'vl_bc': Decimal('0'),
                'vl_icms': Decimal('0'),
            },
        )
        bucket['vl_opr'] += Decimal(str(it.valor_produtos or 0))
        bucket['vl_bc'] += Decimal(str(it.base_icms or 0))
        bucket['vl_icms'] += Decimal(str(it.valor_icms or 0))
    if not by_cfop:
        by_cfop['5102'] = {
            'vl_opr': Decimal(str(apuracao.valor_saidas or 0)),
            'vl_bc': Decimal(str(apuracao.icms_debito or 0)),
            'vl_icms': Decimal(str(apuracao.icms_debito or 0)),
        }
    for cf, b in sorted(by_cfop.items()):
        linhas.append(
            _pipe(
                'C190',
                '00',
                cf,
                '0.00',
                _d(b['vl_opr']),
                _d(b['vl_bc']),
                _d(b['vl_icms']),
                '0.00',
                '0.00',
                '0.00',
                '0.00',
                '0.00',
                '0.00',
                '',
            )
        )

    n_c = 1 + 2 + max(len(itens), 1) + len(by_cfop) + 1  # C001 + C100s + C170s + C190s + C990
    linhas.append(_pipe('C990', str(n_c)))

    # Bloco E — apuração ICMS
    linhas.append(_pipe('E001', '0'))
    linhas.append(_pipe('E100', _date_br(di), _date_br(df)))
    # E110 — campos principais: débitos, créditos, saldo
    vl_tot_debitos = _d(apuracao.icms_debito)
    vl_tot_creditos = _d(apuracao.icms_credito)
    saldo = _d(apuracao.saldo_icms)
    linhas.append(
        _pipe(
            'E110',
            vl_tot_debitos,
            '0.00',
            '0.00',
            '0.00',
            '0.00',
            vl_tot_debitos,
            vl_tot_creditos,
            '0.00',
            '0.00',
            '0.00',
            '0.00',
            '0.00',
            vl_tot_creditos,
            saldo if Decimal(saldo) > 0 else '0.00',
            '0.00',
            '0.00',
            saldo if Decimal(saldo) < 0 else '0.00',
            '0.00',
            '0.00',
            '0.00',
        )
    )

    # E111 — ajustes (manuais F2 + ST destacado como referência)
    ajustes = list(ApuracaoAjusteManual.objects.filter(apuracao=apuracao).order_by('id'))
    for aj in ajustes:
        cod = 'SP0001' if aj.tipo == 'DEBITO' else 'SP0002'
        desc = f'{aj.tipo}: {(aj.motivo or "")[:100]}'
        linhas.append(_pipe('E111', cod, desc, _d(aj.valor)))

    if apuracao.icms_st_debito and Decimal(str(apuracao.icms_st_debito)) > 0:
        linhas.append(
            _pipe(
                'E111',
                'SP00ST',
                'ICMS-ST destacado (débito próprio — não credita ICMS próprio)',
                _d(apuracao.icms_st_debito),
            )
        )

    n_e = 1 + 1 + 1 + len(ajustes) + (1 if apuracao.icms_st_debito else 0) + 1
    linhas.append(_pipe('E990', str(n_e)))

    # Encerramento
    linhas.append(_pipe('9001', '0'))
    total_linhas = len(linhas) + 2  # +9990 +9999
    linhas.append(_pipe('9990', str(total_linhas)))
    linhas.append(_pipe('9999', str(total_linhas)))

    header = [
        '# PREVIA ESTRUTURAL EFD ICMS/IPI — NAO OFICIAL',
        f'# Apuracao id={apuracao.id} empresa={cnpj} periodo={di}/{df}',
        f'# fonte={filtros.get("fonte") or apuracao.fonte} tipo={apuracao.tipo}',
        '# Validacao no PVA/SEFAZ e responsabilidade do contador.',
        '',
    ]
    return '\n'.join(header + linhas) + '\n'


def nome_arquivo_sped(apuracao: ApuracaoFiscal) -> str:
    return (
        f'efd_icms_ipi_previa_{apuracao.empresa_id}_'
        f'{apuracao.data_inicio:%Y%m%d}_{apuracao.data_fim:%Y%m%d}_'
        f'ap{apuracao.id}.txt'
    )
