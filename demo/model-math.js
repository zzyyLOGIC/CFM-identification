/* Presentation only: the original model text is never changed in the report.
 * TeX uses local KaTeX -> native MathML, with untrusted commands disabled.
 * Bare expressions use a bounded lexical formatter, not symbolic inference.
 */
(function(root,factory){
 const api=factory(typeof module==='object'&&module.exports?require('./vendor/katex/katex.min.js'):root.katex);
 if(typeof module==='object'&&module.exports)module.exports=api;else root.ModelMath=api;
})(globalThis,function(katex){
 'use strict';
 const escape=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const greek=/[\u0370-\u03ff]/, han=/[\u3400-\u9fff]/;
 const opening={'(':')','[':']','{':'}'};
 const symbols={'∑':'\\sum ','∈':'\\in ','≤':'\\le ','≥':'\\ge ','≠':'\\ne ','∞':'\\infty ','×':'\\times ','·':'\\cdot ','−':'-','∩':'\\cap ','∪':'\\cup ','→':'\\to '};
 function math(raw,tex,display=false){
  if(!katex||!raw||raw.length>6000||/\\(?:href|url|includegraphics|html\w*|def|gdef|edef|xdef|newcommand|renewcommand|let)\b/.test(tex))return escape(raw);
  try{
   const html=katex.renderToString(tex,{output:'mathml',displayMode:display,throwOnError:true,
     trust:false,strict:'ignore',maxSize:20,maxExpand:200,macros:{}});
   return '<span class="model-math'+(display?' model-math-block':'')+'">'+html+'</span>';
  }catch{return escape(raw);}
 }
 function bareTex(source){
  // Preserve literal grouping braces; only braces following _/^ are TeX groups.
  // Parentheses, operators and signs are preserved, never simplified.
  let i=0;
  function run(stop){let out='';
   while(i<source.length){
    const c=source[i++];if(stop&&c===stop)return out;
    if(c==='_'||c==='^'){
     if(source[i]==='{'){i++;out+=c+'{'+run('}')+'}';}
     else if(han.test(source[i]||'')){let label='';while(han.test(source[i]||''))label+=source[i++];out+=c+'{\\text{'+label+'}}';}
     else out+=c+'{'+(source[i++]||'')+'}';
    }else if(c==='{')out+='\\{'+run('}')+'\\}';
    else if(han.test(c)){let word=c;while(han.test(source[i]||''))word+=source[i++];out+='\\text{'+word+'}';}
    else if(c==='Σ'&&source[i]==='_')out+='\\sum ';
    else if(symbols[c])out+=symbols[c];
    else if(c==='%'||c==='#'||c==='$'||c==='&')out+='\\'+c;
    else out+=c;
   }return out;
  }
  return run().replace(/\b(\d+)\/(\d+)\b/g,'\\frac{$1}{$2}');
 }
 function bareEnd(text,start){
  const stack=[];let i=start,script=false;
  while(i<text.length){
   const c=text[i];
   if(c==='\n'||c==='\r')break;
   if(opening[c]){stack.push(opening[c]);script=false;i++;continue;}
   if(')]}'.includes(c)){if(stack.pop()!==c)return {end:i+1,valid:false};i++;continue;}
   if(c==='_'||c==='^'){script=true;i++;continue;}
   if(han.test(c)){
    if(!stack.length&&!script)break;
    while(han.test(text[i]||''))i++;
    script=false;continue;
   }
   if(/[A-Za-z0-9\s+\-−*/=<>|.,:!%]/.test(c)||greek.test(c)||Object.hasOwn(symbols,c)){
    script=false;i++;continue;
   }
   break;
  }
  return {end:i,valid:stack.length===0&&!script};
 }
 function bareMath(raw){
  // Long sums may break only at outer binary +/-; retain every signed term.
  // This is layout, not factoring or replacing the model's expression.
  const pieces=[];let depth=0,start=0;
  for(let i=0;i<raw.length;i++){
   const c=raw[i];if('([{'.includes(c))depth++;else if(')]}'.includes(c))depth--;
   else if(depth===0&&'+-−'.includes(c)&&i>start&&/[^\s=+\-−*/]$/.test(raw.slice(0,i).trimEnd())){pieces.push(raw.slice(start,i));start=i;}
  }
  pieces.push(raw.slice(start));
  if(raw.length>45&&pieces.length>2)return math(raw,'\\begin{aligned}&'+pieces.map(bareTex).join('\\\\ &')+'\\end{aligned}',true);
  return math(raw,bareTex(raw));
 }
 function plain(text){
  let html='',i=0;
  while(i<text.length){
   if(text[i]==='\\'){
    // Undelimited TeX is common in model JSON. Keep an entire command expression
    // together; never detach the slash and format the remaining command name.
    const stop=text.slice(i).search(/[\n\r。；]/),end=stop<0?text.length:i+stop;
    const raw=text.slice(i,end);html+=math(raw,raw);i=end;continue;
   }
   // ASCII words by themselves remain ordinary prose, not a product of letters.
   if(/[A-Za-z0-9(\[]/.test(text[i])||greek.test(text[i])||text[i]==='∑'){
    const {end,valid}=bareEnd(text,i),raw=text.slice(i,end),trim=raw.trimEnd();
    const hasNotation=/[_^=∑∈≤≥≠]|Σ_|[EP]\s*[([]|[μτΔ][([]|\d\s*\/\s*\d/.test(trim);
    if(end>i&&hasNotation){
     html+=valid?bareMath(trim):escape(trim);
     html+=escape(raw.slice(trim.length));i=end;continue;
    }
    if(end>i){html+=escape(raw);i=end;continue;}
   }
   html+=escape(text[i++]);
  }
  return html;
 }
 function render(value){
  const text=String(value??'');if(text.length>24000)return escape(text);
  // Explicit TeX delimiters are recognized first. Unclosed/invalid TeX is kept.
  const delimited=/\$\$[\s\S]*?\$\$|\\\[[\s\S]*?\\\]|\\\([\s\S]*?\\\)|(?<![\\$])\$(?!\$)(?:\\.|[^$\n])+?\$/g;
  let html='',offset=0;
  for(const m of text.matchAll(delimited)){
   html+=plain(text.slice(offset,m.index));const raw=m[0];
   const double=raw.startsWith('$$')||raw.startsWith('\\[')||raw.startsWith('\\(');
   const tex=raw.slice(double?2:1,double?-2:-1);
   html+=math(raw,tex,raw.startsWith('$$')||raw.startsWith('\\['));offset=m.index+raw.length;
  }
  return html+plain(text.slice(offset));
 }
 return {render};
});
