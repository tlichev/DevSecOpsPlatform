import logging
import time
from contextlib import contextmanager
from typing import Optional

from netmiko import ConnectHandler, NetMikoTimeoutException, NetMikoAuthenticationException

logger = logging.getLogger(__name__)


class NetmikoError(Exception):
    pass


class NetmikoClient:
    DEFAULT_TIMEOUT = 30
    DEFAULT_BANNER_TIMEOUT = 15

    def __init__(self, device):
        self.device = device
        self._connection = None

    def _build_params(self) -> dict:
        return {
            "device_type": self.device.netmiko_device_type,
            "host": self.device.ip_address,
            "username": self.device.ssh_username,
            "password": self.device.ssh_password,
            "port": self.device.ssh_port,
            "timeout": self.DEFAULT_TIMEOUT,
            "banner_timeout": self.DEFAULT_BANNER_TIMEOUT,
            "conn_timeout": 15,
        }

    @contextmanager
    def connect(self):
        params = self._build_params()
        logger.info("Connecting to %s (%s)", self.device.hostname, self.device.ip_address)
        start = time.monotonic()
        try:
            conn = ConnectHandler(**params)
            logger.info("Connected to %s in %.2fs", self.device.hostname, time.monotonic() - start)
            try:
                yield conn
            finally:
                conn.disconnect()
                logger.info("Disconnected from %s", self.device.hostname)
        except NetMikoTimeoutException as exc:
            raise NetmikoError(f"Timeout connecting to {self.device.hostname}: {exc}") from exc
        except NetMikoAuthenticationException as exc:
            raise NetmikoError(f"Auth failed for {self.device.hostname}: {exc}") from exc
        except Exception as exc:
            raise NetmikoError(f"Connection error on {self.device.hostname}: {exc}") from exc

    def push_config(self, config_lines: list[str]) -> str:
        with self.connect() as conn:
            output = conn.send_config_set(config_lines)
            # Save running config
            conn.save_config()
            return output

    def send_command(self, command: str, expect_string: Optional[str] = None) -> str:
        with self.connect() as conn:
            if expect_string:
                return conn.send_command(command, expect_string=expect_string)
            return conn.send_command(command)

    def get_running_config(self) -> str:
        return self.send_command("show running-config")

    def get_version(self) -> str:
        return self.send_command("show version")
