from rest_framework.routers import DefaultRouter

from .views import LeadViewSet, OportunidadeViewSet

router = DefaultRouter()
router.register('crm/leads', LeadViewSet, basename='crm-lead')
router.register('crm/oportunidades', OportunidadeViewSet, basename='crm-oportunidade')

urlpatterns = router.urls
