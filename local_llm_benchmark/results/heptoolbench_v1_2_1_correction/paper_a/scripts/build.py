import pandas as pd, numpy as np, re
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

RUN_PRIORITY = ['api_cloud_consolidated','local_r01',
 'HEPToolBench_phi4_mini_3_8b_full31_r01','HEPToolBench_phi4_14b_full31_r01',
 'HEPToolBench_llama3_1_8b_full31_r01','HEPToolBench_falcon3_10b_full31_r01',
 'HEPToolBench_gemma_small_full31_20260715_r01','HEPToolBench_gemma3_270m_full31_r01',
 'HEPToolBench_local_selection_20260710','local_r02','local_r03']
RUN_RANK={r:i for i,r in enumerate(RUN_PRIORITY)}

# ---------------------------------------------------------------------------
# Schema handling for the HTTP-clean rerun.
#
# The local results were regenerated through a new serving path (Ollama HTTP
# /api/generate, stream=false) after a provenance audit found the earlier local
# consolidation contained cross-model duplicate artifacts and terminal-control
# contamination. Two consequences for this module:
#
#   1. Local structured-debug rows now carry a new partition name, while the
#      API rows kept the original one. They are the same measurement, so both
#      names resolve to the same logical partition.
#   2. The new files distinguish infrastructure failures (CUDA OOM, model-load
#      timeout, HTTP 500, truncation, missing result, runner exception) from
#      genuine model errors. Those rows carry valid_for_scoring=False and an
#      empty score, and must be EXCLUDED, never counted as a zero.
#
# Legacy files lack these columns and are handled unchanged.
# ---------------------------------------------------------------------------
DATA_FILE        = 'HEPToolBench_v1_2_1_S1R_42deployments_31tasks.csv'
MAIN_PARTITION   = 'main28'
DEBUG_PARTITIONS = ('structured_debug3', 'structured_debug_extension')
PARTITION_ALIASES = {
    'main28': ('main28',),
    'structured_debug3': DEBUG_PARTITIONS,
    'structured_debug_extension': DEBUG_PARTITIONS,
}
# Runs from the HTTP-clean pipeline outrank every legacy run, so that if a
# legacy and a clean record ever meet, the clean one wins the deduplication.
HTTPCLEAN_PREFIX = 'httpclean'

def run_rank(run_id):
    if run_id in RUN_RANK: return RUN_RANK[run_id]
    if isinstance(run_id, str) and run_id.startswith(HTTPCLEAN_PREFIX): return 0
    return 999

def has_audit_flags(d):
    """True for HTTP-clean files, which carry the infrastructure-audit columns."""
    return 'valid_for_scoring' in d.columns

# TOTAL parameter count (dense size or full MoE size). None = undisclosed.
TOTAL_B = {
 'gemma3:270m':0.27,'gemma4:e2b':2.0,'phi4-mini:3.8b':3.8,'gemma3:4b':4.0,'gemma4:e4b':4.0,
 'llama3:8b':8.0,'llama3.1:8b':8.0,'qwen3:8b':8.0,'qwen2.5-coder:7b':7.0,'falcon3:10b':10.0,
 'gemma3:12b':12.0,'gemma4:12b':12.0,'ministral-3:14b':14.0,'phi4:14b':14.0,
 'qwen2.5-coder:14b':14.0,'qwen3:14b':14.0,'phi4-reasoning:plus':14.0,
 'gpt-oss:20b':20.0,'devstral:24b':24.0,'mistral-small3.2:24b':24.0,
 'gemma4:26b':26.0,'qwen3.5:27b':27.0,'gemma4:31b':31.0,'granite4:32b-a9b-h':32.0,
 'qwen3.5:35b':35.0,'deepseek-r1:70b':70.0,'llama3.3:70b':70.0,
 'Llama-3.3-70B-Instruct (GitHub Models)':70.0,'qwen3-next:80b':80.0,
 'Sarvam-105B':105.0,'gpt-oss:120b':120.0,'qwen3-coder-next:Q4_K_M':80.0,
 'Codestral':None,'Devstral 2512':123.0,'Mistral Large 2512':675.0,'Mistral Medium 2508':None,
 'Magistral Medium 2509':None,'GPT-4.1':None,'GPT-4.1 mini':None,'GPT-4.1 nano':None,
 'Gemini 3.1 Flash-Lite':None,'Gemini 3.5 Flash':None,
}
# ACTIVE parameters for sparse/MoE models.
ACTIVE_B = {'granite4:32b-a9b-h':9.0,'gpt-oss:120b':5.1,'gpt-oss:20b':3.6,
 'qwen3-next:80b':3.0,'qwen3-coder-next:Q4_K_M':3.0,
 'Mistral Large 2512':41.0,'Sarvam-105B':10.3}
MOE = set(ACTIVE_B)

