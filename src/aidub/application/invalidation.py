"""Dependency-aware artifact invalidation."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum


class ArtifactStage(StrEnum):
    SOURCE = "source"
    PROXY = "proxy"
    SCENE_ANALYSIS = "scene_analysis"
    STEMS = "stems"
    TRANSCRIPT = "transcript"
    DIARIZATION = "diarization"
    TRANSLATION = "translation"
    VOICE = "voice"
    TIMING = "timing"
    LIPSYNC = "lipsync"
    MIX = "mix"
    SUBTITLE = "subtitle"
    QC = "qc"
    EXPORT = "export"


@dataclass(frozen=True, slots=True)
class DependencyNode:
    key: str
    stage: ArtifactStage
    localization_id: str | None = None
    utterance_id: str | None = None
    character_id: str | None = None
    shot_id: str | None = None


@dataclass(frozen=True, slots=True)
class PartialRenderPlan:
    """Execution plan for intelligent partial re-rendering."""

    total_nodes: int
    invalidated_nodes: int
    reusable_cached_nodes: int
    saved_compute_percent: float
    execution_order: tuple[str, ...]


class InvalidationGraph:
    def __init__(self) -> None:
        self._nodes: dict[str, DependencyNode] = {}
        self._parents: dict[str, set[str]] = defaultdict(set)
        self._children: dict[str, set[str]] = defaultdict(set)

    def add(self, node: DependencyNode, *, depends_on: Iterable[str] = ()) -> None:
        if node.key in self._nodes:
            raise ValueError(f"duplicate dependency node: {node.key}")
        dependencies = tuple(depends_on)
        missing = set(dependencies) - self._nodes.keys()
        if missing:
            raise ValueError(f"missing dependency nodes: {', '.join(sorted(missing))}")
        self._nodes[node.key] = node
        for dependency in dependencies:
            self._children[dependency].add(node.key)
            self._parents[node.key].add(dependency)
        if node.key in self.affected_by(node.key):
            self._nodes.pop(node.key)
            for dependency in dependencies:
                self._children[dependency].discard(node.key)
                self._parents[node.key].discard(dependency)
            raise ValueError("dependency cycle detected")

    def affected_by(self, key: str) -> frozenset[str]:
        if key not in self._nodes:
            return frozenset()
        affected: set[str] = set()
        pending = list(self._children[key])
        while pending:
            child = pending.pop()
            if child not in affected:
                affected.add(child)
                pending.extend(self._children[child])
        return frozenset(affected)

    def invalidate_translation(self, *, localization_id: str, utterance_id: str) -> frozenset[str]:
        roots = [
            key
            for key, node in self._nodes.items()
            if node.stage == ArtifactStage.TRANSLATION
            and node.localization_id == localization_id
            and node.utterance_id == utterance_id
        ]
        affected: set[str] = set(roots)
        for root in roots:
            affected.update(self.affected_by(root))
        return frozenset(affected)

    def invalidate_music_track(self, *, track_key: str = "music_track") -> frozenset[str]:
        """
        Invalidate background music track.
        Cascades ONLY to MIX, QC, and EXPORT stages without touching VOICE or LIPSYNC.
        """
        roots = [
            key
            for key, node in self._nodes.items()
            if node.key == track_key
            or (node.stage == ArtifactStage.STEMS and node.key.endswith("_music"))
        ]
        affected: set[str] = set(roots)
        for root in roots:
            affected.update(self.affected_by(root))
        return frozenset(affected)

    def invalidate_lipsync_shot(self, *, shot_id: str) -> frozenset[str]:
        """
        Invalidate visual lip-sync for a single shot.
        Cascades ONLY to LIPSYNC, QC, and EXPORT stages.
        """
        roots = [
            key
            for key, node in self._nodes.items()
            if node.stage == ArtifactStage.LIPSYNC and node.shot_id == shot_id
        ]
        affected: set[str] = set(roots)
        for root in roots:
            affected.update(self.affected_by(root))
        return frozenset(affected)

    def invalidate_voice_character(self, *, character_id: str) -> frozenset[str]:
        """
        Invalidate all voice synthesis and downstream artifacts for a specific character voice actor.
        """
        roots = [
            key
            for key, node in self._nodes.items()
            if node.stage == ArtifactStage.VOICE and node.character_id == character_id
        ]
        affected: set[str] = set(roots)
        for root in roots:
            affected.update(self.affected_by(root))
        return frozenset(affected)

    def create_partial_render_plan(self, invalidated_keys: Iterable[str]) -> PartialRenderPlan:
        """
        Compute topologically sorted execution queue of invalidated nodes and compute savings percentage.
        """
        inv_set = set(invalidated_keys)
        total_nodes = len(self._nodes)
        if total_nodes == 0:
            return PartialRenderPlan(0, 0, 0, 100.0, ())

        invalidated_count = len(inv_set)
        reusable_count = max(0, total_nodes - invalidated_count)
        saved_percent = round((reusable_count / total_nodes) * 100.0, 2)

        # Topological sort of invalidated nodes (Kahn's algorithm on subgraph)
        in_degree = dict.fromkeys(inv_set, 0)
        for k in inv_set:
            for p in self._parents[k]:
                if p in inv_set:
                    in_degree[k] += 1

        queue = [k for k in inv_set if in_degree[k] == 0]
        sorted_order: list[str] = []

        while queue:
            curr = queue.pop(0)
            sorted_order.append(curr)
            for child in self._children[curr]:
                if child in inv_set:
                    in_degree[child] -= 1
                    if in_degree[child] == 0:
                        queue.append(child)

        return PartialRenderPlan(
            total_nodes=total_nodes,
            invalidated_nodes=invalidated_count,
            reusable_cached_nodes=reusable_count,
            saved_compute_percent=saved_percent,
            execution_order=tuple(sorted_order),
        )


__all__ = [
    "ArtifactStage",
    "DependencyNode",
    "InvalidationGraph",
    "PartialRenderPlan",
]
