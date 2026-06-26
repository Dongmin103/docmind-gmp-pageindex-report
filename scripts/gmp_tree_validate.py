#!/usr/bin/env python3
"""Validate a manifest-driven targeted PageIndex tree expansion."""
from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path
from typing import Any

ALLOWED_NODE_FIELDS = {
    "title", "node_id", "start_index", "end_index", "own_start_index", "own_end_index",
    "subtree_start_index", "subtree_end_index", "nodes",
}
DEFAULT_MANIFEST = Path("configs/gmp_facility_expansion_manifest.json")
MANIFEST_NODE_FIELDS = ALLOWED_NODE_FIELDS


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_manifest(path: Path) -> dict[str, Any]:
    manifest = load(path)
    for key in ["target_path", "smoke_name", "source_files", "candidate_subtree", "smoke_rows"]:
        if key not in manifest:
            raise SystemExit(f"manifest missing required key: {key}")
    validate_manifest(manifest)
    return manifest


def validate_page_range(value: Any, label: str) -> None:
    if not (isinstance(value, list) and len(value) == 2 and all(isinstance(v, int) for v in value)):
        raise SystemExit(f"manifest {label} must be [start, end] integers")
    if value[0] > value[1]:
        raise SystemExit(f"manifest {label} has inverted range: {value}")


def validate_node_schema(node: Any, path: str = "candidate_subtree") -> None:
    if not isinstance(node, dict):
        raise SystemExit(f"manifest {path} must be an object")
    missing = MANIFEST_NODE_FIELDS - set(node)
    extra = set(node) - MANIFEST_NODE_FIELDS
    if missing:
        raise SystemExit(f"manifest {path} missing node fields: {sorted(missing)}")
    if extra:
        raise SystemExit(f"manifest {path} has unsupported node fields: {sorted(extra)}")
    if not isinstance(node["title"], str) or not node["title"].strip():
        raise SystemExit(f"manifest {path}.title must be a non-empty string")
    for key in ["start_index", "end_index", "own_start_index", "own_end_index", "subtree_start_index", "subtree_end_index"]:
        if not isinstance(node[key], int):
            raise SystemExit(f"manifest {path}.{key} must be an integer")
    if node["start_index"] > node["end_index"]:
        raise SystemExit(f"manifest {path} has inverted start/end range")
    if node["own_start_index"] > node["own_end_index"]:
        raise SystemExit(f"manifest {path} has inverted own range")
    if node["subtree_start_index"] > node["subtree_end_index"]:
        raise SystemExit(f"manifest {path} has inverted subtree range")
    if not isinstance(node["nodes"], list):
        raise SystemExit(f"manifest {path}.nodes must be a list")
    for i, child in enumerate(node["nodes"]):
        validate_node_schema(child, f"{path}.nodes[{i}]")


