#!/usr/bin/env python3
"""Build a standalone HTML report for the GMP PageIndex tree/eval work."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "reports" / "gmp_pageindex_final_report.html"

WORKSPACE = ROOT / "results" / "pageindex_gmp_workspace" / "gmp-guidance.json"
TREE = ROOT / "results" / "gmp_guidance_structure.json"
TREE_HTML = ROOT / "results" / "visualizations" / "gmp_guidance_tree.html"
TREE_TXT = ROOT / "results" / "visualizations" / "gmp_guidance_tree.txt"
ALIGNMENT = ROOT / "results" / "page_alignment" / "gmp_page_alignment_map.json"
SCORE = ROOT / "results" / "page_alignment" / "score_001_100_agentic_official_alignment.json"
EVAL = ROOT / "eval" / "gmp_eval_testset.jsonl"
PREDICTIONS = ROOT / "results" / "codex_agentic_10x10" / "predictions_001_100_agentic.jsonl"


def main() -> int:
    workspace = read_json(WORKSPACE)
    tree = read_json(TREE)
    alignment = read_json(ALIGNMENT)
    score = read_json(SCORE)
    eval_rows = read_jsonl(EVAL)
    predictions = read_jsonl(PREDICTIONS)

    flat_tree = list(walk(tree.get("structure") or []))
    depth_counts = Counter(depth for _, depth, _ in flat_tree)
    top_rows = build_top_rows(tree.get("structure") or [])
    eval_difficulty = Counter(str(row.get("difficulty", "unknown")) for row in eval_rows)
    eval_qtype = Counter(str(row.get("question_type", "unknown")) for row in eval_rows)
    class_counts = Counter(score.get("alignment_prediction_evaluation", {}).get("classification_counts") or {})
    score_metrics = score.get("alignment_prediction_evaluation", {}).get("metrics") or {}
    summary = score.get("summary") or {}
    pageindex_flow = score.get("pageindex_flow") or {}
    baseline_metrics = score.get("metrics") or {}
    unrecovered = score.get("alignment_prediction_evaluation", {}).get("unrecovered_after_evidence_alignment") or []
    score_items = score.get("alignment_prediction_evaluation", {}).get("items", [])
    notable_items = [item for item in score_items if item.get("classification") != "already_hit"]
    adversarial = score.get("adversarial_probes") or []
    eval_browser_rows = build_eval_browser_rows(eval_rows, predictions, score_items)
    tree_ascii = TREE_TXT.read_text(encoding="utf-8") if TREE_TXT.exists() else ""

    report = render_html(
        workspace=workspace,
        tree=tree,
        flat_tree=flat_tree,
        depth_counts=depth_counts,
        top_rows=top_rows,
        alignment=alignment,
        score=score,
        score_metrics=score_metrics,
        summary=summary,
        pageindex_flow=pageindex_flow,
        baseline_metrics=baseline_metrics,
        eval_rows=eval_rows,
        eval_difficulty=eval_difficulty,
        eval_qtype=eval_qtype,
        class_counts=class_counts,
        notable_items=notable_items,
        unrecovered=unrecovered,
        adversarial=adversarial,
        eval_browser_rows=eval_browser_rows,
        tree_ascii=tree_ascii,
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(report, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size:,} bytes)")
    print(
        "summary: nodes=%d pages=%s eval_rows=%d canonical=%.2f unresolved=%d browser_rows=%d"
        % (
            len(flat_tree),
            workspace.get("page_count"),
            len(eval_rows),
            float(score_metrics.get("aligned_predicted_union_hit_rate", 0.0)),
            len(unrecovered),
            len(eval_browser_rows),
        )
    )
    return 0


def build_eval_browser_rows(
    eval_rows: list[dict[str, Any]], predictions: list[dict[str, Any]], score_items: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    pred_by_id = {str(row.get("id")): row for row in predictions}
    score_by_id = {str(row.get("id")): row for row in score_items}
    out: list[dict[str, Any]] = []
    for row in eval_rows:
        row_id = str(row.get("id", ""))
        pred = pred_by_id.get(row_id, {})
        score_row = score_by_id.get(row_id, {})
        original_hit = bool((score_row.get("original_page_metrics") or {}).get("hit"))
        aligned_hit = bool((score_row.get("aligned_predicted_union_metrics") or {}).get("hit"))
        evidence_hit = bool((score_row.get("evidence_plus_aligned_metrics") or {}).get("hit"))
        out.append(
            {
                "id": row_id,
                "question": row.get("question", ""),
                "difficulty": row.get("difficulty", ""),
                "question_type": row.get("question_type", ""),
                "classification": score_row.get("classification", "missing_score_item"),
                "gold_pages": row.get("gold_pages", ""),
                "predicted_pages": score_row.get("predicted_pages", pred.get("predicted_pages", "")),
                "aligned_predicted_pages": score_row.get("aligned_predicted_pages", ""),
                "evidence_pages_read": score_row.get("evidence_pages_read", pred.get("evidence_pages_read", "")),
                "evidence_plus_aligned_pages": score_row.get("evidence_plus_aligned_pages", ""),
                "gold_section_path": row.get("gold_section_path", []),
                "predicted_section_path": pred.get("predicted_section_path", []),
                "expected_answer": row.get("expected_answer", ""),
                "gold_evidence_summary": row.get("gold_evidence_summary", ""),
                "reason": pred.get("reason", ""),
                "original_hit": original_hit,
                "aligned_hit": aligned_hit,
                "evidence_hit": evidence_hit,
            }
        )
    return out


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected object JSON: {path}")
    return payload


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(path)
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise TypeError(f"expected object row: {path}:{line_no}")
        rows.append(payload)
    return rows


def children(node: dict[str, Any]) -> list[dict[str, Any]]:
    kids = node.get("nodes") or node.get("children") or []
    return kids if isinstance(kids, list) else []


def node_range(node: dict[str, Any]) -> tuple[Any, Any, Any, Any]:
    own_start = node.get("own_start_index", node.get("start_index"))
    own_end = node.get("own_end_index", node.get("end_index"))
    subtree_start = node.get("subtree_start_index", own_start)
    subtree_end = node.get("subtree_end_index", own_end)
    return own_start, own_end, subtree_start, subtree_end


def walk(nodes: Iterable[dict[str, Any]], depth: int = 0, parent_path: tuple[str, ...] = ()):  # noqa: ANN201
    for node in nodes:
        path = parent_path + (str(node.get("title", "Untitled")),)
        yield node, depth, path
        yield from walk(children(node), depth + 1, path)


def build_top_rows(top_nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for node in top_nodes:
        sub = list(walk([node]))
        own_start, own_end, subtree_start, subtree_end = node_range(node)
        rows.append(
            {
                "node_id": node.get("node_id", ""),
                "title": node.get("title", ""),
                "nodes": len(sub),
                "max_depth": max((depth for _, depth, _ in sub), default=0),
                "own_range": fmt_range(own_start, own_end),
                "subtree_range": fmt_range(subtree_start, subtree_end),
                "children": len(children(node)),
            }
        )
    return rows


def render_html(**ctx: Any) -> str:
    workspace = ctx["workspace"]
    score = ctx["score"]
    summary = ctx["summary"]
    score_metrics = ctx["score_metrics"]
    baseline_metrics = ctx["baseline_metrics"]
    pageindex_flow = ctx["pageindex_flow"]
    class_counts = ctx["class_counts"]
    eval_difficulty = ctx["eval_difficulty"]
    eval_qtype = ctx["eval_qtype"]
    depth_counts = ctx["depth_counts"]
    notable_items = ctx["notable_items"]
    unrecovered = ctx["unrecovered"]
    adversarial = ctx["adversarial"]
    flat_tree = ctx["flat_tree"]
    top_rows = ctx["top_rows"]
    tree = ctx["tree"]
    eval_browser_rows = ctx["eval_browser_rows"]
    tree_ascii = ctx["tree_ascii"]

    canonical = float(score_metrics.get("aligned_predicted_union_hit_rate", 0.0))
    original = float(score_metrics.get("original_predicted_page_hit_rate", 0.0))
    diagnostic = float(score_metrics.get("evidence_plus_aligned_hit_rate", 0.0))
    generated = score.get("generated_at") or datetime.now(timezone.utc).isoformat()
    eval_json = json.dumps(eval_browser_rows, ensure_ascii=False).replace("</", "<\\/")

    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>GMP PageIndex 최종 보고서</title>
  <style>{css()}</style>
</head>
<body>
  <main class="page">
    <section class="hero">
      <div class="kicker">GMP PageIndex Report</div>
      <h1>PDF TOC Tree 구축 및 Retrieval Eval 최종 보고서</h1>
      <p class="lead">PageIndex 기반으로 GMP PDF를 구조화하고, Codex/PageIndex-style retrieval 흐름으로 100개 평가셋을 검증한 결과를 한 장의 HTML 보고서로 정리했습니다.</p>
      <div class="badges">
        <span class="badge ok">최종 상태: {esc(score.get('status', 'UNKNOWN'))}</span>
        <span class="badge">생성 시각: {esc(str(generated))}</span>
        <span class="badge warn">공식 기준: aligned predicted union 0.96</span>
      </div>
    </section>

    <section class="grid metrics">
      {metric('Canonical hit', f'{canonical:.2f}', '최종 공식 page hit rate')}
      {metric('Original hit', f'{original:.2f}', 'page alignment 보정 전')}
      {metric('Diagnostic coverage', f'{diagnostic:.2f}', 'evidence+aligned 보조 지표')}
      {metric('Tree nodes', f'{len(flat_tree):,}', f"{workspace.get('page_count')} pages / top {len(tree.get('structure') or [])}")}
    </section>

    <section class="card">
      <h2>1. 우리가 만든 것</h2>
      <p>최종 산출물은 GMP PDF를 PageIndex workspace로 변환한 뒤, TOC/section tree를 확장·정규화하고, 그 tree와 page content를 기반으로 검색 평가를 수행하는 로컬 파이프라인입니다.</p>
      <div class="timeline">
        {step('01', 'PDF → PageIndex workspace', 'PageIndex 기반 pipeline으로 PDF page content와 초기 structure를 생성했습니다.', ['results/pageindex_gmp_workspace/gmp-guidance.json'])}
        {step('02', 'TOC/tree 탐지 및 all-branch 확장', '초기 TOC를 모든 주요 branch에 대해 세분화하고, 중복/오배치 section을 보정했습니다.', ['results/gmp_guidance_structure.json', 'scripts/gmp_expand_all_branches.py', 'scripts/gmp_targeted_expand.py'])}
        {step('03', 'Tree 검증 및 시각화', 'node id, page span, parent-child 포함관계, sibling order를 검증하고 HTML/TXT tree를 생성했습니다.', ['scripts/gmp_all_branch_validate.py', 'scripts/gmp_tree_validate.py', 'results/visualizations/gmp_guidance_tree.html'])}
        {step('04', 'Page coordinate alignment', 'PDF physical page와 문서 내부 page label의 offset을 audit하고 dominant offset을 반영했습니다.', ['results/page_alignment/gmp_page_alignment_map.json', 'results/page_alignment/gmp_page_alignment_report.md'])}
        {step('05', '100문항 retrieval eval', 'get_document → get_document_structure → get_page_content 흐름을 기준으로 예측 page/section과 gold page를 비교했습니다.', ['eval/gmp_eval_testset.jsonl', 'results/codex_agentic_10x10/predictions_001_100_agentic.jsonl', 'results/page_alignment/score_001_100_agentic_official_alignment.json'])}
      </div>
    </section>

    <section class="card">
      <h2>2. Tree가 어떻게 만들어졌나</h2>
      <div class="two-col">
        <div>
          <h3>구조 생성 원리</h3>
          <ul>
            <li>PDF에서 추출한 page text와 TOC/heading 후보를 PageIndex workspace의 <code>structure</code>로 정리했습니다.</li>
            <li>각 node는 <code>node_id</code>, <code>title</code>, own page range, subtree page range, child <code>nodes</code>를 가집니다.</li>
            <li>검색 시에는 먼저 문서와 tree를 보고 관련 section 후보를 고른 뒤, 필요한 page content를 열어 최종 page를 결정합니다.</li>
            <li>이 보고서의 tree 기준 파일은 <code>{rel(TREE)}</code>입니다.</li>
          </ul>
        </div>
        <div class="note">
          <strong>PageIndex flow check</strong>
          <dl class="kv">
            {kv('document_ok', pageindex_flow.get('document_ok'))}
            {kv('structure_ok', pageindex_flow.get('structure_ok'))}
            {kv('page_content_smoke_ok', pageindex_flow.get('page_content_smoke_ok'))}
            {kv('tree_node_count', pageindex_flow.get('tree_node_count'))}
            {kv('structure_top_count', pageindex_flow.get('structure_top_count'))}
          </dl>
        </div>
      </div>
      <h3>Top-level tree summary</h3>
      {top_table(top_rows)}
      <h3>Depth distribution</h3>
      {bars(depth_counts, prefix='depth ')}
    </section>

    <section class="card">
      <h2>3. Tree 시각화</h2>
      <p>아래는 최종 tree의 전체 계층을 두 가지 방식으로 시각화한 것입니다. 첫 번째는 ASCII tree, 두 번째는 접었다 펼칠 수 있는 HTML tree입니다.</p>
      <h3>ASCII tree view</h3>
      <p class="muted">최종 tree 641개 node를 terminal/tree 형태로 표현했습니다. page range와 node id를 함께 확인할 수 있습니다.</p>
      <button class="toggle-btn" type="button" data-target="ascii-tree" data-expanded="false">ASCII tree 전체 펼치기</button>
      <pre id="ascii-tree" class="ascii-tree">{esc(tree_ascii)}</pre>
      <h3>Interactive tree view</h3>
      <p class="muted">실제 tree HTML 원본은 <code>{rel(TREE_HTML)}</code>에 저장되어 있습니다.</p>
      <div class="tree-wrap">
        {tree_html(tree.get('structure') or [])}
      </div>
    </section>

    <section class="card">
      <h2>4. 최종 Eval 결과</h2>
      <div class="grid metrics compact">
        {metric('Eval rows', str(summary.get('items', 0)), '100개 평가셋')}
        {metric('Schema errors', str(summary.get('schema_errors', 0)), 'JSONL/schema 검증')}
        {metric('Validation errors', str(len(score.get('validation_errors') or [])), '평가 입력 검증')}
        {metric('Adversarial probes', f"{sum(1 for x in adversarial if x.get('status') == 'pass')}/{len(adversarial)}", '잘못된 입력/경계 사례')}
      </div>
      <div class="two-col">
        <div>
          <h3>공식 metric</h3>
          <table><tbody>
            {tr('Original predicted page hit rate', pct(original))}
            {tr('Aligned predicted union hit rate', pct(canonical) + ' ← 공식 기준')}
            {tr('Evidence union hit rate', pct(float(score_metrics.get('evidence_union_hit_rate', 0.0))))}
            {tr('Evidence + aligned hit rate', pct(diagnostic) + ' ← 진단값')}
            {tr('Aligned precision avg', f"{float(score_metrics.get('aligned_predicted_union_precision_avg', 0.0)):.4f}")}
            {tr('Evidence+aligned precision avg', f"{float(score_metrics.get('evidence_plus_aligned_precision_avg', 0.0)):.4f}")}
          </tbody></table>
        </div>
        <div>
          <h3>Aligned hit rate란?</h3>
          <div class="note explain">
            <p><strong>질문별 gold page가 retriever의 최종 선택 page 안에 포함됐는지를 보는 공식 검색 성공률입니다.</strong></p>
            <h4>왜 도입했나</h4>
            <p>초기 평가에서는 retriever가 반환한 page 번호와 평가셋의 gold page 번호를 그대로 비교했습니다. 그런데 GMP PDF는 표지, 목차, 부록, 내부 인쇄 page label 때문에 <strong>PDF 물리 page</strong>와 <strong>문서 내부 page 번호</strong>가 일정하게 밀리는 구간이 있었습니다. 이 상태에서 단순 page hit만 보면, 실제로는 맞는 근거 근처를 찾았는데도 page 번호 좌표계가 달라서 miss로 계산되는 문제가 생깁니다.</p>
            <p>그래서 page alignment map을 만든 뒤, 원래 predicted page와 alignment 보정 page를 함께 평가하는 <strong>aligned predicted union</strong>을 공식 기준으로 삼았습니다. 이 지표는 “모델이 문서 구조상 올바른 근거 위치를 찾았는가”를 더 공정하게 평가하기 위한 보정 지표입니다.</p>
            <ul>
              <li><strong>Hit</strong>: 평가셋의 정답 근거 page가 예측 page 또는 page alignment 보정 후 page 집합에 들어간 경우</li>
              <li><strong>Aligned</strong>: PDF 물리 page와 문서 내부 page 번호가 밀리는 문제를 보정했다는 뜻</li>
              <li><strong>96.0%</strong>: 100개 중 96개 문항에서 정답 근거 page를 찾았다는 의미</li>
              <li><strong>99.0%</strong>: 최종 선택 page가 아니라, 중간에 읽은 evidence page까지 포함한 진단용 coverage</li>
            </ul>
            <p class="muted">따라서 발표/보고서의 headline 성능은 96.0%로 두고, 99.0%는 “근거는 읽었지만 최종 page 선택에서 놓친 사례”를 분석하는 보조 지표로 봅니다.</p>
            <h4>Evidence+aligned hit은 무슨 뜻인가</h4>
            <p><strong>Evidence+aligned hit</strong>은 retriever가 최종 답으로 선택한 page뿐 아니라, 답을 고르기 전에 실제로 열어본 <strong>evidence pages</strong>와 그 alignment 보정 page까지 합쳐서 gold page가 포함되는지 확인하는 진단 지표입니다.</p>
            <p>이 지표를 도입한 이유는 실패 원인을 둘로 나누기 위해서입니다. 하나는 retriever가 아예 정답 근거 page 근처를 읽지 못한 경우이고, 다른 하나는 정답 근거 page를 읽었지만 최종 predicted page로 선택하지 못한 경우입니다. 두 경우는 개선 방향이 다르기 때문에 분리해서 봐야 합니다.</p>
            <ul>
              <li><strong>Aligned hit 실패 + Evidence+aligned hit 성공</strong>: 근거 page는 읽었지만 최종 page selection에서 놓친 사례</li>
              <li><strong>Evidence+aligned hit 실패</strong>: 근거 page 자체를 탐색 과정에서 찾지 못한 더 강한 실패 사례</li>
              <li><strong>99.0%</strong>: 100개 중 99개는 탐색 과정 어딘가에서 gold page를 읽었다는 의미</li>
            </ul>
            <p class="muted">다만 Evidence+aligned는 최종 사용자가 받는 page 선택 결과가 아니라 내부 탐색 coverage를 보는 값입니다. 그래서 공식 성능 headline은 96.0%로 유지하고, Evidence+aligned 99.0%는 “retriever가 어디까지 근거를 탐색했는가”를 설명하는 디버깅/개선 지표로 사용합니다.</p>
          </div>
        </div>
      </div>
      <h3>Eval set distribution</h3>
      <div class="two-col">
        <div>{bars(eval_difficulty)}</div>
        <div>{bars(eval_qtype)}</div>
      </div>
      <h3>Retrieval classification</h3>
      {bars(class_counts)}
    </section>

    <section class="card">
      <h2>5. 100개 Eval 인터랙티브 브라우저</h2>
      <p>100개 문항은 본문에 전부 나열하지 않고, 아래 필터/토글로 원하는 문항만 선택해 정량적으로 확인하도록 구성했습니다. 필터를 바꾸면 hit rate와 miss 수가 즉시 다시 계산됩니다.</p>
      {eval_browser_shell(eval_json)}
    </section>

    <section class="card">
      <h2>6. 남은 실패/주의 사례</h2>
      <p>최종 공식 기준에서 대부분은 hit이며, unrecovered는 <strong>{len(unrecovered)}건</strong>입니다. 핵심 잔여 사례는 <code>gmp_eval_025</code>입니다.</p>
      {notable_table(notable_items[:12])}
    </section>

    <section class="card">
      <h2>7. 보고서 기준 산출물</h2>
      <ul class="files">
        {file_item(WORKSPACE, 'PageIndex workspace')}
        {file_item(TREE, '최종 tree JSON')}
        {file_item(TREE_HTML, '기존 tree HTML 시각화')}
        {file_item(TREE_TXT, '기존 tree TXT 시각화')}
        {file_item(ALIGNMENT, 'page alignment map')}
        {file_item(EVAL, '100문항 평가셋')}
        {file_item(PREDICTIONS, 'Codex/PageIndex-style predictions')}
        {file_item(SCORE, '최종 official score')}
      </ul>
    </section>
  </main>
  <script>{eval_browser_js()}</script>
</body>
</html>
"""


