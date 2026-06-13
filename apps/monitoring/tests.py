import json

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from apps.monitoring.models import Alert
from apps.inventory.models import Device

User = get_user_model()

# Minimal AlertManager-style payload
_FIRING_PAYLOAD = {
    'receiver': 'django-webhook',
    'status': 'firing',
    'alerts': [
        {
            'status': 'firing',
            'labels': {
                'alertname': 'DeviceDown',
                'instance': '192.168.100.10',
                'site': 'sofia',
                'severity': 'critical',
            },
            'annotations': {
                'summary': 'Device 192.168.100.10 is unreachable',
                'description': 'ICMP and SNMP checks are failing.',
            },
            'startsAt': '2024-01-01T00:00:00.000Z',
            'endsAt': '0001-01-01T00:00:00Z',
            'fingerprint': 'testfp-devicedown-001',
        }
    ],
}

_RESOLVED_PAYLOAD = {
    'receiver': 'django-webhook',
    'status': 'resolved',
    'alerts': [
        {
            'status': 'resolved',
            'labels': {
                'alertname': 'DeviceDown',
                'instance': '192.168.100.10',
                'site': 'sofia',
                'severity': 'critical',
            },
            'annotations': {
                'summary': 'Device 192.168.100.10 is back',
                'description': '',
            },
            'startsAt': '2024-01-01T00:00:00.000Z',
            'endsAt': '2024-01-01T00:05:00.000Z',
            'fingerprint': 'testfp-devicedown-001',
        }
    ],
}


class AlertWebhookTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        # Create matching device so _handle_device_down() has a target
        self.device = Device.objects.create(
            hostname='SW-SOFIA-01',
            management_ip='192.168.100.10',
            site='sofia',
            device_type='switch',
        )

    def _post(self, payload):
        return self.client.post(
            '/api/alerts/webhook/',
            data=json.dumps(payload),
            content_type='application/json',
        )

    def test_webhook_creates_alert(self):
        resp = self._post(_FIRING_PAYLOAD)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(Alert.objects.count(), 1)

    def test_webhook_correct_fingerprint(self):
        self._post(_FIRING_PAYLOAD)
        alert = Alert.objects.get(fingerprint='testfp-devicedown-001')
        self.assertEqual(alert.alertname, 'DeviceDown')
        self.assertEqual(alert.instance,  '192.168.100.10')
        self.assertEqual(alert.site,      'sofia')
        self.assertEqual(alert.severity,  'critical')

    def test_webhook_idempotent_same_fingerprint(self):
        self._post(_FIRING_PAYLOAD)
        self._post(_FIRING_PAYLOAD)
        self.assertEqual(Alert.objects.count(), 1)

    def test_webhook_resolves_existing_alert(self):
        self._post(_FIRING_PAYLOAD)
        self._post(_RESOLVED_PAYLOAD)
        alert = Alert.objects.get(fingerprint='testfp-devicedown-001')
        self.assertEqual(alert.status, 'resolved')

    def test_webhook_no_auth_required(self):
        # AlertManager calls the webhook without Django session/JWT
        resp = self._post(_FIRING_PAYLOAD)
        self.assertNotEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class AlertViewSetTest(TestCase):
    def setUp(self):
        self.client  = APIClient()
        self.admin   = User.objects.create_user('alert_admin', password='testpass123', role='admin')
        self.readonly = User.objects.create_user('alert_ro',   password='testpass123', role='readonly')
        self.alert = Alert.objects.create(
            fingerprint='testfp-iface-001',
            alertname='InterfaceDown',
            instance='192.168.100.11',
            severity='warning',
            status='firing',
        )

    def test_alert_list_requires_auth(self):
        resp = self.client.get('/api/monitoring/alerts/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_alert_list_authenticated(self):
        self.client.force_authenticate(user=self.readonly)
        resp = self.client.get('/api/monitoring/alerts/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['count'], 1)

    def test_acknowledge_alert(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            f'/api/monitoring/alerts/{self.alert.pk}/acknowledge/',
            {'ack_note': 'Investigating now'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.alert.refresh_from_db()
        self.assertTrue(self.alert.acknowledged)
        self.assertEqual(self.alert.acknowledged_by, self.admin)

    def test_acknowledge_already_acked(self):
        self.client.force_authenticate(user=self.admin)
        self.client.post(
            f'/api/monitoring/alerts/{self.alert.pk}/acknowledge/',
            {'ack_note': 'First ack'},
            format='json',
        )
        resp = self.client.post(
            f'/api/monitoring/alerts/{self.alert.pk}/acknowledge/',
            {'ack_note': 'Second ack'},
            format='json',
        )
        # Second ack should succeed (idempotent) or return 400
        self.assertIn(resp.status_code, [
            status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST
        ])

    def test_filter_alerts_by_status(self):
        Alert.objects.create(
            fingerprint='testfp-resolved-001',
            alertname='HighCPU',
            instance='192.168.100.12',
            severity='warning',
            status='resolved',
        )
        self.client.force_authenticate(user=self.readonly)
        resp = self.client.get('/api/monitoring/alerts/?status=firing')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for a in resp.data['results']:
            self.assertEqual(a['status'], 'firing')
