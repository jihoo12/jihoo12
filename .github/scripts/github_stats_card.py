#!/usr/bin/env python3
"""
github_stats_card.py

Generate a rich GitHub stats card (SVG or PNG) for a README.md, including:
  - avatar photo
  - name / username / bio
  - public repos, followers, total stars, total forks
  - commits / PRs / issues / reviews (requires --token, uses GraphQL)
  - top languages breakdown (from your public repos)
  - public organizations you belong to

Usage:
    python github_stats_card.py <username> [options]

Examples:
    python github_stats_card.py octocat
    python github_stats_card.py octocat -o card.png -f png --theme dark
    python github_stats_card.py octocat --token ghp_xxx   # unlocks commit/PR/issue/review counts

Without --token you still get repos/followers/stars/forks/top-languages, but
commit/PR/issue/review counts require a token because GitHub only exposes
those totals through the authenticated GraphQL API.

A token needs no special scopes for public data - a plain classic token
(or fine-grained token with "Public Repositories: read") is enough.
Create one at: https://github.com/settings/tokens

Embed in README.md:
    ![GitHub Stats](./card.svg)
"""

import argparse
import base64
import os
import sys
from datetime import datetime, timezone

import requests

API_ROOT = "https://api.github.com"
GRAPHQL_URL = "https://api.github.com/graphql"

THEMES = {
    "light": {
        "bg": "#ffffff",
        "border": "#e4e2e2",
        "title": "#2f80ed",
        "text": "#434d58",
        "muted": "#6a737d",
        "icon": "#2f80ed",
        "bar_bg": "#eaeaea",
        "ring": "#2f80ed",
    },
    "dark": {
        "bg": "#0d1117",
        "border": "#30363d",
        "title": "#58a6ff",
        "text": "#c9d1d9",
        "muted": "#8b949e",
        "icon": "#58a6ff",
        "bar_bg": "#21262d",
        "ring": "#58a6ff",
    },
    "radical": {
        "bg": "#141321",
        "border": "#ff6b9d",
        "title": "#fe428e",
        "text": "#e3e3f5",
        "muted": "#a9a9c9",
        "icon": "#f8d847",
        "bar_bg": "#2b2a45",
        "ring": "#fe428e",
    },
}

# Approximate GitHub language colors (subset covering the most common languages)
LANGUAGE_COLORS = {
    "JavaScript": "#f1e05a", "TypeScript": "#3178c6", "Python": "#3572A5",
    "Java": "#b07219", "C++": "#f34b7d", "C": "#555555", "C#": "#178600",
    "Go": "#00ADD8", "Rust": "#dea584", "Ruby": "#701516", "PHP": "#4F5D95",
    "HTML": "#e34c26", "CSS": "#563d7c", "Shell": "#89e051", "Swift": "#F05138",
    "Kotlin": "#A97BFF", "Dart": "#00B4AB", "Vue": "#41b883", "Scala": "#c22d40",
    "Jupyter Notebook": "#DA5B0B", "Lua": "#000080", "R": "#198CE7",
    "Objective-C": "#438eff", "Perl": "#0298c3", "Haskell": "#5e5086",
    "Elixir": "#6e4a7e", "Clojure": "#db5855", "MATLAB": "#e16737",
    "Dockerfile": "#384d54", "Makefile": "#427819", "SCSS": "#c6538c",
}
DEFAULT_LANG_COLOR = "#858585"


# --------------------------------------------------------------------------
# Data fetching
# --------------------------------------------------------------------------

def fetch_json(url, token=None, params=None):
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    resp = requests.get(url, headers=headers, params=params, timeout=15)
    if resp.status_code == 404:
        raise SystemExit(f"Error: GitHub user not found ({url})")
    if resp.status_code == 403:
        raise SystemExit(
            "Error: GitHub API rate limit hit. Pass --token with a "
            "personal access token to get a much higher rate limit."
        )
    resp.raise_for_status()
    return resp.json()


def fetch_all_repos(username, token=None, cap=300):
    """Paginate through public repos owned by the user (capped for card purposes)."""
    repos = []
    page = 1
    while len(repos) < cap:
        url = f"{API_ROOT}/users/{username}/repos"
        batch = fetch_json(url, token, params={"per_page": 100, "page": page, "type": "owner"})
        if not batch:
            break
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return repos[:cap]