def validate_manifest(manifest: dict[str, Any]) -> None:
    target_path = manifest["target_path"]
    if not (isinstance(target_path, list) and target_path and all(isinstance(p, str) and p.strip() for p in target_path)):
        raise SystemExit("manifest target_path must be a non-empty list of strings")
    if not isinstance(manifest["smoke_name"], str) or not manifest["smoke_name"].strip():
        raise SystemExit("manifest smoke_name must be a non-empty string")
    if not isinstance(manifest["source_files"], dict) or not manifest["source_files"]:
        raise SystemExit("manifest source_files must be a non-empty object")
    for key, value in manifest["source_files"].items():
        if not isinstance(key, str) or not isinstance(value, str) or not value.strip():
            raise SystemExit("manifest source_files must map strings to non-empty path strings")
    validate_node_schema(manifest["candidate_subtree"])
    if manifest["candidate_subtree"]["title"] != target_path[-1]:
        raise SystemExit("manifest candidate_subtree.title must match target_path leaf")
    if not isinstance(manifest["smoke_rows"], list):
        raise SystemExit("manifest smoke_rows must be a list")
    for i, row in enumerate(manifest["smoke_rows"]):
        if not isinstance(row, dict):
            raise SystemExit(f"manifest smoke_rows[{i}] must be an object")
        for key in ["label", "source_file", "source_needles", "required_parent_ranges", "checks"]:
            if key not in row:
                raise SystemExit(f"manifest smoke_rows[{i}] missing required key: {key}")
        if not isinstance(row["source_file"], str) or not row["source_file"].strip():
            raise SystemExit(f"manifest smoke_rows[{i}].source_file must be a non-empty string")
        if not isinstance(row["source_needles"], list) or not row["source_needles"]:
            raise SystemExit(f"manifest smoke_rows[{i}].source_needles must be a non-empty list")
        if not all(isinstance(needle, str) and needle.strip() for needle in row["source_needles"]):
            raise SystemExit(f"manifest smoke_rows[{i}].source_needles must contain only non-empty strings")
        if not isinstance(row["required_parent_ranges"], dict):
            raise SystemExit(f"manifest smoke_rows[{i}].required_parent_ranges must be an object")
        for title, rng in row["required_parent_ranges"].items():
            if not isinstance(title, str):
                raise SystemExit(f"manifest smoke_rows[{i}].required_parent_ranges keys must be strings")
            validate_page_range(rng, f"smoke_rows[{i}].required_parent_ranges[{title}]")
        if not isinstance(row["checks"], list) or not row["checks"]:
            raise SystemExit(f"manifest smoke_rows[{i}].checks must be a non-empty list")
        for j, check in enumerate(row["checks"]):
            if not isinstance(check.get("path"), list) or not check["path"]:
                raise SystemExit(f"manifest smoke_rows[{i}].checks[{j}].path must be a non-empty list")
            validate_page_range(check.get("expected_range"), f"smoke_rows[{i}].checks[{j}].expected_range")
            validate_page_range(check.get("expected_own_range"), f"smoke_rows[{i}].checks[{j}].expected_own_range")


def parse_target_path(raw: str | None, manifest: dict[str, Any]) -> list[str]:
    if not raw:
        return list(manifest["target_path"])
    return [part for part in raw.split("/") if part]


def roots(doc: dict[str, Any]) -> list[dict[str, Any]]:
    s = doc.get("structure")
    return s if isinstance(s, list) else [s]


def walk(n: dict[str, Any], path=()):
    yield path + (n.get("title", ""),), n
    for c in n.get("nodes") or []:
        yield from walk(c, path + (n.get("title", ""),))


def all_nodes(doc: dict[str, Any]):
    for r in roots(doc):
        yield from walk(r)


def find_path(doc: dict[str, Any], path: list[str]) -> dict[str, Any] | None:
    matches = [n for p, n in all_nodes(doc) if list(p) == path]
    if len(matches) > 1:
        raise AssertionError(f"ambiguous exact path ({len(matches)} matches): {' / '.join(path)}")
    return matches[0] if matches else None


def normalize_for_diff(doc: dict[str, Any], target_path: list[str]) -> dict[str, Any]:
    out = copy.deepcopy(doc)

    def rec(n: dict[str, Any], path: list[str]):
        n.pop("node_id", None)
        current = path + [n.get("title", "")]
        if current == target_path:
            n["nodes"] = "__TARGET_SUBTREE__"
            return
        for c in n.get("nodes") or []:
            rec(c, current)

    for r in roots(out):
        rec(r, [])
    return out


def source_path(source_root: Path, source_file: str) -> Path:
    path = Path(source_file)
    if path.is_absolute():
        if not path.exists():
            raise FileNotFoundError(f"source file not found: {path}")
        return path
    cwd_relative = path
    if cwd_relative.exists():
        return cwd_relative
    rooted = source_root / path
    if rooted.exists():
        return rooted
    raise FileNotFoundError(f"source file not found without basename fallback: {source_file}")


