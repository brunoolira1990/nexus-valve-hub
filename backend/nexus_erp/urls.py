from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.cadastros.views import consulta_cep, consulta_cnpj, consulta_ie

# API REST: rotas do DefaultRouter em apps.api_urls (empresas, clientes, fornecedores,
# transportadoras, produtos, fiscal, etc.). Tokens JWT abaixo.
urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/consulta-cep/<str:cep>/', consulta_cep, name='consulta-cep'),
    path('api/consulta-cnpj/<str:cnpj>/', consulta_cnpj, name='consulta-cnpj'),
    path('api/consulta-ie/', consulta_ie, name='consulta-ie'),
    path('api/', include('apps.api_urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