def graphql(query, variables, token):
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.post(GRAPHQL_URL, json={"query": query, "variables": variables},
                          headers=headers, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data and data["errors"]:
        raise SystemExit(f"GitHub GraphQL error: {data['errors'][0].get('message')}")
    return data["data"]


CONTRIB_QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      totalPullRequestReviewContributions
    }
  }
}
"""


def fetch_contribution_totals(username, token, created_at):
    """Sum contributionsCollection year-by-year since account creation
    (GraphQL only allows ~1 year windows per call)."""
    start_year = created_at.year
    end_year = datetime.now(timezone.utc).year

    totals = {
        "commits": 0, "prs": 0, "issues": 0, "reviews": 0,
    }
    for year in range(start_year, end_year + 1):
        frm = max(created_at, datetime(year, 1, 1, tzinfo=timezone.utc))
        to = min(datetime.now(timezone.utc), datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc))
        if frm >= to:
            continue
        data = graphql(CONTRIB_QUERY, {
            "login": username,
            "from": frm.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "to": to.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }, token)
        cc = data["user"]["contributionsCollection"]
        totals["commits"] += cc["totalCommitContributions"]
        totals["prs"] += cc["totalPullRequestContributions"]
        totals["issues"] += cc["totalIssueContributions"]
        totals["reviews"] += cc["totalPullRequestReviewContributions"]
    return totals


def fetch_orgs(username, token=None):
    """Public organizations the user belongs to."""
    try:
        orgs = fetch_json(f"{API_ROOT}/users/{username}/orgs", token)
    except SystemExit:
        return []
    return orgs or []


def fetch_avatar_data_uri(avatar_url):
    try:
        resp = requests.get(avatar_url, timeout=15)
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "image/png").split(";")[0]
        b64 = base64.b64encode(resp.content).decode("ascii")
        return f"data:{content_type};base64,{b64}"
    except Exception:
        return None


def compute_top_languages(repos, top_n=5):
    """Weight each repo's primary language by (stars + 1) so popular repos
    count more, then take the top N languages by share.

    Shares are normalized against the sum of the *displayed* top-N languages
    (not the grand total across every language), so the bar always fills to
    100% instead of leaving a leftover "other languages" gap."""
    weights = {}
    for r in repos:
        if r.get("fork"):
            continue
        lang = r.get("language")
        if not lang:
            continue
        weight = r.get("stargazers_count", 0) + 1
        weights[lang] = weights.get(lang, 0) + weight

    if not weights:
        return []

    ranked = sorted(weights.items(), key=lambda kv: kv[1], reverse=True)[:top_n]
    shown_total = sum(w for _, w in ranked)
    return [(lang, w / shown_total) for lang, w in ranked]


def gather_stats(username, token=None):
    user = fetch_json(f"{API_ROOT}/users/{username}", token)
    repos = fetch_all_repos(username, token)

    total_stars = sum(r.get("stargazers_count", 0) for r in repos)
    total_forks = sum(r.get("forks_count", 0) for r in repos)

    created = datetime.strptime(user["created_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    years_on_github = round((datetime.now(timezone.utc) - created).days / 365.25, 1)

    contributions = None
    if token:
        print("Fetching commit/PR/issue history (this walks year-by-year, may take a few seconds)...")
        contributions = fetch_contribution_totals(username, token, created)

    avatar_data_uri = fetch_avatar_data_uri(user.get("avatar_url")) if user.get("avatar_url") else None
    top_languages = compute_top_languages(repos)

    orgs_raw = fetch_orgs(username, token)
    organizations = []
    for org in orgs_raw:
        org_avatar = fetch_avatar_data_uri(org.get("avatar_url")) if org.get("avatar_url") else None
        organizations.append({
            "login": org.get("login", "?"),
            "avatar_data_uri": org_avatar,
        })

    return {
        "login": user.get("login", username),
        "name": user.get("name") or user.get("login", username),
        "bio": user.get("bio") or "",
        "avatar_data_uri": avatar_data_uri,
        "public_repos": user.get("public_repos", 0),
        "followers": user.get("followers", 0),
        "following": user.get("following", 0),
        "total_stars": total_stars,
        "total_forks": total_forks,
        "years_on_github": years_on_github,
        "contributions": contributions,
        "top_languages": top_languages,
        "organizations": organizations,
    }


# --------------------------------------------------------------------------
# SVG rendering
# --------------------------------------------------------------------------

def esc(s):
    return (
        str(s).replace("&", "&amp;").replace("<", "&lt;")
        .replace(">", "&gt;").replace('"', "&quot;")
    )


# Small generic (non-trademarked) line icons, 24x24 viewbox, stroke="currentColor"
ICONS = {
    "repo": '<path d="M4 3h13a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H7a3 3 0 0 1-3-3V3z"/><path d="M4 17a3 3 0 0 1 3-3h12"/>',
    "star": '<path d="M12 2.5l2.9 6 6.6.7-4.9 4.5 1.3 6.5-5.9-3.3-5.9 3.3 1.3-6.5-4.9-4.5 6.6-.7z"/>',
    "fork": '<circle cx="7" cy="5" r="2.2"/><circle cx="17" cy="5" r="2.2"/><circle cx="12" cy="19" r="2.2"/><path d="M7 7.2V11a3 3 0 0 0 3 3h4a3 3 0 0 0 3-3V7.2"/><path d="M12 14v3"/>',
    "followers": '<circle cx="9" cy="8" r="3.2"/><path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6"/><circle cx="17.5" cy="9" r="2.6"/><path d="M15 20c.2-2.6 2-4.7 4.4-5.2"/>',
    "commit": '<circle cx="12" cy="12" r="3"/><path d="M2 12h7"/><path d="M15 12h7"/>',
    "pr": '<circle cx="6" cy="6" r="2.2"/><circle cx="6" cy="18" r="2.2"/><circle cx="18" cy="6" r="2.2"/><path d="M6 8.2V16"/><path d="M18 8.2V14a3 3 0 0 1-3 3h-3"/>',
    "issue": '<circle cx="12" cy="12" r="9"/><path d="M12 7v6"/><circle cx="12" cy="16.3" r="0.15" fill="currentColor" stroke="none"/>',
    "review": '<path d="M4 4h16v12H8l-4 4z"/><path d="M8 9h8"/><path d="M8 12.5h5"/>',
}


def icon_svg(name, x, y, size, color):
    body = ICONS.get(name, "")
    scale = size / 24
    return (f'<g transform="translate({x},{y}) scale({scale})" '
            f'fill="none" stroke="{color}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">'
            f'{body}</g>')


def stat_cell(x, y, w, icon, value, label, colors):
    return f"""
    <g transform="translate({x},{y})">
      {icon_svg(icon, 0, 0, 22, colors['icon'])}
      <text x="30" y="10" class="stat-value">{value:,}</text>
      <text x="30" y="26" class="stat-label">{esc(label)}</text>
    </g>"""


def build_svg(stats, theme_name="light", width=520):
    c = THEMES.get(theme_name, THEMES["light"])

    has_contrib = stats["contributions"] is not None

    # --- header: avatar + name/username/bio ---
    avatar_r = 34
    avatar_cx, avatar_cy = 30 + avatar_r, 34 + avatar_r
    if stats["avatar_data_uri"]:
        avatar_svg = f"""
      <defs>
        <clipPath id="avatarClip"><circle cx="{avatar_cx}" cy="{avatar_cy}" r="{avatar_r}"/></clipPath>
      </defs>
      <circle cx="{avatar_cx}" cy="{avatar_cy}" r="{avatar_r + 2}" fill="none" stroke="{c['ring']}" stroke-width="2"/>
      <image href="{stats['avatar_data_uri']}" x="{avatar_cx - avatar_r}" y="{avatar_cy - avatar_r}"
             width="{avatar_r * 2}" height="{avatar_r * 2}" clip-path="url(#avatarClip)" preserveAspectRatio="xMidYMid slice"/>"""
    else:
        avatar_svg = f"""
      <circle cx="{avatar_cx}" cy="{avatar_cy}" r="{avatar_r}" fill="{c['bar_bg']}" stroke="{c['ring']}" stroke-width="2"/>"""

    text_x = avatar_cx + avatar_r + 20
    bio = stats["bio"]
    if len(bio) > 58:
        bio = bio[:55].rstrip() + "..."

    header_svg = f"""
    {avatar_svg}
    <text x="{text_x}" y="{avatar_cy - 12}" class="name">{esc(stats['name'])}</text>
    <text x="{text_x}" y="{avatar_cy + 8}" class="username">@{esc(stats['login'])} &#8226; {stats['years_on_github']} yrs on GitHub</text>
    {f'<text x="{text_x}" y="{avatar_cy + 26}" class="bio">{esc(bio)}</text>' if bio else ''}
    """

    content_top = 34 + avatar_r * 2 + 26

    # --- stat grid ---
    row1 = [
        ("repo", stats["public_repos"], "Repositories"),
        ("followers", stats["followers"], "Followers"),
        ("star", stats["total_stars"], "Total Stars"),
        ("fork", stats["total_forks"], "Total Forks"),
    ]
    if has_contrib:
        row2 = [
            ("commit", stats["contributions"]["commits"], "Commits"),
            ("pr", stats["contributions"]["prs"], "Pull Requests"),
            ("issue", stats["contributions"]["issues"], "Issues"),
            ("review", stats["contributions"]["reviews"], "PR Reviews"),
        ]
    else:
        row2 = []

    col_w = (width - 60) / 4
    grid_svg = ""
    for i, (icon, value, label) in enumerate(row1):
        grid_svg += stat_cell(30 + i * col_w, content_top, col_w, icon, value, label, c)
    if row2:
        for i, (icon, value, label) in enumerate(row2):
            grid_svg += stat_cell(30 + i * col_w, content_top + 54, col_w, icon, value, label, c)

    grid_rows = 2 if row2 else 1
    langs_top = content_top + grid_rows * 54 + 20

    # --- top languages ---
    langs_svg = ""
    langs_height = 0
    if stats["top_languages"]:
        bar_w = width - 60
        bar_h = 10
        segs = ""
        cursor = 0
        for lang, share in stats["top_languages"]:
            color = LANGUAGE_COLORS.get(lang, DEFAULT_LANG_COLOR)
            seg_w = bar_w * share
            segs += f'<rect x="{cursor:.1f}" y="0" width="{seg_w:.1f}" height="{bar_h}" fill="{color}"/>'
            cursor += seg_w

        legend = ""
        cols = 2
        for i, (lang, share) in enumerate(stats["top_languages"]):
            color = LANGUAGE_COLORS.get(lang, DEFAULT_LANG_COLOR)
            col = i % cols
            row = i // cols
            lx = col * (bar_w / cols)
            ly = 28 + row * 22
            legend += f"""
              <circle cx="{lx + 5}" cy="{ly - 4}" r="5" fill="{color}"/>
              <text x="{lx + 16}" y="{ly}" class="lang-label">{esc(lang)} {share*100:.1f}%</text>"""

        legend_rows = (len(stats["top_languages"]) + cols - 1) // cols
        langs_height = 40 + legend_rows * 22

        langs_svg = f"""
        <text x="0" y="0" class="section-title">Most Used Languages</text>
        <g transform="translate(0, 12)">
          <rect x="0" y="0" width="{bar_w}" height="{bar_h}" rx="5" fill="{c['bar_bg']}"/>
          <clipPath id="langClip"><rect x="0" y="0" width="{bar_w}" height="{bar_h}" rx="5"/></clipPath>
          <g clip-path="url(#langClip)">{segs}</g>
          {legend}
        </g>"""

    langs_block_height = langs_height if stats["top_languages"] else 0
    orgs_top = langs_top + langs_block_height + (20 if stats["top_languages"] else 0)

    # --- organizations ---
    orgs_svg = ""
    orgs_block_height = 0
    if stats["organizations"]:
        org_r = 18
        org_gap = 14
        org_label_gap = 6
        cursor_x = 0
        pieces = []
        for org in stats["organizations"]:
            cx, cy = cursor_x + org_r, org_r
            if org["avatar_data_uri"]:
                clip_id = f"orgClip{esc(org['login'])}".replace(" ", "")
                pieces.append(f"""
                <defs><clipPath id="{clip_id}"><circle cx="{cx}" cy="{cy}" r="{org_r}"/></clipPath></defs>
                <circle cx="{cx}" cy="{cy}" r="{org_r + 1.5}" fill="none" stroke="{c['border']}" stroke-width="1"/>
                <image href="{org['avatar_data_uri']}" x="{cx - org_r}" y="{cy - org_r}"
                       width="{org_r * 2}" height="{org_r * 2}" clip-path="url(#{clip_id})"
                       preserveAspectRatio="xMidYMid slice"/>""")
            else:
                pieces.append(f"""
                <circle cx="{cx}" cy="{cy}" r="{org_r}" fill="{c['bar_bg']}" stroke="{c['border']}" stroke-width="1"/>""")
            pieces.append(f"""
                <text x="{cx}" y="{org_r*2 + org_label_gap + 9}" text-anchor="middle" class="org-label">{esc(org['login'])}</text>""")
            # advance cursor based on label width estimate (roughly monospace-ish average char width)
            label_w = max(org_r * 2, len(org["login"]) * 6.2)
            cursor_x += label_w + org_gap

        orgs_svg = f"""
        <text x="0" y="0" class="section-title">Organizations</text>
        <g transform="translate(0, 14)">
          {''.join(pieces)}
        </g>"""
        orgs_block_height = 14 + org_r * 2 + org_label_gap + 14 + 10

    height = orgs_top + orgs_block_height + 24
    if not stats["top_languages"] and not stats["organizations"]:
        height = content_top + grid_rows * 54 + 24

    svg = f"""<svg width="{width}" height="{height:.0f}" viewBox="0 0 {width} {height:.0f}"
     xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
     font-family="'Segoe UI', Ubuntu, Sans-Serif">
  <style>
    .name {{ fill: {c['title']}; font-size: 19px; font-weight: 700; }}
    .username {{ fill: {c['muted']}; font-size: 12px; }}
    .bio {{ fill: {c['text']}; font-size: 12px; }}
    .stat-value {{ fill: {c['text']}; font-size: 15px; font-weight: 700; }}
    .stat-label {{ fill: {c['muted']}; font-size: 11px; }}
    .section-title {{ fill: {c['text']}; font-size: 13px; font-weight: 700; }}
    .lang-label {{ fill: {c['text']}; font-size: 11px; }}
    .org-label {{ fill: {c['muted']}; font-size: 10px; }}
  </style>

  <rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1:.0f}" rx="12" fill="{c['bg']}" stroke="{c['border']}"/>

  <g transform="translate(0,0)">
    {header_svg}
  </g>

  <g>
    {grid_svg}
  </g>

  <g transform="translate(30, {langs_top:.0f})">
    {langs_svg}
  </g>

  <g transform="translate(30, {orgs_top:.0f})">
    {orgs_svg}
  </g>
