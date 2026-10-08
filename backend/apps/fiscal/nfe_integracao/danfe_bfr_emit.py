"""Cabeçalho emitente DANFE BFR — logo à esquerda, dados compactos à direita."""

from __future__ import annotations

from typing import Any

from brazilfiscalreport.danfe.danfe_basic_field import DanfeBasicField
from brazilfiscalreport.danfe.danfe_block import DanfeBlock
from brazilfiscalreport.danfe.danfe_code import DanfeCode
from brazilfiscalreport.danfe.danfe_ident_info import DanfeIdentInfo
from brazilfiscalreport.danfe.danfe_verification_msg import DanfeVerificationMsg
from brazilfiscalreport.danfe.danfe_conf import URL
from brazilfiscalreport.pdf_element import Element
from brazilfiscalreport.utils import chunks, format_cep, format_cpf_cnpj, format_phone, get_tag_text


def extract_text(node, tag: str) -> str:
    return get_tag_text(node, URL, tag)


def montar_emit_extras_empresa(empresa) -> dict[str, str]:
    """E-mail, site e telefone do cadastro da empresa emitente."""
    extras: dict[str, str] = {}
    if not empresa:
        return extras
    try:
        extras['email'] = (getattr(empresa, 'email', None) or '').strip()
        extras['site'] = (getattr(empresa, 'site', None) or '').strip()
        extras['telefone'] = (getattr(empresa, 'telefone', None) or '').strip()
    except Exception:
        pass
    return extras


def montar_emit_extras_nfe_saida(nfe_saida) -> dict[str, str]:
    """E-mail, site e telefone do cadastro (telefone também como fallback do DANFE)."""
    try:
        pedido = getattr(nfe_saida, 'pedido_venda', None)
        emp = getattr(pedido, 'empresa_emitente', None) if pedido else None
        return montar_emit_extras_empresa(emp)
    except Exception:
        return {}


def montar_emit_extras_nfe_entrada(nfe_entrada) -> dict[str, str]:
    """Extras do emitente para DANFE de entrada própria (mesmo layout da saída)."""
    try:
        return montar_emit_extras_empresa(getattr(nfe_entrada, 'empresa_emitente', None))
    except Exception:
        return {}


def montar_endereco_emitente_bfr(emit_node, extras: dict[str, str] | None = None) -> str:
    """Endereço compacto: logradouro, município/UF, CEP, fone; e-mail/site se couber."""
    extras = extras or {}
    linhas: list[str] = []
    lgr = extract_text(emit_node, 'xLgr')
    nro = extract_text(emit_node, 'nro') or 'S/N'
    if lgr:
        linhas.append(f'{lgr}, {nro}')
    bairro = extract_text(emit_node, 'xBairro')
    mun = extract_text(emit_node, 'xMun')
    uf = extract_text(emit_node, 'UF')
    if mun:
        cidade = f'{bairro} {mun}'.strip() if bairro else mun
        linhas.append(f'{cidade} - {uf}' if uf else cidade)
    cep = format_cep(extract_text(emit_node, 'CEP'))
    if cep:
        linhas.append(cep)
    fone = format_phone(extract_text(emit_node, 'fone'))
    if not fone:
        from apps.fiscal.nfe_saida_xml_nfelib import fone_nfe_digits

        fone = format_phone(fone_nfe_digits(extras.get('telefone')) or '')
    if fone:
        linhas.append(fone if fone.lower().startswith('fone') else f'Fone: {fone}')
    email = _text(extras.get('email'))
    site = _text(extras.get('site'))
    if email and len(linhas) < 6:
        linhas.append(email)
    if site and len(linhas) < 6 and site != email:
        linhas.append(site)
    return '\n'.join(linhas[:6])


def _text(val: Any) -> str:
    return (str(val) if val is not None else '').strip()


def _quebrar_razao_social(pdf, nome: str, largura_mm: float, *, max_linhas: int = 2) -> list[str]:
    nome = _text(nome)
    if not nome:
        return ['Emitente']
    pdf.set_font(pdf.default_font, 'B', 7.5)
    palavras = nome.split()
    linhas: list[str] = []
    atual = ''
    for palavra in palavras:
        candidato = f'{atual} {palavra}'.strip()
        if pdf.get_string_width(candidato) <= largura_mm - 1:
            atual = candidato
        else:
            if atual:
                linhas.append(atual)
            atual = palavra
            if len(linhas) >= max_linhas:
                break
    if atual and len(linhas) < max_linhas:
        linhas.append(atual)
    if len(linhas) > max_linhas:
        linhas = linhas[:max_linhas]
    if len(linhas) == max_linhas and len(palavras) > len(' '.join(linhas).split()):
        ult = linhas[-1]
        if len(ult) > 28:
            linhas[-1] = ult[:28].rstrip() + '...'
    return linhas or [nome[:45]]


