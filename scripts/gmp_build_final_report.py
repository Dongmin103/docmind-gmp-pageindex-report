#!/usr/bin/env python3
"""Build the single-file A4 print-ready GMP DocMIND HTML report."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from html import escape
from pathlib import Path
import shutil
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "results" / "reports" / "print"

WORKSPACE = ROOT / "results" / "pageindex_gmp_workspace" / "gmp-guidance.json"
TREE = ROOT / "results" / "gmp_guidance_structure.json"
TREE_TXT = ROOT / "results" / "visualizations" / "gmp_guidance_tree.txt"
SCORE = ROOT / "results" / "page_alignment" / "score_001_100_agentic_official_alignment.json"
EVAL = ROOT / "eval" / "gmp_eval_testset.jsonl"
PREDICTIONS = ROOT / "results" / "codex_agentic_10x10" / "predictions_001_100_agentic.jsonl"
REPO_URL = "https://github.com/Dongmin103/docmind-gmp-pageindex-report"


def main() -> int:
    out_path = ROOT / "results" / "reports" / "final-report.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    data = load_report_data()
    html = render_sample_report(data)
    out_path.write_text(html, encoding="utf-8")
    # Final deliverable is one self-contained HTML file. Remove any previous intermediate report directory.
    legacy_dir = ROOT / "results" / "reports" / "print"
    if legacy_dir.exists():
        shutil.rmtree(legacy_dir)
    print(f"wrote {out_path.relative_to(ROOT)} ({out_path.stat().st_size:,} bytes)")
    return 0

def load_report_data() -> dict[str, Any]:
    workspace = read_json(WORKSPACE)
    tree = read_json(TREE)
    score = read_json(SCORE)
    eval_rows = read_jsonl(EVAL)
    predictions = read_jsonl(PREDICTIONS)
    flat_tree = list(walk(tree.get("structure") or []))
    top_rows = build_top_rows(tree.get("structure") or [])
    score_metrics = score.get("alignment_prediction_evaluation", {}).get("metrics") or {}
    score_items = score.get("alignment_prediction_evaluation", {}).get("items") or []
    notable_items = [item for item in score_items if item.get("classification") != "already_hit"]
    unrecovered = score.get("alignment_prediction_evaluation", {}).get("unrecovered_after_evidence_alignment") or []
    eval_browser_rows = build_eval_rows(eval_rows, predictions, score_items)
    tree_ascii = TREE_TXT.read_text(encoding="utf-8") if TREE_TXT.exists() else ""
    return {
        "workspace": workspace,
        "tree": tree,
        "score": score,
        "eval_rows": eval_rows,
        "flat_tree": flat_tree,
        "top_rows": top_rows,
        "score_metrics": score_metrics,
        "summary": score.get("summary") or {},
        "pageindex_flow": score.get("pageindex_flow") or {},
        "class_counts": Counter(score.get("alignment_prediction_evaluation", {}).get("classification_counts") or {}),
        "eval_difficulty": Counter(str(row.get("difficulty", "unknown")) for row in eval_rows),
        "eval_qtype": Counter(str(row.get("question_type", "unknown")) for row in eval_rows),
        "depth_counts": Counter(depth for _, depth, _ in flat_tree),
        "notable_items": notable_items,
        "unrecovered": unrecovered,
        "adversarial": score.get("adversarial_probes") or [],
        "eval_browser_rows": eval_browser_rows,
        "tree_ascii": tree_ascii,
        "generated": score.get("generated_at") or datetime.now(timezone.utc).isoformat(),
    }


def render_sample_report(data: dict[str, Any]) -> str:
    score_metrics = data["score_metrics"]
    canonical = float(score_metrics.get("aligned_predicted_union_hit_rate", 0.0))
    original = float(score_metrics.get("original_predicted_page_hit_rate", 0.0))
    diagnostic = float(score_metrics.get("evidence_plus_aligned_hit_rate", 0.0))
    workspace = data["workspace"]
    summary = data["summary"]
    status = data["score"].get("status", "UNKNOWN")
    generated = data["generated"]
    notable = data["notable_items"]
    unrecovered = data["unrecovered"]
    eval_rows = data["eval_browser_rows"]
    eval_json = json.dumps(eval_rows, ensure_ascii=False).replace("</", "<\\/")
    tree_lines = data["tree_ascii"].splitlines()

    body = f"""
    <section class="cover">
      <p class="eyebrow">DocMIND GMP Analysis Report</p>
      <h1>GMP 문서 구조화 및 검색 평가 최종 보고서</h1>
      <p class="lead">GMP 가이던스 PDF를 계층형 tree로 구조화하고, tree 기반 검색 흐름이 100개 평가셋에서 정답 근거 page를 얼마나 잘 찾는지 검증했습니다. 공식 headline 성능은 <strong>{pct(canonical)}</strong>입니다.</p>
      <div class="meta-grid">
        <div><span>대상 문서</span><strong>{esc(workspace.get('doc_name', 'gmp_guidance.pdf'))}</strong></div>
        <div><span>보고서 상태</span><strong>{esc(status)}</strong></div>
        <div><span>생성 시각</span><strong>{esc(str(generated))}</strong></div>
      </div>
      <div class="kpi-grid">
        {kpi('공식 hit rate', pct(canonical), 'Aligned predicted union')}
        {kpi('Eval 문항', str(summary.get('items', 100)), '100개 평가셋')}
        {kpi('Tree nodes', f"{len(data['flat_tree']):,}", f"{workspace.get('page_count')} pages")}
        {kpi('Unrecovered', str(len(unrecovered)), 'gmp_eval_025')}
      </div>
      <div class="cover-actions">
        <a class="report-button" href="../../inputs/gmp_guidance.pdf" target="_blank" rel="noopener">원문 GMP PDF 열기</a>
        <span class="small">보고서와 같은 repository에 포함된 원문 PDF입니다.</span>
      </div>
      <p class="source-line">Repository: <a href="{REPO_URL}">{REPO_URL}</a></p>
    </section>

    <nav class="toc">
      <h2>목차</h2>
      <ol>
        <li><a href="#background">배경</a></li>
        <li><a href="#summary">요약</a></li>
        <li><a href="#method">방법</a></li>
        <li><a href="#results">결과</a></li>
        <li><a href="#interpretation">해석</a></li>
        <li><a href="#limitations">한계</a></li>
        <li><a href="#next-steps">다음 단계</a></li>
        <li><a href="#artifacts">재현 가능한 산출물</a></li>
        <li><a href="#appendix-tree">부록 A. Tree 요약</a></li>
        <li><a href="#appendix-eval">부록 B. Eval 샘플</a></li>
      </ol>
    </nav>

    <section id="background" class="report-section page-break-before">
      <h2>1. 배경</h2>
      <div class="callout info"><strong>기준 레포:</strong> 본 실험은 VectifyAI의 <code>PageIndex</code> repository 구조를 기준으로 GMP PDF를 구조화하고 검색 평가까지 확장한 작업입니다.</div>
      <p><strong>왜 PageIndex를 기준으로 삼았나?</strong> GMP 가이던스처럼 길고 계층이 깊은 규제 문서는 단순 키워드 검색만으로는 원하는 근거 page를 안정적으로 찾기 어렵습니다. 질문은 보통 특정 단어 하나가 아니라 “어느 장/절의 어떤 기준을 확인해야 하는가”에 가깝기 때문에, 문서를 page 단위 텍스트 더미가 아니라 <strong>section tree + page range</strong>로 다루는 방식이 필요했습니다.</p>
      <p>PageIndex는 PDF를 page content와 document structure로 분리해 다루는 흐름을 제공합니다. 이 보고서에서는 그 구조를 GMP 문서에 적용하여, 먼저 목차와 본문 heading을 기반으로 문서 전체를 계층형 tree로 재구성했습니다. 이후 질문별로 <code>get_document</code>, <code>get_document_structure</code>, <code>get_page_content</code> 흐름을 따라 관련 section과 page content를 확인하는 방식으로 검색 성능을 평가했습니다.</p>
      <table>
        <thead><tr><th>구분</th><th>내용</th></tr></thead>
        <tbody>
          {tr('기준 repository', 'VectifyAI/PageIndex')}
          {tr('적용 대상', workspace.get('doc_name', 'GMP guidance PDF'))}
          {tr('핵심 목적', 'GMP 문서를 section tree로 구조화하고, 질문이 요구하는 근거 page를 찾을 수 있는지 검증')}
          {tr('실험 이유', '규제 문서는 제목·장·절·page 범위가 중요하므로 단순 검색보다 구조 기반 검색이 적합한지 확인')}
        </tbody>
      </table>
    </section>

    <section id="summary" class="report-section page-break-before">
      <h2>2. 요약</h2>
      <div class="callout result"><strong>핵심 결과:</strong> 606 page GMP PDF에서 641개 node의 계층형 tree를 구축했고, 100개 평가셋 기준 공식 aligned hit rate는 <strong>{pct(canonical)}</strong>입니다.</div>
      <p>본 작업은 GMP 문서를 단순 키워드 검색 대상으로 보지 않고, 목차와 본문 heading을 기반으로 section/page 범위가 보존된 tree로 재구성했습니다. 이후 질문별로 tree와 page content를 탐색해 정답 근거 page를 찾는 retrieval 평가를 수행했습니다.</p>
      <table>
        <thead><tr><th>항목</th><th>결과</th><th>의미</th></tr></thead>
        <tbody>
          {tr('PDF page 수', workspace.get('page_count'), '전체 문서 범위')}
          {tr('Tree node 수', len(data['flat_tree']), '최종 계층 구조 규모')}
          {tr('Eval 문항 수', summary.get('items', 100), '검색 평가셋')}
          {tr('공식 hit rate', pct(canonical), '최종 선택 page + alignment 보정 기준')}
          {tr('Evidence+aligned', pct(diagnostic), '탐색 과정 coverage 진단 지표')}
        </tbody>
      </table>
    </section>

    <section id="method" class="report-section">
      <h2>3. 방법</h2>
      <div class="method-flow">
        {step('01', 'PDF 구조화', 'GMP PDF를 PageIndex workspace로 변환해 page content와 초기 structure를 생성했습니다.')}
        {step('02', 'Tree 확장/보정', 'TOC와 본문 heading을 기준으로 모든 주요 branch를 세분화하고 page span을 정규화했습니다.')}
        {step('03', 'Page alignment', 'PDF 물리 page와 문서 내부 page 번호가 밀리는 문제를 audit하고 alignment map을 만들었습니다.')}
        {step('04', '100문항 eval', '질문별 gold page/section path와 predicted page를 비교해 official score를 계산했습니다.')}
      </div>
      <div class="callout info"><strong>평가 흐름:</strong> get_document → get_document_structure → get_page_content 흐름을 기준으로, tree를 보고 관련 section 후보를 고른 뒤 page content를 열어 최종 predicted page를 결정하는 방식입니다.</div>
      <h3>Retrieve 작동 방식</h3>
      <p>본 평가에서 retrieve는 PDF 전체를 한 번에 검색하는 방식이 아니라, PageIndex workspace에 저장된 <strong>문서 메타데이터, tree 구조, page content</strong>를 순서대로 확인하는 방식으로 작동합니다. 먼저 문서가 어떤 PDF인지 확인하고, 그 다음 JSON tree에서 질문과 관련된 section path와 page range를 좁힌 뒤, 필요한 page 본문만 열어 근거를 확인합니다.</p>
      <table>
        <thead><tr><th>단계</th><th>PageIndex tool</th><th>확인 내용</th><th>GMP 예시</th></tr></thead>
        <tbody>
          {tr_multi(['1', 'get_document()', '문서명, 타입, 전체 page 수 확인', 'gmp_guidance.pdf · 606 pages'])}
          {tr_multi(['2', 'get_document_structure()', '본문 text를 제외한 JSON tree 확인', '용어의 정의 · subtree p.18-28'])}
          {tr_multi(['3', 'section/page 후보 선택', '질문 의미에 맞는 section path와 tight page range 선택', '“일탈” 질문 → 용어의 정의 → p.18'])}
          {tr_multi(['4', 'get_page_content(pages)', '선택한 page의 실제 본문 확인', 'p.18에서 “일탈” 정의 문장 확인'])}
          {tr_multi(['5', 'prediction 기록', 'predicted_section_path, predicted_pages, evidence_pages_read 저장', 'predicted_pages: 18-19'])}
        </tbody>
      </table>
      <div class="callout neutral"><strong>Tree JSON의 핵심 속성:</strong> <code>title</code>은 section 제목, <code>nodes</code>는 하위 section, <code>own_start_index/end_index</code>는 해당 node 자체의 page 범위, <code>subtree_start_index/end_index</code>는 하위 section까지 포함한 전체 page 범위를 의미합니다.</div>
    </section>

    <section id="results" class="report-section">
      <h2>4. 결과</h2>
      <div class="grid-2">
        <div>
          <h3>공식 metric</h3>
          <table>
            <thead><tr><th>Metric</th><th>Value</th></tr></thead>
            <tbody>
              {tr('Original predicted page hit rate', pct(original))}
              {tr('Aligned predicted union hit rate', pct(canonical))}
              {tr('Evidence union hit rate', pct(float(score_metrics.get('evidence_union_hit_rate', 0.0))))}
              {tr('Evidence+aligned hit rate', pct(diagnostic))}
              {tr('Aligned precision avg', f"{float(score_metrics.get('aligned_predicted_union_precision_avg', 0.0)):.4f}")}
            </tbody>
          </table>
        </div>
        <div>
          <h3>Eval 분포</h3>
          {bar_table(data['eval_difficulty'], 'Difficulty')}
          {bar_table(data['eval_qtype'], 'Question type')}
        </div>
      </div>
      <h3>Retrieval classification</h3>
      {classification_table(data['class_counts'])}
    </section>

    <section id="interpretation" class="report-section">
      <h2>5. 해석</h2>
      <div class="callout info"><strong>Aligned hit rate 도입 배경:</strong> GMP PDF는 PDF 물리 page와 문서 내부 page 번호가 밀리는 구간이 있어, 단순 page 번호 비교만으로는 검색 성능이 왜곡될 수 있습니다. 따라서 page alignment map을 반영한 aligned predicted union을 공식 기준으로 사용했습니다.</div>
      <div class="callout warning"><strong>Evidence+aligned의 의미:</strong> {pct(diagnostic)}는 최종 선택 page가 아니라, retriever가 탐색 과정에서 읽은 evidence page까지 포함한 진단 coverage입니다. 공식 headline은 {pct(canonical)}로 유지합니다.</div>
      <p>잔여 오류는 크게 두 유형으로 나뉩니다. 첫째, 근거 page를 읽었지만 최종 page selection에서 놓친 사례입니다. 둘째, evidence 탐색 과정에서도 gold page를 찾지 못한 더 강한 실패입니다. 현재 완전 미회수 사례는 <code>gmp_eval_025</code> 1건입니다.</p>
    </section>

    <section id="limitations" class="report-section">
      <h2>6. 한계</h2>
      <ul>
        <li>평가셋은 100개 문항으로 구성되어 있어, 더 넓은 GMP 질의 유형을 모두 대표한다고 보기는 어렵습니다.</li>
        <li>Evidence+aligned는 내부 탐색 coverage를 보여주는 진단 지표이며, 최종 사용자에게 반환되는 page 선택 성능과 동일하지 않습니다.</li>
        <li>Tree 구조는 현재 PDF와 산출물 기준으로 검증되었으며, 다른 개정본 PDF에는 page alignment와 tree boundary를 다시 확인해야 합니다.</li>
      </ul>
    </section>

    <section id="next-steps" class="report-section">
      <h2>7. 다음 단계</h2>
      <ol>
        <li><strong>실패 4건 상세 분석:</strong> aligned miss 4건의 원인을 page selection, evidence 탐색, semantic confusion으로 분류합니다.</li>
        <li><strong>평가셋 확장:</strong> 100개에서 더 다양한 장/절/질문 유형으로 확장합니다.</li>
        <li><strong>보고서 배포:</strong> 본 HTML을 브라우저 print/PDF로 내보내 외부 공유용 PDF를 생성합니다.</li>
      </ol>
    </section>

    <section id="artifacts" class="report-section">
      <h2>8. 재현 가능한 산출물</h2>
      <p>본 보고서는 아래 repository artifact를 기준으로 재생성할 수 있습니다.</p>
      <table>
        <thead><tr><th>Artifact</th><th>역할</th></tr></thead>
        <tbody>
          {tr('results/pageindex_gmp_workspace/gmp-guidance.json', 'PageIndex workspace')}
          {tr('results/gmp_guidance_structure.json', '최종 tree JSON')}
          {tr('results/visualizations/gmp_guidance_tree.txt', 'ASCII tree 원본')}
          {tr('eval/gmp_eval_testset.jsonl', '100개 평가셋')}
          {tr('results/codex_agentic_10x10/predictions_001_100_agentic.jsonl', '검색 예측 결과')}
          {tr('results/page_alignment/score_001_100_agentic_official_alignment.json', '최종 official score')}
          {tr('scripts/gmp_build_final_report.py', 'single-file HTML 생성 스크립트')}
        </tbody>
      </table>
    </section>

    <section id="appendix-tree" class="report-section page-break-before">
      <h2>부록 A. Tree 요약</h2>
      <p class="section-note">전체 tree를 긴 표로만 보지 않도록, 최상위 branch의 문서 범위와 node 밀도를 먼저 보여줍니다. 아래 막대는 각 branch가 차지하는 page span을 기준으로 상대 크기를 표현합니다.</p>
      {render_icicle_svg(data)}
      {render_collapsible_tree(data)}
      {tree_overview(data)}
      <table>
        <thead><tr><th>Top branch</th><th>Nodes</th><th>Max depth</th><th>Own pages</th><th>Subtree pages</th></tr></thead>
        <tbody>{''.join(tr_multi([r['title'], r['nodes'], r['max_depth'], r['own_range'], r['subtree_range']]) for r in data['top_rows'])}</tbody>
      </table>
      <h3>Technical ASCII tree</h3>
      <div class="tree-toolbar screen-only">
        <button class="plain-button secondary" type="button" data-toggle-target="ascii-tree" data-toggle-label="ASCII tree">ASCII tree 전체 펼치기</button>
        <span class="small">ASCII는 원본 구조 확인용 기술 부록입니다. 일반 검토는 위의 Document map과 Tree explorer를 사용합니다.</span>
      </div>
      <pre id="ascii-tree" class="ascii-excerpt" aria-label="GMP PageIndex ASCII tree">{esc('\n'.join(tree_lines))}</pre>
    </section>

    <section id="appendix-eval" class="report-section">
      <h2>부록 B. Eval 100문항 브라우저 및 실패 사례</h2>
      <p class="section-note">100개 문항을 모두 본문에 펼치면 인쇄 레이아웃이 깨지므로, 화면에서는 토글/필터로 전체 문항을 확인하고 PDF에서는 요약 표와 실패 사례 중심으로 읽을 수 있게 구성했습니다.</p>
      {eval_browser(eval_json)}
      <h3>주요 실패/보정 사례</h3>
      {notable_table(notable)}
      <h3>평가 문항 예시</h3>
      {eval_sample_table(eval_rows)}
    </section>
    """
    return document("GMP 문서 구조화 및 검색 평가 최종 보고서", body, subtitle="A4 print-ready sample report", doc_type="sample-report")


def document(title: str, body: str, subtitle: str, doc_type: str) -> str:
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{esc(title)}</title>
  <style>{base_css()}</style>
</head>
<body class="{esc(doc_type)}">
  <article class="report-paper">
    {body}
  </article>
  <script>{inline_js()}</script>
</body>
</html>
"""


