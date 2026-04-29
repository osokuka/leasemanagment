import json
from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from accounts.models import ApiKeyScope, User, UserApiKey
from locations.models import (
    Lease,
    LeaseLedger,
    Location,
    Meter,
    MeterLedger,
    MeterType,
    ReadingMetric,
    Unit,
    UnitType,
)


class SettlementApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='settlement-owner', password='test-pass')
        self.api_key, self.raw_key = UserApiKey.create_key(
            user=self.user,
            name='Settlement tool',
            scope=ApiKeyScope.SETTLEMENT_WRITE,
        )
        self.lease = Lease.objects.create(
            name='Tenant Settlement',
            start_date=date(2026, 4, 1),
            monthly_payment=Decimal('500.00'),
            advance_months=0,
        )
        self.lease_ledger = LeaseLedger.objects.get(lease=self.lease, month=4, year=2026)
        self.lease_ledger.amount_due = Decimal('500.00')
        self.lease_ledger.amount_paid = Decimal('0')
        self.lease_ledger.save()

        self.location = Location.objects.create(name='Building', address='Address')
        self.unit = Unit.objects.create(
            location=self.location,
            lease=self.lease,
            name='Unit 1',
            sqm=50,
            unit_type=UnitType.APARTMENT,
        )
        self.meter = Meter.objects.create(
            unit=self.unit,
            name='DFE160',
            meter_type=MeterType.ELECTRIC,
            reading_metric=ReadingMetric.KWH,
            kesco_debitor_id='160',
        )
        self.meter_ledger = MeterLedger.objects.create(
            meter=self.meter,
            month=4,
            year=2026,
            reading=Decimal('123.45'),
            billed_amount=Decimal('111.75'),
        )

    def test_settle_lease_payment_for_period_by_display_id(self):
        response = self.client.post(
            reverse('locations:api_lease_payment_settle', args=[self.lease.display_id]),
            data=json.dumps({'period': '2026-04', 'payment_date': '2026-04-27'}),
            content_type='application/json',
            HTTP_X_API_KEY=self.raw_key,
        )

        self.assertEqual(response.status_code, 200)
        self.lease_ledger.refresh_from_db()
        self.assertEqual(self.lease_ledger.amount_paid, Decimal('500.00'))
        self.assertEqual(self.lease_ledger.status, 'paid')
        self.assertEqual(self.lease_ledger.payment_date, date(2026, 4, 27))

    def test_settle_electric_debt_for_lease_period(self):
        response = self.client.post(
            reverse('locations:api_electric_debt_settle'),
            data=json.dumps({'lease_id': self.lease.display_id, 'month': 4, 'year': 2026}),
            content_type='application/json',
            HTTP_X_API_KEY=self.raw_key,
        )

        self.assertEqual(response.status_code, 200)
        self.meter_ledger.refresh_from_db()
        self.assertEqual(self.meter_ledger.billed_amount, Decimal('0.00'))
        self.assertIsNotNone(self.meter_ledger.settled_at)
        self.assertEqual(response.json()['results'][0]['status'], 'settled')

    def test_settle_electric_debt_by_kesco_debitor_id(self):
        response = self.client.post(
            reverse('locations:api_electric_debt_settle'),
            data=json.dumps({'kesco_debitor_id': '160', 'period': '2026-04'}),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {self.raw_key}',
        )

        self.assertEqual(response.status_code, 200)
        self.meter_ledger.refresh_from_db()
        self.assertEqual(self.meter_ledger.billed_amount, Decimal('0.00'))

    def test_report_key_cannot_settle(self):
        _, raw_key = UserApiKey.create_key(
            user=self.user,
            name='Read only',
            scope=ApiKeyScope.LEASE_REPORT_READ,
        )
        response = self.client.post(
            reverse('locations:api_lease_payment_settle', args=[self.lease.display_id]),
            data=json.dumps({'period': '2026-04'}),
            content_type='application/json',
            HTTP_X_API_KEY=raw_key,
        )

        self.assertEqual(response.status_code, 403)
