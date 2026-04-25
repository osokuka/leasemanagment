from django.utils import translation


class UserLanguageMiddleware:
    """
    Middleware that sets the user's preferred language for each request.
    For authenticated users, reads `preferred_language` from the database.
    Falls back to Django's default LANGUAGE_CODE for anonymous users.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and hasattr(request.user, 'preferred_language'):
            lang = request.user.preferred_language
            if lang:
                translation.activate(lang)
                request.LANGUAGE_CODE = lang
        return self.get_response(request)
