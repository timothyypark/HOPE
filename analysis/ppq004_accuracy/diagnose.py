"""Count unavailable predictions at the existing eligible score cutoffs."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import numpy as np
from score import crossing


def diagnose(args):
    episodes=[json.loads(line) for line in args.annotations.read_text().splitlines()]
    groups=defaultdict(Counter)
    for part in (1,2,3):
        name=f'ppq004_part{part}'
        data=dict(np.load(args.source/f'fit/part{part}/raw_extracted.npz'))
        data['ns']=np.rint(data['t']*1e9).astype(np.int64)
        split='benchmark_holdout' if part==3 else 'development'
        rows={}
        for binary in ('main_replay','v2_replay'):
            for line in (args.replay/f'{name}.{binary}.jsonl').read_text().splitlines():
                r=json.loads(line);rows[r['method'],r['source_index']]=r
        for arc in episodes:
            if arc['recording_id']!=name or arc['direction']!='negative':continue
            begin,end=arc['source_frames']
            truth=crossing(data,begin,end,.15)
            for index in range(begin+(-begin%6),end+1,6):
                if not data['ball_present'][index]:continue
                for method in ('main_batch','main_operator','v2_managed'):
                    row=rows[method,index]
                    if index+30<=end and data['ball_present'][index+30]:
                        reason='AVAILABLE' if row['available'] else row['state']+':'+row['reason']
                        groups[split+':100ms:'+method][reason]+=1
                    if truth and .01<=(truth['arrival_ns']-int(data['ns'][index]))*1e-9<=.5:
                        target=next(t for t in row['targets'] if t['plane']==.15)
                        reason='AVAILABLE' if target['valid'] else target['reason']
                        groups[split+':plane0.15:'+method][reason]+=1
    args.output.write_text(json.dumps({k:dict(v) for k,v in groups.items()},indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('source','annotations','replay','output'):
        p.add_argument('--'+name,type=Path,required=True)
    diagnose(p.parse_args())
