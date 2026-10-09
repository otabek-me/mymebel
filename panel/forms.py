"""Panel formalari."""

from django import forms

from shop.models import Category, Furniture, HeroSlide, Material, SiteSettings
from shop.models import validate_uploaded_image


class LoginForm(forms.Form):
    """Panelga kirish formasi."""

    username = forms.CharField(
        max_length=150,
        label="Login",
        widget=forms.TextInput(attrs={
            'autofocus': True,
            'autocomplete': 'username',
            'placeholder': 'Login',
            'class': 'login-input',
        }),
    )
    password = forms.CharField(
        label="Parol",
        widget=forms.PasswordInput(attrs={
            'autocomplete': 'current-password',
            'placeholder': 'Parolingiz',
            'class': 'login-input',
        }),
    )


class CategoryForm(forms.ModelForm):
    """Kategoriya qo'shish/tahrirlash formasi."""

    class Meta:
        model = Category
        fields = ['name', 'image', 'order']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Masalan: Oshxona mebeli'}),
            'order': forms.NumberInput(attrs={'min': 0}),
        }

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image and hasattr(image, 'size'):
            validate_uploaded_image(image)
        return image


class MaterialForm(forms.ModelForm):
    """Material qo'shish/tahrirlash formasi."""

    class Meta:
        model = Material
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': "Masalan: MDF, Taxta"}),
        }


class FurnitureForm(forms.ModelForm):
    """
    Mebelning asosiy ma'lumotlari formasi.

    Materiallar, rasmlar va detallar view tomonidan alohida qayta ishlanadi
    (chunki ular dinamik qatorlar).
    """

    class Meta:
        model = Furniture
        fields = ['name', 'category', 'description', 'length', 'width', 'height', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Masalan: Zamonaviy oshxona garnituri'}),
            'description': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Mebel haqida batafsil ma\'lumot'}),
            'length': forms.NumberInput(attrs={'step': '0.01', 'min': '0.01', 'placeholder': '3'}),
            'width': forms.NumberInput(attrs={'step': '0.01', 'min': '0.01', 'placeholder': '2'}),
            'height': forms.NumberInput(attrs={'step': '0.01', 'min': '0.01', 'placeholder': '2.5'}),
        }

    def clean(self):
        cleaned = super().clean()
        for field in ('length', 'width', 'height'):
            value = cleaned.get(field)
            if value is not None and value <= 0:
                self.add_error(field, "O'lcham 0 dan katta bo'lishi kerak.")
        return cleaned


class HeroSlideForm(forms.ModelForm):
    class Meta:
        model = HeroSlide
        fields = [
            'image', 'image_mobile', 'focus_x', 'focus_y', 'title', 'subtitle',
            'button_text', 'button_url', 'badge_text', 'order', 'is_active',
        ]
        widgets = {
            'image': forms.ClearableFileInput(attrs={'accept': '.jpg,.jpeg,.png,.webp,.heic,.heif'}),
            'image_mobile': forms.ClearableFileInput(attrs={'accept': '.jpg,.jpeg,.png,.webp,.heic,.heif'}),
            'focus_x': forms.HiddenInput(),
            'focus_y': forms.HiddenInput(),
            'subtitle': forms.Textarea(attrs={'rows': 3}),
            'button_url': forms.TextInput(attrs={'placeholder': '/katalog/ yoki https://...'}),
            'order': forms.NumberInput(attrs={'min': 0}),
        }

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image and hasattr(image, 'size'):
            validate_uploaded_image(image)
        return image

    def clean_image_mobile(self):
        image = self.cleaned_data.get('image_mobile')
        if image and hasattr(image, 'size'):
            validate_uploaded_image(image)
        return image


class SiteSettingsForm(forms.ModelForm):
    class Meta:
        model = SiteSettings
        fields = [
            'hero_title', 'hero_subtitle', 'logo', 'hero_image',
            'usp_1_title', 'usp_1_text', 'usp_2_title', 'usp_2_text',
            'usp_3_title', 'usp_3_text', 'usp_4_title', 'usp_4_text',
        ]
        widgets = {'hero_subtitle': forms.Textarea(attrs={'rows': 3})}

    def clean_logo(self):
        image = self.cleaned_data.get('logo')
        if image and hasattr(image, 'size'):
            validate_uploaded_image(image)
        return image

    def clean_hero_image(self):
        image = self.cleaned_data.get('hero_image')
        if image and hasattr(image, 'size'):
            validate_uploaded_image(image)
        return image
