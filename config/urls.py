from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse


def health_check(request):
    return JsonResponse({'status': 'ok'})


urlpatterns = [
    path('admin/', admin.site.urls),
    path('health/', health_check),

    # App views
    path('', include('apps.inventory.urls', namespace='inventory')),
    path('provisioning/', include('apps.provisioning.urls', namespace='provisioning')),
    path('monitoring/', include('apps.monitoring.urls', namespace='monitoring')),
    path('security/', include('apps.security.urls', namespace='security')),
    path('accounts/', include('apps.accounts.urls', namespace='accounts')),

    # REST API
    path('api/', include('api.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
