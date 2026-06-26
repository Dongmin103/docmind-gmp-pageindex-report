# GMP PageIndex Codex Retriever 10x10 Run Report

## Verdict

- 10 batches of 10 were generated and scored.
- This was a **blind question-only prediction run**: generation used `id/question` plus local PageIndex tree/page content, not gold labels.
- Strict score status is **FAIL** because exact page/path thresholds default to 1.0 and the blind run is not perfect.
- Still, the run is useful as the first real measurement of the Codex/PageIndex execution loop.

## Combined metrics

- predicted_page_hit_rate: `0.66`
- predicted_page_precision_avg: `0.5683`
- predicted_page_recall_avg: `0.66`
- predicted_section_path_hit_rate: `0.06`
- predicted_grounding_ok_rate: `1.0`

## Batch metrics

| batch | page hit | precision | recall | section path hit | grounding | strict status |
|---|---:|---:|---:|---:|---:|---|
| 001-010 | 0.6 | 0.5 | 0.6 | 0.1 | 1.0 | FAIL |
| 011-020 | 0.6 | 0.5 | 0.6 | 0.0 | 1.0 | FAIL |
| 021-030 | 0.8 | 0.75 | 0.8 | 0.0 | 1.0 | FAIL |
| 031-040 | 0.9 | 0.8 | 0.9 | 0.0 | 1.0 | FAIL |
| 041-050 | 0.5 | 0.45 | 0.5 | 0.1 | 1.0 | FAIL |
| 051-060 | 0.7 | 0.6 | 0.7 | 0.2 | 1.0 | FAIL |
| 061-070 | 0.8 | 0.7 | 0.8 | 0.2 | 1.0 | FAIL |
| 071-080 | 0.4 | 0.2333 | 0.4 | 0.0 | 1.0 | FAIL |
| 081-090 | 0.6 | 0.55 | 0.6 | 0.0 | 1.0 | FAIL |
| 091-100 | 0.7 | 0.6 | 0.7 | 0.0 | 1.0 | FAIL |

## Page misses

- page_miss_count: `34`

