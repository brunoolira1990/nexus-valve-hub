import re
import unicodedata
from datetime import date, timedelta

from rest_framework import serializers


_SPLIT_PATTERN = re.compile(r"[/,\-\s]+")


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return normalized.strip().lower()


def _is_indeterminate_payment(normalized: str) -> bool:
    """Condições em que não calculamos vencimentos nem quantidade de parcelas a partir de dias."""
    if not normalized:
        return False
    markers = (
        "a combinar",
        "a combinar.",
        "sob consulta",
        "apos aprovacao",
        "apos aprovacao do pedido",
        "apos pagamento",
        "apos pagamento do pedido",
        "a definir",
        "negociar",
        "conforme negocio",
        "conforme negociacao",
    )
    return any(m in normalized for m in markers)


def pagamento_integralmente_a_vista(dias_parcelas: list[int] | None) -> bool:
    """
    Plano canônico de pagamento integralmente à vista.

    Fonte: ArrayField `dias_parcelas` (inteiros), nunca texto livre.
    True somente quando há exatamente uma parcela com 0 dias: ``[0]``.

    Não classifica como à vista:
    - lista vazia / condição ausente (``[]``);
    - a prazo (ex.: ``[30]``, ``[30, 60]``);
    - misto entrada + prazo (ex.: ``[0, 30]``).

    Não define meio de pagamento fiscal (``tPag``) — apenas o prazo/plano.
    """
    days = list(dias_parcelas or [])
    return len(days) == 1 and int(days[0]) == 0


def parse_payment_condition(text: str) -> list[int]:
    raw = (text or "").strip()
    if raw == "":
        return []

    normalized = _normalize_text(raw)
    normalized = normalized.replace("ddl", " ")
    normalized = re.sub(r"\s+", " ", normalized).strip()

    if _is_indeterminate_payment(normalized):
        return []

    if normalized in {"a vista", "avista", "0"}:
        return [0]

    parts = [p for p in _SPLIT_PATTERN.split(normalized) if p]
    if not parts:
        raise serializers.ValidationError(
            "Condição inválida. Use formatos como '30 DDL', '30/45 DDL', '30/60/90' ou 'à vista'."
        )

    days: list[int] = []
    for part in parts:
        if not part.isdigit():
            raise serializers.ValidationError(
                "Condição inválida. Informe somente números e separadores (ex.: 30/45 DDL)."
            )
        n = int(part)
        if n < 0:
            raise serializers.ValidationError("Dias da condição de pagamento devem ser maiores ou iguais a zero.")
        days.append(n)

    if not days:
        raise serializers.ValidationError("Condição de pagamento vazia.")

    return days


def compute_due_dates(base_date: date, days: list[int]) -> list[date]:
    if base_date is None:
        return []
    return [base_date + timedelta(days=d) for d in days]
