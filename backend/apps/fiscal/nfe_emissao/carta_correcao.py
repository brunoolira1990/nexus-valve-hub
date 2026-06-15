"""Emissão de Carta de Correção Eletrônica (CC-e) — evento SEFAZ, sem alterar XML autorizado."""

from __future__ import annotations

import datetime
import logging
import re
from typing import Any

from django.db import transaction
from apps.fiscal.models import NFeSaida, NFeSaidaEvento
from apps.fiscal.nfe_emissao.carta_correcao_dados import proxima_sequencia_cce
from apps.fiscal.nfe_emissao.consulta_situacao import (
    _homologacao_da_nfe,
    pode_consultar_situacao_sefaz,
)
from apps.fiscal.nfe_emissao.empresa_emitente import resolver_empresa_emitente_nfe
from apps.fiscal.nfe_emissao.resposta_carta_correcao import montar_resposta_carta_correcao
from apps.fiscal.nfe_integracao.adapters.carta_correcao_parser import (
    parse_carta_correcao_resposta,
)
from apps.fiscal.nfe_integracao.adapters.certificado_a1 import carregar_certificado_empresa
from apps.fiscal.nfe_integracao.adapters.exceptions import CertificadoA1Error, PyNFeComunicacaoError
from apps.fiscal.nfe_integracao.adapters.pynfe_adapter import (
    criar_comunicacao_sefaz,
    extrair_xml_resposta,
    transmitir_evento_nfe,
)
from apps.fiscal.nfe_saida_efeitos import _lock_nfe_saida, _registrar_evento

logger = logging.getLogger(__name__)

TAMANHO_MINIMO_CORRECAO = 15
TAMANHO_MAXIMO_CORRECAO = 1000

MSG_CANCELADA = 'NF-e cancelada não permite Carta de Correção.'
MSG_SEM_CHAVE = 'NF-e sem chave de acesso para emissão de Carta de Correção.'
MSG_STATUS_INCOMPATIVEL = (
    'Carta de Correção disponível apenas para NF-e autorizada em homologação ou produção.'
)


class NFeCartaCorrecaoError(ValueError):
    def __init__(self, mensagem: str, *, etapa: str = 'VALIDACAO'):
        self.etapa = etapa
        super().__init__(mensagem)


def _somente_digitos(valor: str) -> str:
    return re.sub(r'\D', '', valor or '')


def validar_texto_correcao(texto: str | None) -> str:
    if texto is None:
        raise NFeCartaCorrecaoError('Texto da correção é obrigatório.')
    bruto = str(texto)
    limpo = bruto.strip()
    if not limpo:
        raise NFeCartaCorrecaoError('Texto da correção não pode ser vazio ou conter apenas espaços.')
    if len(limpo) < TAMANHO_MINIMO_CORRECAO:
        raise NFeCartaCorrecaoError(
            f'Texto da correção deve ter no mínimo {TAMANHO_MINIMO_CORRECAO} caracteres (regra fiscal).',
        )
    if len(limpo) > TAMANHO_MAXIMO_CORRECAO:
        raise NFeCartaCorrecaoError(
            f'Texto da correção deve ter no máximo {TAMANHO_MAXIMO_CORRECAO} caracteres (regra fiscal).',
        )
    return limpo


def pode_emitir_carta_correcao(nf: NFeSaida) -> tuple[bool, str]:
    st = (nf.status or '').strip().upper()
    if st in ('CANCELADA', 'CANCELADA_INTERNA', 'CANCELADO'):
        return False, MSG_CANCELADA

    chave = (nf.chave_acesso or '').strip()
    if len(chave) != 44:
        return False, MSG_SEM_CHAVE

    pode, motivo = pode_consultar_situacao_sefaz(nf)
    if not pode:
        return False, MSG_STATUS_INCOMPATIVEL if 'Consulta' in motivo else motivo
    return True, ''


def _montar_assinar_evento_cce(
    *,
    cnpj: str,
    chave: str,
    uf: str,
    sequencia: int,
    texto_correcao: str,
    cert_path: str,
    senha: str,
    homologacao: bool,
) -> Any:
    try:
        from pynfe.entidades.evento import EventoCartaCorrecao
        from pynfe.entidades.fonte_dados import _fonte_dados
        from pynfe.processamento.assinatura import AssinaturaA1
        from pynfe.processamento.serializacao import SerializacaoXML
    except ImportError as exc:
        raise PyNFeComunicacaoError(
            f'PyNFe indisponível ({exc}). Instale PyNFe e dependências de integração SEFAZ.',
        ) from exc

    carta = EventoCartaCorrecao(
        cnpj=cnpj,
        chave=chave,
        data_emissao=datetime.datetime.now(),
        uf=(uf or 'SP').strip().lower(),
        n_seq_evento=sequencia,
        correcao=texto_correcao,
    )
    serializador = SerializacaoXML(_fonte_dados, homologacao=homologacao)
    xml_evento = serializador.serializar_evento(carta)
    assinador = AssinaturaA1(cert_path, senha)
    return assinador.assinar(xml_evento)


