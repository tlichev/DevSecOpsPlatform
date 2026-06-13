from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from apps.provisioning.models import ProvisioningTemplate, AuditLog
from apps.inventory.models import Device

User = get_user_model()


class ProvisioningTemplateModelTest(TestCase):
    def setUp(self):
        self.template = ProvisioningTemplate.objects.create(
            name='ntp-config',
            description='Configure NTP servers on Cisco IOS',
            device_types=['router', 'switch'],
            content='ntp server {{ ntp_primary }}\nntp server {{ ntp_secondary }}\n',
        )

    def test_template_str_contains_name(self):
        self.assertIn('ntp-config', str(self.template))

    def test_template_content_not_empty(self):
        self.assertTrue(self.template.content.strip())

    def test_template_device_types_is_list(self):
        self.assertIsInstance(self.template.device_types, list)
        self.assertIn('router', self.template.device_types)

    def test_template_name_unique(self):
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            ProvisioningTemplate.objects.create(
                name='ntp-config',
                content='duplicate',
            )


class ProvisioningTemplateAPITest(TestCase):
    def setUp(self):
        self.client   = APIClient()
        self.admin    = User.objects.create_user('prov_admin', password='testpass123', role='admin')
        self.engineer = User.objects.create_user('prov_eng',   password='testpass123', role='engineer')
        self.readonly = User.objects.create_user('prov_ro',    password='testpass123', role='readonly')
        self.template = ProvisioningTemplate.objects.create(
            name='banner-motd',
            description='MOTD banner',
            content='banner motd ^{{ banner_text }}^',
        )

    def test_list_requires_auth(self):
        resp = self.client.get('/api/provisioning/templates/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_readable_by_readonly(self):
        self.client.force_authenticate(user=self.readonly)
        resp = self.client.get('/api/provisioning/templates/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['count'], 1)

    def test_create_blocked_for_readonly(self):
        self.client.force_authenticate(user=self.readonly)
        resp = self.client.post('/api/provisioning/templates/', {
            'name': 'blocked', 'description': 'blocked', 'content': 'blocked',
        })
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_allowed_for_engineer(self):
        self.client.force_authenticate(user=self.engineer)
        resp = self.client.post('/api/provisioning/templates/', {
            'name': 'ospf-auth',
            'description': 'OSPF MD5 auth',
            'content': 'router ospf {{ process_id }}\n area 0 authentication message-digest\n',
            'device_types': ['router'],
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ProvisioningTemplate.objects.count(), 2)

    def test_delete_blocked_for_readonly(self):
        self.client.force_authenticate(user=self.readonly)
        resp = self.client.delete(f'/api/provisioning/templates/{self.template.pk}/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_allowed_for_admin(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.delete(f'/api/provisioning/templates/{self.template.pk}/')
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)


class AuditLogModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('audit_user', password='testpass123', role='engineer')
        self.device = Device.objects.create(
            hostname='SW-TEST-01',
            management_ip='192.168.100.50',
            site='sofia',
            device_type='switch',
        )
        self.template = ProvisioningTemplate.objects.create(
            name='test-template',
            content='hostname {{ hostname }}',
        )
        self.log = AuditLog.objects.create(
            device=self.device,
            template=self.template,
            triggered_by=self.user,
            status='success',
            config_diff='--- before\n+++ after\n+hostname SW-TEST-01\n',
        )

    def test_audit_log_str(self):
        s = str(self.log)
        self.assertIn('SW-TEST-01', s)

    def test_audit_log_status(self):
        self.assertEqual(self.log.status, 'success')

    def test_audit_log_linked_to_user(self):
        self.assertEqual(self.log.triggered_by, self.user)

    def test_audit_log_has_diff(self):
        self.assertIn('+hostname', self.log.config_diff)


class AuditLogAPITest(TestCase):
    def setUp(self):
        self.client   = APIClient()
        self.readonly = User.objects.create_user('auditro', password='testpass123', role='readonly')

    def test_audit_list_requires_auth(self):
        resp = self.client.get('/api/provisioning/audit/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_audit_list_readable_by_readonly(self):
        self.client.force_authenticate(user=self.readonly)
        resp = self.client.get('/api/provisioning/audit/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
