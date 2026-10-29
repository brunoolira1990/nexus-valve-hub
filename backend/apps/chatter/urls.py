from django.urls import path

from apps.chatter.views import NotaChatterViewSet

notas_list = NotaChatterViewSet.as_view({'get': 'list', 'post': 'create'})
notas_detail = NotaChatterViewSet.as_view(
    {'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}
)

urlpatterns = [
    path('notas/', notas_list, name='chatter-notas'),
    path('notas/<int:pk>/', notas_detail, name='chatter-nota-detail'),
]
