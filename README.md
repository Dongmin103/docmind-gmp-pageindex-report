# DocMIND GMP 문서 구조화 및 검색 평가 보고서

이 저장소는 GMP 가이던스 PDF를 대상으로 진행한 **DocMIND 문서 구조화 및 검색 평가 실험**의 결과물입니다.

목표는 단순 PDF 검색이 아니라, 긴 GMP 문서를 다음과 같이 사용할 수 있게 만드는 것이었습니다.

1. PDF의 목차/본문 구조를 탐지해 **계층형 tree**로 만든다.
2. 각 section과 page 범위를 검증한다.
3. tree를 기반으로 질문별 근거 page를 찾는 검색 흐름을 만든다.
4. 100개 평가셋으로 검색 성능을 정량 평가한다.
5. 최종 결과를 공유 가능한 **단일 HTML 보고서**로 확인한다.

가장 먼저 볼 파일은 아래 A4 인쇄용 HTML 보고서입니다.

```text
results/reports/print/sample-analysis-report.html
```

기존 웹형 보고서는 아래 경로에 남아 있습니다.

```text
results/reports/gmp_pageindex_final_report.html
```

---

## A4 인쇄용 HTML 3종

| 파일 | 용도 |
| --- | --- |
| `results/reports/print/design-system.html` | 보고서 색상, 타이포그래피, 카드, 표, callout, print CSS 규칙 |
| `results/reports/print/report-template.html` | 다른 분석 보고서에 재사용 가능한 빈 템플릿 |
| `results/reports/print/sample-analysis-report.html` | GMP 실험 데이터를 반영한 최종 A4 인쇄용 샘플 보고서 |

각 파일은 A4 print CSS, 목차, page number 규칙, 표/카드/callout 스타일을 포함합니다.

---

## 1. 이 프로젝트에서 만든 것

| 산출물 | 설명 | 경로 |
| --- | --- | --- |
| 최종 A4 HTML 보고서 | 전체 과정, tree 시각화, eval 결과를 인쇄/PDF에 맞춰 정리한 보고서 | `results/reports/print/sample-analysis-report.html` |
| 최종 GMP tree JSON | 641개 node로 구성된 GMP 문서 계층 구조 | `results/gmp_guidance_structure.json` |
| ASCII tree | terminal/tree 형태의 전체 구조 시각화 | `results/visualizations/gmp_guidance_tree.txt` |
| HTML tree | 접었다 펼칠 수 있는 tree 시각화 | `results/visualizations/gmp_guidance_tree.html` |
| 100개 eval set | 검색 성능 평가용 질문/정답 page/section path | `eval/gmp_eval_testset.jsonl` |
| 최종 score | aligned hit rate, evidence+aligned 등 공식 평가 결과 | `results/page_alignment/score_001_100_agentic_official_alignment.json` |

---

## 2. 최종 결과 요약

| 항목 | 결과 |
| --- | ---: |
| 대상 문서 | `gmp_guidance.pdf` |
| PDF page 수 | 606 |
| 최종 tree node 수 | 641 |
| top-level branch 수 | 5 |
| eval 문항 수 | 100 |
| 공식 검색 성공률 | 96.0% |
| evidence+aligned 진단 coverage | 99.0% |
| 완전 미회수 문항 | `gmp_eval_025` 1건 |

이 프로젝트의 공식 성능 headline은 다음입니다.

```text
Aligned predicted union hit rate = 96.0%
```

즉, 100개 질문 중 96개에서 정답 근거 page를 최종 predicted page 또는 page alignment 보정 후 page 집합 안에서 찾았습니다.

---

## 3. 최종 보고서 열기

macOS:

```bash
open results/reports/print/sample-analysis-report.html
```

보고서에서 확인할 수 있는 내용:

- GMP PDF가 어떻게 workspace와 tree로 변환됐는지
- 최종 tree가 어떤 구조인지
- ASCII tree 전체 펼치기/접기
- 접이식 HTML tree
- 100개 eval의 정량 성능
- `Aligned hit rate`를 왜 도입했는지
- `Evidence+aligned hit`이 어떤 진단 의미를 가지는지
- 100개 문항을 검색/필터/선택해서 확인하는 eval browser

---

## 4. HTML 보고서 재생성

보고서 HTML은 아래 명령으로 다시 만들 수 있습니다.

```bash
python3 scripts/gmp_build_html_report.py
```

생성 결과:

```text
results/reports/gmp_pageindex_final_report.html
results/reports/print/design-system.html
results/reports/print/report-template.html
results/reports/print/sample-analysis-report.html
```

보고서 생성에 사용하는 주요 입력 파일:

| 파일 | 역할 |
| --- | --- |
| `results/pageindex_gmp_workspace/gmp-guidance.json` | PDF에서 추출한 page content와 초기 document structure |
| `results/gmp_guidance_structure.json` | 최종 보정된 GMP tree |
| `results/visualizations/gmp_guidance_tree.txt` | ASCII tree 원본 |
| `eval/gmp_eval_testset.jsonl` | 100개 평가셋 |
| `results/codex_agentic_10x10/predictions_001_100_agentic.jsonl` | 100개 문항에 대한 검색 예측 결과 |
| `results/page_alignment/score_001_100_agentic_official_alignment.json` | 최종 공식 score |

