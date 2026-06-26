"""Inutilização de numeração NF-e — transmissão SEFAZ (NFeInutilizacao4)."""

from __future__ import annotations

import datetime
import logging
import re
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.fiscal.models import (
    NFeInutilizacaoSefaz,
    NFeNumeracaoConfiguracao,
    NFeNumeracaoNumeroLiberado,
    NFeSaida,
    NFeSaidaEvento,
)
from apps.fiscal.nfe_emissao.config_producao import (
    NFeProducaoConfirmacaoError,
    NFeProducaoDesabilitadaError,
    exigir_producao_habilitada,
)
from apps.fiscal.nfe_emissao.numeracao import _nnf_str, _serie_digits, resolver_config_numeracao_nfe_saida
from apps.fiscal.nfe_emissao.permissoes_producao import exigir_permissao_usuario_producao
from apps.fiscal.nfe_emissao.resposta_inutilizacao import montar_resposta_inutilizacao
from apps.fiscal.nfe_integracao.adapters.exceptions import CertificadoA1Error, PyNFeComunicacaoError
from apps.fiscal.nfe_integracao.adapters.inutilizacao_parser import parse_inutilizacao_resposta
from apps.fiscal.nfe_integracao.adapters.certificado_a1 import carregar_certificado_empresa
from apps.fiscal.nfe_integracao.adapters.pynfe_adapter import (
    criar_comunicacao_sefaz,
    extrair_xml_resposta,
    transmitir_inutilizacao_nfe,
)
from apps.fiscal.nfe_saida_bloqueio import nf_cancelada_operacional
from apps.fiscal.nfe_saida_ciclo_vida import nf_possui_autorizacao_sefaz_efetiva
from apps.fiscal.nfe_saida_efeitos import _lock_nfe_saida, _registrar_evento
from apps.fiscal.nfe_saida_envio_email import nf_inutilizada_operacional

logger = logging.getLogger(__name__)

TAMANHO_MINIMO_JUSTIFICATIVA = 15
TAMANHO_MAXIMO_JUSTIFICATIVA = 255
CONFIRMACAO_TEXTO_PRODUCAO = 'INUTILIZAR'

MSG_CONFIRMACAO_PRODUCAO = (
    'Confirmação obrigatória para inutilização em produção: '
    'confirmar_inutilizacao_producao=true e confirmar_texto="INUTILIZAR".'
)
MSG_TIPO_OPERACAO = 'Inutilização disponível apenas para numeração de NF-e saída.'
MSG_FAIXA_INVALIDA = 'Faixa de numeração inválida (número inicial deve ser ≤ final e ≥ 1).'
MSG_NUMERO_AUTORIZADO = 'Não é possível inutilizar número já autorizado na SEFAZ — use cancelamento se aplicável.'
MSG_NUMERO_CANCELADO = 'Número pertence a NF-e cancelada na SEFAZ.'
MSG_NUMERO_JA_INUTILIZADO = 'Número já consta como inutilizado.'
MSG_FAIXA_JA_INUTILIZADA = 'Faixa já inutilizada anteriormente na SEFAZ.'

_STATUS_AUTORIZADO = frozenset(
    {
        NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO,
        NFeSaida.StatusEmissaoSefaz.AUTORIZADA_PRODUCAO,
    },
)


class NFeInutilizacaoError(ValueError):
    def __init__(self, mensagem: str, *, etapa: str = 'VALIDACAO'):
        self.etapa = etapa
        super().__init__(mensagem)


def _somente_digitos(valor: str) -> str:
    return re.sub(r'\D', '', valor or '')


def _numero_int(valor: str | int | None) -> int | None:
    if valor is None:
        return None
    if isinstance(valor, int):
        return valor if valor > 0 else None
    digits = _somente_digitos(str(valor))
    if not digits:
        return None
    n = int(digits)
    return n if n > 0 else None


