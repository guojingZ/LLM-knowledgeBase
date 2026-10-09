"""Deterministic, file-backed knowledge studio. No model API or graph database."""
from __future__ import annotations

import copy
import difflib
import hashlib
import json
import os
import re
import sys
import tempfile
import threading
import uuid
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from kb_lib import flatten_text, normalize, tokens, weighted_overlap, retrieve_context
from kb_evidence import source_index as index_source, read_bindings, resolve_bindings, support_digest
from kb_trace import VERSION, revisions as trace_revisions, save_trace, read_trace, list_traces
from record_feedback import record_feedback
from sync_feedback_queue import sync_feedback_queue
from kb_write import serialized_write

KINDS = {'scenario': 'scenarios', 'concept': 'concepts', 'entity': 'entities'}
LABELS = {'uses': '使用', 'references': '引用', 'related_to': '相关', 'depends_on': '依赖',
          'produces': '产生', 'contains': '包含', 'is_a': '属于', 'tools': '工具', 'source': '来源'}


def digest(data):
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode('utf-8')).hexdigest()


class StudioError(Exception):
    def __init__(self, message, status=400):
        self.status = status
        super().__init__(message)


def bounded(value, low, high, name):
    try:
        n = int(value)
    except (ValueError, TypeError):
        raise StudioError(f'{name} 必须是整数')
    if not low <= n <= high:
        raise StudioError(f'{name} 必须在 {low}–{high} 之间')
    return n


