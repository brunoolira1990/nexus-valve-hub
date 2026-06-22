"""Emissão de evento de Cancelamento NF-e — SEFAZ, sem alterar XML autorizado."""

from __future__ import annotations

import datetime
import logging
import re
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.fiscal.models import NFeSaida, NFeSaidaEvento
from apps.fiscal.nfe_emissao.config_producao import (
    NFeProducaoConfirmacaoError,
    NFeProducaoDesabilitadaError,
    exigir_producao_habilitada,
)
from apps.fiscal.nfe_emissao.consulta_situacao import (
    _homologacao_da_nfe,
    pode_consultar_situacao_sefaz,
)
from apps.fiscal.nfe_emissao.empresa_emitente import resolver_empresa_emitente_nfe
from apps.fiscal.nfe_emissao.permissoes_producao import exigir_permissao_usuario_producao
from apps.fiscal.nfe_emissao.resposta_cancelamento import montar_resposta_cancelamento
from apps.fiscal.nfe_integracao.adapters.cancelamento_parser import (
    CSTAT_EVENTO_REGISTRADO,
    parse_cancelamento_resposta,
)
from apps.fiscal.nfe_integracao.adapters.certificado_a1 import carregar_certificado_empresa
from apps.fiscal.nfe_integracao.adapters.exceptions import CertificadoA1Error, PyNFeComunicacaoError
from apps.fiscal.nfe_integracao.adapters.pynfe_adapter import (
    criar_comunicacao_sefaz,
    extrair_xml_resposta,
    transmitir_evento_nfe,
)
from apps.fiscal.nfe_saida_bloqueio import nf_cancelada_operacional
from apps.fiscal.nfe_saida_efeitos import _lock_nfe_saida, _registrar_evento

logger = logging.getLogger(__name__)

TAMANHO_MINIMO_JUSTIFICATIVA = 15
TAMANHO_MAXIMO_JUSTIFICATIVA = 255
CONFIRMACAO_TEXTO_PRODUCAO = 'CANCELAR'

MSG_JA_CANCELADA = 'Esta NF-e já está cancelada.'
MSG_SEM_CHAVE = 'NF-e sem chave de acesso para cancelamento SEFAZ.'
MSG_SEM_PROTOCOLO = 'NF-e sem protocolo de autorização para cancelamento SEFAZ.'
MSG_SEM_XML = 'NF-e sem XML autorizado para cancelamento SEFAZ.'
MSG_AMBIENTE_INDEFINIDO = 'Ambiente de emissão da NF-e não está definido.'
MSG_STATUS_INCOMPATIVEL = (
    'Cancelamento disponível apenas para NF-e autorizada em homologação ou produção.'
)
MSG_CANCELAMENTO_JA_REGISTRADO = 'Cancelamento SEFAZ já registrado para esta NF-e.'
MSG_CONFIRMACAO_PRODUCAO = (
    'Confirmação obrigatória para cancelamento em produção: '
    'confirmar_cancelamento_producao=true e confirmar_texto="CANCELAR".'
)


class NFeCancelamentoError(ValueError):
    def __init__(self, mensagem: str, *, etapa: str = 'VALIDACAO'):
        self.etapa = etapa
        super().__init__(mensagem)


def _somente_digitos(valor: str) -> str:
    return re.sub(r'\D', '', valor or '')


def _xml_para_str(xml: Any) -> str:
    if xml is None:
        return ''
    if isinstance(xml, (bytes, bytearray)):
        return xml.decode('utf-8', errors='replace')
    return str(xml)


def validar_justificativa_cancelamento(texto: str | None) -> str:
    if texto is None:
        raise NFeCancelamentoError('Justificativa do cancelamento é obrigatória.')
    limpo = str(texto).strip()
    if not limpo:
        raise NFeCancelamentoError('Justificativa do cancelamento não pode ser vazia.')
    if len(limpo) < TAMANHO_MINIMO_JUSTIFICATIVA:
        raise NFeCancelamentoError(
            f'Justificativa deve ter no mínimo {TAMANHO_MINIMO_JUSTIFICATIVA} caracteres (regra SEFAZ).',
        )
    if len(limpo) > TAMANHO_MAXIMO_JUSTIFICATIVA:
        raise NFeCancelamentoError(
            f'Justificativa deve ter no máximo {TAMANHO_MAXIMO_JUSTIFICATIVA} caracteres.',
        )
    return limpo


def validar_confirmacao_cancelamento_producao(payload: dict | None) -> None:
    data = payload or {}
    if not data.get('confirmar_cancelamento_producao'):
        raise NFeCancelamentoError(MSG_CONFIRMACAO_PRODUCAO, etapa='CONFIRMACAO')
    texto = (data.get('confirmar_texto') or '').strip().upper()
    if texto != CONFIRMACAO_TEXTO_PRODUCAO:
        raise NFeCancelamentoError(MSG_CONFIRMACAO_PRODUCAO, etapa='CONFIRMACAO')