def base_css() -> str:
    return r"""
:root {
  --ink: #18202b;
  --muted: #5d6878;
  --subtle: #8a94a3;
  --line: #d9dee7;
  --panel: #f7f9fc;
  --panel-strong: #eef3f9;
  --accent: #234f7d;
  --accent-soft: #e7eff8;
  --success: #1f6f4a;
  --warning: #8a5a12;
  --danger: #a13c3c;
  --paper: #ffffff;
  --mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
  --sans: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans KR", "Apple SD Gothic Neo", Arial, sans-serif;
}
* { box-sizing: border-box; }
html { color: var(--ink); font-family: var(--sans); font-size: 11pt; line-height: 1.58; background: #edf0f4; }
body { margin: 0; }
a { color: var(--accent); text-decoration: none; }
button, input, select { font: inherit; }
.report-paper { max-width: 210mm; min-height: 297mm; margin: 18px auto; background: var(--paper); padding: 18mm 16mm 20mm; box-shadow: 0 10px 30px rgba(20, 30, 45, .12); }
.cover { border-bottom: 2px solid var(--ink); padding-bottom: 10mm; margin-bottom: 9mm; }
.cover.compact { min-height: auto; }
.eyebrow { color: var(--accent); font-weight: 800; letter-spacing: .08em; text-transform: uppercase; font-size: 9pt; margin: 0 0 4mm; }
h1 { font-size: 26pt; line-height: 1.16; letter-spacing: -0.04em; margin: 0 0 5mm; }
.demo-h1 { font-size: 22pt; }
h2 { font-size: 16pt; line-height: 1.25; margin: 0 0 5mm; letter-spacing: -0.025em; }
h3 { font-size: 12.5pt; margin: 6mm 0 2.5mm; }
h4 { font-size: 10.5pt; margin: 4mm 0 1.5mm; }
p { margin: 0 0 4mm; }
.lead { color: #2f3a48; font-size: 12.5pt; max-width: 170mm; }
.source-line { font-size: 9pt; color: var(--muted); margin-top: 6mm; }
.cover-actions { display: flex; align-items: center; gap: 3mm; margin-top: 6mm; flex-wrap: wrap; }
.report-button { display: inline-flex; align-items: center; justify-content: center; border: 1px solid var(--accent); background: var(--accent); color: #fff; border-radius: 2mm; padding: 2.2mm 4mm; font-weight: 800; font-size: 9.5pt; }
.report-button:hover { background: #183b61; }
.meta-grid, .kpi-grid, .grid-2 { display: grid; gap: 4mm; }
.meta-grid { grid-template-columns: repeat(3, 1fr); margin-top: 8mm; }
.meta-grid div, .kpi, .card, .callout { break-inside: avoid; }
.meta-grid div { border-top: 1px solid var(--line); padding-top: 3mm; }
.meta-grid span, .kpi span { display: block; color: var(--muted); font-size: 8.5pt; font-weight: 700; text-transform: uppercase; letter-spacing: .04em; }
.meta-grid strong { display: block; margin-top: 1mm; font-size: 10.5pt; }
.kpi-grid { grid-template-columns: repeat(4, 1fr); margin: 8mm 0 0; }
.kpi { border: 1px solid var(--line); background: var(--panel); padding: 4mm; border-radius: 3mm; }
.kpi strong { display: block; font-size: 20pt; letter-spacing: -0.04em; margin: 1.5mm 0; }
.report-section { margin: 0 0 9mm; break-inside: auto; }
.section-note { color: var(--muted); font-size: 9.3pt; margin-top: -1mm; }
.page-break-before { break-before: page; }
.toc { border: 1px solid var(--line); background: var(--panel); padding: 6mm; margin: 0 0 10mm; break-inside: avoid; }
.toc h2 { margin-bottom: 3mm; }
.toc ol { columns: 2; margin: 0; padding-left: 5mm; }
.toc li { margin: 0 0 1.5mm; }
.grid-2 { grid-template-columns: 1fr 1fr; align-items: start; }
.card { border: 1px solid var(--line); border-radius: 3mm; background: var(--panel); padding: 4mm; }
.callout { border-left: 4px solid var(--accent); background: var(--accent-soft); padding: 4mm; margin: 4mm 0; border-radius: 0 2mm 2mm 0; }
.callout.warning { border-left-color: var(--warning); background: #fbf4e6; }
.callout.result { border-left-color: var(--success); background: #eaf6ef; }
.callout.neutral { border-left-color: var(--muted); background: var(--panel); }
.method-flow { display: grid; grid-template-columns: repeat(4, 1fr); gap: 3mm; margin: 4mm 0; }
.step { border: 1px solid var(--line); border-radius: 3mm; padding: 4mm; background: #fff; break-inside: avoid; }
.step-num { display: inline-flex; align-items: center; justify-content: center; width: 8mm; height: 8mm; border-radius: 50%; background: var(--ink); color: #fff; font-weight: 800; font-size: 8pt; margin-bottom: 2mm; }
table { width: 100%; border-collapse: collapse; margin: 3mm 0 6mm; break-inside: avoid; font-size: 9.4pt; }
thead { display: table-header-group; }
th, td { border: 1px solid var(--line); padding: 2.4mm 2.8mm; vertical-align: top; overflow-wrap: anywhere; word-break: keep-all; }
th { background: var(--panel-strong); color: #303a48; font-size: 8.5pt; letter-spacing: .035em; text-transform: uppercase; text-align: left; }
tbody tr:nth-child(even) td { background: #fbfcfe; }
code, pre { font-family: var(--mono); }
code { background: var(--panel); border: 1px solid var(--line); border-radius: 1.5mm; padding: 0 .8mm; font-size: 9pt; }
.icicle-panel { border: 1px solid var(--line); border-radius: 3mm; background: #fff; padding: 4mm; margin: 3mm 0 5mm; break-inside: avoid; }
.icicle-panel h3 { margin-top: 0; }
.icicle-caption { color: var(--muted); font-size: 8.8pt; margin-bottom: 2mm; }
.icicle-svg-wrap { width: 100%; overflow: hidden; border: 1px solid var(--line); border-radius: 2mm; background: #fbfcfe; }
.icicle-svg { display: block; width: 100%; height: auto; }
.icicle-axis { fill: var(--muted); font: 10px var(--sans); }
.icicle-label { fill: #111827; font: 10px var(--sans); pointer-events: none; }
.icicle-label.light { fill: #fff; font-weight: 700; }
.icicle-legend { display: flex; flex-wrap: wrap; gap: 2mm 4mm; margin-top: 2.5mm; color: var(--muted); font-size: 8.4pt; }
.icicle-key { display: inline-flex; align-items: center; gap: 1.5mm; }
.icicle-swatch { width: 4mm; height: 3mm; border-radius: .8mm; border: 1px solid rgba(0,0,0,.12); }
.tree-explorer-panel { border: 1px solid var(--line); border-radius: 3mm; background: #fff; padding: 4mm; margin: 3mm 0 5mm; break-inside: avoid; }
.tree-explorer-panel h3 { margin-top: 0; }
.tree-explorer-meta { display: flex; flex-wrap: wrap; gap: 2mm; margin: 2mm 0 3mm; }
.tree-explorer-wrap { border: 1px solid var(--line); border-radius: 2mm; background: #fbfcfe; padding: 3mm; max-height: 118mm; overflow: auto; }
.tree-explorer details { margin: 1.2mm 0 1.2mm 4mm; border-left: 1px solid #e1e7ef; padding-left: 2.5mm; }
.tree-explorer details[open] > summary { background: #eef3f9; }
.tree-explorer summary { cursor: pointer; list-style-position: outside; border-radius: 1.5mm; padding: 1.1mm 1.5mm; line-height: 1.35; }
.tree-explorer summary:hover { background: #f1f5f9; }
.tree-node-title { font-weight: 750; }
.tree-node-muted { color: var(--muted); font-size: 8.1pt; }
.tree-badge { display: inline-block; margin-left: 1mm; border: 1px solid var(--line); border-radius: 999px; padding: .3mm 1.3mm; background: #fff; color: var(--muted); font-size: 7.7pt; font-weight: 650; white-space: nowrap; }
.tree-badge.page { color: var(--accent); border-color: #bfd0e4; background: #f3f7fc; }
.tree-leaf { margin: .8mm 0 .8mm 7mm; padding: .8mm 1.5mm; border-left: 1px solid #e1e7ef; line-height: 1.35; }
.tree-overview { border: 1px solid var(--line); border-radius: 3mm; background: var(--panel); padding: 4mm; margin: 3mm 0 5mm; break-inside: avoid; }
.tree-map { display: grid; gap: 2.3mm; margin-top: 2mm; }
.tree-branch { display: grid; grid-template-columns: 45mm 1fr 32mm; align-items: center; gap: 3mm; }
.tree-branch-title { font-weight: 800; line-height: 1.3; }
.tree-branch-meta { color: var(--muted); font-size: 8.4pt; margin-top: .7mm; }
.tree-branch-bar { height: 8mm; border: 1px solid #ccd5e2; border-radius: 999px; overflow: hidden; background: #fff; }
.tree-branch-fill { height: 100%; min-width: 2mm; background: linear-gradient(90deg, #234f7d, #8eb1d4); }
.tree-branch-stat { text-align: right; color: var(--muted); font-size: 8.8pt; }
.depth-strip { display: grid; grid-template-columns: repeat(8, 1fr); gap: 1.2mm; margin-top: 4mm; }
.depth-cell { border: 1px solid var(--line); background: #fff; border-radius: 2mm; padding: 2mm; text-align: center; }
.depth-cell strong { display: block; font-size: 12pt; }
.depth-cell span { color: var(--muted); font-size: 8pt; }
.tree-toolbar { display: flex; align-items: center; gap: 3mm; margin: 2mm 0; }
.plain-button { border: 1px solid var(--accent); background: var(--accent); color: #fff; border-radius: 2mm; padding: 1.8mm 3mm; cursor: pointer; }
.plain-button.secondary { background: #fff; color: var(--accent); }
.ascii-excerpt { display: block; width: 100%; max-width: 100%; white-space: pre; overflow: auto; border: 1px solid var(--line); background: #101820; color: #e5edf7; padding: 4mm; border-radius: 2mm; font-size: 7.0pt; line-height: 1.32; max-height: 95mm; overflow-wrap: normal; word-break: normal; tab-size: 2; }
.ascii-excerpt.expanded { max-height: none; overflow: auto; }
.eval-browser { border: 1px solid var(--line); border-radius: 3mm; background: var(--panel); padding: 4mm; margin: 4mm 0 6mm; break-inside: avoid; }
.eval-controls { display: grid; grid-template-columns: 1.35fr repeat(3, minmax(24mm, 1fr)); gap: 2mm; margin-bottom: 3mm; }
.eval-controls label { display: grid; gap: .8mm; color: var(--muted); font-size: 8.3pt; font-weight: 700; }
.eval-controls input, .eval-controls select { width: 100%; border: 1px solid var(--line); background: #fff; border-radius: 2mm; padding: 1.8mm 2mm; color: var(--ink); }
.eval-status { display: flex; justify-content: space-between; align-items: center; gap: 3mm; margin: 2mm 0; color: var(--muted); font-size: 8.8pt; }
.eval-table-wrap { max-height: 82mm; overflow: auto; border: 1px solid var(--line); border-radius: 2mm; background: #fff; }
.eval-table { margin: 0; table-layout: fixed; font-size: 8.2pt; }
.eval-table th, .eval-table td { padding: 1.8mm 2mm; }
.eval-table tbody tr { cursor: pointer; }
.eval-table tbody tr.is-selected td { background: #e7eff8; }
.eval-detail { margin-top: 3mm; background: #fff; border: 1px solid var(--line); border-radius: 2mm; padding: 3mm; overflow-wrap: anywhere; }
.eval-detail-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 2mm; margin: 2mm 0; }
.eval-pill { display: inline-block; border: 1px solid var(--line); border-radius: 999px; padding: .6mm 1.8mm; background: var(--panel); margin: 0 1mm 1mm 0; font-size: 8pt; }
.bar-row { display: grid; grid-template-columns: 32mm 1fr 12mm; align-items: center; gap: 2mm; margin: 1.4mm 0; font-size: 9pt; }
.bar-track { height: 3mm; background: #e3e8f0; border-radius: 999px; overflow: hidden; }
.bar-fill { height: 100%; background: var(--accent); }
.small { font-size: 8.5pt; color: var(--muted); }
.screen-only { display: initial; }
ul, ol { margin-top: 0; padding-left: 5mm; }
li { margin-bottom: 1.8mm; }
@page {
  size: A4;
  margin: 16mm 14mm 18mm;
  @bottom-center { content: "Page " counter(page) " / " counter(pages); font-size: 8pt; color: #6b7280; }
}
@media print {
  html { background: #fff; font-size: 10.5pt; }
  body { background: #fff; }
  .report-paper { margin: 0; padding: 0; box-shadow: none; max-width: none; min-height: auto; }
  a { color: inherit; text-decoration: none; }
  .cover { min-height: 238mm; display: flex; flex-direction: column; justify-content: center; }
  .cover.compact { min-height: auto; display: block; }
  .report-section, .toc, .card, .callout, .kpi, table, .step { break-inside: avoid; }
  .method-flow { grid-template-columns: repeat(2, 1fr); }
  .screen-only { display: none !important; }
  .ascii-excerpt { max-height: 85mm; overflow: hidden; font-size: 6.6pt; break-inside: avoid; }
  .ascii-excerpt.expanded { max-height: 85mm; overflow: hidden; }
  .tree-explorer-wrap { max-height: 95mm; overflow: hidden; }
  .tree-explorer details details details { display: none; }
  .eval-browser { break-inside: auto; }
  .eval-controls { display: none; }
  .eval-table-wrap { max-height: none; overflow: visible; }
  .eval-table tbody tr:nth-child(n+21) { display: none; }
  .eval-detail { break-inside: avoid; }
}
@media screen and (min-width: 901px) {
  .report-paper { width: calc(100vw - 48px); max-width: 1180px; padding: 36px 42px 48px; }
}
@media screen and (max-width: 900px) {
  .report-paper { margin: 0; padding: 20px; max-width: none; }
  .meta-grid, .kpi-grid, .grid-2, .method-flow, .eval-controls, .tree-branch, .eval-detail-grid { grid-template-columns: 1fr; }
  .toc ol { columns: 1; }
  .tree-branch-stat { text-align: left; }
}
"""


