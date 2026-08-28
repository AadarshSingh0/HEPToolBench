"""Figure 2: the interface effect. Matched freeform/structured pairs, all models."""
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt, numpy as np, pandas as pd
from matplotlib.lines import Line2D
from build import load, primary, leaderboard, PAIRS, ROOT

plt.rcParams.update({'font.size':8,'axes.labelsize':8.6,'legend.fontsize':7.4,
                     'axes.spines.top':False,'axes.spines.right':False})
C_FREE='#8c8fc4'; C_STRUCT='#2f6f4e'; C_FAIL='#b03030'
C_SMALL='#1f4e79'; C_LARGE='#0f8a7a'; C_UND='#b5651d'
FACE={'small':C_SMALL,'large':C_LARGE,'undisclosed':C_UND}
MARK={'small':'o','large':'D','undisclosed':'s'}

d=load(); lb=leaderboard(d); m=primary(d)
rows=[]
for mdl,g in m.groupby('model'):
    f=g[g.task_id.isin([p[0] for p in PAIRS])]; s=g[g.task_id.isin([p[1] for p in PAIRS])]
    if len(f)!=5 or len(s)!=5: continue
    rows.append(dict(model=mdl,free=f.score.mean(),struct=s.score.mean(),
                     free_pass=int(f.passed.sum()),struct_pass=int(s.passed.sum())))
P=pd.DataFrame(rows).merge(lb[['model','display','size_class','total_b']],on='model')
P['gain']=P['struct']-P['free']; P['fmt_fail']=P['struct'].eq(0.0)
P['norm']=P.gain/(1-P.free).replace(0,np.nan)
P=P.sort_values('free').reset_index(drop=True)

fig=plt.figure(figsize=(7.1,8.6))
gs=fig.add_gridspec(2,1,height_ratios=[1.0,1.45],hspace=0.24)
axA=fig.add_subplot(gs[0]); axB=fig.add_subplot(gs[1])

# --- Manual axis-position controls for panel (b):
# Set `B_X_AXIS_POS` to a numeric y-coordinate (data units) to place the x-axis
# at that y value, or to the strings 'top' or 'bottom' to move ticks/label there.
# Set `B_Y_AXIS_POS` to a numeric x-coordinate (data units) to place the y-axis
# at that x value, or to the strings 'left' or 'right' to move ticks/label there.
# Examples:
#   B_X_AXIS_POS = 0.0    # place x-axis at y=0.0
#   B_X_AXIS_POS = 'top'  # put ticks/label on the top spine
#   B_Y_AXIS_POS = 0.0    # place y-axis at x=0.0
#   B_Y_AXIS_POS = 'right'
B_X_AXIS_POS = None
B_Y_AXIS_POS = None

def _apply_panel_b_axis_positions(ax, xpos, ypos):
    # x-axis (horizontal spine)
    if xpos is not None:
        if isinstance(xpos, (int, float)):
            ax.spines['bottom'].set_position(('data', xpos))
            ax.xaxis.set_ticks_position('bottom'); ax.xaxis.set_label_position('bottom')
        else:
            s = str(xpos).lower()
            if s == 'top':
                ax.xaxis.set_ticks_position('top'); ax.xaxis.set_label_position('top')
                ax.spines['top'].set_visible(True)
            elif s == 'bottom':
                ax.xaxis.set_ticks_position('bottom'); ax.xaxis.set_label_position('bottom')
    # y-axis (vertical spine)
    if ypos is not None:
        if isinstance(ypos, (int, float)):
            ax.spines['left'].set_position(('data', ypos))
            ax.yaxis.set_ticks_position('left'); ax.yaxis.set_label_position('left')
        else:
            s = str(ypos).lower()
            if s == 'right':
                ax.yaxis.set_ticks_position('right'); ax.yaxis.set_label_position('right')
                ax.spines['right'].set_visible(True)
            elif s == 'left':
                ax.yaxis.set_ticks_position('left'); ax.yaxis.set_label_position('left')

