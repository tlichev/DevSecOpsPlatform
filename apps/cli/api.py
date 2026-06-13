from celery.result import AsyncResult
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import IsEngineerOrReadOnly
from .models import CLISession, CLICommand
from .serializers import CLISessionSerializer, CLICommandSerializer
from .tasks import execute_cli_command


class CLISessionViewSet(viewsets.ModelViewSet):
    serializer_class   = CLISessionSerializer
    permission_classes = [IsEngineerOrReadOnly]

    def get_queryset(self):
        qs = CLISession.objects.select_related('device', 'user')
        device_id = self.request.query_params.get('device')
        if device_id:
            qs = qs.filter(device_id=device_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def session_history(request, session_id):
    """All commands for a single session, oldest first."""
    try:
        session = CLISession.objects.get(pk=session_id)
    except CLISession.DoesNotExist:
        return Response({'error': 'Session not found.'}, status=status.HTTP_404_NOT_FOUND)
    commands = CLICommand.objects.filter(session=session).order_by('executed_at')
    return Response(CLICommandSerializer(commands, many=True).data)


@api_view(['POST'])
@permission_classes([IsEngineerOrReadOnly])
def execute_command(request):
    """
    Dispatch an SSH command to a device asynchronously.

    Body  : { device_id, command, session_id }
    Returns: { task_id }
    """
    device_id  = request.data.get('device_id')
    command    = (request.data.get('command') or '').strip()
    session_id = request.data.get('session_id')

    if not device_id or not command or not session_id:
        return Response(
            {'error': 'device_id, command, and session_id are required.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    task = execute_cli_command.apply_async(
        args=[int(device_id), command, int(session_id)],
        queue='provisioning',
    )
    return Response({'task_id': task.id}, status=status.HTTP_202_ACCEPTED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def cli_task_status(request, task_id):
    """Poll the result of an execute_cli_command task."""
    result = AsyncResult(task_id)
    if result.state == 'PENDING':
        return Response({'state': 'PENDING'})
    if result.state == 'FAILURE':
        return Response({'state': 'FAILURE', 'output': str(result.info), 'is_error': True})
    if result.state == 'SUCCESS':
        return Response({'state': 'SUCCESS', **result.result})
    return Response({'state': result.state})
