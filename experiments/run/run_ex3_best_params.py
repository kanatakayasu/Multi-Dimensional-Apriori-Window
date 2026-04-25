"""
EX-2 best-parameter tracking run.
Same experiment as run_ex3_rate025.py but records argmax parameters per shape.
"""
import numpy as np
import json, os
from itertools import combinations
from collections import defaultdict

T, S     = 100, 100
N_ITEMS  = 40
P_ITEM   = 0.15
W_T, W_S = 20, 5
THETA    = 30
N_PAT    = 20
N_SEEDS  = 3
SEED     = 42
RATE     = 0.25

GT_PATTERNS = [frozenset([2*k-1, 2*k]) for k in range(1, N_PAT+1)]
BAND_START  = [5*(k-1) for k in range(1, N_PAT+1)]
ALL_ITEMS   = set(range(1, N_ITEMS+1))

TAU_GRID    = np.arange(0.05, 0.50, 0.02)
WT_GRID     = [4, 13, 26, 54]
MZ_K        = [1, 2, 3, 5]
STDB_PARAMS = [(e1,e2,mp) for e1 in [1,2,3]
                           for e2 in [3,7,15]
                           for mp in [2,5]]

def gen_background(rng):
    txns = {}
    for t in range(T):
        for s in range(S):
            items = frozenset(i for i in range(1, N_ITEMS+1) if rng.random() < P_ITEM)
            txns[(t, s)] = items if items else frozenset([1])
    return txns

def embed_one_pattern(txns, pattern, bs, rng, shape):
    be = bs + 4
    if shape == "A":
        cells = [(t, s) for t in range(30, 71) for s in range(bs, be+1)]
    elif shape == "B":
        cells = []
        for t in range(30, 71):
            sc = bs + round((t - 30) / 40 * 2)
            for s in range(max(0, sc - 2), min(S, sc + 3)):
                cells.append((t, s))
    elif shape == "C":
        cells = [(t, s)
                 for t in list(range(15, 36)) + list(range(65, 86))
                 for s in range(bs, be+1)]
    elif shape == "D":
        center = bs + 2
        cells  = ([(t, center)           for t in range(30, 41)] +
                  [(t, s) for t in range(41, 56) for s in range(bs+1, be)] +
                  [(t, s) for t in range(56, 71) for s in range(bs, be+1)])
    for cell in cells:
        if rng.random() < RATE:
            txns[cell] = pattern

def proposed_method(occurrences):
    dense = set()
    for s_sp in range(S):
        L = sorted(t for (t, x) in occurrences if s_sp <= x <= s_sp + W_S)
        if len(L) < THETA: continue
        lo = hi = 0
        for l in range(T):
            while lo < len(L) and L[lo] < l:        lo += 1
            while hi < len(L) and L[hi] <= l + W_T: hi += 1
            if hi - lo >= THETA:
                for tt in range(l, min(l+W_T+1, T)):
                    for xx in range(s_sp, min(s_sp+W_S+1, S)):
                        dense.add((tt, xx))
    return dense

def jaccard(A, B):
    if not A and not B: return 1.0
    u = len(A | B); return len(A & B) / u if u else 0.0

def pattern_f1(pred, gt):
    pred = set(pred); gt = set(gt)
    if not gt: return float('nan')
    tp = len(pred & gt)
    if tp == 0: return 0.0
    p = tp / len(pred) if pred else 0.0
    r = tp / len(gt)
    return 2*p*r/(p+r) if (p+r) > 0 else 0.0

def colocation_pi(txns):
    occ = defaultdict(set)
    for (t, s), itemset in txns.items():
        for item in itemset:
            if item in ALL_ITEMS: occ[item].add((t, s))
    pi = {}
    for i, j in combinations(sorted(ALL_ITEMS), 2):
        co = len(occ[i] & occ[j])
        if occ[i] and occ[j]:
            pi[frozenset([i,j])] = co / max(len(occ[i]), len(occ[j]))
    return pi

