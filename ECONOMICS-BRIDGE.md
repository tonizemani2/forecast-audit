# From the decline record to cost per megawatt-hour

`[MODEL]` — copied from the registered constraint ledger of 19 November 2026
(`bridge.json`), not recomputed by `reproduce.py`. Reference plants, flow
re-optimised at each point, 8 % real discount rate, no recharge. These rank
inputs; they are not forecasts of any plant.

| Plant | Cost | Net MW per producer | What moves it most (low → high) |
|---|---:|---:|---|
| Enhanced geothermal, 200 °C, binary | **$218/MWh** | 3.6 | well cost ±30 %: 182–254 · discount rate 6–10 %: 193–247 · surface plant ±30 %: 192–243 · swept fraction 0.32–0.63: 246–205 |
| Enhanced geothermal, 300 °C, flash-binary | **$147/MWh** | 9.1 | well cost: 124–170 · surface: 129–165 · discount rate: 130–166 · swept fraction: 170–135 |
| Superhot, 425 °C | **$112/MWh** | 27.2 | well cost: 96–129 · swept fraction: 131–102 · surface: 98–127 · well life 8–30 years: 134–112 |

Three readings.

1. The model reproduces the first commercial plant's vendor-stated $7,000 per
   kW within 2 %. At an 8 % real return that is $219–257/MWh. The public
   argument about returns is this number.
2. **Swept fraction is the one input that moves both cost and build rate.**
   It is what the Project Red record measures (0.32–0.63), and what the
   registered forecasts will test.
3. **Temperature buys the largest step**: output per well rises 7.5-fold
   from 200 °C to 425 °C and cost falls by half — and at 425 °C **well life**
   enters the list of largest swings for the first time ($134 at 8 years,
   $112 at 30). A superhot well that fails early gives the gain back. That is
   why the next release is a qualification basis for wells and instruments
   above 375 °C.

None of the three reaches the prices usually quoted for firm power in 2030 or
2040 at these inputs. Published targets for superhot rock ($20–30/MWh) assume
well costs, lifetimes and reservoir behaviour that no public record yet
shows; this model does not reproduce them and does not claim them.
