"""Standalone evidence index: every gate links to retained receipts and failures."""
import argparse
import html
import json
from pathlib import Path


def report(root):
    results=json.loads((root/'results.json').read_text())
    rows=[]
    for name,gate in results['gates'].items():
        link=html.escape(gate.get('log',name+'.log'),quote=True)
        rows.append('<tr><td>'+html.escape(name)+'</td><td>'+html.escape(gate['status'])+
                    '</td><td>'+html.escape(gate.get('evidence_type','software_fixture'))+
                    '</td><td><a href="'+link+'">raw receipt</a></td><td>'+html.escape(gate.get('reason',''))+'</td></tr>')
    state_sections=[]
    for path in sorted(root.glob('state-score-*.json')):
        s=json.loads(path.read_text());matrix=s.get('confusion_matrix',{})
        state_sections.append('<details><summary>'+html.escape(path.name)+'</summary><pre>'+html.escape(json.dumps(matrix,indent=2))+'</pre></details>')
    # Compact actual trace timelines retain source frame indices for review.
    timeline=[]
    for path in sorted((root/'managed').glob('*.trace.jsonl')):
        previous=None
        with path.open() as f:
            for line in f:
                r=json.loads(line)
                if r['phase']!='after':continue
                if r['play_state']!=previous:
                    timeline.append(dict(recording=path.stem,source_index=r['source_index'],source_ns=r['source_ns'],
                        state=r['play_state'],generation=r['generation'],reason=r['reason']))
                    previous=r['play_state']
    payload=json.dumps(timeline).replace('<','\\u003c')
    figures=''.join('<figure><img style="max-width:100%" src="'+html.escape(p.name,quote=True)+'"><figcaption>'+html.escape(p.name)+'</figcaption></figure>' for p in sorted(root.glob('*.png')))
    text='''<!doctype html><meta charset="utf-8"><title>PPQ004 validation evidence</title>
<style>body{font:16px system-ui;max-width:1200px;margin:32px auto;padding:0 20px}table{border-collapse:collapse;width:100%}td,th{padding:8px;border-bottom:1px solid #ddd;text-align:left}pre{white-space:pre-wrap}a{color:#1254a1}select{padding:8px}</style>
<h1>PPQ004 validation evidence</h1><p>Recorded proxy, controlled fixtures, simulation and physical evidence are separate. Missing evidence never counts as a pass.</p>
<p><a href="results.json">Machine-readable results and source binding</a> · <a href="campaign.json">Frozen campaign</a></p>
<table><thead><tr><th>Gate</th><th>Status</th><th>Evidence</th><th>Receipt</th><th>Limits</th></tr></thead><tbody>'''+''.join(rows)+'''</tbody></table>
<h2>Measured paths and forecasts</h2>'''+figures+'''<h2>Measured classification</h2>'''+''.join(state_sections)+'''
<h2>Actual state transitions</h2><p>Observed classifier transitions are not independent truth labels. Select a state to locate its recording and original source frame.</p><select id="filter"><option>All</option><option>INVALID</option><option>RALLY</option><option>OPPONENT_RALLY</option><option>SERVE</option><option>OPPONENT_SERVE</option></select><pre id="timeline"></pre>
<script>const data='''+payload+''';const filter=document.getElementById('filter');function draw(){document.getElementById('timeline').textContent=data.filter(r=>filter.value==='All'||r.state===filter.value).map(r=>JSON.stringify(r)).join('\\n')}filter.onchange=draw;draw();</script>'''
    (root/'index.html').write_text(text)
    return root/'index.html'

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',type=Path);report(p.parse_args().root)
