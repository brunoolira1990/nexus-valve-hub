"""Numeração automática CQ-AAAAMMDD-NNNN (padrão comercial diário)."""

from __future__ import annotations

import re
from datetime import date

from django.utils import timezone

from apps.comercial.sequencia_diaria_numero import alocar_numero_diario, coerce_data_referencia
from apps.qualidade.models import SequenciaCertificadoQualidade

PREFIX = 'CQ'
_RE_CQ_AUTO = re.compile(r'^CQ-(\d{8})-(\d{4})$', re.I)


class NumeracaoCertificadoQualidadeError(ValueError):
    pass


def numero_certificado_qualidade_vazio(numero: str | None) -> bool:
    return not (numero or '').strip()


def is_numero_cq_automatico(numero: str | None) -> bool:
    return bool(_RE_CQ_AUTO.match((numero or '').strip()))


def gerar_numero_certificado_qualidade(data=None) -> str:
    """Reserva próximo número do dia com lock pessimista (atômico)."""
    data_ref = coerce_data_referencia(data or timezone.localdate())
    return alocar_numero_diario(
        modelo_sequencia=SequenciaCertificadoQualidade,
        filtros={'data_referencia': data_ref},
        prefix=PREFIX,
        data=data_ref,
    )


def extrair_sequencial_cq_automatico(numero: str) -> tuple[date, int] | None:
    raw = (numero or '').strip().upper()
    m = _RE_CQ_AUTO.match(raw)
    if not m:
        return None
    try:
        data_ref = date(int(m.group(1)[:4]), int(m.group(1)[4:6]), int(m.group(1)[6:8]))
    except ValueError:
        return None
    return data_ref, int(m.group(2))
