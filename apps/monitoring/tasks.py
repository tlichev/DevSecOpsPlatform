import logging

from celery import shared_task

logger = logging.getLogger(__name__)

PROMETHEUS_URL = 'http://prometheus:9090'


@shared_task(name='monitoring.sync_alerts', queue='monitoring')
def sync_prometheus_alerts():
    """
    Poll Prometheus /api/v1/alerts and update the Alert model:
    - Create new firing alerts (deduplicated by fingerprint).
    - Mark as resolved any that are no longer firing.
    Does NOT replace the AlertManager webhook — this is a reconciliation fallback.
    """
    import requests
    from django.utils.dateparse import parse_datetime
    from .models import Alert

    try:
        resp = requests.get(f'{PROMETHEUS_URL}/api/v1/alerts', timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.warning('sync_prometheus_alerts: failed to reach Prometheus: %s', exc)
        return {'error': str(exc)}

    prom_alerts = data.get('data', {}).get('alerts', [])
    firing_fingerprints = set()
    created = resolved = 0

    for pa in prom_alerts:
        labels      = pa.get('labels', {})
        annotations = pa.get('annotations', {})
        fingerprint = pa.get('fingerprint', '')
        status      = pa.get('state', 'firing')    # Prometheus uses 'state', not 'status'
        starts_at   = parse_datetime(pa.get('activeAt', '')) if pa.get('activeAt') else None

        if status == 'firing':
            firing_fingerprints.add(fingerprint)

        alert, new = Alert.objects.get_or_create(
            fingerprint=fingerprint,
            defaults={
                'alertname':   labels.get('alertname', ''),
                'instance':    labels.get('instance', ''),
                'site':        labels.get('site', ''),
                'severity':    labels.get('severity', 'warning'),
                'status':      'firing' if status == 'firing' else 'resolved',
                'summary':     annotations.get('summary', ''),
                'description': annotations.get('description', ''),
                'raw_labels':  labels,
                'raw_payload': pa,
                'starts_at':   starts_at,
            },
        )
        if new:
            created += 1

    # Resolve alerts that are no longer firing in Prometheus
    to_resolve = Alert.objects.filter(
        status='firing'
    ).exclude(fingerprint__in=firing_fingerprints)
    for alert in to_resolve:
        alert.resolve()
        resolved += 1

    logger.info('sync_prometheus_alerts: created=%d resolved=%d', created, resolved)
    return {'created': created, 'resolved': resolved}


@shared_task(name='monitoring.mark_devices_from_alerts', queue='monitoring')
def mark_devices_from_alerts():
    """
    Read active DeviceDown alerts and mark corresponding Device records as down.
    Restores devices to 'unknown' when the alert resolves.
    """
    from apps.inventory.models import Device
    from .models import Alert

    # Find all firing DeviceDown alerts
    firing_ips = set(
        Alert.objects.filter(alertname='DeviceDown', status='firing')
        .values_list('instance', flat=True)
    )

    # Mark down
    if firing_ips:
        Device.objects.filter(ip_address__in=firing_ips, status='up').update(status='down')

    # Restore devices that are no longer in a DeviceDown alert
    all_monitored = set(
        Alert.objects.filter(alertname='DeviceDown')
        .values_list('instance', flat=True)
    )
    recovering_ips = all_monitored - firing_ips
    if recovering_ips:
        Device.objects.filter(ip_address__in=recovering_ips, status='down').update(status='unknown')

    return {'firing': len(firing_ips), 'recovering': len(recovering_ips)}
