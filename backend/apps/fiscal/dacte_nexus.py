"""DACTE Nexus — geração própria (ReportLab) a partir do XML de CT-e."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from decimal import Decimal
from io import BytesIO
from typing import Any

from reportlab.graphics.barcode import code128, qr
from reportlab.graphics.shapes import Drawing
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from apps.core.pdf.formatters import format_cnpj, format_currency_br
from apps.fiscal.cte_import.parser import parse_cte_xml

PAGE_W, PAGE_H = A4
MARGIN = 8 * mm
INNER_PAD = 1.6 * mm
LINE = 0.45

TP_CTE = {'0': 'NORMAL', '1': 'COMPLEMENTO', '2': 'ANULAÇÃO', '3': 'SUBSTITUTO'}
TP_SERV = {
    '0': 'NORMAL',
    '1': 'SUBCONTRATAÇÃO',
    '2': 'REDESPACHO',
    '3': 'REDESPACHO INTERMEDIÁRIO',
}
TP_TOMA = {
    '0': 'REMETENTE',
    '1': 'EXPEDIDOR',
    '2': 'RECEBEDOR',
    '3': 'DESTINATÁRIO',
    '4': 'OUTROS',
}
TP_MODAL = {
    '01': 'RODOVIÁRIO',
    '02': 'AÉREO',
    '03': 'AQUAVIÁRIO',
    '04': 'FERROVIÁRIO',
    '05': 'DUTOVIÁRIO',
    '06': 'MULTIMODAL',
}


def _digits(val: Any) -> str:
    return ''.join(c for c in str(val or '') if c.isdigit())


def _text(val: Any) -> str:
    return str(val or '').strip()


def _money(val: Any) -> str:
    try:
        return format_currency_br(val).replace('R$ ', '')
    except Exception:
        return '0,00'


def _cep(val: Any) -> str:
    d = _digits(val)
    if len(d) == 8:
        return f'{d[:5]}-{d[5:]}'
    return _text(val) or '—'


def _fone(val: Any) -> str:
    d = _digits(val)
    if len(d) == 10:
        return f'({d[:2]}) {d[2:6]}-{d[6:]}'
    if len(d) == 11:
        return f'({d[:2]}) {d[2:7]}-{d[7:]}'
    return _text(val) or '—'


def _local_tag(tag: str) -> str:
    return tag.split('}')[-1] if '}' in tag else tag


def _party_ender(party: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(party, dict):
        return {}
    for key in ('enderEmit', 'enderReme', 'enderDest', 'enderExped', 'enderReceb', 'enderToma'):
        node = party.get(key)
        if isinstance(node, dict) and node:
            return node
    return {}


def _party_lines(party: dict[str, Any]) -> list[str]:
    party = party if isinstance(party, dict) else {}
    ender = _party_ender(party)
    nome = _text(party.get('xNome') or party.get('xFant')) or '—'
    doc = format_cnpj(party.get('CNPJ') or party.get('CPF') or '')
    ie = _text(party.get('IE')) or '—'
    end = ', '.join(
        p
        for p in [
            ' '.join(filter(None, [_text(ender.get('xLgr')), _text(ender.get('nro'))])).strip(),
            _text(ender.get('xCpl')),
            _text(ender.get('xBairro')),
        ]
        if p
    ) or '—'
    mun = ' - '.join(filter(None, [_text(ender.get('xMun')), _text(ender.get('UF'))])) or '—'
    cep = _cep(ender.get('CEP'))
    fone = _fone(ender.get('fone') or party.get('fone'))
    return [
        nome,
        f'CNPJ/CPF: {doc}    IE: {ie}',
        end,
        f'{mun}    CEP: {cep}    Fone: {fone}',
    ]


def _serie_nro_de_chave_nfe(chave: str) -> str:
    d = _digits(chave)
    if len(d) != 44:
        return '—'
    return f'{d[22:25]}/{d[25:34]}'


def _normalize_comps(raw: Any) -> list[tuple[str, str]]:
    items: list[Any]
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict):
        if 'xNome' in raw or 'vComp' in raw:
            items = [raw]
        elif isinstance(raw.get('Comp'), list):
            items = raw['Comp']
        elif isinstance(raw.get('Comp'), dict):
            items = [raw['Comp']]
        else:
            items = []
    else:
        items = []
    out: list[tuple[str, str]] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        nome = _text(it.get('xNome')) or '—'
        out.append((nome, _money(it.get('vComp'))))
    return out


def _icms_from_imposto(imposto: dict[str, Any]) -> tuple[str, str, str, str]:
    """Retorna CST, vBC, pICMS, vICMS."""
    if not isinstance(imposto, dict):
        return '—', '0,00', '0,00', '0,00'
    icms = imposto.get('ICMS')
    if not isinstance(icms, dict):
        return '—', '0,00', '0,00', '0,00'
    bloco = next((v for v in icms.values() if isinstance(v, dict)), {})
    return (
        _text(bloco.get('CST') or bloco.get('CST') or '—') or '—',
        _money(bloco.get('vBC')),
        _money(bloco.get('pICMS')),
        _money(bloco.get('vICMS')),
    )


def _extract_qr_and_obs(xml: str) -> tuple[str, str, str, str]:
    """qrCodCTe, xObs, prodPred, RNTRC."""
    qr_url = ''
    x_obs = ''
    prod_pred = ''
    rntrc = ''
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return qr_url, x_obs, prod_pred, rntrc
    for el in root.iter():
        tag = _local_tag(el.tag)
        if tag == 'qrCodCTe' and el.text:
            qr_url = el.text.strip()
        elif tag == 'xObs' and el.text and not x_obs:
            x_obs = el.text.strip()
        elif tag == 'prodPred':
            # pode ser grupo; xProd dentro
            for ch in el:
                if _local_tag(ch.tag) == 'xProd' and ch.text:
                    prod_pred = ch.text.strip()
            if el.text and not prod_pred:
                prod_pred = el.text.strip()
        elif tag == 'xProd' and not prod_pred and el.text:
            # evita pegar de outros grupos; só se ainda vazio e pai prodPred já tratado
            pass
        elif tag == 'RNTRC' and el.text and not rntrc:
            rntrc = el.text.strip()
    if not prod_pred:
        for el in root.iter():
            if _local_tag(el.tag) == 'infCarga':
                for ch in el:
                    if _local_tag(ch.tag) == 'proPred' and ch.text:
                        prod_pred = ch.text.strip()
                        break
    return qr_url, x_obs, prod_pred, rntrc


def _tp_cte_serv_toma(xml: str) -> tuple[str, str, str]:
    tp_cte = tp_serv = toma = ''
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return '—', '—', '—'
    for el in root.iter():
        tag = _local_tag(el.tag)
        if tag == 'ide':
            for ch in el:
                ct = _local_tag(ch.tag)
                if ct == 'tpCTe':
                    tp_cte = (ch.text or '').strip()
                elif ct == 'tpServ':
                    tp_serv = (ch.text or '').strip()
                elif ct == 'toma3':
                    for t in ch:
                        if _local_tag(t.tag) in {'toma', 'tpToma'}:
                            toma = (t.text or '').strip()
                elif ct == 'toma4':
                    for t in ch:
                        if _local_tag(t.tag) in {'toma', 'tpToma'}:
                            toma = (t.text or '').strip() or '4'
            break
    return (
        TP_CTE.get(tp_cte, tp_cte or '—'),
        TP_SERV.get(tp_serv, tp_serv or '—'),
        TP_TOMA.get(toma, toma or '—'),
    )


@dataclass
class DacteData:
    chave: str = ''
    numero: str = ''
    serie: str = ''
    modelo: str = '57'
    dh_emissao: str = ''
    protocolo: str = ''
    dh_protocolo: str = ''
    modal: str = ''
    cfop: str = ''
    nat_op: str = ''
    tp_cte: str = ''
    tp_serv: str = ''
    toma_label: str = ''
    emit: dict[str, Any] = field(default_factory=dict)
    rem: dict[str, Any] = field(default_factory=dict)
    dest: dict[str, Any] = field(default_factory=dict)
    exped: dict[str, Any] = field(default_factory=dict)
    receb: dict[str, Any] = field(default_factory=dict)
    tomador: dict[str, Any] = field(default_factory=dict)
    valor_servico: Any = Decimal('0')
    valor_receber: Any = Decimal('0')
    componentes: list[tuple[str, str]] = field(default_factory=list)
    cst: str = '—'
    v_bc: str = '0,00'
    p_icms: str = '0,00'
    v_icms: str = '0,00'
    chaves_nfe: list[str] = field(default_factory=list)
    qr_url: str = ''
    observacoes: str = ''
    prod_pred: str = ''
    rntrc: str = ''
    mun_ini: str = ''
    uf_ini: str = ''
    mun_fim: str = ''
    uf_fim: str = ''
    cancelado: bool = False


def montar_dacte_data(xml: str) -> DacteData:
    raw = xml.encode('utf-8') if isinstance(xml, str) else xml
    parsed = parse_cte_xml(raw)
    if parsed.erro:
        raise ValueError(parsed.erro)

    qr_url, x_obs, prod_pred, rntrc = _extract_qr_and_obs(xml if isinstance(xml, str) else xml.decode('utf-8', 'ignore'))
    tp_cte, tp_serv, toma_label = _tp_cte_serv_toma(
        xml if isinstance(xml, str) else xml.decode('utf-8', 'ignore'),
    )

    comps_src = parsed.componentes_frete
    totais = parsed.totais_json if isinstance(parsed.totais_json, dict) else {}
    # parser pode devolver um único Comp (dict); preferir lista completa em totais_json.
    if isinstance(totais.get('Comp'), list) and totais['Comp']:
        comps_src = totais['Comp']
    elif not comps_src:
        comps_src = totais

    cst, v_bc, p_icms, v_icms = _icms_from_imposto(parsed.imposto_json or {})
    prot = parsed.prot_json if isinstance(parsed.prot_json, dict) else {}
    dh_prot = _text(prot.get('dhRecbto'))
    if dh_prot:
        try:
            from datetime import datetime

            dt = datetime.fromisoformat(dh_prot.replace('Z', '+00:00'))
            dh_prot = dt.strftime('%d/%m/%Y %H:%M:%S')
        except Exception:
            pass

    dh_emi = ''
    if parsed.dh_emissao:
        dh_emi = parsed.dh_emissao.strftime('%d/%m/%Y %H:%M:%S')

    return DacteData(
        chave=parsed.chave_acesso,
        numero=parsed.numero,
        serie=parsed.serie,
        modelo=parsed.modelo or '57',
        dh_emissao=dh_emi,
        protocolo=parsed.protocolo or _text(prot.get('nProt')),
        dh_protocolo=dh_prot,
        modal=TP_MODAL.get(parsed.modal, parsed.modal or '—'),
        cfop=parsed.cfop,
        nat_op=parsed.nat_op,
        tp_cte=tp_cte,
        tp_serv=tp_serv,
        toma_label=toma_label,
        emit=parsed.emit_json or {},
        rem=parsed.rem_json or {},
        dest=parsed.dest_json or {},
        exped=parsed.exped_json or {},
        receb=parsed.receb_json or {},
        tomador=parsed.tomador_json or {},
        valor_servico=parsed.valor_total_servico or totais.get('vTPrest') or 0,
        valor_receber=parsed.valor_receber or totais.get('vRec') or 0,
        componentes=_normalize_comps(comps_src),
        cst=cst,
        v_bc=v_bc,
        p_icms=p_icms,
        v_icms=v_icms,
        chaves_nfe=list(parsed.chaves_nfe_vinculadas or []),
        qr_url=qr_url,
        observacoes=x_obs,
        prod_pred=prod_pred or '—',
        rntrc=rntrc or '—',
        mun_ini=parsed.municipio_inicio,
        uf_ini=parsed.uf_inicio,
        mun_fim=parsed.municipio_fim,
        uf_fim=parsed.uf_fim,
        cancelado=bool(parsed.cancelado),
    )


class _DacteCanvas:
    def __init__(self, data: DacteData):
        self.data = data
        self.buf = BytesIO()
        self.c = canvas.Canvas(self.buf, pagesize=A4)
        self.c.setTitle(f'DACTE CT-e {data.numero}/{data.serie}')
        self.c.setAuthor('NEXUS APP')
        self.x0 = MARGIN
        self.y = PAGE_H - MARGIN
        self.w = PAGE_W - 2 * MARGIN

    def _line(self, x1, y1, x2, y2):
        self.c.setStrokeColorRGB(0.15, 0.15, 0.15)
        self.c.setLineWidth(LINE)
        self.c.line(x1, y1, x2, y2)

    def _rect(self, x, y, w, h):
        self.c.setStrokeColorRGB(0.15, 0.15, 0.15)
        self.c.setLineWidth(LINE)
        self.c.rect(x, y, w, h, stroke=1, fill=0)

    def _set_font(self, bold: bool, size: float):
        self.c.setFont('Helvetica-Bold' if bold else 'Helvetica', size)

    def _label(self, text: str, x: float, y: float, size: float = 5.5):
        self._set_font(False, size)
        self.c.setFillColorRGB(0.25, 0.25, 0.25)
        self.c.drawString(x, y, text)
        self.c.setFillColorRGB(0, 0, 0)

    def _value(self, text: str, x: float, y: float, size: float = 8, bold: bool = True):
        self._set_font(bold, size)
        self.c.setFillColorRGB(0, 0, 0)
        self.c.drawString(x, y, text)

    def _value_right(self, text: str, x: float, y: float, size: float = 8, bold: bool = True):
        self._set_font(bold, size)
        self.c.drawRightString(x, y, text)

    def _value_center(self, text: str, x: float, y: float, size: float = 8, bold: bool = True):
        self._set_font(bold, size)
        self.c.drawCentredString(x, y, text)

    def _wrap(self, text: str, max_w: float, font: str, size: float) -> list[str]:
        self.c.setFont(font, size)
        words = (text or '').split()
        if not words:
            return ['—']
        lines: list[str] = []
        cur = words[0]
        for w in words[1:]:
            trial = f'{cur} {w}'
            if self.c.stringWidth(trial, font, size) <= max_w:
                cur = trial
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)
        return lines

    def _box_header(self, title: str, x: float, y_top: float, w: float, h: float) -> float:
        """Desenha box com título no topo; retorna y interno para conteúdo."""
        y_bot = y_top - h
        self._rect(x, y_bot, w, h)
        self._label(title, x + INNER_PAD, y_top - 3.2 * mm, 5.2)
        return y_top - 5.2 * mm

    def _draw_canhoto(self):
        h = 14 * mm
        y_bot = self.y - h
        self._rect(self.x0, y_bot, self.w * 0.72, h)
        self._label(
            'DECLARO QUE RECEBI OS VOLUMES DESTE CONHECIMENTO EM PERFEITO ESTADO',
            self.x0 + INNER_PAD,
            self.y - 3.2 * mm,
            5.5,
        )
        self._label('NOME', self.x0 + INNER_PAD, self.y - 7.5 * mm)
        self._line(self.x0 + 12 * mm, self.y - 8.5 * mm, self.x0 + self.w * 0.45, self.y - 8.5 * mm)
        self._label('RG', self.x0 + INNER_PAD, self.y - 12 * mm)
        self._line(self.x0 + 8 * mm, self.y - 13 * mm, self.x0 + 40 * mm, self.y - 13 * mm)
        self._label('ASSINATURA / CARIMBO', self.x0 + 45 * mm, self.y - 12 * mm)

        rx = self.x0 + self.w * 0.72
        rw = self.w * 0.28
        self._rect(rx, y_bot, rw, h)
        self._value_center('CT-e', rx + rw / 2, self.y - 4 * mm, 9)
        self._label('Nº', rx + INNER_PAD, self.y - 7.5 * mm)
        self._value(self.data.numero or '—', rx + 8 * mm, self.y - 7.5 * mm, 8)
        self._label('SÉRIE', rx + INNER_PAD, self.y - 11.5 * mm)
        self._value(self.data.serie or '—', rx + 14 * mm, self.y - 11.5 * mm, 8)
        self.y = y_bot - 1.5 * mm

    def _draw_header(self):
        left_w = self.w * 0.42
        mid_w = self.w * 0.40
        right_w = self.w - left_w - mid_w
        h = 42 * mm
        y_bot = self.y - h

        # Emitente
        self._rect(self.x0, y_bot, left_w, h)
        self._label('EMITENTE / TRANSPORTADORA', self.x0 + INNER_PAD, self.y - 3.2 * mm)
        emit_lines = _party_lines(self.data.emit)
        yy = self.y - 7 * mm
        for i, line in enumerate(emit_lines):
            size = 8 if i == 0 else 6.5
            bold = i == 0
            for wrapped in self._wrap(line, left_w - 2 * INNER_PAD, 'Helvetica-Bold' if bold else 'Helvetica', size):
                self._value(wrapped, self.x0 + INNER_PAD, yy, size, bold=bold)
                yy -= 3.3 * mm
                if yy < y_bot + 2 * mm:
                    break

        # Centro: DACTE + chave + barcode + protocolo
        mx = self.x0 + left_w
        self._rect(mx, y_bot + 28 * mm, mid_w, 14 * mm)
        self._value_center('DACTE', mx + mid_w / 2, self.y - 5 * mm, 14)
        self._value_center(
            'Documento Auxiliar do Conhecimento de Transporte Eletrônico',
            mx + mid_w / 2,
            self.y - 9.5 * mm,
            5.5,
            bold=False,
        )
        self._value_center(f'MODAL: {self.data.modal}', mx + mid_w / 2, self.y - 13 * mm, 7)

        # Modelo / série / número / emissão
        row_h = 9 * mm
        cols = [
            ('MODELO', self.data.modelo),
            ('SÉRIE', self.data.serie),
            ('NÚMERO', self.data.numero),
            ('EMISSÃO', (self.data.dh_emissao or '—')[:16]),
        ]
        cw = mid_w / len(cols)
        ry = y_bot + 19 * mm
        for i, (lab, val) in enumerate(cols):
            cx = mx + i * cw
            self._rect(cx, ry, cw, row_h)
            self._label(lab, cx + 1 * mm, ry + row_h - 3 * mm)
            self._value(str(val or '—')[:18], cx + 1 * mm, ry + 2.2 * mm, 7)

        # Chave + barcode
        self._rect(mx, y_bot, mid_w, 19 * mm)
        self._label('CHAVE DE ACESSO', mx + INNER_PAD, y_bot + 16 * mm)
        chave = self.data.chave or ''
        chave_fmt = ' '.join(chave[i : i + 4] for i in range(0, len(chave), 4)) if chave else '—'
        self._value(chave_fmt, mx + INNER_PAD, y_bot + 12.5 * mm, 6.5)
        if len(chave) == 44:
            try:
                bc = code128.Code128(chave, barHeight=7 * mm, barWidth=0.55, humanReadable=False)
                bw = min(bc.width, mid_w - 4 * mm)
                bc.drawOn(self.c, mx + (mid_w - bw) / 2, y_bot + 3.5 * mm)
            except Exception:
                pass
        self._label(
            f'Protocolo: {self.data.protocolo or "—"}  {self.data.dh_protocolo or ""}'.strip(),
            mx + INNER_PAD,
            y_bot + 1.2 * mm,
            5.5,
        )

        # QR
        rx = mx + mid_w
        self._rect(rx, y_bot, right_w, h)
        self._label('CONSULTA / QR CODE', rx + INNER_PAD, self.y - 3.2 * mm)
        if self.data.qr_url:
            try:
                qr_widget = qr.QrCodeWidget(self.data.qr_url)
                bounds = qr_widget.getBounds()
                qw = bounds[2] - bounds[0]
                qh = bounds[3] - bounds[1]
                size = min(right_w - 4 * mm, h - 8 * mm)
                d = Drawing(size, size, transform=[size / qw, 0, 0, size / qh, 0, 0])
                d.add(qr_widget)
                d.drawOn(self.c, rx + (right_w - size) / 2, y_bot + 3 * mm)
            except Exception:
                self._value('QR indisponível', rx + INNER_PAD, y_bot + h / 2, 7, bold=False)

        self.y = y_bot - 1.5 * mm

    def _draw_meta_row(self):
        h = 10 * mm
        y_bot = self.y - h
        cols = [
            ('TIPO DO CT-e', self.data.tp_cte),
            ('TIPO DO SERVIÇO', self.data.tp_serv),
            ('TOMADOR DO SERVIÇO', self.data.toma_label),
            ('CFOP', f'{self.data.cfop} - {self.data.nat_op}'[:42]),
        ]
        cw = self.w / 4
        for i, (lab, val) in enumerate(cols):
            x = self.x0 + i * cw
            self._rect(x, y_bot, cw, h)
            self._label(lab, x + INNER_PAD, self.y - 3 * mm)
            for j, line in enumerate(self._wrap(str(val), cw - 2 * INNER_PAD, 'Helvetica-Bold', 7)[:2]):
                self._value(line, x + INNER_PAD, self.y - 6.5 * mm - j * 2.8 * mm, 7)
        self.y = y_bot - 1.5 * mm

    def _draw_party_pair(self, left_title: str, left: dict, right_title: str, right: dict):
        h = 22 * mm
        y_bot = self.y - h
        hw = self.w / 2
        for i, (title, party) in enumerate(((left_title, left), (right_title, right))):
            x = self.x0 + i * hw
            self._rect(x, y_bot, hw, h)
            self._label(title, x + INNER_PAD, self.y - 3 * mm)
            lines = _party_lines(party)
            yy = self.y - 6.5 * mm
            for idx, line in enumerate(lines):
                bold = idx == 0
                size = 7 if bold else 6.2
                font = 'Helvetica-Bold' if bold else 'Helvetica'
                for wrapped in self._wrap(line, hw - 2 * INNER_PAD, font, size):
                    self._value(wrapped, x + INNER_PAD, yy, size, bold=bold)
                    yy -= 3.1 * mm
                    if yy < y_bot + 1.5 * mm:
                        break
                if yy < y_bot + 1.5 * mm:
                    break
        self.y = y_bot - 1.5 * mm

    def _draw_tomador_carga(self):
        h = 16 * mm
        y_bot = self.y - h
        left_w = self.w * 0.62
        self._rect(self.x0, y_bot, left_w, h)
        self._label('TOMADOR DO SERVIÇO (DADOS)', self.x0 + INNER_PAD, self.y - 3 * mm)
        yy = self.y - 6.5 * mm
        for i, line in enumerate(_party_lines(self.data.tomador)[:3]):
            self._value(line, self.x0 + INNER_PAD, yy, 7 if i == 0 else 6.2, bold=(i == 0))
            yy -= 3.1 * mm

        rx = self.x0 + left_w
        rw = self.w - left_w
        self._rect(rx, y_bot, rw, h)
        self._label('PRODUTO PREDOMINANTE', rx + INNER_PAD, self.y - 3 * mm)
        self._value(self.data.prod_pred[:40], rx + INNER_PAD, self.y - 7 * mm, 7)
        self._label('INÍCIO / FIM DA PRESTAÇÃO', rx + INNER_PAD, self.y - 11 * mm)
        rota = f'{self.data.mun_ini}/{self.data.uf_ini} → {self.data.mun_fim}/{self.data.uf_fim}'
        self._value(rota[:42], rx + INNER_PAD, self.y - 14 * mm, 6.5)
        self.y = y_bot - 1.5 * mm

    def _draw_valores(self):
        h = 28 * mm
        y_bot = self.y - h
        left_w = self.w * 0.62
        self._rect(self.x0, y_bot, left_w, h)
        self._label('COMPONENTES DO VALOR DA PRESTAÇÃO', self.x0 + INNER_PAD, self.y - 3 * mm)
        comps = self.data.componentes[:8] or [('—', '0,00')]
        col_w = left_w / 2
        for i, (nome, val) in enumerate(comps):
            col = i % 2
            row = i // 2
            x = self.x0 + col * col_w + INNER_PAD
            yy = self.y - 7 * mm - row * 4.2 * mm
            self._value(f'{nome}:', x, yy, 6.2, bold=False)
            self._value_right(val, x + col_w - 3 * mm, yy, 6.5)

        rx = self.x0 + left_w
        rw = self.w - left_w
        self._rect(rx, y_bot, rw, h)
        self._label('VALOR TOTAL DO SERVIÇO', rx + INNER_PAD, self.y - 4 * mm)
        self._value(format_currency_br(self.data.valor_servico), rx + INNER_PAD, self.y - 9 * mm, 11)
        self._label('VALOR A RECEBER', rx + INNER_PAD, self.y - 15 * mm)
        self._value(format_currency_br(self.data.valor_receber), rx + INNER_PAD, self.y - 20 * mm, 11)
        self._label(f'RNTRC: {self.data.rntrc}', rx + INNER_PAD, y_bot + 2.5 * mm, 6)
        self.y = y_bot - 1.5 * mm

    def _draw_imposto(self):
        h = 12 * mm
        y_bot = self.y - h
        cols = [
            ('SITUAÇÃO TRIBUTÁRIA', self.data.cst),
            ('BASE DE CÁLCULO', self.data.v_bc),
            ('ALÍQ. ICMS', self.data.p_icms),
            ('VALOR ICMS', self.data.v_icms),
        ]
        cw = self.w / 4
        self._label('INFORMAÇÕES RELATIVAS AO IMPOSTO', self.x0 + INNER_PAD, self.y + 0.5 * mm, 5.2)
        for i, (lab, val) in enumerate(cols):
            x = self.x0 + i * cw
            self._rect(x, y_bot, cw, h)
            self._label(lab, x + INNER_PAD, self.y - 3.5 * mm)
            self._value(str(val), x + INNER_PAD, self.y - 8.5 * mm, 9)
        self.y = y_bot - 1.5 * mm

    def _draw_documentos(self):
        h = 18 * mm
        y_bot = self.y - h
        self._rect(self.x0, y_bot, self.w, h)
        self._label('DOCUMENTOS ORIGINÁRIOS', self.x0 + INNER_PAD, self.y - 3 * mm)
        self._label('TIPO', self.x0 + INNER_PAD, self.y - 6.5 * mm, 5)
        self._label('CHAVE DE ACESSO NF-e', self.x0 + 18 * mm, self.y - 6.5 * mm, 5)
        self._label('SÉRIE / NÚMERO', self.x0 + self.w * 0.72, self.y - 6.5 * mm, 5)
        yy = self.y - 10 * mm
        docs = self.data.chaves_nfe[:4] or []
        if not docs:
            self._value('Nenhum documento vinculado no XML.', self.x0 + INNER_PAD, yy, 6.5, bold=False)
        for chave in docs:
            self._value('NF-e', self.x0 + INNER_PAD, yy, 6.5)
            self._value(chave, self.x0 + 18 * mm, yy, 6.5, bold=False)
            self._value(_serie_nro_de_chave_nfe(chave), self.x0 + self.w * 0.72, yy, 6.5)
            yy -= 3.2 * mm
        self.y = y_bot - 1.5 * mm

    def _draw_obs(self):
        h = max(22 * mm, min(40 * mm, 8 * mm + 3.2 * mm * 6))
        y_bot = self.y - h
        self._rect(self.x0, y_bot, self.w, h)
        self._label('OBSERVAÇÕES', self.x0 + INNER_PAD, self.y - 3 * mm)
        obs = self.data.observacoes or '—'
        yy = self.y - 6.5 * mm
        for line in self._wrap(obs, self.w - 2 * INNER_PAD, 'Helvetica', 6.5)[:8]:
            self._value(line, self.x0 + INNER_PAD, yy, 6.5, bold=False)
            yy -= 3.1 * mm
        self.y = y_bot - 2 * mm

    def _draw_footer_note(self):
        self._set_font(False, 6)
        self.c.setFillColorRGB(0.35, 0.35, 0.35)
        self.c.drawString(
            self.x0,
            MARGIN - 1 * mm,
            'DACTE gerado pelo NEXUS APP a partir do XML autorizado · Documento auxiliar · Consulte a validade pela chave/QR na SEFAZ',
        )
        self.c.setFillColorRGB(0, 0, 0)
        if self.data.cancelado:
            self.c.saveState()
            self.c.setFillColorRGB(0.75, 0.1, 0.1)
            self.c.setFont('Helvetica-Bold', 40)
            self.c.translate(PAGE_W / 2, PAGE_H / 2)
            self.c.rotate(35)
            self.c.drawCentredString(0, 0, 'CANCELADO')
            self.c.restoreState()

    def build(self) -> bytes:
        self._draw_canhoto()
        self._draw_header()
        self._draw_meta_row()
        self._draw_party_pair('REMETENTE', self.data.rem, 'DESTINATÁRIO', self.data.dest)
        if self.data.exped or self.data.receb:
            self._draw_party_pair('EXPEDIDOR', self.data.exped or {}, 'RECEBEDOR', self.data.receb or {})
        self._draw_tomador_carga()
        self._draw_valores()
        self._draw_imposto()
        self._draw_documentos()
        self._draw_obs()
        self._draw_footer_note()
        self.c.showPage()
        self.c.save()
        return self.buf.getvalue()


def gerar_dacte_nexus_pdf(xml: str) -> bytes:
    """Gera PDF do DACTE Nexus a partir do XML completo do CT-e."""
    data = montar_dacte_data(xml)
    return _DacteCanvas(data).build()
