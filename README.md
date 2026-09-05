# mlocr-bench — multilingual OCR benchmark toolkit

Benchmark an OCR engine across 23 languages, and **validate the dataset before
trusting the score**.

The headline feature is the second half of that sentence. A synthetic OCR corpus
can fail in ways that no text-level check catches, because the ground-truth text
stays perfectly correct while the images do not:

- the generation font lacks glyphs for the script, so the renderer writes
  `.notdef` boxes (*tofu*);
- the font has the glyphs but the renderer applies no **shaping**, so combining
  marks land beside their base letter instead of on it.

Either way the engine scores near 0% and it looks like a model defect. Both
happened in this repository's own dataset: Mongolian was rendered with a font
covering the *vertical* Mongolian script while the text is Mongolian **Cyrillic**
(87% of its glyphs came out as hollow boxes), and Lao lost its tone marks to
unshaped layout. Both are now fixed and the dataset validates clean — see
[`docs/DATA_QUALITY_AUDIT.md`](docs/DATA_QUALITY_AUDIT.md) for the diagnosis and
the fix.

## Install

```bash
pip install -e .            # core: validation + metrics
pip install -e ".[http]"    # also call a live OCR endpoint
pip install -e ".[render]"  # also inspect fonts / regenerate images
pip install -e ".[dev]"     # also run the tests
```

Python 3.9+ (verified on 3.9.6 and 3.14).

## Quick start

```bash
# 1. Audit the dataset. Do this first, always.
mlocr-bench validate

# 2. Benchmark an engine (never hardcode the key)
export MLOCR_API_KEY='your-key'
mlocr-bench run --endpoint http://localhost:16110

# 3. Re-read a stored report
mlocr-bench report reports/benchmark_report.json
```

No OCR service handy? A mock is included:

```bash
python tools/mock_ocr_server.py --port 18110 &
MLOCR_ENDPOINT=http://127.0.0.1:18110 mlocr-bench run --limit 3
```

## What `validate` tells you

Current state of the bundled dataset — all 23 languages pass:

```
lang      imgs   tofu%  blank  clip  dup  verdict
mn          30     0.0      0     0    2  ok
lo          30     0.0      0     0    0  ok
zh          30     0.0      0     0    1  ok
...
ok: 23   suspect: 0   broken: 0
```

Before the font and shaping fixes, the same command reported `mn` at 87.1% tofu
(`broken`) and `lo` at 7.2% (`suspect`).

| Verdict | Meaning |
|---|---|
| `ok` | images carry readable script; scores are meaningful |
| `suspect` | some glyphs missing, or blank/clipped/size anomalies; read with care |
| `broken` | images cannot support a fair score — fix the data, not the model |

`--strict` exits non-zero when anything is `broken`, so CI can gate on it.

## Regenerating broken images

```bash
# See what would change, pick fonts, verify coverage — writes nothing
python tools/regenerate_language.py --languages mn lo --dry-run

# Re-render, then re-inspect every output; exits non-zero if tofu remains
python tools/regenerate_language.py --languages mn lo
```

Ground truth is never touched — only the `.png` is redrawn. A font is used only
after its cmap is confirmed to cover every character, and scripts with combining
marks are rendered through HarfBuzz so the marks are positioned correctly. If no
covering font is installed the tool fails loudly instead of emitting tofu.

## What `run` guarantees

- **Broken languages are excluded from headline averages** and flagged
  `score_trustworthy: false`. Averaging a 0% caused by missing fonts into an
  engine's accuracy misattributes a data defect to the model.
- **Rejected samples report `n/a`, not 0%.** A language the API refuses
  (HTTP 400) has no measured accuracy; `success_rate` carries that information.
  Reporting 0% would conflate "cannot process" with "processes badly".
- **WER is a real word error rate.** See below.
- **Every report is self-describing**: endpoint, dataset root, timestamps, tool
  version and per-language data-quality verdicts travel with the numbers.

## Metrics

| Metric | Definition |
|---|---|
| CER | character edit distance ÷ reference length |
| WER | **word** edit distance ÷ reference word count |
| Accuracy | `100 − CER` |

Two deliberate choices:

**WER is word-level.** The previous implementation computed it as a
*character* edit distance over whitespace-joined tokens, which makes WER
algebraically identical to CER for every input — two columns carrying one
signal. Now they differ: for `"the quick brown fox"` → `"the quick brown cat"`,
CER is 15.79% and WER is 25.00%.

**WER is `None` for scripts without word delimiters** (`zh`, `ja`, `th`, `km`,
`lo`, `my`, ...), shown as `n/a`. Whitespace tokenisation is meaningless there,
and a fabricated 0 or 100 would silently pollute averages.

Text is NFKC-normalised before scoring, so an Indic or Vietnamese prediction
that is visually identical but differently encoded is not counted as an error.

## Layout

```
src/mlocr_bench/     package: dataset, validate, metrics, client, runner, cli
tests/               91 tests
tools/               mock_ocr_server.py, check_font_coverage.py
data/
  synthetic_30_samples_extended/   23 languages × 30 samples
  generators/                      dataset generation scripts
docs/                DATA_QUALITY_AUDIT.md + machine-readable audit
archive/             superseded reports and scripts, kept for provenance
```

Dataset layout — ground truth always comes from the `.txt` sibling:

```
<lang>/<lang>_<NN>.png    image
<lang>/<lang>_<NN>.txt    ground truth (UTF-8)
<lang>/<lang>_<NN>.json   metadata
```

## Before generating data

Check glyph coverage first — this is the check whose absence broke Mongolian:

```bash
python tools/check_font_coverage.py                  # probe all languages
python tools/check_font_coverage.py --languages mn   # probe one
```

It exits non-zero when a language has no usable font, so generation can be
gated instead of silently producing tofu.

## Configuration

| Variable | Purpose |
|---|---|
| `MLOCR_API_KEY` | OCR API key — never commit it |
| `MLOCR_ENDPOINT` | default endpoint |

## Development

```bash
pip install -e ".[dev]"
pytest
```

## Security note

Earlier revisions of the test scripts contained a hardcoded API key. It has been
removed from the working tree, but **it remains in git history and should be
treated as compromised — rotate it.** Keys now come from the environment only.
