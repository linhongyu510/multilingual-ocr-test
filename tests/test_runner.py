"""Tests for the client and the benchmark runner.

A stub client replaces HTTP so aggregation logic is tested deterministically,
including the property that matters most for honest reporting: a language whose
images are broken must not drag down the headline accuracy.
"""

from __future__ import annotations

import json

import pytest
from PIL import Image, ImageDraw

from mlocr_bench.client import OCRClient, OCRResponse
from mlocr_bench.dataset import Sample, load_dataset
from mlocr_bench.runner import run_benchmark
from mlocr_bench.validate import validate_dataset


class StubClient:
    """Stands in for OCRClient; scripted per-language behaviour."""

    endpoint = "http://stub"

    def __init__(self, behaviour):
        self.behaviour = behaviour
        self.calls = 0

    def recognize(self, image_path, language):
        self.calls += 1
        action = self.behaviour.get(language, "echo")
        gt = str(image_path).replace(".png", ".txt")
        with open(gt, encoding="utf-8") as handle:
            truth = handle.read().strip()
        if action == "echo":
            return OCRResponse(text=truth, status="success", elapsed_seconds=0.1, http_status=200)
        if action == "reject":
            return OCRResponse(
                text="", status="http_400", elapsed_seconds=0.01, http_status=400,
                error="unsupported language",
            )
        if action == "empty":
            return OCRResponse(text="", status="success", elapsed_seconds=0.2, http_status=200)
        if action == "garbage":
            return OCRResponse(text="zzzz", status="success", elapsed_seconds=0.2, http_status=200)
        raise AssertionError(action)


def _sample(tmp_path, lang, stem, text, tofu=False):
    d = tmp_path / lang
    d.mkdir(parents=True, exist_ok=True)
    image = Image.new("L", (600, 200), 255)
    draw = ImageDraw.Draw(image)
    if tofu:
        x = 20
        for _ in range(8):
            draw.rectangle([x, 60, x + 30, 130], outline=0, width=5)
            x += 40
    else:
        draw.text((20, 80), "text", fill=0)
    image.save(d / f"{stem}.png")
    (d / f"{stem}.txt").write_text(text, encoding="utf-8")


@pytest.fixture
def mixed_dataset(tmp_path):
    root = tmp_path / "ds"
    for i in range(2):
        _sample(root, "id", f"id_0{i}", f"selamat pagi dunia {i}")
    for i in range(2):
        _sample(root, "bn", f"bn_0{i}", f"শুভ সকাল {i}")
    for i in range(2):
        _sample(root, "mn", f"mn_0{i}", f"Сайн байна уу {i}", tofu=True)
    return root


class TestTextExtraction:
    @pytest.mark.parametrize(
        "payload,expected",
        [
            ({"data": [{"text": "a"}, {"text": "b"}]}, "a b"),
            ({"results": [{"text": "x"}]}, "x"),
            ({"text": "plain"}, "plain"),
            ({"content": "c"}, "c"),
            ("bare string", "bare string"),
            ({}, ""),
            ({"data": []}, ""),
        ],
    )
    def test_accepts_common_response_shapes(self, payload, expected):
        assert OCRClient._extract_text(payload) == expected


class TestCredentials:
    def test_no_key_by_default(self, monkeypatch):
        monkeypatch.delenv("MLOCR_API_KEY", raising=False)
        assert OCRClient(endpoint="http://x").has_credentials is False

    def test_key_from_environment(self, monkeypatch):
        monkeypatch.setenv("MLOCR_API_KEY", "from-env")
        client = OCRClient(endpoint="http://x")
        assert client.has_credentials
        assert client._headers()["Authorization"] == "Bearer from-env"

    def test_explicit_key_wins(self, monkeypatch):
        monkeypatch.setenv("MLOCR_API_KEY", "from-env")
        assert OCRClient(endpoint="http://x", api_key="explicit").api_key == "explicit"

    def test_endpoint_from_environment(self, monkeypatch):
        monkeypatch.setenv("MLOCR_ENDPOINT", "http://from-env:1234")
        assert OCRClient().endpoint == "http://from-env:1234"

    def test_trailing_slash_stripped(self):
        assert OCRClient(endpoint="http://x/").endpoint == "http://x"


