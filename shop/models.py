"""
Shop modellari.

Bu modul mebel do'konining barcha ma'lumot modelini o'z ichiga oladi:
kategoriyalar, materiallar, mebellar, rasmlar, detallar va mijoz murojaatlari.
"""

import os
import uuid
from io import BytesIO

from PIL import Image, ImageOps
from core.services.images import process_image_variants

# HEIC (iPhone rasmlari) qo'llab-quvvatlash — kutubxona mavjud bo'lsa yoqiladi.
try:
    import pillow_heif

    pillow_heif.register_heif_opener()
    HEIF_SUPPORTED = True
except ImportError:  # pragma: no cover
    HEIF_SUPPORTED = False

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.validators import FileExtensionValidator, MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.utils.text import slugify


# ---------------------------------------------------------------------------
# Rasm qayta ishlash yordamchisi
# ---------------------------------------------------------------------------

ALLOWED_IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'webp', 'heic', 'heif']
ALLOWED_IMAGE_FORMATS = {
    'jpg': {'JPEG'},
    'jpeg': {'JPEG'},
    'png': {'PNG'},
    'webp': {'WEBP'},
    'heic': {'HEIF', 'HEIC'},
    'heif': {'HEIF', 'HEIC'},
}
MAX_IMAGE_PIXELS = 80_000_000

# Yuklanadigan rasmning maksimal hajmi (baytda). settings dan olib olinadi.
MAX_IMAGE_SIZE = getattr(settings, 'MAX_IMAGE_SIZE', 10 * 1024 * 1024)

# Saqlanadigan o'lchamlar
FULL_MAX_SIZE = 2000   # asosiy (katta) rasmning maksimal tomoni
MEDIUM_MAX_SIZE = 900  # galereya/miniatyura uchun
THUMB_MAX_SIZE = 400   # karta uchun kichik rasm


def validate_uploaded_image(image):
    """
    Yuklangan rasmni tekshiradi: hajmi va fayl turi.

    Xato bo'lsa ValidationError ko'taradi (foydalanuvchiga o'zbekcha xabar).
    """
    if image is None:
        return

    size = getattr(image, 'size', 0)
    if size and size > MAX_IMAGE_SIZE:
        limit_mb = MAX_IMAGE_SIZE // (1024 * 1024)
        raise ValidationError(
            f"Rasm hajmi juda katta (max {limit_mb} MB). "
            f"Iltimos, kichikroq rasm yuklang."
        )

    name = getattr(image, 'name', '') or ''
    ext = name.rsplit('.', 1)[-1].lower() if '.' in name else ''
    if ext and ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError(
            "Faqat JPG, PNG, WEBP yoki HEIC formatdagi rasmlar qabul qilinadi."
        )

    # Fayl haqiqatan ham rasm ekanini Pillow orqali tekshiramiz.
    pos = image.tell() if hasattr(image, 'tell') else None
    try:
        with Image.open(image) as opened:
            if opened.width * opened.height > MAX_IMAGE_PIXELS:
                raise ValidationError(
                    "Rasm o'lchami juda katta. Iltimos, 80 megapikseldan kichikroq rasm tanlang."
                )
            if opened.format not in ALLOWED_IMAGE_FORMATS.get(ext, set()):
                raise ValidationError(
                    "Fayl kengaytmasi va haqiqiy rasm formati mos kelmaydi."
                )
            opened.verify()
    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError(
            "Fayl buzuq yoki rasm formati noto'g'ri. Iltimos, boshqa rasm yuklang."
        ) from exc
    finally:
        if pos is not None:
            image.seek(pos)


def _load_rgb_image(file_obj):
    """
    Faylni ochib, EXIF orientatsiyasini to'g'rilaydi va RGB rejimga o'tkazadi.
    """
    img = Image.open(file_obj)
    # Telefonda olingan rasmning burilishini (EXIF) to'g'rilash
    img = ImageOps.exif_transpose(img)

    if img.mode == 'P':
        img = img.convert('RGBA')

    if img.mode in ('RGBA', 'LA'):
        # Shaffof fonni oq rangga almashtiramiz (JPEG/WEBP uchun)
        background = Image.new('RGB', img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[-1])
        img = background
    elif img.mode != 'RGB':
        img = img.convert('RGB')

    return img


