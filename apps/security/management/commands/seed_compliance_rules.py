from django.core.management.base import BaseCommand
from apps.security.models import ComplianceRule
from apps.security.compliance_checks import BUILTIN_RULES


class Command(BaseCommand):
    help = "Seed the database with built-in compliance rules"

    def handle(self, *args, **options):
        created = 0
        updated = 0
        for rule_data in BUILTIN_RULES:
            obj, was_created = ComplianceRule.objects.update_or_create(
                name=rule_data["name"],
                defaults=rule_data,
            )
            if was_created:
                created += 1
            else:
                updated += 1
        self.stdout.write(
            self.style.SUCCESS(f"Compliance rules seeded: {created} created, {updated} updated.")
        )
