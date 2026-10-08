"""Fachada neutra A1 — delega ao carregador PKCS#12 fiscal sem acoplar emissão."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from cryptography.hazmat.primitives.serialization import pkcs12

from apps.certificados.contratos import (
    FinalidadeCertificado,
    MaterialCriptograficoA1,
    MetadadosCertificadoSeguros,
)
from apps.certificados.exceptions import (
    CODE_ARQUIVO_INDISPONIVEL,
    CODE_EXPIRADO,
    CODE_FINALIDADE_NAO_SUPORTADA,
    CODE_INVALIDO,
    CODE_NAO_CONFIGURADO,
    CODE_SENHA_INVALIDA,
    MSG_ARQUIVO_INDISPONIVEL,
    MSG_EXPIRADO,
    MSG_FINALIDADE,
    MSG_INVALIDO,
    MSG_NAO_CONFIGURADO,
    MSG_SENHA_INVALIDA,
    CertificadoDigitalError,
)
from apps.certificados.metadados import metadados_de_info_fiscal

# Dependência mínima: apenas o adaptador PKCS#12 existente (sem nfe_emissao/SEFAZ).
from apps.fiscal.nfe_integracao.adapters.certificado_a1 import carregar_certificado_empresa
from apps.fiscal.nfe_integracao.adapters.exceptions import CertificadoA1Error


FINALIDADES_SUPORTADAS = frozenset(FinalidadeCertificado)


def _resolver_finalidade(finalidade: FinalidadeCertificado | str) -> FinalidadeCertificado:
    if isinstance(finalidade, FinalidadeCertificado):
        return finalidade
    try:
        return FinalidadeCertificado(str(finalidade))
    except ValueError as exc:
        raise CertificadoDigitalError(CODE_FINALIDADE_NAO_SUPORTADA, MSG_FINALIDADE) from exc


def _mapear_erro_fiscal(exc: CertificadoA1Error) -> CertificadoDigitalError:
    # Classificar pelo texto original; a mensagem pública é sempre constante sanitizada.
    low = str(exc).lower()
    if 'não possui certificado' in low or 'nao possui certificado' in low:
        return CertificadoDigitalError(CODE_NAO_CONFIGURADO, MSG_NAO_CONFIGURADO)
    if 'senha do certificado não' in low or 'senha do certificado nao' in low:
        return CertificadoDigitalError(CODE_NAO_CONFIGURADO, MSG_NAO_CONFIGURADO)
    if 'senha' in low and (
        'incorreta' in low or 'inválido' in low or 'invalido' in low or 'password' in low
    ):
        return CertificadoDigitalError(CODE_SENHA_INVALIDA, MSG_SENHA_INVALIDA)
    if 'indisponível' in low or 'indisponivel' in low or 'não encontrado' in low or 'nao encontrado' in low:
        return CertificadoDigitalError(CODE_ARQUIVO_INDISPONIVEL, MSG_ARQUIVO_INDISPONIVEL)
    if 'expirad' in low:
        return CertificadoDigitalError(CODE_EXPIRADO, MSG_EXPIRADO)
    return CertificadoDigitalError(CODE_INVALIDO, MSG_INVALIDO)


def _ler_bytes_pfx(empresa: Any) -> tuple[bytes, str]:
    arquivo = getattr(empresa, 'certificado_arquivo', None)
    senha = (getattr(empresa, 'senha_certificado', None) or '').strip()
    if not arquivo:
        raise CertificadoDigitalError(CODE_NAO_CONFIGURADO, MSG_NAO_CONFIGURADO)
    if not senha:
        raise CertificadoDigitalError(CODE_NAO_CONFIGURADO, MSG_NAO_CONFIGURADO)
    try:
        # Preferir leitura via storage Django (bytes) — sem expor path ao caller.
        if hasattr(arquivo, 'open'):
            with arquivo.open('rb') as fh:
                data = fh.read()
        else:
            data = arquivo.read()
            if hasattr(arquivo, 'seek'):
                arquivo.seek(0)
    except Exception as exc:
        raise CertificadoDigitalError(CODE_ARQUIVO_INDISPONIVEL, MSG_ARQUIVO_INDISPONIVEL) from exc
    if not data:
        raise CertificadoDigitalError(CODE_ARQUIVO_INDISPONIVEL, MSG_ARQUIVO_INDISPONIVEL)
    return data, senha


class CertificadoDigitalA1Facade:
    """
    Provider neutro de acesso ao A1.

    Não emite NF-e, não chama SEFAZ e não consulta CENPROT.
    """

    def validar_disponibilidade(
        self, empresa: Any, finalidade: FinalidadeCertificado | str
    ) -> MetadadosCertificadoSeguros:
        fin = _resolver_finalidade(finalidade)
        try:
            info = carregar_certificado_empresa(empresa)
        except CertificadoA1Error as exc:
            raise _mapear_erro_fiscal(exc) from exc
        meta = metadados_de_info_fiscal(info, finalidade=fin)
        if not meta.valido:
            code = CODE_EXPIRADO if info.expirado else CODE_INVALIDO
            detail = MSG_EXPIRADO if info.expirado else MSG_INVALIDO
            raise CertificadoDigitalError(code, detail)
        return meta

    def obter_metadados_seguros(
        self, empresa: Any, finalidade: FinalidadeCertificado | str
    ) -> MetadadosCertificadoSeguros:
        fin = _resolver_finalidade(finalidade)
        try:
            info = carregar_certificado_empresa(empresa)
        except CertificadoA1Error as exc:
            err = _mapear_erro_fiscal(exc)
            return MetadadosCertificadoSeguros(
                disponivel=False,
                valido=False,
                tipo='A1',
                finalidade=fin.value,
                vence_em=None,
                dias_para_expirar=None,
                motivo_indisponibilidade=err.detail,
            )
        return metadados_de_info_fiscal(info, finalidade=fin)

    def carregar_material_criptografico(
        self, empresa: Any, finalidade: FinalidadeCertificado | str
    ) -> MaterialCriptograficoA1:
        fin = _resolver_finalidade(finalidade)
        # Garante mesmas regras de validade da fachada (e mapeamento sanitizado).
        self.validar_disponibilidade(empresa, fin)
        data, senha = _ler_bytes_pfx(empresa)
        try:
            key, certificate, extras = pkcs12.load_key_and_certificates(
                data, senha.encode('utf-8')
            )
        except Exception as exc:
            msg = str(exc).lower()
            if 'password' in msg or 'mac verify' in msg or 'bad decrypt' in msg:
                raise CertificadoDigitalError(CODE_SENHA_INVALIDA, MSG_SENHA_INVALIDA) from exc
            raise CertificadoDigitalError(CODE_INVALIDO, MSG_INVALIDO) from exc
        if certificate is None or key is None:
            raise CertificadoDigitalError(CODE_INVALIDO, MSG_INVALIDO)
        cadeia = tuple(extras or ())
        return MaterialCriptograficoA1(
            certificado=certificate,
            chave_privada=key,
            cadeia=cadeia,
            finalidade=fin,
            carregado_em=datetime.now(timezone.utc),
        )

    def liberar_material(self, contexto: MaterialCriptograficoA1 | None) -> None:
        if contexto is not None:
            contexto.liberar()
