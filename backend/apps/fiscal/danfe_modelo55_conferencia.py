"""
NF-e Saída 3.5.4.3 — DANFE Conferência modelo 55 por matriz oficial MOC 7.0 Anexo II §3.8.1.

Layout A4 retrato (21,0 x 29,7 cm), coordenadas declarativas em danfe_moc_matriz_a4_retrato.py.
Sem chave/protocolo/código de barras falsos; sem valor fiscal; sem SEFAZ.
"""

from __future__ import annotations

from decimal import Decimal
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from apps.core.pdf.formatters import dec, fmt_cnpj, format_currency_br
from apps.fiscal.danfe_conferencia import montar_dados_danfe_conferencia
from apps.fiscal.danfe_moc_matriz_a4_retrato import (
    DANFE_A4_RETRATO_CAMPOS,
    DANFE_DESTINATARIO_CAMPOS,
    DANFE_IMPOSTO_CAMPOS,
    DANFE_PRODUTO_COLUNAS,
    DANFE_PRODUTO_HEADER_LABELS,
    DANFE_TRANSPORTE_CAMPOS,
    MOC_MARGEM_LATERAL_CM,
    MOC_MARGEM_SUPERIOR_CM,
    MOC_PAGINA_ALTURA_CM,
    MOC_PAGINA_LARGURA_CM,
    BoxCm,
    campo_absoluto,
    cm_to_pt,
)
from apps.fiscal.models import NFeSaida
from apps.fiscal.snapshot_fiscal_helpers import get_icms_snapshot, get_ipi_snapshot

MSG_CHAVE_CONFERENCIA = 'CHAVE DE ACESSO NÃO GERADA — NF-e ainda não autorizada'
MSG_PROTOCOLO_CONFERENCIA = 'SEM PROTOCOLO DE AUTORIZAÇÃO — DANFE DE CONFERÊNCIA'
MSG_BARCODE_CONFERENCIA = 'Código de barras será gerado na emissão SEFAZ'
MSG_CONSULTA_CONFERENCIA = (
    'Consulta de autenticidade na página da SEFAZ será habilitada após autorização da NF-e.'
)
MSG_FATURA_VAZIA = 'Sem duplicatas geradas'

WATERMARK_LINES = (
    'NF-e CONFERÊNCIA',
    'SEM VALOR FISCAL',
    'FALTA PROTOCOLO DE APROVAÇÃO DA SEFAZ',
)


def safe_text(val: Any, default: str = '—') -> str:
    s = (str(val) if val is not None else '').strip()
    return s if s else default


def format_money(v) -> str:
    return format_currency_br(v)


def format_cnpj_cpf(raw: str | None) -> str:
    return fmt_cnpj(raw)


def format_ie(raw: str | None) -> str:
    return safe_text(raw)


def format_cep(raw: str | None) -> str:
    digits = ''.join(c for c in str(raw or '') if c.isdigit())
    if len(digits) == 8:
        return f'{digits[:5]}-{digits[5:]}'
    return safe_text(raw)


def format_chave_acesso(chave: str | None) -> str:
    digits = ''.join(c for c in str(chave or '') if c.isdigit())
    if len(digits) != 44:
        return ''
    return ' '.join(digits[i : i + 4] for i in range(0, 44, 4))


