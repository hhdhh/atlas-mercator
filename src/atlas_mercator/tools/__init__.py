"""Tool layer — Pydantic-typed wrappers around ERP/CRM-style actions.

Every tool here is a thin function with a strict schema. Agents consume them
through LangChain's ``@tool`` decorator or call them directly with
type-checked args.
"""

from atlas_mercator.tools.base import BaseTool, ToolRegistry, tool

__all__ = ["BaseTool", "ToolRegistry", "tool"]
