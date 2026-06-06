from django.urls import path
from . import ui_views

urlpatterns = [
    path("", ui_views.dashboard, name="dashboard"),
    path("alerts/", ui_views.alerts, name="alerts"),
    path("grafana/", ui_views.grafana_embed, name="grafana_embed"),
]
