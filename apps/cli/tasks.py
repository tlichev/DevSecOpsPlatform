import time
import logging
from celery import shared_task

logger = logging.getLogger(__name__)

# Commands that should use send_config_set (multi-line config mode)
_CONFIG_PREFIXES = ('interface ', 'router ', 'ip route', 'access-list', 'line ', 'snmp-server', 'ntp server', 'logging ')


@shared_task(bind=True, name='cli.execute_command', queue='provisioning',
             max_retries=0, time_limit=60)
def execute_cli_command(self, device_id: int, command: str, session_id: int) -> dict:
    from netmiko import ConnectHandler
    from netmiko.exceptions import NetmikoTimeoutException, NetmikoAuthenticationException
    from apps.inventory.models import Device
    from .models import CLISession, CLICommand

    try:
        device = Device.objects.get(pk=device_id)
    except Device.DoesNotExist:
        return {'output': 'Device not found.', 'is_error': True, 'duration_ms': 0}

    try:
        session = CLISession.objects.get(pk=session_id)
    except CLISession.DoesNotExist:
        return {'output': 'Session not found.', 'is_error': True, 'duration_ms': 0}

    cmd = command.strip()
    start = time.monotonic()

    try:
        params = device.get_netmiko_params()
        with ConnectHandler(**params) as conn:
            cmd_lower = cmd.lower()

            # Pure navigation commands — no SSH needed
            if cmd_lower in ('exit', 'end', 'logout', 'quit'):
                output = ''
                is_error = False
            # Config-mode block: send as config set
            elif any(cmd_lower.startswith(p) for p in _CONFIG_PREFIXES):
                conn.send_config_set(cmd.splitlines())
                output = conn.send_command('show run | section ' + cmd.split()[0], read_timeout=30)
                is_error = False
            else:
                output = conn.send_command(cmd, read_timeout=30)
                is_error = False

    except NetmikoAuthenticationException:
        output = 'Authentication failed — check SSH credentials for this device.'
        is_error = True
    except NetmikoTimeoutException:
        output = 'Connection timed out — device unreachable on management network.'
        is_error = True
    except Exception as exc:
        output = f'Error: {exc}'
        is_error = True
        logger.warning('cli task failed device=%s cmd=%r: %s', device.hostname, command, exc)

    duration_ms = round((time.monotonic() - start) * 1000)

    CLICommand.objects.create(
        session=session,
        command=command,
        output=output,
        is_error=is_error,
        duration_ms=duration_ms,
    )

    # Touch session.last_used
    from django.utils import timezone
    CLISession.objects.filter(pk=session_id).update(last_used=timezone.now())

    return {
        'output': output,
        'is_error': is_error,
        'duration_ms': duration_ms,
        'device': device.hostname,
        'command': command,
    }
