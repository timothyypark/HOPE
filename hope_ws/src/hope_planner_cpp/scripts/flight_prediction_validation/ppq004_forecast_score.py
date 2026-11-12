"""Compare actual full-take forecast waypoints to held-out measured positions.

Only the scorer reads future measurements. Interpolation samples a predicted
curve at measured acquisition times, never interpolates measurements into input.
Statistics are grouped by screened observed arc, not claimed racket-to-racket
flights. Same-sensor proxy scores cannot qualify independent physical Gate P.
"""
import argparse
import csv
import json
from collections import defaultdict,Counter
from pathlib import Path
import numpy as np
from ppq004_dataset import sha256
from accuracy import statistics


def score(source,replay,annotations,output,split):
    output.mkdir(parents=True,exist_ok=False)
    episodes=[json.loads(s) for s in annotations.read_text().splitlines() if s]
    episodes=[e for e in episodes if e['split']==split]
    by_part=defaultdict(list)
    for e in episodes:by_part[e['recording_id']].append(e)
    groups=defaultdict(list);reasons=Counter();offered=0;available=0
    with (output/'errors.csv').open('w') as out:
        writer=csv.DictWriter(out,fieldnames=['recording_id','arc_id','source_ns','truth_ns','lead_ms','position_error_m','x_error_m','y_error_m','z_error_m'])
        writer.writeheader()
        for recording,arcs in by_part.items():
            part=int(recording[-1]);data=dict(np.load(source/f'fit/part{part}/raw_extracted.npz'))
            times=np.rint(data['t']*1e9).astype(np.int64);positions=data['ball_pos'];present=data['ball_present']
            path=replay/f'{recording}.forecast.jsonl'
            with path.open() as f:
                for line in f:
                    prediction=json.loads(line);cutoff=prediction['source_ns'];index=prediction['source_index']
                    arc=next((a for a in arcs if a['begin_ns']<=cutoff<=a['end_ns']),None)
                    if arc is None:continue
                    offered+=1;reasons[prediction['reason']]+=1
                    w=np.asarray(prediction['waypoints'],dtype=float)
                    if not prediction['physical_available'] or w.ndim!=2 or len(w)<2:continue
                    reference=prediction['prediction_reference_ns']
                    # A missing-frame forecast is not a new measured source cutoff.
                    if reference!=cutoff or not present[index]:continue
                    ix=np.arange(index+1,arc['source_frames'][1]+1)
                    lead=(times[ix]-reference)*1e-9
                    good=present[ix] & (lead>=.01) & (lead<=.15) & (lead<=w[-1,0])
                    ix=ix[good];lead=lead[good]
                    if not len(ix):continue
                    predicted=np.column_stack([np.interp(lead,w[:,0],w[:,axis+1]) for axis in range(3)])
                    errors=predicted-positions[ix];available+=1
                    for i,delta,t in zip(ix,errors,lead):
                        norm=float(np.linalg.norm(delta));groups[arc['physical_flight_id']].append(norm)
                        writer.writerow(dict(recording_id=recording,arc_id=arc['physical_flight_id'],source_ns=cutoff,
                            truth_ns=int(times[i]),lead_ms=t*1000,position_error_m=norm,
                            x_error_m=float(delta[0]),y_error_m=float(delta[1]),z_error_m=float(delta[2])))
    arc_rms=[float(np.sqrt(np.mean(np.square(values)))) for values in groups.values()]
    rng=np.random.default_rng(1226)
    bootstrap=[float(np.median(rng.choice(arc_rms,len(arc_rms),replace=True))) for _ in range(1000)] if arc_rms else []
    target=json.loads((Path(__file__).resolve().parents[2]/'config/ppq004_validation.yaml').read_text())['recorded_accuracy_targets']
    stats=statistics(arc_rms)
    diagnostic_pass=bool(arc_rms) and stats['median']<=target['median_arc_rms_limit_m'] and stats['p95']<=target['p95_arc_rms_limit_m'] and len(groups)/max(1,len(episodes))>=target['minimum_arc_coverage']
    result=dict(evidence_type='measured_recording',truth_kind='recorded_proxy',gate_p='NOT_RUN_RECORDED_PROXY',
        split=split,lead_window_ms=[10,150],source_cutoffs_offered=offered,source_cutoffs_scored=available,
        arcs_offered=len(episodes),arcs_scored=len(groups),arc_rms_m=stats,acceptance=target,
        paired_unit='screened observed arc; physical boundary is unqualified',
        median_arc_rms_bootstrap_95=np.quantile(bootstrap,[.025,.975]).tolist() if bootstrap else None,
        reasons=dict(reasons),verdict='NOT_COVERED' if not arc_rms else 'PASS' if diagnostic_pass else 'FAIL',
        reason='Frozen conditional recorded-proxy diagnostic; not full availability or model adoption',
        input_hashes={'annotation':sha256(annotations),'replay_receipt':sha256(replay/'receipt.json')},
        per_arc={k:dict(samples=len(v),rms_m=float(np.sqrt(np.mean(np.square(v))))) for k,v in groups.items()})
    (output/'results.json').write_text(json.dumps(result,indent=2)+'\n');return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for arg in ('source','replay','annotations','output'):p.add_argument('--'+arg,type=Path,required=True)
    p.add_argument('--split',choices=['development','benchmark_holdout'],required=True)
    a=p.parse_args();print(json.dumps(score(a.source,a.replay,a.annotations,a.output,a.split),indent=2))
if __name__=='__main__':main()
