#!/usr/bin/env python3
"""Smoke assertions for the local GMP PageIndex UI contracts."""

from __future__ import annotations

import ast
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pageindex.ui_contracts import ArtifactLoadError, ArtifactPaths, ScoreSemantics, assert_canonical_score_view  # noqa: E402
from pageindex.ui_data import load_app_view_model  # noqa: E402
import pageindex.ui_data as ui_data  # noqa: E402
from pageindex.ui_experiments import EXPERIMENT_ENABLE_ENV, DEDICATED_RUNS_ROOT, build_experiment_command, is_experiment_enabled, run_experiment  # noqa: E402


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    source_path = Path(ui_data.__file__)
    module_ast = ast.parse(source_path.read_text(encoding="utf-8"))
    forbidden_imports = []
    for node in ast.walk(module_ast):
        if isinstance(node, ast.Import):
            forbidden_imports.extend(alias.name for alias in node.names if alias.name == "streamlit")
        elif isinstance(node, ast.ImportFrom) and node.module == "streamlit":
            forbidden_imports.append(node.module)
    assert_true(not forbidden_imports, "core ui_data.py must not import Streamlit")

    os.environ.pop(EXPERIMENT_ENABLE_ENV, None)
    assert_true(not is_experiment_enabled(), "v0.3 runner must be disabled by default")

    vm = load_app_view_model()
    canonical = vm.canonical_score
    diagnostic = vm.diagnostic_score
    assert_canonical_score_view(canonical)
    assert_true(canonical.semantics is ScoreSemantics.CANONICAL_096, "canonical header must use CANONICAL_096")
    assert_true(canonical.is_canonical, "canonical score view must be marked canonical")
    assert_true(round(canonical.value, 2) == 0.96, f"expected canonical 0.96, got {canonical.value}")
    assert_true(diagnostic.semantics is ScoreSemantics.DIAGNOSTIC_099, "0.99 must be diagnostic semantics")
    assert_true(not diagnostic.is_canonical, "diagnostic score must not be canonical")
    assert_true(round(diagnostic.value, 2) == 0.99, f"expected diagnostic 0.99, got {diagnostic.value}")
    assert_true("gmp_eval_025" in vm.corpus.unresolved_ids, "gmp_eval_025 must remain visible as unresolved")
    assert_true(len(vm.eval_rows) == 100, "expected 100 eval rows")
    assert_true(vm.corpus.page_count == 606, "expected 606-page corpus")

    missing = ArtifactPaths(workspace_json=Path("/tmp/does-not-exist-gmp-guidance.json"))
    try:
        load_app_view_model(missing)
    except ArtifactLoadError:
        pass
    else:
        raise AssertionError("missing workspace artifact must fail closed")

    command = build_experiment_command(vm.paths)
    assert_true("--prediction-page-hit-mode" in command, "runner command must use explicit page-hit mode")
    manifest = run_experiment(command, DEDICATED_RUNS_ROOT, dry_run=True)
    assert_true(manifest.dry_run, "dry run manifest must mark dry_run=true")
    assert_true(manifest.manifest_path.exists(), "dry run manifest must be written")
    assert_true(str(manifest.run_dir).startswith(str(DEDICATED_RUNS_ROOT)), "runner must write to dedicated run directory")

    for bad_dir in [Path("results/pageindex_ui_runs/../../page_alignment"), DEDICATED_RUNS_ROOT.parent / "page_alignment"]:
        try:
            run_experiment(command, bad_dir, dry_run=True)
        except RuntimeError:
            pass
        else:
            raise AssertionError(f"runner must reject canonical/traversal output dir: {bad_dir}")

    print(
        "UI smoke OK: canonical=%.2f diagnostic=%.2f eval_rows=%d unresolved=%s"
        % (canonical.value, diagnostic.value, len(vm.eval_rows), ",".join(vm.corpus.unresolved_ids))
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
