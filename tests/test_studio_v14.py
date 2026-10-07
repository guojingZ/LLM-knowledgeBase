from __future__ import annotations
import json
import subprocess
import sys
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

import yaml
import test_studio as fixtures

PROJECT = Path(__file__).resolve().parents[1]
from studio import StudioError, digest
from kb_lib import retrieve_context
from kb_trace import save_trace, revisions, read_trace, make_trace_id
from sync_feedback_queue import sync_feedback_queue


class StudioV14Tests(unittest.TestCase):
    setUp = fixtures.StudioTests.setUp
    tearDown = fixtures.StudioTests.tearDown
    write_model = fixtures.StudioTests.write_model

    def bind(self, field='define'):
        ev = self.s.evidence('concept://MECE')
        p = next(p for p in ev['candidates'] if 'MECE' in p['text'])
        self.s.bind({'ref':'concept://MECE','evidence_id':p['evidence_id'],
                     'source_sha256':p['source_sha256'],'revision':ev['binding_revision'],
                     'support_field':field,'review_note':'人工检查段落支持所选字段',
                     'node_revision':self.s.detail('concept://MECE')['revision']})
        return p

    def test_review_is_shared_by_gui_one_hop_raw_and_cli(self):
        p = self.bind()
        for mode in ['model-guided','raw']:
            c = retrieve_context(self.root, 'MECE 分解结构不重不漏', mode=mode,
                                 scenario_id=self.scenario['id'] if mode=='model-guided' else None, evidence_k=30)
            evidence = next(e for e in c['evidence'] if e['evidence_id']==p['evidence_id'])
            self.assertEqual(evidence['status'],'confirmed')
            self.assertEqual(evidence['confirmed_for'][0]['support_field'],'define')
            self.assertEqual(evidence['confirmation_bonus'],.05)
        process = subprocess.run([sys.executable,str(PROJECT/'scripts/kb_context.py'),
                                  '--project',str(self.root),'--question','MECE 分解结构不重不漏',
                                  '--scenario',self.scenario['id'],'--json'],capture_output=True,text=True)
        self.assertEqual(process.returncode,0,process.stderr)
        result=json.loads(process.stdout)
        self.assertTrue(any(e['evidence_id']==p['evidence_id'] and e['status']=='confirmed' for e in result['evidence']))
        self.assertEqual(self.s.trace(result['trace_id'])['metadata']['entrypoint'],'cli')

    def test_confirmed_candidate_is_deduplicated_and_field_changes_require_review(self):
        p=self.bind()
        ev=self.s.evidence('concept://MECE')
        self.assertNotIn(p['evidence_id'],[p['evidence_id'] for p in ev['candidates']])
        document=yaml.safe_load(self.s.model_path('concept').read_text())
        document['concepts'][0]['tags']=['新标签']
        self.write_model('concepts',document['concepts'])
        self.assertEqual(self.s.evidence('concept://MECE')['confirmed'][0]['status'],'confirmed')
        document['concepts'][0]['define']='修改后的定义'
        self.write_model('concepts',document['concepts'])
        self.assertEqual(self.s.evidence('concept://MECE')['confirmed'][0]['status'],'stale')
        c=retrieve_context(self.root,'MECE 分解结构不重不漏',mode='raw',evidence_k=30)
        self.assertFalse(any(e['status']=='confirmed' for e in c['evidence']))

    def test_legacy_records_survive_and_need_scope_confirmation(self):
        p=self.s.evidence('concept://MECE')['candidates'][0]
        legacy={'version':'1.0','bindings':{'concept://MECE':[{k:p[k] for k in ['evidence_id','source','source_sha256','line_start','line_end']}|{'confirmed_at':'2026-09-30'}]}}
        path=self.root/'registry/gui_evidence.yaml';path.write_text(yaml.safe_dump(legacy))
        ev=self.s.evidence('concept://MECE')
        self.assertEqual(ev['confirmed'][0]['status'],'needs_review')
        self.assertNotIn(p['evidence_id'],[p['evidence_id'] for p in ev['candidates']])
        self.s.bind({'ref':'concept://MECE','evidence_id':p['evidence_id'],'source_sha256':p['source_sha256'],'revision':ev['binding_revision'],'support_field':'define'})
        self.assertEqual(self.s.evidence('concept://MECE')['confirmed'][0]['status'],'confirmed')
        self.assertEqual(len(yaml.safe_load(path.read_text())['bindings']['concept://MECE']),1)

    def test_invalid_scope_and_node_conflict_never_write_binding(self):
        ev=self.s.evidence('concept://MECE');p=ev['candidates'][0]
        args={'ref':'concept://MECE','evidence_id':p['evidence_id'],'source_sha256':p['source_sha256'],'revision':ev['binding_revision']}
        for extra in [{'support_field':'relations.references[99]'},{'support_field':'sources'},{'node_revision':'outdated'}]:
            with self.assertRaises(StudioError):self.s.bind(args|extra)
        self.assertFalse((self.root/'registry/gui_evidence.yaml').exists())

    def test_one_hop_does_not_include_preview_targets_and_records_unique_runs(self):
        a=self.s.query({'question':'定位根因，MECE 分解复杂问题','scenario':self.scenario['id']})
        b=self.s.query({'question':'定位根因，MECE 分解复杂问题','scenario':self.scenario['id']})
        self.assertNotEqual(a['trace_id'],b['trace_id'])
        self.assertEqual([n['ref'] for n in a['knowledge_items']],['concept://MECE'])
        self.assertNotIn('entity://逻辑树',[n['ref'] for n in a['knowledge_items']])
        self.assertTrue(any(p['refs']==['scenario://'+self.scenario['id'],'concept://MECE','entity://逻辑树'] for p in a['continuations']['items']))
        self.assertTrue(all(p['preview_only'] for p in a['continuations']['items']))
        direct={ref for phase in a['selected_scenario']['phases'] for ref in phase['uses']}
        self.assertTrue(all(p['refs'][-1] not in direct for p in a['continuations']['items']))
        self.assertEqual(a['one_hop_edges'][0]['field'],'composition[0].uses[0]')
        self.assertEqual(len(self.s.traces()['items']),2)
        self.assertEqual(self.s.trace(a['trace_id'])['metadata']['version_consistency'],'stable')

    def test_trace_snapshot_is_unchanged_by_later_source_edit_and_id_cannot_overwrite(self):
        result=self.s.query({'question':'MECE 分解复杂问题','scenario':self.scenario['id']})
        context_path=self.root/'runs/evaluation'/result['trace_id']/'context.json'
        before=context_path.read_bytes()
        (self.root/fixtures.SOURCE).write_text('完全改变来源内容')
        self.assertEqual(self.s.trace(result['trace_id'])['context']['evidence'],result['evidence'])
        with self.assertRaises(FileExistsError):
            save_trace(self.root,{}, {},'cli',0,revisions(self.root),result['trace_id'])
        self.assertEqual(context_path.read_bytes(),before)
        with self.assertRaises(StudioError):self.s.trace('../../model/concepts')
        self.assertNotEqual(make_trace_id('same'),make_trace_id('same'))

    def test_feedback_sync_is_idempotent_conflicts_and_never_edits_model(self):
        result=self.s.query({'question':'MECE 分解复杂问题','scenario':self.scenario['id']})
        before={p:p.read_bytes() for p in (self.root/'model').glob('*.yaml')}
        revision=self.s.trace(result['trace_id'])['feedback_revision']
        payload={'trace_id':result['trace_id'],'revision':revision,'rating':'partial','issues':['missing_knowledge'],
                 'notes':'缺少验证步骤','scenario_verdict':'correct','evidence_verdict':'partial'}
        feedback=self.s.feedback(payload);self.assertEqual(feedback['status'],'recorded')
        with self.assertRaises(StudioError) as error:self.s.feedback(payload|{'notes':'旧窗口覆盖'})
        self.assertEqual(error.exception.status,409)
        payload['revision']=feedback['revision'];self.assertEqual(self.s.feedback(payload)['status'],'unchanged')
        queue=self.root/'registry/application_feedback_queue.yaml';data=queue.read_bytes()
        sync_feedback_queue(self.root);self.assertEqual(queue.read_bytes(),data)
        doc=yaml.safe_load(data);self.assertEqual(len(doc['items']),1)
        self.assertEqual(doc['items'][0]['review_status'],'pending')
        self.assertFalse(doc['items'][0]['model_updated'])
        self.assertEqual(before,{p:p.read_bytes() for p in before})

    def test_feedback_queue_failure_can_retry_and_review_status_is_preserved(self):
        result=self.s.query({'question':'MECE 分解问题','scenario':self.scenario['id']})
        payload={'trace_id':result['trace_id'],'revision':self.s.trace(result['trace_id'])['feedback_revision'],
                 'rating':'helpful','issues':[],'notes':'有用'}
        with patch('studio.sync_feedback_queue',side_effect=OSError('simulated write failure')):
            first=self.s.feedback(payload)
        self.assertEqual(first['queue_status'],'sync_failed')
        self.assertEqual(self.s.trace(result['trace_id'])['feedback']['rating'],'helpful')
        payload['revision']=first['revision'];self.assertEqual(self.s.feedback(payload)['queue_status'],'synced')
        queue=self.root/'registry/application_feedback_queue.yaml';document=yaml.safe_load(queue.read_bytes())
        document['items'][0]['review_status']='reviewed';document['items'][0]['reviewer_note']='人工审查过'
        queue.write_text(yaml.safe_dump(document),encoding='utf-8')
        sync_feedback_queue(self.root)
        self.assertEqual(self.s.trace(result['trace_id'])['review']['review_status'],'reviewed')
        self.assertEqual(self.s.traces()['items'][0]['review_status'],'reviewed')
        payload['notes']='补充新的意见';self.s.feedback(payload)
        self.assertEqual(self.s.trace(result['trace_id'])['review']['review_status'],'pending')

    def test_overview_includes_all_nodes_and_usage_and_partial_review_coverage(self):
        self.bind();result=self.s.query({'question':'MECE 分解复杂问题','scenario':self.scenario['id']})
        overview=self.s.overview()
        self.assertEqual(len(overview['nodes']),6)
        mece=next(n for n in overview['nodes'] if n['ref']=='concept://MECE')
        self.assertEqual(mece['confirmed_fields'],['define']);self.assertEqual(mece['query_count'],1)
        independent=next(n for n in overview['nodes'] if n['id']=='无关联')
        self.assertEqual(independent['query_count'],0)
        self.assertEqual(overview['matrix'][0]['uses'],{'concept://MECE':['分解']})
        self.assertEqual(overview['coverage']['nodes_with_confirmed_fields'],1)

    def test_trace_failed_write_cleans_only_new_run(self):
        with patch('kb_trace.atomic_write',side_effect=OSError('simulated disk failure')):
            with self.assertRaises(OSError):save_trace(self.root,{'question':'测试'}, {},'gui',0,revisions(self.root),'new-failed-run')
        self.assertFalse((self.root/'runs/evaluation/new-failed-run').exists())

    def test_http_new_workflows_and_invalid_inputs(self):
        server=fixtures.create_server(self.root,0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        address='http://127.0.0.1:'+str(server.server_address[1])
        def request(path,payload=None):
            req=urllib.request.Request(address+path,data=json.dumps(payload).encode() if payload is not None else None,headers={'Content-Type':'application/json'})
            with urllib.request.urlopen(req) as response:return response.read()
        try:
            self.assertIn(b'queryOneHop',request('/workflows.js'))
            result=json.loads(request('/api/query',{'question':'MECE 分解问题','scenario':self.scenario['id']}))
            self.assertEqual(json.loads(request('/api/traces'))['items'][0]['trace_id'],result['trace_id'])
            self.assertEqual(len(json.loads(request('/api/overview'))['nodes']),6)
            self.assertEqual(json.loads(request('/api/trace?trace_id='+result['trace_id']))['context']['trace_id'],result['trace_id'])
            for payload in [{'question':''},{'question':'x','mode':'unknown'},{'question':'x','scenario':'不存在'},{'question':'x','evidence_k':100}]:
                with self.assertRaises(urllib.error.HTTPError):request('/api/query',payload)
            self.assertEqual(len(self.s.traces()['items']),1)
        finally:server.shutdown();server.server_close();thread.join()


if __name__=='__main__':unittest.main()
