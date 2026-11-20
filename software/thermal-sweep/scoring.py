"""Out-of-sample checks for the Project Red ensemble.

`hindcast` re-runs the frozen calibration protocol on a truncated record and
compares its band with months it never saw. `score` judges the registered
forecast F1 on a later regulator workbook with the ensemble locked. In both,
the drive is the actually reported flow and injection temperature.
"""
import math

import fieldmodel as fm

NOISE_F = 1.0                    # reporting resolution and month-to-month scatter of the record
REGISTERED_THROUGH = '2026-07-31'
BREACH_FRACTION = 0.4            # PLAN section 6, F1
SCORED_MONTHS = 6


def quantile(values, p):
    ordered = sorted(values)
    position = (len(ordered) - 1) * p
    low = math.floor(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def outlet_f(params, records):
    """Monthly-mean reservoir-outlet temperature in deg F (None when shut in)."""
    return [None if v is None else fm.c_to_f(v) for v in fm.red_series(params, records)]


def calibrate(outlets, records, fit):
    """Wellhead offset and RMSE of every run on the given fit months; accepted set by the PLAN rule."""
    runs = []
    for series in outlets:
        residual = [series[i] - records[i]['production_temp_f'] for i in fit]
        offset = math.fsum(residual) / len(residual)
        rmse = math.sqrt(math.fsum((r - offset) ** 2 for r in residual) / len(residual))
        runs.append(dict(series=series, offset_f=offset, rmse_f=rmse))
    best = min(r['rmse_f'] for r in runs)
    threshold = max(1.0, 1.25 * best)
    return [r for r in runs if r['rmse_f'] <= threshold], best, threshold


def month_band(accepted, records, index):
    values = [r['series'][index] - r['offset_f'] for r in accepted]
    observed = records[index]['production_temp_f']
    low, mid, high = quantile(values, 0.1) - NOISE_F, quantile(values, 0.5), quantile(values, 0.9) + NOISE_F
    return dict(month_end=records[index]['month_end'], observed_f=observed, p10_f=low, median_f=mid, p90_f=high,
                inside=low <= observed <= high, error_f=mid - observed)


def hindcast(outlets, records, cutoff, extra_months=()):
    """Calibrate on the record up to `cutoff`, then judge the later steady months."""
    known = [r for r in records if r['month_end'] <= cutoff]
    fit = fm.fit_months(known)
    accepted, best, threshold = calibrate(outlets, records, fit)
    later = [i for i in fm.fit_months(records) if records[i]['month_end'] > cutoff]
    later += [i for i, r in enumerate(records) if r['month_end'] in extra_months and r['month_end'] > cutoff]
    rows = [month_band(accepted, records, i) for i in sorted(later)]
    last, previous = fit[-1], fit[-2]
    slope = ((records[last]['production_temp_f'] - records[previous]['production_temp_f'])
             / (last - previous))
    for row, i in zip(rows, sorted(later)):
        row['persistence_error_f'] = records[last]['production_temp_f'] - row['observed_f']
        row['trend_error_f'] = records[last]['production_temp_f'] + slope * (i - last) - row['observed_f']

    def mean_abs(key):
        return math.fsum(abs(r[key]) for r in rows) / len(rows)

    return dict(cutoff=cutoff, fit_months=[records[i]['month_end'] for i in fit], accepted_runs=len(accepted),
                best_rmse_f=best, acceptance_rmse_f=threshold, months=rows,
                inside=sum(r['inside'] for r in rows), of=len(rows),
                mean_abs_error_f=dict(model=mean_abs('error_f'), persistence=mean_abs('persistence_error_f'),
                                      linear_trend=mean_abs('trend_error_f')))


def score(locked, records):
    """Judge F1 on steady months after registration. `locked`: series + offset per accepted run."""
    months = [i for i in fm.fit_months(records) if records[i]['month_end'] > REGISTERED_THROUGH]
    rows = [month_band(locked, records, i) for i in months]
    judged = rows[:SCORED_MONTHS]
    outside = sum(not r['inside'] for r in judged)
    if len(judged) < SCORED_MONTHS:
        verdict = 'PENDING'
    else:
        verdict = 'REJECTED' if outside / SCORED_MONTHS > BREACH_FRACTION else 'RETAINED'
    return dict(scoreable_months=len(rows), judged=len(judged), outside=outside, verdict=verdict, months=rows)
