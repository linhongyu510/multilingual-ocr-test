#!/usr/bin/env python3
"""Regenerate sample images for languages whose rendering is broken.

Ground truth is preserved exactly; only the ``.png`` is re-rendered, with a font
whose cmap is verified to cover every character first. Each image is then
re-inspected and the run aborts if tofu remains, so this cannot quietly repeat
the failure it exists to fix.

Background: ``mn`` images were rendered with a font recorded in metadata as
``NotoSansMongolian-Regular`` while the text is Mongolian *Cyrillic*. Noto Sans
Mongolian covers the traditional vertical script, not Cyrillic, so every glyph
came out as ``.notdef`` — and the sidecar JSON still claimed
``"no_garbled": true``.

Usage
-----
    python tools/regenerate_language.py --languages mn lo --dry-run
    python tools/regenerate_language.py --languages mn lo
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from mlocr_bench.fonts import FontCoverageError, find_font_for_text  # noqa: E402
from mlocr_bench.shaping import (  # noqa: E402
    draw_shaped_text,
    measure_shaped,
    needs_shaping,
    shaped_line_metrics,
    shaping_available,
)
from mlocr_bench.validate import inspect_image  # noqa: E402

DEFAULT_DATASET = REPO_ROOT / "data" / "synthetic_30_samples_extended"


def wrap_units(text: str, measure, max_width: int) -> list[str]:
    """Wrap ``text`` to ``max_width`` px using ``measure(str) -> px``.

    Splits on spaces where the script has them and per character otherwise, so
    scripts without word delimiters wrap instead of overflowing the canvas.
    """
    if measure(text) <= max_width:
        return [text]

    units = text.split(" ") if " " in text else list(text)
    joiner = " " if " " in text else ""
    lines: list[str] = []
    current = ""
    for unit in units:
        candidate = f"{current}{joiner}{unit}" if current else unit
        if measure(candidate) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = unit
    if current:
        lines.append(current)
    return lines


def render(
    text: str,
    font_path: Path,
    size: tuple[int, int],
    *,
    shaped: bool,
    font_px: int = 44,
    margin: int = 60,
) -> Image.Image:
    """Render ``text`` centred on a white canvas of ``size``.

    ``shaped=True`` routes through HarfBuzz + FreeType so combining marks are
    positioned correctly; otherwise PIL's own layout is used, which is adequate
    for scripts without combining marks.
    """
    width, height = size
    image = Image.new("L", size, 255)
    draw = ImageDraw.Draw(image)

    font_px = min(font_px, max(16, height - 2 * margin))
    while font_px >= 16:
        if shaped:
            measure = lambda s: measure_shaped(s, font_path, font_px)  # noqa: E731
            ascent, descent = shaped_line_metrics(font_path, font_px)
        else:
            pil_font = ImageFont.truetype(str(font_path), font_px)
            measure = lambda s: draw.textlength(s, font=pil_font)  # noqa: E731
            ascent, descent = pil_font.getmetrics()

        lines = wrap_units(text, measure, width - 2 * margin)
        line_height = ascent + descent + 10
        if line_height * len(lines) <= height - 2 * margin:
            break
        font_px -= 4

    block_height = line_height * len(lines)
    y = max(margin, (height - block_height) // 2)
    for line in lines:
        line_width = measure(line)
        x = max(margin, (width - line_width) // 2)
        if shaped:
            draw_shaped_text(image, (x, y + ascent), line, font_path, font_px, fill=0)
        else:
            draw.text((x, y), line, font=ImageFont.truetype(str(font_path), font_px), fill=0)
        y += line_height
    return image


def dominant_size(lang_dir: Path) -> tuple[int, int]:
    """Reuse the language's existing canvas size so the corpus stays comparable."""
    sizes: dict[tuple[int, int], int] = {}
    for png in sorted(lang_dir.glob("*.png")):
        with Image.open(png) as handle:
            sizes[handle.size] = sizes.get(handle.size, 0) + 1
    if not sizes:
        return (1400, 500)
    return max(sizes.items(), key=lambda kv: kv[1])[0]


