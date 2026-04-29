from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.core.paginator import Paginator
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST
from .models import Location, Unit, Meter, MeterLedger, ParkingPlace, Lease, LeaseLedger, LeaseStatus, SalePayment, SaleStatus, SalePaymentStatus
from .forms import LocationForm, UnitForm, MeterForm, MeterLedgerForm, ParkingPlaceForm, ParkingBulkCreateForm, LeaseForm, LeaseLedgerForm, SalePaymentForm

LEASES_PER_PAGE = 15

LOCATIONS_PER_PAGE = 15
UNITS_PER_PAGE = 15
METERS_PER_PAGE = 15
LEDGERS_PER_PAGE = 12


# --- Decorators ---
def super_user_required(view_func):
    return user_passes_test(lambda u: u.is_authenticated and u.is_super_user)(view_func)


def admin_required(view_func):
    return user_passes_test(lambda u: u.is_authenticated and u.is_admin)(view_func)


# ===========================
# Dashboard
# ===========================
@login_required
def dashboard(request):
    """Dashboard with KPI cards for key metrics."""
    from datetime import date
    from decimal import Decimal
    from django.db.models import Q, F, Sum, Count, DecimalField, Value, Exists, OuterRef
    from django.db.models.functions import Coalesce
    from django.db.models.expressions import ExpressionWrapper

    # KPI 1: Leases with unpaid debt — total_debt = total_due - total_paid
    # Advance payments are already reflected in ledger entries (auto-generated as paid).
    # Overpayments create a negative balance that offsets future months.
    today = date.today()

    all_leases = Lease.objects.annotate(
        total_due=Coalesce(Sum('payment_ledgers__amount_due'), Value(0, output_field=DecimalField(max_digits=10, decimal_places=2))),
        total_paid=Coalesce(Sum('payment_ledgers__amount_paid'), Value(0, output_field=DecimalField(max_digits=10, decimal_places=2))),
        entry_count=Count('payment_ledgers')
    )

    unpaid_leases = []
    for lease in all_leases:
        if lease.entry_count == 0 and lease.start_date and lease.start_date <= today:
            # Implicit debt — no ledger entries at all
            months_behind = (today.year * 12 + today.month) - (lease.start_date.year * 12 + lease.start_date.month) + 1
            if months_behind < 1:
                months_behind = 1
            implicit_due = lease.monthly_payment * months_behind
            lease.total_debt = implicit_due - (lease.monthly_payment * (lease.advance_months or 0)) - (lease.deposit or Decimal('0'))
        else:
            lease.total_debt = lease.total_due - lease.total_paid

        if lease.total_debt > 0:
            unpaid_leases.append(lease)

    unpaid_leases.sort(key=lambda l: l.total_debt, reverse=True)
    unpaid_leases_count = len(unpaid_leases)
    unpaid_total_sum = sum(lease.total_debt for lease in unpaid_leases)

    # Calculate periods due for each unpaid lease
    for lease in unpaid_leases:
        if lease.monthly_payment and lease.monthly_payment > 0:
            lease.periods_due = int(lease.total_debt / lease.monthly_payment)
        else:
            lease.periods_due = 0

    # KPI 2: Units with Meter Debts (units with billed_amount > 0 and no payment recorded)
    # MeterLedger has no payment field, so "unpaid" = billed_amount > 0 exists
    units_with_meter_debt = Unit.objects.annotate(
        has_unpaid_meter=Exists(
            Meter.objects.filter(
                unit=OuterRef('pk'),
                ledgers__billed_amount__gt=0
            )
        )
    ).filter(has_unpaid_meter=True)
    units_with_meter_debt_count = units_with_meter_debt.count()

    # KPI 3: Total Active Leases
    active_leases_count = Lease.objects.filter(is_active=True).count()

    # KPI 4: Total Units
    total_units_count = Unit.objects.count()

    # KPI 5: Sales — units with active sale status
    for_sale_units = Unit.objects.filter(sale_status=SaleStatus.FOR_SALE).select_related('location').order_by('name')[:10]
    reserved_units = Unit.objects.filter(sale_status=SaleStatus.RESERVED).select_related('location').order_by('name')[:10]
    sold_partial_units = Unit.objects.filter(sale_status=SaleStatus.SOLD_PARTIAL).select_related('location').order_by('name')[:10]

    for_sale_count = Unit.objects.filter(sale_status=SaleStatus.FOR_SALE).count()
    reserved_count = Unit.objects.filter(sale_status=SaleStatus.RESERVED).count()
    sold_partial_count = Unit.objects.filter(sale_status=SaleStatus.SOLD_PARTIAL).count()
    sold_paid_count = Unit.objects.filter(sale_status=SaleStatus.SOLD_PAID).count()

    # Calculate outstanding receivables from sold units
    sold_units_with_balance = Unit.objects.filter(sale_status=SaleStatus.SOLD_PARTIAL)
    total_receivables = Decimal('0')
    for u in sold_units_with_balance:
        bal = u.sale_balance or Decimal('0')
        if bal > 0:
            total_receivables += bal

    # Combine all sale units for preview
    all_sale_units = list(for_sale_units) + list(reserved_units) + list(sold_partial_units)

    context = {
        'unpaid_leases_count': unpaid_leases_count,
        'unpaid_total_sum': unpaid_total_sum,
        'unpaid_leases': unpaid_leases[:10],  # preview on dashboard
        'units_with_meter_debt_count': units_with_meter_debt_count,
        'units_with_meter_debt': units_with_meter_debt[:20],
        'active_leases_count': active_leases_count,
        'total_units_count': total_units_count,
        # Sales KPIs
        'for_sale_count': for_sale_count,
        'reserved_count': reserved_count,
        'sold_partial_count': sold_partial_count,
        'sold_paid_count': sold_paid_count,
        'total_receivables': total_receivables,
        'sale_units': all_sale_units[:10],
    }
    return render(request, 'locations/dashboard.html', context)


