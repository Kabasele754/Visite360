from django.test import SimpleTestCase, override_settings

from apps.ai_core.services.providers import DeterministicLocalProvider


class DeterministicLocalProviderTests(SimpleTestCase):
    @override_settings(AI_EMBEDDING_DIMENSIONS=16)
    def test_embedding_is_stable_and_dimensioned(self):
        provider = DeterministicLocalProvider()
        first = provider.embed(["hello"])[0]
        second = provider.embed(["hello"])[0]
        self.assertEqual(first, second)
        self.assertEqual(len(first), 16)

from apps.ai_core.services.providers import (
    _fit_dimensions,
    _google_native_embedding_dimensions,
    _normalize_vector,
)


class GeminiEmbeddingDimensionTests(SimpleTestCase):
    @override_settings(
        GOOGLE_GENAI_USE_VERTEXAI=True,
        GOOGLE_EMBEDDING_NATIVE_DIMENSIONS=0,
    )
    def test_vertex_native_dimension_is_capped_at_768(self):
        self.assertEqual(
            _google_native_embedding_dimensions(
                model="text-embedding-004",
                requested_dimensions=1536,
            ),
            768,
        )

    def test_native_vector_can_be_padded_to_pgvector_width_and_normalized(self):
        vector = [1.0] * 768
        fitted = _fit_dimensions(vector, 1536)
        normalized = _normalize_vector(fitted)
        self.assertEqual(len(normalized), 1536)
        self.assertAlmostEqual(sum(value * value for value in normalized), 1.0, places=6)

from apps.ai_core.services.router import AIProviderRouter


class AIRouterRetryClassificationTests(SimpleTestCase):
    def test_vertex_resource_exhausted_is_retryable(self):
        error = RuntimeError("429 RESOURCE_EXHAUSTED: Resource exhausted")
        self.assertTrue(AIProviderRouter._is_retryable_error(error))

    def test_invalid_argument_is_not_retryable(self):
        error = RuntimeError("400 INVALID_ARGUMENT")
        self.assertFalse(AIProviderRouter._is_retryable_error(error))
