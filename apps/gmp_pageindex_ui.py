#!/usr/bin/env python3
"""Streamlit shell for the local GMP PageIndex explorer.

Presentation UI scope: v0.1 document exploration and v0.2 evaluation
analysis. The v0.3 runner remains implemented in the core package, but is not
exposed here so demos stay local/offline/read-only by default.
"""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any, Iterable

import streamlit as st

from pageindex.ui_contracts import ArtifactLoadError, ArtifactPaths, ScoreSemantics, assert_canonical_score_view
from pageindex.ui_data import (
    eval_filter_options,
    load_app_view_model,
    load_page_view,
    parse_pages,
    search_pages,
    search_tree,
    summarize_eval_rows,
)


st.set_page_config(page_title="GMP PageIndex", page_icon="📄", layout="wide", initial_sidebar_state="expanded")


def main() -> None:
    _inject_css()
    paths = _paths_from_sidebar()
    try:
        vm = load_app_view_model(paths)
    except ArtifactLoadError as exc:
        _render_error(str(exc))
        st.stop()
        return

    _render_hero(vm)
    tab_doc, tab_eval = st.tabs(["v0.1 문서 탐색", "v0.2 Eval 분석"])
    with tab_doc:
        _render_document_explorer(vm)
    with tab_eval:
        _render_eval_explorer(vm)


