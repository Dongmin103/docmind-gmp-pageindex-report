#!/usr/bin/env python3
"""Build/merge source-grounded expansion candidates for multiple GMP tree branches."""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any

from gmp_targeted_expand import assign_node_ids, write_json, write_visualizations

NODE_FIELDS = {
    "title", "node_id", "start_index", "end_index", "own_start_index", "own_end_index",
    "subtree_start_index", "subtree_end_index", "nodes",
}
SECTIONS = Path("../.omx/pageindex_codex/sections")
DEFAULT_TREE = Path("results/gmp_guidance_structure.json")
DEFAULT_MANIFEST = Path("configs/gmp_all_branch_expansion_manifest.json")

SOURCE_MAP = {
    "용어의 정의": "0005_용어의_정의.txt",
    "기준서": "0016_기준서.txt",
    "문서": "0021_문서.txt",
    "밸리데이션": "0024_밸리데이션.txt",
    "제조관리": "0034_제조관리.txt",
    "제조위생관리": "0038_제조위생관리.txt",
    "원자재 및 제품의 관리": "0042_원자재_및_제품의_관리.txt",
    "불만처리 및 회수": "0047_불만처리_및_회수.txt",
    "변경관리": "0048_변경관리.txt",
    "자율점검": "0049_자율점검.txt",
    "교육 및 훈련": "0050_교육_및_훈련.txt",
    "위탁제조 및 위탁시험의 관리": "0051_위탁제조_및_위탁시험의_관리.txt",
    "별첨1 의약품 제조소의 시설": "0052_별첨1_의약품_제조소의_시설.txt",
}

CHILD_SOURCE_MAP = {
    "기준서": {
        "제품표준서": "0017_제품표준서.txt",
        "품질관리기준서": "0018_품질관리기준서.txt",
        "제조관리기준서": "0019_제조관리기준서.txt",
        "제조위생관리기준서": "0020_제조위생관리기준서.txt",
    },
    "문서": {
        "문서의 작성": "0022_문서의_작성.txt",
        "문서의 관리": "0023_문서의_관리.txt",
    },
    "밸리데이션": {
        "밸리데이션의 대상": "0025_밸리데이션의_대상.txt",
        "공정 밸리데이션": "0026_공정_밸리데이션.txt",
        "시험방법 밸리데이션": "0027_시험방법_밸리데이션.txt",
        "세척 밸리데이션": "0028_세척_밸리데이션.txt",
        "제조지원설비 밸리데이션": "0029_제조지원설비_밸리데이션.txt",
    },
    "제조관리": {
        "제조공정관리": "0035_제조공정관리.txt",
        "포장공정관리": "0036_포장공정관리.txt",
        "반품 및 재포장": "0037_반품_및_재포장.txt",
    },
    "제조위생관리": {
        "작업원의 위생": "0039_작업원의_위생.txt",
        "작업소의 위생관리": "0040_작업소의_위생관리.txt",
        "제조설비의 세척": "0041_제조설비의_세척.txt",
    },
    "원자재 및 제품의 관리": {
        "입고관리": "0043_입고관리.txt",
        "보관관리": "0044_보관관리.txt",
        "원생약의 보관관리": "0045_원생약의_보관관리.txt",
        "출고관리": "0046_출고관리.txt",
    },
    "별첨1 의약품 제조소의 시설": {
        "의약품 등의 제조업 및 수입자의 시설기준령": "0052_별첨1_의약품_제조소의_시설.txt",
        "의약품 등의 제조업 및 수입자의 시설기준령 시행규칙": "0052_별첨1_의약품_제조소의_시설.txt",
    },
}

TARGET_PATHS = [
    ["제2장 완제의약품 제조 및 품질관리기준", "용어의 정의"],
    ["제2장 완제의약품 제조 및 품질관리기준", "기준서"],
    ["제2장 완제의약품 제조 및 품질관리기준", "문서"],
    ["제2장 완제의약품 제조 및 품질관리기준", "밸리데이션"],
    ["제2장 완제의약품 제조 및 품질관리기준", "제조관리"],
    ["제2장 완제의약품 제조 및 품질관리기준", "제조위생관리"],
    ["제2장 완제의약품 제조 및 품질관리기준", "원자재 및 제품의 관리"],
    ["제2장 완제의약품 제조 및 품질관리기준", "불만처리 및 회수"],
    ["제2장 완제의약품 제조 및 품질관리기준", "변경관리"],
    ["제2장 완제의약품 제조 및 품질관리기준", "자율점검"],
    ["제2장 완제의약품 제조 및 품질관리기준", "교육 및 훈련"],
    ["제2장 완제의약품 제조 및 품질관리기준", "위탁제조 및 위탁시험의 관리"],
    ["별첨1 의약품 제조소의 시설"],
]

