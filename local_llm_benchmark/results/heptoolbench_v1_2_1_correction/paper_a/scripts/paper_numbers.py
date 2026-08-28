"""Emit every number cited in the paper. Single source of truth."""
import pandas as pd, numpy as np, json
from build import (load, primary, leaderboard, PAIRS, DISPLAY, wilson,
                   TOTAL_B, ACTIVE_B, MOE, OPEN_WEIGHT, CLOSED_WEIGHT, HERE)
from scipy.stats import wilcoxon, spearmanr, mannwhitneyu, fisher_exact

FREEFORM = ['mg_basic_001','mg_basic_002','mg_basic_003','mg_debug_001','mg_debug_002',
            'mg_debug_003','mg_runcard_004','mg_workflow_005']
N = {}
d = load(); lb = leaderboard(d); m = primary(d)
STRUCT28 = sorted(set(m['task_id'].unique()) - set(FREEFORM))
assert len(FREEFORM)==8 and len(STRUCT28)==20

mm = m.merge(lb[['model','display','size_class','weights','route','total_b','active_b','is_moe']],on='model')
N['n_models']=len(lb); N['n_tasks_main']=28; N['n_tasks_debug']=3
N['n_obs_main']=len(mm)
N['n_checkpoints']=int(lb['model'].nunique()-1)  # Llama 3.3 70B appears under two routes
N['n_local']=int((lb.route=='local').sum()); N['n_api']=int((lb.route=='api').sum())
N['n_open']=int((lb.weights=='open').sum()); N['n_closed']=int((lb.weights=='closed').sum())
N['n_disclosed']=int(lb.total_b.notna().sum()); N['n_moe']=int(lb.is_moe.sum())
N['size_min_b']=float(lb.total_b.min()); N['size_max_b']=float(lb.total_b.max())
for c in ['small','large','undisclosed']:
    N[f'n_{c}']=int((lb.size_class==c).sum())

# ---- leaderboard extremes
top_pass = lb.sort_values(['passes','mean_score'],ascending=False).iloc[0]
top_mean = lb.sort_values('mean_score',ascending=False).iloc[0]
N['top_pass_model']=top_pass['display']; N['top_pass_n']=int(top_pass['passes'])
N['top_pass_mean']=round(top_pass['mean_score'],3)
N['top_mean_model']=top_mean['display']; N['top_mean_val']=round(top_mean['mean_score'],3)
N['top_mean_passes']=int(top_mean['passes'])
bo = lb[lb.weights=='open'].sort_values(['passes','mean_score'],ascending=False).iloc[0]
bc = lb[lb.weights=='closed'].sort_values(['passes','mean_score'],ascending=False).iloc[0]
N['best_open']=bo['display']; N['best_open_pass']=int(bo['passes']); N['best_open_mean']=round(bo['mean_score'],3)
N['best_closed']=bc['display']; N['best_closed_pass']=int(bc['passes']); N['best_closed_mean']=round(bc['mean_score'],3)
N['best_open_ci']=[round(bo['ci_lo'],3),round(bo['ci_hi'],3)]
N['best_closed_ci']=[round(bc['ci_lo'],3),round(bc['ci_hi'],3)]

# ---- freeform vs structured across the whole 28
ff = mm[mm.task_id.isin(FREEFORM)]; ss = mm[mm.task_id.isin(STRUCT28)]
N['ff_mean']=round(ff.score.mean(),3); N['ff_pass']=int(ff.passed.sum()); N['ff_n']=len(ff)
N['ss_mean']=round(ss.score.mean(),3); N['ss_pass']=int(ss.passed.sum()); N['ss_n']=len(ss)
N['ff_pass_rate']=round(ff.passed.mean(),3); N['ss_pass_rate']=round(ss.passed.mean(),3)
for c in ['small','large','undisclosed']:
    a=ff[ff.size_class==c]; b=ss[ss.size_class==c]
    N[f'ff_{c}_pass']=f'{int(a.passed.sum())}/{len(a)}'
    N[f'ss_{c}_pass']=f'{int(b.passed.sum())}/{len(b)}'
    N[f'ff_{c}_mean']=round(a.score.mean(),3); N[f'ss_{c}_mean']=round(b.score.mean(),3)
