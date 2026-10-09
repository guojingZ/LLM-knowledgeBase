"""Incremental knowledge construction. Agents propose; reviewed changes are published."""
from __future__ import annotations
import copy
import difflib
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
import yaml
from kb_evidence import digest, source_index, support_digest
from kb_trace import atomic_write
from kb_write import project_write_lock

KINDS = {'scenario': 'scenarios', 'concept': 'concepts', 'entity': 'entities'}
BASE = 'runs/build/knowledge'
STATE = 'registry/knowledge_build.yaml'
MANIFEST = 'registry/source_manifest.yaml'
MUTATIONS = {'sources.import', 'sources.scan', 'sources.admit', 'jobs.create',
             'jobs.extract', 'jobs.compare', 'jobs.review', 'jobs.publish', 'publications.recover'}


class BuildError(ValueError):
    def __init__(self, message, status=422):
        super().__init__(message); self.status = status


def now():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def yaml_bytes(value):
    return yaml.safe_dump(value, allow_unicode=True, sort_keys=False).encode('utf-8')


def text(value, label, maximum=4000, empty=False):
    if not isinstance(value, str) or (not empty and not value.strip()) or len(value) > maximum:
        raise BuildError(f'{label} 必须是非空文本，最多 {maximum} 字符' if not empty else f'{label} 文本无效')
    return value


def identifier(value, prefix):
    if not isinstance(value, str) or not re.fullmatch(prefix + r'-[a-f0-9]{16}', value):
        raise BuildError('无效记录 ID')
    return value


def render_nodes(original, key, updates, additions):
    """Replace only affected YAML entries; preserve neighboring comments and bytes."""
    bom = b'\xef\xbb\xbf' if original.startswith(b'\xef\xbb\xbf') else b''
    source = original.decode('utf-8-sig'); doc = yaml.safe_load(source)
    syntax = yaml.compose(source)
    sequence = next(v for k, v in syntax.value if k.value == key)
    lines = source.splitlines(keepends=True); changes = []
    prefix = re.match(r'^(\s*)-', lines[sequence.value[0].start_mark.line]).group(1) if sequence.value else ''
    for i, mapping in enumerate(sequence.value):
        name = next(v.value for k, v in mapping.value if k.value == 'id')
        if name not in updates: continue
        begin = mapping.start_mark.line
        end = sequence.value[i+1].start_mark.line if i+1 < len(sequence.value) else sequence.end_mark.line
        while end > begin + 1 and (not lines[end-1].strip() or lines[end-1].lstrip().startswith('#')): end -= 1
        block = yaml.safe_dump([updates[name]], allow_unicode=True, sort_keys=False, width=100)
        changes.append((begin, end, ''.join(prefix + line for line in block.splitlines(keepends=True))))
    if additions and sequence.value:
        block = yaml.safe_dump(additions, allow_unicode=True, sort_keys=False, width=100)
        at = sequence.end_mark.line
        changes.append((at, at, ('\n' if at and not lines[at-1].endswith('\n') else '') +
                        ''.join(prefix + line for line in block.splitlines(keepends=True))))
    if additions and not sequence.value:
        before = source[:sequence.start_mark.index].rstrip()
        suffix = source[sequence.end_mark.index:]
        comment, _, tail = suffix.partition('\n')
        block = yaml.safe_dump(additions, allow_unicode=True, sort_keys=False, width=100)
        result = (before + comment + '\n' + block + tail).encode('utf-8')
        doc[key] = additions
        if yaml.safe_load(result) != doc: raise BuildError('无法安全新增首条模型，未发布')
        return bom + result
    for begin, end, block in sorted(changes, reverse=True): lines[begin:end] = [block]
    result = ''.join(lines).encode('utf-8')
    expected = copy.deepcopy(doc)
    expected[key] = [updates.get(n['id'], n) for n in doc[key]] + additions
    if yaml.safe_load(result) != expected: raise BuildError('无法安全替换模型条目，未发布')
    return bom + result


