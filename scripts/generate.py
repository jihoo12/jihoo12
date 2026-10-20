#!/usr/bin/env python3
"""
Profile SVG generator — "Unknown Pleasures" style.

The past year of GitHub contributions is drawn as a stack of ridgelines,
one line per week, in the spirit of the pulsar plot on Joy Division's
album cover. Each bump in a line is one day; the taller it is, the more
you shipped that day.

Standard library only. Usage:
    GITHUB_TOKEN=... python3 scripts/generate.py --user jihoo12 --out assets
    python3 scripts/generate.py --demo            # synthetic data, no token
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import random
import subprocess
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from xml.sax.saxutils import escape

# ── Palette ──────────────────────────────────────────────────────────────

THEMES = {
    "dark": {
        "bg": "#0c0d10",
        "fg": "#ece7df",
        "dim": "#5c6069",
        "faint": "#23262c",
        "accent": "#ff5d3a",
    },
    "light": {
        "bg": "#f5f1ea",
        "fg": "#16171a",
        "dim": "#8a8780",
        "faint": "#dcd6cc",
        "accent": "#e2401f",
    },
}

MONO = "'JetBrains Mono','SF Mono',ui-monospace,Menlo,Consolas,monospace"
SANS = "'Inter','Helvetica Neue',-apple-system,'Segoe UI',Helvetica,Arial,sans-serif"

# ── Data ─────────────────────────────────────────────────────────────────


@dataclass
class Profile:
    login: str
    name: str
    days: list[tuple[dt.date, int]]           # chronological
    total: int
    stars: int = 0
    repos: int = 0
    followers: int = 0
    languages: list[tuple[str, float]] = field(default_factory=list)  # (name, share)


QUERY = """
query($login: String!) {
  user(login: $login) {
    login
    name
    followers { totalCount }
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false,
                 orderBy: {field: PUSHED_AT, direction: DESC}) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 8, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name } }
        }
      }
    }
  }
}
"""


def resolve_token() -> str | None:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        return token
    try:  # local convenience: reuse the gh CLI session
        out = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=5)
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def fetch_profile(login: str, token: str) -> Profile:
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "profile-svg"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if payload.get("errors"):
        raise RuntimeError(payload["errors"])
    user = payload["data"]["user"]

    cal = user["contributionsCollection"]["contributionCalendar"]
    days = [
        (dt.date.fromisoformat(d["date"]), d["contributionCount"])
        for w in cal["weeks"] for d in w["contributionDays"]
    ]

    lang_bytes: dict[str, int] = {}
    stars = 0
    for repo in user["repositories"]["nodes"]:
        stars += repo["stargazerCount"]
        for edge in repo["languages"]["edges"]:
            lang_bytes[edge["node"]["name"]] = lang_bytes.get(edge["node"]["name"], 0) + edge["size"]
    total_bytes = sum(lang_bytes.values()) or 1
    languages = sorted(((k, v / total_bytes) for k, v in lang_bytes.items()), key=lambda kv: -kv[1])

    return Profile(
        login=user["login"],
        name=user["name"] or user["login"],
        days=days,
        total=cal["totalContributions"],
        stars=stars,
        repos=user["repositories"]["totalCount"],
        followers=user["followers"]["totalCount"],
        languages=languages[:5],
    )


def demo_profile(login: str) -> Profile:
    rng = random.Random(login)
    today = dt.date.today()
    start = today - dt.timedelta(days=364 + (today.weekday() + 1) % 7)
    days, mood = [], 0.5
    for i in range((today - start).days + 1):
        d = start + dt.timedelta(days=i)
        mood = min(1.0, max(0.0, mood + rng.uniform(-0.18, 0.18)))
        busy = mood * (0.45 if d.weekday() >= 5 else 1.0)
        days.append((d, int(rng.random() < busy + 0.1) * int(rng.expovariate(1 / (busy * 14 + 1)))))
    return Profile(login, login, days, sum(c for _, c in days), 42, 18, 27,
                   [("Rust", .38), ("Python", .24), ("TypeScript", .19), ("C", .11), ("Shell", .08)])


# ── Stats ────────────────────────────────────────────────────────────────


def streaks(days: list[tuple[dt.date, int]]) -> tuple[int, int]:
    longest = run = 0
    for _, c in days:
        run = run + 1 if c else 0
        longest = max(longest, run)
    # current streak: today may still be empty, so don't let it break the run
    current = 0
    tail = days[:-1] if days and days[-1][1] == 0 else days
    for _, c in reversed(tail):
        if not c:
            break
        current += 1
    return current, longest


def weeks_of(days: list[tuple[dt.date, int]]) -> list[list[tuple[dt.date, int]]]:
    weeks: list[list[tuple[dt.date, int]]] = []
    for d, c in days:
        if not weeks or d.weekday() == 6:   # GitHub weeks start on Sunday
            weeks.append([])
        weeks[-1].append((d, c))
    return weeks


# ── Geometry ─────────────────────────────────────────────────────────────


def noise(seed: str, n: int) -> list[float]:
    """Deterministic smooth noise in [-1, 1] — same data, same picture."""
    rng = random.Random(hashlib.sha1(seed.encode()).hexdigest())
    raw = [rng.uniform(-1, 1) for _ in range(n)]
    k = 3
    return [sum(raw[max(0, i - k):i + k + 1]) / (2 * k + 1) * 1.8 for i in range(n)]


def ridge(week, peak: float, width: float, height: float, samples: int = 96) -> list[tuple[float, float]]:
    """Return (x, lift) samples for one week. Days sit in the middle 70%,
    edges stay near-flat with a little hiss, like the original pulsar plot."""
    centers = {d.weekday(): c for d, c in week}
    hiss = noise(week[0][0].isoformat(), samples)
    pts = []
    for i in range(samples):
        t = i / (samples - 1)
        lift = 0.0
        for wd in range(7):
            slot = (wd + 1) % 7                     # Sunday-first column order
            c = centers.get(wd, 0)
            if not c:
                continue
            mu = 0.15 + 0.7 * slot / 6
            amp = (c / peak) ** 0.42
            lift += amp * math.exp(-((t - mu) ** 2) / (2 * 0.032 ** 2))
        envelope = math.exp(-((t - 0.5) ** 2) / (2 * 0.26 ** 2))
        lift = lift * envelope + hiss[i] * 0.022 * (0.4 + envelope)
        pts.append((t * width, max(-0.03, lift) * height))
    return pts


def smooth_path(pts: list[tuple[float, float]], ox: float, base: float) -> str:
    """Catmull–Rom → cubic Bézier for a silky line."""
    p = [(ox + x, base - y) for x, y in pts]
    d = [f"M{p[0][0]:.1f},{p[0][1]:.1f}"]
    for i in range(len(p) - 1):
        p0, p1, p2 = p[max(i - 1, 0)], p[i], p[i + 1]
        p3 = p[min(i + 2, len(p) - 1)]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d.append(f"C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}")
    return "".join(d)


def mix(a: str, b: str, t: float) -> str:
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(ca, cb))


# ── Render ───────────────────────────────────────────────────────────────

W, H = 880, 470


def render(p: Profile, theme: str) -> str:
    c = THEMES[theme]
    weeks = weeks_of(p.days)
    peak = max((n for _, n in p.days), default=1) or 1
    week_totals = [sum(n for _, n in w) for w in weeks]
    max_week = max(week_totals) or 1
    best_week = week_totals.index(max_week)
    best_day = max(p.days, key=lambda dc: dc[1])
    current, longest = streaks(p.days)
    active = sum(1 for _, n in p.days if n)

    # ridge field
    fx, fy, fw, fh = 372, 78, 460, 288
    gap = fh / max(len(weeks), 1)
    amp = 66
    lines = []
    for i, week in enumerate(weeks):
        base = fy + amp * 0.55 + i * gap
        pts = ridge(week, peak, fw, amp)
        d = smooth_path(pts, fx, base)
        heat = week_totals[i] / max_week
        stroke = c["accent"] if i == best_week else mix(c["dim"], c["fg"], heat ** 0.7)
        sw = 1.5 if i == best_week else 1.05
        delay = i * 0.035
        # an open path fills along its implicit closing chord (which is never
        # stroked), so a bg fill makes each ridge occlude the ones behind it
        lines.append(
            f'<path class="ln" d="{d}" pathLength="1" fill="{c["bg"]}" stroke="{stroke}" '
            f'stroke-width="{sw}" style="animation-delay:{delay:.2f}s"/>'
        )

    # month ticks along the left edge of the field
    ticks, last_month = [], None
    for i, week in enumerate(weeks):
        m = week[0][0].month
        if m != last_month and i > 0:
            y = fy + amp * 0.55 + i * gap
            ticks.append(
                f'<line x1="{fx - 14}" y1="{y:.1f}" x2="{fx - 6}" y2="{y:.1f}" stroke="{c["dim"]}" stroke-width="1"/>'
                f'<text x="{fx - 20}" y="{y + 3:.1f}" class="mono tick" text-anchor="end">'
                f'{week[0][0].strftime("%b").upper()}</text>'
            )
        last_month = m

    # weekday labels under the field
    wd = "SMTWTFS"
    day_labels = "".join(
        f'<text x="{fx + fw * (0.15 + 0.7 * k / 6):.1f}" y="{fy + fh + amp * 0.55 + 22:.1f}" '
        f'class="mono tick" text-anchor="middle">{wd[k]}</text>'
        for k in range(7)
    )

    # left column
    lx = 48
    stats = [
        ("CURRENT STREAK", f"{current}", "days"),
        ("LONGEST STREAK", f"{longest}", "days"),
        ("ACTIVE DAYS", f"{active}", f"/ {len(p.days)}"),
        ("PEAK DAY", f"{best_day[1]}", best_day[0].strftime("%b %d").lower()),
    ]
    stat_rows = "".join(
        f'<g class="fade" style="animation-delay:{0.6 + k * 0.12:.2f}s">'
        f'<text x="{lx}" y="{218 + k * 34}" class="mono label">{label}</text>'
        f'<text x="{lx + 270}" y="{218 + k * 34}" class="mono val" text-anchor="end">{val}'
        f'<tspan class="unit" dx="5">{unit}</tspan></text>'
        f'<line x1="{lx}" y1="{228 + k * 34}" x2="{lx + 270}" y2="{228 + k * 34}" stroke="{c["faint"]}"/>'
        f'</g>'
        for k, (label, val, unit) in enumerate(stats)
    )

    # language strip
    ly = 370
    bar, cursor = [], 0.0
    for k, (name, share) in enumerate(p.languages):
        w = share * 270
        col = c["accent"] if k == 0 else mix(c["fg"], c["bg"], 0.25 + k * 0.15)
        bar.append(f'<rect x="{lx + cursor:.1f}" y="{ly}" width="{max(w - 2, 1):.1f}" height="3" fill="{col}"/>')
        cursor += w
    lang_names = "  ".join(
        f'{escape(n.lower())} {round(s * 100)}' for n, s in p.languages[:3]
    )

    year_from = p.days[0][0].strftime("%Y.%m") if p.days else ""
    year_to = p.days[-1][0].strftime("%Y.%m") if p.days else ""
    updated = dt.date.today().isoformat()

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{escape(p.login)}: {p.total} contributions in the last year">
<title>{escape(p.login)} — {p.total} contributions in the last year</title>
<style>
  .mono {{ font-family: {MONO}; }}
  .sans {{ font-family: {SANS}; }}
  .tick {{ font-size: 8.5px; fill: {c["dim"]}; letter-spacing: .12em; }}
  .label {{ font-size: 9.5px; fill: {c["dim"]}; letter-spacing: .16em; }}
  .val {{ font-size: 15px; fill: {c["fg"]}; font-weight: 500; }}
  .unit {{ font-size: 9.5px; fill: {c["dim"]}; }}
  /* base styles are the final state, so static renderers show everything;
     the "from" keyframes + backwards fill handle the entrance */
  .ln {{ stroke-linecap: round; stroke-linejoin: round;
         animation: draw 1.6s cubic-bezier(.6,0,.2,1) backwards; }}
  .fade {{ animation: fade .9s ease-out backwards; }}
  .pulse {{ animation: pulse 2.4s ease-in-out infinite; }}
  @keyframes draw {{ from {{ stroke-dasharray: 1; stroke-dashoffset: 1; }}
                     to {{ stroke-dasharray: 1; stroke-dashoffset: 0; }} }}
  @keyframes fade {{ from {{ opacity: 0; transform: translateY(4px); }} }}
  @keyframes pulse {{ 0%,100% {{ opacity: 1; }} 50% {{ opacity: .25; }} }}
  @media (prefers-reduced-motion: reduce) {{
    .ln, .fade, .pulse {{ animation: none; }}
  }}
</style>
<rect width="{W}" height="{H}" rx="14" fill="{c["bg"]}"/>
<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="13.5" fill="none" stroke="{c["faint"]}"/>

<!-- header -->
<g class="fade">
  <circle cx="{lx + 3}" cy="44" r="3" fill="{c["accent"]}" class="pulse"/>
  <text x="{lx + 14}" y="47.5" class="mono label">{escape(p.login.upper())} / SIGNAL</text>
  <text x="{W - 48}" y="47.5" class="mono label" text-anchor="end">{year_from} — {year_to}</text>
</g>

<!-- headline -->
<g class="fade" style="animation-delay:.25s">
  <text x="{lx - 3}" y="152" class="sans" font-size="76" font-weight="300" letter-spacing="-3" fill="{c["fg"]}">{p.total:,}</text>
  <text x="{lx}" y="178" class="mono label">CONTRIBUTIONS · LAST 52 WEEKS</text>
</g>

{stat_rows}

<!-- languages -->
<g class="fade" style="animation-delay:1.1s">
  <text x="{lx}" y="{ly - 10}" class="mono label">LANGUAGES</text>
  {"".join(bar)}
  <text x="{lx}" y="{ly + 20}" class="mono tick" style="letter-spacing:.04em">{lang_names}</text>
</g>

<!-- ridges -->
<g>{"".join(lines)}</g>
<g class="fade" style="animation-delay:.4s">{"".join(ticks)}{day_labels}</g>

<!-- footer -->
<g class="fade" style="animation-delay:1.4s">
  <text x="{lx}" y="{H - 34}" class="mono tick" xml:space="preserve">★ {p.stars}   REPOS {p.repos}   FOLLOWERS {p.followers}</text>
  <text x="{W - 48}" y="{H - 34}" class="mono tick" text-anchor="end">UPDATED {updated}</text>
</g>
</svg>
'''


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--user", default=os.environ.get("GITHUB_REPOSITORY_OWNER", "jihoo12"))
    ap.add_argument("--out", default="assets")
    ap.add_argument("--demo", action="store_true", help="use synthetic data")
    args = ap.parse_args()

    token = None if args.demo else resolve_token()
    profile = fetch_profile(args.user, token) if token else demo_profile(args.user)
    if not token:
        print("no token found — rendering demo data")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for theme in THEMES:
        path = out / f"signal-{theme}.svg"
        path.write_text(render(profile, theme), encoding="utf-8")
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