class Studio:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.lock = threading.RLock()
        self._source_cache = {}

    def model_path(self, kind):
        if kind not in KINDS:
            raise StudioError('未知节点类型')
        return self.root / 'model' / (KINDS[kind] + '.yaml')

    def source_path(self, source):
        if not isinstance(source, str) or not source.startswith('raw/accepted/'):
            raise StudioError('来源必须位于 raw/accepted/')
        if '..' in Path(source).parts or '\\' in source:
            raise StudioError('不允许路径穿越')
        p = (self.root / source).resolve()
        allowed = (self.root / 'raw/accepted').resolve()
        if not allowed.is_relative_to(self.root) or not p.is_relative_to(allowed) or not p.is_file():
            raise StudioError('来源不存在或越过允许目录', 404)
        if p.suffix.lower() not in {'.md', '.txt'}:
            raise StudioError('仅支持 Markdown / 文本来源')
        return p

    def snapshot(self):
        documents, revisions, nodes = {}, {}, {}
        for kind, key in KINDS.items():
            data = self.model_path(kind).read_bytes()
            doc = yaml.safe_load(data)
            if not isinstance(doc, dict) or not isinstance(doc.get(key), list):
                raise StudioError(f'{key}.yaml 顶层结构无效', 422)
            documents[kind], revisions[kind] = doc, digest(data)
            for item in doc[key]:
                if not isinstance(item, dict) or not isinstance(item.get('id'), str):
                    raise StudioError(f'{key}.yaml 节点结构无效', 422)
                ref = f'{kind}://{item["id"]}'
                if ref in nodes:
                    raise StudioError(f'重复节点：{ref}', 422)
                nodes[ref] = {'ref': ref, 'kind': kind, 'id': item['id'], 'data': item}
        manifest_path = self.root / 'registry/source_manifest.yaml'
        manifest = yaml.safe_load(manifest_path.read_text(encoding='utf-8')) or {}
        sources = {x['path']: x for x in manifest.get('sources', []) if x.get('status') == 'accepted'}
        return documents, revisions, nodes, sources

    def find(self, ref, snapshot=None):
        snap = snapshot or self.snapshot()
        if ref not in snap[2]:
            raise StudioError(f'节点不存在：{ref}', 404)
        return snap[2][ref]

    def summary(self, item):
        return {k: item[k] for k in ('ref', 'kind', 'id')} | {'define': item['data'].get('define', '')}

    def edges(self, snap):
        result = []
        for ref, item in snap[2].items():
            node = item['data']
            for relation, targets in (node.get('relations') or {}).items():
                if isinstance(targets, list):
                    for i, target in enumerate(targets):
                        result.append({'source': ref, 'target': target, 'relation': relation,
                                       'field': f'relations.{relation}[{i}]'})
            for i, phase in enumerate(node.get('composition') or []):
                for j, target in enumerate(phase.get('uses') or []):
                    result.append({'source': ref, 'target': target, 'relation': 'uses',
                                   'field': f'composition[{i}].uses[{j}]', 'phase': phase.get('phase', '')})
            for i, part in enumerate(node.get('decomposition') or []):
                if isinstance(part, dict) and part.get('uses'):
                    for j, target in enumerate(part['uses'] if isinstance(part['uses'], list) else [part['uses']]):
                        result.append({'source': ref, 'target': target, 'relation': 'uses',
                                       'field': f'decomposition[{i}].uses[{j}]'})
            for i, target in enumerate((((node.get('ipo') or {}).get('process') or {}).get('tools') or [])):
                result.append({'source': ref, 'target': target, 'relation': 'tools', 'field': f'ipo.process.tools[{i}]'})
        return [e | {'label': LABELS.get(e['relation'], e['relation'])} for e in result]

    def validate_node(self, kind, node, old_id, snap):
        if not isinstance(node, dict) or node.get('id') != old_id:
            raise StudioError('节点必须是对象，且 id 不可修改；重命名需另行迁移引用', 422)
        if not isinstance(node.get('define'), str) or not node['define'].strip():
            raise StudioError('define 必须是非空文本', 422)
        for key in ('sources', 'tags'):
            value = node.get(key, [])
            if not isinstance(value, list) or any(not isinstance(x, str) for x in value):
                raise StudioError(f'{key} 必须是文本列表', 422)
        if not node.get('sources'):
            raise StudioError('sources 不可为空', 422)
        for source in node['sources']:
            if source not in snap[3]:
                raise StudioError(f'来源不在已准入清单中：{source}', 422)
            self.source_path(source)
        relations = node.get('relations') or {}
        if not isinstance(relations, dict):
            raise StudioError('relations 必须是对象', 422)
        for relation, targets in relations.items():
            if relation not in LABELS or relation in {'source', 'tools'}:
                raise StudioError(f'不支持的关系类型：{relation}', 422)
            if not isinstance(targets, list) or any(not isinstance(x, str) for x in targets):
                raise StudioError(f'relations.{relation} 必须是引用列表', 422)
        if kind == 'entity' and not any(relations.values()):
            raise StudioError('实体至少需要一项关系', 422)
        composition = node.get('composition', [])
        if kind == 'scenario' and (not isinstance(composition, list) or not composition):
            raise StudioError('场景 composition 必须是非空列表', 422)
        if not isinstance(composition, list):
            raise StudioError('composition 必须是列表', 422)
        for phase in composition:
            if not isinstance(phase, dict) or not isinstance(phase.get('phase'), str):
                raise StudioError('composition 中每项必须包含 phase 文本', 422)
            if not isinstance(phase.get('uses', []), list):
                raise StudioError('composition.uses 必须是列表', 422)
        ipo = node.get('ipo') or {}
        decomposition = node.get('decomposition') or []
        if kind == 'concept' and not ipo and not decomposition:
            raise StudioError('概念需要 ipo 或 decomposition', 422)
        if not isinstance(ipo, dict) or not isinstance(ipo.get('process', {}), dict):
            raise StudioError('ipo 和 ipo.process 必须是对象', 422)
        for key in ('input', 'output'):
            if key in ipo and not isinstance(ipo[key], list):
                raise StudioError(f'ipo.{key} 必须是列表', 422)
        for key in ('steps', 'tools'):
            if key in ipo.get('process', {}) and not isinstance(ipo['process'][key], list):
                raise StudioError(f'ipo.process.{key} 必须是列表', 422)
        if not isinstance(decomposition, list) or any(not isinstance(x, dict) for x in decomposition):
            raise StudioError('decomposition 必须是对象列表', 422)
        for part in decomposition:
            if part.get('uses') and not isinstance(part['uses'], (str, list)):
                raise StudioError('decomposition.uses 必须是引用或引用列表', 422)
        # Check only explicit reference fields; free prose never becomes a relation.
        staged = (snap[0], snap[1], {f'{kind}://{old_id}': {'data': node}}, snap[3])
        for edge in self.edges(staged):
            target = edge['target']
            if not isinstance(target, str) or target not in snap[2] or not target.startswith(('concept://', 'entity://')):
                raise StudioError(f'断链引用：{edge["field"]} → {target}', 422)
        try:
            yaml.safe_dump(node, allow_unicode=True, sort_keys=False)
        except (TypeError, yaml.YAMLError):
            raise StudioError('节点包含不可序列化值', 422)

    def detail(self, ref):
        snap = self.snapshot()
        item = self.find(ref, snap)
        edges = self.edges(snap)
        return self.summary(item) | {'node': item['data'], 'revision': snap[1][item['kind']],
                                   'outgoing': [e for e in edges if e['source'] == ref],
                                   'incoming': [e for e in edges if e['target'] == ref]}

    def status(self):
        snap = self.snapshot()
        es = self.edges(snap)
        broken = [e for e in es if e['target'] not in snap[2]]
        return {'version': VERSION, 'counts': {kind: len(snap[0][kind][key]) for kind, key in KINDS.items()},
                'sources': len(snap[3]), 'edges': len(es), 'broken_references': len(broken),
                'relations': sorted(set(e['relation'] for e in es)), 'revisions': snap[1],
                'model_authority': 'model/*.yaml', 'write_mode': 'preview + revision + atomic replace'}

    def search(self, query='', kind=None):
        snap = self.snapshot()
        if kind and kind not in KINDS:
            raise StudioError('未知节点类型')
        query_norm = normalize(query)
        return [self.summary(n) for n in snap[2].values() if (not kind or n['kind'] == kind)
                and (not query_norm or query_norm in normalize(flatten_text(n['data'])))]

    def source_index(self, source):
        self.source_path(source)
        return index_source(self.root, source, self._source_cache)

    def bindings(self):
        try:
            return read_bindings(self.root)
        except ValueError as exc:
            raise StudioError(str(exc), 422)

    def evidence(self, ref, query='', limit=8):
        snap = self.snapshot()
        item = self.find(ref, snap)
        limit = bounded(limit, 1, 30, 'limit')
        bindings, revision = self.bindings()
        bound = bindings['bindings'].get(ref, [])
        candidates, source_info, all_paragraphs = [], [], {}
        query_tokens = tokens(query or item['id'])
        expansion = tokens(item['data'].get('define', '') + ' ' + flatten_text(item['data'].get('tags', [])))
        for source in item['data'].get('sources', []):
            if source not in snap[3]:
                source_info.append({'path': source, 'status': 'not_in_manifest'}); continue
            try:
                index = self.source_index(source)
            except StudioError as exc:
                source_info.append({'path': source, 'status': 'missing', 'error': str(exc)}); continue
            source_info.append({'path': source, 'sha256': index['sha256'], 'paragraphs': len(index['paragraphs']),
                                'manifest_hash_matches': index['sha256'] == snap[3][source].get('sha256'), 'status': 'available'})
            for p in index['paragraphs']:
                all_paragraphs[p['evidence_id']] = p
                score = .8 * weighted_overlap(query_tokens, tokens(p['text'])) + .2 * weighted_overlap(expansion, tokens(p['text']))
                if score > 0:
                    candidates.append(p | {'score': round(score, 4), 'status': 'candidate_unconfirmed'})
        candidates.sort(key=lambda p: (-p['score'], p['source'], p['line_start']))
        confirmed = resolve_bindings(ref, item['data'], all_paragraphs, bindings)
        registered = {b['evidence_id'] for b in confirmed}
        candidates = [p for p in candidates if p['evidence_id'] not in registered]
        status = 'confirmed' if any(b['status'] == 'confirmed' for b in confirmed) else ('review_required' if confirmed else 'candidates_only')
        return {'ref': ref, 'sources': source_info, 'candidates': candidates[:limit], 'confirmed': confirmed,
                'binding_revision': revision, 'evidence_status': status}

    def locate(self, evidence_id):
        for source in self.snapshot()[3]:
            try:
                index = self.source_index(source)
            except StudioError:
                continue
            for p in index['paragraphs']:
                if p['evidence_id'] == evidence_id:
                    lines = index['text'].splitlines()
                    begin = max(1, p['line_start'] - 3); end = min(len(lines), p['line_end'] + 3)
                    return p | {'context_start': begin, 'context_end': end, 'context': '\n'.join(lines[begin-1:end])}
        raise StudioError('证据 ID 已失效或不存在，请重新读取来源', 404)

    @serialized_write
    def bind(self, payload):
        with self.lock:
            ref = payload.get('ref')
            snap = self.snapshot()
            item = self.find(ref, snap)
            if payload.get('node_revision') and payload['node_revision'] != snap[1][item['kind']]:
                raise StudioError('节点内容已变化，请刷新后再确认', 409)
            field = payload.get('support_field', 'define')
            note = payload.get('review_note', '')
            if not isinstance(note, str) or len(note) > 1000:
                raise StudioError('确认理由必须是最多 1000 字符的文本')
            try:
                node_sha = support_digest(item['data'], field)
            except ValueError as exc:
                raise StudioError(str(exc), 422)
            p = self.locate(payload.get('evidence_id'))
            if p['source'] not in item['data'].get('sources', []):
                raise StudioError('证据来源未被该节点引用', 422)
            if p['source_sha256'] != payload.get('source_sha256'):
                raise StudioError('原文已变化，请刷新后再确认', 409)
            data, revision = self.bindings()
            if payload.get('revision') != revision:
                raise StudioError('证据登记已变化，请刷新', 409)
            existing = data['bindings'].setdefault(ref, [])
            existing[:] = [b for b in existing if not (b['evidence_id'] == p['evidence_id'] and (not b.get('support_field') or b.get('support_field') == field))]
            existing.append({k: p[k] for k in ('evidence_id', 'source', 'source_sha256', 'line_start', 'line_end')} | {
                'support_field': field, 'node_sha256': node_sha, 'review_note': note,
                'text': p['text'], 'section': p['section'],
                'confirmed_at': datetime.now(timezone.utc).isoformat()})
            data['version'] = '2.0'
            self.atomic_write(self.root / 'registry/gui_evidence.yaml', yaml.safe_dump(data,allow_unicode=True,sort_keys=False).encode())
            return {'status': 'confirmed', 'evidence_id': p['evidence_id']}

    @serialized_write
    def unbind(self, payload):
        with self.lock:
            ref = payload.get('ref'); self.find(ref)
            data, revision = self.bindings()
            if payload.get('revision') != revision:
                raise StudioError('证据登记已变化，请刷新',409)
            current = data['bindings'].get(ref,[])
            field = payload.get('support_field')
            data['bindings'][ref] = [b for b in current if not (b['evidence_id'] == payload.get('evidence_id') and
                                    ('support_field' not in payload or b.get('support_field') == field))]
            if data['bindings'][ref] == current:
                return {'status': 'unchanged'}
            self.atomic_write(self.root/'registry/gui_evidence.yaml',yaml.safe_dump(data,allow_unicode=True,sort_keys=False).encode())
            return {'status':'removed'}

    def graph(self, ref, depth=1, direction='both', kinds=None, relations=None, max_nodes=60):
        snap = self.snapshot(); self.find(ref, snap)
        depth = bounded(depth, 1, 2, 'depth'); max_nodes = bounded(max_nodes, 2, 120, 'max_nodes')
        adjacency = self.adjacency(self.edges(snap), direction, kinds, relations, snap)
        found, queue, truncated = {ref: 0}, deque([ref]), False
        while queue:
            current = queue.popleft()
            if found[current] >= depth:
                continue
            for target, edge, reverse in adjacency.get(current, []):
                if target not in found:
                    if len(found) >= max_nodes:
                        truncated = True; continue
                    found[target] = found[current] + 1; queue.append(target)
        visible_edges = [e for e in self.edges(snap) if e['source'] in found and e['target'] in found
                         and (not relations or e['relation'] in relations)]
        return {'center': ref, 'nodes': [self.summary(snap[2][r]) | {'depth': d} for r, d in found.items()],
                'edges': visible_edges, 'truncated': truncated, 'direction': direction,
                'note': '箭头表示 YAML 中记录的方向；反向浏览不会改变原关系。'}

    def adjacency(self, edges, direction, kinds, relations, snap):
        if direction not in {'both', 'outgoing', 'incoming'}:
            raise StudioError('direction 必须为 both / outgoing / incoming')
        if kinds and any(k not in KINDS for k in kinds):
            raise StudioError('未知节点类型过滤')
        adjacency = {}
        for e in edges:
            if e['target'] not in snap[2] or (relations and e['relation'] not in relations):
                continue
            a, b = e['source'], e['target']
            if direction in {'both','outgoing'} and (not kinds or snap[2][b]['kind'] in kinds):
                adjacency.setdefault(a, []).append((b, e, False))
            if direction in {'both','incoming'} and (not kinds or snap[2][a]['kind'] in kinds):
                adjacency.setdefault(b, []).append((a, e, True))
        for values in adjacency.values():
            values.sort(key=lambda x: (x[0], x[1]['field']))
        return adjacency

    def multihop(self, payload):
        snap = self.snapshot()
        q = payload.get('query', '')
        if not isinstance(q, str) or len(q) > 2000:
            raise StudioError('query 必须是最多 2000 字符的文本')
        start, target = payload.get('start_ref'), payload.get('target_ref')
        depth = bounded(payload.get('max_depth', 3), 1, 4, 'max_depth')
        limit = bounded(payload.get('max_paths', 6), 1, 12, 'max_paths')
        direction = payload.get('direction', 'both')
        ranked = []
        query_tokens = tokens(q)
        for ref, n in snap[2].items():
            text = n['id'] + ' ' + n['data'].get('define','') + ' ' + flatten_text(n['data'].get('tags', []))
            score = weighted_overlap(query_tokens, tokens(text))
            if normalize(n['id']) and normalize(n['id']) in normalize(q): score += .5
            if score >= .16:
                ranked.append(self.summary(n) | {'score': round(min(1, score),4)})
        ranked.sort(key=lambda n:(-n['score'], n['ref']))
        context = None
        if start:
            self.find(start, snap); seeds = [start]
        elif q.strip():
            context = retrieve_context(self.root, q)
            if context['status'] in {'no_evidence','needs_clarification'}:
                return {'query': q, 'status': context['status'], 'paths': [], 'seeds': ranked[:5],
                        'candidate_scenarios': context.get('candidate_scenarios', []),
                        'message': '问题超出当前库或候选接近，请指定起点节点或明确问题。', 'truncated': False}
            scenario = context.get('selected_scenario')
            seeds = ([f'scenario://{scenario["id"]}'] if scenario else [])
            seeds += [n['ref'] for n in ranked[:3] if n['ref'] not in seeds]
            seeds = seeds[:3]
        else:
            raise StudioError('请填写问题或指定 start_ref')
        if target: self.find(target, snap)
        adjacency = self.adjacency(self.edges(snap), direction, payload.get('kinds'), payload.get('relations'), snap)
        results, explored, truncated, visited = [], 0, False, set()
        query_scores = {n['ref']: n['score'] for n in ranked}
        for seed in seeds:
            queue = deque([(seed, [seed], [])]); distances = {seed:0}
            while queue:
                current, refs, steps = queue.popleft()
                if steps and (not target or current == target):
                    signature = tuple(refs)
                    if signature not in visited:
                        visited.add(signature)
                        results.append({'refs': refs, 'steps': steps, 'seed': seed,
                                        'score': round(query_scores.get(current, 0) + .1 * len(steps),4)})
                    if target:
                        break
                if len(steps) >= depth: continue
                for nxt, edge, reverse in adjacency.get(current, []):
                    explored += 1
                    if explored > 3000:
                        truncated = True; queue.clear(); break
                    if nxt in refs: continue
                    next_depth = len(steps) + 1
                    # One shortest route per seed and destination; avoids cycles and hub explosion.
                    if distances.get(nxt, 99) <= next_depth: continue
                    distances[nxt] = next_depth
                    step = edge | {'from': current, 'to': nxt, 'traversal': 'reverse' if reverse else 'forward',
                        'explanation': f'{edge["source"]} 在 {edge["field"]} 记录“{edge["label"]}” → {edge["target"]}；' + ('本步反向浏览该引用。' if reverse else '本步沿记录方向展开。')}
                    queue.append((nxt, refs + [nxt], steps + [step]))
            if truncated: break
        if target:
            results.sort(key=lambda p: (len(p['steps']), p['refs']))
        else:
            results.sort(key=lambda p: (-p['score'], -len(p['steps']), p['refs']))
        selected = results[:limit]
        for p in selected:
            p['nodes'] = [self.summary(snap[2][r]) for r in p['refs']]
            ev = self.evidence(p['refs'][-1], q, 2)
            p['evidence'] = [b for b in ev['confirmed'] if b['status'] == 'confirmed'] + ev['candidates'][:2]
            p['evidence_status'] = ev['evidence_status']
            p['summary'] = ' → '.join(snap[2][r]['id'] for r in p['refs'])
        return {'query':q, 'status':'paths_found' if selected else ('limit_reached' if truncated else 'no_path'), 'paths':selected,
                'seeds':[self.summary(snap[2][r]) for r in seeds], 'explored_edges':explored,
                'truncated':truncated, 'additional_paths_omitted':max(0,len(results)-limit),
                'direction':direction, 'mode':'explicit_reference_traversal',
                'message':('路径说明模型中的关联，不等同于因果推断；段落候选未经人工确认。' if selected else
                           '达到展开上限，尚未找到路径；不能据此断定节点之间无路径。' if truncated else
                           '在指定方向和跳数范围内没有明确引用路径。')}

    def query(self, payload):
        question = payload.get('question', '')
        mode = payload.get('mode', 'model-guided')
        scenario = payload.get('scenario') or None
        if not isinstance(question, str) or not question.strip() or len(question) > 2000:
            raise StudioError('请输入最多 2000 字符的问题')
        if mode not in {'raw', 'model-guided'} or (scenario is not None and not isinstance(scenario, str)):
            raise StudioError('检索模式或场景参数无效')
        top_k = bounded(payload.get('top_k', 3), 1, 10, 'top_k')
        evidence_k = bounded(payload.get('evidence_k', 8), 1, 30, 'evidence_k')
        parameters = {'question': question, 'mode': mode, 'scenario': scenario,
                      'top_k': top_k, 'evidence_k': evidence_k}
        with self.lock:
            before, started = trace_revisions(self.root), time.perf_counter()
            try:
                result = retrieve_context(self.root, question, mode=mode, scenario_id=scenario,
                                          top_k=top_k, evidence_k=evidence_k)
            except ValueError as exc:
                raise StudioError(str(exc))
            snap = self.snapshot()
            selected = result.get('selected_scenario')
            direct_refs = {n['ref'] for n in result.get('knowledge_items', [])}
            all_direct_refs = {ref for phase in (selected or {}).get('phases', []) for ref in phase.get('uses', [])}
            direct_edges = [e for e in self.edges(snap) if selected and
                            e['source'] == 'scenario://' + selected['id'] and e['target'] in direct_refs
                            and e['field'].startswith('composition[')]
            first_by_target = {}
            for edge in direct_edges:
                first_by_target.setdefault(edge['target'], edge)
            suggestions = []
            if result['status'] == 'context_ready' and mode == 'model-guided':
                seen = set()
                for edge in self.edges(snap):
                    if edge['source'] not in first_by_target or edge['target'] not in snap[2]:
                        continue
                    if edge['target'] in all_direct_refs or edge['target'] == first_by_target[edge['source']]['source']:
                        continue
                    signature = (edge['source'], edge['target'], edge['relation'])
                    if signature in seen:
                        continue
                    seen.add(signature)
                    first = first_by_target[edge['source']]
                    suggestions.append({'refs': [first['source'], edge['source'], edge['target']],
                                        'steps': [first, edge], 'preview_only': True})
            result['one_hop_edges'] = direct_edges
            result['continuations'] = {'items': suggestions[:12], 'total': len(suggestions),
                                       'preview_only': True, 'truncated': len(suggestions) > 12}
            result['retrieval_explanation'] = '选择场景 → 取阶段直接引用知识 → 在相关来源中检索段落；不递归检索后续节点。'
            return save_trace(self.root, result, parameters, 'gui', (time.perf_counter() - started) * 1000, before)

    def query_paths(self, payload, entrypoint='gui'):
        with self.lock:
            before, started = trace_revisions(self.root), time.perf_counter()
            result = self.multihop(payload)
            result['query_kind'] = 'multihop'
            result['question'] = result['query'] or (str(payload.get('start_ref', '')) + ' → ' + str(payload.get('target_ref') or '关联知识'))
            return save_trace(self.root, result, payload, entrypoint, (time.perf_counter() - started) * 1000, before)

    def traces(self):
        try:
            return list_traces(self.root)
        except ValueError as exc:
            raise StudioError(str(exc))

    def trace(self, trace_id):
        try:
            return read_trace(self.root, trace_id)
        except FileNotFoundError as exc:
            raise StudioError(str(exc), 404)
        except (ValueError, OSError) as exc:
            raise StudioError(str(exc))

    def feedback(self, payload):
        with self.lock:
            try:
                result = record_feedback(self.root, payload)
            except FileNotFoundError as exc:
                raise StudioError(str(exc), 404)
            except ValueError as exc:
                raise StudioError(str(exc), 409 if '版本' in str(exc) else 400)
            try:
                sync_feedback_queue(self.root)
            except (OSError, ValueError, yaml.YAMLError) as exc:
                print(f'Feedback queue sync failed: {type(exc).__name__}: {exc}', file=sys.stderr)
                return result | {'queue_status': 'sync_failed', 'warning': '评价已保存，待审队列未同步；刷新本次记录后再次保存可重试。'}
            return result | {'queue_status': 'synced'}

    def overview(self):
        snap = self.snapshot()
        bindings, binding_revision = self.bindings()
        usage = {}
        traces = self.traces()
        for run in traces['items']:
            for ref in run['used_refs']:
                usage[ref] = usage.get(ref, 0) + 1
        nodes = []
        for ref, item in snap[2].items():
            paragraphs = {}
            if bindings['bindings'].get(ref):
                for source in item['data'].get('sources', []):
                    if source not in snap[3]:
                        continue
                    try:
                        paragraphs.update({p['evidence_id']: p for p in self.source_index(source)['paragraphs']})
                    except (StudioError, ValueError):
                        continue
            reviews = resolve_bindings(ref, item['data'], paragraphs, bindings)
            valid = [r for r in reviews if r['status'] == 'confirmed']
            pending = [r for r in reviews if r['status'] != 'confirmed']
            nodes.append(self.summary(item) | {'source_count': len(item['data'].get('sources', [])),
                         'confirmed_count': len(valid), 'review_required_count': len(pending),
                         'confirmed_fields': sorted({r['support_field'] for r in valid if r['support_field'] != 'node'}),
                         'confirmed_association_count': sum(r['support_field'] == 'node' for r in valid),
                         'evidence_status': 'review_required' if pending else ('confirmed' if valid else 'sources_only'),
                         'query_count': usage.get(ref, 0)})
        grouped, broken = {}, []
        for edge in self.edges(snap):
            if edge['target'] not in snap[2]:
                broken.append(edge); continue
            key = (edge['source'], edge['target'], edge['relation'])
            if key not in grouped:
                grouped[key] = {k: edge[k] for k in ('source', 'target', 'relation', 'label')} | {'fields': [], 'phases': []}
            grouped[key]['fields'].append(edge['field'])
            if edge.get('phase'):
                grouped[key]['phases'].append(edge['phase'])
        matrix = []
        for scenario in snap[0]['scenario']['scenarios']:
            uses = {}
            for phase in scenario.get('composition', []):
                for ref in phase.get('uses', []):
                    uses.setdefault(ref, []).append(phase['phase'])
            matrix.append({'ref': 'scenario://' + scenario['id'], 'id': scenario['id'], 'uses': uses})
        return {'nodes': nodes, 'edges': list(grouped.values()), 'matrix': matrix,
                'revisions': snap[1], 'binding_revision': binding_revision,
                'counts': {kind: len(snap[0][kind][key]) for kind, key in KINDS.items()},
                'sources': len(snap[3]), 'edge_records': len(self.edges(snap)), 'broken_references': broken,
                'trace_count': len(traces['items']), 'skipped_traces': traces['skipped'],
                'coverage': {'nodes_with_confirmed_fields': sum(bool(n['confirmed_fields']) for n in nodes),
                             'nodes_needing_review': sum(bool(n['review_required_count']) for n in nodes),
                             'scope': 'field_review_only_not_whole_node_correctness'}}

    def replace_node_text(self, kind, old_id, node):
        raw = self.model_path(kind).read_bytes()
        text = raw.decode('utf-8-sig')
        syntax = yaml.compose(text)
        key = KINDS[kind]
        sequence = next((v for k,v in syntax.value if k.value == key), None)
        if not isinstance(sequence, yaml.SequenceNode):
            raise StudioError('模型序列结构无效', 422)
        lines = text.splitlines(keepends=True)
        for i, mapping in enumerate(sequence.value):
            item_id = next((v.value for k,v in mapping.value if k.value == 'id'), None)
            if item_id != old_id: continue
            start = mapping.start_mark.line
            end = sequence.value[i+1].start_mark.line if i+1 < len(sequence.value) else sequence.end_mark.line
            # Preserve comments/blank lines that introduce the next entry.
            while end > start+1 and (not lines[end-1].strip() or lines[end-1].lstrip().startswith('#')):
                end -= 1
            prefix = re.match(r'^(\s*)-', lines[start]).group(1)
            block = yaml.safe_dump([node],allow_unicode=True,sort_keys=False,width=100,default_flow_style=False)
            replacement = ''.join(prefix + line if line.strip() else line for line in block.splitlines(keepends=True))
            new = ''.join(lines[:start]) + replacement + ''.join(lines[end:])
            parsed = yaml.safe_load(new)
            expected = copy.deepcopy(yaml.safe_load(text))
            expected[key][i] = node
            if parsed != expected:
                raise StudioError('无法安全替换该节点，未写入任何修改', 422)
            return raw, new.encode('utf-8')
        raise StudioError('节点不存在',404)

    def preview(self, ref, payload):
        snap = self.snapshot(); item = self.find(ref,snap)
        if payload.get('revision') != snap[1][item['kind']]:
            raise StudioError('模型文件已变化，请刷新节点后重新编辑', 409)
        node = payload.get('node')
        self.validate_node(item['kind'], node, item['id'], snap)
        before, after = self.replace_node_text(item['kind'], item['id'], node)
        # Diff node content instead of incidental serialization of the whole file.
        a = json.dumps(item['data'],ensure_ascii=False,indent=2).splitlines()
        b = json.dumps(node,ensure_ascii=False,indent=2).splitlines()
        changes = '\n'.join(difflib.unified_diff(a,b,fromfile='当前节点',tofile='修改节点',lineterm=''))
        incoming = [e for e in self.edges(snap) if e['target']==ref]
        impacted = sorted(set(e['source'] for e in incoming))
        return {'ref':ref,'revision':snap[1][item['kind']],'changed':node != item['data'],'diff':changes,
                'impact':{'incoming_edges':len(incoming),'nodes':[self.summary(snap[2][r]) for r in impacted]},
                'preview_token':digest(after)}, before, after

    def atomic_write(self, path, data):
        path.parent.mkdir(parents=True,exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix='.studio-', dir=path.parent)
        try:
            with os.fdopen(fd,'wb') as f:
                f.write(data); f.flush(); os.fsync(f.fileno())
            os.replace(tmp,path)
        finally:
            if os.path.exists(tmp): os.unlink(tmp)

    @serialized_write
    def save(self, ref, payload):
        with self.lock:
            result,before,after = self.preview(ref,payload)
            if result['preview_token'] != payload.get('preview_token'):
                raise StudioError('请先预览当前修改，再保存',409)
            if not result['changed']:
                return {'status':'unchanged','revision':result['revision']}
            item = self.find(ref); path = self.model_path(item['kind'])
            # Recheck immediately before writing; detects external changes after preview.
            if digest(path.read_bytes()) != result['revision']:
                raise StudioError('模型被外部修改，未写入',409)
            backup_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid.uuid4().hex[:10]
            history = self.root / 'runs/gui/history'
            self.atomic_write(history/(backup_id+'.yaml'),before)
            record = {'backup_id':backup_id,'ref':ref,'kind':item['kind'],'before':digest(before),
                      'after':digest(after),'created_at':datetime.now(timezone.utc).isoformat()}
            self.atomic_write(history/(backup_id+'.json'),json.dumps(record,ensure_ascii=False,indent=2).encode())
            self.atomic_write(path,after)
            return {'status':'saved','revision':digest(after),'backup_id':backup_id}

    def history(self, ref):
        self.find(ref)
        records = []
        for p in sorted((self.root/'runs/gui/history').glob('*.json'),reverse=True):
            r = json.loads(p.read_text(encoding='utf-8'))
            if r.get('ref') == ref: records.append(r)
        return records

    @serialized_write
    def rollback(self, payload):
        with self.lock:
            backup_id = payload.get('backup_id','')
            if not isinstance(backup_id,str) or not re.fullmatch(r'\d{8}T\d{6}-[a-f0-9]{10}',backup_id):
                raise StudioError('无效备份 ID')
            base = self.root/'runs/gui/history'/backup_id
            record_path = base.with_suffix('.json')
            if not record_path.exists(): raise StudioError('备份不存在',404)
            record = json.loads(record_path.read_text())
            current = self.model_path(record['kind']).read_bytes()
            if digest(current) != payload.get('revision') or digest(current) != record['after']:
                raise StudioError('文件已有后续修改；拒绝整文件回滚以免覆盖他人修改',409)
            data = base.with_suffix('.yaml').read_bytes()
            if digest(data) != record['before']:
                raise StudioError('备份校验不通过',422)
            self.atomic_write(self.model_path(record['kind']),data)
            return {'status':'restored','revision':digest(data)}