class KnowledgeBuild:
    def __init__(self, studio):
        self.studio = studio; self.root = studio.root

    def path(self, relative):
        p = self.root / relative
        if not p.resolve().is_relative_to(self.root): raise BuildError('项目路径越界')
        return p

    def read(self, relative, default=None):
        p = self.path(relative)
        if not p.exists(): return copy.deepcopy(default)
        value = yaml.safe_load(p.read_bytes())
        if not isinstance(value, dict): raise BuildError(f'记录结构无效：{relative}')
        return value

    def state(self):
        value = self.read(STATE, {'version': '1.0', 'sources': {}})
        if not isinstance(value.get('sources'), dict): raise BuildError('资料登记结构无效')
        return value

    def revision(self, relative):
        p = self.path(relative)
        return digest(p.read_bytes()) if p.exists() else digest(b'')

    def check(self, relative, supplied):
        if supplied != self.revision(relative): raise BuildError('记录版本已变化，请刷新后重新操作', 409)

    def commit(self, changes, purpose):
        """Journal before writing; compensate on failure and recover after process death."""
        items = []
        for name, after in changes.items():
            p = self.path(name); before = p.read_bytes() if p.exists() else None
            if before != after: items.append((name, before, after))
        if not items: return None
        pub = 'pub-' + uuid.uuid4().hex[:16]; folder = self.path(f'{BASE}/publications/{pub}')
        folder.mkdir(parents=True)
        plan = {'publication_id': pub, 'purpose': purpose, 'created_at': now(), 'status': 'prepared', 'files': []}
        for i, (name, before, after) in enumerate(items):
            for label, data in [('before', before), ('after', after)]:
                if data is not None: atomic_write(folder / f'{i}.{label}', data)
            plan['files'].append({'path': name, 'before': digest(before) if before is not None else None,
                                  'after': digest(after) if after is not None else None})
        atomic_write(folder / 'manifest.json', encoded(plan))
        try:
            for name, before, after in items:
                current = self.path(name).read_bytes() if self.path(name).exists() else None
                if current != before: raise BuildError('写入期间发现外部修改，停止发布', 409)
                if after is None: self.path(name).unlink(missing_ok=True)
                else: atomic_write(self.path(name), after)
            plan['status'] = 'committed'; atomic_write(folder / 'manifest.json', encoded(plan))
        except Exception:
            try:
                self._restore(folder, plan)
                plan['status'] = 'rolled_back'
            except Exception as exc:
                plan['status'] = 'recovery_required'; plan['error'] = str(exc)
            atomic_write(folder / 'manifest.json', encoded(plan))
            raise
        return pub

    def _restore(self, folder, plan):
        for i in reversed(range(len(plan['files']))):
            item = plan['files'][i]; p = self.path(item['path'])
            current = digest(p.read_bytes()) if p.exists() else None
            if current not in {item['before'], item['after']}:
                raise BuildError(f'恢复遇到外部修改，保留现场：{item["path"]}', 409)
            if current == item['before']: continue
            if item['before'] is None: p.unlink(missing_ok=True)
            else:
                data = (folder / f'{i}.before').read_bytes()
                if digest(data) != item['before']: raise BuildError('恢复备份校验失败')
                atomic_write(p, data)

    def publications(self):
        items = [self.read(str(p.relative_to(self.root))) for p in self.path(f'{BASE}/publications').glob('*/manifest.json')]
        return sorted(items, key=lambda p: p.get('created_at', ''), reverse=True)

    def execute(self, action, payload=None):
        payload = payload or {}
        if not isinstance(payload, dict): raise BuildError('参数必须是 JSON 对象')
        methods = {'sources.list': self.sources, 'sources.read': self.source_read,
                   'sources.import': self.source_import, 'sources.scan': self.source_scan,
                   'sources.admit': self.source_admit, 'catalog': self.catalog,
                   'jobs.list': self.jobs, 'jobs.create': self.job_create, 'jobs.get': self.job_get,
                   'jobs.packet': self.packet, 'jobs.extract': self.extract, 'jobs.compare': self.compare,
                   'jobs.review': self.review, 'jobs.preview': self.preview, 'jobs.publish': self.publish,
                   'publications.list': lambda _: {'items': self.publications()}, 'publications.recover': self.recover,
                   'tools': lambda _: tool_contract()}
        if action not in methods: raise BuildError('未知操作；使用 tools 查看操作契约', 404)
        if action not in MUTATIONS: return methods[action](payload)
        with self.studio.lock, project_write_lock(self.root):
            if action != 'publications.recover' and any(p['status'] in {'prepared', 'recovery_required'} for p in self.publications()):
                raise BuildError('有未完成写入，请先执行 publications.recover', 409)
            return methods[action](payload)

    def _rows(self):
        state = self.state(); manifest = self.read(MANIFEST, {'sources': []})
        known = {r['path']: r for r in state['sources'].values()}
        paths = {r['path'] for r in manifest.get('sources', [])} | set(known)
        for base in ['raw/inbox', 'raw/accepted']:
            paths.update(str(p.relative_to(self.root)).replace('\\', '/') for p in self.path(base).rglob('*')
                         if p.is_file() and p.name != 'PUT_RAW_FILES_HERE.md')
        admitted = {r['path']: r for r in manifest.get('sources', [])}
        nodes = self.studio.snapshot()[2]; result = []
        for name in sorted(paths):
            if not name.startswith(('raw/inbox/', 'raw/accepted/')) or '..' in Path(name).parts:
                raise BuildError('来源登记路径无效')
            p = self.path(name); data = p.read_bytes() if p.is_file() else None
            old = known.get(name, {}); entry = admitted.get(name, {})
            linked = [ref for ref, n in nodes.items() if name in n['data'].get('sources', [])]
            source_id = old.get('source_id', 'src-' + digest(name)[:16])
            sha = digest(data) if data is not None else None
            baseline = old.get('processed_sha256', entry.get('sha256') if linked else None)
            admission = old.get('admission', 'accepted' if entry.get('status') == 'accepted' else 'pending')
            processing = 'needs_update' if data is None or (baseline and baseline != sha) else ('processed' if baseline else 'unprocessed')
            job_id = old.get('active_job')
            if job_id:
                job = self.read(f'{BASE}/jobs/{job_id}/job.json', {})
                if job and job.get('status') != 'completed' and processing != 'needs_update': processing = job['status']
            result.append({**old, 'source_id': source_id, 'path': name, 'admission': admission,
                           'sha256': sha, 'processed_sha256': baseline, 'processing': processing,
                           'missing': data is None, 'supported': p.suffix.lower() in {'.md', '.txt'},
                           'bytes': len(data) if data is not None else 0, 'linked_nodes': linked,
                           'legacy_linked': bool(linked and not old.get('active_job')),
                           'changed': bool(old.get('observed_sha256') and old['observed_sha256'] != sha)})
        return result

    def sources(self, payload):
        rows = self._rows(); hashes = {}
        for r in rows:
            if r['sha256']: hashes.setdefault(r['sha256'], []).append(r['source_id'])
        return {'items': rows, 'revision': self.revision(STATE),
                'duplicate_groups': [ids for ids in hashes.values() if len(ids) > 1]}

    def source(self, source_id):
        identifier(source_id, 'src')
        for row in self._rows():
            if row['source_id'] == source_id: return row
        raise BuildError('资料不存在', 404)

    def source_read(self, payload):
        row = self.source(payload.get('source_id'))
        if not row['supported'] or row['missing']: raise BuildError('仅支持存在的 Markdown / 文本文件')
        return row | {'text': self.path(row['path']).read_text(encoding='utf-8-sig')}

    def _register(self, state, row, changes):
        record = {k: row[k] for k in ('source_id', 'path', 'admission', 'processed_sha256')}
        record.update(state['sources'].get(row['source_id'], {}))
        if record.get('observed_sha256') != row['sha256'] or record.get('path') != row['path']:
            record['updated_at'] = now()
        record.update({'path': row['path'], 'observed_sha256': row['sha256']})
        if row['sha256'] and row['supported']:
            snapshot = f'{BASE}/source_versions/{row["source_id"]}/{row["sha256"]}.txt'
            data = self.path(row['path']).read_bytes()
            if digest(data) != row['sha256']: raise BuildError('扫描期间原文变化，请刷新后重试', 409)
            if self.path(snapshot).exists() and digest(self.path(snapshot).read_bytes()) != row['sha256']:
                raise BuildError('已有原文快照校验失败，保留现场，不覆盖')
            changes[snapshot] = data
        state['sources'][row['source_id']] = record
        return record

    def _manifest(self, rows):
        doc = self.read(MANIFEST, {'version': '1.0'})
        old = {r['path']: r for r in doc.get('sources', [])}
        records = [{**old.get(r['path'], old.get(r['path'].replace('raw/accepted/', 'raw/inbox/', 1), {})),
                    'path': r['path'], 'status': r['admission'], 'sha256': r['sha256'], 'bytes': r['bytes']} for r in rows]
        if records != doc.get('sources'): doc['generated_at'] = now()
        doc.update({'source_count': len(rows), 'sources': records})
        groups = {}
        for r in rows:
            if r['sha256']: groups.setdefault(r['sha256'], []).append(r['path'])
        doc['duplicate_groups'] = [v for v in groups.values() if len(v) > 1]
        return yaml_bytes(doc)

    def source_import(self, payload):
        name = text(payload.get('name'), '文件名', 120)
        if name != Path(name).name or any(c in name for c in '/\\:<>|?*') or any(ord(c) < 32 for c in name) or name.endswith(('.', ' ')) or name.startswith('.') or re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])', name.split('.')[0], re.I):
            raise BuildError('请使用普通文件名，不含路径或特殊字符')
        if Path(name).suffix.lower() not in {'.md', '.txt'}: raise BuildError('仅支持 .md / .txt')
        data = text(payload.get('text'), '原文', 250000).encode('utf-8')
        if len(data) > 600000: raise BuildError('单份资料最多 600 KB')
        for row in self._rows():
            if row['sha256'] == digest(data): return {'status': 'duplicate', 'source': row}
        path = 'raw/inbox/' + name
        if self.path(path).exists(): raise BuildError('同名文件已存在，请换名称；更新已有资料应保留原路径', 409)
        state = self.state(); source_id = 'src-' + digest(path)[:16]
        state['sources'][source_id] = {'source_id': source_id, 'path': path, 'admission': 'pending',
                                      'observed_sha256': digest(data), 'processed_sha256': None, 'created_at': now()}
        self.commit({path: data, STATE: yaml_bytes(state)}, 'import_source')
        return {'status': 'imported', 'source': self.source(source_id)}

    def source_scan(self, payload):
        state = self.state(); rows = self._rows(); changes = {}
        for row in rows: self._register(state, row, changes)
        changes[STATE] = yaml_bytes(state); changes[MANIFEST] = self._manifest(rows)
        self.commit(changes, 'scan_sources')
        return self.sources({})

    def source_admit(self, payload):
        self.check(STATE, payload.get('revision'))
        row = self.source(payload.get('source_id')); decision = payload.get('decision')
        if decision not in {'accepted', 'rejected'}: raise BuildError('请选择准入或不纳入')
        if row['sha256'] != payload.get('source_sha256'): raise BuildError('原文已经变化，请刷新', 409)
        if row['missing'] or not row['supported']: raise BuildError('资料不存在或格式不支持')
        if row['admission'] == decision: return {'status': 'unchanged', 'source': row}
        if row['admission'] == 'accepted' and decision == 'rejected':
            raise BuildError('已准入来源不能直接撤回；先审查引用影响，避免断开正式知识')
        state = self.state(); changes = {}; record = self._register(state, row, changes)
        if decision == 'accepted' and row['path'].startswith('raw/inbox/'):
            dest = row['path'].replace('raw/inbox/', 'raw/accepted/', 1)
            if self.path(dest).exists(): raise BuildError('已准入目录存在同名资料，未覆盖', 409)
            changes[dest] = self.path(row['path']).read_bytes(); changes[row['path']] = None
            record['path'] = dest
        record.update({'admission': decision, 'admission_note': text(payload.get('note', ''), '说明', empty=True)})
        rows = [r | {'path': record['path'], 'admission': decision} if r['source_id'] == row['source_id'] else r for r in self._rows()]
        changes[STATE] = yaml_bytes(state); changes[MANIFEST] = self._manifest(rows)
        self.commit(changes, 'admit_source')
        return {'status': decision, 'source': self.source(row['source_id'])}

    def catalog(self, payload):
        snap = self.studio.snapshot(); aliases = self.read('registry/aliases.yaml', {'aliases': []})
        if payload.get('ref'): return self.studio.detail(payload['ref'])
        return {'items': [{'ref': ref, 'id': item['id'], 'kind': item['kind'],
                           'define': item['data'].get('define'), 'type': item['data'].get('type'),
                           'tags': item['data'].get('tags', [])} for ref, item in snap[2].items()],
                'aliases': aliases.get('aliases', []), 'model_revisions': snap[1]}

    def job_path(self, job_id):
        return f'{BASE}/jobs/{identifier(job_id, "job")}/job.json'

    def load_job(self, payload):
        job = self.read(self.job_path(payload.get('job_id')))
        if job is None: raise BuildError('任务不存在', 404)
        return job

    def jobs(self, payload):
        items = []
        for path in sorted(self.path(f'{BASE}/jobs').glob('*/job.json'), reverse=True):
            job = self.read(str(path.relative_to(self.root)))
            items.append({k: job[k] for k in ('job_id', 'title', 'status', 'created_at', 'sources')})
        return {'items': sorted(items, key=lambda j: j['created_at'], reverse=True)}

    def job_create(self, payload):
        ids = payload.get('source_ids')
        if not isinstance(ids, list) or not 1 <= len(ids) <= 20 or len(ids) != len(set(ids)): raise BuildError('请选择 1–20 份不同资料')
        rows = [self.source(i) for i in ids]
        if any(r['admission'] != 'accepted' or r['missing'] or not r['supported'] for r in rows): raise BuildError('任务只能使用存在且已准入的文本资料')
        state = self.state(); changes = {}; job_id = 'job-' + uuid.uuid4().hex[:16]
        for row in rows: self._register(state, row, changes)['active_job'] = job_id
        snap = self.studio.snapshot(); folder = f'{BASE}/jobs/{job_id}'
        job = {'job_id': job_id, 'title': text(payload.get('title', Path(rows[0]['path']).name), '任务名', 120),
               'created_at': now(), 'status': 'awaiting_extraction', 'model_revisions': snap[1],
               'sources': [{k: r[k] for k in ('source_id', 'path', 'sha256')} for r in rows],
               'observations': None, 'proposals': [], 'publications': []}
        changes[folder + '/models.json'] = encoded({ref: item['data'] for ref, item in snap[2].items()})
        changes[self.job_path(job_id)] = encoded(job); changes[STATE] = yaml_bytes(state)
        changes[folder + '/task.md'] = self.instructions(job, 'extraction').encode('utf-8')
        self.commit(changes, 'create_extraction_job')
        return self.job_get({'job_id': job_id})

    def freshness(self, job):
        issues = []
        if self.studio.snapshot()[1] != job['model_revisions']: issues.append('正式模型已变化；新建任务重新比较，不能覆盖当前模型')
        for source in job['sources']:
            row = self.source(source['source_id'])
            if row['sha256'] != source['sha256'] or row['path'] != source['path'] or row['admission'] != 'accepted':
                issues.append('资料版本或准入状态已变化：' + source['path'])
        return issues

    def job_get(self, payload):
        job = self.load_job(payload)
        return job | {'revision': self.revision(self.job_path(job['job_id'])), 'freshness_issues': self.freshness(job),
                      'task_path': f'{BASE}/jobs/{job["job_id"]}/task.md'}

    def instructions(self, job, phase):
        command = 'jobs.extract' if phase == 'extraction' else 'jobs.compare'
        return ('# 知识建设任务\n\n任务：' + job['job_id'] + '\n\n' +
                ('第一轮只从原文提取候选，不为了匹配现有名称而改写原意。' if phase == 'extraction' else
                 '第二轮比较 observations 与已有节点。先读目录，再用 catalog/ref 读取完整节点。') +
                '\n使用人定义的场景、概念、实体及现有字段；证据不足或框架无法表达的内容单列疑问。\n' +
                '通过 jobs.packet 获取原文快照、判据、示例和结果格式。输出 JSON，使用 ' + command +
                ' 提交。候选不是正式知识；不执行 review/publish，除非用户明确要求执行审查决定。\n')

    def packet(self, payload):
        job = self.load_job(payload); phase = payload.get('phase', 'extraction')
        if phase not in {'extraction', 'comparison'}: raise BuildError('phase 必须是 extraction / comparison')
        models = self.read(f'{BASE}/jobs/{job["job_id"]}/models.json')
        docs = []
        for s in job['sources']:
            raw = self.path(f'{BASE}/source_versions/{s["source_id"]}/{s["sha256"]}.txt').read_bytes()
            if digest(raw) != s['sha256']: raise BuildError('原文快照校验失败')
            docs.append(s | {'text': raw.decode('utf-8-sig')})
        return {'job_id': job['job_id'], 'revision': self.revision(self.job_path(job['job_id'])),
                'phase': phase, 'instructions': self.instructions(job, phase), 'source_documents': docs,
                'rubric': self.path('application/build-rubric.md').read_text(encoding='utf-8'),
                'catalog': [{'ref': ref, 'id': n['id'], 'define': n.get('define'), 'type': n.get('type')} for ref, n in models.items()] if phase == 'comparison' else [],
                'observations': job['observations'] if phase == 'comparison' else None,
                'result_schema': tool_contract()['result_formats'][phase], 'freshness_issues': self.freshness(job)}

    def _evidence(self, job, value):
        if not isinstance(value, dict): raise BuildError('证据必须是对象')
        s = next((s for s in job['sources'] if s['source_id'] == value.get('source_id')), None)
        if not s: raise BuildError('证据必须来自本任务资料')
        lines = self.path(f'{BASE}/source_versions/{s["source_id"]}/{s["sha256"]}.txt').read_text(encoding='utf-8-sig').splitlines()
        start, end = value.get('line_start'), value.get('line_end')
        if type(start) is not int or type(end) is not int or not 1 <= start <= end <= len(lines): raise BuildError('原文行号无效')
        excerpt = text(value.get('excerpt'), '原文摘录', 20000)
        if excerpt != '\n'.join(lines[start-1:end]): raise BuildError('摘录与原文行号不一致，禁止提交改写证据')
        result = {**s, 'line_start': start, 'line_end': end, 'excerpt': excerpt}
        if 'support_field' in value: result['support_field'] = value['support_field']
        return result

    def extract(self, payload):
        job = self.load_job(payload); self.check(self.job_path(job['job_id']), payload.get('revision'))
        if job['proposals'] or job['publications']: raise BuildError('任务已进入比较阶段，请新建任务重新提取')
        values = payload.get('observations'); note = text(payload.get('note', ''), '提取说明', empty=True)
        if not isinstance(values, list) or len(values) > 200 or (not values and not note.strip()): raise BuildError('observations 必须是列表；无候选时说明理由')
        observations = []
        for i, value in enumerate(values):
            if not isinstance(value, dict) or value.get('kind') not in KINDS: raise BuildError('候选类型必须是 scenario / concept / entity')
            evidence = value.get('evidence')
            if not isinstance(evidence, list) or not evidence: raise BuildError('每个候选必须附原文证据')
            observations.append({'observation_id': f'obs-{i+1:04d}', 'kind': value['kind'],
                                 'id': text(value.get('id'), '候选名', 120), 'define': text(value.get('define'), '定义'),
                                 'question': text(value.get('question', ''), '疑问', empty=True),
                                 'evidence': [self._evidence(job, e) for e in evidence]})
        if observations == job['observations'] and note == job.get('extraction_note'): return self.job_get(payload) | {'unchanged': True}
        job.update({'observations': observations, 'extraction_note': note, 'status': 'awaiting_comparison'})
        self.commit({self.job_path(job['job_id']): encoded(job)}, 'submit_extraction')
        return self.job_get(payload)

    def compare(self, payload):
        job = self.load_job(payload); self.check(self.job_path(job['job_id']), payload.get('revision'))
        if job['observations'] is None: raise BuildError('先提交第一轮提取，再比较已有知识')
        if job['publications']: raise BuildError('任务已有发布记录，请新建任务')
        values = payload.get('proposals'); note = text(payload.get('note', ''), '比较说明', empty=True)
        if not isinstance(values, list) or len(values) > 200 or (not values and not note.strip()): raise BuildError('proposals 必须是列表；无变化时说明理由')
        models = self.read(f'{BASE}/jobs/{job["job_id"]}/models.json'); proposals = []; used = set()
        observation_ids = {v['observation_id'] for v in job['observations']}
        for i, value in enumerate(values):
            if not isinstance(value, dict) or value.get('action') not in {'new', 'update', 'evidence', 'merge', 'conflict', 'ignore'}: raise BuildError('候选动作无效')
            action = value['action']; obs = value.get('observation_ids')
            if not isinstance(obs, list) or not obs or any(o not in observation_ids for o in obs): raise BuildError('建议必须关联第一轮候选')
            ref = value.get('target_ref'); node = copy.deepcopy(value.get('node'))
            if action == 'new':
                if not isinstance(node, dict) or not isinstance(ref, str) or ref.split('://')[0] not in KINDS or ref != ref.split('://')[0] + '://' + str(node.get('id')):
                    raise BuildError('新增需提供合法 target_ref 和完整 node')
                if ref in models: raise BuildError('已有同名节点，请使用补充或合并')
            elif action in {'update', 'evidence', 'merge'}:
                if ref not in models: raise BuildError('目标节点不存在')
                node = copy.deepcopy(models[ref]) if action != 'update' else node
                if not isinstance(node, dict) or node.get('id') != models[ref]['id']: raise BuildError('更新不可改 id')
            supports = [self._evidence(job, s) for s in value.get('supports', [])]
            if action in {'new', 'update', 'evidence', 'merge'}:
                if ref in used: raise BuildError('同一目标的变化请合并为一条建议')
                used.add(ref)
                if not supports: raise BuildError('发布知识必须附支持字段及原文证据')
                node['sources'] = list(dict.fromkeys((node.get('sources') or []) + [s['path'] for s in supports]))
                for s in supports: support_digest(node, s.get('support_field'))
            aliases = value.get('aliases', [])
            if not isinstance(aliases, list) or any(not isinstance(a, str) or not a.strip() or len(a) > 120 for a in aliases): raise BuildError('别名必须是短文本列表')
            if action == 'merge' and not aliases: raise BuildError('合并需登记候选名称 aliases')
            proposals.append({'proposal_id': f'candidate-{i+1:04d}', 'action': action, 'target_ref': ref,
                              'node': node, 'observation_ids': obs, 'supports': supports, 'aliases': aliases,
                              'reason': text(value.get('reason'), '建议理由'), 'review': {'decision': 'pending', 'note': ''}, 'published': False})
        covered = {o for p in proposals for o in p['observation_ids']}
        if observation_ids - covered:
            raise BuildError('第一轮候选尚未全部比较；无须纳入的候选也请用 ignore 并说明理由：' + ', '.join(sorted(observation_ids - covered)))
        staged_nodes = copy.deepcopy(self.studio.snapshot()[2])
        for p in proposals:
            if p['node'] and p['action'] in {'new', 'update', 'evidence', 'merge'}:
                staged_nodes[p['target_ref']] = {'data': p['node']}
        snap = self.studio.snapshot(); staged = (snap[0], snap[1], staged_nodes, snap[3])
        for p in proposals:
            if p['action'] in {'new', 'update', 'evidence', 'merge'}:
                kind, name = p['target_ref'].split('://', 1)
                self.studio.validate_node(kind, p['node'], name, staged)
        stripped = lambda ps: [{k: v for k, v in p.items() if k not in {'review', 'published'}} for p in ps]
        if stripped(proposals) == stripped(job['proposals']) and note == job.get('comparison_note'): return self.job_get(payload) | {'unchanged': True}
        job.update({'proposals': proposals, 'comparison_note': note, 'status': 'review_required'})
        self.commit({self.job_path(job['job_id']): encoded(job)}, 'submit_comparison')
        return self.job_get(payload)

    def review(self, payload):
        job = self.load_job(payload); self.check(self.job_path(job['job_id']), payload.get('revision'))
        decision = payload.get('decision'); note = text(payload.get('note', ''), '审查说明', empty=True)
        if decision not in {'approved', 'rejected', 'hold'}: raise BuildError('审查决定无效')
        p = next((p for p in job['proposals'] if p['proposal_id'] == payload.get('proposal_id')), None)
        if p is None or p['published']: raise BuildError('候选不存在或已发布')
        if p['action'] == 'conflict' and decision == 'approved': raise BuildError('冲突不能直接发布为事实；保留待审或拒绝，解决后提交新建议')
        if decision in {'rejected', 'hold'} and not note.strip(): raise BuildError('拒绝或待定需说明理由')
        if p['review']['decision'] == decision and p['review']['note'] == note: return self.job_get(payload) | {'unchanged': True}
        p['review'] = {'decision': decision, 'note': note, 'reviewed_at': now()}
        self.commit({self.job_path(job['job_id']): encoded(job)}, 'review_candidate')
        return self.job_get(payload)

    def _publication(self, job):
        issues = self.freshness(job)
        if issues: raise BuildError('；'.join(issues), 409)
        if job['observations'] is None or job['status'] == 'awaiting_comparison': raise BuildError('尚未完成两轮处理')
        chosen = [p for p in job['proposals'] if p['review']['decision'] == 'approved' and not p['published']]
        remaining = [p for p in job['proposals'] if p['review']['decision'] in {'pending', 'hold'}]
        if not chosen and remaining: raise BuildError('没有可发布候选；请先审查')
        snap = self.studio.snapshot(); nodes = copy.deepcopy(snap[2]); changes = {}; diffs = []
        for p in chosen:
            if p['action'] in {'new', 'update', 'evidence', 'merge'}: nodes[p['target_ref']] = {'data': p['node']}
        for p in chosen:
            if p['action'] not in {'new', 'update', 'evidence', 'merge'}: continue
            kind, name = p['target_ref'].split('://', 1)
            self.studio.validate_node(kind, p['node'], name, (snap[0], snap[1], nodes, snap[3]))
            old = snap[2].get(p['target_ref'], {}).get('data', {})
            diffs.append({'proposal_id': p['proposal_id'], 'ref': p['target_ref'], 'action': p['action'],
                          'diff': '\n'.join(difflib.unified_diff(json.dumps(old, ensure_ascii=False, indent=2).splitlines(),
                                     json.dumps(p['node'], ensure_ascii=False, indent=2).splitlines(), fromfile='当前', tofile='建议')),
                          'supports': p['supports'], 'aliases': p['aliases']})
        for kind, key in KINDS.items():
            relevant = [p for p in chosen if p['action'] in {'new', 'update', 'evidence', 'merge'} and p['target_ref'].startswith(kind + '://')]
            if relevant:
                updates = {p['node']['id']: p['node'] for p in relevant if p['action'] != 'new'}
                additions = [p['node'] for p in relevant if p['action'] == 'new']
                changes[f'model/{key}.yaml'] = render_nodes(self.studio.model_path(kind).read_bytes(), key, updates, additions)
        bindings = self.read('registry/gui_evidence.yaml', {'version': '2.0', 'bindings': {}})
        aliases = self.read('registry/aliases.yaml', {'version': '1.0', 'aliases': []})
        for p in chosen:
            for s in p['supports'] if p['action'] in {'new', 'update', 'evidence', 'merge'} else []:
                candidates = source_index(self.root, s['path'])['paragraphs']
                paragraph = next((e for e in candidates if e['line_start'] <= s['line_start'] and e['line_end'] >= s['line_end']), None)
                if not paragraph: raise BuildError('支持范围跨越段落，请分开登记')
                field = s['support_field']; ref = p['target_ref']; records = bindings['bindings'].setdefault(ref, [])
                records[:] = [r for r in records if not (r['evidence_id'] == paragraph['evidence_id'] and r.get('support_field') == field)]
                records.append({**paragraph, 'support_field': field, 'node_sha256': support_digest(p['node'], field),
                                'review_note': p['review']['note'] or p['reason'], 'confirmed_at': now(), 'build_job': job['job_id']})
            if p['action'] == 'merge':
                entry = next((a for a in aliases['aliases'] if a['canonical'] == p['target_ref']), None)
                if entry is None: entry = {'canonical': p['target_ref'], 'variants': []}; aliases['aliases'].append(entry)
                entry['variants'] = list(dict.fromkeys(entry['variants'] + p['aliases']))
        if any(p['supports'] and p['action'] in {'new', 'update', 'evidence', 'merge'} for p in chosen):
            bindings['version'] = '2.0'; changes['registry/gui_evidence.yaml'] = yaml_bytes(bindings)
        if any(p['action'] == 'merge' for p in chosen): changes['registry/aliases.yaml'] = yaml_bytes(aliases)
        return changes, chosen, remaining, diffs

    def preview(self, payload):
        job = self.load_job(payload); changes, chosen, remaining, diffs = self._publication(job)
        identity = {'job_revision': self.revision(self.job_path(job['job_id'])),
                    'revisions': {p: self.revision(p) for p in [STATE, MANIFEST, 'registry/gui_evidence.yaml', 'registry/aliases.yaml']},
                    'model_revisions': self.studio.snapshot()[1], 'changes': {p: digest(v) for p, v in changes.items()},
                    'selected': [p['proposal_id'] for p in chosen]}
        # Time stamps belong to publication, not preview identity.
        identity['changes'].pop('registry/gui_evidence.yaml', None)
        return {'job_id': job['job_id'], 'preview_token': digest(json.dumps(identity, sort_keys=True)), 'diffs': diffs,
                'approved_count': len(chosen), 'remaining_count': len(remaining), 'will_complete': not remaining,
                'files': list(changes), 'no_model_change': not any(n.startswith('model/') for n in changes)}

    def publish(self, payload):
        job = self.load_job(payload)
        if job['status'] == 'completed': return self.job_get(payload) | {'unchanged': True}
        preview = self.preview(payload)
        if payload.get('preview_token') != preview['preview_token']: raise BuildError('请预览当前差异，再发布；版本变化需重新预览', 409)
        changes, chosen, remaining, _ = self._publication(job); state = self.state()
        for p in chosen: p['published'] = True
        job['status'] = 'partial_published' if remaining else 'completed'
        job['publications'].append({'published_at': now(), 'proposal_ids': [p['proposal_id'] for p in chosen],
                                    'reviewed_no_change': not chosen})
        # A partial publication advances this task's model baseline; unreviewed proposals still get revalidated.
        job['model_revisions'] = {kind: digest(changes.get(f'model/{key}.yaml', self.studio.model_path(kind).read_bytes())) for kind, key in KINDS.items()}
        for s in job['sources']:
            record = self._register(state, self.source(s['source_id']), changes)
            if not remaining: record['processed_sha256'] = s['sha256']
        changes[STATE] = yaml_bytes(state); changes[self.job_path(job['job_id'])] = encoded(job)
        publication_id = self.commit(changes, 'publish_reviewed_knowledge')
        return self.job_get(payload) | {'publication_id': publication_id, 'published_count': len(chosen)}

    def recover(self, payload):
        pub = identifier(payload.get('publication_id'), 'pub')
        folder = self.path(f'{BASE}/publications/{pub}'); plan = self.read(f'{BASE}/publications/{pub}/manifest.json')
        if not plan: raise BuildError('写入记录不存在', 404)
        if plan['status'] not in {'prepared', 'recovery_required'}: return {'status': plan['status'], 'unchanged': True}
        self._restore(folder, plan); plan['status'] = 'rolled_back'
        atomic_write(folder / 'manifest.json', encoded(plan)); return {'status': 'rolled_back'}


