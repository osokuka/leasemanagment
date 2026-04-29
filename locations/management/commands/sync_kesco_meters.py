import json
import os
import time
import random
import base64
from datetime import datetime
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from locations.models import Location, Meter, MeterLedger, MeterType, ReadingMetric, Unit, UnitType, KescoCredential


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
        
        # Try to use database credentials first
        accounts = self.load_accounts_from_db()
        
        # Fallback to env/file-based accounts if none in DB
        if not accounts:
            accounts = self.load_accounts(options)
        
        for account in accounts:
            credential = account.get('credential')
            token = account.get('token')
            user_id = account.get('user_id')
            
            # If we have a credential object, try to get a valid token
            if credential:
                try:
                    token, needs_captcha = credential.get_valid_token()
                    if needs_captcha:
                        self.stderr.write(
                            self.style.WARNING(
                                f'KESCO account {credential.username} requires captcha login. '
                                f'Please use the iframe login page.'
                            )
                        )
                        credential.last_sync_status = 'Requires captcha login'
                        credential.save(update_fields=['last_sync_status', 'updated_at'])
                        continue
                    
                    user_id = user_id or credential.user_id
                except Exception as e:
                    self.stderr.write(self.style.ERROR(f'KESCO account {credential.username}: {str(e)}'))
                    if credential:
                        credential.last_sync_status = str(e)[:50]
                        credential.save(update_fields=['last_sync_status', 'updated_at'])
                    continue
            
            if not token:
                self.stderr.write(self.style.WARNING(f'Skipping account {account.get("username", "<unknown>")}: no token'))
                continue
            
            if not user_id:
                user_id = self.user_id_from_token(token)
            
            if not user_id:
                raise CommandError(f'KESCO account {account.get("username", "<unknown>")} has no user_id and none could be read from the token.')

            try:
                # Sleep before querying user debitors
                delay = random.uniform(3, 10)
                self.stdout.write(f'  Sleeping {delay:.1f}s before querying KESCO...')
                time.sleep(delay)
                payload = self.fetch_user_data(user_id, token)
                balances = list(self.extract_balances(payload))
                for i, (balance, source_timestamp) in enumerate(balances):
                    # Sleep between each meter/debitor operation
                    if i > 0:
                        delay = random.uniform(3, 10)
                        self.stdout.write(f'  Sleeping {delay:.1f}s before processing next debitor...')
                        time.sleep(delay)
                    was_created = self.upsert_balance(balance, source_timestamp)
                    if was_created:
                        created += 1
                    else:
                        updated += 1
                
                # Update last sync time for credential
                if credential:
                    credential.last_sync_at = timezone.now()
                    credential.last_sync_status = 'Sync completed'
                    credential.save(update_fields=['last_sync_at', 'last_sync_status', 'updated_at'])
            except Exception as e:
                self.stderr.write(self.style.ERROR(f'KESCO sync failed for {account.get("username", "<unknown>")}: {str(e)}'))
                if credential:
                    credential.last_sync_at = timezone.now()
                    credential.last_sync_status = f'Error: {str(e)[:30]}'
                    credential.save(update_fields=['last_sync_at', 'last_sync_status', 'updated_at'])

        self.stdout.write(self.style.SUCCESS(f'KESCO sync completed. meters_created={created} ledgers_updated={updated}'))

    def load_accounts_from_db(self):
        """Load active KESCO credentials from database."""
        accounts = []
        try:
            credentials = KescoCredential.objects.filter(is_active=True)
            for cred in credentials:
                accounts.append({
                    'credential': cred,
                    'token': cred.bearer_token if cred.is_token_valid else None,
                    'user_id': cred.user_id,
                    'username': cred.username,
                })
        except Exception as e:
            # DB might not have KescoCredential table yet (before migration)
            self.stdout.write(self.style.WARNING(f'Could not load KESCO credentials from DB: {e}'))
        return accounts

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
        url = os.environ.get('KESCO_USER_DATA_URL_TEMPLATE', 'https://fatura.kesco-energy.com/api/Account/user-debitors')
        self.stdout.write(self.style.HTTP_SUCCESS(f'  → GET {url}'))
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
                raw = response.read().decode('utf-8')
                self.stdout.write(self.style.SUCCESS(f'  ← HTTP {response.status} — {len(raw)} bytes'))
                payload = json.loads(raw)
                # Log full payload for debugging
                self.stdout.write(self.style.HTTP_SUCCESS(f'  📦 RAW PAYLOAD: {json.dumps(payload, indent=2)[:2000]}'))
                return payload
        except HTTPError as exc:
            body = exc.read().decode('utf-8', errors='replace') if hasattr(exc, 'read') else ''
            self.stdout.write(self.style.ERROR(f'  ✗ HTTP {exc.code}: {body[:500]}'))
            raise CommandError(f'KESCO request failed for user_id={user_id}: HTTP {exc.code}') from exc
        except URLError as exc:
            raise CommandError(f'KESCO request failed for user_id={user_id}: {exc.reason}') from exc

    def extract_balances(self, payload):
        data = payload.get('Data') or {}
        debitors = data.get('debitors', [])
        if isinstance(debitors, dict):
            debitors = [debitors]
        
        self.stdout.write(self.style.SUCCESS(f'  📋 Found {len(debitors)} debitor(s) in payload'))
        
        for debitor in debitors:
            if isinstance(debitor, dict):
                debitor_id = debitor.get('ElDebitorId', 'N/A')
                agency_id = debitor.get('AgencyId', 'N/A')
                total_debt = debitor.get('TotalDebt', 'N/A')
                last_due = debitor.get('LastDueDate', 'N/A')
                self.stdout.write(self.style.HTTP_SUCCESS(
                    f'    ⚡ Debitor: {agency_id}{debitor_id} | Debt: {total_debt} | Due: {last_due}'
                ))
                yield debitor, timezone.now()

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
        debitor_id = str(balance.get('ElDebitorId') or '').strip()
        agency_id = str(balance.get('AgencyId') or '').strip()
        if not debitor_id:
            self.stderr.write('Skipping KESCO balance without ElDebitorId.')
            return False

        # Build meter name: AgencyId + ElDebitorId (e.g. DFE160)
        meter_name = f'{agency_id}{debitor_id}'

        holding_unit = None
        orphan = None
        created = False

        self.stdout.write(f'  🔍 Looking for meter with kesco_debitor_id={debitor_id}...')

        # Priority 1: Find meter explicitly linked by kesco_debitor_id
        meter = Meter.objects.filter(kesco_debitor_id=debitor_id).first()
        if meter:
            self.stdout.write(self.style.SUCCESS(f'    ✓ Found existing meter: {meter.name} (pk={meter.pk})'))
        else:
            self.stdout.write(f'    ✗ No meter found with kesco_debitor_id={debitor_id}')

        # Priority 2: Fallback — find orphan created by earlier sync
        if meter is None:
            orphan = Meter.objects.filter(serial_number=f"KESCO-{debitor_id}").first()
            if orphan:
                self.stdout.write(self.style.WARNING(f'    ⚠ Found orphan meter: {orphan.name} (pk={orphan.pk})'))
            else:
                self.stdout.write(f'    ✗ No orphan found with serial_number=KESCO-{debitor_id}')

        if meter is None and orphan is None:
            # Create new meter under holding location
            holding_unit = self.get_holding_unit()
            created = True
            self.stdout.write(self.style.HTTP_SUCCESS(f'    ➕ Creating new meter: {meter_name}'))
            meter = Meter.objects.create(
                unit=holding_unit,
                name=meter_name,
                meter_type=MeterType.ELECTRIC,
                reading_metric=ReadingMetric.KWH,
                kesco_debitor_id=debitor_id,
                kesco_agency_id=agency_id,
                kesco_full_name=balance.get('FullName') or None,
                kesco_address=balance.get('DebitorAddress') or None,
                kesco_tariff_group=balance.get('TariffGroup') or None,
            )
            self.stdout.write(self.style.SUCCESS(f'    ✓ Meter created: pk={meter.pk}'))

        # Merge orphan into linked meter if both exist
        if meter is not None and orphan is not None and orphan.pk != meter.pk:
            from locations.models import MeterLedger as ML
            for old_ledger in ML.objects.filter(meter=orphan):
                ML.objects.update_or_create(
                    meter=meter,
                    month=old_ledger.month,
                    year=old_ledger.year,
                    defaults={
                        'reading': old_ledger.reading,
                        'billed_amount': old_ledger.billed_amount,
                        'settled_at': old_ledger.settled_at,
                    },
                )
            orphan.delete()
            self.stdout.write(self.style.SUCCESS(
                f'  Merged orphan "{orphan.name}" into "{meter.name}".'
            ))

        # If only orphan exists, promote it
        if meter is None and orphan is not None:
            meter = orphan
            created = False

        # Update KESCO fields on meter
        changed = False
        if meter.name != meter_name:
            meter.name = meter_name
            changed = True
        if meter.kesco_debitor_id != debitor_id:
            meter.kesco_debitor_id = debitor_id
            changed = True
        if meter.kesco_agency_id != agency_id:
            meter.kesco_agency_id = agency_id
            changed = True
        full_name = balance.get('FullName') or None
        if meter.kesco_full_name != full_name:
            meter.kesco_full_name = full_name
            changed = True
        address = balance.get('DebitorAddress') or None
        if meter.kesco_address != address:
            meter.kesco_address = address
            changed = True
        tariff = balance.get('TariffGroup') or None
        if meter.kesco_tariff_group != tariff:
            meter.kesco_tariff_group = tariff
            changed = True

        # Parse LastDueDate
        last_due_date = None
        last_due_raw = balance.get('LastDueDate')
        if last_due_raw:
            try:
                last_due_date = datetime.fromisoformat(
                    last_due_raw.replace('Z', '+00:00')
                ).date()
            except (ValueError, AttributeError):
                pass
        if meter.kesco_last_due_date != last_due_date:
            meter.kesco_last_due_date = last_due_date
            changed = True

        if changed:
            meter.save(update_fields=[
                'name', 'kesco_debitor_id', 'kesco_agency_id',
                'kesco_full_name', 'kesco_address', 'kesco_tariff_group',
                'kesco_last_due_date', 'updated_at',
            ])
            self.stdout.write(self.style.SUCCESS(f'    ✓ Meter fields updated'))

        # Extract billing month/year from LastDueDate
        if last_due_date:
            month, year = last_due_date.month, last_due_date.year
        else:
            month, year = source_timestamp.month, source_timestamp.year

        amount = self.decimal_or_zero(balance.get('TotalDebt'))
        self.stdout.write(f'  💰 Creating/updating ledger: meter={meter.name}, month={month}/{year}, amount={amount}')

        ledger, ledger_created = MeterLedger.objects.update_or_create(
            meter=meter,
            month=month,
            year=year,
            defaults={
                'reading': None,
                'billed_amount': amount,
                'settled_at': source_timestamp.date() if amount == 0 else None,
            },
        )
        
        if ledger_created:
            self.stdout.write(self.style.SUCCESS(f'    ✓ Ledger CREATED (pk={ledger.pk})'))
        else:
            self.stdout.write(f'    ℹ Ledger EXISTS (pk={ledger.pk}), updated billed_amount={amount}')
        
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
        debitor_id = str(balance.get('ElDebitorId') or '').strip()
        full_name = str(balance.get('FullName') or '').strip()
        address = str(balance.get('DebitorAddress') or '').strip()
        tariff = str(balance.get('TariffGroup') or '').strip()
        parts = [f'{agency}-{debitor_id}']
        if full_name:
            parts.append(full_name)
        if address:
            parts.append(address)
        if tariff:
            parts.append(f'Tariff: {tariff}')
        return ' | '.join(parts)

    def decimal_or_zero(self, value):
        try:
            return Decimal(str(value or '0'))
        except (InvalidOperation, ValueError):
            return Decimal('0')
