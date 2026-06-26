"""Local artifact loading and view normalization for the GMP PageIndex UI.

This module is deliberately Streamlit-free. It reads existing local artifacts,
normalizes them into typed view objects, and fails closed on missing/malformed
inputs instead of silently falling back to stale data.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from .ui_contracts import (
    AppViewModel,
    ArtifactLoadError,
    ArtifactPaths,
    CorpusSummary,
    EvalRowView,
    PageView,
    ScoreSemantics,
    ScoreView,
    TreeNodeView,
    assert_canonical_score_view,
)

STOPWORDS = {
    "한다",
    "있는",
    "없는",
    "또는",
    "그리고",
    "에서",
    "으로",
    "에게",
    "대한",
    "관련",
    "경우",
    "문서",
    "기준",
    "정답",
    "취지",
    "페이지",
    "섹션",
    "항목",
    "명시",
    "기재",
    "하여",
    "해야",
    "하여야",
    "있다",
    "된다",
    "관리",
    "제조",
    "품질",
    "제품",
    "의약품",
    "완제의약품",
}


def load_app_view_model(paths: ArtifactPaths | None = None) -> AppViewModel:
    paths = paths or ArtifactPaths()
    workspace = _read_json(paths.workspace_json)
    alignment = _read_json(paths.alignment_map_json)
    score = _read_json(paths.official_score_json)
    eval_rows = _read_jsonl(paths.eval_jsonl)
    predictions = _read_jsonl(paths.predictions_jsonl)

    _validate_workspace(workspace, paths.workspace_json)
    _validate_alignment(alignment, paths.alignment_map_json)
    _validate_score(score, paths.official_score_json)

    tree_nodes = tuple(_flatten_tree(workspace.get("structure") or []))
    scores = _build_score_views(score)
    assert_canonical_score_view(scores[ScoreSemantics.CANONICAL_096])

    eval_views = tuple(_build_eval_views(eval_rows, predictions, score))
    corpus = CorpusSummary(
        doc_id=str(workspace.get("id", "")),
        doc_name=str(workspace.get("doc_name", "")),
        page_count=int(workspace.get("page_count") or len(workspace.get("pages") or [])),
        tree_node_count=len(tree_nodes),
        mapped_internal_pages=int(alignment.get("mapped_page_count") or len(alignment.get("internal_to_physical") or {})),
        dominant_offset=alignment.get("dominant_offset"),
        unresolved_ids=tuple(item.get("id", "") for item in (score.get("alignment_prediction_evaluation", {}).get("unrecovered_after_evidence_alignment") or [])),
    )
    return AppViewModel(corpus=corpus, scores=scores, tree_nodes=tree_nodes, eval_rows=eval_views, paths=paths)


def load_page_view(physical_page: int, paths: ArtifactPaths | None = None) -> PageView:
    paths = paths or ArtifactPaths()
    workspace = _read_json(paths.workspace_json)
    alignment = _read_json(paths.alignment_map_json)
    pages = workspace.get("pages") or []
    page_by_number = {int(item.get("page")): item for item in pages}
    item = page_by_number.get(int(physical_page))
    if not item:
        raise ArtifactLoadError(f"Physical page {physical_page} is not present in {paths.workspace_json}.")
    content = str(item.get("content", ""))
    physical_to_internal = {int(k): int(v) for k, v in (alignment.get("physical_to_internal") or {}).items()}
    internal_to_physical = {int(k): int(v) for k, v in (alignment.get("internal_to_physical") or {}).items()}
    internal = physical_to_internal.get(int(physical_page))
    aligned_from_internal = internal_to_physical.get(internal) if internal is not None else None
    return PageView(
        physical_page=int(physical_page),
        internal_page=internal,
        aligned_from_internal=aligned_from_internal,
        first_line=_first_line(content),
        content=content,
    )


def search_tree(query: str, tree_nodes: Iterable[TreeNodeView], limit: int = 12) -> list[TreeNodeView]:
    query_tokens = set(tokenize(query))
    compact_query = compact(query)
    scored: list[TreeNodeView] = []
    for node in tree_nodes:
        haystack = " > ".join(node.path)
        hay_tokens = set(tokenize(haystack))
        overlap = query_tokens & hay_tokens
        title_bonus = 0.0
        if compact_query and compact(node.title) and compact(node.title) in compact_query:
            title_bonus += 4.0
        path_bonus = sum(1.0 for part in node.path if compact(part) and compact(part) in compact_query)
        score = (len(overlap) * 2.0) + title_bonus + path_bonus - (0.03 * max(0, node.depth - 2))
        if score > 0:
            scored.append(_replace_tree_score(node, score))
    return sorted(scored, key=lambda node: (node.score, -node.depth), reverse=True)[:limit]


def search_pages(query: str, paths: ArtifactPaths | None = None, limit: int = 8) -> list[PageView]:
    paths = paths or ArtifactPaths()
    workspace = _read_json(paths.workspace_json)
    query_tokens = set(tokenize(query))
    scored: list[tuple[float, int]] = []
    for item in workspace.get("pages") or []:
        page = int(item.get("page"))
        text = str(item.get("content", ""))
        overlap = query_tokens & set(tokenize(text))
        phrase_bonus = 2.5 if compact(query) and compact(query) in compact(text) else 0.0
        score = len(overlap) + phrase_bonus
        if score > 0:
            scored.append((score, page))
    pages = [page for _, page in sorted(scored, key=lambda pair: (pair[0], -pair[1]), reverse=True)[:limit]]
    return [load_page_view(page, paths) for page in pages]


def eval_filter_options(rows: Iterable[EvalRowView]) -> dict[str, list[str]]:
    rows = list(rows)
    return {
        "difficulty": sorted(set(row.difficulty for row in rows)),
        "question_type": sorted(set(row.question_type for row in rows)),
        "classification": sorted(set(row.classification for row in rows)),
    }


def summarize_eval_rows(rows: Iterable[EvalRowView]) -> dict[str, Any]:
    rows = list(rows)
    return {
        "items": len(rows),
        "original_hits": sum(1 for row in rows if row.original_hit),
        "aligned_hits": sum(1 for row in rows if row.aligned_hit),
        "evidence_plus_aligned_hits": sum(1 for row in rows if row.evidence_plus_aligned_hit),
        "classification_counts": dict(Counter(row.classification for row in rows)),
    }


def parse_pages(pages: Any) -> list[int]:
    if pages is None:
        return []
    text = str(pages).strip()
    if not text:
        return []
    out: set[int] = set()
    for part in re.split(r"\s*,\s*", text):
        if not part:
            continue
        if re.fullmatch(r"\d+", part):
            out.add(int(part))
            continue
        m = re.fullmatch(r"(\d+)\s*-\s*(\d+)", part)
        if m:
            start, end = int(m.group(1)), int(m.group(2))
            if start > end:
                raise ArtifactLoadError(f"Reversed page range: {part}")
            out.update(range(start, end + 1))
            continue
        raise ArtifactLoadError(f"Invalid page token: {part!r}")
    return sorted(out)


def pages_to_range(pages: Iterable[int]) -> str:
    ordered = sorted(set(int(page) for page in pages))
    if not ordered:
        return ""
    chunks: list[str] = []
    start = prev = ordered[0]
    for page in ordered[1:]:
        if page == prev + 1:
            prev = page
            continue
        chunks.append(str(start) if start == prev else f"{start}-{prev}")
        start = prev = page
    chunks.append(str(start) if start == prev else f"{start}-{prev}")
    return ",".join(chunks)


def tokenize(text: Any) -> list[str]:
    tokens = re.findall(r"[가-힣A-Za-z0-9]{2,}", str(text or "").lower())
    normalized = [_normalize_token(tok) for tok in tokens]
    return [tok for tok in normalized if tok and tok not in STOPWORDS]


def compact(text: Any) -> str:
    return re.sub(r"\s+", "", str(text or ""))


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ArtifactLoadError(f"Required artifact is missing: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ArtifactLoadError(f"Invalid JSON artifact {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ArtifactLoadError(f"Expected object JSON artifact: {path}")
    return payload


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise ArtifactLoadError(f"Required artifact is missing: {path}")
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ArtifactLoadError(f"Invalid JSONL artifact {path}:{line_no}: {exc}") from exc
        if not isinstance(row, dict):
            raise ArtifactLoadError(f"Expected object JSONL row at {path}:{line_no}")
        rows.append(row)
    return rows


def _validate_workspace(payload: dict[str, Any], path: Path) -> None:
    for key in ("id", "page_count", "structure", "pages"):
        if key not in payload:
            raise ArtifactLoadError(f"Workspace artifact {path} missing key: {key}")
    if not isinstance(payload.get("structure"), list) or not isinstance(payload.get("pages"), list):
        raise ArtifactLoadError(f"Workspace artifact {path} has invalid structure/pages shape.")


def _validate_alignment(payload: dict[str, Any], path: Path) -> None:
    for key in ("dominant_offset", "internal_to_physical", "physical_to_internal"):
        if key not in payload:
            raise ArtifactLoadError(f"Alignment artifact {path} missing key: {key}")


def _validate_score(payload: dict[str, Any], path: Path) -> None:
    if "alignment_prediction_evaluation" not in payload:
        raise ArtifactLoadError(f"Official score artifact {path} lacks alignment_prediction_evaluation.")
    metrics = payload.get("alignment_prediction_evaluation", {}).get("metrics") or {}
    for key in ("aligned_predicted_union_hit_rate", "evidence_plus_aligned_hit_rate"):
        if key not in metrics:
            raise ArtifactLoadError(f"Official score artifact {path} missing metric: {key}")


def _build_score_views(score: dict[str, Any]) -> dict[ScoreSemantics, ScoreView]:
    alignment_metrics = score.get("alignment_prediction_evaluation", {}).get("metrics") or {}
    prediction_metrics = score.get("prediction_evaluation", {}).get("metrics") or {}
    canonical = ScoreView(
        semantics=ScoreSemantics.CANONICAL_096,
        label="Canonical aligned page hit",
        value=float(alignment_metrics["aligned_predicted_union_hit_rate"]),
        description="공식 UI 기본값: original predicted pages + internal→physical page alignment. 0.99 coverage를 섞지 않습니다.",
        is_canonical=True,
    )
    original = ScoreView(
        semantics=ScoreSemantics.ORIGINAL_093,
        label="Original predicted page hit",
        value=float(prediction_metrics.get("predicted_page_hit_rate", 0.0)),
        description="원본 Codex prediction JSONL만 평가한 보수 기준입니다.",
    )
    diagnostic = ScoreView(
        semantics=ScoreSemantics.DIAGNOSTIC_099,
        label="Diagnostic evidence coverage",
        value=float(alignment_metrics["evidence_plus_aligned_hit_rate"]),
        description="진단 전용: predicted/evidence pages + alignment coverage. Canonical header에 쓰면 안 됩니다.",
    )
    return {view.semantics: view for view in (canonical, original, diagnostic)}


def _flatten_tree(nodes: list[dict[str, Any]], path: tuple[str, ...] = ()) -> list[TreeNodeView]:
    out: list[TreeNodeView] = []
    for node in nodes:
        title = str(node.get("title", ""))
        current = path + (title,)
        start = node.get("start_index") or node.get("own_start_index")
        end = node.get("end_index") or node.get("own_end_index") or start
        subtree_start = node.get("subtree_start_index") or start
        subtree_end = node.get("subtree_end_index") or end or subtree_start
        out.append(
            TreeNodeView(
                node_id=str(node.get("node_id", "")),
                title=title,
                path=current,
                depth=len(current),
                page_range=_format_range(start, end),
                subtree_range=_format_range(subtree_start, subtree_end),
            )
        )
        out.extend(_flatten_tree(node.get("nodes") or [], current))
    return out


def _build_eval_views(eval_rows: list[dict[str, Any]], predictions: list[dict[str, Any]], score: dict[str, Any]) -> list[EvalRowView]:
    pred_by_id = {str(row.get("id")): row for row in predictions}
    alignment_items = {
        str(item.get("id")): item
        for item in (score.get("alignment_prediction_evaluation", {}).get("items") or [])
    }
    views: list[EvalRowView] = []
    for row in eval_rows:
        row_id = str(row.get("id", ""))
        pred = pred_by_id.get(row_id, {})
        alignment = alignment_items.get(row_id, {})
        original_metrics = alignment.get("original_page_metrics") or {}
        aligned_metrics = alignment.get("aligned_predicted_union_metrics") or {}
        evidence_metrics = alignment.get("evidence_plus_aligned_metrics") or {}
        views.append(
            EvalRowView(
                row_id=row_id,
                question=str(row.get("question", "")),
                difficulty=str(row.get("difficulty", "")),
                question_type=str(row.get("question_type", "")),
                expected_answer=str(row.get("expected_answer", "")),
                gold_pages=str(row.get("gold_pages", "")),
                gold_section_path=tuple(str(part) for part in (row.get("gold_section_path") or [])),
                predicted_pages=str(pred.get("predicted_pages", "")),
                aligned_predicted_pages=str(alignment.get("aligned_predicted_pages", "")),
                evidence_pages_read=str(pred.get("evidence_pages_read", "")),
                aligned_evidence_pages_read=str(alignment.get("aligned_evidence_pages_read", "")),
                evidence_plus_aligned_pages=str(alignment.get("evidence_plus_aligned_pages", "")),
                original_hit=bool(original_metrics.get("hit")),
                aligned_hit=bool(aligned_metrics.get("hit")),
                evidence_plus_aligned_hit=bool(evidence_metrics.get("hit")),
                classification=str(alignment.get("classification", "unknown")),
                predicted_section_path=tuple(str(part) for part in (pred.get("predicted_section_path") or [])),
                reason=str(pred.get("reason", "")),
            )
        )
    return views


def _replace_tree_score(node: TreeNodeView, score: float) -> TreeNodeView:
    return TreeNodeView(
        node_id=node.node_id,
        title=node.title,
        path=node.path,
        depth=node.depth,
        page_range=node.page_range,
        subtree_range=node.subtree_range,
        score=round(score, 4),
    )


def _format_range(start: Any, end: Any) -> str:
    if start is None:
        return ""
    start_i = int(start)
    end_i = int(end if end is not None else start_i)
    return str(start_i) if start_i == end_i else f"{start_i}-{end_i}"


def _first_line(content: str) -> str:
    return next((line.strip() for line in content.splitlines() if line.strip()), "")[:180]


def _normalize_token(token: str) -> str:
    token = token.lower().strip()
    suffixes = [
        "하여야",
        "하여",
        "하는",
        "한다",
        "된다",
        "되어",
        "하며",
        "하고",
        "까지",
        "부터",
        "에서",
        "으로",
        "에게",
        "에는",
        "로서",
        "로써",
        "들을",
        "으로서",
        "으로써",
        "과의",
        "와의",
        "의",
        "을",
        "를",
        "이",
        "가",
        "은",
        "는",
        "에",
        "와",
        "과",
        "도",
        "만",
    ]
    changed = True
    while changed:
        changed = False
        for suffix in suffixes:
            if token.endswith(suffix) and len(token) > len(suffix) + 1:
                token = token[: -len(suffix)]
                changed = True
                break
    return token
