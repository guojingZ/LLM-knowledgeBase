// DOM/API integration harness. No rendering engine; not a browser screenshot test.
const fs=require('fs'),vm=require('vm'),assert=require('assert'),path=require('path');
const PROJECT=path.resolve(__dirname,'..');
const html=fs.readFileSync(path.join(PROJECT,'gui/frontend/index.html'),'utf8');
class Element {
 constructor(tag='div'){this.tagName=tag;this.children=[];this._text='';this.value='';this.dataset={};this.hidden=false;this.disabled=false;this.className='';this.attributes={};this.classList={toggle:(c,force)=>{const v=new Set(this.className.split(' ').filter(Boolean));if(force??!v.has(c))v.add(c);else v.delete(c);this.className=[...v].join(' ');}};}
 set textContent(v){this._text=String(v??'');this.children=[];}
 get textContent(){return this._text+this.children.map(x=>x.textContent||'').join('');}
 append(...xs){this.children.push(...xs);}
 replaceChildren(...xs){this._text='';this.children=xs;}
 setAttribute(k,v){this.attributes[k]=v;}
 showModal(){this.open=true;} close(){this.open=false;}
 click(){return this.onclick?.({target:this});}
}
const elements=new Map();for(const m of html.matchAll(/<([a-z]+)[^>]*\bid="([^"]+)"[^>]*>/g)){const e=new Element(m[1]);if(m[0].includes(' hidden'))e.hidden=true;if(m[0].includes(' disabled'))e.disabled=true;elements.set(m[2],e);}
for(const [id,value]of Object.entries({'graph-depth':'1','graph-direction':'both','graph-kind':'','graph-relation':'','path-depth':'3','path-direction':'both'}))elements.get(id).value=value;
const kindButtons=['scenario','concept','entity'].map(k=>{const b=new Element('button');b.dataset.kind=k;elements.get('kind-tabs').append(b);return b;});
const viewButtons=['browse','graph','paths'].map(k=>{const b=new Element('button');b.dataset.view=k;return b;});
const doc={getElementById:id=>elements.get(id),createElement:tag=>new Element(tag),createElementNS:(_,tag)=>new Element(tag),querySelectorAll:selector=>selector.includes('kind-tabs')?kindButtons:selector.includes('main-tabs')?viewButtons:[]};
const errors=[];const sandbox={document:doc,Option:function(t,v){const n=new Element('option');n.textContent=t;n.value=v;return n;},window:{addEventListener(){}},location:{hash:''},fetch:(path,args)=>fetch((process.env.QA_ADDRESS||'http://127.0.0.1:8794')+path,args),console,setTimeout,clearTimeout,URL,URLSearchParams,Blob};
const context=vm.createContext(sandbox);vm.runInContext(fs.readFileSync(path.join(PROJECT,'gui/frontend/main.js'),'utf8'),context);
const $=id=>elements.get(id);const state=()=>vm.runInContext('state',context);
async function waitFor(predicate,label){const start=Date.now();while(!predicate()){if(Date.now()-start>30000)throw Error('Timeout: '+label+' / '+$('notice').textContent);await new Promise(r=>setTimeout(r,50));}}
async function clickText(root,text){const visit=n=>n.tagName==='button'&&n._text===text?n:n.children.map(visit).find(Boolean);const b=visit(root);assert(b,'Missing button '+text);await b.click();return b;}
(async()=>{
 await waitFor(()=>state().evidence&&$('metrics').children.length===4,'initial data');assert.equal($('node-list').children.length,17);
 await vm.runInContext("selectNode('concept://MECE')",context);assert.equal(state().current.ref,'concept://MECE');assert($('node-content').textContent.includes('IPO'));assert(state().evidence.candidates.length>0);
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
 console.log(JSON.stringify({ok:true,checks:['all nodes','node/IPO view','evidence context','confirm/unconfirm','edit preview/save','history rollback','two-hop SVG/fields','multi-hop explanations','out-of-scope abstention','search retains full navigation','unsaved edit guard'],visual_rendering:false},null,2));
})().catch(e=>{console.error(e);process.exitCode=1;});
