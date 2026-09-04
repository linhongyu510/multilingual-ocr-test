"""Benchmark runner: execute a dataset against an OCR engine and aggregate.

Two properties matter for a benchmark whose numbers get quoted:

*Reproducibility* — every report embeds the dataset root, endpoint, sample
count, tool version and a data-quality summary, so a number can always be
traced back to the run that produced it.

*Honesty about invalid data* — languages whose rendered images are broken (see
:mod:`mlocr_bench.validate`) are reported separately and excluded from headline
averages. Averaging a 0% score caused by missing fonts into an engine's overall
accuracy misattributes a data defect to the model.
"""

from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Sequence

from . import __version__
from .client import OCRClient, OCRResponse
from .dataset import Sample, group_by_language
from .metrics import mean, score_sample
from .validate import LanguageQuality

__all__ = ["SampleResult", "LanguageSummary", "BenchmarkReport", "run_benchmark"]


@dataclass
class SampleResult:
    """Per-sample outcome, metrics included."""

    sample_id: str
    language: str
    image_path: str
    ground_truth: str
    prediction: str
    status: str
    elapsed_seconds: float
    cer: float | None = None
    wer: float | None = None
    accuracy: float | None = None
    http_status: int | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == "success"

    def as_dict(self) -> dict[str, object]:
        return {
            "sample_id": self.sample_id,
            "language": self.language,
            "image_path": self.image_path,
            "ground_truth": self.ground_truth,
            "prediction": self.prediction,
            "status": self.status,
            "http_status": self.http_status,
            "elapsed_seconds": round(self.elapsed_seconds, 4),
            "cer": None if self.cer is None else round(self.cer, 4),
            "wer": None if self.wer is None else round(self.wer, 4),
            "accuracy": None if self.accuracy is None else round(self.accuracy, 4),
            "error": self.error,
        }


@dataclass
class LanguageSummary:
    """Aggregated engine performance for one language.

    ``avg_*`` values are computed over *successful* samples only; ``success_rate``
    carries the failure information. Reporting an accuracy that silently mixes in
    zeros for rejected requests would conflate "cannot process" with
    "processes badly".
    """

    language: str
    total: int = 0
    success: int = 0
    avg_cer: float | None = None
    avg_wer: float | None = None
    avg_accuracy: float | None = None
    avg_elapsed_seconds: float | None = None
    status_breakdown: dict[str, int] = field(default_factory=dict)
    data_quality: str = "unknown"
    data_quality_note: str = ""

    @property
    def success_rate(self) -> float:
        return self.success / self.total * 100.0 if self.total else 0.0

    @property
    def trustworthy(self) -> bool:
        """False when the input images cannot support a fair score."""
        return self.data_quality != "broken"

    def as_dict(self) -> dict[str, object]:
        def r(v: float | None) -> float | None:
            return None if v is None else round(v, 2)

        return {
            "language": self.language,
            "total": self.total,
            "success": self.success,
            "success_rate_percent": round(self.success_rate, 2),
            "avg_accuracy_percent": r(self.avg_accuracy),
            "avg_cer_percent": r(self.avg_cer),
            "avg_wer_percent": r(self.avg_wer),
            "avg_elapsed_seconds": r(self.avg_elapsed_seconds),
            "status_breakdown": self.status_breakdown,
            "data_quality": self.data_quality,
            "data_quality_note": self.data_quality_note,
            "score_trustworthy": self.trustworthy,
        }


