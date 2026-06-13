from django.contrib.auth import get_user_model
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import UserSerializer, UserMeSerializer, CustomTokenObtainPairSerializer
from .permissions import IsAdminUser

User = get_user_model()


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class UserViewSet(viewsets.ModelViewSet):
    """
    Admin-only CRUD for user accounts.
    The me() action is accessible to any authenticated user.
    """
    queryset = User.objects.all().order_by('username')
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminUser]

    def get_queryset(self):
        qs = super().get_queryset()
        role = self.request.query_params.get('role')
        if role:
            qs = qs.filter(role=role)
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() in ('1', 'true', 'yes'))
        return qs

    @action(
        detail=False,
        methods=['get'],
        permission_classes=[permissions.IsAuthenticated],
        url_path='me',
    )
    def me(self, request):
        return Response(UserMeSerializer(request.user).data)

    @action(
        detail=True,
        methods=['post'],
        permission_classes=[permissions.IsAuthenticated, IsAdminUser],
        url_path='set-role',
    )
    def set_role(self, request, pk=None):
        user = self.get_object()
        role = request.data.get('role', '')
        valid = [r[0] for r in User.ROLE_CHOICES]
        if role not in valid:
            return Response(
                {'error': f'role must be one of: {valid}'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.role = role
        user.save(update_fields=['role'])
        return Response(UserSerializer(user).data)

    @action(
        detail=True,
        methods=['post'],
        permission_classes=[permissions.IsAuthenticated, IsAdminUser],
        url_path='toggle-active',
    )
    def toggle_active(self, request, pk=None):
        user = self.get_object()
        if user.pk == request.user.pk:
            return Response(
                {'error': 'You cannot deactivate your own account.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.is_active = not user.is_active
        user.save(update_fields=['is_active'])
        return Response({'id': user.pk, 'is_active': user.is_active})
