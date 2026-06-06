from django.urls import path
from . import ui_views

urlpatterns = [
    path("", ui_views.device_list, name="inventory_list"),
    path("<int:pk>/", ui_views.device_detail, name="inventory_detail"),
    path("add/", ui_views.device_add, name="inventory_add"),
    path("discovery/", ui_views.discovery_list, name="discovery_list"),
]
