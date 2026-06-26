#!/usr/bin/env python3
"""Manifest-driven targeted branch expansion helper for a PageIndex tree."""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import html
import json
from pathlib import Path
from typing import Any

DEFAULT_MANIFEST = Path("configs/gmp_facility_expansion_manifest.json")
NODE_FIELDS = {
    "title", "node_id", "start_index", "end_index", "own_start_index", "own_end_index",
    "subtree_start_index", "subtree_end_index", "nodes",
}


def utc_stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_manifest(path: Path) -> dict[str, Any]:
    manifest = load_json(path)
    for key in ["target_path", "candidate_subtree", "source_files", "smoke_name", "smoke_rows"]:
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
    missing = NODE_FIELDS - set(node)
    extra = set(node) - NODE_FIELDS
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


def iter_nodes(root: Any):
    if isinstance(root, dict):
        yield root
        for child in root.get("nodes", []) or []:
            yield from iter_nodes(child)
    elif isinstance(root, list):
        for item in root:
            yield from iter_nodes(item)


def assign_node_ids(data: Any) -> None:
    for i, n in enumerate(iter_nodes(data)):
        n["node_id"] = f"{i:04d}"


def walk_with_path(node: dict[str, Any], path: tuple[str, ...] = ()):
    current = path + (node.get("title", ""),)
    yield current, node
    for child in node.get("nodes", []) or []:
        yield from walk_with_path(child, current)


def find_unique_exact_path(roots: list[dict[str, Any]], path: list[str]) -> dict[str, Any]:
    matches = [node for root in roots for current, node in walk_with_path(root) if list(current) == path]
    if not matches:
        raise SystemExit(f"target path not found exactly: {' / '.join(path)}")
    if len(matches) > 1:
        raise SystemExit(f"target path is ambiguous ({len(matches)} matches): {' / '.join(path)}")
    return matches[0]


def replace_target_tree(doc: dict[str, Any], candidate: dict[str, Any], target_path: list[str]) -> dict[str, Any]:
    merged = copy.deepcopy(doc)
    structure = merged.get("structure")
    roots = structure if isinstance(structure, list) else [structure]
    target = find_unique_exact_path(roots, target_path)
    for key in ["title", "start_index", "end_index", "nodes", "own_start_index", "own_end_index", "subtree_start_index", "subtree_end_index"]:
        target[key] = copy.deepcopy(candidate[key])
    assign_node_ids(merged.get("structure"))
    return merged


def render_lines(nodes: list[dict[str, Any]], prefix: str = "") -> list[str]:
    lines: list[str] = []
    for idx, n in enumerate(nodes):
        last = idx == len(nodes) - 1
        branch = "└── " if last else "├── "
        own = ""
        if (n.get("own_start_index"), n.get("own_end_index")) != (n.get("start_index"), n.get("end_index")):
            own = f" own[{n.get('own_start_index')}-{n.get('own_end_index')}]"
        lines.append(f"{prefix}{branch}{n.get('title')} [{n.get('start_index')}-{n.get('end_index')}]{own} #{n.get('node_id')}")
        child_prefix = prefix + ("    " if last else "│   ")
        lines.extend(render_lines(n.get("nodes", []) or [], child_prefix))
    return lines


def node_depth(node: dict[str, Any], depth: int = 0) -> int:
    children = node.get("nodes", []) or []
    return max([depth, *(node_depth(child, depth + 1) for child in children)])


def count_nodes(nodes: list[dict[str, Any]]) -> int:
    return sum(1 + count_nodes(node.get("nodes", []) or []) for node in nodes)


