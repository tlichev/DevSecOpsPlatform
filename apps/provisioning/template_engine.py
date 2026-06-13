"""
Jinja2-based config template engine.
Looks up templates in: DB (ProvisioningTemplate) first, then file-based config_templates/.
"""
from __future__ import annotations
import os
import logging
from pathlib import Path

from jinja2 import (
    Environment, FileSystemLoader, BaseLoader, TemplateNotFound,
    select_autoescape, StrictUndefined,
)

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / 'config_templates'


class DBLoader(BaseLoader):
    """Loads templates from the ProvisioningTemplate DB model."""

    def get_source(self, environment, template):
        try:
            from .models import ProvisioningTemplate
            tmpl = ProvisioningTemplate.objects.get(name=template, is_active=True)
            source = tmpl.content
            return source, f'db:{template}', lambda: False
        except Exception:
            raise TemplateNotFound(template)


def _build_env(use_strict: bool = False) -> Environment:
    loaders = [DBLoader(), FileSystemLoader(str(TEMPLATES_DIR))]
    from jinja2 import ChoiceLoader
    env = Environment(
        loader=ChoiceLoader(loaders),
        autoescape=False,        # network configs are not HTML
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
        undefined=StrictUndefined if use_strict else environment_undefined(),
    )
    # Custom filters
    env.filters['upper'] = str.upper
    env.filters['lower'] = str.lower
    return env


def environment_undefined():
    from jinja2 import Undefined
    return Undefined


def build_context(device) -> dict:
    """Build the standard template context from a Device instance."""
    return {
        'device':      device,
        'hostname':    device.hostname,
        'ip_address':  device.ip_address,
        'wan_ip':      device.wan_ip or '',
        'loopback_ip': device.loopback_ip or '',
        'site':        device.site,
        'site_label':  device.get_site_display(),
        'device_type': device.device_type,
        'vendor':      device.vendor,
        'model':       device.model,
        'os_version':  device.os_version,
        'snmp_community': device.snmp_community,
        'ssh_username': device.ssh_username,
        # Topology constants
        'MGMT_NETWORK': '192.168.100.0/24',
        'NTP_SERVER':   '192.168.100.1',
        'SYSLOG_SERVER': '192.168.100.1',
    }


def render_template(template_name: str, device, extra_context: dict | None = None) -> str:
    """
    Render a named Jinja2 template for a device.
    Returns the rendered string.
    Raises TemplateNotFound or jinja2.TemplateSyntaxError on failure.
    """
    env  = _build_env()
    tmpl = env.get_template(template_name)
    ctx  = build_context(device)
    if extra_context:
        ctx.update(extra_context)
    return tmpl.render(**ctx)


def render_string(source: str, device, extra_context: dict | None = None) -> str:
    """Render an inline Jinja2 string (for DB templates during preview)."""
    env  = _build_env()
    tmpl = env.from_string(source)
    ctx  = build_context(device)
    if extra_context:
        ctx.update(extra_context)
    return tmpl.render(**ctx)


def list_file_templates() -> list[dict]:
    """Return metadata for all file-based templates."""
    templates = []
    if not TEMPLATES_DIR.exists():
        return templates
    for path in sorted(TEMPLATES_DIR.glob('*.j2')):
        templates.append({
            'name':     path.name,
            'stem':     path.stem,
            'size':     path.stat().st_size,
            'source':   'file',
        })
    return templates


def list_all_templates() -> list[dict]:
    """Return file-based + active DB templates."""
    result = list_file_templates()
    try:
        from .models import ProvisioningTemplate
        for t in ProvisioningTemplate.objects.filter(is_active=True):
            result.append({
                'name':   t.name,
                'stem':   t.name,
                'source': 'db',
                'device_type': t.device_type,
                'site':        t.site,
                'description': t.description,
            })
    except Exception:
        pass
    return result
