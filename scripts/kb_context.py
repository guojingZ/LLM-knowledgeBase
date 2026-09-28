#!/usr/bin/env python3
"""Build a traceable knowledge context for a question without calling an LLM."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from kb_lib import retrieve_context


def make_trace_id(question: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = hashlib.sha256(question.encode("utf-8")).hexdigest()[:8]
    return f"qa-{timestamp}-{suffix}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=".")
    parser.add_argument("--question", required=True)
    parser.add_argument("--mode", choices=("model-guided", "raw"), default="model-guided")
    parser.add_argument("--scenario")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--evidence-k", type=int, default=8)
    parser.add_argument("--trace-id")
    parser.add_argument("--no-save", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    project = Path(args.project).resolve()
    trace_id = args.trace_id or make_trace_id(args.question)
    context = retrieve_context(
        project,
        args.question,
        mode=args.mode,
        scenario_id=args.scenario,
        top_k=args.top_k,
        evidence_k=args.evidence_k,
    )
    context["trace_id"] = trace_id
    context["generated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")

    if not args.no_save:
        run = project / "runs/evaluation" / trace_id
        run.mkdir(parents=True, exist_ok=True)
        (run / "query.json").write_text(
            json.dumps(
                {
                    "trace_id": trace_id,
                    "question": args.question,
                    "mode": args.mode,
                    "scenario": args.scenario,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (run / "context.json").write_text(
            json.dumps(context, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    if args.json:
        print(json.dumps(context, ensure_ascii=False, indent=2))
    else:
        print(f"trace_id: {trace_id}")
        print(context["context_text"])
    # needs_clarification and no_evidence are valid business outcomes.  Keep the
    # process successful so desktop Agents can always consume the JSON payload;
    # reserve non-zero exits for actual execution errors.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
