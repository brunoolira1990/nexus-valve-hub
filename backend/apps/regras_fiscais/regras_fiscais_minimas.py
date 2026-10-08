"""Validação de regras fiscais mínimas para produção — ERP 4.0.14.10 / 4.0.14.10.1."""

from __future__ import annotations

from typing import Any

from django.db.models import Q

from apps.cadastros.models import Empresa
from apps.produtos.models import Produto
from apps.regras_fiscais.models import RegraFiscal, RegraFiscalEntrada, RegraFiscalSaida


def _str(val: str | None) -> str:
    return (val or '').strip()


def _regime_eh_simples(regime: str) -> bool:
    r = _str(regime).lower()
    return 'simples' in r or r == 'mei'


def _icms_preenchido(*, cst: str = '', csosn: str = '') -> bool:
    return bool(_str(cst) or _str(csosn))


def _cfop_legado(regra: RegraFiscal) -> bool:
    return bool(_str(regra.cfop))


def _cfop_saida(regra: RegraFiscalSaida) -> bool:
    return bool(_str(regra.cfop_venda))


def _cfop_entrada(regra: RegraFiscalEntrada) -> bool:
    return bool(_str(regra.cfop_entrada) or _str(regra.cfop_origem) or _str(regra.cfop))


def _natureza_legado(regra: RegraFiscal) -> bool:
    return bool(_str(regra.operacao))


def _natureza_saida(regra: RegraFiscalSaida) -> bool:
    return bool(_str(regra.tipo_operacao) or _str(regra.descricao_cenario) or _str(regra.nome))


def _natureza_entrada(regra: RegraFiscalEntrada) -> bool:
    return bool(_str(regra.tipo_operacao_fiscal) or _str(regra.descricao_cenario) or _str(regra.nome))


def _icms_legado_ok(regra: RegraFiscal, regime: str) -> bool:
    return _icms_preenchido(cst=regra.cst_icms)


def _icms_saida_ok(regra: RegraFiscalSaida, regime: str) -> bool:
    if _regime_eh_simples(regime):
        return _icms_preenchido(cst=regra.cst_icms, csosn=regra.csosn)
    return _icms_preenchido(cst=regra.cst_icms)


def _icms_entrada_ok(regra: RegraFiscalEntrada, regime: str) -> bool:
    if _regime_eh_simples(regime):
        return _icms_preenchido(cst=regra.cst_icms_esperado, csosn=regra.csosn_esperado)
    return _icms_preenchido(cst=regra.cst_icms_esperado)


def _regra_legada_valida(regra: RegraFiscal, regime: str) -> bool:
    return _cfop_legado(regra) and _natureza_legado(regra) and _icms_legado_ok(regra, regime)


def _regra_saida_valida(regra: RegraFiscalSaida, regime: str) -> bool:
    return _cfop_saida(regra) and _natureza_saida(regra) and _icms_saida_ok(regra, regime)


def _regra_entrada_valida(regra: RegraFiscalEntrada, regime: str) -> bool:
    return _cfop_entrada(regra) and _natureza_entrada(regra) and _icms_entrada_ok(regra, regime)


def _rotulo_entrada(regra: RegraFiscalEntrada) -> str:
    return _str(regra.nome) or f'#{regra.pk}'


def pendencias_regra_entrada_incompleta(regra: RegraFiscalEntrada, regime: str) -> list[str]:
    pendencias: list[str] = []
    if not _cfop_entrada(regra):
        pendencias.append('Falta CFOP.')
    if not _natureza_entrada(regra):
        pendencias.append('Falta natureza da operação.')
    if not _icms_entrada_ok(regra, regime):
        pendencias.append('Falta CST/CSOSN.')
    return pendencias


def regra_entrada_esta_incompleta(regra: RegraFiscalEntrada, regime: str) -> bool:
    return bool(pendencias_regra_entrada_incompleta(regra, regime))


def _contar_produtos_sem_ncm() -> int:
    total = 0
    for produto in Produto.objects.select_related('familia', 'familia__ncm_padrao').only('pk', 'ncm', 'familia_id'):
        if not produto.get_ncm_efetivo_codigo():
            total += 1
    return total


