# Failed campaigns, beside the passes

Every campaign below had its plan, gates and falsifiers frozen and
time-stamped before its run. Numbers are `[MODEL]` on `measured`
(operator-reported) regulator data unless marked `SIMULATED`.

| Campaign (19 Nov 2026) | Question | Gate results | Outcome |
|---|---|---|---|
| Project Red calibration and hindcast | does a conduction model hold on months it has not seen? | fit 0.51 °F on nine months; hindcasts five of five and three of three months inside the band | **passed**; five forecasts registered (F1–F5) |
| Fleet hindcast, 100 Nevada wells | does a one-path version forecast long-lived wells? | beats "no change" in 44 % of wells (needed 60 %): **fail** · beats a straight line in 34 % (50 %): **fail** · 32 % of held-out months inside the 80 % band (70–90 %): **fail** · saw 15 % of real declines (60 %): **fail** · false alarms on flat wells 18 % (≤ 20 %): pass | **four of five gates failed.** Median error 6.0 °F against 3.5 °F for a straight line. Forecast F6 registered anyway, with its falsifier |
| Fleet repair | can a drawdown term and calibrated bands fix it? | passed all six gates on 41 development wells; on 48 sealed wells: four pass, false alarms on flat wells 29 % (≤ 20 %): **fail**, beats the Arps decline curve in 38 % of wells (≥ 50 %): **fail** | **failed on sealed wells.** No new fleet forecast registered |
| Water recapture forecast | does any of four simple hypotheses beat "same as last year"? | skill: 2.9 points error against 4.6: pass · calibration: six of six held-out months inside a band meant to hold five: **fail** | **calibration gate failed.** The comparator is registered as baseline W0 |
| Transfer to a second site (EGS Collab) | does the Project Red fraction predict a 10 m experiment? | modelled cooling 0.01 K against a 2 K bound | **test without power**: not rejected, nothing learned |
| Chemical flow conformance as a general product (`SIMULATED`) | does a temperature-switching fluid beat simply running slower? | three of five gates failed on sealed cases | **stopped** by the frozen rule |

What the failures say: wellhead temperature alone does not forecast a fleet;
the Project Red result is one calibrated site, not a method proven across
fields; and the water ratio is forecastable only as "about what it was".

Full records (plans, sealed results, time-stamp tokens) are held with SHA-256
manifests; `registered/sweep-fleet/` carries the fleet record and its hindcast.
