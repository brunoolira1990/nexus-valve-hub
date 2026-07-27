from django.urls import path

from apps.auditoria.views import AuditoriaCapacidadeView, AuditoriaObjetoHistoricoView

urlpatterns = [
    path('capacidade/', AuditoriaCapacidadeView.as_view(), name='auditoria-capacidade'),
    # slug restringe caracteres; entidades fora do MVP retornam 404 na view.
    path(
        'objetos/<slug:app_label>/<slug:model_name>/<int:object_id>/',
        AuditoriaObjetoHistoricoView.as_view(),
        name='auditoria-objeto-historico',
    ),
]
