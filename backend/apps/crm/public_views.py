import hashlib
import hmac
import json
import time

from django.conf import settings
from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import Lead
from .serializers import SiteLeadCaptureSerializer


MAX_PAYLOAD_BYTES = 16 * 1024
CLOCK_SKEW_SECONDS = 5 * 60


def _invalid_signature_response(detail):
    return Response({'detail': detail}, status=status.HTTP_401_UNAUTHORIZED)


def _build_observacoes(payload):
    lines = [f"Assunto: {payload['assunto']}", payload['mensagem']]
    context = (
        ('Produto de interesse', payload.get('produto_interesse')),
        ('Página de origem', payload.get('pagina_origem')),
        ('UTM source', payload.get('utm_source')),
        ('UTM medium', payload.get('utm_medium')),
        ('UTM campaign', payload.get('utm_campaign')),
        ('UTM content', payload.get('utm_content')),
        ('UTM term', payload.get('utm_term')),
    )
    for label, value in context:
        if value:
            lines.append(f'{label}: {value}')
    return '\n'.join(lines)


def _lead_response(lead, duplicate):
    return Response(
        {
            'success': True,
            'lead_id': lead.id,
            'external_id': lead.external_id,
            'duplicate': duplicate,
        },
        status=status.HTTP_200_OK if duplicate else status.HTTP_201_CREATED,
    )


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def site_lead_capture(request):
    """Recebe captações assinadas pelo backend do site Nexus Válvulas."""
    raw_body = request.body
    if len(raw_body) > MAX_PAYLOAD_BYTES:
        return Response(
            {'detail': 'Payload excede o limite permitido.'},
            status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        )

    secret = (getattr(settings, 'CRM_SITE_HMAC_SECRET', '') or '').strip()
    if not secret:
        return Response(
            {'detail': 'Integração de captação não configurada.'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    timestamp_header = request.headers.get('X-Site-Timestamp', '').strip()
    request_id_header = request.headers.get('X-Site-Request-Id', '').strip()
    signature_header = request.headers.get('X-Site-Signature', '').strip().lower()
    if not timestamp_header or not request_id_header or not signature_header:
        return _invalid_signature_response('Cabeçalhos de integração incompletos.')

    try:
        timestamp = int(timestamp_header)
    except ValueError:
        return _invalid_signature_response('Timestamp de integração inválido.')

    if abs(time.time() - timestamp) > CLOCK_SKEW_SECONDS:
        return _invalid_signature_response('Assinatura expirada.')

    signed_message = f'{timestamp_header}.'.encode('utf-8') + raw_body
    expected_signature = hmac.new(
        secret.encode('utf-8'),
        signed_message,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature_header, expected_signature):
        return _invalid_signature_response('Assinatura de integração inválida.')

    try:
        payload = json.loads(raw_body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return Response(
            {'detail': 'JSON inválido.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = SiteLeadCaptureSerializer(data=payload)
    serializer.is_valid(raise_exception=False)
    if serializer.errors:
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    validated = serializer.validated_data

    if validated['external_id'] != request_id_header:
        return Response(
            {'detail': 'Request ID não corresponde ao identificador da submissão.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    existing = Lead.objects.filter(external_id=validated['external_id']).first()
    if existing:
        return _lead_response(existing, duplicate=True)

    empresa = validated.get('empresa', '').strip()
    lead_data = {
        'external_id': validated['external_id'],
        'nome': empresa or validated['nome'],
        'nome_contato': validated['nome'],
        'email': validated['email'].strip().lower(),
        'telefone': validated.get('telefone', '').strip(),
        'origem': Lead.Origem.SITE,
        'status': Lead.Status.NOVO,
        'produto_interesse': validated.get('produto_interesse', '').strip(),
        'pagina_origem': validated.get('pagina_origem', '').strip(),
        'utm_source': validated.get('utm_source', '').strip(),
        'utm_medium': validated.get('utm_medium', '').strip(),
        'utm_campaign': validated.get('utm_campaign', '').strip(),
        'utm_content': validated.get('utm_content', '').strip(),
        'utm_term': validated.get('utm_term', '').strip(),
        'observacoes': _build_observacoes(validated),
    }

    try:
        with transaction.atomic():
            lead = Lead.objects.create(**lead_data)
    except IntegrityError:
        lead = Lead.objects.filter(external_id=validated['external_id']).first()
        if lead:
            return _lead_response(lead, duplicate=True)
        raise

    return _lead_response(lead, duplicate=False)
