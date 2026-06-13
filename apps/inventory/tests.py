from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from apps.inventory.models import Device

User = get_user_model()


class DeviceModelTest(TestCase):
    def setUp(self):
        self.device = Device.objects.create(
            hostname='SW-SOFIA-01',
            management_ip='192.168.100.10',
            site='sofia',
            device_type='switch',
        )

    def test_device_str_contains_hostname(self):
        self.assertIn('SW-SOFIA-01', str(self.device))

    def test_device_status_defaults_to_unknown(self):
        self.assertEqual(self.device.status, 'unknown')

    def test_device_site(self):
        self.assertEqual(self.device.site, 'sofia')

    def test_device_type(self):
        self.assertEqual(self.device.device_type, 'switch')

    def test_device_management_ip(self):
        self.assertEqual(self.device.management_ip, '192.168.100.10')


class DeviceAPITest(TestCase):
    def setUp(self):
        self.client   = APIClient()
        self.admin    = User.objects.create_user('inv_admin', password='testpass123', role='admin')
        self.engineer = User.objects.create_user('inv_eng',   password='testpass123', role='engineer')
        self.readonly = User.objects.create_user('inv_ro',    password='testpass123', role='readonly')

        self.device = Device.objects.create(
            hostname='R-BURGAS-01',
            management_ip='192.168.100.20',
            site='burgas',
            device_type='router',
        )

    def test_device_list_requires_auth(self):
        resp = self.client.get('/api/devices/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_device_list_returns_200_for_authenticated_user(self):
        self.client.force_authenticate(user=self.readonly)
        resp = self.client.get('/api/devices/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('results', resp.data)
        self.assertEqual(resp.data['count'], 1)

    def test_device_retrieve(self):
        self.client.force_authenticate(user=self.readonly)
        resp = self.client.get(f'/api/devices/{self.device.pk}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['hostname'], 'R-BURGAS-01')

    def test_device_create_requires_engineer(self):
        self.client.force_authenticate(user=self.readonly)
        resp = self.client.post('/api/devices/', {
            'hostname': 'SW-PLOVDIV-01',
            'management_ip': '192.168.100.30',
            'site': 'plovdiv',
            'device_type': 'switch',
        })
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_device_create_as_engineer(self):
        self.client.force_authenticate(user=self.engineer)
        resp = self.client.post('/api/devices/', {
            'hostname': 'SW-PLOVDIV-01',
            'management_ip': '192.168.100.30',
            'site': 'plovdiv',
            'device_type': 'switch',
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Device.objects.count(), 2)

    def test_device_filter_by_site(self):
        Device.objects.create(
            hostname='FW-SOFIA-01',
            management_ip='192.168.100.11',
            site='sofia',
            device_type='firewall_primary',
        )
        self.client.force_authenticate(user=self.readonly)
        resp = self.client.get('/api/devices/?site=sofia')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['count'], 1)
        self.assertEqual(resp.data['results'][0]['site'], 'sofia')


class DashboardStatsTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user   = User.objects.create_user('stats_user', password='testpass123', role='readonly')
        Device.objects.create(
            hostname='R-SOFIA-01',
            management_ip='192.168.100.1',
            site='sofia',
            device_type='router',
            status='up',
        )
        Device.objects.create(
            hostname='R-BURGAS-01',
            management_ip='192.168.100.2',
            site='burgas',
            device_type='router',
            status='down',
        )

    def test_stats_requires_auth(self):
        resp = self.client.get('/api/dashboard/stats/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_stats_returns_expected_keys(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.get('/api/dashboard/stats/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('total', resp.data)
        self.assertIn('up', resp.data)
        self.assertIn('down', resp.data)

    def test_stats_counts_match_db(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.get('/api/dashboard/stats/')
        self.assertEqual(resp.data['total'], 2)
        self.assertEqual(resp.data['up'],    1)
        self.assertEqual(resp.data['down'],  1)
