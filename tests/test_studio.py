from __future__ import annotations
import copy
import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from unittest.mock import patch
import yaml

PROJECT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT/'gui/backend'))
from studio import Studio, StudioError, digest
from app import create_server
sys.path.insert(0,str(PROJECT))
from apply_update import apply
SOURCE='raw/accepted/source.md'

class StudioTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        for d in ['model','registry','raw/accepted']:(self.root/d).mkdir(parents=True)
        (self.root/SOURCE).write_text('# 标题\n\n## 结构化方法\n\n分解复杂问题，定位根因，开展验证。\n这是原始第二行。\n\nMECE 保证分解结构不重不漏。\n',encoding='utf-8')
        self.concept={'id':'MECE','define':'分解结构不重不漏','sources':[SOURCE],'ipo':{'input':['问题'],'process':{'steps':['分解']},'output':['结构']},'relations':{'references':['entity://逻辑树'],'related_to':['concept://分解']}}
        self.entity={'id':'逻辑树','define':'分解问题的图形工具','sources':[SOURCE],'relations':{'uses':['concept://MECE']}}
        self.scenario={'id':'如何分析和解决复杂问题','define':'定位问题根因','sources':[SOURCE],'composition':[{'phase':'分解','uses':['concept://MECE'],'rule':'先明确问题'}]}
        self.write_model('concepts',[self.concept,{'id':'分解','define':'整体拆成部分','sources':[SOURCE],'ipo':{'process':{'steps':['拆分']}},'relations':{}},{'id':'无关联','define':'正文提到 MECE 但没有引用关系','sources':[SOURCE],'ipo':{'process':{'steps':['描述']}}}])
        self.write_model('entities',[self.entity,{'id':'MECE','define':'同名不同类型','sources':[SOURCE],'relations':{'uses':['concept://分解']}}])
        self.write_model('scenarios',[self.scenario])
        manifest={'sources':[{'path':SOURCE,'status':'accepted','sha256':digest((self.root/SOURCE).read_bytes())}]}
        (self.root/'registry/source_manifest.yaml').write_text(yaml.safe_dump(manifest),encoding='utf-8');self.s=Studio(self.root)
    def tearDown(self):self.temp.cleanup()
    def write_model(self,kind,items):
        (self.root/f'model/{kind}.yaml').write_text('# model header remains\n'+yaml.safe_dump({'version':'2.0',kind:items},allow_unicode=True,sort_keys=False),encoding='utf-8')
    def payload(self,ref):
        d=self.s.detail(ref);node=copy.deepcopy(d['node']);node['define']+='，更新描述';return {'node':node,'revision':d['revision']}
    def test_explicit_graph_excludes_free_text_and_distinguishes_same_id(self):
        refs={n['ref'] for n in self.s.graph('concept://MECE',1,direction='outgoing')['nodes']}
        self.assertEqual(refs,{'concept://MECE','entity://逻辑树','concept://分解'})
        self.assertIn('scenario://如何分析和解决复杂问题',{n['ref'] for n in self.s.graph('concept://MECE',1,direction='incoming')['nodes']})
    def test_graph_filters_depth_limit_and_original_arrows(self):
        g=self.s.graph('scenario://如何分析和解决复杂问题',2,direction='outgoing',kinds=['concept'],relations=['uses'])
        self.assertEqual(len(g['nodes']),2);self.assertEqual(g['edges'][0]['source'],'scenario://如何分析和解决复杂问题')
        self.assertTrue(self.s.graph('concept://MECE',2,max_nodes=2)['truncated'])
        with self.assertRaises(StudioError):self.s.graph('concept://MECE',depth=9)
    def test_multihop_returns_real_two_hop_fields_and_no_cycle(self):
        p=self.s.multihop({'start_ref':'scenario://如何分析和解决复杂问题','target_ref':'entity://逻辑树','direction':'outgoing','max_depth':3})
        self.assertEqual(p['status'],'paths_found');path=p['paths'][0]
        self.assertEqual(path['refs'],['scenario://如何分析和解决复杂问题','concept://MECE','entity://逻辑树'])
        self.assertEqual([s['field'] for s in path['steps']],['composition[0].uses[0]','relations.references[0]'])
        self.assertEqual(len(path['refs']),len(set(path['refs'])));self.assertTrue(path['evidence'])
        self.assertTrue(all(e['status']=='candidate_unconfirmed' for e in path['evidence']))
    def test_reverse_is_labeled_disconnected_and_depth_limited(self):
        p=self.s.multihop({'start_ref':'concept://MECE','target_ref':'scenario://如何分析和解决复杂问题'})
        self.assertEqual(p['paths'][0]['steps'][0]['traversal'],'reverse')
        self.assertEqual(self.s.multihop({'start_ref':'concept://MECE','target_ref':'concept://无关联'})['status'],'no_path')
        self.assertEqual(self.s.multihop({'start_ref':'scenario://如何分析和解决复杂问题','target_ref':'entity://逻辑树','max_depth':1})['status'],'no_path')
        with self.assertRaises(StudioError):self.s.multihop({'query':''})
    def test_evidence_exact_lines_section_stable_id(self):
        p=self.s.evidence('concept://MECE')['candidates'][0];lines=(self.root/SOURCE).read_text().splitlines()
        self.assertEqual(p['text'],'\n'.join(lines[p['line_start']-1:p['line_end']]));self.assertEqual(p['section'],'标题 / 结构化方法')
        self.assertEqual(self.s.locate(p['evidence_id'])['text'],p['text'])
        (self.root/SOURCE).write_text('新增说明\n\n'+(self.root/SOURCE).read_text(),encoding='utf-8')
        self.assertIn(p['evidence_id'],[x['evidence_id'] for x in self.s.source_index(SOURCE)['paragraphs']])
    def test_confirm_repeat_unbind_and_source_changes_are_stale(self):
        ev=self.s.evidence('concept://MECE');p=ev['candidates'][0]
        payload={'ref':'concept://MECE','evidence_id':p['evidence_id'],'source_sha256':p['source_sha256'],'revision':ev['binding_revision']};self.s.bind(payload)
        with self.assertRaises(StudioError) as caught:self.s.bind(payload)
        self.assertEqual(caught.exception.status,409)
        payload['revision']=self.s.evidence('concept://MECE')['binding_revision'];self.s.bind(payload)
        self.assertEqual(len(self.s.evidence('concept://MECE')['confirmed']),1)
        (self.root/SOURCE).write_text((self.root/SOURCE).read_text()+'\n原文变化\n',encoding='utf-8')
        self.assertEqual(self.s.evidence('concept://MECE')['confirmed'][0]['status'],'stale')
        self.s.unbind({'ref':'concept://MECE','evidence_id':p['evidence_id'],'revision':self.s.evidence('concept://MECE')['binding_revision']})
        self.assertEqual(self.s.evidence('concept://MECE')['confirmed'],[])
    def test_source_paths_reject_escape_and_symlink(self):
        outside=self.root/'outside.md';outside.write_text('outside')
        for path in ['../outside.md','raw/accepted/../../outside.md']:
            with self.assertRaises(StudioError):self.s.source_index(path)
        try:(self.root/'raw/accepted/link.md').symlink_to(outside)
        except OSError:return  # Windows may require administrator rights for symlinks.
        with self.assertRaises(StudioError):self.s.source_index('raw/accepted/link.md')
    def test_each_kind_saves_preserves_others_repeats_and_rolls_back(self):
        for ref in ['concept://MECE','entity://逻辑树','scenario://如何分析和解决复杂问题']:
            kind=ref.split('://')[0];path=self.s.model_path(kind);before=path.read_bytes();payload=self.payload(ref)
            preview=self.s.preview(ref,payload)[0];payload['preview_token']=preview['preview_token'];r=self.s.save(ref,payload)
            self.assertEqual(r['status'],'saved');self.assertTrue(path.read_text().startswith('# model header remains'))
            original=yaml.safe_load(before);changed=yaml.safe_load(path.read_bytes());key={'concept':'concepts','entity':'entities','scenario':'scenarios'}[kind]
            self.assertEqual(changed[key][1:],original[key][1:]);self.assertEqual(self.s.find(ref)['data'],payload['node'])
            repeat=dict(payload,revision=r['revision']);repeat['preview_token']=self.s.preview(ref,repeat)[0]['preview_token']
            self.assertEqual(self.s.save(ref,repeat)['status'],'unchanged')
            self.s.rollback({'backup_id':r['backup_id'],'revision':r['revision']});self.assertEqual(before,path.read_bytes())
    def test_preview_required_and_revision_conflict_never_writes(self):
        ref='concept://MECE';payload=self.payload(ref);path=self.s.model_path('concept');before=path.read_bytes()
        with self.assertRaises(StudioError):self.s.save(ref,payload)
        payload['preview_token']=self.s.preview(ref,payload)[0]['preview_token'];path.write_bytes(before+b'\n# external editor\n');modified=path.read_bytes()
        with self.assertRaises(StudioError) as error:self.s.save(ref,payload)
        self.assertEqual(error.exception.status,409);self.assertEqual(path.read_bytes(),modified)
    def test_invalid_shapes_and_broken_refs_never_modify(self):
        ref='concept://MECE';payload=self.payload(ref);before=self.s.model_path('concept').read_bytes()
        for change in [{'id':'新 ID'},{'sources':['raw/accepted/unknown.md']},{'relations':{'related_to':['concept://不存在']}},{'ipo':{'process':'bad'}},{'decomposition':['bad']}]:
            p=copy.deepcopy(payload);p['node'].update(change)
            with self.assertRaises(StudioError):self.s.preview(ref,p)
        self.assertEqual(before,self.s.model_path('concept').read_bytes())
    def test_rollback_protects_later_changes_failed_replace_is_atomic(self):
        ref='concept://MECE';payload=self.payload(ref);payload['preview_token']=self.s.preview(ref,payload)[0]['preview_token'];r=self.s.save(ref,payload)
        path=self.s.model_path('concept');path.write_bytes(path.read_bytes()+b'\n# later\n')
        with self.assertRaises(StudioError):self.s.rollback({'backup_id':r['backup_id'],'revision':digest(path.read_bytes())})
        before=path.read_bytes();payload=self.payload(ref);payload['preview_token']=self.s.preview(ref,payload)[0]['preview_token'];original_replace=__import__('os').replace
        def fail(src,dst):
            if Path(dst)==path:raise OSError('simulated disk failure')
            return original_replace(src,dst)
        with patch('studio.os.replace',side_effect=fail):
            with self.assertRaises(OSError):self.s.save(ref,payload)
        self.assertEqual(before,path.read_bytes());self.assertFalse(list(path.parent.glob('.studio-*')))
    def test_overlay_keeps_user_data_git_and_is_idempotent(self):
        source=self.root/'update-source';target=self.root/'update-target'
        for d in ['model','raw/accepted','registry','runs','eval','gui/backend']:(source/d).mkdir(parents=True)
        target.mkdir();(target/'model').mkdir();(target/'.git').mkdir();(target/'.git/config').write_text('git state')
        (target/'model/concepts.yaml').write_text('local edits');(source/'model/concepts.yaml').write_text('baseline')
        (source/'gui/backend/app.py').write_text('new program');(source/'registry/gui_evidence.yaml').write_text('new registry')
        first=apply(source,target)
        self.assertEqual((target/'model/concepts.yaml').read_text(),'local edits')
        self.assertEqual((target/'.git/config').read_text(),'git state')
        self.assertEqual((target/'gui/backend/app.py').read_text(),'new program')
        second=apply(source,target);self.assertEqual(second['updated'],0);self.assertEqual(second['created'],0)
        with self.assertRaises(ValueError):apply(source,source/'nested')

    def test_http_assets_unicode_edit_and_input_guards(self):
        server=create_server(self.root,0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();address=f'http://127.0.0.1:{server.server_address[1]}'
        def request(path,payload=None,headers=None):
            req=urllib.request.Request(address+path,data=json.dumps(payload,ensure_ascii=False).encode() if payload is not None else None,headers={'Content-Type':'application/json'}|(headers or {}))
            with urllib.request.urlopen(req) as r:return r.status,r.read()
        try:
            self.assertEqual(request('/')[0],200);self.assertIn(b'Knowledge Studio',request('/')[1]);self.assertEqual(json.loads(request('/api/status')[1])['version'],'1.3.0')
            payload=self.payload('concept://MECE');payload['preview_token']=json.loads(request('/api/preview/concept/MECE',payload)[1])['preview_token']
            self.assertEqual(json.loads(request('/api/save/concept/MECE',payload)[1])['status'],'saved')
            self.assertEqual(json.loads(request('/api/node/entity/'+urllib.parse.quote('逻辑树',safe=''))[1])['id'],'逻辑树')
            for path,payload,headers in [('/api/save/concept/MECE',{}, {'Origin':'https://evil.example'}),('/api/model/nope',None,{}),('/api/multihop',[],{}),('/unknown',None,{})]:
                with self.assertRaises(urllib.error.HTTPError) as e:request(path,payload,headers)
                self.assertIn(e.exception.code,[400,403,404,422])
        finally:server.shutdown();server.server_close();thread.join()

if __name__=='__main__':unittest.main()