class DanfeEmitInfoNexus(Element):
    """Logo à esquerda; razão social (máx. 2 linhas) e endereço à direita."""

    def __init__(self, emit: str, address, logo_image=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.emit = emit
        self.logo_image = logo_image
        self.address = address

    def render(self):
        super().render()
        pad = 1.5
        h_logo = 24.0
        w_logo = 36.0
        y_top = self.y + 0.8

        if self.logo_image:
            self.pdf.image(
                name=self.logo_image,
                x=self.x + pad,
                y=y_top,
                w=w_logo,
                h=h_logo,
                keep_aspect_ratio=True,
            )
            x_text = self.x + w_logo + pad * 1.5
            w_text = self.w - w_logo - pad * 2.5
        else:
            x_text = self.x + pad
            w_text = self.w - pad * 2

        linhas_nome = _quebrar_razao_social(self.pdf, self.emit, w_text, max_linhas=2)
        y_nome = y_top
        self.pdf.set_font(self.pdf.default_font, 'B', 7.5)
        for ln in linhas_nome:
            self.pdf.set_xy(x_text, y_nome)
            self.pdf.cell(w=w_text, h=3.6, text=ln, border=0, align='L')
            y_nome += 3.6

        y_addr = max(y_nome + 0.3, y_top + 1)
        self.pdf.set_font(self.pdf.default_font, '', 6.5)
        self.pdf.set_xy(x_text, y_addr)
        self.pdf.text_box(
            text=self.address,
            text_align='L',
            h_line=2.8,
            x=x_text,
            y=y_addr,
            w=w_text,
            h=max(self.h - (y_addr - self.y) - 0.5, 10.0),
            border=False,
        )


def draw_header_emit_nexus(danfe) -> None:
    w_ident_box = 33
    w_code_box = 88
    w_emit_box = danfe.edw - w_ident_box - w_code_box
    h_emit_box = 31
    old_y = danfe.get_y()
    emit_name = extract_text(danfe.emit, 'xNome')
    extras = getattr(danfe, '_nexus_emit_extras', None) or {}
    address = montar_endereco_emitente_bfr(danfe.emit, extras)

    b_emit = DanfeBlock(pdf=danfe)
    e_emit_info = DanfeEmitInfoNexus(
        h=h_emit_box,
        w=w_emit_box,
        new_x='RIGHT',
        new_y='TOP',
        emit=emit_name,
        logo_image=danfe.logo_image,
        address=address,
        pdf=danfe,
    )
    b_emit.add_field(e_emit_info)
    e_ident_info = DanfeIdentInfo(
        h=h_emit_box,
        w=w_ident_box,
        new_x='RIGHT',
        new_y='TOP',
        serie_nf=danfe.serie_nf,
        nr_nota=danfe.nr_nota,
        tp_nf=danfe.tp_nf,
        pdf=danfe,
    )
    b_emit.add_field(e_ident_info)
    e_danfe_code = DanfeCode(
        h=10,
        w=w_code_box,
        new_x='LEFT',
        new_y='BOTTOM',
        key_nfe=danfe.key_nfe,
        pdf=danfe,
    )
    b_emit.add_field(e_danfe_code)
    f_chave_acesso = DanfeBasicField(
        w=w_code_box,
        description='CHAVE DE ACESSO',
        content=' '.join(chunks(danfe.key_nfe, 4)),
        type='chave_acesso',
        new_x='LEFT',
        new_y='BOTTOM',
        pdf=danfe,
    )
    b_emit.add_field(f_chave_acesso)
    f_autenticidade_msg = DanfeVerificationMsg(
        w=f_chave_acesso.w,
        h=15,
        new_x='L_BLOCK',
        new_y='BOTTOM',
        pdf=danfe,
    )
    b_emit.add_field(f_autenticidade_msg)

    danfe.y = old_y + h_emit_box
    text_nat_op = extract_text(danfe.ide, 'natOp')
    f_nat_op = DanfeBasicField(
        w=w_emit_box + w_ident_box,
        description='NATUREZA DA OPERAÇÃO',
        content=text_nat_op,
        pdf=danfe,
    )
    b_emit.add_field(f_nat_op)
    f_prot = DanfeBasicField(
        w=w_code_box,
        description='PROTOCOLO DE AUTORIZAÇÃO DE USO',
        content=danfe.prot_uso,
        type='protocolo',
        new_x='L_BLOCK',
        new_y='BOTTOM',
        pdf=danfe,
    )
    b_emit.add_field(f_prot)
    f_emit_ie = DanfeBasicField(
        w=b_emit.w / 3,
        description='INSCRIÇÃO ESTADUAL',
        content=extract_text(danfe.emit, 'IE'),
        pdf=danfe,
    )
    b_emit.add_field(f_emit_ie)
    f_emit_ie_st = DanfeBasicField(
        w=b_emit.w / 3,
        description='INSCRIÇÃO ESTADUAL DO SUBST. TRIB',
        content=extract_text(danfe.emit, 'IEST'),
        pdf=danfe,
    )
    b_emit.add_field(f_emit_ie_st)
    f_emit_cnpj = DanfeBasicField(
        w=b_emit.w - f_emit_ie.w - f_emit_ie_st.w,
        description='CNPJ / CPF',
        content=danfe.emit_cnpj_cpf,
        pdf=danfe,
    )
    b_emit.add_field(f_emit_cnpj)
    b_emit.render()
