"""One command: pull the regulator workbook, refit, rebalance the water, regenerate the audit.

    python3 reproduce.py                 # downloads the Nevada workbook, writes out/
    python3 reproduce.py --workbook X    # use a workbook already on disk
    python3 reproduce.py --offline       # use the bundled extract (no network)
    python3 reproduce.py --full-grid     # also repeat the 1,440-run search (minutes)

Standard library only. Every number in out/results.json carries a label:
measured (regulator record, operator-reported) / [MODEL] / registered.
"""
import argparse
import hashlib
import itertools
import json
import multiprocessing
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / 'software/thermal-sweep'))

import audit                                                           # noqa: E402
import extract_ndom                                                    # noqa: E402
import fieldmodel as fm                                                # noqa: E402
from scoring import quantile                                           # noqa: E402
from svgchart import chart                                             # noqa: E402

DATA = HERE / 'software/thermal-sweep/data'
REGISTERED = HERE / 'registered'
TOL_F, TOL_REL = 0.1, 0.005
PRINTED_WATER = {'recapture_mass': 0.659, 'recapture_volume': 0.727, 'cumulative_injected_minus_produced_gal': 192.9e6}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def num(value, unit, label):
    return {'value': value, 'unit': unit, 'label': label}


def _misfit(job):
    params, records = job
    r = fm.red_misfit(params, records)
    return {'params': params, 'rmse_f': r['rmse_f'], 'wellhead_f': r['wellhead_f']}