def render_html_nodes(nodes: list[dict[str, Any]], level: int = 0) -> str:
    parts: list[str] = []
    for node in nodes:
        children = node.get("nodes", []) or []
        title = html.escape(str(node.get("title", "")))
        node_id = html.escape(str(node.get("node_id", "")))
        start = node.get("start_index")
        end = node.get("end_index")
        own_start = node.get("own_start_index")
        own_end = node.get("own_end_index")
        page = f"{start}–{end}"
        own = ""
        if (own_start, own_end) != (start, end):
            own = f"<span class=\"badge badge-own\">own {html.escape(str(own_start))}–{html.escape(str(own_end))}</span>"
        child_badge = f"<span class=\"badge badge-child\">{len(children)} child</span>" if children else ""
        open_attr = " open" if level < 2 else ""
        row = (
            f"<span class=\"node-row level-{min(level, 6)}\" data-title=\"{title.lower()}\" "
            f"data-page=\"{html.escape(page)}\">"
            f"<span class=\"title\">{title}</span>"
            f"<span class=\"badge badge-page\">p.{html.escape(page)}</span>"
            f"{own}"
            f"<span class=\"badge badge-id\">#{node_id}</span>"
            f"{child_badge}"
            "</span>"
        )
        if children:
            parts.append(
                f"<details class=\"tree-node level-{min(level, 6)}\"{open_attr}>"
                f"<summary>{row}</summary>"
                f"<div class=\"children\">{render_html_nodes(children, level + 1)}</div>"
                "</details>"
            )
        else:
            parts.append(f"<div class=\"leaf tree-node level-{min(level, 6)}\">{row}</div>")
    return "\n".join(parts)


