from decimal import Decimal
from io import BytesIO
import random

from django.core.management.base import BaseCommand
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils.text import slugify
from PIL import Image, ImageDraw

from shop.models import Category, Furniture, FurnitureDetail, FurnitureMaterial, HeroSlide, Material


class Command(BaseCommand):
    help = "Do'kon uchun namunaviy kategoriya, material va mebellarni yaratadi."

    def handle(self, *args, **options):
        categories = {
            name: Category.objects.get_or_create(
                name=name,
                defaults={'order': order},
            )[0]
            for order, name in enumerate(('Oshxona', 'Yotoqxona', 'Mehmonxona'), start=1)
        }
        materials = {
            name: Material.objects.get_or_create(name=name)[0]
            for name in ('Taxta', 'Akril', 'Laminat', 'MDF')
        }

        examples = [
            ('Zamonaviy oshxona garnituri', 'Oshxona', (3, 2.5, 2.4), [('MDF', 12500000), ('Akril', 16800000)], [('Yumshoq yopiluvchi tortma', 450000), ('Tosh ish stoli', 1800000)]),
            ('Klassik oshxona stoli', 'Oshxona', (1.6, 0.9, 0.76), [('Taxta', 2800000), ('Laminat', 1900000)], [("Qo'shimcha stul", 650000)]),
            ('Yotoqxona garnituri', 'Yotoqxona', (3.2, 2.1, 2.2), [('MDF', 14500000), ('Laminat', 11200000)], [('Yoritgichli tumba', 850000), ("Ko'zgu", 600000)]),
            ('Uch eshikli kiyim shkafi', 'Yotoqxona', (2.4, 0.65, 2.3), [('MDF', 7200000), ('Laminat', 5600000)], [('Ichki tortmalar', 500000)]),
            ('Mehmonxona TV tumbasi', 'Mehmonxona', (1.8, 0.45, 0.55), [('Taxta', 3200000), ('MDF', 2600000)], [('Kabel yashirgich', 180000)]),
            ('Kitoblar uchun ochiq javon', 'Mehmonxona', (1.2, 0.35, 2.0), [('Taxta', 3900000), ('Laminat', 2750000)], [("Qo'shimcha javon", 250000)]),
        ]

        for name, category_name, dimensions, options, details in examples:
            furniture, _ = Furniture.objects.get_or_create(
                slug=slugify(name),
                defaults={
                    'name': name,
                    'description': (
                        f"{name}. Mustahkam materiallardan tayyorlanadi. "
                        "O'lcham va ranglarni xonangizga moslab kelishish mumkin."
                    ),
                    'category': categories[category_name],
                    'length': Decimal(str(dimensions[0])),
                    'width': Decimal(str(dimensions[1])),
                    'height': Decimal(str(dimensions[2])),
                    'is_active': True,
                },
            )
            for material_name, amount in options:
                FurnitureMaterial.objects.get_or_create(
                    furniture=furniture,
                    material=materials[material_name],
                    defaults={'price': Decimal(amount)},
                )
            for detail_name, amount in details:
                FurnitureDetail.objects.get_or_create(
                    furniture=furniture,
                    name=detail_name,
                    defaults={'price': Decimal(amount)},
                )

        if not HeroSlide.objects.exists():
            self._create_demo_slides()

        self.stdout.write(self.style.SUCCESS(
            "Namunaviy ma'lumotlar tayyor: 3 kategoriya, 4 material, 6 mebel va demo bannerlar."
        ))

    def _create_demo_slides(self):
        slides = (
            ('Sokin va tabiiy ko‘rinish', 'Uy uchun mos mebel variantlarini ko‘rib chiqing.', 'Yangi kolleksiya'),
            ('Har bir xonaga o‘ziga xos yechim', 'O‘lcham va materiallarni o‘zingizga moslang.', 'O‘zingizga moslang'),
            ('Tanlov sizdan boshlanadi', 'Katalogni ko‘ring va narx variantlarini solishtiring.', ''),
        )
        palettes = (
            ((195, 166, 134), (42, 68, 53), (224, 201, 172)),
            ((180, 146, 111), (52, 75, 63), (231, 218, 194)),
            ((206, 184, 154), (47, 67, 58), (164, 127, 91)),
        )
        for order, (content, palette) in enumerate(zip(slides, palettes), start=1):
            title, subtitle, badge = content
            image_bytes = BytesIO()
            width, height = 1920, 1000
            low_width, low_height = 480, 250
            start, end, accent = palette
            noise = random.Random(401 + order)
            pixels = []
            for y in range(low_height):
                for x in range(low_width):
                    blend = min(1, max(0, (x / low_width * .72 + y / low_height * .28)))
                    grain = noise.randrange(-4, 5)
                    pixels.append(tuple(
                        max(0, min(255, round(start[channel] * (1 - blend) + end[channel] * blend) + grain))
                        for channel in range(3)
                    ))
            image = Image.new('RGB', (low_width, low_height))
            image.putdata(pixels)
            image = image.resize((width, height), Image.Resampling.BICUBIC)
            draw = ImageDraw.Draw(image, 'RGBA')
            draw.ellipse((1190, 105, 1930, 845), fill=(*accent, 36), outline=(*accent, 80), width=4)
            draw.rounded_rectangle((1290, 410, 1830, 815), radius=34, fill=(30, 38, 32, 62), outline=(255, 255, 255, 80), width=3)
            draw.rounded_rectangle((1360, 345, 1760, 490), radius=24, fill=(255, 255, 255, 24), outline=(255, 255, 255, 90), width=3)
            draw.line((1560, 490, 1560, 815), fill=(255, 255, 255, 65), width=3)
            draw.ellipse((1470, 535, 1650, 715), fill=(*accent, 70), outline=(255, 255, 255, 80), width=3)
            image.save(image_bytes, format='PNG', optimize=True)
            upload = SimpleUploadedFile(
                f'demo-banner-{order}.png', image_bytes.getvalue(), content_type='image/png',
            )
            HeroSlide.objects.create(
                image=upload,
                focus_x=52,
                focus_y=50,
                title=title,
                subtitle=subtitle,
                button_text="Katalogni ko'rish",
                button_url='/katalog/',
                badge_text=badge,
                order=order,
                is_active=True,
            )
