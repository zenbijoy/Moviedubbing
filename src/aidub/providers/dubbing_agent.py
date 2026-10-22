"""Dubbing Agent — Autonomous agentic orchestration loop."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from aidub.contracts.base import Identifier
from aidub.providers.agent_state import AgentState, SegmentState
from aidub.providers.agent_tools import DubbingAgentToolRegistry
from aidub.providers.router import LlmProviderRouter, LlmRequest

logger = logging.getLogger(__name__)


class DubbingAgent:
    """
    Autonomous agentic dubbing coordinator.

    Loops over dialogue segments, planning tool usage (translation, QC, fitting,
    glossary extraction), observing execution output, and refining results until
    quality thresholds are met.
    """

    def __init__(
        self,
        router: LlmProviderRouter,
        tools: DubbingAgentToolRegistry,
        *,
        max_iterations: int = 15,
        quality_threshold: float = 0.80,
    ) -> None:
        self._router = router
        self._tools = tools
        self._max_iterations = max_iterations
        self._quality_threshold = quality_threshold

    def run(
        self,
        segments: list[dict[str, Any]],
        source_language: str = "auto",
        target_language: str = "bn",
    ) -> AgentState:
        """
        Execute agentic dubbing workflow over segments.

        Args:
            segments: List of input raw dialogue segments.
            source_language: Original audio language.
            target_language: Target dubbing language tag.

        Returns:
            AgentState containing final translated and verified segments.
        """
        parsed_segs = [
            SegmentState(
                utterance_id=Identifier(s.get("utterance_id", f"seg_{i:03d}")),
                speaker_id=Identifier(s.get("speaker_id", "spk_0")),
                source_text=s.get("text", s.get("source_text", "")),
                target_text=s.get("tgt", s.get("target_text", "")),
                start_ms=int(float(s.get("start", 0)) * 1000),
                end_ms=int(float(s.get("end", 0)) * 1000),
                duration_ms=int((float(s.get("end", 0)) - float(s.get("start", 0))) * 1000),
            )
            for i, s in enumerate(segments)
        ]

        state = AgentState(
            segments=parsed_segs,
            source_language=source_language,
            target_language=target_language,
        )

        logger.info(
            "Dubbing Agent starting loop: %d segments, target_lang=%s, max_iterations=%d",
            state.total_segments,
            target_language,
            self._max_iterations,
        )

        for iteration in range(self._max_iterations):
            if state.all_segments_pass(self._quality_threshold):
                logger.info(
                    "Dubbing Agent achieved quality threshold (%.2f) at iteration %d",
                    state.pass_rate,
                    iteration,
                )
                break

            system_prompt = self._build_system_prompt()
            user_prompt = self._build_user_prompt(state, iteration)

            request = LlmRequest(
                request_id=Identifier(f"agent_loop_iter_{iteration}"),
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.2,
                json_mode=False,
            )

            try:
                response = self._router.complete(request)
            except Exception as exc:
                logger.warning("Agent LLM call failed on iteration %d: %s", iteration, exc)
                break

            tool_action = _parse_tool_call(response.content)
            if not tool_action:
                logger.info("Agent signaled completion or no tool call in output.")
                break

            tool_name, tool_args = tool_action
            logger.info("Agent selected action [Iter %d]: %s", iteration, tool_name)

            try:
                result = self._tools.execute(tool_name, tool_args)
                state.iteration_history.append(
                    {
                        "iteration": iteration,
                        "action": tool_name,
                        "args": tool_args,
                        "result_summary": str(result)[:300],
                    }
                )
                self._apply_tool_result_to_state(state, tool_name, tool_args, result)
            except Exception as exc:
                logger.error("Agent tool execution error (%s): %s", tool_name, exc)
                state.iteration_history.append(
                    {
                        "iteration": iteration,
                        "action": tool_name,
                        "error": str(exc),
                    }
                )

        return state

    def _build_system_prompt(self) -> str:
        tools_schema = self._tools.get_tools_schema_openai()
        tools_desc = "\n".join(
            f"- {t['function']['name']}: {t['function']['description']}" for t in tools_schema
        )
        return (
            "You are an AI Dubbing Agent producing a high-quality localized film dubbing.\n"
            "Your objective is to translate dialogue, maintain terminology consistency, and ensure speech fits target video timing slots.\n\n"
            f"Available tools:\n{tools_desc}\n\n"
            "To execute a tool, reply ONLY in the following format:\n"
            "TOOL: <tool_name>\n"
            "ARGS: <valid_json_arguments_object>\n\n"
            "If all segments are translated and verified satisfactorily, reply with: DONE"
        )

    def _build_user_prompt(self, state: AgentState, iteration: int) -> str:
        untranslated = [s for s in state.segments if not s.target_text]
        unverified = [s for s in state.segments if s.target_text and not s.passed_qc]

        status_summary = (
            f"Iteration {iteration}/{self._max_iterations}\n"
            f"Total Segments: {state.total_segments}\n"
            f"Pass Rate: {state.pass_rate * 100:.1f}%\n"
            f"Untranslated: {len(untranslated)}\n"
            f"Unverified: {len(unverified)}\n\n"
            "Sample Segments Needing Attention:\n"
        )

        attn_list = (untranslated + unverified)[:5]
        for s in attn_list:
            status_summary += f"- ID: {s.utterance_id} | Source: {s.source_text!r} | Target: {s.target_text!r} | Dur: {s.duration_ms}ms\n"

        return status_summary

    def _apply_tool_result_to_state(
        self,
        state: AgentState,
        tool_name: str,
        tool_args: dict[str, Any],
        result: Any,
    ) -> None:
        if tool_name == "translate_batch" and isinstance(result, list):
            for res in result:
                if isinstance(res, dict) and "utterance_id" in res:
                    state.update_segment_translation(
                        res["utterance_id"], res.get("translated_text", "")
                    )
        elif tool_name == "evaluate_quality" and isinstance(result, dict):
            u_id = result.get("utterance_id")
            if u_id:
                state.update_segment_qc(
                    u_id,
                    quality_score=float(result.get("score", 0.0)),
                    passed_qc=bool(result.get("passed", False)),
                )


def _parse_tool_call(content: str) -> tuple[str, dict[str, Any]] | None:
    match = re.search(r"TOOL:\s*(\w+)\s*\nARGS:\s*(\{.*?\})", content, re.DOTALL)
    if not match:
        return None
    tool_name = match.group(1).strip()
    try:
        args = json.loads(match.group(2).strip())
        return tool_name, args
    except Exception:
        return None


__all__ = ["DubbingAgent"]
