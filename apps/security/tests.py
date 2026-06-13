from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from apps.security.models import ComplianceRule, GoldenConfig
from apps.inventory.models import Device

User = get_user_model()

# Representative running-config excerpt (Cisco IOS style)
COMPLIANT_CONFIG = """
!
hostname R-SOFIA-01
!
ip ssh version 2
ip ssh authentication-retries 3
!
aaa new-model
aaa authentication login default local
!
ntp server 10.0.0.1
ntp server 10.0.0.2
!
service password-encryption
service timestamps log datetime msec
!
login banner ^
  Authorized access only. All activity is monitored.
^
!
no service telnet
!
router ospf 1
 area 0 authentication message-digest
!
snmp-server community public RO SNMP_ACL
!
logging host 10.0.0.5
"""

NON_COMPLIANT_CONFIG = """
!
hostname R-SOFIA-02
ip ssh version 1
transport input telnet
enable password cisco
no aaa new-model
"""


class ComplianceRuleCheckTest(TestCase):
    def _make_rule(self, pattern, match_means_pass=True, severity='warning', category='access'):
        return ComplianceRule(
            name='test-rule',
            pattern=pattern,
            match_means_pass=match_means_pass,
            severity=severity,
            category=category,
        )

    # Presence checks (match_means_pass=True)

    def test_presence_check_passes_when_found(self):
        rule = self._make_rule(r'ip ssh version 2', match_means_pass=True)
        self.assertTrue(rule.evaluate(COMPLIANT_CONFIG))

    def test_presence_check_fails_when_absent(self):
        rule = self._make_rule(r'ip ssh version 2', match_means_pass=True)
        self.assertFalse(rule.evaluate(NON_COMPLIANT_CONFIG))

    def test_aaa_new_model_present(self):
        rule = self._make_rule(r'aaa new-model', match_means_pass=True, severity='critical')
        self.assertTrue(rule.evaluate(COMPLIANT_CONFIG))
        self.assertFalse(rule.evaluate(NON_COMPLIANT_CONFIG))

    def test_ntp_server_present(self):
        rule = self._make_rule(r'ntp server \S+', match_means_pass=True)
        self.assertTrue(rule.evaluate(COMPLIANT_CONFIG))
        self.assertFalse(rule.evaluate(NON_COMPLIANT_CONFIG))

    def test_ospf_md5_auth_present(self):
        rule = self._make_rule(r'authentication message-digest', match_means_pass=True)
        self.assertTrue(rule.evaluate(COMPLIANT_CONFIG))
        self.assertFalse(rule.evaluate(NON_COMPLIANT_CONFIG))

    def test_service_password_encryption(self):
        rule = self._make_rule(r'service password-encryption', match_means_pass=True)
        self.assertTrue(rule.evaluate(COMPLIANT_CONFIG))
        self.assertFalse(rule.evaluate(NON_COMPLIANT_CONFIG))

    # Absence checks (match_means_pass=False)

    def test_telnet_disabled_passes_when_absent(self):
        rule = self._make_rule(r'transport input telnet', match_means_pass=False, severity='critical')
        self.assertTrue(rule.evaluate(COMPLIANT_CONFIG))

    def test_telnet_disabled_fails_when_present(self):
        rule = self._make_rule(r'transport input telnet', match_means_pass=False, severity='critical')
        self.assertFalse(rule.evaluate(NON_COMPLIANT_CONFIG))

    def test_enable_password_absent_passes(self):
        rule = self._make_rule(r'^enable password', match_means_pass=False, severity='critical')
        self.assertTrue(rule.evaluate(COMPLIANT_CONFIG))

    def test_enable_password_absent_fails_when_set(self):
        rule = self._make_rule(r'^enable password', match_means_pass=False, severity='critical')
        self.assertFalse(rule.evaluate(NON_COMPLIANT_CONFIG))

    # Case insensitivity

    def test_pattern_is_case_insensitive(self):
        rule = self._make_rule(r'IP SSH VERSION 2', match_means_pass=True)
        self.assertTrue(rule.evaluate(COMPLIANT_CONFIG))


class ComplianceRuleEvidenceTest(TestCase):
    def test_get_evidence_returns_matched_text(self):
        rule = ComplianceRule(
            name='NTP Server',
            pattern=r'ntp server \S+',
            match_means_pass=True,
            severity='warning',
            category='management',
        )
        evidence = rule.get_evidence(COMPLIANT_CONFIG)
        self.assertTrue(evidence.startswith('ntp server'))

    def test_get_evidence_returns_empty_when_no_match(self):
        rule = ComplianceRule(
            name='Missing',
            pattern=r'non-existent-feature xyz',
            match_means_pass=True,
            severity='info',
            category='management',
        )
        self.assertEqual(rule.get_evidence(COMPLIANT_CONFIG), '')

    def test_get_evidence_truncates_at_500_chars(self):
        long_pattern = r'hostname'
        rule = ComplianceRule(
            name='Hostname',
            pattern=long_pattern,
            match_means_pass=True,
            severity='info',
            category='management',
        )
        config = 'hostname ' + 'R' * 600
        evidence = rule.get_evidence(config)
        self.assertLessEqual(len(evidence), 500)


class GoldenConfigModelTest(TestCase):
    def test_golden_config_str(self):
        gc = GoldenConfig.objects.create(
            device_type='router',
            content='hostname {{ hostname }}\nip ssh version 2\n',
        )
        self.assertIn('router', str(gc))

    def test_golden_config_unique_per_device_type(self):
        GoldenConfig.objects.create(device_type='switch', content='! switch baseline')
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            GoldenConfig.objects.create(device_type='switch', content='! duplicate')


class ComplianceAPITest(TestCase):
    def setUp(self):
        self.client   = APIClient()
        self.engineer = User.objects.create_user('sec_eng', password='testpass123', role='engineer')
        self.readonly = User.objects.create_user('sec_ro',  password='testpass123', role='readonly')
        self.device   = Device.objects.create(
            hostname='R-SOFIA-01',
            management_ip='192.168.100.1',
            site='sofia',
            device_type='router',
        )
        self.rule = ComplianceRule.objects.create(
            name='SSH v2',
            pattern=r'ip ssh version 2',
            match_means_pass=True,
            severity='critical',
            category='access',
        )

    def test_rules_list_authenticated(self):
        self.client.force_authenticate(user=self.readonly)
        resp = self.client.get('/api/security/rules/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['count'], 1)

    def test_rules_create_requires_engineer(self):
        self.client.force_authenticate(user=self.readonly)
        resp = self.client.post('/api/security/rules/', {
            'name': 'NTP', 'pattern': r'ntp server',
            'match_means_pass': True, 'severity': 'warning', 'category': 'management',
        })
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_compliance_summary_authenticated(self):
        self.client.force_authenticate(user=self.readonly)
        resp = self.client.get('/api/security/compliance/summary/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
