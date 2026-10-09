"""
Maxsus admin panel view'lari.

Barcha sahifalar `@staff_required` bilan himoyalangan.
Murojaatlarni o'chirish uchun view ham, URL ham mavjud emas.
"""

from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Count, Min, Q
from django.db.models.deletion import ProtectedError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from shop.models import (
    Category,
    Furniture,
    FurnitureDetail,
    FurnitureImage,
    FurnitureMaterial,
    HeroSlide,
    Inquiry,
    Material,
    SiteSettings,
)
from shop.utils import format_price

from .decorators import staff_required
from .forms import (
    CategoryForm, FurnitureForm, HeroSlideForm, LoginForm, MaterialForm, SiteSettingsForm,
)

# Brute-force himoyasi sozlamalari
MAX_LOGIN_ATTEMPTS = 5
LOGIN_LOCKOUT_SECONDS = 600  # 10 daqiqa


# ---------------------------------------------------------------------------
# Autentifikatsiya
# ---------------------------------------------------------------------------


def panel_login(request):
    """Panelga kirish (faqat is_staff foydalanuvchilar)."""
    # Allaqachon kirgan bo'lsa
    if request.user.is_authenticated and request.user.is_staff:
        return redirect('panel:dashboard')

    if request.method == 'POST':
        form = LoginForm(request.POST)
        ip = _get_client_ip(request)
        lock_key = f'login_lock_{ip}'
        attempt_key = f'login_attempts_{ip}'

        if cache.get(lock_key):
            return render(request, 'panel/login.html', {
                'form': form,
                'login_error': "Juda ko'p urinish. 10 daqiqadan keyin qayta urinib ko'ring.",
            })

        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)

            # Faqat staff foydalanuvchilar kira oladi
            if user is not None and user.is_staff:
                login(request, user)
                cache.delete(attempt_key)
                # Xavfsiz redirect
                next_url = request.GET.get('next') or request.POST.get('next')
                if next_url and url_has_allowed_host_and_scheme(
                    next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
                ):
                    return redirect(next_url)
                return redirect('panel:dashboard')

            # Muvaffaqiyatsiz urinish
            attempts = cache.get(attempt_key, 0) + 1
            cache.set(attempt_key, attempts, LOGIN_LOCKOUT_SECONDS)
            if attempts >= MAX_LOGIN_ATTEMPTS:
                cache.set(lock_key, True, LOGIN_LOCKOUT_SECONDS)
                login_error = "Juda ko'p urinish. 10 daqiqadan keyin qayta urinib ko'ring."
            else:
                login_error = "Login yoki parol noto'g'ri."
        else:
            login_error = "Login yoki parol noto'g'ri."
    else:
        form = LoginForm()
        login_error = ''

    return render(request, 'panel/login.html', {'form': form, 'login_error': login_error})


@require_POST
def panel_logout(request):
    """Paneldan chiqish."""
    logout(request)
    return redirect('panel:login')


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


@staff_required
def dashboard(request):
    """Panel bosh sahifasi: statistika va oxirgi murojaatlar."""
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timezone.timedelta(days=7)

    stats = {
        'today_inquiries': Inquiry.objects.filter(created_at__gte=today_start).count(),
        'week_inquiries': Inquiry.objects.filter(created_at__gte=week_start).count(),
        'total_inquiries': Inquiry.objects.count(),
        'new_inquiries': Inquiry.objects.filter(status=Inquiry.STATUS_NEW).count(),
        'total_furniture': Furniture.objects.count(),
        'active_furniture': Furniture.objects.filter(is_active=True).count(),
        'total_categories': Category.objects.count(),
        'total_materials': Material.objects.count(),
    }

    recent_inquiries = Inquiry.objects.select_related('furniture')[:10]

    return render(request, 'panel/dashboard.html', {
        'stats': stats,
        'recent_inquiries': recent_inquiries,
    })


# ---------------------------------------------------------------------------
# Bosh sahifa bannerlari va kontenti
# ---------------------------------------------------------------------------