def render_html_document(roots: list[dict[str, Any]], lines: list[str]) -> str:
    node_total = count_nodes(roots)
    max_depth = max((node_depth(root) for root in roots), default=0)
    escaped_text = "\n".join(html.escape(line) for line in lines)
    tree_html = render_html_nodes(roots)
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>GMP Guidance Tree</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #ffffff;
      --panel: #ffffff;
      --ink: #1f2933;
      --muted: #6b7280;
      --line: #e5e7eb;
      --soft: #f8fafc;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans KR", "Apple SD Gothic Neo", sans-serif;
    }}
    .wrap {{ max-width: 1320px; margin: 0 auto; padding: 24px; }}
    header {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 16px;
      align-items: end;
      margin-bottom: 16px;
      padding-bottom: 16px;
      border-bottom: 1px solid var(--line);
    }}
    h1 {{ margin: 0; font-size: 24px; letter-spacing: -0.02em; font-weight: 700; }}
    .subtitle {{ margin: 6px 0 0; color: var(--muted); font-size: 14px; }}
    .stats {{ display: flex; gap: 10px; flex-wrap: wrap; justify-content: flex-end; }}
    .stat {{
      min-width: 88px;
      padding: 8px 10px;
      background: var(--soft);
      border: 1px solid var(--line);
      border-radius: 8px;
    }}
    .stat strong {{ display:block; font-size: 16px; }}
    .stat span {{ color: var(--muted); font-size: 12px; }}
    .toolbar {{
      position: sticky;
      top: 0;
      z-index: 5;
      display: flex;
      gap: 8px;
      align-items: center;
      margin-bottom: 14px;
      padding: 10px 0;
      background: rgba(255,255,255,0.94);
      border-bottom: 1px solid var(--line);
    }}
    input[type="search"] {{
      flex: 1;
      min-width: 180px;
      padding: 9px 10px;
      border: 1px solid var(--line);
      border-radius: 6px;
      font-size: 14px;
      outline: none;
      background: white;
    }}
    input[type="search"]:focus {{ border-color: #9ca3af; }}
    button {{
      border: 1px solid var(--line);
      background: white;
      color: var(--ink);
      border-radius: 6px;
      padding: 9px 10px;
      cursor: pointer;
      font-weight: 600;
    }}
    button:hover {{ background: var(--soft); }}
    .layout {{ display: grid; grid-template-columns: minmax(0, 1fr) 340px; gap: 16px; align-items: start; }}
    .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
    }}
    .panel-head {{
      display:flex;
      justify-content:space-between;
      gap:12px;
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
      background: var(--soft);
    }}
    .panel-head h2 {{ margin:0; font-size: 15px; }}
    .hint {{ color: var(--muted); font-size: 12px; }}
    .tree {{ padding: 12px 14px 18px; }}
    details {{ position: relative; }}
    summary {{ list-style: none; cursor: pointer; }}
    summary::-webkit-details-marker {{ display: none; }}
    summary::before {{
      content: "▸";
      display: inline-flex;
      width: 20px;
      height: 20px;
      align-items: center;
      justify-content: center;
      margin-right: 4px;
      color: var(--muted);
      transition: transform .15s ease;
    }}
    details[open] > summary::before {{ transform: rotate(90deg); color: #374151; }}
    .children {{
      margin-left: 22px;
      padding-left: 14px;
      border-left: 1px solid var(--line);
    }}
    .tree-node {{ margin: 3px 0; }}
    .leaf {{ margin-left: 24px; }}
    .node-row {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      max-width: 100%;
      padding: 4px 6px;
      border-radius: 5px;
      line-height: 1.45;
      vertical-align: top;
    }}
    .node-row:hover {{ background: #f8fafc; }}
    .title {{ overflow-wrap: anywhere; }}
    .level-0 > summary .node-row, .leaf.level-0 .node-row {{ font-weight: 750; font-size: 16px; }}
    .level-1 > summary .node-row, .leaf.level-1 .node-row {{ font-weight: 700; }}
    .level-2 > summary .node-row, .leaf.level-2 .node-row {{ font-weight: 650; }}
    .level-3 > summary .node-row, .leaf.level-3 .node-row {{ font-weight: 600; }}
    .badge {{
      flex: 0 0 auto;
      display: inline-flex;
      align-items: center;
      border-radius: 4px;
      padding: 1px 5px;
      font-size: 11px;
      font-weight: 600;
      white-space: nowrap;
      border: 1px solid var(--line);
      color: var(--muted);
      background: #fff;
    }}
    .badge-page {{ color: #374151; background: #f9fafb; }}
    .badge-own {{ color: #57534e; background: #fafaf9; }}
    .badge-id {{ color: #6b7280; background: #ffffff; }}
    .badge-child {{ color: #6b7280; background: #f9fafb; }}
    mark {{ background: #fef3c7; padding: 0 .08em; border-radius: 3px; }}
    .side {{ position: sticky; top: 74px; display: grid; gap: 16px; }}
    .focus {{ padding: 14px; }}
    .focus h3 {{ margin: 0 0 12px; font-size: 15px; }}
    .focus ul {{ margin: 0; padding-left: 20px; color: var(--muted); line-height: 1.7; }}
    .focus li strong {{ color: var(--ink); }}
    pre {{
      margin: 0;
      max-height: 520px;
      overflow: auto;
      padding: 16px;
      background: #fafafa;
      color: #374151;
      font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
      font-size: 12px;
      line-height: 1.55;
      white-space: pre;
    }}
    .hidden-by-search {{ display: none !important; }}
    .dimmed {{ opacity: .32; }}
    @media (max-width: 980px) {{
      header, .layout {{ grid-template-columns: 1fr; }}
      .stats {{ justify-content: flex-start; }}
      .side {{ position: static; }}
      .toolbar {{ flex-wrap: wrap; }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <header>
      <div>
        <h1>GMP Guidance Tree</h1>
        <p class="subtitle">PageIndex 기반 GMP 문서 TOC 트리 · 전체 branch 세밀도 확장본</p>
      </div>
      <div class="stats">
        <div class="stat"><strong>{node_total}</strong><span>nodes</span></div>
        <div class="stat"><strong>{max_depth}</strong><span>max depth</span></div>
        <div class="stat"><strong>1–606</strong><span>pages</span></div>
      </div>
    </header>
    <div class="toolbar">
      <input id="search" type="search" placeholder="검색: 품질경영, 밸리데이션, 제조관리, p.54 ...">
      <button type="button" onclick="setAll(true)">전체 펼치기</button>
      <button type="button" onclick="setAll(false)">접기</button>
    </div>
    <div class="layout">
      <main class="panel">
        <div class="panel-head">
          <h2>Interactive Tree</h2>
          <span class="hint">클릭해서 접고 펼칠 수 있음</span>
        </div>
        <div id="tree" class="tree">
          {tree_html}
        </div>
      </main>
      <aside class="side">
        <section class="panel focus">
          <h3>읽는 방법</h3>
          <ul>
            <li>상위 branch는 기본으로 열어 전체 균형을 먼저 볼 수 있음</li>
            <li>검색어를 입력하면 매칭 branch의 부모가 자동으로 열림</li>
            <li>각 node의 p.범위와 own 범위를 함께 확인 가능</li>
          </ul>
        </section>
        <section class="panel">
          <div class="panel-head"><h2>Raw tree</h2><span class="hint">복사용</span></div>
          <pre>{escaped_text}</pre>
        </section>
      </aside>
    </div>
  </div>
  <script>
    const tree = document.getElementById('tree');
    const search = document.getElementById('search');
    function setAll(open) {{
      document.querySelectorAll('details').forEach(d => d.open = open);
    }}
    function normalize(s) {{ return (s || '').toLowerCase().replace(/\\s+/g, ''); }}
    function clearMarks() {{
      document.querySelectorAll('.title').forEach(el => {{
        el.innerHTML = el.textContent;
      }});
    }}
    search.addEventListener('input', () => {{
      const q = normalize(search.value);
      clearMarks();
      document.querySelectorAll('.tree-node').forEach(n => n.classList.remove('hidden-by-search', 'dimmed'));
      if (!q) return;
      document.querySelectorAll('.tree-node').forEach(node => {{
        const text = normalize(node.textContent);
        const match = text.includes(q);
        if (match) {{
          let p = node.parentElement;
          while (p) {{
            if (p.tagName === 'DETAILS') p.open = true;
            p = p.parentElement;
          }}
        }} else {{
          node.classList.add('dimmed');
        }}
      }});
    }});
  </script>
</body>
</html>
"""


def write_visualizations(doc: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    roots = doc.get("structure") if isinstance(doc.get("structure"), list) else [doc.get("structure")]
    lines = render_lines(roots)
    txt = "\n".join(lines) + "\n"
    (out_dir / "gmp_guidance_tree.txt").write_text(txt, encoding="utf-8")
    (out_dir / "gmp_guidance_tree.md").write_text("# GMP Guidance Tree\n\n```text\n" + txt + "```\n", encoding="utf-8")
    (out_dir / "gmp_guidance_tree.html").write_text(render_html_document(roots, lines), encoding="utf-8")


def write_candidate_artifacts(candidate: dict[str, Any], manifest: dict[str, Any], artifact_dir: Path, stamp: str) -> tuple[Path, Path]:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    json_path = artifact_dir / f"gmp-facility-targeted-expansion-candidate-{stamp}.json"
    md_path = artifact_dir / f"gmp-facility-targeted-expansion-candidate-{stamp}.md"
    write_json(json_path, candidate)
    lines = render_lines([candidate])
    sources = "\n".join(f"- {key}: {path}" for key, path in manifest["source_files"].items())
    md_path.write_text(
        "# GMP Facility Targeted Expansion Candidate\n\n"
        "## Source files\n" + sources + "\n\n"
        "## Candidate tree\n\n```text\n" + "\n".join(lines) + "\n```\n",
        encoding="utf-8",
    )
    return json_path, md_path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tree", default="results/gmp_guidance_structure.json")
    ap.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    ap.add_argument("--artifact-dir", default=".omx/artifacts")
    ap.add_argument("--visualization-dir", default="results/visualizations")
    ap.add_argument("--candidate-only", action="store_true")
    ap.add_argument("--merge", action="store_true")
    ap.add_argument("--stamp", default=None)
    args = ap.parse_args()

    stamp = args.stamp or utc_stamp()
    tree_path = Path(args.tree)
    artifact_dir = Path(args.artifact_dir)
    manifest = load_manifest(Path(args.manifest))
    candidate = manifest["candidate_subtree"]
    json_path, md_path = write_candidate_artifacts(candidate, manifest, artifact_dir, stamp)

    backup_path = artifact_dir / f"gmp-guidance-structure-baseline-before-facility-expansion-{stamp}.json"
    if tree_path.exists() and not backup_path.exists():
        backup_path.write_text(tree_path.read_text(encoding="utf-8"), encoding="utf-8")

    summary = {
        "stamp": stamp,
        "manifest": str(args.manifest),
        "candidate_json": str(json_path),
        "candidate_md": str(md_path),
        "baseline_backup": str(backup_path),
        "merged_tree": None,
        "visualizations": None,
    }

    if args.merge:
        doc = load_json(tree_path)
        merged = replace_target_tree(doc, candidate, manifest["target_path"])
        write_json(tree_path, merged)
        write_visualizations(merged, Path(args.visualization_dir))
        summary["merged_tree"] = str(tree_path)
        summary["visualizations"] = str(args.visualization_dir)

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
