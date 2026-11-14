"""Visualize added descriptive coverage; error samples use new support only."""
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def plot(args):
    results=[json.loads((p/'results.json').read_text()) for p in (args.baseline,args.candidate)]
    fig,axes=plt.subplots(1,2,figsize=(11,4.8),layout='constrained')
    splits=['development','benchmark_holdout'];labels=['Development','Previously used holdout']
    for j,(result,color,label) in enumerate(zip(results,['#64748b','#176c8e'],['Before','With descriptive forecasts'])):
        counts=[result['comparisons'][s+':main_operator']['common_free_flight']['100']['coverage']['v2_managed'] for s in splits]
        bars=axes[0].bar(np.arange(2)+(j-.5)*.34,[c['cutoffs']/c['offered_cutoffs']*100 for c in counts],
                         width=.34,color=color,label=label)
        for bar,c in zip(bars,counts):
            axes[0].text(bar.get_x()+bar.get_width()/2,bar.get_height()+2,
                         f"{c['cutoffs']}/{c['offered_cutoffs']}\n{c['arcs']}/{c['offered_arcs']} arcs",ha='center',fontsize=8)
    axes[0].set(xticks=np.arange(2),xticklabels=labels,ylim=(0,112),ylabel='Available 100 ms forecasts (%)',title='Physical forecast coverage')
    axes[0].legend(loc='upper center',bbox_to_anchor=(.5,-.11),ncol=2,fontsize=8)
    indexed=[]
    for path in (args.baseline,args.candidate):
        with (path/'common-errors.csv').open() as stream:
            indexed.append({(r['split'],r['arc_id'],r['source_index']):float(r['error_m'])
                            for r in csv.DictReader(stream) if r['method']=='v2_managed' and r['query']=='100'})
    for i,split in enumerate(splits):
        arcs=defaultdict(list)
        for key,value in indexed[1].items():
            if key not in indexed[0] and key[0]==split:arcs[key[1]].append(value)
        rms=np.sort([np.sqrt(np.mean(np.square(v)))*1000 for v in arcs.values()])
        axes[1].plot(rms,np.arange(1,len(rms)+1)/len(rms)*100,label=labels[i],lw=2)
    axes[1].set(xlabel='Per-arc RMS position error at 100 ms (mm)',ylabel='Cumulative share of arcs (%)',
                title='Error on newly covered cutoffs')
    axes[1].legend(fontsize=8)
    for ax in axes:
        ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True);ax.spines[['right','top']].set_visible(False)
    fig.suptitle('PPQ004: descriptive coverage increases; command-eligible targets are unchanged\n'
                 'Same-sensor recorded-proxy scoring; previously qualified estimates remain identical',fontsize=11)
    args.output.mkdir(parents=True,exist_ok=True)
    for suffix in ('png','svg'):fig.savefig(args.output/('descriptive-coverage.'+suffix),dpi=180)
    plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('baseline','candidate','output'):p.add_argument('--'+name,type=Path,required=True)
    plot(p.parse_args())
