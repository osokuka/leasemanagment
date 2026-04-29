"""KESCO integration views."""
import json
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.db.models import Count, Q

from .models import KescoCredential, Meter, MeterLedger


@login_required
def kesco_dashboard(request):
    """KESCO integration dashboard showing credentials and sync status."""
    credentials = KescoCredential.objects.all().order_by('username')

    # Aggregate stats — KESCO meters are identified by kesco_debitor_id, not serial_number
    total_meters = Meter.objects.count()
    kesco_meters = Meter.objects.filter(kesco_debitor_id__isnull=False).count()

    # Recent ledgers from KESCO sync — filter by meters that have KESCO data
    recent_syncs = MeterLedger.objects.filter(
        meter__kesco_debitor_id__isnull=False
    ).select_related('meter').order_by('-created_at')[:20]

    # Show latest ledger per KESCO meter for quick status
    kesco_meter_status = []
    if kesco_meters > 0:
        from django.db.models import Max
        latest_ledgers = MeterLedger.objects.filter(
            meter__kesco_debitor_id__isnull=False
        ).values('meter_id').annotate(
            latest=Max('created_at')
        ).order_by('-latest')[:10]

        for entry in latest_ledgers:
            ledger = MeterLedger.objects.filter(
                meter_id=entry['meter_id'],
                created_at=entry['latest']
            ).select_related('meter').first()
            if ledger:
                kesco_meter_status.append(ledger)

    context = {
        'credentials': credentials,
        'total_meters': total_meters,
        'kesco_meters': kesco_meters,
        'recent_syncs': recent_syncs,
        'kesco_meter_status': kesco_meter_status,
    }
    return render(request, 'locations/kesco/dashboard.html', context)


@login_required
def kesco_credential_list(request):
    """List all KESCO credentials."""
    credentials = KescoCredential.objects.all().order_by('username')
    context = {'credentials': credentials}
    return render(request, 'locations/kesco/credential_list.html', context)


@login_required
def kesco_credential_create(request):
    """Create a new KESCO credential."""
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        bearer_token = request.POST.get('bearer_token', '').strip()
        user_id = request.POST.get('user_id', '').strip() or None

        if not username:
            messages.error(request, _('Username is required.'))
            return redirect('locations:kesco_credential_create')

        # Check if already exists
        if KescoCredential.objects.filter(username=username).exists():
            messages.error(request, _('Credential for this username already exists.'))
            return redirect('locations:kesco_credential_list')

        now = timezone.now()
        credential = KescoCredential.objects.create(
            username=username,
            password=password,
            user_id=user_id,
            bearer_token=bearer_token or None,
            token_obtained_at=now if bearer_token else None,
            token_expires_at=(now + timedelta(seconds=604800)) if bearer_token else None,
            last_sync_status='Token provided manually' if bearer_token else 'Awaiting token',
        )
        if bearer_token:
            messages.success(request, _('Credential and token saved successfully.'))
        else:
            messages.success(request, _('Credential saved. Add token by editing.'))
        return redirect('locations:kesco_credential_list')

    return render(request, 'locations/kesco/credential_form.html')


@login_required
def kesco_credential_edit(request, uuid):
    """Edit a KESCO credential."""
    credential = get_object_or_404(KescoCredential, uuid=uuid)

    if request.method == 'POST':
        credential.username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        bearer_token = request.POST.get('bearer_token', '').strip()
        user_id = request.POST.get('user_id', '').strip() or None
        is_active = request.POST.get('is_active') == 'on'

        if password:
            credential.password = password
        if bearer_token:
            credential.bearer_token = bearer_token
            now = timezone.now()
            credential.token_obtained_at = now
            credential.token_expires_at = now + timedelta(seconds=604800)
            credential.last_sync_status = 'Token updated manually'
        credential.user_id = user_id
        credential.is_active = is_active
        credential.save()
        messages.success(request, _('Credential updated successfully.'))
        return redirect('locations:kesco_credential_list')

    context = {'credential': credential}
    return render(request, 'locations/kesco/credential_form.html', context)


@login_required
@require_POST
def kesco_credential_delete(request, uuid):
    """Delete a KESCO credential."""
    credential = get_object_or_404(KescoCredential, uuid=uuid)
    credential.delete()
    messages.success(request, _('Credential deleted.'))
    return redirect('locations:kesco_credential_list')


@login_required
def kesco_credential_login_page(request, uuid):
    """Show token status for a credential."""
    credential = get_object_or_404(KescoCredential, uuid=uuid)
    return render(request, 'locations/kesco/login_page.html', {
        'credential': credential,
    })


