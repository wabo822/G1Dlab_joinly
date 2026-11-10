"""Inline SVG and HTML charts. No external script, compatible with the CSP."""
import math

from markupsafe import Markup, escape

SWATCH_COLORS = ('#2066fa', '#7046e8', '#c44b7a', '#c56a1a', '#1f7a4d', '#1954ca', '#0e7c7b', '#8a4b12')


def _numbers(values):
    return [float(value or 0) for value in values] or [0.0]


def _format_value(value, suffix=''):
    number = float(value or 0)
    if number.is_integer():
        text = str(int(number))
    else:
        text = f'{number:.1f}'.replace('.', ',')
    return f'{text}{suffix}'


def _tick_indexes(count, inner_w, min_px=56):
    if count <= 1:
        return [0]
    step = max(1, math.ceil((count - 1) * min_px / max(inner_w, 1)))
    indexes = list(range(0, count, step))
    last = count - 1
    if indexes[-1] != last:
        spacing = inner_w / (count - 1)
        if (last - indexes[-1]) * spacing < min_px * 0.65:
            indexes[-1] = last
        else:
            indexes.append(last)
    return indexes


def line_chart(values, labels=None, width=420, height=180, color='#2066fa'):
    numbers = _numbers(values)
    labels = list(labels or [])
    peak = max(numbers) or 1.0
    pad_x, pad_top, pad_bottom = 8, 16, 28
    # Extra side room so the first and last date stay inside the viewBox.
    inner_w = width - pad_x * 2 - 24
    origin_x = pad_x + 12
    inner_h = height - pad_top - pad_bottom
    count = len(numbers)

    def x_at(index):
        if count == 1:
            return origin_x + inner_w / 2
        return origin_x + inner_w * index / (count - 1)

    def y_at(value):
        return pad_top + inner_h * (1 - (value / peak))

    points = ' '.join(f'{x_at(i):.1f},{y_at(v):.1f}' for i, v in enumerate(numbers))
    area = f'{x_at(0):.1f},{pad_top + inner_h:.1f} ' + points + f' {x_at(count - 1):.1f},{pad_top + inner_h:.1f}'
    ticks = []
    for index in _tick_indexes(count, inner_w):
        label = labels[index] if index < len(labels) else ''
        if not label:
            continue
        if index == 0:
            anchor, x = 'start', origin_x
        elif index == count - 1:
            anchor, x = 'end', origin_x + inner_w
        else:
            anchor, x = 'middle', x_at(index)
        ticks.append(
            f'<text x="{x:.1f}" y="{height - 8}" text-anchor="{anchor}" font-size="11" fill="#505873">'
            f'<title>{escape(str(label))}</title>{escape(str(label))}</text>'
        )
    svg = (
        f'<svg class="chart chart-line" viewBox="0 0 {width} {height}" width="100%" role="img" aria-hidden="true">'
        f'<polygon fill="{color}22" points="{area}"/>'
        f'<polyline fill="none" stroke="{color}" stroke-width="3" stroke-linejoin="round" stroke-linecap="round" points="{points}"/>'
        + ''.join(ticks) + '</svg>'
    )
    return Markup(svg)


def bar_chart(values, labels=None, width=640, height=200, color='#2066fa', suffix=''):
    """Horizontal bars with CSS-ellipsis labels, a tooltip, and a trailing value."""
    # width/height are kept in the signature for callers; layout is CSS-driven.
    del width, height
    numbers = _numbers(values)
    labels = list(labels or [])
    peak = max(numbers) or 1.0
    rows = []
    for index, value in enumerate(numbers):
        full = labels[index] if index < len(labels) else ''
        length = 0 if peak <= 0 else max(0, min(100, 100 * (value / peak)))
        rows.append(
            '<div class="chart-bar-row"'
            f' title="{escape(str(full))}">'
            f'<span class="chart-bar-label">{escape(str(full) or "—")}</span>'
            '<svg class="chart-bar-track" viewBox="0 0 100 10" preserveAspectRatio="none" aria-hidden="true">'
            f'<rect x="0" y="0" width="100" height="10" rx="3" fill="#edf0fa"/>'
            f'<rect x="0" y="0" width="{length:.1f}" height="10" rx="3" fill="{escape(color)}"/>'
            '</svg>'
            f'<span class="chart-bar-value">{escape(_format_value(value, suffix))}</span>'
            '</div>'
        )
    return Markup('<div class="chart-bars">' + ''.join(rows) + '</div>')


