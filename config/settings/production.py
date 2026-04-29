"""
Production settings.
"""
from .base import *  # noqa

DEBUG = False

# ── Reverse proxy (Nginx Proxy Manager) ──
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# ── Security headers ──
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'SAMEORIGIN'

# ── Allowed hosts ──
# Inherited from base.py (loaded from DJANGO_ALLOWED_HOSTS env var).
# Append any additional hosts from a production-specific env var.
_extra_hosts = os.environ.get('DJANGO_EXTRA_ALLOWED_HOSTS', '').strip()
if _extra_hosts:
    ALLOWED_HOSTS += [h.strip() for h in _extra_hosts.split(',') if h.strip()]
