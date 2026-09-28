#!/usr/bin/env python3
"""Build a deterministic source manifest for inbox and accepted files."""

from __future__ import annotations

import argparse
import hashlib
from datetime import datetime, timezone
from pathlib import Path

import yaml


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect(project: Path) -> list[dict]:
    records: list[dict] = []
    for status, folder in (("pending", "raw/inbox"), ("accepted", "raw/accepted")):
        base = project / folder
        if not base.exists():
            continue
        for path in sorted(p for p in base.rglob("*") if p.is_file()):
            if path.name == "PUT_RAW_FILES_HERE.md":
                continue
            stat = path.stat()
            records.append(
                {
                    "path": path.relative_to(project).as_posix(),
                    "status": status,
                    "sha256": sha256(path),
                    "bytes": stat.st_size,
                    "modified_at": datetime.fromtimestamp(
                        stat.st_mtime, tz=timezone.utc
                    ).isoformat(timespec="seconds"),
                }
            )
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", nargs="?", default=".")
    parser.add_argument(
        "--output", default="registry/source_manifest.yaml", help="Project-relative path"
    )
    args = parser.parse_args()

    project = Path(args.project).resolve()
    output = project / args.output
    records = collect(project)
    by_hash: dict[str, list[str]] = {}
    for item in records:
        by_hash.setdefault(item["sha256"], []).append(item["path"])
    duplicates = [paths for paths in by_hash.values() if len(paths) > 1]

    document = {
        "version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_count": len(records),
        "duplicate_groups": duplicates,
        "sources": records,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    accepted = sum(item["status"] == "accepted" for item in records)
    pending = sum(item["status"] == "pending" for item in records)
    print(f"sources={len(records)} accepted={accepted} pending={pending}")
    print(f"duplicate_groups={len(duplicates)} output={output}")
    return 1 if duplicates else 0


if __name__ == "__main__":
    raise SystemExit(main())
