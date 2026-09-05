"""Font resolution with verified glyph coverage.

Why this module exists
----------------------
The three generators under ``data/generators/`` each pick fonts with their own
hardcoded ``if lang == ...`` ladder ending in ``ImageFont.load_default()``.
Languages absent from the ladder fall through to a font that does not cover
their script, and nothing checks the result. Mongolian was rendered with
``NotoSans-Regular.ttf`` (no Cyrillic in the shipped subset) and, failing that,
the PIL bitmap default — producing 30 images of ``.notdef`` boxes while the run
reported success.

The fix is to stop guessing. :func:`resolve_font` asks the font's own cmap
whether it actually maps the codepoints about to be drawn, and refuses to return
a font that does not. A missing script becomes a loud error at generation time
instead of a silent 0% OCR score weeks later.

Requires ``fontTools`` for cmap inspection: ``pip install fonttools``.
"""

from __future__ import annotations

import functools
from pathlib import Path

from PIL import ImageFont

try:
    from fontTools.ttLib import TTCollection, TTFont

    HAVE_FONTTOOLS = True
except ModuleNotFoundError:  # pragma: no cover
    HAVE_FONTTOOLS = False

__all__ = [
    "FontCoverageError",
    "font_covers",
    "resolve_font",
    "find_font_for_text",
    "search_dirs",
]


class FontCoverageError(RuntimeError):
    """No available font covers the requested text."""


#: Where fonts live on Linux CI images and on macOS workstations.
_SEARCH_DIRS = (
    "/usr/share/fonts",
    "/usr/local/share/fonts",
    "/Library/Fonts",
    "/System/Library/Fonts",
    "~/.fonts",
    "~/Library/Fonts",
)

#: Preferred font basenames per language, tried before a broad search.
#: Names only — the file is located wherever it happens to be installed, so the
#: table stays valid across distributions. Matching ignores spaces, case and
#: punctuation, so "LaoSangamMN" also finds "Lao Sangam MN.ttf".
#:
#: Order matters: a font dedicated to the script comes first, because a
#: pan-Unicode font may contain the glyphs yet not apply the script's shaping
#: rules. Lao rendered with Arial Unicode has correct letters but misplaced
#: tone marks, so a dedicated Lao font must win.
PREFERRED: dict[str, tuple[str, ...]] = {
    "zh": ("NotoSansCJKsc-Regular", "NotoSansCJK-Regular", "NotoSansSC-Regular", "PingFang", "Arial Unicode"),
    "zh-Hant": ("NotoSansCJKtc-Regular", "NotoSansCJK-Regular", "NotoSansTC-Regular", "PingFang", "Arial Unicode"),
    "ja": ("NotoSansCJKjp-Regular", "NotoSansCJK-Regular", "NotoSansJP-Regular", "Hiragino", "Arial Unicode"),
    "ko": ("NotoSansCJKkr-Regular", "NotoSansCJK-Regular", "NotoSansKR-Regular", "AppleGothic", "Arial Unicode"),
    "hi": ("NotoSansDevanagari-Regular", "DevanagariSangamMN", "Kohinoor", "Arial Unicode"),
    "ne": ("NotoSansDevanagari-Regular", "DevanagariSangamMN", "Kohinoor", "Arial Unicode"),
    "bn": ("NotoSansBengali-Regular", "BanglaSangamMN", "Bangla MN", "Arial Unicode"),
    "ta": ("NotoSansTamil-Regular", "TamilSangamMN", "Tamil MN", "Arial Unicode"),
    "te": ("NotoSansTelugu-Regular", "TeluguSangamMN", "Telugu MN", "Arial Unicode"),
    "kn": ("NotoSansKannada-Regular", "KannadaSangamMN", "Kannada MN", "Arial Unicode"),
    "ml": ("NotoSansMalayalam-Regular", "MalayalamSangamMN", "Malayalam MN", "Arial Unicode"),
    "si": ("NotoSansSinhala-Regular", "SinhalaSangamMN", "Sinhala MN", "Arial Unicode"),
    "ur": ("NotoNastaliqUrdu-Regular", "NotoSansArabic-Regular", "GeezaPro", "Arial Unicode"),
    "ug": ("NotoSansArabic-Regular", "GeezaPro", "Arial Unicode"),
    "th": ("NotoSansThai-Regular", "ThonburiMN", "Thonburi", "Arial Unicode"),
    "my": ("NotoSansMyanmar", "MyanmarSangamMN", "Myanmar MN", "Arial Unicode"),
    "km": ("NotoSansKhmer-Regular", "KhmerSangamMN", "Khmer MN", "Arial Unicode"),
    "lo": ("NotoSansLao-Regular", "NotoSansLaoLooped-Regular", "LaoSangamMN", "Lao MN", "Arial Unicode"),
    # Mongolian here is Cyrillic script, not the traditional vertical script.
    # This entry is the one whose absence produced the tofu images; note that
    # NotoSansMongolian would be wrong — it covers the vertical script only.
    "mn": ("NotoSans-Regular", "NotoSansCyrillic-Regular", "DejaVuSans", "Arial Unicode", "Helvetica"),
    "id": ("NotoSans-Regular", "DejaVuSans", "Arial Unicode", "Helvetica"),
    "ms": ("NotoSans-Regular", "DejaVuSans", "Arial Unicode", "Helvetica"),
    "vi": ("NotoSans-Regular", "DejaVuSans", "Arial Unicode", "Helvetica"),
    "tl": ("NotoSans-Regular", "DejaVuSans", "Arial Unicode", "Helvetica"),
}


