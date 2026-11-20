# Forecast and audit record for the first enhanced-geothermal production history — v1

One public production history exists for an enhanced geothermal doublet:
Project Red in Nevada, reported monthly to the Nevada Division of Minerals.
This repository reads that record and nothing else, and does four things with
it. Everything runs with the Python standard library.

    python3 reproduce.py

pulls the regulator's workbook from its public URL and, in a few seconds:

1. **Refits a conduction model** of the fractured rock to the nine steady
   months. Root-mean-square error **0.51 °F** (`[MODEL]`, calibrated to
   operator-reported data; calibration is not validation). The record fits
   only if **32–63 % of the stated fracture area exchanges heat** (10th–90th
   percentile of the accepted ensemble, median 0.47).
2. **Recomputes the water balance** of the well pair: **65.9 % of injected
   mass returns** (72.7 % by volume) over 18 steady months, and the ratio has
   not moved in 2.3 years (+0.2 ± 1.5 points per year). Injected minus
   produced since December 2023: 192.9 million gallons (`measured`).
3. **Regenerates a 33-row audit** of what a short seller and the operator
   said about this well pair in 2026, each row with the record's number and a
   verdict that follows from a rule in `audit.py`. 18 of the 24 rows on
   temperature and water get a data verdict; both sides are right on some and
   wrong on others. See `AUDIT.md`.
4. **Checks the registered forecasts.** Six temperature forecasts and one
   water forecast were frozen, hashed and time-stamped by two independent
   authorities on 19 November 2026, before the months they describe exist
   (`registered/`). They are scored against later regulator workbooks, hit or
   miss. State today: **pending**.

## What failed

The same kind of model was tested on 100 older Nevada wells and lost four of
five gates set in advance. A repair passed on development wells and failed on
sealed ones. A calibration gate on the water forecast failed. All of it is in
`FAILED-CAMPAIGNS.md`, beside the passes, because a forecast record is only
worth reading if its losses are in it.

## Files

| Path | What |
|---|---|
| `reproduce.py` | the one command; writes `out/results.json`, `out/audit.json`, `out/AUDIT.md`, two SVG figures |
| `audit.py` | every audit row and its verdict rule |
| `software/thermal-sweep/`, `software/water-retention/` | model code, byte-identical to the registered packages (hashes in `registered/*/manifest.json`) |
| `registered/` | forecast files, statements, manifests, RFC 3161 time-stamp tokens |
| `AUDIT.md` | the audit as text |
| `FAILED-CAMPAIGNS.md` | every failed gate |
| `ECONOMICS-BRIDGE.md`, `bridge.json` | what the decline means for cost per MWh at 200, 300 and 425 °C (`[MODEL]`) |
| `results.schema.json`, `llms.txt`, `CITATION.cff` | for machines and citations |
| `test_release.py` | `python3 -m unittest test_release` (offline) |

## Labels

`measured` = the regulator's record, operator-reported and unaudited.
`[MODEL]` = computed here. `vendor-stated` = quoted from a company.
`registered` = frozen and time-stamped before the data existed.
Nothing here is investment advice or a statement about anyone's intent.

## Limits

One well pair. Monthly means. A two-well ratio inside an operating field is
not a closed water balance. Mass figures use an extrapolated density fit.
The forecasts can lose; the next workbook decides.

## Licence

Code: MIT. Text, tables and figures: CC BY 4.0. Regulator data: public record
of the State of Nevada, reproduced verbatim with its source URL.