@staff_required
def hero_slide_list(request):
    slides = HeroSlide.objects.all()
    settings_obj = SiteSettings.objects.filter(pk=1).first() or SiteSettings(pk=1)
    if request.method == 'POST':
        settings_form = SiteSettingsForm(
            request.POST, request.FILES, instance=settings_obj, prefix='site',
        )
        if settings_form.is_valid():
            settings_form.save()
            messages.success(request, "Bosh sahifa sozlamalari saqlandi.")
            return redirect('panel:hero_slide_list')
        slide_form = HeroSlideForm()
        messages.error(request, "Sozlamalarni saqlashda xatolik. Maydonlarni tekshiring.")
    else:
        settings_form = SiteSettingsForm(instance=settings_obj, prefix='site')
        slide_form = HeroSlideForm()
    return render(request, 'panel/hero_slide_list.html', {
        'slides': slides,
        'settings_form': settings_form,
        'slide_form': slide_form,
    })


@staff_required
def hero_slide_form(request, pk=None):
    slide = get_object_or_404(HeroSlide, pk=pk) if pk else None
    if request.method == 'POST':
        form = HeroSlideForm(request.POST, request.FILES, instance=slide)
        if form.is_valid():
            try:
                with transaction.atomic():
                    item = form.save()
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                messages.success(request, "Banner saqlandi.")
                return redirect('panel:hero_slide_list')
    else:
        initial = None if slide else {
            'order': HeroSlide.objects.count(),
            'is_active': True,
        }
        form = HeroSlideForm(instance=slide, initial=initial)
    return render(request, 'panel/hero_slide_form.html', {
        'form': form, 'slide': slide,
    })


@staff_required
@require_POST
def hero_slide_toggle(request, pk):
    slide = get_object_or_404(HeroSlide, pk=pk)
    slide.is_active = not slide.is_active
    try:
        slide.save(update_fields=['is_active'])
    except ValidationError as exc:
        messages.error(request, ' '.join(exc.messages))
    else:
        messages.success(request, "Banner holati yangilandi.")
    return redirect('panel:hero_slide_list')


@staff_required
@require_POST
def hero_slide_move(request, pk, direction):
    slide = get_object_or_404(HeroSlide, pk=pk)
    if direction not in ('up', 'down'):
        return redirect('panel:hero_slide_list')
    items = list(HeroSlide.objects.order_by('order', 'pk'))
    index = next((i for i, item in enumerate(items) if item.pk == slide.pk), None)
    if index is not None:
        neighbor_index = index - 1 if direction == 'up' else index + 1
        if 0 <= neighbor_index < len(items):
            items[index], items[neighbor_index] = items[neighbor_index], items[index]
            with transaction.atomic():
                for order, item in enumerate(items):
                    if item.order != order:
                        item.order = order
                        item.save(update_fields=['order'])
    return redirect('panel:hero_slide_list')


@staff_required
@require_http_methods(['GET', 'POST'])
def hero_slide_delete(request, pk):
    slide = get_object_or_404(HeroSlide, pk=pk)
    if request.method == 'POST':
        slide.delete()
        messages.success(request, "Banner va uning rasmlari o'chirildi.")
        return redirect('panel:hero_slide_list')
    return render(request, 'panel/hero_slide_confirm_delete.html', {'slide': slide})


# ---------------------------------------------------------------------------
# Kategoriyalar
# ---------------------------------------------------------------------------


@staff_required
def category_list(request):
    """Kategoriyalar ro'yxati."""
    categories = Category.objects.annotate(furniture_count=Count('furniture_set'))
    return render(request, 'panel/category_list.html', {'categories': categories})


@staff_required
def category_form(request, pk=None):
    """Kategoriya qo'shish yoki tahrirlash."""
    category = get_object_or_404(Category, pk=pk) if pk else None

    if request.method == 'POST':
        form = CategoryForm(request.POST, request.FILES, instance=category)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                "Kategoriya muvaffaqiyatli saqlandi." if not pk else "Kategoriya yangilandi.",
            )
            return redirect('panel:category_list')
        messages.error(request, "Iltimos, xatolarni tuzating.")
    else:
        form = CategoryForm(instance=category)

    return render(request, 'panel/category_form.html', {'form': form, 'category': category})