OPEN_WEIGHT = {
 'gemma3:270m','gemma3:4b','gemma3:12b','gemma4:e2b','gemma4:e4b','gemma4:12b','gemma4:26b','gemma4:31b',
 'llama3:8b','llama3.1:8b','llama3.3:70b','Llama-3.3-70B-Instruct (GitHub Models)',
 'qwen3:8b','qwen3:14b','qwen3.5:27b','qwen3.5:35b','qwen2.5-coder:7b','qwen2.5-coder:14b','qwen3-coder-next:Q4_K_M','qwen3-next:80b',
 'deepseek-r1:70b','phi4:14b','phi4-mini:3.8b','phi4-reasoning:plus','granite4:32b-a9b-h',
 'gpt-oss:120b','gpt-oss:20b','falcon3:10b','mistral-small3.2:24b','devstral:24b','ministral-3:14b',
 'Mistral Large 2512','Devstral 2512','Sarvam-105B',
}
CLOSED_WEIGHT = {
 'GPT-4.1','GPT-4.1 mini','GPT-4.1 nano','Gemini 3.1 Flash-Lite','Gemini 3.5 Flash',
 'Mistral Medium 2508','Magistral Medium 2509','Codestral',
}

DISPLAY = {
 'Codestral':'Codestral 2508','Llama-3.3-70B-Instruct (GitHub Models)':'Llama 3.3 70B (API)',
 'Sarvam-105B':'Sarvam 105B','deepseek-r1:70b':'DeepSeek-R1 70B','devstral:24b':'Devstral 24B',
 'falcon3:10b':'Falcon 3 10B','gemma3:12b':'Gemma 3 12B','gemma3:270m':'Gemma 3 270M','gemma3:4b':'Gemma 3 4B',
 'gemma4:12b':'Gemma 4 12B','gemma4:26b':'Gemma 4 26B','gemma4:31b':'Gemma 4 31B','gemma4:e2b':'Gemma 4 E2B',
 'gemma4:e4b':'Gemma 4 E4B','gpt-oss:120b':'gpt-oss 120B','gpt-oss:20b':'gpt-oss 20B',
 'granite4:32b-a9b-h':'Granite 4 32B-A9B','llama3.1:8b':'Llama 3.1 8B','llama3.3:70b':'Llama 3.3 70B (local)',
 'llama3:8b':'Llama 3 8B','ministral-3:14b':'Ministral 3 14B','mistral-small3.2:24b':'Mistral Small 3.2 24B',
 'phi4-mini:3.8b':'Phi-4 mini 3.8B','phi4-reasoning:plus':'Phi-4 Reasoning Plus','phi4:14b':'Phi-4 14B',
 'qwen2.5-coder:7b':'Qwen2.5-Coder 7B','qwen2.5-coder:14b':'Qwen2.5-Coder 14B','qwen3-coder-next:Q4_K_M':'Qwen3-Coder-Next',
 'qwen3-next:80b':'Qwen3-Next 80B-A3B','qwen3.5:27b':'Qwen3.5 27B','qwen3.5:35b':'Qwen3.5 35B',
 'qwen3:14b':'Qwen3 14B','qwen3:8b':'Qwen3 8B',
}

PAIRS=[('mg_basic_001','mg_structured_001','Drell--Yan process'),
 ('mg_basic_002','mg_structured_002','Top-pair process'),
 ('mg_basic_003','mg_structured_003','Higgs+jet process'),
 ('mg_runcard_004','mg_runcard_structured_004','Run-card cuts'),
 ('mg_workflow_005','mg_workflow_structured_005','MG5+P8+Delphes workflow')]

def wilson(k,n,z=1.96):
    if n==0: return (np.nan,np.nan)
    p=k/n; den=1+z*z/n
    c=(p+z*z/(2*n))/den
    h=z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return max(0,c-h),min(1,c+h)

def _fill_metadata(d):
    """Repair sparse metadata in the combined file so a newly added model whose
    task_partition / deployment_type cells were left blank is not silently
    dropped. The task_id->partition map comes from the file's OWN populated rows,
    so no partition is invented; deployment_type is filled from deployment_group.
    """
    if 'task_partition' in d.columns and d['task_partition'].isna().any():
        known=(d.dropna(subset=['task_partition'])
                 .drop_duplicates('task_id').set_index('task_id')['task_partition'])
        d['task_partition']=d['task_partition'].fillna(d['task_id'].map(known))
    if 'deployment_type' in d.columns and 'deployment_group' in d.columns:
        grp={'local':'local_ollama','api':'api_cloud'}
        d['deployment_type']=d['deployment_type'].fillna(d['deployment_group'].map(grp))
    return d

