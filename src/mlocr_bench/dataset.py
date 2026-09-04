"""Dataset loading for the multilingual OCR benchmark.

The on-disk layout is one directory per BCP-47-ish language tag, each holding
``<lang>_<index>.png`` images with sibling ``.txt`` ground truth (UTF-8) and
optional ``.json`` metadata::

    <root>/
      zh/zh_00.png  zh_00.txt  zh_00.json
      hi/hi_00.png  hi_00.txt  hi_00.json

Ground truth is always read from the ``.txt`` sibling, which is the
authoritative source. The bundled ``manifest.json`` is *not* used for loading:
it stores absolute paths from the machine that generated the data and does not
resolve anywhere else. :func:`audit_manifest` reports on it instead.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

__all__ = ["Sample", "load_dataset", "iter_languages", "audit_manifest"]


@dataclass(frozen=True)
class Sample:
    """One benchmark item."""

    image_path: Path
    text_path: Path
    ground_truth: str
    language: str
    sample_id: str

    @property
    def is_empty(self) -> bool:
        return not self.ground_truth.strip()


def iter_languages(root: Path) -> list[str]:
    """Language directories present under ``root``, sorted."""
    if not root.is_dir():
        raise NotADirectoryError(f"dataset root not found: {root}")
    return sorted(p.name for p in root.iterdir() if p.is_dir() and not p.name.startswith("."))


def load_dataset(
    root: str | Path,
    *,
    languages: list[str] | None = None,
    limit_per_language: int | None = None,
    skip_empty: bool = True,
) -> list[Sample]:
    """Load samples from ``root``.

    Parameters
    ----------
    languages
        Restrict to these language tags. Unknown tags raise ``ValueError`` so a
        typo fails loudly instead of silently producing an empty run.
    limit_per_language
        Take at most this many samples per language (deterministic: sorted by
        filename) — useful for smoke tests.
    skip_empty
        Drop samples whose ground truth is blank. Such samples make CER
        undefined and would otherwise distort aggregates.
    """
    root = Path(root).expanduser().resolve()
    available = iter_languages(root)

    if languages is not None:
        unknown = sorted(set(languages) - set(available))
        if unknown:
            raise ValueError(
                f"language(s) not present in {root}: {', '.join(unknown)}. "
                f"available: {', '.join(available)}"
            )
        wanted = [lang for lang in available if lang in set(languages)]
    else:
        wanted = available

    samples: list[Sample] = []
    for lang in wanted:
        count = 0
        for image_path in sorted((root / lang).glob("*.png")):
            text_path = image_path.with_suffix(".txt")
            if not text_path.exists():
                continue
            ground_truth = text_path.read_text(encoding="utf-8").strip()
            if skip_empty and not ground_truth:
                continue
            samples.append(
                Sample(
                    image_path=image_path,
                    text_path=text_path,
                    ground_truth=ground_truth,
                    language=lang,
                    sample_id=image_path.stem,
                )
            )
            count += 1
            if limit_per_language is not None and count >= limit_per_language:
                break
    return samples


def group_by_language(samples: list[Sample]) -> dict[str, list[Sample]]:
    grouped: dict[str, list[Sample]] = {}
    for s in samples:
        grouped.setdefault(s.language, []).append(s)
    return grouped


def audit_manifest(root: str | Path) -> dict[str, object]:
    """Check ``manifest.json`` against what is actually on disk.

    Handles both manifest layouts: the legacy one stores an absolute ``path``
    from the generating host, while the one written by ``fix-manifest`` stores
    an ``image`` path relative to the dataset root. A relative path is resolved
    against ``root`` before checking existence, so a portable manifest is not
    reported as broken.

    Returns a report rather than raising, so callers can surface the drift.
    """
    root = Path(root).expanduser().resolve()
    manifest_path = root / "manifest.json"
    report: dict[str, object] = {
        "manifest_present": manifest_path.exists(),
        "entries": 0,
        "resolvable_paths": 0,
        "unresolvable_paths": 0,
        "duplicate_entries": 0,
        "languages_in_manifest": 0,
        "languages_on_disk": len(iter_languages(root)),
    }
    if not manifest_path.exists():
        return report

    entries = json.loads(manifest_path.read_text(encoding="utf-8"))
    report["entries"] = len(entries)

    seen: set[tuple[str, str]] = set()
    dupes = 0
    resolvable = 0
    langs: set[str] = set()
    for entry in entries:
        lang = entry.get("language", "")
        langs.add(lang)

        # New format: "image" (relative). Legacy format: "path" (absolute).
        raw = entry.get("image") or entry.get("path") or ""
        candidate = Path(raw)
        resolved = candidate if candidate.is_absolute() else root / candidate

        key = (lang, candidate.name or raw)
        if key in seen:
            dupes += 1
        seen.add(key)

        if raw and resolved.exists():
            resolvable += 1

    report["duplicate_entries"] = dupes
    report["resolvable_paths"] = resolvable
    report["unresolvable_paths"] = len(entries) - resolvable
    report["languages_in_manifest"] = len(langs)
    return report


def iter_samples(root: str | Path, **kwargs: object) -> Iterator[Sample]:
    yield from load_dataset(root, **kwargs)  # type: ignore[arg-type]
