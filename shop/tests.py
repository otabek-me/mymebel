from decimal import Decimal
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.cache import cache
from django.db.models.deletion import ProtectedError
from django.test import Client, TestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.urls import reverse
from PIL import Image

from core.templatetags.ui import phone_pretty, phone_tel

from .models import (
    Category,
    Furniture,
    FurnitureDetail,
    FurnitureImage,
    FurnitureMaterial,
    HeroSlide,
    Inquiry,
    Material,
    SiteSettings,
    validate_uploaded_image,
)


@override_settings(STORAGES={
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class StorefrontTests(TestCase):
    def setUp(self):
        cache.clear()
        self.category = Category.objects.create(name='Oshxona')
        self.material = Material.objects.create(name='MDF')
        self.other_material = Material.objects.create(name='Akril')
        self.furniture = Furniture.objects.create(
            name='Zamonaviy oshxona',
            description='Sifatli oshxona mebeli',
            category=self.category,
            length=Decimal('3.00'),
            width=Decimal('2.50'),
            height=Decimal('2.40'),
        )
        self.option = FurnitureMaterial.objects.create(
            furniture=self.furniture,
            material=self.material,
            price=Decimal('1000000.50'),
        )
        self.addon = FurnitureDetail.objects.create(
            furniture=self.furniture,
            name='Yumshoq yopiluvchi tortma',
            price=Decimal('125000.25'),
        )
        self.other_furniture = Furniture.objects.create(
            name='Yotoqxona shkafi',
            description='Shkaf',
            category=self.category,
            length=Decimal('2.00'),
            width=Decimal('0.60'),
            height=Decimal('2.20'),
        )
        self.other_addon = FurnitureDetail.objects.create(
            furniture=self.other_furniture,
            name='Begona detal',
            price=Decimal('900000.00'),
        )

    def test_phone_filters_format_display_and_tel_values(self):
        phone = '+998 (99) 557-14-205'
        self.assertEqual(phone_pretty(phone), '+998 99 557 14 205')
        self.assertEqual(phone_tel(phone), '+9989955714205')
        self.assertEqual(phone_pretty('+998 90 123 45 67'), '+998 90 123 45 67')

    def test_storefront_pages_render(self):
        for path in (
            reverse('shop:home'),
            reverse('shop:catalog'),
            reverse('shop:catalog_category', args=[self.category.slug]),
            reverse('shop:furniture_detail', args=[self.furniture.slug]),
            reverse('sitemap'),
            reverse('robots_txt'),
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_homepage_fallback_and_site_content_render_without_banners(self):
        SiteSettings.objects.create(
            hero_title='O‘lchamga mos yechim',
            hero_subtitle='Foydalanuvchi kiritgan izoh.',
            usp_1_title='O‘lchamga mos',
        )
        response = self.client.get(reverse('shop:home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'O‘lchamga mos yechim')
        self.assertContains(response, 'Foydalanuvchi kiritgan izoh.')
        self.assertContains(response, 'O‘lchamga mos</h2>')
        self.assertContains(response, 'hero-fallback')
        self.assertNotContains(response, 'hero-controls')

    def test_homepage_hero_uses_webp_preload_and_one_slide_hides_controls(self):
        image_bytes = BytesIO()
        Image.new('RGB', (1920, 1000), '#8a7258').save(image_bytes, format='PNG')
        slide = HeroSlide.objects.create(
            image=SimpleUploadedFile('hero.png', image_bytes.getvalue(), content_type='image/png'),
            title='Tabiiy ranglar',
            subtitle='O‘zingizga mos mebel tanlang.',
            button_text="Katalogni ko'rish",
            button_url='/katalog/',
        )
        response = self.client.get(reverse('shop:home'))
        self.assertContains(response, 'aria-roledescription="carousel"')
        self.assertContains(response, 'fetchpriority="high"')
        self.assertContains(response, slide.image_medium.url)
        self.assertContains(response, 'media="(max-width: 768px)"')
        self.assertNotContains(response, 'hero-controls')
        self.assertEqual(slide.image.name.rsplit('.', 1)[-1], 'webp')

    def test_inquiry_uses_server_prices_and_product_scoped_details(self):
        response = self.client.post(reverse('shop:create_inquiry'), {
            'furniture_id': self.furniture.pk,
            'material_id': self.option.pk,
            'details': [self.addon.pk, self.other_addon.pk],
            'phone': '+998 90 123 45 67',
            'customer_name': 'Ali',
            'total_price': '1',
        })

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['ok'])
        inquiry = Inquiry.objects.get()
        self.assertEqual(inquiry.total_price, Decimal('1125000.75'))
        self.assertEqual(inquiry.material_price, Decimal('1000000.50'))
        self.assertEqual(inquiry.phone, '+998 90 123 45 67')
        self.assertEqual(
            inquiry.selected_details,
            [{'name': self.addon.name, 'price': '125000.25'}],
        )
        self.assertFalse(inquiry.is_seen)

        self.option.price = Decimal('2000000')
        self.option.save()
        self.addon.price = Decimal('500000')
        self.addon.save()
        inquiry.refresh_from_db()
        self.assertEqual(inquiry.total_price, Decimal('1125000.75'))
        self.assertEqual(inquiry.material_price, Decimal('1000000.50'))
        self.assertEqual(inquiry.selected_details[0]['price'], '125000.25')

    def test_invalid_phone_is_rejected_and_honeypot_does_not_create_inquiry(self):
        payload = {
            'furniture_id': self.furniture.pk,
            'material_id': self.option.pk,
            'phone': '901234567',
        }
        response = self.client.post(reverse('shop:create_inquiry'), payload)
        self.assertEqual(response.status_code, 400)

        payload.update(phone='+998 90 123 45 67', website='https://spam.example')
        response = self.client.post(reverse('shop:create_inquiry'), payload)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['ok'])
        self.assertFalse(Inquiry.objects.exists())

    def test_inquiry_rate_limit_blocks_rapid_repeat(self):
        payload = {
            'furniture_id': self.furniture.pk,
            'material_id': self.option.pk,
            'phone': '+998 90 123 45 67',
        }
        url = reverse('shop:create_inquiry')
        self.assertEqual(self.client.post(url, payload).status_code, 200)
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 429)
        self.assertEqual(Inquiry.objects.count(), 1)

    def test_inquiry_cannot_be_deleted_directly_or_by_queryset(self):
        inquiry = Inquiry.objects.create(
            furniture=self.furniture,
            furniture_name=self.furniture.name,
            material_name=self.material.name,
            material_price=Decimal('1'),
            total_price=Decimal('1'),
            phone='+998 90 123 45 67',
        )
        with self.assertRaises(PermissionDenied):
            inquiry.delete()
        with self.assertRaises(PermissionDenied):
            Inquiry.objects.filter(pk=inquiry.pk).delete()
        with self.assertRaises(ProtectedError):
            self.furniture.delete()
        self.assertTrue(Inquiry.objects.filter(pk=inquiry.pk).exists())

    def test_csrf_is_required_for_ajax_inquiry(self):
        client = Client(enforce_csrf_checks=True)
        client.get(reverse('shop:furniture_detail', args=[self.furniture.slug]))
        response = client.post(reverse('shop:create_inquiry'), {
            'furniture_id': self.furniture.pk,
            'material_id': self.option.pk,
            'phone': '+998 90 123 45 67',
        })
        self.assertEqual(response.status_code, 403)

    def test_image_variants_are_converted_and_bounded(self):
        with TemporaryDirectory() as media_dir:
            image_bytes = BytesIO()
            Image.new('RGBA', (2400, 1200), (120, 80, 40, 128)).save(image_bytes, format='PNG')
            upload = SimpleUploadedFile('cabinet.png', image_bytes.getvalue(), content_type='image/png')
            with override_settings(MEDIA_ROOT=media_dir):
                picture = FurnitureImage.objects.create(
                    furniture=self.furniture,
                    image=upload,
                    is_main=True,
                )
                picture.refresh_from_db()
                self.assertTrue(picture.image.name.endswith('.webp'))
                self.assertTrue(picture.medium.name.endswith('.webp'))
                self.assertTrue(picture.thumbnail.name.endswith('.webp'))
                for field, maximum in (
                    (picture.image, 2000),
                    (picture.medium, 900),
                    (picture.thumbnail, 400),
                ):
                    with Image.open(field.path) as processed:
                        self.assertLessEqual(max(processed.size), maximum)
                        self.assertEqual(processed.mode, 'RGB')
                stored_paths = [field.path for field in (picture.image, picture.medium, picture.thumbnail)]
                picture.delete()
                self.assertTrue(all(not Path(path).exists() for path in stored_paths))

    def test_invalid_image_extension_is_rejected(self):
        upload = SimpleUploadedFile('not-image.txt', b'plain text', content_type='text/plain')
        with self.assertRaises(ValidationError):
            validate_uploaded_image(upload)

    def test_mismatched_image_extension_and_content_are_rejected(self):
        image_bytes = BytesIO()
        Image.new('RGB', (20, 10), 'red').save(image_bytes, format='PNG')
        upload = SimpleUploadedFile(
            'renamed.jpg',
            image_bytes.getvalue(),
            content_type='image/jpeg',
        )
        with self.assertRaisesMessage(ValidationError, 'kengaytmasi'):
            validate_uploaded_image(upload)

    def test_exif_rotation_is_applied_before_saving(self):
        with TemporaryDirectory() as media_dir:
            image_bytes = BytesIO()
            image = Image.new('RGB', (120, 60), 'blue')
            exif = Image.Exif()
            exif[274] = 6
            image.save(image_bytes, format='JPEG', exif=exif)
            upload = SimpleUploadedFile('rotated.jpg', image_bytes.getvalue(), content_type='image/jpeg')

            with override_settings(MEDIA_ROOT=media_dir):
                picture = FurnitureImage.objects.create(furniture=self.furniture, image=upload)
                picture.refresh_from_db()
                with Image.open(picture.image.path) as processed:
                    self.assertEqual(processed.size, (60, 120))

class SeedShopCommandTests(TestCase):
    def test_seed_command_is_idempotent_and_adds_expected_catalog(self):
        call_command('seed_shop', verbosity=0)
        call_command('seed_shop', verbosity=0)

        self.assertEqual(Category.objects.count(), 3)
        self.assertEqual(Material.objects.count(), 4)
        self.assertEqual(Furniture.objects.count(), 6)
        self.assertEqual(FurnitureMaterial.objects.count(), 12)
        self.assertEqual(FurnitureDetail.objects.count(), 8)
        self.assertEqual(HeroSlide.objects.count(), 3)