def inline_js() -> str:
    return r"""
(function () {
  function text(value) {
    if (Array.isArray(value)) return value.join(" > ");
    return value == null ? "" : String(value);
  }
  function html(value) {
    return text(value).replace(/[&<>"']/g, function (ch) {
      return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch];
    });
  }
  function pill(label, value) {
    return '<span class="eval-pill"><strong>' + html(label) + '</strong> ' + html(value) + '</span>';
  }
  function optionize(select, rows, key) {
    if (!select) return;
    Array.from(new Set(rows.map(function (row) { return text(row[key]); }).filter(Boolean))).sort().forEach(function (value) {
      var opt = document.createElement("option");
      opt.value = value;
      opt.textContent = value;
      select.appendChild(opt);
    });
  }
  function setupAsciiToggle() {
    document.querySelectorAll("[data-toggle-target]").forEach(function (button) {
      button.addEventListener("click", function () {
        var target = document.getElementById(button.getAttribute("data-toggle-target"));
        if (!target) return;
        target.classList.toggle("expanded");
        var label = button.getAttribute("data-toggle-label") || "영역";
        button.textContent = label + (target.classList.contains("expanded") ? " 접기" : " 전체 펼치기");
      });
    });
  }
  function setupEvalBrowser() {
    var dataEl = document.getElementById("eval-data");
    if (!dataEl) return;
    var rows = [];
    try { rows = JSON.parse(dataEl.textContent || "[]"); } catch (err) { rows = []; }
    var state = { selected: rows[0] ? rows[0].id : "" };
    var controls = {
      search: document.getElementById("eval-search"),
      difficulty: document.getElementById("eval-difficulty"),
      hit: document.getElementById("eval-hit"),
      select: document.getElementById("eval-select"),
      count: document.getElementById("eval-count"),
      tbody: document.getElementById("eval-tbody"),
      detail: document.getElementById("eval-detail")
    };
    optionize(controls.difficulty, rows, "difficulty");
    rows.forEach(function (row) {
      var opt = document.createElement("option");
      opt.value = row.id;
      opt.textContent = row.id + " · " + text(row.question).slice(0, 42);
      controls.select.appendChild(opt);
    });
    function isVisible(row) {
      var q = text(controls.search && controls.search.value).trim().toLowerCase();
      var blob = [
        row.id, row.question, row.difficulty, row.classification,
        row.gold_pages, row.predicted_pages, row.aligned_predicted_pages,
        row.evidence_pages_read, row.evidence_plus_aligned_pages,
        row.gold_section_path, row.predicted_section_path, row.expected_answer
      ].map(text).join(" ").toLowerCase();
      if (q && blob.indexOf(q) === -1) return false;
      if (controls.difficulty.value && text(row.difficulty) !== controls.difficulty.value) return false;
      if (controls.hit.value === "aligned-hit" && !row.aligned_hit) return false;
      if (controls.hit.value === "aligned-miss" && row.aligned_hit) return false;
      if (controls.hit.value === "evidence-hit" && !row.evidence_hit) return false;
      if (controls.hit.value === "evidence-miss" && row.evidence_hit) return false;
      return true;
    }
    function renderDetail(row) {
      if (!row) {
        controls.detail.innerHTML = '<p class="small">선택된 문항이 없습니다.</p>';
        return;
      }
      controls.detail.innerHTML =
        '<h3>' + html(row.id) + ' · ' + html(row.question) + '</h3>' +
        '<div class="eval-detail-grid">' +
          '<div>' + pill("Gold", row.gold_pages) + pill("Pred", row.predicted_pages) + pill("Aligned", row.aligned_predicted_pages) + '</div>' +
          '<div>' + pill("Aligned hit", row.aligned_hit ? "hit" : "miss") + pill("Evidence+aligned", row.evidence_hit ? "hit" : "miss") + '</div>' +
          '<div>' + pill("Difficulty", row.difficulty) + '</div>' +
        '</div>' +
        '<p><strong>Gold section:</strong> ' + html(row.gold_section_path) + '</p>' +
        '<p><strong>Predicted section:</strong> ' + html(row.predicted_section_path) + '</p>' +
        '<p><strong>Evidence pages read:</strong> ' + html(row.evidence_pages_read) + ' / <strong>Evidence+aligned:</strong> ' + html(row.evidence_plus_aligned_pages) + '</p>' +
        '<p><strong>Expected answer:</strong> ' + html(row.expected_answer) + '</p>' +
        '<p><strong>Gold evidence summary:</strong> ' + html(row.gold_evidence_summary) + '</p>' +
        '<p><strong>Retriever reason:</strong> ' + html(row.reason) + '</p>';
    }
    function render() {
      var visible = rows.filter(isVisible);
      if (!visible.some(function (row) { return row.id === state.selected; })) {
        state.selected = visible[0] ? visible[0].id : "";
      }
      if (controls.count) controls.count.textContent = visible.length + " / " + rows.length + "개 문항 표시";
      if (controls.select) controls.select.value = state.selected;
      controls.tbody.innerHTML = visible.map(function (row) {
        var hit = row.aligned_hit ? "aligned hit" : (row.evidence_hit ? "evidence only" : "miss");
        return '<tr data-id="' + html(row.id) + '" class="' + (row.id === state.selected ? "is-selected" : "") + '">' +
          '<td>' + html(row.id) + '</td><td>' + html(row.difficulty) + '</td>' +
          '<td>' + html(hit) + '</td><td>' + html(row.gold_pages) + '</td><td>' + html(row.question) + '</td></tr>';
      }).join("");
      renderDetail(rows.find(function (row) { return row.id === state.selected; }) || visible[0]);
      controls.tbody.querySelectorAll("tr").forEach(function (tr) {
        tr.addEventListener("click", function () {
          state.selected = tr.getAttribute("data-id");
          render();
        });
      });
    }
    [controls.search, controls.difficulty, controls.hit].forEach(function (el) {
      if (el) el.addEventListener("input", render);
    });
    if (controls.select) controls.select.addEventListener("change", function () {
      state.selected = controls.select.value;
      render();
    });
    render();
  }
  setupAsciiToggle();
  setupEvalBrowser();
})();
"""


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(path)
    return payload


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def children(node: dict[str, Any]) -> list[dict[str, Any]]:
    kids = node.get("nodes") or node.get("children") or []
    return kids if isinstance(kids, list) else []