# how many models pass zero freeform tasks
per=ff.groupby(['model','size_class'],as_index=False).passed.sum()
N['models_zero_freeform']=int((per.passed==0).sum())
N['models_zero_freeform_small']=int(((per.passed==0)&(per.size_class=='small')).sum())
N['models_any_freeform']=int((per.passed>0).sum())
best_ff=per.sort_values('passed',ascending=False).iloc[0]
N['best_freeform_model']=DISPLAY.get(best_ff['model'],best_ff['model']); N['best_freeform_n']=int(best_ff['passed'])

# ---- matched pairs
rows=[]
for mdl,g in m.groupby('model'):
    f=g[g.task_id.isin([p[0] for p in PAIRS])]; s=g[g.task_id.isin([p[1] for p in PAIRS])]
    if len(f)!=5 or len(s)!=5: continue
    rows.append(dict(model=mdl,free=f.score.mean(),struct=s.score.mean(),
        free_pass=int(f.passed.sum()),struct_pass=int(s.passed.sum())))
P=pd.DataFrame(rows).merge(lb[['model','display','size_class','weights','route','total_b','active_b','is_moe']],on='model')
P['gain']=P.struct-P.free
P['norm_gain']=P.gain/(1-P.free).replace(0,np.nan)
P['fmt_fail']=P.struct.eq(0.0)
P=P.sort_values('free').reset_index(drop=True)
P.to_csv(HERE/'pairs.csv',index=False,encoding='utf-8')
n=len(P)
N['pair_n_models']=n
N['pair_free_mean']=round(P.free.mean(),3); N['pair_struct_mean']=round(P.struct.mean(),3)
N['pair_gain']=round(P.gain.mean(),3)
N['pair_free_pass']=f'{int(P.free_pass.sum())}/{5*n}'; N['pair_struct_pass']=f'{int(P.struct_pass.sum())}/{5*n}'
w=wilcoxon(P.struct,P.free,alternative='greater'); N['pair_wilcoxon_p']=float(w.pvalue); N['pair_wilcoxon_W']=float(w.statistic)
N['pair_n_improved']=int((P.gain>0).sum()); N['pair_n_worse']=int((P.gain<0).sum())
ok=P[~P.fmt_fail]
N['headroom_pct']=round(100*ok.norm_gain.mean(),1)
N['headroom_all_pct']=round(100*P.norm_gain.mean(),1)
N['fmt_fail_models']=list(P[P.fmt_fail].display)
N['n_fmt_fail']=len(N['fmt_fail_models'])
sp1=spearmanr(ok.gain,ok.free); sp2=spearmanr(ok.norm_gain,ok.free)
N['spear_abs_rho']=round(float(sp1.statistic),3); N['spear_abs_p']=float(sp1.pvalue)
N['spear_norm_rho']=round(float(sp2.statistic),3); N['spear_norm_p']=float(sp2.pvalue)
for c in ['small','large','undisclosed']:
    s=P[P.size_class==c]
    N[f'pair_{c}_free']=round(s.free.mean(),3); N[f'pair_{c}_struct']=round(s.struct.mean(),3)
    N[f'pair_{c}_gain']=round(s.gain.mean(),3)
    N[f'pair_{c}_free_pass']=f'{int(s.free_pass.sum())}/{5*len(s)}'
    N[f'pair_{c}_struct_pass']=f'{int(s.struct_pass.sum())}/{5*len(s)}'
    N[f'pair_{c}_n']=len(s)
