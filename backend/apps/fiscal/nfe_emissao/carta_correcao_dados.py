"""Dados unificados de prévia/comprovante — Carta de Correção (CC-e) NF-e Saída."""

from __future__ import annotations

from typing import Any

from django.utils import timezone

from apps.core.pdf.formatters import fmt_cnpj
from apps.fiscal.models import NFeSaida, NFeSaidaEvento
from apps.fiscal.nfe_emissao.consulta_situacao import _homologacao_da_nfe
from apps.fiscal.nfe_emissao.empresa_emitente import resolver_empresa_emitente_nfe
from apps.fiscal.nfe_integracao.adapters.carta_correcao_parser import CSTAT_EVENTO_REGISTRADO

MSG_O_QUE_NAO_PODE_CORRIGIR = (
    'A CC-e não pode corrigir: valores ou bases de impostos; alíquotas; quantidades ou preços que alterem o total; '
    'dados cadastrais que mudem emitente ou destinatário; data de emissão ou saída; numeração da NF-e.'
)


class NFeCartaCorrecaoDadosError(ValueError):
    pass


def _cstat_registrado(resumo: dict[str, Any] | None) -> bool:
    if not resumo:
        return False
    cstat = str(resumo.get('cStat') or resumo.get('cstat') or '').strip()
    return cstat in CSTAT_EVENTO_REGISTRADO


def _nome_usuario(usuario) -> str:
    if not usuario:
        return ''
    nome = (getattr(usuario, 'get_full_name', lambda: '')() or '').strip()
    if nome:
        return nome
    return (getattr(usuario, 'username', None) or getattr(usuario, 'email', None) or '').strip()


def _fmt_nnf(numero: str | None) -> str:
    digits = ''.join(c for c in str(numero or '') if c.isdigit())
    if not digits:
        return str(numero or '').strip()
    return digits.lstrip('0') or '0'


def _fmt_serie(serie: str | None) -> str:
    digits = ''.join(c for c in str(serie or '') if c.isdigit())
    return str(int(digits)) if digits else str(serie or '').strip()


def _identidade_nfe(nf: NFeSaida) -> dict[str, str]:
    from apps.fiscal.nfe_saida_apresentacao import montar_apresentacao_nfe_saida

    ap = montar_apresentacao_nfe_saida(nf)
    numero = _fmt_nnf(nf.numero_nfe) or str(ap.get('numero_fiscal') or nf.numero or '').strip()
    serie = _fmt_serie(nf.serie_nfe) or str(ap.get('serie_fiscal') or '').strip()
    chave = (nf.chave_acesso or ap.get('chave_acesso') or '').strip()
    return {
        'numero_nfe': numero or '—',
        'serie_nfe': serie or '—',
        'chave_acesso': chave,
    }


def listar_cce_anteriores(nf: NFeSaida) -> list[dict[str, Any]]:
    """CC-e já registradas na SEFAZ (cStat 135/136) — ordem cronológica."""
    qs = (
        NFeSaidaEvento.objects.filter(
            nfe_saida=nf,
            tipo_evento=NFeSaidaEvento.TipoEvento.CARTA_CORRECAO_EMITIDA,
        )
        .select_related('criado_por')
        .order_by('criado_em', 'id')
    )
    out: list[dict[str, Any]] = []
    for ev in qs:
        resumo = ev.resumo if isinstance(ev.resumo, dict) else {}
        if not _cstat_registrado(resumo):
            continue
        seq_raw = resumo.get('sequencia_evento') or resumo.get('n_seq_evento') or (len(out) + 1)
        try:
            sequencia = int(seq_raw)
        except (TypeError, ValueError):
            sequencia = len(out) + 1
        texto = str(resumo.get('texto_correcao') or '').strip()
        emitido = str(resumo.get('emitido_em') or ev.criado_em.isoformat())
        out.append(
            {
                'evento_id': ev.pk,
                'sequencia': sequencia,
                'cstat': str(resumo.get('cStat') or resumo.get('cstat') or ''),
                'xmotivo': str(resumo.get('xMotivo') or resumo.get('xmotivo') or ''),
                'protocolo': str(resumo.get('protocolo') or ''),
                'emitido_em': emitido,
                'texto_correcao': texto,
                'texto_resumo': (texto[:120] + '…') if len(texto) > 120 else texto,
                'usuario_nome': _nome_usuario(ev.criado_por),
                'ambiente': str(resumo.get('ambiente') or ''),
                'tem_comprovante': True,
            },
        )
    return out


def proxima_sequencia_cce(nf: NFeSaida) -> int:
    return len(listar_cce_anteriores(nf)) + 1


