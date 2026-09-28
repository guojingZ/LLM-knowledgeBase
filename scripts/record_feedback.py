#!/usr/bin/env python3
"""Record human feedback for one saved application trace."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import yaml


ISSUES = {
    "wrong_scenario",
    "missing_knowledge",
    "wrong_source",
    "unsupported_claim",
    "incomplete_answer",
    "out_of_scope_error",
    "other",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", nargs="?", default=".")
    parser.add_argument("--trace-id", required=True)
    parser.add_argument("--rating", choices=("helpful", "partial", "not_helpful"), required=True)
    parser.add_argument("--issue", action="append", default=[])
    parser.add_argument("--notes", default="")
    parser.add_argument("--expected-scenario")
    parser.add_argument("--expected-source", action="append", default=[])
    args = parser.parse_args()

    unknown = sorted(set(args.issue) - ISSUES)
    if unknown:
        raise SystemExit(f"Unknown issue types: {unknown}; allowed: {sorted(ISSUES)}")

    project = Path(args.project).resolve()
    run = project / "runs/evaluation" / args.trace_id
    context_path = run / "context.json"
    if not context_path.exists():
        raise SystemExit(f"Trace does not exist: {context_path}")
    context = json.loads(context_path.read_text(encoding="utf-8"))
    feedback = {
        "feedback_id": f"feedback://{args.trace_id}",
        "trace_id": args.trace_id,
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "question": context.get("question"),
        "observed_scenario": (context.get("selected_scenario") or {}).get("id"),
        "rating": args.rating,
        "issues": args.issue,
        "notes": args.notes,
        "expected_scenario": args.expected_scenario,
        "expected_sources": args.expected_source,
        "review_status": "pending",
        "model_updated": False,
    }
    (run / "feedback.yaml").write_text(
        yaml.safe_dump(feedback, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    print(run / "feedback.yaml")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
