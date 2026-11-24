'use strict';
const get=id=>document.getElementById(id);
const pretty=v=>JSON.stringify(v,null,2);
let csrf='',catalog={},worksheet=null,generation=0,sourceRun=null;
async function request(path,body){
 const response=await fetch(path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify(body)});
 const data=await response.json();
 if(!response.ok)throw Error(data.error||'请求未完成');
 return data;
}
function message(error){get('status').textContent=error.message;}
function clearReview(){worksheet=null;get('review').hidden=true;get('items').replaceChildren();get('result').textContent='';get('status').textContent='';}
function group(label,entries){
 const parent=document.createElement('optgroup');parent.label=label;
 for(const [id,name] of entries){const option=document.createElement('option');option.value=id;option.textContent=name;parent.append(option);}
 get('operation').append(parent);
}
const savedSchema={intake:'已保存的 business-intake-1，含原文、材料及 A0 候选',query_id:'选中的问题',candidate:'该题的事实读题',request_sha256:'同一份事实读题的原请求摘要',query_review:'生成该事实请求时的原目标复核记录。网页会另请本次审核人核对目标。'};
async function select(){
 const op=get('operation').value,serial=++generation;
 clearReview();get('problem').value='{}';
 const saved=op==='reading';
 get('synthetic-label').hidden=!saved;
 get('description').textContent=saved?'导入已保存的业务读题。在下一页核对目标，逐项审查条件后进入原库。':catalog.native[op]?.description||'先检查所声明的数学问题，按原方法的审核表逐项填写。';
 const schema=saved?savedSchema:await request('/api/math-library?operation='+encodeURIComponent(op));
 if(serial===generation)get('schema').textContent=pretty(schema);
}
function show(data){
 clearReview();get('result').textContent=pretty(data);get('status').textContent=data.state||'已完成';
 if(data.state!=='REVIEW_REQUIRED'||!data.worksheet)return;
 worksheet=data.worksheet;get('review').hidden=false;
 const local=Boolean(worksheet.items);get('native-label').hidden=local;get('sign').hidden=!local;
 if(local){
  for(const [key,text] of Object.entries(worksheet.items)){
   const label=document.createElement('label'),field=document.createElement('input');
   field.type='checkbox';field.dataset.key=key;label.append(field,document.createTextNode(' '+text));get('items').append(label);
  }
 }else{
  const op=get('operation').value,hash=worksheet.problem_sha256||data.problem_sha256,problem=JSON.parse(get('problem').value);
  const decisions=keys=>Object.fromEntries((Array.isArray(keys)?keys:Object.keys(keys||{})).map(k=>[k,'PENDING']));
  const record=keys=>({authority:'',reviewer:'',evidence:'',problem_sha256:hash,decisions:decisions(keys)});
  let template={version:problem.version,...record(worksheet.decisions)};
  if(op==='DAG_GENERAL_ID')Object.assign(template,{unresolved_responses:[],restriction_responses:[]});
  if(op==='MEAN_ORDER_D2_E1')template={version:problem.version,problem_sha256:hash,reviewer:'',evidence:'',synthetic_fixture:false,
    reviewed_target_direction_population:false,reviewed_complete_a4_and_no_unmodeled_constraints:false,
    reviewed_base_assumptions_and_all_arrangement_scope:false,reviewed_bounds_and_each_order_axis:false};
  if(op==='BINARY_IV_LATE_ATE')template={version:problem.version,problem_sha256:hash,reading_review:record(worksheet.reading_decisions),science_review:record(worksheet.science_decisions)};
  get('native-review').value=pretty(template);
 }
}
async function send(review){
 const op=get('operation').value,problem=JSON.parse(get('problem').value);
 if(sourceRun){
  if(!get('source-confirmed').checked)throw Error('请先核对原问和全部材料。');
  show(await request('/api/math-library',{source_run:sourceRun.id,source_binding:sourceRun.uploaded_math.binding,
   source_confirmed:true,review}));return;
 }
 if(op==='reading'){
  const result=await request('/api/library-reading',{intake:problem.intake,query_id:problem.query_id,candidate:problem.candidate,
    request_sha256:problem.request_sha256,query_review:problem.query_review,synthetic:get('synthetic').checked});
  location.href='/#run='+encodeURIComponent(result.id);return;
 }
 show(await request('/api/math-library',{operation:op,problem,review}));
}
get('prepare').onclick=async()=>{get('prepare').disabled=true;try{await send(null);}catch(e){clearReview();message(e);}finally{get('prepare').disabled=false;}};
get('submit-review').onclick=async()=>{
 try{
  if(!worksheet)return;
  let record;
  if(worksheet.items){
   const decisions={};for(const input of get('items').querySelectorAll('input'))decisions[input.dataset.key]=input.checked?'ACCEPTED':'PENDING';
   record={binding:worksheet.binding,decisions,reviewer:get('reviewer').value,evidence:get('evidence').value};
  }else{record=JSON.parse(get('native-review').value);}
  await send(record);
 }catch(e){message(e);}
};
get('problem').oninput=clearReview;
get('export-file').onclick=()=>{
 try{
  const question=get('export-question').value.trim(),operation=get('operation').value;
  if(!question||operation==='reading')throw Error('请填写业务原问并选择数学方法。');
  const problem=JSON.parse(get('problem').value),doc={format:'causal-id.math-request/1',question,operation,problem};
  const url=URL.createObjectURL(new Blob([pretty(doc)],{type:'application/json'})),link=document.createElement('a');
  link.href=url;link.download='math-request.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
 }catch(e){message(e);}
};
get('file').onchange=async()=>{const f=get('file').files[0];if(f){get('problem').value=await f.text();get('synthetic').checked=false;clearReview();}};
get('operation').onchange=()=>select().catch(message);
get('example').onclick=async()=>{
 try{
  const op=get('operation').value,data=await request('/api/math-example?operation='+encodeURIComponent(op));
  if(get('operation').value!==op)return;
  get('problem').value=pretty(data);if(op==='reading')get('synthetic').checked=true;
  clearReview();get('status').textContent='已载入合成材料，请核对规格。';
 }catch(e){message(e);}
};
async function initialize(){
 csrf=(await request('/api/health')).csrf;catalog=await request('/api/math-library');
 group('业务读题',[['reading','导入已保存的规范化读题']]);group('数学规格与诊断',Object.entries(catalog.native).map(([k,v])=>[k,v.label]));
 group('正式研究合同',Object.entries(catalog.research));
 for(const name of Object.values(catalog.classic)){const li=document.createElement('li');li.textContent=name;get('methods').append(li);}
 get('operation').value='requirements';await select();
 const bound=location.hash.match(/^#study=([a-f0-9]{32})$/);
 if(bound){
  const run=await request('/api/run?id='+encodeURIComponent(bound[1])),item=run.uploaded_math;
  if(!item||item.error)throw Error(item?.error||'本次未找到与原问绑定的数学规格。');
  sourceRun=run;get('operation').value=item.operation;await select();get('operation').disabled=true;
  get('example').hidden=true;get('file').disabled=true;get('export-request').hidden=true;
  get('problem').value=pretty(item.problem);get('problem').readOnly=true;get('original-question').textContent=run.case.business_question;
  get('original-materials').textContent=run.case.sources.map(s=>s.label+'\n'+s.text).join('\n\n');
  get('original-math').hidden=false;get('prepare').disabled=true;
  get('source-confirmed').onchange=()=>{clearReview();get('prepare').disabled=!get('source-confirmed').checked;};
  if(run.uploaded_math_review?.source_binding===item.binding)show(run.uploaded_math_review.result);
  return;
 }
 const match=location.hash.match(/^#source=([a-f0-9]{32})$/);
 if(!match)return;
 const run=await request('/api/run?id='+encodeURIComponent(match[1]));get('source-question').textContent=run.case.business_question;get('from-source').hidden=false;
 get('consent').onchange=()=>get('copy').disabled=!get('consent').checked;
 get('copy').onclick=async()=>{get('copy').disabled=true;try{
  const r=await request('/api/library-reading',{source_run:run.id,allow_send:get('consent').checked});location.href='/#run='+encodeURIComponent(r.id);
 }catch(e){message(e);get('copy').disabled=!get('consent').checked;}};
}
initialize().catch(message);
