from django.urls import path
from django.conf.urls.i18n import i18n_patterns
from . import views

app_name = 'accounts'

urlpatterns = [
    # Auth
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # User CRUD
    path('users/', views.user_list, name='user_list'),
    path('users/create/', views.user_create, name='user_create'),
    path('users/<uuid:uuid>/edit/', views.user_update, name='user_update'),
    path('users/<uuid:uuid>/api-keys/create/', views.user_api_key_create, name='user_api_key_create'),
    path('users/<uuid:uuid>/api-keys/<uuid:key_uuid>/revoke/', views.user_api_key_revoke, name='user_api_key_revoke'),
    path('users/<uuid:uuid>/delete/', views.user_delete, name='user_delete'),

    # Company Profile
    path('settings/company/', views.company_profile_view, name='company_profile'),
]
