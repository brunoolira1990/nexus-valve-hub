"""Consulta de Inscrição Estadual via SEFAZ NFeConsultaCadastro."""

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings

from apps.cadastros.consulta_cnpj import normalizar_cnpj_digitos
from apps.cadastros.models import Empresa
from apps.cadastros.utils import normalizar_cnpj, validar_cnpj
from apps.fiscal.nfe_integracao.adapters.certificado_a1 import carregar_certificado_empresa
from apps.fiscal.nfe_integracao.adapters.consulta_cadastro_parser import parse_consulta_cadastro_response
from apps.fiscal.nfe_integracao.adapters.exceptions import CertificadoA1Error, PyNFeComunicacaoError
from apps.fiscal.nfe_integracao.adapters.pynfe_adapter import (
    consulta_cadastro_contribuinte,
    criar_comunicacao_sefaz,
)
from apps.fiscal.nfe_integracao.prontidao_consulta_sefaz import validar_prontidao_consulta_sefaz

logger = logging.getLogger(__name__)

UFS_VALIDAS = frozenset(
    {
        'AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MT', 'MS', 'MG', 'PA',
        'PB', 'PR', 'PE', 'PI', 'RJ', 'RN', 'RS', 'RO', 'RR', 'SC', 'SP', 'SE', 'TO',
    },
)


class ConsultaIeError(Exception):
    def __init__(self, mensagem: str, codigo: str = 'ERRO_CONSULTA_IE') -> None:
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.codigo = codigo


def _resolver_empresa(empresa_id: int | None) -> Empresa:
    if empresa_id:
        try:
            return Empresa.objects.get(pk=empresa_id)
        except Empresa.DoesNotExist as exc:
            raise ConsultaIeError(
                'Empresa não encontrada para uso do certificado digital.',
                'EMPRESA_NAO_ENCONTRADA',
            ) from exc

    empresa = (
        Empresa.objects.filter(certificado_arquivo__isnull=False)
        .exclude(certificado_arquivo='')
        .exclude(senha_certificado='')
        .order_by('id')
        .first()
    )
    if not empresa:
        raise ConsultaIeError(
            'Certificado digital não configurado para consulta SEFAZ.',
            'CERTIFICADO_NAO_CONFIGURADO',
        )
    return empresa


def _ambiente_empresa(empresa: Empresa) -> tuple[str, bool]:
    ambiente = (getattr(empresa, 'nfe_ambiente', '') or 'homologacao').strip().lower()
    homologacao = ambiente != Empresa.NfeAmbiente.PRODUCAO
    return ('homologacao' if homologacao else 'producao', homologacao)


def _payload_erro(
    *,
    cnpj: str,
    uf: str,
    ambiente: str,
    mensagem: str,
    erro_codigo: str,
    erro_tecnico: str = '',
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        'sucesso': False,
        'cnpj': cnpj,
        'uf': uf,
        'inscricao_estadual': '',
        'inscricoes_estaduais': [],
        'situacao_ie': '',
        'razao_social': '',
        'municipio': '',
        'cnae': '',
        'fonte': 'SEFAZ_NFE_CONSULTA_CADASTRO',
        'ambiente': ambiente,
        'mensagem_usuario': mensagem,
        'erro_codigo': erro_codigo,
    }
    if settings.DEBUG and erro_tecnico:
        payload['erro_tecnico_resumido'] = erro_tecnico[:500]
    return payload


def consultar_inscricao_estadual(
    cnpj: str | None,
    uf: str | None,
    *,
    empresa_id: int | None = None,
) -> dict[str, Any]:
    """
    Consulta IE na SEFAZ (NFeConsultaCadastro) usando certificado A1 da empresa.
    Não persiste resultado — apenas retorna payload normalizado.
    """
    cnpj_canonico = normalizar_cnpj(cnpj)
    cnpj_digitos = normalizar_cnpj_digitos(cnpj)
    uf_norm = (uf or '').strip().upper()

    if not uf_norm:
        raise ConsultaIeError(
            'Informe a UF para consultar a Inscrição Estadual.',
            'UF_OBRIGATORIA',
        )
    if uf_norm not in UFS_VALIDAS:
        raise ConsultaIeError(
            'Consulta cadastral SEFAZ não configurada para esta UF.',
            'UF_NAO_SUPORTADA',
        )
    if len(cnpj_canonico) != 14:
        raise ConsultaIeError('CNPJ inválido. Informe 14 caracteres alfanuméricos.', 'CNPJ_INVALIDO')
    if not validar_cnpj(cnpj_canonico):
        raise ConsultaIeError('CNPJ inválido.', 'CNPJ_INVALIDO')
    if not cnpj_canonico.isdigit():
        raise ConsultaIeError(
            'A consulta de Inscrição Estadual via SEFAZ ainda aceita apenas CNPJ numérico.',
            'CNPJ_ALFANUMERICO_NAO_SUPORTADO',
        )

    empresa = _resolver_empresa(empresa_id)
    ambiente, homologacao = _ambiente_empresa(empresa)

    pode_consultar, motivo_bloqueio, _tipo = validar_prontidao_consulta_sefaz(empresa)
    if not pode_consultar:
        raise ConsultaIeError(
            motivo_bloqueio or 'Certificado digital não configurado para consulta SEFAZ.',
            'CERTIFICADO_NAO_CONFIGURADO',
        )

    try:
        cert_info = carregar_certificado_empresa(empresa)
    except CertificadoA1Error as exc:
        raise ConsultaIeError(
            'Certificado digital não configurado para consulta SEFAZ.',
            'CERTIFICADO_NAO_CONFIGURADO',
        ) from exc

    if not cert_info.valido:
        raise ConsultaIeError(
            'Certificado digital não configurado para consulta SEFAZ.',
            'CERTIFICADO_INVALIDO',
        )

    try:
        comunicacao = criar_comunicacao_sefaz(
            uf_norm,
            cert_info.caminho,
            (empresa.senha_certificado or '').strip(),
            homologacao=homologacao,
        )
        resposta = consulta_cadastro_contribuinte(
            comunicacao,
            cnpj_canonico,
            uf=uf_norm,
        )
    except PyNFeComunicacaoError as exc:
        msg = str(exc)
        codigo = 'SEFAZ_INDISPONIVEL'
        if 'não configurada' in msg.lower():
            codigo = 'UF_ENDPOINT_NAO_CONFIGURADO'
            msg_usuario = 'Consulta cadastral SEFAZ não configurada para esta UF.'
        else:
            msg_usuario = 'Consulta SEFAZ indisponível no momento.'
        return _payload_erro(
            cnpj=cnpj_canonico,
            uf=uf_norm,
            ambiente=ambiente,
            mensagem=msg_usuario,
            erro_codigo=codigo,
            erro_tecnico=msg,
        )

    parsed = parse_consulta_cadastro_response(resposta, cnpj=cnpj_canonico, uf=uf_norm)
    payload = parsed.to_dict()
    payload['ambiente'] = ambiente
    if not payload.get('mensagem_usuario'):
        payload['mensagem_usuario'] = (
            'Inscrição Estadual encontrada na SEFAZ.'
            if parsed.sucesso
            else 'Nenhuma Inscrição Estadual localizada para este CNPJ/UF.'
        )
    if settings.DEBUG and not parsed.sucesso and parsed.erro_codigo:
        payload['erro_tecnico_resumido'] = f'cStat={parsed.c_stat}; {parsed.x_motivo}'[:500]
    return payload
