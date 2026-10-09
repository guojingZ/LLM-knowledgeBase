#!/usr/bin/env python3
"""Print the current project status from authoritative files."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import yaml


def load(path: Path) -> dict:
    if not path.exists():
        return {}
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", nargs="?", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'gui/backend'))
    from studio import Studio
    from kb_build import KnowledgeBuild
    build = KnowledgeBuild(Studio(project))
    rows = build.execute('sources.list')['items']
    status = {
        "version": (project / "VERSION").read_text(encoding="utf-8").strip(),
        "accepted_sources": sum(r["admission"] == "accepted" and not r["missing"] for r in rows),
        "pending_sources": sum(r["admission"] == "pending" for r in rows),
        "knowledge_processing": dict(Counter(r["processing"] for r in rows)),
        "construction_jobs": len(build.execute("jobs.list")["items"]),
        "unfinished_writes": sum(p["status"] in {"prepared", "recovery_required"} for p in build.publications()),
        "scenarios": len(load(project / "model/scenarios.yaml").get("scenarios") or []),
        "concepts": len(load(project / "model/concepts.yaml").get("concepts") or []),
        "entities": len(load(project / "model/entities.yaml").get("entities") or []),
        "seed_questions": len(load(project / "eval/questions.yaml").get("questions") or []),
        "question_set_status": load(project / "eval/questions.yaml").get("status"),
        "saved_application_traces": len(list((project / "runs/evaluation").glob("qa-*/context.json"))),
        "feedback_queue": len(load(project / "registry/application_feedback_queue.yaml").get("items") or []),
    }
    if args.json:
        print(json.dumps(status, ensure_ascii=False, indent=2))
    else:
        for key, value in status.items():
            print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
