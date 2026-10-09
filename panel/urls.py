"""Maxsus admin panel URL konfiguratsiyasi."""

from django.urls import path

from . import views

app_name = 'panel'

urlpatterns = [
    # Autentifikatsiya
    path('kirish/', views.panel_login, name='login'),
    path('login/', views.panel_login),
    path('logout/', views.panel_logout, name='logout'),

    # Dashboard
    path('', views.dashboard, name='dashboard'),

    # Bosh sahifa bannerlari
    path('bannerlar/', views.hero_slide_list, name='hero_slide_list'),
    path('bannerlar/qoshish/', views.hero_slide_form, name='hero_slide_add'),
    path('bannerlar/<int:pk>/tahrirlash/', views.hero_slide_form, name='hero_slide_edit'),
    path('bannerlar/<int:pk>/holat/', views.hero_slide_toggle, name='hero_slide_toggle'),
    path('bannerlar/<int:pk>/tartib/<str:direction>/', views.hero_slide_move, name='hero_slide_move'),
    path('bannerlar/<int:pk>/ochirish/', views.hero_slide_delete, name='hero_slide_delete'),

    # Kategoriyalar
    path('kategoriyalar/', views.category_list, name='category_list'),
    path('kategoriyalar/qoshish/', views.category_form, name='category_add'),
    path('kategoriyalar/<int:pk>/tahrirlash/', views.category_form, name='category_edit'),
    path('kategoriyalar/<int:pk>/ochirish/', views.category_delete, name='category_delete'),

    # Materiallar
    path('materiallar/', views.material_list, name='material_list'),
    path('materiallar/qoshish/', views.material_form, name='material_add'),
    path('materiallar/<int:pk>/tahrirlash/', views.material_form, name='material_edit'),
    path('materiallar/<int:pk>/ochirish/', views.material_delete, name='material_delete'),

    # Mebellar
    path('mebellar/', views.furniture_list, name='furniture_list'),
    path('mebellar/qoshish/', views.furniture_form, name='furniture_add'),
    path('mebellar/<int:pk>/tahrirlash/', views.furniture_form, name='furniture_edit'),
    path('mebellar/<int:pk>/ochirish/', views.furniture_delete, name='furniture_delete'),
    path('mebellar/<int:pk>/holat/', views.furniture_toggle_active, name='furniture_toggle'),
    path('mebellar/<int:pk>/rasm-ochirish/', views.furniture_image_delete, name='furniture_image_delete'),

    # Buyurtmalar
    path('buyurtmalar/', views.inquiry_list, name='inquiry_list'),
    path('buyurtmalar/<int:pk>/', views.inquiry_detail, name='inquiry_detail'),
    path('buyurtmalar/<int:pk>/holat/', views.inquiry_update_status, name='inquiry_update_status'),

    # AJAX yordamchi endpoint'lar
    path('api/kategoriya-qoshish/', views.api_add_category, name='api_add_category'),
    path('api/material-qoshish/', views.api_add_material, name='api_add_material'),
    path('api/bildirishnoma/', views.api_notifications, name='api_notifications'),
]
