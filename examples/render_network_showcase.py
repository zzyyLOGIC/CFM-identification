"""Combine and render existing identification results on a common network."""
import json


def combine(parts,er300):
    first=parts['r1a']
    if first['graph_fingerprint']!=parts['r1b']['graph_fingerprint']:
        raise ValueError('R1a/R1b demonstration network fingerprint mismatch')
    if er300 and first['graph_fingerprint']!=parts['r2']['graph_fingerprint']:
        raise ValueError('R2 hypothetical D2 must reuse the same ER300 graph')
    if first['node_count']!=300 and er300:
        raise ValueError('ER300 showcase expected a 300-node graph')
    cases=[*parts['r1a']['business_cases'], *parts['r1b']['business_cases'],
           *parts['r2']['business_cases']]
    return dict(release='v2.1 A4 hardened + business routing',
        network='shared ER300 fixed graph' if er300 else 'toy network + star D2',
        node_count=first['node_count'],arm_count=first['arm_count'],
        point_arm_count=first['point_arm_count'],
        batch_sha256=first['batch_sha256'],source_spec_sha256=first['source_spec_sha256'],
        arm_matrix_status=first['arm_matrix_status'],
        arm_matrix_support_exact=first['arm_matrix_support_exact'],
        arm_matrix_support=first['arm_matrix_support'],arm_labels=first['arm_labels'],
        business_cases=cases,
        business_verified=sum(c['status']=='POINT' for c in cases),
        business_rejected=sum(c['status']!='POINT' for c in cases),
        source_notes={
            'A4':'Explicit SYMBOLIC population information declarations, not measured outcomes',
            'A5':'R2 mean-signature sufficiency separately admitted ONLY in hypothetical D2',
            'D2':'Hypothetical fixed-quota protocol on same graph, not the shared Bernoulli Estimation protocol',
            'Estimation':'No PFN, numerical effect, or simulator truth used in Identification',
        })


