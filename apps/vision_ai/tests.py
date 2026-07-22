import io
from PIL import Image
from django.test import SimpleTestCase

from apps.vision_ai.services.panorama import extract_panorama_frames


class PanoramaTests(SimpleTestCase):
    def test_regular_image_returns_one_frame(self):
        image = Image.new("RGB", (400, 300), "white")
        buffer = io.BytesIO()
        image.save(buffer, "JPEG")
        frames = extract_panorama_frames(buffer.getvalue(), max_frames=4)
        self.assertEqual(len(frames), 1)

    def test_equirectangular_image_returns_requested_frames(self):
        image = Image.new("RGB", (800, 400), "white")
        buffer = io.BytesIO()
        image.save(buffer, "JPEG")
        frames = extract_panorama_frames(buffer.getvalue(), max_frames=4)
        self.assertEqual(len(frames), 4)


class PanoramaGeometryTests(SimpleTestCase):
    def test_frame_center_maps_to_frame_orientation(self):
        import math
        from apps.vision_ai.services.geometry import angular_distance, frame_pixel_to_panorama

        yaw, pitch = frame_pixel_to_panorama(
            x=448, y=448, width=896, height=896,
            frame_yaw_degrees=90, frame_pitch_degrees=0, fov_degrees=82,
        )
        self.assertLess(angular_distance(yaw, pitch, math.pi / 2, 0), 1e-6)

from django.test import override_settings
from apps.vision_ai.services.providers import enabled_provider_names


class EnabledVisionProviderTests(SimpleTestCase):
    @override_settings(
        VISION_ENABLE_YOLO=True,
        VISION_ENABLE_PADDLEOCR=True,
        VISION_ENABLE_GEMINI=True,
        VISION_ENABLE_OPENAI=True,
        OPENAI_API_KEY="",
        GOOGLE_GENAI_USE_VERTEXAI=True,
        GOOGLE_CLOUD_PROJECT="example-project",
        GOOGLE_CLOUD_LOCATION="us-central1",
        GEMINI_API_KEY="",
    )
    def test_unconfigured_openai_is_skipped_but_vertex_gemini_is_kept(self):
        names = enabled_provider_names(["yolo", "paddleocr", "gemini", "openai"])
        self.assertEqual(names, ["yolo", "paddleocr", "gemini"])

class DeepPanoramaCoverageTests(SimpleTestCase):
    def test_deep_profile_returns_twenty_four_views(self):
        image = Image.new("RGB", (1600, 800), "white")
        buffer = io.BytesIO()
        image.save(buffer, "JPEG")
        frames = extract_panorama_frames(buffer.getvalue(), max_frames=24)
        self.assertEqual(len(frames), 24)
        self.assertEqual(len({(frame.yaw, frame.pitch) for frame in frames}), 24)
        self.assertTrue(any(frame.pitch < 0 for frame in frames))
        self.assertTrue(any(frame.pitch > 0 for frame in frames))

from apps.vision_ai.services.panorama import (
    InvalidPanoramaImageError,
    prepare_image_bytes,
)


class PanoramaRecoveryTests(SimpleTestCase):
    def test_jpeg_with_leading_camera_bytes_is_recovered(self):
        image = Image.new("RGB", (800, 400), "white")
        buffer = io.BytesIO()
        image.save(buffer, "JPEG")
        prepared = prepare_image_bytes(b"CAMERA-METADATA\x00\x00" + buffer.getvalue())
        self.assertTrue(prepared.repaired)
        self.assertEqual((prepared.width, prepared.height), (800, 400))
        frames = extract_panorama_frames(prepared.image_bytes, max_frames=4)
        self.assertEqual(len(frames), 4)

    def test_html_storage_response_is_rejected_with_clear_error(self):
        with self.assertRaises(InvalidPanoramaImageError) as context:
            prepare_image_bytes(b"<!doctype html><html><body>Access denied</body></html>")
        self.assertIn("instead of image data", str(context.exception))


class ExactPointSelectionTests(SimpleTestCase):
    def test_click_selects_small_object_inside_large_shelf_region(self):
        from types import SimpleNamespace
        from apps.vision_ai.models import VisionInsight
        from apps.vision_ai.services.geometry import frame_pixel_to_panorama
        from apps.vision_ai.services.insights import find_point_insight

        frame = SimpleNamespace(
            yaw=0.0,
            pitch=0.0,
            metadata={"width": 896, "height": 896, "fov": 82},
        )
        broad = SimpleNamespace(
            id=1,
            kind=VisionInsight.Kind.OBJECT,
            confidence=0.95,
            bbox=[80, 80, 820, 820],
            polygon=[],
            frame=frame,
            yaw=0.0,
            pitch=0.0,
            angular_radius=0.2,
        )
        product = SimpleNamespace(
            id=2,
            kind=VisionInsight.Kind.OBJECT,
            confidence=0.72,
            bbox=[500, 390, 650, 610],
            polygon=[],
            frame=frame,
            yaw=0.15,
            pitch=0.0,
            angular_radius=0.08,
        )
        yaw, pitch = frame_pixel_to_panorama(
            x=560,
            y=500,
            width=896,
            height=896,
            frame_yaw_degrees=0,
            frame_pitch_degrees=0,
            fov_degrees=82,
        )
        analysis = SimpleNamespace(insights=SimpleNamespace(all=lambda: [broad, product]))
        selected, _ = find_point_insight(analysis, yaw=yaw, pitch=pitch)
        self.assertIs(selected, product)

    def test_projection_round_trip_is_pixel_accurate(self):
        from apps.vision_ai.services.geometry import (
            frame_pixel_to_panorama,
            panorama_to_frame_pixel,
        )

        yaw, pitch = frame_pixel_to_panorama(
            x=215,
            y=643,
            width=896,
            height=896,
            frame_yaw_degrees=120,
            frame_pitch_degrees=-30,
            fov_degrees=82,
        )
        pixel = panorama_to_frame_pixel(
            yaw=yaw,
            pitch=pitch,
            width=896,
            height=896,
            frame_yaw_degrees=120,
            frame_pitch_degrees=-30,
            fov_degrees=82,
        )
        self.assertIsNotNone(pixel)
        self.assertAlmostEqual(pixel[0], 215, places=6)
        self.assertAlmostEqual(pixel[1], 643, places=6)


class StrictVisionJsonTests(SimpleTestCase):
    def test_first_valid_json_object_is_parsed_without_concatenating_second(self):
        from apps.ai_core.services.providers import parse_json_object

        payload = (
            'Preface {"scene_type":"shop","summary":"A concise shop view."}'
            ' {"scene_type":"wrong","summary":"Second response"}'
        )
        parsed = parse_json_object(payload)
        self.assertEqual(parsed["scene_type"], "shop")
        self.assertEqual(parsed["summary"], "A concise shop view.")