def _save_webp(img, quality=85):
    """Rasmni WEBP formatiga siqib, BytesIO qaytaradi."""
    output = BytesIO()
    img.save(output, format='WEBP', quality=quality, method=6)
    output.seek(0)
    return output


def optimized_image_fields(upload, base_name):
    """
    Yuklangan rasmni optimallaydi va turli o'lchamlarini tayyorlaydi.

    Qaytaradi (full, medium, thumb) — har biri InMemoryUploadedFile yoki None.
    Uchta o'lcham bitta manba rasmdan yasaladi, shuning uchun bir marta
    o'qiladi va serverda ko'p joy egallamaydi.
    """
    img = _load_rgb_image(upload)

    def _variant(size, suffix, quality=85):
        copy = img.copy()
        if copy.width > size or copy.height > size:
            copy.thumbnail((size, size), Image.Resampling.LANCZOS)
        buf = _save_webp(copy, quality=quality)
        filename = f"{base_name}{suffix}.webp"
        return InMemoryUploadedFile(
            buf, 'ImageField', filename, 'image/webp', buf.getbuffer().nbytes, None
        )

    full = _variant(FULL_MAX_SIZE, '', quality=92)
    medium = _variant(MEDIUM_MAX_SIZE, '_medium', quality=88)
    thumb = _variant(THUMB_MAX_SIZE, '_thumb', quality=85)
    return full, medium, thumb


# ---------------------------------------------------------------------------
# Modellar
# ---------------------------------------------------------------------------


class Category(models.Model):
    """Mebel kategoriyasi (masalan: Oshxona, Yotoqxona)."""

    name = models.CharField(max_length=100, unique=True, verbose_name="Nomi")
    slug = models.SlugField(max_length=100, unique=True, blank=True, verbose_name="URL slug")
    image = models.ImageField(
        upload_to='categories/',
        blank=True,
        null=True,
        validators=[FileExtensionValidator(ALLOWED_IMAGE_EXTENSIONS)],
        verbose_name="Rasm",
    )
    order = models.IntegerField(default=0, verbose_name="Tartib")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan")

    class Meta:
        verbose_name = "Kategoriya"
        verbose_name_plural = "Kategoriyalar"
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name) or 'kategoriya'
            slug = base_slug
            counter = 1
            while Category.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_furniture_count(self):
        """Bu kategoriyadagi faol mebellar soni."""
        return self.furniture_set.filter(is_active=True).count()


class Material(models.Model):
    """Mebel materiali (masalan: Taxta, MDF, Akril)."""

    name = models.CharField(max_length=100, unique=True, verbose_name="Nomi")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan")

    class Meta:
        verbose_name = "Material"
        verbose_name_plural = "Materiallar"
        ordering = ['name']

    def __str__(self):
        return self.name


