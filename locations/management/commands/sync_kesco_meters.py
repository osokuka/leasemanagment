import json
import os
import time
import base64
from datetime import datetime
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from locations.models import Location, Meter, MeterLedger, MeterType, ReadingMetric, Unit, UnitType


UNASSIGNED_LOCATION_NAME = 'Location 0 - Unassigned KESCO Meters'
UNASSIGNED_UNIT_NAME = 'Unassigned KESCO Meters'
DEFAULT_URL_TEMPLATE = 'https://fatura.kesco-energy.com/api/Account/user-data?userId={user_id}'
DEFAULT_LOGIN_URL = 'https://fatura.kesco-energy.com/api/Account/login'


class Command(BaseCommand):
    help = 'Outbound-only KESCO sync. Registers KESCO meters under Location 0 and upserts current expense standings.'

    def add_arguments(self, parser):
        parser.add_argument('--once', action='store_true', help='Run once and exit. This is the default behavior.')
        parser.add_argument('--loop', action='store_true', help='Run continuously using KESCO_SYNC_INTERVAL_SECONDS.')
        parser.add_argument('--user-id', action='append', dest='user_ids', help='KESCO user ID. Can be passed multiple times.')

    def handle(self, *args, **options):
        if options['loop']:
            interval = int(os.environ.get('KESCO_SYNC_INTERVAL_SECONDS', '3600'))
            while True:
                self.sync(options)
                time.sleep(interval)
        else:
            self.sync(options)

    def sync(self, options):
        created = 0
        updated = 0
        accounts = self.load_accounts(options)
        for account in accounts:
            token = account.get('token') or self.login(account)
            user_id = account.get('user_id') or self.user_id_from_token(token)
            if not user_id:
                raise CommandError(f'KESCO account {account.get("username", "<unknown>")} has no user_id and none could be read from the token.')

            payload = self.fetch_user_data(user_id, token)
            for balance, source_timestamp in self.extract_balances(payload):
                was_created = self.upsert_balance(balance, source_timestamp)
                if was_created:
                    created += 1
                else:
                    updated += 1

        self.stdout.write(self.style.SUCCESS(f'KESCO sync completed. meters_created={created} ledgers_updated={updated}'))

    def load_accounts(self, options):
        accounts = []
        credentials_file = os.environ.get('KESCO_ACCOUNTS_FILE', '').strip()
        credentials_json = os.environ.get('KESCO_ACCOUNTS_JSON', '').strip()

        if credentials_file:
            with open(credentials_file, 'r', encoding='utf-8') as handle:
                data = json.load(handle)
            accounts.extend(data.get('accounts', data if isinstance(data, list) else []))

        if credentials_json:
            data = json.loads(credentials_json)
            accounts.extend(data.get('accounts', data if isinstance(data, list) else []))

        if accounts:
            return accounts

        token = os.environ.get('KESCO_BEARER_TOKEN', '').strip()
        user_ids = options.get('user_ids') or []
        env_user_ids = [value.strip() for value in os.environ.get('KESCO_USER_IDS', '').split(',') if value.strip()]
        user_ids = user_ids + env_user_ids
        if token and user_ids:
            return [{'token': token, 'user_id': user_id, 'username': 'env-token'} for user_id in user_ids]

        raise CommandError('Provide KESCO_ACCOUNTS_FILE/KESCO_ACCOUNTS_JSON, or KESCO_BEARER_TOKEN with KESCO_USER_IDS.')

    def login(self, account):
        username = account.get('username') or account.get('email')
        password = account.get('password')
        if not username or not password:
            raise CommandError('Each KESCO account requires username/email and password.')

        login_url = os.environ.get('KESCO_LOGIN_URL', DEFAULT_LOGIN_URL)
        username_field = os.environ.get('KESCO_LOGIN_USERNAME_FIELD', 'email')
        password_field = os.environ.get('KESCO_LOGIN_PASSWORD_FIELD', 'password')
        body = json.dumps({
            username_field: username,
            password_field: password,
        }).encode('utf-8')

        request = Request(
            login_url,
            data=body,
            headers={
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'User-Agent': 'bldg-mgm-kesco-sync/1.0',
            },
            method='POST',
        )
        try:
            with urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode('utf-8'))
        except HTTPError as exc:
            raise CommandError(f'KESCO login failed for account={username}: HTTP {exc.code}') from exc
        except URLError as exc:
            raise CommandError(f'KESCO login failed for account={username}: {exc.reason}') from exc

        token = self.extract_token(payload)
        if not token:
            raise CommandError(f'KESCO login response did not contain a bearer token for account={username}.')
        return token

    def extract_token(self, payload):
        candidates = [
            payload.get('token'),
            payload.get('access_token'),
            payload.get('accessToken'),
            payload.get('jwt'),
        ]
        data = payload.get('Data') or payload.get('data') or {}
        if isinstance(data, dict):
            candidates.extend([
                data.get('token'),
                data.get('access_token'),
                data.get('accessToken'),
                data.get('jwt'),
            ])
        return next((value for value in candidates if value), None)

    def user_id_from_token(self, token):
        try:
            payload_part = token.split('.')[1]
            padding = '=' * (-len(payload_part) % 4)
            decoded = base64.urlsafe_b64decode(payload_part + padding)
            payload = json.loads(decoded.decode('utf-8'))
        except (IndexError, ValueError, json.JSONDecodeError):
            return None
        return payload.get('id') or payload.get('sub') or payload.get('nameid')

    def fetch_user_data(self, user_id, token):
        url_template = os.environ.get('KESCO_USER_DATA_URL_TEMPLATE', DEFAULT_URL_TEMPLATE)
        url = url_template.format(user_id=user_id)
        request = Request(
            url,
            headers={
                'Accept': 'application/json',
                'Authorization': f'Bearer {token}',
                'User-Agent': 'bldg-mgm-kesco-sync/1.0',
            },
        )
        try:
            with urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode('utf-8'))
        except HTTPError as exc:
            raise CommandError(f'KESCO request failed for user_id={user_id}: HTTP {exc.code}') from exc
        except URLError as exc:
            raise CommandError(f'KESCO request failed for user_id={user_id}: {exc.reason}') from exc

    def extract_balances(self, payload):
        data = payload.get('Data') or {}
        source_timestamp = self.parse_source_timestamp(data.get('lastUpdate'))
        balances = data.get('balances') or data.get('meters') or data.get('balance') or []
        if isinstance(balances, dict):
            balances = [balances]
        for balance in balances:
            if isinstance(balance, dict):
                yield balance, source_timestamp

    def parse_source_timestamp(self, value):
        if not value:
            return timezone.localtime()
        normalized = value.replace('Z', '+00:00')
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return timezone.localtime()
        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed)
        return parsed

    @transaction.atomic
    def upsert_balance(self, balance, source_timestamp):
        serial_number = str(balance.get('AMeterId') or '').strip()
        if not serial_number:
            self.stderr.write('Skipping KESCO balance without AMeterId.')
            return False

        holding_unit = self.get_holding_unit()
        meter = Meter.objects.filter(serial_number=serial_number).first()
        created = False
        if meter is None:
            created = True
            meter = Meter.objects.create(
                unit=holding_unit,
                name=self.build_meter_name(balance),
                meter_type=MeterType.ELECTRIC,
                reading_metric=ReadingMetric.KWH,
                serial_number=serial_number,
            )
        else:
            changed = False
            new_name = self.build_meter_name(balance)
            if meter.name != new_name:
                meter.name = new_name
                changed = True
            if changed:
                meter.save(update_fields=['name', 'updated_at'])

        amount = self.decimal_or_zero(balance.get('CurrentBalance'))
        ledger, _ = MeterLedger.objects.update_or_create(
            meter=meter,
            month=source_timestamp.month,
            year=source_timestamp.year,
            defaults={
                'reading': None,
                'billed_amount': amount,
                'settled_at': source_timestamp.date() if amount == 0 else None,
            },
        )
        return created

    def get_holding_unit(self):
        location, _ = Location.objects.get_or_create(
            name=UNASSIGNED_LOCATION_NAME,
            defaults={
                'address': 'Fictive holding location for KESCO meters pending unit assignment.',
                'focal_point': 'System generated',
            },
        )
        unit, _ = Unit.objects.get_or_create(
            location=location,
            name=UNASSIGNED_UNIT_NAME,
            defaults={
                'sqm': 0,
                'unit_type': UnitType.UNDEFINED,
            },
        )
        return unit

    def build_meter_name(self, balance):
        agency = str(balance.get('AgencyId') or 'KESCO').strip()
        debitor_id = str(balance.get('DebitorId') or '').strip()
        serial = str(balance.get('AMeterId') or '').strip()
        consumer = str(balance.get('ConsumerName') or '').strip()
        provider_id = f'{agency}{debitor_id}' if debitor_id else agency
        parts = [provider_id, serial]
        if consumer:
            parts.append(consumer)
        return ' - '.join(parts)

    def decimal_or_zero(self, value):
        try:
            return Decimal(str(value or '0'))
        except (InvalidOperation, ValueError):
            return Decimal('0')