def cancelamento_sefaz_ja_registrado(nf: NFeSaida) -> bool:
    for ev in NFeSaidaEvento.objects.filter(
        nfe_saida=nf,
        tipo_evento=NFeSaidaEvento.TipoEvento.CANCELAMENTO_SEFAZ_EMITIDO,
    ):
        resumo = ev.resumo if isinstance(ev.resumo, dict) else {}
        cstat = str(resumo.get('cStat') or resumo.get('cstat') or '').strip()
        if cstat in CSTAT_EVENTO_REGISTRADO:
            return True
    return False


def _status_cancelado_pos_sefaz(nf: NFeSaida, homolog: bool) -> str:
    return 'CANCELADA_HOMOLOGACAO' if homolog else 'CANCELADA_PRODUCAO'


def pode_cancelar_nfe_sefaz(nf: NFeSaida, *, usuario=None) -> tuple[bool, str]:
    if nf_cancelada_operacional(nf):
        return False, MSG_JA_CANCELADA
    if cancelamento_sefaz_ja_registrado(nf):
        return False, MSG_CANCELAMENTO_JA_REGISTRADO

    chave = (nf.chave_acesso or '').strip()
    if len(chave) != 44:
        return False, MSG_SEM_CHAVE

    protocolo = (nf.protocolo_autorizacao or '').strip()
    if not protocolo:
        return False, MSG_SEM_PROTOCOLO

    if not (nf.xml_autorizado or '').strip():
        return False, MSG_SEM_XML

    amb = (nf.ambiente_emissao or '').strip().lower()
    if amb not in (NFeSaida.AmbienteEmissao.HOMOLOGACAO, NFeSaida.AmbienteEmissao.PRODUCAO):
        return False, MSG_AMBIENTE_INDEFINIDO

    pode, motivo = pode_consultar_situacao_sefaz(nf)
    if not pode:
        return False, MSG_STATUS_INCOMPATIVEL if 'Consulta' in motivo else motivo

    homolog = _homologacao_da_nfe(nf)
    if not homolog:
        try:
            exigir_producao_habilitada()
            exigir_permissao_usuario_producao(usuario)
        except NFeProducaoDesabilitadaError as exc:
            return False, str(exc)
        except PermissionError as exc:
            return False, str(exc)

    return True, ''


def _montar_assinar_evento_cancelamento(
    *,
    cnpj: str,
    chave: str,
    uf: str,
    protocolo: str,
    justificativa: str,
    cert_path: str,
    senha: str,
    homologacao: bool,
) -> Any:
    try:
        from pynfe.entidades.evento import EventoCancelarNota
        from pynfe.entidades.fonte_dados import _fonte_dados
        from pynfe.processamento.assinatura import AssinaturaA1
        from pynfe.processamento.serializacao import SerializacaoXML
    except ImportError as exc:
        raise PyNFeComunicacaoError(
            f'PyNFe indisponível ({exc}). Instale PyNFe e dependências de integração SEFAZ.',
        ) from exc

    evento = EventoCancelarNota(
        cnpj=cnpj,
        chave=chave,
        data_emissao=datetime.datetime.now(),
        uf=(uf or 'SP').strip().lower(),
        protocolo=protocolo,
        justificativa=justificativa,
    )
    serializador = SerializacaoXML(_fonte_dados, homologacao=homologacao)
    xml_evento = serializador.serializar_evento(evento)
    assinador = AssinaturaA1(cert_path, senha)
    return assinador.assinar(xml_evento)


def _aplicar_status_cancelado_sefaz(nf: NFeSaida, *, homolog: bool, justificativa: str, usuario) -> None:
    status_novo = _status_cancelado_pos_sefaz(nf, homolog)
    nf.status = status_novo
    nf.motivo_cancelamento = justificativa
    nf.cancelada_em = timezone.now()
    if usuario and getattr(usuario, 'is_authenticated', False):
        nf.cancelada_por = usuario
    nf.save(update_fields=['status', 'motivo_cancelamento', 'cancelada_em', 'cancelada_por'])