class SiteSettings(models.Model):
    """Editable homepage content and branding; a single row with primary key 1."""

    hero_title = models.CharField(
        max_length=180, default='Uyingizga mos mebel', verbose_name="Hero sarlavhasi",
    )
    hero_subtitle = models.CharField(
        max_length=300,
        default="O'lcham, material va ko'rinishni tanlang — qolganini birga kelishamiz.",
        verbose_name="Hero izohi",
    )
    logo = models.ImageField(
        upload_to='site/branding/', blank=True, null=True,
        validators=[FileExtensionValidator(ALLOWED_IMAGE_EXTENSIONS)],
        verbose_name="Logotip rasmi",
    )
    logo_medium = models.ImageField(
        upload_to='site/branding/medium/', blank=True, null=True, editable=False,
    )
    hero_image = models.ImageField(
        upload_to='site/hero/', blank=True, null=True,
        validators=[FileExtensionValidator(ALLOWED_IMAGE_EXTENSIONS)],
        verbose_name="Yakuniy aloqa bloki rasmi",
    )
    hero_image_medium = models.ImageField(
        upload_to='site/hero/medium/', blank=True, null=True, editable=False,
    )
    usp_1_title = models.CharField(max_length=100, blank=True, verbose_name="Ishonch 1 sarlavhasi")
    usp_1_text = models.CharField(max_length=180, blank=True, verbose_name="Ishonch 1 izohi")
    usp_2_title = models.CharField(max_length=100, blank=True, verbose_name="Ishonch 2 sarlavhasi")
    usp_2_text = models.CharField(max_length=180, blank=True, verbose_name="Ishonch 2 izohi")
    usp_3_title = models.CharField(max_length=100, blank=True, verbose_name="Ishonch 3 sarlavhasi")
    usp_3_text = models.CharField(max_length=180, blank=True, verbose_name="Ishonch 3 izohi")
    usp_4_title = models.CharField(max_length=100, blank=True, verbose_name="Ishonch 4 sarlavhasi")
    usp_4_text = models.CharField(max_length=180, blank=True, verbose_name="Ishonch 4 izohi")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Yangilangan")

    class Meta:
        verbose_name = "Sayt sozlamasi"
        verbose_name_plural = "Sayt sozlamalari"

    @classmethod
    def load(cls):
        return cls.objects.filter(pk=1).first() or cls(pk=1)

    def save(self, *args, **kwargs):
        existing = type(self).objects.filter(pk=1).first()
        self.pk = 1
        replacements = []
        for source_name, medium_name in (
            ('logo', 'logo_medium'),
            ('hero_image', 'hero_image_medium'),
        ):
            source = getattr(self, source_name)
            if source and not getattr(source, '_committed', True):
                old_source = getattr(existing, source_name, None)
                old_medium = getattr(existing, medium_name, None)
                full, medium = process_image_variants(
                    source, f'{uuid.uuid4().hex}-{source.name}',
                    max_size=2400, medium_size=1280,
                )
                setattr(self, source_name, full)
                setattr(self, medium_name, medium)
                replacements.extend((old_source, old_medium))
            elif not source and existing and getattr(existing, source_name):
                replacements.extend((getattr(existing, source_name), getattr(existing, medium_name)))
                setattr(self, medium_name, None)
        super().save(*args, **kwargs)
        if replacements:
            transaction.on_commit(lambda: _delete_replaced_files(replacements))

    def delete(self, *args, **kwargs):
        files = [self.logo, self.logo_medium, self.hero_image, self.hero_image_medium]
        result = super().delete(*args, **kwargs)
        transaction.on_commit(lambda: _delete_replaced_files(files))
        return result

    def __str__(self):
        return "Sayt sozlamalari"


