"""Serviço de consulta de status do webservice NF-e (SEFAZ)."""

from __future__ import annotations

import logging
import traceback
from dataclasses import dataclass, field
from typing import Any

from django.conf import settings
from django.utils import timezone

from apps.fiscal.nfe_integracao.adapters.certificado_a1 import (
    CertificadoA1Info,
    carregar_certificado_empresa,
)
from apps.fiscal.nfe_integracao.adapters.exceptions import (
    CertificadoA1Error,
    NFeIntegracaoError,
    PyNFeComunicacaoError,
)
from apps.fiscal.nfe_integracao.adapters.nfelib_adapter import RetornoStatusServicoParsed
from apps.fiscal.nfe_integracao.adapters.pynfe_adapter import (
    criar_comunicacao_sefaz,
    extrair_xml_resposta,
    resolver_url_status_servico,
    status_servico_nfe,
)
from apps.fiscal.nfe_integracao.adapters.status_servico_parser import (
    extrair_diagnostico_http_resposta,
    motivo_resposta_html_sefaz,
    parse_status_servico_response,
)
from apps.fiscal.nfe_integracao.adapters.tipos_erro import (
    TIPO_ERRO_CERTIFICADO,
    TIPO_ERRO_CONEXAO,
    TIPO_ERRO_EMPRESA_BLOQUEADA,
    TIPO_ERRO_GENERICO,
    TIPO_ERRO_PARSE,
    TIPO_ERRO_PYNFE,
    TIPO_ERRO_RESPOSTA_VAZIA,
    TIPO_ERRO_SEFAZ,
)
from apps.fiscal.nfe_integracao.prontidao_consulta_sefaz import (
    MSG_EMPRESA_TESTE,
    certificado_parece_fixture_teste,
    validar_prontidao_consulta_sefaz,
)

logger = logging.getLogger(__name__)


@dataclass
class ResultadoStatusServico:
    sucesso: bool
    uf: str
    ambiente: str
    modelo: str
    certificado: CertificadoA1Info | None = None
    retorno: RetornoStatusServicoParsed | None = None
    xml_resposta: str = ''
    raw_response: str = ''
    erro: str | None = None
    erro_tecnico: str = ''
    tipo_erro: str = ''
    motivo: str = ''
    mensagens: list[str] = field(default_factory=list)
    consultado_em: str | None = None
    traceback_resumido: str = ''
    endpoint_sefaz: str = ''
    diagnostico_http: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        cert = self.certificado
        ret = self.retorno
        return {
            'ok': self.sucesso,
            'sucesso': self.sucesso,
            'uf': self.uf,
            'ambiente': self.ambiente,
            'modelo': self.modelo,
            'erro': self.erro,
            'erro_tecnico': self.erro_tecnico or self.erro or '',
            'tipo_erro': self.tipo_erro,
            'motivo': self.motivo,
            'cstat': (ret.c_stat if ret else '') or '',
            'c_stat': (ret.c_stat if ret else '') or '',
            'mensagens': self.mensagens,
            'consultado_em': self.consultado_em,
            'xml_resposta': self.xml_resposta,
            'xml_retorno': self.xml_resposta,
            'raw_response': self.raw_response,
            'traceback_resumido': self.traceback_resumido,
            'endpoint_sefaz': self.endpoint_sefaz,
            'diagnostico_http': dict(self.diagnostico_http),
            'certificado': None
            if not cert
            else {
                'valido': cert.valido,
                'titular': cert.razao_social,
                'cnpj': cert.cnpj,
                'cpf': cert.cpf,
                'razao_social': cert.razao_social,
                'validade_inicio': cert.validade_inicio.isoformat() if cert.validade_inicio else None,
                'validade_fim': cert.validade_fim.isoformat() if cert.validade_fim else None,
                'expirado': cert.expirado,
                'expira_em_dias': cert.expira_em_dias,
                'mensagens': cert.mensagens,
            },
            'retorno': None
            if not ret
            else {
                'tp_amb': ret.tp_amb,
                'ver_aplic': ret.ver_aplic,
                'c_stat': ret.c_stat,
                'x_motivo': ret.x_motivo,
                'c_uf': ret.c_uf,
                'dh_recbto': ret.dh_recbto,
                't_med': ret.t_med,
                'versao': ret.versao,
                'servico_operacional': ret.servico_operacional,
            },
        }


def _traceback_debug(exc: BaseException) -> str:
    if not settings.DEBUG:
        return ''
    return traceback.format_exc(limit=8)


