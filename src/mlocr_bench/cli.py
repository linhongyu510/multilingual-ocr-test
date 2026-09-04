"""Command line interface for mlocr-bench.

Subcommands
-----------
``validate``   audit dataset image/text quality; exits non-zero on broken data
``run``        benchmark an OCR endpoint and write JSON/CSV reports
``report``     re-render a stored JSON report as a table
``fix-manifest`` rewrite manifest/stats with verified, relative-path metadata
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import __version__
from .dataset import audit_manifest, iter_languages, load_dataset
from .validate import validate_dataset

DEFAULT_DATASET = Path("data/synthetic_30_samples_extended")


# --------------------------------------------------------------------------- #
# rendering helpers
# --------------------------------------------------------------------------- #
def _fmt(value: object, width: int, suffix: str = "") -> str:
    if value is None:
        return "n/a".rjust(width)
    if isinstance(value, float):
        return f"{value:.2f}{suffix}".rjust(width)
    return f"{value}{suffix}".rjust(width)


def _print_validation(report: dict, *, verbose: bool) -> None:
    print(f"\n{'lang':<9}{'imgs':>5}{'tofu%':>8}{'blank':>7}{'clip':>6}{'dup':>5}  {'verdict':<9}")
    print("-" * 72)
    for lang, quality in report.items():
        print(
            f"{lang:<9}{quality.images:>5}{quality.tofu_ratio:>8.1f}"
            f"{quality.blank_images:>7}{quality.clipped_images:>6}"
            f"{quality.duplicate_texts:>5}  {quality.verdict:<9}"
        )
    broken = [k for k, v in report.items() if v.verdict == "broken"]
    suspect = [k for k, v in report.items() if v.verdict == "suspect"]
    print("-" * 72)
    print(f"ok: {len(report) - len(broken) - len(suspect)}   suspect: {len(suspect)}   broken: {len(broken)}")

    if broken or suspect or verbose:
        print("\nfindings:")
        for lang, quality in report.items():
            if quality.verdict != "ok" or verbose:
                print(f"  [{quality.verdict:<7}] {lang}: {quality.note}")
    if broken:
        print(
            "\nBroken languages carry no readable script in their images; any OCR score\n"
            "for them measures the dataset, not the engine. Regenerate them with a font\n"
            "that covers the script before quoting numbers."
        )


def _print_report(payload: dict) -> None:
    run = payload.get("run", {})
    totals = payload.get("totals", {})
    print(f"\nendpoint : {run.get('endpoint')}")
    print(f"dataset  : {run.get('dataset_root')}")
    print(f"started  : {run.get('started_at')}")
    print(
        f"samples  : {totals.get('samples')}  "
        f"success {totals.get('successful_samples')} "
        f"({totals.get('success_rate_percent')}%)"
    )
    print(
        f"overall  : accuracy {totals.get('avg_accuracy_percent')}%  "
        f"CER {totals.get('avg_cer_percent')}%  WER {totals.get('avg_wer_percent')}%"
    )

    header = (
        f"\n{'lang':<9}{'n':>4}{'ok':>4}{'succ%':>7}{'acc%':>8}"
        f"{'CER%':>8}{'WER%':>8}{'sec':>7}  {'data':<8}{'trust':<6}"
    )
    print(header)
    print("-" * len(header))
    for lang, s in payload.get("languages", {}).items():
        print(
            f"{lang:<9}{s['total']:>4}{s['success']:>4}"
            f"{_fmt(s['success_rate_percent'],7)}{_fmt(s['avg_accuracy_percent'],8)}"
            f"{_fmt(s['avg_cer_percent'],8)}{_fmt(s['avg_wer_percent'],8)}"
            f"{_fmt(s['avg_elapsed_seconds'],7)}  {s['data_quality']:<8}"
            f"{'yes' if s['score_trustworthy'] else 'NO':<6}"
        )
    print("-" * len(header))
    if totals.get("note"):
        print(totals["note"])


# --------------------------------------------------------------------------- #
# subcommands
# --------------------------------------------------------------------------- #
def cmd_validate(args: argparse.Namespace) -> int:
    samples = load_dataset(args.dataset, languages=args.languages, limit_per_language=args.limit)
    if not samples:
        print(f"no samples found under {args.dataset}", file=sys.stderr)
        return 2

    print(f"validating {len(samples)} samples across {len({s.language for s in samples})} languages")
    report = validate_dataset(samples)
    _print_validation(report, verbose=args.verbose)

    manifest = audit_manifest(args.dataset)
    if manifest["manifest_present"]:
        print(
            f"\nmanifest.json: {manifest['entries']} entries, "
            f"{manifest['unresolvable_paths']} unresolvable path(s), "
            f"{manifest['duplicate_entries']} duplicate(s)"
        )
        if manifest["unresolvable_paths"]:
            print(
                "  manifest paths do not resolve on this machine (they are absolute paths\n"
                "  from the generating host). Loading uses the on-disk layout instead;\n"
                "  run 'mlocr-bench fix-manifest' to regenerate it with relative paths."
            )

    if args.json:
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(
                {
                    "dataset_root": str(Path(args.dataset).resolve()),
                    "tool_version": __version__,
                    "languages": {k: v.as_dict() for k, v in report.items()},
                    "manifest_audit": manifest,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"\nwrote {out}")

    broken = [k for k, v in report.items() if v.verdict == "broken"]
    if broken and args.strict:
        return 1
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    from .client import OCRClient, MissingDependencyError
    from .runner import run_benchmark

    samples = load_dataset(args.dataset, languages=args.languages, limit_per_language=args.limit)
    if not samples:
        print(f"no samples found under {args.dataset}", file=sys.stderr)
        return 2

    try:
        client = OCRClient(
            endpoint=args.endpoint,
            api_key=args.api_key,
            timeout=args.timeout,
            retries=args.retries,
        )
    except MissingDependencyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if not client.has_credentials:
        print(
            f"warning: no API key set. Pass --api-key or export MLOCR_API_KEY "
            f"if {client.endpoint} requires authentication.",
            file=sys.stderr,
        )

    reachable, detail = client.health_check()
    if not reachable:
        print(f"error: OCR endpoint unreachable — {detail}", file=sys.stderr)
        print(
            "       start the service, or point --endpoint at a running instance.",
            file=sys.stderr,
        )
        return 3

    quality = None
    if not args.skip_validation:
        print("validating dataset quality first ...")
        quality = validate_dataset(samples)
        broken = [k for k, v in quality.items() if v.verdict == "broken"]
        if broken:
            print(
                f"note: {', '.join(broken)} have unusable images and will be excluded "
                f"from headline averages (still measured and reported)."
            )

    total = len(samples)
    print(f"running {total} samples against {client.endpoint} with {args.workers} worker(s)")

    def progress(done: int, count: int, _result: object) -> None:
        if done % max(1, count // 20) == 0 or done == count:
            pct = done / count * 100
            print(f"  {done}/{count} ({pct:.0f}%)", flush=True)

    report = run_benchmark(
        samples,
        client,
        max_workers=args.workers,
        quality=quality,
        progress=None if args.quiet else progress,
    )

    payload = report.as_dict(include_samples=not args.summary_only)
    _print_report(payload)

    out_dir = Path(args.out_dir)
    json_path = report.write_json(out_dir / "benchmark_report.json", include_samples=not args.summary_only)
    csv_path = report.write_csv(out_dir / "benchmark_summary.csv")
    print(f"\nwrote {json_path}")
    print(f"wrote {csv_path}")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    path = Path(args.report)
    if not path.exists():
        print(f"report not found: {path}", file=sys.stderr)
        return 2
    payload = json.loads(path.read_text(encoding="utf-8"))
    if "languages" not in payload:
        print(f"{path} is not an mlocr-bench report", file=sys.stderr)
        return 2
    _print_report(payload)
    return 0


def cmd_fix_manifest(args: argparse.Namespace) -> int:
    """Regenerate manifest.json / stats.json from what is actually on disk."""
    root = Path(args.dataset).resolve()
    samples = load_dataset(root)
    if not samples:
        print(f"no samples found under {root}", file=sys.stderr)
        return 2

    quality = validate_dataset(samples)
    entries = []
    for sample in samples:
        entries.append(
            {
                "language": sample.language,
                "image": str(sample.image_path.relative_to(root)),
                "text": str(sample.text_path.relative_to(root)),
                "ground_truth": sample.ground_truth,
                "char_count": len(sample.ground_truth),
                "sample_id": sample.sample_id,
            }
        )

    languages = sorted({s.language for s in samples})
    stats = {
        "generated_by": f"mlocr-bench {__version__} fix-manifest",
        "total_samples": len(samples),
        "languages": len(languages),
        "language_list": languages,
        "samples_per_language": {
            lang: sum(1 for s in samples if s.language == lang) for lang in languages
        },
        "image_sizes": sorted(
            {f"{w}x{h}" for q in quality.values() for (w, h) in q.sizes}
        ),
        "data_quality": {
            lang: {"verdict": q.verdict, "tofu_ratio_percent": round(q.tofu_ratio, 2)}
            for lang, q in quality.items()
        },
        "verified": True,
    }

    if args.dry_run:
        print(json.dumps(stats, ensure_ascii=False, indent=2))
        print(f"\n(dry run) would write {len(entries)} manifest entries to {root}/manifest.json")
        return 0

    (root / "manifest.json").write_text(
        json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (root / "stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"wrote {root/'manifest.json'} ({len(entries)} entries, relative paths)")
    print(f"wrote {root/'stats.json'} ({len(languages)} languages, {len(samples)} samples)")
    return 0


# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mlocr-bench",
        description="Benchmark and validate multilingual OCR datasets and engines.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  mlocr-bench validate\n"
            "  mlocr-bench validate --languages mn lo --verbose\n"
            "  mlocr-bench run --endpoint http://localhost:16110 --limit 5\n"
            "  mlocr-bench report reports/benchmark_report.json\n"
        ),
    )
    parser.add_argument("--version", action="version", version=f"mlocr-bench {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_common(sub: argparse.ArgumentParser) -> None:
        sub.add_argument(
            "--dataset", default=str(DEFAULT_DATASET), help=f"dataset root (default: {DEFAULT_DATASET})"
        )
        sub.add_argument("--languages", nargs="+", help="restrict to these language tags")
        sub.add_argument("--limit", type=int, help="max samples per language")

    p_validate = subparsers.add_parser("validate", help="audit dataset image and text quality")
    add_common(p_validate)
    p_validate.add_argument("--json", help="also write the audit to this JSON path")
    p_validate.add_argument("--verbose", action="store_true", help="show notes for every language")
    p_validate.add_argument(
        "--strict", action="store_true", help="exit non-zero when any language is broken"
    )
    p_validate.set_defaults(func=cmd_validate)

    p_run = subparsers.add_parser("run", help="benchmark an OCR endpoint")
    add_common(p_run)
    p_run.add_argument("--endpoint", help="OCR base URL (env: MLOCR_ENDPOINT)")
    p_run.add_argument("--api-key", help="API key (env: MLOCR_API_KEY; prefer the env var)")
    p_run.add_argument("--workers", type=int, default=4, help="concurrent requests (default: 4)")
    p_run.add_argument("--timeout", type=float, default=30.0, help="per-request timeout seconds")
    p_run.add_argument("--retries", type=int, default=2, help="retries for transient failures")
    p_run.add_argument("--out-dir", default="reports", help="report output directory")
    p_run.add_argument("--summary-only", action="store_true", help="omit per-sample detail in JSON")
    p_run.add_argument("--skip-validation", action="store_true", help="do not audit data first")
    p_run.add_argument("--quiet", action="store_true", help="suppress progress output")
    p_run.set_defaults(func=cmd_run)

    p_report = subparsers.add_parser("report", help="re-render a stored JSON report")
    p_report.add_argument("report", help="path to benchmark_report.json")
    p_report.set_defaults(func=cmd_report)

    p_fix = subparsers.add_parser(
        "fix-manifest", help="regenerate manifest.json/stats.json from disk"
    )
    p_fix.add_argument("--dataset", default=str(DEFAULT_DATASET), help="dataset root")
    p_fix.add_argument("--dry-run", action="store_true", help="print instead of writing")
    p_fix.set_defaults(func=cmd_fix_manifest)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (ValueError, NotADirectoryError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
