#!/usr/bin/env python3
"""Draw the README's contribution chart: the last year as a skyline, one block
per day, raised by that day's contributions, in the banner's paper, ink and
orange. Writes assets/contrib-light.svg and assets/contrib-dark.svg.

    python3 scripts/contrib.py            # needs the gh CLI, logged in

In GitHub Actions the gh CLI reads GH_TOKEN (the workflow's GITHUB_TOKEN), so
the same script redraws the chart every day; see
.github/workflows/contributions.yml. Standard library only.
"""
import datetime as dt
import json
import math
import os
import pathlib
import subprocess

LOGIN = os.environ.get('GH_LOGIN', 'ChenFangfc')
ROOT = pathlib.Path(__file__).resolve().parent.parent

QUERY = """query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount contributionLevel weekday } }
      }
    }
  }
}"""

LEVELS = ['NONE', 'FIRST_QUARTILE', 'SECOND_QUARTILE', 'THIRD_QUARTILE', 'FOURTH_QUARTILE']

# Top-face colour per level; the front and side faces are the same hue, darker.
THEMES = {
    'light': {
        'bg': '#f8f7f3', 'border': '#e6e2d9', 'ink': '#16191d', 'muted': '#62666d', 'hair': '#d6d0c4',
        'accent': '#ff5f05', 'accent_text': '#b8430e',
        'levels': ['#e9e4d9', '#f8cfb1', '#f6a26c', '#f9782f', '#ff5f05'],
        'front': 0.86, 'side': 0.74,
    },
    'dark': {
        'bg': '#161b22', 'border': '#30363d', 'ink': '#e6edf3', 'muted': '#8d96a0', 'hair': '#3d444d',
        'accent': '#ff7a2e', 'accent_text': '#ff8a47',
        'levels': ['#262c35', '#5b3421', '#97491f', '#d9621d', '#ff7a2e'],
        'front': 0.78, 'side': 0.62,
    },
}

# Geometry (px in the SVG's own units; GitHub scales the image to the column).
W, H = 900, 226
CELL = 14.4        # step from one week to the next
DEPTH_X, DEPTH_Y = 5.4, 6.0   # step from one weekday row to the one behind it
GAP = 2.2          # space between blocks
MAX_H = 84         # height of the busiest day: a back-row peak stays clear of the summary line
FLOOR = 2.4        # thickness of an empty day's tile


def fetch():
    out = subprocess.run(
        ['gh', 'api', 'graphql', '-f', f'query={QUERY}', '-F', f'login={LOGIN}'],
        check=True, capture_output=True, text=True,
    ).stdout
    cal = json.loads(out)['data']['user']['contributionsCollection']['contributionCalendar']
    return cal['totalContributions'], cal['weeks']


def shade(hex_colour, k):
    r, g, b = (int(hex_colour[i:i + 2], 16) for i in (1, 3, 5))
    return '#{:02x}{:02x}{:02x}'.format(*(round(c * k) for c in (r, g, b)))


def stats(weeks):
    days = [d for w in weeks for d in w['contributionDays']]
    active = [d for d in days if d['contributionCount'] > 0]
    busiest = max(days, key=lambda d: d['contributionCount'])
    best = run = 0
    for d in days:
        run = run + 1 if d['contributionCount'] > 0 else 0
        best = max(best, run)
    return len(active), busiest, best


def months(weeks, x_of_week):
    """Month labels at the first week that starts in each month."""
    labels, last = [], None
    for i, w in enumerate(weeks):
        first = dt.date.fromisoformat(w['contributionDays'][0]['date'])
        if first.month != last and first.day <= 7 and i < len(weeks) - 2:
            labels.append((x_of_week(i), first.strftime('%b')))
        last = first.month
    return labels