@dataclass
class BenchmarkReport:
    """Full run: provenance, per-language summaries, per-sample detail."""

    endpoint: str
    dataset_root: str
    started_at: str
    finished_at: str
    total_samples: int
    languages: dict[str, LanguageSummary]
    results: list[SampleResult]
    tool_version: str = __version__

    # ---- headline aggregates ------------------------------------------------
    @property
    def trustworthy_languages(self) -> list[str]:
        return [k for k, v in self.languages.items() if v.trustworthy]

    @property
    def excluded_languages(self) -> list[str]:
        return [k for k, v in self.languages.items() if not v.trustworthy]

    @property
    def successful_samples(self) -> int:
        return sum(1 for r in self.results if r.ok)

    @property
    def overall_success_rate(self) -> float:
        return self.successful_samples / self.total_samples * 100.0 if self.total_samples else 0.0

    @property
    def overall_accuracy(self) -> float | None:
        """Mean accuracy over successful samples in trustworthy languages."""
        trusted = set(self.trustworthy_languages)
        return mean([r.accuracy for r in self.results if r.ok and r.language in trusted])

    @property
    def overall_cer(self) -> float | None:
        trusted = set(self.trustworthy_languages)
        return mean([r.cer for r in self.results if r.ok and r.language in trusted])

    @property
    def overall_wer(self) -> float | None:
        trusted = set(self.trustworthy_languages)
        return mean([r.wer for r in self.results if r.ok and r.language in trusted])

    def as_dict(self, *, include_samples: bool = True) -> dict[str, object]:
        payload: dict[str, object] = {
            "schema_version": 2,
            "tool_version": self.tool_version,
            "run": {
                "endpoint": self.endpoint,
                "dataset_root": self.dataset_root,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
            },
            "totals": {
                "samples": self.total_samples,
                "successful_samples": self.successful_samples,
                "success_rate_percent": round(self.overall_success_rate, 2),
                "avg_accuracy_percent": None
                if self.overall_accuracy is None
                else round(self.overall_accuracy, 2),
                "avg_cer_percent": None if self.overall_cer is None else round(self.overall_cer, 2),
                "avg_wer_percent": None if self.overall_wer is None else round(self.overall_wer, 2),
                "note": (
                    "Averages cover successful samples in languages whose rendered images "
                    "passed data-quality validation. Languages excluded as untrustworthy: "
                    + (", ".join(self.excluded_languages) or "none")
                ),
            },
            "languages": {k: v.as_dict() for k, v in self.languages.items()},
        }
        if include_samples:
            payload["samples"] = [r.as_dict() for r in self.results]
        return payload

    def write_json(self, path: str | Path, *, include_samples: bool = True) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.as_dict(include_samples=include_samples), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path

    def write_csv(self, path: str | Path) -> Path:
        import csv

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "language",
                    "total",
                    "success",
                    "success_rate_percent",
                    "avg_accuracy_percent",
                    "avg_cer_percent",
                    "avg_wer_percent",
                    "avg_elapsed_seconds",
                    "data_quality",
                    "score_trustworthy",
                ]
            )
            for lang, summary in self.languages.items():
                d = summary.as_dict()
                writer.writerow(
                    [
                        lang,
                        d["total"],
                        d["success"],
                        d["success_rate_percent"],
                        d["avg_accuracy_percent"],
                        d["avg_cer_percent"],
                        d["avg_wer_percent"],
                        d["avg_elapsed_seconds"],
                        d["data_quality"],
                        d["score_trustworthy"],
                    ]
                )
        return path


def _summarize(
    results: Sequence[SampleResult],
    quality: dict[str, LanguageQuality] | None,
) -> dict[str, LanguageSummary]:
    summaries: dict[str, LanguageSummary] = {}
    by_language: dict[str, list[SampleResult]] = {}
    for result in results:
        by_language.setdefault(result.language, []).append(result)

    for language, group in sorted(by_language.items()):
        ok = [r for r in group if r.ok]
        breakdown: dict[str, int] = {}
        for r in group:
            breakdown[r.status] = breakdown.get(r.status, 0) + 1

        summary = LanguageSummary(
            language=language,
            total=len(group),
            success=len(ok),
            avg_cer=mean([r.cer for r in ok]),
            avg_wer=mean([r.wer for r in ok]),
            avg_accuracy=mean([r.accuracy for r in ok]),
            avg_elapsed_seconds=mean([r.elapsed_seconds for r in group]),
            status_breakdown=dict(sorted(breakdown.items())),
        )
        if quality and language in quality:
            summary.data_quality = quality[language].verdict
            summary.data_quality_note = quality[language].note
        summaries[language] = summary
    return summaries


def run_benchmark(
    samples: Iterable[Sample],
    client: OCRClient,
    *,
    max_workers: int = 4,
    quality: dict[str, LanguageQuality] | None = None,
    progress: Callable[[int, int, SampleResult], None] | None = None,
    normalize: bool = True,
) -> BenchmarkReport:
    """Run every sample through ``client`` and aggregate the outcome."""
    samples = list(samples)
    started = datetime.now(timezone.utc)

    def work(sample: Sample) -> SampleResult:
        response: OCRResponse = client.recognize(sample.image_path, sample.language)
        result = SampleResult(
            sample_id=sample.sample_id,
            language=sample.language,
            image_path=str(sample.image_path),
            ground_truth=sample.ground_truth,
            prediction=response.text,
            status=response.status,
            elapsed_seconds=response.elapsed_seconds,
            http_status=response.http_status,
            error=response.error,
        )
        if response.ok:
            m = score_sample(
                sample.ground_truth,
                response.text,
                language=sample.language,
                normalize=normalize,
            )
            result.cer, result.wer, result.accuracy = m.cer, m.wer, m.accuracy
        return result

    results: list[SampleResult] = []
    if max_workers <= 1:
        for index, sample in enumerate(samples, start=1):
            result = work(sample)
            results.append(result)
            if progress:
                progress(index, len(samples), result)
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(work, s): s for s in samples}
            for index, future in enumerate(as_completed(futures), start=1):
                result = future.result()
                results.append(result)
                if progress:
                    progress(index, len(samples), result)

    results.sort(key=lambda r: (r.language, r.sample_id))
    finished = datetime.now(timezone.utc)

    dataset_root = ""
    if samples:
        dataset_root = str(Path(samples[0].image_path).parent.parent)

    return BenchmarkReport(
        endpoint=client.endpoint,
        dataset_root=dataset_root,
        started_at=started.isoformat(),
        finished_at=finished.isoformat(),
        total_samples=len(samples),
        languages=_summarize(results, quality),
        results=results,
    )
