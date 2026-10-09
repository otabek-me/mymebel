from decimal import Decimal
from io import BytesIO
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse
from PIL import Image

from shop.models import Category, Furniture, FurnitureMaterial, HeroSlide, Inquiry, Material


@override_settings(STORAGES={
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class PanelWorkflowTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Yotoqxona')
        self.material = Material.objects.create(name='Laminat')
        self.furniture = Furniture.objects.create(
            name='Kiyim shkafi',
            description='Uch eshikli shkaf',
            category=self.category,
            length=Decimal('2.00'),
            width=Decimal('0.60'),
            height=Decimal('2.20'),
        )
        self.option = FurnitureMaterial.objects.create(
            furniture=self.furniture,
            material=self.material,
            price=Decimal('2500000'),
        )
        self.inquiry = Inquiry.objects.create(
            furniture=self.furniture,
            furniture_name=self.furniture.name,
            material_name=self.material.name,
            material_price=self.option.price,
            total_price=self.option.price,
            phone='+998 90 123 45 67',
        )
        self.user = get_user_model().objects.create_user(
            username='operator',
            password='Long-and-safe-Password-123',
            is_staff=True,
        )

    def test_panel_pages_require_staff_and_render_for_staff(self):
        self.assertEqual(reverse('panel:login'), '/panel/kirish/')
        self.assertEqual(self.client.get('/panel/login/').status_code, 200)
        protected_urls = (
            reverse('panel:dashboard'),
            reverse('panel:category_list'),
            reverse('panel:material_list'),
            reverse('panel:furniture_list'),
            reverse('panel:inquiry_list'),
        )
        for url in protected_urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 302)

        self.client.force_login(self.user)
        for url in protected_urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_login_form_has_the_custom_fields_and_keeps_only_the_username_after_failure(self):
        response = self.client.get(reverse('panel:login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'autocomplete="username"')
        self.assertContains(response, 'autocomplete="current-password"')
        self.assertContains(response, 'id="password-toggle"')

        response = self.client.post(reverse('panel:login'), {
            'username': 'operator',
            'password': 'wrong-password',
        })
        self.assertContains(response, 'Login yoki parol noto&#x27;g&#x27;ri.')
        self.assertContains(response, 'id="id_username"')
        self.assertContains(response, 'value="operator"')
        password_widget = response.context['form']['password'].field.widget
        self.assertFalse(password_widget.render_value)

    def test_failed_login_attempts_lock_the_client_for_ten_minutes(self):
        ip_address = '203.0.113.55'
        cache.delete(f'login_lock_{ip_address}')
        cache.delete(f'login_attempts_{ip_address}')
        for _ in range(5):
            response = self.client.post(reverse('panel:login'), {
                'username': 'operator',
                'password': 'wrong-password',
            }, REMOTE_ADDR=ip_address)

        self.assertEqual(
            response.context['login_error'],
            "Juda ko'p urinish. 10 daqiqadan keyin qayta urinib ko'ring.",
        )
        self.assertTrue(cache.get(f'login_lock_{ip_address}'))
        cache.delete(f'login_lock_{ip_address}')
        cache.delete(f'login_attempts_{ip_address}')

    def test_opening_inquiries_marks_them_seen_and_updates_status(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('panel:inquiry_list'))
        self.assertEqual(response.status_code, 200)
        self.inquiry.refresh_from_db()
        self.assertTrue(self.inquiry.is_seen)
        self.assertContains(response, self.inquiry.phone)

        response = self.client.post(
            reverse('panel:inquiry_update_status', args=[self.inquiry.pk]),
            {'status': Inquiry.STATUS_CONTACTED},
        )
        self.assertRedirects(response, reverse('panel:inquiry_list'))
        self.inquiry.refresh_from_db()
        self.assertEqual(self.inquiry.status, Inquiry.STATUS_CONTACTED)

    def test_customer_submission_reaches_panel_notifications_and_inquiry_list(self):
        self.inquiry.is_seen = True
        self.inquiry.save(update_fields=['is_seen'])
        response = self.client.post(reverse('shop:create_inquiry'), {
            'furniture_id': self.furniture.pk,
            'material_id': self.option.pk,
            'phone': '+998 91 234 56 78',
            'customer_name': 'Dilnoza',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['ok'])

        self.client.force_login(self.user)
        notifications = self.client.get(reverse('panel:api_notifications')).json()
        self.assertEqual(notifications['count'], 1)
        self.assertEqual(notifications['items'][0]['phone'], '+998 91 234 56 78')
        self.assertEqual(notifications['items'][0]['furniture'], self.furniture.name)

        response = self.client.get(reverse('panel:inquiry_list'))
        self.assertContains(response, '+998 91 234 56 78')
        saved_inquiry = Inquiry.objects.get(phone='+998 91 234 56 78')
        self.assertTrue(saved_inquiry.is_seen)

    def test_notifications_endpoint_returns_unseen_snapshot_and_no_delete_route(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('panel:api_notifications'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['items'][0]['phone'], self.inquiry.phone)

        self.assertEqual(
            self.client.get(f'/panel/buyurtmalar/{self.inquiry.pk}/ochirish/').status_code,
            404,
        )

    def test_furniture_form_saves_material_and_product_specific_details(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('panel:furniture_add'), {
            'name': 'Yangi yotoqxona stoli',
            'category': self.category.pk,
            'description': 'Qo‘lda tayyorlangan',
            'length': '1.20',
            'width': '0.50',
            'height': '0.75',
            'is_active': 'on',
            'material_id': [self.material.pk],
            'material_price': ['875000.50'],
            'detail_name': ['Qo‘shimcha tortma'],
            'detail_price': ['125000'],
        })

        self.assertRedirects(response, reverse('panel:furniture_list'))
        furniture = Furniture.objects.get(name='Yangi yotoqxona stoli')
        self.assertEqual(
            furniture.furniture_materials.get().price,
            Decimal('875000.50'),
        )
        self.assertEqual(furniture.details.get().name, 'Qo‘shimcha tortma')

    def test_inline_category_and_material_creation_is_staff_only(self):
        response = self.client.post(reverse('panel:api_add_category'), {'name': 'Bolalar xonasi'})
        self.assertEqual(response.status_code, 302)

        self.client.force_login(self.user)
        response = self.client.post(reverse('panel:api_add_category'), {'name': 'Bolalar xonasi'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['ok'])
        response = self.client.post(reverse('panel:api_add_material'), {'name': 'Shpon'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['ok'])

    def test_inline_creation_controls_and_modal_are_wired_outside_the_furniture_form(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('panel:furniture_add'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        parent_form_start = html.index('<form id="furniture-form"')
        parent_form_end = html.index('</form>', parent_form_start)
        modal_position = html.index('<div id="ajax-modal"')

        self.assertLess(parent_form_end, modal_position)
        self.assertRegex(html, r'<button type="button" id="open-category-modal"')
        self.assertRegex(html, r'<button type="button" id="open-material-modal"')
        self.assertIn(reverse('panel:api_add_category'), html)
        self.assertIn(reverse('panel:api_add_material'), html)
        self.assertIn("'X-CSRFToken':csrfToken", html)
        self.assertIn('Kategoriya qo‘shildi', html)

    def test_banner_management_create_preview_order_toggle_and_delete(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('panel:hero_slide_list')).status_code, 200)
        self.assertContains(self.client.get(reverse('panel:hero_slide_list')), "Birinchi bannerni qo'shing")
        image_bytes = BytesIO()
        Image.new('RGB', (1920, 1000), '#947a60').save(image_bytes, format='PNG')
        upload = SimpleUploadedFile('banner.png', image_bytes.getvalue(), content_type='image/png')

        with TemporaryDirectory() as media_dir, override_settings(MEDIA_ROOT=media_dir):
            response = self.client.post(reverse('panel:hero_slide_add'), {
                'image': upload,
                'title': 'Yangi banner',
                'subtitle': 'Bosh sahifa uchun izoh',
                'button_text': 'Katalogni ko‘rish',
                'button_url': '/katalog/',
                'focus_x': '34',
                'focus_y': '66',
                'order': '0',
                'is_active': 'on',
            })
            self.assertRedirects(response, reverse('panel:hero_slide_list'))
            slide = HeroSlide.objects.get()
            self.assertEqual(slide.focus_x, 34)
            self.assertEqual(slide.focus_y, 66)
            self.assertTrue(slide.image.name.endswith('.webp'))
            self.assertTrue(slide.image_medium.storage.exists(slide.image_medium.name))

            response = self.client.post(reverse('panel:hero_slide_toggle', args=[slide.pk]))
            self.assertRedirects(response, reverse('panel:hero_slide_list'))
            slide.refresh_from_db()
            self.assertFalse(slide.is_active)

            delete_page = self.client.get(reverse('panel:hero_slide_delete', args=[slide.pk]))
            self.assertContains(delete_page, "o'chirasizmi")
            response = self.client.post(reverse('panel:hero_slide_delete', args=[slide.pk]))
            self.assertRedirects(response, reverse('panel:hero_slide_list'))
            self.assertFalse(HeroSlide.objects.exists())

    def test_banner_limit_and_external_button_url_validation(self):
        image_bytes = BytesIO()
        Image.new('RGB', (32, 18), '#947a60').save(image_bytes, format='PNG')
        image_content = image_bytes.getvalue()
        with TemporaryDirectory() as media_dir, override_settings(MEDIA_ROOT=media_dir):
            for index in range(6):
                HeroSlide.objects.create(
                    image=SimpleUploadedFile(
                        f'banner-{index}.png', image_content, content_type='image/png',
                    ),
                    title=f'Banner {index}',
                    subtitle='Test banner',
                    button_url='/katalog/',
                )
            with self.assertRaisesMessage(ValidationError, '6 ta faol'):
                HeroSlide.objects.create(
                    image=SimpleUploadedFile(
                        'banner-seventh.png', image_content, content_type='image/png',
                    ),
                    title='Yettinchi banner',
                    subtitle='Test banner',
                    button_url='/katalog/',
                )

        self.client.force_login(self.user)
        response = self.client.post(reverse('panel:hero_slide_add'), {
            'title': 'Noto‘g‘ri havola',
            'subtitle': 'Test banner',
            'button_text': "Katalogni ko'rish",
            'button_url': 'javascript:alert(1)',
            'focus_x': '50',
            'focus_y': '50',
            'order': '7',
            'is_active': '',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'http(s) manzil')
