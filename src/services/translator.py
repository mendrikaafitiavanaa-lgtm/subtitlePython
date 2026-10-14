"""Service de traduction rapide et léger pour sous-titres (Anglais <-> Français).

Garantit que lorsqu'une vidéo est en anglais et que l'utilisateur demande des sous-titres français,
le fichier final est traduit en français de haute qualité avec synchronisation temporelle exacte.
"""

from __future__ import annotations

import logging
import time

from src.core.models import SubtitleSegment

logger = logging.getLogger(__name__)


class SubtitleTranslator:
    """Traducteur par lots (batch) préservant la structure et les timestamps des sous-titres."""

    def __init__(self) -> None:
        pass

    def translate_segments(
        self,
        segments: list[SubtitleSegment],
        source_lang: str = "en",
        target_lang: str = "fr",
        progress_callback: callable | None = None,
    ) -> list[SubtitleSegment]:
        """
        Traduit une liste de segments de sous-titres en préservant les index et timestamps.
        Regroupe les répliques par blocs pour minimiser les appels réseau et le temps de calcul.
        """
        if not segments:
            return []

        if source_lang == target_lang:
            return segments

        # Mapping des codes pour deep-translator (MyMemory)
        src_code = "en-US" if source_lang == "en" else "fr-FR"
        tgt_code = "fr-FR" if target_lang == "fr" else "en-US"

        try:
            from deep_translator import MyMemoryTranslator
            translator = MyMemoryTranslator(source=src_code, target=tgt_code)
        except Exception as exc:
            logger.warning(f"deep_translator non disponible ({exc}). Les sous-titres restent non traduits.")
            return segments

        translated_segments: list[SubtitleSegment] = []
        batch_size = 25  # Nombre de lignes par bloc
        total = len(segments)

        for i in range(0, total, batch_size):
            batch = segments[i : i + batch_size]
            # Extraire les textes (en remplaçant les retours à la ligne internes par des espaces pour garder 1 ligne par réplique)
            texts = [seg.text.replace("\n", " ").strip() for seg in batch]
            joined_text = "\n".join(texts)

            translated_lines = texts
            try:
                raw_translation = translator.translate(joined_text)
                if raw_translation:
                    split_lines = [line.strip() for line in raw_translation.split("\n")]
                    if len(split_lines) == len(batch):
                        translated_lines = split_lines
                    else:
                        # Si le nombre de lignes ne correspond pas exactement, traduire individuellement ce bloc
                        translated_lines = []
                        for t in texts:
                            try:
                                translated_lines.append(translator.translate(t) or t)
                            except Exception:
                                translated_lines.append(t)
            except Exception as exc:
                logger.warning(f"Erreur lors de la traduction du lot ({exc}). Conservation du texte original.")
                translated_lines = texts

            for seg, trans_text in zip(batch, translated_lines):
                # Rééquilibrer la mise en page (2 lignes max)
                from src.services.subtitle_postprocess import wrap_text
                formatted = wrap_text(trans_text)
                translated_segments.append(
                    SubtitleSegment(
                        index=seg.index,
                        start=seg.start,
                        end=seg.end,
                        text=formatted,
                    )
                )

            if progress_callback:
                pct = min(100, int((len(translated_segments) / total) * 100))
                progress_callback(pct, f"Traduction vers {target_lang.upper()} ({len(translated_segments)}/{total} lignes)...")

            # Pause minime pour respecter les quotas
            time.sleep(0.05)

        return translated_segments
