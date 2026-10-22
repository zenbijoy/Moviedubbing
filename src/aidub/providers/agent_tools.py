"""Agent tool registry and tool definitions for the agentic dubbing workflow."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class AgentTool:
    """A callable tool exposed to the Dubbing Agent."""

    name: str
    description: str
    fn: Callable[..., Any]
    parameters_schema: dict[str, Any]


class DubbingAgentToolRegistry:
    """
    Registry of tools accessible by the Dubbing Agent.

    Provides schema formatting for LLM function calling and safe tool invocation.
    """

    def __init__(self) -> None:
        self._tools: dict[str, AgentTool] = {}

    def register(self, tool: AgentTool) -> None:
        """Register a tool with the registry."""
        self._tools[tool.name] = tool
        logger.debug("Registered agent tool: %s", tool.name)

    def get_tool(self, name: str) -> AgentTool | None:
        """Retrieve a registered tool by name."""
        return self._tools.get(name)

    def get_tools_schema_openai(self) -> list[dict[str, Any]]:
        """Format registered tools for OpenAI/OpenRouter function calling API."""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters_schema,
                },
            }
            for tool in self._tools.values()
        ]

    def execute(self, name: str, kwargs: dict[str, Any]) -> Any:
        """Execute a tool by name with keyword arguments."""
        tool = self.get_tool(name)
        if tool is None:
            raise KeyError(f"Agent tool {name!r} is not registered")
        logger.info("Executing agent tool: %s(args=%s)", name, list(kwargs.keys()))
        return tool.fn(**kwargs)


__all__ = ["AgentTool", "DubbingAgentToolRegistry"]
