# Data Quality Audit — `synthetic_30_samples_extended`

Generated with `mlocr-bench validate` (v0.2.0). Machine-readable form:
[`data_quality_audit.json`](data_quality_audit.json). Every figure below is
reproducible with:

```bash
mlocr-bench validate --json docs/data_quality_audit.json
```

## Why this audit exists

A synthetic OCR corpus can fail in ways no text-level check catches. The
ground-truth `.txt` holds perfect text, so manifests, encodings and character
counts all look correct — while the image is unreadable. Two distinct failures
were found here:

1. **Missing coverage.** The generation font has no glyphs for the script, so the
   renderer emits `.notdef` — the hollow rectangle known as *tofu*.
2. **Missing shaping.** The font has the glyphs, but the renderer applies no
   complex-text layout, so combining marks are placed beside their base letter
   instead of above or below it.

An OCR engine scored on such images returns ~0% accuracy. Read without this
audit, that looks like an engine defect. It is a data defect.

## Current state — all languages pass

Both defects have been fixed and the images regenerated. Ground truth was never
modified.

| Property | Value |
|---|---|
| Languages on disk | 23 |
| Images | 690 (30 per language) |
| Glyph blobs analysed | 10,430 |
| Glyph blobs rendered as `.notdef` | 2 (0.02%, all in `ko`) |
| `mn` / `lo` `.notdef` blobs | **0** (were 500 and 37) |
| Distinct ground-truth texts | 684 of 690 (6 duplicates) |
| Image dimensions | `1200x300`, `1400x500`, `2200x900` |
| Blank images | 0 |
| Clipped images | 0 |
| Verdicts | **ok: 23, suspect: 0, broken: 0** |

`mlocr-bench validate --strict` exits 0. The two residual blobs in `ko` are
0.4% of that language, far below the 5% `suspect` threshold; Hangul syllable
blocks are square by construction, so a small number of enclosed forms is
expected rather than a rendering failure.

## The defects, as originally measured

| Verdict | Count | Languages |
|---|---|---|
| `ok` | 21 | bn, hi, id, ja, km, kn, ko, ml, ms, my, ne, si, ta, te, th, tl, ug, ur, vi, zh, zh-Hant |
| `suspect` | 1 | lo |
| `broken` | 1 | mn |

Across the corpus, 539 of 10,344 glyph blobs (5.2%) were `.notdef`.

### `mn` (Mongolian Cyrillic) — was broken

| Metric | Before | After |
|---|---|---|
| Glyph blobs | 574 | 678 |
| `.notdef` blobs | 500 (**87.1%**) | **0** |
| Images affected | 30 of 30 | 0 |

All 30 images rendered as hollow boxes; none contained Cyrillic.

**Root cause — two compounding mistakes.**

The sidecar JSON recorded `"font_used": "NotoSansMongolian-Regular-72px"` with
`"no_garbled": true`. But **Noto Sans Mongolian covers the traditional vertical
Mongolian script, not Cyrillic**, and this corpus is Mongolian Cyrillic. The
font named in the metadata could not have rendered this text under any
circumstances, and the `no_garbled` claim was never verified.

In the generators, `mn` is absent from every font table:
`gen_30_samples_batch2.py` covers only `si`, `ta`, `te`, `th`, `ur`, `zh`,
`zh-Hant`; `gen_synthetic_extended.py` — which actually produces `mn` — resolves
fonts through hardcoded Linux paths such as
`/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf`, none of which exist on the
generating machine, and ends with `return ImageFont.load_default()`. The glyph
self-test `test_font_perfect()` ends with a bare `return True`, so any language
without an explicit probe string was declared "perfect" unchecked.

This was never a font-availability problem: 121 fonts on this machine cover the
required Cyrillic range. The generator simply never asked for one.

**Fix.** `tools/regenerate_language.py` re-rendered all 30 images with a font
whose cmap was verified to contain every character (`Arial Unicode.ttf`), then
re-inspected each output. Verified visually: legible Cyrillic matching the
ground truth.

### `lo` (Lao) — was suspect

| Metric | Before | After |
|---|---|---|
| Glyph blobs | 515 | 497 |
| `.notdef` blobs | 37 (**7.2%**) | **0** |
| Images affected | 30 of 30 | 0 |

**Root cause — shaping, not coverage.** This one is subtler, and a font swap
does not fix it. Lao places tone marks and vowel signs above and below the base
consonant. Correct placement requires a shaping engine to apply mark
positioning, where combining marks carry a zero advance and stack onto the
preceding glyph.

`PIL.ImageDraw.text` only shapes text when Pillow was built against **libraqm**.
The Pillow build here reports `features.check("raqm") is False`, so it advanced
the pen by each character's own width and every mark landed *next to* its base
instead of on it. Re-rendering with a dedicated Lao font produced the same
defect, which is what identified layout rather than the font as the cause.

**Fix.** Shaping is now performed explicitly in `src/mlocr_bench/shaping.py`:
HarfBuzz (`uharfbuzz`) computes glyph ids and positions, and FreeType
(`freetype-py`) rasterises each glyph *by glyph id* — something PIL cannot do.
Combining marks are drawn at their negative offsets, back over the base glyph.
Verified visually: tone marks correctly attached, `ຫຼ` forming its proper
ligature.

The other 12 languages whose scripts need shaping (`th`, `km`, `my`, `hi`, `ne`,
`bn`, `ta`, `te`, `kn`, `ml`, `si`, `ur`, `ug`) were inspected image by image and
found **already correct**, so they were left untouched rather than regenerated.

`lo` images remain `2200x900` while most of the corpus is `1400x500`. The
original canvas size was preserved deliberately, since size variation may be an
intentional robustness dimension.

## Guards added so this cannot recur

| Guard | Behaviour |
|---|---|
| `src/mlocr_bench/fonts.py` | Selects a font only after confirming its cmap covers every character; raises `FontCoverageError` instead of falling back to `load_default()` |
| Placeholder-font exclusion | Fonts like macOS `LastResort` declare huge coverage but draw a box-with-question-mark; excluded by name, since coverage checks alone accept them |
| `src/mlocr_bench/shaping.py` | Refuses to render a shaping-required script when HarfBuzz/FreeType are unavailable, rather than emitting misplaced marks |
| `tools/regenerate_language.py` | Re-inspects every image it writes and exits non-zero if any tofu remains |
| Extended tofu detector | Now catches both hollow boxes and boxes containing a placeholder mark |
| `tools/check_font_coverage.py` | Standalone gate; exits non-zero if any language lacks a covering font |
| Metadata | Records `font_used`, `font_coverage_verified` and `text_shaping`; the unverifiable `no_garbled` claim was removed |

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
