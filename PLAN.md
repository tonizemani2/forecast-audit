# Release 1 — forecast and audit record: packaging plan and acceptance gates

19 November 2026 · frozen before the release is built or run; time-stamped
copy in `qa/release-forecast-audit-2026-11-19-plan-freeze/`. Executes WP-2 of
the North Star execution brief. This is packaging of results that already
exist in registered records; no model is changed and no forecast is touched.

## What the release must do

From a clean copy with only the Python standard library, one command

    python3 reproduce.py

pulls the Nevada Division of Minerals workbook from the regulator's public
URL, extracts the Project Red well pair (permits 1506 / 1505), re-fits the
conduction model, recomputes the water balance, regenerates every row of the
claim audit with its verdict, checks the registered forecast hashes and writes
labelled machine-readable results — in under 60 s, with no manual step.

## Sources copied, never edited

Byte-identical copies of `fieldmodel.py`, `sweep.py`, `extract_ndom.py`,
`scoring.py`, `svgchart.py` (from `software/thermal-sweep/`) and
`retention.py` (from `software/water-retention/`), in the same relative
layout, with their SHA-256 listed against the registered manifests. The
registered packages themselves are not touched.

## Gates (decided before the first run)

| Gate | Statistic | Pass |
|---|---|---|
| P1 fit | best-fit RMSE on the nine fit months, and the best-fit parameter set, against `qa/thermal-sweep-2026-11-19/match.json` (0.50855 °F) | same parameter set; RMSE within 0.1 °F |
| P2 ensemble | every registered accepted member (21) re-run; each RMSE within 0.1 °F of its registered value; median area ratio | within 0.1 °F each; median 0.474 within 0.005 |
| P3 water | recapture over the steady months by mass and by volume, and cumulative injected minus produced volume, against `qa/water-retention-2026-11-19` (65.9 %, 72.7 %, 192.9 M gal) | each within 0.5 % relative |
| P4 audit | every row of the claim audit is regenerated; each row computed from the workbook reproduces the numbers printed in `company/CLAIM-AUDIT-FERVO-2026-11-19.md` to their printed precision, and its verdict follows from a rule written in the code | all rows present; every computed number matches |
| P5 source | fresh extract from the downloaded workbook equals the registered extract month for month (new later months are reported, never fitted) | identical on the registered months |
| P6 runtime | wall time of the one command in a temporary directory outside the repository | < 60 s |
| P7 standard library | the command runs with `python3 -I -S` semantics (no site packages) | no third-party import |
| P8 forecasts | SHA-256 of each bundled registered forecast equals the registered manifest; both time-stamp tokens verify against the file | all equal; tokens present |

**Hold rule (from the brief):** a difference above 0.1 °F or 0.5 % against
the registered record is fixed in this package, or the affected claim is
withdrawn from the release. A row whose printed number does not reproduce is
corrected in the public audit with a dated note; the private audit is not
rewritten.

## Contents

`reproduce.py`, `audit.py`, copied model files, the registered extract and
`SOURCES.json`; `registered/` (forecast files, statements, manifests and
RFC 3161 tokens of the thermal-sweep, sweep-fleet and water-retention
records); `AUDIT.md` (public text of the audit); `FAILED-CAMPAIGNS.md` (every
failed gate of the forecasting line, beside the passes); `ECONOMICS-BRIDGE.md`
and `bridge.json` (`[MODEL]` cost per MWh at 200, 300 and 425 °C from the
registered ledger, copied with labels, not recomputed here); `README.md`,
`LICENSE`, `CITATION.cff`, `llms.txt`, `results.schema.json`, tests.

Not in the release: any hardware design, control method, flow-control
valuation (`conformance.py`, its trials and figures), internal plans, names of
people, prices or offers.

## Disclosure

The audit names a listed company and gives verdicts on both sides. Building
the release is not publishing it; publication is the owner's decision
(`next-stage/HUMAN-QUEUE.md` item 32).
