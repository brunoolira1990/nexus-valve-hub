"""Endpoints de API da Contingência SEFAZ (NF-e).

Adiciona ações na NFeSaidaViewSet:
- /contingencia/status (get)        — situação da contingência de uma empresa
- /contingencia/ativar (post)       — ativar modo de contingência (tpEmis 2/6/7)
- /contingencia/encerrar (post)     — encerrar a contingência ativa
- /contingencia/transmitir-pendentes (post) — transmitir NFs emitidas em contingência
- /emitir-contingencia (post, por NF) — emitir NF-e em contingência (EPEC)
"""

from rest_framework import response, status

from apps.fiscal.contingencia_sefaz import (
    TP_EMIS_PERMITIDOS_NFE,
    ContingenciaSefazError,
    encerrar_contingencia,
    emitir_em_contingencia,
    obter_contingencia_ativa,
    registrar_contingencia,
    transmitir_pendentes_contingencia,
)


def _empresa_contingencia(request):
    """Resolve a empresa alvo da ação de contingência (query param empresa_id)."""
    from apps.cadastros.models import Empresa

    empresa_id = request.query_params.get('empresa_id') or (
        request.data.get('empresa_id') if hasattr(request, 'data') else None
    )
    if not empresa_id:
        raise ContingenciaSefazError('Informe a empresa (parâmetro empresa_id).')
    try:
        empresa = Empresa.objects.get(pk=int(empresa_id))
    except (Empresa.DoesNotExist, ValueError, TypeError):
        raise ContingenciaSefazError('Empresa informada não existe.')
    return empresa


def _resumo_registro(registro, nfe_pendentes: int = 0) -> dict:
    return {
        'ativa': True,
        'empresa_id': registro.empresa_id,
        'tp_emis': registro.tp_emis,
        'tp_emis_label': TP_EMIS_PERMITIDOS_NFE.get(registro.tp_emis, registro.tp_emis),
        'motivo': registro.motivo,
        'inicio': registro.inicio.isoformat() if registro.inicio else None,
        'tempo_ativo_horas': None,
        'nfe_pendentes': nfe_pendentes,
    }


def _pendentes_contingencia(empresa) -> int:
    from apps.fiscal.models import NFeSaida

    return NFeSaida.objects.filter(
        empresa_emitente=empresa,
        tipo_emissao__in=('2', '6', '7'),
        status_emissao_sefaz__in=('xml_assinado', 'xml_gerado', 'enviada_homologacao', 'enviada_producao'),
    ).count()


def status_contingencia(viewset, request, pk=None):
    """GET /nfe-saida/contingencia/status/"""
    try:
        from apps.fiscal import contingencia_sefaz as _cf

        empresa = _empresa_contingencia(request)
    except ContingenciaSefazError as exc:
        return response.Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    registro = _cf.obter_contingencia_ativa(empresa)
    if registro:
        payload = _resumo_registro(registro, _pendentes_contingencia(empresa))
    else:
        payload = {
            'ativa': False,
            'empresa_id': empresa.pk,
            'tp_emis': '1',
            'tp_emis_label': 'Emissão normal',
            'motivo': '',
            'inicio': None,
            'tempo_ativo_horas': None,
            'nfe_pendentes': 0,
        }
    return response.Response(payload)


def ativar_contingencia(viewset, request, pk=None):
    """POST /nfe-saida/contingencia/ativar/"""
    from apps.fiscal import contingencia_sefaz as _cf

    motivo = (request.data.get('motivo') or '').strip()
    if not motivo:
        return response.Response(
            {'detail': 'Informe o motivo da contingência (ex.: SEFAZ-SP indisponível).'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    tp_emis = ''.join(c for c in str(request.data.get('tp_emis') or '2') if c.isdigit())[:1] or '2'
    if tp_emis not in TP_EMIS_PERMITIDOS_NFE or tp_emis == '1':
        return response.Response(
            {'detail': f'tpEmis inválido. Use {", ".join(sorted(TP_EMIS_PERMITIDOS_NFE))}.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        empresa = _empresa_contingencia(request)
        registro = _cf.registrar_contingencia(empresa, motivo=motivo, tp_emis=tp_emis)
        payload = _resumo_registro(registro, 0)
        return response.Response(payload, status=status.HTTP_201_CREATED)
    except ContingenciaSefazError as exc:
        return response.Response({'detail': str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)


def encerrar_contingencia(viewset, request, pk=None):
    """POST /nfe-saida/contingencia/encerrar/"""
    try:
        from apps.fiscal import contingencia_sefaz as _cf

        empresa = _empresa_contingencia(request)
        registro = _cf.encerrar_contingencia(empresa)
        if not registro:
            return response.Response(
                {'detail': 'Nenhuma contingência ativa para a empresa.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return response.Response({
            'empresa_id': empresa.pk,
            'encerrada_em': registro.encerrada_em.isoformat() if registro.encerrada_em else None,
            'tp_emis': registro.tp_emis,
            'motivo': registro.motivo,
            'inicio': registro.inicio.isoformat() if registro.inicio else None,
        })
    except ContingenciaSefazError as exc:
        return response.Response({'detail': str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)


def transmitir_pendentes_contingencia(viewset, request, pk=None):
    """POST /nfe-saida/contingencia/transmitir-pendentes/"""
    try:
        from apps.fiscal import contingencia_sefaz as _cf

        empresa = _empresa_contingencia(request)
        resultado = _cf.transmitir_pendentes_contingencia(empresa, usuario=request.user)
        code = status.HTTP_200_OK if not resultado['falhas'] else status.HTTP_207_MULTI_STATUS
        return response.Response(resultado, status=code)
    except ContingenciaSefazError as exc:
        return response.Response({'detail': str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
    except Exception as exc:  # noqa: BLE001 — transmissão SEFAZ pode falhar de várias formas
        return response.Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)


def emitir_contingencia(viewset, request, pk=None):
    """POST /nfe-saida/{pk}/emitir-contingencia/"""
    from apps.fiscal import contingencia_sefaz as _cf

    nf = viewset.get_object()
    try:
        resultado = _cf.emitir_em_contingencia(nf, usuario=request.user)
        return response.Response(resultado)
    except ContingenciaSefazError as exc:
        return response.Response({'detail': str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
