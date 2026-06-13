from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .api import (
    ComplianceRuleViewSet,
    ComplianceResultViewSet,
    GoldenConfigViewSet,
    DriftResultViewSet,
    run_compliance_view,
    run_all_compliance_view,
    run_drift_view,
    run_all_drift_view,
    compliance_summary_view,
)

app_name = 'security'

router = DefaultRouter()
router.register('rules',      ComplianceRuleViewSet,   basename='rule')
router.register('results',    ComplianceResultViewSet, basename='result')
router.register('golden',     GoldenConfigViewSet,     basename='golden')
router.register('drift',      DriftResultViewSet,      basename='drift')

urlpatterns = [
    # Browser views
    path('',                          views.security_home,       name='home'),
    path('compliance/',               views.compliance,          name='compliance'),
    path('compliance/<int:device_id>/', views.compliance_device,  name='compliance_device'),
    path('drift/',                    views.drift_detection,     name='drift'),
    path('drift/<int:device_id>/',    views.drift_device,        name='drift_device'),

    # REST API
    path('api/', include(router.urls)),
    path('api/compliance/summary/',           compliance_summary_view,   name='api-compliance-summary'),
    path('api/compliance/run/<int:device_id>/', run_compliance_view,     name='api-run-compliance'),
    path('api/compliance/run-all/',            run_all_compliance_view,  name='api-run-all-compliance'),
    path('api/drift/run/<int:device_id>/',     run_drift_view,           name='api-run-drift'),
    path('api/drift/run-all/',                 run_all_drift_view,       name='api-run-all-drift'),
]
