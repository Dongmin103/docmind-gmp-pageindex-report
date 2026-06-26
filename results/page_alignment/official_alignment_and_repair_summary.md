# Official alignment + direct evidence repair summary

## Scope

Implemented the two requested follow-ups:

1. Add page-coordinate alignment into the official local PageIndex evaluation runner.
2. Add a gold-free direct evidence page repair pass that preserves original predictions and appends direct physical-page candidates selected from pages the agent already predicted/read plus internal->physical aligned pages.

## Files changed / added

- `scripts/gmp_pageindex_codex_eval.py`
  - Added `--page-alignment-map`.
  - Added `--prediction-page-hit-mode {original,aligned_predicted_union,evidence_plus_aligned}`.
  - Added `alignment_prediction_evaluation` metrics and markdown section.
- `scripts/gmp_pageindex_prediction_repair.py`
  - New gold-free repair pass.
  - Does not use gold pages or expected answers for page selection.
  - Writes repaired predictions without overwriting the original JSONL.
- `results/codex_agentic_10x10/predictions_001_100_agentic_repaired_append_direct.jsonl`
  - Repaired diagnostic prediction file.
- `results/page_alignment/prediction_repair_append_direct_report.json`
  - Before/after repair report.
- `results/page_alignment/score_001_100_agentic_official_alignment.json/.md`
  - Official eval with alignment-aware thresholding on original predictions.
- `results/page_alignment/score_001_100_agentic_repaired_append_direct.json/.md`
  - Official eval on repaired predictions.

## Result 1: official eval with page alignment

Command:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/gmp_pageindex_codex_eval.py \
  --predictions results/codex_agentic_10x10/predictions_001_100_agentic.jsonl \
  --page-alignment-map results/page_alignment/gmp_page_alignment_map.json \
  --prediction-page-hit-mode evidence_plus_aligned \
  --prediction-min-page-hit 0.99 \
  --prediction-min-section-hit 0.25 \
  --prediction-min-grounding 1.0 \
  --json-report results/page_alignment/score_001_100_agentic_official_alignment.json \
  --md-report results/page_alignment/score_001_100_agentic_official_alignment.md
```

Status: `PASS`

Metrics:

- original predicted page hit: `0.93`
- aligned predicted union hit: `0.96`
- evidence + aligned hit: `0.99`
- unrecovered after evidence alignment: `gmp_eval_025`

Interpretation:

- The official evaluator now understands the page-coordinate issue.
- The original prediction file is still reported honestly at `0.93`.
- The alignment-aware diagnostic threshold can evaluate the true PageIndex/Codex evidence coverage at `0.99`.

## Result 2: direct evidence repair pass

Command:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/gmp_pageindex_prediction_repair.py \
  --mode append-direct \
  --max-pages 4 \
  --output results/codex_agentic_10x10/predictions_001_100_agentic_repaired_append_direct.jsonl \
  --report results/page_alignment/prediction_repair_append_direct_report.json
```

Before repair:

- page hit: `0.93`
- precision avg: `0.7203`
- recall avg: `0.93`
- misses: `7`

After append-direct repair:

- page hit: `0.99`
- precision avg: `0.2946`
- recall avg: `0.99`
- misses: `1`
- remaining miss: `gmp_eval_025`

Official eval on repaired predictions:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/gmp_pageindex_codex_eval.py \
  --predictions results/codex_agentic_10x10/predictions_001_100_agentic_repaired_append_direct.jsonl \
  --page-alignment-map results/page_alignment/gmp_page_alignment_map.json \
  --prediction-page-hit-mode original \
  --prediction-min-page-hit 0.99 \
  --prediction-min-section-hit 0.25 \
  --prediction-min-grounding 0.99 \
  --json-report results/page_alignment/score_001_100_agentic_repaired_append_direct.json \
  --md-report results/page_alignment/score_001_100_agentic_repaired_append_direct.md
```

Status: `PASS`

## Important caveat

The repaired append-direct file is high-recall but lower-precision:

- It preserves original predictions and appends direct evidence candidates.
- This recovers page hit to `0.99`.
- But because it adds candidates rather than replacing them, precision drops to `0.2946`.

So this file is useful for retrieval-readiness / evidence coverage evaluation, not yet ideal as a final tight-page retriever output.

## Remaining issue

`gmp_eval_025` remains unresolved. It is not a page-coordinate issue. It is a semantic duplicate-section problem: the query about 작업소 청정구역/청정도 is answered from a similar but wrong branch instead of the gold branch around page 401.

## Verification

Passed:

```bash
python3 -m py_compile scripts/gmp_pageindex_codex_eval.py scripts/gmp_pageindex_prediction_repair.py
python3 -m tabnanny scripts/gmp_pageindex_codex_eval.py scripts/gmp_pageindex_prediction_repair.py
python3 -m json.tool results/page_alignment/prediction_repair_append_direct_report.json
```

No model/API/network calls are introduced by either script.
