from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from .models import User, Role


class UserCreationFormCustom(UserCreationForm):
    """Form for creating a new user."""
    role = forms.ChoiceField(
        choices=Role.choices,
        label=_('Role'),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email', 'role')
        labels = {
            'username': _('Username'),
            'email': _('Email'),
        }
        help_texts = {
            'username': _('Usernames are stored in lowercase and are not case-sensitive.'),
        }

    def __init__(self, *args, allowed_role_choices=None, **kwargs):
        super().__init__(*args, **kwargs)
        if allowed_role_choices is not None:
            self.fields['role'].choices = allowed_role_choices
            if len(allowed_role_choices) == 1:
                self.fields['role'].initial = allowed_role_choices[0][0]
        for field in self.fields.values():
            if hasattr(field, 'widget'):
                css_class = 'form-select' if isinstance(field.widget, forms.Select) else 'form-control'
                field.widget.attrs.update({'class': css_class})

    def clean_username(self):
        username = self.cleaned_data['username'].strip().lower()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError(_('A user with that username already exists.'))
        return username


class UserChangeFormCustom(UserChangeForm):
    """Form for editing an existing user."""
    new_password1 = forms.CharField(
        label=_('New password'),
        required=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}),
        help_text=_('Leave blank to keep the current password.'),
    )
    new_password2 = forms.CharField(
        label=_('Confirm new password'),
        required=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}),
    )
    role = forms.ChoiceField(
        choices=Role.choices,
        label=_('Role'),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    class Meta(UserChangeForm.Meta):
        model = User
        fields = ('username', 'email', 'role', 'is_active')
        labels = {
            'username': _('Username'),
            'email': _('Email'),
            'is_active': _('Active'),
        }
        help_texts = {
            'username': _('Usernames are stored in lowercase and are not case-sensitive.'),
        }

    def __init__(
        self,
        *args,
        can_edit_profile=True,
        can_reset_password=False,
        allowed_role_choices=None,
        can_change_role=True,
        can_change_active=True,
        **kwargs,
    ):
        self.can_reset_password = can_reset_password
        super().__init__(*args, **kwargs)
        self.fields.pop('password', None)
        if not can_edit_profile:
            for field_name in ('username', 'email', 'role', 'is_active'):
                self.fields.pop(field_name, None)
        else:
            if allowed_role_choices is not None and 'role' in self.fields:
                self.fields['role'].choices = allowed_role_choices
            if not can_change_role:
                self.fields.pop('role', None)
            if not can_change_active:
                self.fields.pop('is_active', None)
        if not can_reset_password:
            self.fields.pop('new_password1', None)
            self.fields.pop('new_password2', None)
        for field in self.fields.values():
            if hasattr(field, 'widget'):
                css_class = 'form-select' if isinstance(field.widget, forms.Select) else 'form-control'
                field.widget.attrs.update({'class': css_class})

    def clean_username(self):
        username = self.cleaned_data['username'].strip().lower()
        duplicate = User.objects.filter(username__iexact=username)
        if self.instance.pk:
            duplicate = duplicate.exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise forms.ValidationError(_('A user with that username already exists.'))
        return username

    def clean(self):
        cleaned_data = super().clean()
        if not self.can_reset_password:
            return cleaned_data

        password1 = cleaned_data.get('new_password1')
        password2 = cleaned_data.get('new_password2')
        if password1 or password2:
            if password1 != password2:
                self.add_error('new_password2', _('The two password fields did not match.'))
            else:
                try:
                    validate_password(password1, self.instance)
                except ValidationError as error:
                    self.add_error('new_password1', error)
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get('new_password1')
        if self.can_reset_password and password:
            user.set_password(password)
        if commit:
            user.save()
        return user
