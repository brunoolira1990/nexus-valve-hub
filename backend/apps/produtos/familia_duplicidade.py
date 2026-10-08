"""Duplicidade de Família/Figura por descrição base + modelo de formação.

Regra de negócio (ERP 4.0.14.x):
- Bloqueia quando `descricao_base` (chave normalizada) e `tipo_regra_codigo`
  coincidem com outra família.
- Não cria constraint/migration nesta etapa.

Concorrência:
- A checagem antecipada em `validate()` sozinha NÃO serializa dois POST.
- Criação/atualização revalida sob `pg_advisory_xact_lock` dentro de
  `transaction.atomic()`, antes de `reservar_codigo_figura()` / INSERT.
- Assim a requisição perdedora recebe HTTP 400 sem reservar código (quando
  perde a disputa antes da reserva).

Advisory lock — cálculo de key1/key2 (determinístico entre processos):
- NÃO usa o builtin hash do Python (valor randomizado por processo).
- Usa `hashlib.sha256` sobre a string UTF-8:
  ``familia-dup|{tipo_regra}|{chave_descricao}``
  onde `chave_descricao` = `normalizar_descricao_produto(...)`.
- key1 = bytes[0:4] interpretados como int32 big-endian **signed**;
- key2 = bytes[4:8] interpretados como int32 big-endian **signed**;
- Faixa: [-2_147_483_648, 2_147_483_647] (int4 do PostgreSQL).
- O mesmo input gera as mesmas chaves após restart, em threads e em
  workers distintos.

Risco residual de colisão:
- Apenas 64 bits efetivos (dois int32). Em teoria, pares distintos podem
  colidir e serializar desnecessariamente (ou, em colisão + validação em
  falha, expor falso positivo só se a busca por descrição/modelo também
  coincidir — a rechecagem SQL/Python impede INSERT duplicado real).
- Probabilidade prática é desprezível com o volume de famílias; a
  proteção forte permanente continua sendo UNIQUE/index (migration futura
  após limpeza dos pares históricos).

Update (PATCH/PUT):
- Bloqueia o **par de destino** (nova descrição+modelo) antes da rechecagem.
- Se o par de origem diferir, também o bloqueia.
- Múltiplas chaves são adquiridas em ordem lexicográfica de (key1, key2)
  para evitar deadlock em atualizações cruzadas.

Normalização:
- Mesma função do persistido: `normalizar_descricao_produto`.

Diagnóstico (dev, sem exclusão automática):
- Podem existir pares históricos (ex.: 0114/9607; 6119/6119OD). Constraint
  UNIQUE exigiria limpeza + migration autorizada em tarefa separada.
"""

from __future__ import annotations

import hashlib
from typing import Any, Iterable

from django.db import connection, transaction
from rest_framework import serializers

from apps.produtos.descricao_norm import normalizar_descricao_produto
from apps.produtos.models import FamiliaProduto

MSG_DUPLICIDADE_DESCRICAO_MODELO = (
    'Já existe a Família/Figura {codigo} — {descricao} com o mesmo modelo de formação.'
)

# int4 signed — contrato de pg_advisory_xact_lock(int, int)
INT32_MIN = -(1 << 31)
INT32_MAX = (1 << 31) - 1

_ADVISORY_PREFIX = 'familia-dup|'


def chave_descricao_duplicidade_familia(texto: str | None) -> str:
    """Chave idêntica à normalização persistida no serializer."""
    return normalizar_descricao_produto(texto or '')


def mensagem_duplicidade_descricao_modelo(familia: FamiliaProduto) -> str:
    return MSG_DUPLICIDADE_DESCRICAO_MODELO.format(
        codigo=(familia.codigo_figura or '').strip(),
        descricao=(familia.descricao_base or '').strip(),
    )


def payload_erro_duplicidade_descricao_modelo(familia: FamiliaProduto) -> dict[str, Any]:
    """Erro estruturado amigável para o frontend."""
    msg = mensagem_duplicidade_descricao_modelo(familia)
    return {
        'descricao_base': [msg],
        'familia_existente_id': familia.id,
        'familia_existente_codigo': familia.codigo_figura,
        'familia_existente_descricao': familia.descricao_base,
        'familia_existente_tipo_regra_codigo': familia.tipo_regra_codigo,
    }


