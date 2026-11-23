from fractions import Fraction
from itertools import combinations, product
from pathlib import Path
import sys

import pytest

package_root = Path(__file__).resolve().parents[1] / "identification"
if package_root.is_dir():
    sys.path.insert(0, str(package_root))
from cfm_id import network_strata
from cfm_id.network_event_handoff import native_support


NODES=["松亭","溪口","西圩","云田","南埠"]
MEMBERS="松亭、云田为第一层，溪口、西圩、南埠为第二层"
LAW="各层内均匀无放回抽取。第一层抽一站，第二层抽两站。两层独立"


def reading(text,table=None):
    rows=[dict(source_id="original",quote=line) for line in text.split("。")]
    sources=[dict(source_id="shared_roster",text=table)] if table else []
    return network_strata.read({"sources":sources},rows,NODES)


def test_two_group_law_matches_independent_full_allocation_enumeration():
    law,_=reading(MEMBERS+"。"+LAW)
    groups=law["groups"]
    assert groups==[["松亭","云田"],["溪口","西圩","南埠"]] and law["quotas"]==[1,2]
    edges=[("松亭","云田"),("松亭","南埠"),("云田","南埠"),("云田","西圩")]
    net=dict(basis="edges",nodes=NODES,roster_complete=True,complete_for=NODES,edges=edges)
    units=["云田","松亭"]
    ends=[[0,1],[0,0]]
    observed=native_support(net,law,{"kind":"majority"},units,ends)
    lists=[set(a+b) for a,b in product(combinations(groups[0],1),combinations(groups[1],2))]
    for u in units:
        peers={b if a==u else a for a,b in edges if u in (a,b)}
        assert observed[u]=={f"{z},{e}":str(Fraction(sum(
            (u in draws)==z and (2*len(peers&draws)>len(peers))==e for draws in lists),len(lists))) for z,e in ends}


@pytest.mark.parametrize("changed",[
    "每层抽一站。两层独立。边际等概率",
    "每层等概率抽一站。层间相关",
    "每层等概率抽一站。两层独立。全网统一抽一站",
    "每层等概率抽一站。两层独立。松亭入选概率为1/5",
    "每层等概率抽一站。两层独立。第二层抽两站",
    "每层等概率抽两站。两层独立",
])
def test_declines_incomplete_and_conflicting_joint_laws(changed):
    assert reading(MEMBERS+"。"+changed) is None


def test_uniform_subset_claim_from_one_stratum_does_not_license_another():
    nodes=[*NODES,"柳口"]
    text="松亭、云田为第一层，其余为第二层。第一层均匀无放回抽一站。第二层抽两站，层内仅个人边际相等。两层独立。"
    rows=[dict(source_id="allocation",quote=line) for line in text.split("。")]
    assert network_strata.read({},rows,nodes) is None


def test_authoritative_roster_and_inconsistent_membership():
    table="node_id,抽签分层\n松亭,1\n溪口,2\n西圩,2\n云田,1\n南埠,2"
    assert reading("按名册分层。"+LAW,table)[0]["quotas"]==[1,2]
    assert reading(LAW,table) is None
    assert reading(MEMBERS+"。"+LAW,table.replace("云田,1","云田,2")) is None
    assert reading("按名册分层。"+LAW,table.replace("抽签分层","配送片区")) is None
    assert reading("云田、松亭为第一层，其余三站为第二层。"+LAW)[0]==reading(MEMBERS+"。"+LAW)[0]
    assert reading("云田、松亭为第一层，其余两站为第二层。"+LAW) is None


def test_candidate_must_match_joint_assignment_not_only_margins():
    law,_=reading(MEMBERS+"。"+LAW)
    good=dict(kind="fixed",description=MEMBERS+"。"+LAW)
    assert network_strata.candidate_agrees(good,law,NODES)
    for bad in (dict(good,quota="2"),dict(good,quotas=[2,1]),dict(good,kind="independent"),
                dict(good,description=LAW),dict(good,description=good["description"].replace("两层独立","两层联动")),
                dict(good,groups=[["云田"],["松亭","溪口","西圩","南埠"]])):
        assert not network_strata.candidate_agrees(bad,law,NODES)


def test_website_binds_both_foci_and_requires_all_three_scientific_decisions(tmp_path):
    from cfm_id.direct_verification import verify, replay
    from demo.tests.test_uploaded_network_contrast import decisions, fixture_case
    case,draft,table=fixture_case(tmp_path,subgroup=True,rule="any")
    case["business_question"]=case["business_question"].replace("仅评价【谷口】","只评价谷口和山南，两站各占一半")
    text="谷口、山南为第一层，其余为第二层。每层等概率抽一站，两层独立。分配变量为开放。"
    next(s for s in case["sources"] if s["source_id"]=="law")["text"]=text
    facts=draft["network_facts"]
    facts["assignment"].update(value={"kind":"fixed","description":text},evidence=[{"source_id":"law","quote":text}])
    facts["contrast"]["value"]["population"]=["谷口","山南"]
    old=verify(case,draft,network=table,version="direct-verification/17")
    assert not old.get("estimation_handoff_allowed") and replay(case,draft,old)
    current=verify(case,draft,network=table)
    assert current["decision"]=="PREMISES_REQUIRED" and not current["estimation_handoff_allowed"]
    for code in ("UNSURE","DECLINED"):
        review=decisions(current)
        review["decisions"]["consistency"]=code
        stopped=verify(case,draft,network=table,science_review=review)
        assert not stopped["estimation_handoff_allowed"] and replay(case,draft,stopped)
    signed=verify(case,draft,network=table,science_review=decisions(current))
    assert signed["estimation_handoff_allowed"] and replay(case,draft,signed)
    h=signed["effective_answer"]["estimate_handoff"]
    assert h["support"]=={u:{"1,1":"1/4","0,1":"1/2"} for u in ("谷口","山南")}
    assert [q["unit"] for q in h["queries"]]==["谷口","谷口","山南","山南"]
    facts["assignment"]["value"]["description"]=text.replace("谷口、山南","谷口、西湾")
    conflict=verify(case,draft,network=table)
    assert conflict["effective_answer"]==draft and not conflict["estimation_handoff_allowed"]
