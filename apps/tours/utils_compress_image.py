from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter


def _open_image(image_field):
    if hasattr(image_field, "seek"):
        image_field.seek(0)

    img = Image.open(image_field)
    img = ImageOps.exif_transpose(img)

    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    elif img.mode != "RGB":
        img = img.convert("RGB")

    return img


def _resize_keep_ratio(img, max_width, max_height):
    original_width, original_height = img.size

    if original_width <= max_width and original_height <= max_height:
        return img, False

    ratio = min(max_width / original_width, max_height / original_height)
    new_size = (int(original_width * ratio), int(original_height * ratio))

    resized = img.resize(new_size, Image.Resampling.LANCZOS)
    resized = resized.filter(
        ImageFilter.UnsharpMask(radius=1.2, percent=115, threshold=2)
    )

    return resized, True


def _add_watermark(img, watermark_text):
    draw = ImageDraw.Draw(img)

    font_size = max(18, min(42, img.width // 45))
    padding = max(12, img.width // 90)

    try:
        font = ImageFont.truetype("DejaVuSans.ttf", font_size)
    except Exception:
        font = ImageFont.load_default()

    bbox = font.getbbox(watermark_text)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    x = img.width - text_width - padding
    y = img.height - text_height - padding

    draw.text((x + 2, y + 2), watermark_text, font=font, fill=(0, 0, 0))
    draw.text((x, y), watermark_text, font=font, fill=(255, 255, 255))

    return img


def _save_webp_adaptive(
    img,
    initial_quality=82,
    min_quality=60,
    step=4,
    target_max_kb=None,
    method=6,
):
    best_bytes = None
    best_size_kb = None
    best_quality = initial_quality

    quality = initial_quality

    while quality >= min_quality:
        buffer = BytesIO()

        img.save(
            buffer,
            format="WEBP",
            quality=quality,
            method=method,
            optimize=True,
        )

        size_kb = round(buffer.tell() / 1024, 2)

        best_bytes = buffer.getvalue()
        best_size_kb = size_kb
        best_quality = quality

        if target_max_kb is None or size_kb <= target_max_kb:
            break

        quality -= step

    return ContentFile(best_bytes), best_size_kb, best_quality


def compress_pil_image_to_webp(
    img,
    initial_quality=78,
    min_quality=54,
    target_max_kb=180,
    method=6,
):
    if img.mode != "RGB":
        img = img.convert("RGB")

    content, final_size_kb, final_quality = _save_webp_adaptive(
        img,
        initial_quality=initial_quality,
        min_quality=min_quality,
        target_max_kb=target_max_kb,
        method=method,
    )

    return content, final_size_kb, final_quality


def compress_image(
    image_field,
    watermark_text="ziarama - visite virtuelle",
    add_watermark=False,
    max_width=2600,
    max_height=1300,
    initial_quality=82,
    min_quality=60,
    target_max_kb=850,
):
    img = _open_image(image_field)

    img, resized = _resize_keep_ratio(img, max_width, max_height)

    if add_watermark:
        img = _add_watermark(img, watermark_text)

    content, final_size_kb, final_quality = _save_webp_adaptive(
        img,
        initial_quality=initial_quality,
        min_quality=min_quality,
        target_max_kb=target_max_kb,
    )

    if final_size_kb < 8:
        raise ValueError("Compression trop forte : fichier inutilisable.")

    return content, final_size_kb


def generate_thumbnail(
    image_file,
    size=(1200, 600),
    quality=72,
    target_max_kb=180,
):
    image = _open_image(image_file)
    image = ImageOps.fit(image, size, Image.Resampling.LANCZOS)
    image = image.filter(ImageFilter.UnsharpMask(radius=1.0, percent=110, threshold=2))

    content, final_size_kb, final_quality = _save_webp_adaptive(
        image,
        initial_quality=quality,
        min_quality=50,
        target_max_kb=target_max_kb,
    )

    return content, final_size_kb


def generate_panorama_thumbnail(
    image_file,
    size=(1200, 600),
    quality=70,
    target_max_kb=160,
):
    image = _open_image(image_file)
    image = image.resize(size, Image.Resampling.LANCZOS)
    image = image.filter(ImageFilter.UnsharpMask(radius=1.0, percent=110, threshold=2))

    content, final_size_kb, final_quality = _save_webp_adaptive(
        image,
        initial_quality=quality,
        min_quality=50,
        target_max_kb=target_max_kb,
    )

    return content, final_size_kb


def generate_panorama_preview(
    image_file,
    size=(512, 256),
    quality=38,
    target_max_kb=28,
    blur_radius=1.15,
):
    image = _open_image(image_file)
    image = image.resize(size, Image.Resampling.LANCZOS)
    image = image.filter(ImageFilter.GaussianBlur(radius=blur_radius))

    content, final_size_kb, final_quality = _save_webp_adaptive(
        image,
        initial_quality=quality,
        min_quality=28,
        target_max_kb=target_max_kb,
    )

    return content, final_size_kb


def generate_placeholder(
    image_file,
    size=(80, 40),
    quality=40,
    target_max_kb=12,
):
    image = _open_image(image_file)
    image = ImageOps.fit(image, size, Image.Resampling.LANCZOS)
    image = image.filter(ImageFilter.GaussianBlur(radius=1.2))

    content, final_size_kb, final_quality = _save_webp_adaptive(
        image,
        initial_quality=quality,
        min_quality=30,
        target_max_kb=target_max_kb,
    )

    return content, final_size_kb