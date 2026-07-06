from django.core.management.base import BaseCommand

from apps.security.models import ComplianceResult, ComplianceRule
from apps.inventory.models import Device


class Command(BaseCommand):
    help = (
        'Seed passing ComplianceResult records for all devices × active rules '
        '(demo/test only — does not SSH to any device).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Delete ALL existing ComplianceResult records before seeding.',
        )

    def handle(self, *args, **options):
        rules   = list(ComplianceRule.objects.filter(is_active=True))
        devices = list(Device.objects.all())

        if not rules:
            self.stdout.write(self.style.WARNING('No active compliance rules found — nothing to seed.'))
            return
        if not devices:
            self.stdout.write(self.style.WARNING('No devices found — nothing to seed.'))
            return

        if options['clear']:
            deleted, _ = ComplianceResult.objects.all().delete()
            self.stdout.write(self.style.WARNING(f'Cleared {deleted} existing result(s).'))

        to_create = []
        skipped   = 0

        for device in devices:
            for rule in rules:
                # Mirror the real task's device_type filter
                if rule.device_types and device.device_type not in rule.device_types:
                    skipped += 1
                    continue
                to_create.append(ComplianceResult(
                    device=device,
                    rule=rule,
                    status=ComplianceResult.STATUS_PASS,
                    evidence='[TEST] Forced pass — demo only',
                    task_id='seed_compliance_pass',
                ))

        ComplianceResult.objects.bulk_create(to_create)

        self.stdout.write(self.style.SUCCESS(
            f'Seeded {len(to_create)} passing result(s) across '
            f'{len(devices)} device(s) and {len(rules)} rule(s).'
            + (f' ({skipped} skipped by device_type filter)' if skipped else '')
        ))
