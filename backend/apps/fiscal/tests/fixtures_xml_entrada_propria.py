"""XML sintético para testes — sem dados reais de produção."""

from __future__ import annotations


def xml_nfe_entrada_propria_sintetico(
    *,
    chave: str,
    cnpj_emitente: str = '12345678000199',
    cnpj_destinatario: str = '98765432000188',
    tp_nf: str = '0',
    n_nf: str = '100',
    serie: str = '1',
    dh_emi: str = '2026-01-15T10:00:00-03:00',
    v_nf: str = '1500.00',
) -> bytes:
    """NF-e entrada própria: emitente = empresa (tpNF=0)."""
    cnpj_e = ''.join(c for c in cnpj_emitente if c.isdigit())
    cnpj_d = ''.join(c for c in cnpj_destinatario if c.isdigit())
    ch = ''.join(c for c in chave if c.isdigit())[:44].ljust(44, '0')
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">
<NFe xmlns="http://www.portalfiscal.inf.br/nfe">
<infNFe Id="NFe{ch}" versao="4.00">
<ide>
<tpNF>{tp_nf}</tpNF>
<tpAmb>1</tpAmb>
<nNF>{n_nf}</nNF>
<serie>{serie}</serie>
<mod>55</mod>
<natOp>DEVOLUCAO</natOp>
<dhEmi>{dh_emi}</dhEmi>
</ide>
<emit>
<CNPJ>{cnpj_e}</CNPJ>
<xNome>EMPRESA TESTE ENTRADA PROPRIA</xNome>
</emit>
<dest>
<CNPJ>{cnpj_d}</CNPJ>
<xNome>CLIENTE TESTE DESTINATARIO</xNome>
</dest>
<det nItem="1">
<prod>
<cProd>001</cProd>
<xProd>ITEM TESTE</xProd>
<NCM>84818095</NCM>
<CFOP>1202</CFOP>
<uCom>UN</uCom>
<qCom>1.0000</qCom>
<vUnCom>1500.00</vUnCom>
<vProd>1500.00</vProd>
</prod>
<imposto><ICMS><ICMS00><CST>00</CST></ICMS00></ICMS></imposto>
</det>
<total><ICMSTot><vProd>1500.00</vProd><vNF>{v_nf}</vNF></ICMSTot></total>
</infNFe>
</NFe>
<protNFe versao="4.00"><infProt>
<chNFe>{ch}</chNFe>
<nProt>000000000000001</nProt>
<cStat>100</cStat>
<xMotivo>Autorizado</xMotivo>
</infProt></protNFe>
</nfeProc>""".encode('utf-8')


def xml_nfe_compra_fornecedor_sintetico(
    *,
    chave: str,
    cnpj_fornecedor: str = '11111111000111',
    cnpj_destinatario: str = '12345678000199',
) -> bytes:
    """NF-e compra: destinatário = empresa, emitente = fornecedor (tpNF=1)."""
    return xml_nfe_entrada_propria_sintetico(
        chave=chave,
        cnpj_emitente=cnpj_fornecedor,
        cnpj_destinatario=cnpj_destinatario,
        tp_nf='1',
        n_nf='200',
    )