def make_html(record):
    body=json.dumps(record,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
    return '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>Causal-IDFM — Network Identification Showcase v2.1</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{font-family:Inter,system-ui,-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;color:#16263a;background:#f5f7fb}
*{box-sizing:border-box}body{margin:0}main{max-width:1160px;margin:auto;padding:34px 24px 64px}
h1{font-size:32px;letter-spacing:-.5px;margin:12px 0 10px}h2{font-size:19px;margin:0 0 16px}
p{line-height:1.65;color:#556578}.eyebrow{color:#1a6a86;font-weight:700;letter-spacing:.12em;font-size:12px}
header{padding-bottom:18px;border-bottom:1px solid #dde4ed}.sub{max-width:820px}
.metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:22px 0}
.metric{background:white;border:1px solid #e0e7ef;padding:20px;border-radius:14px}.metric b{font-size:29px;display:block;color:#174f76}
.metric span{font-size:12px;color:#6b7b8f}.section{background:#fff;border:1px solid #e0e7ef;border-radius:16px;padding:22px;margin:20px 0}
.key{display:flex;gap:14px;flex-wrap:wrap;color:#66788c;font-size:12px}.dot{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:4px}
.cases{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.case{border:1px solid #dee5ed;border-radius:12px;padding:16px;background:#fcfdff}
.badge{font-size:11px;font-weight:750;border-radius:999px;padding:4px 9px;display:inline-block;background:#e2f3eb;color:#087454}
.badge.block{background:#fdf0dd;color:#865613}.case h3{font-size:15px;line-height:1.4;margin:12px 0 5px}
.case p{font-size:12px;margin:4px 0}.tag{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:11px;color:#43546a;word-break:break-all}
pre{background:#f2f5f9;color:#35465a;font-size:11px;line-height:1.6;padding:12px;white-space:pre-wrap;word-break:break-word;border-radius:10px;max-height:190px;overflow:auto}
small{color:#74849a}#heat{max-width:100%;overflow-x:auto}#hover{color:#1a5c86;font-weight:600;min-height:24px;font-size:13px;margin-top:8px}
footer{color:#74849a;font-size:12px;margin-top:35px;line-height:1.6}details{margin-top:9px}summary{cursor:pointer;color:#386e9a;font-size:12px;font-weight:600}
@media(max-width:750px){.metrics{grid-template-columns:repeat(2,1fr)}.cases{grid-template-columns:1fr} main{padding:20px 13px}}
</style></head><body><main>
<header><div class="eyebrow">CAUSAL-IDFM / VERIFIED IDENTIFICATION SHOWCASE</div>
<h1>网络干扰下的因果识别</h1>
<p class="sub">对业务查询进行正式数学识别、验证与安全诊断。此页由真实代码运行记录生成，显示总体可识别性与支持概率；不提供未经估计的因果效果数值。</p></header>
<div class="metrics" id="metrics"></div>
<section class="section"><h2>Network Arms：Population Support 矩阵</h2>
<p>横向四列表示 (0,0)、(0,1)、(1,0)、(1,1)；纵向是实际网络中的节点。颜色越深代表该 arm 的总体正支持概率越大。悬停查看精确节点与概率近似值。</p>
<div id="heat"></div><div id="hover">将鼠标移到热图单元格上查看。</div>
<div class="key"><span><i class="dot" style="background:#d7e6f5"></i>低支持</span><span><i class="dot" style="background:#087e8b"></i>高支持</span><span><i class="dot" style="background:#e4e7eb"></i>Zero / Undefined</span></div></section>
<section class="section"><h2>真实运行的业务查询和识别结论</h2><div class="cases" id="cases"></div></section>
<section class="section"><h2>数学与实现边界</h2>
<p><b>POINT Identification ≠ 得到效应数值</b>。已知协议、完整潜在结果独立性、总体信息算子和正支持等条件允许数学识别；有限样本模型估计精度由 Estimation 单独评估。</p>
<p><b>R1b 与 R2 不混用：</b>完整分配有支持且 A4 足够时走 R1b；仅当另外接受 mean-signature sufficiency 且类支持成立时，才允许 R2 处理某些 off-support 政策。</p>
<p><b>来源与实证边界：</b>本页的 A4 总体算子属于经明确声明的符号研究资料；D2 固定配额在共享 ER300 图上是单独构造的假设性协议，不是 Estimation 的原 Bernoulli(.5) 实验。</p>
</section><footer>Research demonstration · No PFN call · No simulator ground-truth leakage · Model assumptions require expert validation.</footer>
</main><script type="application/json" id="data">''' + body + '''</script>
<script>
const r=JSON.parse(document.getElementById('data').textContent);
const metrics=[['Network nodes',r.node_count],['Verified arms',r.point_arm_count+' / '+r.arm_count],['Verified business queries',r.business_verified],['Safely blocked',r.business_rejected]];
document.getElementById('metrics').innerHTML=metrics.map(([label,n])=>'<div class="metric"><b>'+n+'</b><span>'+label+'</span></div>').join('');
const width=820, height=r.node_count*3+25, rowH=3, cellW=110, x0=120;
const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox',`0 0 ${width} ${height}`);
svg.setAttribute('width','820');svg.setAttribute('height',String(height));
const NS='http://www.w3.org/2000/svg';const el=(name,attr,parent=svg)=>{let e=document.createElementNS(NS,name);Object.entries(attr).forEach(([k,v])=>e.setAttribute(k,String(v)));parent.appendChild(e);return e};
for(let c=0;c<4;c++){let t=el('text',{x:x0+c*cellW+5,y:13,'font-size':11,fill:'#5a6980'});t.textContent=r.arm_labels[c]}
for(let i=0;i<r.node_count;i++){if(i%25===0){let t=el('text',{x:2,y:26+i*rowH,'font-size':10,fill:'#6c7b8f'});t.textContent='node-'+i}
 for(let a=0;a<2;a++)for(let s=0;s<2;s++){let idx=2*a+s,status=r.arm_matrix_status[i][a][s],v=r.arm_matrix_support[i][a][s];
 let k=v==null?0:Math.min(1,Math.max(0,(v-.03)/.40));let light=86-48*k;
 let fill=status==='POINT'?`hsl(184,55%,${light}%)`:'#e4e7eb';
 let q=el('rect',{x:x0+idx*cellW,y:19+i*rowH,width:cellW-4,height:rowH-0.25,fill});
 q.addEventListener('mouseenter',()=>{document.getElementById('hover').textContent=`node-${i} · ${r.arm_labels[idx]} · ${status} · support≈${v==null?'undefined':v.toFixed(8)}`})}}
document.getElementById('heat').append(svg);
const area=document.getElementById('cases');
for(const c of r.business_cases){const card=document.createElement('article');card.className='case';
 const badge=document.createElement('span');badge.className='badge'+(c.status==='POINT'?'':' block');badge.textContent=c.status;card.append(badge);
 const h=document.createElement('h3');h.textContent=c.title;card.append(h);
 const p=document.createElement('p');p.textContent=c.explanation;card.append(p);
 const route=document.createElement('p');route.className='tag';route.textContent=c.route||c.reason||'Not routed';card.append(route);
 const details=document.createElement('details');const summary=document.createElement('summary');summary.textContent='查看识别记录 / 数学公式';
 const pre=document.createElement('pre');pre.textContent=JSON.stringify(c.result||c.attempted,null,2);details.append(summary,pre);card.append(details);area.append(card)}
</script></body></html>'''