def load(path=None, drop_invalid=True, report=False):
    """Load a result CSV.

    On HTTP-clean files, rows flagged not-valid-for-scoring are infrastructure
    failures, not model failures; they are dropped so they cannot be averaged in
    as zeros. Pass drop_invalid=False to inspect them. valid_for_scoring_final is
    the authoritative flag when present (it post-dates the infrastructure repairs).
    """
    if path is None: path = ROOT / 'data' / DATA_FILE
    d=pd.read_csv(path,encoding='utf-8')
    # Drop any raw columns whose names collide with quantities the leaderboard
    # computes (e.g. the final file ships a transport-level 'route' column that
    # would clash with the local/api route derived here and vanish in merges).
    d=d.drop(columns=[c for c in ('route','display','size_class','weights',
             'pass_fraction','ci_lo','ci_hi') if c in d.columns], errors='ignore')
    d=_fill_metadata(d)
    if has_audit_flags(d):
        # A row is scorable if the base flag says so OR the repair pass revalidated
        # it. valid_for_scoring_final==True is a repair override: it marks rows that
        # an earlier run deferred (truncation/OOM) but a re-run then completed, while
        # the base flag and infrastructure_status keep their stale pre-repair values.
        base=d['valid_for_scoring'].astype(str).str.lower().isin(('true','1'))
        override=(d['valid_for_scoring_final'].astype(str).str.lower().isin(('true','1'))
                  if 'valid_for_scoring_final' in d.columns else False)
        v=base | override
        d['valid_for_scoring']=v
        if drop_invalid:
            if report and (~v).any():
                st=d.loc[~v,'infrastructure_status'].value_counts().to_dict() if 'infrastructure_status' in d.columns else {}
                print(f"[build] excluded {int((~v).sum())} infrastructure-invalid rows (never repaired): {st}")
            d=d[v].copy()
    d['passed']=d['passed'].astype(str).str.lower().eq('true')
    d['score']=pd.to_numeric(d['score'],errors='coerce')
    d['run_rank']=d['run_id'].map(run_rank)
    return d

def primary(d, partition=MAIN_PARTITION):
    """One canonical row per model/task using run priority.

    Either debug partition name selects both, so callers written against the
    pre-rerun schema keep working on new and old files alike.
    """
    parts=PARTITION_ALIASES.get(partition,(partition,))
    m=d[d['task_partition'].isin(parts)].copy()
    by,asc=['model','task_id','run_rank'],[True,True,True]
    if 'completed_at' in m.columns:      # tie-break: latest repair run wins
        by.append('completed_at'); asc.append(False)
    m=m.sort_values(by,ascending=asc).drop_duplicates(['model','task_id'],keep='first')
    return m

def coverage(d, partition=MAIN_PARTITION, expected=None):
    """Per-model count of scorable tasks: use this to track rerun progress."""
    m=primary(d,partition)
    c=m.groupby('model',as_index=False).agg(valid_tasks=('task_id','nunique'),
                                            deployment=('deployment_type','first'))
    c['display']=c['model'].map(DISPLAY).fillna(c['model'])
    if expected is None: expected=int(c['valid_tasks'].max())
    c['complete']=c['valid_tasks']==expected
    return c.sort_values(['complete','valid_tasks']).reset_index(drop=True)

def leaderboard(d):
    m=primary(d)
    s=m.groupby('model',as_index=False).agg(tasks=('task_id','nunique'),passes=('passed','sum'),
        mean_score=('score','mean'),deployment=('deployment_type','first'),
        provider=('provider_or_runtime','first'))
    s=s[s['tasks']==28].copy()
    s['display']=s['model'].map(DISPLAY).fillna(s['model'])
    s['total_b']=s['model'].map(TOTAL_B)
    s['active_b']=s['model'].map(lambda x: ACTIVE_B.get(x, TOTAL_B.get(x)))
    s['is_moe']=s['model'].isin(MOE)
    s['weights']=np.where(s['model'].isin(OPEN_WEIGHT),'open',
                  np.where(s['model'].isin(CLOSED_WEIGHT),'closed','UNKNOWN'))
    s['route']=np.where(s['deployment']=='local_ollama','local','api')
    s['pass_fraction']=s['passes']/s['tasks']
    ci=s.apply(lambda r: wilson(r['passes'],r['tasks']),axis=1)
    s['ci_lo']=[c[0] for c in ci]; s['ci_hi']=[c[1] for c in ci]
    def cls(r):
        b=r['total_b']
        if pd.isna(b) or b is None: return 'undisclosed'
        return 'small' if b<50 else 'large'
    s['size_class']=s.apply(cls,axis=1)
    return s.sort_values(['pass_fraction','mean_score'],ascending=False).reset_index(drop=True)

if __name__=='__main__':
    import sys
    src = sys.argv[1] if len(sys.argv)>1 else None
    d=load(src, report=True); lb=leaderboard(d)
    assert (lb['weights']!='UNKNOWN').all(), lb[lb['weights']=='UNKNOWN']['model'].tolist()
    cov=coverage(d, expected=28)
    missing=cov[~cov['complete']]
    if len(missing):
        print(f"[build] {len(missing)} model(s) INCOMPLETE on {MAIN_PARTITION} "
              f"and excluded from the leaderboard:")
        for _,r in missing.iterrows():
            print(f"        {r['display']:<28} {int(r['valid_tasks'])}/28 scorable tasks")
    print('models:',len(lb))
    print(lb[['display','weights','route','size_class','total_b','active_b','passes','pass_fraction','mean_score']].round(3).to_string(index=False))
    print()
    print('=== size_class x weights ==='); print(pd.crosstab(lb['size_class'],lb['weights']))
    print('=== size_class x route ==='); print(pd.crosstab(lb['size_class'],lb['route']))
    lb.to_csv(HERE/'leaderboard.csv',index=False,encoding='utf-8')