@transaction.atomic
def emitir_carta_correcao_nfe_saida(
    nfe_saida: NFeSaida,
    *,
    texto_correcao: str,
    usuario=None,
) -> dict[str, Any]:
    nf = _lock_nfe_saida(nfe_saida.pk)
    texto = validar_texto_correcao(texto_correcao)

    pode, motivo = pode_emitir_carta_correcao(nf)
    if not pode:
        raise NFeCartaCorrecaoError(motivo)

    chave = (nf.chave_acesso or '').strip()
    empresa = resolver_empresa_emitente_nfe(nf)
    homolog = _homologacao_da_nfe(nf)
    ambiente_label = 'homologacao' if homolog else 'producao'
    sequencia = proxima_sequencia_cce(nf)

    cnpj = _somente_digitos(empresa.cnpj or '')
    if len(cnpj) not in (11, 14):
        raise NFeCartaCorrecaoError('CNPJ/CPF do emitente inválido para Carta de Correção.', etapa='EMITENTE')

    uf = (empresa.uf or 'SP').strip()
    if not uf:
        raise NFeCartaCorrecaoError('UF do emitente não cadastrada.', etapa='EMITENTE')

    try:
        cert = carregar_certificado_empresa(empresa)
    except CertificadoA1Error as exc:
        raise NFeCartaCorrecaoError(str(exc), etapa='CERTIFICADO') from exc

    senha = (empresa.senha_certificado or '').strip()
    if not senha:
        raise NFeCartaCorrecaoError('Senha do certificado não cadastrada.', etapa='CERTIFICADO')

    logger.info(
        'CARTA_CORRECAO_INICIO nfe_id=%s chave=%s ambiente=%s seq=%s',
        nf.pk,
        chave,
        ambiente_label,
        sequencia,
    )

    try:
        xml_assinado = _montar_assinar_evento_cce(
            cnpj=cnpj,
            chave=chave,
            uf=uf,
            sequencia=sequencia,
            texto_correcao=texto,
            cert_path=cert.caminho,
            senha=senha,
            homologacao=homolog,
        )
        comunicacao = criar_comunicacao_sefaz(uf, cert.caminho, senha, homologacao=homolog)
        resposta_bruta = transmitir_evento_nfe(comunicacao, xml_assinado, id_lote=nf.pk)
        xml_retorno = extrair_xml_resposta(resposta_bruta)
        resultado = parse_carta_correcao_resposta(xml_retorno)
    except PyNFeComunicacaoError as exc:
        logger.warning('CARTA_CORRECAO_ERRO nfe_id=%s msg=%s', nf.pk, exc)
        raise NFeCartaCorrecaoError(str(exc), etapa='COMUNICACAO_SEFAZ') from exc

    emitido_em = datetime.datetime.now().astimezone()
    evento = _registrar_evento(
        nf,
        tipo=NFeSaidaEvento.TipoEvento.CARTA_CORRECAO_EMITIDA,
        status_anterior=nf.status or '',
        status_novo=nf.status or '',
        resumo={
            'ambiente': ambiente_label,
            'chave_acesso': chave,
            'texto_correcao': texto,
            'cStat': resultado.c_stat,
            'xMotivo': resultado.x_motivo,
            'protocolo': resultado.protocolo,
            'sequencia_evento': sequencia,
            'n_seq_evento': resultado.n_seq_evento or str(sequencia),
            'tp_evento': resultado.tp_evento or '110110',
            'dh_reg_evento': resultado.dh_reg_evento,
            'emitido_em': emitido_em.isoformat(),
            'id_evento': resultado.id_evento,
        },
        observacao='Carta de Correção Eletrônica transmitida à SEFAZ (XML autorizado da NF-e não alterado).',
        usuario=usuario,
    )

    logger.info(
        'CARTA_CORRECAO_FIM nfe_id=%s cStat=%s protocolo=%s ok=%s',
        nf.pk,
        resultado.c_stat,
        resultado.protocolo,
        resultado.ok,
    )

    return montar_resposta_carta_correcao(
        nf,
        resultado,
        ok=resultado.ok,
        texto_correcao=texto,
        sequencia_evento=sequencia,
        evento_id=evento.pk,
    )
