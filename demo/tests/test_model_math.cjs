const {test}=require('node:test');
const assert=require('node:assert/strict');
const {render}=require('../model-math.js');
test('explicit TeX, fractions and matrix notation use actual local MathML',()=>{
 for(const raw of [String.raw`\(\frac{1}{2}\sum_i w_i\mu_i(1)\)`,
   String.raw`$$\tau=\begin{pmatrix}a&b\\c&d\end{pmatrix}$$`,
   String.raw`\tau = E[Y\mid T=1]-E[Y\mid T=0]`]){
  const h=render(raw);assert.match(h,/<math /);assert.match(h,/<semantics>/);assert.doesNotMatch(h,/katex-error/);
 }
 assert.match(render(String.raw`\[\frac{1}{3}\]`),/<mfrac>/);
});
test('real plain model prose keeps Chinese explanations and renders indices, weights and summation',()=>{
 const raw='令 Z_i 为店 i 是否启用，μ_i(z,g)=E[Y_i | Z_i=z,G_i=g]。目标为 (1/4)∑_{i∈{甲,乙,丙,丁}}{μ_i(1,1)−μ_i(0,1)}。';
 const h=render(raw);
 assert.match(h,/令 /);assert.match(h,/为店 i 是否启用/);assert.match(h,/目标为/);
 assert.match(h,/<msub>/);assert.match(h,/<mfrac>/);assert.match(h,/∑/);
 // The minus and grouping braces are retained, not replaced by a library answer.
 assert.match(h,/<mo>−<\/mo>/);assert.match(h,/<mo[^>]*>\{<\/mo>/);
});
test('long sums wrap at outer operators while retaining every signed term',()=>{
 const s='(1/2){μ_甲(1)-μ_甲(0)}+(1/3){μ_乙(1)-μ_乙(0)}+(1/6){μ_丙(1)-μ_丙(0)}+0·D_丁';
 const h=render(s+' + 0·D_戊');assert.match(h,/<mtable/);
 for(const label of ['甲','乙','丙','丁','戊'])assert.ok(h.includes(label));
 assert.equal((h.match(/<mo>−<\/mo>/g)||[]).length,3);
});
test('unparseable and unsafe input is retained safely with no executable attributes or links',()=>{
 for(const raw of [String.raw`\(\notacommand{x}\)`,String.raw`\(\href{javascript:alert(1)}{open}\)`,
  String.raw`\(\htmlClass{verified}{wrong}\)`,String.raw`\(\def\a{\a}\a\)`,
  '<img src=x onerror=alert(1)>','<script>alert(1)</script>']){
  const h=render(raw);assert.doesNotMatch(h,/<script|<img|<a\b|class="verified"/);
 }
 assert.match(render(String.raw`\(\notacommand{x}\)`),/\\notacommand/);
 assert.equal(render('模型认为需要补充信息。'),'模型认为需要补充信息。');
});
test('ordinary statuses, URLs, unmatched brackets and originals are not silently rewritten',()=>{
 assert.equal(render('POINT 与 API'),'POINT 与 API');
 const prose='ordinary English explanation '.repeat(500);assert.equal(render(prose),prose);
 assert.equal(render('E[Y_i | T_i=1'),'E[Y_i | T_i=1');
 const source='(1/2){μ_甲(1)-μ_甲(0)}+(1/3){μ_乙(1)-μ_乙(0)}';
 assert.match(render(source),/<mfrac>/);assert.equal(source,'(1/2){μ_甲(1)-μ_甲(0)}+(1/3){μ_乙(1)-μ_乙(0)}');
});