def tool_contract():
    definitions = [
        ('sources.list', [], '列出资料准入、处理状态和引用影响'), ('sources.read', ['source_id'], '读取原文'),
        ('sources.import', ['name', 'text'], '导入文本到待准入区'), ('sources.scan', [], '扫描新增、修改和缺失资料'),
        ('sources.admit', ['source_id', 'revision', 'source_sha256', 'decision'], '按用户决定准入或不纳入'),
        ('catalog', [], '读取节点目录；可传 ref 获取完整节点'), ('jobs.list', [], '列出提炼任务'),
        ('jobs.create', ['source_ids'], '创建两轮任务并冻结来源与模型基线'), ('jobs.get', ['job_id'], '读取任务、候选、审查和版本'),
        ('jobs.packet', ['job_id'], '读取 extraction / comparison 阶段任务包'),
        ('jobs.extract', ['job_id', 'revision', 'observations'], '提交忠实于原文的第一轮候选'),
        ('jobs.compare', ['job_id', 'revision', 'proposals'], '提交增量比较；不改正式模型'),
        ('jobs.review', ['job_id', 'revision', 'proposal_id', 'decision'], '记录用户审查决定'),
        ('jobs.preview', ['job_id'], '校验并预览通过的变化'), ('jobs.publish', ['job_id', 'preview_token'], '发布经用户审查的变化'),
        ('publications.list', [], '查看写入记录'), ('publications.recover', ['publication_id'], '恢复意外中断的写入')]
    fields = {
        'source_id': {'type': 'string', 'pattern': '^src-[a-f0-9]{16}$'},
        'source_ids': {'type': 'array', 'items': {'type': 'string'}, 'minItems': 1, 'maxItems': 20, 'uniqueItems': True},
        'job_id': {'type': 'string', 'pattern': '^job-[a-f0-9]{16}$'},
        'publication_id': {'type': 'string', 'pattern': '^pub-[a-f0-9]{16}$'},
        'revision': {'type': 'string', 'description': '原样使用 sources.list 或 jobs.get/packet 的 revision'},
        'source_sha256': {'type': 'string', 'description': '原样使用 sources.list 当前资料 sha256'},
        'name': {'type': 'string', 'maxLength': 120, 'description': '普通 .md/.txt 文件名'},
        'text': {'type': 'string', 'maxLength': 250000}, 'title': {'type': 'string', 'maxLength': 120},
        'ref': {'type': 'string', 'description': 'scenario://ID、concept://ID 或 entity://ID'},
        'phase': {'type': 'string', 'enum': ['extraction', 'comparison'], 'default': 'extraction'},
        'observations': {'type': 'array', 'items': {'type': 'object'}, 'maxItems': 200, 'description': '见 result_formats.extraction'},
        'proposals': {'type': 'array', 'items': {'type': 'object'}, 'maxItems': 200, 'description': '见 result_formats.comparison；必须覆盖全部 observation_ids'},
        'proposal_id': {'type': 'string'}, 'decision': {'type': 'string'},
        'note': {'type': 'string', 'maxLength': 4000}, 'preview_token': {'type': 'string'}
    }
    optional = {'sources.admit': ['note'], 'catalog': ['ref'], 'jobs.create': ['title'],
                'jobs.packet': ['phase'], 'jobs.extract': ['note'], 'jobs.compare': ['note'], 'jobs.review': ['note']}
    operations = []
    for name, required, desc in definitions:
        properties = {k: copy.deepcopy(fields[k]) for k in required + optional.get(name, [])}
        if name == 'sources.admit': properties['decision']['enum'] = ['accepted', 'rejected']
        if name == 'jobs.review': properties['decision']['enum'] = ['approved', 'rejected', 'hold']
        operations.append({'name': name, 'description': desc, 'required': required, 'mutates': name in MUTATIONS,
                           'requires_user_decision': name in {'sources.admit', 'jobs.review', 'jobs.publish', 'publications.recover'},
                           'input_schema': {'type': 'object', 'properties': properties, 'required': required}})
    return {'version': '1.0', 'transport': 'CLI JSON / local HTTP JSON',
            'guide': 'application/agent-operations.md', 'rubric': 'application/build-rubric.md',
            'operations': operations,
            'result_formats': {
                'extraction': {'observations': [{'kind': 'concept', 'id': '原文知识名', 'define': '忠实定义',
                                                 'evidence': [{'source_id': 'src-…', 'line_start': 1, 'line_end': 1, 'excerpt': '该行完整原文'}]}], 'note': '无候选时说明理由'},
                'comparison': {'proposals': [{'action': 'new/update/evidence/merge/conflict/ignore', 'target_ref': 'concept://知识名',
                                             'observation_ids': ['obs-0001'], 'node': '新增或更新时提供完整节点对象',
                                             'supports': [{'source_id': 'src-…', 'line_start': 1, 'line_end': 1, 'excerpt': '该行完整原文', 'support_field': 'define'}],
                                             'reason': '比较理由', 'aliases': 'merge 时提供名称列表'}], 'note': '无变化时说明理由'}}}
