from rest_framework import serializers
from .models import ComplianceRule, ComplianceCheck, ConfigSnapshot, DriftReport, UserProfile


class ComplianceRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComplianceRule
        fields = ["id", "name", "description", "check_command", "expected_pattern",
                  "must_match", "severity", "remediation", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]


class ComplianceCheckSerializer(serializers.ModelSerializer):
    device_hostname = serializers.CharField(source="device.hostname", read_only=True)
    rule_name = serializers.CharField(source="rule.name", read_only=True)
    rule_severity = serializers.CharField(source="rule.severity", read_only=True)
    initiated_by_username = serializers.CharField(source="initiated_by.username", read_only=True, allow_null=True)

    class Meta:
        model = ComplianceCheck
        fields = ["id", "device_hostname", "rule_name", "rule_severity",
                  "status", "output", "detail", "checked_at", "initiated_by_username"]


class ConfigSnapshotSerializer(serializers.ModelSerializer):
    device_hostname = serializers.CharField(source="device.hostname", read_only=True)
    taken_by_username = serializers.CharField(source="taken_by.username", read_only=True, allow_null=True)

    class Meta:
        model = ConfigSnapshot
        fields = ["id", "device_hostname", "is_golden", "taken_at", "taken_by_username", "comment"]
        read_only_fields = ["id", "taken_at"]


class DriftReportSerializer(serializers.ModelSerializer):
    device_hostname = serializers.CharField(source="device.hostname", read_only=True)

    class Meta:
        model = DriftReport
        fields = ["id", "device_hostname", "status", "diff", "checked_at"]


class UserProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.CharField(source="user.email", read_only=True)

    class Meta:
        model = UserProfile
        fields = ["id", "username", "email", "role", "created_at"]
        read_only_fields = ["id", "created_at"]
