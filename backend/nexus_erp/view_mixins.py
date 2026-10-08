"""Mixins compartilhados para ViewSets."""

from __future__ import annotations

from django.db.models import ProtectedError
from rest_framework import status
from rest_framework.response import Response

from nexus_erp.delete_protection import format_protected_delete_message


class FriendlyDestroyMixin:
    """Converte ProtectedError em resposta 409 com mensagem operacional."""

    destroy_entity_label: str = 'registro'

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError as exc:
            msg = format_protected_delete_message(exc, entidade=self.destroy_entity_label)
            return Response({'detail': msg}, status=status.HTTP_409_CONFLICT)
