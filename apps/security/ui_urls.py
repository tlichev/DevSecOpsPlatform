from django.urls import path
from . import ui_views

urlpatterns = [
    path("", ui_views.compliance_dashboard, name="security_dashboard"),
    path("checks/", ui_views.compliance_checks, name="compliance_checks"),
    path("drift/", ui_views.drift_reports, name="drift_reports"),
    path("drift/<int:pk>/", ui_views.drift_detail, name="drift_detail"),
]
