# Data Quality Audit — `synthetic_30_samples_extended`

Generated with `mlocr-bench validate` (v0.2.0). Machine-readable form:
[`data_quality_audit.json`](data_quality_audit.json). Every figure below is
reproducible with:

```bash
mlocr-bench validate --json docs/data_quality_audit.json
```

## Why this audit exists

A synthetic OCR corpus can fail in a way no text-level check catches. If the
font used at generation time has no glyphs for a script, the renderer emits
`.notdef` — the hollow rectangle known as *tofu*. The ground-truth `.txt` still
holds perfect text, so manifests, encodings and character counts all look
correct, while the image contains no readable script at all.

An OCR engine scored on such images returns ~0% accuracy. Read without this
audit, that looks like an engine defect. It is a data defect.

## Dataset as measured

| Property | Value |
|---|---|
| Languages on disk | 23 |
| Images | 690 (30 per language) |
| Glyph blobs analysed | 10,344 |
| Glyph blobs rendered as `.notdef` | 539 (5.2%) |
| Distinct ground-truth texts | 684 of 690 (6 duplicates) |
| Image dimensions | `1200x300`, `1400x500`, `2200x900` |
| Blank images | 0 |
| Clipped images | 0 |

## Verdicts

| Verdict | Count | Languages |
|---|---|---|
| `ok` | 21 | bn, hi, id, ja, km, kn, ko, ml, ms, my, ne, si, ta, te, th, tl, ug, ur, vi, zh, zh-Hant |
| `suspect` | 1 | lo |
| `broken` | 1 | mn |

### `mn` (Mongolian Cyrillic) — broken, do not score

| Metric | Value |
|---|---|
| Glyph blobs | 574 |
| `.notdef` blobs | 500 (**87.1%**) |
| Images affected | 30 of 30 |

All 30 images render as hollow boxes; none contains Cyrillic. Any accuracy
number for `mn` measures the dataset, not the engine.

**Root cause.** In `data/generators/gen_30_samples_batch2.py`, the
`get_perfect_font_for_language()` font table has entries for `si`, `ta`, `te`,
`th`, `ur`, `zh` and `zh-Hant` — but **no entry for `mn`**. Its glyph self-test
`test_font_perfect()` has no probe string for `mn` either. So generation fell
through to `ImageFont.load_default()`, a bitmap font with no Cyrillic coverage,
and the missing self-test meant nothing flagged it. 30 unusable images were
written while the run reported success.

This is not a font-availability problem: `tools/check_font_coverage.py` finds
**121 fonts on this machine** that cover the required Cyrillic range. The
generator simply never asked for one.

### `lo` (Lao) — suspect, interpret with care

37 of 515 glyph blobs (7.2%) are `.notdef`, spread across all 30 images. The Lao
consonants and vowels render correctly; specific marks do not. Scores are
usable as a lower bound but are depressed by a data defect, not only by engine
limits. These images are also `2200x900` while most of the corpus is
`1400x500`.

## Metadata drift (fixed)

`manifest.json` and `stats.json` no longer match what the earlier documentation
claimed. Both have been regenerated from disk with `mlocr-bench fix-manifest`.

| Field | Before | After (verified) |
|---|---|---|
| `manifest.json` entries | 720 | 690 |
| Entries resolvable on this machine | **0 of 720** | 690 of 690 |
| Duplicate entries | 30 (`km` listed twice) | 0 |
| `stats.json` `total_samples` | 720 | 690 |
| `stats.json` `languages` | 24 (`km` counted twice) | 23 |
| Path style | absolute `/root/lhy/paddleocr/...` | relative to dataset root |
| Claimed image size | `1200x300` for all | three real sizes recorded |
| Claimed `no_garbled` | `true` | per-language verdicts recorded |

The old manifest listed `km` twice — once from `synthetic_30_samples_final` and
once from `synthetic_30_samples_extended` — which produced the 24-language,
720-sample claim. On disk there have always been 23 languages and 690 samples.

## Recommended actions

1. **Regenerate `mn`** with a Cyrillic-capable font, then re-validate. Until
   then exclude it from any published score; `mlocr-bench` does this
   automatically.
2. **Regenerate `lo`** with a font covering the full Lao block.
3. **Add a font-coverage gate to generation.** Run
   `python tools/check_font_coverage.py` before generating, and make
   `test_font_perfect()` fail loudly instead of silently returning
   `load_default()`.
4. **Normalise image dimensions**, or record them as an intentional variable if
   robustness across sizes is being tested.
5. **Re-run the audit after any dataset change** — it is one command and it is
   the only check that catches this failure class.
