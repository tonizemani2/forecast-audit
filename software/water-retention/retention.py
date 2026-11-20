"""Pair recapture ratio of the Project Red doublet: quantity, hypotheses, bands, gates.

Protocol: PLAN.md (frozen). The thermal-sweep package is imported, not edited.
Nothing here reads a month after the cut-off it is given.
"""
import datetime
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'software/thermal-sweep'))

import fieldmodel as fm                                                # noqa: E402

TRAIN_THROUGH = '2025-12-31'
REGISTERED_THROUGH = '2026-07-31'
HORIZON_END = '2027-12-31'
SHUT_IN_GAL = 3.0e6              # PLAN section 5: a month below this injects "nothing" for the epoch rule
COLD_F = 130.0                   # PLAN section 7: injection below this is the cold regime
ROLLING = 6                      # training months predicted in the rolling-origin selection
COVERAGE = 0.8
GATE_BAND = (0.70, 0.90)         # gate R2
SCORED_MONTHS = 6
MAX_OUTSIDE = 2                  # W1-a / W0-a
PARAMETERS = dict(M1=1, M2=2, M3=2, M4=2)


# ---- quantity -------------------------------------------------------------

def masses(record, produced='fit'):
    """Injected and produced mass of one month, kg. `produced` selects the density of the hot stream."""
    injected = record['injection_gal'] * fm.GAL_M3 * fm.water_density(fm.f_to_c(record['injection_temp_f']))
    density = fm.RHO_PRODUCED if produced == 'fixed' else fm.water_density(fm.f_to_c(record['production_temp_f']))
    return injected, record['production_gal'] * fm.GAL_M3 * density


def ratio(record, produced='fit'):
    """Pair recapture ratio; `produced='volume'` is the plain gallon ratio."""
    if produced == 'volume':
        return record['production_gal'] / record['injection_gal']
    injected, out = masses(record, produced)
    return out / injected


def steady_months(records):
    """Rule W: own production at the threshold, positive injection, 90 steady days before. Volumes only."""
    chosen, conditioned = [], 0
    for i, r in enumerate(records):
        steady = r['production_gal'] >= fm.STEADY_GAL
        if steady and r['injection_gal'] > 0 and conditioned >= fm.CONDITIONING_DAYS:
            chosen.append(i)
        if steady:
            conditioned += fm.month_days(r['month_end'])
    return chosen


def month_index(month_end):
    date = datetime.date.fromisoformat(month_end)
    return date.year * 12 + date.month - 1


def features(records):
    """Regressors per month from reported values up to and including that month."""
    first = datetime.date.fromisoformat(records[0]['month_end']).replace(day=1)
    epoch = first
    rows = []
    for i, r in enumerate(records):
        start = datetime.date.fromisoformat(r['month_end']).replace(day=1)
        days = fm.month_days(r['month_end'])
        low = [x['injection_gal'] < SHUT_IN_GAL for x in records[max(0, i - 2):i + 1]]
        if i >= 2 and low == [True, True, False]:
            epoch = start
        rows.append(dict(
            month_end=r['month_end'],
            years=((start - first).days + days / 2) / 365.25,
            epoch_start=epoch.isoformat(),
            epoch_days=(start - epoch).days + days / 2,
            rate_kg_s=masses(r)[0] / (days * 86400) if r['injection_gal'] > 0 else 0.0,
            cold=r['injection_temp_f'] < COLD_F))
    return rows


# ---- hypotheses -----------------------------------------------------------

def regressor(model, feature):
    return dict(M1=lambda f: 0.0, M2=lambda f: f['years'], M3=lambda f: f['epoch_days'] ** -0.5,
                M4=lambda f: f['rate_kg_s'])[model](feature)


def fit(model, points):
    """Least-squares (a, b). `points` are (feature, R). M3 is fitted on the loss fraction."""
    xs = [regressor(model, f) for f, _ in points]
    ys = [1.0 - r if model == 'M3' else r for _, r in points]
    mean_x, mean_y = math.fsum(xs) / len(xs), math.fsum(ys) / len(ys)
    spread = math.fsum((x - mean_x) ** 2 for x in xs)
    if model == 'M1' or spread <= 1e-12 * max(1.0, mean_x * mean_x):
        return mean_y, 0.0
    slope = math.fsum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / spread
    return mean_y - slope * mean_x, slope


def predict(model, coefficients, feature):
    value = coefficients[0] + coefficients[1] * regressor(model, feature)
    return 1.0 - value if model == 'M3' else value


def comparator_window(points, target_index):
    """C0's months: steady months in the 12 calendar months before `target_index`; else the last three."""
    earlier = [p for p in points if month_index(p[0]['month_end']) < target_index]
    window = [p for p in earlier if month_index(p[0]['month_end']) >= target_index - 12]
    return window if len(window) >= 3 else earlier[-3:]


def mean_ratio(points):
    return math.fsum(r for _, r in points) / len(points)