</svg>"""
    return svg


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate a rich GitHub stats card for README.md")
    parser.add_argument("username", help="GitHub username")
    parser.add_argument("-o", "--output", default=None, help="Output file path (default: <username>_stats.<ext>)")
    parser.add_argument("-f", "--format", choices=["svg", "png"], default="svg", help="Output format (default: svg)")
    parser.add_argument("--theme", choices=list(THEMES.keys()), default="light", help="Card color theme")
    parser.add_argument("--token", default=None,
                         help="GitHub personal access token. Required for commit/PR/issue/review counts; "
                              "also raises API rate limits. Create one at https://github.com/settings/tokens")
    args = parser.parse_args()

    print(f"Fetching GitHub data for '{args.username}'...")
    stats = gather_stats(args.username, token=args.token)

    if not args.token:
        print("Note: no --token given, so commit/PR/issue/review counts are omitted "
              "(GitHub only exposes those totals via the authenticated API).")

    svg_code = build_svg(stats, theme_name=args.theme)
    out_path = args.output or f"{args.username}_stats.{args.format}"

    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    if args.format == "svg":
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(svg_code)
    else:
        import cairosvg
        cairosvg.svg2png(bytestring=svg_code.encode("utf-8"), write_to=out_path, scale=2)

    print(f"Done! Card saved to: {out_path}")
    print(f"\nAdd this to your README.md:\n\n![GitHub Stats]({out_path})\n")


if __name__ == "__main__":
    main()