@staff_required
@require_POST
def category_delete(request, pk):
    """Kategoriyani o'chirish (ishlatilayotgan bo'lsa ogohlantirish)."""
    category = get_object_or_404(Category, pk=pk)
    count = category.furniture_set.count()
    if count:
        messages.error(
            request,
            f"«{category.name}» kategoriyasini o'chirib bo'lmaydi — unga {count} ta mebel bog'langan.",
        )
    else:
        # Rasm faylini o'chirish
        if category.image:
            category.image.delete(save=False)
        category.delete()
        messages.success(request, "Kategoriya o'chirildi.")
    return redirect('panel:category_list')


# ---------------------------------------------------------------------------
# Materiallar
# ---------------------------------------------------------------------------


@staff_required
def material_list(request):
    """Materiallar ro'yxati."""
    materials = Material.objects.annotate(usage_count=Count('furniture_materials'))
    return render(request, 'panel/material_list.html', {'materials': materials})


@staff_required
def material_form(request, pk=None):
    """Material qo'shish yoki tahrirlash."""
    material = get_object_or_404(Material, pk=pk) if pk else None

    if request.method == 'POST':
        form = MaterialForm(request.POST, instance=material)
        if form.is_valid():
            form.save()
            messages.success(request, "Material saqlandi.")
            return redirect('panel:material_list')
        messages.error(request, "Iltimos, xatolarni tuzating.")
    else:
        form = MaterialForm(instance=material)

    return render(request, 'panel/material_form.html', {'form': form, 'material': material})


@staff_required
@require_POST
def material_delete(request, pk):
    """Materialni o'chirish (ishlatilayotgan bo'lsa ogohlantirish)."""
    material = get_object_or_404(Material, pk=pk)
    count = material.furniture_materials.count()
    if count:
        messages.error(
            request,
            f"«{material.name}» materialini o'chirib bo'lmaydi — u {count} ta mebelda ishlatilgan.",
        )
    else:
        material.delete()
        messages.success(request, "Material o'chirildi.")
    return redirect('panel:material_list')


# ---------------------------------------------------------------------------
# Mebellar
# ---------------------------------------------------------------------------


@staff_required
def furniture_list(request):
    """Mebellar ro'yxati (qidiruv va filtr bilan)."""
    qs = (
        Furniture.objects.select_related('category')
        .annotate(min_price=Min('furniture_materials__price'), image_count=Count('images'))
        .order_by('-created_at', 'pk')
    )

    query = request.GET.get('q', '').strip()
    if query:
        qs = qs.filter(Q(name__icontains=query) | Q(description__icontains=query))

    category_id = request.GET.get('category')
    if category_id:
        qs = qs.filter(category_id=category_id)

    status = request.GET.get('status')
    if status == 'active':
        qs = qs.filter(is_active=True)
    elif status == 'inactive':
        qs = qs.filter(is_active=False)

    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    query_params = request.GET.copy()
    query_params.pop('page', None)

    return render(request, 'panel/furniture_list.html', {
        'page_obj': page_obj,
        'categories': Category.objects.all(),
        'query': query,
        'selected_category': category_id,
        'status': status,
        'query_string': query_params.urlencode(),
    })


