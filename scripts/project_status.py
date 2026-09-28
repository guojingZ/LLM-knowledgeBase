#!/usr/bin/env python3
"""Print the current project status from authoritative files."""

from __future__ import annotations

import argparse
import json
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
    status = {
        "version": (project / "VERSION").read_text(encoding="utf-8").strip(),
        "accepted_sources": len(list((project / "raw/accepted").glob("*.md"))),
        "pending_sources": len([p for p in (project / "raw/inbox").glob("*") if p.is_file() and p.name != "PUT_RAW_FILES_HERE.md"]),
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
