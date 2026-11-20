# Registered forecasts — thermal-sweep campaign

Registered 2026-11-19. `[MODEL]`. Protocol and falsifiers: `software/thermal-sweep/PLAN.md` §6.
Scoring replays the locked ensemble with the actual published flows and injection temperatures.
Ensemble: 21 accepted runs of 1440 (RMSE ≤ 1.00 °F on 9 fit months).

## F1 — Project Red wellhead temperature, monthly mean (°F)

Assumed drive: 25.3 M gal/month produced, 34.1 M gal/month injected. Band = ensemble p10–p90 ± 1 °F.

| Month | cold reinjection 88 °F: p10 / median / p90 | warm reinjection 170 °F: p10 / median / p90 |
|---|---|---|
| 2026-08 | 325.2 / 328.1 / 331.6 | 325.2 / 328.1 / 331.6 |
| 2026-09 | 322.2 / 325.5 / 329.5 | 322.2 / 325.5 / 329.5 |
| 2026-10 | 319.2 / 323.0 / 327.5 | 319.2 / 323.1 / 327.6 |
| 2026-11 | 316.2 / 320.6 / 325.6 | 316.3 / 320.8 / 325.9 |
| 2026-12 | 313.0 / 318.1 / 323.6 | 313.3 / 318.5 / 324.2 |
| 2027-01 | 309.7 / 315.5 / 321.6 | 310.1 / 315.8 / 322.5 |
| 2027-02 | 306.4 / 313.0 / 319.7 | 307.0 / 313.2 / 320.9 |
| 2027-03 | 303.0 / 310.2 / 317.8 | 303.9 / 310.5 / 319.4 |
| 2027-04 | 299.4 / 307.2 / 315.8 | 300.5 / 308.2 / 317.8 |
| 2027-05 | 295.7 / 304.2 / 313.7 | 297.1 / 306.1 / 316.2 |
| 2027-06 | 291.8 / 301.0 / 311.7 | 293.7 / 304.0 / 314.6 |
| 2027-07 | 287.9 / 298.0 / 309.6 | 290.1 / 301.9 / 313.0 |
| 2027-08 | 283.8 / 295.3 / 307.5 | 286.5 / 299.9 / 311.3 |
| 2027-09 | 279.6 / 292.6 / 305.4 | 282.9 / 297.8 / 309.7 |
| 2027-10 | 275.4 / 289.9 / 303.3 | 279.2 / 295.4 / 308.1 |
| 2027-11 | 271.1 / 287.3 / 301.2 | 275.5 / 293.1 / 306.4 |
| 2027-12 | 266.8 / 284.6 / 299.0 | 271.9 / 291.2 / 304.8 |

## F2 — Project Red decline from the 347 °F plateau at the 12th forecast month

- cold-reinjection (2027-07): 37.4 / 49.0 / 59.1 °F (p10 / median / p90)
- warm-reinjection (2027-07): 34.0 / 45.1 / 56.9 °F (p10 / median / p90)

## F3 — Utah FORGE 2026 test, commingled reservoir-outlet cooling (K)

Relative to the first-ten-day maximum; 9.5 bpm × 0.85, 65 °C injection, 215 °C rock.
Members with more than 4 K modelled cooling over days 10–27 of the 2024 test are removed (amendment A1).

| Hypothesis | retained weight | day 60 | day 90 | day 120 | rate d100–120 (K/day) | P(≥1 K by day 120) |
|---|---|---|---|---|---|---|
| H_T | 113 of 126 | -0.00 / 0.04 / 3.46 | -0.01 / 0.20 / 6.46 | -0.02 / 0.51 / 9.56 | -0.000 / 0.011 / 0.087 | 0.42 |
| tracer-area | 36 of 36 | -0.00 / -0.00 / 0.45 | -0.01 / -0.00 / 1.29 | -0.02 / -0.00 / 2.38 | -0.000 / -0.000 / 0.037 | 0.19 |

## F4 — Utah FORGE, stage contributing most to commingled cooling at day 120 (members ≥ 0.5 K)

- H_T: {'10': 22, '8': 4, '9': 24, 'toe': 7}
- tracer-area: {'10': 6, '9': 2}

## F5 — Cape-class producer side (public reconstruction), 50 kg/s per side

| Nominal height | months to sustained 2 °F decline (p10 / median / p90) | months to 10 % of ΔT | geometry as stated: 2 °F / 10 % |
|---|---|---|---|
| 143.0 m | 10.0 / 16.0 / 24.0 | 36.0 / 41.0 / 53.0 | 84 / 106 |
| 228.0 m | 26.0 / 41.0 / 61.0 | 67.0 / 81.0 / 103.0 | 145 / 175 |

Limits: `software/thermal-sweep/PLAN.md` §9. A calibrated model is not a validated one; these
forecasts exist to be scored.
