"""Shared, collision-safe retrieval traces. Saved contexts are historical snapshots."""
from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

import yaml

from kb_evidence import digest, source_path

VERSION = '1.5.0'


def make_trace_id(question=''):
    return 'qa-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '-' + uuid.uuid4().hex[:12]


def safe_path(project, relative):
    root = Path(project).resolve()
    path = root / relative
    if not path.resolve().is_relative_to(root):
        raise ValueError('记录路径越过项目目录')
    return path


def trace_dir(project, trace_id):
    if not isinstance(trace_id, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,127}', trace_id):
        raise ValueError('无效 trace_id')
    return safe_path(project, 'runs/evaluation/' + trace_id)


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.kb-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def revisions(project):
    paths = ['model/scenarios.yaml', 'model/concepts.yaml', 'model/entities.yaml',
             'registry/source_manifest.yaml', 'registry/gui_evidence.yaml',
             'scripts/kb_lib.py', 'scripts/kb_evidence.py', 'scripts/kb_trace.py', 'gui/backend/studio.py']
    result = {name: digest((Path(project) / name).read_bytes()) for name in paths if (Path(project) / name).is_file()}
    manifest_path = Path(project) / 'registry/source_manifest.yaml'
    manifest = yaml.safe_load(manifest_path.read_bytes()) if manifest_path.exists() else {}
    for item in (manifest or {}).get('sources', []):
        if item.get('status') != 'accepted':
            continue
        name = item['path']
        try:
            result[name] = digest(source_path(project, name).read_bytes())
        except (ValueError, OSError):
            result[name] = 'unavailable'
    return result


def save_trace(project, context, parameters, entrypoint, elapsed_ms, before, trace_id=None):
    trace_id = trace_id or make_trace_id()
    run = trace_dir(project, trace_id)
    run.parent.mkdir(parents=True, exist_ok=True)
    run.mkdir()  # Never overwrite a prior run, including a user-supplied ID.
    generated = datetime.now(timezone.utc).isoformat(timespec='milliseconds')
    result = context | {'trace_id': trace_id, 'generated_at': generated}
    after = revisions(project)
    metadata = {'trace_schema': '1.0', 'app_version': VERSION, 'entrypoint': entrypoint,
                'query_kind': result.get('query_kind', 'one_hop'), 'elapsed_ms': round(elapsed_ms, 2),
                'elapsed_scope': 'retrieval_and_preview_excluding_persistence_transport',
                'revisions_before': before, 'revisions_after': after,
                'version_consistency': 'stable' if before == after else 'changed_during_query',
                'replay': 'stored_result_snapshot', 'answer_generated': False}
    try:
        for filename, value in [('query.json', {'trace_id': trace_id, **parameters}),
                                ('metadata.json', metadata), ('context.json', result)]:
            atomic_write(run / filename, (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    except Exception:
        shutil.rmtree(run)
        raise
    return result


def review_items(project):
    path = safe_path(project, 'registry/application_feedback_queue.yaml')
    document = yaml.safe_load(path.read_bytes()) if path.exists() else {}
    return {item['feedback_id']: item for item in (document or {}).get('items', [])}


def read_trace(project, trace_id, reviews=None):
    run = trace_dir(project, trace_id)
    context_path = safe_path(project, str((run / 'context.json').relative_to(Path(project).resolve())))
    if not context_path.is_file():
        raise FileNotFoundError('运行记录不存在')
    def read_json(name):
        path = safe_path(project, str((run / name).relative_to(Path(project).resolve())))
        return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
    feedback_path = safe_path(project, str((run / 'feedback.yaml').relative_to(Path(project).resolve())))
    data = feedback_path.read_bytes() if feedback_path.exists() else b''
    result = {'trace_id': trace_id, 'query': read_json('query.json'), 'context': read_json('context.json'),
              'metadata': read_json('metadata.json'), 'feedback': yaml.safe_load(data) or {},
              'feedback_revision': digest(data)}
    if any(not isinstance(result[key], dict) for key in ('query', 'context', 'metadata', 'feedback')):
        raise ValueError('运行记录结构无效')
    feedback = result['feedback']
    review = (review_items(project) if reviews is None else reviews).get(feedback.get('feedback_id'), {})
    if review.get('source_revision') and review['source_revision'] != result['feedback_revision']:
        review = {}
    result['review'] = {key: review.get(key, feedback.get(key)) for key in ('review_status', 'reviewer_note', 'model_updated')}
    return result


def list_traces(project):
    base = safe_path(project, 'runs/evaluation')
    rows, skipped = [], []
    if not base.exists():
        return {'items': rows, 'skipped': skipped}
    reviews = review_items(project)
    for directory in base.iterdir():
        if not directory.is_dir() or directory.name.startswith('.') or not (directory / 'context.json').exists():
            continue
        try:
            record = read_trace(project, directory.name, reviews)
            context, metadata, feedback = record['context'], record['metadata'], record['feedback']
            refs = set(item['ref'] for item in context.get('knowledge_items', []) if item.get('ref'))
            if context.get('selected_scenario'):
                refs.add('scenario://' + context['selected_scenario']['id'])
            for path in context.get('paths', []):
                refs.update(path.get('refs', []))
            rows.append({'trace_id': directory.name, 'question': context.get('question', context.get('query', '')),
                         'generated_at': context.get('generated_at', ''), 'mode': context.get('mode', record['query'].get('mode', '')),
                         'query_kind': metadata.get('query_kind', 'legacy'), 'entrypoint': metadata.get('entrypoint', 'legacy'),
                         'status': context.get('status', ''), 'elapsed_ms': metadata.get('elapsed_ms'),
                         'rating': feedback.get('rating'), 'review_status': record['review'].get('review_status'),
                         'used_refs': sorted(refs), 'has_metadata': bool(metadata)})
        except (ValueError, KeyError, TypeError, AttributeError, OSError, yaml.YAMLError):
            skipped.append(directory.name)
    rows.sort(key=lambda row: (row['generated_at'], row['trace_id']), reverse=True)
    return {'items': rows, 'skipped': skipped}
