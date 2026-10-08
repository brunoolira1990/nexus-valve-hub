"""Geração automática de codigo_figura para FamiliaProduto (padrão NNNN)."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Literal

from django.conf import settings
from django.db import IntegrityError, transaction

from apps.core.app_contexto import resolver_ambiente_app

# Padrão das novas famílias automáticas: exatamente 4 dígitos (0052, 6118, 0199).
CODIGO_FIGURA_VALIDO_RE = re.compile(r'^\d{4}$')
_RE_PREFIXO_NUMERICO = re.compile(r'^(\d{4})')

MAX_CODIGO_FIGURA_AUTO = 9999
ENV_POLITICA = 'FAMILIA_CODIGO_POLITICA_PREFIXO'
MSG_FAIXA_ESGOTADA = (
    'A faixa automática de códigos de família foi esgotada. '
    'Revise a política de numeração antes de cadastrar uma nova família.'
)
MSG_POLITICA_OBRIGATORIA_PRODUCAO = (
    'Em produção, defina explicitamente FAMILIA_CODIGO_POLITICA_PREFIXO='
    'PREFIXO_GLOBAL_UNICIDADE (decisão do operador). '
    'Valores aceitos: VALOR_COMPLETO, PREFIXO_GLOBAL_UNICIDADE ou PREFIXO_GLOBAL_SEQUENCIAL.'
)


class PoliticaPrefixoCodigoFigura:
    """
    Políticas de ocupação do prefixo numérico — escolha explícita em produção.

    Decisão de produção (ERP 4.0.14.x, operador): PREFIXO_GLOBAL_UNICIDADE.
    — Sufixo no codigo_figura é válido quando o template não o acrescenta (ex.: 0023OD).
    — Templates OD_MM_ESPESSURA / OD_POLEGADA_ESPESSURA acrescentam OD no produto (ex.: 6119).
    — MANUAL_FABRICANTE não participa da ocupação de prefixo NNNN.

    PREFIXO_GLOBAL_UNICIDADE:
        Sufixos ocupam o número-base (6119OD bloqueia 6119); geração automática
        escolhe o menor NNNN livre a partir de 0001 (lacunas). Contador persistido
        serve de mutex/marca d'água — não define o ponto de partida.
        Política de produção.

    PREFIXO_GLOBAL_SEQUENCIAL:
        Maior prefixo numérico define piso da sequência (9000OD => próximo >= 9001).
        Não usar em produção neste ERP (não criar migration 0028).

    VALOR_COMPLETO:
        Unicidade pelo valor completo; 6119 e 6119OD podem coexistir.
        Também preenche lacunas a partir de 0001 (fallback de desenvolvimento).
        Não usar em produção neste ERP.    """

    VALOR_COMPLETO = 'VALOR_COMPLETO'
    PREFIXO_GLOBAL_UNICIDADE = 'PREFIXO_GLOBAL_UNICIDADE'
    PREFIXO_GLOBAL_SEQUENCIAL = 'PREFIXO_GLOBAL_SEQUENCIAL'

    TODAS = frozenset(
        {
            VALOR_COMPLETO,
            PREFIXO_GLOBAL_UNICIDADE,
            PREFIXO_GLOBAL_SEQUENCIAL,
        },
    )


class FamiliaCodigoEsgotadoError(Exception):
    """Faixa 0001–9999 esgotada para geração automática."""


class FamiliaCodigoConfigError(Exception):
    """Configuração inválida ou ausente para geração automática em produção."""


@dataclass(frozen=True)
class ConfigPoliticaCodigoFigura:
    politica: str
    origem: Literal['explicita', 'fallback', 'invalida_fallback']
    ambiente_app: str
    alerta_fallback: str | None = None
    bloqueio_producao: str | None = None

    @property
    def usa_fallback(self) -> bool:
        return self.origem != 'explicita'


def _valor_env_politica() -> str:
    return (os.environ.get(ENV_POLITICA) or '').strip()


def resolver_config_politica_codigo_figura() -> ConfigPoliticaCodigoFigura:
    """Resolve política ativa, origem e bloqueios de produção (sem expor outras env vars)."""
    raw = _valor_env_politica()
    ambiente = resolver_ambiente_app()
    em_producao = ambiente == 'producao'

    if raw in PoliticaPrefixoCodigoFigura.TODAS:
        return ConfigPoliticaCodigoFigura(
            politica=raw,
            origem='explicita',
            ambiente_app=ambiente,
        )

    if raw:
        politica = PoliticaPrefixoCodigoFigura.VALOR_COMPLETO
        cfg = ConfigPoliticaCodigoFigura(
            politica=politica,
            origem='invalida_fallback',
            ambiente_app=ambiente,
            alerta_fallback=(
                f'Valor inválido em {ENV_POLITICA}; usando fallback {politica} até correção.'
            ),
        )
    else:
        politica = PoliticaPrefixoCodigoFigura.VALOR_COMPLETO
        cfg = ConfigPoliticaCodigoFigura(
            politica=politica,
            origem='fallback',
            ambiente_app=ambiente,
            alerta_fallback=(
                f'{ENV_POLITICA} não definida; usando fallback {politica} (permitido em dev/homolog).'
            ),
        )

    if em_producao:
        return ConfigPoliticaCodigoFigura(
            politica=cfg.politica,
            origem=cfg.origem,
            ambiente_app=ambiente,
            alerta_fallback=cfg.alerta_fallback,
            bloqueio_producao=MSG_POLITICA_OBRIGATORIA_PRODUCAO,
        )
    return cfg


def exigir_configuracao_producao_familia_codigo() -> ConfigPoliticaCodigoFigura:
    cfg = resolver_config_politica_codigo_figura()
    if cfg.bloqueio_producao:
        raise FamiliaCodigoConfigError(cfg.bloqueio_producao)
    return cfg


def obter_politica_prefixo_codigo_figura() -> str:
    return resolver_config_politica_codigo_figura().politica


def codigo_figura_valido(codigo: str | None) -> bool:
    return bool(CODIGO_FIGURA_VALIDO_RE.match((codigo or '').strip()))


def formatar_codigo_figura(numero: int) -> str:
    n = int(numero)
    if n < 0 or n > MAX_CODIGO_FIGURA_AUTO:
        raise ValueError(f'Código fora da faixa automática: {n}')
    return f'{n:04d}'


def extrair_prefixo_numerico(codigo: str | None) -> int | None:
    m = _RE_PREFIXO_NUMERICO.match((codigo or '').strip())
    return int(m.group(1)) if m else None


# Templates que intercalam "OD" no codigo_figura ao montar o código do produto
# (via _prefixo_od em codigo_produto.montar_codigo_interno).
REGRAS_TEMPLATE_ACRESCENTAM_OD = frozenset(
    {
        'BASE_OD_MM_ESPESSURA',
        'BASE_OD_POLEGADA_ESPESSURA',
    },
)


def template_acrescenta_od(tipo_regra_codigo: str | None) -> bool:
    """True se o template dimensional acrescenta OD ao código-base da família."""
    return (tipo_regra_codigo or '').strip() in REGRAS_TEMPLATE_ACRESCENTAM_OD


def codigo_figura_termina_com_od(codigo: str | None) -> bool:
    return (codigo or '').strip().upper().endswith('OD')


def familia_participa_prefixo_figura(tipo_regra_codigo: str | None) -> bool:
    """
    MANUAL_FABRICANTE não participa da numeração de figura NNNN.
    Ex.: 18900001-04DC não deve ocupar o prefixo 1890 para geração automática.
    """
    from apps.produtos.models import FamiliaProduto

    return (tipo_regra_codigo or '').strip() != FamiliaProduto.TipoRegraCodigo.MANUAL_FABRICANTE


def prefixos_numericos_ocupados() -> set[int]:
    """Prefixos de famílias de figura (ativas e inativas; exclui MANUAL_FABRICANTE)."""
    from apps.produtos.models import FamiliaProduto

    out: set[int] = set()
    qs = FamiliaProduto.objects.exclude(
        tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.MANUAL_FABRICANTE,
    ).values_list('codigo_figura', flat=True)
    for cod in qs:
        p = extrair_prefixo_numerico(cod)
        if p is not None:
            out.add(p)
    return out


def prefixos_produtos_ocupados() -> set[int]:
    """
    Prefixos NNNN presentes no início de Produto.codigo_completo.

    Ex.: ``00750D13`` → 75; ``0202.050025`` → 202.
    Códigos sem quatro dígitos iniciais são ignorados.
    """
    from apps.produtos.models import Produto

    out: set[int] = set()
    qs = (
        Produto.objects.exclude(codigo_completo__isnull=True)
        .exclude(codigo_completo='')
        .values_list('codigo_completo', flat=True)
        .iterator(chunk_size=2000)
    )
    for cod in qs:
        p = extrair_prefixo_numerico(cod)
        if p is not None:
            out.add(p)
    return out


def prefixos_globalmente_ocupados() -> set[int]:
    """União família (ativa/inativa) + prefixos de produto — base da busca do menor livre."""
    return prefixos_numericos_ocupados() | prefixos_produtos_ocupados()


def codigos_nnnn_ocupados() -> set[str]:
    from apps.produtos.models import FamiliaProduto

    return {
        (c or '').strip()
        for c in FamiliaProduto.objects.exclude(
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.MANUAL_FABRICANTE,
        ).values_list('codigo_figura', flat=True)
        if codigo_figura_valido(c)
    }


def codigos_especiais_com_prefixo() -> list[str]:
    """NNNN+sufixo de famílias de figura (exclui MANUAL_FABRICANTE)."""
    from apps.produtos.models import FamiliaProduto

    return sorted(
        (c or '').strip()
        for c in FamiliaProduto.objects.exclude(
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.MANUAL_FABRICANTE,
        ).values_list('codigo_figura', flat=True)
        if (c or '').strip()
        and not codigo_figura_valido(c)
        and extrair_prefixo_numerico(c) is not None
    )


def classificar_codigo_figura_contextual(
    *,
    codigo: str,
    tipo_regra_codigo: str,
) -> str:
    """
    Classificação contextual (auditoria / orientação).

    Retornos:
    - NNNN
    - MANUAL_FABRICANTE
    - TECNICO_SUFIXO_VALIDO (sufixo no código; template não acrescenta o mesmo)
    - POSSIVEL_REPETICAO_TEMPLATE (ex.: ...OD com regra que acrescenta OD)
    - OUTRO
    """
    from apps.produtos.models import FamiliaProduto

    c = (codigo or '').strip()
    regra = (tipo_regra_codigo or '').strip()
    if regra == FamiliaProduto.TipoRegraCodigo.MANUAL_FABRICANTE:
        return 'MANUAL_FABRICANTE'
    if codigo_figura_valido(c):
        return 'NNNN'
    if extrair_prefixo_numerico(c) is not None and not codigo_figura_valido(c):
        if codigo_figura_termina_com_od(c) and template_acrescenta_od(regra):
            return 'POSSIVEL_REPETICAO_TEMPLATE'
        return 'TECNICO_SUFIXO_VALIDO'
    return 'OUTRO'


def maior_codigo_figura_valido_existente() -> int:
    nnnn = codigos_nnnn_ocupados()
    return max((int(c) for c in nnnn), default=0)


def maior_prefixo_numerico_existente() -> int:
    return max(prefixos_numericos_ocupados(), default=0)


def _politica_usa_prefixo_global(politica: str) -> bool:
    return politica in (
        PoliticaPrefixoCodigoFigura.PREFIXO_GLOBAL_UNICIDADE,
        PoliticaPrefixoCodigoFigura.PREFIXO_GLOBAL_SEQUENCIAL,
    )


def _politica_preenche_lacunas(politica: str) -> bool:
    """
    PREFIXO_GLOBAL_UNICIDADE (produção) e VALOR_COMPLETO (fallback):
    escolhem o menor NNNN livre a partir de 0001.
    PREFIXO_GLOBAL_SEQUENCIAL permanece monotônico (maior prefixo + 1).
    """
    return politica in (
        PoliticaPrefixoCodigoFigura.PREFIXO_GLOBAL_UNICIDADE,
        PoliticaPrefixoCodigoFigura.VALOR_COMPLETO,
    )


def candidato_ocupado(
    n: int,
    *,
    politica: str,
    prefixos: set[int],
    nnnn: set[str],
) -> bool:
    """n ocupado por família e/ou prefixo de produto (já unidos em ``prefixos`` quando aplicável)."""
    if n < 1 or n > MAX_CODIGO_FIGURA_AUTO:
        return True
    if _politica_usa_prefixo_global(politica):
        return n in prefixos
    # VALOR_COMPLETO: NNNN puro da família OU prefixo de produto bloqueia o número.
    return formatar_codigo_figura(n) in nnnn or n in prefixos


def piso_contador_para_politica(politica: str) -> int:
    """Piso mínimo da busca (sem ler contador persistido)."""
    if politica == PoliticaPrefixoCodigoFigura.PREFIXO_GLOBAL_SEQUENCIAL:
        return maior_prefixo_numerico_existente() + 1
    if _politica_preenche_lacunas(politica):
        return 1
    return maior_codigo_figura_valido_existente() + 1


def proximo_candidato_livre_a_partir_de(inicio: int, *, politica: str) -> int | None:
    if _politica_usa_prefixo_global(politica) or _politica_preenche_lacunas(politica):
        prefixos = prefixos_globalmente_ocupados()
    else:
        prefixos = prefixos_numericos_ocupados()
    nnnn = codigos_nnnn_ocupados()
    n = max(1, int(inicio))
    while n <= MAX_CODIGO_FIGURA_AUTO:
        if not candidato_ocupado(n, politica=politica, prefixos=prefixos, nnnn=nnnn):
            return n
        n += 1
    return None


def calcular_proximo_numero_inicial(*, politica: str) -> int:
    base = piso_contador_para_politica(politica)
    livre = proximo_candidato_livre_a_partir_de(base, politica=politica)
    if livre is None:
        return MAX_CODIGO_FIGURA_AUTO + 1
    return livre


def recalibrar_proximo_numero_sequencial(*, contador_atual: int, politica: str) -> int:
    """
    Para PREFIXO_GLOBAL_SEQUENCIAL: max(contador_atual, maior_prefixo + 1).
    Nunca reduz o contador.
    """
    if politica != PoliticaPrefixoCodigoFigura.PREFIXO_GLOBAL_SEQUENCIAL:
        return int(contador_atual)
    piso = maior_prefixo_numerico_existente() + 1
    return max(int(contador_atual), piso)


def _obter_ou_criar_sequencia_locked():
    """
    Mutex de geração automática via SELECT FOR UPDATE na linha pk=1.

    Papel da sequência após lacunas:
    - Serializa reservas concorrentes (não é SEQUENCE do PostgreSQL).
    - ``proximo_numero`` vira marca d'água / último N+1 reservado (auditoria);
      em políticas de lacuna a busca sempre recomeça em 0001.
    """
    from apps.produtos.models import FamiliaProdutoCodigoSequencia

    politica = obter_politica_prefixo_codigo_figura()
    seq = (
        FamiliaProdutoCodigoSequencia.objects.select_for_update()
        .filter(pk=1)
        .first()
    )
    if seq is not None:
        novo = recalibrar_proximo_numero_sequencial(contador_atual=seq.proximo_numero, politica=politica)
        if novo != seq.proximo_numero:
            seq.proximo_numero = novo
            seq.save(update_fields=['proximo_numero'])
        return seq
    inicial = calcular_proximo_numero_inicial(politica=politica)
    try:
        FamiliaProdutoCodigoSequencia.objects.create(pk=1, proximo_numero=inicial)
    except IntegrityError:
        pass
    seq = FamiliaProdutoCodigoSequencia.objects.select_for_update().get(pk=1)
    novo = recalibrar_proximo_numero_sequencial(contador_atual=seq.proximo_numero, politica=politica)
    if novo != seq.proximo_numero:
        seq.proximo_numero = novo
        seq.save(update_fields=['proximo_numero'])
    return seq


@transaction.atomic
def reservar_codigo_figura() -> str:
    """
    Reserva o próximo codigo_figura automático (NNNN).

    PREFIXO_GLOBAL_UNICIDADE / VALOR_COMPLETO: menor livre a partir de 0001
    (família ativa/inativa + prefixo de produto). 0000 nunca é usado.

    PREFIXO_GLOBAL_SEQUENCIAL: monotônico a partir do maior prefixo / contador.
    """
    exigir_configuracao_producao_familia_codigo()
    seq = _obter_ou_criar_sequencia_locked()
    politica = obter_politica_prefixo_codigo_figura()
    prefixos = prefixos_globalmente_ocupados()
    nnnn = codigos_nnnn_ocupados()

    if _politica_preenche_lacunas(politica):
        n = 1
    else:
        n = int(seq.proximo_numero)
        if politica == PoliticaPrefixoCodigoFigura.PREFIXO_GLOBAL_SEQUENCIAL:
            n = max(n, maior_prefixo_numerico_existente() + 1)
        if n > MAX_CODIGO_FIGURA_AUTO:
            raise FamiliaCodigoEsgotadoError(MSG_FAIXA_ESGOTADA)

    tentativas = 0
    limite_tentativas = MAX_CODIGO_FIGURA_AUTO - n + 2
    while n <= MAX_CODIGO_FIGURA_AUTO and tentativas < limite_tentativas:
        tentativas += 1
        if not candidato_ocupado(n, politica=politica, prefixos=prefixos, nnnn=nnnn):
            codigo = formatar_codigo_figura(n)
            # Marca d'água: nunca reduz; documenta último reservado+1.
            seq.proximo_numero = max(int(seq.proximo_numero), n + 1)
            seq.save(update_fields=['proximo_numero'])
            return codigo
        n += 1

    raise FamiliaCodigoEsgotadoError(MSG_FAIXA_ESGOTADA)