def _empresa_principal() -> Empresa | None:
    return Empresa.objects.order_by('pk').first()


def _aviso(msg: str) -> dict[str, Any]:
    return {'nivel': 'aviso', 'mensagem': msg}


def validar_regra_fiscal_entrada_para_uso(regime: str | None = None) -> dict[str, Any]:
    """
    Valida se há regra fiscal de entrada utilizável no fluxo de NF-e Entrada.
    Usar em preparar/finalizar entrada fiscal — não na prontidão geral.
    """
    empresa = _empresa_principal()
    regime_eff = _str(regime) if regime is not None else _str(empresa.regime_tributario if empresa else '')

    regras_entrada = list(RegraFiscalEntrada.objects.filter(ativo=True))
    entrada_legado = list(RegraFiscal.objects.filter(operacao=RegraFiscal.Operacao.ENTRADA))

    validas = [r for r in regras_entrada if _regra_entrada_valida(r, regime_eff)]
    validas.extend([r for r in entrada_legado if _regra_legada_valida(r, regime_eff)])

    bloqueios: list[str] = []
    incompletas: list[str] = []

    for regra in regras_entrada:
        pend = pendencias_regra_entrada_incompleta(regra, regime_eff)
        if pend:
            rotulo = _rotulo_entrada(regra)
            incompletas.append(f'Regra fiscal de entrada "{rotulo}" incompleta ({"; ".join(pend)})')

    if not validas:
        if regras_entrada or entrada_legado:
            bloqueios.append('Não é possível finalizar a entrada fiscal sem regra fiscal de entrada válida.')
        else:
            bloqueios.append(
                'Não há regra fiscal de entrada ativa. O fluxo de NF-e Entrada fiscal será bloqueado até o cadastro da regra.',
            )
        bloqueios.append('Cadastre uma regra fiscal de entrada com CFOP, natureza e CST/CSOSN.')

    return {
        'valida': bool(validas),
        'bloqueios': bloqueios,
        'regras_validas': len(validas),
        'regras_incompletas': incompletas,
    }