def render(theme, total, weeks):
    t = THEMES[theme]
    peak = max((d['contributionCount'] for w in weeks for d in w['contributionDays']), default=0) or 1
    active, busiest, streak = stats(weeks)
    n = len(weeks)
    x0 = 40                           # front-left corner of the first week, under the title
    y0 = H - 42                       # front edge of the Saturday row

    def corner(w, z):                 # floor corner of week w, depth row z (0 = front)
        return x0 + w * CELL + z * DEPTH_X, y0 - z * DEPTH_Y

    parts = []
    # Back rows first and, within a row, left to right, so nearer blocks
    # cover the faces they hide.
    for z in range(6, -1, -1):
        weekday = 6 - z               # Sunday at the back, Saturday in front
        for wi, week in enumerate(weeks):
            day = next((d for d in week['contributionDays'] if d['weekday'] == weekday), None)
            if day is None:
                continue
            count = day['contributionCount']
            level = LEVELS.index(day['contributionLevel'])
            h = FLOOR if count == 0 else FLOOR + (MAX_H - FLOOR) * math.sqrt(count / peak)
            top = t['levels'][level]
            x, y = corner(wi, z)
            fw = CELL - GAP                         # front width of a block
            dx, dy = DEPTH_X - GAP * 0.4, DEPTH_Y - GAP * 0.45   # its depth
            # front face, right face, top face
            front = f'{x:.1f},{y:.1f} {x + fw:.1f},{y:.1f} {x + fw:.1f},{y - h:.1f} {x:.1f},{y - h:.1f}'
            side = (f'{x + fw:.1f},{y:.1f} {x + fw + dx:.1f},{y - dy:.1f} '
                    f'{x + fw + dx:.1f},{y - dy - h:.1f} {x + fw:.1f},{y - h:.1f}')
            lid = (f'{x:.1f},{y - h:.1f} {x + fw:.1f},{y - h:.1f} '
                   f'{x + fw + dx:.1f},{y - dy - h:.1f} {x + dx:.1f},{y - dy - h:.1f}')
            title = f'<title>{day["date"]}: {count} contribution{"s" if count != 1 else ""}</title>' if count else ''
            parts.append(
                f'<g>{title}<polygon points="{front}" fill="{shade(top, t["front"])}"/>'
                f'<polygon points="{side}" fill="{shade(top, t["side"])}"/>'
                f'<polygon points="{lid}" fill="{top}"/></g>'
            )

    month_labels = ''.join(
        f'<text x="{x:.1f}" y="{y0 + 22:.1f}" class="m">{label}</text>'
        for x, label in months(weeks, lambda i: x0 + i * CELL)
    )
    legend_x = W - 36 - 5 * 15 - 34
    legend = ''.join(
        f'<rect x="{legend_x + 30 + i * 15}" y="27" width="11" height="11" rx="2.5" fill="{c}"/>'
        for i, c in enumerate(t['levels'])
    )
    busy_date = dt.date.fromisoformat(busiest['date']).strftime('%b %-d')
    summary = (f'{total:,} contributions in the last year · {active} active days · '
               f'longest streak {streak} day{"s" if streak != 1 else ""} · busiest day {busiest["contributionCount"]} ({busy_date})')
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="t d">
<title id="t">Chen Fang's GitHub contributions</title>
<desc id="d">{summary}</desc>
<style>
  text {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', Helvetica, Arial, sans-serif; }}
  .s {{ font-size: 12.5px; fill: {t['muted']}; }}
  .m, .l {{ font-size: 11px; fill: {t['muted']}; }}
</style>
<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="16" fill="{t['bg']}" stroke="{t['border']}"/>
<text x="36" y="38" class="s">{summary}</text>
<text x="{legend_x}" y="37" class="l">Less</text>{legend}<text x="{legend_x + 30 + 5 * 15 + 2}" y="37" class="l">More</text>
{''.join(parts)}
{month_labels}
</svg>
"""


def main():
    total, weeks = fetch()
    for theme in THEMES:
        path = ROOT / 'assets' / f'contrib-{theme}.svg'
        path.write_text(render(theme, total, weeks), encoding='utf-8')
        print(f'wrote {path.relative_to(ROOT)} ({path.stat().st_size // 1024} KB)')


if __name__ == '__main__':
    main()
