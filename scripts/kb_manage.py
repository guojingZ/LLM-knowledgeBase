#!/usr/bin/env python3
"""Discover and invoke knowledge-building operations using JSON files or stdin."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'gui/backend'))
from studio import Studio, StudioError
from kb_build import KnowledgeBuild, BuildError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', help='tools lists operations and required parameters')
    parser.add_argument('--project', default=str(ROOT))
    parser.add_argument('--input', help='JSON parameter file; - reads stdin')
    args = parser.parse_args()
    try:
        payload = json.loads(sys.stdin.read() if args.input == '-' else Path(args.input).read_text(encoding='utf-8-sig')) if args.input else {}
        result = KnowledgeBuild(Studio(args.project)).execute(args.operation, payload)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (BuildError, StudioError, ValueError, TypeError, KeyError, OSError) as exc:
        print(json.dumps({'error': str(exc), 'status': getattr(exc, 'status', 422)}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