def validar_regras_fiscais_minimas() -> dict[str, Any]:
    """Retorna críticos gerais, avisos e métricas fiscais para prontidão de produção."""
    criticos: list[dict[str, Any]] = []
    avisos: list[dict[str, Any]] = []
    avisos_entrada: list[dict[str, Any]] = []
    ok: list[dict[str, Any]] = []

    empresa = _empresa_principal()
    regime = _str(empresa.regime_tributario) if empresa else ''

    regras_legado = list(RegraFiscal.objects.all())
    regras_saida = list(RegraFiscalSaida.objects.filter(ativo=True))
    regras_entrada = list(RegraFiscalEntrada.objects.filter(ativo=True))
    regras_saida_todas = RegraFiscalSaida.objects.count()
    regras_entrada_todas = RegraFiscalEntrada.objects.count()

    regras_total = len(regras_legado) + regras_saida_todas + regras_entrada_todas
    regras_ativas = len(regras_legado) + len(regras_saida) + len(regras_entrada)

    saida_legado = [r for r in regras_legado if r.operacao == RegraFiscal.Operacao.SAIDA]
    entrada_legado = [r for r in regras_legado if r.operacao == RegraFiscal.Operacao.ENTRADA]
    regras_saida_venda = [
        *saida_legado,
        *[r for r in regras_saida if not r.tipo_operacao or r.tipo_operacao == RegraFiscalSaida.TipoOperacao.VENDA],
    ]
    regras_compra = [
        *entrada_legado,
        *[r for r in regras_entrada if r.tipo_operacao_fiscal == RegraFiscalEntrada.TipoOperacaoFiscal.COMPRA],
    ]

    produtos_sem_ncm = _contar_produtos_sem_ncm()
    entrada_uso = validar_regra_fiscal_entrada_para_uso(regime)

    metricas = {
        'empresa_cadastrada': bool(empresa),
        'regime_tributario': regime,
        'regras_total': regras_total,
        'regras_ativas': regras_ativas,
        'regras_saida': len(regras_saida_venda),
        'regras_compra': len(regras_compra),
        'regras_legado': len(regras_legado),
        'regras_saida_cenario': len(regras_saida),
        'regras_entrada_cenario': len(regras_entrada),
        'produtos_sem_ncm': produtos_sem_ncm,
        'regras_entrada_validas': entrada_uso['regras_validas'],
    }

    checklist_saida = [
        {'item': 'Empresa com regime tributário', 'ok': bool(regime), 'nota': ''},
        {'item': 'Empresa com CNPJ/UF', 'ok': bool(empresa and _str(empresa.cnpj) and _str(empresa.uf)), 'nota': ''},
        {'item': 'Regra fiscal de venda ativa', 'ok': len(regras_saida_venda) > 0, 'nota': ''},
        {
            'item': 'CFOP de venda configurado',
            'ok': any(_cfop_legado(r) for r in saida_legado) or any(_cfop_saida(r) for r in regras_saida),
            'nota': '',
        },
        {
            'item': 'CST/CSOSN de saída configurado',
            'ok': any(_icms_legado_ok(r, regime) for r in saida_legado)
            or any(_icms_saida_ok(r, regime) for r in regras_saida),
            'nota': '',
        },
        {'item': 'Produtos com NCM', 'ok': produtos_sem_ncm == 0, 'nota': f'{produtos_sem_ncm} produto(s) sem NCM.'},
    ]

    checklist_entrada = [
        {'item': 'Regra fiscal de entrada ativa', 'ok': bool(regras_entrada or entrada_legado), 'nota': ''},
        {
            'item': 'CFOP de entrada configurado',
            'ok': any(_cfop_legado(r) for r in entrada_legado) or any(_cfop_entrada(r) for r in regras_entrada),
            'nota': '',
        },
        {
            'item': 'CST/CSOSN de entrada configurado',
            'ok': entrada_uso['valida'],
            'nota': 'Obrigatório ao finalizar NF-e Entrada fiscal.',
        },
    ]

    if not empresa:
        criticos.append({'nivel': 'critico', 'mensagem': 'Empresa emitente não cadastrada.'})
    else:
        if not _str(empresa.cnpj):
            criticos.append({'nivel': 'critico', 'mensagem': 'Empresa emitente sem CNPJ.'})
        if not _str(empresa.uf):
            criticos.append({'nivel': 'critico', 'mensagem': 'Empresa emitente sem UF.'})
        if not regime:
            criticos.append({'nivel': 'critico', 'mensagem': 'Empresa emitente sem regime tributário informado.'})
        if not getattr(empresa.certificado_arquivo, 'name', None):
            avisos.append(_aviso('Certificado digital não configurado na empresa emitente.'))

    if regras_total == 0:
        criticos.append({'nivel': 'critico', 'mensagem': 'Nenhuma regra fiscal cadastrada.'})
    elif regras_ativas == 0:
        criticos.append(
            {
                'nivel': 'critico',
                'mensagem': 'Nenhuma regra fiscal ativa cadastrada. Cadastre regras fiscais mínimas antes de iniciar produção.',
            },
        )

    if regras_ativas > 0 and not regras_saida_venda:
        criticos.append({'nivel': 'critico', 'mensagem': 'Nenhuma regra fiscal de venda/saída ativa cadastrada.'})

    saida_invalidas = 0
    for regra in saida_legado:
        if not _regra_legada_valida(regra, regime):
            saida_invalidas += 1
            if not _cfop_legado(regra):
                criticos.append({'nivel': 'critico', 'mensagem': f'Regra fiscal legada de saída #{regra.pk} sem CFOP.'})
            elif not _natureza_legado(regra):
                criticos.append({'nivel': 'critico', 'mensagem': f'Regra fiscal legada de saída #{regra.pk} sem natureza da operação.'})
            elif not _icms_legado_ok(regra, regime):
                criticos.append({'nivel': 'critico', 'mensagem': f'Regra fiscal legada de saída #{regra.pk} sem CST/CSOSN de ICMS.'})

    for regra in entrada_legado:
        if not _regra_legada_valida(regra, regime):
            msg = f'Regra fiscal legada de entrada #{regra.pk} incompleta. Será obrigatória ao finalizar NF-e Entrada.'
            avisos_entrada.append(_aviso(msg))
            avisos.append(_aviso(msg))

    for regra in regras_saida:
        if not _regra_saida_valida(regra, regime):
            saida_invalidas += 1
            rotulo = _str(regra.nome) or f'#{regra.pk}'
            if not _cfop_saida(regra):
                criticos.append({'nivel': 'critico', 'mensagem': f'Regra fiscal de saída "{rotulo}" ativa sem CFOP.'})
            elif not _natureza_saida(regra):
                criticos.append({'nivel': 'critico', 'mensagem': f'Regra fiscal de saída "{rotulo}" ativa sem natureza da operação.'})
            elif not _icms_saida_ok(regra, regime):
                criticos.append({'nivel': 'critico', 'mensagem': f'Regra fiscal de saída "{rotulo}" ativa sem CST/CSOSN de ICMS.'})

    for regra in regras_entrada:
        pend = pendencias_regra_entrada_incompleta(regra, regime)
        if pend:
            rotulo = _rotulo_entrada(regra)
            msg = (
                f'Regra fiscal de entrada "{rotulo}" incompleta ({", ".join(pend)}). '
                'Corrija antes de finalizar entradas fiscais de NF-e.'
            )
            avisos_entrada.append(_aviso(msg))
            avisos.append(_aviso(msg))

    if not regras_entrada and not entrada_legado:
        msg = 'Nenhuma regra fiscal de entrada ativa. O fluxo de NF-e Entrada fiscal será bloqueado até o cadastro da regra.'
        avisos_entrada.append(_aviso(msg))
        avisos.append(_aviso(msg))
    elif not entrada_uso['valida']:
        msg = 'Não há regra fiscal de entrada válida. O fluxo de NF-e Entrada fiscal será bloqueado até o cadastro da regra.'
        avisos_entrada.append(_aviso(msg))
        avisos.append(_aviso(msg))

    if produtos_sem_ncm > 0:
        criticos.append(
            {
                'nivel': 'critico',
                'mensagem': f'{produtos_sem_ncm} produto(s) sem NCM. Revise o cadastro de produtos antes de produção.',
            },
        )

    if not any(r.tipo_operacao == RegraFiscalSaida.TipoOperacao.DEVOLUCAO for r in regras_saida):
        avisos.append(_aviso('Nenhuma regra fiscal ativa para operação de devolução.'))

    interestadual = any(
        _str(r.uf_origem) and _str(r.uf_destino) and _str(r.uf_origem) != _str(r.uf_destino)
        for r in [*regras_saida, *saida_legado]
    )
    if not interestadual:
        avisos.append(_aviso('Nenhuma regra fiscal para operação interestadual identificada.'))

    regras_sem_obs = RegraFiscalSaida.objects.filter(ativo=True).filter(Q(observacoes='') | Q(observacoes__isnull=True)).count()
    if regras_sem_obs:
        avisos.append(_aviso(f'{regras_sem_obs} regra(s) fiscal(is) de saída sem observação.'))

    if empresa and regime and regras_saida_venda and saida_invalidas == 0 and produtos_sem_ncm == 0:
        ok.append(
            {
                'nivel': 'ok',
                'mensagem': (
                    f'Fiscal mínimo para venda/saída: empresa com regime, '
                    f'{len(regras_saida_venda)} regra(s) de venda/saída válida(s).'
                ),
            },
        )

    bloqueios_fluxo: dict[str, list[str]] = {}
    if not entrada_uso['valida']:
        bloqueios_fluxo['nfe_entrada'] = list(entrada_uso['bloqueios'])
        if entrada_uso['regras_incompletas']:
            bloqueios_fluxo['nfe_entrada'].extend(entrada_uso['regras_incompletas'])

    return {
        'criticos': criticos,
        'avisos': avisos,
        'avisos_entrada': avisos_entrada,
        'ok': ok,
        'metricas': metricas,
        'checklist_fiscal': checklist_saida + checklist_entrada,
        'checklist_saida': checklist_saida,
        'checklist_entrada': checklist_entrada,
        'bloqueios_por_fluxo': bloqueios_fluxo,
    }
