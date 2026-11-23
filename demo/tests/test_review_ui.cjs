// No browser, server or API: execute the real page script with a minimal DOM.
// From the identification package: node --test demo/tests/test_review_ui.cjs
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {test} = require('node:test');
const app = fs.readFileSync(path.join(__dirname, '../app.js'), 'utf8');
const clone = x => JSON.parse(JSON.stringify(x));

function harness(view) {
  const elements = new Map(), requests = [];
  function element(selector) {
    if (!elements.has(selector)) elements.set(selector, Object.assign(new EventTarget(), {
      hidden:false, disabled:false, open:false, checked:false, value:'', textContent:'', innerHTML:'',
      querySelectorAll:() => [], focus() {}, append() {},
    }));
    return elements.get(selector);
  }
  function readRows(html) {
    for (const match of html.matchAll(/<article class="review-row" id="([^"]+)">([\s\S]*?)<\/article>/g)) {
      const row = element('#'+match[1]), refs = [];
      for (const input of match[2].matchAll(/<input type="checkbox" data-ref="([^"]+)"\s*(checked)?/g))
        refs.push({dataset:{ref:input[1]}, checked:!!input[2]});
      row.reason = {value:''}; row.rejected = match[2].includes('value="REJECTED" selected');
      row.querySelector = s => s === '.reason' ? row.reason : null;
      row.querySelectorAll = s => s === '[data-ref]:checked' ? refs.filter(x=>x.checked) : [];
    }
  }
  let fieldsHTML = '';
  Object.defineProperty(element('#review-fields'), 'innerHTML', {
    get:()=>fieldsHTML, set:html=>{ fieldsHTML=html; readRows(html); }
  });
  const document = {
    querySelector:s=>s.includes('option[value="REJECTED"]')
      ? [...elements.values()].find(x=>x.rejected)||null : element(s),
    querySelectorAll:()=>[], createElement:()=>({}),
  };
  const context = vm.createContext({document, structuredClone, console, Date,
    setTimeout:()=>1, clearTimeout:()=>{},
    fetch:async(url,options)=>{
      if(options.method==='POST') { requests.push(JSON.parse(options.body)); return {ok:true,json:async()=>({})}; }
      return {ok:true,json:async()=>({...clone(view),busy:true})};
    },
  });
  vm.runInContext(app.replace(/init\(\);\s*$/, ''), context);
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../input-files.js'),'utf8'),context);
  const terms=JSON.parse(fs.readFileSync(path.join(__dirname,'../condition_terms.json'),'utf8'));
  const help=JSON.parse(fs.readFileSync(path.join(__dirname,'../condition_explanations.json'),'utf8'));
  assert.deepEqual(Object.keys(help).sort(),Object.keys(terms).sort());
  context.catalog=Object.fromEntries(Object.entries(terms).map(([key,[term,label,category]])=>[key,{key,term,label,category,text:label,explanation:help[key]}]));
  vm.runInContext('conditionTerms=catalog;',context);
  context.fixture = clone(view);
  vm.runInContext('current=fixture; runId=fixture.id; renderRun(current);', context);
  return {element,requests,context,
    summary:()=>clone(vm.runInContext('reviewSummary(current)',context)),
    confirm:()=>element('#confirm-summary').onclick(),
    poll:()=>vm.runInContext('poll()',context),
  };
}

async function openHome(hash='',duringLoad=()=>{}) {
  const page=harness(fixture()), calls=[];
  const catalog=JSON.parse(fs.readFileSync(path.join(__dirname,'../examples.json'),'utf8')).reverse();
  for (const field of ['#network-nodes','#network-edges']) page.element(field).files=[];
  page.context.location={hash};
  page.context.fetch=async(url,options)=>{
    calls.push([options.method,url]);
    if(url==='/api/examples') duringLoad(page);
    const value=url==='/api/examples'?catalog:url.startsWith('/api/run?')?fixture():{};
    return {ok:true,json:async()=>value};
  };
  await vm.runInContext('init()',page.context);
  return {page,calls,store:catalog.find(x=>x.id==='n100')};
}

test('opening the homepage loads the 100-store question and its network files, without starting an analysis',async()=>{
  const {page,calls,store}=await openHome();
  assert.deepEqual(calls,[['GET','/api/health'],['GET','/api/examples']]);
  assert.equal(vm.runInContext('selected.id',page.context),'n100');
  assert.equal(page.element('#question').value,store.case.business_question);
  assert.equal(page.element('#examples').innerHTML.match(/<h3>(.*?)<\/h3>/)[1],store.title);
  assert.match(page.element('#example-sources').innerHTML,/id="use-example-network" checked/);
  for(const f of store.network_files.files) assert.ok(page.element('#example-sources').innerHTML.includes('role='+f.role));
  assert.equal(page.element('#network-completeness').value,store.network_files.declaration.completeness);
  assert.equal(page.element('#allow-send').checked,false);
  page.element('#clear-input').onclick();
  assert.equal(page.element('#question').value,'');
  assert.equal(vm.runInContext('inputSelection().example_id',page.context),null);
});

test('a saved run, a new blank question or an edit during loading takes priority over the default example',async()=>{
  const id='a'.repeat(32);
  const saved=await openHome('#run='+id);
  assert.equal(vm.runInContext('selected',saved.page.context),null);
  assert.ok(saved.calls.some(([,u])=>u==='/api/run?id='+id));
  const blank=await openHome('',p=>p.element('#clear-input').dispatchEvent(new Event('click')));
  assert.equal(vm.runInContext('selected',blank.page.context),null);
  const edited=await openHome('',p=>{p.element('#question').value='自己的研究问题';});
  assert.equal(edited.page.element('#question').value,'自己的研究问题');
  assert.equal(vm.runInContext('selected',edited.page.context),null);
});

