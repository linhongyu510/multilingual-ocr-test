"""Tests for font coverage resolution and complex-script shaping.

These lock in the two defects that produced the broken images:

* a language absent from the font table silently fell through to a font that
  did not cover its script, and then to ``ImageFont.load_default()``;
* text was drawn without shaping, so combining marks landed beside their base
  letter instead of on it.
"""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

from mlocr_bench.fonts import (
    FALLBACK_FONT_STEMS,
    FontCoverageError,
    _is_fallback_font,
    _normalise_stem,
    find_font_for_text,
    font_covers,
    missing_codepoints,
)
from mlocr_bench.shaping import (
    SHAPING_REQUIRED_SCRIPTS,
    draw_shaped_text,
    measure_shaped,
    needs_shaping,
    shaped_line_metrics,
    shaping_available,
)
from mlocr_bench.validate import inspect_image

from pathlib import Path

# Sample text per language, matching the corpus scripts.
PROBES = {
    "mn": "Сайн уу, та хэрхэн байна?",
    "lo": "ສະບາຍດີ, ທ່ານເປັນແນວໃດ?",
    "zh": "你好，你好吗？",
    "hi": "नमस्ते, आप कैसे हैं?",
    "th": "สวัสดี คุณสบายดีไหม",
    "ta": "வணக்கம், நீங்கள் எப்படி?",
}


class TestNameNormalisation:
    """Font families are named inconsistently across installations."""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("Lao Sangam MN", "laosangammn"),
            ("LaoSangamMN", "laosangammn"),
            ("lao-sangam-mn", "laosangammn"),
            ("NotoSansLao-Regular", "notosanslaoregular"),
        ],
    )
    def test_spacing_and_punctuation_ignored(self, raw, expected):
        assert _normalise_stem(raw) == expected

    def test_spaced_and_unspaced_names_match(self):
        # The regression: "LaoSangamMN" in "lao sangam mn" is False as a raw
        # substring test, so the dedicated Lao font was never selected.
        assert _normalise_stem("LaoSangamMN") in _normalise_stem("Lao Sangam MN")


class TestFallbackFontExclusion:
    """Placeholder fonts declare coverage but draw nothing readable."""

    @pytest.mark.parametrize("name", ["LastResort", "LastResort.otf", "lastresort", "Adobe Blank"])
    def test_placeholder_fonts_rejected(self, name):
        assert _is_fallback_font(Path(name))

    @pytest.mark.parametrize("name", ["Arial Unicode.ttf", "Lao Sangam MN.ttf", "NotoSans-Regular.ttf"])
    def test_real_fonts_accepted(self, name):
        assert not _is_fallback_font(Path(name))

    def test_resolver_never_returns_a_placeholder(self):
        for lang, text in PROBES.items():
            try:
                chosen = find_font_for_text(text, lang)
            except FontCoverageError:
                continue
            assert not _is_fallback_font(chosen), f"{lang} resolved to placeholder {chosen.name}"


class TestCoverageVerification:
    def test_covering_font_reports_no_missing_glyphs(self):
        for lang, text in PROBES.items():
            try:
                chosen = find_font_for_text(text, lang)
            except FontCoverageError:
                pytest.skip(f"no font for {lang} on this machine")
            assert missing_codepoints(text, chosen) == []
            assert font_covers(text, chosen)

    def test_unrenderable_text_raises_instead_of_silently_degrading(self):
        # Unassigned plane-15 private use text cannot be covered; the resolver
        # must fail loudly rather than return load_default() and emit tofu.
        with pytest.raises(FontCoverageError):
            find_font_for_text("\U000f0000\U000f0001\U000f0002", "xx")

    def test_mongolian_resolves_to_a_cyrillic_capable_font(self):
        """The original pipeline recorded NotoSansMongolian for Cyrillic text."""
        chosen = find_font_for_text(PROBES["mn"], "mn")
        assert font_covers(PROBES["mn"], chosen)
        # Noto Sans Mongolian covers the vertical script, not Cyrillic.
        assert "mongolian" not in chosen.stem.lower()


@pytest.mark.skipif(not shaping_available(), reason="uharfbuzz/freetype-py not installed")
class TestShaping:
    def test_shaping_required_scripts_include_combining_mark_languages(self):
        for lang in ("lo", "th", "km", "my", "hi", "bn", "ta", "ur"):
            assert needs_shaping(lang)

    def test_latin_and_cyrillic_do_not_need_shaping(self):
        for lang in ("id", "ms", "vi", "tl", "mn"):
            assert lang not in SHAPING_REQUIRED_SCRIPTS

    def test_combining_marks_do_not_advance_the_pen(self):
        """A mark must stack on its base, not occupy its own width.

        If every glyph advanced, shaped width would match the unshaped width
        and the marks would sit beside their bases — the original defect.
        """
        font = find_font_for_text(PROBES["lo"], "lo")
        shaped_width = measure_shaped(PROBES["lo"], font, 48)
        pil_font = ImageFont.truetype(str(font), 48)
        unshaped_width = ImageDraw.Draw(Image.new("L", (10, 10))).textlength(
            PROBES["lo"], font=pil_font
        )
        assert shaped_width < unshaped_width

    def test_shaped_lao_renders_without_placeholder_glyphs(self, tmp_path):
        font = find_font_for_text(PROBES["lo"], "lo")
        ascent, descent = shaped_line_metrics(font, 48)
        width = int(measure_shaped(PROBES["lo"], font, 48)) + 80
        image = Image.new("L", (width, ascent + descent + 40), 255)
        draw_shaped_text(image, (40, ascent + 20), PROBES["lo"], font, 48)
        out = tmp_path / "lo.png"
        image.save(out)

        findings = inspect_image(out)
        assert findings.tofu_blobs == 0
        assert not findings.is_blank
        assert findings.glyph_blobs > 0

    def test_shaped_output_has_ink(self, tmp_path):
        font = find_font_for_text(PROBES["lo"], "lo")
        ascent, descent = shaped_line_metrics(font, 40)
        image = Image.new("L", (900, ascent + descent + 40), 255)
        draw_shaped_text(image, (20, ascent + 20), PROBES["lo"], font, 40)
        assert (np.asarray(image) < 128).sum() > 200

    def test_draw_shaped_text_rejects_non_grayscale(self):
        font = find_font_for_text(PROBES["lo"], "lo")
        with pytest.raises(ValueError):
            draw_shaped_text(Image.new("RGB", (100, 50), 255), (0, 30), "ດ", font, 20)
