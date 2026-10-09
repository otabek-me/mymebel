"""SEO uchun sitemap sinflari."""

from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from .models import Category, Furniture


class StaticViewSitemap(Sitemap):
    """Statik sahifalar (bosh sahifa, katalog)."""
    priority = 0.8
    changefreq = 'daily'

    def items(self):
        return ['shop:home', 'shop:catalog']

    def location(self, item):
        return reverse(item)


class CategorySitemap(Sitemap):
    """Kategoriya sahifalari."""
    priority = 0.7
    changefreq = 'weekly'

    def items(self):
        return Category.objects.all()

    def location(self, obj):
        return reverse('shop:catalog_category', args=[obj.slug])


class FurnitureSitemap(Sitemap):
    """Mebel sahifalari."""
    priority = 0.9
    changefreq = 'weekly'

    def items(self):
        return Furniture.objects.filter(is_active=True)

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return reverse('shop:furniture_detail', args=[obj.slug])
