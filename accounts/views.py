from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST
from django.conf import settings
from .models import User, Role
from .forms import UserCreationFormCustom, UserChangeFormCustom


# --- Decorators ---
def super_user_required(view_func):
    return user_passes_test(lambda u: u.is_super_user)(view_func)


def admin_required(view_func):
    return user_passes_test(lambda u: u.is_admin)(view_func)


def can_edit_user_profile(actor, target):
    if actor.is_super_user:
        return True
    if actor.role == Role.ADMIN:
        return target.role == Role.DATA_ENTRY_CLERK and not target.is_superuser
    return False


def can_reset_user_password(actor, target):
    if actor.is_super_user:
        return True
    if actor.role == Role.ADMIN:
        return target.role == Role.DATA_ENTRY_CLERK and not target.is_superuser
    return actor.role == Role.DATA_ENTRY_CLERK and actor.pk == target.pk


def allowed_role_choices_for(actor):
    if actor.is_super_user:
        return Role.choices
    if actor.role == Role.ADMIN:
        return [(Role.DATA_ENTRY_CLERK, _('Data Entry Clerk'))]
    return []


# --- Auth Views ---
def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        username = request.POST['username'].strip()
        password = request.POST['password']
        matched_user = User.objects.filter(username__iexact=username).first()
        if matched_user:
            username = matched_user.username
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('dashboard')
        messages.error(request, _('Invalid username or password.'))

    return render(request, 'accounts/login.html')


@login_required
def logout_view(request):
    logout(request)
    return redirect('/login/')


# --- User CRUD ---
@login_required
def user_list(request):
    users = User.objects.all().order_by('username')
    return render(request, 'accounts/user_list.html', {'users': users})


@admin_required
def user_create(request):
    form_kwargs = {
        'allowed_role_choices': allowed_role_choices_for(request.user),
    }
    if request.method == 'POST':
        form = UserCreationFormCustom(request.POST, **form_kwargs)
        if form.is_valid():
            user = form.save()
            messages.success(request, _('User "{user}" created successfully.').format(user=user.username))
            return redirect('accounts:user_list')
    else:
        form = UserCreationFormCustom(**form_kwargs)

    return render(request, 'accounts/user_form.html', {'form': form, 'title': _('Create User')})


@login_required
def user_update(request, pk):
    editing_user = get_object_or_404(User, pk=pk)
    can_edit_profile = can_edit_user_profile(request.user, editing_user)
    can_reset_password = can_reset_user_password(request.user, editing_user)

    if not can_edit_profile and not can_reset_password:
        raise PermissionDenied

    can_change_role = can_edit_profile and request.user.pk != editing_user.pk
    can_change_active = can_edit_profile and request.user.pk != editing_user.pk
    form_kwargs = {
        'instance': editing_user,
        'can_edit_profile': can_edit_profile,
        'can_reset_password': can_reset_password,
        'allowed_role_choices': allowed_role_choices_for(request.user),
        'can_change_role': can_change_role,
        'can_change_active': can_change_active,
    }

    if request.method == 'POST':
        form = UserChangeFormCustom(request.POST, **form_kwargs)
        if form.is_valid():
            form.save()
            messages.success(request, _('User "{user}" updated successfully.').format(user=editing_user.username))
            return redirect('accounts:user_list')
    else:
        form = UserChangeFormCustom(**form_kwargs)

    return render(request, 'accounts/user_form.html', {
        'form': form,
        'title': _('Edit User'),
        'editing_user': editing_user,
        'can_edit_profile': can_edit_profile,
        'can_reset_password': can_reset_password,
    })


@super_user_required
@require_POST
def user_delete(request, pk):
    user = get_object_or_404(User, pk=pk)
    if user == request.user:
        messages.error(request, _('You cannot delete yourself.'))
        return redirect('accounts:user_list')
    username = user.username
    user.delete()
    messages.success(request, _('User "{user}" deleted successfully.').format(user=username))
    return redirect('accounts:user_list')


@login_required
@require_POST
def set_language_view(request):
    """Save user's language preference to database."""
    lang = request.POST.get('language', 'en')
    valid_langs = [code for code, _ in settings.LANGUAGES]
    if lang in valid_langs:
        request.user.preferred_language = lang
        request.user.save(update_fields=['preferred_language'])
    return redirect(request.POST.get('next', '/dashboard/'))
