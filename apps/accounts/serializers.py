from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Embed role + capability flags directly into the JWT claims."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['username'] = user.username
        token['role'] = user.role
        token['is_admin'] = user.is_admin()
        token['is_engineer'] = user.is_engineer()
        token['full_name'] = user.get_full_name()
        return token


class UserSerializer(serializers.ModelSerializer):
    is_admin_flag = serializers.SerializerMethodField()
    is_engineer_flag = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id', 'username', 'first_name', 'last_name', 'email',
            'role', 'is_superuser', 'is_active',
            'date_joined', 'last_login',
            'is_admin_flag', 'is_engineer_flag',
        )
        read_only_fields = (
            'id', 'username', 'is_superuser', 'date_joined', 'last_login',
        )

    def get_is_admin_flag(self, obj):
        return obj.is_admin()

    def get_is_engineer_flag(self, obj):
        return obj.is_engineer()


class UserMeSerializer(serializers.ModelSerializer):
    """Read-only serializer for the /api/accounts/me/ endpoint."""
    is_admin = serializers.SerializerMethodField()
    is_engineer = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id', 'username', 'first_name', 'last_name', 'email',
            'role', 'is_admin', 'is_engineer',
            'last_login', 'date_joined',
        )
        read_only_fields = fields

    def get_is_admin(self, obj):
        return obj.is_admin()

    def get_is_engineer(self, obj):
        return obj.is_engineer()
