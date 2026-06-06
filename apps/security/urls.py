from rest_framework.routers import DefaultRouter
from .views import (
    ComplianceRuleViewSet, ComplianceCheckViewSet, ConfigSnapshotViewSet,
    DriftReportViewSet, SecurityActionViewSet, UserProfileViewSet,
)

router = DefaultRouter()
router.register("rules", ComplianceRuleViewSet, basename="compliance-rule")
router.register("checks", ComplianceCheckViewSet, basename="compliance-check")
router.register("snapshots", ConfigSnapshotViewSet, basename="snapshot")
router.register("drift", DriftReportViewSet, basename="drift")
router.register("actions", SecurityActionViewSet, basename="security-action")
router.register("users", UserProfileViewSet, basename="user-profile")

urlpatterns = router.urls
