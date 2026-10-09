"""shop ilovasi URL konfiguratsiyasi (mijoz qismi)."""

from django.urls import path

from . import views

app_name = 'shop'

urlpatterns = [
    path('', views.home, name='home'),
    path('katalog/', views.catalog, name='catalog'),
    path('katalog/<slug:category_slug>/', views.catalog, name='catalog_category'),
    path('mebel/<slug:slug>/', views.furniture_detail, name='furniture_detail'),
    path('api/murojaat/', views.create_inquiry, name='create_inquiry'),
]