test('direct verification uses the report contract across revisions, including wrapped answers',()=>{
  for(const revision of [12,13,14,27]){
    const view=fixture();
    view.review_kind=null;
    view.result={version:'direct-verification/'+revision,decision:'CORRECTED',checks:[],
      effective_answer:{answer:{status:'POINT',functional:'已核验的两端率之差',value:'2/7'}}};
    const h=harness(view),html=h.element('#result').innerHTML;
    assert.match(html,/数学核验已纠正原答/);
    assert.match(html,/已核验的两端率之差/);
    assert.match(html,/2\/7/);
    assert.doesNotMatch(html,/本次检查未通过/);
    assert.equal(vm.runInContext("isDirectVerification({version:'direct-verification/14'})",h.context),false);
  }
});

test('the policy result shows both branches and accepts one explicit reply to the open question',async()=>{
  const view=fixture();
  view.review_kind=null;
  const quote={source_id:'design',quote:'目标档案的两项均值'};
  view.result={version:'direct-verification/21',decision:'CONDITIONAL_RESULT',checks:[],
    proof:{method:'TWO_STAGE_POLICY_BRANCH_MEANS',sources:[quote],terms:[
      {history:'高位',action:'出库',weight:'1/3',mean:'9',contribution:'3',weight_source:quote,source:quote},
      {history:'低位',action:'留库',weight:'2/3',mean:'3',contribution:'2',weight_source:quote,source:quote}]},
    effective_answer:{status:'NEEDS_INPUT',value:null,functional:'加权和为 5',reason:'需核对统计口径',estimate_handoff:{mode:'STOP'}},
    clarification_questions:['这些量是否已经按政策历史标准化？']};
  view.user_question={items:view.result.clarification_questions};
  const h=harness(view),html=h.element('#result').innerHTML;
  assert.match(html,/<td>高位<\/td><td>出库<\/td><td>1\/3<\/td><td>9<\/td><td>3<\/td>/);
  assert.match(html,/<td>低位<\/td><td>留库<\/td><td>2\/3<\/td><td>3<\/td><td>2<\/td>/);
  assert.match(html,/政策水平待核实/);
  h.element('#clarification-answer').value='否';
  await h.element('#send-clarification').onclick();
  assert.ok(h.requests.some(x=>x.action==='clarify'&&x.payload?.text==='否'));
});

test('a within-stratum quota stays attached to the named strata in the disagreement display',()=>{
  const h=harness(fixture());
  h.context.alignment={matched:false,fields:{assignment:{state:'DISAGREEMENT',
    source:{kind:'stratified',groups:[['松亭','云田'],['溪口','西圩']],quotas:[1,1]},
    solver:{kind:'fixed',quota:'每层恰好启用一站'}}}};
  const html=vm.runInContext('networkAlignmentHTML(alignment)',h.context);
  assert.match(html,/第 1 层（松亭、云田）等概率抽 1 个/);
  assert.match(html,/第 2 层（溪口、西圩）等概率抽 1 个/);
  assert.match(html,/每层恰好启用一站/);
  assert.doesNotMatch(html,/全网等概率无放回抽 每层/);
});

test('a scope conflict identifies both the roster and the named subgroup',()=>{
  const h=harness(fixture());
  h.context.alignment={matched:false,source_target_complete:true,fields:{population:{state:'DISAGREEMENT',
    source:{'东港':'1'},solver:{'东港':'1'},model:{scope:'whole',population:'东港'}}}};
  const html=vm.runInContext('networkAlignmentHTML(alignment)',h.context);
  assert.match(html,/范围填写为全体名册，同时填写的评价对象为东港/);
  assert.match(html,/网页已读取名册和关系表/);
  assert.doesNotMatch(html,/权重 whole/);
});

test('the natural-language result displays the probability of each ordered event before any delivery',()=>{
  const h=harness(fixture());
  h.context.local={decision:'CONDITIONAL_RESULT',proof:{binder:'uploaded-network-comparison/1',
    binding_source:'natural-network-materials/1',population:['西港'],ordered_events:['0,1','0,0'],
    joint_probabilities:{西港:{'0,1':'0','0,0':'3/4'}}},
    network_manifest:{nodes:['西港','竹港'],edges:[]},
    effective_answer:{status:'UNDEFINED',functional:'西港左端未定义。',reason:'原比较停估。'}};
  const html=vm.runInContext('directResultHTML(local)',h.context);
  assert.match(html,/左端 \(0,1\).*右端 \(0,0\)/);
  assert.match(html,/<th scope="row">西港<\/th><td>0<\/td><td>3\/4<\/td>/);
  assert.doesNotMatch(html,/估计端已收到/);
});

