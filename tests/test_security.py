import pytest
from apps.security.compliance_checks import evaluate_rule, BUILTIN_RULES


class TestComplianceEvaluator:
    def test_ssh_v2_compliant(self):
        output = "SSH Enabled - version 2.0\nAuthentication timeout: 120 secs"
        assert evaluate_rule(output, r"SSH Enabled - version 2\.0", must_match=True) is True

    def test_ssh_v2_non_compliant(self):
        output = "SSH Enabled - version 1.99\nAuthentication timeout: 120 secs"
        assert evaluate_rule(output, r"SSH Enabled - version 2\.0", must_match=True) is False

    def test_telnet_disabled_compliant(self):
        # "transport input ssh" — telnet pattern must NOT match
        output = "line vty 0 4\n login local\n transport input ssh"
        assert evaluate_rule(output, r"transport input telnet", must_match=False) is True

    def test_telnet_disabled_non_compliant(self):
        output = "line vty 0 4\n transport input telnet ssh"
        assert evaluate_rule(output, r"transport input telnet", must_match=False) is False

    def test_all_builtin_rules_have_required_fields(self):
        required_keys = {"name", "description", "check_command", "expected_pattern", "must_match", "severity"}
        for rule in BUILTIN_RULES:
            missing = required_keys - rule.keys()
            assert not missing, f"Rule '{rule.get('name')}' missing: {missing}"

    def test_builtin_rules_severity_valid(self):
        valid_severities = {"critical", "high", "medium", "low"}
        for rule in BUILTIN_RULES:
            assert rule["severity"] in valid_severities, f"Invalid severity in rule {rule['name']}"


@pytest.mark.django_db
class TestComplianceRuleAPI:
    def test_seed_command_creates_rules(self):
        from django.core.management import call_command
        from apps.security.models import ComplianceRule

        call_command("seed_compliance_rules")
        assert ComplianceRule.objects.count() == len(BUILTIN_RULES)

    def test_seed_command_idempotent(self):
        from django.core.management import call_command
        from apps.security.models import ComplianceRule

        call_command("seed_compliance_rules")
        call_command("seed_compliance_rules")
        assert ComplianceRule.objects.count() == len(BUILTIN_RULES)