def montar_identidade_emitente(nf: NFeSaida) -> dict[str, str]:
    empresa = resolver_empresa_emitente_nfe(nf)
    emitente = (empresa.razao_social or empresa.nome_fantasia or '').strip()
    cnpj = fmt_cnpj(empresa.cnpj or '')
    if not emitente:
        raise NFeCartaCorrecaoDadosError('Empresa emitente não identificada para a NF-e.')
    return {
        'emitente': emitente,
        'emitente_cnpj': cnpj,
        'emitente_uf': (empresa.uf or '').strip(),
    }


def montar_dados_contexto_cce(nf: NFeSaida) -> dict[str, Any]:
    """Contexto read-only da NF-e para CC-e (sem texto, sem transmissão)."""
    homolog = _homologacao_da_nfe(nf)
    ambiente = 'homologacao' if homolog else 'producao'
    ident = _identidade_nfe(nf)
    emit = montar_identidade_emitente(nf)
    destinatario = ''
    if nf.cliente_id and getattr(nf, 'cliente', None):
        destinatario = (nf.cliente.razao_social or '').strip()
    anteriores = listar_cce_anteriores(nf)
    seq = proxima_sequencia_cce(nf)
    total = len(anteriores)
    mensagem_multiplas = ''
    if total:
        mensagem_multiplas = (
            f'Esta NF-e já possui {total} Carta(s) de Correção. '
            f'Uma nova CC-e será emitida como sequência {seq}.'
        )
    return {
        'ok': True,
        'nfe_saida_id': nf.pk,
        'ambiente': ambiente,
        'ambiente_label': 'Homologação' if homolog else 'Produção',
        'homologacao': homolog,
        'emitente': emit['emitente'],
        'emitente_cnpj': emit['emitente_cnpj'],
        'destinatario': destinatario or '—',
        'chave_acesso': ident['chave_acesso'],
        'numero_nfe': ident['numero_nfe'],
        'serie_nfe': ident['serie_nfe'],
        'sequencia_prevista': seq,
        'total_cce_anteriores': total,
        'mensagem_multiplas': mensagem_multiplas,
        'cce_anteriores': anteriores,
        'o_que_nao_pode_corrigir': MSG_O_QUE_NAO_PODE_CORRIGIR,
    }


def montar_dados_previa_cce(nf: NFeSaida, *, texto_correcao: str) -> dict[str, Any]:
    from apps.fiscal.nfe_emissao.carta_correcao import validar_texto_correcao

    texto = validar_texto_correcao(texto_correcao)
    base = montar_dados_contexto_cce(nf)
    base['texto_correcao'] = texto
    base['previa_em'] = timezone.now().isoformat()
    base['somente_leitura'] = True
    base['transmitido'] = False
    return base


def montar_dados_comprovante_cce(evento: NFeSaidaEvento) -> dict[str, Any]:
    if evento.tipo_evento != NFeSaidaEvento.TipoEvento.CARTA_CORRECAO_EMITIDA:
        raise NFeCartaCorrecaoDadosError('Evento informado não é Carta de Correção.')
    nf = evento.nfe_saida
    resumo = evento.resumo if isinstance(evento.resumo, dict) else {}
    homolog = _homologacao_da_nfe(nf)
    ambiente = str(resumo.get('ambiente') or ('homologacao' if homolog else 'producao'))
    ident = _identidade_nfe(nf)
    emit = montar_identidade_emitente(nf)
    destinatario = ''
    if nf.cliente_id and getattr(nf, 'cliente', None):
        destinatario = (nf.cliente.razao_social or '').strip()
    seq_raw = resumo.get('sequencia_evento') or resumo.get('n_seq_evento') or ''
    try:
        sequencia = int(seq_raw)
    except (TypeError, ValueError):
        sequencia = None
    return {
        'ok': True,
        'evento_id': evento.pk,
        'nfe_saida_id': nf.pk,
        'ambiente': ambiente,
        'ambiente_label': 'Homologação' if ambiente == 'homologacao' else 'Produção',
        'homologacao': ambiente == 'homologacao',
        'emitente': emit['emitente'],
        'emitente_cnpj': emit['emitente_cnpj'],
        'destinatario': destinatario or '—',
        'chave_acesso': ident['chave_acesso'] or str(resumo.get('chave_acesso') or ''),
        'numero_nfe': ident['numero_nfe'],
        'serie_nfe': ident['serie_nfe'],
        'sequencia_evento': sequencia,
        'texto_correcao': str(resumo.get('texto_correcao') or ''),
        'cstat': str(resumo.get('cStat') or resumo.get('cstat') or ''),
        'xmotivo': str(resumo.get('xMotivo') or resumo.get('xmotivo') or ''),
        'protocolo': str(resumo.get('protocolo') or ''),
        'emitido_em': str(resumo.get('emitido_em') or evento.criado_em.isoformat()),
        'usuario_nome': _nome_usuario(evento.criado_por),
        'transmitido': True,
    }