def stacked_bar(series_a, series_b, labels=None, width=640, height=200, color_a='#1f7a4d', color_b='#c56a1a',
                label_a='Contrôlés', label_b='Non présentés'):
    """Horizontal stacked bars with a wrapping colour key."""
    del width, height
    a = _numbers(series_a)
    b = [float(value or 0) for value in series_b] or [0.0]
    if len(b) < len(a):
        b.extend([0.0] * (len(a) - len(b)))
    if len(a) < len(b):
        a.extend([0.0] * (len(b) - len(a)))
    labels = list(labels or [])
    key = (
        '<p class="chart-key">'
        f'<span class="chart-swatch chart-swatch-a"></span>{escape(label_a)}'
        f'<span class="chart-swatch chart-swatch-b"></span>{escape(label_b)}'
        '</p>'
    )
    rows = []
    for index, (left, right) in enumerate(zip(a, b)):
        full = labels[index] if index < len(labels) else ''
        total = left + right
        share_a = 0 if total <= 0 else 100 * (left / total)
        share_b = 0 if total <= 0 else 100 * (right / total)
        value = f'{_format_value(left)} / {_format_value(total)}' if total else '0'
        rows.append(
            '<div class="chart-bar-row"'
            f' title="{escape(str(full))}">'
            f'<span class="chart-bar-label">{escape(str(full) or "—")}</span>'
            '<svg class="chart-bar-track" viewBox="0 0 100 10" preserveAspectRatio="none" aria-hidden="true">'
            '<rect x="0" y="0" width="100" height="10" rx="3" fill="#edf0fa"/>'
            + (f'<rect x="0" y="0" width="{share_a:.1f}" height="10" rx="3" fill="{escape(color_a)}"/>' if share_a else '')
            + (f'<rect x="{share_a:.1f}" y="0" width="{share_b:.1f}" height="10" rx="3" fill="{escape(color_b)}"/>' if share_b else '')
            + '</svg>'
            f'<span class="chart-bar-value">{escape(value)}</span>'
            '</div>'
        )
    return Markup('<div class="chart-bars">' + key + ''.join(rows) + '</div>')


def donut_chart(values, labels=None, colors=None, width=180, height=180):
    """Donut plot plus an HTML legend that can wrap inside the card."""
    numbers = [max(0.0, float(value or 0)) for value in values] or [0.0]
    labels = list(labels or [])
    palette = colors or SWATCH_COLORS
    total = sum(numbers) or 1.0
    cx, cy, r, thickness = width / 2, height / 2, min(width, height) * 0.34, 22
    start = -90
    slices = []

    def point(angle, radius):
        rad = math.radians(angle)
        return cx + radius * math.cos(rad), cy + radius * math.sin(rad)

    items = []
    for index, value in enumerate(numbers):
        color = palette[index % len(palette)]
        label = labels[index] if index < len(labels) else f'#{index + 1}'
        items.append((index, value, color, label))
        if value <= 0:
            continue
        sweep = 360 * (value / total)
        if sweep >= 359.9:
            slices.append(
                f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="none" stroke="{color}" stroke-width="{thickness}"/>'
            )
        else:
            end = start + sweep
            large = 1 if sweep > 180 else 0
            x1, y1 = point(start, r)
            x2, y2 = point(end, r)
            slices.append(
                f'<path d="M {x1:.2f} {y1:.2f} A {r:.1f} {r:.1f} 0 {large} 1 {x2:.2f} {y2:.2f}" '
                f'fill="none" stroke="{color}" stroke-width="{thickness}" stroke-linecap="butt"/>'
            )
        start += sweep

    legend = []
    for index, value, color, label in items:
        legend.append(
            '<li>'
            f'<span class="chart-swatch chart-swatch-{index % 8}"></span>'
            f'<span class="chart-legend-label">{escape(str(label))} '
            f'<span class="chart-legend-count">({int(value)})</span></span>'
            '</li>'
        )
    svg = (
        f'<svg class="chart chart-donut-plot" viewBox="0 0 {width} {height}" width="160" height="160" role="img" aria-hidden="true">'
        f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="none" stroke="#edf0fa" stroke-width="{thickness}"/>'
        + ''.join(slices) + '</svg>'
    )
    return Markup(
        '<div class="chart-donut">' + svg + '<ul class="chart-legend">' + ''.join(legend) + '</ul></div>'
    )