def validar_justificativa_inutilizacao(texto: str | None) -> str:
    if texto is None:
        raise NFeInutilizacaoError('Justificativa da inutilização é obrigatória.')
    limpo = str(texto).strip()
    if not limpo:
        raise NFeInutilizacaoError('Justificativa da inutilização não pode ser vazia.')
    if len(limpo) < TAMANHO_MINIMO_JUSTIFICATIVA:
        raise NFeInutilizacaoError(
            f'Justificativa deve ter no mínimo {TAMANHO_MINIMO_JUSTIFICATIVA} caracteres (regra SEFAZ).',
        )
    if len(limpo) > TAMANHO_MAXIMO_JUSTIFICATIVA:
        raise NFeInutilizacaoError(
            f'Justificativa deve ter no máximo {TAMANHO_MAXIMO_JUSTIFICATIVA} caracteres.',
        )
    return limpo


def validar_confirmacao_inutilizacao_producao(payload: dict | None) -> None:
    data = payload or {}
    if not data.get('confirmar_inutilizacao_producao'):
        raise NFeInutilizacaoError(MSG_CONFIRMACAO_PRODUCAO, etapa='CONFIRMACAO')
    texto = (data.get('confirmar_texto') or '').strip().upper()
    if texto != CONFIRMACAO_TEXTO_PRODUCAO:
        raise NFeInutilizacaoError(MSG_CONFIRMACAO_PRODUCAO, etapa='CONFIRMACAO')


def _exigir_gates_producao(usuario, confirmacao_payload: dict | None) -> None:
    exigir_producao_habilitada()
    exigir_permissao_usuario_producao(usuario)
    validar_confirmacao_inutilizacao_producao(confirmacao_payload)


def _status_inutilizada(ambiente: str) -> str:
    if ambiente == NFeNumeracaoConfiguracao.Ambiente.HOMOLOGACAO:
        return 'INUTILIZADA_HOMOLOGACAO'
    return 'INUTILIZADA_PRODUCAO'


def _faixa_sobrepoe(ini_a: int, fim_a: int, ini_b: int, fim_b: int) -> bool:
    return not (fim_a < ini_b or ini_a > fim_b)


def _inutilizacao_ja_registrada(cfg: NFeNumeracaoConfiguracao, ini: int, fim: int) -> bool:
    for reg in NFeInutilizacaoSefaz.objects.filter(configuracao=cfg, sefaz_ok=True):
        if _faixa_sobrepoe(ini, fim, reg.numero_inicial, reg.numero_final):
            return True
    return False


def _nfs_por_numero(
    cfg: NFeNumeracaoConfiguracao,
    *,
    numero_inicial: int,
    numero_final: int,
) -> dict[int, NFeSaida]:
    serie_norm = _serie_digits(cfg.serie)
    ambiente = cfg.ambiente
    empresa_id = cfg.empresa_id
    por_numero: dict[int, NFeSaida] = {}
    qs = NFeSaida.objects.filter(
        empresa_emitente_id=empresa_id,
        ambiente_emissao=ambiente,
    ).exclude(numero_nfe='')
    for nf in qs:
        serie_nf = _serie_digits(nf.serie_nfe or '')
        if serie_nf != serie_norm:
            continue
        n = _numero_int(nf.numero_nfe)
        if n is None or n < numero_inicial or n > numero_final:
            continue
        por_numero[n] = nf
    return por_numero


def _motivo_bloqueio_numero(nf: NFeSaida) -> str | None:
    if nf_inutilizada_operacional(nf):
        return MSG_NUMERO_JA_INUTILIZADO
    if nf_cancelada_operacional(nf):
        return MSG_NUMERO_CANCELADO
    if nf_possui_autorizacao_sefaz_efetiva(nf):
        return MSG_NUMERO_AUTORIZADO
    sefaz = (nf.status_emissao_sefaz or '').strip().upper()
    if sefaz in _STATUS_AUTORIZADO:
        return MSG_NUMERO_AUTORIZADO
    st = (nf.status or '').strip().upper()
    if st.startswith('AUTORIZADA') or st in ('EMITIDA', 'EMITIDO'):
        return MSG_NUMERO_AUTORIZADO
    return None


