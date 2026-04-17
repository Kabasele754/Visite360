
from io import BytesIO
from django.core.files.base import ContentFile
from PIL import Image, ImageDraw, ImageFont


def compress_image(
    image_field,
    watermark_text="ziarama - visite virtuelle",
    quality=90,
    add_watermark=True,
    max_width=2600,
    max_height=1300,
):
    img = Image.open(image_field)

    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    original_width, original_height = img.size
    print(f"Image originale : {original_width} x {original_height}")

    if original_width > max_width or original_height > max_height:
        ratio = min(max_width / original_width, max_height / original_height)
        new_size = (int(original_width * ratio), int(original_height * ratio))
        img = img.resize(new_size, Image.Resampling.LANCZOS)
        print(f"Image redimensionnée : {new_size}")
    else:
        print("Aucun redimensionnement nécessaire")

    if add_watermark:
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", 30)
        except Exception:
            font = ImageFont.load_default()

        bbox = font.getbbox(watermark_text)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        x = img.width - text_width - 20
        y = img.height - text_height - 20

        draw.text((x + 1, y + 1), watermark_text, font=font, fill=(0, 0, 0))
        draw.text((x, y), watermark_text, font=font, fill=(255, 255, 255))

    buffer = BytesIO()
    img.save(buffer, format="WEBP", quality=quality, method=6, optimize=True)

    final_size_kb = round(buffer.tell() / 1024, 2)
    print(f"Taille compressée : {final_size_kb} Ko")

    if final_size_kb < 10:
        raise ValueError("Compression trop forte : fichier inutilisable.")

    buffer.seek(0)
    return ContentFile(buffer.getvalue()), final_size_kb


def generate_thumbnail(image_file, size=(1200, 600), format="WEBP", quality=88):
    image = Image.open(image_file)

    if image.mode in ("RGBA", "P"):
        image = image.convert("RGB")

    image.thumbnail(size)

    buffer = BytesIO()
    image.save(buffer, format=format, quality=quality)

    buffer.seek(0)
    return ContentFile(buffer.getvalue()), round(buffer.tell() / 1024, 2)