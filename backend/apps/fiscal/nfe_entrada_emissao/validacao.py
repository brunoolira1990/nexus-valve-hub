"""Validações operacionais para NF-e entrada própria emitida (ERP 4.0.15.0)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from apps.fiscal.models import ItemNFeEntrada, NFeEntrada

TIPO_PENDENCIA = 'PENDENCIA'
TIPO_ALERTA = 'ALERTA'

PIS_COFINS_NT_CSTS = frozenset({'04', '05', '06', '07', '08', '09', '49'})
ICMS_NT_CSTS = frozenset({'40', '41', '50', '60'})


class NFeEntradaEmissaoValidationError(ValueError):
    pass


def _text(val: str | None) -> str:
    return (val or '').strip()


def _pendencia(codigo: str, mensagem: str) -> dict[str, str]:
    return {'tipo': TIPO_PENDENCIA, 'codigo': codigo, 'mensagem': mensagem}


def _alerta(codigo: str, mensagem: str) -> dict[str, str]:
    return {'tipo': TIPO_ALERTA, 'codigo': codigo, 'mensagem': mensagem}


def validar_destinatario_entrada_propria_emitida(nf: NFeEntrada) -> None:
    tem_cliente = bool(nf.cliente_destinatario_id)
    tem_fornecedor = bool(nf.fornecedor_id)
    if not tem_cliente and not tem_fornecedor:
        raise NFeEntradaEmissaoValidationError(
            'Informe Cliente ou Fornecedor como destinatário da NF-e de entrada própria.',
        )
    if tem_cliente and tem_fornecedor:
        raise NFeEntradaEmissaoValidationError(
            'Destinatário deve ser Cliente ou Fornecedor — não ambos simultaneamente.',
        )


def validar_itens_entrada_propria_emitida(nf: NFeEntrada) -> None:
    itens = list(nf.itens.all())
    if not itens:
        raise NFeEntradaEmissaoValidationError(
            'Cadastre ao menos um item com NCM, CFOP e unidade.',
        )
    for idx, item in enumerate(itens, start=1):
        _validar_item_fiscal(item, idx)


def _validar_item_fiscal(item: ItemNFeEntrada, indice: int) -> None:
    ncm = (item.ncm or '').strip()
    cfop = (item.cfop or '').strip()
    unidade = (item.unidade or '').strip()
    if not ncm:
        raise NFeEntradaEmissaoValidationError(f'Item {indice}: NCM obrigatório.')
    if not cfop:
        raise NFeEntradaEmissaoValidationError(f'Item {indice}: CFOP obrigatório.')
    if not unidade:
        raise NFeEntradaEmissaoValidationError(f'Item {indice}: unidade obrigatória.')
    if not item.produto_id:
        raise NFeEntradaEmissaoValidationError(f'Item {indice}: produto obrigatório.')
    if item.quantidade is None or item.quantidade <= 0:
        raise NFeEntradaEmissaoValidationError(f'Item {indice}: quantidade inválida.')
    if item.valor is None or item.valor < 0:
        raise NFeEntradaEmissaoValidationError(f'Item {indice}: valor inválido.')


def validar_rascunho_entrada_propria_emitida(nf: NFeEntrada) -> None:
    if nf.tipo_origem != NFeEntrada.TipoOrigem.ENTRADA_PROPRIA_EMITIDA:
        raise NFeEntradaEmissaoValidationError(
            'Validação aplicável apenas a NF-e entrada própria emitida.',
        )
    if not nf.empresa_emitente_id:
        raise NFeEntradaEmissaoValidationError('Empresa emitente obrigatória.')
    validar_destinatario_entrada_propria_emitida(nf)
    validar_itens_entrada_propria_emitida(nf)


def _validar_impostos_item(item: ItemNFeEntrada, indice: int) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    imp = item.impostos_json or {}
    if not isinstance(imp, dict) or not imp:
        out.append(
            _pendencia(
                'IMPOSTOS_JSON_AUSENTE',
                f'Item {indice}: preencha impostos_json (ICMS, PIS e COFINS) informados pelo operador.',
            ),
        )
        return out

    icms = imp.get('icms') if isinstance(imp.get('icms'), dict) else {}
    pis = imp.get('pis') if isinstance(imp.get('pis'), dict) else {}
    cof = imp.get('cofins') if isinstance(imp.get('cofins'), dict) else {}

    cst_icms = _text(icms.get('cst') or icms.get('cst_icms') or icms.get('csosn'))
    if not cst_icms:
        out.append(_pendencia('ICMS_CST_AUSENTE', f'Item {indice}: CST/CSOSN ICMS obrigatório em impostos_json.'))
    elif _text(icms.get('orig')) == '':
        out.append(
            _pendencia('ICMS_ORIG_AUSENTE', f'Item {indice}: origem da mercadoria (orig) obrigatória em impostos_json.icms.'),
        )
    elif cst_icms not in ICMS_NT_CSTS:
        for campo in ('base', 'aliquota', 'valor'):
            if _text(str(icms.get(campo) if icms.get(campo) is not None else '')) == '':
                out.append(
                    _pendencia(
                        'ICMS_CAMPOS_AUSENTES',
                        f'Item {indice}: informe base, alíquota e valor ICMS em impostos_json (sem cálculo automático).',
                    ),
                )
                break

    cst_pis = _text(pis.get('cst'))
    if not cst_pis:
        out.append(_pendencia('PIS_CST_AUSENTE', f'Item {indice}: CST PIS obrigatório em impostos_json.'))
    elif cst_pis not in PIS_COFINS_NT_CSTS:
        for campo in ('base', 'aliquota', 'valor'):
            if _text(str(pis.get(campo) if pis.get(campo) is not None else '')) == '':
                out.append(
                    _pendencia(
                        'PIS_CAMPOS_AUSENTES',
                        f'Item {indice}: informe base, alíquota e valor PIS em impostos_json.',
                    ),
                )
                break

    cst_cof = _text(cof.get('cst'))
    if not cst_cof:
        out.append(_pendencia('COFINS_CST_AUSENTE', f'Item {indice}: CST COFINS obrigatório em impostos_json.'))
    elif cst_cof not in PIS_COFINS_NT_CSTS:
        for campo in ('base', 'aliquota', 'valor'):
            if _text(str(cof.get(campo) if cof.get(campo) is not None else '')) == '':
                out.append(
                    _pendencia(
                        'COFINS_CAMPOS_AUSENTES',
                        f'Item {indice}: informe base, alíquota e valor COFINS em impostos_json.',
                    ),
                )
                break

    return out


def _validar_pre_emissao_entrada_comum(
    nf: NFeEntrada,
    *,
    ambiente: str,
    exigir_numeracao: bool = False,
) -> dict[str, Any]:
    pendencias: list[dict[str, str]] = []
    alertas: list[dict[str, str]] = []

    if nf.tipo_origem != NFeEntrada.TipoOrigem.ENTRADA_PROPRIA_EMITIDA:
        pendencias.append(
            _pendencia('TIPO_ORIGEM_INVALIDO', 'Apenas NF-e entrada própria emitida pode ser validada para emissão.'),
        )

    ambiente_esperado = (
        NFeEntrada.AmbienteEmissao.PRODUCAO
        if ambiente == 'producao'
        else NFeEntrada.AmbienteEmissao.HOMOLOGACAO
    )
    if (nf.ambiente_emissao or NFeEntrada.AmbienteEmissao.HOMOLOGACAO) != ambiente_esperado:
        pendencias.append(
            _pendencia(
                'AMBIENTE_INVALIDO',
                f'NF-e deve estar marcada para ambiente {ambiente} para esta emissão.',
            ),
        )

    if not nf.empresa_emitente_id:
        pendencias.append(_pendencia('EMITENTE_AUSENTE', 'Empresa emitente obrigatória.'))

    try:
        validar_destinatario_entrada_propria_emitida(nf)
    except NFeEntradaEmissaoValidationError as exc:
        pendencias.append(_pendencia('DESTINATARIO_INVALIDO', str(exc)))

    if not _text(nf.fin_nfe):
        pendencias.append(_pendencia('FIN_NFE_AUSENTE', 'Finalidade da NF-e (fin_nfe) obrigatória.'))

    if not _text(nf.nat_op):
        pendencias.append(_pendencia('NAT_OP_AUSENTE', 'Natureza da operação (nat_op) obrigatória.'))

    if _text(nf.fin_nfe) == '4':
        ch_ref = ''.join(c for c in _text(nf.chave_nfe_referenciada) if c.isdigit())
        if len(ch_ref) != 44:
            pendencias.append(
                _pendencia(
                    'CHAVE_REFERENCIA_INVALIDA',
                    'Devolução (finNFe=4) exige chave da NF-e original com 44 dígitos para gerar <refNFe>.',
                ),
            )

    if exigir_numeracao or _text(nf.chave_acesso):
        if not (nf.chave_acesso and nf.serie_nfe and nf.numero_nfe and nf.codigo_numerico):
            pendencias.append(
                _pendencia(
                    'NUMERACAO_NAO_RESERVADA',
                    f'Reserve a numeração de entrada própria em {ambiente} antes de gerar o XML oficial.',
                ),
            )

    try:
        validar_itens_entrada_propria_emitida(nf)
    except NFeEntradaEmissaoValidationError as exc:
        pendencias.append(_pendencia('ITENS_INVALIDOS', str(exc)))

    for idx, item in enumerate(nf.itens.all().order_by('id'), start=1):
        pendencias.extend(_validar_impostos_item(item, idx))

    emp = nf.empresa_emitente
    if emp:
        if len(''.join(c for c in (emp.cnpj or '') if c.isdigit())) != 14:
            pendencias.append(_pendencia('EMITENTE_CNPJ_INVALIDO', 'CNPJ da empresa emitente inválido.'))
        if not _text(emp.ie):
            pendencias.append(_pendencia('EMITENTE_IE_AUSENTE', 'IE da empresa emitente obrigatória.'))

    return {
        'pronta': len(pendencias) == 0,
        'pendencias': pendencias,
        'alertas': alertas,
        'nf_entrada_id': nf.pk,
        'ambiente': ambiente,
    }


def validar_pre_emissao_homologacao_entrada(
    nf: NFeEntrada,
    *,
    exigir_numeracao: bool = False,
) -> dict[str, Any]:
    """Retorna pronta, pendencias e alertas para emissão homologação."""
    payload = _validar_pre_emissao_entrada_comum(
        nf,
        ambiente='homologacao',
        exigir_numeracao=exigir_numeracao,
    )
    if nf.status_emissao_sefaz == NFeEntrada.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO:
        payload['pendencias'].append(
            _pendencia('JA_AUTORIZADA', 'NF-e já autorizada em homologação SEFAZ.'),
        )
        payload['pronta'] = False
    payload['mensagem'] = (
        'NF-e entrada própria pronta para emissão homologação SEFAZ.'
        if payload['pronta']
        else 'Existem pendências antes da emissão homologação.'
    )
    return payload


def validar_pre_emissao_producao_entrada(
    nf: NFeEntrada,
    *,
    exigir_numeracao: bool = False,
) -> dict[str, Any]:
    """Retorna pronta, pendencias e alertas para emissão produção."""
    from apps.fiscal.nfe_emissao.config_producao import MSG_PRODUCAO_NAO_HABILITADA, nfe_producao_habilitada
    from apps.fiscal.nfe_integracao.adapters.certificado_a1 import carregar_certificado_empresa
    from apps.fiscal.nfe_integracao.adapters.exceptions import CertificadoA1Error

    payload = _validar_pre_emissao_entrada_comum(
        nf,
        ambiente='producao',
        exigir_numeracao=exigir_numeracao,
    )
    pendencias = payload['pendencias']

    if not nfe_producao_habilitada():
        pendencias.append(_pendencia('PRODUCAO_DESABILITADA', MSG_PRODUCAO_NAO_HABILITADA))

    if nf.status_emissao_sefaz == NFeEntrada.StatusEmissaoSefaz.AUTORIZADA_PRODUCAO:
        pendencias.append(_pendencia('JA_AUTORIZADA', 'NF-e já autorizada em produção SEFAZ.'))

    if nf.status_emissao_sefaz == NFeEntrada.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO:
        pendencias.append(
            _pendencia(
                'JA_AUTORIZADA_HOMOLOG',
                'NF-e já autorizada em homologação — use nova NF-e para produção.',
            ),
        )

    if (
        nf.ambiente_emissao == NFeEntrada.AmbienteEmissao.HOMOLOGACAO
        and _text(nf.chave_acesso)
    ):
        pendencias.append(
            _pendencia(
                'NUMERACAO_HOMOLOG_RESERVADA',
                'Numeração de homologação já reservada — use "Preparar para produção" '
                'nesta mesma NF-e (desfaz a reserva local sem SEFAZ) ou gere uma nova nota.',
            ),
        )

    emp = nf.empresa_emitente
    if emp:
        try:
            carregar_certificado_empresa(emp)
        except CertificadoA1Error as exc:
            pendencias.append(_pendencia('CERTIFICADO_A1', str(exc)))

    payload['pronta'] = len(pendencias) == 0
    payload['mensagem'] = (
        'NF-e entrada própria pronta para emissão produção SEFAZ.'
        if payload['pronta']
        else 'Existem pendências antes da emissão produção.'
    )
    return payload


def exigir_pronta_ou_erro(validacao: dict[str, Any]) -> None:
    if validacao.get('pronta'):
        return
    msgs = [p['mensagem'] for p in (validacao.get('pendencias') or [])]
    raise NFeEntradaEmissaoValidationError(msgs[0] if msgs else 'NF-e com pendências de emissão.')
