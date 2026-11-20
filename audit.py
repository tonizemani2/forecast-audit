"""Regenerate every row of the claim audit from the regulator record.

Each row carries: who made the claim, the claim, what the record gives, the
verdict and how the verdict follows. `basis` says where the row's evidence
comes from:
  workbook    recomputed here from the Nevada Division of Minerals workbook
  arithmetic  recomputed here from numbers quoted in the cited documents
  document    read in the cited document on 2026-11-19; carried, not recomputed
Labels on our numbers: measured (regulator record, operator-reported) / [MODEL].
A verdict is on the stated number against the stated record, never on intent.
"""
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'software/thermal-sweep'))
sys.path.insert(0, str(HERE / 'software/water-retention'))

import fieldmodel as fm                                                # noqa: E402
import retention                                                       # noqa: E402

PLATEAU_F = 347.0
SUPPORTED, CONTRADICTED, NOT_CHECKABLE = 'supported', 'contradicted', 'not checkable from public data'


def by_month(records):
    return {r['month_end'][:7]: r for r in records}


def volume_loss(r):
    return 1.0 - r['production_gal'] / r['injection_gal']


def near(value, claimed, tolerance):
    return abs(value - claimed) <= tolerance


def ols(xs, ys):
    """Slope, standard error of the slope."""
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    resid = sum((y - my - slope * (x - mx)) ** 2 for x, y in zip(xs, ys))
    return slope, math.sqrt(resid / (n - 2) / sxx)


def years(month_end):
    y, m = int(month_end[:4]), int(month_end[5:7])
    return (y - 2023) + (m - 12) / 12.0 + 0.5 / 12.0


def water(records):
    """Steady-month recapture (rule W of the registered water-retention plan) and cumulative difference."""
    steady = [records[i] for i in retention.steady_months(records)]
    vol = [retention.ratio(r, 'volume') for r in steady]
    mass = [retention.ratio(r) for r in steady]
    xs = [years(r['month_end']) for r in steady]
    by_year = {}
    for r, v in zip(steady, vol):
        by_year.setdefault(r['month_end'][:4], []).append(1 - v)
    return {
        'steady_months': len(steady), 'first': steady[0]['month_end'], 'last': steady[-1]['month_end'],
        'recapture_volume': sum(vol) / len(vol), 'recapture_volume_min': min(vol), 'recapture_volume_max': max(vol),
        'recapture_mass': sum(mass) / len(mass), 'recapture_mass_min': min(mass), 'recapture_mass_max': max(mass),
        'trend_volume_points_per_year': tuple(100 * v for v in ols(xs, vol)),
        'trend_mass_points_per_year': tuple(100 * v for v in ols(xs, mass)),
        'loss_volume_by_year': {y: sum(v) / len(v) for y, v in by_year.items()},
        'cumulative_injected_minus_produced_gal': sum(r['injection_gal'] - r['production_gal'] for r in records),
        'steady_temperatures_f': [r['production_temp_f'] for r in steady],
    }


def flows(records, floor_gal=0.0):
    """Mean mass rates over the months producing more than floor_gal, kg/s ([MODEL] density of each stream)."""
    months = [r for r in records if r['production_gal'] > floor_gal and r['injection_gal'] > 0]
    seconds = sum(fm.month_days(r['month_end']) * 86400 for r in months)
    injected = sum(retention.masses(r)[0] for r in months) / seconds
    produced = sum(retention.masses(r)[1] for r in months) / seconds
    return injected, produced, len(months)


