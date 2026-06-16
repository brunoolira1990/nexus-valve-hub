"""Dados de contexto — Cancelamento SEFAZ NF-e Saída."""

from __future__ import annotations

from typing import Any

from apps.core.pdf.formatters import fmt_cnpj
from apps.fiscal.models import NFeSaida
from apps.fiscal.nfe_emissao.cancelamento_sefaz import pode_cancelar_nfe_sefaz
from apps.fiscal.nfe_emissao.consulta_situacao import _homologacao_da_nfe
from apps.fiscal.nfe_emissao.empresa_emitente import resolver_empresa_emitente_nfe
from apps.fiscal.nfe_saida_financeiro import montar_flags_financeiro_nfe


def _fmt_nnf(numero: str | None) -> str:
    digits = ''.join(c for c in str(numero or '') if c.isdigit())
    if not digits:
        return str(numero or '').strip()
    return digits.lstrip('0') or '0'


def _fmt_serie(serie: str | None) -> str:
    digits = ''.join(c for c in str(serie or '') if c.isdigit())
    return str(int(digits)) if digits else str(serie or '').strip()


def montar_dados_contexto_cancelamento(nf: NFeSaida, *, usuario=None) -> dict[str, Any]:
    pode, motivo = pode_cancelar_nfe_sefaz(nf, usuario=usuario)
    homolog = _homologacao_da_nfe(nf)
    ambiente = 'homologacao' if homolog else 'producao'
    empresa = resolver_empresa_emitente_nfe(nf)
    financeiro = montar_flags_financeiro_nfe(nf)
    cliente_nome = ''
    if nf.cliente_id and nf.cliente:
        cliente_nome = nf.cliente.razao_social or ''

    return {
        'ok': pode,
        'pode_cancelar': pode,
        'motivo_bloqueio': motivo,
        'ambiente': ambiente,
        'ambiente_label': 'Homologação' if homolog else 'Produção SEFAZ',
        'producao': not homolog,
        'exige_confirmacao_producao': not homolog,
        'texto_confirmacao_producao': 'CANCELAR',
        'alerta_producao': (
            'Você está cancelando uma NF-e autorizada em PRODUÇÃO. '
            'Esta ação transmite evento fiscal real para a SEFAZ.'
            if not homolog
            else ''
        ),
        'alerta_financeiro': (
            'Esta NF-e possui contas a receber vinculadas. '
            'O cancelamento fiscal não altera o financeiro automaticamente.'
            if financeiro.get('financeiro_gerado')
            else ''
        ),
        'financeiro_gerado': bool(financeiro.get('financeiro_gerado')),
        'nfe': {
            'id': nf.pk,
            'numero_nfe': _fmt_nnf(nf.numero_nfe) or str(nf.numero or ''),
            'serie_nfe': _fmt_serie(nf.serie_nfe),
            'chave_acesso': nf.chave_acesso or '',
            'protocolo_autorizacao': nf.protocolo_autorizacao or '',
            'valor_total': float(nf.valor_total or 0),
            'cliente_nome': cliente_nome,
            'status': nf.status or '',
            'status_emissao_sefaz': nf.status_emissao_sefaz or '',
        },
        'emitente': {
            'nome': (empresa.razao_social or empresa.nome_fantasia or '').strip(),
            'cnpj': fmt_cnpj(empresa.cnpj or ''),
            'uf': (empresa.uf or '').strip(),
        },
    }
