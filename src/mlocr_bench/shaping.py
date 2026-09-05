#!/usr/bin/env python3
"""Render text with real complex-script shaping.

Why this exists
---------------
``PIL.ImageDraw.text`` only shapes text when Pillow was built against libraqm.
The Pillow build available here reports ``features.check("raqm") is False``, so
it advances the pen by each character's own width and never applies mark
positioning. For scripts with combining marks that places tone marks and vowel
signs *beside* the base letter instead of above or below it. Lao rendered that
way is unreadable even though every glyph exists in the font — swapping fonts
does not help, because the defect is in layout, not coverage.

So shaping is done explicitly:

1. **HarfBuzz** (``uharfbuzz``) maps characters to glyph ids and computes each
   glyph's advance and offset — the same engine browsers and the OS use. A
   combining mark comes back with ``x_advance == 0``, meaning it stacks onto the
   preceding base rather than following it.
2. **FreeType** (``freetype-py``) rasterises each glyph *by glyph id*, which PIL
   cannot do. Its negative ``bitmap_left`` for marks is what pulls them back
   over their base.

:func:`shaping_available` reports whether this path is usable, so callers can
refuse to emit malformed images instead of silently producing them.
"""

from __future__ import annotations

import functools
from pathlib import Path

import numpy as np
from PIL import Image

try:
    import uharfbuzz as hb

    HAVE_UHARFBUZZ = True
except ModuleNotFoundError:  # pragma: no cover
    HAVE_UHARFBUZZ = False

try:
    import freetype

    HAVE_FREETYPE = True
except ModuleNotFoundError:  # pragma: no cover
    HAVE_FREETYPE = False

__all__ = [
    "SHAPING_REQUIRED_SCRIPTS",
    "draw_shaped_text",
    "measure_shaped",
    "needs_shaping",
    "shaped_line_metrics",
    "shaping_available",
]

#: Languages whose scripts use combining marks, reordering or contextual
#: joining that a shaping engine must resolve. Rendering these without shaping
#: yields images that look like text but are typographically wrong.
SHAPING_REQUIRED_SCRIPTS: frozenset[str] = frozenset(
    {
        "lo",  # Lao: tone marks / vowel signs above and below the base
        "th",  # Thai: same structure
        "km",  # Khmer: subscript consonants
        "my",  # Myanmar: stacked medials
        "hi",  # Devanagari: conjuncts and matras
        "ne",  # Devanagari
        "bn",  # Bengali
        "ta",  # Tamil
        "te",  # Telugu
        "kn",  # Kannada
        "ml",  # Malayalam
        "si",  # Sinhala
        "ur",  # Urdu: Arabic contextual joining, right-to-left
        "ug",  # Uyghur: Arabic script
    }
)


def shaping_available() -> bool:
    """True when shaped rendering can actually be performed."""
    return HAVE_UHARFBUZZ and HAVE_FREETYPE


def missing_shaping_deps() -> list[str]:
    missing = []
    if not HAVE_UHARFBUZZ:
        missing.append("uharfbuzz")
    if not HAVE_FREETYPE:
        missing.append("freetype-py")
    return missing


def needs_shaping(language: str) -> bool:
    return language in SHAPING_REQUIRED_SCRIPTS


@functools.lru_cache(maxsize=32)
def _hb_font(font_path: str, size_px: int) -> "hb.Font":
    blob = hb.Blob.from_file_path(font_path)
    face = hb.Face(blob)
    font = hb.Font(face)
    font.scale = (size_px * 64, size_px * 64)
    return font


@functools.lru_cache(maxsize=32)
def _ft_face(font_path: str, size_px: int) -> "freetype.Face":
    face = freetype.Face(font_path)
    face.set_char_size(size_px * 64)
    return face


def _require() -> None:
    if not shaping_available():
        raise RuntimeError(
            "shaped rendering needs: " + ", ".join(missing_shaping_deps()) + " (pip install them)"
        )


def _shape(text: str, font_path: str, size_px: int) -> list[tuple[int, float, float]]:
    """Return ``(glyph_id, pen_x, pen_y)`` in pixels for each shaped glyph."""
    font = _hb_font(font_path, size_px)
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(font, buf)

    out: list[tuple[int, float, float]] = []
    pen_x = pen_y = 0.0
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        out.append((info.codepoint, (pen_x + pos.x_offset) / 64.0, (pen_y + pos.y_offset) / 64.0))
        pen_x += pos.x_advance
        pen_y += pos.y_advance
    return out


def measure_shaped(text: str, font_path: str | Path, size_px: int) -> float:
    """Advance width of ``text`` in pixels after shaping."""
    _require()
    font = _hb_font(str(font_path), size_px)
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(font, buf)
    return sum(p.x_advance for p in buf.glyph_positions) / 64.0


def shaped_line_metrics(font_path: str | Path, size_px: int) -> tuple[int, int]:
    """``(ascender, descender)`` in pixels for the font at this size."""
    _require()
    face = _ft_face(str(font_path), size_px)
    ascender = int(face.size.ascender / 64.0)
    descender = int(abs(face.size.descender) / 64.0)
    return ascender, descender


def draw_shaped_text(
    image: Image.Image,
    xy: tuple[float, float],
    text: str,
    font_path: str | Path,
    size_px: int,
    fill: int = 0,
) -> None:
    """Draw ``text`` onto a mode-``L`` ``image`` with ``xy`` as (left, baseline).

    Glyphs are rasterised by glyph id at HarfBuzz's computed positions, so
    combining marks land on their base letter. Anti-aliased coverage is
    alpha-composited so overlapping marks do not erase the base glyph.
    """
    _require()
    if image.mode != "L":
        raise ValueError(f"expected mode 'L' image, got {image.mode!r}")

    font_path = str(font_path)
    face = _ft_face(font_path, size_px)
    canvas = np.asarray(image).astype(np.float32)
    height, width = canvas.shape
    left, baseline = xy

    for glyph_id, dx, dy in _shape(text, font_path, size_px):
        face.load_glyph(glyph_id, freetype.FT_LOAD_RENDER)
        bitmap = face.glyph.bitmap
        rows, cols = bitmap.rows, bitmap.width
        if rows == 0 or cols == 0:
            continue

        coverage = np.array(bitmap.buffer, dtype=np.uint8).reshape(rows, bitmap.pitch)[:, :cols]
        # bitmap_left is negative for combining marks; that is what pulls them
        # back over the base glyph rather than beside it.
        x0 = int(round(left + dx + face.glyph.bitmap_left))
        y0 = int(round(baseline - dy - face.glyph.bitmap_top))

        sx0, sy0 = max(0, -x0), max(0, -y0)
        x1, y1 = min(width, x0 + cols), min(height, y0 + rows)
        x0c, y0c = max(0, x0), max(0, y0)
        if x1 <= x0c or y1 <= y0c:
            continue

        patch = coverage[sy0 : sy0 + (y1 - y0c), sx0 : sx0 + (x1 - x0c)].astype(np.float32) / 255.0
        target = canvas[y0c:y1, x0c:x1]
        canvas[y0c:y1, x0c:x1] = target * (1.0 - patch) + float(fill) * patch

    image.paste(Image.fromarray(np.clip(canvas, 0, 255).astype(np.uint8), mode="L"), (0, 0))
