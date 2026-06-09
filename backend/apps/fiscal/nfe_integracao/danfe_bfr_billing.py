"""
DANFE BFR — bloco FATURA / DUPLICATAS (grade 5 colunas, até 2 linhas / 10 parcelas).

Substitui o desenho padrão da biblioteca, que comprime muitas parcelas em células estreitas
e baixas (altura 3 mm).
"""

from __future__ import annotations

from brazilfiscalreport.danfe.danfe import URL, extract_text, format_number, get_date_utc
from brazilfiscalreport.danfe.danfe_basic_field import DanfeBasicField
from brazilfiscalreport.danfe.danfe_block import DanfeBlock
from brazilfiscalreport.danfe.config import InvoiceDisplay

MAX_DUPLICATAS_BFR = 10
COLUNAS_DUP = 5
ALTURA_CELULA_DUP_MM = 5.2


def draw_billing_nexus(self) -> None:
    """Método para monkey-patch em DanfeNexus._draw_billing."""
    if not self.cobr:
        return

    block_fatura = DanfeBlock(description='FATURA / DUPLICATAS', pdf=self)
    fat = self.cobr.find(f'{URL}fat')
    dup_nodes = self.cobr.findall(f'{URL}dup')[:MAX_DUPLICATAS_BFR]

    numero = extract_text(fat, 'nFat')
    valor_original = format_number(extract_text(fat, 'vOrig'), 2)
    valor_desconto = format_number(extract_text(fat, 'vDesc'), 2)
    valor_liquido = format_number(extract_text(fat, 'vLiq'), 2)

    w_numero = w_original = w_desconto = block_fatura.w / 4
    w_liquido = block_fatura.w - w_numero - w_original - w_desconto

    if self.invoice_display == InvoiceDisplay.FULL_DETAILS:
        block_fatura.add_field(
            DanfeBasicField(w=w_numero, description='NÚMERO', content=numero, pdf=self),
        )
        block_fatura.add_field(
            DanfeBasicField(
                w=w_original,
                type='number',
                description='VALOR ORIGINAL',
                content=valor_original,
                pdf=self,
            ),
        )
        block_fatura.add_field(
            DanfeBasicField(
                w=w_desconto,
                type='number',
                description='VALOR DO DESCONTO',
                content=valor_desconto,
                pdf=self,
            ),
        )
        block_fatura.add_field(
            DanfeBasicField(
                w=w_liquido,
                type='number',
                description='VALOR LÍQUIDO',
                content=valor_liquido,
                pdf=self,
            ),
        )
    block_fatura.render()

    if not dup_nodes:
        return

    self.set_font(self.default_font, '', self.get_font_size('FONT_DUPLICATES', True))
    dups_text: list[str] = []
    for item_dup in dup_nodes:
        num = extract_text(item_dup, 'nDup')
        venc = extract_text(item_dup, 'dVenc')
        venc, _hr = get_date_utc(venc)
        valor = format_number(extract_text(item_dup, 'vDup'), 2)
        dups_text.append(f'{num}  {venc}  {valor}')

    w_cel = block_fatura.w / COLUNAS_DUP
    old_x = self.x
    for i in range(0, len(dups_text), COLUNAS_DUP):
        linha = dups_text[i : i + COLUNAS_DUP]
        linha += [''] * (COLUNAS_DUP - len(linha))
        for dup_text in linha:
            self.cell(w_cel, ALTURA_CELULA_DUP_MM, dup_text, border=1, align='L')
        self.ln()
        self.x = old_x
