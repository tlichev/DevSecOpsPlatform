from rest_framework import serializers
from .models import ComplianceRule, ComplianceResult, GoldenConfig, DriftResult


class ComplianceRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ComplianceRule
        fields = [
            'id', 'name', 'description', 'category', 'pattern',
            'match_means_pass', 'device_types', 'severity', 'is_active',
            'remediation', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class ComplianceResultSerializer(serializers.ModelSerializer):
    device_hostname = serializers.CharField(source='device.hostname', read_only=True)
    device_site     = serializers.CharField(source='device.site',     read_only=True)
    rule_name       = serializers.CharField(source='rule.name',       read_only=True)
    rule_category   = serializers.CharField(source='rule.category',   read_only=True)
    rule_severity   = serializers.CharField(source='rule.severity',   read_only=True)
    passed          = serializers.BooleanField(read_only=True)

    class Meta:
        model  = ComplianceResult
        fields = [
            'id', 'device', 'device_hostname', 'device_site',
            'rule', 'rule_name', 'rule_category', 'rule_severity',
            'status', 'passed', 'evidence', 'error_message',
            'checked_at', 'task_id',
        ]
        read_only_fields = fields


class GoldenConfigSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        model  = GoldenConfig
        fields = [
            'id', 'device_type', 'name', 'description', 'content',
            'is_active', 'version',
            'created_by', 'created_by_username', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at']

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)


class DriftResultSerializer(serializers.ModelSerializer):
    device_hostname = serializers.CharField(source='device.hostname',          read_only=True)
    device_site     = serializers.CharField(source='device.site',              read_only=True)
    device_type     = serializers.CharField(source='device.device_type',       read_only=True)
    golden_name     = serializers.CharField(source='golden_config.name',       read_only=True, default='')
    is_clean        = serializers.BooleanField(read_only=True)

    class Meta:
        model  = DriftResult
        fields = [
            'id', 'device', 'device_hostname', 'device_site', 'device_type',
            'golden_config', 'golden_name',
            'status', 'is_clean', 'drift_lines', 'diff',
            'error_message', 'checked_at', 'task_id',
        ]
        read_only_fields = fields


class ComplianceSummarySerializer(serializers.Serializer):
    """Aggregate compliance stats for the dashboard."""
    overall_score      = serializers.IntegerField()
    total_checks       = serializers.IntegerField()
    total_pass         = serializers.IntegerField()
    total_fail         = serializers.IntegerField()
    total_error        = serializers.IntegerField()
    devices_checked    = serializers.IntegerField()
    devices_compliant  = serializers.IntegerField()  # score >= 80%
    devices_drifted    = serializers.IntegerField()
    last_checked       = serializers.DateTimeField(allow_null=True)