class HeroSlide(models.Model):
    """Homepage carousel banner."""

    image = models.ImageField(
        upload_to='hero-slides/', validators=[FileExtensionValidator(ALLOWED_IMAGE_EXTENSIONS)],
        verbose_name="Asosiy rasm",
    )
    image_medium = models.ImageField(
        upload_to='hero-slides/medium/', blank=True, null=True, editable=False,
    )
    image_mobile = models.ImageField(
        upload_to='hero-slides/mobile/', blank=True, null=True,
        validators=[FileExtensionValidator(ALLOWED_IMAGE_EXTENSIONS)],
        verbose_name="Mobil rasm",
    )
    image_mobile_medium = models.ImageField(
        upload_to='hero-slides/mobile/medium/', blank=True, null=True, editable=False,
    )
    focus_x = models.PositiveSmallIntegerField(
        default=50, validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Fokus X (%)",
    )
    focus_y = models.PositiveSmallIntegerField(
        default=50, validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Fokus Y (%)",
    )
    title = models.CharField(max_length=180, verbose_name="Sarlavha")
    subtitle = models.CharField(max_length=300, verbose_name="Izoh")
    button_text = models.CharField(max_length=80, default="Katalogni ko'rish", verbose_name="Tugma matni")
    button_url = models.CharField(max_length=500, default='/katalog/', verbose_name="Tugma havolasi")
    badge_text = models.CharField(max_length=100, blank=True, verbose_name="Yorliq")
    order = models.PositiveSmallIntegerField(default=0, verbose_name="Tartib")
    is_active = models.BooleanField(default=True, verbose_name="Faol")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan")

    class Meta:
        verbose_name = "Bosh sahifa banneri"
        verbose_name_plural = "Bosh sahifa bannerlari"
        ordering = ['order', 'pk']

    def clean(self):
        super().clean()
        url = (self.button_url or '').strip()
        if url.startswith('/') and not url.startswith('//'):
            pass
        else:
            from urllib.parse import urlparse

            parsed = urlparse(url)
            if parsed.scheme not in ('http', 'https') or not parsed.netloc:
                raise ValidationError({
                    'button_url': "Havola ichki yo'l (/katalog/) yoki http(s) manzil bo'lishi kerak."
                })
        if self.is_active and type(self).objects.filter(is_active=True).exclude(pk=self.pk).count() >= 6:
            raise ValidationError("Bir vaqtda ko'pi bilan 6 ta faol banner bo'lishi mumkin.")

    def save(self, *args, **kwargs):
        existing = type(self).objects.filter(pk=self.pk).first() if self.pk else None
        replacements = []
        for source_name, medium_name in (
            ('image', 'image_medium'),
            ('image_mobile', 'image_mobile_medium'),
        ):
            source = getattr(self, source_name)
            if source and not getattr(source, '_committed', True):
                if existing:
                    replacements.extend((getattr(existing, source_name), getattr(existing, medium_name)))
                full, medium = process_image_variants(
                    source, f'{uuid.uuid4().hex}-{source.name}',
                    max_size=2400, medium_size=1280,
                )
                setattr(self, source_name, full)
                setattr(self, medium_name, medium)
            elif not source and existing and getattr(existing, source_name):
                replacements.extend((getattr(existing, source_name), getattr(existing, medium_name)))
                setattr(self, medium_name, None)
        self.full_clean()
        super().save(*args, **kwargs)
        if replacements:
            transaction.on_commit(lambda: _delete_replaced_files(replacements))

    def delete(self, *args, **kwargs):
        files = [self.image, self.image_medium, self.image_mobile, self.image_mobile_medium]
        result = super().delete(*args, **kwargs)
        transaction.on_commit(lambda: _delete_replaced_files(files))
        return result

    def __str__(self):
        return self.title


def _delete_replaced_files(fields):
    for field in fields:
        if field and field.name and field.storage.exists(field.name):
            field.storage.delete(field.name)


class Furniture(models.Model):
    """Mebel mahsuloti."""

    name = models.CharField(max_length=200, verbose_name="Nomi")
    slug = models.SlugField(max_length=200, unique=True, blank=True, verbose_name="URL slug")
    description = models.TextField(verbose_name="Tavsif")
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='furniture_set',
        verbose_name="Kategoriya",
    )

    # O'lchamlar (metrda)
    length = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=[MinValueValidator(0.01)],
        verbose_name="Uzunlik (m)", help_text="Metrda (masalan: 3 yoki 2.5)",
    )
    width = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=[MinValueValidator(0.01)],
        verbose_name="Kenglik (m)", help_text="Metrda (masalan: 2 yoki 1.8)",
    )
    height = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=[MinValueValidator(0.01)],
        verbose_name="Balandlik (m)", help_text="Metrda (masalan: 2.5 yoki 3)",
    )

    materials = models.ManyToManyField(
        Material,
        through='FurnitureMaterial',
        related_name='furnitures',
        verbose_name="Materiallar",
    )

    is_active = models.BooleanField(default=True, verbose_name="Faol")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="O'zgartirilgan")

    class Meta:
        verbose_name = "Mebel"
        verbose_name_plural = "Mebellar"
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name) or 'mebel'
            slug = base_slug
            counter = 1
            while Furniture.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_main_image(self):
        """Asosiy rasmni qaytaradi (bo'lmasa — birinchi rasm)."""
        images = list(self.images.all())
        return next((image for image in images if image.is_main), images[0] if images else None)

    def get_min_price(self):
        """Eng arzon material narxi."""
        result = self.furniture_materials.aggregate(min_p=models.Min('price'))
        return result['min_p'] or 0

    def get_dimensions_display(self):
        """O'lchamlarni chiroyli ko'rinishda qaytaradi."""
        return f"{self.length:g} m × {self.width:g} m × {self.height:g} m"


