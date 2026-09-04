"""Tests for dataset loading and image quality validation.

Fixtures synthesise images rather than depending on the bundled corpus, so the
suite stays fast and still exercises the tofu (``.notdef``) detector that tells
a data defect apart from an engine defect.
"""

from __future__ import annotations

import json

import numpy as np
import pytest
from PIL import Image, ImageDraw

from mlocr_bench.dataset import audit_manifest, iter_languages, load_dataset
from mlocr_bench.validate import inspect_image, unusable_languages, validate_dataset


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _write_sample(lang_dir, stem, text, draw_fn, size=(600, 200)):
    lang_dir.mkdir(parents=True, exist_ok=True)
    image = Image.new("L", size, color=255)
    draw_fn(ImageDraw.Draw(image), size)
    image.save(lang_dir / f"{stem}.png")
    (lang_dir / f"{stem}.txt").write_text(text, encoding="utf-8")


def _draw_text(draw, size):
    draw.text((20, 80), "readable text here", fill=0)


def _draw_tofu(draw, size, width=5):
    """Draw hollow rectangles: exactly what a font renders for missing glyphs."""
    x = 20
    for _ in range(8):
        draw.rectangle([x, 60, x + 30, 130], outline=0, width=width)
        x += 40


def _draw_blank(draw, size):
    return None


@pytest.fixture
def dataset(tmp_path):
    root = tmp_path / "ds"
    for i in range(3):
        _write_sample(root / "zh", f"zh_0{i}", f"你好世界{i}", _draw_text)
    for i in range(3):
        _write_sample(root / "mn", f"mn_0{i}", f"Сайн байна уу {i}", _draw_tofu)
    for i in range(2):
        _write_sample(root / "xx", f"xx_0{i}", f"blank {i}", _draw_blank)
    return root


# --------------------------------------------------------------------------- #
class TestLoadDataset:
    def test_discovers_languages(self, dataset):
        assert iter_languages(dataset) == ["mn", "xx", "zh"]

    def test_loads_all_samples(self, dataset):
        assert len(load_dataset(dataset)) == 8

    def test_ground_truth_from_txt_sibling(self, dataset):
        sample = next(s for s in load_dataset(dataset) if s.sample_id == "zh_00")
        assert sample.ground_truth == "你好世界0"
        assert sample.language == "zh"

    def test_language_filter(self, dataset):
        samples = load_dataset(dataset, languages=["zh"])
        assert len(samples) == 3
        assert {s.language for s in samples} == {"zh"}

    def test_unknown_language_fails_loudly(self, dataset):
        """A typo must not silently yield an empty benchmark run."""
        with pytest.raises(ValueError, match="not present"):
            load_dataset(dataset, languages=["nope"])

    def test_limit_per_language_is_deterministic(self, dataset):
        first = load_dataset(dataset, limit_per_language=2)
        second = load_dataset(dataset, limit_per_language=2)
        assert [s.sample_id for s in first] == [s.sample_id for s in second]
        assert len(first) == 6

    def test_missing_root(self, tmp_path):
        with pytest.raises(NotADirectoryError):
            load_dataset(tmp_path / "absent")

    def test_image_without_text_is_skipped(self, dataset):
        orphan = dataset / "zh" / "zh_99.png"
        Image.new("L", (100, 50), 255).save(orphan)
        assert all(s.sample_id != "zh_99" for s in load_dataset(dataset))

    def test_empty_ground_truth_skipped_by_default(self, dataset):
        _write_sample(dataset / "zh", "zh_88", "   ", _draw_text)
        assert all(s.sample_id != "zh_88" for s in load_dataset(dataset))
        assert any(s.sample_id == "zh_88" for s in load_dataset(dataset, skip_empty=False))


