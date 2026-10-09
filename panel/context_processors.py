from shop.models import Inquiry


def panel_notifications(request):
    """Panel navigatsiyasi uchun ko'rilmagan murojaatlar soni."""
    if not request.user.is_authenticated or not request.user.is_staff:
        return {'panel_unseen_count': 0, 'panel_latest_inquiry_id': ''}

    unseen = Inquiry.objects.filter(is_seen=False)
    return {
        'panel_unseen_count': unseen.count(),
        'panel_latest_inquiry_id': unseen.order_by('-created_at').values_list('pk', flat=True).first() or '',
    }