def _inject_css() -> None:
    st.markdown(
        """
        <style>
        :root {
            --gmp-bg: #f7f8fb;
            --gmp-panel: #ffffff;
            --gmp-panel-soft: #f2f6fb;
            --gmp-text: #111827;
            --gmp-muted: #64748b;
            --gmp-border: #e5e7eb;
            --gmp-blue: #2563eb;
            --gmp-blue-soft: #dbeafe;
            --gmp-green: #047857;
            --gmp-green-soft: #d1fae5;
            --gmp-amber: #b45309;
            --gmp-amber-soft: #fef3c7;
            --gmp-red: #b91c1c;
            --gmp-red-soft: #fee2e2;
            --gmp-shadow: 0 10px 30px rgba(15, 23, 42, 0.06);
        }
        .stApp { background: var(--gmp-bg); color: var(--gmp-text); }
        section[data-testid="stSidebar"] { background: #ffffff; border-right: 1px solid var(--gmp-border); }
        div[data-testid="stVerticalBlock"] { gap: 1rem; }
        .block-container { padding-top: 2rem; padding-bottom: 3rem; max-width: 1420px; }
        h1, h2, h3 { letter-spacing: -0.03em; }
        .gmp-hero {
            border: 1px solid var(--gmp-border);
            border-radius: 22px;
            background: linear-gradient(135deg, #ffffff 0%, #f8fbff 100%);
            box-shadow: var(--gmp-shadow);
            padding: 28px 30px;
            margin: 0 0 18px 0;
        }
        .gmp-kicker { color: var(--gmp-blue); font-size: 13px; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
        .gmp-title { font-size: 36px; line-height: 1.14; font-weight: 850; margin: 8px 0 10px; color: #0f172a; }
        .gmp-subtitle { color: var(--gmp-muted); font-size: 16px; line-height: 1.65; margin: 0; max-width: 930px; }
        .gmp-badges { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 18px; }
        .gmp-badge {
            display: inline-flex; align-items: center; gap: 7px;
            border-radius: 999px; border: 1px solid var(--gmp-border);
            background: #fff; padding: 7px 11px; font-size: 13px; color: #334155; font-weight: 650;
        }
        .gmp-badge.blue { color: #1d4ed8; background: var(--gmp-blue-soft); border-color: #bfdbfe; }
        .gmp-badge.green { color: var(--gmp-green); background: var(--gmp-green-soft); border-color: #a7f3d0; }
        .gmp-badge.amber { color: var(--gmp-amber); background: var(--gmp-amber-soft); border-color: #fde68a; }
        .gmp-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; margin: 12px 0 20px; }
        .gmp-card {
            border: 1px solid var(--gmp-border); border-radius: 18px; background: var(--gmp-panel);
            box-shadow: 0 6px 18px rgba(15, 23, 42, 0.04); padding: 18px;
        }
        .gmp-card.soft { background: var(--gmp-panel-soft); }
        .gmp-label { color: var(--gmp-muted); font-size: 12px; font-weight: 750; text-transform: uppercase; letter-spacing: .05em; }
        .gmp-value { color: #0f172a; font-size: 30px; line-height: 1.1; font-weight: 850; margin-top: 7px; }
        .gmp-help { color: var(--gmp-muted); font-size: 13px; line-height: 1.45; margin-top: 8px; }
        .gmp-section-title { font-size: 22px; font-weight: 820; letter-spacing: -0.025em; margin: 4px 0 4px; }
        .gmp-section-copy { color: var(--gmp-muted); font-size: 14px; line-height: 1.6; margin-bottom: 10px; }
        .gmp-candidate {
            border: 1px solid var(--gmp-border); border-radius: 16px; background: #fff;
            padding: 14px 15px; margin: 0 0 10px 0;
        }
        .gmp-candidate-title { font-weight: 780; color: #111827; font-size: 15px; line-height: 1.45; }
        .gmp-candidate-meta { display: flex; flex-wrap: wrap; gap: 7px; margin: 9px 0; }
        .gmp-path { color: var(--gmp-muted); font-size: 12.5px; line-height: 1.55; }
        .gmp-page-line { color: #334155; font-size: 13px; line-height: 1.6; border-left: 3px solid #cbd5e1; padding-left: 10px; margin-top: 8px; }
        .gmp-divider { height: 1px; background: var(--gmp-border); margin: 12px 0; }
        .gmp-score-note {
            border: 1px solid #bfdbfe; background: #eff6ff; color: #1e3a8a;
            padding: 13px 15px; border-radius: 16px; line-height: 1.6; font-size: 14px; margin-bottom: 16px;
        }
        .gmp-status-hit { color: var(--gmp-green); background: var(--gmp-green-soft); border: 1px solid #a7f3d0; }
        .gmp-status-miss { color: var(--gmp-red); background: var(--gmp-red-soft); border: 1px solid #fecaca; }
        .gmp-status-neutral { color: #475569; background: #f1f5f9; border: 1px solid #cbd5e1; }
        .gmp-status {
            display: inline-flex; align-items: center; border-radius: 999px; padding: 6px 10px;
            font-size: 12px; font-weight: 760; white-space: nowrap;
        }
        div[data-testid="stMetric"] {
            background: #ffffff; border: 1px solid var(--gmp-border); border-radius: 16px;
            padding: 14px 16px; box-shadow: 0 6px 16px rgba(15, 23, 42, 0.035);
        }
        div[data-testid="stTextArea"] textarea { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 13px; line-height: 1.55; }
        .stTabs [data-baseweb="tab-list"] { gap: 8px; }
        .stTabs [data-baseweb="tab"] {
            background: #ffffff; border: 1px solid var(--gmp-border); border-radius: 999px;
            padding: 9px 16px; color: #334155;
        }
        .stTabs [aria-selected="true"] { background: #0f172a !important; color: #ffffff !important; border-color: #0f172a !important; }
        @media (max-width: 980px) { .gmp-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } .gmp-title { font-size: 30px; } }
        @media (max-width: 640px) { .gmp-grid { grid-template-columns: 1fr; } .gmp-hero { padding: 22px; } }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _paths_from_sidebar() -> ArtifactPaths:
    st.sidebar.markdown("### 데이터 소스")
    st.sidebar.caption("발표용 화면은 기존 로컬 산출물만 읽습니다. v0.3 실행 기능은 숨겨져 있습니다.")
    workspace_json = Path(st.sidebar.text_input("workspace", "results/pageindex_gmp_workspace/gmp-guidance.json"))
    alignment_map_json = Path(st.sidebar.text_input("alignment map", "results/page_alignment/gmp_page_alignment_map.json"))
    official_score_json = Path(st.sidebar.text_input("official score", "results/page_alignment/score_001_100_agentic_official_alignment.json"))
    eval_jsonl = Path(st.sidebar.text_input("eval jsonl", "eval/gmp_eval_testset.jsonl"))
    predictions_jsonl = Path(st.sidebar.text_input("canonical predictions", "results/codex_agentic_10x10/predictions_001_100_agentic.jsonl"))
    repaired_predictions_jsonl = Path(
        st.sidebar.text_input(
            "diagnostic predictions",
            "results/codex_agentic_10x10/predictions_001_100_agentic_repaired_append_direct.jsonl",
        )
    )
    st.sidebar.markdown("---")
    st.sidebar.caption("UI 기준: `DESIGN.md` / v0.1+v0.2 presentation mode")
    return ArtifactPaths(
        workspace_json=workspace_json,
        alignment_map_json=alignment_map_json,
        official_score_json=official_score_json,
        eval_jsonl=eval_jsonl,
        predictions_jsonl=predictions_jsonl,
        repaired_predictions_jsonl=repaired_predictions_jsonl,
    )


def _render_hero(vm) -> None:
    canonical = vm.canonical_score
    assert_canonical_score_view(canonical)
    diagnostic = vm.diagnostic_score
    original = vm.scores[ScoreSemantics.ORIGINAL_093]
    unresolved = ", ".join(vm.corpus.unresolved_ids) or "none"

    _html(
        f"""
        <section class="gmp-hero">
          <div class="gmp-kicker">Local GMP Retrieval Dashboard</div>
          <div class="gmp-title">GMP PageIndex Explorer</div>
          <p class="gmp-subtitle">
            PDF tree, page alignment, and 100-question retrieval evaluation을 한 화면에서 검토하는 발표용 로컬 대시보드입니다.
            기본 화면은 파일 기반 read-only이며 API 호출이나 v0.3 실행 버튼을 노출하지 않습니다.
          </p>
          <div class="gmp-badges">
            <span class="gmp-badge green">● Offline / read-only</span>
            <span class="gmp-badge blue">Canonical score locked to 0.96</span>
            <span class="gmp-badge amber">Unresolved: {escape(unresolved)}</span>
          </div>
        </section>
        <div class="gmp-grid">
          {_metric_card('Canonical page hit', f'{canonical.value:.2f}', '공식 발표 기준 · aligned predicted union', 'blue')}
          {_metric_card('Original page hit', f'{original.value:.2f}', 'alignment 보정 전 예측 page hit', '')}
          {_metric_card('Diagnostic coverage', f'{diagnostic.value:.2f}', 'evidence+aligned 진단값 · 공식 점수 아님', 'green')}
          {_metric_card('Corpus', f'{vm.corpus.page_count:,}p', f'{vm.corpus.tree_node_count:,} tree nodes · {vm.corpus.mapped_internal_pages:,} mapped', '')}
        </div>
        <div class="gmp-score-note">
          <strong>Score rule.</strong> 이 UI의 공식 기준은 <strong>0.96 aligned predicted union</strong>입니다.
          <strong>0.99</strong>는 evidence page까지 포함한 진단용 coverage이므로 발표 화면에서도 보조 지표로만 표시합니다.
        </div>
        """
    )

    with st.expander("Artifact / corpus metadata", expanded=False):
        st.json(
            {
                "doc_id": vm.corpus.doc_id,
                "doc_name": vm.corpus.doc_name,
                "page_count": vm.corpus.page_count,
                "tree_node_count": vm.corpus.tree_node_count,
                "mapped_internal_pages": vm.corpus.mapped_internal_pages,
                "dominant_offset": vm.corpus.dominant_offset,
                "unresolved_ids": vm.corpus.unresolved_ids,
            }
        )


def _render_document_explorer(vm) -> None:
    _section_heading(
        "v0.1 문서 탐색",
        "질문을 입력하면 tree/section 후보와 실제 PDF page content를 함께 확인합니다.",
    )
    query = st.text_input("질문 또는 키워드", "공정 밸리데이션은 어떤 단위로 실시하여야 하는가?", key="doc-query")
    left, right = st.columns([1.05, 1.45], gap="large")

    with left:
        _panel_title("Tree / section candidates", "질문 의미와 제목/path 토큰이 가까운 섹션 후보")
        candidates = search_tree(query, vm.tree_nodes, limit=12) if query else list(vm.tree_nodes[:12])
        if not candidates:
            st.warning("Tree 후보가 없습니다. 다른 키워드를 입력해보세요.")
        for idx, node in enumerate(candidates, 1):
            _render_tree_candidate(idx, node)

    with right:
        _panel_title("Page evidence", "physical/internal/aligned page를 함께 보여주는 원문 확인 영역")
        page_candidates = search_pages(query, vm.paths, limit=8) if query else []
        default_page = page_candidates[0].physical_page if page_candidates else 1
        page = st.number_input("Physical PDF page", min_value=1, max_value=vm.corpus.page_count, value=int(default_page), step=1)
        try:
            page_view = load_page_view(int(page), vm.paths)
        except ArtifactLoadError as exc:
            st.error(str(exc))
            return
        c1, c2, c3 = st.columns(3)
        c1.metric("Physical page", page_view.physical_page)
        c2.metric("Internal label", page_view.internal_page if page_view.internal_page is not None else "N/A")
        c3.metric("Aligned physical", page_view.aligned_from_internal if page_view.aligned_from_internal is not None else "N/A")
        _html(f'<div class="gmp-page-line">{escape(page_view.first_line or "첫 줄 정보 없음")}</div>')
        st.text_area("Page text", page_view.content, height=430, label_visibility="collapsed")
        if page_candidates:
            _panel_title("Text search page candidates", "원문 텍스트 기준 관련 page 후보")
            for pv in page_candidates:
                _html(
                    f"""
                    <div class="gmp-candidate">
                      <div class="gmp-candidate-title">p.{pv.physical_page} <span class="gmp-path">/ internal {pv.internal_page or 'N/A'}</span></div>
                      <div class="gmp-page-line">{escape(pv.first_line)}</div>
                    </div>
                    """
                )


def _render_eval_explorer(vm) -> None:
    _section_heading(
        "v0.2 Eval 분석",
        "100개 평가셋에서 hit/miss, section path, predicted/evidence page를 필터링해 검토합니다.",
    )
    rows = list(vm.eval_rows)
    options = eval_filter_options(rows)
    c1, c2, c3, c4 = st.columns(4)
    difficulty = c1.multiselect("difficulty", options["difficulty"], default=options["difficulty"])
    qtype = c2.multiselect("question_type", options["question_type"], default=options["question_type"])
    classifications = c3.multiselect("classification", options["classification"], default=options["classification"])
    hit_view = c4.selectbox("hit view", ["all", "original miss", "aligned miss", "evidence+aligned miss", "unresolved only"], index=0)
    text_filter = st.text_input("row text filter", "", placeholder="질문, row id, section path 검색")

    filtered = [
        row
        for row in rows
        if row.difficulty in difficulty
        and row.question_type in qtype
        and row.classification in classifications
        and (not text_filter or text_filter.lower() in (row.row_id + row.question + " ".join(row.gold_section_path)).lower())
    ]
    if hit_view == "original miss":
        filtered = [row for row in filtered if not row.original_hit]
    elif hit_view == "aligned miss":
        filtered = [row for row in filtered if not row.aligned_hit]
    elif hit_view == "evidence+aligned miss":
        filtered = [row for row in filtered if not row.evidence_plus_aligned_hit]
    elif hit_view == "unresolved only":
        filtered = [row for row in filtered if row.row_id in vm.corpus.unresolved_ids]

    summary = summarize_eval_rows(filtered)
    _html(
        f"""
        <div class="gmp-grid">
          {_metric_card('Filtered rows', str(summary['items']), '현재 필터에 남은 문항 수', '')}
          {_metric_card('Original hits', str(summary['original_hits']), '원본 predicted page hit', '')}
          {_metric_card('Aligned hits', str(summary['aligned_hits']), '공식 canonical hit 기준', 'blue')}
          {_metric_card('Evidence+aligned', str(summary['evidence_plus_aligned_hits']), '진단 coverage 기준', 'green')}
        </div>
        """
    )

    if not filtered:
        st.warning("조건에 맞는 eval row가 없습니다.")
        return

    with st.expander("Filtered row overview", expanded=False):
        st.dataframe(
            [
                {
                    "id": row.row_id,
                    "difficulty": row.difficulty,
                    "type": row.question_type,
                    "class": row.classification,
                    "aligned": "hit" if row.aligned_hit else "miss",
                    "gold_pages": row.gold_pages,
                    "predicted_pages": row.aligned_predicted_pages or row.predicted_pages,
                    "question": row.question,
                }
                for row in filtered
            ],
            use_container_width=True,
            hide_index=True,
        )

    selected_id = st.selectbox("Eval row", [row.row_id for row in filtered], index=0)
    row = next(row for row in filtered if row.row_id == selected_id)
    _render_eval_row(row, vm)


def _render_eval_row(row, vm) -> None:
    _html(
        f"""
        <div class="gmp-card">
          <div class="gmp-label">Selected eval row</div>
          <div class="gmp-section-title">{escape(row.row_id)} · {escape(row.question)}</div>
          <div class="gmp-candidate-meta">
            {_status('Original', row.original_hit)}
            {_status('Aligned', row.aligned_hit)}
            {_status('Evidence+aligned', row.evidence_plus_aligned_hit)}
            <span class="gmp-status gmp-status-neutral">{escape(row.difficulty)}</span>
            <span class="gmp-status gmp-status-neutral">{escape(row.question_type)}</span>
            <span class="gmp-status gmp-status-neutral">{escape(row.classification)}</span>
          </div>
        </div>
        """
    )

    left, right = st.columns([1, 1], gap="large")
    with left:
        _panel_title("Section path", "gold와 predicted section을 비교합니다")
        _path_card("Gold section", row.gold_section_path, tone="green")
        _path_card("Predicted section", row.predicted_section_path, tone="blue")
        _panel_title("Expected answer", "평가셋의 기대 답변")
        st.write(row.expected_answer)
        if row.reason:
            _panel_title("Retriever reason", "retriever가 남긴 판단 근거")
            st.write(row.reason)

    with right:
        _panel_title("Page sets", "gold / predicted / aligned / evidence page 비교")
        st.json(
            {
                "gold_pages": row.gold_pages,
                "predicted_pages": row.predicted_pages,
                "aligned_predicted_pages": row.aligned_predicted_pages,
                "evidence_pages_read": row.evidence_pages_read,
                "aligned_evidence_pages_read": row.aligned_evidence_pages_read,
                "evidence_plus_aligned_pages": row.evidence_plus_aligned_pages,
            }
        )

    page_options = sorted(
        set(
            parse_pages(row.predicted_pages)
            + parse_pages(row.aligned_predicted_pages)
            + parse_pages(row.evidence_plus_aligned_pages)
            + parse_pages(row.gold_pages)
        )
    )
    if page_options:
        page = st.selectbox("Open related page", page_options, index=0, key=f"page-{row.row_id}")
        pv = load_page_view(int(page), vm.paths)
        _html(
            f'<div class="gmp-page-line">Physical p.{pv.physical_page} / internal {pv.internal_page or "N/A"} / first line: {escape(pv.first_line)}</div>'
        )
        st.text_area("Related page content", pv.content, height=320, key=f"content-{row.row_id}-{page}", label_visibility="collapsed")


def _render_tree_candidate(idx: int, node: Any) -> None:
    path = " › ".join(str(part) for part in node.path)
    _html(
        f"""
        <div class="gmp-candidate">
          <div class="gmp-candidate-title">{idx}. {escape(node.title)}</div>
          <div class="gmp-candidate-meta">
            <span class="gmp-status gmp-status-neutral">node {escape(node.node_id)}</span>
            <span class="gmp-status gmp-status-neutral">p.{escape(str(node.page_range))}</span>
            <span class="gmp-status gmp-status-neutral">subtree {escape(str(node.subtree_range))}</span>
            <span class="gmp-status gmp-status-neutral">score {node.score:.2f}</span>
          </div>
          <div class="gmp-path">{escape(path)}</div>
        </div>
        """
    )


def _path_card(label: str, path: Iterable[str], tone: str = "") -> None:
    value = " › ".join(path) if path else "N/A"
    tone_class = "green" if tone == "green" else "blue" if tone == "blue" else ""
    _html(
        f"""
        <div class="gmp-candidate">
          <span class="gmp-badge {tone_class}">{escape(label)}</span>
          <div class="gmp-path" style="margin-top:10px;">{escape(value)}</div>
        </div>
        """
    )


def _section_heading(title: str, copy: str) -> None:
    _html(f'<div class="gmp-section-title">{escape(title)}</div><div class="gmp-section-copy">{escape(copy)}</div>')


def _panel_title(title: str, copy: str) -> None:
    _html(f'<div class="gmp-label" style="margin-top:4px;">{escape(title)}</div><div class="gmp-help" style="margin-bottom:10px;">{escape(copy)}</div>')


def _metric_card(label: str, value: str, help_text: str, tone: str) -> str:
    tone_class = " soft" if tone in {"blue", "green"} else ""
    return (
        f'<div class="gmp-card{tone_class}">'
        f'<div class="gmp-label">{escape(label)}</div>'
        f'<div class="gmp-value">{escape(value)}</div>'
        f'<div class="gmp-help">{escape(help_text)}</div>'
        '</div>'
    )


def _status(label: str, ok: bool) -> str:
    klass = "gmp-status-hit" if ok else "gmp-status-miss"
    text = "hit" if ok else "miss"
    return f'<span class="gmp-status {klass}">{escape(label)}: {text}</span>'


def _render_error(message: str) -> None:
    _html(
        f"""
        <div class="gmp-card">
          <div class="gmp-label">Artifact load error</div>
          <div class="gmp-section-title">필수 로컬 산출물을 읽을 수 없습니다</div>
          <div class="gmp-help">{escape(message)}</div>
        </div>
        """
    )


def _html(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