class DanfeMocA4RetratoRenderer:
    """Renderizador DANFE A4 retrato — matriz MOC 3.8.1."""

    def __init__(self, dados: dict[str, Any]):
        self.d = dados
        self.buf = BytesIO()
        self.page_w = cm_to_pt(MOC_PAGINA_LARGURA_CM)
        self.page_h = cm_to_pt(MOC_PAGINA_ALTURA_CM)
        self.c = canvas.Canvas(self.buf, pagesize=A4)
        self.c.setPageSize((self.page_w, self.page_h))
        self.c.setTitle(f'DANFE Conferência NF {dados.get("numero_nf")}')
        self.page = 0
        self.total_pages = 1
        self._itens: list[dict] = list(dados.get('itens') or [])
        self._itens_idx = 0

    def _box(self, name: str) -> BoxCm:
        return campo_absoluto(DANFE_A4_RETRATO_CAMPOS[name])

    def _box_campo(self, campo: dict) -> BoxCm:
        return campo_absoluto(campo)

    def _y_pt(self, y_top_cm: float) -> float:
        return self.page_h - cm_to_pt(y_top_cm)

    def _y_bottom_pt(self, y_top_cm: float, h_cm: float) -> float:
        return self.page_h - cm_to_pt(y_top_cm + h_cm)

    def _x_pt(self, x_cm: float) -> float:
        return cm_to_pt(x_cm)

    def draw_rect(self, box: BoxCm, stroke: float = 0.5) -> None:
        self.c.setLineWidth(stroke)
        self.c.rect(
            self._x_pt(box.x),
            self._y_bottom_pt(box.y, box.h),
            cm_to_pt(box.w),
            cm_to_pt(box.h),
            stroke=1,
            fill=0,
        )

    def draw_hline(self, x_cm: float, y_cm: float, w_cm: float) -> None:
        self.c.setLineWidth(0.35)
        y_pt = self._y_pt(y_cm)
        self.c.line(self._x_pt(x_cm), y_pt, self._x_pt(x_cm + w_cm), y_pt)

    def draw_vline(self, x_cm: float, y_cm: float, h_cm: float) -> None:
        self.c.setLineWidth(0.35)
        x_pt = self._x_pt(x_cm)
        self.c.line(x_pt, self._y_pt(y_cm), x_pt, self._y_bottom_pt(y_cm, h_cm))

    def draw_label(self, x_cm: float, y_cm: float, text: str, *, size: float = 5.5, bold: bool = True) -> None:
        self.c.setFont('Times-Bold' if bold else 'Times-Roman', size)
        self.c.drawString(self._x_pt(x_cm), self._y_pt(y_cm), text.upper()[:200])

    def draw_value(self, x_cm: float, y_cm: float, text: str, *, size: float = 6.5, max_chars: int = 120) -> None:
        self.c.setFont('Times-Roman', size)
        self.c.drawString(self._x_pt(x_cm), self._y_pt(y_cm), safe_text(text)[:max_chars])

    def draw_multiline_clipped(
        self,
        text: str,
        box: BoxCm,
        *,
        font_size: float = 6,
        line_h: float = 0.30,
        pad_x: float = 0.08,
        pad_y: float = 0.28,
    ) -> None:
        max_lines = max(1, int((box.h - pad_y) / line_h))
        y = box.y + pad_y
        for ln in self._wrap(text, int(box.w / 0.16))[:max_lines]:
            self.draw_value(box.x + pad_x, y, ln, size=font_size)
            y += line_h

    def draw_campo_rotulo_valor(
        self,
        box: BoxCm,
        rotulo: str,
        valor: str,
        *,
        rotulo_size: float = 4.8,
        valor_size: float = 6,
    ) -> None:
        self.draw_rect(box, stroke=0.35)
        self.draw_label(box.x + 0.06, box.y + 0.06, rotulo, size=rotulo_size)
        self.draw_value(
            box.x + 0.06,
            box.y + max(0.28, box.h - 0.34),
            valor,
            size=valor_size,
            max_chars=int(box.w / 0.14),
        )

    def draw_danfe_watermark(self) -> None:
        """Marca d'água centralizada na folha A4 (atrás do conteúdo)."""
        cx = self.page_w / 2
        cy = self.page_h * 0.48
        self.c.saveState()
        try:
            self.c.setFillAlpha(0.19)
        except Exception:
            pass
        self.c.setFillColor(colors.HexColor('#5a6472'))
        self.c.translate(cx, cy)
        self.c.rotate(-12)
        self.c.setFont('Times-Bold', 17)
        yy = 28
        for line in WATERMARK_LINES:
            self.c.drawCentredString(0, yy, line)
            yy -= 24
        self.c.restoreState()
        self.c.setFillColor(colors.black)

    @staticmethod
    def _wrap(text: str, max_chars: int) -> list[str]:
        text = safe_text(text, '')
        if not text:
            return ['—']
        if len(text) <= max_chars:
            return [text]
        words = text.split()
        lines: list[str] = []
        cur = ''
        for w in words:
            trial = f'{cur} {w}'.strip()
            if len(trial) <= max_chars:
                cur = trial
            else:
                if cur:
                    lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        return lines or ['—']

    @staticmethod
    def _fmt_qty(v) -> str:
        d = dec(v)
        if d == d.to_integral_value():
            return str(int(d))
        return f'{d:.3f}'.replace('.', ',')

    def _draw_outlines_pagina1(self) -> None:
        for key in (
            'canhoto_recebemos',
            'canhoto_nfe',
            'canhoto_data_recebimento',
            'canhoto_ident_assinatura',
            'emitente',
            'quadro_danfe',
            'codigo_barras',
            'chave_acesso',
            'natureza_operacao',
            'protocolo_autorizacao',
            'ie_emitente',
            'ie_st_emitente',
            'cnpj_emitente',
            'destinatario_bloco',
            'fatura_duplicatas',
            'calculo_imposto',
            'transportador',
            'produtos_bloco',
            'informacoes_complementares',
            'reservado_fisco',
            'rodape_impressao',
        ):
            self.draw_rect(self._box(key))
        dest = self._box('destinatario_bloco')
        self.draw_label(dest.x + 0.08, dest.y + 0.10, 'DESTINATÁRIO / REMETENTE', size=5.5)
        for campo in DANFE_DESTINATARIO_CAMPOS.values():
            self.draw_rect(self._box_campo(campo), stroke=0.3)
        fat = self._box('fatura_duplicatas')
        self.draw_label(fat.x + 0.08, fat.y + 0.10, 'FATURA / DUPLICATA', size=5.5)
        imp = self._box('calculo_imposto')
        self.draw_label(imp.x + 0.08, imp.y + 0.10, 'CÁLCULO DO IMPOSTO', size=5.5)
        for campo in DANFE_IMPOSTO_CAMPOS.values():
            self.draw_rect(self._box_campo(campo), stroke=0.3)
        tr = self._box('transportador')
        self.draw_label(tr.x + 0.08, tr.y + 0.10, 'TRANSPORTADOR / VOLUMES TRANSPORTADOS', size=5.5)
        for campo in DANFE_TRANSPORTE_CAMPOS.values():
            self.draw_rect(self._box_campo(campo), stroke=0.3)
        pr = self._box('produtos_bloco')
        self.draw_label(pr.x + 0.08, pr.y + 0.12, 'DADOS DOS PRODUTOS / SERVIÇOS', size=5.5)
        self.draw_hline(pr.x, pr.y + 0.55, pr.w)
        inf = self._box('informacoes_complementares')
        self.draw_label(inf.x + 0.08, inf.y + 0.10, 'DADOS ADICIONAIS', size=5.5)
        self.draw_label(inf.x + 0.08, inf.y + 0.28, 'INFORMAÇÕES COMPLEMENTARES', size=5)
        fis = self._box('reservado_fisco')
        self.draw_label(fis.x + 0.08, fis.y + 0.28, 'RESERVADO AO FISCO', size=5)

    def _fill_canhoto(self) -> None:
        emit = self.d['emitente_detalhe']
        dest = self.d['destinatario_detalhe']
        b_rec = self._box('canhoto_recebemos')
        texto = (
            f'RECEBEMOS DE {safe_text(emit.get("x_nome"))} OS PRODUTOS E/OU SERVIÇOS '
            f'CONSTANTES DA NOTA FISCAL ELETRÔNICA INDICADA ABAIXO.'
        )
        self.draw_multiline_clipped(texto, b_rec, font_size=6, line_h=0.28)
        b_nfe = self._box('canhoto_nfe')
        num = self.d.get('numero_canhoto') or self.d.get('numero_exibicao', self.d['numero_nf'])
        serie = self.d.get('serie_exibicao', self.d['serie'])
        self.draw_label(b_nfe.x + 0.08, b_nfe.y + 0.12, 'NF-e', size=5)
        self.draw_value(b_nfe.x + 0.08, b_nfe.y + 0.45, num, size=6.5)
        self.draw_value(b_nfe.x + 0.08, b_nfe.y + 0.85, f'Série {serie}', size=6.5)
        b_data = self._box('canhoto_data_recebimento')
        self.draw_label(b_data.x + 0.06, b_data.y + 0.10, 'DATA DE RECEBIMENTO', size=4.8)
        self.draw_value(b_data.x + 0.06, b_data.y + 0.30, '___/___/______', size=6)
        b_ass = self._box('canhoto_ident_assinatura')
        self.draw_label(b_ass.x + 0.06, b_ass.y + 0.10, 'IDENTIFICAÇÃO E ASSINATURA DO RECEBEDOR', size=4.8)
        tot = self.d['totais_imposto']['valor_total_nota']
        self.draw_value(
            b_rec.x + 0.06,
            b_rec.y + b_rec.h - 0.38,
            f'VALOR TOTAL {tot}  DESTINATÁRIO: {safe_text(dest.get("x_nome"))[:40]}',
            size=5.5,
        )

    def _fill_emitente_danfe(self) -> None:
        emit = self.d['emitente_detalhe']
        be = self._box('emitente')
        self.draw_label(be.x + 0.08, be.y + 0.12, 'IDENTIFICAÇÃO DO EMITENTE', size=5)
        self.draw_value(be.x + 0.10, be.y + 0.55, safe_text(emit.get('x_nome')), size=9)
        self.draw_multiline_clipped(safe_text(emit.get('ender')), be, font_size=6.5, line_h=0.32, pad_y=1.05)
        self.draw_value(
            be.x + 0.10,
            be.y + 2.35,
            f"{safe_text(emit.get('cidade'))}/{safe_text(emit.get('uf'))}  CEP {format_cep(emit.get('cep'))}  "
            f"Fone {safe_text(emit.get('telefone'))}",
            size=6,
        )
        bd = self._box('quadro_danfe')
        cx = bd.x + bd.w / 2
        self.c.setFont('Times-Bold', 16)
        self.c.drawCentredString(self._x_pt(cx), self._y_pt(bd.y + 0.55), 'DANFE')
        self.c.setFont('Times-Roman', 6)
        self.c.drawCentredString(
            self._x_pt(cx),
            self._y_pt(bd.y + 1.05),
            'DOCUMENTO AUXILIAR DA NOTA FISCAL ELETRÔNICA',
        )
        self.c.setFont('Times-Bold', 7)
        self.c.drawString(self._x_pt(bd.x + 0.15), self._y_pt(bd.y + 1.55), '0 - ENTRADA')
        mark = 'X' if self.d.get('tipo_operacao_saida') else ' '
        self.c.drawString(self._x_pt(bd.x + 0.15), self._y_pt(bd.y + 1.90), f'{mark} 1 - SAÍDA')
        num = self.d.get('numero_exibicao', self.d['numero_nf'])
        serie = self.d.get('serie_exibicao', self.d['serie'])
        self.c.drawString(self._x_pt(bd.x + 3.2), self._y_pt(bd.y + 1.55), f'Nº {num}')
        self.c.drawString(self._x_pt(bd.x + 3.2), self._y_pt(bd.y + 1.90), f'Série {serie}')
        self.c.drawString(self._x_pt(bd.x + 3.2), self._y_pt(bd.y + 2.25), f'Folha {self.page}/{self.total_pages}')

    def _fill_chave_barcode(self) -> None:
        chave_digits = ''.join(c for c in str(self.d.get('chave_acesso') or '') if c.isdigit())
        b_ch = self._box('chave_acesso')
        b_bc = self._box('codigo_barras')
        self.draw_label(b_ch.x + 0.06, b_ch.y + 0.06, 'CHAVE DE ACESSO', size=4.8)
        if self.d.get('chave_placeholder_barcode', True) or len(chave_digits) != 44:
            self.draw_value(b_ch.x + 0.06, b_ch.y + 0.14, MSG_CHAVE_CONFERENCIA, size=6, max_chars=90)
            self.draw_multiline_clipped(MSG_CONSULTA_CONFERENCIA, b_bc, font_size=5.5, pad_y=0.35)
            self.draw_value(b_bc.x + 0.06, b_bc.y + 0.55, MSG_BARCODE_CONFERENCIA, size=5.5, max_chars=55)
        else:
            self.draw_value(b_ch.x + 0.06, b_ch.y + 0.14, format_chave_acesso(chave_digits), size=6.5)
            self._draw_code128(b_bc, chave_digits)
        b_nat = self._box('natureza_operacao')
        self.draw_label(b_nat.x + 0.06, b_nat.y + 0.06, 'NATUREZA DA OPERAÇÃO', size=4.8)
        self.draw_value(b_nat.x + 0.06, b_nat.y + 0.14, self.d.get('natureza_operacao', '—'), size=6.5)
        b_pr = self._box('protocolo_autorizacao')
        proto = self.d.get('protocolo') or self.d.get('protocolo_display', MSG_PROTOCOLO_CONFERENCIA)
        self.draw_label(b_pr.x + 0.06, b_pr.y + 0.06, 'PROTOCOLO DE AUTORIZAÇÃO DE USO', size=4.8)
        self.draw_value(b_pr.x + 0.06, b_pr.y + 0.14, proto, size=6, max_chars=85)
        emit = self.d['emitente_detalhe']
        self.draw_campo_rotulo_valor(
            self._box('ie_emitente'),
            'INSCRIÇÃO ESTADUAL',
            format_ie(emit.get('ie')),
        )
        self.draw_campo_rotulo_valor(
            self._box('ie_st_emitente'),
            'INSC. ESTADUAL SUBST. TRIB.',
            safe_text(emit.get('ie_st'), '—'),
        )
        self.draw_campo_rotulo_valor(
            self._box('cnpj_emitente'),
            'CNPJ',
            format_cnpj_cpf(emit.get('cnpj')),
        )

    def _draw_code128(self, box: BoxCm, chave_digits: str) -> None:
        try:
            from reportlab.graphics import renderPDF
            from reportlab.graphics.barcode import code128
            from reportlab.graphics.shapes import Drawing

            x_pt = self._x_pt(box.x)
            y_pt = self._y_bottom_pt(box.y, box.h)
            w_pt = cm_to_pt(box.w)
            h_pt = cm_to_pt(box.h)
            bc = code128.Code128(chave_digits, barHeight=cm_to_pt(1.0), barWidth=0.28)
            d = Drawing(w_pt, h_pt * 0.55)
            d.add(bc)
            renderPDF.draw(d, self.c, x_pt + 1, y_pt + h_pt * 0.35)
        except Exception:
            self.draw_value(box.x + 0.08, box.y + 0.4, format_chave_acesso(chave_digits), size=6)

    def _fill_destinatario(self) -> None:
        dest = self.d['destinatario_detalhe']
        mapping = {
            'dest_nome': ('NOME / RAZÃO SOCIAL', safe_text(dest.get('x_nome'))),
            'dest_cnpj': ('CNPJ / CPF', format_cnpj_cpf(dest.get('cnpj'))),
            'dest_data_emissao': ('DATA DA EMISSÃO', dest.get('data_emissao', '—')),
            'dest_endereco': ('ENDEREÇO', safe_text(dest.get('ender'))),
            'dest_bairro': ('BAIRRO / DISTRITO', safe_text(dest.get('bairro'))),
            'dest_cep': ('CEP', format_cep(dest.get('cep'))),
            'dest_data_saida': ('DATA ENTRADA/SAÍDA', dest.get('data_saida', '—')),
            'dest_municipio': ('MUNICÍPIO', safe_text(dest.get('cidade'))),
            'dest_fone': ('FONE / FAX', safe_text(dest.get('fone'), '—')),
            'dest_uf': ('UF', safe_text(dest.get('uf'))),
            'dest_ie': ('INSCRIÇÃO ESTADUAL', format_ie(dest.get('ie'))),
            'dest_hora_saida': ('HORA ENTRADA/SAÍDA', dest.get('hora_saida', '—')),
        }
        for key, (rot, val) in mapping.items():
            self.draw_campo_rotulo_valor(self._box_campo(DANFE_DESTINATARIO_CAMPOS[key]), rot, val)

    def _fill_fatura(self) -> None:
        dups = self.d.get('duplicatas') or []
        bf = self._box('fatura_duplicatas')
        if not dups:
            self.draw_value(bf.x + 0.10, bf.y + 0.38, MSG_FATURA_VAZIA, size=6)
            return
        y = bf.y + 0.42
        for dup in dups[:7]:
            self.draw_value(
                bf.x + 0.10,
                y,
                f"Nº {dup['numero']}   Venc: {dup['vencimento']}   Valor: {dup['valor']}",
                size=5.5,
            )
            y += 0.30

    def _fill_imposto(self) -> None:
        t = self.d['totais_imposto']
        mapping = {
            'imp_base_icms': ('BASE DE CÁLC. DO ICMS', t['base_icms']),
            'imp_valor_icms': ('VALOR DO ICMS', t['valor_icms']),
            'imp_base_icms_st': ('BASE DE CÁLC. ICMS ST', t['base_icms_st']),
            'imp_valor_icms_st': ('VALOR DO ICMS ST', t['valor_icms_st']),
            'imp_valor_produtos': ('VALOR TOTAL DOS PRODUTOS', t['valor_produtos']),
            'imp_valor_frete': ('VALOR DO FRETE', t['valor_frete']),
            'imp_valor_seguro': ('VALOR DO SEGURO', t['valor_seguro']),
            'imp_desconto': ('DESCONTO', t['desconto']),
            'imp_outras_desp': ('OUTRAS DESPESAS ACESS.', t['outras_despesas']),
            'imp_valor_ipi': ('VALOR DO IPI', t['valor_ipi']),
            'imp_valor_total_nota': ('VALOR TOTAL DA NOTA', t['valor_total_nota']),
        }
        for key, (rot, val) in mapping.items():
            self.draw_campo_rotulo_valor(self._box_campo(DANFE_IMPOSTO_CAMPOS[key]), rot, val)

    def _fill_transporte(self) -> None:
        tr = self.d['transporte_detalhe']
        mapping = {
            'transp_nome': ('NOME / RAZÃO SOCIAL', tr['nome']),
            'transp_frete': ('FRETE POR CONTA', tr['frete_conta'][:42]),
            'transp_cod_antt': ('CÓDIGO ANTT', tr['codigo_antt']),
            'transp_placa': ('PLACA DO VEÍCULO', tr['placa']),
            'transp_uf_placa': ('UF', tr['uf_veiculo']),
            'transp_cnpj': ('CNPJ / CPF', tr['cnpj']),
            'transp_endereco': ('ENDEREÇO', tr['endereco'][:48]),
            'transp_municipio': ('MUNICÍPIO', tr['municipio']),
            'transp_uf': ('UF', tr['uf']),
            'transp_ie': ('INSCRIÇÃO ESTADUAL', tr['ie']),
            'transp_quantidade': ('QUANTIDADE', tr['quantidade']),
            'transp_especie': ('ESPÉCIE', tr['especie']),
            'transp_marca': ('MARCA', tr['marca']),
            'transp_numeracao': ('NUMERAÇÃO', tr['numeracao']),
            'transp_peso_bruto': ('PESO BRUTO', tr['peso_bruto']),
            'transp_peso_liquido': ('PESO LÍQUIDO', tr['peso_liquido']),
        }
        for key, (rot, val) in mapping.items():
            self.draw_campo_rotulo_valor(self._box_campo(DANFE_TRANSPORTE_CAMPOS[key]), rot, val)

    def _prod_col_x_positions(self, base_x: float) -> list[float]:
        xs = [base_x]
        for _name, col in DANFE_PRODUTO_COLUNAS:
            xs.append(xs[-1] + col['w'])
        return xs

    def _draw_produtos_header(self, y_top: float, *, continuacao: bool = False) -> float:
        if continuacao:
            pr = self._box('produtos_bloco_continuacao')
            hdr = BoxCm(pr.x, y_top, pr.w, 0.55)
        else:
            ref = self._box('produtos_cabecalho')
            hdr = BoxCm(ref.x, y_top, ref.w, ref.h)
        self.draw_rect(hdr, stroke=0.4)
        self.draw_hline(hdr.x, y_top + hdr.h, hdr.w)
        base_x = hdr.x
        xs = self._prod_col_x_positions(base_x)
        for x in xs[1:]:
            self.draw_vline(x, y_top, hdr.h)
        for (name, col), x_left in zip(DANFE_PRODUTO_COLUNAS, xs[:-1]):
            label = DANFE_PRODUTO_HEADER_LABELS.get(name, name.upper())
            fs = 4.2 if col['w'] < 1.2 else 4.8
            self.c.setFont('Times-Bold', fs)
            pad = 0.02
            if col['w'] >= 4:
                self.c.drawString(self._x_pt(x_left + pad), self._y_pt(y_top + 0.20), label[:48])
            else:
                self.c.drawString(self._x_pt(x_left + pad), self._y_pt(y_top + 0.22), label[:14])
        return y_top + hdr.h

    def _draw_produto_linha(self, y_top: float, linha: dict) -> float:
        snap = linha.get('snapshot_fiscal') or {}
        icms = get_icms_snapshot(snap)
        desc = safe_text(linha.get('x_prod'))
        inf_ad = safe_text(linha.get('inf_ad_prod'), '')
        x_ped = safe_text(linha.get('x_ped'), '')
        n_item = safe_text(linha.get('n_item_ped'), '')
        aux: list[str] = []
        if x_ped or n_item:
            aux.append(f'xPed: {x_ped or "—"}  nItemPed: {n_item or "—"}')
        if inf_ad:
            aux.append(inf_ad)
        desc_col = next(c for n, c in DANFE_PRODUTO_COLUNAS if n == 'descricao')
        max_desc_chars = max(18, int(desc_col['w'] / 0.11))
        desc_lines = self._wrap(desc, max_desc_chars)
        h = max(0.50, 0.22 + len(desc_lines) * 0.24 + len(aux) * 0.24)

        corpo = self._box('produtos_corpo')
        if self.page > 1:
            corpo = self._box('produtos_bloco_continuacao')
        row = BoxCm(corpo.x, y_top, corpo.w, h)
        self.draw_rect(row, stroke=0.35)
        xs = self._prod_col_x_positions(corpo.x)
        for x in xs[1:]:
            self.draw_vline(x, y_top, h)
        self.draw_hline(corpo.x, y_top + h, corpo.w)

        cst_val = safe_text(icms.get('cst_icms') or icms.get('csosn'))[:4]
        vals = {
            'codigo': safe_text(linha.get('c_prod'))[:14],
            'descricao': desc_lines[0],
            'ncm': safe_text(linha.get('ncm'))[:10],
            'cst': cst_val,
            'cfop': safe_text(linha.get('cfop'))[:5],
            'un': safe_text(linha.get('u_com'))[:4],
            'qtd': self._fmt_qty(linha.get('q_com')),
            'v_unit': format_money(linha.get('v_un_com')),
            'v_total': format_money(linha.get('v_prod')),
            'bc_icms': format_money(icms.get('base') or 0),
            'v_icms': format_money(icms.get('valor') or 0),
            'aliq_icms': (safe_text(icms.get('aliquota')) or '0')[:6],
        }
        ry = y_top + 0.16
        for (name, col), x_left in zip(DANFE_PRODUTO_COLUNAS, xs[:-1]):
            fs = 4.8 if name == 'descricao' else 5.2
            if name in ('qtd', 'v_unit', 'v_total', 'bc_icms', 'v_icms', 'aliq_icms'):
                fs = 5.0
            self.c.setFont('Times-Roman', fs)
            txt = vals.get(name, '—')
            if name != 'descricao':
                self.c.drawRightString(self._x_pt(x_left + col['w'] - 0.04), self._y_pt(ry), txt[:16])
            else:
                self.c.drawString(self._x_pt(x_left + 0.03), self._y_pt(ry), txt[:max_desc_chars + 5])

        dy = ry + 0.38
        desc_x = xs[1] + 0.03
        self.c.setFont('Times-Roman', 4.8)
        for extra in desc_lines[1:]:
            self.c.drawString(self._x_pt(desc_x), self._y_pt(dy), extra[:max_desc_chars + 8])
            dy += 0.22
        for line in aux:
            self.c.drawString(self._x_pt(desc_x), self._y_pt(dy), line[:90])
            dy += 0.22
        return y_top + h

    def _preencher_grade_produtos_vazia(self, y_from: float, y_to: float) -> None:
        """Linhas horizontais na área de produtos não usada (aspecto tabela fiscal)."""
        if y_to - y_from < 0.35:
            return
        corpo = self._box('produtos_corpo')
        if self.page > 1:
            corpo = self._box('produtos_bloco_continuacao')
        y = y_from
        step = 0.55
        while y < y_to - 0.05:
            self.draw_hline(corpo.x, y, corpo.w)
            y += step

    def _fill_dados_adicionais(self) -> None:
        bi = self._box('informacoes_complementares')
        bf = self._box('reservado_fisco')
        self.draw_multiline_clipped(
            safe_text(self.d.get('informacoes_complementares'), ''),
            bi,
            font_size=5.5,
            line_h=0.28,
            pad_y=0.45,
        )
        inf_fisco = safe_text(self.d.get('informacoes_fisco'), '')
        if inf_fisco and inf_fisco != '—':
            self.draw_multiline_clipped(inf_fisco, bf, font_size=5.5, line_h=0.28, pad_y=0.45)

    def _draw_outlines_continuacao(self) -> None:
        cab = self._box('cabecalho_continuacao')
        self.draw_rect(cab)
        for key in ('emitente', 'quadro_danfe', 'codigo_barras', 'chave_acesso', 'natureza_operacao'):
            c = DANFE_A4_RETRATO_CAMPOS[key]
            rel = BoxCm(cab.x + c['x'], cab.y + c['y'] - 0.42 + 0.42, c['w'], c['h'])
            self.draw_rect(rel, stroke=0.35)
        pr = self._box('produtos_bloco_continuacao')
        self.draw_rect(pr)
        self.draw_label(pr.x + 0.08, pr.y + 0.10, 'DADOS DOS PRODUTOS / SERVIÇOS (continuação)', size=5.5)

    def _fill_cabecalho_continuacao(self) -> None:
        emit = self.d['emitente_detalhe']
        cab = self._box('cabecalho_continuacao')
        self.draw_value(
            cab.x + 0.10,
            cab.y + 0.15,
            f"DANFE CONFERÊNCIA — {safe_text(emit.get('x_nome'))[:65]}",
            size=7,
        )
        num = self.d.get('numero_exibicao', self.d['numero_nf'])
        serie = self.d.get('serie_exibicao', self.d['serie'])
        self.draw_value(
            cab.x + 0.10,
            cab.y + 0.50,
            f'NF {num}  Série {serie}  Folha {self.page}/{self.total_pages}',
            size=6.5,
        )
        self.draw_value(cab.x + 0.10, cab.y + 0.85, self.d.get('chave_display', MSG_CHAVE_CONFERENCIA)[:95], size=5.5)
        self.draw_value(cab.x + 0.10, cab.y + 1.20, self.d.get('natureza_operacao', '—')[:95], size=5.5)
        off = cab.y + 5.72 - 0.42
        self.draw_value(
            cab.x + 0.10,
            off,
            f"CNPJ {format_cnpj_cpf(emit.get('cnpj'))}  IE {format_ie(emit.get('ie'))}",
            size=5.5,
        )

    def _produtos_area(self, continuacao: bool) -> tuple[float, float]:
        if continuacao:
            b = self._box('produtos_bloco_continuacao')
            y_start = b.y + 0.58
            y_end = b.y + b.h - 0.08
        else:
            b = self._box('produtos_corpo')
            y_start = b.y
            y_end = b.y + b.h
        return y_start, y_end

    def _estimate_pages(self) -> int:
        y0, y1 = self._produtos_area(False)
        area = max(y1 - y0, 5.0)
        n = len(self._itens)
        per_first = max(1, int(area / 0.52))
        per_next = max(1, int((self._box('produtos_bloco_continuacao').h - 0.7) / 0.52))
        if n <= per_first:
            return 1
        rest = n - per_first
        return 1 + (rest + per_next - 1) // per_next

    def _new_page(self, *, continuacao: bool = False) -> None:
        if self.page:
            self.c.showPage()
        self.page += 1
        self.c.setPageSize((self.page_w, self.page_h))
        self.draw_danfe_watermark()
        self.c.setStrokeColor(colors.black)
        self.c.setFillColor(colors.black)
        if continuacao:
            self._draw_outlines_continuacao()
            self._fill_cabecalho_continuacao()

    def build(self) -> bytes:
        self.page = 0
        self._itens_idx = 0
        self.total_pages = self._estimate_pages()

        self._new_page(continuacao=False)
        self.page = 1
        self._draw_outlines_pagina1()
        self._fill_canhoto()
        self._fill_emitente_danfe()
        self._fill_chave_barcode()
        self._fill_destinatario()
        self._fill_fatura()
        self._fill_imposto()
        self._fill_transporte()

        y, y_end = self._produtos_area(False)
        y = self._draw_produtos_header(y)

        while self._itens_idx < len(self._itens):
            if y + 0.54 > y_end:
                self._preencher_grade_produtos_vazia(y, y_end)
                self.total_pages = max(self.total_pages, self.page + 1)
                self._new_page(continuacao=True)
                y, y_end = self._produtos_area(True)
                y = self._draw_produtos_header(y, continuacao=True)
                continue
            y = self._draw_produto_linha(y, self._itens[self._itens_idx]) + 0.01
            self._itens_idx += 1

        self._preencher_grade_produtos_vazia(y, y_end)

        if self.page == self.total_pages:
            for key in ('informacoes_complementares', 'reservado_fisco'):
                self.draw_rect(self._box(key), stroke=0.35)
            self._fill_dados_adicionais()
        rod = self._box('rodape_impressao')
        self.c.setFont('Times-Roman', 4.5)
        self.c.drawRightString(
            self._x_pt(rod.x + rod.w),
            self._y_pt(rod.y + 0.12),
            f'Folha {self.page}/{self.total_pages} — DANFE de conferência (sem valor fiscal)',
        )
        self.c.setFont('Times-Roman', 5)
        self.c.drawRightString(
            self.page_w - cm_to_pt(MOC_MARGEM_LATERAL_CM),
            self._y_pt(MOC_PAGINA_ALTURA_CM - MOC_MARGEM_SUPERIOR_CM - 0.12),
            f'Folha {self.page}/{self.total_pages}',
        )
        self.c.save()
        return self.buf.getvalue()


# Compatibilidade com testes/importacoes anteriores
DanfeTopDownCanvas = DanfeMocA4RetratoRenderer


def gerar_danfe_modelo55_conferencia_pdf(nfe_saida: NFeSaida) -> tuple[bytes, dict[str, Any]]:
    """Gera PDF DANFE modelo 55 de conferência (delega para danfe_render 3.5.4.4)."""
    from apps.fiscal.danfe_render import gerar_danfe_modelo55_conferencia_pdf as _render

    return _render(nfe_saida)
