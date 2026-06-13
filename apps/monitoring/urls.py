from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .api import AlertViewSet, alerts_webhook

app_name = 'monitoring'

router = DefaultRouter()
router.register('alerts', AlertViewSet, basename='alert')

urlpatterns = [
    # Browser views
    path('',            views.monitoring_home, name='home'),
    path('alerts/',     views.alerts,          name='alerts'),
    path('dashboards/', views.dashboards,       name='dashboards'),

    # REST API (also reachable at /api/monitoring/ via api/urls.py)
    path('api/', include(router.urls)),
]