# ===========================
# Filtered List Views (Dashboard drill-downs)
# ===========================
@login_required
def unpaid_ledgers_list(request):
    """List all leases that have unpaid debt."""
    from datetime import date
    from decimal import Decimal
    from django.db.models import Sum, Count, DecimalField, Value
    from django.db.models.functions import Coalesce

    today = date.today()

    all_leases = Lease.objects.annotate(
        total_due=Coalesce(Sum('payment_ledgers__amount_due'), Value(0, output_field=DecimalField(max_digits=10, decimal_places=2))),
        total_paid=Coalesce(Sum('payment_ledgers__amount_paid'), Value(0, output_field=DecimalField(max_digits=10, decimal_places=2))),
        entry_count=Count('payment_ledgers')
    )

    all_unpaid_leases = []
    for lease in all_leases:
        if lease.entry_count == 0 and lease.start_date and lease.start_date <= today:
            # No ledger entries at all — implicit debt
            months_behind = (today.year * 12 + today.month) - (lease.start_date.year * 12 + lease.start_date.month) + 1
            if months_behind < 1:
                months_behind = 1
            lease.total_debt = lease.monthly_payment * months_behind
        else:
            lease.total_debt = lease.total_due - lease.total_paid

        if lease.total_debt > 0:
            all_unpaid_leases.append(lease)

    all_unpaid_leases.sort(key=lambda l: l.total_debt, reverse=True)

    paginator = Paginator(all_unpaid_leases, LEASES_PER_PAGE)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'locations/unpaid_ledgers_list.html', {
        'page_obj': page_obj,
        'title': _('Unpaid Leases'),
    })


@login_required
def units_with_meter_debt_list(request):
    """List all units that have meter entries with billed amounts."""
    from django.db.models import Exists, OuterRef
    units = Unit.objects.annotate(
        has_unpaid_meter=Exists(
            Meter.objects.filter(
                unit=OuterRef('pk'),
                ledgers__billed_amount__gt=0
            )
        )
    ).filter(has_unpaid_meter=True).select_related('location').order_by('name')
    paginator = Paginator(units, UNITS_PER_PAGE)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'locations/units_with_meter_debt_list.html', {
        'page_obj': page_obj,
        'title': _('Units with Meter Debts'),
    })


# ===========================
# Location CRUD
# ===========================
@login_required
def location_list(request):
    locations = Location.objects.all().order_by('name')
    paginator = Paginator(locations, LOCATIONS_PER_PAGE)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'locations/location_list.html', {'page_obj': page_obj})


@admin_required
def location_create(request):
    if request.method == 'POST':
        form = LocationForm(request.POST)
        if form.is_valid():
            location = form.save()
            messages.success(request, _('Location "{name}" created successfully.').format(name=location.name))
            return redirect('/locations/')
    else:
        form = LocationForm()
    return render(request, 'locations/location_form.html', {'form': form, 'title': _('Create Location')})


@admin_required
def location_update(request, uuid):
    location = get_object_or_404(Location, uuid=uuid)
    if request.method == 'POST':
        form = LocationForm(request.POST, instance=location)
        if form.is_valid():
            form.save()
            messages.success(request, _('Location "{name}" updated successfully.').format(name=location.name))
            return redirect('/locations/')
    else:
        form = LocationForm(instance=location)
    return render(request, 'locations/location_form.html', {'form': form, 'title': _('Edit Location'), 'editing_location': location})


