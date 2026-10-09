#!/usr/bin/env python3
"""Create a deterministic project zip with an internal SHA-256 manifest."""

from __future__ import annotations

import argparse
import hashlib
import zipfile
from pathlib import Path


EXCLUDED_PARTS = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".venv", "node_modules"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".zip", ".bak"}
ZIP_TIMESTAMP = (2026, 10, 8, 0, 0, 0)


def package_files(project: Path) -> list[Path]:
    return [
        path
        for path in sorted(project.rglob("*"))
        if path.is_file()
        and path.name not in {"PACKAGE-MANIFEST.sha256", ".knowledge-write.lock"}
        and not set(path.relative_to(project).parts) & EXCLUDED_PARTS
        and path.suffix.lower() not in EXCLUDED_SUFFIXES
    ]


def zip_info(name: str, executable: bool = False) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, ZIP_TIMESTAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = ((0o755 if executable else 0o644) & 0xFFFF) << 16
    return info


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", nargs="?", default=".")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    project = Path(args.project).resolve()
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    files = package_files(project)
    prefix = project.name
    manifest_lines: list[str] = []

    with zipfile.ZipFile(output, "w") as archive:
        for path in files:
            relative = path.relative_to(project).as_posix()
            data = path.read_bytes()
            manifest_lines.append(f"{hashlib.sha256(data).hexdigest()}  {relative}")
            executable = (relative.startswith("scripts/") and path.suffix == ".py") or path.suffix == ".sh"
            archive.writestr(zip_info(f"{prefix}/{relative}", executable), data)
        manifest = ("\n".join(manifest_lines) + "\n").encode("utf-8")
        archive.writestr(zip_info(f"{prefix}/PACKAGE-MANIFEST.sha256"), manifest)

    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    print(f"files={len(files)}")
    print(f"sha256={digest}")
    print(f"output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
