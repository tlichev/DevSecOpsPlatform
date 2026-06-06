from rest_framework.routers import DefaultRouter
from .views import DeviceViewSet, DiscoveryJobViewSet

router = DefaultRouter()
router.register("devices", DeviceViewSet, basename="device")
router.register("discovery", DiscoveryJobViewSet, basename="discovery")

urlpatterns = router.urls
