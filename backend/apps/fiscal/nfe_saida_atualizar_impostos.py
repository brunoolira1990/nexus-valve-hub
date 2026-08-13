"""NF-e Saída 3.5.2 — atualizar snapshot fiscal dos itens a partir da regra atual."""

from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.cadastros.endereco_fiscal import (
    EnderecoFiscalResult,
    mensagem_endereco_inconsistente_nf,
    validar_endereco_fiscal,
)
from apps.cadastros.models import Empresa
from apps.fiscal.models import ItemNFeSaida, NFeSaida, NFeSaidaEvento
from apps.fiscal.nfe_saida_bloqueio import (
    STATUS_NFE_RASCUNHO,
    nf_ja_finalizada_operacionalmente,
    pode_atualizar_impostos_nfe,
)
from apps.fiscal.nfe_saida_efeitos import _lock_nfe_saida, _registrar_evento
from apps.fiscal.snapshot_fiscal_helpers import (
    cfop_from_snapshot_fiscal,
    get_reforma_tributaria_snapshot,
    normalize_snapshot_fiscal_for_nfe,
)
from apps.regras_fiscais.reforma_tributaria_config import normalizar_percentual_reforma
from apps.produtos.snapshot import build_produto_snapshot
from apps.fiscal.nfe_cbenef_sp import codigo_beneficio_icms_para_snapshot
from apps.fiscal.nfe_icms_calculo import calcular_base_valor_icms_saida
from apps.regras_fiscais.base_pis_cofins_saida import calcular_base_pis_cofins_saida
from apps.regras_fiscais.models import RegraFiscalSaida
from apps.fiscal.nfe_saida_textos_fiscais import (
    aplicar_textos_fiscais_nf,
    calcular_textos_fiscais_preview,
    mesclar_recomendacoes_snapshot,
)
from apps.regras_fiscais.recomendacoes_nfe_config import normalizar_recomendacoes_nfe
from apps.fiscal.nfe_saida_reforma_calculo import (
    aplicar_reforma_tributaria_item,
    mensagem_reforma_aplicada,
)
from apps.regras_fiscais.reforma_tributaria_config import (
    normalizar_reforma_tributaria,
    reforma_tributaria_preenchida,
)
from apps.comercial.pricing import normalize_ncm
from apps.regras_fiscais.saida_fiscal import (
    BuscaRegraFiscalSaidaDict,
    buscar_regra_fiscal_nfe_saida_rascunho,
    _resultado_nao_encontrada,
)
from apps.fiscal.nfe_difal_calculo import (
    calcular_difal_item,
    deve_aplicar_difal,
    validar_parametros_difal_regra,
)
from apps.fiscal.nfe_destinatario_fiscal import resolver_perfil_destinatario_nf

MSG_BLOQUEIO_STATUS = 'Impostos só podem ser atualizados em NF-e rascunho.'

_STATUS_REAPLICAR_FISCAL_POS_EMISSAO = frozenset(
    {
        NFeSaida.StatusEmissaoSefaz.REJEITADA_PRODUCAO,
        NFeSaida.StatusEmissaoSefaz.REJEITADA_HOMOLOGACAO,
        NFeSaida.StatusEmissaoSefaz.ERRO_TRANSMISSAO,
        'REJEITADA',
    },
)


def nf_permite_reaplicar_fiscal_pos_emissao(nf: NFeSaida) -> bool:
    """Permite reaplicar snapshots após rejeição/erro SEFAZ mesmo sem diff na regra."""
    return (nf.status_emissao_sefaz or '').strip().upper() in _STATUS_REAPLICAR_FISCAL_POS_EMISSAO


def _limpar_xml_emissao_para_reaplicar_fiscal(nf: NFeSaida) -> list[str]:
    """Remove XML de tentativa anterior para forçar regeneração na próxima emissão."""
    nf.xml_nfe_gerado = ''
    nf.xml_assinado = ''
    nf.xml_envio_lote = ''
    nf.xml_retorno = ''
    nf.xml_autorizado = ''
    update_fields = [
        'xml_nfe_gerado',
        'xml_assinado',
        'xml_envio_lote',
        'xml_retorno',
        'xml_autorizado',
    ]
    if nf.chave_acesso and nf.numero_nfe:
        nf.status_emissao_sefaz = NFeSaida.StatusEmissaoSefaz.NUMERACAO_RESERVADA
        update_fields.append('status_emissao_sefaz')
    return update_fields

_CAMPOS_COMPARACAO: list[tuple[str, str]] = [
    ('cenario_fiscal_saida_id', 'Cenário fiscal de saída'),
    ('regra_fiscal_saida_id', 'Regra fiscal de saída'),
    ('cfop', 'CFOP'),
    ('cst_icms', 'CST ICMS'),
    ('modalidade_bc_icms', 'Modalidade BC ICMS'),
    ('reducao_bc_icms', 'Redução BC ICMS (%)'),
    ('base_icms', 'Base ICMS'),
    ('aliquota_icms', 'Alíquota ICMS'),
    ('valor_icms', 'Valor ICMS'),
    ('codigo_beneficio_icms', 'Cód. benefício ICMS'),
    ('motivo_desoneracao_icms', 'Motivo desoneração ICMS'),
    ('cst_ipi', 'CST IPI'),
    ('aliquota_ipi', 'Alíquota IPI'),
    ('valor_ipi', 'Valor IPI'),
    ('cst_pis', 'CST PIS'),
    ('aliquota_pis', 'Alíquota PIS'),
    ('valor_pis', 'Valor PIS'),
    ('cst_cofins', 'CST COFINS'),
    ('aliquota_cofins', 'Alíquota COFINS'),
    ('valor_cofins', 'Valor COFINS'),
    ('cst_ibs_cbs', 'CST IBS/CBS'),
    ('classificacao_tributaria', 'Classificação tributária'),
    ('aliquota_cbs', 'Alíquota CBS'),
    ('valor_cbs', 'Valor CBS'),
    ('aliquota_ibs_estadual', 'Alíquota IBS estadual'),
    ('valor_ibs_estadual', 'Valor IBS estadual'),
    ('difal_v_icms_uf_dest', 'DIFAL ICMS UF destino'),
    ('difal_v_fcp_uf_dest', 'DIFAL FCP UF destino'),
]