@super_user_required
@require_POST
def location_delete(request, uuid):
    location = get_object_or_404(Location, uuid=uuid)
    name = location.name
    location.delete()
    messages.success(request, _('Location "{name}" deleted successfully.').format(name=name))
    return redirect('/locations/')


# ===========================
# Location Detail
# ===========================
@login_required
def location_detail(request, uuid):
    location = get_object_or_404(Location, uuid=uuid)
    units = location.units.all().order_by('name')
    paginator = Paginator(units, UNITS_PER_PAGE)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'locations/location_detail.html', {
        'location': location,
        'page_obj': page_obj,
    })


# ===========================
# Unit CRUD
# ===========================
@login_required
def unit_create(request, location_uuid):
    location = get_object_or_404(Location, uuid=location_uuid)
    if request.method == 'POST':
        form = UnitForm(request.POST)
        if form.is_valid():
            unit = form.save(commit=False)
            unit.location = location
            unit.save()
            messages.success(request, _('Unit "{name}" created successfully.').format(name=unit.name))
            return redirect('/locations/' + str(location_uuid) + '/')
    else:
        form = UnitForm()
    return render(request, 'locations/unit_form.html', {
        'form': form, 'title': _('Add Unit'), 'location': location,
    })


@login_required
def unit_update(request, location_uuid, unit_uuid):
    unit = get_object_or_404(Unit, uuid=unit_uuid, location__uuid=location_uuid)
    if request.method == 'POST':
        form = UnitForm(request.POST, instance=unit)
        if form.is_valid():
            form.save()
            messages.success(request, _('Unit "{name}" updated successfully.').format(name=unit.name))
            return redirect('/locations/' + str(location_uuid) + '/')
    else:
        form = UnitForm(instance=unit)
    return render(request, 'locations/unit_form.html', {
        'form': form, 'title': _('Edit Unit'), 'location': unit.location,
    })


@super_user_required
@require_POST
def unit_delete(request, location_uuid, unit_uuid):
    unit = get_object_or_404(Unit, uuid=unit_uuid, location__uuid=location_uuid)
    name = unit.name
    unit.delete()
    messages.success(request, _('Unit "{name}" deleted successfully.').format(name=name))
    return redirect('/locations/' + str(location_uuid) + '/')


# ===========================
# Unit Detail
# ===========================
@login_required
def unit_detail(request, location_uuid, unit_uuid):
    unit = get_object_or_404(Unit, uuid=unit_uuid, location__uuid=location_uuid)
    meters = unit.meters.all().order_by('name')
    parking = unit.parking_assignments.all().order_by('label')
    available_parking = ParkingPlace.objects.filter(location=unit.location, unit__isnull=True).order_by('label')
    lease_ledgers = []
    if unit.lease:
        lease_ledgers = list(unit.lease.payment_ledgers.all().order_by('year', 'month'))
        # Compute running balance and mark credit-covered months
        balance = 0
        for entry in sorted(lease_ledgers, key=lambda e: (e.year, e.month)):
            entry.balance_before = balance
            balance += (entry.amount_due or 0) - (entry.amount_paid or 0)
            entry.running_balance = balance
            entry.effectively_paid = entry.balance_before < 0
        lease_ledgers.reverse()

    # Sale payments — calculate remaining balance progressively
    sale_payments = list(unit.sale_payments.all().order_by('due_date'))
    total_sale = unit.sale_price or Decimal('0')
    remaining = total_sale

    for sp in sale_payments:
        # Amount due for this row = remaining before this payment
        sp.display_amount_due = remaining
        paid = sp.amount_paid or Decimal('0')
        remaining -= paid
        # Running balance = what's left after this payment (negative = still owed)
        sp.running_balance = -remaining

    return render(request, 'locations/unit_detail.html', {
        'unit': unit,
        'meters': meters,
        'parking': parking,
        'available_parking': available_parking,
        'lease_ledgers': lease_ledgers,
        'sale_payments': sale_payments,
    })


@login_required
@require_POST
def unit_assign_parking(request, location_uuid, unit_uuid):
    """Assign an available parking place to this unit."""
    unit = get_object_or_404(Unit, uuid=unit_uuid, location__uuid=location_uuid)
    parking_uuid = request.POST.get('parking_uuid')
    
    if parking_uuid:
        parking = get_object_or_404(ParkingPlace, uuid=parking_uuid, location__uuid=location_uuid, unit__isnull=True)
        parking.unit = unit
        parking.save(update_fields=['unit', 'updated_at'])
        messages.success(request, _('Parking "{label}" assigned to this unit.').format(label=parking.label))
    
    return redirect('/locations/' + str(location_uuid) + '/units/' + str(unit_uuid) + '/')


