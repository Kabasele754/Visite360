from __future__ import annotations

import html
import os
import tempfile
from pathlib import Path

from PIL import Image

from .orientation import normalize_heading, normalize_pitch, normalize_roll, normalize_fov


XMP_HEADER = b"http://ns.adobe.com/xap/1.0/\x00"


def _fmt_float(value, default=0.0) -> str:
    try:
        return f"{float(value):.6f}".rstrip("0").rstrip(".")
    except Exception:
        return str(default)


def _build_gpano_xmp(
    *,
    width: int,
    height: int,
    heading: float = 0,
    pitch: float = 0,
    roll: float = 0,
    initial_fov: float = 90,
) -> bytes:
    """Build minimal Google Photo Sphere XMP for a full equirectangular panorama."""
    heading = _fmt_float(normalize_heading(heading), 0)
    pitch = _fmt_float(normalize_pitch(pitch), 0)
    roll = _fmt_float(normalize_roll(roll), 0)
    initial_fov = _fmt_float(normalize_fov(initial_fov), 90)

    xmp = f"""<?xpacket begin=\"\ufeff\" id=\"W5M0MpCehiHzreSzNTczkc9d\"?>
<x:xmpmeta xmlns:x=\"adobe:ns:meta/\">
  <rdf:RDF xmlns:rdf=\"http://www.w3.org/1999/02/22-rdf-syntax-ns#\">
    <rdf:Description
      rdf:about=\"\"
      xmlns:GPano=\"http://ns.google.com/photos/1.0/panorama/\"
      GPano:UsePanoramaViewer=\"True\"
      GPano:ProjectionType=\"equirectangular\"
      GPano:PoseHeadingDegrees=\"{html.escape(heading)}\"
      GPano:PosePitchDegrees=\"{html.escape(pitch)}\"
      GPano:PoseRollDegrees=\"{html.escape(roll)}\"
      GPano:InitialViewHeadingDegrees=\"{html.escape(heading)}\"
      GPano:InitialViewPitchDegrees=\"{html.escape(pitch)}\"
      GPano:InitialHorizontalFOVDegrees=\"{html.escape(initial_fov)}\"
      GPano:CroppedAreaImageWidthPixels=\"{int(width)}\"
      GPano:CroppedAreaImageHeightPixels=\"{int(height)}\"
      GPano:FullPanoWidthPixels=\"{int(width)}\"
      GPano:FullPanoHeightPixels=\"{int(height)}\"
      GPano:CroppedAreaLeftPixels=\"0\"
      GPano:CroppedAreaTopPixels=\"0\" />
  </rdf:RDF>
</x:xmpmeta>
<?xpacket end=\"w\"?>"""
    return xmp.encode("utf-8")


def _strip_existing_xmp(jpeg_bytes: bytes) -> bytes:
    """Remove existing XMP APP1 segment to avoid duplicate GPano metadata."""
    if not jpeg_bytes.startswith(b"\xff\xd8"):
        return jpeg_bytes

    out = bytearray(jpeg_bytes[:2])
    i = 2

    while i + 4 <= len(jpeg_bytes):
        if jpeg_bytes[i] != 0xFF:
            out.extend(jpeg_bytes[i:])
            break

        marker = jpeg_bytes[i:i + 2]
        if marker in (b"\xff\xda", b"\xff\xd9"):
            out.extend(jpeg_bytes[i:])
            break

        length = int.from_bytes(jpeg_bytes[i + 2:i + 4], "big")
        if length < 2 or i + 2 + length > len(jpeg_bytes):
            out.extend(jpeg_bytes[i:])
            break

        payload = jpeg_bytes[i + 4:i + 2 + length]
        if marker == b"\xff\xe1" and payload.startswith(XMP_HEADER):
            i += 2 + length
            continue

        out.extend(jpeg_bytes[i:i + 2 + length])
        i += 2 + length

    return bytes(out)


def _insert_xmp_app1(jpeg_bytes: bytes, xmp_packet: bytes) -> bytes:
    if not jpeg_bytes.startswith(b"\xff\xd8"):
        raise ValueError("Le fichier préparé n'est pas un JPEG valide.")

    payload = XMP_HEADER + xmp_packet
    segment_length = len(payload) + 2
    if segment_length > 65535:
        raise ValueError("Le bloc XMP est trop grand pour un segment JPEG APP1.")

    app1 = b"\xff\xe1" + segment_length.to_bytes(2, "big") + payload
    clean = _strip_existing_xmp(jpeg_bytes)
    return clean[:2] + app1 + clean[2:]


def prepare_streetview_jpeg_with_xmp(scene) -> str:
    """Create a temporary JPEG copy with Photo Sphere XMP.

    The original uploaded file is never modified. Google Street View Publish can
    ignore heading/pitch/roll sent in create_photo unless these values also exist
    in Photo Sphere XMP, so we inject them here before binary upload.
    """
    source_path = scene.image.path
    temp_to_remove: list[str] = []

    with Image.open(source_path) as img:
        width, height = img.size
        if img.format != "JPEG":
            rgb = img.convert("RGB")
            converted = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
            converted.close()
            rgb.save(converted.name, "JPEG", quality=92, optimize=True)
            jpeg_path = converted.name
            temp_to_remove.append(jpeg_path)
        else:
            jpeg_path = source_path

    jpeg_bytes = Path(jpeg_path).read_bytes()
    xmp = _build_gpano_xmp(
        width=width,
        height=height,
        heading=getattr(scene, "heading", 0) or 0,
        pitch=getattr(scene, "pitch", 0) or 0,
        roll=getattr(scene, "roll", 0) or 0,
        initial_fov=getattr(scene, "initial_fov", 90) or 90,
    )

    output = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
    output.close()
    Path(output.name).write_bytes(_insert_xmp_app1(jpeg_bytes, xmp))

    for temp_path in temp_to_remove:
        try:
            os.remove(temp_path)
        except OSError:
            pass

    return output.name