@transaction.atomic
def emitir_cancelamento_nfe_saida(
    nfe_saida: NFeSaida,
    *,
    justificativa: str,
    usuario=None,
    confirmacao_payload: dict | None = None,
) -> dict[str, Any]:
    nf = _lock_nfe_saida(nfe_saida.pk)
    texto = validar_justificativa_cancelamento(justificativa)

    pode, motivo = pode_cancelar_nfe_sefaz(nf, usuario=usuario)
    if not pode:
        raise NFeCancelamentoError(motivo)

    homolog = _homologacao_da_nfe(nf)
    if not homolog:
        try:
            exigir_producao_habilitada()
            exigir_permissao_usuario_producao(usuario)
            validar_confirmacao_cancelamento_producao(confirmacao_payload)
        except NFeProducaoDesabilitadaError as exc:
            raise NFeCancelamentoError(str(exc), etapa='PERMISSAO') from exc
        except NFeProducaoConfirmacaoError as exc:
            raise NFeCancelamentoError(str(exc), etapa='CONFIRMACAO') from exc
        except PermissionError as exc:
            raise NFeCancelamentoError(str(exc), etapa='PERMISSAO') from exc

    chave = (nf.chave_acesso or '').strip()
    protocolo = (nf.protocolo_autorizacao or '').strip()
    ambiente_label = 'homologacao' if homolog else 'producao'
    status_anterior = nf.status or ''

    empresa = resolver_empresa_emitente_nfe(nf)
    cnpj = _somente_digitos(empresa.cnpj or '')
    if len(cnpj) not in (11, 14):
        raise NFeCancelamentoError('CNPJ/CPF do emitente inválido para cancelamento.', etapa='EMITENTE')

    uf = (empresa.uf or 'SP').strip()
    if not uf:
        raise NFeCancelamentoError('UF do emitente não cadastrada.', etapa='EMITENTE')

    try:
        cert = carregar_certificado_empresa(empresa)
    except CertificadoA1Error as exc:
        raise NFeCancelamentoError(str(exc), etapa='CERTIFICADO') from exc

    senha = (empresa.senha_certificado or '').strip()
    if not senha:
        raise NFeCancelamentoError('Senha do certificado não cadastrada.', etapa='CERTIFICADO')

    logger.info(
        'CANCELAMENTO_INICIO nfe_id=%s chave=%s ambiente=%s',
        nf.pk,
        chave,
        ambiente_label,
    )

    try:
        xml_assinado = _montar_assinar_evento_cancelamento(
            cnpj=cnpj,
            chave=chave,
            uf=uf,
            protocolo=protocolo,
            justificativa=texto,
            cert_path=cert.caminho,
            senha=senha,
            homologacao=homolog,
        )
        xml_enviado = _xml_para_str(xml_assinado)
        comunicacao = criar_comunicacao_sefaz(uf, cert.caminho, senha, homologacao=homolog)
        resposta_bruta = transmitir_evento_nfe(comunicacao, xml_assinado, id_lote=nf.pk)
        xml_retorno = extrair_xml_resposta(resposta_bruta)
        resultado = parse_cancelamento_resposta(xml_retorno)
    except PyNFeComunicacaoError as exc:
        logger.warning('CANCELAMENTO_ERRO nfe_id=%s msg=%s', nf.pk, exc)
        raise NFeCancelamentoError(str(exc), etapa='COMUNICACAO_SEFAZ') from exc

    emitido_em = datetime.datetime.now().astimezone()
    status_novo = _status_cancelado_pos_sefaz(nf, homolog) if resultado.ok else status_anterior

    if resultado.ok:
        _aplicar_status_cancelado_sefaz(nf, homolog=homolog, justificativa=texto, usuario=usuario)
        from apps.fiscal.nfe_saida_pedido_cancelamento import aplicar_efeitos_comerciais_pos_cancelamento_sefaz

        try:
            aplicar_efeitos_comerciais_pos_cancelamento_sefaz(nf, usuario=usuario, motivo=texto)
        except ValueError as exc:
            logger.warning(
                'CANCELAMENTO_EFEITOS_COMERCIAIS nfe_id=%s err=%s',
                nf.pk,
                exc,
            )

    evento = _registrar_evento(
        nf,
        tipo=NFeSaidaEvento.TipoEvento.CANCELAMENTO_SEFAZ_EMITIDO,
        status_anterior=status_anterior,
        status_novo=status_novo,
        resumo={
            'ambiente': ambiente_label,
            'chave_acesso': chave,
            'justificativa': texto,
            'protocolo_autorizacao': protocolo,
            'cStat': resultado.c_stat,
            'xMotivo': resultado.x_motivo,
            'protocolo': resultado.protocolo,
            'protocolo_cancelamento': resultado.protocolo,
            'n_seq_evento': resultado.n_seq_evento or '1',
            'tp_evento': resultado.tp_evento or '110111',
            'dh_reg_evento': resultado.dh_reg_evento,
            'emitido_em': emitido_em.isoformat(),
            'id_evento': resultado.id_evento,
            'xml_enviado': xml_enviado,
            'xml_retorno': resultado.xml_retorno,
            'sefaz_ok': resultado.ok,
        },
        observacao='Evento de cancelamento transmitido à SEFAZ (XML autorizado da NF-e não alterado).',
        usuario=usuario,
    )

    logger.info(
        'CANCELAMENTO_FIM nfe_id=%s cStat=%s protocolo=%s ok=%s',
        nf.pk,
        resultado.c_stat,
        resultado.protocolo,
        resultado.ok,
    )

    return montar_resposta_cancelamento(
        nf,
        resultado,
        ok=resultado.ok,
        justificativa=texto,
        evento_id=evento.pk,
    )