@login_required
@require_POST
def unit_unassign_parking(request, location_uuid, unit_uuid, parking_uuid):
    """Unassign a parking place from this unit."""
    unit = get_object_or_404(Unit, uuid=unit_uuid, location__uuid=location_uuid)
    parking = get_object_or_404(ParkingPlace, uuid=parking_uuid, unit=unit)
    
    parking.unit = None
    parking.save(update_fields=['unit', 'updated_at'])
    messages.success(request, _('Parking "{label}" unassigned from this unit.').format(label=parking.label))
    
    return redirect('/locations/' + str(location_uuid) + '/units/' + str(unit_uuid) + '/')


# ===========================
# Meter CRUD
# ===========================
@login_required
def meter_create(request, location_uuid, unit_uuid):
    unit = get_object_or_404(Unit, uuid=unit_uuid, location__uuid=location_uuid)
    if request.method == 'POST':
        form = MeterForm(request.POST, lock_unit=True)
        if form.is_valid():
            meter = form.save(commit=False)
            meter.unit = unit
            meter.save()
            messages.success(request, _('Meter "{name}" created successfully.').format(name=meter.name))
            return redirect('/locations/' + str(location_uuid) + '/units/' + str(unit_uuid) + '/')
    else:
        form = MeterForm(lock_unit=True)
    return render(request, 'locations/meter_form.html', {
        'form': form, 'title': _('Add Meter'), 'unit': unit,
    })


@login_required
def meter_update(request, location_uuid, unit_uuid, meter_uuid):
    meter = get_object_or_404(Meter, uuid=meter_uuid, unit__uuid=unit_uuid)
    if request.method == 'POST':
        form = MeterForm(request.POST, instance=meter)
        if form.is_valid():
            form.save()
            messages.success(request, _('Meter "{name}" updated successfully.').format(name=meter.name))
            return redirect('/locations/' + str(meter.unit.location.uuid) + '/units/' + str(meter.unit.uuid) + '/')
    else:
        form = MeterForm(instance=meter)
    return render(request, 'locations/meter_form.html', {
        'form': form, 'title': _('Edit Meter'), 'unit': meter.unit,
    })


@super_user_required
@require_POST
def meter_delete(request, location_uuid, unit_uuid, meter_uuid):
    meter = get_object_or_404(Meter, uuid=meter_uuid, unit__uuid=unit_uuid)
    name = meter.name
    meter.delete()
    messages.success(request, _('Meter "{name}" deleted successfully.').format(name=name))
    return redirect('/locations/' + str(location_uuid) + '/units/' + str(unit_uuid) + '/')


# ===========================
# Meter Ledger CRUD
# ===========================
@login_required
def meter_ledger_list(request, location_uuid, unit_uuid, meter_uuid):
    meter = get_object_or_404(Meter, uuid=meter_uuid, unit__uuid=unit_uuid)
    ledgers = meter.ledgers.all().order_by('-year', '-month')
    paginator = Paginator(ledgers, LEDGERS_PER_PAGE)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'locations/meter_ledger_list.html', {
        'meter': meter, 'page_obj': page_obj,
    })


@login_required
def meter_ledger_create(request, location_uuid, unit_uuid, meter_uuid):
    meter = get_object_or_404(Meter, uuid=meter_uuid, unit__uuid=unit_uuid)
    if request.method == 'POST':
        form = MeterLedgerForm(request.POST)
        if form.is_valid():
            ledger = form.save(commit=False)
            ledger.meter = meter
            ledger.save()
            messages.success(request, _('Ledger entry created successfully.'))
            return redirect('/locations/' + str(location_uuid) + '/units/' + str(unit_uuid) + '/meters/' + str(meter_uuid) + '/ledger/')
    else:
        form = MeterLedgerForm()
    return render(request, 'locations/meter_ledger_form.html', {
        'form': form, 'title': _('Add Ledger Entry'), 'meter': meter,
    })


@login_required
def meter_ledger_update(request, location_uuid, unit_uuid, meter_uuid, ledger_uuid):
    ledger = get_object_or_404(MeterLedger, uuid=ledger_uuid, meter__uuid=meter_uuid)
    if request.method == 'POST':
        form = MeterLedgerForm(request.POST, instance=ledger)
        if form.is_valid():
            form.save()
            messages.success(request, _('Ledger entry updated successfully.'))
            return redirect('/locations/' + str(location_uuid) + '/units/' + str(unit_uuid) + '/meters/' + str(meter_uuid) + '/ledger/')
    else:
        form = MeterLedgerForm(instance=ledger)
    return render(request, 'locations/meter_ledger_form.html', {
        'form': form, 'title': _('Edit Ledger Entry'), 'meter': ledger.meter,
    })


