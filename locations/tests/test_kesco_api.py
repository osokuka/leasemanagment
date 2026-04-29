import json

from django.test import TestCase
from django.urls import reverse

from accounts.models import ApiKeyScope, User, UserApiKey
from locations.models import Location, Meter, MeterLedger, MeterType, ReadingMetric, Unit, UnitType


class KescoMeterApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='api-owner', password='test-pass')
        self.api_key, self.raw_key = UserApiKey.create_key(
            user=self.user,
            name='KESCO tool',
            scope=ApiKeyScope.KESCO_METER_WRITE,
        )
        self.url = reverse('locations:api_kesco_meter_upsert')

    def test_rejects_missing_api_key(self):
        response = self.client.post(
            self.url,
            data=json.dumps({'kesco_debitor_id': '160'}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 401)

    def test_upserts_meter_and_ledger_with_scoped_api_key(self):
        payload = {
            'kesco_debitor_id': '160',
            'kesco_agency_id': 'DFE',
            'kesco_full_name': 'Test Consumer',
            'kesco_address': 'Test Address',
            'kesco_tariff_group': '4/02',
            'kesco_last_due_date': '2026-04-12T00:00:00',
            'ledger': {
                'month': 4,
                'year': 2026,
                'billed_amount': '111.75',
            },
        }

        response = self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_API_KEY=self.raw_key,
        )

        self.assertEqual(response.status_code, 200)
        meter = Meter.objects.get(kesco_debitor_id='160')
        self.assertEqual(meter.name, 'DFE160')
        self.assertEqual(meter.kesco_full_name, 'Test Consumer')
        ledger = MeterLedger.objects.get(meter=meter, month=4, year=2026)
        self.assertEqual(str(ledger.billed_amount), '111.75')

        payload['kesco_full_name'] = 'Updated Consumer'
        payload['ledger']['billed_amount'] = '99.50'
        response = self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {self.raw_key}',
        )

        self.assertEqual(response.status_code, 200)
        meter.refresh_from_db()
        ledger.refresh_from_db()
        self.assertEqual(meter.kesco_full_name, 'Updated Consumer')
        self.assertEqual(str(ledger.billed_amount), '99.50')
        self.assertEqual(Meter.objects.filter(kesco_debitor_id='160').count(), 1)

    def test_accepts_raw_kesco_debitors_and_creates_missing_meters_in_location_zero(self):
        location = Location.objects.create(
            name='Existing Location',
            address='Existing Address',
        )
        unit = Unit.objects.create(
            location=location,
            name='Existing Unit',
            sqm=10,
            unit_type=UnitType.APARTMENT,
        )
        existing = Meter.objects.create(
            unit=unit,
            name='Old Name',
            meter_type=MeterType.ELECTRIC,
            reading_metric=ReadingMetric.KWH,
            kesco_debitor_id='160',
        )
        payload = {
            'Data': {
                'debitors': [
                    {
                        'AgencyId': 'DFE',
                        'ElDebitorId': 160,
                        'FullName': 'Existing Consumer',
                        'DebitorAddress': 'Existing KESCO Address',
                        'TariffGroup': '4/02',
                        'LastDueDate': '2026-04-12T00:00:00',
                        'TotalDebt': 111.75,
                        'MeterReading': '1234.50',
                    },
                    {
                        'AgencyId': 'PRN',
                        'ElDebitorId': 999,
                        'FullName': 'New Consumer',
                        'DebitorAddress': 'New KESCO Address',
                        'TariffGroup': '5/01',
                        'LastDueDate': '2026-05-15T00:00:00',
                        'TotalDebt': 42,
                    },
                ]
            }
        }

        response = self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_API_KEY=self.raw_key,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Meter.objects.filter(kesco_debitor_id='160').count(), 1)
        existing.refresh_from_db()
        self.assertEqual(existing.name, 'DFE160')
        self.assertEqual(existing.kesco_address, 'Existing KESCO Address')
        existing_ledger = MeterLedger.objects.get(meter=existing, month=4, year=2026)
        self.assertEqual(str(existing_ledger.reading), '1234.50')
        self.assertEqual(str(existing_ledger.billed_amount), '111.75')

        created = Meter.objects.get(kesco_debitor_id='999')
        self.assertEqual(created.name, 'PRN999')
        self.assertEqual(created.unit.name, 'Unassigned KESCO Meters')
        self.assertEqual(created.unit.location.name, 'Location 0 - Unassigned KESCO Meters')
        new_ledger = MeterLedger.objects.get(meter=created, month=5, year=2026)
        self.assertEqual(str(new_ledger.billed_amount), '42.00')