def stcp_max_pi(txns, W_t):
    occ_t = defaultdict(lambda: defaultdict(set))
    for (t, s), itemset in txns.items():
        for item in itemset:
            if item in ALL_ITEMS: occ_t[item][t].add(s)
    max_pi = {}
    for i, j in combinations(sorted(ALL_ITEMS), 2):
        best = 0.0
        for l in range(T - W_t + 1):
            occ_i = set(); occ_j = set()
            for t in range(l, l + W_t):
                occ_i |= {(t, ss) for ss in occ_t[i][t]}
                occ_j |= {(t, ss) for ss in occ_t[j][t]}
            co = len(occ_i & occ_j)
            if occ_i and occ_j:
                pi_w = co / max(len(occ_i), len(occ_j))
                best = max(best, pi_w)
        max_pi[frozenset([i,j])] = best
    return max_pi

def lisa_method(occurrences):
    count_x = np.zeros(S)
    for (t, x) in occurrences: count_x[x] += 1
    z = count_x - count_x.mean(); s2 = np.var(z)
    if s2 == 0: return set()
    local_I = np.zeros(S)
    for x in range(S):
        nb = [i for i in [x-1, x+1] if 0 <= i < S]
        if nb: local_I[x] = z[x] * (sum(z[i] for i in nb)/len(nb)) / s2
    hh = [x for x in range(S) if z[x] > 0 and local_I[x] > 0]
    return {(t, x) for x in hh for t in range(T)}

def mzoom_k(occurrences, k=1):
    def cdns(P, t0,t1,x0,x1):
        v=(t1-t0+1)*(x1-x0+1)
        return (P[t1+1,x1+1]-P[t0,x1+1]-P[t1+1,x0]+P[t0,x0])/v if v>0 else 0.0
    grid=np.zeros((T,S))
    for (t,x) in occurrences:
        if 0<=t<T and 0<=x<S: grid[t,x]=1
    all_cells=set()
    for _ in range(k):
        P=np.zeros((T+1,S+1)); P[1:,1:]=grid.cumsum(0).cumsum(1)
        t0,t1,x0,x1=0,T-1,0,S-1
        for __ in range(2000):
            bd=cdns(P,t0,t1,x0,x1); bb=(t0,t1,x0,x1)
            for a,b,c,d in[(t0+1,t1,x0,x1),(t0,t1-1,x0,x1),(t0,t1,x0+1,x1),(t0,t1,x0,x1-1)]:
                if a>b or c>d: continue
                dd=cdns(P,a,b,c,d)
                if dd>bd: bd=dd; bb=(a,b,c,d)
            if bb==(t0,t1,x0,x1): break
            t0,t1,x0,x1=bb
        nc={(tt,xx) for tt in range(t0,t1+1) for xx in range(x0,x1+1)}
        all_cells|=nc
        for (tt,xx) in nc:
            if 0<=tt<T and 0<=xx<S: grid[tt,xx]=0
    return all_cells

def stdbscan(pts_arr, eps1, eps2, min_pts):
    n=len(pts_arr)
    if n==0: return set()
    dt=np.abs(pts_arr[:,0:1]-pts_arr[:,0]); dx=np.abs(pts_arr[:,1:2]-pts_arr[:,1])
    adj=(dt<=eps2)&(dx<=eps1); np.fill_diagonal(adj,False)
    nbrs=[np.where(adj[i])[0].tolist() for i in range(n)]
    vis=[False]*n; cl=[-1]*n; cid=0
    for i in range(n):
        if vis[i]: continue
        vis[i]=True; nb=nbrs[i]
        if len(nb)<min_pts: continue
        cl[i]=cid; q=list(nb); seen=set(nb)
        while q:
            j=q.pop(0)
            if not vis[j]:
                vis[j]=True; nb_j=nbrs[j]
                if len(nb_j)>=min_pts:
                    for kk in nb_j:
                        if kk not in seen: seen.add(kk); q.append(kk)
            if cl[j]==-1: cl[j]=cid
        cid+=1
    return {(int(pts_arr[i,0]),int(pts_arr[i,1])) for i,c in enumerate(cl) if c>=0}

