"""Language middleware: one default language for every visitor.

Without a language cookie Django's LocaleMiddleware falls back to the
browser's Accept-Language header — so a German browser would get German even
though the conference is international. This subclass skips the header: only
the cookie set explicitly through the in-app language switcher counts,
otherwise LANGUAGE_CODE from the settings.
"""

from django.conf import settings
from django.middleware.locale import LocaleMiddleware
from django.utils import translation


class DefaultLanguageMiddleware(LocaleMiddleware):
    def process_request(self, request):
        lang = request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME)
        if lang not in dict(settings.LANGUAGES):
            lang = settings.LANGUAGE_CODE
        translation.activate(lang)
        request.LANGUAGE_CODE = translation.get_language()