---

## 5. 검증 명령

아래 명령으로 주요 artifact와 HTML 보고서 생성이 정상인지 확인할 수 있습니다.

```bash
python3 scripts/gmp_build_html_report.py
python3 -m compileall pageindex scripts
python3 -m tabnanny scripts/gmp_build_html_report.py
```

보고서 생성 성공 시 다음과 유사한 요약이 출력됩니다.

```text
summary: nodes=641 pages=606 eval_rows=100 canonical=0.96 unresolved=1 browser_rows=100
```

---

## 6. 프로젝트 구조

```text
.
├── configs/
│   ├── gmp_all_branch_expansion_manifest.json
│   └── gmp_facility_expansion_manifest.json
├── eval/
│   └── gmp_eval_testset.jsonl
├── inputs/
│   ├── gmp_guidance.pdf
│   └── gmp_guidance_first12.pdf
├── results/
│   ├── gmp_guidance_structure.json
│   ├── pageindex_gmp_workspace/
│   ├── page_alignment/
│   ├── codex_agentic_10x10/
│   ├── visualizations/
│   │   ├── gmp_guidance_tree.txt
│   │   ├── gmp_guidance_tree.md
│   │   └── gmp_guidance_tree.html
│   └── reports/
│       └── gmp_pageindex_final_report.html
├── scripts/
│   ├── gmp_build_html_report.py
│   ├── gmp_pageindex_codex_retriever.py
│   ├── gmp_pageindex_codex_eval.py
│   ├── gmp_page_coordinate_alignment.py
│   ├── gmp_all_branch_validate.py
│   ├── gmp_expand_all_branches.py
│   └── gmp_targeted_expand.py
├── pageindex/
└── run_gmp_pageindex_codex.sh
```

---

## 7. Tree 구성 요약

최종 tree는 641개 node로 구성됩니다.

| Top-level branch | Node 수 | Subtree page range |
| --- | ---: | --- |
| Preface | 1 | 1-9 |
| 제1장 서론 | 3 | 9-16 |
| 제2장 완제의약품 제조 및 품질관리기준 | 531 | 16-478 |
| 별첨1 의약품 제조소의 시설 | 83 | 478-554 |
| 별첨2 컴퓨터화 시스템 | 23 | 554-606 |

각 node는 다음 정보를 가집니다.

- `node_id`: node 식별자
- `title`: section 제목
- `own_start_index`, `own_end_index`: 해당 node 자체 page 범위
- `subtree_start_index`, `subtree_end_index`: child를 포함한 전체 subtree page 범위
- `nodes`: child node 목록

전체 tree는 아래 파일에서 확인할 수 있습니다.

```text
results/visualizations/gmp_guidance_tree.txt
```

---

## 8. Eval metric 해석

### Aligned hit rate

질문별 gold page가 retriever의 최종 선택 page 안에 포함됐는지를 보는 공식 검색 성공률입니다.

이 지표를 도입한 이유는 GMP PDF에서 **PDF 물리 page**와 **문서 내부 page 번호**가 밀리는 구간이 있었기 때문입니다. 단순히 predicted page와 gold page를 그대로 비교하면, 실제로는 근거 위치를 찾았는데도 page 좌표계 차이 때문에 miss로 계산될 수 있습니다.

그래서 `page alignment map`을 만들고, 원래 predicted page와 alignment 보정 page를 함께 평가하는 `aligned predicted union`을 공식 기준으로 사용했습니다.

### Evidence+aligned hit

최종 predicted page뿐 아니라, retriever가 답을 고르기 전에 실제로 열어본 `evidence_pages_read`와 그 alignment 보정 page까지 포함해서 gold page가 있었는지 보는 진단 지표입니다.

도입 이유는 실패 원인을 분리하기 위해서입니다.

- **Aligned hit 실패 + Evidence+aligned hit 성공**: 근거 page는 읽었지만 최종 page selection에서 놓친 사례
- **Evidence+aligned hit 실패**: 근거 page 자체를 탐색 과정에서 찾지 못한 더 강한 실패 사례

따라서 공식 headline은 96.0%이고, Evidence+aligned 99.0%는 개선 방향을 찾기 위한 보조 지표입니다.

---

## 9. 사용한 기반 기술

이 프로젝트는 VectifyAI의 open-source PageIndex repository를 기반으로 진행했습니다.

- 원본 repository: https://github.com/VectifyAI/PageIndex
- 본 repo에서는 GMP 문서에 맞춰 tree 확장, page alignment, eval set, 검색 평가, 최종 HTML 보고서를 추가했습니다.

---

## 10. 주의 사항

- 이 저장소는 DocMIND GMP 문서 구조화/검색 평가 실험 결과를 공유하기 위한 public repo입니다.
- `.env`, `.venv`, logs, 임시 실행 결과는 포함하지 않습니다.
- 기본 HTML 보고서는 API key 없이 로컬 artifact만 읽습니다.
