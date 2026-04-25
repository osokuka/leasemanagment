"""
Management command to auto-generate missing lease ledger entries.
For each lease, creates a LedgerLedger entry for every month from
the lease start_date up to the current month (or end_date, whichever is sooner).
"""
from datetime import date
from decimal import Decimal
from django.core.management.base import BaseCommand
from locations.models import Lease, LeaseLedger, LeaseStatus


class Command(BaseCommand):
    help = 'Auto-generate missing lease ledger entries for all active leases.'

    def handle(self, *args, **options):
        today = date.today()
        total_created = 0

        for lease in Lease.objects.all():
            if not lease.start_date:
                continue

            # Determine the last month to generate
            if lease.end_date and lease.end_date < today:
                last_date = lease.end_date
            else:
                last_date = today

            start_year = lease.start_date.year
            start_month = lease.start_date.month
            end_year = last_date.year
            end_month = last_date.month

            year, month = start_year, start_month
            advance_remaining = lease.advance_months or 0
            
            # Count existing entries to determine how many advance months are already accounted for
            existing_entries = list(
                LeaseLedger.objects.filter(lease=lease).order_by('year', 'month')
            )
            # If entries exist, they may already have payments. Skip advance for months that exist.
            existing_months = set((e.year, e.month) for e in existing_entries)
            
            # Decrement advance for existing months from the start
            temp_year, temp_month = start_year, start_month
            while advance_remaining > 0 and (temp_year, temp_month) <= (end_year, end_month):
                if (temp_year, temp_month) in existing_months:
                    # This month already has an entry - its payment is already recorded
                    advance_remaining -= 1
                if temp_month == 12:
                    temp_month = 1
                    temp_year += 1
                else:
                    temp_month += 1
            
            while (year, month) <= (end_year, end_month):
                # Check if entry already exists
                exists = LeaseLedger.objects.filter(
                    lease=lease, month=month, year=year
                ).exists()

                if not exists:
                    # Mark advance months as paid
                    if advance_remaining > 0:
                        amount_paid = lease.monthly_payment or Decimal('0')
                        advance_remaining -= 1
                    else:
                        amount_paid = Decimal('0')
                    LeaseLedger.objects.create(
                        lease=lease,
                        month=month,
                        year=year,
                        amount_due=lease.monthly_payment or Decimal('0'),
                        amount_paid=amount_paid,
                    )
                    total_created += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  Created: {lease.display_id} — {month:02d}/{year}'
                        )
                    )

                # Advance to next month
                if month == 12:
                    month = 1
                    year += 1
                else:
                    month += 1

        self.stdout.write(self.style.SUCCESS(f'\nDone. {total_created} ledger entries created.'))
