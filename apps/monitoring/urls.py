from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import AlertViewSet, GrafanaDashboardViewSet, alertmanager_webhook

router = DefaultRouter()
router.register("alerts", AlertViewSet, basename="alert")
router.register("dashboards", GrafanaDashboardViewSet, basename="dashboard")

urlpatterns = router.urls + [
    path("webhook/alertmanager/", alertmanager_webhook, name="alertmanager_webhook"),
]
