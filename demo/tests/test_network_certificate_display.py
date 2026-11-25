"""Exercise the real JS renderer with native results, and the review submitter."""
import json
import shutil
import subprocess
from pathlib import Path
import pytest
from test_observational_effect_entry import fixture,prepared
from cfm_id import observational_effect_entry as entry

DEMO=Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('name',['observed','stratum','nodewise'])
def test_native_observational_formulas_render_and_keep_averaging(name):
    if not shutil.which('node'):pytest.skip('Node is required for frontend checks')
    case,wire=fixture(name);r=prepared(case,wire);s=r['condition_review']
    r=entry.complete(case,r,dict(binding=s['binding'],authority='SYNTHETIC_TEST',decisions={x['code']:'ADOPTED' for x in s['items']}))
    script=r"""
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const app=fs.readFileSync('app.js','utf8'),report=JSON.parse(fs.readFileSync(0,'utf8'));
const ctx={ModelMath:require('./model-math.js'),esc:s=>String(s).replaceAll('<','&lt;')};vm.createContext(ctx);
vm.runInContext(app.slice(app.indexOf('function jointCertificateHTML('),app.indexOf('function directAnswerHTML(')),ctx);
const out=ctx.jointCertificateHTML(report.joint_entry.native_result.certificate);
assert.match(out,/<math /);assert.doesNotMatch(out,/undefined|katex-error|请展开证书/);
assert.match(out,/m_i\(a,s\)|m<\/mi>/);assert.ok(out.includes('甲站'));
process.stdout.write(out);
"""
    proc=subprocess.run(['node','-e',script],input=json.dumps(r,ensure_ascii=False),cwd=DEMO,text=True,encoding='utf8',capture_output=True)
    assert proc.returncode==0,proc.stderr
    assert {'observed':'实际采用规律','stratum':'总体占比','nodewise':'全部关系邻居'}[name] in proc.stdout


def test_scientific_form_submission_calls_bound_action():
    if not shutil.which('node'):pytest.skip('Node is required for frontend checks')
    script=r"""
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),app=fs.readFileSync('app.js','utf8');
const button={disabled:false},message={textContent:''},form={dataset:{binding:'bound'},querySelector:()=>button};
let submitted;
const ctx={$:()=>message,current:{id:'run',result:{condition_review:{kind:'joint_natural'}}},FormData:class{*[Symbol.iterator](){yield ['target','ADOPTED'];}},api:async(url,p)=>{submitted=p},poll:async()=>{}};
vm.createContext(ctx);const start=app.indexOf("$('#network-condition-form').onsubmit=")+"$('#network-condition-form').onsubmit=".length;
const fn=vm.runInContext('('+app.slice(start,app.indexOf('\nfunction isDirectVerification',start)).trim().replace(/;$/,'')+')',ctx);
(async()=>{await fn({preventDefault(){},currentTarget:form});assert.equal(message.textContent,'');assert.equal(submitted.action,'review_joint_conditions');assert.equal(submitted.payload.binding,'bound');assert.equal(submitted.payload.decisions.target,'ADOPTED');assert.equal(button.disabled,false)})().catch(e=>{console.error(e);process.exitCode=1});
"""
    proc=subprocess.run(['node','-e',script],cwd=DEMO,text=True,encoding='utf8',capture_output=True)
    assert proc.returncode==0,proc.stderr