@staff_required
def furniture_form(request, pk=None):
    """
    Mebel qo'shish yoki tahrirlash.

    Hammasi bitta sahifada: asosiy ma'lumot, materiallar (narx bilan),
    rasmlar va qo'shimcha detallar. Saqlash tranzaksiya ichida bajariladi.
    """
    furniture = get_object_or_404(Furniture, pk=pk) if pk else None

    if request.method == 'POST':
        form = FurnitureForm(request.POST, instance=furniture)
        errors = []

        # --- Dinamik qatorlarni serverdan o'qish ---
        material_ids = request.POST.getlist('material_id')
        material_prices = request.POST.getlist('material_price')
        detail_names = request.POST.getlist('detail_name')
        detail_prices = request.POST.getlist('detail_price')
        image_orders = request.POST.getlist('image_order')  # mavjud rasmlar tartibi
        main_image = request.POST.get('main_image')          # asosiy rasm belgisi
        delete_images = request.POST.getlist('delete_image')  # o'chiriladigan rasmlar
        new_images = request.FILES.getlist('new_images')      # yangi yuklangan rasmlar

        # --- Materiallarni tekshirish ---
        parsed_materials = []
        seen_materials = set()
        for i, mid in enumerate(material_ids):
            if not mid:
                continue
            if not mid.isdigit():
                errors.append(f"{i + 1}-material ro'yxatdan to'g'ri tanlanmagan.")
                continue
            price = material_prices[i] if i < len(material_prices) else ''
            try:
                parsed_price = Decimal(price)
                if not parsed_price.is_finite() or parsed_price < 0:
                    raise InvalidOperation
            except (InvalidOperation, TypeError, ValueError):
                errors.append(f"{i + 1}-material uchun narx noto'g'ri kiritilgan.")
                continue
            material_pk = int(mid)
            if material_pk in seen_materials:
                errors.append("Bitta materialni ikki marta qo'shib bo'lmaydi.")
                continue
            seen_materials.add(material_pk)
            if not Material.objects.filter(pk=material_pk).exists():
                errors.append(f"{i + 1}-material ro'yxatdan topilmadi.")
                continue
            if parsed_price.as_tuple().exponent < -2 or parsed_price.adjusted() > 9:
                errors.append(f"{i + 1}-material narxi 2 kasr xonasi va 10 ta butun raqamdan oshmasin.")
                continue
            parsed_materials.append((material_pk, parsed_price))

        if not parsed_materials:
            errors.append("Kamida bitta material va uning narxi kiritilishi kerak.")

        # --- Detallarni tekshirish ---
        parsed_details = []
        for i, name in enumerate(detail_names):
            name = name.strip()
            if not name:
                continue
            price = detail_prices[i] if i < len(detail_prices) else ''
            try:
                parsed_price = Decimal(price)
                if not parsed_price.is_finite() or parsed_price < 0:
                    raise InvalidOperation
            except (InvalidOperation, TypeError, ValueError):
                errors.append(f"«{name}» detali uchun narx noto'g'ri kiritilgan.")
                continue
            if len(name) > 200:
                errors.append("Detal nomi 200 belgidan oshmasligi kerak.")
                continue
            if parsed_price.as_tuple().exponent < -2 or parsed_price.adjusted() > 9:
                errors.append(f"«{name}» detal narxi 2 kasr xonasi va 10 ta butun raqamdan oshmasin.")
                continue
            parsed_details.append((name, parsed_price))

        # --- Rasmlarni tekshirish ---
        from shop.models import validate_uploaded_image
        from django.core.exceptions import ValidationError
        for img in new_images:
            try:
                validate_uploaded_image(img)
            except ValidationError as e:
                errors.append(f"«{img.name}»: {e.messages[0]}")

        if form.is_valid() and not errors:
            try:
                with transaction.atomic():
                    obj = form.save()

                    # Materiallarni yangilash (narx bilan)
                    obj.furniture_materials.all().delete()
                    FurnitureMaterial.objects.bulk_create([
                        FurnitureMaterial(furniture=obj, material_id=mid, price=price)
                        for mid, price in parsed_materials
                    ])

                    # Detallarni yangilash
                    obj.details.all().delete()
                    FurnitureDetail.objects.bulk_create([
                        FurnitureDetail(furniture=obj, name=name, price=price, order=i)
                        for i, (name, price) in enumerate(parsed_details)
                    ])

                    # Mavjud rasmlarni o'chirish
                    for img_id in delete_images:
                        if img_id.isdigit():
                            image = FurnitureImage.objects.filter(
                                furniture=obj, pk=int(img_id)
                            ).first()
                            if image:
                                image.delete()

                    # Mavjud rasmlarning tartibini va asosiy belgisini yangilash
                    for position, img_id in enumerate(image_orders):
                        if not img_id.isdigit():
                            continue
                        img = FurnitureImage.objects.filter(furniture=obj, pk=int(img_id)).first()
                        if img:
                            img.order = position
                            img.is_main = (str(img.pk) == main_image)
                            img.save(update_fields=['order', 'is_main'])

                    # Yangi rasmlarni qo'shish
                    has_main = obj.images.filter(is_main=True).exists()
                    start_order = obj.images.count()
                    for idx, img in enumerate(new_images):
                        FurnitureImage.objects.create(
                            furniture=obj,
                            image=img,
                            order=start_order + idx,
                            is_main=(
                                main_image == f'new-{idx}'
                                or (not has_main and idx == 0)
                            ),
                        )
                        has_main = has_main or main_image == f'new-{idx}' or idx == 0

                messages.success(
                    request,
                    "Mebel muvaffaqiyatli saqlandi." if not pk else "Mebel yangilandi.",
                )
                return redirect('panel:furniture_list')
            except (ValueError, ValidationError, IntegrityError) as e:
                errors.append(f"Saqlashda xatolik: {e}")
        else:
            if not form.is_valid():
                errors.append("Asosiy maydonlarda xatolik bor.")

        for err in errors:
            messages.error(request, err)
    else:
        form = FurnitureForm(instance=furniture)

    # Mavjud ma'lumotlarni shablonga tayyorlash
    materials_list = Material.objects.order_by('name')
    existing_materials = []
    if furniture:
        existing_materials = list(
            furniture.furniture_materials.select_related('material').order_by('price')
        )
    existing_details = list(furniture.details.order_by('order')) if furniture else []
    existing_images = list(
        furniture.images.order_by('-is_main', 'order') if furniture else []
    )

    return render(request, 'panel/furniture_form.html', {
        'form': form,
        'furniture': furniture,
        'materials_list': materials_list,
        'existing_materials': existing_materials,
        'existing_details': existing_details,
        'existing_images': existing_images,
    })