@admin_required
@require_POST
def meter_ledger_settle(request, location_uuid, unit_uuid, meter_uuid, ledger_uuid):
    ledger = get_object_or_404(MeterLedger, uuid=ledger_uuid, meter__uuid=meter_uuid)
    ledger.billed_amount = 0
    ledger.settled_at = timezone.localdate()
    ledger.save(update_fields=['billed_amount', 'settled_at', 'updated_at'])
    messages.success(request, _('Meter expense reset to zero because the tenant payment was verified.'))
    return redirect('/locations/' + str(location_uuid) + '/units/' + str(unit_uuid) + '/meters/' + str(meter_uuid) + '/ledger/')


@super_user_required
@require_POST
def meter_ledger_delete(request, location_uuid, unit_uuid, meter_uuid, ledger_uuid):
    ledger = get_object_or_404(MeterLedger, uuid=ledger_uuid, meter__uuid=meter_uuid)
    ledger.delete()
    messages.success(request, _('Ledger entry deleted successfully.'))
    return redirect('/locations/' + str(location_uuid) + '/units/' + str(unit_uuid) + '/meters/' + str(meter_uuid) + '/ledger/')


# ===========================
# Parking CRUD
# ===========================
@login_required
def parking_create(request, location_uuid):
    location = get_object_or_404(Location, uuid=location_uuid)
    if request.method == 'POST':
        form = ParkingPlaceForm(request.POST)
        form._location = location
        if form.is_valid():
            parking = form.save(commit=False)
            parking.location = location
            parking.save()
            messages.success(request, _('Parking place "{label}" created.').format(label=parking.label))
            return redirect('/locations/' + str(location_uuid) + '/')
    else:
        form = ParkingPlaceForm(initial={'location': location})
    return render(request, 'locations/parking_form.html', {
        'form': form, 'title': _('Add Parking Place'), 'location': location,
    })


@login_required
def parking_bulk_create(request, location_uuid):
    """Bulk create multiple parking places."""
    location = get_object_or_404(Location, uuid=location_uuid)
    
    if request.method == 'POST':
        form = ParkingBulkCreateForm(request.POST)
        if form.is_valid():
            labels = form.cleaned_data['labels']
            covered = form.cleaned_data['covered']
            
            created_count = 0
            skipped_count = 0
            
            for label in labels:
                if ParkingPlace.objects.filter(location=location, label=label).exists():
                    skipped_count += 1
                    messages.warning(request, _('Parking place "{label}" already exists, skipped.').format(label=label))
                    continue
                
                ParkingPlace.objects.create(
                    location=location,
                    label=label,
                    covered=covered,
                )
                created_count += 1
            
            messages.success(
                request, 
                _('Successfully created {count} parking place(s).').format(count=created_count) +
                (f' {skipped_count} skipped (duplicates).' if skipped_count else '')
            )
            return redirect('/locations/' + str(location_uuid) + '/')
    else:
        form = ParkingBulkCreateForm(location=location)
    
    return render(request, 'locations/parking_bulk_form.html', {
        'form': form,
        'title': _('Add Parking Places'),
        'location': location,
    })


@login_required
def parking_list(request, location_uuid=None):
    """List all parking places, optionally filtered by location."""
    location_filter = request.GET.get('location')

    if location_uuid:
        location = get_object_or_404(Location, uuid=location_uuid)
        parking_qs = ParkingPlace.objects.filter(location=location).select_related('unit', 'location').order_by('label')
    elif location_filter:
        location = get_object_or_404(Location, uuid=location_filter)
        parking_qs = ParkingPlace.objects.filter(location=location).select_related('unit', 'location').order_by('label')
    else:
        location = None
        parking_qs = ParkingPlace.objects.all().select_related('unit', 'location').order_by('location__name', 'label')

    status_filter = request.GET.get('status', 'all')

    if status_filter == 'assigned':
        parking_qs = parking_qs.filter(unit__isnull=False)
    elif status_filter == 'unassigned':
        parking_qs = parking_qs.filter(unit__isnull=True)

    total = parking_qs.count()
    assigned_count = parking_qs.filter(unit__isnull=False).count()
    unassigned_count = parking_qs.filter(unit__isnull=True).count()

    locations = Location.objects.all().order_by('name')

    context = {
        'location': location,
        'locations': locations,
        'parking_places': parking_qs,
        'status_filter': status_filter,
        'total': total,
        'assigned_count': assigned_count,
        'unassigned_count': unassigned_count,
    }
    return render(request, 'locations/parking_list.html', context)