def css() -> str:
    return """
    :root{--bg:#f6f7fb;--panel:#fff;--text:#111827;--muted:#64748b;--line:#e5e7eb;--blue:#2563eb;--blue2:#dbeafe;--green:#047857;--green2:#d1fae5;--amber:#b45309;--amber2:#fef3c7;--red:#b91c1c;--red2:#fee2e2;--shadow:0 14px 34px rgba(15,23,42,.07)}
    *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif;line-height:1.62} code{background:#f1f5f9;border:1px solid #e2e8f0;border-radius:6px;padding:.1rem .32rem;font-size:.92em} .page{max-width:1180px;margin:0 auto;padding:34px 24px 70px}.hero,.card{background:var(--panel);border:1px solid var(--line);border-radius:24px;box-shadow:var(--shadow)}.hero{padding:34px 38px;margin-bottom:18px;background:linear-gradient(135deg,#fff 0%,#f8fbff 100%)}.kicker{color:var(--blue);font-size:13px;font-weight:850;letter-spacing:.09em;text-transform:uppercase}.hero h1{font-size:42px;line-height:1.12;letter-spacing:-.04em;margin:9px 0 12px}.lead{color:var(--muted);font-size:17px;max-width:880px}.badges{display:flex;flex-wrap:wrap;gap:8px;margin-top:18px}.badge{display:inline-flex;border:1px solid var(--line);border-radius:999px;padding:7px 11px;font-size:13px;font-weight:750;background:#fff;color:#334155}.badge.ok{color:var(--green);background:var(--green2);border-color:#a7f3d0}.badge.warn{color:var(--amber);background:var(--amber2);border-color:#fde68a}.grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin:16px 0}.metric{background:#fff;border:1px solid var(--line);border-radius:18px;padding:18px;box-shadow:0 6px 18px rgba(15,23,42,.04)}.metric .label{color:var(--muted);font-size:12px;font-weight:850;letter-spacing:.05em;text-transform:uppercase}.metric .value{font-size:31px;font-weight:900;letter-spacing:-.04em;margin-top:7px}.metric .help{color:var(--muted);font-size:13px;margin-top:6px}.card{padding:28px 30px;margin:18px 0}.card h2{font-size:27px;letter-spacing:-.03em;margin:0 0 14px}.card h3{font-size:18px;margin:22px 0 10px}.two-col{display:grid;grid-template-columns:1fr 1fr;gap:18px}.note{background:#f8fafc;border:1px solid var(--line);border-radius:18px;padding:18px}.timeline{display:grid;gap:12px}.step{display:grid;grid-template-columns:58px 1fr;gap:14px;border:1px solid var(--line);border-radius:18px;padding:15px;background:#fff}.num{width:42px;height:42px;border-radius:999px;display:grid;place-items:center;background:#0f172a;color:#fff;font-weight:900}.step h4{margin:0 0 4px;font-size:16px}.step p{margin:0;color:var(--muted)}.refs{display:flex;flex-wrap:wrap;gap:6px;margin-top:9px}.ref{font-size:12px;border:1px solid #cbd5e1;background:#f8fafc;border-radius:999px;padding:3px 8px;color:#475569}.kv{display:grid;grid-template-columns:1fr auto;gap:7px 16px}.kv dt{color:var(--muted)}.kv dd{margin:0;font-weight:800}table{width:100%;border-collapse:separate;border-spacing:0;border:1px solid var(--line);border-radius:16px;overflow:hidden;background:#fff}th,td{text-align:left;padding:10px 12px;border-bottom:1px solid var(--line);vertical-align:top}th{background:#f8fafc;font-size:12px;color:#475569;text-transform:uppercase;letter-spacing:.05em}tr:last-child td{border-bottom:0}.bars{display:grid;gap:8px}.bar{display:grid;grid-template-columns:minmax(140px,1.2fr) 2fr 54px;gap:10px;align-items:center}.bar-label{font-size:13px;color:#334155;overflow:hidden;text-overflow:ellipsis}.bar-track{height:12px;background:#e2e8f0;border-radius:999px;overflow:hidden}.bar-fill{height:100%;background:#2563eb;border-radius:999px}.bar-count{text-align:right;color:#475569;font-size:13px}.toggle-btn{border:1px solid var(--line);background:#fff;color:#0f172a;border-radius:999px;padding:9px 14px;font-weight:800;cursor:pointer;margin:4px 0 12px}.toggle-btn:hover{background:#eff6ff;border-color:#bfdbfe}.ascii-tree{max-height:520px;overflow:auto;white-space:pre;font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;font-size:12px;line-height:1.55;background:#0f172a;color:#e5e7eb;border-radius:18px;padding:18px;border:1px solid #1e293b}.ascii-tree.expanded{max-height:none;overflow:visible}.tree-wrap{max-height:720px;overflow:auto;border:1px solid var(--line);border-radius:18px;background:#fbfdff;padding:16px}.tree details{margin:2px 0 2px 20px}.tree summary{cursor:pointer;padding:5px 6px;border-radius:8px}.tree summary:hover{background:#eff6ff}.tree .leaf{margin:2px 0 2px 20px;padding:5px 6px;color:#334155}.node-meta{color:#64748b;font-size:12px;margin-left:7px}.files{columns:2;gap:28px}.files li{break-inside:avoid;margin:0 0 8px}.muted{color:var(--muted)}.pill{display:inline-flex;border-radius:999px;padding:4px 8px;font-size:12px;font-weight:800}.pill.ok{background:var(--green2);color:var(--green)}.pill.warn{background:var(--amber2);color:var(--amber)}.pill.bad{background:var(--red2);color:var(--red)}.eval-controls{display:grid;grid-template-columns:1.5fr repeat(4,1fr);gap:10px;margin:14px 0}.eval-controls input,.eval-controls select{width:100%;border:1px solid var(--line);border-radius:12px;padding:10px 11px;background:#fff;color:#111827}.eval-summary{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:12px 0}.mini{border:1px solid var(--line);border-radius:14px;padding:12px;background:#f8fafc}.mini strong{display:block;font-size:22px}.eval-grid{display:grid;grid-template-columns:.9fr 1.1fr;gap:16px;margin-top:14px}.eval-list{max-height:430px;overflow:auto;border:1px solid var(--line);border-radius:16px}.eval-list table{border:0;border-radius:0}.eval-list tr{cursor:pointer}.eval-list tr:hover td{background:#eff6ff}.eval-detail{border:1px solid var(--line);border-radius:18px;background:#fff;padding:18px;min-height:430px}.path{font-size:13px;color:#475569;border-left:3px solid #cbd5e1;padding-left:10px}.pages{display:grid;grid-template-columns:repeat(2,1fr);gap:8px}.page-chip{background:#f8fafc;border:1px solid var(--line);border-radius:12px;padding:9px}.hit{color:var(--green)}.miss{color:var(--red)}@media(max-width:900px){.grid,.two-col,.eval-grid{grid-template-columns:1fr 1fr}.eval-controls{grid-template-columns:1fr 1fr}.hero h1{font-size:34px}.files{columns:1}}@media(max-width:620px){.grid,.two-col,.step,.eval-grid,.eval-summary,.pages{grid-template-columns:1fr}.page{padding:20px 14px}.hero,.card{padding:22px}.bar{grid-template-columns:1fr}.bar-count{text-align:left}.eval-controls{grid-template-columns:1fr}}
    """


