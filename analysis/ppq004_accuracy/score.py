"""Paired recorded-proxy accuracy; future observations are used only here."""
import argparse
from collections import defaultdict, Counter
import csv
import json
from pathlib import Path
import numpy as np
from run import digest

METHODS = ('main_batch', 'main_operator', 'v2_managed')


def free_flight(state, omega, duration, drag, magnus, step=0.0005):
    """Common RK4 free-flight kernel; no contacts or fitting to future truth."""
    state = np.asarray(state, dtype=float).copy()
    omega = np.asarray(omega, dtype=float)
    remaining = np.broadcast_to(np.asarray(duration, dtype=float), (len(state),)).copy()
    if not len(state):
        return state
    def rhs(value):
        v = value[:, 3:]
        a = -drag * np.linalg.norm(v, axis=1)[:, None] * v + magnus * np.cross(omega, v)
        a[:, 2] -= 9.81
        return np.column_stack((v, a))
    while np.max(remaining) > 1e-12:
        h = np.minimum(remaining, step)[:, None]
        k1 = rhs(state); k2 = rhs(state + h * k1 / 2)
        k3 = rhs(state + h * k2 / 2); k4 = rhs(state + h * k3)
        state += h * (k1 + 2*k2 + 2*k3 + k4) / 6
        remaining = np.maximum(0, remaining - h[:, 0])
    return state


def crossing(data, begin, end, plane):
    p, present, t = data['ball_pos'], data['ball_present'], data['ns']
    choices = [i for i in range(begin, end) if present[i] and present[i+1]
               and p[i, 0] >= plane and p[i+1, 0] < plane]
    if len(choices) != 1:
        return None
    i = choices[0]
    fraction = (plane-p[i, 0])/(p[i+1, 0]-p[i, 0])
    return dict(index=i, arrival_ns=float(t[i]+fraction*(t[i+1]-t[i])),
                position=p[i]+fraction*(p[i+1]-p[i]), bracket=[int(t[i]), int(t[i+1])])


def distribution(values):
    if not values:
        return dict(n=0, median=None, p95=None)
    return dict(n=len(values), median=float(np.median(values)), p95=float(np.percentile(values, 95)))


def paired_summary(rows, offered, main, metric='error_m', scale=1000):
    by_method = {m: {} for m in METHODS}
    for row in rows:
        key = (row['arc_id'], row['source_index'], row['query'])
        if key in by_method[row['method']]:
            raise ValueError('Duplicate score identity')
        by_method[row['method']][key] = row
    support = {}
    for method, indexed in by_method.items():
        groups = defaultdict(list)
        for key, row in indexed.items():
            groups[key[0]].append(row[metric])
        rms = [float(np.sqrt(np.mean(np.square(v)))) * scale for v in groups.values()]
        support[method] = dict(cutoffs=len(indexed), arcs=len(groups), offered_cutoffs=len(offered),
                               offered_arcs=len({key[0] for key in offered}),
                               own_support_arc_rms=distribution(rms))
    keys = sorted(set(by_method[main]) & set(by_method['v2_managed']))
    groups = defaultdict(lambda: [[], []])
    for key in keys:
        groups[key[0]][0].append(by_method[main][key][metric])
        groups[key[0]][1].append(by_method['v2_managed'][key][metric])
    arcs = []
    for arc, (a, b) in sorted(groups.items()):
        x, y = float(np.sqrt(np.mean(np.square(a))))*scale, float(np.sqrt(np.mean(np.square(b))))*scale
        arcs.append(dict(arc_id=arc, paired_cutoffs=len(a), main_rms=x, v2_rms=y, difference_v2_minus_main=y-x))
    differences = [a['difference_v2_minus_main'] for a in arcs]
    result = dict(main_method=main, metric=metric, scale=scale, coverage=support,
                  paired_cutoffs=len(keys), paired_arcs=len(arcs), per_arc=arcs,
                  main_paired_arc_rms=distribution([a['main_rms'] for a in arcs]),
                  v2_paired_arc_rms=distribution([a['v2_rms'] for a in arcs]),
                  median_paired_difference=None, paired_bootstrap_95=None,
                  assessment='INSUFFICIENT_PAIRED_SUPPORT',
                  main_only_cutoffs=len(set(by_method[main])-set(by_method['v2_managed'])),
                  v2_only_cutoffs=len(set(by_method['v2_managed'])-set(by_method[main])),
                  v2_lower_availability=(support['v2_managed']['cutoffs'] < support[main]['cutoffs']
                     or support['v2_managed']['arcs'] < support[main]['arcs']))
    if differences:
        rng = np.random.default_rng(140126)
        bootstrap = np.median(rng.choice(differences, size=(5000, len(differences)), replace=True), axis=1)
        low, high = map(float, np.quantile(bootstrap, [0.025, 0.975]))
        result.update(median_paired_difference=float(np.median(differences)), paired_bootstrap_95=[low, high])
        if len(arcs) >= 5:
            result['assessment'] = 'V2_LOWER_PAIRED_ERROR' if high < 0 else 'MAIN_LOWER_PAIRED_ERROR' if low > 0 else 'NO_CLEAR_PAIRED_DIFFERENCE'
    return result


