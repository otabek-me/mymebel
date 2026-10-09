"""Panel uchun maxsus decorator'lar."""

from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied


def staff_required(view_func):
    """
    Faqat `is_staff=True` foydalanuvchilarga ruxsat beradi.

    Anonim foydalanuvchi login sahifasiga yo'naltiriladi,
    staff bo'lmagan foydalanuvchiga esa 403 qaytariladi.
    """
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not user.is_staff:
            raise PermissionDenied("Bu sahifa faqat xodimlar uchun.")
        return view_func(request, *args, **kwargs)

    return _wrapped
