"""Recuperação administrativa de numeração NF-e Saída perdida após descarte/exclusão local — ERP 4.0.15.2.25."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from django.db import transaction

from apps.fiscal.models import NFeNumeracaoConfiguracao, NFeNumeracaoNumeroLiberado, NFeSaida, NFeSaidaEvento
from apps.fiscal.nfe_emissao.numeracao import _nnf_str, _serie_digits, obter_config_numeracao
from apps.fiscal.nfe_emissao.numeracao_liberacao import (
    _numero_inteiro_nf,
    nf_pode_liberar_numero_fiscal,
    nf_teve_comunicacao_sefaz_ou_incerta,
)
from apps.fiscal.nfe_saida_ciclo_vida import STATUS_NFE_DESCARTADA_INTERNA, nf_esta_descartada_ou_inativa
from apps.fiscal.nfe_saida_efeitos import _registrar_evento

CONFIRMACAO_TOKEN = 'RECUPERAR_NUMERO_NFE_LOCAL'

MSG_SEGURO = (
    'Número {numero} recuperado para reutilização local. '
    'Nenhum indício de comunicação SEFAZ encontrado.'
)
MSG_INSEGURO = (
    'Número {numero} não pode ser recuperado porque há indício fiscal externo '
    'ou número posterior já consumido.'
)
MSG_JA_NO_POOL = (
    'Número {numero} já está disponível no pool de reutilização (idempotente).'
)


@dataclass
class AnaliseRecuperacaoNumeracao:
    seguro: bool
    mensagem: str
    empresa_id: int
    serie: str
    ambiente: str
    modelo: str
    numero: int
    configuracao_id: int | None = None
    ja_no_pool: bool = False
    pool_id: int | None = None
    nfe_origem_id: int | None = None
    nfe_origem_status: str = ''
    nfe_origem_excluida: bool = False
    nfe_ativa_com_numero: int | None = None
    numeros_posteriores_bloqueio: list[int] = field(default_factory=list)
    indicios_sefaz: list[str] = field(default_factory=list)
    detalhes: dict[str, Any] = field(default_factory=dict)


def _resolver_configuracao(
    *,
    empresa_id: int,
    serie: str,
    ambiente: str,
    modelo: str = '55',
) -> NFeNumeracaoConfiguracao:
    serie_norm = _serie_digits(serie)
    try:
        return obter_config_numeracao(empresa_id, ambiente=ambiente, modelo=modelo)
    except Exception:
        cfg = (
            NFeNumeracaoConfiguracao.objects.filter(
                empresa_id=empresa_id,
                ambiente=ambiente,
                modelo_documento=modelo,
                tipo_operacao=NFeNumeracaoConfiguracao.TipoOperacao.SAIDA,
                serie=serie_norm,
                ativo=True,
            )
            .first()
        )
        if cfg is None:
            raise ValueError(
                f'Configuração de numeração não encontrada para empresa #{empresa_id}, '
                f'série {serie_norm}, ambiente {ambiente}, modelo {modelo}.',
            )
        return cfg


def _nfs_mesma_serie_ambiente(
    *,
    empresa_id: int,
    serie: str,
    ambiente: str,
) -> list[NFeSaida]:
    serie_norm = _serie_digits(serie)
    candidatas = list(
        NFeSaida.objects.filter(
            empresa_emitente_id=empresa_id,
            ambiente_emissao=ambiente,
        ).select_related('pedido_venda', 'faturamento_pedido_venda')
    )
    return [nf for nf in candidatas if _serie_digits(nf.serie_nfe or '') == serie_norm]


def _nf_indica_consumo_fiscal_externo(nf: NFeSaida) -> tuple[bool, str]:
    bloqueado, motivo = nf_teve_comunicacao_sefaz_ou_incerta(nf)
    return bloqueado, motivo


def _coletar_indicios_sefaz_nf(nf: NFeSaida) -> list[str]:
    indicios: list[str] = []
    checks = [
        ('protocolo_autorizacao', nf.protocolo_autorizacao),
        ('recibo_lote', nf.recibo_lote),
        ('xml_envio_lote', bool((nf.xml_envio_lote or '').strip())),
        ('xml_autorizado', bool((nf.xml_autorizado or '').strip())),
        ('xml_protocolo', bool((nf.xml_protocolo or '').strip())),
        ('cstat_autorizacao', nf.cstat_autorizacao),
        ('cstat_lote', nf.cstat_lote),
        ('status_emissao_sefaz', nf.status_emissao_sefaz),
        ('status', nf.status),
    ]
    for nome, valor in checks:
        if valor:
            indicios.append(f'{nome}={valor}')
    bloqueado, motivo = _nf_indica_consumo_fiscal_externo(nf)
    if bloqueado and motivo and motivo not in indicios:
        indicios.append(motivo)
    return indicios


def analisar_recuperacao_numero_nfe_local(
    *,
    empresa_id: int,
    serie: str,
    ambiente: str,
    numero: int,
    modelo: str = '55',
) -> AnaliseRecuperacaoNumeracao:
    if numero < 1 or numero > 999_999_999:
        raise ValueError('Número fiscal fora do intervalo permitido (1–999999999).')

    cfg = _resolver_configuracao(
        empresa_id=empresa_id,
        serie=serie,
        ambiente=ambiente,
        modelo=modelo,
    )
    analise = AnaliseRecuperacaoNumeracao(
        seguro=False,
        mensagem='',
        empresa_id=empresa_id,
        serie=_serie_digits(serie),
        ambiente=ambiente,
        modelo=modelo,
        numero=numero,
        configuracao_id=cfg.pk,
    )

    pool = (
        NFeNumeracaoNumeroLiberado.objects.filter(
            configuracao_id=cfg.pk,
            numero=numero,
            consumido_em__isnull=True,
        )
        .order_by('pk')
        .first()
    )
    if pool:
        analise.seguro = True
        analise.ja_no_pool = True
        analise.pool_id = pool.pk
        analise.nfe_origem_id = pool.nfe_saida_origem_id
        analise.mensagem = MSG_JA_NO_POOL.format(numero=numero)
        return analise

    nfs_serie = _nfs_mesma_serie_ambiente(
        empresa_id=empresa_id,
        serie=serie,
        ambiente=ambiente,
    )
    nfs_numero = [nf for nf in nfs_serie if _numero_inteiro_nf(nf) == numero]
    nf_origem: NFeSaida | None = None
    if nfs_numero:
        nf_origem = sorted(nfs_numero, key=lambda n: n.pk, reverse=True)[0]
        analise.nfe_origem_id = nf_origem.pk
        analise.nfe_origem_status = nf_origem.status or ''
        if not nf_esta_descartada_ou_inativa(nf_origem):
            analise.nfe_ativa_com_numero = nf_origem.pk
            analise.mensagem = MSG_INSEGURO.format(numero=numero)
            analise.detalhes['motivo'] = (
                f'Existe NF-e ativa #{nf_origem.pk} com número {numero} (status {nf_origem.status}).'
            )
            return analise
        analise.indicios_sefaz = _coletar_indicios_sefaz_nf(nf_origem)
        if analise.indicios_sefaz:
            analise.mensagem = MSG_INSEGURO.format(numero=numero)
            analise.detalhes['motivo'] = 'Indícios SEFAZ na NF-e origem descartada.'
            return analise
        pode, msg = nf_pode_liberar_numero_fiscal(nf_origem)
        if not pode:
            analise.mensagem = MSG_INSEGURO.format(numero=numero)
            analise.detalhes['motivo'] = msg
            return analise
    else:
        analise.nfe_origem_excluida = True

    posteriores_bloqueio: list[int] = []
    for nf in nfs_serie:
        n = _numero_inteiro_nf(nf)
        if n is None or n <= numero:
            continue
        bloqueado, _ = _nf_indica_consumo_fiscal_externo(nf)
        if bloqueado:
            posteriores_bloqueio.append(n)
    analise.numeros_posteriores_bloqueio = sorted(set(posteriores_bloqueio))
    if analise.numeros_posteriores_bloqueio:
        analise.mensagem = MSG_INSEGURO.format(numero=numero)
        analise.detalhes['motivo'] = (
            'Número(s) posterior(es) com indício de autorização/transmissão SEFAZ: '
            f'{analise.numeros_posteriores_bloqueio}.'
        )
        return analise

    analise.seguro = True
    analise.mensagem = MSG_SEGURO.format(numero=numero)
    return analise


@transaction.atomic
def executar_recuperacao_numero_nfe_local(
    *,
    empresa_id: int,
    serie: str,
    ambiente: str,
    numero: int,
    motivo: str,
    modelo: str = '55',
    usuario=None,
) -> dict[str, Any]:
    motivo = (motivo or '').strip()
    if len(motivo) < 10:
        raise ValueError('Informe um motivo com pelo menos 10 caracteres.')

    analise = analisar_recuperacao_numero_nfe_local(
        empresa_id=empresa_id,
        serie=serie,
        ambiente=ambiente,
        numero=numero,
        modelo=modelo,
    )
    if not analise.seguro:
        return {
            'executado': False,
            'seguro': False,
            'mensagem': analise.mensagem,
            'analise': analise,
        }

    cfg = NFeNumeracaoConfiguracao.objects.select_for_update().get(pk=analise.configuracao_id)

    existente = (
        NFeNumeracaoNumeroLiberado.objects.select_for_update()
        .filter(configuracao_id=cfg.pk, numero=numero, consumido_em__isnull=True)
        .first()
    )
    if existente:
        return {
            'executado': False,
            'seguro': True,
            'ja_no_pool': True,
            'mensagem': MSG_JA_NO_POOL.format(numero=numero),
            'pool_id': existente.pk,
            'analise': analise,
        }

    nf_origem_id = analise.nfe_origem_id
    row = NFeNumeracaoNumeroLiberado.objects.create(
        configuracao_id=cfg.pk,
        numero=numero,
        nfe_saida_origem_id=nf_origem_id,
        liberado_por=usuario if usuario and getattr(usuario, 'is_authenticated', False) else None,
        motivo=motivo,
    )

    if nf_origem_id:
        nf = NFeSaida.objects.filter(pk=nf_origem_id).first()
        if nf:
            _registrar_evento(
                nf,
                tipo=NFeSaidaEvento.TipoEvento.NUMERACAO_RECUPERADA_LOCALMENTE,
                status_novo=nf.status or STATUS_NFE_DESCARTADA_INTERNA,
                resumo={
                    'numero_nfe': _nnf_str(numero),
                    'serie_nfe': analise.serie,
                    'ambiente_emissao': ambiente,
                    'configuracao_id': cfg.pk,
                    'reutilizacao_id': row.pk,
                    'recuperacao_administrativa': True,
                    'nfe_origem_excluida': False,
                    'mensagem': MSG_SEGURO.format(numero=numero),
                },
                observacao=motivo,
                usuario=usuario,
            )

    return {
        'executado': True,
        'seguro': True,
        'ja_no_pool': False,
        'mensagem': MSG_SEGURO.format(numero=numero),
        'pool_id': row.pk,
        'configuracao_id': cfg.pk,
        'nfe_origem_id': nf_origem_id,
        'nfe_origem_excluida': analise.nfe_origem_excluida,
        'analise': analise,
    }


def formatar_relatorio_recuperacao(analise: AnaliseRecuperacaoNumeracao) -> str:
    linhas = [
        '=== Recuperação de numeração NF-e Saída (local) ===',
        f'Empresa ID: {analise.empresa_id}',
        f'Série: {analise.serie}',
        f'Ambiente: {analise.ambiente}',
        f'Modelo: {analise.modelo}',
        f'Número: {analise.numero}',
        f'Configuração numeração ID: {analise.configuracao_id or "—"}',
        f'Seguro para recuperar: {"SIM" if analise.seguro else "NÃO"}',
        f'Já no pool: {"SIM" if analise.ja_no_pool else "NÃO"}',
    ]
    if analise.pool_id:
        linhas.append(f'Pool ID: {analise.pool_id}')
    if analise.nfe_origem_id:
        linhas.append(
            f'NF-e origem ID: {analise.nfe_origem_id} (status: {analise.nfe_origem_status or "—"})'
        )
    elif analise.nfe_origem_excluida:
        linhas.append('NF-e origem: não encontrada (possível exclusão física anterior).')
    if analise.nfe_ativa_com_numero:
        linhas.append(f'BLOQUEIO: NF-e ativa com o número: #{analise.nfe_ativa_com_numero}')
    if analise.indicios_sefaz:
        linhas.append('Indícios SEFAZ na NF-e origem:')
        for item in analise.indicios_sefaz:
            linhas.append(f'  - {item}')
    if analise.numeros_posteriores_bloqueio:
        linhas.append(
            'BLOQUEIO: números posteriores autorizados/transmitidos: '
            + ', '.join(str(n) for n in analise.numeros_posteriores_bloqueio)
        )
    if analise.detalhes.get('motivo'):
        linhas.append(f'Motivo do bloqueio: {analise.detalhes["motivo"]}')
    linhas.append('')
    linhas.append(analise.mensagem)
    return '\n'.join(linhas)