def pode_inutilizar_faixa_numeracao(
    cfg: NFeNumeracaoConfiguracao,
    *,
    numero_inicial: int,
    numero_final: int,
    usuario=None,
) -> tuple[bool, str, dict[str, Any]]:
    detalhes: dict[str, Any] = {'numeros_bloqueados': [], 'nfs_na_faixa': []}
    if cfg.tipo_operacao != NFeNumeracaoConfiguracao.TipoOperacao.SAIDA:
        return False, MSG_TIPO_OPERACAO, detalhes
    if not cfg.ativo:
        return False, 'Configuração de numeração inativa.', detalhes
    if numero_inicial < 1 or numero_final < numero_inicial:
        return False, MSG_FAIXA_INVALIDA, detalhes
    if numero_final > 999_999_999:
        return False, 'Número final fora do intervalo permitido pela SEFAZ.', detalhes

    homolog = cfg.ambiente == NFeNumeracaoConfiguracao.Ambiente.HOMOLOGACAO
    if not homolog:
        try:
            exigir_producao_habilitada()
            exigir_permissao_usuario_producao(usuario)
        except NFeProducaoDesabilitadaError as exc:
            return False, str(exc), detalhes
        except PermissionError as exc:
            return False, str(exc), detalhes

    if _inutilizacao_ja_registrada(cfg, numero_inicial, numero_final):
        return False, MSG_FAIXA_JA_INUTILIZADA, detalhes

    por_numero = _nfs_por_numero(cfg, numero_inicial=numero_inicial, numero_final=numero_final)
    for n, nf in sorted(por_numero.items()):
        motivo = _motivo_bloqueio_numero(nf)
        detalhes['nfs_na_faixa'].append(
            {
                'nfe_saida_id': nf.pk,
                'numero': n,
                'status': nf.status,
                'status_emissao_sefaz': nf.status_emissao_sefaz,
            },
        )
        if motivo:
            detalhes['numeros_bloqueados'].append({'numero': n, 'motivo': motivo, 'nfe_saida_id': nf.pk})
    if detalhes['numeros_bloqueados']:
        primeiro = detalhes['numeros_bloqueados'][0]
        return False, f"Número {primeiro['numero']}: {primeiro['motivo']}", detalhes

    return True, '', detalhes


def sugerir_faixa_inutilizacao_nfe(nf: NFeSaida) -> dict[str, Any]:
    n = _numero_int(nf.numero_nfe)
    return {
        'numero_inicial': n,
        'numero_final': n,
        'serie': _serie_digits(nf.serie_nfe or ''),
        'numero_exibicao': str(int(n)) if n else (nf.numero_nfe or ''),
    }


def pode_inutilizar_numero_nfe(
    nf: NFeSaida,
    *,
    usuario=None,
) -> tuple[bool, str, NFeNumeracaoConfiguracao | None]:
    n = _numero_int(nf.numero_nfe)
    if n is None:
        return False, 'NF-e sem número fiscal reservado para inutilização.', None
    if not (nf.serie_nfe or '').strip():
        return False, 'NF-e sem série fiscal para inutilização.', None
    ambiente = (nf.ambiente_emissao or '').strip()
    if ambiente not in (
        NFeNumeracaoConfiguracao.Ambiente.HOMOLOGACAO,
        NFeNumeracaoConfiguracao.Ambiente.PRODUCAO,
    ):
        return False, 'Ambiente de emissão da NF-e não definido.', None
    empresa_id = nf.empresa_emitente_id
    if not empresa_id:
        return False, 'NF-e sem empresa emitente.', None

    try:
        cfg = resolver_config_numeracao_nfe_saida(
            empresa_id,
            ambiente=ambiente,
            serie_nfe=nf.serie_nfe,
        )
    except Exception as exc:
        return False, str(exc), None

    pode, motivo, _ = pode_inutilizar_faixa_numeracao(
        cfg,
        numero_inicial=n,
        numero_final=n,
        usuario=usuario,
    )
    return pode, motivo, cfg


