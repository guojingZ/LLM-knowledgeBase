'use strict';
let traceRequestId=0;
const statusNames={context_ready:'上下文已就绪',needs_clarification:'需确认场景',no_evidence:'当前库缺少依据',paths_found:'找到引用路径',no_path:'未找到范围内路径',limit_reached:'达到展开上限'};
const reviewNames={pending:'待审',reviewed:'已审查',accepted:'已采纳',rejected:'未采纳',handled:'已处理'};
const ratingNames={helpful:'有用',partial:'部分有用',not_helpful:'无用'};
function action(text,fn,cls='quiet'){const b=el('button',text,cls);b.onclick=run(fn);return b;}
async function openNode(ref){await selectNode(ref);if(state.current?.ref===ref)setView('browse');}
function renderSupportFields(){
 const root=$('support-field');clear(root);root.append(new Option('节点定义','define'));
 const n=state.current.node;
 for(const key of ['goal','trigger','ipo','decomposition'])if(n[key])root.append(new Option(key,key));
 for(const [i,phase]of(n.composition||[]).entries())if(phase.rule)root.append(new Option('阶段规则 · '+phase.phase,'composition['+i+'].rule'));
 for(const edge of state.current.outgoing)root.append(new Option((relationNames[edge.relation]||edge.relation)+' · '+edge.target.split('://')[1]+' · '+edge.field,edge.field));
 root.append(new Option('节点关联 · 未逐字段审查','node'));
 $('support-note').value='';
}
async function queryOneHop(){
 $('query-run').disabled=true;
 try{
  const result=await api('/api/query',{question:$('query-question').value,mode:$('query-mode').value||'model-guided',scenario:$('query-mode').value==='raw'?null:($('query-scenario').value||null)});
  state.query=result;state.overview=null;clear($('query-results'));renderSnapshot(result,$('query-results'),true);
  $('query-results').prepend?.(action('查看本次运行记录',()=>loadTrace(result.trace_id)));
  if(!$('query-results').prepend)$('query-results').append(action('查看本次运行记录',()=>loadTrace(result.trace_id)));
 }finally{$('query-run').disabled=false;}
}
function renderSnapshot(c,root,showPreview=false){
 clear(root);
 const overview=el('article',undefined,'result-card');overview.append(el('span',statusNames[c.status]||c.status,'badge'),el('h2',c.question||c.query||'指定路径查询'));
 overview.append(el('p',c.mode==='raw'?'本次直接检索已准入原文，没有场景或图关系展开。':c.query_kind==='multihop'?'本次为主动提交的明确关系路径探索。':'场景 → 阶段直接知识 → 相关来源段落；本次未递归检索后续节点。','muted'));
 if(c.trace_id)overview.append(el('code',c.trace_id));
 if(c.selected_scenario){overview.append(el('h3','选中的场景'),refButton('scenario://'+c.selected_scenario.id),el('p',c.selected_scenario.goal||c.selected_scenario.define));}
 if(c.status==='needs_clarification')overview.append(el('p','候选接近或问题含多个意图。先确认场景，再据此使用上下文。','warning-text'));
 if(c.status==='no_evidence')overview.append(el('p','本次未取得足够库内依据。可补充问题背景或材料，不据此生成确定结论。','warning-text'));
 if(c.candidate_scenarios?.length){const d=el('details');d.open=c.status==='needs_clarification';d.append(el('summary','查看候选场景及匹配分（不是正确概率）'));for(const candidate of c.candidate_scenarios){const row=el('div',undefined,'edge-row');row.append(refButton('scenario://'+candidate.id),el('span','匹配分 '+candidate.score,'muted'));if(showPreview)row.append(action('选择后重新检索',()=>{$('query-scenario').value=candidate.id;return queryOneHop();}));d.append(row);}overview.append(d);}
 root.append(overview);
 if(c.knowledge_items?.length){
  const block=el('article',undefined,'result-card');block.append(el('h2','本次取到的直接知识 · '+c.knowledge_items.length));
  for(const item of c.knowledge_items){const card=el('div',undefined,'knowledge-row');card.append(refButton(item.ref),el('p',item.define,'muted'));const edges=(c.one_hop_edges||[]).filter(e=>e.target===item.ref);for(const edge of edges)card.append(el('small','阶段：'+edge.phase+' · 引用位置：'+edge.field));block.append(card);}
  if(c.selected_scenario?.phases){const phases=el('details');phases.append(el('summary','查看场景阶段与完整直接引用'));for(const phase of c.selected_scenario.phases){const box=el('div',undefined,'phase');box.append(el('h3',phase.phase),el('p',phase.rule));for(const ref of phase.uses||[])box.append(refButton(ref));phases.append(box);}block.append(phases);}
  root.append(block);
 }
 if(c.paths?.length){
  const block=el('article',undefined,'result-card');block.append(el('h2','保存的关系路径'));
  for(const p of c.paths){const row=el('div',undefined,'path-card');row.append(el('h3',p.steps.length+' 跳'));for(const ref of p.refs)row.append(refButton(ref));for(const step of p.steps)row.append(el('p',step.explanation,'muted'));for(const e of p.evidence||[])row.append(evidenceCard(e));block.append(row);}root.append(block);
 }
 if(c.evidence?.length){const block=el('article',undefined,'result-card');block.append(el('h2','本次原文依据 · '+c.evidence.length),el('p','候选只表示检索相关；人工确认仅针对登记的支持字段。','muted'));for(const p of c.evidence)block.append(evidenceCard(p));root.append(block);}
 if(showPreview){
  const block=el('article',undefined,'result-card continuation');block.append(el('h2','下一步可以怎样开始多跳？'),el('p','以下只预览模型已有的后续关系，没有把后续节点或其原文加入本次检索。先核对一跳是否够用，再主动开始探索。','muted'));
  const preview=c.continuations;
  if(preview?.items.length)overview.append(action('查看可继续探索的路径',()=>block.scrollIntoView({behavior:'smooth',block:'start'})));
  if(!preview?.items.length)block.append(el('p',c.mode==='raw'?'原文对照检索没有场景路径。':c.status!=='context_ready'?'先明确场景或取得库内依据，再展示后续路径。':'当前直接知识没有可预览的新出向节点。','empty'));
  for(const path of preview?.items||[]){const row=el('div',undefined,'continuation-row');const chain=el('div',undefined,'path-chain');path.refs.forEach((ref,i)=>{if(i)chain.append(el('span','→','muted'));chain.append(refButton(ref));});row.append(chain);for(const step of path.steps)row.append(el('small',(relationNames[step.relation]||step.relation)+' · '+step.field));row.append(action('用此路径开始探索',()=>{ $('path-query').value=c.question;$('path-start').value=path.refs[0];$('path-target').value=path.refs.at(-1);$('path-depth').value=String(path.steps.length);$('path-direction').value='outgoing';setView('paths');tell('已填入探索路径。点击“查询知识路径”后才会执行多跳。');}));block.append(row);}
  if(preview?.truncated)block.append(el('p','展示前 '+preview.items.length+' 条，共 '+preview.total+' 条可探索关系；排序不是任务适用性判断。','muted'));
  root.append(block);
 }
 if(c.context_text){const d=el('details',undefined,'result-card');d.append(el('summary','查看交给 Agent 的完整上下文'),el('pre',c.context_text));root.append(d);}
}
async function loadOverview(){
 if(!state.overview)state.overview=await api('/api/overview');
 renderOverview();
}
function overviewNodes(){
 const q=$('overview-search').value.trim().toLocaleLowerCase(),kind=$('overview-kind').value,status=$('coverage-status').value;
 return state.overview.nodes.filter(n=>(!kind||n.kind===kind)&&(!q||(n.id+' '+n.define).toLocaleLowerCase().includes(q))&&(!status||n.evidence_status===status));
}
function renderOverview(){
 if(!state.overview)return;
 const value=state.overview;clear($('overview-summary'));
 for(const [title,count]of [['节点',value.nodes.length],['关系组',value.edges.length],['原始引用',value.edge_records],['有确认字段的节点',value.coverage.nodes_with_confirmed_fields],['需复核节点',value.coverage.nodes_needing_review],['运行记录',value.trace_count]]){const card=el('div',undefined,'summary-item');card.append(el('strong',String(count)),el('span',title));$('overview-summary').append(card);}
 for(const mode of ['graph','matrix','coverage'])$('overview-'+mode+'-panel').hidden=state.overviewMode!==mode;
 for(const b of document.querySelectorAll('#overview-tabs button'))b.classList.toggle('active',b.dataset.overview===state.overviewMode);
 $('overview-overlay').textContent=state.highlightRefs.length?'已叠加所选运行的 '+state.highlightRefs.length+' 个使用节点。位置来自当前模型；历史内容请以运行快照为准。':'';
 if(state.highlightRefs.length)$('overview-overlay').append(action('清除叠加',()=>{state.highlightRefs=[];state.highlightEdges=[];renderOverview();}));
 if(state.overviewMode==='graph')renderGlobalGraph(overviewNodes());
 else if(state.overviewMode==='matrix')renderMatrix();
 else renderCoverage(overviewNodes());
}
function renderGlobalGraph(nodes){
 const root=$('overview-canvas');clear(root);const positions=new Map(),center=550,all=state.overview.nodes;
 for(const [kind,radius]of [['scenario',180],['entity',345],['concept',490]]){
  const members=all.filter(n=>n.kind===kind);
  members.forEach((n,i)=>{const angle=2*Math.PI*i/members.length-Math.PI/2;positions.set(n.ref,{x:center+radius*Math.cos(angle),y:center+radius*Math.sin(angle)});});
 }
 const svg=svgEl('svg',{viewBox:'0 0 1100 1100',role:'img','aria-label':'全部场景概念实体关系图'});svg.style.width=String(1100*Number($('overview-zoom').value||100)/100)+'px';
 const defs=svgEl('defs'),marker=svgEl('marker',{id:'global-arrow',viewBox:'0 0 10 10',refX:9,refY:5,markerWidth:3,markerHeight:3,orient:'auto'});marker.append(svgEl('path',{d:'M 0 0 L 10 5 L 0 10 z',fill:'#aab8ca'}));defs.append(marker);svg.append(defs);
 const visible=new Set(nodes.map(n=>n.ref)),highlight=new Set(state.highlightRefs),relation=$('overview-relation').value;
 let edgeCount=0;
 for(const e of state.overview.edges){
  if(!visible.has(e.source)||!visible.has(e.target))continue;
  if(relation==='core'&&e.relation==='related_to')continue;
  if(relation&&relation!=='core'&&e.relation!==relation)continue;
  const a=positions.get(e.source),b=positions.get(e.target),selected=state.highlightEdges.some(h=>h.source===e.source&&h.target===e.target&&(!h.relation||h.relation===e.relation));
  const line=svgEl('line',{x1:a.x,y1:a.y,x2:b.x,y2:b.y,stroke:selected?'#d38721':'#b5c2d2','stroke-width':selected?2.5:.6,opacity:selected?1:.25,'marker-end':'url(#global-arrow)'});line.append(svgEl('title',{},e.label+' · '+e.fields.join(' / ')));svg.append(line);edgeCount++;
 }
 const colors={scenario:'#957545',concept:'#3976b9',entity:'#419286'};
 for(const n of nodes){
  const p=positions.get(n.ref),selected=highlight.has(n.ref),group=svgEl('g',{role:'button',tabindex:0,class:'global-node','aria-label':n.id});
  group.append(svgEl('title',{},kindNames[n.kind]+' · '+n.id+'\n'+n.define+'\n查询使用 '+n.query_count+' 次'),svgEl('circle',{cx:p.x,cy:p.y,r:selected?9:n.kind==='scenario'?7:5,fill:colors[n.kind],stroke:selected?'#d38721':n.review_required_count?'#df812b':'white','stroke-width':selected?3:1}));
  if($('overview-labels').checked||selected)group.append(svgEl('text',{x:p.x+10,y:p.y+4,fill:'#26394d','font-size':11},n.id.length>18?n.id.slice(0,17)+'…':n.id));
  group.onclick=run(()=>openNode(n.ref));group.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();run(()=>openNode(n.ref))();}};svg.append(group);
 }
 root.append(svg);$('overview-count').textContent='显示 '+nodes.length+' / '+all.length+' 个节点 · '+edgeCount+' 组关系';
}
function makeTable(headers){const table=el('table'),head=el('thead'),row=el('tr');for(const title of headers)row.append(el('th',title));head.append(row);table.append(head);const body=el('tbody');table.append(body);return {table,head,row,body};}
function renderMatrix(){
 const q=$('overview-search').value.trim().toLocaleLowerCase(),kind=$('overview-kind').value;
 const columns=state.overview.nodes.filter(n=>n.kind!=='scenario'&&(!kind||kind==='scenario'||n.kind===kind)&&(!q||kind==='scenario'||(n.id+' '+n.define).toLocaleLowerCase().includes(q)));
 const root=$('overview-matrix');clear(root);if(!columns.length){root.append(el('p','没有匹配的知识列，可调整名称或类型筛选。','empty'));return;}
 const {table,row,body}=makeTable(['场景 / 直接引用']);
 table.className='incidence-table';
 for(const column of columns){const cell=el('th');cell.append(refButton(column.ref));cell.title=column.id;row.append(cell);}
 for(const scenario of state.overview.matrix){if(kind==='scenario'&&q&&!scenario.id.toLocaleLowerCase().includes(q))continue;const r=el('tr'),name=el('th');name.append(refButton(scenario.ref));r.append(name);for(const column of columns){const phases=scenario.uses[column.ref];const cell=el('td',phases?'●':'');if(phases){cell.className='used-cell';cell.title=column.id+'：'+phases.join('、');cell.append(action('查看',()=>openNode(column.ref),'matrix-link'));}r.append(cell);}body.append(r);}
 root.append(table);
}
function renderCoverage(nodes){
 const root=$('overview-coverage');clear(root);const {table,body}=makeTable(['节点','类型','来源数','支持记录','已确认范围','待复核','查询使用次数']);
 for(const n of nodes){const row=el('tr'),name=el('td');name.append(refButton(n.ref));row.append(name,el('td',kindNames[n.kind]),el('td',String(n.source_count)),el('td',String(n.confirmed_count)),el('td',n.confirmed_fields.join('、')||(n.confirmed_association_count?'节点关联 · 未逐字段':'尚无字段确认')),el('td',String(n.review_required_count)),el('td',String(n.query_count)));body.append(row);}root.append(table);
}
async function loadRuns(){
 const result=await api('/api/traces');state.runs=result;renderRuns();
}
function renderRuns(){
 if(!state.runs)return;const q=$('runs-search').value.trim().toLocaleLowerCase(),items=state.runs.items;
 const reviewed=items.filter(x=>x.rating);const counts={helpful:0,partial:0,not_helpful:0};for(const x of reviewed)counts[x.rating]=(counts[x.rating]||0)+1;
 $('runs-summary').textContent=items.length+' 次运行 · 已评价 '+reviewed.length+' · 有用 '+counts.helpful+' / 部分 '+counts.partial+' / 无用 '+counts.not_helpful+(state.runs.skipped.length?' · '+state.runs.skipped.length+' 条异常记录未读取':'');
 const root=$('runs-list');clear(root);const {table,body}=makeTable(['问题 / 记录','时间（本机）','入口','状态','检索耗时','评价']);
 for(const item of items.filter(x=>!q||(x.question+' '+x.trace_id).toLocaleLowerCase().includes(q))){const row=el('tr'),name=el('td');name.append(action(item.question||'指定节点路径',()=>loadTrace(item.trace_id)),el('small',item.trace_id));row.append(name,el('td',item.generated_at?new Date(item.generated_at).toLocaleString('zh-CN',{hour12:false}):'未记录'),el('td',(item.entrypoint==='legacy'?'旧记录':item.entrypoint)+' · '+(item.query_kind==='one_hop'?'一跳':item.query_kind==='multihop'?'多跳':item.query_kind==='raw'?'原文':'旧格式')),el('td',statusNames[item.status]||item.status),el('td',item.elapsed_ms===null||item.elapsed_ms===undefined?'未记录':item.elapsed_ms+' ms'),el('td',item.rating?ratingNames[item.rating]+' · '+(reviewNames[item.review_status]||item.review_status||'待审'):'未评价'));body.append(row);}
 if(!items.length)root.append(el('p','尚无运行记录。提交一次一跳检索后，可在此回放和评价。','empty'));else root.append(table);
}
async function loadTrace(id){
 const ticket=++traceRequestId;
 const trace=await api('/api/trace?trace_id='+encodeURIComponent(id));if(ticket!==traceRequestId)return;
 state.trace=trace;setView('runs');$('trace-panel').hidden=false;const root=$('trace-heading');clear(root);
 root.append(el('h2',trace.context.question||trace.context.query||id),el('code',id),el('p','以下段落和确认状态均为记录时快照；当前状态请进入知识浏览检查。','muted'));
 root.append(el('p',trace.metadata.app_version?'版本 '+trace.metadata.app_version+' · '+trace.metadata.elapsed_ms+' ms 检索耗时 · '+(trace.metadata.version_consistency==='stable'?'查询期间文件版本稳定':'查询期间文件变化，需复核'):'旧格式记录，没有完整版本与耗时信息；保留原始结果。','muted'));
 renderSnapshot(trace.context,$('trace-result'));
 const details=el('details',undefined,'result-card');details.append(el('summary','查看参数与版本标识'),el('pre',JSON.stringify({query:trace.query,metadata:trace.metadata},null,2)));$('trace-result').append(details);
 const f=trace.feedback;$('feedback-scenario').value=f.scenario_verdict||'uncertain';$('feedback-evidence').value=f.evidence_verdict||'uncertain';$('feedback-rating').value=f.rating||'';$('feedback-issue').value=f.issues?.[0]||'';$('feedback-expected').value=f.expected_scenario||'';$('feedback-notes').value=f.notes||'';
 $('feedback-state').textContent=f.rating?'已保存 · '+(reviewNames[trace.review?.review_status]||trace.review?.review_status||'待人工审查')+' · 未自动修改模型':'尚未评价';
}
async function saveFeedback(){
 if(!state.trace)return;
 const id=state.trace.trace_id,issue=$('feedback-issue').value;
 $('feedback-save').disabled=true;
 try{
  const issues=[...(state.trace.feedback.issues||[]).slice(1),...(issue?[issue]:[])];if($('feedback-scenario').value==='incorrect'&&!issues.includes('wrong_scenario'))issues.push('wrong_scenario');
  const result=await api('/api/feedback',{trace_id:id,revision:state.trace.feedback_revision,rating:$('feedback-rating').value,issues,notes:$('feedback-notes').value,expected_scenario:$('feedback-expected').value||null,expected_sources:state.trace.feedback.expected_sources||[],scenario_verdict:$('feedback-scenario').value,evidence_verdict:$('feedback-evidence').value});
  tell(result.warning||'评价已保存并进入待审队列，知识模型未自动修改。',result.queue_status==='sync_failed');if(state.trace.trace_id===id)await loadTrace(id);await loadRuns();
 }finally{$('feedback-save').disabled=false;}
}
function exportJson(value,name){const url=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)],{type:'application/json'}));const link=el('a');link.href=url;link.download=name;link.click();URL.revokeObjectURL(url);}
$('query-run').onclick=run(queryOneHop);
$('query-mode').onchange=()=>{$('query-scenario').disabled=$('query-mode').value==='raw';};
for(const b of document.querySelectorAll('#overview-tabs button'))b.onclick=()=>{state.overviewMode=b.dataset.overview;renderOverview();};
for(const id of ['overview-kind','overview-relation','coverage-status','overview-labels'])$(id).onchange=renderOverview;
$('overview-search').oninput=renderOverview;$('overview-zoom').oninput=renderOverview;
$('overview-refresh').onclick=run(async()=>{state.overview=null;await loadOverview();});
$('runs-search').oninput=renderRuns;$('runs-refresh').onclick=run(loadRuns);$('feedback-save').onclick=run(saveFeedback);
$('trace-overlay').onclick=()=>{if(!state.trace)return;const c=state.trace.context;state.highlightRefs=[...new Set([...(c.knowledge_items||[]).map(n=>n.ref),...(c.selected_scenario?['scenario://'+c.selected_scenario.id]:[]),...(c.paths||[]).flatMap(p=>p.refs)])];state.highlightEdges=c.one_hop_edges||(c.paths||[]).flatMap(p=>p.steps);state.overviewMode='graph';state.overview=null;$('overview-kind').value='';$('overview-search').value='';$('coverage-status').value='';setView('overview');};
$('trace-export').onclick=()=>{if(state.trace)exportJson(state.trace,state.trace.trace_id+'.json');};
