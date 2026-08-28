"""Figure 3: main-suite performance versus disclosed total parameter count."""
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D
from build import load, leaderboard, ROOT

plt.rcParams.update({'font.size':8,'axes.labelsize':8.8,'legend.fontsize':7.4,
                     'axes.spines.top':False,'axes.spines.right':False})
C_LOCAL='#1f4e79'; C_API='#b5651d'

lb=leaderboard(load())
known=lb[lb.total_b.notna()].copy()

fig,ax=plt.subplots(figsize=(7.1,4.3))
for _,r in known.iterrows():
    local=r['route']=='local'
    ax.scatter(r['total_b'],r['mean_score'],marker='o' if local else '^',s=48,
               facecolor=C_LOCAL if local else C_API,
               edgecolor='black' if r['is_moe'] else 'white',
               lw=1.15 if r['is_moe'] else 0.7,zorder=4)

labels={
 'Gemma 3 270M':(0.34,0.235),'Gemma 4 E2B':(1.35,0.76),
 'Phi-4 Reasoning Plus':(8.0,0.285),'Qwen3 8B':(4.8,0.82),
 'Qwen3 14B':(8.5,0.87),'gpt-oss 20B':(15,0.95),
 'Llama 3.3 70B (local)':(36,0.650),'Llama 3.3 70B (API)':(40,0.88),
 'DeepSeek-R1 70B':(115,0.62),'Qwen3-Next 80B-A3B':(50,0.93),
 'gpt-oss 120B':(190,0.96),'Devstral 2512':(150,0.84),
 'Mistral Large 2512':(480,0.70)
}
for name,(tx,ty) in labels.items():
    s=known[known.display==name]
    if len(s):
        r=s.iloc[0]
        ax.annotate(name,xy=(r.total_b,r.mean_score),xytext=(tx,ty),fontsize=6.7,
                    color='0.25',ha='center',
                    arrowprops=dict(arrowstyle='-',color='0.45',lw=0.6))

ax.set_xscale('log'); ax.set_xlim(0.18,1000); ax.set_ylim(0.20,1.0)
ax.set_xlabel('Disclosed total parameter count (billions, log scale)')
ax.set_ylabel('Mean score on the 28-task main suite')
ax.grid(alpha=0.2,lw=0.6)
ax.legend(handles=[
    Line2D([],[],marker='o',ls='none',ms=5,mfc=C_LOCAL,mec='white',label='served locally'),
    Line2D([],[],marker='^',ls='none',ms=5,mfc=C_API,mec='white',label='served by API'),
    Line2D([],[],marker='o',ls='none',ms=5,mfc='white',mec='black',mew=1.1,label='sparse / MoE')],
    frameon=False,loc='upper left')

fig.savefig(ROOT/'figures'/'fig3_scale.pdf',bbox_inches='tight')
fig.savefig(ROOT/'figures'/'fig3_scale.png',dpi=300,bbox_inches='tight')
from scipy.stats import spearmanr
res=spearmanr(known.total_b,known.mean_score)
print('fig3 ok. n=%d rho=%.3f p=%.4g'%(len(known),res.statistic,res.pvalue))
