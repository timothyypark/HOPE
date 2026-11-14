"""Audit added descriptive coverage without relabeling command eligibility."""
import argparse
from collections import defaultdict
import csv
import json
from pathlib import Path
import numpy as np
from run import digest


def compare(args):
    report={'recordings':[], 'support':{}}
    for part in (1,2,3):
        name=f'ppq004_part{part}'
        output=name+'.v2_replay.jsonl'
        runs=[]
        for root in (args.baseline,args.candidate):
            receipt=json.loads((root/'receipt.json').read_text())
            assert receipt['completed_ns'] and receipt['source_unchanged']
            expected=next(r['output_sha256'] for r in receipt['runs']
                          if r['recording']==name and r['binary']=='v2_replay')
            assert digest(root/output)==expected
            runs.append([json.loads(line) for line in (root/output).read_text().splitlines()])
        old,new=runs
        assert len(old)==len(new)
        row=dict(recording=name,queries=len(old),old_available=0,new_available=0,
                 added_descriptive=0,qualified_state_changes=0,native_command_target_changes=0)
        for a,b in zip(old,new):
            assert (a['source_index'],a['source_ns'])==(b['source_index'],b['source_ns'])
            row['old_available']+=bool(a['available']);row['new_available']+=bool(b['available'])
            if a['available']:
                row['qualified_state_changes']+=int(not b['available'] or
                    any(a[k]!=b[k] for k in ('position','velocity','omega','generation')))
            elif b['available']:
                assert b['reason'].startswith('DESCRIPTIVE_ONLY:')
                row['added_descriptive']+=1
            for x,y in zip(a['targets'],b['targets']):
                assert x['plane']==y['plane']
                row['native_command_target_changes']+=int(x['valid']!=y['valid'] or
                    (x['valid'] and any(x[k]!=y[k] for k in ('position','arrival_ns'))))
        report['recordings'].append(row)
    scores=[]
    for root in (args.baseline_scores,args.candidate_scores):
        with (root/'common-errors.csv').open() as f:
            scores.append({(r['split'],r['arc_id'],int(r['source_index'])):float(r['error_m'])
                           for r in csv.DictReader(f) if r['method']=='v2_managed' and r['query']=='100'})
    old,new=scores
    for split in ('development','benchmark_holdout'):
        for label,keys in [('original_support',set(old)),('newly_covered',set(new)-set(old))]:
            groups=defaultdict(list)
            for key in sorted(keys):
                if key[0]==split and key in new:groups[key[1]].append(new[key])
            rms=[float(np.sqrt(np.mean(np.square(v))))*1000 for v in groups.values()]
            report['support'][split+':'+label]=dict(arcs=len(rms),cutoffs=sum(map(len,groups.values())),
                median_arc_rms_mm=float(np.median(rms)) if rms else None,
                p95_arc_rms_mm=float(np.percentile(rms,95)) if rms else None,
                worst_arc_rms_mm=max(rms) if rms else None)
    report['original_score_changes']=sum(key not in new or new[key]!=value for key,value in old.items())
    report['command_and_original_state_parity']=not report['original_score_changes'] and all(
        not r['qualified_state_changes'] and not r['native_command_target_changes'] for r in report['recordings'])
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    if not report['command_and_original_state_parity']:
        raise SystemExit('Parity failed; retain report and investigate')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('baseline','candidate','baseline-scores','candidate-scores','output'):
        p.add_argument('--'+name,type=Path,required=True)
    compare(p.parse_args())
