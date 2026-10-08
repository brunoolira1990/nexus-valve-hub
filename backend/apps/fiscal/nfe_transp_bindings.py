"""Bindings NF-e 4.00 — grupo transp (transportadora, volumes, veículo)."""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from apps.fiscal.models import NFeSaida
from apps.fiscal.nfe_saida_xml_nfelib import _dec_field, _digits, _text
from apps.fiscal.nfe_xml_higienizacao import normalizar_ie_xml

XENDER_TRANSPORTADORA_MAX = 60


def _dec_str(v: Any, places: int = 2) -> str:
    from apps.core.pdf.formatters import dec

    return f'{dec(v):.{places}f}'


def normalizar_xender_transportadora_xml(texto: str | None) -> str:
    """Remove espaços/vírgulas finais e colapsa whitespace — compatível com TString do XSD."""
    s = _text(texto)
    if not s:
        return ''
    s = re.sub(r'\s+', ' ', s)
    s = re.sub(r'[,;\s]+$', '', s)
    return s.strip()


def montar_xender_transportadora(
    logradouro: str | None,
    numero: str | None,
    complemento: str | None = None,
) -> str:
    """
    Monta transporta/xEnder: logradouro + número (+ complemento se couber).
    Não inclui bairro, cidade, UF ou CEP (vão em xMun/UF).
    """
    logr = _text(logradouro)
    nro = _text(numero)
    comp = _text(complemento)

    linha = ' '.join(p for p in (logr, nro) if p).strip()
    if comp and linha:
        candidato = f'{linha} {comp}'.strip()
        if len(candidato) <= XENDER_TRANSPORTADORA_MAX:
            linha = candidato
    elif comp and not linha:
        linha = comp

    return normalizar_xender_transportadora_xml(linha)[:XENDER_TRANSPORTADORA_MAX]


def montar_transporte_dados_nfe(nf: NFeSaida) -> dict[str, Any]:
    """Dados de transporte da NF-e para preview, XML preliminar e XML oficial."""
    tr = nf.transportadora if nf.transportadora_id else None
    ender = ''
    if tr:
        ender = montar_xender_transportadora(tr.logradouro, tr.numero, tr.complemento)
    placa = _text(nf.placa_veiculo) or (_text(tr.placa_padrao) if tr else '')
    uf_veic = _text(nf.uf_veiculo) or (_text(tr.uf_placa) if tr else '')

    return {
        'mod_frete': _text(nf.modalidade_frete) or '9',
        'transportadora_nome': _text(tr.razao_social) if tr else '',
        'transportadora_cnpj': _digits(tr.cnpj) if tr else '',
        'transportadora_ie': _text(tr.ie) if tr else '',
        'transportadora_ender': ender,
        'transportadora_mun': _text(tr.cidade) if tr else '',
        'transportadora_uf': (_text(tr.uf) if tr else '')[:2],
        'valor_frete': _dec_str(nf.valor_frete),
        'quantidade_volumes': int(nf.quantidade_volumes or 0),
        'especie_volumes': _text(nf.especie_volumes),
        'marca_volumes': _text(nf.marca_volumes),
        'numeracao_volumes': _text(nf.numeracao_volumes),
        'peso_bruto': _dec_str(nf.peso_bruto),
        'peso_liquido': _dec_str(nf.peso_liquido),
        'placa_veiculo': placa.replace('-', '').upper()[:7],
        'uf_veiculo': uf_veic.upper()[:2],
    }


def aplicar_transp_nfelib(inf: Any, nfe_module: Any, transporte: dict[str, Any] | None) -> None:
    """Preenche inf.transp no binding nfelib (Tnfe)."""
    tr = transporte or {}
    mod_frete = _text(tr.get('mod_frete')) or '9'
    inf.transp = nfe_module.Tnfe.InfNfe.Transp(modFrete=mod_frete)

    if mod_frete == '9':
        return

    transp_kw: dict[str, Any] = {}
    cnpj = _digits(tr.get('transportadora_cnpj'), max_len=14)
    if len(cnpj) == 14:
        transp_kw['CNPJ'] = cnpj
    elif len(cnpj) == 11:
        transp_kw['CPF'] = cnpj
    nome = _text(tr.get('transportadora_nome'))
    if nome:
        transp_kw['xNome'] = nome[:60]
    ie = normalizar_ie_xml(tr.get('transportadora_ie'))
    if ie and ie != 'ISENTO':
        transp_kw['IE'] = ie
    ender = normalizar_xender_transportadora_xml(_text(tr.get('transportadora_ender')))
    if ender:
        transp_kw['xEnder'] = ender[:XENDER_TRANSPORTADORA_MAX]
    mun = _text(tr.get('transportadora_mun'))
    if mun:
        transp_kw['xMun'] = mun[:60]
    uf = _text(tr.get('transportadora_uf'))
    if uf:
        transp_kw['UF'] = uf[:2]
    if transp_kw:
        inf.transp.transporta = nfe_module.Tnfe.InfNfe.Transp.Transporta(**transp_kw)

    vol_kw: dict[str, Any] = {}
    q_vol = int(tr.get('quantidade_volumes') or 0)
    if q_vol > 0:
        vol_kw['qVol'] = str(q_vol)
    esp = _text(tr.get('especie_volumes'))
    if esp:
        vol_kw['esp'] = esp[:60]
    marca = _text(tr.get('marca_volumes'))
    if marca:
        vol_kw['marca'] = marca[:60]
    n_vol = _text(tr.get('numeracao_volumes'))
    if n_vol:
        vol_kw['nVol'] = n_vol[:60]
    peso_b = tr.get('peso_bruto')
    if peso_b is not None and Decimal(str(peso_b or 0)) > 0:
        vol_kw['pesoB'] = _dec_field(peso_b, places=3)
    peso_l = tr.get('peso_liquido')
    if peso_l is not None and Decimal(str(peso_l or 0)) > 0:
        vol_kw['pesoL'] = _dec_field(peso_l, places=3)
    if vol_kw:
        inf.transp.vol = [nfe_module.Tnfe.InfNfe.Transp.Vol(**vol_kw)]

    placa = _text(tr.get('placa_veiculo')).replace('-', '').upper()[:7]
    uf_veic = _text(tr.get('uf_veiculo')).upper()[:2]
    if placa:
        veic_kw: dict[str, Any] = {'placa': placa}
        if uf_veic:
            veic_kw['UF'] = uf_veic
        inf.transp.veicTransp = nfe_module.Tnfe.InfNfe.Transp.VeicTransp(**veic_kw)
