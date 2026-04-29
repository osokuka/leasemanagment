from django.core.management.base import BaseCommand
from django.db import transaction
from locations.models import Meter, MeterLedger


class Command(BaseCommand):
    help = 'Merge orphan KESCO meters into their linked counterparts.'

    def handle(self, *args, **options):
        # Find all meters with kesco_debitor_id
        linked = Meter.objects.exclude(kesco_debitor_id__isnull=True).exclude(kesco_debitor_id='')

        for lm in linked:
            # Find orphan with matching serial pattern
            orphan_serial = f"KESCO-{lm.kesco_debitor_id}"
            orphan = Meter.objects.filter(serial_number=orphan_serial).first()
            if orphan and orphan.pk != lm.pk:
                self.stdout.write(
                    self.style.WARNING(
                        f'Merging orphan "{orphan.name}" (pk={orphan.pk}) → "{lm.name}" (pk={lm.pk})'
                    )
                )
                self._merge_orphan(orphan, lm)

        # Also delete any meters whose name still has the old dash-separated format
        # and have no kesco_debitor_id
        old_meters = Meter.objects.filter(name__contains=' | ')
        for old in old_meters:
            self.stdout.write(self.style.ERROR(f'Deleting old meter: "{old.name}" (pk={old.pk})'))
            MeterLedger.objects.filter(meter=old).delete()
            old.delete()

        self.stdout.write(self.style.SUCCESS('Cleanup complete.'))

    @transaction.atomic
    def _merge_orphan(self, orphan, target):
        for ledger in MeterLedger.objects.filter(meter=orphan):
            MeterLedger.objects.update_or_create(
                meter=target,
                month=ledger.month,
                year=ledger.year,
                defaults={
                    'reading': ledger.reading,
                    'billed_amount': ledger.billed_amount,
                    'settled_at': ledger.settled_at,
                },
            )
        orphan.delete()
