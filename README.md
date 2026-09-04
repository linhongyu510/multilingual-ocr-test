# mlocr-bench — multilingual OCR benchmark toolkit

Benchmark an OCR engine across 23 languages, and **validate the dataset before
trusting the score**.

The headline feature is the second half of that sentence. A synthetic OCR corpus
can fail in a way that no text-level check catches: when the generation font
lacks glyphs for a script, the renderer writes `.notdef` boxes (*tofu*) while the
ground-truth text stays perfectly correct. The engine then scores ~0% and it
looks like a model defect. In this repository's own dataset, that is exactly what
happened to Mongolian — **87% of its glyphs are hollow boxes**. See
[`docs/DATA_QUALITY_AUDIT.md`](docs/DATA_QUALITY_AUDIT.md).

## Install

```bash
pip install -e .            # core: validation + metrics
pip install -e ".[http]"    # also call a live OCR endpoint
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

```
lang      imgs   tofu%  blank  clip  dup  verdict
mn          30    87.1      0     0    2  broken
lo          30     7.2      0     0    0  suspect
zh          30     0.0      0     0    1  ok
```

| Verdict | Meaning |
|---|---|
| `ok` | images carry readable script; scores are meaningful |
| `suspect` | some glyphs missing, or blank/clipped/size anomalies; read with care |
| `broken` | images cannot support a fair score — fix the data, not the model |

`--strict` exits non-zero when anything is `broken`, so CI can gate on it.

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
