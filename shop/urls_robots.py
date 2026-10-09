"""robots.txt uchun alohida URL moduli."""

from django.urls import path

from . import views

urlpatterns = [
    path('', views.robots_txt, name='robots_txt'),
]