function fixture(kind='query') {
  const dimension={field_role:'PENDING',value_state:'PENDING',source_coverage:'PENDING'};
  const candidate={version:'network-randomized-effect-reading-1',
    study:{outcome:'本周每小时净收入'},
    target:{first:{own:1,exposure:0},second:{own:0,exposure:0},population:['甲','乙'],aggregation:'EQUAL_MEAN'},
    exposure:{kind:'STRICT_MAJORITY_TIES_LOW'},
    assignment:{kind:'INDEPENDENT_BERNOULLI',probabilities:{'甲':'1/2','乙':'1/2'}},
    scientific_statements:Object.fromEntries(['consistency','assignment_outcome_independence','finite_conditional_means'].map(k=>[k,{status:'PROPOSED'}])),
    information:[{availability:'SYMBOLIC_POPULATION_OPERATOR'}], additional_restrictions:[],unresolved:[]};
  return {id:'a'.repeat(32),query_id:'q1',review_kind:kind,stage:'REVIEW_REQUIRED',busy:false,events:[],downloads:[],
    queries:[{query_id:'q1',business_goal:{value:'自己用助手比不用时，每小时净收入增加多少？'},
      semantics:{target_population:{value:'甲乙两人'},aggregation:{value:'等权平均'}}}],
    attachment_report:{factual_data:{nodes:2,observed:1,features:20}},
    review_templates:{[kind]:{binding_sha256:'fixture-binding',authority:'SYNTHETIC_TEST',
      decisions:{check:['query','source'].includes(kind)?clone(dimension):'PENDING'}}},
    review_sheets:{[kind]:{binding_sha256:'fixture-binding',fields:{
      'common.outcome':{candidate:{value:'本周每小时净收入'}},
      ...(kind==='source'?{'':{candidate}}:{})},source_catalog:{s1:{text:'冻结的测试材料'}}}},
    plan:kind==='query'?null:{reading_candidate:candidate,methods:[{method:'R1A_COMPOSITION'}]},
  };
}

function compact(h, available) {
  assert.equal((h.element('#compact-review').innerHTML.match(/<article>/g)||[]).length,3);
  assert.equal(h.element('#compact-review').hidden,false);
  assert.equal(h.element('#review-details').open,false);
  assert.equal(h.element('#confirm-summary').hidden,false);
  assert.equal(h.element('#confirm-summary').disabled,!available);
}

