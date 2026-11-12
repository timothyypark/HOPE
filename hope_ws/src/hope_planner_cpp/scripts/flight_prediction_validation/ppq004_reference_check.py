"""Reproduce the archived training-only holdout within frozen tolerances."""
import argparse
import json
from pathlib import Path
import subprocess
import sys


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--tools',type=Path,required=True)
    p.add_argument('--fit',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    proc=subprocess.run([sys.executable,str(a.tools/'score_holdout.py'),'--fit',str(a.fit)],capture_output=True,text=True)
    (a.output/'stdout.json').write_text(proc.stdout);(a.output/'stderr.log').write_text(proc.stderr)
    if proc.returncode:raise SystemExit(proc.returncode)
    r=json.loads(proc.stdout);checks={}
    for metric,expected,tolerance in [('endpoint_mm',20.7699,.05),('future_rms_mm',11.9898,.05),('net_time_ms',1.60218,.01)]:
        actual=r['summary'][metric]['median'];checks[metric]=dict(expected=expected,actual=actual,tolerance=tolerance,pass_check=abs(actual-expected)<=tolerance)
    counts=(r['train_arcs'],r['holdout_arcs'],r['causal_arcs'])==(246,27,24)
    result=dict(status='PASS' if counts and all(x['pass_check'] for x in checks.values()) else 'FAIL',checks=checks,counts_match=counts,
        evidence_type='measured_recording',scope='archived train-only physics benchmark, not V2 qualification')
    (a.output/'results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));return int(result['status']!='PASS')
if __name__=='__main__':raise SystemExit(main())
