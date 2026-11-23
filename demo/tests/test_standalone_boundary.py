"""ID-only packaging boundaries; the web cannot silently invoke estimation."""
from pathlib import Path
import ast
import json
import subprocess
import sys

import pytest

from demo.backend.engine import Engine, Run
from demo.backend.runtime import PROJECT_ROOT, application_root


def test_no_full_pipeline_or_test_fixture_dependency():
    forbidden = {'autocfm', 'estimation', 'policy', 'simulator', 'torch', 'tests', 'examples', 'evaluation'}
    for path in (PROJECT_ROOT/'demo/backend').glob('*.py'):
        for node in ast.walk(ast.parse(path.read_text('utf8'))):
            modules = [a.name for a in node.names] if isinstance(node, ast.Import) else (
                [node.module] if isinstance(node, ast.ImportFrom) and not node.level and node.module else [])
            assert not any(m.split('.')[0] in forbidden for m in modules), (path.name, modules)


@pytest.mark.parametrize('entry',[PROJECT_ROOT/'demo/serve.py', application_root()/'serve.py'])
def test_entrypoint_works_outside_repository_without_torch(tmp_path,entry):
    code = '''import importlib.abc, sys, runpy
class RejectPipeline(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'autocfm', 'torch', 'estimation', 'policy', 'simulator'}:
            raise AssertionError('Forbidden dependency: '+fullname)
sys.meta_path.insert(0, RejectPipeline())
sys.argv = [sys.argv[1], '--help']
runpy.run_path(sys.argv[0], run_name='__main__')
'''
    result = subprocess.run([sys.executable, '-c', code, str(entry)], cwd=tmp_path,
        capture_output=True, text=True, timeout=40)
    assert result.returncode == 0, result.stderr
    assert '--port' in result.stdout


def test_catalog_preserves_original_examples_and_identification_only_boundary():
    examples = json.loads((PROJECT_ROOT/'demo/examples.json').read_text('utf8'))
    ids = {x['id'] for x in examples}
    assert len(ids) == len(examples)
    assert {'n100', 'lit_vaccine', 'lit_school', 'lit_seed_policy',
            'lit_observational_peers', 'partial_policy', 'partial_mean_order',
            'dag_backdoor', 'dag_frontdoor'} <= ids
    for item in examples:
        assert item['case']['business_question'] and item['case']['sources']
        assert 'data' not in item and 'data_schema' not in item
        for run in item.get('saved_runs', []):
            assert 'estimation' not in run
    assert any(x['id'] == 'n100' for x in examples)


def test_estimation_is_rejected_without_mutating_identification(tmp_path):
    engine = Engine(tmp_path/'runs')
    run = Run(owner='test', result={'state':'POINT', 'independent_replay':True})
    engine.runs[run.id] = run
    with pytest.raises(ValueError, match='ESTIMATION_NOT_IN_IDENTIFICATION_DEMO'):
        engine.action(run.owner, run.id, 'estimate', {})
    assert run.result == {'state':'POINT', 'independent_replay':True}
    assert not engine.view(run.owner, run.id)['can_estimate']
    with pytest.raises(ValueError, match='ESTIMATION_NOT_IN_IDENTIFICATION_DEMO'):
        engine.start('test', {'question':'任意问题', 'allow_send':True, 'use_example_data':True})


def test_page_does_not_offer_estimation_inputs_or_actions():
    html = (PROJECT_ROOT/'demo/index.html').read_text('utf8')
    js = (PROJECT_ROOT/'demo/app.js').read_text('utf8')
    for identifier in ('data-file', 'schema-file', 'use-example-data', 'example-data-option'):
        assert f'id="{identifier}"' not in html
        assert f"$('#{identifier}')" not in js
    assert "action:'estimate'" not in js
    assert '查看识别公式、界限和所需假设' in html
