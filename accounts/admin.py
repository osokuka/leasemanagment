from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import User, Role, CompanyProfile, UserApiKey


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    model = User
    list_display = ('username', 'email', 'role', 'is_active', 'is_staff', 'last_login')
    list_filter = ('role', 'is_active', 'is_staff', 'is_superuser')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'email')}),
        (_('Role & Permissions'), {'fields': ('role', 'is_active', 'is_staff', 'is_superuser')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'role', 'password1', 'password2'),
        }),
    )
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('username',)


@admin.register(CompanyProfile)
class CompanyProfileAdmin(admin.ModelAdmin):
    model = CompanyProfile
    list_display = ('company_name', 'tax_number', 'email', 'phone', 'city')


@admin.register(UserApiKey)
class UserApiKeyAdmin(admin.ModelAdmin):
    model = UserApiKey
    list_display = ('name', 'user', 'scope', 'key_prefix', 'is_active', 'last_used_at', 'created_at')
    list_filter = ('scope', 'is_active', 'created_at')
    search_fields = ('name', 'user__username', 'key_prefix')
    readonly_fields = ('uuid', 'key_prefix', 'key_hash', 'last_used_at', 'created_at', 'updated_at')
