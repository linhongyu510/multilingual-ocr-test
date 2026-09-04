"""Dataset quality validation.

The benchmark is only as trustworthy as its rendered images. A synthetic
multilingual corpus fails in ways that are invisible to a text-only check: if
the font used at generation time lacks glyphs for a script, the renderer
substitutes ``.notdef`` — the hollow rectangle commonly called *tofu*. The
ground-truth ``.txt`` still contains perfectly good text, so every text-level
check passes, yet the image carries no readable script at all.

An OCR engine scored against such images reports ~0% accuracy, which is easily
misread as an engine defect when the real fault is in the data. This module
detects that class of failure so data problems and model problems can be told
apart.

Checks
------
``tofu``            fraction of glyph blobs that are hollow ``.notdef`` boxes
``blank``           images with (almost) no ink
``clipped``         ink touching the canvas edge, i.e. text cut off
``geometry``        inconsistent image dimensions within/across languages
``ground_truth``    missing/empty ``.txt``, duplicate texts

Requires Pillow and numpy; both are declared as install dependencies.
"""

from __future__ import annotations

import collections
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image

from .dataset import Sample, group_by_language

__all__ = ["ImageQuality", "LanguageQuality", "inspect_image", "validate_dataset"]

#: Ink threshold on an 8-bit grayscale image.
_INK_THRESHOLD = 128
#: An image counts as blank only when it has almost no ink in absolute terms.
#: A *fraction* alone is size-dependent — the same line of text on a larger
#: canvas has a smaller ink fraction — so short-but-valid samples on a big
#: canvas would be misreported as blank. Both conditions must hold.
_BLANK_INK_PIXELS = 40
_BLANK_INK_FRACTION = 0.0002
#: A glyph blob counts as tofu when its border is essentially solid ...
_TOFU_BORDER_MIN = 0.90
#: ... and its interior essentially empty.
_TOFU_INTERIOR_MAX = 0.02
#: A language is flagged BROKEN above this tofu fraction.
TOFU_BROKEN_THRESHOLD = 50.0
#: ... and SUSPECT above this one.
TOFU_SUSPECT_THRESHOLD = 5.0


@dataclass
class ImageQuality:
    """Per-image findings."""

    path: Path
    width: int
    height: int
    ink_fraction: float
    glyph_blobs: int
    tofu_blobs: int
    is_blank: bool
    is_clipped: bool

    @property
    def tofu_ratio(self) -> float:
        return self.tofu_blobs / self.glyph_blobs * 100.0 if self.glyph_blobs else 0.0


@dataclass
class LanguageQuality:
    """Aggregated findings for one language."""

    language: str
    images: int = 0
    glyph_blobs: int = 0
    tofu_blobs: int = 0
    images_with_tofu: int = 0
    blank_images: int = 0
    clipped_images: int = 0
    sizes: collections.Counter = field(default_factory=collections.Counter)
    duplicate_texts: int = 0
    empty_texts: int = 0

    @property
    def tofu_ratio(self) -> float:
        return self.tofu_blobs / self.glyph_blobs * 100.0 if self.glyph_blobs else 0.0

    @property
    def verdict(self) -> str:
        """``broken`` / ``suspect`` / ``ok`` — usability of this language's images."""
        if self.images and self.blank_images == self.images:
            return "broken"
        if self.tofu_ratio > TOFU_BROKEN_THRESHOLD:
            return "broken"
        if self.tofu_ratio > TOFU_SUSPECT_THRESHOLD or self.clipped_images or self.blank_images:
            return "suspect"
        return "ok"

    @property
    def note(self) -> str:
        notes: list[str] = []
        if self.tofu_ratio > TOFU_SUSPECT_THRESHOLD:
            notes.append(
                f"{self.tofu_ratio:.0f}% of glyphs render as .notdef boxes "
                f"({self.images_with_tofu}/{self.images} images) — generation font "
                f"lacks this script"
            )
        if self.blank_images:
            notes.append(f"{self.blank_images} blank image(s)")
        if self.clipped_images:
            notes.append(f"{self.clipped_images} image(s) with text touching the canvas edge")
        if len(self.sizes) > 1:
            dims = ", ".join(f"{w}x{h}(x{n})" for (w, h), n in self.sizes.most_common())
            notes.append(f"inconsistent image sizes: {dims}")
        if self.duplicate_texts:
            notes.append(f"{self.duplicate_texts} duplicate ground-truth text(s)")
        if self.empty_texts:
            notes.append(f"{self.empty_texts} empty ground-truth text(s)")
        return "; ".join(notes) or "no issues detected"

    def as_dict(self) -> dict[str, object]:
        return {
            "language": self.language,
            "images": self.images,
            "glyph_blobs": self.glyph_blobs,
            "tofu_blobs": self.tofu_blobs,
            "tofu_ratio_percent": round(self.tofu_ratio, 2),
            "images_with_tofu": self.images_with_tofu,
            "blank_images": self.blank_images,
            "clipped_images": self.clipped_images,
            "image_sizes": {f"{w}x{h}": n for (w, h), n in sorted(self.sizes.items())},
            "duplicate_texts": self.duplicate_texts,
            "empty_texts": self.empty_texts,
            "verdict": self.verdict,
            "note": self.note,
        }