def _advisory_lock_keys_from_normalized(chave_desc: str, tipo_regra: str) -> tuple[int, int]:
    """
    Deriva (key1, key2) de forma estável entre processos.

    Implementação: SHA-256 via hashlib (nunca o builtin hash do Python).
    """
    material = f'{_ADVISORY_PREFIX}{tipo_regra}|{chave_desc}'.encode('utf-8')
    digest = hashlib.sha256(material).digest()
    k1 = int.from_bytes(digest[0:4], 'big', signed=True)
    k2 = int.from_bytes(digest[4:8], 'big', signed=True)
    if not (INT32_MIN <= k1 <= INT32_MAX and INT32_MIN <= k2 <= INT32_MAX):
        raise ValueError('Chaves advisory fora da faixa int32.')
    return k1, k2


def advisory_lock_keys_para_par(
    descricao_base: str | None,
    tipo_regra_codigo: str | None,
) -> tuple[int, int] | None:
    """Retorna (key1, key2) ou None se o par for incompleto."""
    chave = chave_descricao_duplicidade_familia(descricao_base)
    tipo = (tipo_regra_codigo or '').strip()
    if not chave or not tipo:
        return None
    return _advisory_lock_keys_from_normalized(chave, tipo)


def adquirir_locks_tx_duplicidade_familia_pares(
    pares: Iterable[tuple[str | None, str | None]],
) -> None:
    """
    Adquire `pg_advisory_xact_lock` para cada par distinto.

    Ordem determinística por (key1, key2) — evita deadlock em updates cruzados.
    Requer `transaction.atomic()`. No-op fora de PostgreSQL.
    """
    keys: set[tuple[int, int]] = set()
    for desc, tipo in pares:
        pair = advisory_lock_keys_para_par(desc, tipo)
        if pair is not None:
            keys.add(pair)
    if not keys:
        return
    if connection.vendor != 'postgresql':
        return
    with connection.cursor() as cursor:
        for k1, k2 in sorted(keys):
            cursor.execute('SELECT pg_advisory_xact_lock(%s, %s)', [k1, k2])


def adquirir_lock_tx_duplicidade_familia(
    *,
    descricao_base: str | None,
    tipo_regra_codigo: str | None,
) -> None:
    """Compat: bloqueia um único par (destino). Preferir a variante multi-par."""
    adquirir_locks_tx_duplicidade_familia_pares([(descricao_base, tipo_regra_codigo)])


def buscar_familia_duplicada_descricao_modelo(
    *,
    descricao_base: str | None,
    tipo_regra_codigo: str | None,
    excluir_id: int | None = None,
) -> FamiliaProduto | None:
    """
    Retorna a primeira família com a mesma chave de descrição e mesmo modelo.
    """
    chave = chave_descricao_duplicidade_familia(descricao_base)
    tipo = (tipo_regra_codigo or '').strip()
    if not chave or not tipo:
        return None

    qs = FamiliaProduto.objects.filter(tipo_regra_codigo=tipo).only(
        'id',
        'codigo_figura',
        'descricao_base',
        'tipo_regra_codigo',
    )
    if excluir_id is not None:
        qs = qs.exclude(pk=excluir_id)

    # Caminho rápido: valor já persistido na forma normalizada do cadastro.
    hit = qs.filter(descricao_base=chave).order_by('id').first()
    if hit is not None:
        return hit
    hit = qs.filter(descricao_base__iexact=chave).order_by('id').first()
    if hit is not None:
        return hit

    # Legado: espaços/caixa/acentos inconsistentes no banco.
    for fam in qs.order_by('id').iterator(chunk_size=200):
        if chave_descricao_duplicidade_familia(fam.descricao_base) == chave:
            return fam
    return None


def garantir_unicidade_descricao_modelo_na_tx(
    *,
    descricao_base: str | None,
    tipo_regra_codigo: str | None,
    excluir_id: int | None = None,
    descricao_origem: str | None = None,
    tipo_regra_origem: str | None = None,
) -> None:
    """
    Lock (destino [+ origem]) + recheck do destino.

    Chamar dentro de `transaction.atomic()` em create/update.
    No update, passar origem para ordenar locks e evitar deadlock cruzado.
    """
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError(
            'garantir_unicidade_descricao_modelo_na_tx exige transaction.atomic().',
        )
    pares: list[tuple[str | None, str | None]] = [(descricao_base, tipo_regra_codigo)]
    if descricao_origem is not None or tipo_regra_origem is not None:
        pares.append(
            (
                descricao_origem if descricao_origem is not None else descricao_base,
                tipo_regra_origem if tipo_regra_origem is not None else tipo_regra_codigo,
            ),
        )
    adquirir_locks_tx_duplicidade_familia_pares(pares)
    existente = buscar_familia_duplicada_descricao_modelo(
        descricao_base=descricao_base,
        tipo_regra_codigo=tipo_regra_codigo,
        excluir_id=excluir_id,
    )
    if existente is not None:
        raise serializers.ValidationError(payload_erro_duplicidade_descricao_modelo(existente))