def _dec(v) -> Decimal:
    if v is None or v == '':
        return Decimal('0')
    s = str(v).strip()
    if ',' in s:
        return normalizar_percentual_reforma(v)
    try:
        return Decimal(s)
    except Exception:
        return normalizar_percentual_reforma(v)


def _q2(v: Decimal) -> str:
    return str(v.quantize(Decimal('0.01')))


def _text(val) -> str:
    return (str(val) if val is not None else '').strip()


def _valor_produto_item(item: ItemNFeSaida) -> Decimal:
    qtd = _dec(item.quantidade)
    unit = _dec(item.valor)
    snap_c = item.snapshot_comercial or {}
    desconto = _dec(snap_c.get('desconto'))
    return max(qtd * unit - desconto, Decimal('0'))


def _ncm_item(item: ItemNFeSaida) -> str:
    from apps.fiscal.snapshot_fiscal_helpers import get_ncm_snapshot

    ncm = get_ncm_snapshot(item.snapshot_fiscal)
    if ncm:
        return ncm
    if item.produto_id:
        return _text(item.produto.get_ncm_efetivo_codigo() or item.produto.ncm)
    return _text((item.snapshot_produto or {}).get('ncm'))


def _uf_origem_nf(nf: NFeSaida) -> str:
    pedido = nf.pedido_venda
    if pedido and pedido.empresa_emitente_id and pedido.empresa_emitente:
        return _text(pedido.empresa_emitente.uf).upper()[:2]
    emp = Empresa.objects.order_by('pk').first()
    return _text(emp.uf).upper()[:2] if emp else ''


def _cliente_nf(nf: NFeSaida):
    if nf.cliente_id and nf.cliente:
        return nf.cliente
    pedido = nf.pedido_venda
    if pedido and pedido.cliente_id and pedido.cliente:
        return pedido.cliente
    return None


def _uf_destino_nf(nf: NFeSaida, endereco_result: EnderecoFiscalResult | None = None) -> str:
    if endereco_result is not None:
        if endereco_result.bloqueio_fiscal or not endereco_result.consistente:
            return ''
        if endereco_result.uf_destino:
            return endereco_result.uf_destino
    cliente = _cliente_nf(nf)
    if cliente:
        uf = _text(cliente.uf).upper()[:2]
        if len(uf) == 2:
            return uf
    return ''


def _mensagem_regra_nao_encontrada(ncm: str, uf_origem: str, uf_destino: str) -> str:
    ncm_txt = _text(ncm) or '—'
    ufo = _text(uf_origem).upper()[:2] or '—'
    ufd = _text(uf_destino).upper()[:2] or '—'
    if len(ufo) != 2:
        return 'UF origem incompleta para buscar regra fiscal.'
    if len(ufd) != 2:
        return 'UF destino incompleta ou inconsistente para buscar regra fiscal.'
    return f'Não foi encontrada regra fiscal de saída para NCM {ncm_txt}, origem {ufo} e destino {ufd}.'


def _montar_contexto_fiscal_nf(
    nf: NFeSaida,
    *,
    endereco_result: EnderecoFiscalResult | None,
) -> dict[str, Any]:
    cliente = _cliente_nf(nf)
    pedido = nf.pedido_venda
    emp = pedido.empresa_emitente if pedido and pedido.empresa_emitente_id else None
    if not emp:
        emp = Empresa.objects.order_by('pk').first()
    ufo = _uf_origem_nf(nf)
    ufd = _uf_destino_nf(nf, endereco_result)
    from apps.regras_fiscais.cenario_fiscal_saida import garantir_cenario_saida_padrao

    cenario = garantir_cenario_saida_padrao()
    return {
        'empresa_emitente_id': emp.pk if emp else None,
        'empresa_emitente': _text(emp.razao_social) if emp else '',
        'uf_origem': ufo,
        'cliente_id': cliente.pk if cliente else None,
        'cliente_razao_social': _text(cliente.razao_social) if cliente else '',
        'cnpj_cliente': _text(cliente.cnpj) if cliente else '',
        'ie_cliente': _text(cliente.ie) if cliente else '',
        'uf_destino': ufd,
        'cidade_destino': endereco_result.cidade_destino if endereco_result else (_text(cliente.cidade) if cliente else ''),
        'operacao': 'VENDA',
        'tipo_documento': 'NF-e',
        'ambiente': _text(getattr(nf, 'ambiente', '') or getattr(nf, 'tipo_ambiente', '')),
        'fonte_consultada': 'CENARIO_SAIDA_PADRAO',
        'cenario_fiscal_saida_id': cenario.pk if cenario else None,
        'endereco_fiscal': endereco_result.to_dict() if endereco_result else {},
    }