def _parsed_from_dict(parsed_dict: dict[str, Any]) -> RetornoStatusServicoParsed:
    return RetornoStatusServicoParsed(
        tp_amb=parsed_dict.get('tp_amb') or None,
        ver_aplic=parsed_dict.get('ver_aplic') or None,
        c_stat=parsed_dict.get('c_stat') or None,
        x_motivo=parsed_dict.get('x_motivo') or None,
        c_uf=parsed_dict.get('c_uf') or None,
        dh_recbto=parsed_dict.get('dh_recbto') or None,
        t_med=parsed_dict.get('t_med') or None,
        versao=parsed_dict.get('versao') or None,
        servico_operacional=bool(parsed_dict.get('servico_operacional')),
    )


def _falha(
    *,
    uf: str,
    ambiente: str,
    modelo: str,
    certificado: CertificadoA1Info | None,
    motivo: str,
    erro_tecnico: str,
    tipo_erro: str,
    agora: str,
    xml_resposta: str = '',
    raw_response: str = '',
    retorno: RetornoStatusServicoParsed | None = None,
    mensagens_extra: list[str] | None = None,
    traceback_resumido: str = '',
    endpoint_sefaz: str = '',
    diagnostico_http: dict[str, str] | None = None,
) -> ResultadoStatusServico:
    msgs = list(certificado.mensagens) if certificado else []
    if mensagens_extra:
        msgs.extend(mensagens_extra)
    if motivo and motivo not in msgs:
        msgs.append(motivo)
    return ResultadoStatusServico(
        sucesso=False,
        uf=uf,
        ambiente=ambiente,
        modelo=modelo,
        certificado=certificado,
        retorno=retorno,
        xml_resposta=xml_resposta,
        raw_response=raw_response or xml_resposta,
        erro=motivo,
        erro_tecnico=erro_tecnico or motivo,
        tipo_erro=tipo_erro,
        motivo=motivo,
        mensagens=msgs,
        consultado_em=agora,
        traceback_resumido=traceback_resumido,
        endpoint_sefaz=endpoint_sefaz,
        diagnostico_http=dict(diagnostico_http or {}),
    )


