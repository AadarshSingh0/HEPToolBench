"""Figure 5: run-to-run stability. Ten deployments, five repeats each, 28-task main suite.

Models along the x-axis, one colour each. For every deployment the five individual
runs are shown as light dots, the diamond is their mean with a one standard
deviation bar, and the short horizontal rule marks the designated (canonical) run
used everywhere else in the paper, so the figure also shows that reading a single
run per deployment is a representative draw.

Panel (a): mean score.  Panel (b): strict pass count (of 28).
Reads the stability result file from data/.
"""
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt, numpy as np, pandas as pd
from matplotlib.lines import Line2D
from build import load, leaderboard, ROOT, DISPLAY

plt.rcParams.update({'font.size': 8, 'axes.labelsize': 8.6, 'legend.fontsize': 7.2,
                     'axes.spines.top': False, 'axes.spines.right': False})

STAB = ROOT / 'data' / 'HEPToolBench_stability_v1_2_1_10models_x5.csv'
s = pd.read_csv(STAB, encoding='utf-8')
s['passed'] = s['passed'].astype(str).str.lower().eq('true')
s = s[s['task_partition'] == 'main28'].copy()
lb = leaderboard(load()).set_index('model')

rows = []
for mdl, g in s.groupby('model'):
    pc = g.groupby('repeat')['passed'].sum().astype(float)
    ms = g.groupby('repeat')['score'].mean()
    rows.append(dict(disp=DISPLAY.get(mdl, mdl),
                     score_runs=ms.values, pass_runs=pc.values,
                     score_mean=ms.mean(), score_sd=ms.std(ddof=1),
                     pass_mean=pc.mean(), pass_sd=pc.std(ddof=1),
                     canon_score=lb.loc[mdl, 'mean_score'] if mdl in lb.index else np.nan,
                     canon_pass=lb.loc[mdl, 'passes'] if mdl in lb.index else np.nan))
R = pd.DataFrame(rows).sort_values('score_mean', ascending=False).reset_index(drop=True)
x = np.arange(len(R))
palette = plt.cm.tab10(np.linspace(0, 1, 10))[:len(R)]

fig, (axA, axB) = plt.subplots(2, 1, figsize=(7.2, 6.6), sharex=True,
                               gridspec_kw={'hspace': 0.12})
rng = np.random.default_rng(7)

for ax, runs_c, mean_c, sd_c, canon_c in [
        (axA, 'score_runs', 'score_mean', 'score_sd', 'canon_score'),
        (axB, 'pass_runs', 'pass_mean', 'pass_sd', 'canon_pass')]:
    for i, r in R.iterrows():
        col = palette[i]
        jit = rng.uniform(-0.16, 0.16, len(r[runs_c]))
        ax.scatter(i + jit, r[runs_c], s=16, color=col, edgecolor='none',
                   alpha=0.55, zorder=2)
        ax.errorbar(i, r[mean_c], yerr=r[sd_c], fmt='D', ms=6, color=col,
                    ecolor=col, elinewidth=1.5, capsize=3.5, mec='black',
                    mew=0.5, zorder=4)
        if not np.isnan(r[canon_c]):
            ax.hlines(r[canon_c], i - 0.22, i + 0.22, color='0.15', lw=1.6, zorder=5)
    ax.grid(axis='y', alpha=0.2, lw=0.6)
    ax.set_xlim(-0.6, len(R) - 0.4)

axA.set_ylabel('Mean scorer score')
axA.set_title('(a)  Mean score, five runs per deployment (mean $\\pm$ 1 s.d.)',
              loc='left', fontsize=9.2, fontweight='bold')
axB.set_ylabel('Strict passes (of 28)')
axB.set_title('(b)  Strict pass count, same five runs',
              loc='left', fontsize=9.2, fontweight='bold')
axB.set_xticks(x)
axB.set_xticklabels(R['disp'], rotation=32, ha='right', fontsize=7.6)

h = [Line2D([], [], marker='o', ls='none', ms=4, mfc='0.6', mec='none', label='individual run'),
     Line2D([], [], marker='D', ls='none', ms=6, mfc='0.4', mec='black', mew=0.5,
            label='mean $\\pm$ 1 s.d.'),
     Line2D([], [], marker='_', ls='none', ms=10, mec='0.15', mew=1.6, label='designated run')]
axA.legend(handles=h, frameon=False, loc='lower left', fontsize=7.2, ncol=3)

fig.savefig(ROOT / 'figures' / 'fig5_stability.pdf', bbox_inches='tight')
fig.savefig(ROOT / 'figures' / 'fig5_stability.png', dpi=300, bbox_inches='tight')
print('fig5 ok. pass sd mean=%.2f score sd mean=%.4f n=%d' %
      (R.pass_sd.mean(), R.score_sd.mean(), len(R)))
