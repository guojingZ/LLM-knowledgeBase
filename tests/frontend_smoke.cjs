// DOM/API integration harness. No rendering engine; not a browser screenshot test.
const fs=require('fs'),vm=require('vm'),assert=require('assert'),path=require('path');
const PROJECT=path.resolve(__dirname,'..');
const html=fs.readFileSync(path.join(PROJECT,'gui/frontend/index.html'),'utf8');
class Element {
 constructor(tag='div'){this.tagName=tag;this.children=[];this._text='';this.value='';this.dataset={};this.hidden=false;this.disabled=false;this.className='';this.attributes={};this.style={};this.classList={toggle:(c,force)=>{const v=new Set(this.className.split(' ').filter(Boolean));if(force??!v.has(c))v.add(c);else v.delete(c);this.className=[...v].join(' ');}};}
 set textContent(v){this._text=String(v??'');this.children=[];}
 get textContent(){return this._text+this.children.map(x=>x.textContent||'').join('');}
 append(...xs){this.children.push(...xs);if(this.tagName==='select'&&!this.value)this.value=this.children[0]?.value||'';}
 prepend(...xs){this.children.unshift(...xs);}
 replaceChildren(...xs){this._text='';this.children=xs;}
 setAttribute(k,v){this.attributes[k]=v;}
 showModal(){this.open=true;} close(){this.open=false;}
 click(){return this.onclick?.({target:this});}
}
const elements=new Map();for(const m of html.matchAll(/<([a-z]+)[^>]*\bid="([^"]+)"[^>]*>/g)){const e=new Element(m[1]);if(m[0].includes(' hidden'))e.hidden=true;if(m[0].includes(' disabled'))e.disabled=true;elements.set(m[2],e);}
for(const [id,value]of Object.entries({'graph-depth':'1','graph-direction':'both','graph-kind':'','graph-relation':'','path-depth':'3','path-direction':'both','query-mode':'model-guided','query-scenario':'','support-field':'define','overview-relation':'core','overview-zoom':'100'}))elements.get(id).value=value;
const kindButtons=['scenario','concept','entity'].map(k=>{const b=new Element('button');b.dataset.kind=k;elements.get('kind-tabs').append(b);return b;});
const viewButtons=['construction','query','overview','runs','browse','graph','paths'].map(k=>{const b=new Element('button');b.dataset.view=k;return b;});
const overviewButtons=['graph','matrix','coverage'].map(k=>{const b=new Element('button');b.dataset.overview=k;return b;});
const doc={getElementById:id=>elements.get(id),createElement:tag=>new Element(tag),createElementNS:(_,tag)=>new Element(tag),querySelectorAll:selector=>selector.includes('kind-tabs')?kindButtons:selector.includes('main-tabs')?viewButtons:selector.includes('overview-tabs')?overviewButtons:[]};
const errors=[];const sandbox={document:doc,Option:function(t,v){const n=new Element('option');n.textContent=t;n.value=v;return n;},window:{addEventListener(){}},location:{hash:''},fetch:(path,args)=>fetch((process.env.QA_ADDRESS||'http://127.0.0.1:8794')+path,args),console,setTimeout,clearTimeout,URL,URLSearchParams,Blob};
const context=vm.createContext(sandbox);vm.runInContext(fs.readFileSync(path.join(PROJECT,'gui/frontend/main.js'),'utf8'),context);vm.runInContext(fs.readFileSync(path.join(PROJECT,'gui/frontend/workflows.js'),'utf8'),context);
vm.runInContext(fs.readFileSync(path.join(PROJECT,'gui/frontend/construction.js'),'utf8'),context);
const $=id=>elements.get(id);const state=()=>vm.runInContext('state',context);
async function waitFor(predicate,label){const start=Date.now();while(!predicate()){if(Date.now()-start>30000)throw Error('Timeout: '+label+' / '+$('notice').textContent);await new Promise(r=>setTimeout(r,50));}}
async function clickText(root,text){const visit=n=>n.tagName==='button'&&n._text===text?n:n.children.map(visit).find(Boolean);const b=visit(root);assert(b,'Missing button '+text);await b.click();return b;}
(async()=>{
 await waitFor(()=>state().all.length===414&&$('metrics').children.length===4,'initial data');assert.equal($('node-list').children.length,17);
 await vm.runInContext("openNode('concept://MECE')",context);assert.equal(state().current.ref,'concept://MECE');assert($('node-content').textContent.includes('IPO'));assert(state().evidence.candidates.length>0);
 const evidence=state().evidence.candidates[0];await vm.runInContext(`openEvidence('${evidence.evidence_id}')`,context);assert($('source-dialog').open);assert($('source-text').textContent.includes(evidence.text.split('\n')[0]));$('source-close').click();
 await clickText($('evidence-content'),'确认该段支持节点');assert.equal(state().evidence.confirmed.length,1);await clickText($('evidence-content'),'撤销确认');assert.equal(state().evidence.confirmed.length,0);
 $('edit-mode').click();const node=JSON.parse($('editor').value);node.define+='（前端验证）';$('editor').value=JSON.stringify(node,null,2);$('editor').oninput();assert(state().dirty);assert($('save').disabled);
 await $('preview').click();assert(!$('save').disabled);assert($('preview-result').textContent.includes('前端验证'));await $('save').click();assert(!state().dirty);assert(state().current.node.define.endsWith('（前端验证）'));
 await clickText($('history-list'),'回滚此保存');assert(!state().current.node.define.endsWith('（前端验证）'));
 $('graph-depth').value='2';await vm.runInContext('loadGraph()',context);assert($('graph-canvas').children[0].tagName==='svg');assert($('graph-edges').textContent.includes('relations.'));
 $('path-query').value='面对复杂业务故障时，如何定位根因？';await $('path-run').click();assert.equal(state().paths.status,'paths_found');assert(state().paths.paths.some(p=>p.steps.length>=2));assert($('path-results').textContent.includes('本步'));assert(!$('path-export').disabled);
 $('path-query').value='明天上海会不会下雨？';await $('path-run').click();assert.equal(state().paths.status,'no_evidence');assert.equal(state().paths.paths.length,0);
 $('search').value='MECE';$('search').oninput();await waitFor(()=>state().navigation!==null,'search');assert.equal(state().all.length,414);assert($('node-list').children.some(n=>n._text==='MECE'));
 // Unsaved-node navigation must retain edits until the user chooses to discard.
 $('edit-mode').click();$('editor').value+=' ';$('editor').oninput();const pending=vm.runInContext("selectNode('entity://逻辑树')",context);await waitFor(()=>$('discard-dialog').open,'discard modal');$('discard-cancel').click();await pending;assert.equal(state().current.ref,'concept://MECE');$('discard').click();
 // New v1.4 flow: one-hop is complete before any optional multi-hop query.
 $('query-question').value='面对复杂业务故障时，如何定位根因？';$('query-mode').value='model-guided';$('query-scenario').value='';
 await $('query-run').click();assert.equal(state().query.query_kind,'one_hop');assert(state().query.trace_id);assert(state().query.continuations.items.length);
 const pathBefore=state().paths;await clickText($('query-results'),'用此路径开始探索');assert.equal(state().view,'paths');assert.equal(state().paths,pathBefore);assert.equal($('path-direction').value,'outgoing');
 await vm.runInContext('loadTrace(state.query.trace_id)',context);assert.equal(state().view,'runs');assert.equal(state().trace.context.trace_id,state().query.trace_id);
 $('feedback-rating').value='partial';$('feedback-scenario').value='correct';$('feedback-evidence').value='partial';$('feedback-notes').value='还需要验证步骤的依据';
 await $('feedback-save').click();assert.equal(state().trace.feedback.rating,'partial');assert.equal(state().trace.feedback.model_updated,false);assert($('feedback-state').textContent.includes('待审'));
 $('trace-overlay').click();await waitFor(()=>state().overview&&$('overview-canvas').children.length,'global overview');assert.equal(state().overview.nodes.length,414);assert(state().highlightRefs.length);assert.equal($('overview-canvas').children[0].tagName,'svg');
 overviewButtons[1].click();assert.equal($('overview-matrix').children[0].tagName,'table');assert.equal($('overview-matrix').children[0].children[1].children.length,17);
 overviewButtons[2].click();assert.equal($('overview-coverage').children[0].children[1].children.length,414);
 // v1.5: exercise the actual UI events through review and incremental publication.
 await vm.runInContext("setView('construction')",context);
 await waitFor(()=>vm.runInContext('buildState.sources!==null',context),'construction inventory');
 assert.equal(vm.runInContext('buildState.sources.items.length',context),50);
 const raw='# GUI 新资料\n\nMECE 分解遵循相互独立、完全穷尽。\n';
 $('build-import-name').value='GUI-增量.md';$('build-import-text').value=raw;await $('build-import').click();
 assert($('build-sources').textContent.includes('待准入'));await clickText($('build-sources'),'准入');
 await clickText($('build-sources'),'GUI-增量.md');assert($('build-source-detail').textContent.includes(raw));
 const source=vm.runInContext("buildState.sources.items.find(s=>s.path.endsWith('GUI-增量.md'))",context);
 const tr=$('build-sources').children[0].children[1].children.find(r=>r.textContent.includes('GUI-增量.md'));
 const check=tr.children[0].children[0];check.checked=true;check.onchange();assert(!$('build-create').disabled);
 $('build-title').value='GUI 增量验证';await $('build-create').click();
 const job=()=>vm.runInContext('buildState.job',context);assert.equal(job().status,'awaiting_extraction');
 $('build-extract-json').value=JSON.stringify({observations:[{kind:'concept',id:'MECE',define:'分解不重不漏',evidence:[{source_id:source.source_id,line_start:3,line_end:3,excerpt:raw.split('\n')[2]}]}]});
 await $('build-extract-submit').click();assert.equal(job().status,'awaiting_comparison');
 $('build-compare-json').value=JSON.stringify({proposals:[{action:'evidence',target_ref:'concept://MECE',observation_ids:['obs-0001'],reason:'增补原文依据',supports:[{source_id:source.source_id,line_start:3,line_end:3,excerpt:raw.split('\n')[2],support_field:'define'}]}]});
 await $('build-compare-submit').click();assert.equal(job().status,'review_required');
 await clickText($('build-candidates'),'通过');await $('build-preview-button').click();assert(!$('build-publish').disabled);assert($('build-preview').textContent.includes('raw/accepted/GUI-增量.md'));
 await $('build-publish').click();assert.equal(job().status,'completed');
 await vm.runInContext("openNode('concept://MECE')",context);assert(state().current.node.sources.includes('raw/accepted/GUI-增量.md'));assert(state().evidence.confirmed.some(e=>e.support_field==='define'));
 await $('build-tools').click();assert($('build-agent-tools').textContent.includes('input_schema'));
 console.log(JSON.stringify({ok:true,checks:['all nodes','node/IPO view','evidence context','confirm/unconfirm','edit preview/save','history rollback','two-hop SVG/fields','multi-hop explanations','out-of-scope abstention','search retains full navigation','unsaved edit guard','one-hop context and preview isolation','trace replay','feedback sync','global graph all nodes','scenario matrix','field coverage','source import/admission/read','create two-round task','extract/compare result import','candidate review','incremental publish and shared evidence','Agent operation discovery'],visual_rendering:false},null,2));
})().catch(e=>{console.error(e);process.exitCode=1;});
