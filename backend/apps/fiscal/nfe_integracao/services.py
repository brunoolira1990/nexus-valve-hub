"""Persistência e orquestração — integração SEFAZ NF-e 3.6 / 3.6.1."""

from __future__ import annotations

from typing import Any

from django.conf import settings

from apps.cadastros.models import Empresa
from apps.fiscal.models import NFeSefazStatusConsulta
from apps.fiscal.nfe_integracao.adapters.certificado_a1 import carregar_certificado_empresa
from apps.fiscal.nfe_integracao.adapters.sefaz_status_service import (
    ResultadoStatusServico,
    consultar_status_servico_empresa,
)


def _campo_texto(valor: str | None) -> str:
    return (valor or '').strip() if valor is not None else ''


def _motivo_exibicao(resultado: ResultadoStatusServico) -> str:
    if resultado.motivo:
        return _campo_texto(resultado.motivo)
    ret = resultado.retorno
    if ret and ret.x_motivo:
        return _campo_texto(ret.x_motivo)
    if resultado.erro_tecnico:
        return _campo_texto(resultado.erro_tecnico)
    if resultado.erro:
        return _campo_texto(resultado.erro)
    if not resultado.sucesso:
        return 'Falha sem retorno SEFAZ'
    return ''


def validar_certificado_empresa(empresa: Empresa) -> dict[str, Any]:
    info = carregar_certificado_empresa(empresa)
    return {
        'valido': info.valido,
        'titular': info.razao_social,
        'cnpj': info.cnpj,
        'cpf': info.cpf,
        'razao_social': info.razao_social,
        'validade_inicio': info.validade_inicio.isoformat() if info.validade_inicio else None,
        'validade_fim': info.validade_fim.isoformat() if info.validade_fim else None,
        'vencido': info.expirado,
        'dias_para_vencimento': info.expira_em_dias,
        'expirado': info.expirado,
        'expira_em_dias': info.expira_em_dias,
        'mensagens': info.mensagens,
        'erro': None if info.valido else '; '.join(info.mensagens) or 'Certificado inválido.',
    }


def executar_status_servico(
    empresa: Empresa,
    *,
    uf: str | None = None,
    homologacao: bool = True,
    usuario: Any = None,
) -> tuple[NFeSefazStatusConsulta, ResultadoStatusServico]:
    resultado = consultar_status_servico_empresa(
        empresa,
        uf=uf,
        homologacao=homologacao,
    )
    cert = resultado.certificado
    ret = resultado.retorno
    motivo = _motivo_exibicao(resultado)
    c_stat = _campo_texto(ret.c_stat if ret else '')
    if not c_stat and not resultado.sucesso and not motivo:
        motivo = 'Falha sem retorno SEFAZ'

    registro = NFeSefazStatusConsulta.objects.create(
        empresa=empresa,
        uf=resultado.uf,
        ambiente=resultado.ambiente,
        modelo=resultado.modelo,
        sucesso=resultado.sucesso,
        c_stat=c_stat,
        x_motivo=motivo,
        ver_aplic=_campo_texto(ret.ver_aplic if ret else ''),
        tp_amb=_campo_texto(ret.tp_amb if ret else ''),
        c_uf=_campo_texto(ret.c_uf if ret else ''),
        dh_recbto=_campo_texto(ret.dh_recbto if ret else ''),
        t_med=_campo_texto(ret.t_med if ret else ''),
        versao_retorno=_campo_texto(ret.versao if ret else ''),
        servico_operacional=ret.servico_operacional if ret else False,
        certificado_valido=bool(cert and cert.valido),
        certificado_cnpj=(cert.cnpj if cert else '') or '',
        certificado_validade_fim=cert.validade_fim if cert else None,
        xml_resposta=resultado.xml_resposta or resultado.raw_response or '',
        raw_response=resultado.raw_response or resultado.xml_resposta or '',
        erro_tecnico=_campo_texto(resultado.erro_tecnico or resultado.erro),
        tipo_erro=_campo_texto(resultado.tipo_erro),
        traceback_resumido=resultado.traceback_resumido if settings.DEBUG else '',
        mensagens=resultado.mensagens,
        consultado_por=usuario,
    )
    return registro, resultado


def resposta_api_consulta(
    registro: NFeSefazStatusConsulta,
    resultado: ResultadoStatusServico,
) -> dict[str, Any]:
    """Payload padronizado POST consultar (3.6.1)."""
    return {
        'ok': resultado.sucesso,
        'cstat': registro.c_stat,
        'c_stat': registro.c_stat,
        'motivo': registro.x_motivo,
        'x_motivo': registro.x_motivo,
        'ambiente': registro.ambiente,
        'uf': registro.uf,
        'tipo_erro': registro.tipo_erro,
        'erro_tecnico': registro.erro_tecnico,
        'xml_retorno': registro.xml_resposta,
        'xml_resposta': registro.xml_resposta,
        'raw_response': registro.raw_response,
        'servico_operacional': registro.servico_operacional,
        'id': registro.id,
        'consultado_em': registro.consultado_em.isoformat() if registro.consultado_em else None,
        'resultado': resultado.to_dict(),
    }
