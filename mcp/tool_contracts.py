"""
Tool contracts: a small, explicit schema for agent tool definitions.

Why this exists:
- Reliability in 2026 agent systems is mostly about structure: strict inputs/outputs,
  schema validation, and predictable tool behavior.
- This module defines a minimal "contract" shape that tools can publish (and the
  orchestrator can lint) without pulling in heavy framework dependencies.
"""

from __future__ import annotations

from typing import Any, Dict, NotRequired, TypedDict


class JsonSchema(TypedDict, total=False):
    # Minimal JSON-Schema-ish structure used in this repo. Not a full spec.
    type: str
    properties: Dict[str, Any]
    required: list[str]
    additionalProperties: bool


class ToolContract(TypedDict):
    name: str
    description: str
    input_schema: JsonSchema
    output_schema: NotRequired[JsonSchema]
    version: NotRequired[str]


pip_install_contract: ToolContract = {
    "name": "pip_install",
    "description": "Installs a Python package using pip.",
    "input_schema": {
        "type": "object",
        "properties": {"package_name": {"type": "string", "description": "The name of the Python package to install."}},
        "required": ["package_name"],
        "additionalProperties": False,
    },
}

shell_contract: ToolContract = {
    "name": "shell",
    "description": "Executes a shell command.",
    "input_schema": {"type": "object", "properties": {"command": {"type": "string", "description": "The shell command to execute."}}, "required": ["command"], "additionalProperties": False},
}
