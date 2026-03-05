"""Data model for the pipeline tree."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PipelineNode:
    """Single node in the pipeline tree."""

    step_id: str
    step_number: str
    name: str
    description: str
    module_path: str
    function_name: str
    inputs: List[str]
    outputs: List[str]
    parameters: Dict[str, Any] = field(default_factory=dict)
    children: List[PipelineNode] = field(default_factory=list)
    branch_condition: Optional[str] = None
    function_signature: Optional[str] = None
    line_number: Optional[int] = None
    docstring: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "step_id": self.step_id,
            "step_number": self.step_number,
            "name": self.name,
            "description": self.description,
            "module_path": self.module_path,
            "function_name": self.function_name,
            "inputs": self.inputs,
            "outputs": self.outputs,
        }
        if self.parameters:
            d["parameters"] = self.parameters
        if self.children:
            d["children"] = [c.to_dict() for c in self.children]
        if self.branch_condition:
            d["branch_condition"] = self.branch_condition
        if self.function_signature:
            d["function_signature"] = self.function_signature
        if self.line_number is not None:
            d["line_number"] = self.line_number
        if self.docstring:
            d["docstring"] = self.docstring
        return d


@dataclass
class PipelineTree:
    """Root container for the full pipeline tree."""

    version: str
    source_hash: str
    pipeline_name: str
    entry_point: str
    steps: List[PipelineNode] = field(default_factory=list)
    forecast_steps: List[PipelineNode] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "source_hash": self.source_hash,
            "pipeline_name": self.pipeline_name,
            "entry_point": self.entry_point,
            "steps": [s.to_dict() for s in self.steps],
            "forecast_steps": [s.to_dict() for s in self.forecast_steps],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)