@login_required
def parking_update(request, location_uuid, parking_uuid):
    parking = get_object_or_404(ParkingPlace, uuid=parking_uuid, location__uuid=location_uuid)
    if request.method == 'POST':
        form = ParkingPlaceForm(request.POST, instance=parking)
        if form.is_valid():
            form.save()
            messages.success(request, _('Parking place "{label}" updated.').format(label=parking.label))
            return redirect('/locations/' + str(location_uuid) + '/')
    else:
        form = ParkingPlaceForm(instance=parking)
    return render(request, 'locations/parking_form.html', {
        'form': form, 'title': _('Edit Parking Place'), 'location': parking.location,
    })


@super_user_required
@require_POST
def parking_delete(request, location_uuid, parking_uuid):
    parking = get_object_or_404(ParkingPlace, uuid=parking_uuid, location__uuid=location_uuid)
    label = parking.label
    parking.delete()
    messages.success(request, _('Parking place "{label}" deleted.').format(label=label))
    return redirect('/locations/' + str(location_uuid) + '/')


# ===========================
# Lease CRUD
# ===========================
@login_required
def lease_list(request):
    from django.db.models import Q

    leases = Lease.objects.all()
    search_query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()

    if status_filter == 'active':
        leases = leases.filter(is_active=True)
    elif status_filter == 'inactive':
        leases = leases.filter(is_active=False)

    if search_query:
        leases = leases.filter(
            Q(display_id__icontains=search_query)
            | Q(name__icontains=search_query)
            | Q(phone__icontains=search_query)
        )

    leases = leases.order_by('-created_at')
    paginator = Paginator(leases, LEASES_PER_PAGE)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Summary counts
    summary = {
        'active': Lease.objects.filter(is_active=True).count(),
        'inactive': Lease.objects.filter(is_active=False).count(),
    }

    return render(request, 'locations/lease_list.html', {
        'page_obj': page_obj,
        'search_query': search_query,
        'status_filter': status_filter,
        'summary': summary,
    })


@login_required
def lease_detail(request, uuid):
    lease = get_object_or_404(Lease, uuid=uuid)
    units = lease.assigned_units.all().order_by('name')
    return render(request, 'locations/lease_detail.html', {
        'lease': lease,
        'units': units,
    })


@admin_required
def lease_create(request):
    if request.method == 'POST':
        form = LeaseForm(request.POST, request.FILES)
        if form.is_valid():
            lease = form.save()
            messages.success(request, _('Lease "{name}" created successfully.').format(name=lease.name))
            return redirect('/leases/')
    else:
        form = LeaseForm()
    return render(request, 'locations/lease_form.html', {
        'form': form, 'title': _('Create Lease'),
    })


@admin_required
def lease_update(request, uuid):
    lease = get_object_or_404(Lease, uuid=uuid)
    if request.method == 'POST':
        form = LeaseForm(request.POST, request.FILES, instance=lease)
        if form.is_valid():
            form.save()
            messages.success(request, _('Lease "{name}" updated successfully.').format(name=lease.name))
            return redirect('/leases/')
    else:
        form = LeaseForm(instance=lease)
    return render(request, 'locations/lease_form.html', {
        'form': form, 'title': _('Edit Lease'), 'editing_lease': lease,
    })


@super_user_required
@require_POST
def lease_delete(request, uuid):
    lease = get_object_or_404(Lease, uuid=uuid)
    name = lease.name
    lease.delete()
    messages.success(request, _('Lease "{name}" deleted successfully.').format(name=name))
    return redirect('/leases/')


# ===========================
# Lease Ledger CRUD
# ===========================
@login_required
def lease_ledger_list(request, lease_uuid):
    lease = get_object_or_404(Lease, uuid=lease_uuid)
    ledgers = list(lease.payment_ledgers.all().order_by('year', 'month'))

    # Compute running balance and mark credit-covered months as effectively paid
    balance = 0
    total_due = 0
    total_paid = 0
    for entry in ledgers:
        entry.balance_before = balance
        total_due += entry.amount_due or 0
        total_paid += entry.amount_paid or 0
        balance += (entry.amount_due or 0) - (entry.amount_paid or 0)
        entry.running_balance = balance
        # If prior balance was negative (credit), this month is covered by rollover
        entry.effectively_paid = entry.balance_before < 0

    # Reverse for display (newest first)
    ledgers.reverse()

    paginator = Paginator(ledgers, LEDGERS_PER_PAGE)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'locations/lease_ledger_list.html', {
        'lease': lease,
        'page_obj': page_obj,
        'total_due': total_due,
        'total_paid': total_paid,
        'running_balance': total_due - total_paid if ledgers else 0,
    })


