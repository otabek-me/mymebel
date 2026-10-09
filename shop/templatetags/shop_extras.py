"""Shablonlar uchun qo'shimcha filter va teglar."""

from django import template

register = template.Library()


@register.filter
def som(value):
    """
    Narxni "1 250 000 so'm" ko'rinishida formatlaydi.

    Ishlatilishi: {{ price|som }}
    """
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        return "0 so'm"
    return f"{number:,}".replace(',', ' ') + " so'm"


@register.filter
def som_plain(value):
    """Faqat raqamni bo'shliq bilan ajratib qaytaradi: 1 250 000"""
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        return "0"
    return f"{number:,}".replace(',', ' ')


@register.filter
def meter(value):
    """O'lchamni chiroyli ko'rinishda: 3 m yoki 2.5 m"""
    try:
        num = float(value)
    except (TypeError, ValueError):
        return value
    # Butun son bo'lsa kasrsiz ko'rsatamiz
    if num == int(num):
        return f"{int(num)}"
    return f"{num:g}"