def consultar_status_servico_empresa(
    empresa: Any,
    *,
    uf: str | None = None,
    homologacao: bool = True,
    modelo: str = 'nfe',
    timeout: int = 30,
) -> ResultadoStatusServico:
    """
    Valida certificado A1 da empresa e consulta status do serviço NF-e na SEFAZ via PyNFe.
    """
    uf_uso = (uf or getattr(empresa, 'uf', None) or 'SP').strip().upper()
    ambiente = 'homologacao' if homologacao else 'producao'
    agora = timezone.localtime(timezone.now()).isoformat()
    empresa_nome = (getattr(empresa, 'razao_social', '') or '').strip()

    pode_consultar, motivo_bloqueio, tipo_bloqueio = validar_prontidao_consulta_sefaz(empresa)
    if not pode_consultar:
        return _falha(
            uf=uf_uso,
            ambiente=ambiente,
            modelo=modelo,
            certificado=None,
            motivo=motivo_bloqueio,
            erro_tecnico=motivo_bloqueio,
            tipo_erro=tipo_bloqueio or TIPO_ERRO_EMPRESA_BLOQUEADA,
            agora=agora,
        )

    try:
        cert_info = carregar_certificado_empresa(empresa)
    except CertificadoA1Error as exc:
        motivo = str(exc)
        return _falha(
            uf=uf_uso,
            ambiente=ambiente,
            modelo=modelo,
            certificado=None,
            motivo=motivo,
            erro_tecnico=motivo,
            tipo_erro=TIPO_ERRO_CERTIFICADO,
            agora=agora,
        )

    if certificado_parece_fixture_teste(cert_info.razao_social):
        return _falha(
            uf=uf_uso,
            ambiente=ambiente,
            modelo=modelo,
            certificado=cert_info,
            motivo=MSG_EMPRESA_TESTE,
            erro_tecnico=MSG_EMPRESA_TESTE,
            tipo_erro=TIPO_ERRO_EMPRESA_BLOQUEADA,
            agora=agora,
            mensagens_extra=list(cert_info.mensagens),
        )

    if not cert_info.valido:
        motivo = 'Certificado A1 inválido ou expirado.'
        return _falha(
            uf=uf_uso,
            ambiente=ambiente,
            modelo=modelo,
            certificado=cert_info,
            motivo=motivo,
            erro_tecnico='; '.join(cert_info.mensagens) or motivo,
            tipo_erro=TIPO_ERRO_CERTIFICADO,
            agora=agora,
            mensagens_extra=list(cert_info.mensagens),
        )

    endpoint_sefaz = ''
    try:
        comunicacao = criar_comunicacao_sefaz(
            uf_uso,
            cert_info.caminho,
            (getattr(empresa, 'senha_certificado', '') or '').strip(),
            homologacao=homologacao,
        )
        endpoint_sefaz = resolver_url_status_servico(comunicacao, modelo=modelo)
        if logger.isEnabledFor(logging.INFO):
            logger.info(
                'SEFAZ status_servico uf=%s ambiente=%s endpoint=%s',
                uf_uso,
                ambiente,
                endpoint_sefaz,
            )
        resposta_bruta = status_servico_nfe(comunicacao, modelo=modelo, timeout=timeout)
        parsed_dict = parse_status_servico_response(resposta_bruta)
        xml_text = parsed_dict.get('xml_raw') or extrair_xml_resposta(resposta_bruta)
    except PyNFeComunicacaoError as exc:
        tb = _traceback_debug(exc)
        motivo = 'Erro ao consultar status do serviço SEFAZ.'
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug('PyNFeComunicacaoError: %s', exc, exc_info=True)
        tipo = TIPO_ERRO_CONEXAO if 'conectar' in str(exc).lower() or 'timeout' in str(exc).lower() else TIPO_ERRO_PYNFE
        return _falha(
            uf=uf_uso,
            ambiente=ambiente,
            modelo=modelo,
            certificado=cert_info,
            motivo=motivo,
            erro_tecnico=str(exc),
            tipo_erro=tipo,
            agora=agora,
            mensagens_extra=list(cert_info.mensagens),
            traceback_resumido=tb,
        )
    except NFeIntegracaoError as exc:
        return _falha(
            uf=uf_uso,
            ambiente=ambiente,
            modelo=modelo,
            certificado=cert_info,
            motivo='Erro de parsing XML.',
            erro_tecnico=str(exc),
            tipo_erro=TIPO_ERRO_PARSE,
            agora=agora,
            mensagens_extra=list(cert_info.mensagens),
            traceback_resumido=_traceback_debug(exc),
        )
    except Exception as exc:
        tb = _traceback_debug(exc)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug('status_servico exceção: %s', exc, exc_info=True)
        return _falha(
            uf=uf_uso,
            ambiente=ambiente,
            modelo=modelo,
            certificado=cert_info,
            motivo='Erro ao consultar status do serviço SEFAZ.',
            erro_tecnico=str(exc),
            tipo_erro=TIPO_ERRO_GENERICO,
            agora=agora,
            mensagens_extra=list(cert_info.mensagens),
            traceback_resumido=tb,
        )

    parsed = _parsed_from_dict(parsed_dict)
    raw_norm = parsed_dict.get('xml_raw') or xml_text
    diag_http = extrair_diagnostico_http_resposta(resposta_bruta)

    if parsed_dict.get('erro_parse'):
        motivo = parsed_dict.get('motivo_erro') or 'Resposta SEFAZ sem cStat/xMotivo.'
        if parsed_dict.get('resposta_html'):
            motivo = motivo_resposta_html_sefaz(
                uf=uf_uso,
                ambiente=ambiente,
                empresa=empresa_nome,
                endpoint=endpoint_sefaz,
                diagnostico_http=diag_http,
            )
        tipo = TIPO_ERRO_RESPOSTA_VAZIA if 'vazia' in motivo.lower() else TIPO_ERRO_PARSE
        ret = parsed if parsed.c_stat or parsed.x_motivo else None
        return _falha(
            uf=uf_uso,
            ambiente=ambiente,
            modelo=modelo,
            certificado=cert_info,
            motivo=motivo,
            erro_tecnico=motivo,
            tipo_erro=tipo,
            agora=agora,
            xml_resposta=xml_text,
            raw_response=raw_norm,
            retorno=ret,
            mensagens_extra=list(cert_info.mensagens),
            endpoint_sefaz=endpoint_sefaz,
            diagnostico_http=diag_http,
        )

    msgs = list(cert_info.mensagens)
    c_stat = parsed.c_stat or ''
    x_motivo = parsed.x_motivo or ''
    if parsed.servico_operacional:
        msgs.append(f'SEFAZ {uf_uso} ({ambiente}): serviço em operação — cStat {c_stat}.')
        motivo = x_motivo or 'Serviço em operação.'
    else:
        msgs.append(f'SEFAZ {uf_uso} ({ambiente}): retorno cStat={c_stat} — {x_motivo or "sem motivo"}.')
        motivo = x_motivo or f'Retorno SEFAZ cStat={c_stat}.'

    return ResultadoStatusServico(
        sucesso=parsed.servico_operacional,
        uf=uf_uso,
        ambiente=ambiente,
        modelo=modelo,
        certificado=cert_info,
        retorno=parsed,
        xml_resposta=xml_text,
        raw_response=raw_norm,
        erro='' if parsed.servico_operacional else motivo,
        erro_tecnico='' if parsed.servico_operacional else '',
        tipo_erro='' if parsed.servico_operacional else TIPO_ERRO_SEFAZ if c_stat else TIPO_ERRO_PARSE,
        motivo=motivo,
        mensagens=msgs,
        consultado_em=agora,
        endpoint_sefaz=endpoint_sefaz,
        diagnostico_http=diag_http,
    )
