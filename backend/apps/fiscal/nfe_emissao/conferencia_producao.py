"""Payload de permissões e checklist produção na conferência NF-e Saída."""

from __future__ import annotations

from typing import Any

from apps.fiscal.models import NFeSaida
from apps.fiscal.nfe_emissao.config_producao import MSG_PRODUCAO_NAO_HABILITADA, nfe_producao_habilitada
from apps.fiscal.nfe_emissao.empresa_emitente import resolver_empresa_emitente_nfe
from apps.fiscal.nfe_emissao.numeracao import NFeNumeracaoError, obter_config_numeracao
from apps.fiscal.nfe_emissao.permissoes_producao import MSG_SEM_PERMISSAO_USUARIO, usuario_pode_emitir_nfe_producao
from apps.fiscal.nfe_emissao.validacao_producao import montar_validacao_emissao_producao
from apps.fiscal.nfe_saida_prontidao import status_conferencia_display


def _numeracao_producao_resumo(nf: NFeSaida) -> dict[str, Any] | None:
    if not nfe_producao_habilitada():
        return None
    try:
        empresa = resolver_empresa_emitente_nfe(nf)
        cfg = obter_config_numeracao(empresa.pk, ambiente='producao')
        return {
            'modelo_documento': cfg.modelo_documento,
            'serie': cfg.serie,
            'proximo_numero': cfg.proximo_numero,
        }
    except NFeNumeracaoError:
        return None


def montar_permissoes_emissao_producao(
    nf: NFeSaida,
    usuario=None,
) -> dict[str, Any]:
    from apps.fiscal.nfe_emissao.ambiente_emissao_nfe import (
        MSG_AMBIENTE_NAO_DEFINIDO,
        ambiente_emissao_nfe_definido,
    )

    habilitada = nfe_producao_habilitada()
    tem_permissao = usuario_pode_emitir_nfe_producao(usuario)
    validacao = montar_validacao_emissao_producao(nf) if habilitada else None

    motivos: list[str] = []
    if not ambiente_emissao_nfe_definido(nf):
        motivos.append(MSG_AMBIENTE_NAO_DEFINIDO)
    elif not habilitada:
        motivos.append(MSG_PRODUCAO_NAO_HABILITADA)
    elif not tem_permissao:
        motivos.append(MSG_SEM_PERMISSAO_USUARIO)
    if validacao:
        motivos.extend(p['mensagem'] for p in validacao.get('pendencias', []))

    pronta = nf.status_conferencia == NFeSaida.StatusConferencia.PRONTA_PARA_EMISSAO
    nao_autorizada_prod = nf.status_emissao_sefaz != NFeSaida.StatusEmissaoSefaz.AUTORIZADA_PRODUCAO
    ambiente_prod = nf.ambiente_emissao == NFeSaida.AmbienteEmissao.PRODUCAO
    ambiente_definido = ambiente_emissao_nfe_definido(nf)
    pode_tentar = (
        habilitada and tem_permissao and pronta and nao_autorizada_prod and ambiente_prod and ambiente_definido
    )
    checklist_ok = bool(validacao and validacao.get('pronta'))
    pode_emitir = pode_tentar and checklist_ok

    motivo = ''
    if not ambiente_definido:
        motivo = MSG_AMBIENTE_NAO_DEFINIDO
    elif not ambiente_prod:
        motivo = 'NF-e não está configurada para ambiente de produção SEFAZ.'
    elif not habilitada:
        motivo = 'Emissão produção SEFAZ desabilitada neste ambiente.'
    elif not tem_permissao:
        motivo = MSG_SEM_PERMISSAO_USUARIO
    elif not pronta:
        motivo = 'Marque a NF-e como pronta para emissão na conferência.'
    elif not nao_autorizada_prod:
        motivo = 'NF-e já autorizada em produção SEFAZ.'
    elif pode_tentar and not pode_emitir:
        motivo = 'Resolva as pendências do checklist de produção antes de emitir.'

    return {
        'producao_habilitada': habilitada,
        'usuario_pode_emitir_producao': tem_permissao,
        'pode_tentar_emitir_producao': pode_tentar,
        'pode_emitir_producao': pode_emitir,
        'motivo_emitir_producao_bloqueado': motivo,
        'motivos_bloqueio_producao': motivos,
        'validacao_producao': validacao,
    }


def _status_producao_label(nf: NFeSaida) -> str:
    status = (nf.status_emissao_sefaz or '').strip()
    labels = {
        NFeSaida.StatusEmissaoSefaz.AUTORIZADA_PRODUCAO: 'Autorizada produção',
        NFeSaida.StatusEmissaoSefaz.REJEITADA_PRODUCAO: 'Rejeitada produção',
        NFeSaida.StatusEmissaoSefaz.ENVIADA_PRODUCAO: 'Enviada produção (aguardando retorno)',
        NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO: 'Autorizada homologação',
    }
    return labels.get(status, status or 'Aguardando emissão produção')


def montar_emissao_producao_conferencia(nf: NFeSaida, usuario=None) -> dict[str, Any]:
    perm = montar_permissoes_emissao_producao(nf, usuario=usuario)
    val = perm.get('validacao_producao') or {}
    pedido = nf.pedido_venda
    empresa = pedido.empresa_emitente if pedido and pedido.empresa_emitente_id else None
    numeracao = _numeracao_producao_resumo(nf)
    return {
        'habilitada': perm['producao_habilitada'],
        'usuario_pode_emitir': perm['usuario_pode_emitir_producao'],
        'pode_emitir': perm['pode_emitir_producao'],
        'pode_tentar_emitir': perm['pode_tentar_emitir_producao'],
        'motivo_bloqueio': perm['motivo_emitir_producao_bloqueado'],
        'motivos_bloqueio': perm['motivos_bloqueio_producao'],
        'ambiente_label': 'Produção SEFAZ',
        'ambiente_emissao_nfe': nf.ambiente_emissao or '',
        'status_conferencia': nf.status_conferencia or '',
        'status_conferencia_display': status_conferencia_display(nf.status_conferencia),
        'status_producao_label': _status_producao_label(nf),
        'pronta': bool(val.get('pronta')),
        'pendencias': val.get('pendencias') or [],
        'alertas': val.get('alertas') or [],
        'emitente': {
            'id': empresa.pk if empresa else None,
            'nome': empresa.razao_social if empresa else '',
        },
        'destinatario': {
            'id': nf.cliente_id,
            'nome': nf.cliente.razao_social if nf.cliente_id else '',
        },
        'valor_total': float(nf.valor_total),
        'serie_nfe': nf.serie_nfe if nf.ambiente_emissao == NFeSaida.AmbienteEmissao.PRODUCAO else '',
        'numero_nfe': nf.numero_nfe if nf.ambiente_emissao == NFeSaida.AmbienteEmissao.PRODUCAO else '',
        'numeracao_producao': numeracao,
        'status_emissao_sefaz': nf.status_emissao_sefaz or '',
        'autorizada_producao': nf.status_emissao_sefaz == NFeSaida.StatusEmissaoSefaz.AUTORIZADA_PRODUCAO,
        'protocolo_autorizacao': nf.protocolo_autorizacao or '',
        'cstat_autorizacao': nf.cstat_autorizacao or '',
        'motivo_autorizacao': nf.motivo_autorizacao or '',
        'chave_acesso': nf.chave_acesso or '',
        'tem_xml_autorizado': bool((nf.xml_autorizado or '').strip()),
    }
