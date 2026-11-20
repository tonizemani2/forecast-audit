"""Coupled parallel-fracture heat sweep.

Rock slabs between neighbouring fractures conduct normal to the fracture
planes; fluid is quasi-steady along the injector-to-producer path. Equations,
assumptions and limits: PLAN.md section 3. SI units; temperatures in deg C.
"""
import math
import random
from statistics import NormalDist

CW = 4350.0          # J/(kg K), liquid water averaged over 75-200 C
YEAR = 365.25 * 86400
MONTH = YEAR / 12


def viscosity(t_c):
    """Liquid water dynamic viscosity, Pa s."""
    return 2.414e-5 * 10 ** (247.8 / (t_c + 273.15 - 140.0))


def graded(thickness, cells, ratio, symmetric):
    """Cell widths growing geometrically away from a fracture face."""
    if symmetric:
        if cells % 2:
            raise ValueError('symmetric slabs need an even cell count')
        half = [ratio ** j for j in range(cells // 2)]
        widths = half + half[::-1]
    else:
        widths = [ratio ** j for j in range(cells)]
    scale = thickness / sum(widths)
    return [w * scale for w in widths]


class Sweep:
    """N fractures separated by `gaps`; state is rock temperature per layer, station, cell."""

    def __init__(self, gaps, *, path_m, height_m, t_rock_c, k_rock=2.9, rho_c=2.55e6, cw=CW,
                 ns=12, ny=8, grading=1.5, end_m=40.0, end_cells=10, layers=None, n_layers=1):
        self.n = len(gaps) + 1
        if min(gaps, default=1.0) <= 0 or path_m <= 0 or height_m <= 0:
            raise ValueError('positive geometry required')
        self.kappa = [n_layers] * self.n if layers is None else list(layers)
        if len(self.kappa) != self.n or any(not 1 <= k <= n_layers for k in self.kappa):
            raise ValueError('one wetted-layer count in 1..n_layers per fracture')
        self.ns, self.n_layers, self.cw, self.t_rock = ns, n_layers, cw, float(t_rock_c)
        self.path_m, self.height_m = path_m, height_m
        area = (path_m / ns) * (height_m / n_layers)          # one face of one station-layer cell
        widths = graded(end_m, end_cells, grading, False)[::-1]
        self.iface = []                                        # left cell index of each fracture
        for gap in gaps:
            self.iface.append(len(widths) - 1)
            widths += graded(gap, ny, grading, True)
        self.iface.append(len(widths) - 1)
        widths += graded(end_m, end_cells, grading, False)
        self.m = len(widths)
        self.capacity = [rho_c * w * area for w in widths]
        self.link = [k_rock * area / ((widths[c] + widths[c + 1]) / 2) for c in range(self.m - 1)]
        self.g_left = [k_rock * area / (widths[p] / 2) for p in self.iface]
        self.g_right = [k_rock * area / (widths[p + 1] / 2) for p in self.iface]
        for p in self.iface:
            self.link[p] = 0.0                                 # replaced by the fracture coupling
        self.temp = [[[self.t_rock] * self.m for _ in range(ns)] for _ in range(n_layers)]
        self.elapsed_s = 0.0
        self.heat_j = 0.0
        self._cache = {}

    def stored_j(self):
        """Rock sensible heat relative to 0 deg C."""
        return math.fsum(c * t for layer in self.temp for station in layer
                         for c, t in zip(self.capacity, station))

    def wetted_area_m2(self):
        """Total one-sided wetted fracture face area."""
        return self.path_m * self.height_m * sum(self.kappa) / self.n_layers

    def _factor(self, layer, flows, dt):
        key = (layer, dt, tuple(flows))
        cached = self._cache.get(layer)
        if cached and cached[0] == key:
            return cached[1]
        m, link = self.m, self.link
        cdt = [c / dt for c in self.capacity]
        diag = [cdt[c] + (link[c - 1] if c else 0.0) + (link[c] if c < m - 1 else 0.0) for c in range(m)]
        off = [-g for g in link]
        src_l, src_r, expo, w_l, w_r = [], [], [], [], []
        for i, p in enumerate(self.iface):
            gl, gr = self.g_left[i], self.g_right[i]
            gs = gl + gr
            if flows[i] > 0:
                ntu = gs / (flows[i] * self.cw)
                e = math.exp(-ntu)
                beta = -math.expm1(-ntu) / ntu
            else:
                e, beta = 0.0, 0.0
            diag[p] += gl * (1 - (1 - beta) * gl / gs)
            diag[p + 1] += gr * (1 - (1 - beta) * gr / gs)
            off[p] = -(1 - beta) * gl * gr / gs
            src_l.append(gl * beta)
            src_r.append(gr * beta)
            expo.append(e)
            w_l.append(gl / gs)
            w_r.append(gr / gs)
        ratio = [0.0] * m
        for c in range(1, m):
            ratio[c] = off[c - 1] / diag[c - 1]
            diag[c] -= ratio[c] * off[c - 1]
        factors = (cdt, ratio, diag, off, src_l, src_r, expo, w_l, w_r)
        self._cache[layer] = (key, factors)
        return factors

    def step(self, flows_kg_s, t_inj_c, dt_s):
        """Advance one backward-Euler step; flows are total mass flow per fracture."""
        if len(flows_kg_s) != self.n or min(flows_kg_s) < 0 or dt_s <= 0:
            raise ValueError('one nonnegative flow per fracture and a positive step required')
        n, m, ns, iface = self.n, self.m, self.ns, self.iface
        outlet_sum = [0.0] * n
        wall_sum = [0.0] * n
        fluid_sum = [0.0] * n
        for layer in range(self.n_layers):
            flows = [f / k if layer < k else 0.0 for f, k in zip(flows_kg_s, self.kappa)]
            cdt, ratio, diag, off, src_l, src_r, expo, w_l, w_r = self._factor(layer, flows, dt_s)
            active = [i for i in range(n) if flows[i] > 0]
            t_in = [t_inj_c] * n
            for station in range(ns):
                old = self.temp[layer][station]
                x = [a * b for a, b in zip(cdt, old)]
                for i in active:
                    p = iface[i]
                    x[p] += src_l[i] * t_in[i]
                    x[p + 1] += src_r[i] * t_in[i]
                for c in range(1, m):
                    x[c] -= ratio[c] * x[c - 1]
                x[m - 1] /= diag[m - 1]
                for c in range(m - 2, -1, -1):
                    x[c] = (x[c] - off[c] * x[c + 1]) / diag[c]
                self.temp[layer][station] = x
                for i in active:
                    p = iface[i]
                    wall = w_l[i] * x[p] + w_r[i] * x[p + 1]
                    out = wall + (t_in[i] - wall) * expo[i]
                    wall_sum[i] += wall
                    fluid_sum[i] += (t_in[i] + out) / 2
                    t_in[i] = out
            for i in active:
                outlet_sum[i] += t_in[i]
        outlet, wall, fluid = [], [], []
        for i in range(n):
            wet = self.kappa[i] if flows_kg_s[i] > 0 else 0
            outlet.append(outlet_sum[i] / wet if wet else None)
            wall.append(wall_sum[i] / (wet * ns) if wet else None)
            fluid.append(fluid_sum[i] / (wet * ns) if wet else None)
        total = math.fsum(flows_kg_s)
        mixed = math.fsum(f * t for f, t in zip(flows_kg_s, outlet) if t is not None) / total if total else None
        heat = math.fsum(f * self.cw * (t - t_inj_c) for f, t in zip(flows_kg_s, outlet) if t is not None) * dt_s
        self.elapsed_s += dt_s
        self.heat_j += heat
        return dict(outlet_c=outlet, wall_c=wall, fluid_c=fluid, mixed_c=mixed, heat_j=heat, flow_kg_s=total)


# ---- verification targets -------------------------------------------------

def theta_single(t_s, *, k_rock, area_m2, flow_kg_s, alpha, cw=CW):
    """(T_rock - T_out)/(T_rock - T_in) for one fracture in unbounded rock; area is one face."""
    return math.erfc(k_rock * area_m2 / (flow_kg_s * cw * math.sqrt(alpha * t_s)))


def _stehfest(order=12):
    half = order // 2
    weights = []
    for i in range(1, order + 1):
        total = 0.0
        for k in range((i + 1) // 2, min(i, half) + 1):
            total += (k ** half * math.factorial(2 * k)
                      / (math.factorial(half - k) * math.factorial(k) * math.factorial(k - 1)
                         * math.factorial(i - k) * math.factorial(2 * k - i)))
        weights.append((-1) ** (half + i) * total)
    return weights


_WEIGHTS = _stehfest()


def theta_spaced(t_s, *, k_rock, area_m2, flow_kg_s, alpha, half_spacing_m, cw=CW):
    """Same quantity for an infinite array of equal fractures (Gaver-Stehfest inversion)."""
    a = 2 * k_rock * area_m2 / (flow_kg_s * cw * math.sqrt(alpha))
    b = half_spacing_m / math.sqrt(alpha)
    ln2_t = math.log(2) / t_s
    total = 0.0
    for i, weight in enumerate(_WEIGHTS, 1):
        s = i * ln2_t
        root = math.sqrt(s)
        total += weight * math.exp(-a * root * math.tanh(b * root)) / s
    return ln2_t * total


# ---- heterogeneity and hydraulics -----------------------------------------

def lognormal_shares(n, sigma, seed):
    """Deterministic log-normal quantile weights summing to one, in a seeded order."""
    normal = NormalDist()
    weights = [math.exp(sigma * normal.inv_cdf((i + 0.5) / n)) for i in range(n)]
    random.Random(seed).shuffle(weights)
    total = math.fsum(weights)
    return [w / total for w in weights]


def gini(values):
    """Gini coefficient of nonnegative values (0 = equal)."""
    ordered = sorted(values)
    n, total = len(ordered), math.fsum(ordered)
    if not total:
        return 0.0
    return 2 * math.fsum((i + 1) * v for i, v in enumerate(ordered)) / (n * total) - (n + 1) / n


def split(total_kg_s, linear, quadratic, dp_max_pa):
    """Flows through parallel paths sharing one differential dp = r q + a q^2.

    Returns (flows, dp). If dp_max cannot pass the requested total, the pump is
    pressure-limited and the total falls.
    """
    def flows(dp):
        return [2 * dp / (r + math.sqrt(r * r + 4 * a * dp)) for r, a in zip(linear, quadratic)]
    if math.fsum(flows(dp_max_pa)) <= total_kg_s:
        return flows(dp_max_pa), dp_max_pa
    lo, hi = 0.0, dp_max_pa
    for _ in range(60):
        mid = (lo + hi) / 2
        if math.fsum(flows(mid)) > total_kg_s:
            hi = mid
        else:
            lo = mid
    return flows(hi), hi
