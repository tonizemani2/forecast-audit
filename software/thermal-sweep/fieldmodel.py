"""Field drives, the fit-month rule and extrapolated monthly outlet series.

Protocol: PLAN.md sections 5 and 6. Nothing here reads a target temperature
before the drive is built; the fit-month rule uses volumes only.
"""
import datetime
import math

from sweep import MONTH, Sweep, lognormal_shares

GAL_M3 = 3.785411784e-3
BPM_M3_S = 0.158987294928 / 60
RHO_PRODUCED = 892.0            # kg/m3, assumption: produced volume metered hot (PLAN section 5)
STEADY_GAL = 19.0e6             # monthly production volume for a steady month
CONDITIONING_DAYS = 90
PERMUTATION_SEED = 2026111901

RED = dict(clusters=96, cluster_spacing_m=30 * 0.3048, path_m=110.0, height_m=143.0, t_rock_c=185.0)
RED_GRID = dict(
    phi_h=[round(0.08 * (1.0 / 0.08) ** (i / 11), 4) for i in range(12)],
    phi_n=[1.0, 0.75, 0.5, 0.33, 0.25],
    sigma=[0.0, 0.5, 1.0, 1.5],
    lam=[0.0, 0.5],
    k_rock=[2.5, 2.9, 3.3])
RHO_C = 2.55e6


def f_to_c(f):
    return (f - 32.0) / 1.8


def c_to_f(c):
    return c * 1.8 + 32.0


def water_density(t_c):
    """Liquid density for 10-100 C injection water, kg/m3 (quadratic fit, within 0.2 %)."""
    return 1001.1 - 0.0867 * t_c - 0.0035 * t_c * t_c


