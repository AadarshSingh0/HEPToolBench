"""Generate all LaTeX tables from the frozen CSV. Nothing hand-typed."""
import pandas as pd, numpy as np
from build import load, primary, leaderboard, PAIRS, DISPLAY, ROOT
FREEFORM=['mg_basic_001','mg_basic_002','mg_basic_003','mg_debug_001','mg_debug_002',
          'mg_debug_003','mg_runcard_004','mg_workflow_005']
def esc(s): return str(s).replace('_','\\_').replace('&','\\&')
d=load(); lb=leaderboard(d); m=primary(d)
STRUCT=sorted(set(m.task_id.unique())-set(FREEFORM))
dbg=primary(d,'structured_debug3')

sub=m.groupby('model').apply(lambda g: pd.Series({
    'ff_pass':g[g.task_id.isin(FREEFORM)].passed.sum(),
    'ss_pass':g[g.task_id.isin(STRUCT)].passed.sum(),
    'ff_mean':g[g.task_id.isin(FREEFORM)].score.mean(),
    'ss_mean':g[g.task_id.isin(STRUCT)].score.mean()}),include_groups=False).reset_index()
db=dbg.groupby('model',as_index=False).agg(dbg_pass=('passed','sum'),dbg_mean=('score','mean'))
L=lb.merge(sub,on='model').merge(db,on='model')
SZ={'small':'$<$50','large':'$\\geq$50','undisclosed':'n/d'}

# ---------------- Table 1: full leaderboard
rows=[]
for _,r in L.sort_values(['mean_score','passes'],ascending=False).iterrows():
    tb='n/d' if pd.isna(r['total_b']) else (f"{r['total_b']:.2f}" if r['total_b']<1 else f"{r['total_b']:.0f}")
    ab='' if pd.isna(r['active_b']) else (f"{r['active_b']:.2f}" if r['active_b']<1 else f"{r['active_b']:.1f}")
    act=f" ({ab})" if r['is_moe'] else ''
    rows.append(f"\\texttt{{{esc(r['display'])}}} & {'local' if r['route']=='local' else 'API'} & {r['weights']} & {tb}{act} & "
                f"{int(r['passes'])}/28 & {r['mean_score']:.3f} & [{r['ci_lo']:.2f}, {r['ci_hi']:.2f}] & "
                f"{int(r['ff_pass'])}/8 & {int(r['ss_pass'])}/20 & {int(r['dbg_pass'])}/3 \\\\")
t1=r"""\begin{table*}[!htbp]
\centering\footnotesize\setlength{\tabcolsep}{3.2pt}
\renewcommand{\arraystretch}{0.93}
\caption{All %d deployments with complete main and debugging runs, ordered by mean main-suite score.
``Weights'' reports whether a checkpoint is publicly downloadable; ``Params'' is the total count in
billions, with the active count in parentheses for sparse models and \emph{n/d} for undisclosed size.
The 95\%% interval is a Wilson interval on the strict pass fraction.}
\label{tab:leaderboard}
\begin{tabular}{@{}llllrrcrrr@{}}
\toprule
Model & Route & Weights & Params & Pass & Mean & 95\%% CI & Free & Struct. & Dbg \\
\midrule
%s
\bottomrule
\end{tabular}
\end{table*}
"""%(len(L),'\n'.join(rows))
open(ROOT/'tables'/'table_leaderboard.tex','w',encoding='utf-8').write(t1)

# ---------------- Table 2: matched pairs
pr=[]
for fid,sid,lab in PAIRS:
    f=m[m.task_id==fid]; s=m[m.task_id==sid]
    pr.append(f"{lab} & {f.score.mean():.3f} & {s.score.mean():.3f} & "
              f"${s.score.mean()-f.score.mean():+.3f}$ & {int(f.passed.sum())}/{len(f)} & {int(s.passed.sum())}/{len(s)} \\\\")
ff=m[m.task_id.isin([p[0] for p in PAIRS])]; ss=m[m.task_id.isin([p[1] for p in PAIRS])]
pr.append('\\midrule')
pr.append(f"\\textbf{{All five pairs}} & {ff.score.mean():.3f} & {ss.score.mean():.3f} & "
          f"$\\mathbf{{{ss.score.mean()-ff.score.mean():+.3f}}}$ & {int(ff.passed.sum())}/{len(ff)} & "
          f"\\textbf{{{int(ss.passed.sum())}/{len(ss)}}} \\\\")
t2=r"""\begin{table}[t]
\centering\small
\caption{The five matched interface pairs, aggregated over all %d deployments. Physics content and
pass-critical checks are identical within each pair; only the required output form changes.}
\label{tab:pairs}
\begin{tabular}{lrrrcc}
\toprule
& \multicolumn{3}{c}{Mean score} & \multicolumn{2}{c}{Strict passes} \\
\cmidrule(lr){2-4}\cmidrule(lr){5-6}
Task pair & Freeform & Structured & $\Delta$ & Freeform & Structured \\
\midrule
%s
\bottomrule
\end{tabular}
\end{table}
"""%(m.model.nunique(),'\n'.join(pr))
open(ROOT/'tables'/'table_pairs.tex','w',encoding='utf-8').write(t2)