def eval_browser_shell(eval_json: str) -> str:
    return f"""
      <script type="application/json" id="eval-data">{eval_json}</script>
      <div class="eval-controls">
        <input id="eval-search" placeholder="문항 ID, 질문, section path 검색" />
        <select id="eval-difficulty"><option value="">All difficulty</option></select>
        <select id="eval-qtype"><option value="">All question types</option></select>
        <select id="eval-class"><option value="">All classifications</option></select>
        <select id="eval-hit"><option value="">All hit states</option><option value="aligned-hit">Aligned hit</option><option value="aligned-miss">Aligned miss</option><option value="evidence-miss">Evidence+aligned miss</option></select>
      </div>
      <div class="eval-summary">
        <div class="mini"><span class="muted">Filtered rows</span><strong id="eval-count">0</strong></div>
        <div class="mini"><span class="muted">Aligned hit rate</span><strong id="eval-aligned-rate">0%</strong></div>
        <div class="mini"><span class="muted">Evidence+aligned hit rate</span><strong id="eval-evidence-rate">0%</strong></div>
        <div class="mini"><span class="muted">Aligned misses</span><strong id="eval-misses">0</strong></div>
      </div>
      <label class="muted" for="eval-select">문항 선택</label>
      <select id="eval-select"></select>
      <div class="eval-grid">
        <div class="eval-list"><table><thead><tr><th>ID</th><th>Diff</th><th>Type</th><th>Aligned</th><th>Gold</th></tr></thead><tbody id="eval-table"></tbody></table></div>
        <div class="eval-detail" id="eval-detail"></div>
      </div>
    """


