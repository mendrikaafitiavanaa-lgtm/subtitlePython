"""Tests pour le service de traduction de sous-titres."""

import unittest

from src.core.models import SubtitleSegment
from src.services.translator import SubtitleTranslator


class TestSubtitleTranslator(unittest.TestCase):
    def setUp(self):
        self.translator = SubtitleTranslator()

    def test_same_language_returns_unchanged(self):
        segs = [SubtitleSegment(index=1, start=0.0, end=2.0, text="Bonjour le monde")]
        res = self.translator.translate_segments(segs, source_lang="fr", target_lang="fr")
        self.assertEqual(res[0].text, "Bonjour le monde")

    def test_translation_en_to_fr(self):
        segs = [
            SubtitleSegment(index=1, start=0.0, end=2.0, text="The Omnitrix shall be mine."),
            SubtitleSegment(index=2, start=2.5, end=4.0, text="Look at that shooting star!"),
        ]
        res = self.translator.translate_segments(segs, source_lang="en", target_lang="fr")
        self.assertEqual(len(res), 2)
        self.assertIn("Omnitrix", res[0].text)
        # Vérifie que la traduction en français a bien eu lieu
        self.assertTrue("sera" in res[0].text or "est" in res[0].text or "mien" in res[0].text or "moi" in res[0].text)


if __name__ == "__main__":
    unittest.main()
