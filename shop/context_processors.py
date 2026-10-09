"""Barcha sahifalarga umumiy kontekst uzatuvchi processor'lar."""

from django.conf import settings

from .models import SiteSettings

def site_settings(request):
    """
    Sayt sozlamalarini (sayt nomi, telefon, ijtimoiy tarmoqlar)
    barcha shablonlarga uzatadi.
    """
    return {
        'SITE_NAME': getattr(settings, 'SITE_NAME', "Mebel Do'koni"),
        'SELLER_PHONE': getattr(settings, 'SELLER_PHONE', ''),
        'TELEGRAM_URL': getattr(settings, 'TELEGRAM_URL', ''),
        'INSTAGRAM_URL': getattr(settings, 'INSTAGRAM_URL', ''),
        'SITE_SETTINGS': SiteSettings.load(),
    }
