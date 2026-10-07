#!/usr/bin/env python3
"""Record human feedback for one saved application trace."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import yaml

from kb_trace import read_trace, trace_dir, safe_path, atomic_write
from kb_evidence import digest


ISSUES = {
    "wrong_scenario",
    "missing_knowledge",
    "wrong_source",
    "unsupported_claim",
    "incomplete_answer",
    "out_of_scope_error",
    "other",
}


def record_feedback(project, payload):
    project = Path(project).resolve()
    trace_id = payload.get('trace_id')
    trace = read_trace(project, trace_id)
    if payload.get('revision') is not None and payload['revision'] != trace['feedback_revision']:
        raise ValueError('评价版本已变化，请刷新运行记录')
    rating = payload.get('rating')
    issues = payload.get('issues', [])
    notes = payload.get('notes', '')
    expected = payload.get('expected_scenario') or None
    sources = payload.get('expected_sources', [])
    scenario_verdict = payload.get('scenario_verdict', 'uncertain')
    evidence_verdict = payload.get('evidence_verdict', 'uncertain')
    if rating not in {'helpful', 'partial', 'not_helpful'}:
        raise ValueError('请选择结果是否有用')
    if not isinstance(issues, list) or any(not isinstance(x, str) or x not in ISSUES for x in issues):
        raise ValueError('问题类型无效')
    if not isinstance(notes, str) or len(notes) > 4000:
        raise ValueError('反馈说明最多 4000 字符')
    if scenario_verdict not in {'correct', 'incorrect', 'uncertain', 'not_applicable'}:
        raise ValueError('场景评价无效')
    if evidence_verdict not in {'sufficient', 'partial', 'insufficient', 'uncertain'}:
        raise ValueError('证据评价无效')
    if expected is not None:
        scenarios = yaml.safe_load((project / 'model/scenarios.yaml').read_text(encoding='utf-8')).get('scenarios', [])
        if not isinstance(expected, str) or expected not in {n['id'] for n in scenarios}:
            raise ValueError('预期场景不存在')
    if not isinstance(sources, list) or any(not isinstance(x, str) or len(x) > 500 for x in sources):
        raise ValueError('预期来源必须是文本列表')
    context = trace['context']
    values = {'rating': rating, 'issues': sorted(set(issues)), 'notes': notes,
              'expected_scenario': expected, 'expected_sources': sources,
              'scenario_verdict': scenario_verdict, 'evidence_verdict': evidence_verdict}
    current = trace['feedback']
    if current and all(current.get(key) == value for key, value in values.items()):
        return {'status': 'unchanged', 'feedback': current, 'revision': trace['feedback_revision']}
    feedback = {'feedback_id': f'feedback://{trace_id}', 'trace_id': trace_id,
                'recorded_at': datetime.now(timezone.utc).isoformat(timespec='microseconds'),
                'question': context.get('question', context.get('query')),
                'observed_scenario': (context.get('selected_scenario') or {}).get('id'),
                **values, 'review_status': 'pending', 'model_updated': False}
    path = safe_path(project, str((trace_dir(project, trace_id) / 'feedback.yaml').relative_to(project)))
    data = yaml.safe_dump(feedback, allow_unicode=True, sort_keys=False).encode('utf-8')
    atomic_write(path, data)
    return {'status': 'recorded', 'feedback': feedback, 'revision': digest(data)}


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
    record_feedback(project, {'trace_id': args.trace_id, 'rating': args.rating, 'issues': args.issue,
                             'notes': args.notes, 'expected_scenario': args.expected_scenario,
                             'expected_sources': args.expected_source})
    print(trace_dir(project, args.trace_id) / 'feedback.yaml')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
