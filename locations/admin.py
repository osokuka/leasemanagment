from django.contrib import admin
from .models import Location, Unit, Meter, MeterLedger, ParkingPlace, Lease, LeaseLedger


@admin.register(Lease)
class LeaseAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'monthly_payment', 'advance_months', 'unit_count', 'is_active', 'start_date', 'end_date')
    list_filter = ('is_active', 'start_date')
    search_fields = ('name', 'contact', 'phone', 'email')
    readonly_fields = ('uuid', 'created_at', 'updated_at')


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('name', 'address', 'focal_point', 'created_at')
    search_fields = ('name', 'address', 'focal_point')
    readonly_fields = ('uuid', 'created_at', 'updated_at')
    list_filter = ('created_at',)


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ('name', 'location', 'unit_type', 'sqm', 'is_leased_display', 'created_at')
    list_filter = ('unit_type', 'location')
    search_fields = ('name',)
    readonly_fields = ('uuid', 'created_at', 'updated_at')

    @admin.display(boolean=True, description='Leased')
    def is_leased_display(self, obj):
        return obj.is_leased


@admin.register(Meter)
class MeterAdmin(admin.ModelAdmin):
    list_display = ('name', 'unit', 'meter_type', 'reading_metric', 'serial_number')
    list_filter = ('meter_type',)
    search_fields = ('name', 'serial_number')
    readonly_fields = ('uuid', 'created_at', 'updated_at')


@admin.register(MeterLedger)
class MeterLedgerAdmin(admin.ModelAdmin):
    list_display = ('meter', 'month', 'year', 'reading', 'billed_amount')
    list_filter = ('month', 'year', 'meter__meter_type')
    readonly_fields = ('uuid', 'created_at', 'updated_at')


@admin.register(ParkingPlace)
class ParkingPlaceAdmin(admin.ModelAdmin):
    list_display = ('label', 'location', 'unit', 'covered')
    list_filter = ('covered', 'location')
    search_fields = ('label',)
    readonly_fields = ('uuid', 'created_at', 'updated_at')


@admin.register(LeaseLedger)
class LeaseLedgerAdmin(admin.ModelAdmin):
    list_display = ('lease', 'month', 'year', 'amount_due', 'amount_paid', 'status', 'payment_date')
    list_filter = ('status', 'month', 'year')
    search_fields = ('lease__name', 'lease__display_id')
    readonly_fields = ('uuid', 'created_at', 'updated_at')
