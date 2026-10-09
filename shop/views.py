"""
Mijoz qismi view'lari.

Bosh sahifa, katalog, mebel sahifasi va murojaat (buyurtma) yaratish.
Narx har doim serverda qayta hisoblanadi — brauzerdagi qiymatga ishonilmaydi.
"""

import json
import re
from decimal import Decimal, InvalidOperation

from django.core.cache import cache
from django.core.paginator import Paginator
from django.db import DatabaseError
from django.db.models import Count, Min, Prefetch, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from .models import (
    Category, Furniture, FurnitureDetail, FurnitureImage, FurnitureMaterial,
    HeroSlide, Inquiry, SiteSettings,
)
from .utils import format_price

# Telefon raqami formati: +998 XX XXX XX XX (ixtiyoriy +, bo'shliqlar)
PHONE_RE = re.compile(r'^998\d{9}$')

# Bir IP dan murojaat yuborish orasidagi minimal vaqt (soniya)
INQUIRY_RATE_LIMIT_SECONDS = 20


def _base_furniture_queryset():
    """
    Katalog va bosh sahifa uchun optimallashtirilgan queryset.

    N+1 so'rovlarning oldini olish uchun select_related/prefetch_related
    ishlatiladi.
    """
    return (
        Furniture.objects.filter(is_active=True)
        .select_related('category')
        .prefetch_related(
            Prefetch('images', queryset=FurnitureImage.objects.order_by('-is_main', 'order')),
            'furniture_materials',
        )
    )


def home(request):
    """Bosh sahifa: hero, kategoriyalar, ommabop mebellar, 'nega biz'."""
    categories = Category.objects.annotate(
        active_furniture_count=Count(
            'furniture_set',
            filter=Q(furniture_set__is_active=True),
        )
    )

    # Yangi mebellar (birinchi 8 ta)
    new_furniture = _base_furniture_queryset().annotate(
        min_price=Min('furniture_materials__price')
    )[:8]

    # Ommabop mebellar — material narxi eng past bo'lganlar (arzon narxdan)
    popular_furniture = (
        _base_furniture_queryset()
        .annotate(min_price=Min('furniture_materials__price'))
        .order_by('min_price')[:8]
    )

    return render(request, 'shop/home.html', {
        'categories': categories,
        'new_furniture': new_furniture,
        'popular_furniture': popular_furniture,
        'hero_slides': HeroSlide.objects.filter(is_active=True).order_by('order', 'pk')[:6],
        'homepage_settings': SiteSettings.load(),
    })


def catalog(request, category_slug=None):
    """
    Katalog sahifasi: kategoriya filtri, qidiruv, narx bo'yicha saralash,
    sahifalash (pagination).
    """
    qs = _base_furniture_queryset().annotate(min_price=Min('furniture_materials__price'))

    current_category = None
    if category_slug:
        current_category = get_object_or_404(Category, slug=category_slug)
        qs = qs.filter(category=current_category)

    # Qidiruv
    query = request.GET.get('q', '').strip()
    if query:
        qs = qs.filter(Q(name__icontains=query) | Q(description__icontains=query))

    # Saralash
    sort = request.GET.get('sort', 'new')
    sort_map = {
        'new': '-created_at',
        'price_asc': 'min_price',
        'price_desc': '-min_price',
        'name': 'name',
    }
    qs = qs.order_by(sort_map.get(sort, '-created_at'))

    # Sahifalash
    paginator = Paginator(qs, 12)
    page_obj = paginator.get_page(request.GET.get('page'))

    # Sahifalashda GET parametrlarini saqlash uchun
    query_params = request.GET.copy()
    query_params.pop('page', None)

    return render(request, 'shop/catalog.html', {
        'page_obj': page_obj,
        'categories': Category.objects.all(),
        'current_category': current_category,
        'query': query,
        'sort': sort,
        'query_string': query_params.urlencode(),
    })


def furniture_detail(request, slug):
    """Mebel sahifasi: galereya, material va detal tanlash, jonli narx."""
    furniture = get_object_or_404(
        Furniture.objects.filter(is_active=True)
        .select_related('category')
        .prefetch_related(
            Prefetch('images', queryset=FurnitureImage.objects.order_by('-is_main', 'order')),
            Prefetch('details', queryset=FurnitureDetail.objects.order_by('order', 'name')),
            Prefetch(
                'furniture_materials',
                queryset=FurnitureMaterial.objects.select_related('material').order_by('price'),
            ),
        ),
        slug=slug,
    )

    materials = furniture.furniture_materials.all()
    details = furniture.details.all()

    # Narx hisoblash uchun JS'ga uzatiladigan ma'lumot
    pricing_data = {
        'materials': {str(fm.id): str(fm.price) for fm in materials},
        'details': {str(d.id): str(d.price) for d in details},
    }

    return render(request, 'shop/furniture_detail.html', {
        'furniture': furniture,
        'materials': materials,
        'details': details,
        'pricing_data': json.dumps(pricing_data),
    })


