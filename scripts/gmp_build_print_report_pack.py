#!/usr/bin/env python3
"""Build A4 print-ready HTML report pack for the GMP DocMIND analysis."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from html import escape
from pathlib import Path
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
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    data = load_report_data()
    files = {
        "design-system.html": render_design_system(data),
        "report-template.html": render_template(data),
        "sample-analysis-report.html": render_sample_report(data),
    }
    for name, html in files.items():
        path = OUT_DIR / name
        path.write_text(html, encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)} ({path.stat().st_size:,} bytes)")
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


def render_design_system(data: dict[str, Any]) -> str:
    body = f"""
    <section class="cover compact">
      <p class="eyebrow">Design System</p>
      <h1>DocMIND GMP 분석 보고서 HTML 디자인 시스템</h1>
      <p class="lead">A4 인쇄/PDF용 실험·분석 보고서를 위한 레이아웃, 색상, 타이포그래피, 표, 카드, callout 규칙입니다.</p>
      <div class="meta-grid">
        <div><span>문서 성격</span><strong>실험/분석 보고서</strong></div>
        <div><span>출력 대상</span><strong>A4 PDF / Print</strong></div>
        <div><span>톤</span><strong>차분함 · 전문적 · 근거 중심</strong></div>
      </div>
    </section>

    <section class="report-section">
      <h2>1. 디자인 원칙</h2>
      <div class="callout neutral"><strong>핵심 결과 우선.</strong> 첫 페이지에서 목적, 핵심 수치, 결론을 바로 확인할 수 있어야 합니다.</div>
      <div class="grid-2">
        <div class="card"><h3>가독성</h3><p>본문은 10.5-11pt 기준으로 읽기 좋게 유지하고, 표는 행 간격과 zebra background로 구분합니다.</p></div>
        <div class="card"><h3>인쇄 안정성</h3><p>카드와 표가 페이지 중간에서 과도하게 쪼개지지 않도록 <code>break-inside: avoid</code>를 사용합니다.</p></div>
      </div>
    </section>

    <section class="report-section">
      <h2>2. Typography</h2>
      <h1 class="demo-h1">H1 보고서 제목</h1>
      <h2>H2 주요 섹션</h2>
      <h3>H3 하위 분석 항목</h3>
      <p>본문은 한국어 분석 보고서에 맞춰 시스템 sans-serif를 사용합니다. 숫자와 코드성 값은 <code>monospace</code> 또는 표 안에서 정렬합니다.</p>
    </section>

    <section class="report-section">
      <h2>3. Components</h2>
      <div class="kpi-grid">
        {kpi('공식 hit rate', '96.0%', 'aligned predicted union')}
        {kpi('Eval 문항', '100', 'schema valid')}
        {kpi('Tree nodes', '641', 'validated hierarchy')}
        {kpi('Unrecovered', '1', 'gmp_eval_025')}
      </div>
      <div class="callout info"><strong>Info callout.</strong> 해석 기준이나 정의를 설명할 때 사용합니다.</div>
      <div class="callout warning"><strong>Warning callout.</strong> 한계, 주의 사항, 공식 지표가 아닌 보조 지표를 설명할 때 사용합니다.</div>
      <table>
        <thead><tr><th>컴포넌트</th><th>용도</th><th>인쇄 규칙</th></tr></thead>
        <tbody>
          <tr><td>KPI card</td><td>핵심 수치 요약</td><td>첫 페이지 배치</td></tr>
          <tr><td>Callout</td><td>해석/주의 강조</td><td>한 페이지 내 유지</td></tr>
          <tr><td>Data table</td><td>평가 결과 정리</td><td>header 반복, 작은 폰트 허용</td></tr>
        </tbody>
      </table>
    </section>
    """
    return document("Design System", body, subtitle="A4 print-ready visual language", doc_type="design-system")


def render_template(data: dict[str, Any]) -> str:
    body = """
    <section class="cover">
      <p class="eyebrow">Analysis Report Template</p>
      <h1>[프로젝트/실험 보고서 제목]</h1>
      <p class="lead">[보고서의 목적과 핵심 결론을 2-3문장으로 요약합니다. 첫 페이지에서 읽는 사람이 무엇을 검증했고 무엇을 얻었는지 알 수 있어야 합니다.]</p>
      <div class="meta-grid">
        <div><span>작성일</span><strong>[YYYY-MM-DD]</strong></div>
        <div><span>작성자</span><strong>[팀/작성자]</strong></div>
        <div><span>상태</span><strong>[Draft/Final]</strong></div>
      </div>
      <div class="kpi-grid">
        {kpi1}{kpi2}{kpi3}{kpi4}
      </div>
    </section>

    <nav class="toc">
      <h2>목차</h2>
      <ol>
        <li><a href="#summary">요약</a></li>
        <li><a href="#method">방법</a></li>
        <li><a href="#results">결과</a></li>
        <li><a href="#interpretation">해석</a></li>
        <li><a href="#limitations">한계</a></li>
        <li><a href="#next-steps">다음 단계</a></li>
      </ol>
    </nav>

    <section id="summary" class="report-section page-break-before"><h2>1. 요약</h2><p>[핵심 결과와 결론을 먼저 작성합니다.]</p></section>
    <section id="method" class="report-section"><h2>2. 방법</h2><p>[데이터, 절차, 검증 기준을 작성합니다.]</p></section>
    <section id="results" class="report-section"><h2>3. 결과</h2><table><thead><tr><th>항목</th><th>결과</th><th>해석</th></tr></thead><tbody><tr><td>[metric]</td><td>[value]</td><td>[meaning]</td></tr></tbody></table></section>
    <section id="interpretation" class="report-section"><h2>4. 해석</h2><div class="callout info">[결과를 어떻게 읽어야 하는지 설명합니다.]</div></section>
    <section id="limitations" class="report-section"><h2>5. 한계</h2><ul><li>[한계 1]</li><li>[한계 2]</li></ul></section>
    <section id="next-steps" class="report-section"><h2>6. 다음 단계</h2><ol><li>[다음 작업 1]</li><li>[다음 작업 2]</li></ol></section>
    """.format(
        kpi1=kpi("핵심 지표 1", "[값]", "[설명]"),
        kpi2=kpi("핵심 지표 2", "[값]", "[설명]"),
        kpi3=kpi("데이터 수", "[N]", "[범위]"),
        kpi4=kpi("상태", "[PASS]", "[기준]"),
    )
    return document("Report Template", body, subtitle="Reusable A4 analysis report template", doc_type="template")


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
      <p class="source-line">Repository: <a href="{REPO_URL}">{REPO_URL}</a></p>
    </section>

    <nav class="toc">
      <h2>목차</h2>
      <ol>
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

    <section id="summary" class="report-section page-break-before">
      <h2>1. 요약</h2>
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
      <h2>2. 방법</h2>
      <div class="method-flow">
        {step('01', 'PDF 구조화', 'GMP PDF를 PageIndex workspace로 변환해 page content와 초기 structure를 생성했습니다.')}
        {step('02', 'Tree 확장/보정', 'TOC와 본문 heading을 기준으로 모든 주요 branch를 세분화하고 page span을 정규화했습니다.')}
        {step('03', 'Page alignment', 'PDF 물리 page와 문서 내부 page 번호가 밀리는 문제를 audit하고 alignment map을 만들었습니다.')}
        {step('04', '100문항 eval', '질문별 gold page/section path와 predicted page를 비교해 official score를 계산했습니다.')}
      </div>
      <div class="callout info"><strong>평가 흐름:</strong> get_document → get_document_structure → get_page_content 흐름을 기준으로, tree를 보고 관련 section 후보를 고른 뒤 page content를 열어 최종 predicted page를 결정하는 방식입니다.</div>
    </section>

    <section id="results" class="report-section">
      <h2>3. 결과</h2>
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
      <h2>4. 해석</h2>
      <div class="callout info"><strong>Aligned hit rate 도입 배경:</strong> GMP PDF는 PDF 물리 page와 문서 내부 page 번호가 밀리는 구간이 있어, 단순 page 번호 비교만으로는 검색 성능이 왜곡될 수 있습니다. 따라서 page alignment map을 반영한 aligned predicted union을 공식 기준으로 사용했습니다.</div>
      <div class="callout warning"><strong>Evidence+aligned의 의미:</strong> {pct(diagnostic)}는 최종 선택 page가 아니라, retriever가 탐색 과정에서 읽은 evidence page까지 포함한 진단 coverage입니다. 공식 headline은 {pct(canonical)}로 유지합니다.</div>
      <p>잔여 오류는 크게 두 유형으로 나뉩니다. 첫째, 근거 page를 읽었지만 최종 page selection에서 놓친 사례입니다. 둘째, evidence 탐색 과정에서도 gold page를 찾지 못한 더 강한 실패입니다. 현재 완전 미회수 사례는 <code>gmp_eval_025</code> 1건입니다.</p>
    </section>

    <section id="limitations" class="report-section">
      <h2>5. 한계</h2>
      <ul>
        <li>평가셋은 100개 문항으로 구성되어 있어, 더 넓은 GMP 질의 유형을 모두 대표한다고 보기는 어렵습니다.</li>
        <li>Evidence+aligned는 내부 탐색 coverage를 보여주는 진단 지표이며, 최종 사용자에게 반환되는 page 선택 성능과 동일하지 않습니다.</li>
        <li>Tree 구조는 현재 PDF와 산출물 기준으로 검증되었으며, 다른 개정본 PDF에는 page alignment와 tree boundary를 다시 확인해야 합니다.</li>
      </ul>
    </section>

    <section id="next-steps" class="report-section">
      <h2>6. 다음 단계</h2>
      <ol>
        <li><strong>실패 4건 상세 분석:</strong> aligned miss 4건의 원인을 page selection, evidence 탐색, semantic confusion으로 분류합니다.</li>
        <li><strong>평가셋 확장:</strong> 100개에서 더 다양한 장/절/질문 유형으로 확장합니다.</li>
        <li><strong>보고서 배포:</strong> 본 HTML을 브라우저 print/PDF로 내보내 외부 공유용 PDF를 생성합니다.</li>
      </ol>
    </section>

    <section id="artifacts" class="report-section">
      <h2>7. 재현 가능한 산출물</h2>
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
          {tr('scripts/gmp_build_print_report_pack.py', 'A4 인쇄용 HTML 생성 스크립트')}
        </tbody>
      </table>
    </section>

    <section id="appendix-tree" class="report-section page-break-before">
      <h2>부록 A. Tree 요약</h2>
      <table>
        <thead><tr><th>Top branch</th><th>Nodes</th><th>Max depth</th><th>Own pages</th><th>Subtree pages</th></tr></thead>
        <tbody>{''.join(tr_multi([r['title'], r['nodes'], r['max_depth'], r['own_range'], r['subtree_range']]) for r in data['top_rows'])}</tbody>
      </table>
      <h3>ASCII tree excerpt</h3>
      <pre class="ascii-excerpt">{esc('\n'.join(data['tree_ascii'].splitlines()[:80]))}</pre>
    </section>

    <section id="appendix-eval" class="report-section">
      <h2>부록 B. Eval 샘플 및 실패 사례</h2>
      <h3>Notable miss/repair cases</h3>
      {notable_table(notable)}
      <h3>Eval sample rows</h3>
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
th, td { border: 1px solid var(--line); padding: 2.4mm 2.8mm; vertical-align: top; }
th { background: var(--panel-strong); color: #303a48; font-size: 8.5pt; letter-spacing: .035em; text-transform: uppercase; text-align: left; }
tbody tr:nth-child(even) td { background: #fbfcfe; }
code, pre { font-family: var(--mono); }
code { background: var(--panel); border: 1px solid var(--line); border-radius: 1.5mm; padding: 0 .8mm; font-size: 9pt; }
.ascii-excerpt { white-space: pre; overflow: hidden; border: 1px solid var(--line); background: #101820; color: #e5edf7; padding: 4mm; border-radius: 2mm; font-size: 7.6pt; line-height: 1.35; max-height: 105mm; }
.bar-row { display: grid; grid-template-columns: 32mm 1fr 12mm; align-items: center; gap: 2mm; margin: 1.4mm 0; font-size: 9pt; }
.bar-track { height: 3mm; background: #e3e8f0; border-radius: 999px; overflow: hidden; }
.bar-fill { height: 100%; background: var(--accent); }
.small { font-size: 8.5pt; color: var(--muted); }
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
}
@media screen and (max-width: 900px) {
  .report-paper { margin: 0; padding: 20px; max-width: none; }
  .meta-grid, .kpi-grid, .grid-2, .method-flow { grid-template-columns: 1fr; }
  .toc ol { columns: 1; }
}
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
        rows.append({
            "title": node.get("title", ""),
            "nodes": len(sub),
            "max_depth": max((depth for _, depth, _ in sub), default=0),
            "own_range": fmt_range(own_start, own_end),
            "subtree_range": fmt_range(subtree_start, subtree_end),
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
            "classification": score_row.get("classification", "missing_score_item"),
            "gold_pages": row.get("gold_pages", ""),
            "predicted_pages": score_row.get("predicted_pages", pred.get("predicted_pages", "")),
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
    body = "".join(tr_multi([row.get("id"), row.get("difficulty"), row.get("question_type"), "hit" if row.get("aligned_hit") else "miss", row.get("gold_pages"), row.get("question")]) for row in uniq)
    return f"<table><thead><tr><th>ID</th><th>Difficulty</th><th>Type</th><th>Aligned</th><th>Gold</th><th>Question</th></tr></thead><tbody>{body}</tbody></table>"


def fmt_range(start: Any, end: Any) -> str:
    if start in (None, "") and end in (None, ""):
        return "N/A"
    return str(start) if start == end else f"{start}-{end}"


def pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def esc(value: Any) -> str:
    return escape(str(value), quote=True)


if __name__ == "__main__":
    raise SystemExit(main())