# floor: models under 4B
flo=P[P.total_b<=4.0]
N['floor_models']=list(flo.display); N['floor_gain']=round(flo.gain.mean(),3)
mid=P[(P.total_b>=8)&(P.total_b<=35)&(~P.fmt_fail)]
N['mid_n']=len(mid); N['mid_free']=round(mid.free.mean(),3); N['mid_struct']=round(mid.struct.mean(),3)
N['mid_gain']=round(mid.gain.mean(),3)
N['mid_struct_pass']=f'{int(mid.struct_pass.sum())}/{5*len(mid)}'
N['mid_free_pass']=f'{int(mid.free_pass.sum())}/{5*len(mid)}'
perfect=P[(P.struct_pass==5)&(P.free_pass==0)]
N['n_zero_to_five']=len(perfect); N['zero_to_five_examples']=list(perfect.nlargest(4,'gain')['display'])

# ---- per pair
pair_rows=[]
for fid,sid,lab in PAIRS:
    f=mm[mm.task_id==fid]; s=mm[mm.task_id==sid]
    pair_rows.append(dict(pair=lab,free_mean=round(f.score.mean(),3),struct_mean=round(s.score.mean(),3),
        free_pass=int(f.passed.sum()),struct_pass=int(s.passed.sum()),n=len(f)))
N['pairs_table']=pair_rows

# ---- scale (one point per deployment with a disclosed total size)
known=lb.dropna(subset=['total_b'])
sp_scale=spearmanr(known.total_b,known.mean_score)
N['scale_n']=len(known)
N['scale_rho']=round(float(sp_scale.statistic),3)
N['scale_p']=float(sp_scale.pvalue)

# ---- debug extension
dbg=primary(d,'structured_debug3').merge(lb[['model','display','size_class','weights','route','total_b']],on='model')
N['dbg_n_models']=dbg.model.nunique()
N['dbg_api_mean']=round(dbg[dbg.route=='api'].score.mean(),3)
N['dbg_local_mean']=round(dbg[dbg.route=='local'].score.mean(),3)
N['dbg_api_pass']=f"{int(dbg[dbg.route=='api'].passed.sum())}/{len(dbg[dbg.route=='api'])}"
N['dbg_local_pass']=f"{int(dbg[dbg.route=='local'].passed.sum())}/{len(dbg[dbg.route=='local'])}"
N['dbg_api_zeros']=int((dbg[dbg.route=='api'].score==0).sum())
N['dbg_local_zeros']=int((dbg[dbg.route=='local'].score==0).sum())
N['dbg_api_min']=round(dbg[dbg.route=='api'].score.min(),3)
# Route comparison uses one mean per deployment; the three task cases from one
# deployment are not independent observations.
dbg_model=dbg.groupby(['model','display','route'],as_index=False).agg(
    dbg_mean=('score','mean'),dbg_pass=('passed','sum'))
mw=mannwhitneyu(dbg_model[dbg_model.route=='api'].dbg_mean,
                dbg_model[dbg_model.route=='local'].dbg_mean,
                alternative='two-sided')
N['dbg_mw_deployment_p']=float(mw.pvalue)
# Compare debugging with all twenty schema-described main tasks, not only the
# five structured members of the matched pairs.
gen_model=(mm[mm.task_id.isin(STRUCT28)].groupby('model',as_index=False)
           .agg(struct_mean=('score','mean'),struct_pass=('passed','sum')))
dbg_corr=dbg_model.merge(gen_model,on='model')
sp_dbg=spearmanr(dbg_corr.struct_mean,dbg_corr.dbg_mean)
N['dbg_struct_rho']=round(float(sp_dbg.statistic),3)
N['dbg_struct_p']=float(sp_dbg.pvalue)
z=dbg[dbg.route=='local'].groupby('display').score.max()
N['dbg_local_all_zero']=int((z==0).sum()); N['dbg_local_n']=len(z)
ow=dbg[(dbg.weights=='open')&(dbg.route=='api')]
N['dbg_open_api_models']=sorted(ow.display.unique())
N['dbg_open_api_mean']=round(ow.score.mean(),3)
l1=dbg[dbg.model=='llama3.3:70b'].score.tolist()
l2=dbg[dbg.model=='Llama-3.3-70B-Instruct (GitHub Models)'].score.tolist()
N['dbg_llama_local']=[round(x,2) for x in l1]; N['dbg_llama_api']=[round(x,2) for x in l2]
for c in ['small','large','undisclosed']:
    s=dbg[dbg.size_class==c]
    N[f'dbg_{c}_pass']=f'{int(s.passed.sum())}/{len(s)}'; N[f'dbg_{c}_mean']=round(s.score.mean(),3)