HEADING_PATTERNS = [
    ("korean", re.compile(r"^\s*([가-하]\.)\s*(.+)$")),
    ("circled", re.compile(r"^\s*([①-⑳])\s*(.+)$")),
    ("section", re.compile(r"^\s*((?:\d+\.)+\d*)\s+(.{2,})$")),
    ("subnum", re.compile(r"^\s*(\d+\))\s*(.+)$")),
    ("paren", re.compile(r"^\s*(\([0-9]+\))\s*(.+)$")),
]
SPECIAL_HEADING = re.compile(r"^\s*(해\s*설|관련 규정|참고자료)\s*$")
PAGE_HEADER = re.compile(r"^\s*(\d{1,3})\s+완제의약품")
CHAPTER_PAGE = re.compile(r"^\s*2장\s+완제의약품.*?(\d{1,3})\s*$")
NOISE = re.compile(r"^\s*(?:\d+|[ivxlcdm]+)\s*$", re.I)
MAX_SOURCE_HEADING_CHARS = 360
MAX_NODE_TITLE_CHARS = 260


def utc_stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def roots(doc: dict[str, Any]) -> list[dict[str, Any]]:
    s = doc.get("structure")
    return s if isinstance(s, list) else [s]


def walk(node: dict[str, Any], path: tuple[str, ...] = ()):  # yields exact path
    current = path + (node.get("title", ""),)
    yield current, node
    for child in node.get("nodes", []) or []:
        yield from walk(child, current)


def find_exact(doc: dict[str, Any], path: list[str]) -> dict[str, Any]:
    matches = [n for r in roots(doc) for p, n in walk(r) if list(p) == path]
    if len(matches) != 1:
        raise SystemExit(f"expected one match for {' / '.join(path)}, got {len(matches)}")
    return matches[0]


def clean_line(line: str) -> str:
    return re.sub(r"\s+", " ", line.strip())


def compact(text: str) -> str:
    return re.sub(r"\s+", "", text)


def truncate_title(title: str, max_chars: int = MAX_NODE_TITLE_CHARS) -> str:
    """Keep generated node titles readable and explicitly mark safe truncation."""
    title = clean_line(title)
    if len(title) <= max_chars:
        return title
    cut = title.rfind(" ", 0, max_chars)
    if cut < int(max_chars * 0.6):
        cut = max_chars
    return title[:cut].rstrip(" ,.;ㆍ·-/") + "…"


def is_marker(line: str) -> bool:
    s = line.strip()
    if not s or NOISE.match(s):
        return False
    if SPECIAL_HEADING.match(s):
        return True
    return any(pat.match(s) for _, pat in HEADING_PATTERNS)


def build_page_lookup(lines: list[str], start: int, end: int):
    markers: list[tuple[int, int]] = []
    for idx, line in enumerate(lines, 1):
        page = None
        if m := PAGE_HEADER.match(line):
            page = int(m.group(1))
        elif m := CHAPTER_PAGE.match(line):
            page = int(m.group(1))
        if page is not None and start <= page <= end:
            markers.append((idx, page))
    if not markers:
        total = max(len(lines), 1)
        span = max(end - start, 0)
        return lambda line_no: min(end, start + int((line_no - 1) / total * (span + 1))), 1
    markers.sort()
    first_in_range_line = 1
    def lookup(line_no: int) -> int:
        current = start
        for marker_line, page in markers:
            if marker_line <= line_no:
                current = page
            else:
                break
        return min(max(current, start), end)
    return lookup, first_in_range_line


def title_with_continuation(lines: list[str], idx: int, base: str) -> str:
    parts = [clean_line(base)]
    j = idx + 1
    while j < len(lines) and len(parts) < 6:
        nxt = clean_line(lines[j])
        if not nxt or is_marker(nxt) or PAGE_HEADER.match(nxt) or CHAPTER_PAGE.match(nxt):
            break
        if len(" ".join(parts + [nxt])) > MAX_SOURCE_HEADING_CHARS:
            parts.append(nxt)
            break
        parts.append(nxt)
        # Stop once a wrapped criterion sentence appears complete. Keep this
        # after appending so wrapped endings such as "...실시하여야 한다." are
        # preserved rather than cut mid-word.
        if nxt.endswith(("다.", "한다.", "하여야 한다.", "것", "함", ")")):
            break
        j += 1
    return " ".join(parts)


