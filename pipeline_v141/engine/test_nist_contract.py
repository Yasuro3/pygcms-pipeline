"""Regression checks for NIST response identity: no silent run/scan reassignment."""
import importlib.util
from pathlib import Path

p=Path(__file__).resolve().parents[1]/'nist_search'/'scripts'/'run_mssearch_v141.py'
spec=importlib.util.spec_from_file_location('runner',p)
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)

def check():
    q=[{'query_name':'Q01_PGCMS_0001_RT_1.230_SCAN_10'},
       {'query_name':'Q02_PGCMS_0001_RT_1.235_SCAN_11'}]
    data={'ok':True,'groups':[{'header':q[1]['query_name'],'hits':[{'name':'Test B','mf':870,'rank':1}]},
                             {'header':q[0]['query_name'],'hits':[{'name':'Test A','mf':800,'rank':1}]}],
          'n_groups':2,'n_hits':2}
    mapped=mod.map_response(q,data)
    assert mapped[q[0]['query_name']]['hits'][0]['name']=='Test A'
    assert mapped[q[1]['query_name']]['hits'][0]['name']=='Test B'
    print('PASS: unordered NIST groups assigned by complete query identity')
    broken={'ok':True,'groups':[{'header':'Q03_PGCMS_0001_RT_1.235_SCAN_11','hits':[{'name':'Bad'}]}]}
    try:mod.map_response(q,broken)
    except ValueError:pass
    else:raise AssertionError('Unrelated NIST response silently accepted')
    print('PASS: unknown query group rejected')
    bad={'ok':True,'groups':[{'header':q[0]['query_name'],'hits':[]},
                             {'header':q[0]['query_name'],'hits':[]}]}
    try:mod.map_response(q,bad)
    except ValueError:pass
    else:raise AssertionError('Duplicate NIST response silently accepted')
    print('PASS: repeated NIST query rejected')

if __name__=='__main__':check()
