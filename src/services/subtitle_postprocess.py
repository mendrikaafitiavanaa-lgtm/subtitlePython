"""Post-traitement des sous-titres pour atteindre une qualité proche des sites de sous-titres.

Étapes :
1. Découpage des segments Whisper en sous-titres courts (via les timestamps par mot).
2. Filtrage des hallucinations classiques de Whisper.
3. Suppression des répétitions consécutives (boucles).
4. Retour à la ligne équilibré (2 lignes max, ~42 caractères par ligne).
5. Correction des durées (min / max) et des chevauchements.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

from src.core.models import SubtitleSegment
from src.services.fuzzy_corrector import FuzzyKnowledgeCorrector

# --- Règles de style (standards Netflix / sites de sous-titres) ---
MAX_CHARS_PER_LINE = 42
MAX_LINES = 2
MAX_DURATION = 6.0       # secondes
MIN_DURATION = 1.0       # secondes
MIN_GAP = 0.08           # secondes entre deux sous-titres
MAX_WORD_GAP = 0.8       # pause entre deux mots qui force une coupure
MAX_CPS = 20.0           # caractères par seconde (confort de lecture)

_SENTENCE_END = (".", "!", "?", "…", "。", "！", "？")
_CLAUSE_END = (",", ";", ":", "，", "、")

# Phrases que Whisper invente quand il n'y a pas de parole (musique, silence, générique).
_HALLUCINATION_PATTERNS = [
    r"thanks? for watching",
    r"thank you for watching",
    r"see you in the next (video|one|episode)",
    r"see you (next time|soon)!?$",
    r"(please )?(like|subscribe)",
    r"don'?t forget to (like|subscribe)",
    r"subtitles? (by|made by|created by)",
    r"subtitled by",
    r"amara\.org",
    r"www\.[a-z0-9\-]+\.[a-z]{2,}",
    r"merci d'avoir regard",
    r"sous-titr(es|age)\s+(réalisés|realises|par|st'|fait)",
    r"abonne(z|-vous)",
    r"^\W*you\W*$",
    r"^\W*bye\W*$",
    r"^[\W_]*$",  # uniquement de la ponctuation
]
_HALLUCINATION_RE = [re.compile(p, re.IGNORECASE) for p in _HALLUCINATION_PATTERNS]


@dataclass
class Word:
    start: float
    end: float
    text: str


@dataclass
class RawSegment:
    """Segment brut issu de Whisper (avec ou sans mots)."""
    start: float
    end: float
    text: str
    words: list[Word] | None = None
    avg_logprob: float | None = None
    no_speech_prob: float | None = None
    compression_ratio: float | None = None


# ----------------------------------------------------------------------------
# Utilitaires
# ----------------------------------------------------------------------------

def _normalize(text: str) -> str:
    return re.sub(r"[^\w\s]", "", text.lower()).strip()


def is_hallucination(seg: RawSegment) -> bool:
    """Détecte un segment très probablement inventé par Whisper."""
    text = (seg.text or "").strip()
    if not text:
        return True

    # Signaux statistiques fournis par faster-whisper
    if seg.no_speech_prob is not None and seg.avg_logprob is not None:
        if seg.no_speech_prob > 0.6 and seg.avg_logprob < -1.0:
            return True
    if seg.compression_ratio is not None and seg.compression_ratio > 2.4:
        return True

    # Phrases-types d'hallucination
    for rx in _HALLUCINATION_RE:
        if rx.search(text):
            return True
    return False


def wrap_text(text: str, max_chars: int = MAX_CHARS_PER_LINE, max_lines: int = MAX_LINES) -> str:
    """Coupe un texte en lignes équilibrées (comme les sous-titres professionnels)."""
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_chars:
        return text

    # On cherche le meilleur espace proche du milieu (préférence après une ponctuation).
    middle = len(text) / 2
    best_idx, best_score = -1, float("inf")
    for i, ch in enumerate(text):
        if ch != " ":
            continue
        left, right = text[:i], text[i + 1:]
        if len(left) > max_chars or len(right) > max_chars:
            continue
        score = abs(i - middle)
        if left.endswith(_CLAUSE_END + _SENTENCE_END):
            score -= 6
        if score < best_score:
            best_idx, best_score = i, score

    if best_idx == -1:
        # Aucune coupure ne respecte la limite : on coupe au plus proche du milieu.
        spaces = [i for i, c in enumerate(text) if c == " "]
        if not spaces:
            return text
        best_idx = min(spaces, key=lambda i: abs(i - middle))

    return text[:best_idx] + "\n" + text[best_idx + 1:]


# ----------------------------------------------------------------------------
# Découpage
# ----------------------------------------------------------------------------

def _split_with_words(seg: RawSegment) -> list[tuple[float, float, str]]:
    """Découpe un segment en sous-titres courts grâce aux timestamps des mots."""
    max_chars = MAX_CHARS_PER_LINE * MAX_LINES
    chunks: list[tuple[float, float, str]] = []
    current: list[Word] = []

    def flush() -> None:
        nonlocal current
        if not current:
            return
        text = "".join(w.text for w in current).strip()
        if text:
            chunks.append((current[0].start, current[-1].end, text))
        current = []

    for word in seg.words or []:
        if not word.text.strip():
            continue
        if current:
            gap = word.start - current[-1].end
            cur_text = "".join(w.text for w in current).strip()
            would_be = len(cur_text) + len(word.text)
            duration = word.end - current[0].start
            ends_sentence = cur_text.endswith(_SENTENCE_END)

            if (
                gap > MAX_WORD_GAP
                or would_be > max_chars
                or duration > MAX_DURATION
                or (ends_sentence and len(cur_text) >= 18)
                or (cur_text.endswith(_CLAUSE_END) and len(cur_text) >= max_chars * 0.6)
            ):
                flush()
        current.append(word)
    flush()
    return chunks


def _split_without_words(seg: RawSegment) -> list[tuple[float, float, str]]:
    """Découpe de secours par phrases, avec temps proportionnel à la longueur."""
    text = re.sub(r"\s+", " ", seg.text).strip()
    max_chars = MAX_CHARS_PER_LINE * MAX_LINES
    duration = max(seg.end - seg.start, 0.01)

    if len(text) <= max_chars and duration <= MAX_DURATION:
        return [(seg.start, seg.end, text)]

    # Phrases, puis regroupement tant que ça rentre
    sentences = re.split(r"(?<=[.!?…])\s+", text)
    pieces: list[str] = []
    buf = ""
    for s in sentences:
        if buf and len(buf) + 1 + len(s) > max_chars:
            pieces.append(buf)
            buf = s
        else:
            buf = f"{buf} {s}".strip()
    if buf:
        pieces.append(buf)

    # Une phrase seule trop longue : coupe en mots
    final: list[str] = []
    for p in pieces:
        while len(p) > max_chars:
            cut = p.rfind(" ", 0, max_chars)
            cut = cut if cut > 0 else max_chars
            final.append(p[:cut].strip())
            p = p[cut:].strip()
        if p:
            final.append(p)

    total = sum(len(p) for p in final) or 1
    out: list[tuple[float, float, str]] = []
    t = seg.start
    for p in final:
        share = duration * len(p) / total
        out.append((t, t + share, p))
        t += share
    return out


# ----------------------------------------------------------------------------
# Pipeline principal
# ----------------------------------------------------------------------------

def postprocess_segments(
    raw_segments: list[RawSegment],
    corrector: FuzzyKnowledgeCorrector | None = None,
    lang: str = "en",
) -> list[SubtitleSegment]:
    """Transforme les segments bruts de Whisper en sous-titres propres avec correction phonétique et floue."""
    pieces: list[tuple[float, float, str]] = []
    active_corrector = corrector or FuzzyKnowledgeCorrector(default_lang=lang)

    for seg in raw_segments:
        if is_hallucination(seg):
            continue
        parts = _split_with_words(seg) if seg.words else _split_without_words(seg)
        for start, end, text in parts:
            clean_text = text.strip()
            if clean_text:
                # Correction phonétique, logique floue et dictionnaire de connaissances
                corrected_text = active_corrector.correct_text(clean_text, lang=lang)
                if corrected_text.strip():
                    pieces.append((start, end, corrected_text.strip()))

    pieces.sort(key=lambda p: p[0])

    # Suppression des répétitions consécutives (boucle Whisper) et des hallucinations restantes
    deduped: list[tuple[float, float, str]] = []
    for start, end, text in pieces:
        norm = _normalize(text)
        if not norm:
            continue
        if deduped and _normalize(deduped[-1][2]) == norm:
            # même phrase d'affilée : on garde la première
            continue
        deduped.append((start, end, text))

    # Si une même phrase revient plus de 3 fois dans tout le fichier alors qu'elle est
    # très courte, c'est presque toujours une boucle d'hallucination.
    counts: dict[str, int] = {}
    for _, _, text in deduped:
        n = _normalize(text)
        counts[n] = counts.get(n, 0) + 1
    deduped = [
        p for p in deduped
        if not (counts[_normalize(p[2])] > 4 and len(_normalize(p[2]).split()) >= 4)
    ]

    # Correction des durées / chevauchements
    result: list[SubtitleSegment] = []
    for i, (start, end, text) in enumerate(deduped):
        next_start = deduped[i + 1][0] if i + 1 < len(deduped) else float("inf")

        # durée minimale : on étire vers l'avant s'il y a de la place
        needed = max(MIN_DURATION, len(text) / MAX_CPS)
        if end - start < needed:
            end = min(start + needed, next_start - MIN_GAP)
        # pas de chevauchement
        if end > next_start - MIN_GAP:
            end = max(start + 0.3, next_start - MIN_GAP)
        # durée maximale
        if end - start > MAX_DURATION:
            end = start + MAX_DURATION
        if end <= start:
            end = start + 0.5

        result.append(
            SubtitleSegment(
                index=len(result) + 1,
                start=round(start, 3),
                end=round(end, 3),
                text=wrap_text(text),
            )
        )
    return result
