from django.test import SimpleTestCase, override_settings

from apps.knowledge.services.chunking import chunk_text, normalize_text


class ChunkingTests(SimpleTestCase):
    @override_settings(KNOWLEDGE_CHUNK_SIZE=40, KNOWLEDGE_CHUNK_OVERLAP=5)
    def test_chunks_long_text(self):
        chunks = chunk_text("A useful sentence. " * 20)
        self.assertGreater(len(chunks), 1)
        self.assertEqual(chunks[0].position, 0)

    def test_normalizes_whitespace(self):
        self.assertEqual(normalize_text("a   b\n\n\n\nc"), "a b\n\nc")