def search_dirs() -> list[Path]:
    return [p for p in (Path(d).expanduser() for d in _SEARCH_DIRS) if p.is_dir()]


#: Fonts that *declare* wide cmap coverage but draw placeholder shapes rather
#: than real letterforms. macOS ``LastResort`` maps huge codepoint ranges and
#: renders a rounded box containing a question mark — the cmap says "covered",
#: the image says nothing. Because the placeholder has ink inside it, a hollow
#: box detector does not catch it either, so it must be excluded by name.
FALLBACK_FONT_STEMS: frozenset[str] = frozenset(
    {"lastresort", "adobeblank", "notdef", ".notdef", "unifont-upper"}
)


def _is_fallback_font(path: Path) -> bool:
    stem = path.stem.lower().replace(" ", "")
    return any(marker in stem for marker in FALLBACK_FONT_STEMS)


@functools.lru_cache(maxsize=1)
def _all_font_files() -> tuple[Path, ...]:
    found: list[Path] = []
    for directory in search_dirs():
        for pattern in ("*.ttf", "*.otf", "*.ttc"):
            found.extend(directory.rglob(pattern))
    # Placeholder fonts would satisfy every coverage check while rendering
    # nothing readable, so they are never candidates.
    return tuple(sorted(p for p in set(found) if not _is_fallback_font(p)))


@functools.lru_cache(maxsize=4096)
def _coverage(font_path: str) -> frozenset[int]:
    """Codepoints the font maps to a real glyph, read from its cmap."""
    if not HAVE_FONTTOOLS:
        raise RuntimeError("fontTools is required: pip install fonttools")
    path = Path(font_path)
    codepoints: set[int] = set()
    try:
        if path.suffix.lower() == ".ttc":
            collection = TTCollection(str(path), lazy=True)
            try:
                fonts = list(collection.fonts)
            finally:
                pass
            for font in fonts:
                try:
                    for table in font["cmap"].tables:
                        codepoints.update(table.cmap.keys())
                except Exception:
                    continue
            collection.close()
        else:
            font = TTFont(str(path), fontNumber=0, lazy=True)
            try:
                for table in font["cmap"].tables:
                    codepoints.update(table.cmap.keys())
            finally:
                font.close()
    except Exception:
        return frozenset()
    return frozenset(codepoints)


def missing_codepoints(text: str, font_path: str | Path) -> list[str]:
    """Characters of ``text`` the font cannot render (whitespace ignored)."""
    covered = _coverage(str(font_path))
    return [ch for ch in text if not ch.isspace() and ord(ch) not in covered]


def font_covers(text: str, font_path: str | Path) -> bool:
    return not missing_codepoints(text, font_path)


def _normalise_stem(name: str) -> str:
    """Collapse a font name for comparison.

    Installed filenames vary in spacing, case and separators for the same
    family — ``LaoSangamMN`` vs ``Lao Sangam MN.ttf`` vs ``lao-sangam-mn``.
    Comparing raw substrings silently misses the dedicated font and falls back
    to a pan-Unicode one, which is how Lao ended up rendered by a font that has
    the glyphs but does not shape the script.
    """
    return "".join(ch for ch in name.lower() if ch.isalnum())


def find_font_for_text(text: str, language: str | None = None) -> Path:
    """Locate an installed font that covers every character of ``text``.

    Preferred names for ``language`` are tried first for typographic quality;
    otherwise any installed font with full coverage is accepted. Raises
    :class:`FontCoverageError` when nothing covers the text — the loud failure
    that was missing.
    """
    all_fonts = _all_font_files()
    if not all_fonts:
        raise FontCoverageError(f"no font files found under: {', '.join(map(str, search_dirs()))}")

    if language and language in PREFERRED:
        for stem in PREFERRED[language]:
            wanted = _normalise_stem(stem)
            for candidate in all_fonts:
                if wanted in _normalise_stem(candidate.stem) and font_covers(text, candidate):
                    return candidate

    for candidate in all_fonts:
        if font_covers(text, candidate):
            return candidate

    sample = "".join(dict.fromkeys(missing_codepoints(text, all_fonts[0])))[:12]
    raise FontCoverageError(
        f"no installed font covers {language or 'this text'}; "
        f"missing glyphs for {sample!r}. "
        f"Install the matching Noto font (e.g. fonts-noto-core) and retry. "
        f"Rendering anyway would emit .notdef boxes and a misleading 0% OCR score."
    )


def resolve_font(
    text: str,
    language: str | None = None,
    size: int = 28,
    *,
    strict: bool = True,
) -> ImageFont.FreeTypeFont:
    """Return a PIL font that provably renders ``text``.

    Unlike the generators' original helpers this never falls back to
    ``ImageFont.load_default()``: with ``strict=True`` (the default) it raises
    instead, so a coverage gap stops the run rather than producing tofu images.
    """
    path = find_font_for_text(text, language)
    try:
        return ImageFont.truetype(str(path), size)
    except Exception as exc:
        if strict:
            raise FontCoverageError(f"font {path} covers the text but PIL failed to load it: {exc}") from exc
        return ImageFont.load_default()