def walk(nodes: Iterable[dict[str, Any]], depth: int = 0, parent_path: tuple[str, ...] = ()):  # noqa: ANN201
    for node in nodes:
        path = parent_path + (str(node.get("title", "Untitled")),)
        yield node, depth, path
        yield from walk(children(node), depth + 1, path)


def node_range(node: dict[str, Any]) -> tuple[Any, Any, Any, Any]:
    own_start = node.get("own_start_index", node.get("start_index"))
    own_end = node.get("own_end_index", node.get("end_index"))
    subtree_start = node.get("subtree_start_index", own_start)
    subtree_end = node.get("subtree_end_index", own_end)
    return own_start, own_end, subtree_start, subtree_end


def build_top_rows(top_nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for node in top_nodes:
        sub = list(walk([node]))
        own_start, own_end, subtree_start, subtree_end = node_range(node)
        subtree_span = range_span(subtree_start, subtree_end)
        rows.append({
            "title": node.get("title", ""),
            "nodes": len(sub),
            "max_depth": max((depth for _, depth, _ in sub), default=0),
            "own_range": fmt_range(own_start, own_end),
            "subtree_range": fmt_range(subtree_start, subtree_end),
            "subtree_span": subtree_span,
        })
    return rows


def build_eval_rows(eval_rows: list[dict[str, Any]], predictions: list[dict[str, Any]], score_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pred_by_id = {str(row.get("id")): row for row in predictions}
    score_by_id = {str(row.get("id")): row for row in score_items}
    out: list[dict[str, Any]] = []
    for row in eval_rows:
        row_id = str(row.get("id", ""))
        pred = pred_by_id.get(row_id, {})
        score_row = score_by_id.get(row_id, {})
        out.append({
            "id": row_id,
            "question": row.get("question", ""),
            "difficulty": row.get("difficulty", ""),
            "question_type": row.get("question_type", ""),
            "expected_answer": row.get("expected_answer", ""),
            "gold_section_path": row.get("gold_section_path", []),
            "gold_section_title": row.get("gold_section_title", ""),
            "gold_evidence_summary": row.get("gold_evidence_summary", ""),
            "answer_judging_notes": row.get("answer_judging_notes", ""),
            "classification": score_row.get("classification", "missing_score_item"),
            "gold_pages": row.get("gold_pages", ""),
            "predicted_pages": score_row.get("predicted_pages", pred.get("predicted_pages", "")),
            "predicted_section_path": pred.get("predicted_section_path", []),
            "aligned_predicted_pages": score_row.get("aligned_predicted_pages", ""),
            "evidence_pages_read": score_row.get("evidence_pages_read", pred.get("evidence_pages_read", "")),
            "evidence_plus_aligned_pages": score_row.get("evidence_plus_aligned_pages", ""),
            "reason": pred.get("reason", ""),
            "original_hit": bool((score_row.get("original_page_metrics") or {}).get("hit")),
            "aligned_hit": bool((score_row.get("aligned_predicted_union_metrics") or {}).get("hit")),
            "evidence_hit": bool((score_row.get("evidence_plus_aligned_metrics") or {}).get("hit")),
        })
    return out


def kpi(label: str, value: str, note: str) -> str:
    return f"<div class=\"kpi\"><span>{esc(label)}</span><strong>{esc(value)}</strong><em>{esc(note)}</em></div>"


def step(num: str, title: str, text: str) -> str:
    return f"<div class=\"step\"><div class=\"step-num\">{esc(num)}</div><h3>{esc(title)}</h3><p>{esc(text)}</p></div>"


def tr(label: Any, value: Any, note: Any = "") -> str:
    return f"<tr><td>{esc(label)}</td><td><strong>{esc(value)}</strong></td>{'<td>'+esc(note)+'</td>' if note != '' else ''}</tr>"


def tr_multi(values: list[Any]) -> str:
    return "<tr>" + "".join(f"<td>{esc(v)}</td>" for v in values) + "</tr>"


def bar_table(counter: Counter, title: str) -> str:
    items = sorted(counter.items(), key=lambda x: (-x[1], str(x[0])))
    max_count = max((int(v) for _, v in items), default=1)
    rows = [f"<h4>{esc(title)}</h4>"]
    for key, count in items:
        width = int(count) / max_count * 100
        rows.append(f"<div class=\"bar-row\"><span>{esc(key)}</span><div class=\"bar-track\"><div class=\"bar-fill\" style=\"width:{width:.1f}%\"></div></div><strong>{int(count)}</strong></div>")
    return "".join(rows)


def classification_table(counter: Counter) -> str:
    body = "".join(tr_multi([key, count]) for key, count in sorted(counter.items(), key=lambda x: (-x[1], str(x[0]))))
    return f"<table><thead><tr><th>Classification</th><th>Count</th></tr></thead><tbody>{body}</tbody></table>"


def render_icicle_svg(data: dict[str, Any]) -> str:
    nodes = data["tree"].get("structure") or []
    page_count = int(data["workspace"].get("page_count") or 606)
    flat = list(walk(nodes))
    max_depth = max((depth for _, depth, _ in flat), default=0)
    width = 1000
    left = 46
    right = 18
    top = 32
    row_h = 31
    gap = 3
    plot_w = width - left - right
    height = top + row_h * (max_depth + 1) + 42
    palette = ["#234f7d", "#2f6f56", "#8a5a12", "#7c4d8b", "#a13c3c", "#4a647a"]
    top_titles = [str(node.get("title", "Untitled")) for node in nodes]
    color_by_top = {title: palette[idx % len(palette)] for idx, title in enumerate(top_titles)}

    def x_pos(page: Any) -> float:
        page_num = clamp_int(page, 1, page_count)
        return left + ((page_num - 1) / max(page_count - 1, 1)) * plot_w

    rects: list[str] = []
    label_count = 0
    for node, depth, path in flat:
        _, _, subtree_start, subtree_end = node_range(node)
        if subtree_start in (None, "") or subtree_end in (None, ""):
            continue
        start = clamp_int(subtree_start, 1, page_count)
        end = clamp_int(subtree_end, start, page_count)
        x = x_pos(start)
        x_end = x_pos(end) + max(plot_w / page_count, 1.0)
        rect_w = max(x_end - x, 1.2)
        y = top + depth * row_h
        top_title = path[0] if path else str(node.get("title", "Untitled"))
        color = color_by_top.get(top_title, "#234f7d")
        opacity = max(0.28, 0.92 - depth * 0.09)
        title = str(node.get("title", "Untitled"))
        range_label = fmt_range(start, end)
        stroke = "#ffffff" if depth > 0 else "#d4dce8"
        rects.append(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{rect_w:.2f}" height="{row_h-gap:.2f}" '
            f'rx="3" fill="{color}" fill-opacity="{opacity:.2f}" stroke="{stroke}" stroke-width="0.8">'
            f'<title>{esc(" > ".join(path))} · p.{esc(range_label)}</title></rect>'
        )
        min_label_w = 58 if depth <= 1 else 86
        if depth <= 2 and rect_w >= min_label_w and label_count < 55:
            max_chars = max(int(rect_w / 6.4), 5)
            label = truncate(title, max_chars)
            klass = "icicle-label light" if depth == 0 else "icicle-label"
            rects.append(f'<text class="{klass}" x="{x + 5:.2f}" y="{y + 18:.2f}">{esc(label)}</text>')
            label_count += 1

    axes = []
    for page in [1, 100, 200, 300, 400, 500, page_count]:
        x = x_pos(page)
        axes.append(f'<line x1="{x:.2f}" y1="22" x2="{x:.2f}" y2="{height-28}" stroke="#d9dee7" stroke-width="0.8"/>')
        axes.append(f'<text class="icicle-axis" x="{x:.2f}" y="18" text-anchor="middle">p.{page}</text>')
    for depth in range(max_depth + 1):
        y = top + depth * row_h + 18
        axes.append(f'<text class="icicle-axis" x="4" y="{y:.2f}">D{depth}</text>')

    legend = "".join(
        f'<span class="icicle-key"><span class="icicle-swatch" style="background:{color_by_top[title]}"></span>{esc(title)}</span>'
        for title in top_titles
    )
    return f"""
      <div class="icicle-panel">
        <h3>Document map: page span × tree depth</h3>
        <p class="icicle-caption">가로축은 PDF page 범위, 세로축은 tree depth입니다. 넓은 사각형일수록 해당 section subtree가 문서에서 차지하는 page span이 크다는 뜻입니다.</p>
        <div class="icicle-svg-wrap">
          <svg class="icicle-svg" viewBox="0 0 {width} {height}" role="img" aria-label="GMP document tree icicle map">
            <rect x="0" y="0" width="{width}" height="{height}" fill="#fbfcfe"/>
            {''.join(axes)}
            {''.join(rects)}
          </svg>
        </div>
        <div class="icicle-legend">{legend}</div>
      </div>
    """


def render_collapsible_tree(data: dict[str, Any]) -> str:
    nodes = data["tree"].get("structure") or []
    total_nodes = len(data["flat_tree"])
    max_depth = max((depth for _, depth, _ in data["flat_tree"]), default=0)
    opened_default_depth = 1
    tree_html = "".join(render_tree_node(node, 0, opened_default_depth) for node in nodes)
    return f"""
      <div class="tree-explorer-panel">
        <h3>Tree explorer: collapsible section outline</h3>
        <p class="icicle-caption">ASCII 대신 section 제목을 직접 접고 펼쳐 볼 수 있는 탐색용 outline입니다. 화면에서는 전체 {total_nodes:,}개 node를 확인할 수 있고, PDF에서는 깊은 하위 레벨을 접어 레이아웃을 보호합니다.</p>
        <div class="tree-explorer-meta">
          <span class="tree-badge">nodes {total_nodes:,}</span>
          <span class="tree-badge">max depth {max_depth}</span>
          <span class="tree-badge page">top branches {len(nodes)}</span>
        </div>
        <div class="tree-explorer-wrap">
          <div class="tree-explorer" aria-label="Collapsible GMP document tree">
            {tree_html}
          </div>
        </div>
      </div>
    """


def render_tree_node(node: dict[str, Any], depth: int, opened_default_depth: int) -> str:
    kids = children(node)
    own_start, own_end, subtree_start, subtree_end = node_range(node)
    title = node.get("title", "Untitled")
    own_range = fmt_range(own_start, own_end)
    subtree_range = fmt_range(subtree_start, subtree_end)
    badges = (
        f'<span class="tree-badge">D{depth}</span>'
        f'<span class="tree-badge page">p.{esc(subtree_range)}</span>'
    )
    if kids:
        badges += f'<span class="tree-badge">{len(kids)} children</span>'
    summary = (
        f'<span class="tree-node-title">{esc(title)}</span> '
        f'{badges} '
        f'<span class="tree-node-muted">own p.{esc(own_range)}</span>'
    )
    if not kids:
        return f'<div class="tree-leaf">{summary}</div>'
    open_attr = " open" if depth <= opened_default_depth else ""
    child_html = "".join(render_tree_node(child, depth + 1, opened_default_depth) for child in kids)
    return f'<details{open_attr}><summary>{summary}</summary>{child_html}</details>'


def tree_overview(data: dict[str, Any]) -> str:
    rows = data["top_rows"]
    total_span = max(sum(int(row.get("subtree_span") or 0) for row in rows), 1)
    max_nodes = max((int(row.get("nodes") or 0) for row in rows), default=1)
    branch_html: list[str] = []
    for row in rows:
        span = int(row.get("subtree_span") or 0)
        pct_width = max(span / total_span * 100, 3.0)
        node_density = int(row.get("nodes") or 0) / max_nodes * 100
        branch_html.append(
            f"""
            <div class="tree-branch">
              <div>
                <div class="tree-branch-title">{esc(row.get('title'))}</div>
                <div class="tree-branch-meta">depth {esc(row.get('max_depth'))} · {esc(row.get('nodes'))} nodes</div>
              </div>
              <div class="tree-branch-bar" title="page span">
                <div class="tree-branch-fill" style="width:{pct_width:.1f}%"></div>
              </div>
              <div class="tree-branch-stat">p.{esc(row.get('subtree_range'))}<br><span>{span} pages · density {node_density:.0f}%</span></div>
            </div>
            """
        )

    depth_items = sorted(data["depth_counts"].items(), key=lambda x: int(x[0]))[:8]
    depth_html = "".join(
        f"<div class=\"depth-cell\"><span>depth {esc(depth)}</span><strong>{esc(count)}</strong></div>"
        for depth, count in depth_items
    )
    return f"""
      <div class="tree-overview">
        <h3>Tree at a glance</h3>
        <div class="tree-map">{''.join(branch_html)}</div>
        <div class="depth-strip" aria-label="Node count by tree depth">{depth_html}</div>
      </div>
    """


def eval_browser(eval_json: str) -> str:
    return f"""
      <div class="eval-browser" id="eval-browser">
        <script type="application/json" id="eval-data">{eval_json}</script>
        <div class="eval-controls screen-only">
          <label>검색
            <input id="eval-search" type="search" placeholder="ID, 질문, section, page 검색" />
          </label>
          <label>난이도
            <select id="eval-difficulty"><option value="">전체</option></select>
          </label>
          <label>Hit 상태
            <select id="eval-hit">
              <option value="">전체</option>
              <option value="aligned-hit">Aligned hit</option>
              <option value="aligned-miss">Aligned miss</option>
              <option value="evidence-hit">Evidence+aligned hit</option>
              <option value="evidence-miss">Evidence+aligned miss</option>
            </select>
          </label>
          <label>문항 선택
            <select id="eval-select"></select>
          </label>
        </div>
        <div class="eval-status">
          <strong id="eval-count">100개 문항</strong>
          <span>행을 클릭하면 아래 상세 근거가 바뀝니다.</span>
        </div>
        <div class="eval-table-wrap">
          <table class="eval-table">
            <thead><tr><th style="width:22mm;">ID</th><th style="width:20mm;">Diff</th><th style="width:28mm;">Hit</th><th style="width:24mm;">Gold</th><th>Question</th></tr></thead>
            <tbody id="eval-tbody"></tbody>
          </table>
        </div>
        <div class="eval-detail" id="eval-detail"></div>
      </div>
    """


def notable_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<p class=\"small\">특이 사례 없음</p>"
    body = "".join(tr_multi([row.get("id"), row.get("classification"), row.get("gold_pages"), row.get("predicted_pages"), row.get("evidence_plus_aligned_pages")]) for row in rows)
    return f"<table><thead><tr><th>ID</th><th>Classification</th><th>Gold</th><th>Predicted</th><th>Evidence+aligned</th></tr></thead><tbody>{body}</tbody></table>"


def eval_sample_table(rows: list[dict[str, Any]]) -> str:
    sample = rows[:8] + [row for row in rows if row.get("id") == "gmp_eval_025"]
    seen = set()
    uniq = []
    for row in sample:
        if row.get("id") not in seen:
            seen.add(row.get("id"))
            uniq.append(row)
    body = "".join(tr_multi([row.get("id"), row.get("difficulty"), "hit" if row.get("aligned_hit") else "miss", row.get("gold_pages"), row.get("question")]) for row in uniq)
    return f"<table><thead><tr><th>ID</th><th>Difficulty</th><th>Aligned</th><th>Gold</th><th>Question</th></tr></thead><tbody>{body}</tbody></table>"


def fmt_range(start: Any, end: Any) -> str:
    if start in (None, "") and end in (None, ""):
        return "N/A"
    return str(start) if start == end else f"{start}-{end}"


def range_span(start: Any, end: Any) -> int:
    try:
        s = int(start)
        e = int(end)
    except (TypeError, ValueError):
        return 0
    return max(e - s + 1, 1)


def clamp_int(value: Any, min_value: int, max_value: int) -> int:
    try:
        num = int(value)
    except (TypeError, ValueError):
        num = min_value
    return max(min_value, min(num, max_value))


def truncate(value: Any, max_chars: int) -> str:
    text = str(value)
    if len(text) <= max_chars:
        return text
    return text[: max(max_chars - 1, 1)] + "…"


def pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def esc(value: Any) -> str:
    return escape(str(value), quote=True)


if __name__ == "__main__":
    raise SystemExit(main())
