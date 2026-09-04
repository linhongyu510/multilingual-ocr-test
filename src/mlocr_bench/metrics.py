"""Text-recognition metrics: CER, WER, accuracy.

Design notes
------------
The metrics here deliberately separate *character* level and *word* level
edit distance. A previous implementation computed "WER" by running a
character-level edit distance over whitespace-joined tokens, which makes WER
mathematically identical to CER for any input and therefore useless as an
independent signal.

For scripts that do not use whitespace to delimit words (Chinese, Japanese,
Thai, Khmer, Lao, Burmese, ...) whitespace tokenisation is not meaningful. For
those languages ``wer`` returns ``None`` rather than a misleading number; use
``cer`` instead. Call sites must treat ``None`` as "not applicable" and exclude
it from aggregates instead of coercing it to 0 or 100.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, asdict
from typing import Iterable, Sequence

__all__ = [
    "SPACELESS_SCRIPTS",
    "levenshtein",
    "normalize_text",
    "cer",
    "wer",
    "accuracy_from_cer",
    "SampleMetrics",
    "score_sample",
]

#: Languages whose orthography does not delimit words with spaces. WER is not
#: reported for these; CER is the meaningful metric.
SPACELESS_SCRIPTS: frozenset[str] = frozenset(
    {"zh", "zh-Hant", "zh-Hans", "ja", "th", "km", "lo", "my", "bo", "dz"}
)


def levenshtein(a: Sequence[object], b: Sequence[object]) -> int:
    """Edit distance between two sequences (substitution/insert/delete = 1).

    Works on any sequence of comparable items, so it serves both the character
    level (``str``) and the word level (``list[str]``) without a native
    dependency. Uses two rolling rows: O(min(len)) memory.
    """
    if a == b:
        return 0
    if len(a) < len(b):  # keep the inner loop over the shorter sequence
        a, b = b, a
    if not b:
        return len(a)

    previous = list(range(len(b) + 1))
    current = [0] * (len(b) + 1)
    for i, ca in enumerate(a, start=1):
        current[0] = i
        for j, cb in enumerate(b, start=1):
            current[j] = min(
                previous[j] + 1,          # deletion
                current[j - 1] + 1,       # insertion
                previous[j - 1] + (ca != cb),  # substitution
            )
        previous, current = current, previous
    return previous[len(b)]


def normalize_text(
    text: str,
    *,
    form: str = "NFKC",
    collapse_whitespace: bool = True,
    casefold: bool = False,
) -> str:
    """Normalise text prior to scoring.

    Unicode normalisation matters for Indic and Arabic scripts, where the same
    grapheme may be encoded as either a precomposed codepoint or a base plus
    combining marks. Without it, a visually identical prediction can be counted
    as an error and accuracy is understated.
    """
    out = unicodedata.normalize(form, text)
    if collapse_whitespace:
        out = " ".join(out.split())
    else:
        out = out.strip()
    if casefold:
        out = out.casefold()
    return out


def cer(reference: str, hypothesis: str, *, clamp: bool = True) -> float:
    """Character error rate, in percent.

    ``CER = edit_distance(ref, hyp) / len(ref) * 100``

    With an empty reference the rate is undefined; by convention this returns
    0.0 for an empty hypothesis and 100.0 otherwise.

    ``clamp`` caps the result at 100. Capping loses information when the
    hypothesis is much longer than the reference (heavy hallucination), so pass
    ``clamp=False`` when diagnosing over-generation.
    """
    if not reference:
        return 0.0 if not hypothesis else 100.0
    rate = levenshtein(reference, hypothesis) / len(reference) * 100.0
    return min(rate, 100.0) if clamp else rate


def wer(
    reference: str,
    hypothesis: str,
    *,
    language: str | None = None,
    clamp: bool = True,
) -> float | None:
    """Word error rate, in percent — a genuine *word* level edit distance.

    Returns ``None`` when word segmentation is not meaningful for ``language``
    (see :data:`SPACELESS_SCRIPTS`) so that callers do not mistake an
    inapplicable metric for a perfect or failing score.
    """
    if language is not None and language in SPACELESS_SCRIPTS:
        return None

    ref_words = reference.split()
    hyp_words = hypothesis.split()
    if not ref_words:
        return 0.0 if not hyp_words else 100.0

    # Single-token reference in an unknown script: whitespace told us nothing,
    # so WER would just be a coarse 0/100 flag. Report it as inapplicable.
    if language is None and len(ref_words) == 1 and len(reference) > 8:
        return None

    rate = levenshtein(ref_words, hyp_words) / len(ref_words) * 100.0
    return min(rate, 100.0) if clamp else rate


def accuracy_from_cer(cer_percent: float) -> float:
    """Character accuracy in percent, floored at 0."""
    return max(0.0, 100.0 - cer_percent)


@dataclass(frozen=True)
class SampleMetrics:
    """Metrics for a single reference/hypothesis pair."""

    cer: float
    accuracy: float
    wer: float | None
    ref_chars: int
    hyp_chars: int

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def score_sample(
    reference: str,
    hypothesis: str,
    *,
    language: str | None = None,
    normalize: bool = True,
) -> SampleMetrics:
    """Score one prediction against its ground truth."""
    if normalize:
        reference = normalize_text(reference)
        hypothesis = normalize_text(hypothesis)
    c = cer(reference, hypothesis)
    return SampleMetrics(
        cer=c,
        accuracy=accuracy_from_cer(c),
        wer=wer(reference, hypothesis, language=language),
        ref_chars=len(reference),
        hyp_chars=len(hypothesis),
    )


def mean(values: Iterable[float | None]) -> float | None:
    """Mean that ignores ``None`` (inapplicable) entries."""
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    return sum(vals) / len(vals)
