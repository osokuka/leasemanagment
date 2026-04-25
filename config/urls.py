"""
Root URL configuration.
Language is handled by UserLanguageMiddleware — no i18n URL prefixes needed.
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import path, include
from locations import views as location_views
from accounts import views as accounts_views

urlpatterns = [
    path('i18n/', include('django.conf.urls.i18n')),
    path('admin/', admin.site.urls),
    path('', lambda request: redirect('dashboard', permanent=False)),
    # Language switcher — saves to User.preferred_language
    path('set-language/', accounts_views.set_language_view, name='set_language'),

    # Dashboard
    path('dashboard/', location_views.dashboard, name='dashboard'),
    path('dashboard/unpaid-ledgers/', location_views.unpaid_ledgers_list, name='unpaid_ledgers'),
    path('dashboard/meter-debts/', location_views.units_with_meter_debt_list, name='units_with_meter_debt'),

    # Accounts
    path('', include('accounts.urls')),

    # Locations (nested app)
    path('locations/', include('locations.urls')),

    # Lease CRUD (top-level)
    path('leases/', location_views.lease_list, name='lease_list'),
    path('leases/create/', location_views.lease_create, name='lease_create'),
    path('leases/<uuid:uuid>/', location_views.lease_detail, name='lease_detail'),
    path('leases/<uuid:uuid>/edit/', location_views.lease_update, name='lease_update'),
    path('leases/<uuid:uuid>/delete/', location_views.lease_delete, name='lease_delete'),

    # Lease Ledger CRUD
    path('leases/<uuid:lease_uuid>/ledger/', location_views.lease_ledger_list, name='lease_ledger_list'),
    path('leases/<uuid:lease_uuid>/ledger/print/', location_views.lease_ledger_print, name='lease_ledger_print'),
    path('leases/<uuid:lease_uuid>/ledger/create/', location_views.lease_ledger_create, name='lease_ledger_create'),
    path('leases/<uuid:lease_uuid>/ledger/<uuid:ledger_uuid>/edit/', location_views.lease_ledger_update, name='lease_ledger_update'),
    path('leases/<uuid:lease_uuid>/ledger/<uuid:ledger_uuid>/delete/', location_views.lease_ledger_delete, name='lease_ledger_delete'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