if (require.main === module) {
  test('rapid query selection sends only one action',async()=>{
    const view=fixture();view.stage='SELECT_QUERY';const h=harness(view);
    const click=()=>h.element('#query-select').onclick({target:{dataset:{query:'q1'}}});
    await Promise.all([click(),click()]);
    assert.equal(h.requests.filter(x=>x.action==='select').length,1);
  });
  test('A0 stopping before audit never claims completed model review',()=>{
    const view=fixture();view.review_kind=null;view.automatic_review=true;
    view.result={state:'READING_RECHECK_REQUIRED',reason_code:'COMPACT_SCHEMA_REJECTED'};
    const html=harness(view).element('#result').innerHTML;
    assert.doesNotMatch(html,/业务解释经过模型自动复核|问题已核对/);
    assert.match(html,/读取或核对未通过/);
  });
  test('fixed-policy R1b uses three cards and one explicit confirmation; missing science still blocks',async()=>{
    const view=fixture('science');view.automatic_review=true;
    const f=view.plan.reading_candidate;f.version='network-source-selections-1';
    f.target={kind:'FIXED_POLICY_MEAN',assignment:{'甲店':1,'乙店':0},population:['甲店','乙店'],aggregation:'EQUAL_MEAN'};
    f.information[0].operator='ALL_OUTCOMES_TOGETHER_WITH_FULL_ASSIGNMENT';
    view.plan.methods=[{method:'R1B_FULL_ASSIGNMENT'}];
    const h=harness(view);compact(h,true);
    assert.match(h.element('#compact-review').innerHTML,/甲店接受处理；乙店不接受处理/);
    assert.match(h.element('#compact-review').innerHTML,/联合总体分布/);
    assert.equal(h.requests.length,0);await h.confirm();assert.equal(h.requests.length,1);
    for(const status of ['NOT_STATED','UNDECIDED','NOT_ADOPTED','CONFLICTING']){
      const missing=clone(view);missing.plan.reading_candidate.scientific_statements.consistency.status=status;
      compact(harness(missing),false);
    }
    view.plan.methods[0].method='R2_MEAN_SIGNATURE';compact(harness(view),false);
  });
  test('explicitly adopted conditions can be confirmed and remain visible; unknowns cannot',async()=>{
    const view=fixture('science');view.automatic_review=true;
    for(const item of Object.values(view.plan.reading_candidate.scientific_statements))item.status='ADOPTED';
    const h=harness(view);compact(h,true);
    assert.match(h.element('#compact-review').innerHTML,/原文明确采用/);
    assert.match(h.element('#compact-review').innerHTML,/实际结果对应实际完整安排/);
    assert.equal(h.requests.length,0);await h.confirm();assert.equal(h.requests.length,1);
    for(const status of ['UNDECIDED','NOT_ADOPTED','NOT_STATED','CONFLICTING']){
      const missing=clone(view);missing.plan.reading_candidate.scientific_statements.consistency.status=status;
      compact(harness(missing),false);
    }
  });
  test('ID result explains both arms and conditions without rendering an injected estimate',()=>{
    const view=fixture('source');view.review_kind=null;view.automatic_review=true;
    view.result={state:'POINT',independent_replay:true,mathematical_claim:{kind:'POINT',target:{
      kind:'DIRECT_EFFECT',first:[1,0],second:[0,0],exposure:'STRICT_MAJORITY_TIES_LOW',
      evaluation_population:['甲','乙'],unit_weights:['1/2','1/2'],outcome:'每小时净收入',
      treatment:'启用助手为1，未启用为0',remaining_assignment:'ORIGINAL_DESIGN_CONDITIONAL'}},
      certificate:{results:[{assumptions_used:['consistency','full_vector_randomization']}]},
      assumption_choices_review:{retained:[{condition:'MEAN_EXPOSURE_SUFFICIENCY',status:'UNDECIDED',required:false}]}};
    view.estimate={state:'ESTIMATED',estimate:{estimate:2.5,estimand:{outcome:'元/小时'}}};
    const h=harness(view),html=h.element('#result').innerHTML;
    assert.match(html,/自己用助手/);assert.match(html,/本人接受处理/);assert.match(html,/减去：本人不接受处理/);
    assert.match(html,/至多一半/);assert.match(html,/识别公式/);assert.match(html,/<math display="block">/);
    assert.match(html,/本次结论依赖的条件/);assert.match(html,/原随机设计在对应条件下平均/);
    assert.doesNotMatch(html,/2\.5000/);assert.doesNotMatch(html,/模型估计/);assert.doesNotMatch(html,/<mfrac><mn>1<\/mn>/);
    assert.match(html,/尚未决定是否采用同伴分组的均值充分性/);assert.match(html,/所用方法不需要/);
    assert.equal(h.element('#clarification').hidden,true);
    assert.equal(h.element('#review').hidden,true);
  });
  test('clarification displays the actual cited passage without showing internal field paths',()=>{
    const view=fixture('source');view.automatic_review=true;
    view.user_question={items:[{question:'检查additional_restrictions的before与after',
      display_question:'这段话只是说明资料范围，还是另外增加计算条件？',source_texts:['只提供各人的总体分布。']}]};
    const h=harness(view),html=h.element('#clarification-questions').innerHTML;
    assert.match(html,/这段话只是说明/);assert.match(html,/只提供各人的总体分布/);
    assert.doesNotMatch(html,/additional_restrictions|before|after/);
  });
  test('automatic workflow hides routine review pages and technical stepper',()=>{
    for(const kind of ['query','source']){
      const view=fixture(kind);view.automatic_review=true;
      const h=harness(view);
      assert.equal(h.element('#review').hidden,true);
      assert.equal(h.element('#steps').hidden,true);
      assert.equal(h.element('#clarification').hidden,true);
    }
  });
  test('only a concrete clarification is shown; source form stays hidden',()=>{
    const view=fixture('source');view.automatic_review=true;
    view.user_question={message:'原材料尚不清楚',items:[{question:'只评价甲乙两人，还是评价全体？'}]};
    const h=harness(view);
    assert.equal(h.element('#review').hidden,true);
    assert.equal(h.element('#clarification').hidden,false);
    assert.match(h.element('#clarification-questions').innerHTML,/只评价甲乙/);
  });
  test('pending scientific adoption is a visible question, never a background approval',()=>{
    const view=fixture('science');view.automatic_review=true;
    const h=harness(view);assert.equal(h.element('#review').hidden,false);assert.equal(h.requests.length,0);
    assert.match(h.element('#review-title').textContent,/请确认本次采用的假设/);
  });
  test('extra notes are shown with their actual content, not only a generic error',()=>{
    const view=fixture('source');view.plan.reading_candidate.additional_restrictions=[{text:'仅说明资料范围',source_ids:[]}];
    const h=harness(view);assert.match(h.element('#review-issues').innerHTML,/仅说明资料范围/);
    assert.match(h.element('#review-issues').innerHTML,/未必是材料缺失/);
    assert.equal(h.element('#request-recheck').disabled,true); // old server: no invented action
  });
  for (const kind of ['query','source','science','data']) test(`legacy ${kind}: three cards, one action, unchanged bound records`,async()=>{
    const view=fixture(kind), before=clone(view), h=harness(view);
    compact(h,true); assert.equal(h.requests.length,0);
    assert.equal(h.summary().is_approval,false);
    assert.ok(h.element('#compact-review').innerHTML.includes('每小时净收入'));
    await h.confirm();
    assert.equal(h.requests.length,1);
    const payload=h.requests[0].payload;
    assert.equal(payload.kind,kind);
    assert.equal(payload.records[kind].binding_sha256,view.review_templates[kind].binding_sha256);
    assert.equal(payload.records[kind].authority,'SYNTHETIC_TEST');
    assert.equal(typeof payload.records[kind].decisions.check==='object'
      ?payload.records[kind].decisions.check.value_state:payload.records[kind].decisions.check,'ACCEPTED');
    assert.deepEqual(view,before);
  });
  test('null, partial and malformed summaries use the same closed default',()=>{
    for(const summary of [null,{}, {cards:[]}, {cards:[null,null,null]}, {cards:'invalid'}]){
      const view=fixture();view.review_summary=summary;compact(harness(view),true);
    }
  });
  test('valid backend summary is kept; explicit refusal is never replaced',async()=>{
    const view=fixture();view.review_summary=harness(view).summary();
    view.review_summary.cards[0].lines=['来自后台的当前目标'];
    const h=harness(view);compact(h,true);assert.ok(h.element('#compact-review').innerHTML.includes('来自后台'));
    view.review_summary.compact_confirmation_available=false;
    const stopped=harness(view);compact(stopped,false);await stopped.confirm();assert.equal(stopped.requests.length,0);
  });
  test('missing records, sources, stale binding and complex records stay collapsed and block',async()=>{
    const variants=[r=>{r.review_templates={};},r=>{r.review_sheets.query.source_catalog={};},
      r=>{r.review_templates.query.binding_sha256='stale';},
      r=>{r.review_templates.query.material_decisions={s1:'PENDING'};},r=>{r.review_kind='notes';}];
    for(const change of variants){const view=fixture();change(view);const h=harness(view);compact(h,false);await h.confirm();assert.equal(h.requests.length,0);}
  });
  test('unknown science may be read as unknown, but cannot be approved as adopted',async()=>{
    for(const status of ['NOT_STATED','UNDECIDED','REJECTED']){
      const source=fixture('source');source.plan.reading_candidate.scientific_statements.consistency.status=status;
      const reading=harness(source);compact(reading,true);
      const science=fixture('science');science.plan.reading_candidate.scientific_statements.consistency.status=status;
      const approval=harness(science);compact(approval,false);await approval.confirm();assert.equal(approval.requests.length,0);
      assert.ok(approval.element('#compact-review').innerHTML.includes({NOT_STATED:'原文未声明',UNDECIDED:'尚未决定',REJECTED:'不采用'}[status]));
    }
  });
  test('two-policy confirmation displays signed endpoints and blocks scope mismatch',async()=>{
    const view=fixture('science'),f=view.plan.reading_candidate;
    f.version='network-policy-contrast-reading-1';
    f.target={kind:'FIXED_POLICY_MEAN_DIFFERENCE',operation:'FIRST_MINUS_SECOND',
      first:{assignment:{a:1,b:1},population:['a','b'],aggregation:'EQUAL_MEAN'},
      second:{assignment:{a:0,b:0},population:['a','b'],aggregation:'EQUAL_MEAN'},shared_outcome_and_context:{value:true}};
    view.plan.methods=[{method:'R1B_ENDPOINT_DIFFERENCE'}];
    const h=harness(view);compact(h,true);assert.match(h.element('#compact-review').innerHTML,/减去第二方案/);
    assert.match(h.element('#compact-review').innerHTML,/2 个评价对象/);
    await h.confirm();assert.equal(h.requests.length,1);
    f.target.second.population=['a'];const blocked=harness(view);compact(blocked,false);await blocked.confirm();assert.equal(blocked.requests.length,0);
  });
  test('two-stage exclusion is never silently included in one-click approval',async()=>{
    const view=fixture('science'),f=view.plan.reading_candidate;
    f.assignment={kind:'TWO_STAGE_QUOTA_MIXTURE'};
    compact(harness(view),false);
    f.first_stage_exclusion={status:'PROPOSED'};const h=harness(view);compact(h,true);
    assert.match(h.element('#compact-review').innerHTML,/名额方案本身不再直接影响结果/);
    f.first_stage_exclusion.status='NOT_ADOPTED';compact(harness(view),false);
  });
  test('replayed design-specific anchor conditions are shown with the final formula',()=>{
    const h=harness(fixture());
    h.context.evidence={independent_replay:true,certificate:{assumptions_used:['consistency']},answers:[{
      independent_replay:true,native_evidence:{result:{source_batch:{anchor:{result:{assumptions_used:['first_stage_profile_no_direct_outcome_effect']}}}}}}]};
    assert.equal(vm.runInContext('certifiedAssumptions(evidence).includes("first_stage_profile_no_direct_outcome_effect")',h.context),true);
    h.context.evidence.independent_replay=false;
    assert.equal(vm.runInContext('certifiedAssumptions(evidence).includes("first_stage_profile_no_direct_outcome_effect")',h.context),false);
  });
  test('extra restrictions, unresolved facts and unsupported routes cannot be bulk approved',async()=>{
    for(const change of [r=>r.plan.reading_candidate.additional_restrictions.push('额外等式'),
      r=>r.plan.reading_candidate.unresolved.push('总体信息缺失'),r=>r.plan.methods[0].method='OTHER',
      r=>r.plan.rejected_fields=['/target']]){
      const view=fixture('science');change(view);const h=harness(view);compact(h,false);await h.confirm();assert.equal(h.requests.length,0);
    }
  });
  test('stored or user-selected rejection is never overwritten',async()=>{
    const view=fixture();view.review_templates.query.decisions.check.value_state='REJECTED';
    const stored=harness(view);compact(stored,false);await stored.confirm();assert.equal(stored.requests.length,0);
    const edited=harness(fixture());edited.element('#r0').rejected=true;await edited.confirm();
    assert.equal(edited.requests.length,0);assert.equal(edited.element('#review-details').open,false);
    assert.match(edited.element('#review-message').textContent,/拒绝/);
  });
  test('refreshing an unchanged legacy binding still allows exactly one submission',async()=>{
    const h=harness(fixture());
    vm.runInContext('current=structuredClone(fixture); renderRun(current);',h.context);
    compact(h,true);
    await Promise.all([h.confirm(),h.confirm()]);assert.equal(h.requests.length,1);
  });
  test('new details are opt-in; polling does not close details the user opened',()=>{
    const h=harness(fixture());h.element('#review-details').open=true;
    vm.runInContext('renderRun(current)',h.context);assert.equal(h.element('#review-details').open,true);
  });
  test('summary escapes material text; the detailed submit button is inside the closed disclosure',()=>{
    const view=fixture();view.queries[0].business_goal.value='<img src=x onerror=alert(1)>';
    const h=harness(view);assert.ok(!h.element('#compact-review').innerHTML.includes('<img'));
    const html=fs.readFileSync(path.join(__dirname,'../index.html'),'utf8');
    assert.match(html,/<details id="review-details" class="optional">/);
    assert.match(html,/<details id="review-details"[\s\S]*id="review-fields"[\s\S]*id="submit-review"[\s\S]*<\/details>/);
  });
}
module.exports={harness};

