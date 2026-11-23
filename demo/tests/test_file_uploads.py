"""Standalone file inputs: actual parser, no model, estimation or scientific defaults."""
import base64
import json
import pytest
from demo.backend.engine import Engine,Run


def upload(name,role,text):
    return dict(name=name,role=role,content=base64.b64encode(text.encode()).decode())


def payload():
    return dict(question='本周工具是否提高全部门店的评分？',
        network=dict(kind='UNDIRECTED',completeness='UNKNOWN',description='本周开始前登记的相互合作关系'),
        table_mapping=dict(id_column='id',treatment_column='tool',outcome_column='score',
            feature_columns=['x'],treated_value='yes',untreated_value='no',
            treatment='本周启用工具',outcome='本周评分，分',context='本周，全部三个对象',
            outcome_kind='CONTINUOUS',observation_scheme='002没有回访，原因未知'),
        files=[upload('nodes.csv','network_nodes','node_id\n001\n002\n003\n'),
            upload('edges.csv','network_edges','source,target\n001,002\n'),
            upload('rows.csv','table_data','id,tool,score,x\n003,yes,8.75,30\n001,no,9.25,10\n002,yes,,20\n'),
            upload('dictionary.csv','data_dictionary','变量,说明\nscore,空白表示没有回访\n')])


def test_classic_preview_retains_coverage_without_sending_measurements(tmp_path):
    e=Engine(tmp_path/'runs',max_api_calls=0);v=e.preview_uploads('owner',dict(payload(),reading_mode='classic'))
    assert v['receipt']['ready'] and v['factual_data']==dict(nodes=3,features=1,observed=2,
        note='传递字段说明与实际记录范围。')
    case=json.loads(next((tmp_path/'runs').rglob('case.json')).read_text('utf8'))
    sources={s['source_id']:s['text'] for s in case['sources']}
    inventory=json.loads(sources['uploaded_data_inventory'])
    assert inventory['observed_outcome_node_ids']==['001','003']
    assert inventory['missing_outcome_node_ids']==['002']
    assert '空白表示没有回访' in sources['att_01']
    assert '9.25' not in json.dumps(case) and '8.75' not in json.dumps(case)
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
    monkeypatch.setattr(e,'_read_case',lambda *_:pytest.fail('Incomplete attachment reached reader'))
    p=payload();p['files'].append(upload('empty.txt','document',''))
    e._start(r,p)
    assert r.result['reason_code']=='ATTACHMENT_EXTRACTION_INCOMPLETE' and not r.result['backend_called']
