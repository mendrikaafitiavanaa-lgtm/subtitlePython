"""Tests unitaires pour le moteur de correction floue et phonétique."""

import unittest

from src.services.fuzzy_corrector import (
    FuzzyKnowledgeCorrector,
    fuzzy_similarity_ratio,
    phonetic_hash,
)


class TestFuzzyCorrector(unittest.TestCase):
    def setUp(self):
        self.corrector_en = FuzzyKnowledgeCorrector(default_lang="en")
        self.corrector_fr = FuzzyKnowledgeCorrector(default_lang="fr")

    def test_fuzzy_similarity(self):
        self.assertGreaterEqual(fuzzy_similarity_ratio("omnitrix", "omitrix"), 0.85)
        self.assertGreaterEqual(fuzzy_similarity_ratio("tennyson", "tenyson"), 0.85)
        self.assertGreaterEqual(fuzzy_similarity_ratio("briquette", "briquet"), 0.80)

    def test_phonetic_hash(self):
        self.assertEqual(phonetic_hash("phone", "en"), phonetic_hash("fone", "en"))
        self.assertEqual(phonetic_hash("cater", "en"), phonetic_hash("kater", "en"))

    def test_ben10_corrections_en(self):
        samples = [
            ("the neatrix is powerful", "the Omnitrix is powerful"),
            ("we need the omitrix", "we need the Omnitrix"),
            ("smoke sheep stung in fridge", "smoked sheep's tongue in fridge"),
            ("take it easy is he to be but", "take it easy take it easy dweeb"),
            ("this was hardchains", "this was hard candy"),
            ("let us a lasttheworld", "let us them last the whole"),
            ("look at that building star", "look at that shooting star"),
            ("it was and full camp are out there", "it was darn fool camper out there"),
            ("it hurts a wrath mitts", "Two words: breath mints"),
            ("stay with my mikey because with cousin", "stay with my geekazoid cousin"),
            ("i'd watched i'm done with on wrist", "that watch clamped on on wrist"),
            ("the costs a constantmay my life", "the costs costs me my life"),
            ("the battle beyond their trips", "the battle the Omnitrix"),
            ("they are barefoot in woods", "they are bear food in woods"),
            ("super cooly alien dudes", "super-cool alien dudes"),
            ("they had meal worms for dinner", "they had mealworms for dinner"),
        ]
        for src, expected in samples:
            res = self.corrector_en.correct_text(src, lang="en")
            self.assertEqual(res, expected, f"Failed on: {src} -> Got: {res}")

    def test_no_false_positives_on_gonna(self):
        # Vérification critique : 'gonna' ne doit JAMAIS devenir 'Gwen'
        text = "I am gonna get so busted for this because we are gonna leave"
        res = self.corrector_en.correct_text(text, lang="en")
        self.assertEqual(res, text)
        self.assertNotIn("Gwen", res)

        text_gwen = "Hey Gwen look at Ben"
        res_gwen = self.corrector_en.correct_text(text_gwen, lang="en")
        self.assertEqual(res_gwen, "Hey Gwen look at Ben")

    def test_ben10_corrections_fr(self):
        samples = [
            ("bonjour Jean-Jonette comment vas-tu", "bonjour Gwen comment vas-tu"),
            ("voici Minus avec la montre", "voici Ben avec la montre"),
            ("il cherche la matrix", "il cherche l'Omnitrix"),
            ("il mange des asticot mariné", "il mange des asticots marinés"),
            ("voici grand pere avec nous", "voici grand-père avec nous"),
        ]
        for src, expected in samples:
            res = self.corrector_fr.correct_text(src, lang="fr")
            self.assertEqual(res, expected, f"Failed on FR: {src} -> Got: {res}")

    def test_initial_prompt(self):
        prompt_en = self.corrector_en.get_initial_prompt("en")
        self.assertIn("Ben Tennyson", prompt_en)
        self.assertIn("Omnitrix", prompt_en)

        prompt_fr = self.corrector_fr.get_initial_prompt("fr")
        self.assertIn("Grand-père Max", prompt_fr)
        self.assertIn("Omnitrix", prompt_fr)


if __name__ == "__main__":
    unittest.main()
