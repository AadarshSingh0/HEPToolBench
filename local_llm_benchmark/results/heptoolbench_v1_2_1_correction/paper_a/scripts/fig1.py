"""Figure 1: capability overview, all complete models on the 28-task main suite."""
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt, numpy as np, pandas as pd
from matplotlib.lines import Line2D
from matplotlib.colors import LogNorm
from matplotlib.cm import ScalarMappable
from build import load, leaderboard, ROOT

plt.rcParams.update({'font.size':8,'axes.labelsize':9,'legend.fontsize':7.6,
                     'axes.spines.top':False,'axes.spines.right':False})

VENDOR = {'gemma':'Google','gemini':'Google','llama':'Meta','qwen':'Alibaba','deepseek':'DeepSeek',
          'phi':'Microsoft','granite':'IBM','gpt-oss':'OpenAI','gpt-4':'OpenAI','falcon':'TII',
          'mistral':'Mistral','ministral':'Mistral','magistral':'Mistral','codestral':'Mistral',
          'devstral':'Mistral','sarvam':'Sarvam'}
def vendor(raw):
    s=str(raw).lower()
    for k,v in VENDOR.items():
        if k in s: return v
    return 'other'

C_SMALL='#1f4e79'; C_LARGE='#0f8a7a'; C_UND='#7f7f7f'
FACE={'small':C_SMALL,'large':C_LARGE,'undisclosed':C_UND}
MARK={'small':'o','large':'^','undisclosed':'s'}

lb=leaderboard(load()).copy()
lb['vendor']=lb['model'].map(vendor)
lb=lb.sort_values(['pass_fraction','mean_score','display'],ascending=[True,True,False]).reset_index(drop=True)

n=len(lb); y=np.arange(n)
fig,ax=plt.subplots(figsize=(7.1,10.2))
# choose the parameter value used for the color scale: prefer total params when
# available so very large models (e.g. 120B) map to the high end of the colormap;
# fall back to active parameters when total is missing.
lb['plot_param']=lb['total_b']
known=lb['plot_param'].notna()
norm=LogNorm(vmin=lb.loc[known,'plot_param'].min(),vmax=lb.loc[known,'plot_param'].max())
cmap=plt.get_cmap('viridis')

for i,r in lb.iterrows():
    # Use the chosen plot_param value when available; otherwise fall back to
    # the model-size color so undisclosed-size models keep the same hue.
    col = cmap(norm(r['plot_param'])) if pd.notna(r['plot_param']) else FACE.get(r['size_class'], '0.68')
    ax.hlines(i,min(r['pass_fraction'],r['mean_score']),max(r['pass_fraction'],r['mean_score']),
              color=col,lw=1.9,alpha=0.75,zorder=1)
    ax.scatter(r['pass_fraction'],i,marker='D',s=34,facecolor=col,edgecolor='black',lw=0.4,zorder=3)
    ax.scatter(r['mean_score'],i,marker='s',s=33,facecolor=col,edgecolor='black',lw=0.4,zorder=3)
    # place the pass count a few points left of the pass marker to avoid overlap
    ax.annotate(f"{int(r['passes'])}", xy=(r['pass_fraction'], i), xytext=(-8, 0),
                textcoords='offset points', ha='right', va='center', fontsize=6.0,
                color='black', fontweight='bold', zorder=6)
    # color the size-shape marker with the same color as the score markers
    ax.scatter(-0.045,i,marker=MARK[r['size_class']],s=22,facecolor=col,
               edgecolor='black',lw=0.4,clip_on=False,zorder=4)

labels=[f"{r['display']}  ·  {r['vendor']}" for _,r in lb.iterrows()]
ax.set_yticks(y); ax.set_yticklabels(labels,fontsize=7.0)
ax.set_xlim(-0.06,1.02); ax.set_ylim(-0.8,n-0.2)
ax.set_xlabel('Score on the 28-task main suite')
ax.grid(axis='x',alpha=0.22,lw=0.6); ax.tick_params(axis='y',length=0)
ax.spines['left'].set_visible(False)

h=[Line2D([],[],marker='D',ls='none',ms=5,mfc='white',mec='black',label='Strict pass fraction'),
   Line2D([],[],marker='s',ls='none',ms=5,mfc='white',mec='black',label='Mean scorer score'),
    Line2D([],[],marker='o',ls='none',ms=5,mfc='none',mec='black',label=r'$<50$B total params'),
    Line2D([],[],marker='^',ls='none',ms=5,mfc='none',mec='black',label=r'$\geq50$B total params'),
    Line2D([],[],marker='s',ls='none',ms=5,mfc='none',mec='black',label='Size undisclosed')]
ax.legend(handles=h,ncol=3,frameon=False,loc='lower center',bbox_to_anchor=(0.48,1.004))
sm=ScalarMappable(norm=norm,cmap=cmap); sm.set_array(lb.loc[known,'plot_param'])
cb=fig.colorbar(sm,ax=ax,fraction=0.024,pad=0.015)
cb.set_label('Parameters (B, log scale)',fontsize=8); cb.ax.tick_params(labelsize=7)
fig.subplots_adjust(left=0.30,right=0.90,top=0.955,bottom=0.045)
fig.savefig(ROOT/'figures'/'fig1_capability_overview.pdf',bbox_inches='tight')
fig.savefig(ROOT/'figures'/'fig1_capability_overview.png',dpi=300,bbox_inches='tight')
print('fig1 ok, models =',n)