def conformal(residuals):
    """Half-width of the nominal 80 % band from absolute residuals."""
    ordered = sorted(abs(e) for e in residuals)
    return ordered[min(len(ordered), math.ceil(COVERAGE * (len(ordered) + 1))) - 1]


def leave_one_out(model, points):
    return [r - predict(model, fit(model, points[:i] + points[i + 1:]), f) for i, (f, r) in enumerate(points)]


def comparator_band(window):
    if len(window) < 2:
        return 0.0
    return conformal([r - mean_ratio(window[:i] + window[i + 1:]) for i, (_, r) in enumerate(window)])


def rolling_errors(model, points):
    """Rolling origin over the last ROLLING points: each predicted from the points before it."""
    errors = []
    for k in range(len(points) - ROLLING, len(points)):
        feature, observed = points[k]
        if model == 'C0':
            predicted = mean_ratio(comparator_window(points[:k], month_index(feature['month_end'])))
        else:
            predicted = predict(model, fit(model, points[:k]), feature)
        errors.append(predicted - observed)
    return errors


def mean_abs(errors):
    return math.fsum(abs(e) for e in errors) / len(errors)


def points_of(records, through, after=None):
    feats = features(records)
    return [(feats[i], ratio(records[i])) for i in steady_months(records)
            if records[i]['month_end'] <= through and (after is None or records[i]['month_end'] > after)]


def fitted(points, origin_index):
    """Coefficients and band half-width for every hypothesis and for C0 at one origin."""
    models = {}
    for model in PARAMETERS:
        coefficients = fit(model, points)
        models[model] = dict(a=coefficients[0], b=coefficients[1], half_width=conformal(leave_one_out(model, points)),
                             fit_months=len(points))
    window = comparator_window(points, origin_index)
    comparator = dict(value=mean_ratio(window), half_width=comparator_band(window),
                      window=[f['month_end'] for f, _ in window])
    return models, comparator


# ---- stages ---------------------------------------------------------------

def develop(records):
    """Training only: selection by rolling origin, coefficients and bands. Reads nothing after TRAIN_THROUGH."""
    known = [r for r in records if r['month_end'] <= TRAIN_THROUGH]
    points = points_of(known, TRAIN_THROUGH)
    models, comparator = fitted(points, month_index(TRAIN_THROUGH) + 1)
    for model in models:
        models[model]['rolling_mae'] = mean_abs(rolling_errors(model, points))
    comparator['rolling_mae'] = mean_abs(rolling_errors('C0', points))
    selected = min(models, key=lambda m: (models[m]['rolling_mae'], PARAMETERS[m], m))
    return dict(train_through=TRAIN_THROUGH, selected=selected, models=models, comparator=comparator,
                training=[dict(month_end=f['month_end'], ratio=r, years=f['years'], epoch_start=f['epoch_start'],
                               epoch_days=f['epoch_days'], rate_kg_s=f['rate_kg_s']) for f, r in points])


def judged(name, entry, points):
    """One forecaster on a set of (feature, R): rows, error and coverage."""
    rows = []
    for feature, observed in points:
        centre = entry['value'] if name == 'C0' else predict(name, (entry['a'], entry['b']), feature)
        low, high = centre - entry['half_width'], centre + entry['half_width']
        rows.append(dict(month_end=feature['month_end'], observed=observed, predicted=centre, low=low, high=high,
                         inside=low <= observed <= high, error=centre - observed, cold=feature['cold']))
    result = dict(rows=rows, months=len(rows))
    if rows:
        result.update(mae=mean_abs([r['error'] for r in rows]), bias=math.fsum(r['error'] for r in rows) / len(rows),
                      inside=sum(r['inside'] for r in rows), coverage=sum(r['inside'] for r in rows) / len(rows))
    return result


def hindcast(records, frozen):
    """Score every frozen forecaster on the held-out steady months; gates on the selected one."""
    known = [r for r in records if r['month_end'] <= REGISTERED_THROUGH]
    points = points_of(known, REGISTERED_THROUGH, after=TRAIN_THROUGH)
    entries = dict(frozen['models'], C0=frozen['comparator'])
    results = {name: judged(name, entry, points) for name, entry in entries.items()}
    chosen, base = results[frozen['selected']], results['C0']
    gates = dict(
        R1=dict(statistic=chosen['mae'], comparator=base['mae'], passed=chosen['mae'] < base['mae']),
        R2=dict(statistic=chosen['coverage'], inside=chosen['inside'], months=chosen['months'],
                passed=GATE_BAND[0] <= chosen['coverage'] <= GATE_BAND[1]))
    identical = {known[i]['month_end'] for i in fm.fit_months(known)}
    subsets = {}
    for label, keep in (('warm', lambda f: not f['cold']), ('cold', lambda f: f['cold']),
                        ('fit_months_identical', lambda f: f['month_end'] in identical)):
        subset = [p for p in points if keep(p[0])]
        subsets[label] = {name: {k: v for k, v in judged(name, entry, subset).items() if k != 'rows'}
                          for name, entry in entries.items()}
    held = [r for r in known if r['month_end'] > TRAIN_THROUGH]
    steady = {f['month_end'] for f, _ in points}
    return dict(selected=frozen['selected'], gates=gates, results=results, subsets=subsets,
                decision='W1' if gates['R1']['passed'] and gates['R2']['passed'] else 'W0',
                held_out=[dict(month_end=r['month_end'], steady=r['month_end'] in steady, ratio=ratio(r),
                               ratio_fixed_density=ratio(r, 'fixed'), ratio_volume=ratio(r, 'volume'))
                          for r in held if r['injection_gal'] > 0])


