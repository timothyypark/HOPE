"""Negative controls for pairing, coverage, propagation and causal replay."""
import json
import os
from pathlib import Path
import subprocess
import numpy as np
import pytest
import yaml
from score import free_flight, crossing, paired_summary


def test_common_kernel_matches_analytic_gravity():
    state=np.array([[1.,2.,3.,4.,5.,6.],[0.,0.,1.,-2.,0.,3.]])
    dt=np.array([.03,.15])
    actual=free_flight(state,np.zeros((2,3)),dt,0,0)
    expected=state.copy();expected[:,:3]+=state[:,3:]*dt[:,None]
    expected[:,2]-=4.905*dt**2;expected[:,5]-=9.81*dt
    np.testing.assert_allclose(actual,expected,atol=1e-11,rtol=0)


def test_common_kernel_converges_with_drag_and_spin():
    state=[[2.,-.7,.6,-8.,.3,2.]];spin=[[0.,100.,20.]]
    a=free_flight(state,spin,.15,.1286,.00379,.0005)
    b=free_flight(state,spin,.15,.1286,.00379,.00025)
    np.testing.assert_allclose(a,b,atol=1e-8,rtol=0)


def test_no_support_never_becomes_zero_error():
    r=paired_summary([], {('arc',0,100)},'main_operator')
    assert r['paired_arcs']==0 and r['median_paired_difference'] is None
    assert r['main_paired_arc_rms']['median'] is None
    assert r['assessment']=='INSUFFICIENT_PAIRED_SUPPORT'


def test_pairing_requires_identical_cutoffs():
    rows=[dict(method='main_operator',arc_id='a',source_index=0,query=100,error_m=.01),
          dict(method='v2_managed',arc_id='a',source_index=6,query=100,error_m=.001)]
    r=paired_summary(rows,{('a',0,100),('a',6,100)},'main_operator')
    assert r['paired_cutoffs']==0


def test_duplicate_scores_are_rejected():
    row=dict(method='main_operator',arc_id='a',source_index=0,query=100,error_m=.01)
    with pytest.raises(ValueError,match='Duplicate'):
        paired_summary([row,row],{('a',0,100)},'main_operator')


def test_paired_difference_sign_and_arc_weighting():
    rows=[];offered=set()
    for arc in range(6):
        for index in range(100 if arc==0 else 1):
            offered.add((str(arc),index,100))
            for method,error in [('main_operator',.01),('v2_managed',.02)]:
                rows.append(dict(method=method,arc_id=str(arc),source_index=index,query=100,error_m=error))
    r=paired_summary(rows,offered,'main_operator')
    assert r['paired_arcs']==6 and r['assessment']=='MAIN_LOWER_PAIRED_ERROR'
    assert r['median_paired_difference']==pytest.approx(10)
    assert r['paired_bootstrap_95']==pytest.approx([10,10])


def test_missing_output_remains_in_coverage():
    rows=[dict(method=m,arc_id='a',source_index=i,query=100,error_m=.01)
          for m,indices in [('main_operator',[0,6]),('v2_managed',[0])] for i in indices]
    r=paired_summary(rows,{('a',0,100),('a',6,100)},'main_operator')
    assert r['v2_lower_availability'] and r['coverage']['v2_managed']['offered_cutoffs']==2


def test_crossing_requires_adjacent_present_samples():
    d=dict(ball_pos=np.array([[.3,0,1],[.2,0,1],[.1,0,1]]),ball_present=np.array([True,False,True]),ns=np.array([0,3,6]))
    assert crossing(d,0,2,.15) is None
    d['ball_present'][1]=True
    c=crossing(d,0,2,.15)
    assert c['arrival_ns']==pytest.approx(4.5) and c['bracket']==[3,6]


@pytest.fixture
def binaries():
    path=os.environ.get('COMPARISON_BUILD')
    if not path:
        pytest.skip('Set COMPARISON_BUILD for native adapter controls')
    return Path(path)


def synthetic_frames(count=180,sign=1):
    rows=[]
    for i in range(count):
        t=i/300;omega=8*t
        rows.append([i,100_000_000_000+round(t*1e9),1,2.6-4*t,-.7,.6+1*t-4.905*t*t,
                     1,0,sign*np.sin(omega/2),0,sign*np.cos(omega/2)])
    return rows


def invoke(binary,frames,args=()):
    data=''.join(','.join(map(str,r))+'\n' for r in frames)
    p=subprocess.run([str(binary),*map(str,args)],input=data,text=True,capture_output=True,check=True)
    return [json.loads(s) for s in p.stdout.splitlines()]


@pytest.mark.parametrize('name',['main_replay','v2_replay'])
def test_native_future_prefix_invariance_and_nonvacuous_fit(binaries,name):
    config=Path(os.environ['MAIN_SOURCE'])/'hope_ws/src/hope_planner_cpp/config'
    args=[config/'model21800_hardware.yaml',config/'model21800_flight_packetizer.yaml'] if name=='main_replay' else []
    frames=synthetic_frames();short=invoke(binaries/name,frames[:120],args)
    changed=[r.copy() for r in frames]
    for row in changed[120:]: row[3]+=3;row[5]+=1
    full=invoke(binaries/name,changed,args)
    assert short==[r for r in full if r['source_index']<120]
    assert any(r['available'] for r in short), 'Control must exercise fitted predictions'


@pytest.mark.parametrize('name',['main_replay','v2_replay'])
def test_native_quaternion_sign_equivalence(binaries,name):
    config=Path(os.environ['MAIN_SOURCE'])/'hope_ws/src/hope_planner_cpp/config'
    args=[config/'model21800_hardware.yaml',config/'model21800_flight_packetizer.yaml'] if name=='main_replay' else []
    a=invoke(binaries/name,synthetic_frames(),args);b=invoke(binaries/name,synthetic_frames(sign=-1),args)
    assert a==b


def test_main_reads_the_checked_in_fit_profile(binaries,tmp_path):
    config=Path(os.environ['MAIN_SOURCE'])/'hope_ws/src/hope_planner_cpp/config'
    document=yaml.safe_load((config/'model21800_hardware.yaml').read_text())
    parameters=document['hope_planner']['ros__parameters']
    parameters['batch_estimator_window_s']=2.0
    parameters['batch_estimator_min_span_s']=1.0
    parameters['batch_post_bounce_min_span_s']=1.0
    modified=tmp_path/'profile.yaml';modified.write_text(yaml.safe_dump(document))
    rows=invoke(binaries/'main_replay',synthetic_frames(),[modified,config/'model21800_flight_packetizer.yaml'])
    assert not any(r['available'] for r in rows if r['method']=='main_batch')
    assert any(r['available'] for r in rows if r['method']=='main_operator')
