"""Shared image processing utilities for uploaded site imagery."""

import os
from io import BytesIO

from PIL import Image, ImageOps
from django.core.files.uploadedfile import InMemoryUploadedFile


def process_image_variants(upload, base_name, *, max_size, medium_size):
    """Return WEBP original-sized and medium variants without distorting them."""
    upload.seek(0)
    with Image.open(upload) as opened:
        image = ImageOps.exif_transpose(opened)
        if image.mode == 'P':
            image = image.convert('RGBA')
        if image.mode in ('RGBA', 'LA'):
            rgba = image.convert('RGBA')
            background = Image.new('RGBA', rgba.size, (255, 255, 255, 255))
            image = Image.alpha_composite(background, rgba).convert('RGB')
        elif image.mode != 'RGB':
            image = image.convert('RGB')
        else:
            image = image.copy()

    stem = os.path.splitext(os.path.basename(base_name))[0] or 'image'

    def variant(bound, suffix, quality):
        result = image.copy()
        result.thumbnail((bound, bound), Image.Resampling.LANCZOS)
        output = BytesIO()
        result.save(output, format='WEBP', quality=quality, method=6)
        output.seek(0)
        name = f'{stem}{suffix}.webp'
        return InMemoryUploadedFile(
            output, 'ImageField', name, 'image/webp',
            output.getbuffer().nbytes, None,
        )

    return (
        variant(max_size, '', 92),
        variant(medium_size, '_medium', 88),
    )
