from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _


class Role(models.TextChoices):
    SUPER_USER = 'super_user', _('Super User')
    ADMIN = 'admin', _('Admin')
    DATA_ENTRY_CLERK = 'data_entry_clerk', _('Data Entry Clerk')


class User(AbstractUser):
    """Custom user model with role-based access control."""
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
