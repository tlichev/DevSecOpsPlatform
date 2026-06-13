import asyncio
import json
import logging
import select
import threading

import paramiko
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser

logger = logging.getLogger(__name__)


class SSHConsumer(AsyncWebsocketConsumer):
    """
    Bidirectional WebSocket ↔ SSH proxy.

    Browser (xterm.js) ──WS──▶ SSHConsumer ──SSH──▶ Cisco device
    Browser (xterm.js) ◀──WS── SSHConsumer ◀──SSH── Cisco device
    """

    async def connect(self):
        user = self.scope.get('user')
        if (not user
                or isinstance(user, AnonymousUser)
                or not user.is_authenticated
                or not user.is_engineer()):
            await self.close(code=4003)
            return

        self.pk          = self.scope['url_route']['kwargs']['pk']
        self.ssh_client  = None
        self.ssh_channel = None
        self._stop       = threading.Event()
        self._loop       = asyncio.get_running_loop()

        await self.accept()
        await self._write(b'\x1b[36m\r\nConnecting to device\x1b[0m\r\n')

        # Load device
        try:
            from apps.inventory.models import Device
            device = await self._loop.run_in_executor(
                None, lambda: Device.objects.get(pk=self.pk)
            )
        except Exception as exc:
            await self._write(f'\x1b[31mDevice not found: {exc}\x1b[0m\r\n'.encode())
            await self.close()
            return

        await self._write(
            f'\x1b[36mSSH → {device.ip_address}  ({device.hostname})\x1b[0m\r\n'.encode()
        )

        # Open SSH connection (blocking — run in thread pool)
        try:
            await self._loop.run_in_executor(None, self._open_ssh, device)
        except paramiko.AuthenticationException:
            await self._write(b'\x1b[31mAuthentication failed - check SSH credentials.\x1b[0m\r\n')
            await self.close()
            return
        except (paramiko.ssh_exception.NoValidConnectionsError, TimeoutError, OSError) as exc:
            await self._write(f'\x1b[31mCould not connect: {exc}\x1b[0m\r\n'.encode())
            await self.close()
            return
        except Exception as exc:
            await self._write(f'\x1b[31mSSH error: {exc}\x1b[0m\r\n'.encode())
            await self.close()
            return

        # Start background thread that reads SSH output and sends it to the browser
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    # ── SSH setup ─────────────────────────────────────────────────────────────

    def _open_ssh(self, device):
        password = device.get_plaintext_password()
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            hostname=str(device.ip_address),
            username=device.ssh_username or 'admin',
            password=password or '',
            timeout=15,
            look_for_keys=False,
            allow_agent=False,
        )
        channel = client.invoke_shell(term='xterm-256color', width=220, height=50)
        channel.setblocking(False)
        self.ssh_client  = client
        self.ssh_channel = channel

    # ── SSH → WebSocket reader thread ─────────────────────────────────────────

    def _read_loop(self):
        while not self._stop.is_set():
            try:
                r, _, _ = select.select([self.ssh_channel], [], [], 0.05)
                if r:
                    data = self.ssh_channel.recv(4096)
                    if not data:
                        break
                    asyncio.run_coroutine_threadsafe(
                        self.send(bytes_data=data), self._loop
                    )
            except Exception:
                break
        # SSH side closed — tell the browser
        asyncio.run_coroutine_threadsafe(
            self.send(bytes_data=b'\r\n\x1b[33m[Connection closed]\x1b[0m\r\n'),
            self._loop,
        )

    # ── WebSocket → SSH ───────────────────────────────────────────────────────

    async def receive(self, text_data=None, bytes_data=None):
        if not self.ssh_channel or self.ssh_channel.closed:
            return

        if text_data:
            # Check for control messages (resize)
            try:
                msg = json.loads(text_data)
                if msg.get('type') == 'resize':
                    cols = max(20, int(msg.get('cols', 220)))
                    rows = max(5,  int(msg.get('rows', 50)))
                    await self._loop.run_in_executor(
                        None, lambda: self.ssh_channel.resize_pty(width=cols, height=rows)
                    )
                    return
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
            data = text_data.encode('utf-8', errors='replace')
        else:
            data = bytes_data

        if data:
            await self._loop.run_in_executor(None, self.ssh_channel.send, data)

    # ── Disconnect ────────────────────────────────────────────────────────────

    async def disconnect(self, code):
        self._stop.set()
        for obj in (self.ssh_channel, self.ssh_client):
            if obj:
                try:
                    obj.close()
                except Exception:
                    pass

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _write(self, data: bytes):
        await self.send(bytes_data=data)
