import uuid
import os
import json
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def contract_upload_path(instance, filename):
    return os.path.join('contracts', str(instance.uuid), filename)


class UnitType(models.TextChoices):
    APARTMENT = 'apartment', _('Apartment')
    HOUSE = 'house', _('House')
    VILLA = 'villa', _('Villa')
    OFFICE = 'office', _('Office')
    CAFE_RESTAURANT = 'cafe_restaurant', _('Cafe & Restaurant')
    SPACE = 'space', _('Space')
    UNDEFINED = 'undefined', _('Undefined')


class MeterType(models.TextChoices):
    ELECTRIC = 'electric', _('Electric')
    WATER = 'water', _('Water')
    GAS = 'gas', _('Gas')


class ReadingMetric(models.TextChoices):
    KWH = 'kWh', _('kWh')
    CUBIC_M = 'm³', _('m³')
    CUBIC_M_GAS = 'm³_gas', _('m³ (gas)')


class Location(models.Model):
    """Physical location managed within the building management system."""
    uuid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
    )
    name = models.CharField(
        max_length=255,
        verbose_name=_('Location Name'),
    )
    address = models.TextField(
        verbose_name=_('Location Address'),
    )
    google_pin = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name=_('Google Pin'),
    )
    focal_point = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_('Focal Point'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Location')
        verbose_name_plural = _('Locations')
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def parking_count(self):
        return self.parking_places.count()


class LeaseStatus(models.TextChoices):
    PAID = 'paid', _('Paid')
    PARTIAL = 'partial', _('Partial')
    UNPAID = 'unpaid', _('Unpaid')
    OVERDUE = 'overdue', _('Overdue')


def generate_lease_display_id():
    """Generate a memorable 8-character lease ID like 'LS-A3K7M2X9'."""
    import string
    import random
    chars = string.ascii_uppercase + string.digits
    # Remove confusing characters
    chars = chars.replace('0', '').replace('1', '').replace('O', '').replace('I', '')
    return 'LS-' + ''.join(random.choices(chars, k=5))


class Lease(models.Model):
    """A rental agreement assigned to individual units."""
    uuid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
    )
    display_id = models.CharField(
        max_length=8,
        unique=True,
        editable=False,
        db_index=True,
        default='',
        verbose_name=_('Lease ID'),
    )
    name = models.CharField(
        max_length=255,
        verbose_name=_('Responsible Party'),
    )
    contact = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_('Contact Person'),
    )
    phone = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name=_('Phone'),
    )
    email = models.EmailField(
        blank=True,
        null=True,
        verbose_name=_('Email'),
    )
    contract = models.FileField(
        upload_to=contract_upload_path,
        blank=True,
        null=True,
        verbose_name=_('Contract'),
    )
    start_date = models.DateField(
        verbose_name=_('Start Date'),
    )
    end_date = models.DateField(
        blank=True,
        null=True,
        verbose_name=_('End Date'),
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Active'),
    )
    monthly_payment = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name=_('Monthly Payment (€)'),
    )
    advance_months = models.IntegerField(
        default=1,
        verbose_name=_('Months in Advance'),
    )
    deposit = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name=_('Deposit (€)'),
    )
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Notes'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Lease')
        verbose_name_plural = _('Leases')
        ordering = ['-created_at']

    def __str__(self):
        end = self.end_date.strftime('%d.%m.%Y') if self.end_date else '—'
        return f'[{self.display_id}] {self.name} ({self.start_date.strftime("%d.%m.%Y")} — {end}) — €{self.monthly_payment}/mo'

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        if not self.display_id:
            self.display_id = generate_lease_display_id()
        super().save(*args, **kwargs)

        # Auto-generate ledger entries for new leases
        if is_new and self.start_date:
            today = date.today()
            last_date = self.end_date if self.end_date and self.end_date < today else today
            year, month = self.start_date.year, self.start_date.month
            end_year, end_month = last_date.year, last_date.month
            advance_remaining = self.advance_months or 0
            while (year, month) <= (end_year, end_month):
                if not LeaseLedger.objects.filter(lease=self, month=month, year=year).exists():
                    # Mark advance months as paid
                    if advance_remaining > 0:
                        amount_paid = self.monthly_payment or Decimal('0')
                        advance_remaining -= 1
                    else:
                        amount_paid = Decimal('0')
                    LeaseLedger.objects.create(
                        lease=self,
                        month=month,
                        year=year,
                        amount_due=self.monthly_payment or Decimal('0'),
                        amount_paid=amount_paid,
                    )
                if month == 12:
                    month = 1
                    year += 1
                else:
                    month += 1

    @property
    def unit_count(self):
        return self.assigned_units.count()