def _aplicar_inutilizacao_local(
    cfg: NFeNumeracaoConfiguracao,
    *,
    numero_inicial: int,
    numero_final: int,
    justificativa: str,
    resultado,
    usuario,
) -> list[int]:
    status_novo = _status_inutilizada(cfg.ambiente)
    nfs_afetadas: list[int] = []
    por_numero = _nfs_por_numero(cfg, numero_inicial=numero_inicial, numero_final=numero_final)

    for n in range(numero_inicial, numero_final + 1):
        nf = por_numero.get(n)
        if nf is None:
            continue
        nf_locked = _lock_nfe_saida(nf.pk)
        if _motivo_bloqueio_numero(nf_locked):
            continue
        status_anterior = nf_locked.status or ''
        nf_locked.status = status_novo
        nf_locked.save(update_fields=['status'])
        _registrar_evento(
            nf_locked,
            tipo=NFeSaidaEvento.TipoEvento.INUTILIZACAO_SEFAZ_EMITIDA,
            status_anterior=status_anterior,
            status_novo=status_novo,
            resumo={
                'ambiente': cfg.ambiente,
                'serie': cfg.serie,
                'numero_inicial': numero_inicial,
                'numero_final': numero_final,
                'numero_nfe': n,
                'justificativa': justificativa,
                'cStat': resultado.c_stat,
                'xMotivo': resultado.x_motivo,
                'protocolo': resultado.protocolo,
                'configuracao_id': cfg.pk,
            },
            observacao=f'Numeração inutilizada na SEFAZ (nº {n}).',
            usuario=usuario,
        )
        nfs_afetadas.append(nf_locked.pk)

    NFeNumeracaoNumeroLiberado.objects.filter(
        configuracao=cfg,
        consumido_em__isnull=True,
        numero__gte=numero_inicial,
        numero__lte=numero_final,
    ).update(consumido_em=timezone.now())

    return nfs_afetadas


