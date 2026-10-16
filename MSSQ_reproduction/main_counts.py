"""重建兼容性、条件构造比例及错误类型。输入逐题评分，输出计数及CSP贡献；沿用论文定义。"""
from collections import Counter,defaultdict
import statistics_main as b
ALLOWED = {'must': {True: {'N', 'E'}, False: {'C', 'I'}}, 'may': {True: {'N', 'C'}, False: {'I', 'E'}}, 'witness': {True: {'N', 'C'}, False: {'I', 'E'}}, 'counterexample': {True: {'I', 'C'}, False: {'N', 'E'}}}
def detail_counts(rows):
    grouped = defaultdict(dict)
    for r in rows:
        grouped[tuple((r[k] for k in ['model', 'family', 'language', 'csp_id', 'quartet_id']))][r['task']] = r
    totals = Counter()
    models = defaultdict(Counter)
    contrib = defaultdict(lambda: [0, 0, 0, 0])
    events = []
    split = []
    failures = Counter()
    declarations = Counter()
    direction = Counter()
    for key, t in grouped.items():
        known = {task: b.predicted_claim(r) for task, r in t.items()}
        for task in ['witness', 'counterexample']:
            if known[task] is True and (not t[task]['task_success']):
                known[task] = None
        permitted = {'N', 'C', 'I', 'E'}
        for task, value in known.items():
            if value is not None:
                permitted &= ALLOWED[task][value]
        complete = all((v is not None for v in known.values()))
        category = 'direct' if not permitted else 'nonempty_dependent' if permitted == {'E'} else 'compatible' if complete else 'indeterminate'
        totals[category] += 1
        models[key[0]][category] += 1
        split.append(dict(zip(['model', 'family', 'language', 'csp_id', 'quartet_id'], key), category=category, complete_evidence=complete))
        modal = all((t[k]['task_success'] for k in ['must', 'may']))
        full = all((r['task_success'] for r in t.values()))
        both = all((t[k]['construction_valid'] is True for k in ['witness', 'counterexample']))
        judgments_available = all((t[k]['semantic_recoverable'] for k in ['must', 'may']))
        wrong = both and judgments_available and (not modal)
        for name, value in [('modal_correct', modal), ('full', full), ('both_valid', both), ('both_valid_wrong_judgments', wrong), ('both_valid_unavailable_judgments', both and (not judgments_available))]:
            totals[name] += int(value)
        c = contrib[key[1], key[3]]
        for i, value in enumerate([modal and (not full), modal, wrong, both]):
            c[i] += int(value)
        if wrong:
            events.append(dict(zip(['model', 'family', 'language', 'csp_id', 'quartet_id'], key)))
        if modal:
            failure = set()
            for task in ['witness', 'counterexample']:
                r = t[task]
                if r['task_success']:
                    continue
                failure.add('unavailable' if not r['semantic_recoverable'] else 'false_NONE' if b.predicted_claim(r) is False else 'invalid')
            failures['+'.join(sorted(failure)) or 'full'] += 1
        for jt, ct, positive in [('may', 'witness', True), ('must', 'counterexample', False)]:
            if b.predicted_claim(t[jt]) is positive:
                declarations[jt + '_all'] += 1
                declarations[jt + '_all_valid'] += int(t[ct]['construction_valid'] is True)
                if t[jt]['task_success']:
                    declarations[jt + '_gold_correct'] += 1
                    declarations[jt + '_gold_correct_valid'] += int(t[ct]['construction_valid'] is True)
        if t['must']['modality'] == 'contingent':
            w = t['witness']['construction_valid'] is True
            c = t['counterexample']['construction_valid'] is True
            direction['both' if w and c else 'witness_only' if w else 'counterexample_only' if c else 'neither'] += 1
    return (dict(total=dict(totals), by_model={m: dict(c) for m, c in models.items()}, failures_given_correct_judgments=dict(failures), existence_declarations=dict(declarations), contingent_constructions=dict(direction), wrong_judgment_csps=len({(r['family'], r['csp_id']) for r in events}), wrong_judgment_models=len({r['model'] for r in events})), contrib, events, split)