def eval_browser_js() -> str:
    return r"""
(function(){
  document.querySelectorAll('[data-target]').forEach((button) => {
    button.addEventListener('click', () => {
      const target = document.getElementById(button.dataset.target);
      if (!target) return;
      const expanded = button.dataset.expanded === 'true';
      target.classList.toggle('expanded', !expanded);
      button.dataset.expanded = String(!expanded);
      button.textContent = expanded ? 'ASCII tree 전체 펼치기' : 'ASCII tree 접기';
    });
  });
  const dataEl = document.getElementById('eval-data');
  if(!dataEl) return;
  const rows = JSON.parse(dataEl.textContent);
  const $ = (id) => document.getElementById(id);
  const controls = ['eval-search','eval-difficulty','eval-qtype','eval-class','eval-hit'].map($);
  const uniq = (key) => [...new Set(rows.map(r => r[key]).filter(Boolean))].sort();
  function fillSelect(id, values){ const el=$(id); values.forEach(v => { const o=document.createElement('option'); o.value=v; o.textContent=v; el.appendChild(o); }); }
  fillSelect('eval-difficulty', uniq('difficulty'));
  fillSelect('eval-qtype', uniq('question_type'));
  fillSelect('eval-class', uniq('classification'));
  const esc = (v) => String(v ?? '').replace(/[&<>'"]/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[ch]));
  const path = (v) => Array.isArray(v) ? v.join(' › ') : String(v ?? '');
  function pass(v){ return v ? '<span class="pill ok">hit</span>' : '<span class="pill bad">miss</span>'; }
  function filtered(){
    const q = $('eval-search').value.trim().toLowerCase();
    const diff = $('eval-difficulty').value, qt = $('eval-qtype').value, cls = $('eval-class').value, hit = $('eval-hit').value;
    return rows.filter(r => {
      const text = [r.id,r.question,path(r.gold_section_path),path(r.predicted_section_path),r.expected_answer].join(' ').toLowerCase();
      if(q && !text.includes(q)) return false;
      if(diff && r.difficulty !== diff) return false;
      if(qt && r.question_type !== qt) return false;
      if(cls && r.classification !== cls) return false;
      if(hit === 'aligned-hit' && !r.aligned_hit) return false;
      if(hit === 'aligned-miss' && r.aligned_hit) return false;
      if(hit === 'evidence-miss' && r.evidence_hit) return false;
      return true;
    });
  }
  function render(){
    const list = filtered();
    const count = list.length || 1;
    const alignedHits = list.filter(r => r.aligned_hit).length;
    const evidenceHits = list.filter(r => r.evidence_hit).length;
    $('eval-count').textContent = String(list.length);
    $('eval-aligned-rate').textContent = (alignedHits / count * 100).toFixed(1) + '%';
    $('eval-evidence-rate').textContent = (evidenceHits / count * 100).toFixed(1) + '%';
    $('eval-misses').textContent = String(list.length - alignedHits);
    const select = $('eval-select');
    const old = select.value;
    select.innerHTML = '';
    list.forEach(r => { const o=document.createElement('option'); o.value=r.id; o.textContent=`${r.id} · ${r.question.slice(0,80)}`; select.appendChild(o); });
    if(list.some(r => r.id === old)) select.value = old;
    else if(list.some(r => r.id === 'gmp_eval_025')) select.value = 'gmp_eval_025';
    const tbody = $('eval-table');
    tbody.innerHTML = list.map(r => `<tr data-id="${esc(r.id)}"><td>${esc(r.id)}</td><td>${esc(r.difficulty)}</td><td>${esc(r.question_type)}</td><td>${pass(r.aligned_hit)}</td><td>${esc(r.gold_pages)}</td></tr>`).join('');
    tbody.querySelectorAll('tr').forEach(tr => tr.addEventListener('click', () => { select.value = tr.dataset.id; renderDetail(); }));
    renderDetail();
  }
  function renderDetail(){
    const id = $('eval-select').value;
    const r = rows.find(x => x.id === id) || filtered()[0];
    const d = $('eval-detail');
    if(!r){ d.innerHTML = '<p class="muted">필터에 맞는 문항이 없습니다.</p>'; return; }
    d.innerHTML = `
      <h3>${esc(r.id)} · ${esc(r.question)}</h3>
      <p>${pass(r.original_hit)} Original &nbsp; ${pass(r.aligned_hit)} Aligned &nbsp; ${pass(r.evidence_hit)} Evidence+aligned</p>
      <div class="pages">
        <div class="page-chip"><strong>Gold</strong><br>${esc(r.gold_pages)}</div>
        <div class="page-chip"><strong>Predicted</strong><br>${esc(r.predicted_pages)}</div>
        <div class="page-chip"><strong>Aligned predicted</strong><br>${esc(r.aligned_predicted_pages || 'N/A')}</div>
        <div class="page-chip"><strong>Evidence+aligned</strong><br>${esc(r.evidence_plus_aligned_pages || 'N/A')}</div>
      </div>
      <h4>Gold section</h4><div class="path">${esc(path(r.gold_section_path))}</div>
      <h4>Predicted section</h4><div class="path">${esc(path(r.predicted_section_path) || 'N/A')}</div>
      <h4>Expected answer</h4><p>${esc(r.expected_answer)}</p>
      <h4>Gold evidence summary</h4><p class="muted">${esc(r.gold_evidence_summary)}</p>
      <h4>Retriever reason</h4><p class="muted">${esc(r.reason || 'N/A')}</p>
      <p><span class="pill warn">${esc(r.classification)}</span> <span class="pill">${esc(r.difficulty)}</span> <span class="pill">${esc(r.question_type)}</span></p>`;
  }
  controls.forEach(el => el.addEventListener('input', render));
  $('eval-select').addEventListener('change', renderDetail);
  render();
})();
    """


