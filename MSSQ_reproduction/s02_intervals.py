"""S-02整CSP配对区间。输入768条派生评分，输出两终点区间和留一CSP结果；种子27017，10000次，六层各抽四簇。"""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import random
SEED, REPS = (27017, 10000)
ENDPOINTS = {'paired_success': ('independent_pair_success', 'joint_task_success'), 'valid_construction': ('independent_construction_success', 'joint_construction_valid_without_judgment')}

def percentile(values, q):
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] * (1 - position + lower) + ordered[upper] * (position - lower)

def build(rows):
    raw = json.dumps(rows, sort_keys=True).encode('utf-8')
    assert len(rows) == len({(r['model'], r['prompt_id']) for r in rows}) == 768
    strata = defaultdict(set)
    for r in rows:
        strata[r['family'], r['stratum']].add((r['family'], r['csp_id']))
        assert all((type(r[f]) is bool for pair in ENDPOINTS.values() for f in pair))
    assert len(strata) == 6 and all((len(s) == 4 for s in strata.values()))
    clusters = sorted(set.union(*strata.values()))
    assert len(clusters) == 24
    models = sorted({r['model'] for r in rows})
    assert len(models) == 8
    groups = {m: [r for r in rows if r['model'] == m] for m in models}
    assert all((len(g) == 96 for g in groups.values()))
    groups['ALL pooled'] = rows
    counts = {}
    for model, group in groups.items():
        for endpoint, (i, j) in ENDPOINTS.items():
            counts[model, endpoint] = []
            for family, csp in clusters:
                subset = [r for r in group if (r['family'], r['csp_id']) == (family, csp)]
                assert len(subset) == (32 if model == 'ALL pooled' else 4)
                counts[model, endpoint].append((len(subset), sum((r[i] for r in subset)), sum((r[j] for r in subset))))
    samples = {key: [[], [], []] for key in counts}
    rng = random.Random(SEED)
    for _ in range(REPS):
        weight = Counter()
        for _, pool in sorted(strata.items()):
            pool = sorted(pool)
            for _ in range(4):
                weight[rng.choice(pool)] += 1
        weights = [weight[c] for c in clusters]
        assert sum(weights) == 24
        for key, values in counts.items():
            n, i, j = (sum((v[k] * w for v, w in zip(values, weights))) for k in range(3))
            samples[key][0].append(i / n)
            samples[key][1].append(j / n)
            samples[key][2].append(j / n - i / n)
    intervals, loco, totals = ([], [], {})
    for (model, endpoint), values in counts.items():
        n, i, j = (sum((v[k] for v in values)) for k in range(3))
        point = [i / n, j / n, j / n - i / n]
        for index, metric in enumerate(['independent', 'joint', 'joint_minus_independent']):
            series = samples[model, endpoint][index]
            intervals.append({'model': model, 'endpoint': endpoint, 'metric': metric, 'point': point[index], 'low': percentile(series, 0.025), 'high': percentile(series, 0.975), 'replicates': len(series)})
        for cluster, value in zip(clusters, values):
            nn, ii, jj = (n - value[0], i - value[1], j - value[2])
            loco.append({'model': model, 'endpoint': endpoint, 'omitted_family': cluster[0], 'omitted_csp_id': cluster[1], 'n': nn, 'independent': ii / nn, 'joint': jj / nn, 'joint_minus_independent': jj / nn - ii / nn})
        if model == 'ALL pooled':
            totals[endpoint] = {'n': n, 'independent': i, 'joint': j, 'difference_pp': 100 * point[2]}
    conditional = {k: sum((r[k] for r in rows)) for k in ['joint_judgment_correct', 'joint_construction_submitted_given_correct_judgment', 'joint_task_success']}
    return {'intervals.json': intervals, 'leave_one_csp_out.json': loco, 'summary.json': {'totals': totals, 'conditional': conditional, 'pooled_intervals': [r for r in intervals if r['model'] == 'ALL pooled']}, 'method.json': {'seed': SEED, 'replicates': REPS, 'strata': 6, 'csps_per_stratum': 4, 'resampling_unit': 'whole CSP; paired across models, languages, directions and endpoints', 'percentile_method': 'linear interpolation at (n-1)*q', 'source': 'replayed S02 answers paired with MAIN', 'source_sha256': hashlib.sha256(raw).hexdigest(), 'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'interval_rows': len(intervals), 'loco_rows': len(loco)}}