@require_POST
def create_inquiry(request):
    """
    Murojaat (buyurtma) yaratish — AJAX orqali.

    Xavfsizlik:
      * CSRF himoyasi (Django)
      * honeypot maydon (botlar to'ldiradi)
      * bir IP dan tez-tez yuborishni cheklash
      * narx serverda qayta hisoblanadi (brauzerga ishonilmaydi)
    """
    # --- Honeypot: botlar bu maydonni to'ldiradi ---
    if request.POST.get('website', '').strip():
        # Botga xuddi muvaffaqiyatli javob qaytaramiz
        return JsonResponse({'ok': True, 'message': 'Rahmat! Sotuvchi tez orada siz bilan bog\'lanadi.'})

    # --- Rate limit (IP bo'yicha) ---
    ip = _get_client_ip(request)
    cache_key = f'inquiry_rl_{ip}'
    # --- Telefon raqamini tekshirish ---
    raw_phone = request.POST.get('phone', '').strip()
    phone_digits = re.sub(r'\D', '', raw_phone)
    if not PHONE_RE.fullmatch(phone_digits):
        return JsonResponse(
            {'ok': False, 'error': "Telefon raqami noto'g'ri. Format: +998 XX XXX XX XX"},
            status=400,
        )

    # --- Mebel va materialni olish ---
    furniture_id = request.POST.get('furniture_id', '')
    material_id = request.POST.get('material_id', '')
    if not furniture_id.isdigit() or not material_id.isdigit():
        return JsonResponse(
            {'ok': False, 'error': "Mebel yoki material tanlovi noto'g'ri."},
            status=400,
        )
    furniture = Furniture.objects.filter(pk=int(furniture_id), is_active=True).first()
    if furniture is None:
        return JsonResponse(
            {'ok': False, 'error': "Tanlangan mebel mavjud emas yoki faol emas."},
            status=404,
        )

    # Material shu mebelga tegishli ekanini tekshiramiz
    furniture_material = (
        FurnitureMaterial.objects.select_related('material')
        .filter(pk=int(material_id), furniture=furniture)
        .first()
    )
    if furniture_material is None:
        return JsonResponse(
            {'ok': False, 'error': "Tanlangan material bu mebelga tegishli emas."},
            status=400,
        )

    # --- Tanlangan detallarni serverda qayta hisoblash ---
    selected_detail_ids = request.POST.getlist('details')
    if len(selected_detail_ids) > 100 or any(not item.isdigit() for item in selected_detail_ids):
        return JsonResponse(
            {'ok': False, 'error': "Qo'shimcha detallar tanlovi noto'g'ri."},
            status=400,
        )
    valid_details = FurnitureDetail.objects.filter(
        furniture=furniture, pk__in=[int(item) for item in selected_detail_ids]
    )
    details_snapshot = [{'name': d.name, 'price': str(d.price)} for d in valid_details]
    details_total = sum((Decimal(d['price']) for d in details_snapshot), Decimal('0'))

    # --- Jami narxni serverda hisoblash ---
    total_price = furniture_material.price + details_total

    # --- Murojaatni yaratish ---
    customer_name = request.POST.get('customer_name', '').strip()[:100]
    if not cache.add(cache_key, True, INQUIRY_RATE_LIMIT_SECONDS):
        return JsonResponse(
            {'ok': False, 'error': "Iltimos, biroz kutib, qaytadan urinib ko'ring."},
            status=429,
        )

    try:
        inquiry = Inquiry.objects.create(
            furniture=furniture,
            furniture_name=furniture.name,
            material_name=furniture_material.material.name,
            material_price=furniture_material.price,
            selected_details=details_snapshot,
            total_price=total_price,
            customer_name=customer_name,
            phone=f"+{phone_digits[:3]} {phone_digits[3:5]} {phone_digits[5:8]} {phone_digits[8:10]} {phone_digits[10:]}",
        )
    except DatabaseError:
        cache.delete(cache_key)
        raise

    return JsonResponse({
        'ok': True,
        'message': "Rahmat! Sotuvchi tez orada siz bilan bog'lanadi.",
        'inquiry_id': inquiry.pk,
    })


def _get_client_ip(request):
    """Mijoz IP manzilini aniqlaydi (proxy ortida ham ishlaydi)."""
    return request.META.get('REMOTE_ADDR', '0.0.0.0')


def custom_404(request, exception):
    """404 xato sahifasi."""
    return render(request, '404.html', status=404)


def custom_500(request):
    """500 xato sahifasi."""
    return render(request, '500.html', status=500)


def robots_txt(request):
    """robots.txt fayli."""
    lines = [
        "User-agent: *",
        "Disallow: /panel/",
        "",
        f"Sitemap: {request.build_absolute_uri('/sitemap.xml')}",
    ]
    return render(request, 'shop/robots.txt', {'lines': lines}, content_type='text/plain')
