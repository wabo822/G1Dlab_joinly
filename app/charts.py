"""Inline SVG chart. No external script."""
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
    ticks = []
    step = max(1, count // 5)
    for index in range(0, count, step):
        label = labels[index] if index < len(labels) else ''
        ticks.append(
            f'<text x="{x_at(index):.1f}" y="{height - 2}" text-anchor="middle" font-size="11" fill="#505873">{escape(label)}</text>'
        )
    svg = (
        f'<svg viewBox="0 0 {width} {height}" width="100%" role="img">'
        f'<polyline fill="none" stroke="{color}" stroke-width="3" points="{points}"/>'
        + ''.join(ticks) + '</svg>'
    )
    return Markup(svg)
