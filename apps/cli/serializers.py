from rest_framework import serializers
from .models import CLISession, CLICommand


class CLICommandSerializer(serializers.ModelSerializer):
    class Meta:
        model  = CLICommand
        fields = ['id', 'command', 'output', 'is_error', 'executed_at', 'duration_ms']
        read_only_fields = fields


class CLISessionSerializer(serializers.ModelSerializer):
    command_count   = serializers.SerializerMethodField()
    device_hostname = serializers.CharField(source='device.hostname', read_only=True)
    opened_by       = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model  = CLISession
        fields = ['id', 'device', 'device_hostname', 'opened_by',
                  'name', 'created_at', 'last_used', 'command_count']
        read_only_fields = ['id', 'device_hostname', 'opened_by',
                            'created_at', 'last_used', 'command_count']

    def get_command_count(self, obj):
        return obj.commands.count()
