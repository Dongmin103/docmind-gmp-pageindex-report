#!/usr/bin/env python3
"""Validate all-branch GMP tree expansion artifacts."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ALLOWED = {"title", "node_id", "start_index", "end_index", "own_start_index", "own_end_index", "subtree_start_index", "subtree_end_index", "nodes"}
HEADING_PATTERNS = [
    re.compile(r"^\s*([가-하]\.)\s*(.+)$"),
    re.compile(r"^\s*([①-⑳])\s*(.+)$"),
    re.compile(r"^\s*((?:\d+\.)+\d*)\s+(.{2,})$"),
    re.compile(r"^\s*(\d+\))\s*(.+)$"),
    re.compile(r"^\s*(\([0-9]+\))\s*(.+)$"),
]
SPECIAL_HEADING = re.compile(r"^\s*(해\s*설|관련 규정|참고자료)\s*$")
PAGE_HEADER = re.compile(r"^\s*(\d{1,3})\s+완제의약품")
CHAPTER_PAGE = re.compile(r"^\s*2장\s+완제의약품.*?(\d{1,3})\s*$")


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def roots(doc: dict[str, Any]) -> list[dict[str, Any]]:
    s = doc.get("structure")
    return s if isinstance(s, list) else [s]


def walk(n: dict[str, Any], path: tuple[str, ...] = ()): 
    p = path + (n.get("title", ""),)
    yield p, n
    for c in n.get("nodes") or []:
        yield from walk(c, p)


def all_nodes(doc: dict[str, Any]):
    for r in roots(doc):
        yield from walk(r)


def find_exact(doc: dict[str, Any], path: list[str]) -> dict[str, Any] | None:
    matches = [n for p, n in all_nodes(doc) if list(p) == path]
    if len(matches) > 1:
        raise AssertionError(f"ambiguous path: {' / '.join(path)}")
    return matches[0] if matches else None


def branch_stats(doc: dict[str, Any], path: list[str]) -> dict[str, Any]:
    node = find_exact(doc, path)
    if not node:
        return {"missing": True, "descendants": 0, "children": 0, "depth": -1}
    nodes = list(walk(node))
    return {
        "missing": False,
        "range": [node.get("start_index"), node.get("end_index")],
        "children": len(node.get("nodes") or []),
        "descendants": len(nodes) - 1,
        "leaves": sum(1 for _, n in nodes if not (n.get("nodes") or [])),
        "depth": max((len(p) - len(tuple(path)) for p, _ in nodes), default=0),
    }


def compact(text: str) -> str:
    return re.sub(r"\s+", "", text)


def clean_line(line: str) -> str:
    return re.sub(r"\s+", " ", line.strip())


def is_source_marker(line: str) -> bool:
    s = clean_line(line)
    if not s:
        return False
    if SPECIAL_HEADING.match(s) or PAGE_HEADER.match(s) or CHAPTER_PAGE.match(s):
        return True
    return any(pat.match(s) for pat in HEADING_PATTERNS)


def source_line_window(lines: list[str], source_line: int, max_lines: int = 8) -> str:
    """Return the heading/continuation window beginning at the evidence line."""
    start = source_line - 1
    collected: list[str] = []
    for pos in range(start, min(len(lines), start + max_lines)):
        current = lines[pos]
        if pos != start and is_source_marker(current):
            break
        if PAGE_HEADER.match(current) or CHAPTER_PAGE.match(current):
            if pos == start:
                collected.append(current)
            break
        if clean_line(current):
            collected.append(current)
    return "\n".join(collected)


def source_path(source_root: Path, source_file: str) -> Path:
    path = Path(source_file)
    if not path.is_absolute():
        path = source_root / source_file
    return path


def source_contains(source_root: Path, source_file: str, needle: str) -> bool:
    path = source_path(source_root, source_file)
    text = path.read_text(encoding="utf-8")
    compact_text = compact(text)
    compact_needle = compact(needle)
    return needle in text or compact_needle in compact_text


def validate_source_evidence(doc: dict[str, Any], source_root: Path, manifest: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    for idx, row in enumerate(manifest.get("node_evidence", []), 1):
        path = row.get("path", [])
        node = find_exact(doc, path) if isinstance(path, list) else None
        path_ok = node is not None
        source_file = row.get("source_file", "")
        source = source_path(source_root, source_file)
        source_ok = source.exists()
        line_ok = False
        line_grounded_ok = False
        heading_ok = False
        title_ok = False
        no_unmarked_truncation = True
        if source_ok:
            lines = source.read_text(encoding="utf-8").splitlines()
            source_line = row.get("source_line")
            line_ok = isinstance(source_line, int) and 1 <= source_line <= len(lines)
            text_compact = compact("\n".join(lines))
            window_compact = compact(source_line_window(lines, source_line)) if line_ok else ""
            source_heading = str(row.get("source_heading", ""))
            node_title = str(row.get("node_title", ""))
            heading_compact = compact(source_heading)
            title_compact = compact(node_title.rstrip("…"))
            heading_ok = bool(heading_compact) and heading_compact in text_compact
            title_ok = bool(title_compact) and title_compact in text_compact
            line_grounded_ok = bool(window_compact) and (
                (bool(heading_compact) and heading_compact in window_compact)
                or (bool(title_compact) and title_compact in window_compact)
            )
            if heading_compact.startswith(title_compact) and len(heading_compact) > len(title_compact) + 2:
                no_unmarked_truncation = node_title.endswith("…")
        if not path_ok:
            errors.append(f"node evidence path missing #{idx}: {' / '.join(map(str, path))}")
        if not source_ok:
            errors.append(f"node evidence source missing #{idx}: {source_file}")
        elif not line_ok:
            errors.append(f"node evidence source line invalid #{idx}: {source_file}:{row.get('source_line')}")
        elif not line_grounded_ok:
            errors.append(f"node evidence source line not grounded #{idx}: {source_file}:{row.get('source_line')} :: {row.get('node_title')}")
        if source_ok and not (heading_ok or title_ok):
            errors.append(f"node evidence heading not grounded #{idx}: {source_file}:{row.get('source_line')} :: {row.get('node_title')}")
        if not no_unmarked_truncation:
            errors.append(f"node evidence title appears truncated without ellipsis #{idx}: {' / '.join(map(str, path))}")
        rows.append({
            **row,
            "path_ok": path_ok,
            "source_ok": source_ok,
            "line_ok": line_ok,
            "line_grounded_ok": line_grounded_ok,
            "heading_ok": heading_ok,
            "title_ok": title_ok,
            "no_unmarked_truncation": no_unmarked_truncation,
        })
    if manifest.get("targets") and not rows:
        errors.append("node evidence is empty for expanded manifest")
    return rows, errors


def validate(doc: dict[str, Any], baseline: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    nodes = list(all_nodes(doc))
    ids = [n.get("node_id") for _, n in nodes]
    if ids != [f"{i:04d}" for i in range(len(ids))]:
        errors.append("node ids are not contiguous zero-padded strings")
    bad_fields = []
    children_fields = 0
    for p, n in nodes:
        extra = set(n) - ALLOWED
        missing = ALLOWED - set(n)
        if extra or missing:
            bad_fields.append({"path": " / ".join(p), "extra": sorted(extra), "missing": sorted(missing)})
        if "children" in n:
            children_fields += 1
    if bad_fields:
        errors.append(f"canonical field violations: {bad_fields[:5]}")
    if children_fields:
        errors.append(f"children fields found: {children_fields}")
    starts = [n.get("start_index") for _, n in nodes if isinstance(n.get("start_index"), int)]
    ends = [n.get("end_index") for _, n in nodes if isinstance(n.get("end_index"), int)]
    if min(starts) != 1 or max(ends) != 606:
        errors.append(f"page coverage expected 1..606 got {min(starts)}..{max(ends)}")
    repeated = []
    noncontained = []
    nonmonotonic = []
    bad_ranges = []
    for p, n in nodes:
        if len(p) != len(set(p)):
            repeated.append(" / ".join(p))
        s, e = n.get("start_index"), n.get("end_index")
        os, oe = n.get("own_start_index"), n.get("own_end_index")
        ss, se = n.get("subtree_start_index"), n.get("subtree_end_index")
        if not all(isinstance(v, int) for v in [s, e, os, oe, ss, se]) or not (s <= e and os <= oe and ss <= se):
            bad_ranges.append(" / ".join(p))
        prev = None
        for c in n.get("nodes") or []:
            if c.get("start_index") < s or c.get("end_index") > e:
                noncontained.append((" / ".join(p), c.get("title"), c.get("start_index"), c.get("end_index")))
            if prev is not None and c.get("start_index") < prev:
                nonmonotonic.append((" / ".join(p), c.get("title")))
            prev = c.get("start_index")
    if repeated:
        errors.append(f"repeated ancestor title count {len(repeated)}")
    if noncontained:
        errors.append(f"non-contained child count {len(noncontained)}")
    if nonmonotonic:
        errors.append(f"nonmonotonic sibling count {len(nonmonotonic)}")
    if bad_ranges:
        errors.append(f"bad/inverted ranges count {len(bad_ranges)}")

    # Known repaired defect guards.
    all_paths = [list(p) for p, _ in nodes]
    def has_subseq(path, seq):
        return any(path[i:i + len(seq)] == seq for i in range(0, len(path) - len(seq) + 1))
    hard_bad = []
    for p in all_paths:
        if has_subseq(p, ["품질관리", "시험관리", "품질관리", "시험관리"]):
            hard_bad.append("quality duplicate loop: " + " / ".join(p))
        if has_subseq(p, ["제조관리", "제조공정관리", "제조관리", "제조공정관리"]):
            hard_bad.append("manufacturing duplicate loop: " + " / ".join(p))
        if "용어의 정의" in p and ("품질경영" in p or "시설 및 환경의 관리" in p):
            hard_bad.append("definition owns later chapter section: " + " / ".join(p))
    if hard_bad:
        errors.append("hard no-regression defects: " + repr(hard_bad[:5]))

    source_root = Path(manifest.get("source_root", "../.omx/pageindex_codex/sections"))
    smoke = []
    for row in manifest.get("smoke_rows", []):
        ok = source_contains(source_root, row["source_file"], row["source_needle"])
        if not ok:
            errors.append(f"source smoke missing: {row['label']} {row['source_file']} :: {row['source_needle']}")
        prefix_node = find_exact(doc, row["path_prefix"])
        if prefix_node is None:
            errors.append(f"smoke path prefix missing: {' / '.join(row['path_prefix'])}")
        smoke.append({**row, "source_ok": ok, "path_ok": prefix_node is not None})

    node_evidence, evidence_errors = validate_source_evidence(doc, source_root, manifest)
    errors.extend(evidence_errors)

    granularity = []
    coarse_after = []
    for target in manifest.get("targets", []):
        path = target["path"]
        before = branch_stats(baseline, path)
        after = branch_stats(doc, path)
        row = {"path": path, "before": before, "after": after}
        granularity.append(row)
        if not after.get("missing") and after.get("descendants", 0) < 5:
            coarse_after.append(row)
    if coarse_after:
        errors.append("expanded targets still coarse: " + repr([" / ".join(r["path"]) for r in coarse_after]))

    return {
        "status": "PASS" if not errors else "FAIL",
        "metrics": {
            "node_count": len(nodes),
            "page_range": [min(starts), max(ends)],
            "children_fields": children_fields,
            "bad_field_count": len(bad_fields),
            "repeated_ancestor_title_count": len(repeated),
            "noncontained_parent_child_count": len(noncontained),
            "nonmonotonic_sibling_count": len(nonmonotonic),
            "bad_range_count": len(bad_ranges),
            "source_smoke_count": len(smoke),
            "node_evidence_count": len(node_evidence),
            "node_evidence_fail_count": len(evidence_errors),
        },
        "granularity": granularity,
        "smoke": smoke,
        "node_evidence": node_evidence,
        "errors": errors,
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = ["# GMP all-branch expansion validation", "", f"## Status: {report['status']}", "", "## Metrics", ""]
    for k, v in report["metrics"].items():
        lines.append(f"- {k}: {v}")
    lines += ["", "## Granularity before/after", "", "| branch | before desc | after desc | after children | after depth |", "|---|---:|---:|---:|---:|"]
    for row in report["granularity"]:
        lines.append(f"| {' / '.join(row['path'])} | {row['before'].get('descendants')} | {row['after'].get('descendants')} | {row['after'].get('children')} | {row['after'].get('depth')} |")
    lines += ["", "## Source smoke", ""]
    for row in report["smoke"]:
        lines.append(f"- {row['label']}: source_ok={row['source_ok']}, path_ok={row['path_ok']}, source={row['source_file']}:{row['source_line']}")
    lines += ["", "## Per-node source evidence", ""]
    evidence_rows = report.get("node_evidence", [])
    lines.append(f"- checked nodes: {len(evidence_rows)}")
    for row in evidence_rows[:60]:
        lines.append(
            f"- {' / '.join(row['path'])}: path_ok={row['path_ok']}, source_ok={row['source_ok']}, "
            f"line_ok={row['line_ok']}, line_grounded_ok={row['line_grounded_ok']}, "
            f"heading_ok={row['heading_ok']}, title_ok={row['title_ok']}, "
            f"source={row['source_file']}:{row['source_line']}"
        )
    if len(evidence_rows) > 60:
        lines.append(f"- ... {len(evidence_rows) - 60} more evidence rows omitted")
    if report["errors"]:
        lines += ["", "## Errors", ""] + [f"- {e}" for e in report["errors"]]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tree", default="results/gmp_guidance_structure.json")
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--manifest", default="configs/gmp_all_branch_expansion_manifest.json")
    ap.add_argument("--report", required=True)
    args = ap.parse_args()
    report = validate(load(Path(args.tree)), load(Path(args.baseline)), load(Path(args.manifest)))
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    write_markdown(report_path, report)
    report_path.with_suffix(".json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
