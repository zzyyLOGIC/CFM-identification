'use strict';
// File decoding is local. Preview does not call a language model.
const tablePreviewSequence={};
function fileOptions(headers,value,optional=false){return (optional?'<option value="">不选</option>':'<option value="">请选择</option>')+headers.map(h=>`<option value="${esc(h)}" ${h===value?'selected':''}>${esc(h)}</option>`).join('');}
async function previewTable(prefix, reset=false){
 const file=$('#'+prefix+'-file').files[0];if(!file)return;
 const sequence=(tablePreviewSequence[prefix]||0)+1;tablePreviewSequence[prefix]=sequence;
 const host=$('#'+prefix+'-preview');host.textContent='正在本地读取表格…';
 try{
  const data=await upload(file,'preview'), sheet=reset?null:$('#'+prefix+'-sheet').value||null;
  const r=await api('/api/table-preview',{...data,sheet,header_row:Number($('#'+prefix+'-header').value)});
  if(tablePreviewSequence[prefix]!==sequence||$('#'+prefix+'-file').files[0]!==file)return;
  $('#'+prefix+'-sheet').innerHTML=r.sheets.map(s=>`<option value="${esc(s)}" ${s===r.sheet?'selected':''}>${esc(s)}</option>`).join('');
  host.innerHTML=`<p>${r.records??'?'} 条记录；当前工作表：${esc(r.sheet)}。预览仅在本地显示，不调用模型。</p>`+
   `<details><summary>核对前几行与表头</summary><div style="overflow:auto"><table>${r.preview.map(row=>`<tr><th>行 ${row.row}</th>${row.values.map(v=>`<td>${esc(v)}</td>`).join('')}</tr>`).join('')}</table></div></details>`+
   (r.error?`<p class="message error">${esc(r.error)}</p>`:'')+
   (r.other_sheets?.length?`<p class="muted">未选入：${esc(r.other_sheets.join('、'))}。</p>`:'')+
   (r.skipped_preamble_rows?.length?'<p class="muted">表头前有标题或说明；数值导入不把它们当作观测，请把重要方案同时放入业务文字。</p>':'');
  if(prefix==='table'){
   const aliases={id:['node_id','id','对象编号','门店编号'],treatment:['treatment','tool','处理','是否启用'],outcome:['outcome','score','结果','评分'],period:['period','week','时期']};
   for(const key of Object.keys(aliases)){
    const select=$('#map-'+key),prior=reset?'':select.value;
    const proposed=prior||r.headers.find(h=>aliases[key].includes(h.toLowerCase()))||'';
    select.innerHTML=fileOptions(r.headers,proposed,key==='period');
   }
   const old=reset?[]:Array.from($('#map-features').selectedOptions).map(o=>o.value);
   $('#map-features').innerHTML=r.headers.map(h=>`<option value="${esc(h)}" ${old.includes(h)?'selected':''}>${esc(h)}</option>`).join('');
  }
 }catch(e){if(tablePreviewSequence[prefix]===sequence)host.textContent=e.message;}
}
for(const prefix of ['dictionary','table']){
 $('#'+prefix+'-file').onchange=()=>{ $('#'+prefix+'-header').value='1';previewTable(prefix,true);};
 $('#'+prefix+'-refresh').onclick=()=>previewTable(prefix);
 $('#'+prefix+'-sheet').onchange=()=>previewTable(prefix);
}
function resetTableInputs(){
 for(const prefix of ['dictionary','table']){
  tablePreviewSequence[prefix]=(tablePreviewSequence[prefix]||0)+1;
  $('#'+prefix+'-file').value='';$('#'+prefix+'-sheet').innerHTML='';$('#'+prefix+'-header').value='1';$('#'+prefix+'-preview').innerHTML='';
 }
 $('#upload-receipt').innerHTML='';
}
async function buildUploadInput(){
 const docs=Array.from($('#documents').files), nodes=Array.from($('#network-nodes').files), edges=Array.from($('#network-edges').files);
 const d=Array.from($('#dictionary-file').files),t=Array.from($('#table-file').files);
 const all=[...docs,...nodes,...edges,...d,...t];
 if(all.length>10||docs.length+d.length>8)throw Error('最多10份文件，其中普通材料与字段说明合计最多8份。');
 if(all.reduce((n,f)=>n+f.size,0)>20*1024*1024||all.some(f=>f.size>8*1024*1024))throw Error('单文件最多8MB，总计20MB。');
 const files=await Promise.all([...docs.map(f=>upload(f,'document')),...nodes.map(f=>upload(f,'network_nodes')),...edges.map(f=>upload(f,'network_edges')),...t.map(f=>upload(f,'table_data'))]);
 for(const f of d)files.push({...await upload(f,'data_dictionary'),sheet:$('#dictionary-sheet').value||null,header_row:Number($('#dictionary-header').value)});
 let network;
 if(nodes.length||edges.length||selected?.network_files&&$('#use-example-network')?.checked){
  if((nodes.length||edges.length)&&(!nodes.length||!edges.length))throw Error('请同时上传对象表和关系表。');
  network={kind:$('#network-kind').value,completeness:$('#network-completeness').value,description:$('#network-description').value.trim()};
 }
 let table_mapping;
 if(t.length){
  table_mapping={sheet:$('#table-sheet').value||null,header_row:Number($('#table-header').value),id_column:$('#map-id').value,treatment_column:$('#map-treatment').value,
   outcome_column:$('#map-outcome').value,feature_columns:Array.from($('#map-features').selectedOptions).map(o=>o.value),period_column:$('#map-period').value||null,
   treated_value:$('#map-on').value,untreated_value:$('#map-off').value,missing_outcome_values:['',...$('#map-missing').value.split(',').map(x=>x.trim()).filter(Boolean)],
   treatment:$('#map-treatment-text').value,outcome:$('#map-outcome-text').value,context:$('#map-context').value,outcome_kind:$('#map-kind').value,observation_scheme:$('#map-observation').value};
 }
 return {files,...(network?{network}:{}),...(table_mapping?{table_mapping}:{})};
}
function inputSelection(){return {use_example_network:!!(selected?.network_files&&$('#use-example-network')?.checked),example_id:selected?.id||null,...(selected?{source_edits:Array.from(document.querySelectorAll('[data-source]')).filter(e=>e.querySelector('.include-source').checked).map(e=>({source_id:e.dataset.source,text:e.querySelector('.source-edit').value}))}:{})};}
async function checkUploadInput(input){
 const value=await api('/api/input-preview',{reading_mode:$('#reading-mode').value,question:$('#question').value.trim()||'本地文件读取预览，尚未提出识别请求。',...input,...inputSelection()});
 const r=value.receipt, data=value.factual_data, map=value.table_import;
 $('#upload-receipt').innerHTML=`<p><b>${r.ready?'材料已完成本地读取检查':'请先处理以下文件问题'}</b></p>`+
  r.files.map(f=>`<p>${esc(f.name)}：${f.characters} 字符${f.notes.length?'；'+esc(f.notes.join('；')):''}</p>`).join('')+
  (data?`<p>数值数据：${data.nodes} 个对象，${data.observed} 条结果，${data.features} 项特征。${esc(data.note)}</p>`:'')+
  (value.network?`<p>关系文件：${value.network.nodes} 个对象，${value.network.edges} 对联系。已读取全部文件行。</p>`:'')+
  (map?`<p>启用编码 ${esc(map.mapping.treated_value)} → 1；未启用编码 ${esc(map.mapping.untreated_value)} → 0。数值映射未采用的列：${esc(map.unused_columns.join('、')||'无')}；其他工作表：${esc(map.other_sheets.join('、')||'无')}。</p>`:'')+
  (r.issues.length?`<ul class="message error">${r.issues.map(s=>`<li>${esc(s)}</li>`).join('')}</ul>`:'')+
  `<details><summary>查看本次识别可读取的完整材料</summary>${value.sources.map(s=>`<h4>${esc(s.label)}</h4><pre style="white-space:pre-wrap;max-height:320px;overflow:auto">${esc(s.text)}</pre>`).join('')}</details><p class="muted">${esc(r.message)}</p>`;
 if(!r.ready)throw Error('部分附件未完整读取，请按读取回执补充文字版、拆分或移除无关部分；尚未调用模型。');
 return value;
}
$('#preview-input').onclick=async()=>{
 $('#preview-input').disabled=true;
 try{await checkUploadInput(await buildUploadInput());message('本地文件检查完成，没有调用模型。');}
 catch(e){message(e.message,true);}finally{$('#preview-input').disabled=false;}
};
for(const el of document.querySelectorAll('.composer input,.composer select,.composer textarea')){
 el.addEventListener('change',()=>{if($('#upload-receipt').textContent)$('#upload-receipt').textContent='输入已修改；开始读取前会重新核对文件。';});
}