def detect_heading(lines: list[str], idx: int, current_title: str) -> tuple[str, str, str] | None:
    raw = lines[idx]
    s = clean_line(raw)
    if not s or NOISE.match(s):
        return None
    if m := SPECIAL_HEADING.match(s):
        label = "해설" if "해" in m.group(1) else m.group(1)
        if label == "참고자료":
            # include the next short source name when present
            for j in range(idx + 1, min(idx + 4, len(lines))):
                nxt = clean_line(lines[j])
                if nxt and not is_marker(nxt) and not PAGE_HEADER.match(nxt):
                    full = f"참고자료 {nxt}"
                    return "special", truncate_title(full), full
        return "special", label, label
    for kind, pat in HEADING_PATTERNS:
        m = pat.match(s)
        if not m:
            continue
        marker, text = m.group(1), m.group(2)
        title = title_with_continuation(lines, idx, f"{marker} {text}")
        # Skip duplicated section title at the top of the source file.
        normalized = compact(title)
        current_normalized = compact(current_title)
        if idx < 8 and (
            normalized == current_normalized
            or re.fullmatch(r"\d+(?:\.\d+)*" + re.escape(current_normalized), normalized)
        ):
            return None
        return kind, truncate_title(title), title
    return None


def node(title: str, start: int, end: int, children: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    children = children or []
    if children:
        start = min(start, *(c["start_index"] for c in children))
        end = max(end, *(c["end_index"] for c in children))
    return {
        "title": title,
        "node_id": "0000",
        "start_index": start,
        "end_index": end,
        "own_start_index": start,
        "own_end_index": start,
        "subtree_start_index": start,
        "subtree_end_index": end,
        "nodes": children,
    }


def parse_source_to_children(source: Path, current_title: str, start: int, end: int, max_children: int = 40) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    lines = source.read_text(encoding="utf-8").splitlines()
    page_for, first_in_range_line = build_page_lookup(lines, start, end)
    if source.name == "0052_별첨1_의약품_제조소의_시설.txt":
        if current_title == "의약품 등의 제조업 및 수입자의 시설기준령":
            first_in_range_line = 22
        elif current_title == "의약품 등의 제조업 및 수입자의 시설기준령 시행규칙":
            first_in_range_line = 551
    hits: list[dict[str, Any]] = []
    seen: set[str] = set()
    for idx in range(len(lines)):
        if idx + 1 < first_in_range_line:
            continue
        found = detect_heading(lines, idx, current_title)
        if not found:
            continue
        kind, title, source_heading = found
        if title in seen:
            continue
        seen.add(title)
        hits.append({
            "kind": kind,
            "title": title,
            "source_heading": source_heading,
            "line": idx + 1,
            "page": page_for(idx + 1),
        })
    kind_counts: dict[str, int] = {}
    for h in hits:
        kind_counts[h["kind"]] = kind_counts.get(h["kind"], 0) + 1
    # Prefer source criteria and section markers. Avoid exploding every referenced
    # PIC/S/WHO/FDA clause when the source already has Korean criteria headings.
    if kind_counts.get("korean", 0) >= 2:
        allowed = {"korean", "special"}
    elif kind_counts.get("circled", 0) >= 1:
        allowed = {"circled", "special"}
    elif kind_counts.get("section", 0) >= 2:
        allowed = {"section", "special"}
    else:
        allowed = {"korean", "circled", "section", "special"}
    filtered = [h for h in hits if h["kind"] in allowed]
    if len(filtered) < 3:
        filtered = hits
    filtered = filtered[:max_children]
    children: list[dict[str, Any]] = []
    for i, h in enumerate(filtered):
        next_page = filtered[i + 1]["page"] if i + 1 < len(filtered) else end
        child_end = max(h["page"], min(end, next_page))
        children.append(node(h["title"], h["page"], child_end, []))
    return children, filtered


def expand_node(existing: dict[str, Any], source_file: str | None, child_sources: dict[str, str] | None = None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    candidate = copy.deepcopy(existing)
    candidate["nodes"] = copy.deepcopy(existing.get("nodes", []) or [])
    evidence: list[dict[str, Any]] = []
    if child_sources and candidate["nodes"]:
        new_children = []
        for child in candidate["nodes"]:
            title = child["title"]
            source = child_sources.get(title)
            if source:
                parsed, hits = parse_source_to_children(SECTIONS / source, title, child["start_index"], child["end_index"])
                child = copy.deepcopy(child)
                child["nodes"] = parsed
                if parsed:
                    child["own_start_index"] = child["start_index"]
                    child["own_end_index"] = child["start_index"]
                    child["subtree_start_index"] = child["start_index"]
                    child["subtree_end_index"] = child["end_index"]
                evidence.append({
                    "title": title,
                    "source_file": source,
                    "hit_count": len(hits),
                    "sample_hits": hits[:5],
                    "hits": hits,
                })
            new_children.append(child)
        candidate["nodes"] = new_children
    elif source_file:
        parsed, hits = parse_source_to_children(SECTIONS / source_file, existing["title"], existing["start_index"], existing["end_index"])
        candidate["nodes"] = parsed
        candidate["own_start_index"] = existing["start_index"]
        candidate["own_end_index"] = existing["start_index"]
        candidate["subtree_start_index"] = existing["start_index"]
        candidate["subtree_end_index"] = existing["end_index"]
        evidence.append({
            "title": existing["title"],
            "source_file": source_file,
            "hit_count": len(hits),
            "sample_hits": hits[:5],
            "hits": hits,
        })
    return candidate, evidence


def build_manifest(doc: dict[str, Any]) -> dict[str, Any]:
    targets = []
    candidates = []
    smoke_rows = []
    node_evidence = []
    for path in TARGET_PATHS:
        existing = find_exact(doc, path)
        title = path[-1]
        candidate, evidence = expand_node(existing, SOURCE_MAP.get(title), CHILD_SOURCE_MAP.get(title))
        targets.append({
            "path": path,
            "source_file": SOURCE_MAP.get(title),
            "child_sources": CHILD_SOURCE_MAP.get(title, {}),
            "evidence": evidence,
        })
        candidates.append({"path": path, "candidate_subtree": candidate})
        # one smoke row per evidence source with first hit as source needle
        for ev in evidence:
            path_prefix = path if ev["title"] == title else path + [ev["title"]]
            for hit in ev.get("hits", []):
                node_evidence.append({
                    "path": path_prefix + [hit["title"]],
                    "node_title": hit["title"],
                    "source_file": ev["source_file"],
                    "source_line": hit["line"],
                    "source_page": hit["page"],
                    "source_kind": hit["kind"],
                    "source_heading": hit.get("source_heading", hit["title"]),
                })
            if ev["sample_hits"]:
                first = ev["sample_hits"][0]
                smoke_rows.append({
                    "label": re.sub(r"[^0-9A-Za-z가-힣]+", "_", ev["title"]).strip("_"),
                    "path_prefix": path_prefix,
                    "source_file": ev["source_file"],
                    "source_line": first["line"],
                    "source_needle": first.get("source_heading", first["title"]).split(" ", 1)[-1][:80],
                })
    return {
        "name": "gmp_all_branch_expansion",
        "source_root": str(SECTIONS),
        "targets": targets,
        "candidates": candidates,
        "smoke_rows": smoke_rows,
        "node_evidence": node_evidence,
    }


def replace_exact(doc: dict[str, Any], path: list[str], candidate: dict[str, Any]) -> None:
    target = find_exact(doc, path)
    for key in ["title", "start_index", "end_index", "own_start_index", "own_end_index", "subtree_start_index", "subtree_end_index", "nodes"]:
        target[key] = copy.deepcopy(candidate[key])


def write_candidate_md(manifest: dict[str, Any], path: Path) -> None:
    lines = ["# GMP all-branch expansion candidates", ""]
    for item in manifest["candidates"]:
        cand = item["candidate_subtree"]
        lines.append(f"## {' / '.join(item['path'])}")
        lines.append(f"- range: p.{cand['start_index']}-{cand['end_index']}")
        lines.append(f"- direct children: {len(cand.get('nodes') or [])}")
        for child in cand.get("nodes", [])[:20]:
            lines.append(f"  - {child['title']} p.{child['start_index']}-{child['end_index']} children={len(child.get('nodes') or [])}")
        lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tree", default=str(DEFAULT_TREE))
    ap.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    ap.add_argument("--artifact-dir", default=".omx/artifacts")
    ap.add_argument("--visualization-dir", default="results/visualizations")
    ap.add_argument("--merge", action="store_true")
    ap.add_argument("--stamp")
    args = ap.parse_args()
    stamp = args.stamp or utc_stamp()
    tree_path = Path(args.tree)
    artifact_dir = Path(args.artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    doc = load_json(tree_path)
    manifest = build_manifest(doc)
    manifest_path = Path(args.manifest)
    write_json(manifest_path, manifest)
    cand_json = artifact_dir / f"gmp-all-branch-expansion-candidates-{stamp}.json"
    cand_md = artifact_dir / f"gmp-all-branch-expansion-candidates-{stamp}.md"
    write_json(cand_json, manifest)
    write_candidate_md(manifest, cand_md)
    summary = {"manifest": str(manifest_path), "candidate_json": str(cand_json), "candidate_md": str(cand_md), "merged": False}
    if args.merge:
        backup = artifact_dir / f"gmp-guidance-structure-baseline-before-all-branch-expansion-{stamp}.json"
        backup.write_text(tree_path.read_text(encoding="utf-8"), encoding="utf-8")
        merged = copy.deepcopy(doc)
        for item in manifest["candidates"]:
            replace_exact(merged, item["path"], item["candidate_subtree"])
        assign_node_ids(merged.get("structure"))
        write_json(tree_path, merged)
        write_visualizations(merged, Path(args.visualization_dir))
        summary.update({"merged": True, "backup": str(backup), "tree": str(tree_path), "visualization_dir": args.visualization_dir})
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