class FurnitureMaterial(models.Model):
    """Mebel va material orasidagi bog'lanish (har bir material uchun alohida narx)."""

    furniture = models.ForeignKey(
        Furniture, on_delete=models.CASCADE,
        related_name='furniture_materials', verbose_name="Mebel",
    )
    material = models.ForeignKey(
        Material, on_delete=models.PROTECT,
        related_name='furniture_materials', verbose_name="Material",
    )
    price = models.DecimalField(
        max_digits=12, decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name="Narx (so'm)",
    )

    class Meta:
        verbose_name = "Mebel materiali"
        verbose_name_plural = "Mebel materiallari"
        unique_together = [['furniture', 'material']]
        ordering = ['price']

    def __str__(self):
        return f"{self.furniture.name} — {self.material.name}: {self.price:,.0f} so'm"


class FurnitureImage(models.Model):
    """Mebelga tegishli rasm. Har bir mebelga cheksiz rasm yuklash mumkin."""

    furniture = models.ForeignKey(
        Furniture, on_delete=models.CASCADE,
        related_name='images', verbose_name="Mebel",
    )
    image = models.ImageField(
        upload_to='furniture/',
        validators=[FileExtensionValidator(ALLOWED_IMAGE_EXTENSIONS)],
        verbose_name="Rasm",
    )
    # Optimallashdan keyin yaratiladigan qo'shimcha o'lchamlar
    medium = models.ImageField(upload_to='furniture/medium/', blank=True, null=True, editable=False)
    thumbnail = models.ImageField(upload_to='furniture/thumbs/', blank=True, null=True, editable=False)

    order = models.IntegerField(default=0, verbose_name="Tartib")
    is_main = models.BooleanField(default=False, verbose_name="Asosiy rasm")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yuklangan")

    class Meta:
        verbose_name = "Mebel rasmi"
        verbose_name_plural = "Mebel rasmlari"
        ordering = ['-is_main', 'order', 'created_at']

    def __str__(self):
        return f"{self.furniture.name} — rasm #{self.pk}"

    def save(self, *args, **kwargs):
        # Bitta mebelda faqat bitta asosiy rasm bo'ladi
        if self.is_main and self.furniture_id:
            FurnitureImage.objects.filter(
                furniture_id=self.furniture_id, is_main=True
            ).exclude(pk=self.pk).update(is_main=False)

        # Yangi rasm yuklangan bo'lsa — optimallash va versiyalar yaratish
        if self.image and hasattr(self.image, 'file') and _is_new_upload(self.image):
            self._process_upload()

        super().save(*args, **kwargs)

    def _process_upload(self):
        """Asosiy rasmni siqadi va medium/thumb versiyalarini yaratadi."""
        base_name = os.path.splitext(os.path.basename(self.image.name))[0] or 'rasm'
        full, medium, thumb = optimized_image_fields(self.image, base_name)
        self.image = full
        self.medium = medium
        self.thumbnail = thumb

    def delete(self, *args, **kwargs):
        """Model o'chirilganda diskdagi barcha rasm fayllarini ham o'chiradi."""
        for field in (self.image, self.medium, self.thumbnail):
            _delete_file(field)
        super().delete(*args, **kwargs)

    @property
    def display_url(self):
        """Katta ko'rinish uchun rasm (galereya)."""
        return (self.image or self.medium).url if (self.image or self.medium) else ''

    @property
    def medium_url(self):
        """O'rta o'lcham (galereya/thumblar)."""
        return (self.medium or self.image).url if (self.medium or self.image) else ''

    @property
    def thumb_url(self):
        """Kichik o'lcham (kartalar)."""
        return (self.thumbnail or self.medium or self.image).url if (
            self.thumbnail or self.medium or self.image
        ) else ''


def _is_new_upload(image_field):
    """Fayl yangi yuklanganmi yoki allaqachon saqlanganmi aniqlaydi."""
    return not getattr(image_field, '_committed', True)


