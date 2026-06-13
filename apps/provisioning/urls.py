from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .api import (
    ProvisioningTemplateViewSet,
    AuditLogViewSet,
    render_preview_view,
    push_config_view,
    task_status_view,
)

app_name = 'provisioning'

router = DefaultRouter()
router.register('templates', ProvisioningTemplateViewSet, basename='template')
router.register('audit',     AuditLogViewSet,             basename='auditlog')

urlpatterns = [
    # Browser views
    path('',                     views.provisioning_home, name='home'),
    path('push/',                views.push_config,       name='push_config'),
    path('audit/',               views.audit_log,         name='audit_log'),
    path('audit/<int:pk>/',      views.audit_detail,      name='audit_detail'),

    # REST API (also reachable at /api/provisioning/ via api/urls.py)
    path('api/',                          include(router.urls)),
    path('api/render/',                   render_preview_view, name='api-render'),
    path('api/push/',                     push_config_view,    name='api-push'),
    path('api/task/<str:task_id>/',       task_status_view,    name='api-task-status'),
]
