"""Yordamchi funksiyalar."""


def format_price(value):
    """
    Narxni "1 250 000 so'm" ko'rinishida formatlaydi.
    """
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        return "0 so'm"
    # Mingliklarni bo'shliq bilan ajratamiz
    return f"{number:,}".replace(',', ' ') + " so'm"