def _delete_file(field):
    """ImageField faylini diskdan o'chiradi; xatolar chaqiruvchiga uzatiladi."""
    if field and field.name and field.storage.exists(field.name):
        field.storage.delete(field.name)


class FurnitureDetail(models.Model):
    """
    Mebelga qo'shiladigan qo'shimcha detal (masalan: oyna, tortma).

    Detallar umumiy emas — har bir mebelga alohida kiritiladi.
    """

    furniture = models.ForeignKey(
        Furniture, on_delete=models.CASCADE,
        related_name='details', verbose_name="Mebel",
    )
    name = models.CharField(max_length=200, verbose_name="Detal nomi")
    price = models.DecimalField(
        max_digits=12, decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name="Narx (so'm)",
    )
    order = models.IntegerField(default=0, verbose_name="Tartib")

    class Meta:
        verbose_name = "Mebel detali"
        verbose_name_plural = "Mebel detallari"
        ordering = ['order', 'name']

    def __str__(self):
        return f"{self.furniture.name} — {self.name}: {self.price:,.0f} so'm"


# ---------------------------------------------------------------------------
# Buyurtma / murojaat
# ---------------------------------------------------------------------------


class InquiryQuerySet(models.QuerySet):
    """Murojaatlarni o'chirishni butunlay bloklaydi."""

    def delete(self):
        raise PermissionDenied("Buyurtmalarni o'chirish taqiqlangan!")


class InquiryManager(models.Manager):
    """Inquiry uchun maxsus manager."""

    def get_queryset(self):
        return InquiryQuerySet(self.model, using=self._db)


class Inquiry(models.Model):
    """
    Mijoz murojaati (buyurtma).

    Narxlar snapshot sifatida saqlanadi — keyin mebel narxi o'zgarsa ham
    eski murojaat buzilmaydi. Murojaatni o'chirish mumkin emas.
    """

    STATUS_NEW = 'new'
    STATUS_CONTACTED = 'contacted'
    STATUS_COMPLETED = 'completed'
    STATUS_CHOICES = [
        (STATUS_NEW, 'Yangi'),
        (STATUS_CONTACTED, "Bog'lanildi"),
        (STATUS_COMPLETED, 'Yakunlandi'),
    ]

    furniture = models.ForeignKey(
        Furniture, on_delete=models.PROTECT,
        related_name='inquiries', verbose_name="Mebel",
    )

    # Snapshot ma'lumotlar
    furniture_name = models.CharField(max_length=200, verbose_name="Mebel nomi (snapshot)")
    material_name = models.CharField(max_length=100, verbose_name="Material nomi (snapshot)")
    material_price = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name="Material narxi (snapshot)",
    )
    selected_details = models.JSONField(
        default=list, blank=True, verbose_name="Tanlangan detallar",
        help_text="[{'name': 'Detal nomi', 'price': 100000}, ...]",
    )
    total_price = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name="Jami narx (snapshot)",
    )

    # Mijoz ma'lumotlari
    customer_name = models.CharField(max_length=100, blank=True, verbose_name="Mijoz ismi")
    phone = models.CharField(max_length=20, verbose_name="Telefon raqami")

    # Holat
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_NEW, verbose_name="Holat",
    )
    is_seen = models.BooleanField(default=False, verbose_name="Ko'rilgan")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="O'zgartirilgan")

    objects = InquiryManager()

    class Meta:
        verbose_name = "Buyurtma"
        verbose_name_plural = "Buyurtmalar"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.phone} — {self.furniture_name} ({self.get_status_display()})"

    def delete(self, *args, **kwargs):
        raise PermissionDenied("Buyurtmani o'chirish mumkin emas!")

    def get_details_total(self):
        """Tanlangan detallarning umumiy narxi."""
        from decimal import Decimal, InvalidOperation

        total = Decimal('0')
        for detail in self.selected_details or []:
            try:
                total += Decimal(str(detail.get('price', 0)))
            except (InvalidOperation, TypeError, ValueError):
                continue
        return total

    def mark_as_seen(self):
        """Murojaatni ko'rilgan deb belgilaydi."""
        if not self.is_seen:
            self.is_seen = True
            self.save(update_fields=['is_seen', 'updated_at'])