@login_required
def lease_ledger_print(request, lease_uuid):
    """Print-friendly lease ledger view."""
    from accounts.models import CompanyProfile

    lease = get_object_or_404(Lease, uuid=lease_uuid)
    ledgers = list(lease.payment_ledgers.all().order_by('year', 'month'))
    units = lease.assigned_units.select_related('location').prefetch_related('meters__ledgers')

    balance = 0
    total_due = 0
    total_paid = 0
    for entry in ledgers:
        entry.balance_before = balance
        total_due += entry.amount_due or 0
        total_paid += entry.amount_paid or 0
        balance += (entry.amount_due or 0) - (entry.amount_paid or 0)
        entry.running_balance = balance
        entry.effectively_paid = balance <= 0

    # Remaining balance: positive = tenant owes, negative = tenant has credit
    remaining_balance = total_due - total_paid if ledgers else 0

    # Company profile for print header
    company = CompanyProfile.get_or_create_default()

    meter_rows = []
    meter_total_outstanding = 0
    meter_open_count = 0
    meter_settled_count = 0
    meter_count = 0

    for unit in units:
        for meter in unit.meters.all():
            meter_count += 1
            latest_ledger = sorted(
                meter.ledgers.all(),
                key=lambda item: (item.year, item.month),
                reverse=True,
            )
            latest_ledger = latest_ledger[0] if latest_ledger else None
            outstanding = latest_ledger.billed_amount if latest_ledger and latest_ledger.billed_amount else 0
            if outstanding > 0:
                meter_open_count += 1
                meter_total_outstanding += outstanding
            else:
                meter_settled_count += 1
            meter_rows.append({
                'unit': unit,
                'meter': meter,
                'ledger': latest_ledger,
                'outstanding': outstanding,
            })

    return render(request, 'locations/lease_ledger_print.html', {
        'lease': lease,
        'ledgers': ledgers,
        'total_due': total_due,
        'total_paid': total_paid,
        'remaining_balance': remaining_balance,
        'running_balance': remaining_balance,
        'meter_rows': meter_rows,
        'meter_count': meter_count,
        'meter_open_count': meter_open_count,
        'meter_settled_count': meter_settled_count,
        'meter_total_outstanding': meter_total_outstanding,
        'company': company,
        'now': __import__('datetime').date.today(),
    })


@login_required
def lease_ledger_create(request, lease_uuid):
    lease = get_object_or_404(Lease, uuid=lease_uuid)
    if request.method == 'POST':
        form = LeaseLedgerForm(request.POST, request.FILES, lease=lease)
        if form.is_valid():
            ledger = form.save(commit=False)
            ledger.lease = lease
            ledger.save()
            messages.success(request, _('Ledger entry created successfully.'))
            return redirect('/leases/' + str(lease_uuid) + '/ledger/')
    else:
        form = LeaseLedgerForm(lease=lease, initial={'amount_due': lease.monthly_payment})
    return render(request, 'locations/lease_ledger_form.html', {
        'form': form, 'title': _('Add Ledger Entry'), 'lease': lease,
    })


@login_required
def lease_ledger_update(request, lease_uuid, ledger_uuid):
    ledger = get_object_or_404(LeaseLedger, uuid=ledger_uuid, lease__uuid=lease_uuid)
    if request.method == 'POST':
        form = LeaseLedgerForm(request.POST, request.FILES, instance=ledger, lease=ledger.lease)
        if form.is_valid():
            form.save()
            messages.success(request, _('Ledger entry updated successfully.'))
            return redirect('/leases/' + str(lease_uuid) + '/ledger/')
    else:
        form = LeaseLedgerForm(instance=ledger, lease=ledger.lease)
    return render(request, 'locations/lease_ledger_form.html', {
        'form': form, 'title': _('Edit Ledger Entry'), 'lease': ledger.lease,
    })


@super_user_required
@require_POST
def lease_ledger_delete(request, lease_uuid, ledger_uuid):
    ledger = get_object_or_404(LeaseLedger, uuid=ledger_uuid, lease__uuid=lease_uuid)
    ledger.delete()
    messages.success(request, _('Ledger entry deleted successfully.'))
    return redirect('/leases/' + str(lease_uuid) + '/ledger/')


