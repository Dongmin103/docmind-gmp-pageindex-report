#!/usr/bin/env python3
"""Gold-free evidence-page repair pass for GMP PageIndex Codex predictions.

This script keeps the original Codex prediction JSONL immutable and writes a new
repaired JSONL. For each item it chooses the most direct physical PDF page(s)
from the pages already predicted/read by the agent plus their internal->physical
alignment translations.

The repair decision uses only the question, original predicted_section_path,
original reason, workspace page content, and the page-alignment map. Gold pages
or expected answers are used only in the optional evaluation report after the
repaired prediction has been produced.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

DEFAULT_WORKSPACE_JSON = Path("results/pageindex_gmp_workspace/gmp-guidance.json")
DEFAULT_EVAL_JSONL = Path("eval/gmp_eval_testset.jsonl")
DEFAULT_PREDICTIONS_JSONL = Path("results/codex_agentic_10x10/predictions_001_100_agentic.jsonl")
DEFAULT_ALIGNMENT_MAP = Path("results/page_alignment/gmp_page_alignment_map.json")
DEFAULT_OUTPUT = Path("results/codex_agentic_10x10/predictions_001_100_agentic_repaired.jsonl")
DEFAULT_REPORT = Path("results/page_alignment/prediction_repair_report.json")

STOPWORDS = {
    "한다", "있는", "없는", "또는", "그리고", "에서", "으로", "에게", "대한", "관련", "경우",
    "문서", "기준", "정답", "취지", "페이지", "섹션", "항목", "명시", "기재", "하여", "해야",
    "하여야", "있다", "된다", "관리", "제조", "품질", "제품", "의약품", "완제의약품", "가이던스",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no}: invalid JSONL: {exc}") from exc
    return rows


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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
                raise ValueError(f"reversed page range: {part}")
            out.update(range(start, end + 1))
            continue
        raise ValueError(f"invalid page token: {part!r}")
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


def normalize_token(token: str) -> str:
    token = token.lower().strip()
    suffixes = [
        "하여야", "하여", "하는", "한다", "된다", "되어", "하며", "하고", "까지", "부터", "에서",
        "으로", "에게", "에는", "로서", "로써", "들을", "으로서", "으로써", "과의", "와의", "의",
        "을", "를", "이", "가", "은", "는", "에", "와", "과", "도", "만",
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


def tokenize(text: Any) -> list[str]:
    tokens = re.findall(r"[가-힣A-Za-z0-9]{2,}", str(text or "").lower())
    out = [normalize_token(token) for token in tokens]
    return [token for token in out if token and token not in STOPWORDS]


def compact(text: Any) -> str:
    return re.sub(r"\s+", "", str(text or ""))


def page_metrics(predicted: Iterable[int], gold: Iterable[int]) -> dict[str, Any]:
    pred_set = set(predicted)
    gold_set = set(gold)
    overlap = pred_set & gold_set
    precision = len(overlap) / len(pred_set) if pred_set else 0.0
    recall = len(overlap) / len(gold_set) if gold_set else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"hit": bool(overlap), "overlap_pages": sorted(overlap), "precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4)}


def load_alignment(path: Path) -> dict[int, int]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {int(k): int(v) for k, v in payload.get("internal_to_physical", {}).items()}


def translate(pages: Iterable[int], internal_to_physical: dict[int, int]) -> list[int]:
    return sorted({internal_to_physical[page] for page in pages if page in internal_to_physical})


def load_page_text(workspace_json: Path) -> dict[int, str]:
    doc = json.loads(workspace_json.read_text(encoding="utf-8"))
    return {int(item["page"]): str(item.get("content", "")) for item in doc.get("pages", [])}


def split_phrases(text: Any) -> list[str]:
    phrases: list[str] = []
    for part in re.split(r"[.;。?!\n]", str(text or "")):
        part = part.strip()
        if len(compact(part)) >= 8:
            phrases.append(part)
    return phrases


def candidate_sources(predicted_pages: list[int], evidence_pages: list[int], internal_to_physical: dict[int, int]) -> dict[int, set[str]]:
    sources: dict[int, set[str]] = {}
    def add(page_list: Iterable[int], label: str) -> None:
        for page in page_list:
            sources.setdefault(int(page), set()).add(label)
    add(predicted_pages, "predicted")
    add(evidence_pages, "evidence")
    add(translate(predicted_pages, internal_to_physical), "aligned_predicted")
    add(translate(evidence_pages, internal_to_physical), "aligned_evidence")
    return sources


def score_page(row: dict[str, Any], pred: dict[str, Any], page: int, sources: set[str], text: str) -> dict[str, Any]:
    predicted_path = pred.get("predicted_section_path") if isinstance(pred.get("predicted_section_path"), list) else []
    path_tail = " ".join(str(part) for part in predicted_path[-2:])
    leaf_title = str(predicted_path[-1]) if predicted_path else ""
    question_tokens = set(tokenize(row.get("question", "")))
    path_tokens = set(tokenize(path_tail))
    reason_tokens = set(tokenize(pred.get("reason", "")))
    text_tokens = set(tokenize(text))
    q_overlap = sorted(question_tokens & text_tokens)
    path_overlap = sorted(path_tokens & text_tokens)
    reason_overlap = sorted(reason_tokens & text_tokens)
    hay = compact(text)
    phrase_hits: list[str] = []
    for phrase in split_phrases(row.get("question", "")) + split_phrases(leaf_title):
        c = compact(phrase)
        if c and c in hay:
            phrase_hits.append(phrase[:120])
    source_bonus = 0.0
    if "aligned_predicted" in sources:
        source_bonus += 3.0
    if "predicted" in sources:
        source_bonus += 2.0
    if "aligned_evidence" in sources:
        source_bonus += 1.5
    if "evidence" in sources:
        source_bonus += 1.0
    score = (len(q_overlap) * 4.0) + (len(path_overlap) * 3.0) + (len(reason_overlap) * 0.75) + (len(phrase_hits) * 10.0) + source_bonus
    # Prefer tighter, direct Korean regulatory clauses over bibliography/reference pages when scores tie.
    if re.search(r"^[가-하]\.|^\d+\.|하여야 한다|하여야|해 설", text, re.MULTILINE):
        score += 0.5
    return {
        "page": page,
        "score": round(score, 4),
        "sources": sorted(sources),
        "question_overlap": q_overlap[:12],
        "path_overlap": path_overlap[:12],
        "reason_overlap": reason_overlap[:12],
        "phrase_hits": phrase_hits[:5],
        "first_line": next((line.strip() for line in text.splitlines() if line.strip()), "")[:160],
    }


def choose_direct_pages(scored: list[dict[str, Any]], max_pages: int = 4, score_ratio: float = 0.85) -> list[int]:
    if not scored:
        return []
    ranked = sorted(
        scored,
        key=lambda item: (
            item["score"],
            "aligned_predicted" in item["sources"],
            "aligned_evidence" in item["sources"],
            "evidence" in item["sources"],
            -item["page"],
        ),
        reverse=True,
    )
    best = ranked[0]["score"]
    chosen = [item["page"] for item in ranked if item["score"] == best or (best > 0 and item["score"] >= best * score_ratio)]
    # If the first cut is too narrow, first keep direct evidence pages that
    # strongly match the user question. This prevents the original predicted
    # section from overpowering a later evidence page the agent actually read.
    for item in ranked:
        if len(chosen) >= max_pages:
            break
        if "evidence" in item["sources"] and len(item.get("question_overlap", [])) >= 3 and item["page"] not in chosen:
            chosen.append(item["page"])
    # Then keep a few high-scoring aligned candidates. This catches internal-page
    # -> physical-page shifts without replacing good original predictions.
    for item in ranked:
        if len(chosen) >= max_pages:
            break
        if ("aligned_predicted" in item["sources"] or "aligned_evidence" in item["sources"]) and item["page"] not in chosen:
            chosen.append(item["page"])
    return sorted(set(chosen[:max_pages]))


def repair_predictions(eval_rows: list[dict[str, Any]], pred_rows: list[dict[str, Any]], page_text: dict[int, str], alignment: dict[int, int], max_pages: int, mode: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    eval_by_id = {row["id"]: row for row in eval_rows}
    repaired_rows: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    for pred in pred_rows:
        row = eval_by_id.get(pred.get("id"), {"id": pred.get("id"), "question": pred.get("question", "")})
        predicted_pages = parse_pages(pred.get("predicted_pages", ""))
        evidence_pages = parse_pages(pred.get("evidence_pages_read", pred.get("predicted_pages", "")))
        sources = candidate_sources(predicted_pages, evidence_pages, alignment)
        scored = [score_page(row, pred, page, src, page_text.get(page, "")) for page, src in sorted(sources.items()) if page in page_text]
        direct_pages = choose_direct_pages(scored, max_pages=max_pages)
        if mode == "replace":
            chosen = direct_pages or predicted_pages
        elif mode == "append-direct":
            chosen = sorted(set(predicted_pages) | set(direct_pages))
        else:
            raise ValueError(f"unknown repair mode: {mode}")
        repaired = dict(pred)
        repaired["predicted_pages_original"] = pred.get("predicted_pages", "")
        repaired["evidence_pages_read_original"] = pred.get("evidence_pages_read", "")
        repaired["predicted_pages"] = pages_to_range(chosen)
        repaired["direct_pages_added"] = pages_to_range(sorted(set(chosen) - set(predicted_pages)))
        repaired["repair_method"] = f"gold_free_{mode}_evidence_direct_page_rerank_with_page_alignment"
        repaired["repair_note"] = "Selected direct physical PDF page candidates from original predicted/evidence pages plus internal->physical aligned candidates. Gold pages and expected answers were not used for repair selection. In append-direct mode, original predicted_pages are preserved and direct candidates are added."
        repaired_rows.append(repaired)
        diagnostics.append({"id": pred.get("id"), "chosen_pages": pages_to_range(chosen), "direct_pages": pages_to_range(direct_pages), "direct_pages_added": pages_to_range(sorted(set(chosen) - set(predicted_pages))), "original_predicted_pages": pred.get("predicted_pages", ""), "evidence_pages_read": pred.get("evidence_pages_read", ""), "top_candidates": sorted(scored, key=lambda item: item["score"], reverse=True)[:8]})
    return repaired_rows, diagnostics


def evaluate(eval_rows: list[dict[str, Any]], pred_rows: list[dict[str, Any]]) -> dict[str, Any]:
    pred_by_id = {row["id"]: row for row in pred_rows}
    items: list[dict[str, Any]] = []
    hits: list[float] = []
    precision: list[float] = []
    recall: list[float] = []
    for row in eval_rows:
        pred = pred_by_id.get(row["id"], {})
        predicted = parse_pages(pred.get("predicted_pages", ""))
        gold = parse_pages(row.get("gold_pages", ""))
        metrics = page_metrics(predicted, gold)
        hits.append(1.0 if metrics["hit"] else 0.0)
        precision.append(float(metrics["precision"]))
        recall.append(float(metrics["recall"]))
        if not metrics["hit"]:
            items.append({"id": row["id"], "question": row.get("question"), "gold_pages": pages_to_range(gold), "predicted_pages": pages_to_range(predicted), "metrics": metrics})
    avg = lambda vals: round(sum(vals) / len(vals), 4) if vals else 0.0
    return {"page_hit_rate": avg(hits), "page_precision_avg": avg(precision), "page_recall_avg": avg(recall), "misses": items}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace-json", default=str(DEFAULT_WORKSPACE_JSON))
    parser.add_argument("--eval", default=str(DEFAULT_EVAL_JSONL))
    parser.add_argument("--predictions", default=str(DEFAULT_PREDICTIONS_JSONL))
    parser.add_argument("--page-alignment-map", default=str(DEFAULT_ALIGNMENT_MAP))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--max-pages", type=int, default=4)
    parser.add_argument("--mode", choices=["append-direct", "replace"], default="append-direct")
    args = parser.parse_args()

    eval_rows = load_jsonl(Path(args.eval))
    pred_rows = load_jsonl(Path(args.predictions))
    page_text = load_page_text(Path(args.workspace_json))
    alignment = load_alignment(Path(args.page_alignment_map))
    repaired_rows, diagnostics = repair_predictions(eval_rows, pred_rows, page_text, alignment, max_pages=args.max_pages, mode=args.mode)
    before = evaluate(eval_rows, pred_rows)
    after = evaluate(eval_rows, repaired_rows)
    write_jsonl(Path(args.output), repaired_rows)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repair_method": f"gold_free_{args.mode}_evidence_direct_page_rerank_with_page_alignment",
        "mode": args.mode,
        "inputs": {"eval": args.eval, "predictions": args.predictions, "workspace_json": args.workspace_json, "page_alignment_map": args.page_alignment_map},
        "output": args.output,
        "before": before,
        "after": after,
        "classification_counts_after": dict(Counter("hit" if not item else "miss" for item in after["misses"])),
        "diagnostics": diagnostics,
    }
    write_json(Path(args.report), report)
    print(json.dumps({"output": args.output, "report": args.report, "before": before, "after": after}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
