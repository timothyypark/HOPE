import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/flight_prediction_validation'))
from state_machine_scoring import score


def trace():
    return [dict(trace_sequence=i+1,phase=phase,source_index=0,source_ns=100,
                 play_state='RALLY',classification_status='PROVISIONAL',reason='unknown_history')
            for i,phase in enumerate(('before','after_expire','after'))]+[
            dict(trace_sequence=4,phase='footer',frames=1,complete=True)]


def annotation():
    return dict(physical_flight_id='f',recording_id='r',evidence_type='measured_recording',
        parent_sha256='a'*64,review_status='REVIEWED',reviewer='independent',annotation_version='1',
        source_frames=[0,1],begin_ns=0,end_ns=200,available_ns=150,expected_state='SERVE',history_completeness='unknown')


def test_future_serve_cannot_penalize_causal_rally():
    result=score(trace(),[annotation()],1)
    assert result['scored_frames']==0 and result['states']['SERVE']['status']=='NOT_COVERED'


def test_observable_wrong_state_fails():
    a=annotation();a['available_ns']=50
    result=score(trace(),[a],1)
    assert result['verdict']=='FAIL' and result['confusion_matrix']['SERVE']['RALLY']==1


def test_empty_labels_do_not_pass():
    assert score(trace(),[],1)['verdict']=='NOT_COVERED'


@pytest.mark.parametrize('damage',['lost','reordered','truncated','phase','after_footer'])
def test_incomplete_observer_cannot_pass(damage):
    rows=trace()
    if damage=='lost': rows.pop(1)
    if damage=='reordered': rows[0],rows[1]=rows[1],rows[0]
    if damage=='truncated': rows.pop()
    if damage=='phase': rows[1]['phase']='after'
    if damage=='after_footer': rows.append(rows[0])
    with pytest.raises(ValueError): score(rows,[],1)


def test_repeated_source_timestamp_transitions_are_not_deduplicated():
    assert score(trace(),[],1)['trace_complete']