# ===========================
# Sales
# ===========================
@login_required
def sale_list(request):
    """List of units for sale with status filters."""
    from django.db.models import Q

    units = Unit.objects.select_related('location').filter(
        sale_status__in=[SaleStatus.FOR_SALE, SaleStatus.RESERVED,
                         SaleStatus.SOLD_PARTIAL, SaleStatus.SOLD_PAID]
    )
    status_filter = request.GET.get('status', '').strip()
    search_query = request.GET.get('q', '').strip()

    if status_filter and status_filter != 'all':
        units = units.filter(sale_status=status_filter)
    if search_query:
        units = units.filter(
            Q(name__icontains=search_query)
            | Q(buyer_name__icontains=search_query)
            | Q(location__name__icontains=search_query)
        )

    units = units.order_by('location__name', 'name')
    paginator = Paginator(units, LEASES_PER_PAGE)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Summary counts
    summary = {
        'for_sale': Unit.objects.filter(sale_status=SaleStatus.FOR_SALE).count(),
        'reserved': Unit.objects.filter(sale_status=SaleStatus.RESERVED).count(),
        'sold_partial': Unit.objects.filter(sale_status=SaleStatus.SOLD_PARTIAL).count(),
        'sold_paid': Unit.objects.filter(sale_status=SaleStatus.SOLD_PAID).count(),
    }

    return render(request, 'locations/sale_list.html', {
        'page_obj': page_obj,
        'search_query': search_query,
        'status_filter': status_filter,
        'summary': summary,
    })


@login_required
def sale_print(request, unit_uuid):
    """Print-friendly sale report for a unit."""
    from accounts.models import CompanyProfile

    unit = get_object_or_404(Unit, uuid=unit_uuid)
    payments = list(unit.sale_payments.all().order_by('due_date'))

    total_sale = unit.sale_price or Decimal('0')
    remaining = total_sale
    total_paid = Decimal('0')

    for sp in payments:
        paid = sp.amount_paid or Decimal('0')
        total_paid += paid
        sp.display_amount_due = remaining
        remaining -= paid
        sp.running_balance = -remaining

    # Negate remaining balance (client owes)
    display_remaining = -remaining if remaining > 0 else Decimal('0')
    company = CompanyProfile.get_or_create_default()

    return render(request, 'locations/sale_print.html', {
        'unit': unit,
        'payments': payments,
        'total_sale': total_sale,
        'total_paid': total_paid,
        'remaining_balance': display_remaining,
        'company': company,
        'now': __import__('datetime').date.today(),
    })


# ===========================
# Sale Payment CRUD
# ===========================
@login_required
def sale_payment_create(request, location_uuid, unit_uuid):
    unit = get_object_or_404(Unit, uuid=unit_uuid, location__uuid=location_uuid)
    if request.method == 'POST':
        form = SalePaymentForm(request.POST, request.FILES)
        if form.is_valid():
            sp = form.save(commit=False)
            sp.unit = unit
            sp.save()
            messages.success(request, _('Sale payment installment #{num} created.').format(num=sp.installment_number))
            return redirect('/locations/' + str(location_uuid) + '/units/' + str(unit_uuid) + '/')
    else:
        next_num = unit.sale_payments.count() + 1
        form = SalePaymentForm(initial={'installment_number': next_num})
    return render(request, 'locations/sale_payment_form.html', {
        'form': form, 'title': _('Add Sale Payment'), 'unit': unit,
    })


@login_required
def sale_payment_update(request, location_uuid, unit_uuid, payment_uuid):
    unit = get_object_or_404(Unit, uuid=unit_uuid, location__uuid=location_uuid)
    sp = get_object_or_404(SalePayment, uuid=payment_uuid, unit=unit)
    if request.method == 'POST':
        form = SalePaymentForm(request.POST, request.FILES, instance=sp)
        if form.is_valid():
            form.save()
            messages.success(request, _('Sale payment updated successfully.'))
            return redirect('/locations/' + str(location_uuid) + '/units/' + str(unit_uuid) + '/')
    else:
        form = SalePaymentForm(instance=sp)
    return render(request, 'locations/sale_payment_form.html', {
        'form': form, 'title': _('Edit Sale Payment'), 'unit': unit, 'payment': sp,
    })


@super_user_required
@require_POST
def sale_payment_delete(request, location_uuid, unit_uuid, payment_uuid):
    unit = get_object_or_404(Unit, uuid=unit_uuid, location__uuid=location_uuid)
    sp = get_object_or_404(SalePayment, uuid=payment_uuid, unit=unit)
    sp.delete()
    messages.success(request, _('Sale payment deleted successfully.'))
    return redirect('/locations/' + str(location_uuid) + '/units/' + str(unit_uuid) + '/')