def source_evidence(source_root: Path, source_file: str, needles: list[str]) -> list[str]:
    path = source_path(source_root, source_file)
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    hits = []
    for needle in needles:
        found = None
        compact_needle = re.sub(r"\s+", "", needle)
        for i, line in enumerate(lines, 1):
            if needle in line or compact_needle in re.sub(r"\s+", "", line):
                found = f"{path}:{i}: {line.strip()}"
                break
        if not found:
            raise AssertionError(f"source evidence not found: {path} :: {needle}")
        hits.append(found)
    return hits


def validate(doc: dict[str, Any], baseline: dict[str, Any] | None, source_root: Path, target_path: list[str], smoke_rows: list[dict[str, Any]]) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    report: dict[str, Any] = {"metrics": {}, "smoke": [], "errors": errors}
    nodes = list(all_nodes(doc))
    ids = [n.get("node_id") for _, n in nodes]
    expected_ids = [f"{i:04d}" for i in range(len(ids))]
    if ids != expected_ids:
        errors.append("node_id values are not contiguous zero-padded strings")
    bad_fields = []
    children_fields = 0
    for path, n in nodes:
        extra = set(n) - ALLOWED_NODE_FIELDS
        if extra:
            bad_fields.append((" / ".join(path), sorted(extra)))
        if "children" in n:
            children_fields += 1
    if bad_fields:
        errors.append(f"canonical field contract violation: {bad_fields[:5]}")
    if children_fields:
        errors.append(f"children field found in {children_fields} nodes")

    starts = [n.get("start_index") for _, n in nodes if isinstance(n.get("start_index"), int)]
    ends = [n.get("end_index") for _, n in nodes if isinstance(n.get("end_index"), int)]
    if min(starts) != 1 or max(ends) != 606:
        errors.append(f"page coverage expected 1..606, got {min(starts)}..{max(ends)}")

    repeated_ancestor = []
    noncontained = []
    nonmonotonic = []
    for path, n in nodes:
        titles = list(path)
        if len(titles) != len(set(titles)):
            repeated_ancestor.append(" / ".join(titles))
        prev_start = None
        for c in n.get("nodes") or []:
            if c.get("start_index") < n.get("start_index") or c.get("end_index") > n.get("end_index"):
                noncontained.append((" / ".join(path), c.get("title"), c.get("start_index"), c.get("end_index")))
            if prev_start is not None and c.get("start_index") < prev_start:
                nonmonotonic.append((" / ".join(path), c.get("title")))
            prev_start = c.get("start_index")
    if repeated_ancestor:
        errors.append(f"repeated ancestor title count {len(repeated_ancestor)}")
    if noncontained:
        errors.append(f"non-contained parent-child count {len(noncontained)}")
    if nonmonotonic:
        errors.append(f"nonmonotonic sibling count {len(nonmonotonic)}")

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
        if "별첨1 의약품 제조소의 시설" in p and p[-1] == "컴퓨터화 시스템":
            hard_bad.append("appendix1 owns duplicate computer system: " + " / ".join(p))
    if hard_bad:
        errors.append("hard no-regression defects: " + repr(hard_bad[:5]))

    target = find_path(doc, target_path)
    if not target:
        errors.append("target path missing: " + " / ".join(target_path))
    elif len(target.get("nodes") or []) != 3:
        errors.append("target direct children expected 3")

    outside_diff_zero = baseline is None or normalize_for_diff(doc, target_path) == normalize_for_diff(baseline, target_path)
    if not outside_diff_zero:
        errors.append("outside-target normalized diff is nonzero")

    for row in smoke_rows:
        row_report = {"label": row["label"], "checks": [], "sourceEvidence": []}
        for check in row["checks"]:
            path = check["path"]
            n = find_path(doc, path)
            if not n:
                errors.append(f"smoke {row['label']} missing path: {' / '.join(path)}")
                row_report["checks"].append({"path": path, "ok": False, "reason": "missing"})
                continue
            expected_range = tuple(check["expected_range"])
            expected_own = tuple(check.get("expected_own_range", check["expected_range"]))
            actual = (n.get("start_index"), n.get("end_index"))
            actual_own = (n.get("own_start_index"), n.get("own_end_index"))
            ok = actual == expected_range and actual_own == expected_own
            if actual != expected_range:
                errors.append(f"smoke {row['label']} range mismatch for {' / '.join(path)}: {actual} != {expected_range}")
            if actual_own != expected_own:
                errors.append(f"smoke {row['label']} own-range mismatch for {' / '.join(path)}: {actual_own} != {expected_own}")
            row_report["checks"].append({"path": path, "expectedRange": expected_range, "actualRange": actual, "expectedOwnRange": expected_own, "actualOwnRange": actual_own, "ok": ok})
        for title, rng in row["required_parent_ranges"].items():
            rng_tuple = tuple(rng)
            parent = next((n for _, n in nodes if n.get("title") == title and (n.get("start_index"), n.get("end_index")) == rng_tuple), None)
            if not parent:
                errors.append(f"smoke {row['label']} missing parent containment {title} {rng_tuple}")
        row_report["sourceEvidence"] = source_evidence(source_root, row["source_file"], row["source_needles"])
        report["smoke"].append(row_report)

    report["metrics"] = {
        "node_count": len(nodes),
        "page_range": [min(starts), max(ends)],
        "children_fields": children_fields,
        "bad_field_count": len(bad_fields),
        "repeated_ancestor_title_count": len(repeated_ancestor),
        "noncontained_parent_child_count": len(noncontained),
        "nonmonotonic_sibling_count": len(nonmonotonic),
        "outside_target_diff_zero": outside_diff_zero,
    }
    return report, errors


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    status = "PASS" if not report["errors"] else "FAIL"
    lines = ["# GMP Facility Expansion Validation", "", f"## Status: {status}", "", "## Metrics", ""]
    for k, v in report["metrics"].items():
        lines.append(f"- {k}: {v}")
    lines += ["", "## Deterministic smoke", ""]
    for row in report["smoke"]:
        lines.append(f"### {row['label']}")
        for check in row["checks"]:
            lines.append(f"- path: {' / '.join(check['path'])}")
            lines.append(f"  - expected subtree: {check.get('expectedRange')}; actual subtree: {check.get('actualRange')}; ok: {check.get('ok')}")
            lines.append(f"  - expected own: {check.get('expectedOwnRange')}; actual own: {check.get('actualOwnRange')}")
        lines.append("- source evidence:")
        for ev in row.get("sourceEvidence", []):
            lines.append(f"  - `{ev}`")
        lines.append("")
    if report["errors"]:
        lines += ["## Errors", ""] + [f"- {e}" for e in report["errors"]]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tree", required=True)
    ap.add_argument("--target-path")
    ap.add_argument("--baseline")
    ap.add_argument("--smoke", default="facilities")
    ap.add_argument("--source-root", default="../.omx/pageindex_codex/sections")
    ap.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    ap.add_argument("--report", required=True)
    args = ap.parse_args()
    manifest = load_manifest(Path(args.manifest))
    if args.smoke != manifest["smoke_name"]:
        raise SystemExit(f"unsupported smoke suite: {args.smoke}; expected {manifest['smoke_name']}")
    target_path = parse_target_path(args.target_path, manifest)
    if target_path != manifest["target_path"]:
        raise SystemExit(f"unsupported target path: {' / '.join(target_path)}; expected {' / '.join(manifest['target_path'])}")
    doc = load(Path(args.tree))
    baseline = load(Path(args.baseline)) if args.baseline else None
    report, errors = validate(doc, baseline, Path(args.source_root), target_path, manifest["smoke_rows"])
    write_report(Path(args.report), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
