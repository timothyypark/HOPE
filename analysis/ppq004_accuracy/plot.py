"""Plot matched holdout accuracy and coverage without dropping missing output."""
import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def plot(results, output):
    data=json.loads(results.read_text())
    horizons=data['contract']['common_rollout_horizons_ms']
    fig,axes=plt.subplots(2,2,figsize=(12,8),layout='constrained')
    colors={'main':'#245b91','v2':'#c65121'}
    for ax,method,title in zip(axes[0],['main_batch','main_operator'],
                              ['Downstream batch fit baseline','Operator preview baseline']):
        rows=data['comparisons']['benchmark_holdout:'+method]['common_free_flight']
        for field,label,color in [('main_paired_arc_rms','Main',colors['main']),
                                   ('v2_paired_arc_rms','Managed CKF',colors['v2'])]:
            ax.plot(horizons,[rows[str(h)][field]['median'] for h in horizons],
                    'o-',label=label,color=color,lw=2)
        for h in horizons:
            row=rows[str(h)]
            y=max(row['main_paired_arc_rms']['median'],row['v2_paired_arc_rms']['median'])
            ax.annotate(f"n={row['paired_arcs']}",(h,y),xytext=(0,8),textcoords='offset points',
                        ha='center',fontsize=8)
        ax.set(title=title,xlabel='Prediction horizon ahead of current sample (ms)',
               ylabel='Median per-arc RMS position error (mm)',ylim=(0,40))
        ax.legend(frameon=False)
    ax=axes[1,0]
    for shift,method,label,color in [(-2,'main_batch','versus batch',colors['main']),
                                    (2,'main_operator','versus operator','#6a4595')]:
        rows=data['comparisons']['benchmark_holdout:'+method]['common_free_flight']
        med=np.array([rows[str(h)]['median_paired_difference'] for h in horizons])
        ci=np.array([rows[str(h)]['paired_bootstrap_95'] for h in horizons])
        ax.errorbar(np.array(horizons)+shift,med,yerr=[med-ci[:,0],ci[:,1]-med],
                    fmt='o',capsize=4,label=label,color=color)
    ax.axhline(0,color='gray',lw=1)
    ax.set(title='Paired difference and 95% arc bootstrap interval',
           xlabel='Prediction horizon (ms)',ylabel='CKF minus main error (mm); lower favors CKF')
    ax.legend(frameon=False)
    ax=axes[1,1]
    coverage=data['comparisons']['benchmark_holdout:main_operator']['common_free_flight']['100']['coverage']
    methods=['main_batch','main_operator','v2_managed']
    offered=coverage['v2_managed']['offered_cutoffs']
    counts=[coverage[m]['cutoffs'] for m in methods]
    bars=ax.bar(['Main batch','Main operator','Managed CKF'],np.array(counts)/offered*100,
                color=[colors['main'],'#6a4595',colors['v2']])
    for bar,method in zip(bars,methods):
        c=coverage[method]
        ax.text(bar.get_x()+bar.get_width()/2,bar.get_height()+2,
                f"{c['cutoffs']}/{offered} cutoffs\n{c['arcs']}/{c['offered_arcs']} arcs",
                ha='center',fontsize=9)
    ax.set(title='100 ms forecast availability',ylabel='Eligible cutoffs with an estimate (%)',ylim=(0,110))
    for ax in axes.flat:
        ax.grid(axis='y',alpha=.18);ax.set_axisbelow(True)
        ax.spines[['right','top']].set_visible(False)
    fig.suptitle('PPQ004 part 3: conditional prediction accuracy and availability\n'
                 'Common free-flight propagation; same-sensor proxy truth; one previously used holdout take',fontsize=13)
    output.mkdir(parents=True,exist_ok=True)
    for extension in ('png','svg'):
        fig.savefig(output/('accuracy-and-coverage.'+extension),dpi=180)
    plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--results',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();plot(args.results,args.output)
