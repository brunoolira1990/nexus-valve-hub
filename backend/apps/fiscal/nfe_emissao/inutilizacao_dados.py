"""Dados de contexto — Inutilização SEFAZ NF-e."""

from __future__ import annotations

from typing import Any

from apps.core.pdf.formatters import fmt_cnpj
from apps.fiscal.models import NFeNumeracaoConfiguracao, NFeSaida
from apps.fiscal.nfe_emissao.inutilizacao_sefaz import (
    pode_inutilizar_faixa_numeracao,
    pode_inutilizar_numero_nfe,
    sugerir_faixa_inutilizacao_nfe,
)


def montar_dados_contexto_inutilizacao_config(
    cfg: NFeNumeracaoConfiguracao,
    *,
    numero_inicial: int | None = None,
    numero_final: int | None = None,
    usuario=None,
) -> dict[str, Any]:
    empresa = cfg.empresa
    homolog = cfg.ambiente == NFeNumeracaoConfiguracao.Ambiente.HOMOLOGACAO
    ini = numero_inicial if numero_inicial is not None else cfg.proximo_numero
    fim = numero_final if numero_final is not None else ini
    pode, motivo, detalhes = pode_inutilizar_faixa_numeracao(
        cfg,
        numero_inicial=ini,
        numero_final=fim,
        usuario=usuario,
    )
    return {
        'configuracao_id': cfg.pk,
        'empresa_id': empresa.pk,
        'empresa_razao_social': empresa.razao_social or '',
        'cnpj': fmt_cnpj(empresa.cnpj or ''),
        'ambiente': cfg.ambiente,
        'ambiente_label': 'Homologação' if homolog else 'Produção',
        'modelo_documento': cfg.modelo_documento,
        'tipo_operacao': cfg.tipo_operacao,
        'serie': cfg.serie,
        'proximo_numero': cfg.proximo_numero,
        'numero_inicial_sugerido': ini,
        'numero_final_sugerido': fim,
        'pode_inutilizar': pode,
        'motivo_bloqueio': motivo,
        'exige_confirmacao_producao': cfg.ambiente == NFeNumeracaoConfiguracao.Ambiente.PRODUCAO,
        'alerta_producao': (
            'Inutilização em PRODUÇÃO SEFAZ — documento fiscal irreversível. Revise a faixa com o contador.'
            if cfg.ambiente == NFeNumeracaoConfiguracao.Ambiente.PRODUCAO
            else None
        ),
        'numeros_bloqueados': detalhes.get('numeros_bloqueados', []),
        'nfs_na_faixa': detalhes.get('nfs_na_faixa', []),
    }


def montar_dados_contexto_inutilizacao_nfe(nf: NFeSaida, *, usuario=None) -> dict[str, Any]:
    pode, motivo, cfg = pode_inutilizar_numero_nfe(nf, usuario=usuario)
    faixa = sugerir_faixa_inutilizacao_nfe(nf)
    base: dict[str, Any] = {
        'nfe_saida_id': nf.pk,
        'pode_inutilizar': pode,
        'motivo_bloqueio': motivo,
        'numero_inicial_sugerido': faixa.get('numero_inicial'),
        'numero_final_sugerido': faixa.get('numero_final'),
        'configuracao_id': cfg.pk if cfg else None,
        'serie': faixa.get('serie') or nf.serie_nfe or '',
        'ambiente': nf.ambiente_emissao or '',
        'ambiente_label': 'Homologação' if (nf.ambiente_emissao or '') == 'homologacao' else 'Produção',
        'exige_confirmacao_producao': (nf.ambiente_emissao or '') == 'producao',
        'alerta_producao': (
            'Inutilização em PRODUÇÃO SEFAZ — irreversível. Confirme com o contador.'
            if (nf.ambiente_emissao or '') == 'producao'
            else None
        ),
        'nfe': {
            'id': nf.pk,
            'numero_nfe': faixa.get('numero_exibicao') or nf.numero_nfe or '',
            'serie_nfe': nf.serie_nfe or '',
            'status': nf.status or '',
            'status_emissao_sefaz': nf.status_emissao_sefaz or '',
            'chave_acesso': nf.chave_acesso or '',
        },
    }
    if cfg is not None:
        base.update(
            {
                'empresa_id': cfg.empresa_id,
                'empresa_razao_social': cfg.empresa.razao_social or '',
                'cnpj': fmt_cnpj(cfg.empresa.cnpj or ''),
                'modelo_documento': cfg.modelo_documento,
            },
        )
    return base