_apply_panel_b_axis_positions(axB, B_X_AXIS_POS, B_Y_AXIS_POS)

# ---- (a) paired scatter
axA.plot([0,1],[0,1],color='0.5',ls='--',lw=1.0,zorder=1)
axA.text(0.54,0.465,'no effect',rotation=20,fontsize=7,color='0.5',ha='center')
hb=P[~P.fmt_fail]['norm'].mean()
for _,r in P.iterrows():
    if r.fmt_fail:
        axA.scatter(r['free'],r['struct'],marker='X',s=78,color=C_FAIL,zorder=5); continue
    axA.scatter(r['free'],r['struct'],marker=MARK[r['size_class']],s=42,
                facecolor=FACE[r['size_class']],edgecolor='black',lw=0.4,zorder=4)
# Removed model-name annotations from panel (a) to reduce clutter; labels remain
# in the slope chart (panel b).
axA.set_xlim(-0.02,1.02); axA.set_ylim(-0.05,1.07)
axA.set_xlabel('Mean score, freeform interface'); axA.set_ylabel('Mean score, structured interface')
axA.grid(alpha=0.2,lw=0.6)
axA.set_title('(a)  Same physics request, two interfaces',loc='left',fontsize=9.4,fontweight='bold')
h=[Line2D([],[],marker='o',ls='none',ms=5,mfc=C_SMALL,mec='black',label=r'$<50$B'),
   Line2D([],[],marker='D',ls='none',ms=5,mfc=C_LARGE,mec='black',label=r'$\geq50$B'),
   Line2D([],[],marker='s',ls='none',ms=5,mfc=C_UND,mec='black',label='undisclosed')]
#    Line2D([],[],marker='X',ls='none',ms=7,color=C_FAIL,label='no parseable structured output')]
axA.legend(handles=h,frameon=False,loc='lower right',fontsize=7.0)

# ---- (b) slope chart
y=np.arange(len(P))
for i,r in P.iterrows():
    col=C_FAIL if r.fmt_fail else C_STRUCT
    axB.annotate('',xy=(r['struct'],i),xytext=(r['free'],i),
                 arrowprops=dict(arrowstyle='-|>',color=col,lw=1.15,alpha=0.9,shrinkA=1,shrinkB=1))
axB.scatter(P.free,y,s=26,facecolor=C_FREE,edgecolor='black',lw=0.4,zorder=4)
okm=~P.fmt_fail.values
axB.scatter(P.loc[okm,'struct'],y[okm],s=27,marker='s',facecolor=C_STRUCT,edgecolor='black',lw=0.4,zorder=5)
axB.scatter(P.loc[~okm,'struct'],y[~okm],s=62,marker='X',color=C_FAIL,zorder=5)
lbls=[f"{r['display']}   {r['free_pass']}$\\rightarrow${r['struct_pass']}" for _,r in P.iterrows()]
axB.set_yticks(y); axB.set_yticklabels(lbls,fontsize=5.6)
axB.set_ylim(-0.8,len(P)-0.2); axB.set_xlim(-0.03,1.05)
axB.set_xlabel('Mean score on the five matched pairs (annotation: strict passes out of 5)')
axB.grid(axis='x',alpha=0.2,lw=0.6); axB.tick_params(axis='y',length=0)
axB.spines['left'].set_visible(False)
axB.set_title('(b)  Ordered by freeform baseline',loc='left',fontsize=9.4,fontweight='bold')
h2=[Line2D([],[],marker='o',ls='none',ms=5,mfc=C_FREE,mec='black',label='freeform'),
    Line2D([],[],marker='s',ls='none',ms=5,mfc=C_STRUCT,mec='black',label='structured')]
axB.legend(handles=h2,frameon=False,loc='upper left',fontsize=7.2)

fig.savefig(ROOT/'figures'/'fig2_interface_effect.pdf',bbox_inches='tight')
fig.savefig(ROOT/'figures'/'fig2_interface_effect.png',dpi=300,bbox_inches='tight')
print('fig2 ok, n =',len(P),'headroom = %.1f%%'%(100*hb))
