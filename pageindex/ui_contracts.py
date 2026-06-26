"""Typed contracts for the local GMP PageIndex UI.

This module intentionally has no Streamlit dependency. It defines the small set
of value objects the Streamlit shell is allowed to render, which keeps canonical
score semantics separate from diagnostic-only metrics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class ArtifactLoadError(RuntimeError):
    """Raised when a required local UI artifact is missing or malformed."""


class ScoreSemantics(str, Enum):
    """Explicit score channels used by the UI.

    The canonical header must only consume CANONICAL_096. Diagnostic views may
    render DIAGNOSTIC_099, but the two are deliberately different enum values.
    """

    CANONICAL_096 = "canonical_aligned_predicted_union_096"
    ORIGINAL_093 = "original_predicted_pages_093"
    DIAGNOSTIC_099 = "diagnostic_evidence_plus_aligned_099"
    DIAGNOSTIC_REPAIRED = "diagnostic_repaired_append_direct"


@dataclass(frozen=True)
class ScoreView:
    semantics: ScoreSemantics
    label: str
    value: float
    description: str
    is_canonical: bool = False


@dataclass(frozen=True)
class CorpusSummary:
    doc_id: str
    doc_name: str
    page_count: int
    tree_node_count: int
    mapped_internal_pages: int
    dominant_offset: int | None
    unresolved_ids: tuple[str, ...]


@dataclass(frozen=True)
class PageView:
    physical_page: int
    internal_page: int | None
    aligned_from_internal: int | None
    first_line: str
    content: str


@dataclass(frozen=True)
class TreeNodeView:
    node_id: str
    title: str
    path: tuple[str, ...]
    depth: int
    page_range: str
    subtree_range: str
    score: float = 0.0


@dataclass(frozen=True)
class EvalRowView:
    row_id: str
    question: str
    difficulty: str
    question_type: str
    expected_answer: str
    gold_pages: str
    gold_section_path: tuple[str, ...]
    predicted_pages: str
    aligned_predicted_pages: str
    evidence_pages_read: str
    aligned_evidence_pages_read: str
    evidence_plus_aligned_pages: str
    original_hit: bool
    aligned_hit: bool
    evidence_plus_aligned_hit: bool
    classification: str
    predicted_section_path: tuple[str, ...] = field(default_factory=tuple)
    reason: str = ""


@dataclass(frozen=True)
class ArtifactPaths:
    workspace_json: Path = Path("results/pageindex_gmp_workspace/gmp-guidance.json")
    alignment_map_json: Path = Path("results/page_alignment/gmp_page_alignment_map.json")
    official_score_json: Path = Path("results/page_alignment/score_001_100_agentic_official_alignment.json")
    eval_jsonl: Path = Path("eval/gmp_eval_testset.jsonl")
    predictions_jsonl: Path = Path("results/codex_agentic_10x10/predictions_001_100_agentic.jsonl")
    repaired_predictions_jsonl: Path = Path("results/codex_agentic_10x10/predictions_001_100_agentic_repaired_append_direct.jsonl")
    experiment_runs_dir: Path = Path("results/pageindex_ui_runs")


@dataclass(frozen=True)
class AppViewModel:
    corpus: CorpusSummary
    scores: dict[ScoreSemantics, ScoreView]
    tree_nodes: tuple[TreeNodeView, ...]
    eval_rows: tuple[EvalRowView, ...]
    paths: ArtifactPaths

    @property
    def canonical_score(self) -> ScoreView:
        return self.scores[ScoreSemantics.CANONICAL_096]

    @property
    def diagnostic_score(self) -> ScoreView:
        return self.scores[ScoreSemantics.DIAGNOSTIC_099]


def assert_canonical_score_view(score: ScoreView) -> None:
    """Fail fast if a diagnostic score is accidentally routed to the header."""

    if score.semantics is not ScoreSemantics.CANONICAL_096 or not score.is_canonical:
        raise ArtifactLoadError(
            "Canonical header must render ScoreSemantics.CANONICAL_096 only; "
            f"got {score.semantics!r}."
        )


def ensure_no_streamlit_imported(namespace: dict[str, Any]) -> None:
    """Smoke helper: core modules should not import Streamlit."""

    if "streamlit" in namespace or "st" in namespace:
        raise ArtifactLoadError("Core UI contract/data layer must not import Streamlit.")
