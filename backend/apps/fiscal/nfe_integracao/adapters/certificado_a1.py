"""Validação e carga de certificado digital A1 (PFX/P12)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from cryptography import x509
from cryptography.hazmat.primitives.serialization import pkcs12

from apps.fiscal.nfe_integracao.adapters.exceptions import CertificadoA1Error


@dataclass
class CertificadoA1Info:
    valido: bool
    caminho: str
    senha_configurada: bool
    cnpj: str | None = None
    cpf: str | None = None
    razao_social: str | None = None
    validade_inicio: date | None = None
    validade_fim: date | None = None
    serial: str | None = None
    emissor: str | None = None
    mensagens: list[str] = field(default_factory=list)
    expirado: bool = False
    expira_em_dias: int | None = None


def _extrair_documento_subject(cert: x509.Certificate) -> tuple[str | None, str | None]:
    """Retorna (cnpj, cpf) extraídos do subject, se houver."""
    cnpj = None
    cpf = None
    for attr in cert.subject:
        oid_name = getattr(attr.oid, '_name', '') or str(attr.oid)
        if oid_name in ('commonName', 'CN', 'serialNumber'):
            val = str(attr.value)
            digits = ''.join(c for c in val if c.isdigit())
            if len(digits) >= 14 and not cnpj:
                cnpj = digits[:14]
            elif len(digits) == 11 and not cpf:
                cpf = digits
    return cnpj, cpf


def _extrair_cnpj_subject(cert: x509.Certificate) -> str | None:
    cnpj, _ = _extrair_documento_subject(cert)
    return cnpj


def _extrair_razao_subject(cert: x509.Certificate) -> str | None:
    for attr in cert.subject:
        oid_name = getattr(attr.oid, '_name', '') or str(attr.oid)
        if oid_name in ('commonName', 'CN'):
            return str(attr.value)
    return None


def _not_after_date(cert: x509.Certificate) -> date | None:
    na = getattr(cert, 'not_valid_after_utc', None) or getattr(cert, 'not_valid_after', None)
    if na is None:
        return None
    if isinstance(na, datetime):
        if na.tzinfo is None:
            na = na.replace(tzinfo=timezone.utc)
        return na.date()
    return na.date() if hasattr(na, 'date') else na


def _not_before_date(cert: x509.Certificate) -> date | None:
    nb = getattr(cert, 'not_valid_before_utc', None) or getattr(cert, 'not_valid_before', None)
    if nb is None:
        return None
    if isinstance(nb, datetime):
        if nb.tzinfo is None:
            nb = nb.replace(tzinfo=timezone.utc)
        return nb.date()
    return nb.date() if hasattr(nb, 'date') else nb


def validar_certificado_pfx(caminho: str | Path, senha: str) -> CertificadoA1Info:
    """Valida PFX/P12 e retorna metadados do certificado."""
    path = Path(caminho)
    msgs: list[str] = []
    if not path.is_file():
        raise CertificadoA1Error(f'Arquivo de certificado não encontrado: {path}')
    if not senha:
        raise CertificadoA1Error('Senha do certificado não informada.')

    try:
        p12_data = path.read_bytes()
        if not p12_data:
            raise CertificadoA1Error('Arquivo de certificado vazio.')
        _key, certificate, _extras = pkcs12.load_key_and_certificates(
            p12_data,
            senha.encode('utf-8'),
        )
    except CertificadoA1Error:
        raise
    except Exception as exc:
        msg = str(exc).lower()
        if 'password' in msg or 'mac verify' in msg or 'bad decrypt' in msg or 'invalid password' in msg:
            raise CertificadoA1Error(
                'Senha do certificado incorreta ou arquivo PFX inválido.',
            ) from exc
        raise CertificadoA1Error(f'Falha ao abrir certificado A1: {exc}') from exc

    if certificate is None:
        raise CertificadoA1Error('Nenhum certificado encontrado no arquivo PFX.')

    validade_fim = _not_after_date(certificate)
    validade_inicio = _not_before_date(certificate)
    hoje = date.today()
    expirado = bool(validade_fim and validade_fim < hoje)
    expira_em = (validade_fim - hoje).days if validade_fim else None

    if expirado:
        msgs.append(f'Certificado expirado em {validade_fim:%d/%m/%Y}.')
    elif expira_em is not None and expira_em <= 30:
        msgs.append(f'Certificado expira em {expira_em} dia(s).')
    else:
        msgs.append('Certificado A1 válido para uso.')

    issuer = certificate.issuer.rfc4514_string() if certificate.issuer else None
    cnpj, cpf = _extrair_documento_subject(certificate)
    return CertificadoA1Info(
        valido=not expirado,
        caminho=str(path.resolve()),
        senha_configurada=True,
        cnpj=cnpj,
        cpf=cpf,
        razao_social=_extrair_razao_subject(certificate),
        validade_inicio=validade_inicio,
        validade_fim=validade_fim,
        serial=format(certificate.serial_number) if certificate.serial_number else None,
        emissor=issuer,
        mensagens=msgs,
        expirado=expirado,
        expira_em_dias=expira_em,
    )


def carregar_certificado_empresa(empresa: Any) -> CertificadoA1Info:
    """Carrega certificado da empresa emitente (modelo cadastros.Empresa)."""
    arquivo = getattr(empresa, 'certificado_arquivo', None)
    senha = (getattr(empresa, 'senha_certificado', None) or '').strip()
    if not arquivo:
        raise CertificadoA1Error(
            f'Empresa «{getattr(empresa, "razao_social", empresa)}» não possui certificado A1 cadastrado.',
        )
    if not senha:
        raise CertificadoA1Error('Senha do certificado não cadastrada na empresa.')
    try:
        caminho = arquivo.path
    except Exception as exc:
        raise CertificadoA1Error('Arquivo de certificado indisponível no servidor.') from exc
    return validar_certificado_pfx(caminho, senha)
