"""Minimal dependency-free SVG line/band/point charts for the QA record."""
import math
from xml.sax.saxutils import escape

PALETTE = ['#1f6feb', '#d1242f', '#1a7f37', '#9a6700', '#8250df', '#57606a', '#bf3989', '#0a7ea4']


def _ticks(lo, hi, count=6):
    raw = ((hi - lo) or 1.0) / count
    magnitude = 10.0 ** math.floor(math.log10(raw))
    step = next(m * magnitude for m in (1, 2, 5, 10) if m * magnitude >= raw)
    first = math.ceil(lo / step - 1e-9)
    return [round(i * step, 10) for i in range(first, math.floor(hi / step + 1e-9) + 1)]


def chart(path, *, title, xlabel, ylabel, series, width=860, height=460, note=''):
    """series: dicts with label, kind ('line' | 'points' | 'band'), points [(x, y)] or [(x, lo, hi)]."""
    left, right, top, bottom = 70, 20, 44, 104
    xs = [p[0] for s in series for p in s['points']]
    ys = [v for s in series for p in s['points'] for v in p[1:]]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    pad = (y1 - y0) * 0.06 or 1.0
    y0, y1 = y0 - pad, y1 + pad

    def px(x):
        return left + (x - x0) / ((x1 - x0) or 1.0) * (width - left - right)

    def py(y):
        return height - bottom - (y - y0) / (y1 - y0) * (height - top - bottom)

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" font-family="Helvetica,Arial,sans-serif" font-size="12">',
           f'<rect width="{width}" height="{height}" fill="#ffffff"/>',
           f'<text x="{left}" y="24" font-size="15" font-weight="bold">{escape(title)}</text>']
    for tick in _ticks(y0, y1):
        out.append(f'<line x1="{left}" x2="{width - right}" y1="{py(tick):.1f}" y2="{py(tick):.1f}" stroke="#d0d7de"/>')
        out.append(f'<text x="{left - 6}" y="{py(tick) + 4:.1f}" text-anchor="end">{tick:g}</text>')
    for tick in _ticks(x0, x1, 8):
        out.append(f'<line x1="{px(tick):.1f}" x2="{px(tick):.1f}" y1="{height - bottom}" y2="{height - bottom + 5}" stroke="#57606a"/>')
        out.append(f'<text x="{px(tick):.1f}" y="{height - bottom + 18}" text-anchor="middle">{tick:g}</text>')
    out.append(f'<rect x="{left}" y="{top}" width="{width - left - right}" height="{height - top - bottom}" fill="none" stroke="#57606a"/>')
    out.append(f'<text x="{(left + width - right) / 2}" y="{height - bottom + 36}" text-anchor="middle">{escape(xlabel)}</text>')
    out.append(f'<text transform="translate(16 {(top + height - bottom) / 2}) rotate(-90)" text-anchor="middle">{escape(ylabel)}</text>')
    legend_x, legend_y = left, height - 54
    for index, s in enumerate(series):
        colour = s.get('colour', PALETTE[index % len(PALETTE)])
        points = s['points']
        if s['kind'] == 'band':
            upper = ' '.join(f'{px(x):.1f},{py(hi):.1f}' for x, _, hi in points)
            lower = ' '.join(f'{px(x):.1f},{py(lo):.1f}' for x, lo, _ in reversed(points))
            out.append(f'<polygon points="{upper} {lower}" fill="{colour}" fill-opacity="0.18" stroke="none"/>')
        elif s['kind'] == 'line':
            path_d = ' '.join(f'{px(x):.1f},{py(y):.1f}' for x, y in points)
            dash = ' stroke-dasharray="6 4"' if s.get('dashed') else ''
            out.append(f'<polyline points="{path_d}" fill="none" stroke="{colour}" stroke-width="2"{dash}/>')
        else:
            fill = colour if s.get('filled', True) else '#ffffff'
            out += [f'<circle cx="{px(x):.1f}" cy="{py(y):.1f}" r="4" fill="{fill}" stroke="{colour}" stroke-width="1.5"/>'
                    for x, y in points]
        entry = 30 + 6.6 * len(s['label'])
        if legend_x + entry > width - right and legend_x > left:
            legend_x, legend_y = left, legend_y + 17
        out.append(f'<rect x="{legend_x}" y="{legend_y - 9}" width="14" height="10" fill="{colour}" fill-opacity="{0.25 if s["kind"] == "band" else 1}"/>')
        out.append(f'<text x="{legend_x + 19}" y="{legend_y}">{escape(s["label"])}</text>')
        legend_x += entry
    if note:
        out.append(f'<text x="{width - right}" y="{height - 4}" text-anchor="end" font-size="10" fill="#57606a">{escape(note)}</text>')
    out.append('</svg>')
    with open(path, 'w') as handle:
        handle.write('\n'.join(out) + '\n')