class LeaseLedger(models.Model):
    """Monthly payment tracking for a lease."""
    uuid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
    )
    lease = models.ForeignKey(
        Lease,
        on_delete=models.CASCADE,
        related_name='payment_ledgers',
        verbose_name=_('Lease'),
    )
    month = models.IntegerField(
        verbose_name=_('Month'),
    )
    year = models.IntegerField(
        verbose_name=_('Year'),
    )
    amount_due = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_('Amount Due (€)'),
    )
    amount_paid = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name=_('Amount Paid (€)'),
    )
    status = models.CharField(
        max_length=10,
        choices=LeaseStatus.choices,
        default=LeaseStatus.UNPAID,
        verbose_name=_('Status'),
    )
    payment_date = models.DateField(
        blank=True,
        null=True,
        verbose_name=_('Payment Date'),
    )
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Notes'),
    )
    payment_slip = models.ImageField(
        upload_to='payment_slips',
        blank=True,
        null=True,
        verbose_name=_('Payment Slip'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Lease Ledger')
        verbose_name_plural = _('Lease Ledgers')
        ordering = ['-year', '-month']
        unique_together = ['lease', 'month', 'year']

    def __str__(self):
        return f'{self.lease.display_id} — {self.month:02d}/{self.year} ({self.get_status_display()})'

    def save(self, *args, **kwargs):
        # Auto-set amount_due from lease if not set
        if not self.amount_due:
            self.amount_due = self.lease.monthly_payment
        # Auto-determine status from amounts
        if self.amount_paid >= self.amount_due and self.amount_due > 0:
            self.status = LeaseStatus.PAID
        elif self.amount_paid > 0:
            self.status = LeaseStatus.PARTIAL
        else:
            self.status = LeaseStatus.UNPAID
        super().save(*args, **kwargs)


class Unit(models.Model):
    """A unit within a location (apartment, office, etc.)."""
    uuid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.CASCADE,
        related_name='units',
        verbose_name=_('Location'),
    )
    lease = models.ForeignKey(
        Lease,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='assigned_units',
        verbose_name=_('Lease'),
    )
    name = models.CharField(
        max_length=255,
        verbose_name=_('Unit Name'),
    )
    sqm = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_('Area (sqm)'),
    )
    unit_type = models.CharField(
        max_length=20,
        choices=UnitType.choices,
        default=UnitType.UNDEFINED,
        verbose_name=_('Unit Type'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Unit')
        verbose_name_plural = _('Units')
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.get_unit_type_display()})'

    @property
    def is_leased(self):
        return self.lease is not None and self.lease.is_active

    @property
    def parking_count(self):
        return self.parking_assignments.count()

    @property
    def meters(self):
        return self.meter_set.all()


class Meter(models.Model):
    """Utility meter installed in a unit."""
    uuid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
    )
    unit = models.ForeignKey(
        Unit,
        on_delete=models.CASCADE,
        related_name='meters',
        verbose_name=_('Unit'),
    )
    name = models.CharField(
        max_length=255,
        verbose_name=_('Meter Name'),
    )
    meter_type = models.CharField(
        max_length=20,
        choices=MeterType.choices,
        verbose_name=_('Meter Type'),
    )
    reading_metric = models.CharField(
        max_length=20,
        choices=ReadingMetric.choices,
        verbose_name=_('Reading Metric'),
    )
    serial_number = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_('Serial Number'),
    )
    kesco_debitor_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_('KESCO Debitor ID'),
        help_text=_('Link to KESCO ElDebitorId for automatic sync'),
    )
    kesco_agency_id = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name=_('KESCO Agency ID'),
    )
    kesco_full_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_('KESCO Consumer Name'),
    )
    kesco_address = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name=_('KESCO Consumer Address'),
    )
    kesco_tariff_group = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_('KESCO Tariff Group'),
    )
    kesco_last_due_date = models.DateField(
        blank=True,
        null=True,
        verbose_name=_('KESCO Last Due Date'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Meter')
        verbose_name_plural = _('Meters')
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.get_meter_type_display()})'


