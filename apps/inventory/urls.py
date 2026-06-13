from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    path('',                       views.dashboard,     name='dashboard'),
    path('inventory/',             views.device_list,   name='device_list'),
    path('inventory/<int:pk>/',    views.device_detail, name='device_detail'),
    path('sites/sofia/',           views.site_sofia,    name='site_sofia'),
    path('sites/burgas/',          views.site_burgas,   name='site_burgas'),
    path('sites/plovdiv/',         views.site_plovdiv,  name='site_plovdiv'),
]