def _segment_blobs(band: np.ndarray, min_width: int = 8) -> list[tuple[int, int]]:
    """Split an ink band into candidate glyph blobs on empty columns."""
    column_has_ink = band.any(axis=0)
    blobs: list[tuple[int, int]] = []
    start: int | None = None
    for index, has_ink in enumerate(column_has_ink):
        if has_ink and start is None:
            start = index
        elif not has_ink and start is not None:
            blobs.append((start, index))
            start = None
    if start is not None:
        blobs.append((start, len(column_has_ink)))
    return [(a, b) for a, b in blobs if b - a >= min_width]


def _is_tofu(glyph: np.ndarray) -> bool:
    """True when a blob looks like a hollow ``.notdef`` rectangle.

    ``.notdef`` is drawn as a rectangular outline: a solid border enclosing an
    empty centre. The stroke width varies with font and point size (3px, 4px,
    ...), and guessing it from the blob size is unreliable — overestimating by
    one pixel pulls empty interior into the "border" sample and sinks its mean
    below the threshold, silently missing broken glyphs. So each plausible
    stroke width is tried and the blob counts as tofu if any of them yields a
    solid ring around an empty centre.
    """
    height, width = glyph.shape
    if height < 12 or width < 8:
        return False

    max_stroke = max(2, round(min(height, width) * 0.2))
    for stroke in range(2, max_stroke + 1):
        if height <= 2 * (stroke + 1) or width <= 2 * (stroke + 1):
            break
        ring = np.concatenate(
            [
                glyph[:stroke, :].ravel(),
                glyph[-stroke:, :].ravel(),
                glyph[:, :stroke].ravel(),
                glyph[:, -stroke:].ravel(),
            ]
        )
        interior = glyph[stroke + 1 : -(stroke + 1), stroke + 1 : -(stroke + 1)]
        if interior.size == 0:
            continue
        if ring.mean() > _TOFU_BORDER_MIN and interior.mean() < _TOFU_INTERIOR_MAX:
            return True
    return False


def inspect_image(path: str | Path) -> ImageQuality:
    """Analyse a single rendered sample image."""
    path = Path(path)
    with Image.open(path) as handle:
        gray = np.asarray(handle.convert("L"))
    height, width = gray.shape
    ink = gray < _INK_THRESHOLD
    ink_pixels = int(ink.sum())
    ink_fraction = float(ink.mean())

    if not ink.any():
        return ImageQuality(path, width, height, 0.0, 0, 0, True, False)

    rows = np.where(ink.any(axis=1))[0]
    band = ink[rows.min() : rows.max() + 1, :]

    tofu = 0
    blobs = _segment_blobs(band)
    for x0, x1 in blobs:
        glyph = band[:, x0:x1]
        glyph_rows = np.where(glyph.any(axis=1))[0]
        glyph = glyph[glyph_rows.min() : glyph_rows.max() + 1]
        if _is_tofu(glyph):
            tofu += 1

    clipped = bool(ink[0, :].any() or ink[-1, :].any() or ink[:, 0].any() or ink[:, -1].any())

    return ImageQuality(
        path=path,
        width=width,
        height=height,
        ink_fraction=ink_fraction,
        glyph_blobs=len(blobs),
        tofu_blobs=tofu,
        is_blank=ink_pixels < _BLANK_INK_PIXELS and ink_fraction < _BLANK_INK_FRACTION,
        is_clipped=clipped,
    )


def validate_dataset(samples: Iterable[Sample]) -> dict[str, LanguageQuality]:
    """Validate every sample, aggregated per language."""
    results: dict[str, LanguageQuality] = {}
    for language, group in group_by_language(list(samples)).items():
        quality = LanguageQuality(language=language)
        texts: list[str] = []
        for sample in group:
            findings = inspect_image(sample.image_path)
            quality.images += 1
            quality.glyph_blobs += findings.glyph_blobs
            quality.tofu_blobs += findings.tofu_blobs
            if findings.tofu_blobs:
                quality.images_with_tofu += 1
            if findings.is_blank:
                quality.blank_images += 1
            if findings.is_clipped:
                quality.clipped_images += 1
            quality.sizes[(findings.width, findings.height)] += 1

            if sample.is_empty:
                quality.empty_texts += 1
            else:
                texts.append(sample.ground_truth)

        counter = collections.Counter(texts)
        quality.duplicate_texts = sum(n - 1 for n in counter.values() if n > 1)
        results[language] = quality
    return dict(sorted(results.items()))


def unusable_languages(report: dict[str, LanguageQuality]) -> list[str]:
    """Languages whose images cannot support a fair OCR score."""
    return [lang for lang, q in report.items() if q.verdict == "broken"]