function registeredFixture(){
 const v=fixture('science');v.plan={state:'REVIEW_REQUIRED',plan_sha256:'p'.repeat(64),methods:[{method:'DAG_CLASSICAL_FRONTDOOR'}]};
 const sheet={version:'dag-frontdoor-1',problem_sha256:'d'.repeat(64),decisions:{complete_causal_graph_and_latents:'PENDING'}};
 v.review_sheets={native:clone(sheet)};v.review_templates={native:{...clone(sheet),authority:'SYNTHETIC_TEST',reviewer:'',evidence:''}};
 v.review_summary={contract:'registered-web-review-1',plan_sha256:v.plan.plan_sha256,methods:['DAG_CLASSICAL_FRONTDOOR'],
  review_bindings:{native:{identity:{version:sheet.version,problem_sha256:sheet.problem_sha256},decisions:Object.keys(sheet.decisions)}},
  cards:[{title:'目标',lines:['培训干预分布']},{title:'科学条件',lines:['完整图及潜变量；理想干预']},{title:'总体信息',lines:['已知观测联合总体分布及正支持']}],
  compact_confirmation_available:true,needs_individual_attention:[],confirmation_label:'确认采用上述条件并识别',is_approval:false};
 return v;
}
test('registered DAG confirmation preserves native identity without inventing a common hash',async()=>{
 const h=harness(registeredFixture());assert.equal(h.summary().compact_confirmation_available,true);
 await h.confirm();assert.equal(h.requests.length,1);
 const r=h.requests[0].payload.records.native;assert.equal(r.problem_sha256,'d'.repeat(64));assert.equal('binding_sha256' in r,false);
 assert.equal(r.decisions.complete_causal_graph_and_latents,'ACCEPTED');
});
test('registered summary cannot conceal changed plan, method, refused key or omitted worksheet',()=>{
 for(const mutate of [v=>v.review_summary.plan_sha256='stale',v=>v.review_summary.methods=['OTHER'],
  v=>v.review_templates.native.decisions.complete_causal_graph_and_latents='REJECTED',
  v=>delete v.review_summary.review_bindings.native,v=>v.review_templates.native.problem_sha256='changed']){
  const v=registeredFixture();mutate(v);assert.equal(harness(v).summary().compact_confirmation_available,false);
 }
});
test('registered symbolic R2 and R3 render signature condition, not a zero-support full arrangement',()=>{
 const h=harness(registeredFixture());
 for(const route of ['R2','R3_MEAN_SIGNATURE']){
  h.context.resultFixture={certificate:{route},mathematical_claim:{kind:'POINT',target:{assignment:[1,1],kind:'FIXED_FULL_ASSIGNMENT_POLICY_MEAN'}}};
  const html=vm.runInContext('formulaHTML(resultFixture)',h.context);
  assert.match(html,/gᵢ\(a\)/);assert.doesNotMatch(html,/T = \(1, 1\)/);
 }
});
test('DAG formula comes from the certified functional and partial fractions render as fractions',()=>{
 const h=harness(registeredFixture());h.context.resultFixture={mathematical_claim:{kind:'POINT',functional:{operation:'COVARIATE_ADJUSTMENT',outcome:'Y',treatment:'T',sum_over:['Z'],conditional:{outcomes:['Y'],given:['T','Z']},marginal:{variables:['Z']}}}};
 const shown=vm.runInContext('formulaHTML(resultFixture)',h.context);
 assert.match(shown,/do\(x\)/);assert.match(shown,/<dt>X<\/dt><dd>T /);
 assert.doesNotMatch(shown.match(/<math[\s\S]*?<\/math>/)[0],/do\(T\)/);
 h.context.resultFixture={mathematical_claim:{representation:'EXACT_IDENTIFIED_INTERVAL',target:{kind:'FIXED_FULL_ASSIGNMENT_POLICY_CONTRAST'},interval:['1/5','1']}};
 const html=vm.runInContext('formulaHTML(resultFixture)',h.context);assert.match(html,/<mfrac>/);assert.match(html,/Δ/);
});

