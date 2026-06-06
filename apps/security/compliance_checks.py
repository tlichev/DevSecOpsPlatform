"""
Built-in compliance rules seed data.
Run: python manage.py seed_compliance_rules
"""
import re
import logging

logger = logging.getLogger(__name__)

BUILTIN_RULES = [
    {
        "name": "SSH v2 Enabled",
        "description": "Ensure SSH version 2 is the only allowed protocol",
        "check_command": "show ip ssh",
        "expected_pattern": r"SSH Enabled - version 2\.0",
        "must_match": True,
        "severity": "critical",
        "remediation": "ip ssh version 2",
    },
    {
        "name": "Telnet Disabled on VTY",
        "description": "VTY lines must not allow Telnet",
        "check_command": "show running-config | section line vty",
        "expected_pattern": r"transport input telnet",
        "must_match": False,  # must NOT match — telnet should not appear
        "severity": "critical",
        "remediation": "line vty 0 4\n transport input ssh",
    },
    {
        "name": "SNMP v3 Configured",
        "description": "SNMP v3 must be configured for secure management",
        "check_command": "show running-config | include snmp-server user",
        "expected_pattern": r"snmp-server user .+ v3",
        "must_match": True,
        "severity": "high",
        "remediation": "",
    },
    {
        "name": "ACL on VTY Lines",
        "description": "Access control list restricting VTY access must be applied",
        "check_command": "show running-config | section line vty",
        "expected_pattern": r"access-class \S+ in",
        "must_match": True,
        "severity": "high",
        "remediation": "line vty 0 4\n access-class MGMT_ACCESS in",
    },
    {
        "name": "Service Password Encryption",
        "description": "service password-encryption must be enabled",
        "check_command": "show running-config | include service password-encryption",
        "expected_pattern": r"service password-encryption",
        "must_match": True,
        "severity": "high",
        "remediation": "service password-encryption",
    },
    {
        "name": "HTTP Server Disabled",
        "description": "ip http server must be disabled",
        "check_command": "show running-config | include ip http server",
        "expected_pattern": r"^no ip http server|^ip http server",
        "must_match": False,
        "severity": "medium",
        "remediation": "no ip http server\nno ip http secure-server",
    },
    {
        "name": "Logging Enabled",
        "description": "Logging buffered must be configured",
        "check_command": "show running-config | include logging buffered",
        "expected_pattern": r"logging buffered",
        "must_match": True,
        "severity": "medium",
        "remediation": "logging buffered 16384",
    },
    {
        "name": "Banner MOTD Configured",
        "description": "A warning banner must be present",
        "check_command": "show running-config | include banner motd",
        "expected_pattern": r"banner motd",
        "must_match": True,
        "severity": "low",
        "remediation": "",
    },
]


def evaluate_rule(output: str, pattern: str, must_match: bool) -> bool:
    matched = bool(re.search(pattern, output, re.MULTILINE | re.IGNORECASE))
    return matched if must_match else not matched
