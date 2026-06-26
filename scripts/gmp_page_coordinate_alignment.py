#!/usr/bin/env python3
"""Build and apply a GMP PageIndex page-coordinate alignment audit.

The GMP PDF workspace exposes PageIndex pages as physical PDF pages, while many
visible page labels in page content (and some fine-grained tree ranges) are the
internal printed page numbers. For the main body this is commonly:

    physical_page = internal_printed_page + 7

This script does not rewrite the PageIndex workspace or regenerate LLM/Codex
predictions. It creates reproducible alignment artifacts and evaluates existing
Codex agentic predictions with an alignment-aware diagnostic lens.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

DEFAULT_WORKSPACE_JSON = Path("results/pageindex_gmp_workspace/gmp-guidance.json")
DEFAULT_EVAL_JSONL = Path("eval/gmp_eval_testset.jsonl")
DEFAULT_PREDICTIONS_JSONL = Path("results/codex_agentic_10x10/predictions_001_100_agentic.jsonl")
DEFAULT_OUT_DIR = Path("results/page_alignment")

PAGE_LABEL_PATTERNS = [
    # "234 완제의약품 제조 ..."
    re.compile(r"^\s*(?P<label>\d{1,4})\s+완제의약품\s*제조", re.MULTILINE),
    # "2장 완제의약품 ... 235"
    re.compile(r"^\s*2장\s+완제의약품.*?\s(?P<label>\d{1,4})\s*$", re.MULTILINE),
    # "[별첨1] 의약품 제조소의 시설 527"
    re.compile(r"^\s*\[별첨\d+\].*?\s(?P<label>\d{1,4})\s*$", re.MULTILINE),
]

KNOWN_MISS_IDS = {
    "gmp_eval_013",
    "gmp_eval_025",
    "gmp_eval_032",
    "gmp_eval_042",
    "gmp_eval_072",
    "gmp_eval_084",
    "gmp_eval_086",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no}: invalid JSONL: {exc}") from exc
        rows.append(row)
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def compact(text: Any) -> str:
    return re.sub(r"\s+", "", str(text or ""))


def parse_pages(pages: Any) -> list[int]:
    if pages is None:
        return []
    if isinstance(pages, int):
        return [pages]
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
                raise ValueError(f"reversed page range: {part}")
            out.update(range(start, end + 1))
            continue
        raise ValueError(f"invalid page token: {part!r}")
    return sorted(out)


def pages_to_range(pages: Iterable[int]) -> str:
    ordered = sorted(set(int(p) for p in pages))
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


def page_metrics(predicted: Iterable[int], gold: Iterable[int]) -> dict[str, Any]:
    pred_set = set(predicted)
    gold_set = set(gold)
    overlap = pred_set & gold_set
    precision = len(overlap) / len(pred_set) if pred_set else 0.0
    recall = len(overlap) / len(gold_set) if gold_set else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "hit": bool(overlap),
        "overlap_pages": sorted(overlap),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


def detect_internal_label(content: str) -> int | None:
    head = "\n".join(str(content or "").splitlines()[:3])
    for pattern in PAGE_LABEL_PATTERNS:
        m = pattern.search(head)
        if m:
            label = int(m.group("label"))
            # Ignore table-of-contents slash lines like "... / 475"; patterns above
            # are intentionally anchored to actual page header shapes.
            return label
    return None


def load_workspace_pages(workspace_json: Path) -> tuple[list[dict[str, Any]], int]:
    doc = json.loads(workspace_json.read_text(encoding="utf-8"))
    pages = doc.get("pages")
    if not isinstance(pages, list):
        raise ValueError(f"workspace pages missing in {workspace_json}")
    page_count = int(doc.get("page_count") or len(pages))
    return pages, page_count


def build_alignment_map(pages: list[dict[str, Any]], page_count: int) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    internal_to_physical: dict[int, int] = {}
    physical_to_internal: dict[int, int] = {}
    collisions: dict[str, list[int]] = defaultdict(list)

    for item in pages:
        physical = int(item.get("page"))
        label = detect_internal_label(str(item.get("content", "")))
        if label is None:
            entries.append({"physical_page": physical, "internal_page": None, "offset": None, "first_line": first_line(item)})
            continue
        if label in internal_to_physical and internal_to_physical[label] != physical:
            collisions[str(label)].extend([internal_to_physical[label], physical])
        internal_to_physical[label] = physical
        physical_to_internal[physical] = label
        entries.append(
            {
                "physical_page": physical,
                "internal_page": label,
                "offset": physical - label,
                "first_line": first_line(item),
            }
        )

    offset_counts = Counter(entry["offset"] for entry in entries if entry["offset"] is not None)
    segments: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for entry in entries:
        offset = entry["offset"]
        physical = entry["physical_page"]
        internal = entry["internal_page"]
        if offset is None:
            if current:
                segments.append(current)
                current = None
            segments.append({"physical_start": physical, "physical_end": physical, "internal_start": None, "internal_end": None, "offset": None, "count": 1})
            continue
        if current and current["offset"] == offset and current["physical_end"] + 1 == physical:
            current["physical_end"] = physical
            current["internal_end"] = internal
            current["count"] += 1
        else:
            if current:
                segments.append(current)
            current = {
                "physical_start": physical,
                "physical_end": physical,
                "internal_start": internal,
                "internal_end": internal,
                "offset": offset,
                "count": 1,
            }
    if current:
        segments.append(current)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "page_count": page_count,
        "mapped_page_count": len(internal_to_physical),
        "unmapped_physical_pages": [entry["physical_page"] for entry in entries if entry["internal_page"] is None],
        "offset_counts": {str(k): v for k, v in sorted(offset_counts.items(), key=lambda kv: (9999 if kv[0] is None else kv[0]))},
        "dominant_offset": offset_counts.most_common(1)[0][0] if offset_counts else None,
        "segments": segments,
        "internal_to_physical": {str(k): v for k, v in sorted(internal_to_physical.items())},
        "physical_to_internal": {str(k): v for k, v in sorted(physical_to_internal.items())},
        "collisions": {k: sorted(set(v)) for k, v in collisions.items()},
        "entries": entries,
    }


def first_line(item: dict[str, Any]) -> str:
    content = str(item.get("content", ""))
    return next((line.strip() for line in content.splitlines() if line.strip()), "")[:180]


def translate_internal_pages_to_physical(pages: Iterable[int], alignment: dict[str, Any]) -> list[int]:
    mapping = alignment["internal_to_physical"]
    out: set[int] = set()
    for page in pages:
        mapped = mapping.get(str(page))
        if mapped is not None:
            out.add(int(mapped))
    return sorted(out)


def page_text_by_physical(pages: list[dict[str, Any]]) -> dict[int, str]:
    return {int(item["page"]): str(item.get("content", "")) for item in pages}


def score_text_support(row: dict[str, Any], physical_pages: Iterable[int], text_by_page: dict[int, str]) -> dict[str, Any]:
    text = "\n".join(text_by_page.get(page, "") for page in sorted(set(physical_pages)))
    hay = compact(text)
    snippets = [
        row.get("expected_answer", ""),
        row.get("gold_evidence_summary", ""),
        row.get("gold_section_title", ""),
        row.get("question", ""),
    ]
    phrase_hits: list[str] = []
    for snippet in snippets:
        for piece in re.split(r"[.,;。?!\n]", str(snippet)):
            piece = piece.strip()
            if len(piece) >= 8 and compact(piece) in hay:
                phrase_hits.append(piece[:80])
    tokens = [tok for tok in re.findall(r"[가-힣A-Za-z0-9]{2,}", " ".join(map(str, snippets)).lower()) if tok not in {"있는", "없는", "한다", "하여야", "관련", "기준", "관리", "문서", "페이지", "섹션"}]
    text_tokens = set(re.findall(r"[가-힣A-Za-z0-9]{2,}", text.lower()))
    overlap = sorted(set(tokens) & text_tokens)
    return {
        "ok": bool(phrase_hits) or len(overlap) >= 2,
        "phrase_hits": phrase_hits[:5],
        "token_overlap_sample": overlap[:12],
        "content_chars": len(text),
    }


def classify(row_id: str, original: dict[str, Any], aligned_pred: dict[str, Any], evidence: dict[str, Any], aligned_evidence: dict[str, Any]) -> str:
    if original["hit"]:
        return "already_hit"
    if aligned_pred["hit"]:
        return "coordinate_shift_in_predicted_pages"
    if evidence["hit"]:
        return "evidence_read_contains_gold_but_final_page_selection_missed"
    if aligned_evidence["hit"]:
        return "coordinate_shift_in_evidence_pages_read"
    if row_id == "gmp_eval_025":
        return "semantic_duplicate_section_confusion"
    return "unrecovered_selection_or_eval_issue"


def evaluate_alignment(
    eval_rows: list[dict[str, Any]],
    pred_rows: list[dict[str, Any]],
    alignment: dict[str, Any],
    pages: list[dict[str, Any]],
) -> dict[str, Any]:
    eval_by_id = {row["id"]: row for row in eval_rows}
    pred_by_id = {row["id"]: row for row in pred_rows}
    text_by_page = page_text_by_physical(pages)
    item_reports: list[dict[str, Any]] = []

    original_hits: list[float] = []
    aligned_pred_union_hits: list[float] = []
    evidence_union_hits: list[float] = []
    aligned_evidence_union_hits: list[float] = []
    original_precision: list[float] = []
    aligned_pred_union_precision: list[float] = []

    diagnostic_predictions: list[dict[str, Any]] = []

    for row in eval_rows:
        pred = pred_by_id.get(row["id"], {})
        gold_pages = parse_pages(row.get("gold_pages"))
        predicted_pages = parse_pages(pred.get("predicted_pages", ""))
        evidence_pages = parse_pages(pred.get("evidence_pages_read", pred.get("predicted_pages", "")))
        aligned_predicted_pages = translate_internal_pages_to_physical(predicted_pages, alignment)
        aligned_evidence_pages = translate_internal_pages_to_physical(evidence_pages, alignment)
        predicted_union = sorted(set(predicted_pages) | set(aligned_predicted_pages))
        evidence_union = sorted(set(predicted_pages) | set(evidence_pages))
        aligned_evidence_union = sorted(set(predicted_pages) | set(aligned_predicted_pages) | set(evidence_pages) | set(aligned_evidence_pages))

        original_m = page_metrics(predicted_pages, gold_pages)
        aligned_pred_m = page_metrics(predicted_union, gold_pages)
        evidence_m = page_metrics(evidence_union, gold_pages)
        aligned_evidence_m = page_metrics(aligned_evidence_union, gold_pages)

        original_hits.append(1.0 if original_m["hit"] else 0.0)
        aligned_pred_union_hits.append(1.0 if aligned_pred_m["hit"] else 0.0)
        evidence_union_hits.append(1.0 if evidence_m["hit"] else 0.0)
        aligned_evidence_union_hits.append(1.0 if aligned_evidence_m["hit"] else 0.0)
        original_precision.append(float(original_m["precision"]))
        aligned_pred_union_precision.append(float(aligned_pred_m["precision"]))

        classification = classify(row["id"], original_m, aligned_pred_m, evidence_m, aligned_evidence_m)
        support = score_text_support(row, aligned_evidence_union or predicted_pages, text_by_page)
        item = {
            "id": row["id"],
            "question": row.get("question"),
            "gold_pages": pages_to_range(gold_pages),
            "predicted_pages": pages_to_range(predicted_pages),
            "aligned_predicted_pages": pages_to_range(aligned_predicted_pages),
            "predicted_plus_aligned_pages": pages_to_range(predicted_union),
            "evidence_pages_read": pages_to_range(evidence_pages),
            "aligned_evidence_pages_read": pages_to_range(aligned_evidence_pages),
            "evidence_plus_aligned_pages": pages_to_range(aligned_evidence_union),
            "original_page_metrics": original_m,
            "aligned_predicted_union_metrics": aligned_pred_m,
            "evidence_union_metrics": evidence_m,
            "aligned_evidence_union_metrics": aligned_evidence_m,
            "classification": classification,
            "text_support_proxy_on_evidence_plus_aligned": support,
            "is_known_original_miss": row["id"] in KNOWN_MISS_IDS,
        }
        item_reports.append(item)

        diagnostic_row = dict(pred)
        diagnostic_row["predicted_pages_original"] = pages_to_range(predicted_pages)
        diagnostic_row["predicted_pages"] = pages_to_range(predicted_union)
        diagnostic_row["alignment_note"] = "diagnostic union of original predicted pages and internal->physical translated predicted pages; original predictions are preserved separately"
        diagnostic_predictions.append(diagnostic_row)

    def avg(vals: list[float]) -> float:
        return round(sum(vals) / len(vals), 4) if vals else 0.0

    misses = [item for item in item_reports if not item["original_page_metrics"]["hit"]]
    unrecovered = [item for item in item_reports if not item["aligned_evidence_union_metrics"]["hit"]]
    class_counts = Counter(item["classification"] for item in item_reports)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "eval_items": len(eval_rows),
            "prediction_rows": len(pred_rows),
        },
        "metrics": {
            "original_predicted_page_hit_rate": avg(original_hits),
            "original_predicted_page_precision_avg": avg(original_precision),
            "aligned_predicted_union_hit_rate": avg(aligned_pred_union_hits),
            "aligned_predicted_union_precision_avg": avg(aligned_pred_union_precision),
            "evidence_union_hit_rate": avg(evidence_union_hits),
            "evidence_plus_aligned_hit_rate": avg(aligned_evidence_union_hits),
        },
        "classification_counts": dict(class_counts),
        "original_page_misses": misses,
        "unrecovered_after_evidence_alignment": unrecovered,
        "items": item_reports,
        "diagnostic_predictions": diagnostic_predictions,
    }


def write_diagnostic_predictions(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_report(path: Path, alignment: dict[str, Any], evaluation: dict[str, Any]) -> None:
    metrics = evaluation["metrics"]
    lines = [
        "# GMP PageIndex page-coordinate alignment report",
        "",
        f"- generated_at: {evaluation['generated_at']}",
        f"- page_count: {alignment['page_count']}",
        f"- mapped internal page labels: {alignment['mapped_page_count']}",
        f"- dominant offset: physical = internal + {alignment['dominant_offset']}",
        f"- original_predicted_page_hit_rate: {metrics['original_predicted_page_hit_rate']}",
        f"- aligned_predicted_union_hit_rate: {metrics['aligned_predicted_union_hit_rate']}",
        f"- evidence_union_hit_rate: {metrics['evidence_union_hit_rate']}",
        f"- evidence_plus_aligned_hit_rate: {metrics['evidence_plus_aligned_hit_rate']}",
        "",
        "## What this means",
        "",
        "- PageIndex `get_page_content` uses physical PDF pages.",
        "- The visible printed page label inside most GMP content is 7 pages behind the physical page.",
        "- Existing predictions are intentionally preserved. This report adds an alignment-aware diagnostic view instead of blindly rewriting all predictions.",
        "",
        "## Offset segments",
        "",
        "| physical pages | internal pages | offset | count |",
        "|---|---|---:|---:|",
    ]
    for seg in alignment["segments"]:
        if seg["offset"] is None:
            continue
        lines.append(
            f"| {seg['physical_start']}-{seg['physical_end']} | {seg['internal_start']}-{seg['internal_end']} | {seg['offset']} | {seg['count']} |"
        )
    lines.extend([
        "",
        "## Original miss classification",
        "",
        "| id | gold | predicted | aligned predicted | evidence read | aligned evidence | classification |",
        "|---|---|---|---|---|---|---|",
    ])
    for item in evaluation["original_page_misses"]:
        lines.append(
            "| {id} | {gold_pages} | {predicted_pages} | {aligned_predicted_pages} | {evidence_pages_read} | {aligned_evidence_pages_read} | {classification} |".format(
                **item
            )
        )
    lines.extend([
        "",
        "## Unrecovered after evidence alignment",
        "",
    ])
    unrecovered = evaluation["unrecovered_after_evidence_alignment"]
    if unrecovered:
        lines.extend(["| id | gold | predicted | classification |", "|---|---|---|---|"])
        for item in unrecovered:
            lines.append(f"| {item['id']} | {item['gold_pages']} | {item['predicted_pages']} | {item['classification']} |")
    else:
        lines.append("- none")
    lines.extend([
        "",
        "## Artifact policy",
        "",
        "- No model/API/network call is used by this script.",
        "- `*_aligned_union.jsonl` is diagnostic only; it should not replace the original Codex prediction log.",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace-json", default=str(DEFAULT_WORKSPACE_JSON))
    parser.add_argument("--eval", default=str(DEFAULT_EVAL_JSONL))
    parser.add_argument("--predictions", default=str(DEFAULT_PREDICTIONS_JSONL))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()

    workspace_json = Path(args.workspace_json)
    eval_path = Path(args.eval)
    predictions_path = Path(args.predictions)
    out_dir = Path(args.out_dir)

    pages, page_count = load_workspace_pages(workspace_json)
    alignment = build_alignment_map(pages, page_count)
    eval_rows = load_jsonl(eval_path)
    pred_rows = load_jsonl(predictions_path)
    evaluation = evaluate_alignment(eval_rows, pred_rows, alignment, pages)

    alignment_map_path = out_dir / "gmp_page_alignment_map.json"
    audit_path = out_dir / "gmp_page_alignment_audit.json"
    report_path = out_dir / "gmp_page_alignment_report.md"
    known_miss_path = out_dir / "known_miss_alignment_check.json"
    metrics_path = out_dir / "agentic_alignment_adjusted_metrics.json"
    diagnostic_predictions_path = Path("results/codex_agentic_10x10/predictions_001_100_agentic_aligned_union.jsonl")

    write_json(alignment_map_path, alignment)
    audit_payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "workspace_json": str(workspace_json),
        "offset_counts": alignment["offset_counts"],
        "dominant_offset": alignment["dominant_offset"],
        "segments": alignment["segments"],
        "collisions": alignment["collisions"],
        "unmapped_physical_pages": alignment["unmapped_physical_pages"],
    }
    write_json(audit_path, audit_payload)
    write_json(metrics_path, {k: v for k, v in evaluation.items() if k != "diagnostic_predictions"})
    known_items = [item for item in evaluation["items"] if item["is_known_original_miss"]]
    write_json(known_miss_path, {"known_miss_count": len(known_items), "items": known_items})
    write_diagnostic_predictions(diagnostic_predictions_path, evaluation["diagnostic_predictions"])
    write_report(report_path, alignment, evaluation)

    summary = {
        "status": "PASS" if alignment["dominant_offset"] == 7 and not alignment["collisions"] else "CHECK",
        "alignment_map": str(alignment_map_path),
        "audit": str(audit_path),
        "metrics": str(metrics_path),
        "known_miss_check": str(known_miss_path),
        "report": str(report_path),
        "diagnostic_predictions": str(diagnostic_predictions_path),
        "dominant_offset": alignment["dominant_offset"],
        "mapped_page_count": alignment["mapped_page_count"],
        "original_predicted_page_hit_rate": evaluation["metrics"]["original_predicted_page_hit_rate"],
        "aligned_predicted_union_hit_rate": evaluation["metrics"]["aligned_predicted_union_hit_rate"],
        "evidence_plus_aligned_hit_rate": evaluation["metrics"]["evidence_plus_aligned_hit_rate"],
        "unrecovered_after_evidence_alignment": [item["id"] for item in evaluation["unrecovered_after_evidence_alignment"]],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["status"] in {"PASS", "CHECK"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
