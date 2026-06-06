from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

urlpatterns = [
    path("", RedirectView.as_view(url="/dashboard/", permanent=False)),
    path("admin/", admin.site.urls),

    # JWT auth
    path("api/auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/auth/token/verify/", TokenVerifyView.as_view(), name="token_verify"),

    # App APIs
    path("api/inventory/", include("apps.inventory.urls")),
    path("api/provisioning/", include("apps.provisioning.urls")),
    path("api/monitoring/", include("apps.monitoring.urls")),
    path("api/security/", include("apps.security.urls")),

    # UI views
    path("dashboard/", include("apps.monitoring.ui_urls")),
    path("inventory/", include("apps.inventory.ui_urls")),
    path("provisioning/", include("apps.provisioning.ui_urls")),
    path("security/", include("apps.security.ui_urls")),
]
