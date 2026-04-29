import json
import uuid
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.core.mail import EmailMessage
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from accounts.models import ApiKeyScope, UserApiKey
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


UNASSIGNED_LOCATION_NAME = 'Location 0 - Unassigned KESCO Meters'
UNASSIGNED_UNIT_NAME = 'Unassigned KESCO Meters'


def _json_error(message, status=400):
    return JsonResponse({'error': message}, status=status)


def _extract_api_key(request):
    header = request.headers.get('Authorization', '').strip()
    if header.lower().startswith('bearer '):
        return header[7:].strip()
    return request.headers.get('X-API-Key', '').strip()


def _authenticate_api_key(request, scope):
    raw_key = _extract_api_key(request)
    if not raw_key:
        return None, _json_error('Missing API key.', status=401)

    key_hash = UserApiKey.hash_key(raw_key)
    api_key = (
        UserApiKey.objects.select_related('user')
        .filter(key_hash=key_hash, scope=scope, is_active=True, user__is_active=True)
        .first()
    )
    if api_key is None:
        return None, _json_error('Invalid API key.', status=403)

    api_key.last_used_at = timezone.now()
    api_key.save(update_fields=['last_used_at', 'updated_at'])
    return api_key, None


def _parse_date(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    if hasattr(value, 'isoformat') and not isinstance(value, str):
        return value
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00')).date()
    except ValueError:
        return None


def _decimal_or_zero(value):
    try:
        return Decimal(str(value if value is not None else '0'))
    except (InvalidOperation, ValueError):
        return Decimal('0')


def _money(value):
    return str(value.quantize(Decimal('0.01')))


def _lease_financials(lease, as_of=None):
    as_of = as_of or timezone.localdate()
    ledgers = list(lease.payment_ledgers.all().order_by('year', 'month'))
    total_due = sum((entry.amount_due or Decimal('0')) for entry in ledgers)
    total_paid = sum((entry.amount_paid or Decimal('0')) for entry in ledgers)

    if not ledgers and lease.start_date and lease.start_date <= as_of:
        months_behind = (as_of.year * 12 + as_of.month) - (lease.start_date.year * 12 + lease.start_date.month) + 1
        months_behind = max(months_behind, 1)
        total_due = (lease.monthly_payment or Decimal('0')) * months_behind
        total_paid = (lease.monthly_payment or Decimal('0')) * (lease.advance_months or 0) + (lease.deposit or Decimal('0'))

    balance = total_due - total_paid
    ledger_rows = []
    running_balance = Decimal('0')
    for entry in ledgers:
        running_balance += (entry.amount_due or Decimal('0')) - (entry.amount_paid or Decimal('0'))
        ledger_rows.append({
            'uuid': str(entry.uuid),
            'month': entry.month,
            'year': entry.year,
            'amount_due': _money(entry.amount_due or Decimal('0')),
            'amount_paid': _money(entry.amount_paid or Decimal('0')),
            'running_balance': _money(running_balance),
            'status': entry.status,
            'payment_date': entry.payment_date.isoformat() if entry.payment_date else None,
            'notes': entry.notes or '',
        })

    return {
        'total_due': total_due,
        'total_paid': total_paid,
        'balance': balance,
        'has_debt': balance > 0,
        'ledger_rows': ledger_rows,
    }


def _latest_meter_rows(lease):
    rows = []
    total_outstanding = Decimal('0')
    units = lease.assigned_units.select_related('location').prefetch_related('meters__ledgers')
    for unit in units:
        for meter in unit.meters.all():
            latest = sorted(
                meter.ledgers.all(),
                key=lambda ledger: (ledger.year, ledger.month),
                reverse=True,
            )
            ledger = latest[0] if latest else None
            outstanding = ledger.billed_amount if ledger and ledger.billed_amount else Decimal('0')
            total_outstanding += outstanding
            rows.append({
                'unit_uuid': str(unit.uuid),
                'unit_name': unit.name,
                'meter_uuid': str(meter.uuid),
                'meter_name': meter.name,
                'meter_type': meter.meter_type,
                'period': {'month': ledger.month, 'year': ledger.year} if ledger else None,
                'reading': str(ledger.reading) if ledger and ledger.reading is not None else None,
                'outstanding_amount': _money(outstanding),
                'status': 'open' if outstanding > 0 else 'settled',
            })
    return rows, total_outstanding


def _lease_summary(lease, as_of=None, include_ledgers=False, include_meters=False):
    financials = _lease_financials(lease, as_of=as_of)
    data = {
        'uuid': str(lease.uuid),
        'display_id': lease.display_id,
        'name': lease.name,
        'contact': lease.contact or '',
        'phone': lease.phone or '',
        'email': lease.email or '',
        'is_active': lease.is_active,
        'start_date': lease.start_date.isoformat() if lease.start_date else None,
        'end_date': lease.end_date.isoformat() if lease.end_date else None,
        'monthly_payment': _money(lease.monthly_payment or Decimal('0')),
        'total_due': _money(financials['total_due']),
        'total_paid': _money(financials['total_paid']),
        'balance': _money(financials['balance']),
        'has_debt': financials['has_debt'],
    }
    if include_ledgers:
        data['ledgers'] = financials['ledger_rows']
    if include_meters:
        meter_rows, meter_total = _latest_meter_rows(lease)
        data['meters'] = meter_rows
        data['meter_outstanding_total'] = _money(meter_total)
    return data


def _find_lease(identifier):
    value = str(identifier or '').strip()
    if not value:
        return None

    lease = Lease.objects.filter(display_id__iexact=value).first()
    if lease:
        return lease

    try:
        lease_uuid = uuid.UUID(value)
    except ValueError:
        return None
    return Lease.objects.filter(uuid=lease_uuid).first()


def _parse_as_of(request):
    value = request.GET.get('as_of') or request.POST.get('as_of')
    parsed = _parse_date(value)
    return parsed or timezone.localdate()


def _json_payload(request):
    try:
        return json.loads(request.body.decode('utf-8')) if request.body else {}
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def _period_from_payload(payload):
    month = payload.get('month')
    year = payload.get('year')
    period = str(payload.get('period') or '').strip()
    if period and (not month or not year):
        try:
            year_text, month_text = period.split('-', 1)
            year = int(year_text)
            month = int(month_text)
        except (ValueError, TypeError):
            raise ValueError('period must use YYYY-MM format.')
    if not month or not year:
        raise ValueError('month/year or period is required.')
    month = int(month)
    year = int(year)
    if month < 1 or month > 12:
        raise ValueError('month must be between 1 and 12.')
    return month, year


def _find_meter(payload):
    meter_uuid = str(payload.get('meter_uuid') or payload.get('uuid') or '').strip()
    if meter_uuid:
        try:
            return Meter.objects.filter(uuid=uuid.UUID(meter_uuid)).first()
        except ValueError:
            return None

    kesco_debitor_id = str(payload.get('kesco_debitor_id') or payload.get('ElDebitorId') or '').strip()
    if kesco_debitor_id:
        return Meter.objects.filter(kesco_debitor_id=kesco_debitor_id).first()

    serial_number = str(payload.get('serial_number') or '').strip()
    if serial_number:
        return Meter.objects.filter(serial_number=serial_number).first()

    name = str(payload.get('meter_name') or '').strip()
    if name:
        return Meter.objects.filter(name__iexact=name).first()

    return None


def _get_holding_unit():
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


def _get_payload_items(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        data = payload.get('Data') or payload.get('data')
        if isinstance(data, dict):
            debitors = data.get('debitors') or data.get('meters')
            if isinstance(debitors, list):
                return debitors
            if isinstance(debitors, dict):
                return [debitors]
        for key in ('meters', 'debitors'):
            if isinstance(payload.get(key), list):
                return payload[key]
            if isinstance(payload.get(key), dict):
                return [payload[key]]
        return [payload]
    return None


def _upsert_meter(item):
    kesco_debitor_id = str(item.get('kesco_debitor_id') or item.get('ElDebitorId') or '').strip()
    meter_uuid = str(item.get('uuid') or '').strip()
    serial_number = str(item.get('serial_number') or '').strip() or None

    if not kesco_debitor_id and not meter_uuid and not serial_number:
        raise ValueError('One of kesco_debitor_id, uuid, or serial_number is required.')

    meter = None
    if kesco_debitor_id:
        meter = Meter.objects.filter(kesco_debitor_id=kesco_debitor_id).first()
    if meter is None and meter_uuid:
        meter = Meter.objects.filter(uuid=meter_uuid).first()
    if meter is None and serial_number:
        meter = Meter.objects.filter(serial_number=serial_number).first()

    unit = None
    unit_uuid = str(item.get('unit_uuid') or '').strip()
    if unit_uuid:
        unit = Unit.objects.filter(uuid=unit_uuid).first()
        if unit is None:
            raise ValueError(f'Unit not found for unit_uuid={unit_uuid}.')

    agency_id = str(item.get('kesco_agency_id') or item.get('AgencyId') or '').strip()
    name = str(item.get('name') or '').strip()
    if not name:
        name = f'{agency_id}{kesco_debitor_id}' if agency_id or kesco_debitor_id else serial_number

    created = False
    if meter is None:
        created = True
        meter = Meter(
            unit=unit or _get_holding_unit(),
            name=name,
            meter_type=item.get('meter_type') or MeterType.ELECTRIC,
            reading_metric=item.get('reading_metric') or ReadingMetric.KWH,
        )

    meter.unit = unit or meter.unit
    meter.name = name or meter.name
    meter.meter_type = item.get('meter_type') or meter.meter_type or MeterType.ELECTRIC
    meter.reading_metric = item.get('reading_metric') or meter.reading_metric or ReadingMetric.KWH
    meter.serial_number = serial_number if serial_number is not None else meter.serial_number
    meter.kesco_debitor_id = kesco_debitor_id or meter.kesco_debitor_id
    meter.kesco_agency_id = agency_id or meter.kesco_agency_id
    meter.kesco_full_name = item.get('kesco_full_name') or item.get('FullName') or meter.kesco_full_name
    meter.kesco_address = item.get('kesco_address') or item.get('DebitorAddress') or meter.kesco_address
    meter.kesco_tariff_group = item.get('kesco_tariff_group') or item.get('TariffGroup') or meter.kesco_tariff_group
    meter.kesco_last_due_date = (
        _parse_date(item.get('kesco_last_due_date') or item.get('LastDueDate'))
        or meter.kesco_last_due_date
    )
    meter.save()

    ledger_result = None
    ledger_data = item.get('ledger')
    if ledger_data is None and any(key in item for key in ('month', 'year', 'billed_amount', 'TotalDebt', 'LastDueDate')):
        ledger_data = item
    if ledger_data is not None:
        ledger_result = _upsert_ledger(meter, ledger_data)

    return {
        'uuid': str(meter.uuid),
        'created': created,
        'name': meter.name,
        'kesco_debitor_id': meter.kesco_debitor_id,
        'ledger': ledger_result,
    }


def _upsert_ledger(meter, data):
    due_date = _parse_date(data.get('due_date') or data.get('last_due_date') or data.get('LastDueDate'))
    month = data.get('month') or (due_date.month if due_date else None)
    year = data.get('year') or (due_date.year if due_date else None)
    if not month or not year:
        now = timezone.localdate()
        month, year = now.month, now.year

    amount = _decimal_or_zero(
        data.get('billed_amount', data.get('TotalDebt', data.get('total_debt')))
    )
    reading = (
        data.get('reading')
        or data.get('Reading')
        or data.get('meter_reading')
        or data.get('MeterReading')
        or data.get('active_energy')
        or data.get('ActiveEnergy')
    )
    settled_at = _parse_date(data.get('settled_at'))
    if settled_at is None and amount == 0:
        settled_at = timezone.localdate()

    ledger, created = MeterLedger.objects.update_or_create(
        meter=meter,
        month=int(month),
        year=int(year),
        defaults={
            'reading': reading,
            'billed_amount': amount,
            'settled_at': settled_at,
        },
    )
    return {
        'uuid': str(ledger.uuid),
        'created': created,
        'month': ledger.month,
        'year': ledger.year,
        'billed_amount': str(ledger.billed_amount),
    }


@csrf_exempt
@require_POST
def kesco_meter_upsert_api(request):
    api_key, error = _authenticate_api_key(request, ApiKeyScope.KESCO_METER_WRITE)
    if error:
        return error

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _json_error('Invalid JSON payload.')

    items = _get_payload_items(payload)
    if not items:
        return _json_error('Payload must be a meter object, a list, or {"meters": [...]}.')

    results = []
    errors = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append({'index': index, 'error': 'Meter item must be an object.'})
            continue
        try:
            results.append(_upsert_meter(item))
        except ValueError as exc:
            errors.append({'index': index, 'error': str(exc)})

    status = 207 if errors and results else 400 if errors else 200
    return JsonResponse({
        'owner': api_key.user.username,
        'scope': api_key.scope,
        'results': results,
        'errors': errors,
    }, status=status)


@csrf_exempt
@require_GET
def lease_status_api(request):
    api_key, error = _authenticate_api_key(request, ApiKeyScope.LEASE_REPORT_READ)
    if error:
        return error

    as_of = _parse_as_of(request)
    search = request.GET.get('search', '').strip()
    debt_only = request.GET.get('debt_only', '1').lower() not in ('0', 'false', 'no')
    limit = min(int(request.GET.get('limit', '100')), 500)

    leases = Lease.objects.prefetch_related('payment_ledgers').order_by('display_id', 'name')
    if search:
        leases = leases.filter(
            Q(display_id__icontains=search)
            | Q(name__icontains=search)
            | Q(contact__icontains=search)
            | Q(phone__icontains=search)
            | Q(email__icontains=search)
        )

    results = []
    total_debt = Decimal('0')
    debt_count = 0
    for lease in leases:
        summary = _lease_summary(lease, as_of=as_of)
        if debt_only and not summary['has_debt']:
            continue
        if summary['has_debt']:
            debt_count += 1
            total_debt += Decimal(summary['balance'])
        results.append(summary)
        if len(results) >= limit:
            break

    return JsonResponse({
        'owner': api_key.user.username,
        'scope': api_key.scope,
        'as_of': as_of.isoformat(),
        'search': search,
        'debt_only': debt_only,
        'summary': {
            'leases_returned': len(results),
            'leases_with_debt': debt_count,
            'total_debt': _money(total_debt),
        },
        'results': results,
    })


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def lease_report_api(request, lease_identifier):
    api_key, error = _authenticate_api_key(request, ApiKeyScope.LEASE_REPORT_READ)
    if error:
        return error

    lease = _find_lease(lease_identifier)
    if lease is None:
        return _json_error('Lease not found.', status=404)
    lease = (
        Lease.objects.prefetch_related(
            'payment_ledgers',
            'assigned_units__meters__ledgers',
        )
        .get(pk=lease.pk)
    )

    as_of = _parse_as_of(request)
    report = _lease_summary(lease, as_of=as_of, include_ledgers=True, include_meters=True)
    sent_to = None

    if request.method == 'POST':
        try:
            payload = json.loads(request.body.decode('utf-8')) if request.body else {}
        except (UnicodeDecodeError, json.JSONDecodeError):
            return _json_error('Invalid JSON payload.')

        sent_to = payload.get('email_to') or lease.email
        if not sent_to:
            return _json_error('email_to is required when the lease has no email.')

        subject = f'Lease report {lease.display_id} - balance {report["balance"]}'
        lines = [
            f'Lease: {lease.display_id} - {lease.name}',
            f'As of: {as_of.isoformat()}',
            f'Total due: {report["total_due"]}',
            f'Total paid: {report["total_paid"]}',
            f'Balance: {report["balance"]}',
            '',
            'Ledger:',
        ]
        for row in report['ledgers']:
            lines.append(
                f'{row["month"]:02d}/{row["year"]}: due {row["amount_due"]}, paid {row["amount_paid"]}, balance {row["running_balance"]}'
            )
        lines.extend(['', 'Meters:'])
        for row in report['meters']:
            period = row['period']
            period_text = f'{period["month"]:02d}/{period["year"]}' if period else '-'
            lines.append(
                f'{row["unit_name"]} / {row["meter_name"]} / {period_text}: {row["outstanding_amount"]} ({row["status"]})'
            )

        message = EmailMessage(subject=subject, body='\n'.join(lines), to=[sent_to])
        message.send(fail_silently=False)

    return JsonResponse({
        'owner': api_key.user.username,
        'scope': api_key.scope,
        'as_of': as_of.isoformat(),
        'sent_to': sent_to,
        'report': report,
    })


@csrf_exempt
@require_POST
def lease_payment_settle_api(request, lease_identifier):
    api_key, error = _authenticate_api_key(request, ApiKeyScope.SETTLEMENT_WRITE)
    if error:
        return error

    payload = _json_payload(request)
    if payload is None:
        return _json_error('Invalid JSON payload.')

    lease = _find_lease(lease_identifier)
    if lease is None:
        return _json_error('Lease not found.', status=404)

    try:
        month, year = _period_from_payload(payload)
    except ValueError as exc:
        return _json_error(str(exc))

    ledger, created = LeaseLedger.objects.get_or_create(
        lease=lease,
        month=month,
        year=year,
        defaults={
            'amount_due': lease.monthly_payment or Decimal('0'),
            'amount_paid': Decimal('0'),
        },
    )

    amount_paid = payload.get('amount_paid')
    ledger.amount_paid = _decimal_or_zero(amount_paid) if amount_paid is not None else (ledger.amount_due or Decimal('0'))
    payment_date = _parse_date(payload.get('payment_date')) or timezone.localdate()
    ledger.payment_date = payment_date
    notes = payload.get('notes')
    if notes is not None:
        ledger.notes = str(notes)
    ledger.save()

    return JsonResponse({
        'owner': api_key.user.username,
        'scope': api_key.scope,
        'lease': _lease_summary(lease),
        'ledger': {
            'uuid': str(ledger.uuid),
            'created': created,
            'month': ledger.month,
            'year': ledger.year,
            'amount_due': _money(ledger.amount_due or Decimal('0')),
            'amount_paid': _money(ledger.amount_paid or Decimal('0')),
            'status': ledger.status,
            'payment_date': ledger.payment_date.isoformat() if ledger.payment_date else None,
        },
    })


@csrf_exempt
@require_POST
def electric_debt_settle_api(request):
    api_key, error = _authenticate_api_key(request, ApiKeyScope.SETTLEMENT_WRITE)
    if error:
        return error

    payload = _json_payload(request)
    if payload is None:
        return _json_error('Invalid JSON payload.')

    try:
        month, year = _period_from_payload(payload)
    except ValueError as exc:
        return _json_error(str(exc))

    lease_identifier = str(payload.get('lease_id') or payload.get('lease_display_id') or payload.get('lease_uuid') or '').strip()
    meters = []
    if lease_identifier:
        lease = _find_lease(lease_identifier)
        if lease is None:
            return _json_error('Lease not found.', status=404)
        meters = list(Meter.objects.filter(unit__lease=lease, meter_type=MeterType.ELECTRIC))
    else:
        meter = _find_meter(payload)
        if meter is None:
            return _json_error('Meter not found.', status=404)
        if meter.meter_type != MeterType.ELECTRIC:
            return _json_error('Meter is not electric.')
        meters = [meter]

    if not meters:
        return _json_error('No electric meters found for settlement.', status=404)

    settled_at = _parse_date(payload.get('settled_at')) or timezone.localdate()
    results = []
    for meter in meters:
        ledger = MeterLedger.objects.filter(meter=meter, month=month, year=year).first()
        if ledger is None:
            results.append({
                'meter_uuid': str(meter.uuid),
                'meter_name': meter.name,
                'status': 'missing_ledger',
                'month': month,
                'year': year,
            })
            continue
        previous_amount = ledger.billed_amount or Decimal('0')
        ledger.billed_amount = Decimal('0')
        ledger.settled_at = settled_at
        ledger.save(update_fields=['billed_amount', 'settled_at', 'updated_at'])
        results.append({
            'meter_uuid': str(meter.uuid),
            'meter_name': meter.name,
            'ledger_uuid': str(ledger.uuid),
            'status': 'settled',
            'month': month,
            'year': year,
            'previous_billed_amount': _money(previous_amount),
            'billed_amount': _money(ledger.billed_amount or Decimal('0')),
            'settled_at': ledger.settled_at.isoformat() if ledger.settled_at else None,
        })

    return JsonResponse({
        'owner': api_key.user.username,
        'scope': api_key.scope,
        'results': results,
    })