def resolver_cenario_fiscal_saida_vigente(nf: NFeSaida) -> int | None:
    """Resolve o cenário comercial vinculado ao documento ou o padrão vigente.

    O snapshot fiscal do item é evidência histórica do que já foi calculado e
    não pode escolher a regra da próxima atualização. Caso contrário, uma NF-e
    continuaria sendo comparada a um cenário antigo mesmo após o cenário padrão
    ter sido alterado.
    """
    pedido = nf.pedido_venda
    if pedido and pedido.proposta_id and pedido.proposta:
        prop = pedido.proposta
        if prop.cenario_fiscal_saida_id:
            return prop.cenario_fiscal_saida_id
    snap_conv = (pedido.snapshot_conversao or {}) if pedido else {}
    raw = snap_conv.get('cenario_fiscal_saida_id')
    if raw:
        try:
            return int(raw)
        except (TypeError, ValueError):
            pass
    from apps.regras_fiscais.cenario_fiscal_saida import garantir_cenario_saida_padrao

    cenario = garantir_cenario_saida_padrao()
    return cenario.pk if cenario else None


def _resolver_cenario_id_nf(nf: NFeSaida, item: ItemNFeSaida) -> int | None:
    """Compatibilidade interna para as buscas de regra por item."""
    _ = item
    return resolver_cenario_fiscal_saida_vigente(nf)


def _flatten_compare(snap: dict | None) -> dict[str, str]:
    snap = snap or {}
    full_ref = get_reforma_tributaria_snapshot(snap) or {}
    out = {
        'cenario_fiscal_saida_id': _text(snap.get('cenario_fiscal_saida_id')),
        'regra_fiscal_saida_id': _text(snap.get('regra_fiscal_saida_id')),
        'cfop': cfop_from_snapshot_fiscal(snap),
        'cst_icms': _text(snap.get('cst_icms') or snap.get('CSOSN') or snap.get('csosn')),
        'modalidade_bc_icms': _text(snap.get('modalidade_bc_icms') or snap.get('mod_bc_icms')),
        'reducao_bc_icms': _text(snap.get('reducao_bc_icms') or snap.get('p_red_bc')),
        'base_icms': _text(snap.get('base_icms') or snap.get('v_bc_icms')),
        'aliquota_icms': _text(snap.get('aliquota_icms') or snap.get('icms_saida_percentual')),
        'valor_icms': _text(snap.get('valor_icms') or snap.get('v_icms')),
        'codigo_beneficio_icms': _text(snap.get('codigo_beneficio_icms')),
        'motivo_desoneracao_icms': _text(snap.get('motivo_desoneracao_icms')),
        'cst_ipi': _text(snap.get('cst_ipi')),
        'aliquota_ipi': _text(snap.get('aliquota_ipi') or snap.get('ipi_saida_percentual')),
        'valor_ipi': _text(snap.get('valor_ipi') or snap.get('v_ipi')),
        'cst_pis': _text(snap.get('cst_pis')),
        'aliquota_pis': _text(snap.get('aliquota_pis') or snap.get('pis_saida_percentual')),
        'valor_pis': _text(snap.get('valor_pis') or snap.get('v_pis')),
        'cst_cofins': _text(snap.get('cst_cofins')),
        'aliquota_cofins': _text(snap.get('aliquota_cofins') or snap.get('cofins_saida_percentual')),
        'valor_cofins': _text(snap.get('valor_cofins') or snap.get('v_cofins')),
        'cst_ibs_cbs': _text(full_ref.get('cst_ibs_cbs')),
        'classificacao_tributaria': _text(full_ref.get('classificacao_tributaria')),
        'aliquota_cbs': _text(full_ref.get('aliquota_cbs')),
        'valor_cbs': _text(full_ref.get('valor_cbs')),
        'aliquota_ibs_estadual': _text(full_ref.get('aliquota_ibs_estadual')),
        'valor_ibs_estadual': _text(full_ref.get('valor_ibs_estadual') or full_ref.get('valor_ibs_uf')),
        'difal_v_icms_uf_dest': _text((snap.get('difal') or {}).get('v_icms_uf_dest')),
        'difal_v_fcp_uf_dest': _text((snap.get('difal') or {}).get('v_fcp_uf_dest')),
    }
    return out


def _diff_snapshots(antes: dict | None, depois: dict | None) -> list[dict[str, str]]:
    flat_a = _flatten_compare(antes)
    flat_d = _flatten_compare(depois)
    alteracoes: list[dict[str, str]] = []
    for campo, label in _CAMPOS_COMPARACAO:
        a = flat_a.get(campo, '')
        d = flat_d.get(campo, '')
        if a != d:
            alteracoes.append(
                {
                    'campo': campo,
                    'label': label,
                    'antes': a or '—',
                    'depois': d or '—',
                },
            )
    ra = normalizar_recomendacoes_nfe((antes or {}).get('recomendacoes_nfe')) or {}
    rd = normalizar_recomendacoes_nfe((depois or {}).get('recomendacoes_nfe')) or {}
    if ra != rd and rd:
        qtd = sum(1 for v in rd.values() if v)
        alteracoes.append(
            {
                'campo': 'recomendacoes_nfe',
                'label': 'Recomendações NF-e',
                'antes': '—' if not ra else f'{sum(1 for v in ra.values() if v)} ativa(s)',
                'depois': f'{qtd} ativa(s)',
            },
        )
    return alteracoes