| id | predicted pages | gold pages | note |
|---|---|---|---|
| gmp_eval_001 | 119 | 18 | GMP 기준에서 '일탈'은 무엇을 의미하는가? |
| gmp_eval_002 | 357 | 18 | '기준일탈'의 정의는 무엇인가? |
| gmp_eval_003 | 441 | 21 | 이 기준에서 '밸리데이션'은 어떻게 정의되는가? |
| gmp_eval_005 | 357 | 21 | '재가공'의 정의는 무엇인가? |
| gmp_eval_011 | 228 | 54 | 작업소의 기계·설비는 어떤 기준에 따라 배치하여야 하는가? |
| gmp_eval_018 | 237 | 235 | 기록문서 작성 방식에 대한 요구사항은 무엇인가? |
| gmp_eval_019 | 222 | 392 | 작업원은 작업복 등을 어떤 기준에 따라 착용하여야 하는가? |
| gmp_eval_020 | 429 | 423 | 원자재 및 완제품의 보관·출고 방식에 대한 요구사항은? |
| gmp_eval_023 | 69 | 300 | 시험기기·계측기·기록계는 어떻게 교정하여야 하는가? |
| gmp_eval_025 | 24 | 401 | 작업소의 청정구역은 청정도를 어떻게 관리하여야 하는가? |
| gmp_eval_034 | 373 | 367 | 포장작업을 시작하기 전에 반드시 확인하여야 하는 절차는? |
| gmp_eval_042 | 441 | 252 | 공정 밸리데이션은 어떤 단위로 실시하여야 하는가? |
| gmp_eval_045 | 133-134 | 297 | 완제품의 출하승인을 위한 평가는 무엇을 종합하여 판정하는가? |
| gmp_eval_047 | 584 | 572 | 컴퓨터화 시스템에 대한 밸리데이션 문서·보고서는 시스템 전주기에 걸쳐 어떻게 적용·구성하여야 하는가? |
| gmp_eval_049 | 465 | 341 | 작업 전 시설 및 기구에 대하여 수행하여야 하는 확인 절차는? |
| gmp_eval_050 | 388 | 343 | 작업 중인 작업실·보관용기·기계설비에는 무엇을 표시하여야 하는가? |
| gmp_eval_052 | 441-442 | 147 | 변경관리를 승인하는 책임자는 누구인가? |
| gmp_eval_054 | 447 | 150 | 자율점검을 계획하고 추진하는 책임자는 누구인가? |
| gmp_eval_055 | 457-458 | 153 | 제조 또는 시험의 수탁자와 주요 원자재 제조업자를 평가하는 책임자는 누구인가? |
| gmp_eval_065 | 237 | 286 | 시험을 의뢰한 경우 작성하여야 하는 기록 문서는 무엇인가? |
| gmp_eval_068 | 373 | 382 | 포장작업과 관련하여 작성·기록하여야 하는 인적 사항은 무엇인가? |
| gmp_eval_071 | 429 | 21 | '완제의약품'과 '완제품'은 정의상 어떻게 구분되는가? |
| gmp_eval_073 | 256-258 | 248 | 예측적·동시적·회고적 밸리데이션 중 원칙적으로 실시해야 하는 것은 무엇이며 나머지는 어떤 경우에 적용하는가? |
| gmp_eval_075 | 357 | 18 | '일탈'과 '기준일탈'은 어떻게 구분되는가? |
| gmp_eval_076 | 603 | 160 | GMP 기준서는 어떤 네 가지로 구성되며 각각 무엇에 관한 기준서인가? |
| gmp_eval_079 | 94 | 84 | 제조부서와 품질(보증)부서는 조직상 어떤 관계여야 하는가? |
| gmp_eval_080 | 330 | 46 | 품질보증·품질관리·품질평가는 각각 무엇과 관련된 체계인가? |
| gmp_eval_082 | 441 | 243 | 밸리데이션을 생략할 수 있는 조건은 무엇인가? |
| gmp_eval_085 | 388 | 385 | 유통과정에서 반품된 제품은 원칙적으로 어떻게 처리하며, 재입고·재포장은 어떤 경우에 허용되는가? |
| gmp_eval_086 | 290-291 | 408 | 반입된 원자재 등을 적합판정 전에 사용할 수 있는 경우가 있는가? |
| gmp_eval_089 | 388 | 421 | 보관 시 원자재·완제품의 시험 전후 구분 표시를 생략할 수 있는 경우는? |
| gmp_eval_092 | 49-50 | 327 | 제품품질평가 시 평가에 포함되어야 하는 항목들은 무엇인가? |
| gmp_eval_094 | 559 | 28 | 품질경영(품질보증시스템)이 포함하여 시행하여야 하는 체계들은 무엇인가? |
| gmp_eval_099 | 441 | 243 | 밸리데이션 대상에 해당하면 어떤 문서를 작성·구비하며, 결과상 개선이 필요하면 무엇을 해야 하는가? |

## Section-path exact misses

- section_path_miss_count: `94`
- Main reason: PageIndex tree has many fine-grained child nodes, while eval gold often expects a parent/semantic section path; exact-path scoring is much stricter than page retrieval.

## Artifacts

- packets: `results/codex_retriever_10x10/packets/packet_001_010.md` ... `packet_091_100.md`
- batch predictions: `results/codex_retriever_10x10/predictions_001_010_blind.jsonl` ... `predictions_091_100_blind.jsonl`
- combined predictions: `results/codex_retriever_10x10/predictions_001_100_blind.jsonl`
- combined score JSON/MD: `results/codex_retriever_10x10/reports/score_001_100_blind.{json,md}`
- batch summary: `results/codex_retriever_10x10/reports/batch_metric_summary.json`
- generation trace: `results/codex_retriever_10x10/generation_trace_001_100_blind.json`

## Next improvement candidates

1. Add a parent/child path normalization scorer so exact child-vs-parent mismatches do not dominate section hit rate.
2. Add targeted aliases for comparison/exception/multi-hop questions; these batches had the weakest page hit.
3. Let Codex perform a second pass only on page misses by reading top candidate pages and nearby tree siblings, while clearly marking it as an iterative repair run rather than blind benchmark.