test('symbol aliases are derived from variable roles and preserve multi-variable adjustment',()=>{
 const h=harness(registeredFixture());
 const f={operation:'BACKDOOR_ADJUSTMENT',outcome:'康复',treatment:'治疗',sum_over:['年龄','病情'],conditional:{outcomes:['康复'],given:['治疗','年龄','病情']},marginal:{variables:['年龄','病情']}};
 h.context.f=f;
 const math=vm.runInContext('dagFormula(f)',h.context),legend=vm.runInContext('symbolLegend(f)',h.context);
 assert.match(math,/z1, z2/);assert.doesNotMatch(math,/康复|治疗|年龄|病情/);
 for(const word of ['康复','治疗','年龄','病情'])assert.ok(legend.includes(word));
 h.context.f={...f,treatment:'投放',outcome:'购买',sum_over:['地区','价格'],conditional:{outcomes:['购买'],given:['投放','地区','价格']},marginal:{variables:['地区','价格']}};
 assert.equal(vm.runInContext('dagFormula(f)',h.context),math);
 assert.doesNotMatch(vm.runInContext('symbolLegend(f)',h.context),/康复|治疗/);
 h.context.f.conditional.given.push('未声明变量');assert.throws(()=>vm.runInContext('dagFormula(f)',h.context),/Unbound/);
});

test('mean-box formulas keep symbolic parameters separate from numerical substitution',()=>{
 const h=harness(registeredFixture());
 const claim={kind:'PARTIAL',representation:'PARAMETRIC_IDENTIFIED_INTERVAL',
   target:{kind:'FIXED_FULL_ASSIGNMENT_POLICY_CONTRAST'},
   bound_formula:{lower:{constant:'1/4',terms:{b1:'-1'}},upper:{constant:'3/4',terms:{b1:'-1'}},
     parameters:[{symbol:'b1',cell:['<station>',0,2],lower:'1/4',upper:'3/4'}]}};
 h.context.r={mathematical_claim:claim};
 let html=vm.runInContext('formulaHTML(r)',h.context);
 assert.match(html,/<msub><mi>b<\/mi><mn>1<\/mn><\/msub>/);
 assert.match(html,/尚未代入总体数值/);assert.doesNotMatch(html,/代入本次提供/);
 assert.match(html,/&lt;station&gt;/);assert.match(html,/<mfrac>/);
 assert.match(html,/<mtable/);assert.match(html,/识别范围为/);
 h.context.r.mathematical_claim={...claim,representation:'EXACT_IDENTIFIED_INTERVAL',interval:['-1/4','1/4']};
 html=vm.runInContext('formulaHTML(r)',h.context);assert.match(html,/代入本次提供的总体数值/);
 assert.equal((html.match(/<math display="block">/g)||[]).length,2);
});