# ---------------- Table 3: by size class
rws=[]
for c in ['small','large','undisclosed']:
    g=L[L.size_class==c]; mm=m[m.model.isin(g.model)]; dd=dbg[dbg.model.isin(g.model)]
    f=mm[mm.task_id.isin([p[0] for p in PAIRS])]; s=mm[mm.task_id.isin([p[1] for p in PAIRS])]
    lbl={'small':'Disclosed $<$50\\,B','large':'Disclosed $\\geq$50\\,B','undisclosed':'Size undisclosed'}[c]
    rws.append(f"{lbl} & {len(g)} & {f.score.mean():.3f} & {s.score.mean():.3f} & "
               f"${s.score.mean()-f.score.mean():+.3f}$ & {int(f.passed.sum())}/{len(f)} & "
               f"{int(s.passed.sum())}/{len(s)} & {int(dd.passed.sum())}/{len(dd)} \\\\")
t3=r"""\begin{table}[t]
\centering\small
\caption{Interface and debugging results by size class. The 50\,B threshold is a
presentational convention (Sec.~\ref{sec:cohort}); Fig.~\ref{fig:scale} shows the underlying
continuous relationship so that no conclusion depends on the cut.}
\label{tab:sizeclass}
\begin{tabular}{lrrrrccc}
\toprule
& & \multicolumn{3}{c}{Paired mean score} & \multicolumn{2}{c}{Paired passes} & Debug \\
\cmidrule(lr){3-5}\cmidrule(lr){6-7}\cmidrule(lr){8-8}
Class & $N$ & Free & Struct. & $\Delta$ & Free & Struct. & passes \\
\midrule
%s
\bottomrule
\end{tabular}
\end{table}
"""%('\n'.join(rws))
open(ROOT/'tables'/'table_sizeclass.tex','w',encoding='utf-8').write(t3)

# ---------------- Table 4: replicate stability (separate HTTP-clean study)
stab=pd.read_csv(ROOT/'data'/'HEPToolBench_stability_v1_2_1_10models_x5.csv',encoding='utf-8')
stab['passed']=stab['passed'].astype(str).str.lower().eq('true')
g=(stab[stab.task_partition=='main28']
   .groupby(['model','repeat'],as_index=False)
   .agg(n=('task_id','nunique'),passes=('passed','sum'),mean=('score','mean')))
rep=g[g.n==28]
rr=[]
for mdl,s in rep.groupby('model'):
    ps=sorted(s.passes.tolist())
    rr.append((DISPLAY.get(mdl,mdl),len(s),ps,np.mean(ps),np.std(s.passes,ddof=1),
               s['mean'].mean(),np.std(s['mean'],ddof=1)))
rr.sort(key=lambda x:-x[3])
lines=[f"{esc(a)} & {d_:.1f} & {min(c)}--{max(c)} & {e:.2f} & {f:.3f} & {gg:.4f} \\\\"
       for a,b,c,d_,e,f,gg in rr]
t4=r"""\begin{table}[t]
\centering\small
\caption{Run-to-run stability on the 28-task main suite. Ten locally served deployments were
evaluated five times under identical conditions. Pass-count and score standard deviations are
computed across the five per-run values.}
\label{tab:replicates}
\begin{tabular}{lccccc}
\toprule
Deployment & Mean passes & Range & Pass sd & Mean score & Score sd \\
\midrule
%s
\midrule
Mean & & & %.2f & & %.4f \\
\bottomrule
\end{tabular}
\end{table}
"""%('\n'.join(lines),np.mean([x[4] for x in rr]),np.mean([x[6] for x in rr]))
if not rr: raise RuntimeError('No complete five-repeat stability runs found')
open(ROOT/'tables'/'table_replicates.tex','w',encoding='utf-8').write(t4)

# ---------------- Table 5: debug per model, condensed by route
api=L[L.route=='api'].sort_values('dbg_mean',ascending=False)
loc=L[L.route=='local'].sort_values('dbg_mean',ascending=False)
def blk(df):
    return '\n'.join(f"\\texttt{{{esc(r['display'])}}} & {r['ss_mean']:.3f} & {int(r['ss_pass'])}/20 & "
                     f"{r['dbg_mean']:.3f} & {int(r['dbg_pass'])}/3 \\\\" for _,r in df.iterrows())
t5=r"""\begin{table}[p]
\centering\footnotesize
\renewcommand{\arraystretch}{0.90}
\caption{Mean score and strict passes for the twenty schema-described main tasks and the
three-task structured-debugging extension, grouped by serving route. The grouping is descriptive:
route is confounded with model identity, public weight availability, and size.}
\label{tab:debug}
\begin{tabular}{lrrrr}
\toprule
& \multicolumn{2}{c}{Structured generation} & \multicolumn{2}{c}{Structured debugging} \\
\cmidrule(lr){2-3}\cmidrule(lr){4-5}
Model & Mean & Passed & Mean & Passed \\
\midrule
\multicolumn{5}{l}{\emph{Served by API}}\\
%s
\midrule
\multicolumn{5}{l}{\emph{Served locally through Ollama}}\\
%s
\bottomrule
\end{tabular}
\end{table}
"""%(blk(api),blk(loc))
open(ROOT/'tables'/'table_debug.tex','w',encoding='utf-8').write(t5)
print('wrote 5 tables')
for f in ['table_leaderboard','table_pairs','table_sizeclass','table_replicates','table_debug']:
    print(' ',f,len(open(ROOT/'tables'/f'{f}.tex',encoding='utf-8').read()),'bytes')
