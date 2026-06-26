"""Opt-in experiment runner for the GMP PageIndex UI.

The default app path is read-only/offline. This module only runs subprocesses
when an explicit environment gate is enabled. All run outputs are constrained to
`results/pageindex_ui_runs/*`; canonical GMP artifacts are never valid output
locations.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .ui_contracts import ArtifactPaths

EXPERIMENT_ENABLE_ENV = "GMP_PAGEINDEX_UI_ENABLE_RUNNER"
REPO_ROOT = Path(__file__).resolve().parents[1]
DEDICATED_RUNS_ROOT = (REPO_ROOT / "results/pageindex_ui_runs").resolve()
CANONICAL_ROOTS = tuple(
    (REPO_ROOT / path).resolve()
    for path in (
        "results/pageindex_gmp_workspace",
        "results/page_alignment",
    )
)


@dataclass(frozen=True)
class ExperimentManifest:
    run_id: str
    command: list[str]
    run_dir: Path
    manifest_path: Path
    stdout_path: Path | None
    stderr_path: Path | None
    exit_code: int | None
    dry_run: bool
    enabled_env: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "command": self.command,
            "run_dir": str(self.run_dir),
            "manifest_path": str(self.manifest_path),
            "stdout_path": str(self.stdout_path) if self.stdout_path else None,
            "stderr_path": str(self.stderr_path) if self.stderr_path else None,
            "exit_code": self.exit_code,
            "dry_run": self.dry_run,
            "enabled_env": self.enabled_env,
            "created_at": self.created_at,
        }


def is_experiment_enabled() -> bool:
    return os.environ.get(EXPERIMENT_ENABLE_ENV) == "1"


def build_experiment_command(paths: ArtifactPaths) -> list[str]:
    """Build the default deterministic evaluation command for a UI run.

    This command does not call model APIs. It reruns the local official eval over
    existing predictions with the page-alignment map. run_experiment appends
    trace report paths constrained under `results/pageindex_ui_runs/*`.
    """

    return [
        ".venv/bin/python",
        "scripts/gmp_pageindex_codex_eval.py",
        "--predictions",
        str(paths.predictions_jsonl),
        "--page-alignment-map",
        str(paths.alignment_map_json),
        "--prediction-page-hit-mode",
        "aligned_predicted_union",
        "--prediction-min-page-hit",
        "0.96",
        "--prediction-min-section-hit",
        "0.25",
        "--prediction-min-grounding",
        "1.0",
    ]


def run_experiment(command: list[str], runs_dir: Path, dry_run: bool = True, timeout_sec: int = 120) -> ExperimentManifest:
    safe_runs_dir = _resolve_run_root(runs_dir)
    created_at = datetime.now(timezone.utc).isoformat()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run_dir = (safe_runs_dir / run_id).resolve()
    _ensure_under(run_dir, DEDICATED_RUNS_ROOT, "run directory")
    run_dir.mkdir(parents=True, exist_ok=False)
    stdout_path = run_dir / "stdout.txt"
    stderr_path = run_dir / "stderr.txt"
    manifest_path = run_dir / "manifest.json"
    trace_json_path = run_dir / "score.json"
    trace_md_path = run_dir / "score.md"

    command = list(command)
    command_with_outputs = command + [
        "--json-report",
        str(trace_json_path),
        "--md-report",
        str(trace_md_path),
    ]
    _validate_output_containment(command_with_outputs)

    exit_code: int | None = None
    if not dry_run:
        if not is_experiment_enabled():
            raise RuntimeError(f"Experiment runner is disabled. Set {EXPERIMENT_ENABLE_ENV}=1 to run commands.")
        proc = subprocess.run(  # noqa: S603 - explicit opt-in local command from controlled UI command builder.
            command_with_outputs,
            check=False,
            text=True,
            capture_output=True,
            timeout=timeout_sec,
        )
        stdout_path.write_text(proc.stdout, encoding="utf-8")
        stderr_path.write_text(proc.stderr, encoding="utf-8")
        exit_code = proc.returncode
    else:
        stdout_path.write_text("DRY RUN: command not executed.\n", encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")

    manifest = ExperimentManifest(
        run_id=run_id,
        command=command_with_outputs,
        run_dir=run_dir,
        manifest_path=manifest_path,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        exit_code=exit_code,
        dry_run=dry_run,
        enabled_env=f"{EXPERIMENT_ENABLE_ENV}={os.environ.get(EXPERIMENT_ENABLE_ENV, '')}",
        created_at=created_at,
    )
    manifest_path.write_text(json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def _resolve_repo_path(path: Path) -> Path:
    return path.resolve() if path.is_absolute() else (REPO_ROOT / path).resolve()


def _resolve_run_root(runs_dir: Path) -> Path:
    resolved = _resolve_repo_path(runs_dir)
    _ensure_under(resolved, DEDICATED_RUNS_ROOT, "runs root")
    return resolved


def _ensure_under(path: Path, root: Path, label: str) -> None:
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise RuntimeError(f"Invalid {label}: {path} is outside dedicated run root {root}.") from exc


def _validate_output_containment(command: list[str]) -> None:
    output_flags = {"--json-report", "--md-report", "--output", "--report", "--out-dir"}
    for index, token in enumerate(command[:-1]):
        if token not in output_flags:
            continue
        output_path = _resolve_repo_path(Path(command[index + 1]))
        if not _is_under(output_path, DEDICATED_RUNS_ROOT):
            raise RuntimeError(f"Experiment output path is outside dedicated run root: {output_path}")
        for root in CANONICAL_ROOTS:
            if _is_under(output_path, root):
                raise RuntimeError(f"Experiment output path touches canonical artifacts: {output_path}")


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True