def kesco_api_capture_token(request):
    """API endpoint for KESCO capture container to send captured tokens."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    username = data.get('username', '').strip()
    token = data.get('token', '').strip()
    user_id = data.get('user_id', '').strip()

    if not username or not token:
        return JsonResponse({'error': 'username and token required'}, status=400)

    # Find or create credential
    credential, created = KescoCredential.objects.get_or_create(
        username=username,
        defaults={'password': ''},  # password set separately via UI
    )

    now = timezone.now()
    credential.bearer_token = token
    credential.user_id = user_id or credential.user_id
    credential.token_obtained_at = now
    credential.token_expires_at = now + timedelta(seconds=604800)  # 7 days
    credential.last_sync_status = 'Token captured via Selenium container'
    credential.save(update_fields=[
        'bearer_token', 'user_id', 'token_obtained_at',
        'token_expires_at', 'last_sync_status', 'updated_at'
    ])

    return JsonResponse({
        'message': f'Token saved for {username}',
        'expires_at': credential.token_expires_at.isoformat(),
    })


@login_required
@require_POST
def kesco_save_token(request, uuid):
    """Save bearer token captured from iframe after successful login."""
    credential = get_object_or_404(KescoCredential, uuid=uuid)
    
    data = json.loads(request.body)
    token = data.get('token')
    user_id = data.get('user_id')
    
    if not token:
        return JsonResponse({'error': 'Token is required'}, status=400)
    
    now = timezone.now()
    credential.bearer_token = token
    credential.user_id = user_id or credential.user_id
    credential.token_obtained_at = now
    credential.token_expires_at = now + timedelta(hours=24)
    credential.last_sync_status = 'Token captured via iframe'
    credential.save(update_fields=[
        'bearer_token', 'user_id', 'token_obtained_at',
        'token_expires_at', 'last_sync_status', 'updated_at'
    ])
    
    return JsonResponse({'status': 'ok', 'message': 'Token saved successfully'})


@login_required
@require_POST
def kesco_trigger_sync(request, uuid=None):
    """Manually trigger KESCO sync for a specific credential."""
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or \
              'application/json' in request.headers.get('Accept', '')

    results = _run_kesco_sync_logic(uuid)

    if is_ajax:
        if len(results) == 1:
            return JsonResponse(results[0])
        return JsonResponse({'results': results})

    for r in results:
        if r['status'] == 'error':
            messages.warning(request, f"{r['username']}: {r['message']}")
        else:
            messages.success(request, _('KESCO sync completed.'))
    return redirect('locations:kesco_dashboard')


@login_required
@require_POST
def kesco_trigger_sync_all(request):
    """Manually trigger KESCO sync for all credentials."""
    results = _run_kesco_sync_logic(uuid=None)
    for r in results:
        if r['status'] == 'error':
            messages.warning(request, f"{r['username']}: {r['message']}")
        else:
            messages.success(request, _('KESCO sync completed.'))
    return redirect('locations:kesco_dashboard')


def _run_kesco_sync_logic(uuid=None):
    """Run sync for given credential(s). Returns list of result dicts."""
    if uuid:
        credentials = KescoCredential.objects.filter(uuid=uuid)
    else:
        credentials = KescoCredential.objects.filter(is_active=True)

    if not credentials.exists():
        return [{'username': 'N/A', 'status': 'error', 'message': 'No active KESCO credentials found.'}]
    
    results = []
    for cred in credentials:
        try:
            # Check if token is valid, if not attempt login
            if not cred.is_token_valid:
                token, needs_captcha = cred.get_valid_token()
                if needs_captcha:
                    results.append({
                        'username': cred.username,
                        'status': 'error',
                        'message': 'Token expired. Please complete captcha login.'
                    })
                    continue
            
            # Import and run sync command directly
            from .management.commands.sync_kesco_meters import Command as SyncCommand
            
            cmd = SyncCommand()
            
            # Build options
            class Options:
                def __init__(self):
                    self.loop = False
                    self.once = True
                    self.user_ids = [cred.user_id] if cred.user_id else []
            
            # Run sync
            cmd.sync(Options())
            
            # Update last sync time
            cred.last_sync_at = timezone.now()
            cred.last_sync_status = 'Success'
            cred.save(update_fields=['last_sync_at', 'last_sync_status', 'updated_at'])
            
            results.append({
                'username': cred.username,
                'status': 'success',
                'message': 'Sync completed'
            })
            
        except Exception as e:
            cred.last_sync_at = timezone.now()
            cred.last_sync_status = str(e)[:50]
            cred.save(update_fields=['last_sync_at', 'last_sync_status', 'updated_at'])
            
            results.append({
                'username': cred.username,
                'status': 'error',
                'message': str(e)
            })

    return results
