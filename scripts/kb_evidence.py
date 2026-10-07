"""Shared paragraph identity and field-scoped human review for GUI and retrieval."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import yaml


def digest(data):
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode('utf-8')).hexdigest()


def source_path(project, source):
    root = Path(project).resolve()
    if not isinstance(source, str) or not source.startswith('raw/accepted/'):
        raise ValueError('来源必须位于 raw/accepted/')
    if '..' in Path(source).parts or '\\' in source:
        raise ValueError('不允许路径穿越')
    path = (root / source).resolve()
    allowed = (root / 'raw/accepted').resolve()
    if not allowed.is_relative_to(root) or not path.is_relative_to(allowed) or not path.is_file():
        raise ValueError('来源不存在或越过允许目录')
    if path.suffix.lower() not in {'.md', '.txt'}:
        raise ValueError('仅支持 Markdown / 文本来源')
    return path


def source_index(project, source, cache=None):
    data = source_path(project, source).read_bytes()
    sha = digest(data)
    if cache is not None and source in cache and cache[source]['sha256'] == sha:
        return cache[source]
    lines = data.decode('utf-8-sig').splitlines()
    paragraphs, headings, block, begin, fence = [], [], [], 1, False
    occurrences = {}

    def emit(end):
        if not block:
            return
        text = '\n'.join(block)
        key = digest(text)
        occurrences[key] = occurrences.get(key, 0) + 1
        evidence_id = 'ev_' + digest(source + '\n' + key + '\n' + str(occurrences[key]))[:24]
        paragraphs.append({'evidence_id': evidence_id, 'source': source, 'source_sha256': sha,
                           'line_start': begin, 'line_end': end, 'section': ' / '.join(x[1] for x in headings),
                           'text': text})
    for i, line in enumerate(lines, 1):
        is_fence = bool(re.match(r'^\s*(' + chr(96) * 3 + r'|~~~)', line))
        if not fence:
            heading = re.match(r'^(#{1,6})\s+(.+)', line)
            if heading:
                emit(i - 1); block = []
                level = len(heading[1])
                headings[:] = [h for h in headings if h[0] < level]
                headings.append((level, heading[2].strip()))
            if not line.strip():
                emit(i - 1); block = []; continue
        if not block:
            begin = i
        block.append(line)
        if is_fence:
            fence = not fence
    emit(len(lines))
    result = {'path': source, 'sha256': sha, 'text': '\n'.join(lines),
              'line_count': len(lines), 'paragraphs': paragraphs}
    if cache is not None:
        cache[source] = result
    return result


def support_value(node, field):
    if field == 'node':
        return node
    if not isinstance(field, str) or not re.fullmatch(r'[a-z_][a-z_0-9]*(?:\[\d+\])?(?:\.[a-z_][a-z_0-9]*(?:\[\d+\])?)*', field):
        raise ValueError('支持字段格式无效')
    if field.split('.')[0].split('[')[0] not in {'define', 'ipo', 'composition', 'relations', 'decomposition', 'goal', 'trigger'}:
        raise ValueError('请选择定义、规则或明确关系等支持字段')
    value = node
    try:
        for key, number in re.findall(r'([a-z_][a-z_0-9]*)|\[(\d+)\]', field):
            value = value[key] if key else value[int(number)]
    except (KeyError, IndexError, TypeError):
        raise ValueError('支持字段已不存在，请重新选择')
    return value


def support_digest(node, field):
    return digest(json.dumps(support_value(node, field), ensure_ascii=False, sort_keys=True, separators=(',', ':')))


def read_bindings(project):
    path = Path(project) / 'registry/gui_evidence.yaml'
    if not path.exists():
        return {'version': '2.0', 'bindings': {}}, digest(b'')
    data = path.read_bytes()
    result = yaml.safe_load(data)
    if not isinstance(result, dict) or not isinstance(result.get('bindings'), dict):
        raise ValueError('人工证据登记结构无效，请检查 gui_evidence.yaml')
    return result, digest(data)


def resolve_bindings(ref, node, paragraphs, document):
    result = []
    for binding in document['bindings'].get(ref, []):
        current = paragraphs.get(binding.get('evidence_id'))
        item = binding | (current or {})
        item['recorded_source_sha256'] = binding.get('source_sha256')
        item['can_reconfirm'] = bool(current)
        field = binding.get('support_field')
        if not current or current['source'] not in node.get('sources', []):
            status, reason = 'stale', '段落已变化、移除或不再属于节点来源，需重新选择证据'
        elif current['source_sha256'] != binding.get('source_sha256'):
            status, reason = 'stale', '来源内容变化，需重新审查'
        elif not field or not binding.get('node_sha256'):
            status, reason = 'needs_review', '旧确认未记录支持字段及其版本，请补充确认'
        else:
            try:
                matches = support_digest(node, field) == binding['node_sha256']
            except ValueError:
                matches = False
            status, reason = ('confirmed', '') if matches else ('stale', '支持字段内容变化或移除，需重新审查')
        result.append(item | {'status': status, 'reason': reason})
    return result