def _montar_reforma_no_snapshot(
    regra: RegraFiscalSaida | None,
    busca: BuscaRegraFiscalSaidaDict,
    *,
    valor_produto: Decimal,
    valor_icms: Decimal = Decimal('0'),
    valor_pis: Decimal = Decimal('0'),
    valor_cofins: Decimal = Decimal('0'),
    valor_ipi: Decimal = Decimal('0'),
) -> dict[str, Any] | None:
    if not busca.get('tem_reforma_configurada') or regra is None:
        return None
    return aplicar_reforma_tributaria_item(
        regra.reforma_tributaria,
        valor_produto=valor_produto,
        valor_icms=valor_icms,
        valor_pis=valor_pis,
        valor_cofins=valor_cofins,
        valor_ipi=valor_ipi,
    )


def montar_snapshot_fiscal_de_regra_atual(
    nf: NFeSaida,
    item: ItemNFeSaida,
    busca: BuscaRegraFiscalSaidaDict,
    regra: RegraFiscalSaida | None,
) -> dict[str, Any]:
    v_prod = _valor_produto_item(item)
    ncm = _ncm_item(item)
    cst_icms = _text(busca.get('cst_icms'))
    icms_ali = _dec(busca.get('aliquota_icms'))
    reducao_bc = _dec(busca.get('reducao_bc_icms')) if busca.get('reducao_bc_icms') else None
    modalidade_bc = _text(busca.get('modalidade_bc_icms'))
    ipi_ali = _dec(busca.get('aliquota_ipi'))
    pis_ali = _dec(busca.get('aliquota_pis'))
    cofins_ali = _dec(busca.get('aliquota_cofins'))

    base_icms, v_icms = calcular_base_valor_icms_saida(
        v_prod,
        icms_ali,
        reducao_bc_pct=reducao_bc,
        cst_icms=cst_icms,
    )
    v_ipi = (v_prod * ipi_ali / Decimal('100')).quantize(Decimal('0.01')) if ipi_ali else Decimal('0')

    base_pis, base_cofins, _msgs = calcular_base_pis_cofins_saida(
        v_prod,
        v_icms,
        deduzir_icms_base_pis=bool(busca.get('deduzir_icms_base_pis')),
        deduzir_icms_base_cofins=bool(busca.get('deduzir_icms_base_cofins')),
        aliquota_icms_pct=icms_ali,
    )
    v_pis = (base_pis * pis_ali / Decimal('100')).quantize(Decimal('0.01')) if pis_ali else Decimal('0')
    v_cofins = (base_cofins * cofins_ali / Decimal('100')).quantize(Decimal('0.01')) if cofins_ali else Decimal('0')

    cfop = _text(busca.get('cfop'))
    snap: dict[str, Any] = {
        'origem_regra_fiscal_saida': busca['origem'],
        'regra_fiscal_saida_id': busca.get('regra_id'),
        'regra_fiscal_legada_id': busca.get('regra_legada_id'),
        'ncm': ncm,
        'cfop': cfop,
        'cfop_venda': cfop,
        'cfop_saida': cfop,
        'cfop_st': _text(busca.get('cfop_st')),
        'cst_icms': cst_icms,
        'csosn': cst_icms,
        'modalidade_bc_icms': modalidade_bc,
        'reducao_bc_icms': _text(busca.get('reducao_bc_icms')),
        'codigo_beneficio_icms': codigo_beneficio_icms_para_snapshot(busca.get('codigo_beneficio_icms')),
        'motivo_desoneracao_icms': _text(busca.get('motivo_desoneracao_icms')),
        'icms_saida_percentual': _text(busca.get('aliquota_icms')),
        'aliquota_icms': _text(busca.get('aliquota_icms')),
        'base_icms': _q2(base_icms),
        'valor_icms': _q2(v_icms),
        'cst_ipi': _text(busca.get('cst_ipi')),
        'ipi_saida_percentual': _text(busca.get('aliquota_ipi')),
        'aliquota_ipi': _text(busca.get('aliquota_ipi')),
        'base_ipi': _q2(v_prod),
        'valor_ipi': _q2(v_ipi),
        'cst_pis': _text(busca.get('cst_pis')),
        'pis_saida_percentual': _text(busca.get('aliquota_pis')),
        'aliquota_pis': _text(busca.get('aliquota_pis')),
        'base_pis': _q2(base_pis),
        'valor_pis': _q2(v_pis),
        'cst_cofins': _text(busca.get('cst_cofins')),
        'cofins_saida_percentual': _text(busca.get('aliquota_cofins')),
        'aliquota_cofins': _text(busca.get('aliquota_cofins')),
        'base_cofins': _q2(base_cofins),
        'valor_cofins': _q2(v_cofins),
        'deduzir_icms_base_pis': bool(busca.get('deduzir_icms_base_pis')),
        'deduzir_icms_base_cofins': bool(busca.get('deduzir_icms_base_cofins')),
        'atualizado_por_acao': 'ATUALIZAR_IMPOSTOS_NFE',
        'atualizado_em': timezone.now().isoformat(),
        'fonte': 'REGRA_FISCAL_ATUAL',
    }
    if regra is not None:
        snap['regra_fiscal_saida_nome'] = _text(regra.nome) or _text(regra.descricao_cenario)
        snap['cenario_fiscal_saida_id'] = regra.cenario_id
        if regra.cenario_id:
            snap['cenario_fiscal_saida_nome'] = _text(regra.cenario.nome) if regra.cenario else ''
        if regra.fcp_aplicavel:
            snap['fcp_aplicavel'] = True
            snap['aliquota_fcp'] = _q2(_dec(regra.aliquota_fcp))
        if regra.icms_st_aplicavel:
            snap['icms_st_aplicavel'] = True
            snap['aliquota_icms_st'] = _q2(_dec(regra.aliquota_icms_st))
    reforma = _montar_reforma_no_snapshot(
        regra,
        busca,
        valor_produto=v_prod,
        valor_icms=v_icms,
        valor_pis=v_pis,
        valor_cofins=v_cofins,
        valor_ipi=v_ipi,
    )
    if reforma:
        snap['reforma_tributaria'] = reforma
    if regra is not None:
        norm_rec = normalizar_recomendacoes_nfe(regra.recomendacoes_nfe)
        if norm_rec:
            snap['recomendacoes_nfe'] = norm_rec

    ufo = _uf_origem_nf(nf)
    ufd = _uf_destino_nf(nf)
    perfil = resolver_perfil_destinatario_nf(nf)
    if regra is not None and deve_aplicar_difal(
        uf_origem=ufo,
        uf_destino=ufd,
        destinatario_contribuinte=perfil.destinatario_contribuinte,
        consumidor_final=perfil.consumidor_final,
        regra=regra,
    ):
        pendencias_difal = validar_parametros_difal_regra(
            regra,
            uf_destino=ufd,
            nome_item=_descricao_item(item),
        )
        if pendencias_difal:
            snap['difal_pendencias'] = pendencias_difal
        else:
            snap['difal'] = calcular_difal_item(v_prod, regra)
            snap['difal_aplicavel'] = True
    else:
        snap.pop('difal', None)
        snap.pop('difal_aplicavel', None)
        snap.pop('difal_pendencias', None)

    return normalize_snapshot_fiscal_for_nfe(snap)