@staff_required
@require_POST
def furniture_delete(request, pk):
    """Mebelni o'chirish (rasm fayllari ham o'chiriladi)."""
    furniture = get_object_or_404(Furniture, pk=pk)
    name = furniture.name
    images = list(furniture.images.all())
    with transaction.atomic():
        try:
            furniture.delete()
        except ProtectedError:
            messages.error(
                request,
                f"«{name}» mebelini o'chirib bo'lmaydi — unga murojaatlar bog'langan. "
                "Murojaatlar tarixini saqlash uchun mebelni nofaol qiling.",
            )
            return redirect('panel:furniture_list')

    for image in images:
        for field in (image.image, image.medium, image.thumbnail):
            if field and field.name and field.storage.exists(field.name):
                field.storage.delete(field.name)
    messages.success(request, f"«{name}» mebeli o'chirildi.")
    return redirect('panel:furniture_list')


@staff_required
@require_POST
def furniture_toggle_active(request, pk):
    """Mebelni faol/nofaol qilish."""
    furniture = get_object_or_404(Furniture, pk=pk)
    furniture.is_active = not furniture.is_active
    furniture.save(update_fields=['is_active', 'updated_at'])
    status = "faollashtirildi" if furniture.is_active else "nofaol qilindi"
    messages.success(request, f"«{furniture.name}» {status}.")
    return redirect(request.META.get('HTTP_REFERER', '/panel/mebellar/'))


@staff_required
@require_POST
def furniture_image_delete(request, pk):
    """Bitta rasmni o'chirish (AJAX)."""
    image = get_object_or_404(FurnitureImage, pk=pk, furniture_id=request.POST.get('furniture_id'))
    was_main = image.is_main
    furniture = image.furniture
    image.delete()

    # Agar asosiy rasm o'chirilgan bo'lsa, birinchisini asosiy qilamiz
    if was_main:
        first = furniture.images.first()
        if first:
            first.is_main = True
            first.save(update_fields=['is_main'])

    return JsonResponse({'ok': True})


# ---------------------------------------------------------------------------
# Buyurtmalar (murojaatlar)
# ---------------------------------------------------------------------------


@staff_required
def inquiry_list(request):
    """Buyurtmalar ro'yxati. O'chirish tugmasi yo'q."""
    qs = Inquiry.objects.select_related('furniture')

    # Qidiruv (telefon bo'yicha)
    query = request.GET.get('q', '').strip()
    if query:
        qs = qs.filter(Q(phone__icontains=query) | Q(customer_name__icontains=query))

    # Filtr (status)
    status = request.GET.get('status')
    if status in dict(Inquiry.STATUS_CHOICES):
        qs = qs.filter(status=status)

    # Filtr (sana)
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)

    qs.filter(is_seen=False).update(is_seen=True)

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    query_params = request.GET.copy()
    query_params.pop('page', None)

    return render(request, 'panel/inquiry_list.html', {
        'page_obj': page_obj,
        'query': query,
        'status': status,
        'date_from': date_from or '',
        'date_to': date_to or '',
        'status_choices': Inquiry.STATUS_CHOICES,
        'query_string': query_params.urlencode(),
    })


