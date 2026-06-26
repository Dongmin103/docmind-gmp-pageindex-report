# GMP PageIndex page-coordinate alignment report

- generated_at: 2026-06-25T12:43:32.254927+00:00
- page_count: 606
- mapped internal page labels: 580
- dominant offset: physical = internal + 7
- original_predicted_page_hit_rate: 0.93
- aligned_predicted_union_hit_rate: 0.96
- evidence_union_hit_rate: 0.95
- evidence_plus_aligned_hit_rate: 0.99

## What this means

- PageIndex `get_page_content` uses physical PDF pages.
- The visible printed page label inside most GMP content is 7 pages behind the physical page.
- Existing predictions are intentionally preserved. This report adds an alignment-aware diagnostic view instead of blindly rewriting all predictions.

## Offset segments

| physical pages | internal pages | offset | count |
|---|---|---:|---:|
| 11-11 | 4-4 | 7 | 1 |
| 13-13 | 6-6 | 7 | 1 |
| 18-476 | 11-469 | 7 | 459 |
| 482-552 | 475-545 | 7 | 71 |
| 558-605 | 551-598 | 7 | 48 |

## Original miss classification

| id | gold | predicted | aligned predicted | evidence read | aligned evidence | classification |
|---|---|---|---|---|---|---|
| gmp_eval_013 | 533 | 519-521 | 526-528 | 500,519-521,526-528 | 507,526-528,533-535 | coordinate_shift_in_evidence_pages_read |
| gmp_eval_025 | 401 | 81 | 88 | 81-84 | 88-91 | semantic_duplicate_section_confusion |
| gmp_eval_032 | 415 | 408-410 | 415-417 | 408-414 | 415-421 | coordinate_shift_in_predicted_pages |
| gmp_eval_042 | 252 | 245 | 252 | 245 | 252 | coordinate_shift_in_predicted_pages |
| gmp_eval_072 | 535 | 500,516-522,528-530 | 507,523-529,535-537 | 500,516-522,526-530 | 507,523-529,533-537 | coordinate_shift_in_predicted_pages |
| gmp_eval_084 | 249 | 256-260 | 263-267 | 249-266 | 256-273 | evidence_read_contains_gold_but_final_page_selection_missed |
| gmp_eval_086 | 408 | 290-291 | 297-298 | 290-292,408-410 | 297-299,415-417 | evidence_read_contains_gold_but_final_page_selection_missed |

## Unrecovered after evidence alignment

| id | gold | predicted | classification |
|---|---|---|---|
| gmp_eval_025 | 401 | 81 | semantic_duplicate_section_confusion |

## Artifact policy

- No model/API/network call is used by this script.
- `*_aligned_union.jsonl` is diagnostic only; it should not replace the original Codex prediction log.