def _buscar_regra_para_item(
    nf: NFeSaida,
    item: ItemNFeSaida,
    *,
    endereco_result: EnderecoFiscalResult | None = None,
) -> tuple[BuscaRegraFiscalSaidaDict, RegraFiscalSaida | None, list[str], dict[str, Any]]:
    alertas: list[str] = []
    ncm = _ncm_item(item)
    ufo = _uf_origem_nf(nf)
    ufd = _uf_destino_nf(nf, endereco_result)

    if endereco_result and endereco_result.bloqueio_fiscal:
        cliente = _cliente_nf(nf)
        msg = mensagem_endereco_inconsistente_nf(cliente, endereco_result) if cliente else 'Cliente não informado.'
        return _resultado_nao_encontrada(), None, [msg], {}

    if len(ncm) < 8:
        if item.produto_id and not ncm:
            ncm = _text(item.produto.get_ncm_efetivo_codigo() or item.produto.ncm)
    if len(ncm) < 8 or len(ufo) != 2 or len(ufd) != 2:
        msg = _mensagem_regra_nao_encontrada(ncm, ufo, ufd)
        if len(ncm) < 8:
            msg = 'NCM incompleto para buscar regra fiscal.'
        return _resultado_nao_encontrada(), None, [msg], {}

    ncm_busca = normalize_ncm(ncm)
    cenario_id = _resolver_cenario_id_nf(nf, item)
    perfil = resolver_perfil_destinatario_nf(nf)

    busca, regra, filtros_busca = buscar_regra_fiscal_nfe_saida_rascunho(
        produto_id=item.produto_id,
        ncm=ncm_busca,
        uf_origem=ufo,
        uf_destino=ufd,
        cenario_id=cenario_id,
        produto=item.produto if item.produto_id else None,
        destinatario_contribuinte=perfil.destinatario_contribuinte,
        consumidor_final=perfil.consumidor_final,
        tipo_operacao='VENDA',
    )
    if busca['origem'] == 'NAO_ENCONTRADA':
        alertas.append(_mensagem_regra_nao_encontrada(ncm_busca, ufo, ufd))
        if filtros_busca.get('regras_descartadas'):
            alertas.extend(filtros_busca['regras_descartadas'])
    elif regra is not None:
        cfop = _text(busca.get('cfop'))
        alertas.append(
            f'Regra fiscal aplicada: NCM {ncm_busca} · {ufo}→{ufd} · CFOP {cfop or "—"}.',
        )
    return busca, regra, alertas, filtros_busca


def _descricao_item(item: ItemNFeSaida) -> str:
    if item.snapshot_produto and item.snapshot_produto.get('descricao'):
        return str(item.snapshot_produto['descricao'])
    if item.produto_id:
        return item.produto.descricao
    return f'Item #{item.pk}'


