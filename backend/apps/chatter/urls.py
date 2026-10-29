from django.urls import path

from apps.chatter.views import AnexoChatterViewSet, NotaChatterViewSet

notas_list = NotaChatterViewSet.as_view({'get': 'list', 'post': 'create'})
notas_detail = NotaChatterViewSet.as_view(
    {'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}
)
anexos_list = AnexoChatterViewSet.as_view({'get': 'list', 'post': 'create'})
anexos_detail = AnexoChatterViewSet.as_view({'get': 'retrieve', 'delete': 'destroy'})

urlpatterns = [
    path('notas/', notas_list, name='chatter-notas'),
    path('notas/<int:pk>/', notas_detail, name='chatter-nota-detail'),
    path('anexos/', anexos_list, name='chatter-anexos'),
    path('anexos/<int:pk>/', anexos_detail, name='chatter-anexo-detail'),
]