test('result conditions use executed evidence and never example-authored defaults',()=>{
 const h=harness(fixture());h.context.r={state:'POINT',independent_replay:true,certificate:{assumptions_used:['consistency','full_vector_randomization']}};
 const html=vm.runInContext('resultHTML(r,null,["预写答案：无混杂、无干扰"])',h.context);
 assert.match(html,/Consistency/);assert.match(html,/Randomization/);assert.doesNotMatch(html,/预写答案|No interference|Conditional exchangeability/);
 assert.match(html,/这些假设在本题中是什么意思/);assert.match(html,/不要求各对象分别独立抽签/);assert.match(html,/本次记录的正式条件/);
 h.context.unknown={key:'unregistered',text:'仅在本周适用',category:'science'};
 assert.match(vm.runInContext('conditionDetailHTML(unknown)',h.context),/暂无简明解释/);
 assert.doesNotMatch(vm.runInContext('conditionDetailHTML(unknown)',h.context),/随机分配|Randomization/);
 h.context.r.certificate={source_batch_sha256:'x'};h.context.r.condition_record={origin:'EXECUTED_CERTIFICATES',source_batch_sha256:'different',keys:['consistency']};
 assert.equal(vm.runInContext('resultConditions(r).length',h.context),0);
 h.context.r.condition_record.source_batch_sha256='x';assert.equal(vm.runInContext('resultConditions(r)[0].term',h.context),'Consistency');
});

test('compact science cards separate decisions from context and retain every complete statement',()=>{
 const v=registeredFixture();
 v.review_summary.condition_items=v.review_summary.cards[1].lines.map(text=>({text,term:'Consistency',label:'一致性',category:'science'}));
 const h=harness(v),html=h.element('#compact-review').innerHTML;
 assert.match(html,/① 研究目标/);assert.match(html,/② 研究假设/);assert.match(html,/③ 可用信息/);
 assert.match(html,/需你确认采用/);assert.match(html,/<details id="confirmation-scope" class="optional">/);
 for(const c of v.review_summary.cards)for(const text of c.lines)assert.ok(html.includes(text));
 assert.deepEqual(h.summary().review_bindings,v.review_summary.review_bindings);
});

function informationFixture(){
 const v=fixture('information');const sheet={version:'network-contrast-information-evidence-review-1',binding_sha256:'f'.repeat(64),
  source_catalog:{a:{doc_id:'总体均值表',text:'甲店本人与同伴不使用时总体均值为1/2。'},b:{doc_id:'研究说明',text:'甲指名册第一店；本周。'},c:{doc_id:'总体均值表',text:'乙店总体均值为1/3。'}},entry_source_ids:{0:['a','b'],1:['c','b']}};
 v.review_sheets={information:sheet};v.review_templates={information:{version:sheet.version,binding_sha256:sheet.binding_sha256,authority:'SYNTHETIC_TEST',disposition:'PENDING',table_source_ids:[],supporting_source_ids:[],reviewer:'',evidence:''}};
 return v;
}
test('information question requires explicit document choice and preserves exact source partition',async()=>{
 const v=informationFixture(),h=harness(v);assert.equal(h.element('#confirm-summary').disabled,true);
 assert.match(h.element('#compact-review').innerHTML,/总体均值表/);await h.confirm();assert.equal(h.requests.length,0);
 vm.runInContext('informationChoices[current.id+":"+current.review_sheets.information.binding_sha256]="总体均值表"',h.context);
 await h.confirm();const r=h.requests[0].payload.records.information;
 assert.deepEqual(r.table_source_ids,['a','c']);assert.deepEqual(r.supporting_source_ids,['b']);assert.equal(r.disposition,'ACCEPTED');
 assert.equal(v.review_templates.information.disposition,'PENDING');
});
test('information choice cannot skip an entry, reuse stale review, or overwrite refusal',()=>{
 for(const mutate of [v=>v.review_sheets.information.entry_source_ids[1]=['b'],v=>v.review_templates.information.binding_sha256='0'.repeat(64),v=>v.review_templates.information.disposition='REJECTED']){
  const v=informationFixture();mutate(v);const h=harness(v);
  assert.throws(()=>vm.runInContext('informationRecords(current,{[current.id+":"+current.review_sheets.information.binding_sha256]:"总体均值表"})',h.context));
 }
});

test('clarifications ask for business facts without accepting assumptions or changing results',()=>{
 const h=harness(fixture());
 h.context.question='请明确比较两端的自身处理、同伴状态及相减方向。';
 assert.match(vm.runInContext('clarificationText(question,{})',h.context),/本人做什么、相关的人或单位做什么/);
 h.context.question='请说明理论识别可以使用的总体观测信息及覆盖范围；有限样本不能代替。';
 assert.match(vm.runInContext('clarificationText(question,{})',h.context),/只有这一次的记录/);
 assert.doesNotMatch(vm.runInContext('clarificationText(question,{})',h.context),/请提供精确总体/);
 h.context.question='本次计算需要以下条件，请说明是否采用：“实际观察结果对应实际完整安排下的潜在结果”。不知道或尚未决定也可以说明。';
 assert.match(vm.runInContext('clarificationText(question,{})',h.context),/不采用.*尚未决定/);
 h.context.question='请说明甲店与乙店是否在同一天接种。';
 assert.equal(vm.runInContext('clarificationText(question,{})',h.context),h.context.question);
 h.context.pending={busy:false,user_question:{items:[{question:'这句话是否表示尚未决定？',source_texts:['尚未决定<script>bad()</script>']}]},result:{state:'NEEDS_INPUT',backend_called:false}};
 const before=JSON.stringify(h.context.pending);vm.runInContext('renderClarification(pending)',h.context);
 assert.equal(JSON.stringify(h.context.pending),before);
 assert.match(h.element('#clarification-questions').innerHTML,/需要说明的原文/);
 assert.match(h.element('#clarification-questions').innerHTML,/&lt;script&gt;/);
 assert.doesNotMatch(h.element('#clarification-questions').innerHTML,/<script>/);
 h.context.r={state:'NEEDS_INPUT',clarification_questions:['请说明参与范围。']};
 assert.doesNotMatch(vm.runInContext('resultHTML(r,null,{questionsInForm:true})',h.context),/class="stop-questions"/);
 assert.match(vm.runInContext('resultHTML(r)',h.context),/class="stop-questions"/);
});

