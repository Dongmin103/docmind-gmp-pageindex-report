#!/usr/bin/env python3
"""Repo-faithful API-free Codex retriever protocol for GMP PageIndex.

This script does not run a model. It gives Codex a repeatable execution surface
that mirrors `examples/agentic_vectorless_rag_demo.py` without OpenAI Agents SDK:

1. `tool document`   -> PageIndexClient.get_document()
2. `tool structure`  -> PageIndexClient.get_document_structure()
3. Codex reasons over the tree and chooses tight pages.
4. `tool page`       -> PageIndexClient.get_page_content(pages)
5. Codex writes predictions JSONL, later scored by gmp_pageindex_codex_eval.py.

The generated work packets contain questions only. They intentionally do not
include gold pages or gold section paths.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pageindex import PageIndexClient  # noqa: E402

DOC_ID = "gmp-guidance"
DEFAULT_EVAL = Path("eval/gmp_eval_testset.jsonl")
DEFAULT_WORKSPACE = Path("results/pageindex_gmp_workspace")
DEFAULT_OUTPUT_DIR = Path("results/codex_retriever_protocol")

SYSTEM_PROMPT = """You are PageIndex-Codex, a document retrieval agent.

Use the same tool order as PageIndex's agentic vectorless RAG demo:
1. Call/get document metadata first.
2. Call/get document structure to identify relevant page ranges.
3. Select tight page ranges; never fetch the whole document.
4. Fetch only the pages needed to justify the prediction.
5. Output prediction JSONL only; do not include gold labels.