def _processar_item_preview(
    nf: NFeSaida,
    item: ItemNFeSaida,
    *,
    endereco_result: EnderecoFiscalResult | None = None,
    contexto_fiscal: dict[str, Any] | None = None,
) -> dict[str, Any]:
    snap_antes = deepcopy(item.snapshot_fiscal) or {}
    busca, regra, alertas_ctx, filtros_busca = _buscar_regra_para_item(nf, item, endereco_result=endereco_result)
    item_alertas = list(alertas_ctx)
    regra_encontrada = busca['origem'] != 'NAO_ENCONTRADA'
    ncm = _ncm_item(item)
    ncm_norm = normalize_ncm(ncm)
    ufo = _uf_origem_nf(nf)
    ufd = _uf_destino_nf(nf, endereco_result)

    if not regra_encontrada:
        if endereco_result and endereco_result.bloqueio_fiscal:
            diagnostico = {
                'tipo': 'ENDERECO_INCONSISTENTE',
                'pendencia': 'Cliente com endereço fiscal inconsistente.',
                'detalhe': item_alertas[0] if item_alertas else mensagem_endereco_inconsistente_nf(_cliente_nf(nf), endereco_result),
            }
        else:
            detalhe = _mensagem_regra_nao_encontrada(ncm_norm, ufo, ufd)
            diagnostico = {
                'tipo': 'REGRA_NAO_ENCONTRADA',
                'pendencia': 'Regra fiscal não encontrada.',
                'detalhe': detalhe,
                'auditoria_busca': filtros_busca,
            }
        return {
            'item_id': item.pk,
            'produto_nome': _descricao_item(item),
            'ncm': ncm_norm or ncm,
            'regra_encontrada': False,
            'regra_fiscal_saida_id': None,
            'regra_fiscal_saida_nome': '',
            'alteracoes': [],
            'alertas': item_alertas,
            'contexto_fiscal': contexto_fiscal or {},
            'diagnostico': diagnostico,
        }

    snap_depois = montar_snapshot_fiscal_de_regra_atual(nf, item, busca, regra)
    alteracoes = _diff_snapshots(snap_antes, snap_depois)
    if busca.get('mensagens'):
        item_alertas.extend(busca['mensagens'])

    cfop = _text(busca.get('cfop'))
    info = f'Regra fiscal aplicada: NCM {ncm_norm or ncm} · {ufo}→{ufd} · CFOP {cfop or "—"}.'
    msg_ref = mensagem_reforma_aplicada(snap_depois.get('reforma_tributaria'))
    if msg_ref:
        info = f'{info} {msg_ref}'
        item_alertas.append(msg_ref)
    return {
        'item_id': item.pk,
        'produto_nome': _descricao_item(item),
        'ncm': ncm_norm or ncm,
        'regra_encontrada': True,
        'regra_fiscal_saida_id': busca.get('regra_id'),
        'regra_fiscal_saida_nome': _text(regra.nome) if regra else '',
        'alteracoes': alteracoes,
        'alertas': item_alertas,
        'contexto_fiscal': contexto_fiscal or {},
        'diagnostico': {
            'tipo': 'REGRA_APLICADA',
            'informacao': info,
            'auditoria_busca': filtros_busca,
        },
        '_snapshot_novo': snap_depois,
    }


def _validar_pode_atualizar(nf: NFeSaida) -> tuple[bool, str]:
    if nf_ja_finalizada_operacionalmente(nf):
        return False, MSG_BLOQUEIO_STATUS
    if (nf.status or '').strip().upper() != STATUS_NFE_RASCUNHO:
        return False, MSG_BLOQUEIO_STATUS
    if not ItemNFeSaida.objects.filter(nf_id=nf.pk).exists():
        return False, 'NF-e sem itens para atualizar impostos.'
    return True, ''


def preparar_atualizacao_impostos_nfe(nf: NFeSaida, *, usuario=None) -> dict[str, Any]:
    pode, msg = _validar_pode_atualizar(nf)
    if not pode:
        return {
            'nfe_saida_id': nf.pk,
            'pode_aplicar': False,
            'bloqueado': True,
            'mensagem': msg,
            'resumo': {},
            'itens': [],
            'alertas': [msg],
        }

    nf = (
        NFeSaida.objects.select_related('cliente', 'pedido_venda', 'pedido_venda__cliente', 'pedido_venda__empresa_emitente', 'pedido_venda__proposta')
        .prefetch_related('itens__produto')
        .get(pk=nf.pk)
    )

    cep_cache: dict[str, dict[str, str] | None] = {}
    cliente = _cliente_nf(nf)
    endereco_result = (
        validar_endereco_fiscal(cliente, consultar_cep=True, cep_cache=cep_cache)
        if cliente
        else EnderecoFiscalResult(
            consistente=False,
            bloqueio_fiscal=True,
            pendencias=['Cliente não informado na NF-e.'],
        )
    )
    contexto_fiscal = _montar_contexto_fiscal_nf(nf, endereco_result=endereco_result)

    itens_rows: list[dict[str, Any]] = []
    alertas_globais: list[str] = []
    if endereco_result.bloqueio_fiscal and cliente:
        alertas_globais.append(mensagem_endereco_inconsistente_nf(cliente, endereco_result))
    elif endereco_result.pendencias:
        alertas_globais.extend(endereco_result.pendencias)
    com_regra = sem_regra = com_alt = sem_alt = reforma_cfg = 0
    regras_coletadas: list[RegraFiscalSaida] = []

    for item in nf.itens.all().order_by('pk'):
        row = _processar_item_preview(
            nf,
            item,
            endereco_result=endereco_result,
            contexto_fiscal=contexto_fiscal,
        )
        snap_novo = row.pop('_snapshot_novo', None) or {}
        itens_rows.append(row)
        if row['regra_encontrada']:
            com_regra += 1
            _busca, regra, _, _ = _buscar_regra_para_item(nf, item, endereco_result=endereco_result)
            if regra is not None:
                regras_coletadas.append(regra)
        else:
            sem_regra += 1
        if row['alteracoes']:
            com_alt += 1
        else:
            sem_alt += 1
        if reforma_tributaria_preenchida(snap_novo.get('reforma_tributaria')):
            reforma_cfg += 1
        alertas_globais.extend(row.get('alertas') or [])

    textos_fiscais = calcular_textos_fiscais_preview(nf, regras_coletadas)
    textos_alt = len(textos_fiscais.get('alteracoes') or [])
    rec_sug = len(textos_fiscais.get('recomendacoes') or [])

    tem_alteracao_item = com_alt > 0
    tem_textos = textos_alt > 0
    tem_rec_snapshot = any(
        any(a.get('campo') == 'recomendacoes_nfe' for a in (row.get('alteracoes') or []))
        for row in itens_rows
    )
    reaplicar_pos_emissao = nf_permite_reaplicar_fiscal_pos_emissao(nf)
    pode_aplicar = (
        com_regra > 0
        and (tem_alteracao_item or tem_textos or tem_rec_snapshot or reaplicar_pos_emissao)
        and not endereco_result.bloqueio_fiscal
    )

    if endereco_result.bloqueio_fiscal:
        alertas_globais.append('Corrija o endereço fiscal do cliente antes de aplicar regra fiscal.')
    elif reaplicar_pos_emissao and com_regra and not tem_alteracao_item and not tem_textos:
        alertas_globais.append(
            'NF-e com rejeição/erro SEFAZ: confirme para reaplicar os snapshots fiscais, '
            'invalidar o XML da tentativa anterior e revalidar a conferência antes de emitir novamente.',
        )
    elif com_regra and not pode_aplicar:
        alertas_globais.append('Nenhuma alteração fiscal ou texto fiscal encontrado com a regra atual.')
    elif tem_textos and not tem_alteracao_item:
        alertas_globais.append('Há textos fiscais/recomendações para aplicar.')

    return {
        'nfe_saida_id': nf.pk,
        'pode_aplicar': pode_aplicar,
        'reaplicar_fiscal_pos_emissao': reaplicar_pos_emissao,
        'bloqueado': False,
        'mensagem': '',
        'resumo': {
            'itens_total': len(itens_rows),
            'itens_com_regra': com_regra,
            'itens_sem_regra': sem_regra,
            'itens_com_alteracao': com_alt,
            'itens_sem_alteracao': sem_alt,
            'reforma_configurada': reforma_cfg,
            'textos_fiscais_sugeridos': textos_alt,
            'recomendacoes_sugeridas': rec_sug,
        },
        'itens': itens_rows,
        'textos_fiscais': textos_fiscais,
        'alertas': list(dict.fromkeys(alertas_globais)),
        'contexto_fiscal': contexto_fiscal,
        'diagnosticos': [
            row['diagnostico']
            for row in itens_rows
            if row.get('diagnostico')
        ],
    }


