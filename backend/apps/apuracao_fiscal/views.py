import csv
from datetime import datetime
from io import StringIO

from django.http import HttpResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.fiscal.services.apuracao_fiscal import build_apuracao_fiscal


def _csv_response(rows: list[list[str]], filename: str) -> HttpResponse:
    buf = StringIO()
    w = csv.writer(buf)
    for row in rows:
        w.writerow(row)
    resp = HttpResponse(buf.getvalue(), content_type='text/csv; charset=utf-8')
    resp['Content-Disposition'] = f'attachment; filename="{filename}"'
    return resp


class ApuracaoView(APIView):
    """
    Apuração fiscal gerencial + base futura SPED / reforma tributária.

    GET query params: empresa_id, data_inicio, data_fim, tipo (ENTRADA|SAIDA|AMBOS),
    status, cliente_id, fornecedor_id, cfop, ncm, modelo_documento, incluir_canceladas,
    formato (json|csv_apuracao|csv_alertas). Compat: mes, ano (quando datas omitidas).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        formato = (request.query_params.get('formato') or 'json').strip().lower()
        payload = build_apuracao_fiscal(dict(request.query_params))
        if formato == 'csv_apuracao':
            return self._csv_apuracao(payload)
        if formato == 'csv_alertas':
            return self._csv_alertas(payload)
        return Response(payload)

    def _csv_apuracao(self, payload: dict) -> HttpResponse:
        r_ent = payload.get('resumo', {}).get('entrada', {})
        r_sai = payload.get('resumo', {}).get('saida', {})
        saldo = payload.get('resumo', {}).get('saldo_gerencial_saida_menos_entrada', {})
        cards = payload.get('cards', {})
        rows: list[list[str]] = [
            ['secao', 'campo', 'valor'],
            ['filtros', 'data_inicio', str(payload.get('filtros', {}).get('data_inicio', ''))],
            ['filtros', 'data_fim', str(payload.get('filtros', {}).get('data_fim', ''))],
            ['filtros', 'tipo', str(payload.get('filtros', {}).get('tipo', ''))],
            ['cards', 'notas_entrada', str(cards.get('notas_entrada', ''))],
            ['cards', 'notas_saida', str(cards.get('notas_saida', ''))],
            ['cards', 'valor_entradas', str(cards.get('valor_entradas', ''))],
            ['cards', 'valor_saidas', str(cards.get('valor_saidas', ''))],
            ['cards', 'icms_entrada', str(cards.get('icms_entrada', ''))],
            ['cards', 'icms_saida', str(cards.get('icms_saida', ''))],
            ['cards', 'ipi_entrada', str(cards.get('ipi_entrada', ''))],
            ['cards', 'ipi_saida', str(cards.get('ipi_saida', ''))],
            ['cards', 'pis_entrada', str(cards.get('pis_entrada', ''))],
            ['cards', 'pis_saida', str(cards.get('pis_saida', ''))],
            ['cards', 'cofins_entrada', str(cards.get('cofins_entrada', ''))],
            ['cards', 'cofins_saida', str(cards.get('cofins_saida', ''))],
            ['cards', 'cbs', str(cards.get('cbs', ''))],
            ['cards', 'ibs', str(cards.get('ibs', ''))],
            ['cards', 'is', str(cards.get('is', ''))],
            ['cards', 'alertas', str(cards.get('alertas', ''))],
        ]
        for label, block in (('entrada', r_ent), ('saida', r_sai)):
            for k, v in block.items():
                rows.append(['resumo', f'{label}_{k}', str(v)])
        for k, v in saldo.items():
            rows.append(['saldo', k, str(v)])
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        return _csv_response(rows, f'apuracao_fiscal_{ts}.csv')

    def _csv_alertas(self, payload: dict) -> HttpResponse:
        rows: list[list[str]] = [
            ['codigo', 'severidade', 'mensagem', 'documento_tipo', 'documento_id', 'item_id', 'acao_sugerida'],
        ]
        for a in payload.get('alertas', []) or []:
            rows.append(
                [
                    str(a.get('codigo', '')),
                    str(a.get('severidade', '')),
                    str(a.get('mensagem', '')),
                    str(a.get('documento_tipo', '')),
                    str(a.get('documento_id', '')),
                    str(a.get('item_id', '')),
                    str(a.get('acao_sugerida', '')),
                ]
            )
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        return _csv_response(rows, f'apuracao_fiscal_alertas_{ts}.csv')
