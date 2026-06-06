from django.contrib import admin
from .models import ComplianceRule, ComplianceCheck, ConfigSnapshot, DriftReport, UserProfile


@admin.register(ComplianceRule)
class ComplianceRuleAdmin(admin.ModelAdmin):
    list_display = ["name", "severity", "is_active", "created_at"]
    list_filter = ["severity", "is_active"]


@admin.register(ComplianceCheck)
class ComplianceCheckAdmin(admin.ModelAdmin):
    list_display = ["device", "rule", "status", "checked_at"]
    list_filter = ["status"]


@admin.register(ConfigSnapshot)
class ConfigSnapshotAdmin(admin.ModelAdmin):
    list_display = ["device", "is_golden", "taken_at", "taken_by"]
    list_filter = ["is_golden"]


@admin.register(DriftReport)
class DriftReportAdmin(admin.ModelAdmin):
    list_display = ["device", "status", "checked_at"]
    list_filter = ["status"]


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "role", "created_at"]
    list_filter = ["role"]