class TestTofuDetection:
    def test_readable_image_has_no_tofu(self, dataset):
        findings = inspect_image(dataset / "zh" / "zh_00.png")
        assert findings.tofu_blobs == 0
        assert not findings.is_blank

    def test_notdef_boxes_are_detected(self, dataset):
        findings = inspect_image(dataset / "mn" / "mn_00.png")
        assert findings.glyph_blobs > 0
        assert findings.tofu_blobs == findings.glyph_blobs
        assert findings.tofu_ratio == pytest.approx(100.0)

    def test_blank_image_flagged(self, dataset):
        assert inspect_image(dataset / "xx" / "xx_00.png").is_blank

    def test_short_text_on_large_canvas_is_not_blank(self, tmp_path):
        """Blankness must not be judged by ink *fraction* alone.

        The same short line of text has a smaller ink fraction on a bigger
        canvas; a fraction-only rule reports such valid samples as blank.
        """
        root = tmp_path / "big"
        _write_sample(root / "zh", "zh_00", "short", _draw_text, size=(2200, 900))
        findings = inspect_image(root / "zh" / "zh_00.png")
        assert not findings.is_blank

    @pytest.mark.parametrize("stroke", [2, 3, 4, 5, 6])
    def test_tofu_detected_across_stroke_widths(self, tmp_path, stroke):
        """.notdef outlines vary in stroke width by font and point size.

        Guessing a single width from the blob size caused false negatives:
        overestimating by one pixel pulls empty interior into the border
        sample and the glyph slips through as 'readable'.
        """
        root = tmp_path / f"stroke{stroke}"
        _write_sample(
            root / "mn",
            "mn_00",
            "Сайн байна уу",
            lambda d, s: _draw_tofu(d, s, width=stroke),
        )
        findings = inspect_image(root / "mn" / "mn_00.png")
        assert findings.glyph_blobs > 0
        assert findings.tofu_blobs == findings.glyph_blobs, (
            f"stroke width {stroke} not recognised as .notdef"
        )

    def test_dimensions_reported(self, dataset):
        findings = inspect_image(dataset / "zh" / "zh_00.png")
        assert (findings.width, findings.height) == (600, 200)


class TestValidateDataset:
    def test_verdicts(self, dataset):
        report = validate_dataset(load_dataset(dataset))
        assert report["zh"].verdict == "ok"
        assert report["mn"].verdict == "broken"
        assert report["xx"].verdict == "broken"   # entirely blank

    def test_broken_languages_listed(self, dataset):
        report = validate_dataset(load_dataset(dataset))
        assert set(unusable_languages(report)) == {"mn", "xx"}

    def test_note_explains_root_cause(self, dataset):
        report = validate_dataset(load_dataset(dataset))
        assert "notdef" in report["mn"].note
        assert "font" in report["mn"].note

    def test_duplicate_texts_counted(self, tmp_path):
        root = tmp_path / "dup"
        _write_sample(root / "zh", "zh_00", "same text", _draw_text)
        _write_sample(root / "zh", "zh_01", "same text", _draw_text)
        _write_sample(root / "zh", "zh_02", "other", _draw_text)
        assert validate_dataset(load_dataset(root))["zh"].duplicate_texts == 1

    def test_inconsistent_sizes_noted(self, tmp_path):
        root = tmp_path / "sizes"
        _write_sample(root / "zh", "zh_00", "a", _draw_text, size=(600, 200))
        _write_sample(root / "zh", "zh_01", "b", _draw_text, size=(800, 300))
        quality = validate_dataset(load_dataset(root))["zh"]
        assert len(quality.sizes) == 2
        assert "inconsistent image sizes" in quality.note

    def test_serialisable(self, dataset):
        report = validate_dataset(load_dataset(dataset))
        payload = {k: v.as_dict() for k, v in report.items()}
        json.dumps(payload, ensure_ascii=False)  # must not raise
        assert payload["mn"]["verdict"] == "broken"


class TestManifestAudit:
    def test_absent_manifest(self, dataset):
        assert audit_manifest(dataset)["manifest_present"] is False

    def test_unresolvable_absolute_paths_reported(self, dataset):
        (dataset / "manifest.json").write_text(
            json.dumps(
                [
                    {"language": "zh", "path": "/nonexistent/host/zh/zh_00.png"},
                    {"language": "zh", "path": "/nonexistent/host/zh/zh_00.png"},
                ]
            ),
            encoding="utf-8",
        )
        audit = audit_manifest(dataset)
        assert audit["entries"] == 2
        assert audit["unresolvable_paths"] == 2
        assert audit["duplicate_entries"] == 1

    def test_relative_paths_resolve_against_root(self, dataset):
        """The portable format written by fix-manifest must audit clean."""
        (dataset / "manifest.json").write_text(
            json.dumps(
                [
                    {"language": "zh", "image": "zh/zh_00.png", "sample_id": "zh_00"},
                    {"language": "zh", "image": "zh/zh_01.png", "sample_id": "zh_01"},
                ]
            ),
            encoding="utf-8",
        )
        audit = audit_manifest(dataset)
        assert audit["resolvable_paths"] == 2
        assert audit["unresolvable_paths"] == 0
        assert audit["duplicate_entries"] == 0

    def test_duplicates_detected_in_relative_format(self, dataset):
        (dataset / "manifest.json").write_text(
            json.dumps(
                [
                    {"language": "zh", "image": "zh/zh_00.png"},
                    {"language": "zh", "image": "zh/zh_00.png"},
                    {"language": "zh", "image": "zh/zh_01.png"},
                ]
            ),
            encoding="utf-8",
        )
        assert audit_manifest(dataset)["duplicate_entries"] == 1
