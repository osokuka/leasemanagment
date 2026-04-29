from django.urls import path
from . import views
from . import kesco_views
from . import api_views

app_name = 'locations'

urlpatterns = [
    # KESCO Integration
    path('kesco/', kesco_views.kesco_dashboard, name='kesco_dashboard'),
    path('kesco/credentials/', kesco_views.kesco_credential_list, name='kesco_credential_list'),
    path('kesco/credentials/create/', kesco_views.kesco_credential_create, name='kesco_credential_create'),
    path('kesco/credentials/<uuid:uuid>/edit/', kesco_views.kesco_credential_edit, name='kesco_credential_edit'),
    path('kesco/credentials/<uuid:uuid>/delete/', kesco_views.kesco_credential_delete, name='kesco_credential_delete'),
    path('kesco/credentials/<uuid:uuid>/login/', kesco_views.kesco_credential_login_page, name='kesco_credential_login_page'),
    path('kesco/credentials/<uuid:uuid>/save-token/', kesco_views.kesco_save_token, name='kesco_save_token'),
    path('kesco/credentials/<uuid:uuid>/trigger-sync/', kesco_views.kesco_trigger_sync, name='kesco_trigger_sync'),
    path('kesco/trigger-sync-all/', kesco_views.kesco_trigger_sync_all, name='kesco_trigger_sync_all'),
    path('kesco/api/capture-token/', kesco_views.kesco_api_capture_token, name='kesco_api_capture_token'),
    path('api/kesco/meters/upsert/', api_views.kesco_meter_upsert_api, name='api_kesco_meter_upsert'),
    path('api/leases/status/', api_views.lease_status_api, name='api_lease_status'),
    path('api/leases/<str:lease_identifier>/report/', api_views.lease_report_api, name='api_lease_report'),
    path('api/leases/<str:lease_identifier>/settle-payment/', api_views.lease_payment_settle_api, name='api_lease_payment_settle'),
    path('api/electric-debts/settle/', api_views.electric_debt_settle_api, name='api_electric_debt_settle'),

    # Location CRUD
    path('', views.location_list, name='location_list'),
    path('create/', views.location_create, name='location_create'),
    path('<uuid:uuid>/edit/', views.location_update, name='location_update'),
    path('<uuid:uuid>/delete/', views.location_delete, name='location_delete'),

    # Location Detail
    path('<uuid:uuid>/', views.location_detail, name='location_detail'),

    # Unit CRUD
    path('<uuid:location_uuid>/unit/create/', views.unit_create, name='unit_create'),
    path('<uuid:location_uuid>/unit/<uuid:unit_uuid>/edit/', views.unit_update, name='unit_update'),
    path('<uuid:location_uuid>/unit/<uuid:unit_uuid>/delete/', views.unit_delete, name='unit_delete'),

    # Unit Detail
    path('<uuid:location_uuid>/units/<uuid:unit_uuid>/', views.unit_detail, name='unit_detail'),
    path('<uuid:location_uuid>/units/<uuid:unit_uuid>/assign-parking/', views.unit_assign_parking, name='unit_assign_parking'),
    path('<uuid:location_uuid>/units/<uuid:unit_uuid>/unassign-parking/<uuid:parking_uuid>/', views.unit_unassign_parking, name='unit_unassign_parking'),

    # Meter CRUD
    path('<uuid:location_uuid>/units/<uuid:unit_uuid>/meter/create/', views.meter_create, name='meter_create'),
    path('<uuid:location_uuid>/units/<uuid:unit_uuid>/meter/<uuid:meter_uuid>/edit/', views.meter_update, name='meter_update'),
    path('<uuid:location_uuid>/units/<uuid:unit_uuid>/meter/<uuid:meter_uuid>/delete/', views.meter_delete, name='meter_delete'),

    # Meter Ledger CRUD
    path('<uuid:location_uuid>/units/<uuid:unit_uuid>/meters/<uuid:meter_uuid>/ledger/', views.meter_ledger_list, name='meter_ledger_list'),
    path('<uuid:location_uuid>/units/<uuid:unit_uuid>/meters/<uuid:meter_uuid>/ledger/create/', views.meter_ledger_create, name='meter_ledger_create'),
    path('<uuid:location_uuid>/units/<uuid:unit_uuid>/meters/<uuid:meter_uuid>/ledger/<uuid:ledger_uuid>/edit/', views.meter_ledger_update, name='meter_ledger_update'),
    path('<uuid:location_uuid>/units/<uuid:unit_uuid>/meters/<uuid:meter_uuid>/ledger/<uuid:ledger_uuid>/settle/', views.meter_ledger_settle, name='meter_ledger_settle'),
    path('<uuid:location_uuid>/units/<uuid:unit_uuid>/meters/<uuid:meter_uuid>/ledger/<uuid:ledger_uuid>/delete/', views.meter_ledger_delete, name='meter_ledger_delete'),

    # Parking CRUD
    path('parking/', views.parking_list, name='parking_list'),
    path('<uuid:location_uuid>/parking/', views.parking_list, name='parking_list'),
    path('<uuid:location_uuid>/parking/create/', views.parking_create, name='parking_create'),
    path('<uuid:location_uuid>/parking/bulk-create/', views.parking_bulk_create, name='parking_bulk_create'),
    path('<uuid:location_uuid>/parking/<uuid:parking_uuid>/edit/', views.parking_update, name='parking_update'),
    path('<uuid:location_uuid>/parking/<uuid:parking_uuid>/delete/', views.parking_delete, name='parking_delete'),

    # Sale Payment CRUD
    path('<uuid:location_uuid>/units/<uuid:unit_uuid>/sale-payment/create/', views.sale_payment_create, name='sale_payment_create'),
    path('<uuid:location_uuid>/units/<uuid:unit_uuid>/sale-payment/<uuid:payment_uuid>/edit/', views.sale_payment_update, name='sale_payment_update'),
    path('<uuid:location_uuid>/units/<uuid:unit_uuid>/sale-payment/<uuid:payment_uuid>/delete/', views.sale_payment_delete, name='sale_payment_delete'),
]
