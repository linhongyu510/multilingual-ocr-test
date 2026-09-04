#!/usr/bin/env python3
"""Report which languages a font can actually render — before generating data.

Why this exists
---------------
The bundled corpus contains a language (``mn``, Mongolian Cyrillic) whose images
are 87% ``.notdef`` boxes. Tracing it back: the generator's font table has no
entry for ``mn``, its glyph self-test has no probe string for ``mn`` either, so
generation silently fell through to ``ImageFont.load_default()`` — a bitmap font
without Cyrillic — and wrote 30 unusable images while reporting success.

Run this before generating a dataset. It checks real glyph coverage via the
font's own cmap, so a missing script is caught at setup time instead of being
discovered later as a mysterious 0% OCR score.

Usage
-----
    python tools/check_font_coverage.py                     # probe common fonts
    python tools/check_font_coverage.py --font /path/to.ttf # check one font
    python tools/check_font_coverage.py --text "Сайн уу"    # check custom text
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from fontTools.ttLib import TTFont

    HAVE_FONTTOOLS = True
except ModuleNotFoundError:
    HAVE_FONTTOOLS = False

# One representative sample per language in the benchmark.
PROBES: dict[str, str] = {
    "zh": "你好世界",
    "zh-Hant": "你好世界",
    "ja": "こんにちは",
    "ko": "안녕하세요",
    "hi": "नमस्ते",
    "ne": "नमस्ते",
    "bn": "নমস্কার",
    "ta": "வணக்கம்",
    "te": "నమస్కారం",
    "kn": "ನಮಸ್ಕಾರ",
    "ml": "നമസ്കാരം",
    "si": "ආයුබෝවන්",
    "ur": "سلام",
    "ug": "سالام",
    "th": "สวัสดี",
    "my": "မင်္ဂလာပါ",
    "km": "សួស្តី",
    "lo": "ສະບາຍດີ",
    "mn": "Сайн уу",          # Cyrillic — the one that was missing
    "id": "Halo dunia",
    "ms": "Halo dunia",
    "vi": "Xin chào",
    "tl": "Kumusta",
}

# Common install locations across Linux/macOS.
FONT_SEARCH_DIRS = [
    "/usr/share/fonts",
    "/usr/local/share/fonts",
    "/Library/Fonts",
    "/System/Library/Fonts",
    str(Path.home() / ".fonts"),
    str(Path.home() / "Library/Fonts"),
]


def covered_codepoints(font_path: Path) -> set[int]:
    """Codepoints the font's cmap actually maps to a glyph."""
    if not HAVE_FONTTOOLS:
        raise RuntimeError("fontTools is required: pip install fonttools")
    codepoints: set[int] = set()
    font = TTFont(str(font_path), fontNumber=0, lazy=True)
    try:
        for table in font["cmap"].tables:
            codepoints.update(table.cmap.keys())
    finally:
        font.close()
    return codepoints


def missing_for(text: str, codepoints: set[int]) -> list[str]:
    """Characters in ``text`` the font cannot render (whitespace ignored)."""
    return [ch for ch in text if not ch.isspace() and ord(ch) not in codepoints]


def find_fonts() -> list[Path]:
    found: list[Path] = []
    for directory in FONT_SEARCH_DIRS:
        base = Path(directory)
        if not base.is_dir():
            continue
        for pattern in ("*.ttf", "*.otf", "*.ttc"):
            found.extend(base.rglob(pattern))
    return sorted(set(found))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--font", action="append", help="font file to check (repeatable)")
    parser.add_argument("--text", help="check this text instead of the language probes")
    parser.add_argument("--languages", nargs="+", help="restrict to these language tags")
    args = parser.parse_args()

    if not HAVE_FONTTOOLS:
        print(
            "error: fontTools is not installed.\n"
            "       install it with: pip install fonttools",
            file=sys.stderr,
        )
        return 2

    fonts = [Path(f) for f in args.font] if args.font else find_fonts()
    fonts = [f for f in fonts if f.exists()]
    if not fonts:
        print("no font files found; pass --font explicitly", file=sys.stderr)
        return 2

    probes = PROBES
    if args.languages:
        probes = {k: v for k, v in PROBES.items() if k in set(args.languages)}
        unknown = set(args.languages) - set(PROBES)
        if unknown:
            print(f"warning: no probe text for {', '.join(sorted(unknown))}", file=sys.stderr)

    if args.text:
        print(f"checking {len(fonts)} font(s) for: {args.text!r}\n")
        for font_path in fonts:
            try:
                missing = missing_for(args.text, covered_codepoints(font_path))
            except Exception as exc:
                print(f"  [skip] {font_path.name}: {exc}")
                continue
            verdict = "OK" if not missing else f"missing {''.join(missing)!r}"
            print(f"  {'OK  ' if not missing else 'FAIL'} {font_path.name:<45} {verdict}")
        return 0

    print(f"checking {len(fonts)} font(s) against {len(probes)} language probe(s)\n")
    coverage: dict[str, list[str]] = {lang: [] for lang in probes}
    for font_path in fonts:
        try:
            codepoints = covered_codepoints(font_path)
        except Exception:
            continue
        for lang, text in probes.items():
            if not missing_for(text, codepoints):
                coverage[lang].append(font_path.name)

    print(f"{'lang':<9}{'fonts':>7}  first usable font")
    print("-" * 70)
    uncovered = []
    for lang in sorted(coverage):
        hits = coverage[lang]
        if hits:
            print(f"{lang:<9}{len(hits):>7}  {hits[0]}")
        else:
            print(f"{lang:<9}{0:>7}  -- NO FONT COVERS THIS SCRIPT --")
            uncovered.append(lang)
    print("-" * 70)

    if uncovered:
        print(
            f"\n{len(uncovered)} language(s) have no usable font here: {', '.join(uncovered)}.\n"
            "Generating them now would produce .notdef boxes and a misleading 0% OCR score.\n"
            "Install the matching Noto fonts first (e.g. fonts-noto-core / noto-fonts)."
        )
        return 1

    print("\nevery probed language has at least one usable font")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
