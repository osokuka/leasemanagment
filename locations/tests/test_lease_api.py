import json
from datetime import date
from decimal import Decimal

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import ApiKeyScope, User, UserApiKey
from locations.models import Lease, LeaseLedger


class LeaseStatusApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='report-owner', password='test-pass')
        self.api_key, self.raw_key = UserApiKey.create_key(
            user=self.user,
            name='Lease reports',
            scope=ApiKeyScope.LEASE_REPORT_READ,
        )
        self.lease = Lease.objects.create(
            name='Tenant Alpha',
            contact='Alpha Contact',
            phone='123',
            email='tenant@example.com',
            start_date=date(2026, 4, 1),
            monthly_payment=Decimal('500.00'),
            advance_months=0,
        )
        ledger = LeaseLedger.objects.get(lease=self.lease, month=4, year=2026)
        ledger.amount_due = Decimal('500.00')
        ledger.amount_paid = Decimal('200.00')
        ledger.save()

    def test_status_search_returns_debt_summary(self):
        response = self.client.get(
            reverse('locations:api_lease_status'),
            {'search': 'Alpha'},
            HTTP_X_API_KEY=self.raw_key,
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['summary']['leases_with_debt'], 1)
        self.assertEqual(data['summary']['total_debt'], '300.00')
        self.assertEqual(data['results'][0]['display_id'], self.lease.display_id)
        self.assertTrue(data['results'][0]['has_debt'])

    def test_kesco_key_cannot_read_lease_status(self):
        _, raw_key = UserApiKey.create_key(
            user=self.user,
            name='KESCO',
            scope=ApiKeyScope.KESCO_METER_WRITE,
        )

        response = self.client.get(
            reverse('locations:api_lease_status'),
            HTTP_X_API_KEY=raw_key,
        )

        self.assertEqual(response.status_code, 403)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_report_endpoint_accepts_display_id_and_sends_lease_report(self):
        response = self.client.post(
            reverse('locations:api_lease_report', args=[self.lease.display_id]),
            data=json.dumps({'email_to': 'owner@example.com'}),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {self.raw_key}',
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['sent_to'], 'owner@example.com')
        self.assertEqual(data['report']['balance'], '300.00')
        self.assertEqual(len(data['report']['ledgers']), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.lease.display_id, mail.outbox[0].subject)

    def test_report_endpoint_still_accepts_uuid(self):
        response = self.client.get(
            reverse('locations:api_lease_report', args=[self.lease.uuid]),
            HTTP_X_API_KEY=self.raw_key,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['report']['display_id'], self.lease.display_id)
