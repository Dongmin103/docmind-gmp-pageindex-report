#!/usr/bin/env python3
"""Build and smoke-test a PageIndex workspace for the GMP guidance tree.

This keeps the retrieval path PageIndex-native:
  PageIndexClient(workspace=...)
    -> get_document()
    -> get_document_structure()
    -> get_page_content()

No API keys, vector DB, FTS, or model calls are used here. The script verifies
that the completed GMP tree can be consumed by the same local PageIndex tools
used by the agentic retrieval demo.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pageindex import PageIndexClient  # noqa: E402

DEFAULT_TREE = Path("results/gmp_guidance_structure.json")
DEFAULT_PAGES = Path("../.omx/pageindex_codex/gmp_pages.json")
DEFAULT_WORKSPACE = Path("results/pageindex_gmp_workspace")
DEFAULT_REPORT = Path(".omx/artifacts/gmp-pageindex-workspace-smoke-latest.md")
DOC_ID = "gmp-guidance"
DOC_NAME = "gmp_guidance.pdf"

CANONICAL_NODE_FIELDS = {
    "title",
    "node_id",
    "start_index",
    "end_index",
    "own_start_index",
    "own_end_index",
    "subtree_start_index",
    "subtree_end_index",
    "nodes",
}

SMOKE_CASES = [
    {
        "id": "facility_management",
        "pages": "54-56",
        "expected_terms": ["작업소", "기계", "설비"],
        "expected_structure_terms": ["시설 및 환경의 관리", "시설관리"],
    },
    {
        "id": "validation",
        "pages": "243-244",
        "expected_terms": ["밸리데이션", "계획서"],
        "expected_structure_terms": ["밸리데이션", "밸리데이션의 대상"],
    },
    {
        "id": "complaints_recall",
        "pages": "430-431",
        "expected_terms": ["불만", "회수"],
        "expected_structure_terms": ["불만처리 및 회수"],
    },
    {
        "id": "change_control",
        "pages": "441-442",
        "expected_terms": ["변경", "검토"],
        "expected_structure_terms": ["변경관리"],
    },
    {
        "id": "training",
        "pages": "452-453",
        "expected_terms": ["교육", "훈련"],
        "expected_structure_terms": ["교육 및 훈련"],
    },
    {
        "id": "consignment",
        "pages": "456-458",
        "expected_terms": ["위탁", "제조"],
        "expected_structure_terms": ["위탁제조 및 위탁시험의 관리"],
    },
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def roots(structure: Any) -> list[dict[str, Any]]:
    return structure if isinstance(structure, list) else [structure]


def walk(node: dict[str, Any], path: tuple[str, ...] = ()):
    current = path + (str(node.get("title", "")),)
    yield current, node
    for child in node.get("nodes") or []:
        yield from walk(child, current)


def compact(text: str) -> str:
    return re.sub(r"\s+", "", text)


def node_count(structure: Any) -> int:
    return sum(1 for root in roots(structure) for _ in walk(root))


def canonical_violations(structure: Any) -> list[str]:
    bad = []
    for root in roots(structure):
        for path, node in walk(root):
            extra = set(node) - CANONICAL_NODE_FIELDS
            missing = CANONICAL_NODE_FIELDS - set(node)
            if extra or missing:
                bad.append(f"{' / '.join(path)} extra={sorted(extra)} missing={sorted(missing)}")
    return bad


def normalize_pages(raw_pages: dict[str, Any]) -> list[dict[str, Any]]:
    pages = []
    for item in raw_pages.get("pages", []):
        pages.append({
            "page": int(item["page"]),
            "content": item.get("content") or item.get("text") or item.get("page_text") or "",
        })
    return pages


def build_workspace(tree_path: Path, pages_path: Path, workspace: Path) -> Path:
    tree = load_json(tree_path)
    raw_pages = load_json(pages_path)
    pages = normalize_pages(raw_pages)
    if len(pages) != int(raw_pages.get("page_count", len(pages))):
        raise SystemExit(f"page count mismatch: pages={len(pages)} page_count={raw_pages.get('page_count')}")
    doc = {
        "id": DOC_ID,
        "type": "pdf",
        "path": str((REPO_ROOT / "inputs/gmp_guidance.pdf").resolve()),
        "doc_name": tree.get("doc_name") or DOC_NAME,
        "doc_description": "Korean GMP guidance indexed by PageIndex tree.",
        "page_count": len(pages),
        "structure": tree["structure"],
        "pages": pages,
    }
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / f"{DOC_ID}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    meta = {
        DOC_ID: {
            "type": "pdf",
            "doc_name": doc["doc_name"],
            "doc_description": doc["doc_description"],
            "path": doc["path"],
            "page_count": doc["page_count"],
        }
    }
    (workspace / "_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return workspace / f"{DOC_ID}.json"


def smoke_pageindex_tools(workspace: Path) -> dict[str, Any]:
    client = PageIndexClient(workspace=str(workspace))
    metadata = json.loads(client.get_document(DOC_ID))
    structure = json.loads(client.get_document_structure(DOC_ID))
    structure_text = json.dumps(structure, ensure_ascii=False)
    cases = []
    for case in SMOKE_CASES:
        content = json.loads(client.get_page_content(DOC_ID, case["pages"]))
        content_text = "\n".join(str(item.get("content", "")) for item in content)
        page_ok = all(compact(term) in compact(content_text) for term in case["expected_terms"])
        structure_ok = all(compact(term) in compact(structure_text) for term in case["expected_structure_terms"])
        cases.append({
            **case,
            "page_result_count": len(content),
            "page_ok": page_ok,
            "structure_ok": structure_ok,
            "pass": page_ok and structure_ok,
            "content_preview": compact(content_text)[:180],
        })
    return {
        "metadata": metadata,
        "structure_node_count": node_count(structure),
        "canonical_violations": canonical_violations(structure),
        "cases": cases,
        "status": "PASS" if metadata.get("page_count") == 606 and node_count(structure) == 641 and all(c["pass"] for c in cases) else "FAIL",
    }


def write_report(path: Path, workspace_doc: Path, result: dict[str, Any]) -> None:
    lines = [
        "# GMP PageIndex workspace smoke report",
        "",
        f"- status: {result['status']}",
        f"- workspace_doc: `{workspace_doc}`",
        f"- doc_id: `{DOC_ID}`",
        f"- page_count: {result['metadata'].get('page_count')}",
        f"- structure_node_count: {result['structure_node_count']}",
        f"- canonical_violations: {len(result['canonical_violations'])}",
        "",
        "## PageIndex tool smoke cases",
        "",
        "| case | pages | page_ok | structure_ok | pass |",
        "|---|---|---:|---:|---:|",
    ]
    for case in result["cases"]:
        lines.append(
            f"| {case['id']} | {case['pages']} | {case['page_ok']} | {case['structure_ok']} | {case['pass']} |"
        )
    lines += ["", "## Notes", ""]
    lines.append("- This validates PageIndex-native local tools, not vector/FTS search.")
    lines.append("- Agentic retrieval still requires an LLM/Codex step to inspect the tree and choose tight page ranges.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tree", default=str(DEFAULT_TREE))
    ap.add_argument("--pages", default=str(DEFAULT_PAGES))
    ap.add_argument("--workspace", default=str(DEFAULT_WORKSPACE))
    ap.add_argument("--report", default=str(DEFAULT_REPORT))
    ap.add_argument("--json-report")
    args = ap.parse_args()

    workspace_doc = build_workspace(Path(args.tree), Path(args.pages), Path(args.workspace))
    result = smoke_pageindex_tools(Path(args.workspace))
    write_report(Path(args.report), workspace_doc, result)
    out = {**result, "workspace_doc": str(workspace_doc), "report": args.report}
    if args.json_report:
        Path(args.json_report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_report).write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