def sincronizar_cenario_fiscal_para_prontidao(nf: NFeSaida, *, usuario=None) -> dict[str, Any]:
    """Alinha snapshots ao cenário vigente antes da confirmação de emissão.

    A sincronização só é aplicada em NF-e rascunho, não modifica dados
    comerciais e não permite atualização parcial: se algum item não possuir
    cobertura fiscal, nada é gravado e a conferência continua bloqueada.
    """
    preview = preparar_atualizacao_impostos_nfe(nf, usuario=usuario)
    if preview.get('bloqueado'):
        raise ValueError(preview.get('mensagem') or MSG_BLOQUEIO_STATUS)

    resumo = preview.get('resumo') or {}
    itens_sem_regra = int(resumo.get('itens_sem_regra') or 0)
    if itens_sem_regra:
        raise ValueError(
            'Não foi possível sincronizar o cenário fiscal: '
            f'{itens_sem_regra} item(ns) sem regra aplicável. Corrija a cobertura fiscal antes de marcar a NF-e como pronta.',
        )

    if not preview.get('pode_aplicar'):
        return {
            'aplicado': False,
            'itens_atualizados': 0,
            'preview': preview,
            'mensagem': 'Snapshots fiscais já estão alinhados ao cenário vigente.',
        }

    resultado = aplicar_atualizacao_impostos_nfe(
        nf,
        usuario=usuario,
        motivo='Sincronização automática com o cenário fiscal vigente antes de marcar a NF-e como pronta para emissão.',
    )
    return {
        **resultado,
        'aplicado': True,
        'mensagem': (
            'Cenário fiscal vigente aplicado antes da confirmação de prontidão. '
            'Os dados comerciais foram preservados.'
        ),
    }


