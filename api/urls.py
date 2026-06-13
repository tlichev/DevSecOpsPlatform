from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView
from drf_spectacular.views import (
    SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView,
)

from apps.accounts.api import CustomTokenObtainPairView, UserViewSet
from apps.inventory.api import DeviceViewSet, dashboard_stats
from apps.provisioning.api import (
    ProvisioningTemplateViewSet,
    AuditLogViewSet,
    render_preview_view,
    push_config_view,
    task_status_view,
)
from apps.monitoring.api import AlertViewSet, alerts_webhook
from apps.security.api import (
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

router = DefaultRouter()
router.register(r'accounts/users',         UserViewSet,                 basename='account-user')
router.register(r'devices',                DeviceViewSet,               basename='device')
router.register(r'provisioning/templates', ProvisioningTemplateViewSet, basename='prov-template')
router.register(r'provisioning/audit',     AuditLogViewSet,             basename='prov-audit')
router.register(r'monitoring/alerts',      AlertViewSet,                basename='mon-alert')
router.register(r'security/rules',         ComplianceRuleViewSet,       basename='sec-rule')
router.register(r'security/results',       ComplianceResultViewSet,     basename='sec-result')
router.register(r'security/golden',        GoldenConfigViewSet,         basename='sec-golden')
router.register(r'security/drift',         DriftResultViewSet,          basename='sec-drift')

urlpatterns = [
    # ── JWT (custom serializer embeds role + flags in token claims) ───────────
    path('token/',         CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(),          name='token_refresh'),
    path('token/verify/',  TokenVerifyView.as_view(),           name='token_verify'),

    # ── Dashboard ─────────────────────────────────────────────────────────────
    path('dashboard/stats/', dashboard_stats, name='dashboard_stats'),

    # ── AlertManager webhook (receives batched payloads from AlertManager) ──────
    path('alerts/webhook/',  alerts_webhook,  name='alerts_webhook'),

    # ── Provisioning ──────────────────────────────────────────────────────────
    path('provisioning/render/',              render_preview_view, name='prov-render'),
    path('provisioning/push/',                push_config_view,    name='prov-push'),
    path('provisioning/task/<str:task_id>/',  task_status_view,    name='prov-task-status'),

    # ── Security / Compliance ─────────────────────────────────────────────────
    path('security/compliance/summary/',              compliance_summary_view,   name='sec-compliance-summary'),
    path('security/compliance/run/<int:device_id>/',  run_compliance_view,       name='sec-run-compliance'),
    path('security/compliance/run-all/',              run_all_compliance_view,   name='sec-run-all-compliance'),
    path('security/drift/run/<int:device_id>/',       run_drift_view,            name='sec-run-drift'),
    path('security/drift/run-all/',                   run_all_drift_view,        name='sec-run-all-drift'),

    # ── OpenAPI schema + docs ─────────────────────────────────────────────────
    path('schema/',  SpectacularAPIView.as_view(),                    name='schema'),
    path('docs/',    SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('redoc/',   SpectacularRedocView.as_view(url_name='schema'),   name='redoc'),

    # ── DRF router (devices + future ViewSets) ────────────────────────────────
    path('', include(router.urls)),
]