class TestRunBenchmark:
    def test_counts_and_status(self, mixed_dataset):
        samples = load_dataset(mixed_dataset)
        report = run_benchmark(samples, StubClient({"bn": "reject"}), max_workers=1)
        assert report.total_samples == 6
        assert report.successful_samples == 4
        assert report.languages["bn"].success == 0
        assert report.languages["bn"].status_breakdown == {"http_400": 2}

    def test_rejected_language_has_no_fabricated_accuracy(self, mixed_dataset):
        """A language that never returned text must report n/a, not 0%."""
        report = run_benchmark(
            load_dataset(mixed_dataset), StubClient({"bn": "reject"}), max_workers=1
        )
        assert report.languages["bn"].avg_accuracy is None

    def test_broken_data_excluded_from_headline(self, mixed_dataset):
        """The core reporting guarantee: bad *data* must not look like a bad *model*."""
        samples = load_dataset(mixed_dataset)
        quality = validate_dataset(samples)
        # mn renders as tofu, so the engine cannot possibly read it
        report = run_benchmark(
            samples,
            StubClient({"bn": "reject", "mn": "garbage"}),
            max_workers=1,
            quality=quality,
        )
        assert report.languages["mn"].data_quality == "broken"
        assert report.languages["mn"].trustworthy is False
        assert "mn" in report.excluded_languages
        # id echoed perfectly; mn's 0% must not be averaged in
        assert report.overall_accuracy == pytest.approx(100.0)

    def test_without_quality_nothing_is_excluded(self, mixed_dataset):
        report = run_benchmark(
            load_dataset(mixed_dataset), StubClient({"bn": "reject"}), max_workers=1
        )
        assert report.excluded_languages == []
        assert all(v.data_quality == "unknown" for v in report.languages.values())

    def test_concurrency_matches_serial(self, mixed_dataset):
        samples = load_dataset(mixed_dataset)
        serial = run_benchmark(samples, StubClient({"bn": "reject"}), max_workers=1)
        parallel = run_benchmark(samples, StubClient({"bn": "reject"}), max_workers=4)
        assert serial.successful_samples == parallel.successful_samples
        assert [r.sample_id for r in serial.results] == [r.sample_id for r in parallel.results]

    def test_progress_callback_invoked(self, mixed_dataset):
        seen = []
        run_benchmark(
            load_dataset(mixed_dataset),
            StubClient({}),
            max_workers=1,
            progress=lambda done, total, _r: seen.append((done, total)),
        )
        assert seen[-1] == (6, 6)

    def test_empty_prediction_scores_zero_not_none(self, mixed_dataset):
        report = run_benchmark(
            load_dataset(mixed_dataset, languages=["id"]), StubClient({"id": "empty"}), max_workers=1
        )
        assert report.languages["id"].success == 2
        assert report.languages["id"].avg_accuracy == pytest.approx(0.0)


class TestReportSerialisation:
    def test_json_roundtrip(self, mixed_dataset, tmp_path):
        report = run_benchmark(
            load_dataset(mixed_dataset), StubClient({"bn": "reject"}), max_workers=1
        )
        path = report.write_json(tmp_path / "r.json")
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["schema_version"] == 2
        assert payload["totals"]["samples"] == 6
        assert "samples" in payload
        assert payload["run"]["endpoint"] == "http://stub"

    def test_summary_only_omits_samples(self, mixed_dataset, tmp_path):
        report = run_benchmark(load_dataset(mixed_dataset), StubClient({}), max_workers=1)
        payload = json.loads(
            report.write_json(tmp_path / "s.json", include_samples=False).read_text("utf-8")
        )
        assert "samples" not in payload

    def test_csv_has_row_per_language(self, mixed_dataset, tmp_path):
        report = run_benchmark(load_dataset(mixed_dataset), StubClient({}), max_workers=1)
        lines = report.write_csv(tmp_path / "s.csv").read_text("utf-8").strip().splitlines()
        assert len(lines) == 1 + 3          # header + 3 languages
        assert lines[0].startswith("language,total,success")

    def test_provenance_recorded(self, mixed_dataset, tmp_path):
        report = run_benchmark(load_dataset(mixed_dataset), StubClient({}), max_workers=1)
        payload = report.as_dict()
        assert payload["tool_version"]
        assert payload["run"]["started_at"] < payload["run"]["finished_at"]
