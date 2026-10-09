"""
Loyihaning asosiy URL konfiguratsiyasi.

Default Django admin paneli ishlatilmaydi — uning o'rnida
o'zimizning `panel/` ilovasi ulangan.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path

from shop.sitemaps import CategorySitemap, FurnitureSitemap, StaticViewSitemap
from shop.views import custom_404, custom_500

sitemaps = {
    'static': StaticViewSitemap,
    'categories': CategorySitemap,
    'furniture': FurnitureSitemap,
}

urlpatterns = [
    # Mijoz qismi
    path('', include('shop.urls')),
    # Maxsus admin panel
    path('panel/', include('panel.urls')),
    # SEO
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='sitemap'),
    path('robots.txt', include('shop.urls_robots')),
]

# DEBUG rejimida media va static fayllarni Django orqali tarqatamiz
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Xato sahifalari
handler404 = custom_404
handler500 = custom_500
