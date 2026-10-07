#!/usr/bin/env python3
"""CLI for explicit model paths with saved retrieval traces."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'gui/backend'))
from studio import Studio, StudioError


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project',default=str(ROOT))
    p.add_argument('--question',default='')
    p.add_argument('--start-ref')
    p.add_argument('--target-ref')
    p.add_argument('--max-depth',type=int,default=3)
    p.add_argument('--max-paths',type=int,default=6)
    p.add_argument('--direction',choices=['both','outgoing','incoming'],default='both')
    p.add_argument('--no-save', action='store_true')
    a=p.parse_args()
    try:
        payload={'query':a.question,'start_ref':a.start_ref,'target_ref':a.target_ref,
                 'max_depth':a.max_depth,'max_paths':a.max_paths,'direction':a.direction}
        service=Studio(a.project)
        result=service.multihop(payload) if a.no_save else service.query_paths(payload, 'cli')
    except StudioError as exc:
        print(json.dumps({'error':str(exc)},ensure_ascii=False)); return 1
    print(json.dumps(result,ensure_ascii=False,indent=2)); return 0


if __name__=='__main__': raise SystemExit(main())
