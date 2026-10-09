"""Real workflow checks using isolated projects, not the shipped knowledge."""
import copy
import json
import subprocess
import sys
import threading
import unittest
import urllib.request
from unittest.mock import patch
import test_studio as fixtures
from kb_build import KnowledgeBuild, BuildError
from kb_evidence import digest


class KnowledgeBuildTests(unittest.TestCase):
    setUp = fixtures.StudioTests.setUp
    tearDown = fixtures.StudioTests.tearDown
    write_model = fixtures.StudioTests.write_model

    def build(self): return KnowledgeBuild(self.s)
    def call(self, action, **payload): return self.build().execute(action, payload)

    def setup_job(self):
        self.source_text = '# 新资料\n\nMECE 分解结构相互独立、完全穷尽。\n\n分解先确定维度，再检查粒度。\n'
        r = self.call('sources.import', name='新增.md', text=self.source_text)
        self.source_id = r['source']['source_id']
        r = self.call('sources.admit', source_id=self.source_id, decision='accepted',
                      revision=self.call('sources.list')['revision'], source_sha256=r['source']['sha256'])
        self.source_path = r['source']['path']
        j = self.call('jobs.create', source_ids=[self.source_id])
        j = self.call('jobs.extract', job_id=j['job_id'], revision=j['revision'], observations=[{
            'kind':'concept','id':'MECE','define':'分解结构不重不漏','evidence':[
                {'source_id':self.source_id,'line_start':3,'line_end':3,'excerpt':self.source_text.splitlines()[2]}]}])
        self.job_id = j['job_id']; return j

    def proposal(self, action='evidence', ref='concept://MECE', node=None, field='define'):
        value={'action':action,'target_ref':ref,'observation_ids':['obs-0001'],
               'supports':[{'source_id':self.source_id,'line_start':3,'line_end':3,
                            'excerpt':self.source_text.splitlines()[2],'support_field':field}], 'reason':'补充明确原文依据'}
        if node is not None:value['node']=node
        return value

    def submit(self, proposals):
        j=self.call('jobs.get',job_id=self.job_id)
        return self.call('jobs.compare',job_id=self.job_id,revision=j['revision'],proposals=proposals)

    def approve(self, proposal_id='candidate-0001'):
        j=self.call('jobs.get',job_id=self.job_id)
        return self.call('jobs.review',job_id=self.job_id,revision=j['revision'],proposal_id=proposal_id,decision='approved')

    def publish(self):
        p=self.call('jobs.preview',job_id=self.job_id)
        return self.call('jobs.publish',job_id=self.job_id,preview_token=p['preview_token'])

    def test_import_duplicate_admission_and_scan_repeat(self):
        manifest = self.root/'registry/source_manifest.yaml'
        value = fixtures.yaml.safe_load(manifest.read_text());value['sources'][0]['author'] = '保留来源元数据'
        manifest.write_text(fixtures.yaml.safe_dump(value, allow_unicode=True))
        j=self.setup_job()
        self.assertEqual(self.call('sources.import',name='重复.txt',text=self.source_text)['status'],'duplicate')
        self.assertFalse((self.root/'raw/inbox/重复.txt').exists())
        self.assertFalse((self.root/'raw/inbox/新增.md').exists())
        self.call('sources.scan'); before={p:p.read_bytes() for p in (self.root/'registry').glob('*.yaml')}
        self.call('sources.scan')
        self.assertTrue(all(p.read_bytes()==data for p,data in before.items()))
        self.assertEqual(self.call('sources.read',source_id=self.source_id)['text'],self.source_text)
        self.assertEqual(fixtures.yaml.safe_load(manifest.read_text())['sources'][0]['author'], '保留来源元数据')

    def test_two_round_packets_and_false_evidence_rejected(self):
        j=self.setup_job(); (self.root/'application').mkdir();(self.root/'application/build-rubric.md').write_text('判据')
        packet=self.call('jobs.packet',job_id=j['job_id'],phase='comparison')
        self.assertEqual(packet['source_documents'][0]['text'],self.source_text)
        self.assertTrue(packet['catalog']);self.assertTrue(packet['observations'])
        p=self.proposal();p['supports'][0]['excerpt']='伪造原文'
        before=self.s.model_path('concept').read_bytes()
        with self.assertRaises(BuildError):self.submit([p])
        self.assertEqual(self.s.model_path('concept').read_bytes(),before)

    def test_review_publish_shared_evidence_and_repeat(self):
        self.setup_job();before=self.s.find('concept://MECE')['data'];self.submit([self.proposal()])
        self.assertEqual(self.s.find('concept://MECE')['data'],before)
        with self.assertRaises(BuildError):self.call('jobs.preview',job_id=self.job_id)
        self.approve();preview=self.call('jobs.preview',job_id=self.job_id)
        self.assertIn('model/concepts.yaml',preview['files'])
        with self.assertRaises(BuildError):self.call('jobs.publish',job_id=self.job_id,preview_token='old')
        result=self.publish();self.assertEqual(result['status'],'completed')
        self.assertIn(self.source_path,self.s.find('concept://MECE')['data']['sources'])
        self.assertTrue(any(r.get('build_job')==self.job_id for r in self.s.evidence('concept://MECE')['confirmed']))
        self.assertEqual(self.call('sources.read',source_id=self.source_id)['processing'],'processed')
        before=self.s.model_path('concept').read_bytes();self.assertTrue(self.publish()['unchanged'])
        self.assertEqual(self.s.model_path('concept').read_bytes(),before)

    def test_comparison_cannot_silently_drop_observations(self):
        j = self.setup_job()
        with self.assertRaisesRegex(BuildError, '尚未全部比较'):
            self.call('jobs.compare', job_id=j['job_id'], revision=j['revision'], proposals=[], note='跳过')
        self.submit([{'action': 'ignore', 'observation_ids': ['obs-0001'], 'reason': '本轮不重复收录'}])
        self.approve(); before = self.s.model_path('concept').read_bytes(); self.publish()
        self.assertEqual(self.s.model_path('concept').read_bytes(), before)

    def test_multiple_support_fields_and_scoped_unbind(self):
        self.setup_job(); p = self.proposal()
        p['supports'].append(dict(p['supports'][0], support_field='ipo'))
        self.submit([p]); self.approve(); self.publish()
        r = self.s.evidence('concept://MECE')
        records = [e for e in r['confirmed'] if e.get('build_job') == self.job_id]
        self.assertEqual({e['support_field'] for e in records}, {'define', 'ipo'})
        self.s.unbind({'ref': 'concept://MECE', 'evidence_id': records[0]['evidence_id'],
                       'support_field': 'define', 'revision': r['binding_revision']})
        self.assertEqual([e['support_field'] for e in self.s.evidence('concept://MECE')['confirmed']], ['ipo'])

    def test_identical_comparison_preserves_review_and_unrelated_yaml_bytes(self):
        self.setup_job(); proposals = [self.proposal()]; self.submit(proposals); self.approve()
        j = self.submit(proposals); self.assertTrue(j['unchanged'])
        self.assertEqual(j['proposals'][0]['review']['decision'], 'approved')
        before = self.s.model_path('concept').read_bytes()
        from kb_build import render_nodes
        old = self.s.find('concept://MECE')['data']; updated = copy.deepcopy(old); updated['define'] += '增量'
        result = render_nodes(before, 'concepts', {'MECE': updated}, [])
        # Replacing one entry preserves the existing file header and trailing node.
        self.assertEqual(result[:result.index(b'- id: MECE')], before[:before.index(b'- id: MECE')])
        marker = '- id: 分解'.encode()
        self.assertEqual(result[result.index(marker):], before[before.index(marker):])
        self.assertEqual(render_nodes(b'\xef\xbb\xbf' + before, 'concepts', {'MECE': updated}, []), b'\xef\xbb\xbf' + result)
        empty = b'# empty model header\nversion: 2.0\nconcepts: [] # list\n# trailing note\n'
        first = render_nodes(empty, 'concepts', {}, [updated])
        self.assertTrue(first.startswith(b'# empty model header\nversion: 2.0\nconcepts: # list\n'))
        self.assertTrue(first.endswith(b'# trailing note\n'))
        self.publish()

    def test_new_nodes_same_batch_refs_and_unapproved_dependency(self):
        self.setup_job()
        node={'id':'新分解','define':'分解结构不重不漏','sources':[], 'ipo':{'process':{'steps':['分解']}},
              'relations':{'uses':['entity://新工具']}}
        entity={'id':'新工具','define':'分解结构工具','sources':[], 'relations':{'references':['concept://新分解']}}
        self.submit([self.proposal('new','concept://新分解',node),self.proposal('new','entity://新工具',entity)])
        self.approve()
        with self.assertRaises(fixtures.StudioError):self.call('jobs.preview',job_id=self.job_id)
        self.approve('candidate-0002');self.publish()
        self.assertEqual(self.s.find('concept://新分解')['data']['relations']['uses'],['entity://新工具'])

    def test_source_and_model_changes_block_stale_publication(self):
        self.setup_job();self.submit([self.proposal()]);self.approve();p=self.call('jobs.preview',job_id=self.job_id)
        (self.root/self.source_path).write_text(self.source_text+'\n修改\n')
        self.assertTrue(self.call('jobs.get',job_id=self.job_id)['freshness_issues'])
        with self.assertRaises(BuildError):self.call('jobs.publish',job_id=self.job_id,preview_token=p['preview_token'])
        (self.root/self.source_path).write_text(self.source_text)
        data=self.s.model_path('entity').read_bytes();self.s.model_path('entity').write_bytes(data+'\n# 修改\n'.encode())
        with self.assertRaises(BuildError):self.publish()

    def test_source_changes_and_missing_are_visible_without_scanning(self):
        self.setup_job();self.submit([self.proposal()]);self.approve();self.publish()
        (self.root/self.source_path).write_text('新版本')
        r=self.call('sources.read',source_id=self.source_id)
        self.assertEqual(r['processing'],'needs_update');self.assertIn('concept://MECE',r['linked_nodes'])
        (self.root/self.source_path).unlink()
        r=next(r for r in self.call('sources.list')['items'] if r['source_id']==self.source_id)
        self.assertTrue(r['missing']);self.assertEqual(r['processing'],'needs_update')

    def test_rejections_and_empty_job_can_complete_without_changing_models(self):
        self.setup_job();self.submit([self.proposal()]);j=self.call('jobs.get',job_id=self.job_id)
        self.call('jobs.review',job_id=self.job_id,revision=j['revision'],proposal_id='candidate-0001',decision='rejected',note='原文不充分')
        before=self.s.model_path('concept').read_bytes();self.publish()
        self.assertEqual(self.s.model_path('concept').read_bytes(),before)
        self.assertEqual(self.call('sources.read',source_id=self.source_id)['processing'],'processed')
        j=self.call('jobs.create',source_ids=[self.source_id]);self.job_id=j['job_id']
        j=self.call('jobs.extract',job_id=self.job_id,revision=j['revision'],observations=[],note='没有有效知识')
        self.call('jobs.compare',job_id=self.job_id,revision=j['revision'],proposals=[],note='无变化')
        self.assertEqual(self.publish()['status'],'completed')

    def test_partial_publish_conflict_hold_then_close(self):
        self.setup_job();self.submit([self.proposal(),{'action':'conflict','observation_ids':['obs-0001'],'reason':'存在不同解释'}])
        self.approve();r=self.publish();self.assertEqual(r['status'],'partial_published')
        self.assertNotEqual(self.call('sources.read',source_id=self.source_id)['processing'],'processed')
        with self.assertRaises(BuildError):self.approve('candidate-0002')
        j=self.call('jobs.get',job_id=self.job_id)
        self.call('jobs.review',job_id=self.job_id,revision=j['revision'],proposal_id='candidate-0002',decision='rejected',note='本轮不采纳冲突说法')
        self.assertEqual(self.publish()['status'],'completed')

    def test_merge_records_alias_and_keeps_identity(self):
        self.setup_job();p=self.proposal('merge');p['aliases']=['不重不漏原则'];self.submit([p]);self.approve();self.publish()
        catalog=self.call('catalog');self.assertIn({'canonical':'concept://MECE','variants':['不重不漏原则']},catalog['aliases'])
        self.assertEqual(self.s.find('concept://MECE')['data']['id'],'MECE')

    def test_failure_compensates_and_retry_publishes(self):
        self.setup_job();self.submit([self.proposal()]);self.approve()
        from kb_build import atomic_write
        original=self.s.model_path('concept').read_bytes()
        def failing(path,data):
            if str(path).endswith('registry/gui_evidence.yaml'):raise OSError('模拟磁盘失败')
            return atomic_write(path,data)
        with patch('kb_build.atomic_write',side_effect=failing):
            with self.assertRaises(OSError):self.publish()
        self.assertEqual(self.s.model_path('concept').read_bytes(),original)
        self.assertEqual(self.call('jobs.get',job_id=self.job_id)['status'],'review_required')
        self.assertEqual(self.publish()['status'],'completed')

    def test_recover_prepared_journal_and_refuse_external_overwrite(self):
        b=self.build();pub='pub-'+'a'*16;folder=self.root/'runs/build/knowledge/publications'/pub;folder.mkdir(parents=True)
        path=self.root/'registry/recovery.txt';path.write_bytes(b'after');(folder/'0.before').write_bytes(b'before')
        plan={'publication_id':pub,'status':'prepared','files':[{'path':'registry/recovery.txt','before':digest(b'before'),'after':digest(b'after')}]}
        (folder/'manifest.json').write_text(json.dumps(plan))
        with self.assertRaises(BuildError):self.call('sources.scan')
        with self.assertRaisesRegex(ValueError, '未完成写入'):self.s.bind({})
        path.write_bytes(b'external')
        with self.assertRaises(BuildError):self.call('publications.recover',publication_id=pub)
        self.assertEqual(path.read_bytes(),b'external')
        path.write_bytes(b'after');self.call('publications.recover',publication_id=pub);self.assertEqual(path.read_bytes(),b'before')

    def test_path_revision_and_lock_guards(self):
        with self.assertRaises(BuildError):self.call('sources.import',name='../evil.md',text='x')
        for name in ['CON.txt', 'nul.md', 'bad\x00.md']:
            with self.assertRaises(BuildError):self.call('sources.import',name=name,text='x')

        (self.root/'raw/inbox').mkdir();outside=self.root.parent/'outside-build.txt';outside.write_text('外部资料')
        try:
            (self.root/'raw/inbox/link.md').symlink_to(outside)
            with self.assertRaises(BuildError):self.call('sources.list')
        finally:outside.unlink();(self.root/'raw/inbox/link.md').unlink()
        self.setup_job();j=self.call('jobs.get',job_id=self.job_id)
        with self.assertRaises(BuildError):self.call('jobs.compare',job_id=self.job_id,revision='stale',proposals=[])
        (self.root/'registry/.knowledge-write.lock').write_text('existing')
        with self.assertRaises(ValueError):self.call('sources.scan')
        (self.root/'registry/.knowledge-write.lock').unlink()

    def test_legacy_inventory_and_status_share_admission_and_text_counts(self):
        (self.root / 'VERSION').write_text('1.5.0')
        r = self.call('sources.import', name='接入.txt', text='文本来源')
        self.call('sources.admit', source_id=r['source']['source_id'], decision='accepted',
                  revision=self.call('sources.list')['revision'], source_sha256=r['source']['sha256'])
        r = self.call('sources.import', name='拒绝.md', text='不纳入资料')
        self.call('sources.admit', source_id=r['source']['source_id'], decision='rejected',
                  revision=self.call('sources.list')['revision'], source_sha256=r['source']['sha256'])
        project = fixtures.PROJECT
        result = subprocess.run([sys.executable, str(project/'scripts/inventory_sources.py'), str(self.root)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.call('sources.read', source_id=r['source']['source_id'])['admission'], 'rejected')
        result = subprocess.run([sys.executable, str(project/'scripts/project_status.py'), str(self.root), '--json'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['accepted_sources'], 2)

    def test_cli_and_http_share_same_operations(self):
        cmd=[sys.executable,str(fixtures.PROJECT/'scripts/kb_manage.py'),'tools','--project',str(self.root)]
        result=subprocess.run(cmd,capture_output=True,text=True,check=True)
        self.assertTrue(any(t['name']=='jobs.compare' for t in json.loads(result.stdout)['operations']))
        server=fixtures.create_server(self.root,0);thread=threading.Thread(target=server.serve_forever);thread.start()
        try:
            base=f'http://127.0.0.1:{server.server_address[1]}'
            req=urllib.request.Request(base+'/api/build/sources.import',data=json.dumps({'name':'HTTP.md','text':'HTTP 导入原文'}).encode(),headers={'Content-Type':'application/json'})
            source=json.load(urllib.request.urlopen(req))['source']
            self.assertEqual(self.call('sources.read',source_id=source['source_id'])['text'],'HTTP 导入原文')
        finally:server.shutdown();server.server_close();thread.join()


if __name__=='__main__':unittest.main()