Important distinction:
- You are predicting retrieval targets, not answering conversationally.
- Use the question meaning, not only literal title keywords.
- Prefer the section that contains the answer evidence, even if another section title shares a keyword.
"""


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def client(workspace: Path) -> PageIndexClient:
    return PageIndexClient(workspace=str(workspace))


def compact(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def walk(nodes: list[dict[str, Any]], depth: int = 0, max_depth: int | None = None):
    for node in nodes:
        if max_depth is None or depth <= max_depth:
            yield depth, node
        if max_depth is None or depth < max_depth:
            yield from walk(node.get("nodes") or [], depth + 1, max_depth)


def path_lines(nodes: list[dict[str, Any]], max_depth: int = 2, query: str | None = None) -> list[str]:
    terms = [term for term in re.findall(r"[가-힣A-Za-z0-9]{2,}", query or "") if len(term) >= 2]
    lines: list[str] = []
    for depth, node in walk(nodes, max_depth=max_depth):
        title = str(node.get("title", ""))
        hay = compact(title)
        if query and not any(term in hay for term in terms):
            continue
        start = node.get("start_index")
        end = node.get("end_index")
        subtree_start = node.get("subtree_start_index", start)
        subtree_end = node.get("subtree_end_index", end)
        indent = "  " * depth
        lines.append(f"{indent}- {title} [own p.{start}-{end}, subtree p.{subtree_start}-{subtree_end}]")
    return lines


def cmd_tool(args: argparse.Namespace) -> int:
    c = client(Path(args.workspace))
    if args.tool_name == "document":
        print(c.get_document(DOC_ID))
        return 0
    if args.tool_name == "structure":
        structure = json.loads(c.get_document_structure(DOC_ID))
        if args.raw:
            print(json.dumps(structure, ensure_ascii=False, indent=2))
            return 0
        lines = path_lines(structure, max_depth=args.max_depth, query=args.query)
        print("\n".join(lines))
        return 0
    if args.tool_name == "page":
        print(c.get_page_content(DOC_ID, args.pages))
        return 0
    raise SystemExit(f"unknown tool: {args.tool_name}")


def prediction_stub(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "question": row["question"],
        "predicted_section_path": [],
        "predicted_pages": "",
        "evidence_pages_read": "",
        "reason": "",
    }


def cmd_init_predictions(args: argparse.Namespace) -> int:
    rows = load_jsonl(Path(args.eval))
    if args.limit:
        rows = rows[: args.limit]
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(prediction_stub(row), ensure_ascii=False) + "\n")
    print(json.dumps({"output": str(output), "rows": len(rows)}, ensure_ascii=False))
    return 0


def cmd_make_packet(args: argparse.Namespace) -> int:
    rows = load_jsonl(Path(args.eval))
    start = max(args.start, 1)
    selected = rows[start - 1 : start - 1 + args.limit]
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    packet_path = output_dir / f"packet_{start:03d}_{start + len(selected) - 1:03d}.md"
    predictions_path = output_dir / f"predictions_{start:03d}_{start + len(selected) - 1:03d}.jsonl"

    c = client(Path(args.workspace))
    document = json.loads(c.get_document(DOC_ID))
    structure = json.loads(c.get_document_structure(DOC_ID))
    top_structure = "\n".join(path_lines(structure, max_depth=args.max_depth))

    lines = [
        "# GMP PageIndex Codex retriever work packet",
        "",
        f"- generated_at: {datetime.now(timezone.utc).isoformat()}",
        f"- doc_id: `{DOC_ID}`",
        f"- questions: {selected[0]['id']}..{selected[-1]['id']}" if selected else "- questions: none",
        f"- prediction_output: `{predictions_path}`",
        "",
        "## Repo-faithful tool order",
        "",
        "This packet follows `examples/agentic_vectorless_rag_demo.py`:",
        "1. get_document",
        "2. get_document_structure",
        "3. choose tight pages",
        "4. get_page_content",
        "5. emit prediction JSONL",
        "",
        "## System prompt",
        "",
        "```text",
        SYSTEM_PROMPT,
        "```",
        "",
        "## Local tool commands",
        "",
        "```bash",
        ".venv/bin/python scripts/gmp_pageindex_codex_retriever.py tool document",
        ".venv/bin/python scripts/gmp_pageindex_codex_retriever.py tool structure --max-depth 2",
        ".venv/bin/python scripts/gmp_pageindex_codex_retriever.py tool structure --query '변경관리' --max-depth 4",
        ".venv/bin/python scripts/gmp_pageindex_codex_retriever.py tool page --pages '147'",
        "```",
        "",
        "## Document metadata",
        "",
        "```json",
        json.dumps(document, ensure_ascii=False, indent=2),
        "```",
        "",
        f"## Structure preview, depth <= {args.max_depth}",
        "",
        "```text",
        top_structure,
        "```",
        "",
        "## Output schema",
        "",
        "Each JSONL row must be:",
        "",
        "```json",
        json.dumps(
            {
                "id": "gmp_eval_001",
                "question": "question copied exactly",
                "predicted_section_path": ["tree", "path", "leaf"],
                "predicted_pages": "tight pages such as 147 or 54-56",
                "evidence_pages_read": "pages actually inspected",
                "reason": "brief retrieval rationale, not final answer",
            },
            ensure_ascii=False,
            indent=2,
        ),
        "```",
        "",
        "## Questions only, no gold labels",
        "",
    ]
    for row in selected:
        lines.append(f"- `{row['id']}` {row['question']}")

    packet_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with predictions_path.open("w", encoding="utf-8") as f:
        for row in selected:
            f.write(json.dumps(prediction_stub(row), ensure_ascii=False) + "\n")

    print(json.dumps({"packet": str(packet_path), "predictions_template": str(predictions_path), "rows": len(selected)}, ensure_ascii=False))
    return 0


def cmd_validate_predictions(args: argparse.Namespace) -> int:
    rows = load_jsonl(Path(args.predictions))
    errors: list[dict[str, Any]] = []
    required = {"id", "question", "predicted_section_path", "predicted_pages", "evidence_pages_read", "reason"}
    for line_no, row in enumerate(rows, 1):
        missing = sorted(required - set(row))
        if missing:
            errors.append({"line": line_no, "id": row.get("id"), "missing": missing})
        if not isinstance(row.get("predicted_section_path"), list):
            errors.append({"line": line_no, "id": row.get("id"), "error": "predicted_section_path must be list"})
        if not isinstance(row.get("predicted_pages"), str):
            errors.append({"line": line_no, "id": row.get("id"), "error": "predicted_pages must be string"})
        if not args.allow_empty_template:
            for field in ("predicted_pages", "evidence_pages_read", "reason"):
                if not str(row.get(field, "")).strip():
                    errors.append({"line": line_no, "id": row.get("id"), "error": f"{field} must be filled"})
            if not row.get("predicted_section_path"):
                errors.append({"line": line_no, "id": row.get("id"), "error": "predicted_section_path must be filled"})
    result = {"status": "PASS" if not errors else "FAIL", "rows": len(rows), "errors": errors}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default=str(DEFAULT_WORKSPACE))
    sub = parser.add_subparsers(dest="command", required=True)

    tool = sub.add_parser("tool")
    tool.add_argument("tool_name", choices=["document", "structure", "page"])
    tool.add_argument("--pages")
    tool.add_argument("--query")
    tool.add_argument("--max-depth", type=int, default=2)
    tool.add_argument("--raw", action="store_true")
    tool.set_defaults(func=cmd_tool)

    packet = sub.add_parser("make-packet")
    packet.add_argument("--eval", default=str(DEFAULT_EVAL))
    packet.add_argument("--start", type=int, default=1)
    packet.add_argument("--limit", type=int, default=10)
    packet.add_argument("--max-depth", type=int, default=2)
    packet.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    packet.set_defaults(func=cmd_make_packet)

    init = sub.add_parser("init-predictions")
    init.add_argument("--eval", default=str(DEFAULT_EVAL))
    init.add_argument("--limit", type=int)
    init.add_argument("--output", default=str(DEFAULT_OUTPUT_DIR / "predictions_template.jsonl"))
    init.set_defaults(func=cmd_init_predictions)

    validate = sub.add_parser("validate-predictions")
    validate.add_argument("predictions")
    validate.add_argument(
        "--allow-empty-template",
        action="store_true",
        help="Validate generated blank templates. Omit for completed prediction files.",
    )
    validate.set_defaults(func=cmd_validate_predictions)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "tool" and args.tool_name == "page" and not args.pages:
        parser.error("tool page requires --pages")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