def regime_allowance(points):
    """PLAN section 7: |mean R of the cold steady months - mean R of as many steady months just before them|."""
    cold = [i for i, (f, _) in enumerate(points) if f['cold']]
    if not cold:
        return 0.0, [], []
    before = points[max(0, cold[0] - len(cold)):cold[0]]
    if not before:
        return 0.0, [f['month_end'] for f, _ in (points[i] for i in cold)], []
    cold_points = [points[i] for i in cold]
    return (abs(mean_ratio(cold_points) - mean_ratio(before)),
            [f['month_end'] for f, _ in cold_points], [f['month_end'] for f, _ in before])


def register(records, decision, selected):
    """Refit on every steady month to REGISTERED_THROUGH and widen the band by the regime allowance."""
    known = [r for r in records if r['month_end'] <= REGISTERED_THROUGH]
    points = points_of(known, REGISTERED_THROUGH)
    models, comparator = fitted(points, month_index(REGISTERED_THROUGH) + 1)
    allowance, cold, before = regime_allowance(points)
    last = features(known)[-1]
    recent = comparator_window(points, month_index(REGISTERED_THROUGH) + 1)
    forecast = dict(
        id=decision, registered_through=REGISTERED_THROUGH, horizon_end=HORIZON_END, scored_months=SCORED_MONTHS,
        max_outside=MAX_OUTSIDE, regime_allowance=allowance, regime_cold_months=cold, regime_reference_months=before,
        reference=dict(id='C0', value=comparator['value'], half_width=comparator['half_width'] + allowance,
                       window=comparator['window']),
        state=dict(record_start=known[0]['month_end'], epoch_start=last['epoch_start'],
                   assumed_rate_kg_s=math.fsum(f['rate_kg_s'] for f, _ in recent) / len(recent)),
        fit_months=[dict(month_end=f['month_end'], ratio=r, cold=f['cold']) for f, r in points])
    if decision == 'W1':
        entry = models[selected]
        forecast['model'] = dict(id=selected, a=entry['a'], b=entry['b'], half_width=entry['half_width'] + allowance,
                                 fit_months=entry['fit_months'])
    return forecast


def forecaster(forecast):
    """(name, entry) of the registered forecaster in the form `judged` takes."""
    if forecast['id'] == 'W1':
        return forecast['model']['id'], forecast['model']
    return 'C0', forecast['reference']


def table(forecast):
    """Monthly centre and band, August 2026 - December 2027, with no shut-in and the assumed injection rate."""
    name, entry = forecaster(forecast)
    first = datetime.date.fromisoformat(forecast['state']['record_start']).replace(day=1)
    epoch = datetime.date.fromisoformat(forecast['state']['epoch_start'])
    rows, index = [], month_index(forecast['registered_through']) + 1
    while index <= month_index(forecast['horizon_end']):
        start = datetime.date(index // 12, index % 12 + 1, 1)
        end = (start.replace(day=28) + datetime.timedelta(days=4)).replace(day=1) - datetime.timedelta(days=1)
        days = end.day
        feature = dict(month_end=end.isoformat(), years=((start - first).days + days / 2) / 365.25,
                       epoch_days=(start - epoch).days + days / 2, rate_kg_s=forecast['state']['assumed_rate_kg_s'])
        centre = entry['value'] if name == 'C0' else predict(name, (entry['a'], entry['b']), feature)
        rows.append(dict(month_end=end.isoformat(), low=centre - entry['half_width'], ratio=centre,
                         high=centre + entry['half_width']))
        index += 1
    return rows


def score(records, forecast):
    """Judge the registered forecast on a later record: the first six scoreable steady months."""
    points = points_of(records, forecast['horizon_end'], after=forecast['registered_through'])[:forecast['scored_months']]
    name, entry = forecaster(forecast)
    mine = judged(name, entry, points)
    reference = judged('C0', forecast['reference'], points)
    complete = len(points) == forecast['scored_months']
    result = dict(id=forecast['id'], forecaster=name, scored=len(points), last_month=records[-1]['month_end'],
                  result=mine, reference=reference)
    outside = mine['months'] - mine.get('inside', 0)
    if outside > forecast['max_outside']:
        result['band'] = 'BREACHED'
    else:
        result['band'] = 'HELD' if complete else 'PENDING'
    if forecast['id'] == 'W1':
        result['skill'] = ('PENDING' if not complete else 'SKILL' if mine['mae'] < reference['mae'] else 'NO SKILL')
    return result
