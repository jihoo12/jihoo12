#!/usr/bin/env python3
"""
Profile SVG generator — "Unknown Pleasures" style.

Renders a small family of SVGs for a GitHub profile README:

    hero     wordmark + a kernel-style boot log + the last 30 days as one pulse
    work     one card per pinned repo, with a barcode of its weekly commits
    signal   the year in ridgelines (below)
    footer   end-of-transmission rule

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
    created: dt.date | None = None
    website: str = ""
    projects: list[Project] = field(default_factory=list)


@dataclass
class Project:
    name: str
    url: str
    description: str
    language: str
    stars: int
    pushed: dt.date
    commits: dict[dt.date, int] = field(default_factory=dict)   # last year, per day


# Hand-written one-liners for pinned repos; anything missing falls back to
# the repo description. (kind, blurb)
BLURBS = {
    "jihoo": ("LANGUAGE", "An easy programming language with three profiles."),
    "kaguyaos": ("KERNEL", "x86-64 OS: SMP, preemption, NVMe + FAT16, xHCI, IPv4 + DNS."),
    "shady": ("COMPOSITOR", "An experimental 3D Wayland compositor built on wlroots."),
    "horn": ("LOGIC", "Checks derivation certificates for first-order Horn theories."),
    "kamo2": ("TYPE THEORY", "A cubical, dependently typed functional language."),
    "tinyasm": ("ASSEMBLER", "x86-64 assembler + JIT: from mnemonics to mmap'd bytes."),
    "swan": ("ENGINE", "C++20 / Vulkan 1.3 game engine with an editor and Lua."),
}


QUERY = """
query($login: String!) {
  user(login: $login) {
    login
    name
    createdAt
    websiteUrl
    followers { totalCount }
    pinnedItems(first: 6, types: REPOSITORY) {
      nodes {
        ... on Repository {
          name url description stargazerCount pushedAt
          primaryLanguage { name }
        }
      }
    }
    contributionsCollection {
      commitContributionsByRepository(maxRepositories: 100) {
        repository { name }
        contributions(first: 100, orderBy: {field: OCCURRED_AT, direction: DESC}) {
          nodes { occurredAt commitCount }
        }
      }
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

    by_repo = {
        entry["repository"]["name"]: {
            dt.date.fromisoformat(n["occurredAt"][:10]): n["commitCount"]
            for n in entry["contributions"]["nodes"]
        }
        for entry in user["contributionsCollection"]["commitContributionsByRepository"]
    }
    projects = [
        Project(
            name=r["name"], url=r["url"], description=r["description"] or "",
            language=(r["primaryLanguage"] or {}).get("name", ""),
            stars=r["stargazerCount"],
            pushed=dt.date.fromisoformat(r["pushedAt"][:10]),
            commits=by_repo.get(r["name"], {}),
        )
        for r in user["pinnedItems"]["nodes"] if r
    ]

    return Profile(
        created=dt.date.fromisoformat(user["createdAt"][:10]),
        website=user["websiteUrl"] or "",
        projects=projects,
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
    projects = []
    for name, lang in [("jihoo", "Rust"), ("kaguyaos", "Rust"), ("shady", "C"), ("horn", "Rust")]:
        commits = {d: rng.randint(1, 9) for d, _ in days if rng.random() < rng.uniform(.05, .3)}
        projects.append(Project(name, f"https://github.com/{login}/{name}", "", lang,
                                rng.randint(0, 9), max(commits), commits))
    return Profile(login, login, days, sum(c for _, c in days), 42, 18, 27,
                   [("Rust", .38), ("Python", .24), ("TypeScript", .19), ("C", .11), ("Shell", .08)],
                   created=dt.date(2023, 5, 23), website=f"https://{login}.github.io/",
                   projects=projects)


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


def base_css(c: dict[str, str], extra: str = "") -> str:
    """Shared type scale + motion. Base styles are the *final* state, so
    static renderers (and reduced-motion users) see the finished picture."""
    return f'''<style>
  .mono {{ font-family: {MONO}; }}
  .sans {{ font-family: {SANS}; }}
  .tick {{ font-size: 8.5px; fill: {c["dim"]}; letter-spacing: .12em; }}
  .label {{ font-size: 9.5px; fill: {c["dim"]}; letter-spacing: .16em; }}
  .val {{ font-size: 15px; fill: {c["fg"]}; font-weight: 500; }}
  .unit {{ font-size: 9.5px; fill: {c["dim"]}; }}
  .ln {{ stroke-linecap: round; stroke-linejoin: round;
         animation: draw 1.6s cubic-bezier(.6,0,.2,1) backwards; }}
  .fade {{ animation: fade .9s ease-out backwards; }}
  .pulse {{ animation: pulse 2.4s ease-in-out infinite; }}
  @keyframes draw {{ from {{ stroke-dasharray: 1; stroke-dashoffset: 1; }}
                     to {{ stroke-dasharray: 1; stroke-dashoffset: 0; }} }}
  @keyframes fade {{ from {{ opacity: 0; transform: translateY(4px); }} }}
  @keyframes pulse {{ 0%,100% {{ opacity: 1; }} 50% {{ opacity: .25; }} }}
  .grow {{ transform-box: fill-box; transform-origin: 50% 100%;
           animation: grow .7s cubic-bezier(.3,1.4,.5,1) backwards; }}
  .type {{ animation: type .01s steps(1) backwards; }}
  .blink {{ animation: blink 1.05s steps(1) infinite; }}
  @keyframes grow {{ from {{ transform: scaleY(0); }} }}
  @keyframes type {{ from {{ opacity: 0; }} }}
  @keyframes blink {{ 50% {{ opacity: 0; }} }}
  {extra}
  @media (prefers-reduced-motion: reduce) {{
    .ln, .fade, .pulse, .grow, .type, .blink {{ animation: none; }}
  }}
</style>'''


def frame(c: dict[str, str], w: int, h: int, label: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}" role="img" aria-label="{escape(label)}">'
            f'<title>{escape(label)}</title>')


def panel(c: dict[str, str], w: int, h: int) -> str:
    return (f'<rect width="{w}" height="{h}" rx="14" fill="{c["bg"]}"/>'
            f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="13.5" fill="none" stroke="{c["faint"]}"/>')

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
{base_css(c)}
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


def pulse_line(values: list[float], width: float, height: float, seed: str,
               samples: int = 220, sigma: float = 0.55) -> list[tuple[float, float]]:
    """One ridge from evenly spaced values in [0, 1]; sigma is in slot widths."""
    n = max(len(values), 1)
    hiss = noise(seed, samples)
    pts = []
    for i in range(samples):
        t = i / (samples - 1)
        lift = sum(
            v * math.exp(-((t * n - (k + 0.5)) ** 2) / (2 * sigma ** 2))
            for k, v in enumerate(values) if v
        )
        pts.append((t * width, max(-0.04, lift + hiss[i] * 0.03) * height))
    return pts


def ago(d: dt.date) -> str:
    n = (dt.date.today() - d).days
    if n <= 0:
        return "today"
    if n < 14:
        return f"{n}d ago"
    if n < 60:
        return f"{n // 7}w ago"
    return f"{n // 30}mo ago"


def host_of(p: Profile) -> str:
    return p.website.split("//")[-1].rstrip("/") if p.website else f"github.com/{p.login}"


def render_hero(p: Profile, theme: str) -> str:
    c = THEMES[theme]
    w, h, lx = 880, 340, 48
    since = p.created.strftime("%Y.%m") if p.created else "—"
    langs = " · ".join(n.lower() for n, _ in p.languages[:3])

    log = [
        ("boot", f"{p.login}, online since {since}"),
        ("cpu", f"{langs} online"),
        ("fs", f"mounted {p.repos} repositories"),
        ("proc", "kernels, compilers, compositors"),
        ("net", f"link up → {escape(host_of(p))}"),
        ("sig", f"{p.total:,} contributions / 52w"),
    ]
    rng = random.Random(p.login)
    stamp, rows = 0.0, []
    bx, by, lh = 508, 100, 19
    for i, (key, msg) in enumerate(log):
        rows.append(
            f'<text x="{bx}" y="{by + i * lh}" class="mono type" font-size="10.5" xml:space="preserve" '
            f'style="animation-delay:{0.7 + i * 0.32:.2f}s">'
            f'<tspan fill="{c["dim"]}">[{stamp:7.4f}]</tspan> '
            f'<tspan fill="{c["accent"]}">{key:<4}</tspan> '
            f'<tspan fill="{c["fg"]}">{msg}</tspan></text>'
        )
        stamp += rng.uniform(0.008, 0.03)
    py = by + len(log) * lh + 8
    prompt_delay = 0.7 + len(log) * 0.32
    prompt = (
        f'<g class="type" style="animation-delay:{prompt_delay:.2f}s">'
        f'<text x="{bx}" y="{py}" class="mono" font-size="10.5" fill="{c["fg"]}">'
        f'<tspan fill="{c["dim"]}">{escape(p.login)}@kaguya</tspan>:~$</text>'
        f'<rect x="{bx + 6.3 * (len(p.login) + 11) + 2:.1f}" y="{py - 9}" width="6.5" height="11" '
        f'fill="{c["accent"]}" class="blink"/></g>'
    )

    # the last 30 days, as a single pulse across the bottom
    recent = [n for _, n in p.days[-30:]]
    top = max(recent) or 1
    vals = [(n / top) ** 0.8 for n in recent]
    base = 296
    pts = pulse_line(vals, w - 2 * lx, 30, p.login + "hero", sigma=0.32)
    d = smooth_path(pts, lx, base)
    end_y = base - pts[-1][1]

    return f'''{frame(c, w, h, f"{p.name} — kernels, compilers and things that draw pixels")}
{base_css(c)}
{panel(c, w, h)}
<g class="fade">
  <circle cx="{lx + 3}" cy="44" r="3" fill="{c["accent"]}" class="pulse"/>
  <text x="{lx + 14}" y="47.5" class="mono label">{escape(p.login.upper())} / README</text>
  <text x="{w - lx}" y="47.5" class="mono label" text-anchor="end">EST. {since}</text>
</g>
<g class="fade" style="animation-delay:.15s">
  <text x="{lx - 6}" y="196" class="sans" font-size="124" font-weight="300" letter-spacing="-6" fill="{c["fg"]}">{escape(p.name.lower())}<tspan fill="{c["accent"]}">.</tspan></text>
</g>
<g class="fade" style="animation-delay:.4s">
  <text x="{lx}" y="236" class="sans" font-size="16" fill="{mix(c["fg"], c["bg"], .3)}">Kernels, compilers and things that draw pixels.</text>
</g>
<line x1="{bx - 22}" y1="86" x2="{bx - 22}" y2="{py + 4}" stroke="{c["faint"]}" class="fade" style="animation-delay:.5s"/>
{"".join(rows)}
{prompt}
<path class="ln" d="{d}" pathLength="1" fill="none" stroke="{c["fg"]}" stroke-width="1.2" style="animation-delay:.3s;animation-duration:2.4s"/>
<circle cx="{w - lx}" cy="{end_y:.1f}" r="3" fill="{c["accent"]}" class="pulse"/>
<g class="fade" style="animation-delay:1s">
  <text x="{lx}" y="{base + 26}" class="mono tick">LAST 30 DAYS</text>
  <text x="{w - lx}" y="{base + 26}" class="mono tick" text-anchor="end">NOW</text>
</g>
</svg>
'''


def project_meta(proj: Project) -> tuple[str, str]:
    kind, blurb = BLURBS.get(proj.name.lower(), ("", ""))
    if not blurb:
        blurb = proj.description.split(". ")[0].rstrip(".") + "."
        if len(blurb) > 68:
            blurb = blurb[:66].rsplit(" ", 1)[0] + "…"
    return kind or "PROJECT", blurb


def render_card(proj: Project, idx: int, theme: str) -> str:
    c = THEMES[theme]
    w, h, lx = 880, 124, 48
    kind, blurb = project_meta(proj)
    tags = " · ".join(t for t in (kind, proj.language.upper()) if t)

    # weekly commit barcode for the last 52 weeks
    today = dt.date.today()
    weeks = [0] * 52
    for d, n in proj.commits.items():
        k = 51 - (today - d).days // 7
        if 0 <= k < 52:
            weeks[k] += n
    top = max(weeks) or 1
    gx, gw, gbase, gh = 548, 248, 84, 44
    step = gw / 52
    bars = []
    for k, n in enumerate(weeks):
        x = gx + k * step
        if not n:
            bars.append(f'<rect x="{x:.1f}" y="{gbase - 1}" width="{step * .62:.1f}" height="1" fill="{c["faint"]}"/>')
            continue
        bh = max(2.0, (n / top) ** 0.6 * gh)
        col = c["accent"] if k == 51 or n == top else mix(c["dim"], c["fg"], (n / top) ** 0.7)
        bars.append(
            f'<rect x="{x:.1f}" y="{gbase - bh:.1f}" width="{step * .62:.1f}" height="{bh:.1f}" fill="{col}" '
            f'class="grow" style="animation-delay:{0.3 + k * 0.012:.3f}s"/>'
        )

    return f'''{frame(c, w, h, f"{proj.name} — {blurb}")}
{base_css(c)}
{panel(c, w, h)}
<g class="fade">
  <text x="{lx}" y="40" class="mono label" fill="{c["accent"]}" style="fill:{c["accent"]}">{idx:02d}</text>
  <text x="{lx + 30}" y="40" class="mono label">{escape(tags)}</text>
</g>
<g class="fade" style="animation-delay:.1s">
  <text x="{lx - 2}" y="76" class="sans" font-size="30" font-weight="300" letter-spacing="-1" fill="{c["fg"]}">{escape(proj.name)}</text>
  <text x="{lx}" y="100" class="mono" font-size="10.5" fill="{mix(c["fg"], c["bg"], .38)}">{escape(blurb)}</text>
</g>
<g class="fade" style="animation-delay:.2s">
  <text x="{gx + gw}" y="30" class="mono tick" text-anchor="end">{sum(weeks)} COMMITS · 52W</text>
  <text x="{gx}" y="{gbase + 18}" class="mono tick">★ {proj.stars}</text>
  <text x="{gx + gw}" y="{gbase + 18}" class="mono tick" text-anchor="end">PUSHED {ago(proj.pushed).upper()}</text>
</g>
{"".join(bars)}
<text x="{w - lx}" y="68" class="sans fade" font-size="20" fill="{c["dim"]}" text-anchor="end" style="animation-delay:.5s">↗</text>
</svg>
'''


def render_footer(p: Profile, theme: str) -> str:
    c = THEMES[theme]
    w, h, lx = 880, 100, 48
    vals = [0.0] * 40
    vals[33] = 1.0                        # one last heartbeat before the end
    base = 50
    pts = pulse_line(vals, w - 2 * lx, 22, p.login + "eof", sigma=0.7)
    d = smooth_path(pts, lx, base)
    return f'''{frame(c, w, h, "end of transmission")}
{base_css(c)}
{panel(c, w, h)}
<path class="ln" d="{d}" pathLength="1" fill="none" stroke="{c["dim"]}" stroke-width="1.1" style="animation-duration:2.6s"/>
<circle cx="{w - lx}" cy="{base - pts[-1][1]:.1f}" r="3" fill="{c["accent"]}" class="pulse"/>
<g class="fade" style="animation-delay:.6s">
  <text x="{lx}" y="{base + 28}" class="mono tick">EOF · THANKS FOR TUNING IN</text>
  <text x="{w - lx}" y="{base + 28}" class="mono tick" text-anchor="end">{escape(host_of(p).upper())}</text>
</g>
</svg>
'''


def themed(stem: str, alt: str) -> str:
    return (f'<picture><source media="(prefers-color-scheme: dark)" srcset="assets/{stem}-dark.svg">'
            f'<img alt="{escape(alt)}" src="assets/{stem}-light.svg" width="100%"></picture>')


def update_readme(path: Path, p: Profile) -> None:
    """Rewrite the block between <!-- work:start --> and <!-- work:end -->."""
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    start, end = "<!-- work:start -->", "<!-- work:end -->"
    if start not in text or end not in text:
        return
    cards = "\n".join(
        f'<a href="{proj.url}">{themed(f"work-{proj.name.lower()}", f"{proj.name}: {project_meta(proj)[1]}")}</a>'
        for proj in p.projects
    )
    head, rest = text.split(start, 1)
    _, tail = rest.split(end, 1)
    path.write_text(f"{head}{start}\n{cards}\n{end}{tail}", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--user", default=os.environ.get("GITHUB_REPOSITORY_OWNER", "jihoo12"))
    ap.add_argument("--out", default="assets")
    ap.add_argument("--demo", action="store_true", help="use synthetic data")
    ap.add_argument("--readme", default="README.md", help="README whose work block gets refreshed")
    args = ap.parse_args()

    token = None if args.demo else resolve_token()
    profile = fetch_profile(args.user, token) if token else demo_profile(args.user)
    if not token:
        print("no token found — rendering demo data")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for stale in out.glob("work-*.svg"):      # pins may have changed
        stale.unlink()
    for theme in THEMES:
        files = {
            f"hero-{theme}.svg": render_hero(profile, theme),
            f"signal-{theme}.svg": render(profile, theme),
            f"footer-{theme}.svg": render_footer(profile, theme),
        }
        for i, proj in enumerate(profile.projects, 1):
            files[f"work-{proj.name.lower()}-{theme}.svg"] = render_card(proj, i, theme)
        for name, svg in files.items():
            (out / name).write_text(svg, encoding="utf-8")
            print(f"wrote {out / name}")

    update_readme(Path(args.readme), profile)


if __name__ == "__main__":
    main()
