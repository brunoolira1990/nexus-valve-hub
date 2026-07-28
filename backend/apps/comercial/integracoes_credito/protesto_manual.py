"""Registro manual auditável de protestos — sem HTTP externo e sem certificado A1."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.comercial.integracoes_credito.sanitizacao import limitar_texto, mascarar_cnpj, validar_resultado_normalizado
from apps.comercial.models import (
    AnaliseFinanceiraProposta,
    AnaliseFinanceiraPropostaEvento,
    ConsultaExternaAnaliseFinanceira,
)

PROVIDER = 'PESQUISA_PROTESTO'
PRODUTO = 'CONSULTA_MANUAL'
ORIGEM = 'PESQUISA_PROTESTO_MANUAL'
FONTE_EVENTO = 'PESQUISA_PROTESTO_MANUAL'

RESULTADO_SEM = 'SEM_PROTESTOS_INFORMADOS'
RESULTADO_COM = 'COM_PROTESTOS_INFORMADOS'
RESULTADO_INCONCLUSIVA = 'CONSULTA_INCONCLUSIVA'
RESULTADOS_VALIDOS = frozenset({RESULTADO_SEM, RESULTADO_COM, RESULTADO_INCONCLUSIVA})

AVISO_COBERTURA = (
    'Resultado registrado manualmente. A consulta abrange protestos em cartório '
    'e não representa todas as dívidas ou restrições financeiras.'
)

# Tolerância técnica: clock skew / fuso.
TOLERANCIA_FUTURO = timedelta(minutes=5)
# Sem confirmação adicional: rejeitar consultas absurdamente antigas.
MAX_IDADE_CONSULTA = timedelta(days=365 * 5)

MAX_OBS = 500
MAX_CARTORIOS = 500
MAX_MOTIVO = 500
MAX_UFS = 27


class ProtestoManualError(Exception):
    """Erro de validação/negócio do registro manual de protesto."""

    def __init__(self, code: str, detail: str, *, http_status: int = 400):
        self.code = code
        self.detail = detail
        self.http_status = http_status
        super().__init__(detail)

    def to_dict(self) -> dict[str, str]:
        return {'code': self.code, 'detail': self.detail}


def _nome_exibicao(user) -> str:
    if user is None:
        return ''
    return (user.get_full_name() or '').strip() or user.get_username()


def _parse_consultado_em(valor: Any) -> datetime:
    if valor is None or valor == '':
        return timezone.now()
    if isinstance(valor, datetime):
        dt = valor
    else:
        raw = str(valor).strip()
        dt = parse_datetime(raw)
        if dt is None:
            raise ProtestoManualError('CONSULTADO_EM_INVALIDO', 'consultado_em deve ser ISO-8601.')
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    agora = timezone.now()
    if dt > agora + TOLERANCIA_FUTURO:
        raise ProtestoManualError(
            'CONSULTADO_EM_FUTURO',
            'consultado_em não pode ser data futura além da tolerância técnica.',
        )
    if dt < agora - MAX_IDADE_CONSULTA:
        raise ProtestoManualError(
            'CONSULTADO_EM_ANTIGO',
            'consultado_em está absurdamente antigo. Informe uma data recente da consulta no portal.',
        )
    return dt


def _normalizar_ufs(valor: Any) -> list[str]:
    if valor is None or valor == '':
        return []
    if isinstance(valor, str):
        parts = [p.strip().upper() for p in valor.replace(';', ',').split(',') if p.strip()]
    elif isinstance(valor, (list, tuple)):
        parts = [str(p).strip().upper() for p in valor if str(p).strip()]
    else:
        raise ProtestoManualError('UFS_INVALIDAS', 'ufs_informadas deve ser lista ou texto.')
    if len(parts) > MAX_UFS:
        raise ProtestoManualError('UFS_INVALIDAS', 'Quantidade de UFs informadas excede o limite.')
    for uf in parts:
        if len(uf) != 2 or not uf.isalpha():
            raise ProtestoManualError('UFS_INVALIDAS', f'UF inválida: {uf}')
    # estáveis e sem duplicata preservando ordem
    vistos: set[str] = set()
    out: list[str] = []
    for uf in parts:
        if uf not in vistos:
            vistos.add(uf)
            out.append(uf)
    return out


def _validar_quantidade(resultado: str, quantidade: Any) -> int | None:
    if quantidade is None or quantidade == '':
        return None
    try:
        q = int(quantidade)
    except (TypeError, ValueError):
        raise ProtestoManualError('QUANTIDADE_INVALIDA', 'quantidade_informada deve ser inteiro.') from None
    if q < 0:
        raise ProtestoManualError('QUANTIDADE_INVALIDA', 'quantidade_informada não pode ser negativa.')
    if resultado == RESULTADO_COM and q == 0:
        raise ProtestoManualError(
            'QUANTIDADE_INVALIDA',
            'Com protestos informados, quantidade_informada (quando enviada) deve ser maior que zero.',
        )
    return q


def _cnpj_mascarado_da_analise(analise: AnaliseFinanceiraProposta) -> str:
    cliente = getattr(analise, 'cliente', None)
    cnpj = getattr(cliente, 'cnpj', None) if cliente is not None else None
    return mascarar_cnpj(cnpj)


def _resolver_registro_anterior(
    analise: AnaliseFinanceiraProposta,
    registro_anterior_id: Any,
) -> ConsultaExternaAnaliseFinanceira | None:
    if registro_anterior_id is None or registro_anterior_id == '':
        return None
    try:
        ant_id = int(registro_anterior_id)
    except (TypeError, ValueError):
        raise ProtestoManualError('REGISTRO_ANTERIOR_INVALIDO', 'registro_anterior_id inválido.') from None
    try:
        anterior = ConsultaExternaAnaliseFinanceira.objects.get(pk=ant_id)
    except ConsultaExternaAnaliseFinanceira.DoesNotExist as exc:
        raise ProtestoManualError('REGISTRO_ANTERIOR_NAO_ENCONTRADO', 'Registro anterior não encontrado.') from exc
    if anterior.analise_financeira_id != analise.pk:
        raise ProtestoManualError(
            'REGISTRO_ANTERIOR_OUTRA_ANALISE',
            'Correção só pode referenciar registro da mesma análise.',
        )
    if anterior.tipo != ConsultaExternaAnaliseFinanceira.Tipo.PROTESTO_MANUAL:
        raise ProtestoManualError(
            'REGISTRO_ANTERIOR_TIPO_INVALIDO',
            'Correção só pode referenciar registro PROTESTO_MANUAL.',
        )
    return anterior


def montar_resultado_normalizado(
    *,
    resultado: str,
    quantidade_informada: int | None,
    ufs_informadas: list[str],
    cartorios_informados: str | None,
    observacao: str | None,
    consultado_em: datetime,
    registrado_em: datetime,
    usuario,
    corrige_registro_id: int | None,
    motivo_correcao: str | None,
) -> dict[str, Any]:
    payload = {
        'origem': ORIGEM,
        'registro_manual': True,
        'resultado': resultado,
        'quantidade_informada': quantidade_informada,
        'ufs_informadas': ufs_informadas,
        'cartorios_informados': cartorios_informados,
        'observacao': observacao,
        'consultado_em': consultado_em.isoformat(),
        'registrado_em': registrado_em.isoformat(),
        'registrado_por': {
            'id': str(getattr(usuario, 'pk', '') or ''),
            'nome_exibicao': _nome_exibicao(usuario),
        },
        'corrige_registro_id': corrige_registro_id,
        'motivo_correcao': motivo_correcao,
        'aviso': AVISO_COBERTURA,
    }
    return validar_resultado_normalizado(payload)


def validar_payload_protesto_manual(data: dict[str, Any] | None) -> dict[str, Any]:
    raw = dict(data or {})
    resultado = str(raw.get('resultado') or '').strip().upper()
    if resultado not in RESULTADOS_VALIDOS:
        raise ProtestoManualError(
            'RESULTADO_INVALIDO',
            'resultado deve ser SEM_PROTESTOS_INFORMADOS, COM_PROTESTOS_INFORMADOS ou CONSULTA_INCONCLUSIVA.',
        )

    observacao = limitar_texto(raw.get('observacao'), max_len=MAX_OBS) or None
    if resultado == RESULTADO_INCONCLUSIVA and not observacao:
        raise ProtestoManualError(
            'OBSERVACAO_OBRIGATORIA',
            'Consulta inconclusiva exige observação explicando o motivo.',
        )

    quantidade = _validar_quantidade(resultado, raw.get('quantidade_informada'))
    ufs = _normalizar_ufs(raw.get('ufs_informadas'))
    cartorios = limitar_texto(raw.get('cartorios_informados'), max_len=MAX_CARTORIOS) or None
    consultado_em = _parse_consultado_em(raw.get('consultado_em'))

    registro_anterior_id = raw.get('registro_anterior_id')
    motivo_correcao = limitar_texto(raw.get('motivo_correcao'), max_len=MAX_MOTIVO) or None
    if registro_anterior_id not in (None, '') and not motivo_correcao:
        raise ProtestoManualError(
            'MOTIVO_CORRECAO_OBRIGATORIO',
            'Correção exige motivo_correcao.',
        )

    return {
        'resultado': resultado,
        'quantidade_informada': quantidade,
        'ufs_informadas': ufs,
        'cartorios_informados': cartorios,
        'observacao': observacao,
        'consultado_em': consultado_em,
        'registro_anterior_id': registro_anterior_id,
        'motivo_correcao': motivo_correcao,
    }


@transaction.atomic
def registrar_protesto_manual(
    *,
    analise: AnaliseFinanceiraProposta,
    usuario,
    payload: dict[str, Any] | None,
) -> ConsultaExternaAnaliseFinanceira:
    """Cria registro append-only + evento na mesma transação. Sem HTTP externo."""
    validado = validar_payload_protesto_manual(payload)
    anterior = _resolver_registro_anterior(analise, validado['registro_anterior_id'])
    if anterior is not None and anterior.pk is not None:
        # autorreferência: só possível se alguém enviar o próprio id ainda inexistente — rejeitar id igual
        # após create não se aplica; validação pós-create não necessária. Se id igual a algo já
        # existente, a nova linha terá outro pk.
        pass

    agora = timezone.now()
    resultado_norm = montar_resultado_normalizado(
        resultado=validado['resultado'],
        quantidade_informada=validado['quantidade_informada'],
        ufs_informadas=validado['ufs_informadas'],
        cartorios_informados=validado['cartorios_informados'],
        observacao=validado['observacao'],
        consultado_em=validado['consultado_em'],
        registrado_em=agora,
        usuario=usuario,
        corrige_registro_id=anterior.pk if anterior else None,
        motivo_correcao=validado['motivo_correcao'] if anterior else None,
    )

    registro = ConsultaExternaAnaliseFinanceira.objects.create(
        analise_financeira=analise,
        tipo=ConsultaExternaAnaliseFinanceira.Tipo.PROTESTO_MANUAL,
        provider=PROVIDER,
        produto=PRODUTO,
        status=ConsultaExternaAnaliseFinanceira.Status.CONCLUIDA,
        solicitada_por=usuario if getattr(usuario, 'is_authenticated', False) else None,
        concluida_em=agora,
        cnpj_mascarado=_cnpj_mascarado_da_analise(analise),
        resultado_normalizado=resultado_norm,
        erro_sanitizado='',
        protocolo_mascarado='',
        custo_consulta=None,
        registro_anterior=anterior,
    )

    # Defesa: não permitir autorreferência (impossível no create normal).
    if registro.registro_anterior_id == registro.pk:
        raise ProtestoManualError('REGISTRO_ANTERIOR_INVALIDO', 'Autorreferência não permitida.')

    evento_dados = {
        'registro_id': registro.pk,
        'resultado': validado['resultado'],
        'fonte': FONTE_EVENTO,
        'consultado_em': validado['consultado_em'].isoformat(),
        'indica_correcao': bool(anterior),
    }
    if anterior:
        evento_dados['registro_anterior_id'] = anterior.pk

    AnaliseFinanceiraPropostaEvento.objects.create(
        analise=analise,
        tipo=AnaliseFinanceiraPropostaEvento.Tipo.PROTESTO_MANUAL_REGISTRADO,
        ator=usuario if getattr(usuario, 'is_authenticated', False) else None,
        dados=evento_dados,
    )
    return registro


def listar_protestos_manuais(analise: AnaliseFinanceiraProposta):
    return (
        ConsultaExternaAnaliseFinanceira.objects.filter(
            analise_financeira=analise,
            tipo=ConsultaExternaAnaliseFinanceira.Tipo.PROTESTO_MANUAL,
        )
        .select_related('solicitada_por', 'registro_anterior')
        .order_by('-solicitada_em', '-id')
    )