# ---- replicate stability (separate HTTP-clean five-repeat study)
stab=pd.read_csv(HERE.parent/'data'/'HEPToolBench_stability_v1_2_1_10models_x5.csv',encoding='utf-8')
stab['passed']=stab['passed'].astype(str).str.lower().eq('true')
g=(stab[stab.task_partition=='main28']
   .groupby(['model','repeat'],as_index=False)
   .agg(n=('task_id','nunique'),passes=('passed','sum'),mean=('score','mean')))
rep=g[g.n==28]
reps=[]
for mdl,s in rep.groupby('model'):
    reps.append(dict(model=DISPLAY.get(mdl,mdl),runs=len(s),passes=sorted(s.passes.tolist()),
        pass_sd=round(float(np.std(s.passes,ddof=1)),2),
        score_mean=round(float(s['mean'].mean()),3),
        score_sd=round(float(np.std(s['mean'],ddof=1)),4)))
N['replicates']=reps
N['rep_n_models']=len(reps)
if reps:
    N['rep_mean_pass_sd']=round(float(np.mean([r['pass_sd'] for r in reps])),2)
    N['rep_mean_score_sd']=round(float(np.mean([r['score_sd'] for r in reps])),4)
    N['rep_max_spread']=int(max(max(r['passes'])-min(r['passes']) for r in reps))
else:
    raise RuntimeError('No complete five-repeat stability runs found')

# ---- pass-bar tightness diagnostic
tight=[]
for t,gg in mm.groupby('task_id'):
    pa=gg[gg.passed].score
    if len(pa): tight.append((t,round(pa.min(),3),round(gg.score.mean(),3),int(gg.passed.sum()),len(gg)))
T=pd.DataFrame(tight,columns=['task','min_pass_score','mean','passes','n']).sort_values('min_pass_score',ascending=False)
N['tight_tasks']=T[T.min_pass_score>=0.95].task.tolist()
N['n_tight']=len(N['tight_tasks'])
N['max_failing_score']=round(float(mm.loc[~mm.passed,'score'].max()),3)
N['min_passing_score']=round(float(mm.loc[mm.passed,'score'].min()),3)
mark=mm[mm.task_id.isin(STRUCT28)].failure_modes.fillna('').str.contains(
    'includes_markdown_fence',regex=False)
N['structured_markdown_fence_n']=int(mark.sum())
N['structured_markdown_fence_pass']=int(
    mm[mm.task_id.isin(STRUCT28)].loc[mark,'passed'].sum())
# tasks where api pass rate < local pass rate
inv=[]
for t,gg in mm.groupby('task_id'):
    a=gg[gg.route=='api']; l=gg[gg.route=='local']
    if len(a) and len(l) and a.passed.mean()<l.passed.mean()-0.15:
        inv.append(dict(task=t,api=round(a.passed.mean(),3),local=round(l.passed.mean(),3),
                        api_mean=round(a.score.mean(),3),local_mean=round(l.score.mean(),3)))
N['inverted_tasks']=inv; N['n_inverted']=len(inv)

with open(HERE/'numbers.json','w',encoding='utf-8') as f: json.dump(N,f,indent=1,default=str,ensure_ascii=False)
for k,v in N.items():
    if isinstance(v,(list,dict)) and len(str(v))>150: print(f'{k}: <{type(v).__name__} len {len(v)}>')
    else: print(f'{k}: {v}')
