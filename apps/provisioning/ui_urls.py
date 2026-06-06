from django.urls import path
from . import ui_views

urlpatterns = [
    path("", ui_views.job_list, name="provisioning_list"),
    path("templates/", ui_views.template_list, name="template_list"),
    path("templates/<int:pk>/", ui_views.template_detail, name="template_detail"),
    path("jobs/<int:pk>/", ui_views.job_detail, name="job_detail"),
    path("audit/", ui_views.audit_log, name="audit_log"),
]
