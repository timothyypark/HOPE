"""Negative controls for PPQ004 clock, geometry and absent-frame conversion."""
import sys
from pathlib import Path
import numpy as np
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/flight_prediction_validation'))
from ppq004_dataset import observations, source_ns, quaternion_equivalent, check_csv


def fixture():
    return dict(t=np.array([0.,1/300,2/300]),rate=np.array(300.),
        ball_present=np.array([True,False,True]),
        ball_pos=np.array([[1.,-.7,.2],[np.nan]*3,[.98,-.7,.21]]),
        ball_quat=np.array([[0.,0.,0.,1.],[np.nan]*4,[0.,0.,0.,-1.]]),
        ball_rms=np.array([.001,np.nan,.002]))


def test_missing_frame_and_source_identity():
    rows=list(observations(fixture(),3,'a'*64))
    assert len(rows)==3 and rows[1]['source_index']==1
    assert rows[1]['streams']['ball']['position_m'] is None
    assert not rows[1]['streams']['ball']['orientation_available']
    assert not rows[0]['streams']['ball']['angular_velocity_authorized']
    assert rows[0]['split']=='benchmark_holdout'
    assert rows[2]['streams']['ball']['quaternion_xyzw']==[0,0,0,-1]
    assert rows[2]['source_time_ns']==6666667
    assert len({r['source_frame_sha256'] for r in rows})==3


def test_integer_epoch_and_overflow():
    epoch=1800000000000000000
    assert source_ns(1/300,epoch)-epoch==3333333
    with pytest.raises(ValueError): source_ns(float('nan'))
    with pytest.raises(ValueError): source_ns(1,2**63)
    with pytest.raises(ValueError): source_ns(1,1.5)


def test_reordered_and_duplicate_are_preserved_not_sorted():
    data=fixture();data['t']=np.array([.01,.01,0.])
    rows=list(observations(data,1,'a'*64))
    assert [r['ordering'] for r in rows]==['first','duplicate','backstep']
    assert [r['source_index'] for r in rows]==[0,1,2]


def test_quaternion_order_and_sign():
    q=[.1,.2,.3,.9]
    assert quaternion_equivalent(q,[-x for x in q])
    assert not quaternion_equivalent(q,[.9,.1,.2,.3])


def test_csv_not_omega_and_exact_roundtrip(tmp_path):
    data=fixture(); path=tmp_path/'rows.csv'
    expected=np.column_stack([data['t'][[0,2]],data['ball_pos'][[0,2]],data['ball_quat'][[0,2]]])
    np.savetxt(path,expected,delimiter=',',fmt='%.17g')
    assert check_csv(data,path)==2
    expected[0,4:]=[1,0,0,0]
    np.savetxt(path,expected,delimiter=',',fmt='%.17g')
    with pytest.raises(ValueError): check_csv(data,path)