@staff_required
def inquiry_detail(request, pk):
    """Bitta buyurtma tafsiloti. Bosilganda ko'rilgan deb belgilanadi."""
    inquiry = get_object_or_404(Inquiry.objects.select_related('furniture'), pk=pk)
    inquiry.mark_as_seen()
    return render(request, 'panel/inquiry_detail.html', {
        'inquiry': inquiry,
        'status_choices': Inquiry.STATUS_CHOICES,
    })


@staff_required
@require_POST
def inquiry_update_status(request, pk):
    """Buyurtma statusini o'zgartirish (yagona ruxsat etilgan amal)."""
    inquiry = get_object_or_404(Inquiry, pk=pk)
    new_status = request.POST.get('status')
    if new_status in dict(Inquiry.STATUS_CHOICES):
        inquiry.status = new_status
        inquiry.save(update_fields=['status', 'updated_at'])
        messages.success(request, "Holat yangilandi.")
    else:
        messages.error(request, "Noto'g'ri holat.")
    return redirect('panel:inquiry_list')


# ---------------------------------------------------------------------------
# AJAX yordamchi endpoint'lar (formadan chiqmasdan qo'shish)
# ---------------------------------------------------------------------------


@staff_required
@require_POST
def api_add_category(request):
    """Formadan chiqmasdan yangi kategoriya qo'shish (AJAX)."""
    name = request.POST.get('name', '').strip()
    if not name:
        return JsonResponse({'ok': False, 'error': "Kategoriya nomini kiriting."}, status=400)
    if len(name) > 100:
        return JsonResponse({'ok': False, 'error': "Kategoriya nomi 100 belgidan oshmasligi kerak."}, status=400)
    if Category.objects.filter(name__iexact=name).exists():
        return JsonResponse({'ok': False, 'error': "Bu nomdagi kategoriya allaqachon mavjud."}, status=400)
    category = Category.objects.create(name=name)
    return JsonResponse({'ok': True, 'id': category.pk, 'name': category.name})


@staff_required
@require_POST
def api_add_material(request):
    """Formadan chiqmasdan yangi material qo'shish (AJAX)."""
    name = request.POST.get('name', '').strip()
    if not name:
        return JsonResponse({'ok': False, 'error': "Material nomini kiriting."}, status=400)
    if len(name) > 100:
        return JsonResponse({'ok': False, 'error': "Material nomi 100 belgidan oshmasligi kerak."}, status=400)
    if Material.objects.filter(name__iexact=name).exists():
        return JsonResponse({'ok': False, 'error': "Bu nomdagi material allaqachon mavjud."}, status=400)
    material = Material.objects.create(name=name)
    return JsonResponse({'ok': True, 'id': material.pk, 'name': material.name})


@staff_required
@require_GET
def api_notifications(request):
    """
    Bildirishnoma polling endpoint'i.

    Panel har 10 soniyada shu manzilga so'rov yuboradi va yangi
    (ko'rilmagan) murojaatlar haqida ma'lumot oladi.
    """
    unseen = Inquiry.objects.filter(is_seen=False).order_by('-created_at')
    count = unseen.count()

    # Oxirgi 5 ta ko'rilmagan murojaat haqida qisqa ma'lumot
    last_id = request.GET.get('last_id')
    new_items = [{
        'id': i.pk,
        'phone': i.phone,
        'furniture': i.furniture_name,
        'total': format_price(i.total_price),
    } for i in unseen[:5]]

    # Mijoz brauzerida ovozli signal uchun: yangi element bormi?
    has_new = bool(last_id and new_items and str(new_items[0]['id']) != str(last_id))

    return JsonResponse({
        'ok': True,
        'count': count,
        'items': new_items,
        'has_new': has_new,
        'latest_id': new_items[0]['id'] if new_items else None,
    })


def _get_client_ip(request):
    """Proxy sarlavhasiga ko'r-ko'rona ishonmasdan, so'rov IP manzilini oladi."""
    return request.META.get('REMOTE_ADDR', '0.0.0.0')