test('stop explanations distinguish reading, unknown, refusal and unsupported constraints without changing results',()=>{
 const h=harness(fixture());
 const cases=[
  [{state:'READING_RECHECK_REQUIRED',reason_code:'COMPACT_SCHEMA_REJECTED',clarification_questions:['请补充条件']},'reading',/无需重写/,/读取记录中还需核对/],
  [{state:'NEEDS_INPUT',reason_code:'ALL_MODEL_NODES_REQUIRE_MEAN_SUFFICIENCY'},'missing',/尚未决定/,/默认采用/],
  [{state:'ADAPTER_NOT_CONNECTED',reason_code:'DECLARED_MODEL_EXCLUDES:consistency'},'declined',/本次未采用/,/请补充条件/],
  [{state:'ADAPTER_NOT_CONNECTED',reason_code:'ADDITIONAL_INFORMATION_OR_RESTRICTIONS_REQUIRE_SEPARATE_ADAPTER',reading_candidate:{additional_restrictions:[{text:'甲乙总体均值相等<script>x</script>'}]}},'coverage',/当前方法不能把它们全部纳入/,/<script>/],
  [{state:'NEEDS_INPUT',reason_code:'UNKNOWN_CODE'},'missing',/也可能是模型遗漏/,/原材料确实缺项/],
  [{state:'READING_RECHECK_REQUIRED',reason_code:'TARGET_FIELD_CONTRACT_CONFLICT_AFTER_REREAD'},'reading',/目标类别和比较两端相互冲突/,/请补充条件/],
  [{state:'ADAPTER_NOT_CONNECTED',reason_code:'ADDITIONAL_EFFECT_MODEL_REQUIRES_SEPARATE_ADAPTER',reading_candidate:{additional_restrictions:[{text:'不另行假定暴露充分性'}]}},'coverage',/若读取有误，应重读/,/请补充条件/],
 ];
 for(const [r,kind,yes,no] of cases){
  h.context.r=clone(r);const before=JSON.stringify(h.context.r);
  assert.equal(vm.runInContext('stopExplanation(r).kind',h.context),kind);
  const html=vm.runInContext('resultHTML(r)',h.context);assert.match(html,yes);assert.doesNotMatch(html,no);
  assert.equal(JSON.stringify(h.context.r),before);
 }
 assert.match(vm.runInContext('finiteClarification("请补充原文中的分配或科学条件字段：assignment.treated_sets/set_probabilities or unit_weights")',h.context),/各个名单的中签机会/);
 assert.match(vm.runInContext('finiteClarification("请说明理论识别可以使用的总体观测信息及覆盖范围；有限样本不能代替。")',h.context),/若附件已有说明，请指出位置/);
});

test('usage page omits the coverage catalog and shows limits only for an actual size stop',()=>{
 const h=harness(fixture());
 vm.runInContext('renderUploadLimits()',h.context);assert.match(h.element('#network-import-limit').textContent,/由当前服务检查/);
 h.context.metadata={groups:[{title:'实际登记能力',description:'范围有限'}],notes:['未接通的接口另列'],import_limits:{nodes:2000,edges:50000},finite_partial:{max_nodes:12,extended_design_max_nodes:8}};
 vm.runInContext('coverageInfo=metadata;renderUploadLimits()',h.context);
 assert.match(h.element('#network-import-limit').textContent,/2000 个对象/);
 const source=fs.readFileSync(path.join(__dirname,'../index.html'),'utf8');assert.doesNotMatch(source,/coverage-help|coverage-content|上方能力范围|<span>结果说明<\/span>/);
 h.context.r={state:'POINT',methods:[{method:'R1A_COMPOSITION'}],facts:{study:{nodes:Array(100).fill('a')}}};
 assert.equal(vm.runInContext('methodScopeHTML(r)',h.context),'');
 h.context.r={state:'ADAPTER_NOT_CONNECTED',reason_code:'EXTENDED_DESIGN_EXACT_ENUMERATION_LIMIT_8',reading_candidate:{study:{nodes:Array(9).fill('a')},assignment:{kind:'RERANDOMIZED_BALANCED'}}};
 assert.match(vm.runInContext('resultHTML(r)',h.context),/最多支持 8 个对象/);
 assert.match(vm.runInContext('stopExplanation(r).title',h.context),/规模上限/);
 h.context.r.reason_code='BOUNDED_D1_D8_E1_E5_FINITE_DOMAIN_REQUIRED';
 assert.doesNotMatch(vm.runInContext('stopExplanation(r).title',h.context),/规模上限/);
 h.context.r={state:'PARTIAL',methods:[{method:'BOUNDED_POLICY_MEAN_FINITE'}],mathematical_claim:{representation:'EXACT_IDENTIFIED_INTERVAL'}};
 assert.equal(vm.runInContext('methodScopeHTML(r)',h.context),'');
 h.context.r={state:'REVIEW_REQUIRED',methods:[{method:'MEAN_ORDER_D2_E1'}]};
 assert.equal(vm.runInContext('methodScopeHTML(r)',h.context),'');
});
