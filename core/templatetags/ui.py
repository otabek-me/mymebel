"""Umumiy UI shablon filtrlari."""

import re

from django import template

register = template.Library()


def _phone_digits(value):
    return re.sub(r"\D", "", str(value or ""))


@register.filter
def phone_pretty(value):
    """O'zbekiston raqamlarini o'qilishi oson guruhlarga ajratadi."""
    digits = _phone_digits(value)
    if digits.startswith("00"):
        digits = digits[2:]
    if not digits.startswith("998"):
        return str(value or "").strip()

    subscriber = digits[3:]
    if len(subscriber) == 9:
        groups = (subscriber[:2], subscriber[2:5], subscriber[5:7], subscriber[7:])
    elif len(subscriber) == 10:
        groups = (subscriber[:2], subscriber[2:5], subscriber[5:7], subscriber[7:])
    else:
        return f"+{digits}"
    return "+998 " + " ".join(group for group in groups if group)


@register.filter
def phone_tel(value):
    """tel: havolasi uchun telefonni raqamlardan iborat E.164 ko'rinishiga keltiradi."""
    text = str(value or "").strip()
    digits = _phone_digits(text)
    if digits.startswith("00"):
        digits = digits[2:]
    if not digits:
        return ""
    return f"+{digits}"