@transaction.atomic
def emitir_inutilizacao_numeracao(
    configuracao: NFeNumeracaoConfiguracao,
    *,
    numero_inicial: int,
    numero_final: int,
    justificativa: str,
    usuario=None,
    confirmacao_payload: dict | None = None,
    ano: int | None = None,
) -> dict[str, Any]:
    cfg = (
        NFeNumeracaoConfiguracao.objects.select_for_update()
        .select_related('empresa')
        .filter(pk=configuracao.pk)
        .first()
    )
    if cfg is None:
        raise NFeInutilizacaoError('Configuração de numeração não encontrada.')

    texto = validar_justificativa_inutilizacao(justificativa)
    ini = int(numero_inicial)
    fim = int(numero_final)

    pode, motivo, _ = pode_inutilizar_faixa_numeracao(cfg, numero_inicial=ini, numero_final=fim, usuario=usuario)
    if not pode:
        raise NFeInutilizacaoError(motivo)

    homolog = cfg.ambiente == NFeNumeracaoConfiguracao.Ambiente.HOMOLOGACAO
    if not homolog:
        try:
            _exigir_gates_producao(usuario, confirmacao_payload)
        except NFeProducaoDesabilitadaError as exc:
            raise NFeInutilizacaoError(str(exc), etapa='PERMISSAO') from exc
        except NFeProducaoConfirmacaoError as exc:
            raise NFeInutilizacaoError(str(exc), etapa='CONFIRMACAO') from exc
        except PermissionError as exc:
            raise NFeInutilizacaoError(str(exc), etapa='PERMISSAO') from exc

    empresa = cfg.empresa
    cnpj = _somente_digitos(empresa.cnpj or '')
    if len(cnpj) not in (11, 14):
        raise NFeInutilizacaoError('CNPJ/CPF do emitente inválido para inutilização.', etapa='EMITENTE')

    uf = (empresa.uf or 'SP').strip()
    if not uf:
        raise NFeInutilizacaoError('UF do emitente não cadastrada.', etapa='EMITENTE')

    try:
        cert = carregar_certificado_empresa(empresa)
    except CertificadoA1Error as exc:
        raise NFeInutilizacaoError(str(exc), etapa='CERTIFICADO') from exc

    senha = (empresa.senha_certificado or '').strip()
    if not senha:
        raise NFeInutilizacaoError('Senha do certificado não cadastrada.', etapa='CERTIFICADO')

    serie_transmissao = str(int(_serie_digits(cfg.serie))) if _serie_digits(cfg.serie).isdigit() else cfg.serie

    logger.info(
        'INUTILIZACAO_INICIO cfg_id=%s serie=%s faixa=%s-%s ambiente=%s',
        cfg.pk,
        cfg.serie,
        ini,
        fim,
        cfg.ambiente,
    )

    try:
        comunicacao = criar_comunicacao_sefaz(uf, cert.caminho, senha, homologacao=homolog)
        resposta_bruta = transmitir_inutilizacao_nfe(
            comunicacao,
            cnpj=cnpj,
            numero_inicial=ini,
            numero_final=fim,
            justificativa=texto,
            serie=serie_transmissao,
            ano=ano,
        )
        xml_retorno = extrair_xml_resposta(resposta_bruta)
        resultado = parse_inutilizacao_resposta(xml_retorno)
    except PyNFeComunicacaoError as exc:
        logger.warning('INUTILIZACAO_ERRO cfg_id=%s msg=%s', cfg.pk, exc)
        raise NFeInutilizacaoError(str(exc), etapa='COMUNICACAO_SEFAZ') from exc

    nfs_afetadas: list[int] = []
    if resultado.ok:
        nfs_afetadas = _aplicar_inutilizacao_local(
            cfg,
            numero_inicial=ini,
            numero_final=fim,
            justificativa=texto,
            resultado=resultado,
            usuario=usuario,
        )

    registro = NFeInutilizacaoSefaz.objects.create(
        configuracao=cfg,
        serie=cfg.serie,
        ambiente=cfg.ambiente,
        ano=resultado.ano or str(datetime.datetime.now().year)[-2:],
        numero_inicial=ini,
        numero_final=fim,
        justificativa=texto,
        protocolo=resultado.protocolo,
        cstat=resultado.c_stat,
        xmotivo=resultado.x_motivo,
        xml_retorno=resultado.xml_retorno,
        sefaz_ok=resultado.ok,
        criado_por=usuario if usuario and getattr(usuario, 'is_authenticated', False) else None,
    )

    logger.info(
        'INUTILIZACAO_FIM cfg_id=%s cStat=%s protocolo=%s ok=%s nfs=%s',
        cfg.pk,
        resultado.c_stat,
        resultado.protocolo,
        resultado.ok,
        len(nfs_afetadas),
    )

    return montar_resposta_inutilizacao(
        configuracao_id=cfg.pk,
        serie=cfg.serie,
        ambiente=cfg.ambiente,
        numero_inicial=ini,
        numero_final=fim,
        resultado=resultado,
        ok=resultado.ok,
        justificativa=texto,
        inutilizacao_id=registro.pk,
        nfs_afetadas=nfs_afetadas,
    )


@transaction.atomic
def emitir_inutilizacao_nfe_saida(
    nfe_saida: NFeSaida,
    *,
    justificativa: str,
    usuario=None,
    confirmacao_payload: dict | None = None,
) -> dict[str, Any]:
    nf = _lock_nfe_saida(nfe_saida.pk)
    pode, motivo, cfg = pode_inutilizar_numero_nfe(nf, usuario=usuario)
    if not pode or cfg is None:
        raise NFeInutilizacaoError(motivo)
    faixa = sugerir_faixa_inutilizacao_nfe(nf)
    n = faixa['numero_inicial']
    if n is None:
        raise NFeInutilizacaoError('Número fiscal inválido para inutilização.')
    return emitir_inutilizacao_numeracao(
        cfg,
        numero_inicial=n,
        numero_final=n,
        justificativa=justificativa,
        usuario=usuario,
        confirmacao_payload=confirmacao_payload,
    )
