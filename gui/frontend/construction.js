'use strict';
const buildState={sources:null,jobs:null,job:null,preview:null,selected:new Set(),source:null,publications:[]};
const buildNames={pending:'待准入',accepted:'已准入',rejected:'不纳入',unprocessed:'未处理',processed:'已处理',needs_update:'需更新',awaiting_extraction:'待提取',awaiting_comparison:'待比较',review_required:'候选待审',partial_published:'部分已发布',completed:'已完成',approved:'通过',hold:'待定',new:'新增',update:'补充字段',evidence:'补充证据',merge:'合并名称',conflict:'冲突',ignore:'不纳入'};
const buildApi=(action,payload={})=>api('/api/build/'+action,payload);

async function loadConstruction(){
 const [sources,jobs,publications]=await Promise.all([buildApi('sources.list'),buildApi('jobs.list'),buildApi('publications.list')]);buildState.sources=sources;buildState.jobs=jobs;buildState.publications=publications.items;renderBuildSources();renderBuildJobs();renderBuildPublications();
 if(buildState.job)await loadBuildJob(buildState.job.job_id);
}
function buildButton(label,fn){const b=el('button',label);b.onclick=run(fn);return b;}
function renderBuildSources(){
 const root=$('build-sources');clear(root);const {table,body}=makeTable(['选择','资料','准入','知识处理','模型引用','操作']);
 const query=$('build-filter').value.toLocaleLowerCase();const filter=$('build-status').value;
 for(const s of buildState.sources.items.filter(s=>(!query||s.path.toLocaleLowerCase().includes(query))&&(!filter||s.admission===filter||s.processing===filter))){
  const row=el('tr'),pick=el('input');pick.type='checkbox';pick.checked=buildState.selected.has(s.source_id);pick.disabled=s.admission!=='accepted'||s.missing||!s.supported;pick.setAttribute('aria-label','选择 '+s.path);pick.onchange=()=>{if(pick.checked)buildState.selected.add(s.source_id);else buildState.selected.delete(s.source_id);updateBuildSelection();};
  const select=el('td');select.append(pick);const name=el('td');name.append(buildButton(s.path.replace(/^raw\/(inbox|accepted)\//,''),()=>openBuildSource(s.source_id)),el('small',s.source_id));
  const actions=el('td');if(s.admission!=='accepted'&&!s.missing&&s.supported){actions.append(buildButton('准入',()=>admitBuildSource(s,'accepted')));if(s.admission!=='rejected')actions.append(buildButton('不纳入',()=>admitBuildSource(s,'rejected')));}
  row.append(select,name,el('td',buildNames[s.admission]),el('td',s.missing?'文件缺失':!s.supported?'格式不支持':buildNames[s.processing]||s.processing),el('td',s.linked_nodes.length+(s.legacy_linked?' · 历史模型引用':'')),actions);body.append(row);
 }
 root.append(table);$('build-summary').textContent=buildState.sources.items.length+' 份资料 · '+buildState.sources.items.filter(s=>s.processing==='needs_update').length+' 份需更新 · '+buildState.sources.duplicate_groups.length+' 组重复';updateBuildSelection();
}
function updateBuildSelection(){const active=new Set(buildState.sources.items.filter(s=>s.admission==='accepted'&&!s.missing&&s.supported).map(s=>s.source_id));for(const id of buildState.selected)if(!active.has(id))buildState.selected.delete(id);$('build-selected').textContent='已选 '+buildState.selected.size+' 份';$('build-create').disabled=!buildState.selected.size;}
async function openBuildSource(id){const s=await buildApi('sources.read',{source_id:id});buildState.source=s;const root=$('build-source-detail');clear(root);root.append(el('h3',s.path),el('p','当前原文版本：'+s.sha256,'muted'),el('pre',s.text));if(s.linked_nodes.length){root.append(el('h3','引用影响'));for(const ref of s.linked_nodes)root.append(refButton(ref));}root.hidden=false;}
async function admitBuildSource(s,decision){await buildApi('sources.admit',{source_id:s.source_id,source_sha256:s.sha256,revision:buildState.sources.revision,decision,note:$('build-admission-note').value});tell(decision==='accepted'?'资料已准入。勾选后创建提炼任务。':'已记录不纳入；原文保留。');await loadConstruction();}
async function importBuildSource(){const result=await buildApi('sources.import',{name:$('build-import-name').value,text:$('build-import-text').value});tell(result.status==='duplicate'?'已有相同内容，未重复导入。':'已导入待准入区。');await loadConstruction();}
async function createBuildJob(){const job=await buildApi('jobs.create',{source_ids:[...buildState.selected],title:$('build-title').value||undefined});buildState.selected.clear();buildState.job=job;await loadConstruction();$('build-job-panel').scrollIntoView?.({behavior:'smooth'});tell('任务已创建。导出第一轮任务包，交给本地 Agent。');}
function renderBuildJobs(){const root=$('build-jobs');clear(root);for(const j of buildState.jobs.items){const row=el('div',undefined,'build-job-row');row.append(buildButton(j.title,()=>loadBuildJob(j.job_id)),el('span',buildNames[j.status]||j.status,'badge'),el('small',j.job_id));root.append(row);}if(!buildState.jobs.items.length)root.append(el('p','先准入资料，再勾选创建任务。','empty'));}
function renderBuildPublications(){const root=$('build-publications');clear(root);for(const p of buildState.publications){const details=el('details');details.append(el('summary',p.publication_id+' · '+p.purpose+' · '+p.status),el('pre',JSON.stringify(p,null,2)));if(['prepared','recovery_required'].includes(p.status))details.append(buildButton('恢复中断写入',async()=>{await buildApi('publications.recover',{publication_id:p.publication_id});await init();await loadConstruction();tell('中断写入已回退。重新检查任务后操作。');}));root.append(details);}if(!buildState.publications.length)root.append(el('p','尚无写入记录。','muted'));}
async function loadBuildJob(id){buildState.job=await buildApi('jobs.get',{job_id:id});buildState.preview=null;renderBuildJob();}
function renderBuildJob(){
 const j=buildState.job;const panel=$('build-job-panel');panel.hidden=!j;if(!j)return;
 clear($('build-job-heading'));$('build-job-heading').append(el('h2',j.title),el('code',j.job_id),el('p',(buildNames[j.status]||j.status)+' · '+j.sources.length+' 份原文','muted'));
 for(const issue of j.freshness_issues)$('build-job-heading').append(el('p',issue,'warning-text'));
 $('build-extract-submit').disabled=j.observations!==null&&j.proposals.length>0||j.publications.length>0;
 $('build-compare-submit').disabled=j.observations===null||j.publications.length>0;
 $('build-publish').disabled=true;clear($('build-preview'));
 const root=$('build-candidates');clear(root);
 if(j.observations!==null){const details=el('details');details.append(el('summary','第一轮原文候选 · '+j.observations.length),el('pre',JSON.stringify({observations:j.observations,note:j.extraction_note},null,2)));root.append(details);}
 for(const p of j.proposals){
  const card=el('article',undefined,'result-card');card.append(el('h3',(buildNames[p.action]||p.action)+' · '+(p.target_ref||p.proposal_id)),el('p',p.reason));
  const originals=(p.supports?.length?p.supports:j.observations.filter(o=>p.observation_ids.includes(o.observation_id)).flatMap(o=>o.evidence));
  for(const s of originals)card.append(el('small',s.path+' · L'+s.line_start+'–'+s.line_end+(s.support_field?' · 支持 '+s.support_field:'')),el('blockquote',s.excerpt));
  if(p.aliases?.length)card.append(el('p','合并名称：'+p.aliases.join('、')));
  if(p.node){const details=el('details');details.append(el('summary','完整建议节点'),el('pre',JSON.stringify(p.node,null,2)));card.append(details);}
  card.append(el('p','审查：'+(p.published?'已发布':buildNames[p.review.decision]||'未审查')+(p.review.note?' · '+p.review.note:''),'muted'));
  if(!p.published&&j.status!=='completed'){const note=el('textarea');note.value=p.review.note;note.placeholder='审查理由；拒绝或待定需填写';note.setAttribute('aria-label','审查理由 '+p.proposal_id);const actions=el('div',undefined,'toolbar');for(const [decision,label]of [['approved','通过'],['rejected','拒绝'],['hold','待定']]){const b=buildButton(label,()=>reviewBuildCandidate(p,decision,note.value));b.disabled=decision==='approved'&&p.action==='conflict';actions.append(b);}card.append(note,actions);}
  root.append(card);
 }
 if(j.comparison_note)root.append(el('p','比较说明：'+j.comparison_note));
 if(j.status==='completed')root.append(el('p','已完成处理。需要进一步变更时创建新任务，原文和审查记录继续保留。','muted'));
}
async function exportBuildPacket(phase){if(!buildState.job)return;const packet=await buildApi('jobs.packet',{job_id:buildState.job.job_id,phase});exportJson(packet,buildState.job.job_id+'-'+phase+'.json');}
async function submitBuildResult(phase){
 const j=buildState.job;let value;try{value=JSON.parse($(phase==='extraction'?'build-extract-json':'build-compare-json').value);}catch{throw new Error('请输入有效 JSON 结果。');}
 if(value.job_id&&value.job_id!==j.job_id)throw new Error('结果属于另一任务，未导入。');
 buildState.job=await buildApi(phase==='extraction'?'jobs.extract':'jobs.compare',{...value,job_id:j.job_id,revision:value.revision||j.revision});renderBuildJob();await loadConstruction();tell('已保存候选结果；正式模型未改动。');
}
async function reviewBuildCandidate(p,decision,note){const j=buildState.job;buildState.job=await buildApi('jobs.review',{job_id:j.job_id,revision:j.revision,proposal_id:p.proposal_id,decision,note});renderBuildJob();tell('已记录审查决定。发布前查看差异。');}
async function previewBuild(){const p=await buildApi('jobs.preview',{job_id:buildState.job.job_id});buildState.preview=p;const root=$('build-preview');clear(root);root.append(el('h3','发布预览'),el('p',p.approved_count+' 条已通过 · '+p.remaining_count+' 条仍待审 · '+(p.will_complete?'本次可完成资料处理':'本次仅发布通过部分')));for(const d of p.diffs){root.append(el('h4',d.ref),el('pre',d.diff||'节点内容不变，仅登记字段证据'));if(d.aliases?.length)root.append(el('p','登记别名：'+d.aliases.join('、')));for(const s of d.supports)root.append(el('p','登记支持：'+s.support_field+' ← '+s.path+' · L'+s.line_start+'–'+s.line_end));}root.append(el('p','涉及文件：'+(p.files.join('、')||'仅处理与审查记录')));if(p.no_model_change)root.append(el('p','本次不修改模型内容，记录已处理结果。'));$('build-publish').disabled=false;}
async function publishBuild(){if(!buildState.preview)return;const r=await buildApi('jobs.publish',{job_id:buildState.job.job_id,preview_token:buildState.preview.preview_token});buildState.job=r;await init();if(state.current&&!state.dirty)await selectNode(state.current.ref,true);await loadConstruction();tell('已发布 '+(r.published_count||0)+' 条通过建议，状态：'+buildNames[r.status]);}

$('build-refresh').onclick=run(loadConstruction);
$('build-scan').onclick=run(async()=>{await buildApi('sources.scan');await loadConstruction();tell('已扫描资料，变化或缺失会显示复核状态。');});
$('build-filter').oninput=renderBuildSources;$('build-status').onchange=renderBuildSources;
$('build-import').onclick=run(importBuildSource);$('build-create').onclick=run(createBuildJob);
$('build-file').onchange=run(async()=>{const f=$('build-file').files?.[0];if(f){$('build-import-name').value=f.name;$('build-import-text').value=await f.text();}});
$('build-extract-export').onclick=run(()=>exportBuildPacket('extraction'));$('build-compare-export').onclick=run(()=>exportBuildPacket('comparison'));
$('build-extract-submit').onclick=run(()=>submitBuildResult('extraction'));$('build-compare-submit').onclick=run(()=>submitBuildResult('comparison'));
$('build-preview-button').onclick=run(previewBuild);$('build-publish').onclick=run(publishBuild);
$('build-tools').onclick=run(async()=>{const value=await buildApi('tools');const root=$('build-agent-tools');clear(root);root.append(el('pre',JSON.stringify(value,null,2)));root.hidden=false;});