def metric(label: str, value: str, help_text: str) -> str:
    return f"<div class='metric'><div class='label'>{esc(label)}</div><div class='value'>{esc(value)}</div><div class='help'>{esc(help_text)}</div></div>"


def step(num: str, title: str, text: str, refs: list[str]) -> str:
    refs_html = "".join(f"<span class='ref'>{esc(ref)}</span>" for ref in refs)
    return f"<div class='step'><div class='num'>{esc(num)}</div><div><h4>{esc(title)}</h4><p>{esc(text)}</p><div class='refs'>{refs_html}</div></div></div>"


def kv(k: str, v: Any) -> str:
    return f"<dt>{esc(k)}</dt><dd>{esc(str(v))}</dd>"


def top_table(rows: list[dict[str, Any]]) -> str:
    body = "".join(
        "<tr>" + td(row["node_id"]) + td(row["title"]) + td(row["nodes"]) + td(row["max_depth"]) + td(row["own_range"]) + td(row["subtree_range"]) + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr><th>ID</th><th>Top branch</th><th>Nodes</th><th>Max depth</th><th>Own pages</th><th>Subtree pages</th></tr></thead><tbody>{body}</tbody></table>"


def notable_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<p class='muted'>특이/실패 classification item이 없습니다.</p>"
    body = "".join(
        "<tr>"
        + td(row.get("id", ""))
        + td(row.get("classification", ""))
        + td(row.get("gold_pages", ""))
        + td(row.get("predicted_pages", ""))
        + td(row.get("aligned_predicted_pages", ""))
        + td(row.get("evidence_plus_aligned_pages", ""))
        + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr><th>ID</th><th>Classification</th><th>Gold</th><th>Predicted</th><th>Aligned</th><th>Evidence+aligned</th></tr></thead><tbody>{body}</tbody></table>"


def bars(counter: Counter, prefix: str = "") -> str:
    items = sorted(counter.items(), key=lambda x: (-x[1], str(x[0])))
    max_count = max((int(v) for _, v in items), default=1)
    body = "".join(
        f"<div class='bar'><div class='bar-label'>{esc(prefix + str(k))}</div><div class='bar-track'><div class='bar-fill' style='width:{(int(v)/max_count)*100:.1f}%'></div></div><div class='bar-count'>{int(v)}</div></div>"
        for k, v in items
    )
    return f"<div class='bars'>{body}</div>"


def tree_html(nodes: list[dict[str, Any]]) -> str:
    return "<div class='tree'>" + "".join(render_node(node, 0) for node in nodes) + "</div>"


def render_node(node: dict[str, Any], depth: int) -> str:
    title = str(node.get("title", "Untitled"))
    node_id = str(node.get("node_id", ""))
    own_start, own_end, subtree_start, subtree_end = node_range(node)
    meta = f"#{node_id} · own {fmt_range(own_start, own_end)} · subtree {fmt_range(subtree_start, subtree_end)}"
    kids = children(node)
    if not kids:
        return f"<div class='leaf'>{esc(title)} <span class='node-meta'>{esc(meta)}</span></div>"
    open_attr = " open" if depth < 2 else ""
    inner = "".join(render_node(child, depth + 1) for child in kids)
    return f"<details{open_attr}><summary>{esc(title)} <span class='node-meta'>{esc(meta)} · {len(kids)} children</span></summary>{inner}</details>"


def file_item(path: Path, label: str) -> str:
    exists = path.exists()
    size = path.stat().st_size if exists else 0
    cls = "ok" if exists else "bad"
    status = "exists" if exists else "missing"
    return f"<li><span class='pill {cls}'>{status}</span> <strong>{esc(label)}</strong><br><code>{esc(rel(path))}</code> <span class='muted'>({size:,} bytes)</span></li>"


def tr(label: str, value: str) -> str:
    return f"<tr><td>{esc(label)}</td><td><strong>{esc(value)}</strong></td></tr>"


def td(value: Any) -> str:
    return f"<td>{esc(str(value))}</td>"


def fmt_range(start: Any, end: Any) -> str:
    if start in (None, "") and end in (None, ""):
        return "N/A"
    return str(start) if start == end else f"{start}-{end}"


def pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def esc(value: Any) -> str:
    return escape(str(value), quote=True)


if __name__ == "__main__":
    raise SystemExit(main())