def regenerate(
    dataset: Path,
    language: str,
    *,
    dry_run: bool,
    backup_dir: Path | None,
) -> tuple[int, int]:
    """Re-render one language. Returns (regenerated, still_broken)."""
    lang_dir = dataset / language
    if not lang_dir.is_dir():
        raise FileNotFoundError(f"no such language directory: {lang_dir}")

    texts = sorted(lang_dir.glob("*.txt"))
    if not texts:
        raise FileNotFoundError(f"no ground-truth .txt files under {lang_dir}")

    corpus = "".join(p.read_text(encoding="utf-8") for p in texts)
    try:
        font_path = find_font_for_text(corpus, language)
    except FontCoverageError as exc:
        print(f"  {language}: {exc}", file=sys.stderr)
        return (0, len(texts))

    size = dominant_size(lang_dir)
    shaped = needs_shaping(language)
    if shaped and not shaping_available():
        print(
            f"  {language}: needs complex-script shaping but uharfbuzz/freetype-py are "
            f"missing; refusing to render misplaced marks. pip install uharfbuzz freetype-py",
            file=sys.stderr,
        )
        return (0, len(texts))

    mode = "HarfBuzz-shaped" if shaped else "plain"
    print(
        f"  {language}: font={font_path.name}  canvas={size[0]}x{size[1]}  "
        f"samples={len(texts)}  rendering={mode}"
    )

    if dry_run:
        sample_text = texts[0].read_text(encoding="utf-8").strip()
        print(f"    (dry run) would re-render e.g. {texts[0].stem} -> {sample_text[:40]!r}")
        return (0, 0)

    regenerated = 0
    still_broken = 0
    for text_path in texts:
        text = text_path.read_text(encoding="utf-8").strip()
        if not text:
            continue
        image_path = text_path.with_suffix(".png")

        if backup_dir is not None and image_path.exists():
            target = backup_dir / language
            target.mkdir(parents=True, exist_ok=True)
            shutil.copy2(image_path, target / image_path.name)

        render(text, font_path, size, shaped=shaped).save(image_path)

        # Verify through the same detector used for auditing, not by assumption.
        findings = inspect_image(image_path)
        if findings.tofu_blobs or findings.is_blank:
            print(
                f"    STILL BROKEN {image_path.name}: "
                f"tofu={findings.tofu_blobs}/{findings.glyph_blobs} blank={findings.is_blank}",
                file=sys.stderr,
            )
            still_broken += 1
        regenerated += 1

        json_path = text_path.with_suffix(".json")
        meta = {}
        if json_path.exists():
            try:
                meta = json.loads(json_path.read_text(encoding="utf-8"))
            except ValueError:
                meta = {}
        meta.update(
            {
                "language": language,
                "text": text,
                "image_path": f"{language}/{image_path.name}",
                "text_path": f"{language}/{text_path.name}",
                "char_count": len(text),
                "word_count": len(text.split()),
                "font_used": font_path.name,
                "font_coverage_verified": True,
                "text_shaping": "harfbuzz" if shaped else "none",
                "regenerated_by": "tools/regenerate_language.py",
                "regenerated_on": date.today().isoformat(),
                "image_size": f"{size[0]}x{size[1]}",
            }
        )
        # Drop the stale, unverified claim from the previous pipeline.
        meta.pop("no_garbled", None)
        meta.pop("font_optimized", None)
        json_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    return (regenerated, still_broken)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET))
    parser.add_argument("--languages", nargs="+", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--backup-dir",
        help="copy replaced PNGs here first (outside the dataset; not committed)",
    )
    args = parser.parse_args()

    dataset = Path(args.dataset).expanduser().resolve()
    backup_dir = Path(args.backup_dir).expanduser().resolve() if args.backup_dir else None
    if backup_dir is not None:
        backup_dir.mkdir(parents=True, exist_ok=True)

    print(f"dataset: {dataset}")
    total_done = total_bad = 0
    for language in args.languages:
        done, bad = regenerate(dataset, language, dry_run=args.dry_run, backup_dir=backup_dir)
        total_done += done
        total_bad += bad

    if args.dry_run:
        return 0

    print(f"\nre-rendered {total_done} image(s); {total_bad} still failing validation")
    if total_bad:
        print(
            "Some images still contain placeholder glyphs — do not treat these languages\n"
            "as fixed. Install a font that genuinely covers the script and re-run.",
            file=sys.stderr,
        )
        return 1
    print("Run 'mlocr-bench validate' to confirm, then 'mlocr-bench fix-manifest'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
