"""Round trip from uploaded materials to reviewed compact result using the normal web API."""
import base64
from copy import deepcopy
import time
from demo.backend.engine import Engine
from tests_gateway.test_compact_entry import fixture,review

def test_focused_single_field_and_user_confirmation(tmp_path):
    case,raw=fixture()
    class Local(Engine):
        def call(self,r,request,stage):
            stages.append(stage)
            if stage=="compact_focus":
                return {"network":deepcopy(raw["network"])}
            first=deepcopy(raw);first["network"]["quote"]="Invented reference"
            return first
    stages=[];e=Local(tmp_path);owner="test-owner";e.credential(owner,"longcat","local-test")
    source=base64.b64encode(case["sources"][0]["text"].encode()).decode()
    rid=e.start(owner,dict(allow_send=True,synthetic=True,automatic_review=True,provider="longcat",reading_mode="compact",
        question=case["business_question"],files=[dict(name="study.txt",role="document",content=source)]))
    def idle():
        for _ in range(600):
            if not e.runs[rid].busy:return e.view(owner,rid)
            time.sleep(.01)
        raise AssertionError("workflow timeout")
    initial=idle()
    assert not initial["error"] and initial["result"] is None and stages==["compact_read","compact_focus"]
    plan=initial["compact_plan"];e.action(owner,rid,"compact_confirm",review(plan))
    final=idle()
    assert final["result"]["state"]=="POINT" and final["result"]["estimate_handoff"]["mode"]=="ESTIMATE_POINT"
    assert not final["compact_plan"] and not final["estimate"]