def rows(records):
    m, w = by_month(records), water(records)
    out = []

    def add(row_id, who, claim, record, verdict, rule, basis, values=None):
        out.append({'id': row_id, 'who': who, 'claim': claim, 'record': record, 'verdict': verdict,
                    'verdict_rule': rule, 'basis': basis, 'values': values or {}})

    # ---- A. thermal decline, Project Red ----
    feb, mar, apr, may24 = m['2024-02'], m['2024-03'], m['2024-04'], m['2024-05']
    inj_up = mar['injection_gal'] / feb['injection_gal'] - 1
    drop = feb['production_temp_f'] - mar['production_temp_f']
    v = {'injection_gal': [feb['injection_gal'], mar['injection_gal']], 'injection_change': inj_up,
         'temp_f': [feb['production_temp_f'], mar['production_temp_f']], 'volume_loss': [volume_loss(feb), volume_loss(mar)]}
    ok = near(100 * inj_up, 33, 1) and near(drop, 90, 1) and near(100 * volume_loss(feb), 21, 1) and near(100 * volume_loss(mar), 57, 1)
    add('A1', 'short report', 'March 2024: 33 % more water injected, production temperature down 90 °F, loss 21 % → 57 %',
        f"injection {feb['injection_gal'] / 1e6:.2f} → {mar['injection_gal'] / 1e6:.2f} M gal ({100 * inj_up:+.1f} %); temperature {feb['production_temp_f']:.0f} → {mar['production_temp_f']:.0f} °F; volume loss {100 * volume_loss(feb):.1f} % → {100 * volume_loss(mar):.1f} %",
        SUPPORTED if ok else CONTRADICTED, 'each quoted number within one unit of the record', 'workbook', v)
    prod_drop = 1 - mar['production_gal'] / feb['production_gal']
    recovered = may24['production_temp_f'] >= PLATEAU_F - 1
    add('A2', 'short report', 'that month shows a failed attempt to boost output that "crushed" temperatures',
        f"production fell {100 * prod_drop:.0f} % that month while injection was the highest of all {len(records)} months: {mar['injection_gal'] == max(r['injection_gal'] for r in records)}; temperature {apr['production_temp_f']:.0f} °F in April, {may24['production_temp_f']:.0f} in May 2024",
        CONTRADICTED + ' as reservoir cooling' if recovered else NOT_CHECKABLE,
        'contradicted as cooling if the plateau reading returns within two months; the cause of the month is not checkable at monthly resolution',
        'workbook', {'production_drop': prod_drop, 'may_2024_f': may24['production_temp_f']})
    ambient = 40.0
    share = (feb['production_temp_f'] - mar['production_temp_f']) / (feb['production_temp_f'] - ambient)
    add('A3', 'critic of the short report', 'the 90 °F is an averaging artefact of a throttled and stopped producer',
        f"{100 * share:.0f} % of readings near {ambient:.0f} °F turn {feb['production_temp_f']:.0f} into {mar['production_temp_f']:.0f} ([MODEL], assumption on ambient); produced volume fell {100 * prod_drop:.0f} %",
        SUPPORTED + ' for the produced stream' if near(100 * share, 100 * prod_drop, 5) else NOT_CHECKABLE,
        'supported if the share of near-ambient readings needed is within five points of the fall in produced volume',
        'workbook', {'share_needed': share, 'production_drop': prod_drop, 'ambient_f_assumption': ambient})
    add('A4', 'short report', 'the operator "altered" the temperature history',
        'the 2024 paper was not read; the 2026 charts plot hourly data against material-balance time; no sub-monthly record is public',
        NOT_CHECKABLE, 'no public record at the needed resolution', 'document')
    nov25, may26, jun26, jul26 = m['2025-11'], m['2026-05'], m['2026-06'], m['2026-07']
    rate = (nov25['production_temp_f'] - may26['production_temp_f']) / 6 * 12
    add('A5', 'short report', 'decline "has now accelerated to 24 °F per year" (November 2025 – May 2026)',
        f"{nov25['production_temp_f']:.0f} → {may26['production_temp_f']:.0f} °F in six months = {rate:.0f} °F per year",
        SUPPORTED if near(rate, 24, 1) else CONTRADICTED, 'arithmetic on the two monthly readings within 1 °F per year', 'workbook', {'rate_f_per_year': rate})
    d6 = may26['production_temp_f'] - jun26['production_temp_f']
    p6 = jun26['production_gal'] / may26['production_gal'] - 1
    add('A6', 'short report', 'June 2026: temperature "plummeted by 90 °F in a single month"',
        f"{may26['production_temp_f']:.0f} → {jun26['production_temp_f']:.0f} °F; production {may26['production_gal'] / 1e6:.1f} → {jun26['production_gal'] / 1e6:.1f} M gal ({100 * p6:+.0f} %); July {jul26['production_temp_f']:.0f} °F at {jul26['production_gal'] / 1e6:.1f} M gal",
        SUPPORTED if near(d6, 90, 1) else CONTRADICTED, 'the quoted drop within 1 °F of the record', 'workbook',
        {'drop_f': d6, 'production_change': p6, 'july_f': jul26['production_temp_f']})
    add('A7', 'short report', '24 °F per year is "nearly 16×" the viable rate', f'{rate:.0f} / 1.5 = {rate / 1.5:.0f}',
        'arithmetic supported; the viability threshold is an opinion — ' + NOT_CHECKABLE, 'ratio recomputed; the threshold has no record', 'arithmetic', {'ratio': rate / 1.5})
    steady_idx = retention.steady_months(records)
    undisturbed = [records[i] for i in fm.fit_months(records)]
    first_low = next(r for r in undisturbed if r['month_end'] > '2024-05' and r['production_temp_f'] < PLATEAU_F - 4)
    plateau_run = [r['production_temp_f'] for r in undisturbed if '2024-05' <= r['month_end'][:7] <= '2025-11']
    add('A8', 'operator', '"more than 500 days" of stable temperature; decline onset at about 500 days',
        f"undisturbed steady months read {min(plateau_run):.0f}–{max(plateau_run):.0f} °F from May 2024 to November 2025; first lower reading in an undisturbed run {first_low['month_end'][:7]} ({first_low['production_temp_f']:.0f} °F)",
        SUPPORTED if first_low['month_end'][:7] == '2025-12' and min(plateau_run) >= PLATEAU_F - 4 else CONTRADICTED,
        'supported if undisturbed months stay within 4 °F of the plateau until late 2025', 'workbook',
        {'plateau_run_f': plateau_run, 'first_lower_month': first_low['month_end']})
    recent = [m[k]['production_temp_f'] for k in ('2025-12', '2026-01', '2026-02', '2026-03')]
    gaps = [PLATEAU_F - t for t in recent]
    add('A9', 'operator', '"only recently … a slight temperature decrease of approximately 2.5 °F" (13 April 2026)',
        f"December 2025 – March 2026 monthly averages {', '.join(f'{t:.0f}' for t in recent)} °F against the {PLATEAU_F:.0f} plateau: {min(gaps):.0f}–{max(gaps):.0f} °F lower",
        CONTRADICTED + ' on the regulator\'s monthly wellhead metric' if min(gaps) > 2.5 + 1 else SUPPORTED,
        'contradicted if every month before the post is more than 3.5 °F below the plateau. Caveat: the operator quotes hourly flowing temperature with no stated cut-off',
        'workbook', {'monthly_f': recent, 'below_plateau_f': gaps})
    temps = w['steady_temperatures_f']
    add('A10', 'operator', 'average production temperature 347 °F',
        f"{PLATEAU_F:.0f} °F is the plateau reading; the mean of the {len(temps)} steady monthly averages is {sum(temps) / len(temps):.0f} °F",
        SUPPORTED + ' as the plateau, not as a whole-period mean' if max(temps) == PLATEAU_F else CONTRADICTED,
        'supported as a plateau if the highest steady reading equals it', 'workbook', {'steady_mean_f': sum(temps) / len(temps), 'steady_max_f': max(temps)})
    add('A11', 'operator (Q3 2026 call)', 'after a stable period a decline was observed; "this was expected"',
        f"decline: {PLATEAU_F:.0f} → {may26['production_temp_f']:.0f} (May 2026), {jul26['production_temp_f']:.0f} (July 2026)",
        'decline supported; "expected" ' + NOT_CHECKABLE, 'a forecast dated before onset is not public', 'workbook',
        {'below_plateau_july_f': PLATEAU_F - jul26['production_temp_f']})
    add('A12', 'short report, citing the registration statement', 'the operator stated no "premature thermal decline"',
        f"{PLATEAU_F - jul26['production_temp_f']:.0f} °F below plateau by July 2026", 'turns on "premature" — ' + NOT_CHECKABLE,
        'the number stands beside the word', 'workbook', {'below_plateau_july_f': PLATEAU_F - jul26['production_temp_f']})
    add('A13', 'short report', 'pilot ran at about 41 % of forecast capacity (2.1 MW against 5.1 MW)',
        f'2.1 / 5.1 = {2.1 / 5.1:.2f} (both figures as printed in the operator\'s 2023 paper and 2026 post)',
        SUPPORTED if near(2.1 / 5.1, 0.41, 0.005) else CONTRADICTED, 'ratio of the two quoted figures', 'arithmetic', {'ratio': 2.1 / 5.1})
    inj, prod, n_all = flows(records)
    inj2, prod2, n_main = flows(records, 2.0e6)
    add('A14', 'operator', 'circulation "roughly 36 kg/s"',
        f'over the {n_all} months with any production: injected {inj:.1f} kg/s, produced {prod:.1f} kg/s, mean {(inj + prod) / 2:.1f}; '
        f'over the {n_main} months producing more than 2 M gal: injected {inj2:.1f}, produced {prod2:.1f}, mean {(inj2 + prod2) / 2:.1f} kg/s ([MODEL] density)',
        SUPPORTED + ' as a rate between the two streams; neither stream alone is 36' if prod < 36 < inj and prod2 < 36 < inj2 else CONTRADICTED,
        'supported if the figure lies between the produced and the injected mean rate under both month selections. '
        'Correction of 19 Nov 2026: the first private audit printed 41.1 / 28.0 / 34.5 kg/s; that selection of months was not recorded and does not reproduce',
        'workbook', {'all_producing_months': {'months': n_all, 'injected_kg_s': inj, 'produced_kg_s': prod},
                     'months_over_2_M_gal': {'months': n_main, 'injected_kg_s': inj2, 'produced_kg_s': prod2}})
    add('A15', 'operator', 'average gross output 2.1 MW, net about 1.4 MW',
        'the workbook carries energy for the whole plant only; the operator states gross power is calculated from a plant model',
        NOT_CHECKABLE, 'no metered pair output is public', 'document')

    # ---- B. water, Project Red ----
    add('B1', 'operator', '"recapture rates of approximately 70 % under steady-state conditions"',
        f"{w['steady_months']} steady months: {100 * w['recapture_volume']:.1f} % by volume ({100 * w['recapture_volume_min']:.1f}–{100 * w['recapture_volume_max']:.1f}), {100 * w['recapture_mass']:.1f} % by mass ([MODEL] density)",
        SUPPORTED if near(100 * w['recapture_volume'], 70, 5) else CONTRADICTED, 'volume recapture within five points of the figure', 'workbook',
        {k: w[k] for k in ('steady_months', 'recapture_volume', 'recapture_mass')})
    years_text = ', '.join(f'{100 * v:.1f} % ({y})' for y, v in sorted(w['loss_volume_by_year'].items()))
    add('B2', 'short report', 'water loss "~30 %"', f"mean volume loss {100 * (1 - w['recapture_volume']):.1f} %; by year {years_text}",
        SUPPORTED + ' (rounded)' if near(100 * (1 - w['recapture_volume']), 30, 5) else CONTRADICTED, 'within five points', 'workbook',
        {'loss_volume': 1 - w['recapture_volume'], 'by_year': w['loss_volume_by_year']})
    tv, tm = w['trend_volume_points_per_year'], w['trend_mass_points_per_year']
    add('B3', 'operator', 'recapture is "expected to improve" as the reservoir pressurises',
        f"trend over {w['steady_months']} steady months: {tv[0]:+.1f} ± {tv[1]:.1f} points per year by volume, {tm[0]:+.1f} ± {tm[1]:.1f} by mass",
        CONTRADICTED + ' to July 2026; the claim is forward-looking and stays open' if tv[0] < 2 * tv[1] else SUPPORTED,
        'contradicted to date if the slope is below twice its standard error', 'workbook', {'trend_volume': tv, 'trend_mass': tm})
    loss = 1 - w['recapture_volume']
    add('B4', 'short report', 'loss "doubled" from 10–20 % in the 2023 flow test',
        f'the operator\'s 2025 post states 80–90 % recapture in a 37-day test; the record gives {100 * loss:.0f} %: {loss / 0.20:.1f}× to {loss / 0.10:.1f}×, {loss / 0.15:.1f}× from the midpoint',
        SUPPORTED if loss / 0.20 <= 2 <= loss / 0.10 else CONTRADICTED, 'two lies inside the range of ratios', 'arithmetic', {'ratio_from_midpoint': loss / 0.15})
    window = ['2025-11', '2025-12', '2026-01', '2026-02', '2026-03', '2026-04', '2026-05', '2026-06', '2026-07']
    losses = [100 * volume_loss(m[k]) for k in window]
    june_lowest = m['2026-06']['injection_gal'] == min(m[k]['injection_gal'] for k in window)
    earlier = [k for k in sorted(m) if k < '2026-06' and m[k]['injection_gal'] > 0 and m[k]['production_gal'] > 0
               and 100 * volume_loss(m[k]) > losses[7]]
    add('B5', 'short report', 'losses consistently high November 2025 – July 2026; June 2026 "a 10-month high of 35 %, despite lower overall injection"',
        f"volume loss by month: {', '.join(f'{x:.1f}' for x in losses)} %; June injection {m['2026-06']['injection_gal'] / 1e6:.1f} M gal, lowest of the window: {june_lowest}; last higher loss {earlier[-1]} ({100 * volume_loss(m[earlier[-1]]):.1f} %)",
        SUPPORTED if near(losses[7], 35, 1) and june_lowest else CONTRADICTED, 'June within one point of the quoted loss and the lowest injection of the window',
        'workbook', {'loss_percent': dict(zip(window, losses)), 'last_higher': earlier[-1]})
    diff = w['cumulative_injected_minus_produced_gal']
    add('B6', 'short report', '"193 million gallons" lost since December 2023', f'injected minus produced, all months: {diff / 1e6:.1f} M gal',
        SUPPORTED + ' as a difference of two meters' if near(diff / 1e6, 193, 1) else CONTRADICTED, 'within 1 M gal', 'workbook', {'difference_gal': diff})
    dec23, jan24 = m['2023-12'], m['2024-01']
    over = dec23['production_gal'] > dec23['injection_gal'] and jan24['production_gal'] > jan24['injection_gal']
    add('B7', 'short report', 'that water was lost "to subsurface leak-off"',
        f'the pair sits inside an operating field with other producers and injectors; in December 2023 and January 2024 the producer returned more than the injector took: {over}',
        NOT_CHECKABLE, 'the record cannot say where the difference went', 'workbook', {'early_months_over_unity': over})
    add('B8', 'short report quoting an analyst and the operator', 'the shortfall is "temporarily stored" rather than lost',
        'no pressure, tracer or field-balance record is public', NOT_CHECKABLE, 'no record', 'document')
    gross_gwh = 33.0
    add('B9', 'operator (2025 post)', 'at scale, "approximately 50–200 gallons per MWh"',
        f'Project Red: {diff / 1e6:.1f} M gal over about {gross_gwh:.0f} GWh gross ([MODEL]) ≈ {diff / (gross_gwh * 1000):,.0f} gal/MWh',
        'different design; ' + NOT_CHECKABLE + ' for the commercial project', 'no commercial-project volume is public', 'arithmetic',
        {'gal_per_mwh': diff / (gross_gwh * 1000), 'gross_gwh_model': gross_gwh})

    # ---- C. water, Cape Station ----
    add('C1', 'operator; short report', 'commercial designs "expected to achieve recapture rates exceeding 99 %"',
        'no injected, produced or diverted volume of the commercial project is public', NOT_CHECKABLE, 'no record', 'document')
    add('C2', 'short report', 'the Utah water right rests on a "non-consumptive" designation',
        'State Engineer order on application A84679 (3 Mar 2026): purpose "nonconsumptive geothermal"; "reason to believe that it will function in a non-consumptive manner, from a basin-wide perspective"',
        SUPPORTED + ' as a description of the filing', 'the order uses the word', 'document')
    kg_s = 2720 * 1233.48184 * 1000 / (365.25 * 86400)
    sustain = {f'{int(100 * loss_frac)}%': [kg_s / loss_frac * kw / 1000 for kw in (95, 106)] for loss_frac in (0.01, 0.10, 0.30)}
    add('C3', 'water-right applicant', '"up to 2,720 acre-feet annually" of make-up water; plant "rated at 2000 MW"',
        f"[MODEL] arithmetic: 2,720 acre-feet a year is {kg_s:.0f} kg/s; at 95–106 kW gross per kg/s (vendor-stated) that make-up sustains {sustain['1%'][0]:,.0f}–{sustain['1%'][1]:,.0f} MW gross at 1 % loss, {sustain['10%'][0]:.0f}–{sustain['10%'][1]:.0f} MW at 10 %, {sustain['30%'][0]:.0f}–{sustain['30%'][1]:.0f} MW at 30 %",
        'no verdict — a consequence: the right as sized is consistent with 99 % recapture and has no room for Project-Red-type loss at the rated size',
        'unit conversion and division', 'arithmetic', {'makeup_kg_s': kg_s, 'sustained_mw_gross': sustain})
    add('C4', 'short report', 'the utility protested the water right',
        'the right\'s file: protest received 27 June 2025; hearing 25 August 2025; late request for reconsideration 5 May 2026',
        'protest ' + SUPPORTED + '; its wording is in exhibits not read', 'dates in the public file', 'document')
    add('C5', 'short report', 'the regulator will require data on water "diverted, injected, and produced"',
        'order, condition 3: an annual groundwater monitoring report including "a metering record of all source wells"; injected and produced volumes go in monthly reports that may be held confidential for up to five years',
        SUPPORTED + ' for diverted water; injected and produced volumes: ' + NOT_CHECKABLE, 'text of the order', 'document')
    add('C6', 'operator (Q3 2026 call)', 'water is "exactly in line with our prior disclosures"', 'no number was given on the call', NOT_CHECKABLE, 'no number', 'document')
    add('C7', 'short report', '24 hours of a 30-day flow test were released and no water-loss figure',
        'the cited paper, credit agreement and employee statements were not read', 'not audited', 'sources not read', 'document')

    # ---- D. seismicity ----
    add('D1', 'short report', 'a magnitude 3.1 event near the commercial project',
        'USGS catalogue: ml 3.13 on 2026-09-12 22:52 UTC, 16 km NE of Milford; a second, ml 3.12, on 2026-11-07',
        'event ' + SUPPORTED + '; attribution ' + NOT_CHECKABLE, 'catalogue query of 2026-11-19, carried', 'document')
    add('D2', 'short report', 'about 58 events of magnitude 2 or more to April 2026, 39 more since',
        'M ≥ 2.0 within 20 km: 49 to April 2026, 17 in March–April, 46 from May to 5 October; the circle contains the Utah FORGE site',
        'direction ' + SUPPORTED + '; counts differ (other catalogue and radius); attribution ' + NOT_CHECKABLE, 'catalogue query of 2026-11-19, carried', 'document')
    return out


def settled(audit_rows):
    """Rows of sections A and B whose verdict rests on data."""
    core = [r for r in audit_rows if r['id'][0] in 'AB']
    with_verdict = [r for r in core if r['verdict'] != NOT_CHECKABLE and r['verdict'] != 'not audited'
                    and not r['verdict'].startswith('turns on') and not r['verdict'].startswith('different design')]
    return len(with_verdict), len(core)
