"""Behavior of the actual shared direct-entry projection, plus existing upload failure checks."""
import csv
import io
import json
import sys
from pathlib import Path

import pytest

TEST_ROOT = Path(__file__).resolve().parent
if (TEST_ROOT.parent / 'identification').is_dir():
    sys.path.insert(0,str(TEST_ROOT.parent / 'identification'))

from demo.backend.engine import Engine, Run
from cfm_id_llm.direct_answer import network_request
import base64

def upload(name,role,text):
    return dict(name=name,role=role,content=base64.b64encode(text.encode()).decode())

def payload():
    return dict(question='本周工具是否提高全部门店的评分？',
        network=dict(kind='UNDIRECTED',completeness='UNKNOWN',description='本周开始前登记的相互合作关系'),
        table_mapping=dict(id_column='id',treatment_column='tool',outcome_column='score',
            feature_columns=['x'],treated_value='yes',untreated_value='no',
            treatment='本周启用工具',outcome='本周评分，分',context='本周，全部三个对象',
            outcome_kind='CONTINUOUS',observation_scheme='002没有回访，原因未知'),
        files=[upload('nodes.csv','network_nodes','node_id,姓名\n001,甲\n002,乙\n003,丙\n'),
            upload('edges.csv','network_edges','source,target\n001,002\n'),
            upload('rows.csv','table_data','id,tool,score,x,备注\n003,yes,8.75,30,"原,行"\n001,no,9.25,10,01\n002,yes,,20,\n'),
            upload('dictionary.csv','data_dictionary','变量,说明\nscore,空白表示没有回访\n')])

@pytest.mark.parametrize('mode',['direct_verify','network_direct_verify','network_local_review','classic','compact'])
def test_preview_accurately_discloses_materials_and_preserves_raw_row_identity(tmp_path,mode):
    e=Engine(tmp_path/'runs',max_api_calls=0);v=e.preview_uploads('owner',dict(payload(),reading_mode=mode))
    assert v['receipt']['ready'] and v['factual_data']['observed']==2
    case=json.loads(next((tmp_path/'runs').rglob('case.json')).read_text('utf8'))
    raw=json.loads(network_request(case)['user_prompt'])
    assert raw['question']==payload()['question']
    assert raw['sources']==[{k:s[k] for k in ('source_id','label','text')} for s in v['sources']]
    sources={s['source_id']:s['text'] for s in case['sources']}
    inventory=json.loads(sources['uploaded_data_inventory'])
    assert inventory['observed_outcome_node_ids']==['001','003']
    assert inventory['missing_outcome_node_ids']==['002'] and '空白表示没有回访' in sources['att_01']
    if mode in ('direct_verify','network_direct_verify','network_local_review'):
        rows=lambda name:list(csv.reader(io.StringIO(sources[name])))
        assert rows('shared_roster')==[['node_id','姓名'],['001','甲'],['002','乙'],['003','丙']]
        assert rows('shared_edges')==[['source','target'],['001','002']]
        assert rows('shared_observations')==[['id','tool','score','x','备注'],['003','yes','8.75','30','原,行'],
                                               ['001','no','9.25','10','01'],['002','yes','','20','']]
        assert v['table_import']['raw_measurements_in_shared_input']
    else:
        assert 'shared_observations' not in sources and '9.25' not in json.dumps(case)
    assert v['table_import']['source_rows']==[3,4,2] and not v['table_import']['scientific_approval']
    assert e.calls==0 and not e.runs

@pytest.mark.parametrize('mutation,error',[
    ('id','编号集合'),('missing_network','同时上传'),('count','COUNT_OUTCOME_DECLARATION_MISMATCH')])
def test_invalid_files_stop_before_any_model(tmp_path,mutation,error):
    p=payload()
    if mutation=='id':p['files'][2]=upload('rows.csv','table_data','id,tool,score,x\n999,yes,8,30\n001,no,9,10\n002,yes,,20\n')
    elif mutation=='missing_network':p['files'].pop(1)
    else:p['table_mapping']['outcome_kind']='COUNT'
    e=Engine(tmp_path/'runs',max_api_calls=0)
    with pytest.raises(ValueError,match=error):e.preview_uploads('owner',p)
    assert e.calls==0

def test_empty_attachment_blocks_start_and_does_not_call_reader(tmp_path,monkeypatch):
    e=Engine(tmp_path/'runs',max_api_calls=0);r=Run(owner='test')
    monkeypatch.setattr(e,'_direct_verify',lambda *_:pytest.fail('Incomplete attachment reached reader'))
    p=payload();p['files'].append(upload('empty.txt','document',''))
    e._start(r,p)
    assert r.result['reason_code']=='ATTACHMENT_EXTRACTION_INCOMPLETE' and not r.result['backend_called']