# ---------------------------------------------------------------
all_best_params = []

for shape in ["A", "B", "C", "D"]:
    col_taus = []; stcp_params_list = []
    mz_ks = []; stdb_params_list = []
    print(f"\nShape={shape}", flush=True)

    for seed_offset in range(N_SEEDS):
        seed = SEED + seed_offset * 13
        rng  = np.random.default_rng(seed)
        txns = gen_background(rng)
        rng_e = np.random.default_rng(seed + 500)
        for pat, bs in zip(GT_PATTERNS, BAND_START):
            embed_one_pattern(txns, pat, bs, rng_e, shape)

        # GT
        prop_dense = {}
        prop_found = []
        for pat, bs in zip(GT_PATTERNS, BAND_START):
            occ = [(t,s) for (t,s),items in txns.items() if pat.issubset(items)]
            d = proposed_method(occ)
            prop_dense[pat] = d
            if d: prop_found.append(pat)
        gt_pats = prop_found
        if not gt_pats:
            print(f"  seed={seed} no GT, skip")
            continue

        # --- Colocation best tau ---
        pi_global = colocation_pi(txns)
        best_f1, best_tau = -1, None
        for tau in TAU_GRID:
            f = pattern_f1({p for p,v in pi_global.items() if v>=tau}, gt_pats)
            if f > best_f1: best_f1 = f; best_tau = round(float(tau), 3)
        col_taus.append(best_tau)

        # --- STCP best (tau, wt) ---
        best_f1, best_p = -1, None
        for wt in WT_GRID:
            pi_wt = stcp_max_pi(txns, wt)
            for tau in TAU_GRID:
                f = pattern_f1({p for p,v in pi_wt.items() if v>=tau}, gt_pats)
                if f > best_f1: best_f1 = f; best_p = (round(float(tau),3), wt)
        stcp_params_list.append(best_p)
        print(f"  seed={seed} Col_tau={best_tau} STCP={best_p}", flush=True)

        # --- MZoom & ST-DBSCAN: best per-pattern then mode ---
        mz_k_votes = []; stdb_votes = []
        for pat in gt_pats:
            occ = [(t,s) for (t,s),items in txns.items() if pat.issubset(items)]
            GT_d = prop_dense[pat]
            pts = np.array(occ, dtype=int) if occ else np.empty((0,2),dtype=int)

            best_j, best_k = -1, None
            for k in MZ_K:
                j = jaccard(GT_d, mzoom_k(occ, k=k))
                if j > best_j: best_j = j; best_k = k
            mz_k_votes.append(best_k)

            best_j, best_sp = -1, None
            for e1,e2,mp in STDB_PARAMS:
                j = jaccard(GT_d, stdbscan(pts,e1,e2,mp))
                if j > best_j: best_j = j; best_sp = (e1,e2,mp)
            stdb_votes.append(best_sp)

        from collections import Counter
        mz_ks.append(Counter(mz_k_votes).most_common(1)[0][0])
        stdb_params_list.append(Counter(map(str,stdb_votes)).most_common(1)[0][0])

    from collections import Counter
    def mode(lst): return Counter(str(x) for x in lst).most_common(1)[0][0] if lst else "N/A"

    all_best_params.append({
        "shape": shape,
        "col_tau":   mode(col_taus),
        "stcp":      mode(stcp_params_list),
        "mzoom_k":   mode(mz_ks),
        "stdbscan":  mode(stdb_params_list),
    })

print("\n===== Best Parameters =====")
for r in all_best_params:
    print(r)

os.makedirs("experiments/results/ex3", exist_ok=True)
with open("experiments/results/ex3/ex3_best_params.json", "w") as f:
    json.dump(all_best_params, f, indent=2)
print("Saved: experiments/results/ex3/ex3_best_params.json")
