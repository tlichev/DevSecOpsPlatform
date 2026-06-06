from rest_framework.routers import DefaultRouter
from .views import ConfigTemplateViewSet, ProvisioningJobViewSet, AuditLogViewSet

router = DefaultRouter()
router.register("templates", ConfigTemplateViewSet, basename="template")
router.register("jobs", ProvisioningJobViewSet, basename="job")
router.register("audit", AuditLogViewSet, basename="audit")

urlpatterns = router.urls
