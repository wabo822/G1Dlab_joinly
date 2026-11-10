"""Inline SVG charts. No external script, compatible with the CSP."""
from markupsafe import Markup, escape


def line_chart(values, labels=None, width=640, height=180, color='#2066fa'):
    numbers = [float(value or 0) for value in values] or [0.0]
    labels = list(labels or [])
    peak = max(numbers) or 1.0
    pad_x, pad_y = 24, 16
    inner_w = width - pad_x * 2
    inner_h = height - pad_y * 2 - 18
    count = len(numbers)

    def x_at(index):
        if count == 1:
            return width / 2
        return pad_x + inner_w * index / (count - 1)

    def y_at(value):
        return pad_y + inner_h * (1 - (value / peak))

    points = ' '.join(f'{x_at(i):.1f},{y_at(v):.1f}' for i, v in enumerate(numbers))
    area = f'{pad_x:.1f},{pad_y + inner_h:.1f} ' + points + f' {x_at(count - 1):.1f},{pad_y + inner_h:.1f}'
    ticks = []
    step = max(1, count // 6)
    for index in range(0, count, step):
        label = labels[index] if index < len(labels) else ''
        ticks.append(
            f'<text x="{x_at(index):.1f}" y="{height - 2}" text-anchor="middle" font-size="11" fill="#505873">{escape(str(label))}</text>'
        )
    svg = (
        f'<svg class="chart" viewBox="0 0 {width} {height}" width="100%" role="img" aria-hidden="true">'
        f'<polygon fill="{color}22" points="{area}"/>'
        f'<polyline fill="none" stroke="{color}" stroke-width="3" stroke-linejoin="round" stroke-linecap="round" points="{points}"/>'
        + ''.join(ticks) + '</svg>'
    )
    return Markup(svg)


def bar_chart(values, labels=None, width=640, height=200, color='#2066fa'):
    numbers = [float(value or 0) for value in values] or [0.0]
    labels = list(labels or [])
    peak = max(numbers) or 1.0
    pad_x, pad_y = 16, 12
    inner_w = width - pad_x * 2
    inner_h = height - pad_y * 2 - 22
    count = len(numbers)
    gap = 6
    bar_w = max(8, (inner_w - gap * max(count - 1, 0)) / count)
    bars = []
    ticks = []
    for index, value in enumerate(numbers):
        x = pad_x + index * (bar_w + gap)
        h = inner_h * (value / peak)
        y = pad_y + inner_h - h
        bars.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{max(h, 1):.1f}" rx="4" fill="{color}"/>'
        )
        label = labels[index] if index < len(labels) else ''
        if label:
            ticks.append(
                f'<text x="{x + bar_w / 2:.1f}" y="{height - 4}" text-anchor="middle" font-size="10" fill="#505873">{escape(str(label))}</text>'
            )
    svg = (
        f'<svg class="chart" viewBox="0 0 {width} {height}" width="100%" role="img" aria-hidden="true">'
        + ''.join(bars) + ''.join(ticks) + '</svg>'
    )
    return Markup(svg)


def stacked_bar(series_a, series_b, labels=None, width=640, height=200, color_a='#1f7a4d', color_b='#c56a1a'):
    a = [float(value or 0) for value in series_a] or [0.0]
    b = [float(value or 0) for value in series_b] or [0.0]
    if len(b) < len(a):
        b.extend([0.0] * (len(a) - len(b)))
    if len(a) < len(b):
        a.extend([0.0] * (len(b) - len(a)))
    labels = list(labels or [])
    totals = [x + y for x, y in zip(a, b)]
    peak = max(totals) or 1.0
    pad_x, pad_y = 16, 12
    inner_w = width - pad_x * 2
    inner_h = height - pad_y * 2 - 22
    count = len(a)
    gap = 6
    bar_w = max(8, (inner_w - gap * max(count - 1, 0)) / count)
    bars = []
    ticks = []
    for index, (left, right) in enumerate(zip(a, b)):
        x = pad_x + index * (bar_w + gap)
        h_a = inner_h * (left / peak)
        h_b = inner_h * (right / peak)
        y_b = pad_y + inner_h - h_b
        y_a = y_b - h_a
        if h_b:
            bars.append(f'<rect x="{x:.1f}" y="{y_b:.1f}" width="{bar_w:.1f}" height="{h_b:.1f}" rx="3" fill="{color_b}"/>')
        if h_a:
            bars.append(f'<rect x="{x:.1f}" y="{y_a:.1f}" width="{bar_w:.1f}" height="{h_a:.1f}" rx="3" fill="{color_a}"/>')
        label = labels[index] if index < len(labels) else ''
        if label:
            ticks.append(
                f'<text x="{x + bar_w / 2:.1f}" y="{height - 4}" text-anchor="middle" font-size="10" fill="#505873">{escape(str(label))}</text>'
            )
    svg = (
        f'<svg class="chart" viewBox="0 0 {width} {height}" width="100%" role="img" aria-hidden="true">'
        + ''.join(bars) + ''.join(ticks) + '</svg>'
    )
    return Markup(svg)


def donut_chart(values, labels=None, colors=None, width=260, height=180):
    numbers = [max(0.0, float(value or 0)) for value in values] or [0.0]
    labels = list(labels or [])
    palette = colors or ('#2066fa', '#7046e8', '#c44b7a', '#c56a1a', '#1f7a4d', '#1954ca', '#0e7c7b', '#8a4b12')
    total = sum(numbers) or 1.0
    cx, cy, r, thickness = 80, 90, 62, 22
    start = -90
    slices = []
    legend = []
    import math

    def point(angle, radius):
        rad = math.radians(angle)
        return cx + radius * math.cos(rad), cy + radius * math.sin(rad)

    for index, value in enumerate(numbers):
        sweep = 360 * (value / total)
        color = palette[index % len(palette)]
        if value <= 0:
            continue
        if sweep >= 359.9:
            slices.append(
                f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{color}" stroke-width="{thickness}"/>'
            )
        else:
            end = start + sweep
            large = 1 if sweep > 180 else 0
            x1, y1 = point(start, r)
            x2, y2 = point(end, r)
            slices.append(
                f'<path d="M {x1:.2f} {y1:.2f} A {r} {r} 0 {large} 1 {x2:.2f} {y2:.2f}" '
                f'fill="none" stroke="{color}" stroke-width="{thickness}" stroke-linecap="butt"/>'
            )
        start += sweep
        label = labels[index] if index < len(labels) else f'#{index + 1}'
        legend.append(
            f'<rect x="155" y="{18 + index * 20}" width="10" height="10" rx="2" fill="{color}"/>'
            f'<text x="171" y="{27 + index * 20}" font-size="11" fill="#111738">{escape(str(label))} ({int(value)})</text>'
        )
    svg = (
        f'<svg class="chart" viewBox="0 0 {width} {height}" width="100%" role="img" aria-hidden="true">'
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#edf0fa" stroke-width="{thickness}"/>'
        + ''.join(slices) + ''.join(legend) + '</svg>'
    )
    return Markup(svg)
