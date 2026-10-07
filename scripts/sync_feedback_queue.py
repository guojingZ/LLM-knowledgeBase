#!/usr/bin/env python3
"""Synchronize application feedback into a review queue without editing the model."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import yaml

from kb_trace import atomic_write, safe_path
from kb_evidence import digest


TARGET_BY_ISSUE = {
    "wrong_scenario": "scenario_mapping",
    "missing_knowledge": "model_content",
    "wrong_source": "evidence_link",
    "unsupported_claim": "answer_policy",
    "incomplete_answer": "prompt_or_model",
    "out_of_scope_error": "boundary_policy",
    "other": "manual_triage",
}


def load(path: Path) -> dict:
    if not path.exists():
        return {}
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def sync_feedback_queue(project):
    project = Path(project).resolve()
    queue_path = safe_path(project, 'registry/application_feedback_queue.yaml')
    existing = load(queue_path)
    existing_by_id = {item["feedback_id"]: item for item in existing.get("items") or []}
    items = []

    for path in sorted((project / "runs/evaluation").glob("*/feedback.yaml")):
        path = safe_path(project, str(path.relative_to(project)))
        feedback = load(path)
        feedback_id = feedback.get("feedback_id")
        if not feedback_id:
            continue
        previous = existing_by_id.get(feedback_id, {})
        source_revision = digest(path.read_bytes())
        if previous.get('source_revision') and previous['source_revision'] != source_revision:
            previous = {}
        issues = feedback.get("issues") or ["other"]
        items.append(
            {
                "feedback_id": feedback_id,
                "trace_id": feedback.get("trace_id"),
                "question": feedback.get("question"),
                "rating": feedback.get("rating"),
                "issues": issues,
                "review_targets": sorted({TARGET_BY_ISSUE.get(issue, "manual_triage") for issue in issues}),
                "observed_scenario": feedback.get("observed_scenario"),
                "expected_scenario": feedback.get("expected_scenario"),
                "expected_sources": feedback.get("expected_sources") or [],
                "notes": feedback.get("notes", ""),
                "source_feedback": path.relative_to(project).as_posix(),
                "source_revision": source_revision,
                "scenario_verdict": feedback.get("scenario_verdict", "uncertain"),
                "evidence_verdict": feedback.get("evidence_verdict", "uncertain"),
                "review_status": previous.get("review_status", "pending"),
                "reviewer_note": previous.get("reviewer_note", ""),
                "model_updated": previous.get("model_updated", False),
            }
        )

    document = {
        "version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "items": items,
    }
    if existing.get('items') != items or not queue_path.exists():
        atomic_write(queue_path, yaml.safe_dump(document, allow_unicode=True, sort_keys=False).encode('utf-8'))
    return {'items': len(items), 'output': str(queue_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", nargs="?", default=".")
    args = parser.parse_args()
    print(sync_feedback_queue(args.project))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