def aplicar_atualizacao_impostos_nfe(
    nf: NFeSaida,
    *,
    usuario=None,
    motivo: str = '',
) -> dict[str, Any]:
    preview = preparar_atualizacao_impostos_nfe(nf, usuario=usuario)
    if preview.get('bloqueado'):
        raise ValueError(preview.get('mensagem') or MSG_BLOQUEIO_STATUS)
    if not preview.get('pode_aplicar'):
        raise ValueError(
            preview.get('alertas', ['Nenhuma alteração fiscal para aplicar.'])[0]
            if preview.get('alertas')
            else 'Nenhuma alteração fiscal para aplicar.',
        )

    reaplicar_pos_emissao = bool(preview.get('reaplicar_fiscal_pos_emissao'))

    motivo_txt = (motivo or '').strip() or 'Atualização fiscal a partir da regra fiscal atual.'

    with transaction.atomic():
        nf_locked = _lock_nfe_saida(nf.pk)
        pode, msg = _validar_pode_atualizar(nf_locked)
        if not pode:
            raise ValueError(msg)

        itens_db = list(
            ItemNFeSaida.objects.select_for_update()
            .filter(nf_id=nf_locked.pk)
            .select_related('produto')
            .order_by('pk'),
        )

        regras_aplicar: list[RegraFiscalSaida] = []
        aplicados = 0
        alteracoes_por_item: list[dict[str, Any]] = []
        nf_locked = (
            NFeSaida.objects.select_related('cliente', 'pedido_venda', 'pedido_venda__cliente')
            .get(pk=nf_locked.pk)
        )
        cliente_locked = _cliente_nf(nf_locked)
        endereco_locked = (
            validar_endereco_fiscal(cliente_locked, consultar_cep=True)
            if cliente_locked
            else EnderecoFiscalResult(bloqueio_fiscal=True)
        )
        if endereco_locked.bloqueio_fiscal:
            raise ValueError(
                mensagem_endereco_inconsistente_nf(cliente_locked, endereco_locked)
                if cliente_locked
                else 'Cliente não informado na NF-e.',
            )

        for item in itens_db:
            row = _processar_item_preview(
                nf_locked,
                item,
                endereco_result=endereco_locked,
            )
            if not row['regra_encontrada']:
                continue
            _, regra, _, filtros_evt = _buscar_regra_para_item(
                nf_locked,
                item,
                endereco_result=endereco_locked,
            )
            if regra is not None:
                regras_aplicar.append(regra)
            if not row['alteracoes'] and not reaplicar_pos_emissao:
                continue
            snap_novo = row['_snapshot_novo']
            snap_antes = item.snapshot_fiscal or {}
            merged = normalize_snapshot_fiscal_for_nfe({**snap_antes, **snap_novo})
            merged, _ = mesclar_recomendacoes_snapshot(merged, regra)
            item.snapshot_fiscal = merged
            item.save(update_fields=['snapshot_fiscal'])
            aplicados += 1
            diag = row.get('diagnostico') or {}
            alteracoes_por_item.append(
                {
                    'item_id': item.pk,
                    'alteracoes': row['alteracoes'],
                    'auditoria_busca': diag.get('auditoria_busca') or filtros_evt,
                    'regra_aplicada': diag.get('informacao', ''),
                },
            )

        campos_txt, textos_aplicados, _ = aplicar_textos_fiscais_nf(nf_locked, regras_aplicar)
        if campos_txt:
            nf_locked.save(update_fields=list(campos_txt.keys()))

        regras_evt = [
            {
                'item_id': alt['item_id'],
                'filtros': alt.get('auditoria_busca'),
                'regra_aplicada': alt.get('regra_aplicada', ''),
            }
            for alt in alteracoes_por_item
        ]
        resumo_evt = {
            'itens_total': len(itens_db),
            'itens_com_regra': preview['resumo']['itens_com_regra'],
            'itens_sem_regra': preview['resumo']['itens_sem_regra'],
            'itens_com_alteracao': aplicados,
            'textos_fiscais_aplicados': textos_aplicados,
            'recomendacoes_aplicadas': preview['resumo'].get('recomendacoes_sugeridas', 0),
            'alteracoes_por_item': alteracoes_por_item,
            'textos_fiscais': preview.get('textos_fiscais'),
            'motivo': motivo_txt,
            'contexto_fiscal': preview.get('contexto_fiscal'),
            'fonte_consultada': 'CENARIO_SAIDA_PADRAO',
            'regras_aplicadas': regras_evt,
        }
        from apps.fiscal.nfe_integracao.nfe_xml_preliminar import invalidar_xml_preliminar_armazenado
        from apps.fiscal.nfe_saida_prontidao import invalidar_prontidao_apos_atualizar_fiscal

        invalidar_xml_preliminar_armazenado(nf_locked)
        if reaplicar_pos_emissao:
            campos_xml = _limpar_xml_emissao_para_reaplicar_fiscal(nf_locked)
            nf_locked.save(update_fields=campos_xml)
        invalidar_prontidao_apos_atualizar_fiscal(nf_locked, usuario=usuario)

        if aplicados > 0 and preview['resumo']['itens_com_regra'] > 0:
            obs_evt = (
                f'Atualização fiscal executada. Regra aplicada no cenário padrão de saída. '
                f'{aplicados} item(ns) com alteração fiscal. Dados comerciais preservados. {motivo_txt}'
            )
        elif reaplicar_pos_emissao and aplicados > 0:
            obs_evt = (
                f'Reaplicação fiscal após rejeição/erro SEFAZ. {aplicados} item(ns) '
                f'com snapshot fiscal normalizado. XML anterior invalidado. {motivo_txt}'
            )
        elif preview['resumo']['itens_sem_regra'] > 0:
            obs_evt = (
                f'Atualização fiscal executada. Nenhuma regra aplicável no cenário padrão de saída. '
                f'{preview["resumo"]["itens_sem_regra"]} item(ns) sem regra. {motivo_txt}'
            )
        else:
            obs_evt = (
                f'Impostos/textos fiscais atualizados. {motivo_txt} · '
                f'{aplicados} item(ns), {textos_aplicados} texto(s) NF-e.'
            )
        _registrar_evento(
            nf_locked,
            tipo=NFeSaidaEvento.TipoEvento.IMPOSTOS_ATUALIZADOS,
            observacao=obs_evt,
            resumo=resumo_evt,
            usuario=usuario,
        )

    from apps.fiscal.nfe_saida_conferencia import montar_conferencia_nfe_saida

    nf_refresh = NFeSaida.objects.get(pk=nf.pk)
    resultado = {
        'nfe_saida_id': nf.pk,
        'aplicado': True,
        'itens_atualizados': aplicados,
        'preview': preview,
        'conferencia': montar_conferencia_nfe_saida(nf_refresh, modo='abertura', incluir_checklist=False),
        'mensagem': 'Fiscal e textos atualizados com sucesso.',
    }
    return resultado
