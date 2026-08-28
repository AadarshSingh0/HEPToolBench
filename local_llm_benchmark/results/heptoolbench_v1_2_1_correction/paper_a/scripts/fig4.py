"""Figure 4: structured generation and the structured-debugging extension."""
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt, numpy as np
from matplotlib.lines import Line2D
from build import load, primary, leaderboard, ROOT

plt.rcParams.update({'font.size':8,'axes.labelsize':8.6,'legend.fontsize':7.4,
                     'axes.spines.top':False,'axes.spines.right':False})
C_API='#b5651d'; C_LOC='#1f4e79'
FREEFORM=['mg_basic_001','mg_basic_002','mg_basic_003','mg_debug_001','mg_debug_002',
          'mg_debug_003','mg_runcard_004','mg_workflow_005']

d=load(); lb=leaderboard(d)
main=primary(d,'main28'); dbg=primary(d,'structured_debug3')
structured=sorted(set(main.task_id)-set(FREEFORM))
g=(main[main.task_id.isin(structured)].groupby('model',as_index=False)
   .agg(gen_mean=('score','mean'),gen_pass=('passed','sum')))
b=dbg.groupby('model',as_index=False).agg(dbg_mean=('score','mean'),dbg_pass=('passed','sum'))
L=lb.merge(g,on='model').merge(b,on='model')

fig=plt.figure(figsize=(7.1,3.5))
gs=fig.add_gridspec(1,2,width_ratios=[1.0,1.0],wspace=0.30)
axA=fig.add_subplot(gs[0,0]); axB=fig.add_subplot(gs[0,1])

axA.plot([0,1],[0,1],color='0.55',ls='--',lw=1.0,zorder=1)
for _,r in L.iterrows():
    local=r['route']=='local'
    axA.scatter(r['gen_mean'],r['dbg_mean'],marker='o' if local else '^',s=44,
                facecolor=C_LOC if local else C_API,edgecolor='white',lw=0.6,zorder=4)
axA.set_xlabel('Structured generation (20-task mean)')
axA.set_ylabel('Structured debugging (3-task mean)')
axA.set_xlim(-0.03,1.05); axA.set_ylim(-0.05,1.07)
axA.grid(alpha=0.2,lw=0.6)
axA.set_title('(a)  Generation and debugging',loc='left',fontsize=9.0,fontweight='bold')
axA.legend(handles=[Line2D([],[],marker='o',ls='none',ms=5,mfc=C_LOC,mec='white',label='served locally'),
                    Line2D([],[],marker='^',ls='none',ms=5,mfc=C_API,mec='white',label='served by API')],
           frameon=False,loc='upper left',fontsize=7.0)

for i,(rt,col,lab) in enumerate([('api',C_API,'API'),('local',C_LOC,'local')]):
    s=L[L.route==rt]
    rng=np.random.default_rng(11+i); j=rng.uniform(-0.15,0.15,len(s))
    axB.scatter(i+j,s.dbg_mean,s=25,facecolor=col,edgecolor='none',alpha=0.72,zorder=3)
    axB.hlines(s.dbg_mean.mean(),i-0.28,i+0.28,color='black',lw=1.8,zorder=4)
    axB.text(i,1.055,'mean %.3f\n$n=%d$'%(s.dbg_mean.mean(),len(s)),ha='center',fontsize=7.0)
axB.set_xticks([0,1]); axB.set_xticklabels(['API route','local route'],fontsize=7.8)
axB.set_xlim(-0.55,1.55); axB.set_ylim(-0.08,1.16)
axB.set_ylabel('Mean score on the 3 debug tasks')
axB.grid(axis='y',alpha=0.2,lw=0.6)
axB.set_title('(b)  One point per deployment',loc='left',fontsize=9.0,fontweight='bold')

fig.savefig(ROOT/'figures'/'fig4_debugging.pdf',bbox_inches='tight')
fig.savefig(ROOT/'figures'/'fig4_debugging.png',dpi=300,bbox_inches='tight')
from scipy.stats import spearmanr, mannwhitneyu
sp=spearmanr(L.gen_mean,L.dbg_mean)
mw=mannwhitneyu(L[L.route=='api'].dbg_mean,L[L.route=='local'].dbg_mean,alternative='two-sided')
print('fig4 ok. rho=%.3f p=%.4g; route MW p=%.4g'%(sp.statistic,sp.pvalue,mw.pvalue))
