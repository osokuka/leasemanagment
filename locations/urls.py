from django.urls import path
from . import views

app_name = 'locations'

urlpatterns = [
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
    path('<uuid:location_uuid>/parking/create/', views.parking_create, name='parking_create'),
    path('<uuid:location_uuid>/parking/<uuid:parking_uuid>/edit/', views.parking_update, name='parking_update'),
    path('<uuid:location_uuid>/parking/<uuid:parking_uuid>/delete/', views.parking_delete, name='parking_delete'),
]