def neighbours(best):
    out = []
    for name, values in fm.RED_GRID.items():
        i = values.index(best[name])
        for j in (i - 1, i + 1):
            if 0 <= j < len(values):
                out.append(dict(best, **{name: values[j]}))
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--out', type=Path, default=Path('out'))
    parser.add_argument('--workbook', type=Path)
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--full-grid', action='store_true')
    args = parser.parse_args()
    started = time.time()
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / 'figures').mkdir(exist_ok=True)
    source = json.loads((DATA / 'SOURCES.json').read_text())['sources']['S1']
    bundled = extract_ndom.read_csv(DATA / 'project-red-ndom-monthly.csv')
    checks = {}

    # 1. the regulator workbook
    if args.offline:
        records, workbook = bundled, {'mode': 'offline: bundled extract', 'sha256': None}
    else:
        path = args.workbook
        if path is None:
            path = args.out / 'ndom-workbook.xlsx'
            with urllib.request.urlopen(source['url'], timeout=40) as reply:
                path.write_bytes(reply.read())
        digest = sha(path)
        fresh = extract_ndom.well_pair(path)
        records = fresh[:len(bundled)]
        workbook = {'mode': 'downloaded' if args.workbook is None else 'local file', 'url': source['url'], 'sha256': digest,
                    'same_file_as_registered': digest == source['sha256'], 'months': len(fresh),
                    'months_after_registered_record': [r['month_end'] for r in fresh[len(bundled):]]}
        checks['P5_extract_equals_registered'] = records == bundled
    registered_match = json.loads((REGISTERED / 'thermal-sweep/match.json').read_text())
    best_params = registered_match['summary']['best']['params']
    accepted = registered_match['accepted']

    # 2. the fit: best member, its grid neighbours, every accepted member (or the whole grid)
    jobs = [best_params] + neighbours(best_params) + [a['params'] for a in accepted]
    if args.full_grid:
        jobs = [dict(zip(fm.RED_GRID, v)) for v in itertools.product(*fm.RED_GRID.values())]
    with multiprocessing.Pool(max(1, multiprocessing.cpu_count() - 1)) as pool:
        runs = pool.map(_misfit, [(p, records) for p in jobs], chunksize=1)
    key = lambda p: json.dumps(p, sort_keys=True)
    by_params = {key(r['params']): r for r in runs}
    best = by_params[key(best_params)]
    lowest = min(runs, key=lambda r: r['rmse_f'])
    member_diffs = [abs(by_params[key(a['params'])]['rmse_f'] - a['rmse_f']) for a in accepted]
    ratios = [a['area_ratio'] for a in accepted]
    months = fm.fit_months(records)
    checks['P1_same_best_parameters'] = key(lowest['params']) == key(best_params)
    checks['P1_rmse_within_0.1F'] = abs(best['rmse_f'] - registered_match['summary']['best']['rmse_f']) <= TOL_F
    checks['P2_every_accepted_member_within_0.1F'] = max(member_diffs) <= TOL_F
    checks['P2_median_area_ratio'] = abs(quantile(ratios, 0.5) - 0.474) <= 0.005

    # 3. water
    water = audit.water(records)
    water_diff = {k: abs(water[k] - v) / v for k, v in PRINTED_WATER.items()}
    checks['P3_water_within_0.5pct'] = max(water_diff.values()) <= TOL_REL

    # 4. the audit
    rows = audit.rows(records)
    settled, core = audit.settled(rows)
    checks['P4_all_rows_present'] = len(rows) == 33

    # 5. registered forecasts
    forecasts = {}
    for name in ('thermal-sweep', 'sweep-fleet', 'water-retention'):
        manifest = json.loads((REGISTERED / name / 'manifest.json').read_text())
        digest = sha(REGISTERED / name / 'forecast.json')
        tokens = {t: (REGISTERED / name / f'forecast.json.{t}.tsr').stat().st_size > 0
                  and manifest['results'].get(f'forecast.json.{t}.tsr', sha(REGISTERED / name / f'forecast.json.{t}.tsr'))
                  == sha(REGISTERED / name / f'forecast.json.{t}.tsr') for t in ('freetsa', 'digicert')}
        forecasts[name] = {'forecast_sha256': digest, 'equals_registered_manifest': digest == manifest['results']['forecast.json'],
                           'rfc3161_tokens_match_manifest': tokens, 'state': 'PENDING until a later regulator workbook'}
    checks['P8_forecast_hashes'] = all(f['equals_registered_manifest'] and all(f['rfc3161_tokens_match_manifest'].values())
                                       for f in forecasts.values())

    # 6. figures
    year = lambda r: int(r['month_end'][:4]) + (int(r['month_end'][5:7]) - 0.5) / 12
    flowing = [i for i, v in enumerate(best['wellhead_f']) if v is not None]
    chart(args.out / 'figures/project-red-fit.svg', title='Project Red wellhead temperature: regulator record and refit model',
          xlabel='year', ylabel='deg F, monthly mean',
          series=[{'label': 'regulator record (measured)', 'kind': 'points', 'points': [(year(records[i]), records[i]['production_temp_f']) for i in flowing]},
                  {'label': 'fit months', 'kind': 'points', 'points': [(year(records[i]), records[i]['production_temp_f']) for i in months]},
                  {'label': 'model, best member [MODEL]', 'kind': 'line', 'points': [(year(records[i]), best['wellhead_f'][i]) for i in flowing]}],
          note='Calibration is not validation. Operator-reported monthly means.')
    steady = [records[i] for i in audit.retention.steady_months(records)]
    chart(args.out / 'figures/recapture.svg', title='Project Red pair recapture ratio, steady months', xlabel='year', ylabel='produced / injected',
          series=[{'label': 'by volume (measured)', 'kind': 'points', 'points': [(year(r), audit.retention.ratio(r, 'volume')) for r in steady]},
                  {'label': 'by mass [MODEL density]', 'kind': 'points', 'points': [(year(r), audit.retention.ratio(r)) for r in steady]}],
          note='A two-well ratio inside an operating field, not a closed water balance.')

    elapsed = time.time() - started
    checks['P6_under_60s'] = elapsed < 60 or args.full_grid
    result = {
        'release': 'forecast-audit-v1', 'run_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'workbook': workbook,
        'fit': {
            'fit_months': [records[i]['month_end'] for i in months],
            'observed_f': num([records[i]['production_temp_f'] for i in months], 'deg F', 'measured'),
            'fitted_f': num([best['wellhead_f'][i] for i in months], 'deg F', '[MODEL]'),
            'rmse_f': num(best['rmse_f'], 'deg F', '[MODEL] calibrated to measured; calibration is not validation'),
            'registered_rmse_f': num(registered_match['summary']['best']['rmse_f'], 'deg F', 'registered 2026-11-19'),
            'best_parameters': best_params, 'runs': len(runs), 'full_grid': args.full_grid,
            'accepted_members_rerun': len(accepted), 'largest_member_difference_f': num(max(member_diffs), 'deg F', '[MODEL]'),
            'swept_area_ratio': num({'p10': quantile(ratios, 0.1), 'median': quantile(ratios, 0.5), 'p90': quantile(ratios, 0.9)},
                                    'fraction of stated fracture area', '[MODEL] accepted ensemble, registered'),
        },
        'water': {
            'steady_months': water['steady_months'],
            'recapture_by_mass': num(water['recapture_mass'], 'fraction', '[MODEL] density on measured volumes'),
            'recapture_by_volume': num(water['recapture_volume'], 'fraction', 'measured'),
            'cumulative_injected_minus_produced': num(water['cumulative_injected_minus_produced_gal'], 'US gal', 'measured'),
            'trend_by_volume': num(list(water['trend_volume_points_per_year']), 'points per year, slope and standard error', 'measured'),
            'relative_difference_to_registered_print': water_diff,
        },
        'audit': {'rows': len(rows), 'settled_in_sections_A_and_B': settled, 'rows_in_sections_A_and_B': core},
        'registered_forecasts': forecasts, 'checks': checks, 'all_checks_pass': all(checks.values()),
        'runtime_s': round(elapsed, 1),
    }
    (args.out / 'results.json').write_text(json.dumps(result, indent=1) + '\n')
    (args.out / 'audit.json').write_text(json.dumps(rows, indent=1, ensure_ascii=False) + '\n')
    lines = ['# Claim audit — regenerated', '', f'Regenerated {result["run_utc"]} from the regulator workbook. Verdicts are on stated numbers against the stated record, never on intent. No position in any security is held or recommended.', '',
             '| # | Who | Claim | Record | Verdict | Basis |', '|---|---|---|---|---|---|']
    lines += [f"| {r['id']} | {r['who']} | {r['claim']} | {r['record']} | **{r['verdict']}** | {r['basis']} |" for r in rows]
    (args.out / 'AUDIT.md').write_text('\n'.join(lines) + '\n')
    print(f"fit RMSE {best['rmse_f']:.3f} deg F (registered {registered_match['summary']['best']['rmse_f']:.3f}); "
          f"recapture {100 * water['recapture_mass']:.1f} % by mass, {100 * water['recapture_volume']:.1f} % by volume; "
          f"audit rows {len(rows)}, settled {settled} of {core} in A and B")
    for name, ok in checks.items():
        print(('PASS ' if ok else 'FAIL ') + name)
    print(f'{elapsed:.1f} s; results in {args.out}/')
    return 0 if all(checks.values()) else 1


if __name__ == '__main__':
    sys.exit(main())