def score(args):
    receipt = json.loads((args.replay / 'receipt.json').read_text())
    if not receipt.get('completed_ns') or not receipt['source_unchanged']:
        raise ValueError('Replay not complete with unchanged source')
    contract = receipt['contract']
    args.output.mkdir(parents=True, exist_ok=False)
    episodes = [json.loads(line) for line in args.annotations.read_text().splitlines()]
    common_rows, plane_rows = [], []
    common_offered, plane_offered = defaultdict(set), defaultdict(set)
    inventory, reasons = [], defaultdict(Counter)
    for part in (1, 2, 3):
        name = f'ppq004_part{part}'
        data_path = args.source / f'fit/part{part}/raw_extracted.npz'
        data = dict(np.load(data_path)); data['ns'] = np.rint(data['t']*1e9).astype(np.int64)
        input_path=args.replay/(name+'.csv')
        expected_input=next(r['input_sha256'] for r in receipt['runs'] if r['recording']==name)
        if digest(input_path)!=expected_input:
            raise ValueError('Replay input changed')
        replay_input=np.loadtxt(input_path,delimiter=',')
        np.testing.assert_array_equal(replay_input[:,0],np.arange(len(data['t'])))
        np.testing.assert_array_equal(replay_input[:,1],data['ns'])
        np.testing.assert_array_equal(replay_input[:,2],data['ball_present'])
        present=data['ball_present'].astype(bool)
        np.testing.assert_allclose(replay_input[present,3:6],data['ball_pos'][present],rtol=0,atol=1e-14)
        split = 'benchmark_holdout' if part == 3 else 'development'
        arcs = [e for e in episodes if e['recording_id'] == name and e['direction'] == 'negative']
        if any(e['split']!=split for e in arcs):
            raise ValueError('Annotation split mismatch')
        rows = {m: {} for m in METHODS}
        for binary in ('main_replay', 'v2_replay'):
            path = args.replay / f'{name}.{binary}.jsonl'
            expected = next(r['output_sha256'] for r in receipt['runs'] if r['recording']==name and r['binary']==binary)
            if digest(path) != expected:
                raise ValueError('Replay output changed')
            for line in path.read_text().splitlines():
                row = json.loads(line); method=row['method']; index=row['source_index']
                if index in rows[method] or row['source_ns'] != int(data['ns'][index]):
                    raise ValueError('Duplicate/misaligned replay source')
                rows[method][index] = row
        expected_indices = set(range(0, len(data['t']), 6))
        if any(set(v) != expected_indices for v in rows.values()):
            raise ValueError('Incomplete replay denominator')
        inventory.append(dict(recording=name, split=split, frames=len(data['t']),
                              incoming_arcs=len(arcs), all_arcs=sum(e['recording_id']==name for e in episodes),
                              source_sha256=digest(data_path)))
        work = defaultdict(list)
        for arc in arcs:
            begin, end = arc['source_frames']; arc_id=arc['physical_flight_id']
            for index in range(begin + (-begin % 6), end+1, 6):
                if not data['ball_present'][index]:
                    continue
                for method in METHODS:
                    r=rows[method][index]; reasons[split+':'+method][r['reason']] += 1
                for horizon in contract['common_rollout_horizons_ms']:
                    target=index+round(horizon*.3)
                    if target>end or not data['ball_present'][target]:
                        continue
                    key=(arc_id,index,horizon);common_offered[split,horizon].add(key)
                    for method in METHODS:
                        row=rows[method][index]
                        if row['available']:
                            work[horizon].append((method,arc_id,index,target,row))
            for plane in [contract['primary_plane_m'], *contract['diagnostic_planes_m']]:
                truth=crossing(data,begin,end,plane)
                if truth is None:
                    continue
                for index in range(begin + (-begin % 6), truth['index']+1, 6):
                    lead=(truth['arrival_ns']-int(data['ns'][index]))*1e-9
                    if not data['ball_present'][index] or not 0.01 <= lead <= 0.5:
                        continue
                    key=(arc_id,index,plane);plane_offered[split,plane].add(key)
                    for method in METHODS:
                        row=rows[method][index]; target=next(t for t in row['targets'] if t['plane']==plane)
                        if not target['valid']:
                            continue
                        time_error=abs(target['arrival_ns']-truth['arrival_ns'])*1e-6
                        bracket_error=max(truth['bracket'][0]-target['arrival_ns'],0,target['arrival_ns']-truth['bracket'][1])*1e-6
                        plane_rows.append(dict(split=split,recording=name,arc_id=arc_id,source_index=index,
                            query=plane,method=method,lead_ms=lead*1000,
                            error_m=float(np.linalg.norm(np.asarray(target['position'])-truth['position'])),
                            time_error_ms=time_error,time_outside_bracket_ms=bracket_error))
        for horizon, items in work.items():
            states=[r['position']+r['velocity'] for _,_,_,_,r in items]
            spins=[r['omega'] for _,_,_,_,r in items]
            dt=[(int(data['ns'][j])-int(data['ns'][i]))*1e-9 for _,_,i,j,_ in items]
            predicted=free_flight(states,spins,dt,.12861635416914574,.00379260504480258)
            for (method,arc_id,index,target,row), state in zip(items,predicted):
                common_rows.append(dict(split=split,recording=name,arc_id=arc_id,source_index=index,
                    query=horizon,method=method,error_m=float(np.linalg.norm(state[:3]-data['ball_pos'][target]))))
    result=dict(contract=contract, replay_receipt_sha256=digest(args.replay/'receipt.json'),
                annotation_sha256=digest(args.annotations), inventory=inventory,
                reasons={k:dict(v) for k,v in reasons.items()}, comparisons={})
    for split in ('development','benchmark_holdout'):
        for main in ('main_operator','main_batch'):
            key=split+':'+main
            result['comparisons'][key]=dict(common_free_flight={},native_planes={})
            for horizon in contract['common_rollout_horizons_ms']:
                subset=[r for r in common_rows if r['split']==split and r['query']==horizon]
                result['comparisons'][key]['common_free_flight'][str(horizon)]=paired_summary(subset,common_offered[split,horizon],main)
            for plane in [contract['primary_plane_m'],*contract['diagnostic_planes_m']]:
                subset=[r for r in plane_rows if r['split']==split and r['query']==plane]
                result['comparisons'][key]['native_planes'][str(plane)]={
                    metric:paired_summary(subset,plane_offered[split,plane],main,metric,1000 if metric=='error_m' else 1)
                    for metric in ('error_m','time_error_ms','time_outside_bracket_ms')}
    for name, rows in (('common-errors',common_rows),('plane-errors',plane_rows)):
        with (args.output/(name+'.csv')).open('w') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(rows[0]) if rows else ['method']);writer.writeheader();writer.writerows(rows)
    (args.output/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result['inventory'],indent=2))
    for main in ('main_operator','main_batch'):
        r=result['comparisons']['benchmark_holdout:'+main]['common_free_flight']['100']
        print(main, json.dumps({k:r[k] for k in ('assessment','paired_arcs','paired_cutoffs','main_paired_arc_rms','v2_paired_arc_rms','paired_bootstrap_95','v2_lower_availability')}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('replay','source','annotations','output'):
        p.add_argument('--'+name,type=Path,required=True)
    score(p.parse_args())
