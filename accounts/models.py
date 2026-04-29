import hashlib
import secrets

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _
import uuid


class Role(models.TextChoices):
    SUPER_USER = 'super_user', _('Super User')
    ADMIN = 'admin', _('Admin')
    DATA_ENTRY_CLERK = 'data_entry_clerk', _('Data Entry Clerk')


class User(AbstractUser):
    """Custom user model with role-based access control."""
    uuid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.DATA_ENTRY_CLERK,
    )
    is_active = models.BooleanField(default=True)
    preferred_language = models.CharField(
        max_length=5,
        default='en',
        verbose_name=_('Preferred Language'),
    )

    def __str__(self):
        return f'{self.username} ({self.get_role_display()})'

    def save(self, *args, **kwargs):
        if self.username:
            self.username = self.username.strip().lower()
        super().save(*args, **kwargs)

    @property
    def is_super_user(self):
        return self.role == Role.SUPER_USER or self.is_superuser

    @property
    def is_admin(self):
        return self.role in [Role.SUPER_USER, Role.ADMIN]

    @property
    def can_edit(self):
        return self.role != Role.DATA_ENTRY_CLERK or True  # all roles can edit


class ApiKeyScope(models.TextChoices):
    KESCO_METER_WRITE = 'kesco_meter_write', _('KESCO meter write')
    LEASE_REPORT_READ = 'lease_report_read', _('Lease report read')
    SETTLEMENT_WRITE = 'settlement_write', _('Settlement write')


class UserApiKey(models.Model):
    """Least-privilege API key owned by a user."""
    uuid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='api_keys',
        verbose_name=_('User'),
    )
    name = models.CharField(
        max_length=100,
        verbose_name=_('Key Name'),
    )
    scope = models.CharField(
        max_length=50,
        choices=ApiKeyScope.choices,
        verbose_name=_('Scope'),
    )
    key_prefix = models.CharField(
        max_length=16,
        db_index=True,
        verbose_name=_('Key Prefix'),
    )
    key_hash = models.CharField(
        max_length=64,
        unique=True,
        verbose_name=_('Key Hash'),
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Active'),
    )
    last_used_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_('Last Used At'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('User API Key')
        verbose_name_plural = _('User API Keys')
        ordering = ['user__username', 'name']

    def __str__(self):
        return f'{self.name} ({self.user.username}, {self.scope})'

    @staticmethod
    def hash_key(raw_key):
        return hashlib.sha256(raw_key.encode('utf-8')).hexdigest()

    @classmethod
    def create_key(cls, *, user, name, scope):
        raw_key = 'bmgm_' + secrets.token_urlsafe(32)
        key = cls.objects.create(
            user=user,
            name=name,
            scope=scope,
            key_prefix=raw_key[:12],
            key_hash=cls.hash_key(raw_key),
        )
        return key, raw_key

    def matches(self, raw_key):
        return secrets.compare_digest(self.key_hash, self.hash_key(raw_key))


class CompanyProfile(models.Model):
    """Single company profile for the building management system."""
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    company_name = models.CharField(max_length=255, verbose_name=_('Company Name'))
    tax_number = models.CharField(max_length=50, blank=True, verbose_name=_('Tax Number'))
    registration_number = models.CharField(max_length=50, blank=True, verbose_name=_('Registration Number'))
    address = models.TextField(blank=True, verbose_name=_('Address'))
    city = models.CharField(max_length=100, blank=True, verbose_name=_('City'))
    phone = models.CharField(max_length=30, blank=True, verbose_name=_('Phone'))
    email = models.EmailField(blank=True, verbose_name=_('Email'))
    website = models.URLField(blank=True, null=True, verbose_name=_('Website'))
    logo = models.ImageField(upload_to='company/', blank=True, null=True, verbose_name=_('Logo'))
    fiscal_code = models.CharField(max_length=50, blank=True, verbose_name=_('Fiscal Code'))
    nipt = models.CharField(max_length=50, blank=True, verbose_name=_('NIPT'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Company Profile')
        verbose_name_plural = _('Company Profiles')

    def __str__(self):
        return self.company_name

    @classmethod
    def get_or_create_default(cls):
        """Get the first company profile or create a default one."""
        obj = cls.objects.first()
        if obj is None:
            obj = cls.objects.create(company_name=_('My Company'))
        return obj