class MeterLedger(models.Model):
    """Monthly billing record for a meter."""
    uuid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
    )
    meter = models.ForeignKey(
        Meter,
        on_delete=models.CASCADE,
        related_name='ledgers',
        verbose_name=_('Meter'),
    )
    month = models.IntegerField(
        verbose_name=_('Month'),
    )
    year = models.IntegerField(
        verbose_name=_('Year'),
    )
    reading = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name=_('Reading'),
    )
    billed_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name=_('Billed Amount (€)'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    settled_at = models.DateField(
        blank=True,
        null=True,
        verbose_name=_('Settled Date'),
    )

    class Meta:
        verbose_name = _('Meter Ledger')
        verbose_name_plural = _('Meter Ledgers')
        ordering = ['-year', '-month']
        unique_together = ['meter', 'month', 'year']

    def __str__(self):
        return f'{self.meter.name} — {self.month:02d}/{self.year}'
    @property
    def has_debt(self):
        return bool(self.billed_amount and self.billed_amount > 0)

    @property
    def settlement_status(self):
        return _('Open') if self.has_debt else _('Settled')


class KescoCredential(models.Model):
    """KESCO portal credentials and bearer token for an account."""
    uuid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
    )
    username = models.CharField(
        max_length=255,
        unique=True,
        verbose_name=_('KESCO Username / Account ID'),
    )
    password = models.CharField(
        max_length=500,
        verbose_name=_('KESCO Password'),
    )
    user_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_('KESCO User ID'),
    )
    bearer_token = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Bearer Token'),
    )
    token_obtained_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_('Token Obtained At'),
    )
    token_expires_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_('Token Expires At'),
    )
    last_sync_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_('Last Sync At'),
    )
    last_sync_status = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name=_('Last Sync Status'),
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Active'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('KESCO Credential')
        verbose_name_plural = _('KESCO Credentials')
        ordering = ['username']

    def __str__(self):
        return f'KESCO: {self.username}'

    @property
    def is_token_valid(self):
        if not self.bearer_token or not self.token_expires_at:
            return False
        return timezone.now() < self.token_expires_at

    @property
    def needs_captcha_login(self):
        """Return True if token is invalid/expired and login is needed."""
        return not self.is_token_valid

    def login_to_kesco(self):
        """Attempt to login to KESCO and save the bearer token."""
        login_url = os.environ.get(
            'KESCO_LOGIN_URL',
            'https://fatura.kesco-energy.com/api/Account/login'
        )
        username_field = os.environ.get('KESCO_LOGIN_USERNAME_FIELD', 'Username')
        password_field = os.environ.get('KESCO_LOGIN_PASSWORD_FIELD', 'Password')

        body = json.dumps({
            username_field: self.username,
            password_field: self.password,
            'RememberMe': True,
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
            # If 400/401, might be captcha issue
            if exc.code in (400, 401, 403):
                self.last_sync_status = f'Login failed (HTTP {exc.code}) - may require captcha'
                self.save(update_fields=['last_sync_status', 'updated_at'])
                raise Exception(f'KESCO login failed for {self.username}: HTTP {exc.code}. This may require captcha verification.')
            raise Exception(f'KESCO login failed for {self.username}: HTTP {exc.code}')
        except URLError as exc:
            raise Exception(f'KESCO login failed for {self.username}: {exc.reason}')

        # Extract token
        token = self._extract_token(payload)
        if not token:
            raise Exception(f'KESCO login response did not contain a bearer token for {self.username}.')

        # Extract user_id from token JWT
        user_id = self._user_id_from_token(token)
        if not user_id:
            user_id = payload.get('userId') or payload.get('Data', {}).get('userId')

        # KESCO tokens expire in 7 days (604800 seconds)
        now = timezone.now()
        self.bearer_token = token
        self.user_id = user_id or self.user_id
        self.token_obtained_at = now
        self.token_expires_at = now + timedelta(seconds=604800)
        self.last_sync_status = 'Token obtained'
        self.save(update_fields=[
            'bearer_token', 'user_id', 'token_obtained_at',
            'token_expires_at', 'last_sync_status', 'updated_at'
        ])
        return token

    def _extract_token(self, payload):
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

    def _user_id_from_token(self, token):
        import base64
        try:
            payload_part = token.split('.')[1]
            padding = '=' * (-len(payload_part) % 4)
            decoded = base64.urlsafe_b64decode(payload_part + padding)
            payload = json.loads(decoded.decode('utf-8'))
            return payload.get('id') or payload.get('sub') or payload.get('nameid')
        except (IndexError, ValueError, json.JSONDecodeError):
            return None

    def get_valid_token(self):
        """Return a valid token, refreshing if needed. Returns (token, needs_captcha)."""
        if self.is_token_valid:
            return self.bearer_token, False

        try:
            token = self.login_to_kesco()
            return token, False
        except Exception as e:
            if 'captcha' in str(e).lower():
                return None, True
            raise


class ParkingPlace(models.Model):
    """A parking space within a location."""
    uuid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.CASCADE,
        related_name='parking_places',
        verbose_name=_('Location'),
    )
    label = models.CharField(
        max_length=100,
        verbose_name=_('Label'),
    )
    unit = models.ForeignKey(
        Unit,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='parking_assignments',
        verbose_name=_('Assigned Unit'),
    )
    covered = models.BooleanField(
        default=False,
        verbose_name=_('Covered'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Parking Place')
        verbose_name_plural = _('Parking Places')
        ordering = ['label']
        unique_together = ['location', 'label']

    def __str__(self):
        assigned = f' → {self.unit.name}' if self.unit else ''
        return f'{self.label}{assigned}'