def month_days(month_end):
    date = datetime.date.fromisoformat(month_end)
    first_next = (date.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
    return (first_next - date.replace(day=1)).days


def ndom_drive(records, lam):
    """Monthly effective sweep flow and injection temperature from the regulator record."""
    drive = []
    for r in records:
        seconds = month_days(r['month_end']) * 86400
        t_inj = f_to_c(r['injection_temp_f']) if r['injection_gal'] > 0 else None
        produced = r['production_gal'] * GAL_M3 * RHO_PRODUCED / seconds
        injected = r['injection_gal'] * GAL_M3 * water_density(t_inj) / seconds if t_inj is not None else 0.0
        flow = produced + lam * (injected - produced) if produced > 0 else 0.0
        drive.append(dict(month_end=r['month_end'], seconds=seconds, flow_kg_s=max(flow, 0.0),
                          t_inj_c=t_inj if flow > 0 else None))
    return drive


def fit_months(records):
    """Indices of steady months after wellbore conditioning; volumes only."""
    steady = [r['production_gal'] >= STEADY_GAL for r in records]
    chosen, conditioned = [], 0
    for i, r in enumerate(records):
        if conditioned >= CONDITIONING_DAYS and 0 < i < len(records) - 1 and all(steady[i - 1:i + 2]):
            chosen.append(i)
        if steady[i]:
            conditioned += month_days(r['month_end'])
    return chosen


def monthly_outlet(gaps, shares, drive, *, path_m, height_m, t_rock_c, k_rock, ns, sub,
                   layers=None, n_layers=1, ny=8, per_fracture=False):
    """Mixed outlet temperature at the end of each drive interval (None when shut in)."""
    model = Sweep(gaps, path_m=path_m, height_m=height_m, t_rock_c=t_rock_c, k_rock=k_rock,
                  rho_c=RHO_C, ns=ns, ny=ny, layers=layers, n_layers=n_layers)
    idle = [0.0] * len(shares)
    series, detail = [], []
    for interval in drive:
        flow = interval['flow_kg_s']
        if flow > 0:
            flows = [s * flow for s in shares]
            for _ in range(sub):
                row = model.step(flows, interval['t_inj_c'], interval['seconds'] / sub)
            series.append(row['mixed_c'])
            detail.append(row['outlet_c'])
        else:
            model.step(idle, t_rock_c, interval['seconds'])
            series.append(None)
            detail.append(None)
    return (series, detail) if per_fracture else series


def interval_means(series):
    """Interval-average estimate from end-of-interval values (trapezoid; first flowing interval as is)."""
    return [None if value is None else value if not i or series[i - 1] is None
            else (value + series[i - 1]) / 2 for i, value in enumerate(series)]


def extrapolated(gaps, shares, drive, *, ns=16, sub=1, **geometry):
    """Richardson extrapolation in path stations and time step (gates N1, N2, N4)."""
    coarse = monthly_outlet(gaps, shares, drive, ns=ns, sub=sub, **geometry)
    fine = monthly_outlet(gaps, shares, drive, ns=2 * ns, sub=2 * sub, **geometry)
    if isinstance(coarse, tuple):
        series = [None if a is None else 2 * b - a for a, b in zip(coarse[0], fine[0])]
        detail = [None if a is None else [None if x is None else 2 * y - x for x, y in zip(a, b)]
                  for a, b in zip(coarse[1], fine[1])]
        return series, detail
    return [None if a is None else 2 * b - a for a, b in zip(coarse, fine)]


def red_geometry(phi_h, phi_n, sigma):
    """Gaps, flow shares and wetted height for one Project Red parameter set."""
    flowing = max(2, round(RED['clusters'] * phi_n))
    gaps = [RED['cluster_spacing_m'] / phi_n] * (flowing - 1)
    shares = lognormal_shares(flowing, sigma, PERMUTATION_SEED)
    return gaps, shares, RED['height_m'] * phi_h


def red_series(params, records, drive=None, **numerics):
    """Monthly-mean reservoir-outlet series (deg C) for one parameter set over the supplied record."""
    gaps, shares, height = red_geometry(params['phi_h'], params['phi_n'], params['sigma'])
    drive = drive or ndom_drive(records, params['lam'])
    return interval_means(extrapolated(
        gaps, shares, drive, path_m=RED['path_m'], height_m=height,
        t_rock_c=params.get('t_rock_c', RED['t_rock_c']), k_rock=params['k_rock'], **numerics))


def red_misfit(params, records, **numerics):
    """Closed-form wellhead offset and RMSE (deg F) on the fit months."""
    series = red_series(params, records, **numerics)
    months = fit_months(records)
    if any(series[i] is None for i in months):
        raise ValueError('fit month without flow')
    offsets = [c_to_f(series[i]) - records[i]['production_temp_f'] for i in months]
    delta = math.fsum(offsets) / len(offsets)
    rmse = math.sqrt(math.fsum((o - delta) ** 2 for o in offsets) / len(offsets))
    wellhead = [None if s is None else c_to_f(s) - delta for s in series]
    return dict(params=params, rmse_f=rmse, offset_f=delta, wellhead_f=wellhead, outlet_c=series)


def red_area_m2(params):
    """One-sided effective wetted area and its ratio to the stated design."""
    flowing = max(2, round(RED['clusters'] * params['phi_n']))
    area = flowing * RED['path_m'] * RED['height_m'] * params['phi_h']
    return area, area / (RED['clusters'] * RED['path_m'] * RED['height_m'])


# ---- Utah FORGE 16A -> 16B (PLAN section 6, forecasts F3 and F4) ----------

FORGE = dict(
    path_m=100.0, nominal_width_m=300.0, clusters=27, t_rock_c=215.0,
    toe_md_ft=[10076.0, 10276.0, 10476.0, 10676.0, 10876.0],       # assumption: five clusters over stages 3R-5
    tests=[dict(name='2024', start_day=0, days=27, bpm=9.0, t_inj_c=20.0),
           dict(name='2025', start_day=368, days=7, bpm=9.0, t_inj_c=20.0),            # assumption: conditions as 2024
           dict(name='2026', start_day=734, days=122, bpm=9.5 * 0.85, t_inj_c=65.0)],   # 85 % recovery: assumption
    tracer_area_ratio=dict(fredd=5.5e6 * 0.3048 ** 2 / (27 * 100.0 * 300.0),
                           mcclure=9.7e6 * 0.3048 ** 2 / (27 * 100.0 * 300.0)),
    layers=12)


def forge_clusters(rows, pattern):
    """Positions (m along 16A), flow shares and stage labels from the spinner table."""
    column = dict(august='august_2024_pct', april='april_2024_pct')[pattern]
    listed = [r for r in rows if r['cluster'] != 'below-9976']
    toe = next(r for r in rows if r['cluster'] == 'below-9976')
    clusters = []
    for stage in sorted({r['stage'] for r in listed}):
        members = [r for r in listed if r['stage'] == stage]
        known = [r for r in members if r[column] != '']
        if len(known) == len(members):
            values = [float(r[column]) for r in members]
        else:                                    # April 2024: stage total only (S4), split equally
            total = dict(april={'8': 16.2, '7': 1.8, '6': 0.0})[pattern][stage]
            values = [total / len(members)] * len(members)
        clusters += [(float(r['perf_top_ft_md']), v, stage) for r, v in zip(members, values)]
    clusters += [(md, float(toe[column]) / len(FORGE['toe_md_ft']), 'toe') for md in FORGE['toe_md_ft']]
    clusters.sort()
    total = math.fsum(c[1] for c in clusters)
    positions = [c[0] * 0.3048 for c in clusters]
    return dict(gaps=[b - a for a, b in zip(positions, positions[1:])],
                shares=[c[1] / total for c in clusters], stages=[c[2] for c in clusters])


def forge_drive():
    """Daily intervals while circulating, 30-day conduction intervals while shut in."""
    drive, day = [], 0
    for test in FORGE['tests']:
        idle = test['start_day'] - day
        while idle > 0:
            chunk = min(30, idle)
            drive.append(dict(test=None, seconds=chunk * 86400.0, flow_kg_s=0.0, t_inj_c=None))
            idle -= chunk
        flow = test['bpm'] * BPM_M3_S * water_density(test['t_inj_c'])
        drive += [dict(test=test['name'], day=d + 1, seconds=86400.0, flow_kg_s=flow, t_inj_c=test['t_inj_c'])
                  for d in range(test['days'])]
        day = test['start_day'] + test['days']
    return drive


def forge_geometry(clusters, area_ratio, beta):
    """Wetted width per cluster proportional to flow share ** beta (0 = equal widths)."""
    area = area_ratio * FORGE['clusters'] * FORGE['path_m'] * FORGE['nominal_width_m']
    shares = clusters['shares']
    flowing = [s > 0 for s in shares]
    if beta == 0:
        return dict(height_m=area / (sum(flowing) * FORGE['path_m']), n_layers=1, layers=None)
    levels = FORGE['layers']
    kappa = [max(1, round(levels * (s / max(shares)) ** beta)) for s in shares]
    wetted = sum(k for k, f in zip(kappa, flowing) if f)
    return dict(height_m=area * levels / (FORGE['path_m'] * wetted), n_layers=levels, layers=kappa)


def forge_run(clusters, area_ratio, beta, k_rock):
    """Commingled reservoir-outlet temperature per test day, and per stage for the 2026 test."""
    drive = forge_drive()
    series, detail = extrapolated(clusters['gaps'], clusters['shares'], drive, path_m=FORGE['path_m'],
                                  t_rock_c=FORGE['t_rock_c'], k_rock=k_rock, per_fracture=True,
                                  **forge_geometry(clusters, area_ratio, beta))
    mixed = {test['name']: [series[i] for i, d in enumerate(drive) if d['test'] == test['name']]
             for test in FORGE['tests']}
    days = [i for i, d in enumerate(drive) if d['test'] == '2026']
    stages = {}
    for name in sorted(set(clusters['stages'])):
        members = [i for i, s in enumerate(clusters['stages']) if s == name and clusters['shares'][i] > 0]
        weight = math.fsum(clusters['shares'][i] for i in members)
        if weight > 0:
            stages[name] = dict(share=weight, outlet_c=[
                math.fsum(clusters['shares'][i] * detail[d][i] for i in members) / weight for d in days])
    return dict(mixed_c=mixed, stages=stages)


def cooling(series, day):
    """Cooling at `day` (1-based) relative to the maximum of the first ten days."""
    return max(series[:10]) - series[day - 1]


# ---- Cape-class producer side (forecast F5) -------------------------------

CAPE = dict(clusters=150, cluster_spacing_m=9.8255, path_m=152.4, t_rock_c=200.0, t_inj_c=75.0,
            flow_kg_s=50.0, nominal_height_m=[143.0, 228.0], months=180)


def cape_run(phi_h, phi_n, sigma, k_rock, nominal_height_m):
    """Monthly reservoir-outlet temperature for one producer side at constant flow."""
    flowing = max(2, round(CAPE['clusters'] * phi_n))
    gaps = [CAPE['cluster_spacing_m'] / phi_n] * (flowing - 1)
    shares = lognormal_shares(flowing, sigma, PERMUTATION_SEED)
    drive = [dict(seconds=MONTH, flow_kg_s=CAPE['flow_kg_s'], t_inj_c=CAPE['t_inj_c'])] * CAPE['months']
    return extrapolated(gaps, shares, drive, path_m=CAPE['path_m'], height_m=nominal_height_m * phi_h,
                        t_rock_c=CAPE['t_rock_c'], k_rock=k_rock)


def months_to_decline(series, kelvin):
    """First month whose decline from the running maximum reaches `kelvin` and stays there; None if never."""
    peak = series[0]
    for month, value in enumerate(series, 1):
        peak = max(peak, value)
        if peak - value >= kelvin and all(peak - later >= kelvin for later in series[month:]):
            return month
    return None
