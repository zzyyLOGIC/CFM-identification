/* Display only replayed certificate algebra; no browser solver or guessed regions. */
'use strict';
const SymbolicBounds=(()=>{
 const esc=x=>String(x).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const q=x=>{if(!/^-?\d+(?:\/\d+)?$/.test(x))throw Error('Invalid rational');const [a,b]=x.split('/');return b?'\\frac{'+a+'}{'+b+'}':a;};
 const sum=terms=>{
  const parts=[];
  for(const [value,symbol] of terms){
   if(value==='0')continue;
   const negative=value.startsWith('-'),absolute=negative?value.slice(1):value;
   parts.push((negative?'-':parts.length?'+':'')+(symbol&&absolute==='1'?'':q(absolute))+symbol);
  }
  return parts.join('')||'0';
 };
 const affine=v=>sum(v.map((x,i)=>[x,i?'\\,p_{'+i+'}':'']));
 const math=x=>ModelMath.render('\\['+x+'\\]');
 function html(c,problem=null){
  if(c.version!=='symbolic-mean-joint-1')throw Error('Wrong certificate');
  const unique=side=>[...new Map(c[side].map(x=>[JSON.stringify(x.value),x.value])).values()];
  const low=unique('lower'),high=unique('upper');
  if(!low.length||!high.length)return '<p>声明的参数范围内没有可行均值模型。</p>';
  const extrema=(xs,name,op)=>xs.length===1?affine(xs[0]):xs.length<=12?'\\'+op+'\\left\\{'+xs.map(affine).join(',\\;')+'\\right\\}':'\\'+op+'_{1\\le j\\le '+xs.length+'} '+name+'_{j}(p)';
  let h=math('L(p)='+extrema(low,'\\ell','max'))+math('U(p)='+extrema(high,'u','min'))+math('L(p)\\le\\theta\\le U(p)');
  h+='<p>θ 是本次问题的目标。p 是材料中保留的总体参数；这些公式仅用于下述参数范围内、同时满足全部限制的模型。</p>';
  h+=math(c.parameter_domain.map((x,i)=>q(x.lower)+'\\le p_{'+(i+1)+'}\\le '+q(x.upper)).join(',\\quad'));
  h+='<p>'+c.parameters.map((x,i)=>'p'+(i+1)+'：'+esc(problem?.parameters?.find(p=>p.id===x)?.description||x)).join('；')+'。</p>';
  if(problem){
   const ids=problem.coordinates.map(x=>x.id),terms=co=>Object.entries(co).map(([k,v])=>[v,'\\,m_{'+(ids.indexOf(k)+1)+'}']),linear=co=>sum(terms(co));
   const rhs=a=>affine([a.constant,...c.parameters.map(k=>a.coefficients[k]||'0')]);
   h+='<details><summary>本次求界采用的均值和限制</summary><p>采用材料明确给出的完整有限均值模型；未知参数是总体信息，不是样本估计值。</p>';
   h+='<p>'+problem.coordinates.map((x,i)=>'m'+(i+1)+'：'+esc(x.description)).join('；')+'。</p>';
   h+=math('\\theta='+sum([...terms(problem.target),[problem.target_offset.constant,''],...c.parameters.map((k,i)=>[problem.target_offset.coefficients[k]||'0','\\,p_{'+(i+1)+'}'])]));
   for(const x of problem.coordinates){const name='m_{'+(ids.indexOf(x.id)+1)+'}';h+=math(rhs(x.lower)+'\\le '+name+'\\le '+rhs(x.upper));if(x.known)h+=math(name+'='+rhs(x.known));}
   if(problem.outcome_domain==='BINARY')h+='<p>结果为0/1，每个总体均值还须位于[0,1]。</p>';
   for(const x of problem.constraints)h+='<p>'+esc(x.adoption==='ADOPTED'?'采用':x.adoption==='NOT_ADOPTED'?'不采用':'尚未决定')+'：</p>'+math(linear(x.coefficients)+({EQ:'=',LE:'\\le ',GE:'\\ge '}[x.relation])+rhs(x.rhs));
   h+='</details>';
  }
  if(low.length>12||high.length>12)h+='<details><summary>展开上下界中的各个表达式</summary>'+low.map((v,i)=>math('\\ell_{'+(i+1)+'}(p)='+affine(v))).join('')+high.map((v,i)=>math('u_{'+(i+1)+'}(p)='+affine(v))).join('')+'</details>';
  const regions=[...new Map(c.lower.map(x=>[JSON.stringify(x.region.map(r=>r.le_zero)),x.region])).values()];
  h+='<details><summary>哪些参数取值与研究条件相容</summary><p>在上面的参数范围内，至少满足以下一组即可；每组内的条件须同时满足。没有满足任何一组时，材料的限制互相冲突，不返回区间。</p>'+regions.map((r,i)=>'<p>第 '+(i+1)+' 组：</p>'+math(r.length?r.map(x=>affine(x.le_zero)+'\\le 0').join(',\\quad'):'\\text{整个已声明参数范围}')).join('')+'</details>';
  return h;
 }
 return {html};
})();
