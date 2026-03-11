"""CLI for the pipeline tree agent.

Usage:
    python -m pipeline.tree_cli              # pretty terminal output
    python -m pipeline.tree_cli --json       # JSON to stdout
    python -m pipeline.tree_cli --json -o f  # JSON to file
    python -m pipeline.tree_cli --force      # force rebuild
    python -m pipeline.tree_cli --watch      # rebuild on source changes
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import List

from pipeline.tree_builder import build_pipeline_tree, has_changed
from pipeline.tree_schema import PipelineNode, PipelineTree


# ── Terminal renderer ────────────────────────────────────────────────────────


def render_tree(tree: PipelineTree) -> str:
    lines: List[str] = []
    lines.append("")
    lines.append("  ORBITAL MODELING PIPELINE TREE")
    lines.append("  " + "=" * 56)
    lines.append(f"  Entry: {tree.entry_point}")
    lines.append(f"  Built: {tree.version}")
    lines.append(f"  Hash:  {tree.source_hash[:16]}...")
    lines.append("")

    for i, step in enumerate(tree.steps):
        is_last = i == len(tree.steps) - 1
        _render_node(lines, step, prefix="  ", is_last=is_last)

    if tree.forecast_steps:
        lines.append("")
        lines.append("  FORECAST PIPELINE (separate entry point)")
        lines.append("  " + "=" * 56)
        lines.append("  Entry: routers/models.py :: forecast()")
        lines.append("")
        for i, step in enumerate(tree.forecast_steps):
            is_last = i == len(tree.forecast_steps) - 1
            _render_node(lines, step, prefix="  ", is_last=is_last)

    lines.append("")
    return "\n".join(lines)


def _render_node(
    lines: List[str],
    node: PipelineNode,
    prefix: str,
    is_last: bool,
) -> None:
    connector = "\u2514\u2500\u2500 " if is_last else "\u251c\u2500\u2500 "
    child_prefix = prefix + ("    " if is_last else "\u2502   ")

    # Step header
    lines.append(f"{prefix}{connector}{node.step_number}. {node.name}")

    # File location
    loc = f"{node.module_path} :: {node.function_name}()"
    if node.line_number is not None:
        loc += f" [L{node.line_number}]"
    lines.append(f"{child_prefix}\u251c\u2500\u2500 File: {loc}")

    # Inputs
    lines.append(f"{child_prefix}\u251c\u2500\u2500 Inputs: {', '.join(node.inputs)}")

    # Outputs
    lines.append(f"{child_prefix}\u251c\u2500\u2500 Outputs: {', '.join(node.outputs)}")

    # Description
    lines.append(f"{child_prefix}\u251c\u2500\u2500 Description: {node.description}")

    # Parameters
    if node.parameters:
        params = _format_params(node.parameters)
        lines.append(f"{child_prefix}\u251c\u2500\u2500 Parameters: {params}")

    # Branch condition
    if node.branch_condition:
        lines.append(f"{child_prefix}\u251c\u2500\u2500 BRANCH: {node.branch_condition}")

    # Sub-steps
    if node.children:
        lines.append(f"{child_prefix}\u2514\u2500\u2500 Sub-steps:")
        for j, child in enumerate(node.children):
            child_is_last = j == len(node.children) - 1
            _render_node(lines, child, child_prefix + "    ", child_is_last)
    else:
        # Replace last ├ with └ for the final attribute line
        if lines:
            last = lines[-1]
            lines[-1] = last.replace("\u251c\u2500\u2500", "\u2514\u2500\u2500", 1) if last.count("\u251c\u2500\u2500") == 1 else last

    lines.append(f"{child_prefix}")


def _format_params(params: dict) -> str:
    parts = []
    for k, v in params.items():
        if isinstance(v, list):
            parts.append(f"{k}=[{', '.join(str(x) for x in v)}]")
        else:
            parts.append(f"{k}={v}")
    return ", ".join(parts)


# ── CLI ──────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Orbital pipeline tree agent")
    parser.add_argument("--json", action="store_true", help="output JSON")
    parser.add_argument("-o", "--output", help="write JSON to file")
    parser.add_argument("--force", action="store_true", help="force rebuild")
    parser.add_argument("--watch", action="store_true", help="watch for changes and rebuild")
    args = parser.parse_args()

    if args.watch:
        print("Watching for pipeline changes (Ctrl+C to stop)...")
        tree = build_pipeline_tree(force_rebuild=True)
        print(render_tree(tree))
        try:
            while True:
                time.sleep(2)
                if has_changed():
                    print("\n--- Source changed, rebuilding ---\n")
                    tree = build_pipeline_tree(force_rebuild=True)
                    print(render_tree(tree))
        except KeyboardInterrupt:
            print("\nStopped.")
        return

    tree = build_pipeline_tree(force_rebuild=args.force)

    if args.json or args.output:
        json_str = tree.to_json()
        if args.output:
            with open(args.output, "w") as f:
                f.write(json_str)
            print(f"Tree written to {args.output}")
        else:
            print(json_str)
    else:
        print(render_tree(tree))


if __name__ == "__main__":
    main()
