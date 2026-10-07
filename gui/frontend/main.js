'use strict';
const $ = id => document.getElementById(id);
const kindNames = {scenario:'场景', concept:'概念', entity:'实体'};
const relationNames = {uses:'使用', references:'引用', related_to:'相关', depends_on:'依赖', produces:'产生', contains:'包含', is_a:'属于', tools:'工具'};
let state = {query:null,overview:null,overviewMode:'graph',trace:null,highlightRefs:[],highlightEdges:[],kind:'scenario', view:'query', all:[], navigation:null, current:null, revision:null, original:'', preview:null, evidence:null, paths:null, dirty:false};
let requestId=0, searchTimer;
function el(tag, text, cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
function clear(n){n.replaceChildren();}
function tell(text, error=false){$('notice').hidden=false;$('notice').textContent=text;$('notice').className='notice'+(error?' error':'');}
async function api(path, payload){
 const response=await fetch(path,payload===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
 let value;try{value=await response.json();}catch{throw new Error('服务未返回有效 JSON，请检查终端。');}
 if(!response.ok)throw new Error(value.error||`HTTP ${response.status}`);return value;
}
function run(fn){return async(...args)=>{try{await fn(...args);}catch(e){tell(e.message,true);}};}
function endpoint(ref,action='node'){const at=ref.indexOf('://');return `/api/${action}/${ref.slice(0,at)}/${encodeURIComponent(ref.slice(at+3))}`;}
function refButton(ref){const b=el('button',ref.split('://').slice(1).join('://'),'ref-button');b.title=ref;b.onclick=run(()=>openNode(ref));return b;}
function badges(values){const n=el('div');for(const v of values||[])n.append(el('span',v,'badge'));return n;}
function renderList(){
 clear($('node-list'));const q=$('search').value.trim().toLocaleLowerCase();
 const nodes=(state.navigation||state.all).filter(n=>n.kind===state.kind);
 $('list-count').textContent=`${nodes.length} 个${kindNames[state.kind]}`;
 for(const n of nodes){const b=el('button',n.id,n.ref===state.current?.ref?'active':'');b.append(el('span',n.define,'small'));b.onclick=run(()=>openNode(n.ref));$('node-list').append(b);}
 if(!nodes.length)$('node-list').append(el('p','没有匹配节点','empty'));
}
async function init(){
 const [status,all]=await Promise.all([api('/api/status'),api('/api/search')]);state.all=all;state.navigation=null;state.overview=null;$('search').value='';
 clear($('metrics'));for(const [label,count] of [['场景',status.counts.scenario],['概念',status.counts.concept],['实体',status.counts.entity],['来源',status.sources]]){const n=el('div',undefined,'metric');n.append(el('strong',String(count)),el('span',label));$('metrics').append(n);}
 clear($('graph-relation'));$('graph-relation').append(new Option('全部关系',''));for(const r of status.relations)$('graph-relation').append(new Option(relationNames[r]||r,r));
 for(const id of ['path-start','path-target']){const old=$(id).value;clear($(id));$(id).append(new Option(id==='path-start'?'根据问题自动定位':'探索关联知识',''));for(const n of all)$(id).append(new Option(`${kindNames[n.kind]} · ${n.id}`,n.ref));$(id).value=old;}
 for(const id of ['query-scenario','feedback-expected']){const old=$(id).value;clear($(id));$(id).append(new Option(id==='query-scenario'?'根据问题自动选择':'不指定',''));for(const n of all.filter(n=>n.kind==='scenario'))$(id).append(new Option(n.id,n.id));$(id).value=old;}
 clear($('overview-relation'));$('overview-relation').append(new Option('隐藏一般相关关系','core'),new Option('全部关系',''));for(const r of status.relations)$('overview-relation').append(new Option(relationNames[r]||r,r));
 renderList();if(status.broken_references)tell(`发现 ${status.broken_references} 条断链，请先检查模型。`,true);
}
function setView(view){state.view=view;for(const v of ['query','overview','runs','browse','graph','paths'])$(v+'-view').hidden=v!==view;for(const b of document.querySelectorAll('.main-tabs button'))b.classList.toggle('active',b.dataset.view===view);if(view==='graph')run(loadGraph)();if(view==='overview')run(loadOverview)();if(view==='runs')run(loadRuns)();}
async function discardCheck(){if(!state.dirty)return true;const d=$('discard-dialog');d.showModal();return new Promise(resolve=>{const close=ok=>{d.close();$('discard-cancel').onclick=null;$('discard-confirm').onclick=null;d.oncancel=null;resolve(ok);};$('discard-cancel').onclick=()=>close(false);$('discard-confirm').onclick=()=>close(true);d.oncancel=e=>{e.preventDefault();close(false);};});}
async function selectNode(ref, force=false){
 if(!force&&ref===state.current?.ref)return;
 if(!force&&!(await discardCheck()))return;
 const ticket=++requestId;const detail=await api('/api/detail?ref='+encodeURIComponent(ref));if(ticket!==requestId)return;
 state.current=detail;state.kind=detail.kind;state.revision=detail.revision;state.original=JSON.stringify(detail.node,null,2);state.dirty=false;state.preview=null;
 $('editor').value=state.original;$('save').disabled=true;clear($('preview-result'));$('edit-state').textContent='';
 for(const b of document.querySelectorAll('#kind-tabs button'))b.classList.toggle('active',b.dataset.kind===state.kind);
 clear($('node-heading'));$('node-heading').append(el('span',`${kindNames[detail.kind]} · ${detail.node.type||detail.node.category||'知识节点'}`,'eyebrow'),el('h1',detail.id),badges(detail.node.tags));
 $('selection-label').textContent=ref;renderList();renderNode();renderSupportFields();editMode(false);
 $('evidence-content').replaceChildren(el('p','正在定位原文…','loading'));
 await Promise.all([loadEvidence('',ticket),loadHistory(ticket)]);if(state.view==='graph')await loadGraph();
}
function renderNode(){
 const root=$('node-content');clear(root);if(!state.current)return;const n=state.current.node;
 root.append(el('p',n.define,'definition'));
 function field(title,value){if(value===undefined||value===null||value===''||(Array.isArray(value)&&!value.length))return;const box=el('div',undefined,'field-block');box.append(el('h3',title));if(Array.isArray(value)){const ul=el('ul');for(const v of value)ul.append(el('li',typeof v==='string'?v:JSON.stringify(v)));box.append(ul);}else box.append(el('p',typeof value==='string'?value:JSON.stringify(value)));root.append(box);}
 field('触发条件',n.trigger);field('目标',n.goal);field('输入',n.inputs);field('输出',n.outputs);
 if(n.ipo){field('IPO · 输入',n.ipo.input);field('IPO · 处理步骤',n.ipo.process?.steps);field('IPO · 输出',n.ipo.output);}
 for(const part of n.composition||[]){const p=el('div',undefined,'phase');p.append(el('h3',part.phase));for(const r of part.uses||[])p.append(refButton(r));if(part.rule)p.append(el('p',part.rule));if(part.key_points){const ul=el('ul');for(const v of part.key_points)ul.append(el('li',v));p.append(ul);}root.append(p);}
 if(n.decomposition)field('分解结构',n.decomposition);
 const relationships=el('div',undefined,'field-block');relationships.append(el('h3','明确关系'));for(const [relation,targets]of Object.entries(n.relations||{})){const row=el('div');row.append(el('span',(relationNames[relation]||relation)+'：','muted'));for(const ref of targets)row.append(refButton(ref));relationships.append(row);}if(!Object.keys(n.relations||{}).length)relationships.append(el('p','场景通过阶段 uses 引用知识项。','muted'));root.append(relationships);
 const inbound=el('div',undefined,'field-block');inbound.append(el('h3',`被引用 · ${state.current.incoming.length} 条`));for(const ref of [...new Set(state.current.incoming.map(e=>e.source))])inbound.append(refButton(ref));root.append(inbound);
 const known=new Set(['id','define','type','category','tags','sources','trigger','goal','inputs','outputs','ipo','composition','decomposition','relations']);const extra=Object.fromEntries(Object.entries(n).filter(([k])=>!known.has(k)));if(Object.keys(extra).length){const d=el('details');d.append(el('summary','其他字段'),el('pre',JSON.stringify(extra,null,2)));root.append(d);}
}
function editMode(edit){$('node-content').hidden=edit;$('edit-panel').hidden=!edit;$('read-mode').classList.toggle('active',!edit);$('edit-mode').classList.toggle('active',edit);}
async function loadEvidence(query='',ticket=requestId){
 if(!state.current)return;const value=await api(endpoint(state.current.ref)+'/evidence?q='+encodeURIComponent(query));if(ticket!==requestId)return;state.evidence=value;renderEvidence();
}
function evidenceCard(p, canBind=false){
 const card=el('div',undefined,'evidence-card');const status=p.status==='confirmed'?'已人工确认':p.status==='stale'?'需重新审查':p.status==='needs_review'?'旧确认 · 待补充复核':'检索候选 · 未确认';card.append(el('span',status,'badge '+(p.status==='confirmed'?'confirmed':'warning')));
 card.append(el('div',p.section||'正文','muted'),el('div',`${p.source} · L${p.line_start}–${p.line_end}`,'muted'));
 card.append(el('p',p.text||p.reason||'原文已变化'));if(p.reason)card.append(el('p',p.reason,'muted'));if(p.support_field)card.append(el('p','支持范围：'+p.support_field,'muted'));if(p.review_note)card.append(el('p','确认理由：'+p.review_note,'muted'));for(const review of p.confirmed_for||[]){const row=el('div',undefined,'muted');row.append(refButton(review.ref),el('span','支持字段：'+review.support_field));card.append(row);}const actions=el('div',undefined,'evidence-actions');
 const open=el('button','定位原文');open.disabled=!p.evidence_id||((p.status==='stale'||p.status==='needs_review')&&!p.can_reconfirm);open.onclick=run(()=>openEvidence(p.evidence_id,p.source_sha256));actions.append(open);
 if(canBind||((p.status==='stale'||p.status==='needs_review')&&p.can_reconfirm&&state.view==='browse')){const bind=el('button',p.status==='candidate_unconfirmed'?'确认该段支持节点':'补充／重新确认');bind.onclick=run(async()=>{await api('/api/evidence/bind',{ref:state.current.ref,evidence_id:p.evidence_id,source_sha256:p.source_sha256,revision:state.evidence.binding_revision,node_revision:state.revision,support_field:$('support-field').value||'define',review_note:$('support-note').value});state.overview=null;tell('已确认所选支持范围，有效记录会参与检索。');await loadEvidence($('evidence-query').value);});actions.append(bind);}
 if(['confirmed','stale','needs_review'].includes(p.status)&&canBind===false&&state.evidence?.confirmed.some(x=>x.evidence_id===p.evidence_id)&&state.view==='browse'){const unbind=el('button','撤销确认');unbind.onclick=run(async()=>{await api('/api/evidence/unbind',{ref:state.current.ref,evidence_id:p.evidence_id,revision:state.evidence.binding_revision});state.overview=null;await loadEvidence($('evidence-query').value);tell('已撤销该段证据确认。');});actions.append(unbind);}
 card.append(actions);return card;
}
function renderEvidence(){
 const root=$('evidence-content');clear(root);const ev=state.evidence;
 root.append(el('h3','来源文件'));for(const s of ev.sources){const card=el('div',undefined,'source-card');const b=el('button',s.path.replace('raw/accepted/',''));b.onclick=run(()=>openSource(s.path));card.append(b);card.append(el('p',s.status==='available'?`${s.paragraphs} 个段落${s.manifest_hash_matches?'':' · 来源哈希与清单不一致，需复核'}`:s.error||s.status,'muted'));root.append(card);}
 if(ev.confirmed.length){root.append(el('h3','已登记证据'));for(const p of ev.confirmed)root.append(evidenceCard(p));}
 root.append(el('h3','相关段落候选'));for(const p of ev.candidates)root.append(evidenceCard(p,true));if(!ev.candidates.length)root.append(el('p','没有匹配段落，可调整关键词或查看全文。','empty'));
}
async function openEvidence(id,expectedHash){const p=await api('/api/evidence/'+encodeURIComponent(id));$('source-title').textContent=p.source.replace('raw/accepted/','');$('source-location').textContent=`${p.section||'正文'} · 证据 L${p.line_start}–${p.line_end} · ${p.evidence_id}${expectedHash&&expectedHash!==p.source_sha256?' · 当前来源与记录版本不同，请结合历史快照复核':''}`;clear($('source-text'));const lines=p.context.split('\n');for(let i=0;i<lines.length;i++){const number=p.context_start+i;const line=el(number>=p.line_start&&number<=p.line_end?'mark':'span',`${number.toString().padStart(4,' ')}  ${lines[i]}\n`);$('source-text').append(line);}$('source-dialog').showModal();}
async function openSource(path){const p=await api('/api/source?path='+encodeURIComponent(path));$('source-title').textContent=path.replace('raw/accepted/','');$('source-location').textContent=`全文 · ${p.line_count} 行 · SHA256 ${p.sha256.slice(0,16)}…`;$('source-text').textContent=p.text.split('\n').map((l,i)=>`${String(i+1).padStart(4,' ')}  ${l}`).join('\n');$('source-dialog').showModal();}
async function preview(){
 if(!state.current)return;let node;try{node=JSON.parse($('editor').value);}catch{throw new Error('JSON 格式无效，请先修正。');}
 const p=await api(endpoint(state.current.ref,'preview'),{node,revision:state.revision});state.preview={node,token:p.preview_token};$('save').disabled=!p.changed;
 const root=$('preview-result');clear(root);root.append(el('h3',p.changed?'检查通过 · 待保存':'没有内容变化'),el('p',`修改可能影响 ${p.impact.nodes.length} 个引用节点 / ${p.impact.incoming_edges} 条入向引用。`,'muted'));
 for(const n of p.impact.nodes)root.append(refButton(n.ref));if(p.diff)root.append(el('pre',p.diff));
}
async function save(){
 if(!state.preview||!state.current)return;const result=await api(endpoint(state.current.ref,'save'),{node:state.preview.node,revision:state.revision,preview_token:state.preview.token});tell(result.status==='saved'?'已写入正式模型，并创建可校验备份。':'内容未变化。');const ref=state.current.ref;await init();await selectNode(ref,true);
}
async function loadHistory(ticket=requestId){if(!state.current)return;const rows=await api('/api/history?ref='+encodeURIComponent(state.current.ref));if(ticket!==requestId)return;const root=$('history-list');clear(root);if(!rows.length)root.append(el('p','暂无工作台保存记录。','muted'));for(const h of rows){const n=el('div',undefined,'history-row');n.append(el('span',h.created_at,'muted'));const b=el('button','回滚此保存');b.disabled=h.after!==state.revision;b.title=b.disabled?'模型已有后续修改，禁止整文件回滚。':'仅回滚该保存，后续版本冲突会被拒绝。';b.onclick=run(async()=>{if(!(await discardCheck()))return;await api('/api/rollback',{backup_id:h.backup_id,revision:state.revision});tell('已恢复该次保存前的文件。');const ref=state.current.ref;await init();await selectNode(ref,true);});n.append(b);root.append(n);}}
async function loadGraph(){
 const root=$('graph-canvas');if(!state.current){root.replaceChildren(el('p','先在左侧选择一个节点。','empty'));return;}
 const ref=state.current.ref;const params=new URLSearchParams({depth:$('graph-depth').value,direction:$('graph-direction').value,max_nodes:'45'});if($('graph-kind').value)params.set('kinds',$('graph-kind').value);if($('graph-relation').value)params.set('relations',$('graph-relation').value);
 const g=await api(endpoint(ref,'graph')+'?'+params);if(ref!==state.current?.ref)return;renderGraph(g);$('graph-count').textContent=`${g.nodes.length} 个节点 · ${g.edges.length} 条关系${g.truncated?' · 已达到节点上限':''}`;
 const rows=$('graph-edges');clear(rows);const details=el('details');details.append(el('summary',`查看关系字段明细（${g.edges.length}）`));for(const e of g.edges){const r=el('div',undefined,'edge-row');r.append(refButton(e.source),el('span',`— ${e.label} →`,'muted'),refButton(e.target),el('code',e.field));if(e.phase)r.append(el('span',e.phase,'muted'));details.append(r);}rows.append(details);
}
function svgEl(tag,attrs,text){const n=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const[k,v]of Object.entries(attrs||{}))n.setAttribute(k,String(v));if(text!==undefined)n.textContent=text;return n;}
function renderGraph(g){
 const root=$('graph-canvas');clear(root);const width=960;
 const layers=[g.nodes.filter(n=>n.depth===1),g.nodes.filter(n=>n.depth===2)];
 const height=Math.max(500,140+layers.reduce((sum,ns)=>sum+Math.ceil(ns.length/5)*100,0));
 const svg=svgEl('svg',{viewBox:`0 0 ${width} ${height}`,role:'img','aria-label':'局部知识关系图'});
 const defs=svgEl('defs');const marker=svgEl('marker',{id:'arrow',viewBox:'0 0 10 10',refX:9,refY:5,markerWidth:6,markerHeight:6,orient:'auto-start-reverse'});marker.append(svgEl('path',{d:'M 0 0 L 10 5 L 0 10 z',fill:'#9bacc2'}));defs.append(marker);svg.append(defs);
 const pos=new Map([[g.center,{x:width/2,y:55}]]);let rowStart=160;
 for(const ns of layers){for(let i=0;i<ns.length;i++){const column=i%5,row=Math.floor(i/5);const inRow=Math.min(5,ns.length-row*5);pos.set(ns[i].ref,{x:(width-(inRow-1)*186)/2+column*186,y:rowStart+row*100});}rowStart+=Math.ceil(ns.length/5)*100;}
 for(const e of g.edges){const a=pos.get(e.source),b=pos.get(e.target);if(!a||!b)continue;const dx=b.x-a.x,dy=b.y-a.y;if(!dx&&!dy)continue;const t=Math.min(84/Math.max(1,Math.abs(dx)),25/Math.max(1,Math.abs(dy)));svg.append(svgEl('line',{x1:a.x+dx*t,y1:a.y+dy*t,x2:b.x-dx*t,y2:b.y-dy*t,class:'edge','marker-end':'url(#arrow)'}));}
 const colors={scenario:'#957545',concept:'#3976b9',entity:'#419286'};
 for(const n of g.nodes){const p=pos.get(n.ref);if(!p)continue;const group=svgEl('g',{class:'node',tabindex:0,role:'button','aria-label':n.id});group.append(svgEl('title',{},`${n.ref}\n${n.define}`),svgEl('rect',{x:p.x-84,y:p.y-25,width:168,height:50,rx:7,fill:'white',stroke:n.ref===g.center?'#223047':'#c7d4e4','stroke-width':n.ref===g.center?2:1}),svgEl('circle',{cx:p.x-70,cy:p.y,r:4,fill:colors[n.kind]}));const label=n.id.length>28?n.id.slice(0,27)+'…':n.id;const parts=label.length>14?[label.slice(0,14),label.slice(14)]:[label];for(let i=0;i<parts.length;i++)group.append(svgEl('text',{x:p.x+4,y:p.y+(parts.length===1?4:-3+i*16),'text-anchor':'middle'},parts[i]));group.onclick=run(()=>selectNode(n.ref));group.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();run(()=>selectNode(n.ref))();}};svg.append(group);}
 root.append(svg);
}
async function queryPaths(){
 $('path-run').disabled=true;try{const p=await api('/api/multihop',{query:$('path-query').value,start_ref:$('path-start').value||null,target_ref:$('path-target').value||null,max_depth:Number($('path-depth').value),max_paths:6,direction:$('path-direction').value});state.paths=p;state.overview=null;$('path-export').disabled=false;renderPaths(p);if(p.trace_id)$('path-results').prepend(action('查看本次运行记录',()=>loadTrace(p.trace_id)));}finally{$('path-run').disabled=false;}
}
function renderPaths(p){const root=$('path-results');clear(root);root.append(el('p',p.message,'muted'));if(!p.paths.length){root.append(el('p',p.status==='no_path'?'在指定方向和跳数范围内未找到明确路径。':p.message,'empty'));for(const s of p.seeds||[])root.append(refButton(s.ref));return;}root.append(el('p',`返回 ${p.paths.length} 条路径 · ${p.explored_edges} 次关系展开${p.truncated?' · 展开达到上限':''}${p.additional_paths_omitted?` · 另有 ${p.additional_paths_omitted} 条候选未展示`:''}`,'muted'));for(const path of p.paths){const card=el('article',undefined,'path-card');card.append(el('h3',`${path.steps.length} 跳 · ${path.nodes.at(-1).id}`));const chain=el('div',undefined,'path-chain');path.refs.forEach((ref,i)=>{if(i)chain.append(el('span','→','muted'));chain.append(refButton(ref));});card.append(chain);for(const[i,step]of path.steps.entries())card.append(el('div',`${i+1}. ${step.explanation}`,'path-step'));card.append(el('h3','终点原文依据'));for(const ev of path.evidence)card.append(evidenceCard(ev));if(!path.evidence.length)card.append(el('p','终点暂无匹配段落；关系存在不表示证据已确认。','muted'));root.append(card);}}
for(const b of document.querySelectorAll('#kind-tabs button'))b.onclick=()=>{state.kind=b.dataset.kind;for(const x of document.querySelectorAll('#kind-tabs button'))x.classList.toggle('active',x===b);renderList();};
for(const b of document.querySelectorAll('.main-tabs button'))b.onclick=()=>setView(b.dataset.view);
$('search').oninput=()=>{clearTimeout(searchTimer);searchTimer=setTimeout(run(async()=>{const q=$('search').value;const result=await api('/api/search?q='+encodeURIComponent(q));if(q!==$('search').value)return;state.navigation=result;renderList();}),180);};
$('reload').onclick=run(async()=>{if(!(await discardCheck()))return;const ref=state.current?.ref;await init();if(ref)await selectNode(ref,true);if(state.view==='overview')await loadOverview();if(state.view==='runs')await loadRuns();tell('已重新读取正式模型。');});
$('read-mode').onclick=()=>editMode(false);$('edit-mode').onclick=()=>{if(state.current)editMode(true);};
$('editor').oninput=()=>{state.dirty=$('editor').value!==state.original;state.preview=null;$('save').disabled=true;clear($('preview-result'));$('edit-state').textContent=state.dirty?'有未保存修改':'';};
$('preview').onclick=run(preview);$('save').onclick=run(save);$('discard').onclick=()=>{$('editor').value=state.original;state.dirty=false;state.preview=null;$('save').disabled=true;clear($('preview-result'));$('edit-state').textContent='';};
$('evidence-search').onclick=run(()=>loadEvidence($('evidence-query').value));$('evidence-query').onkeydown=e=>{if(e.key==='Enter')run(()=>loadEvidence($('evidence-query').value))();};
$('graph-refresh').onclick=run(loadGraph);$('path-run').onclick=run(queryPaths);$('path-use-current').onclick=()=>{if(state.current){$('path-start').value=state.current.ref;tell('已选择当前节点为查询起点。');}};
$('path-export').onclick=()=>{if(!state.paths)return;const blob=new Blob([JSON.stringify(state.paths,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const link=el('a');link.href=url;link.download='knowledge-paths.json';link.click();URL.revokeObjectURL(url);};
$('source-close').onclick=()=>$('source-dialog').close();window.addEventListener('beforeunload',e=>{if(state.dirty){e.preventDefault();e.returnValue='';}});
run(async()=>{await init();const hash=decodeURIComponent(location.hash.slice(1));if(state.all.some(n=>n.ref===hash))await openNode(hash);})();
