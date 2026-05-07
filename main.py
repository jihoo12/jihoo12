#https://github.com/jihoo12/legendary-enigma/blob/main/main.py
import requests
import math
import os
from datetime import datetime

TOKEN = os.getenv('MY_GITHUB_TOKEN')
URL = 'https://api.github.com/graphql'

def calculate_level(stats):
    commits = stats.get('totalCommitContributions', 0)
    prs = stats.get('totalPullRequestContributions', 0)
    issues = stats.get('totalIssueContributions', 0)
    reviews = stats.get('totalPullRequestReviewContributions', 0)
    stars = stats.get('stars', 0)
    xp = (commits * 1) + (prs * 5) + (reviews * 4) + (issues * 1) + (stars * 2)
    level = int(math.sqrt(xp / 10)) if xp > 0 else 0
    current_lvl_base = (level ** 2) * 10
    next_lvl_base = ((level + 1) ** 2) * 10
    denom = next_lvl_base - current_lvl_base
    progress_pct = (xp - current_lvl_base) / denom if denom > 0 else 0
    return {"level": level, "xp": xp, "next_lvl_base": next_lvl_base, "progress_pct": progress_pct}

def generate_svg(stats, lvl):
    width = 450
    height = 240
    progress_width = 400
    fill_width = int(progress_width * lvl['progress_pct'])
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M UTC")

    # Catppuccin Latte Palette
    # Base: #eff1f5, Blue: #1e66f5, Rosewater: #dc8a78, Text: #4c4f69, Subtext: #6c6f85, Surface: #ccd0da
    
    svg = f"""
<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <style>
    .header {{ font: 700 22px 'Segoe UI', Ubuntu, Sans-Serif; fill: #1e66f5; }}
    .stat {{ font: 600 14px 'Segoe UI', Ubuntu, Sans-Serif; fill: #6c6f85; }}
    .value {{ font: 700 16px 'Segoe UI', Ubuntu, Sans-Serif; fill: #4c4f69; }}
    .level-badge {{ font: 800 28px 'Segoe UI', Ubuntu, Sans-Serif; fill: #ea76cb; filter: drop-shadow(0 0 2px #ea76cb); }}
    .small {{ font: 400 10px 'Segoe UI', Ubuntu, Sans-Serif; fill: #9ca0b0; }}
    .bar-bg {{ fill: #ccd0da; }}
    .bar-fill {{ fill: url(#grad); }}
  </style>
  
  <defs>
    <!-- Background Gradient (Base to Mantle) -->
    <linearGradient id="rectGrad" x1="0" y1="0" x2="{width}" y2="{height}" gradientUnits="userSpaceOnUse">
      <stop stop-color="#eff1f5"/>
      <stop offset="1" stop-color="#e6e9ef"/>
    </linearGradient>
    <!-- Progress Bar Gradient (Sapphire to Blue) -->
    <linearGradient id="grad" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#209fb5"/>
      <stop offset="100%" stop-color="#1e66f5"/>
    </linearGradient>
  </defs>

  <!-- Background -->
  <rect width="{width}" height="{height}" rx="15" fill="url(#rectGrad)" stroke="#bcc0cc" stroke-width="2"/>
  
  <!-- Header & Level -->
  <text x="30" y="45" class="header">🚀 Dev Rank</text>
  <text x="330" y="55" class="level-badge">Lv {lvl['level']}</text>
  
  <!-- Stats Grid -->
  <g transform="translate(30, 80)">
    <text y="0" class="stat">Commits</text>
    <text x="100" y="0" class="value">{stats['totalCommitContributions']}</text>
    
    <text y="30" class="stat">PRs</text>
    <text x="100" y="30" class="value">{stats['totalPullRequestContributions']}</text>
    
    <text y="60" class="stat">Reviews</text>
    <text x="100" y="60" class="value">{stats['totalPullRequestReviewContributions']}</text>

    <text x="200" y="0" class="stat">Issues</text>
    <text x="280" y="0" class="value">{stats['totalIssueContributions']}</text>

    <text x="200" y="30" class="stat">Stars</text>
    <text x="280" y="30" class="value">{stats['stars']}</text>
    
    <text x="200" y="60" class="stat">Total XP</text>
    <text x="280" y="60" class="value">{lvl['xp']}</text>
  </g>

  <!-- Progress Bar -->
  <text x="30" y="180" class="stat">Progress to Lvl {lvl['level'] + 1}</text>
  <rect x="25" y="190" width="{progress_width}" height="12" rx="6" class="bar-bg"/>
  <rect x="25" y="190" width="{fill_width}" height="12" rx="6" class="bar-fill"/>
  
  <text x="30" y="225" class="small">Updated {timestamp}</text>
</svg>
"""
    return svg

def update_stats(username):
    query = """
    query($login: String!) {
      user(login: $login) {
        repositories(first: 100, ownerAffiliations: OWNER, privacy: PUBLIC) {
          nodes { stargazerCount }
        }
        contributionsCollection {
          totalCommitContributions
          totalIssueContributions
          totalPullRequestContributions
          totalPullRequestReviewContributions
        }
      }
    }
    """
    headers = {"Authorization": f"Bearer {TOKEN}"}
    response = requests.post(URL, json={'query': query, 'variables': {"login": username}}, headers=headers)
    data = response.json().get('data', {}).get('user')
    
    stats = data['contributionsCollection']
    total_stars = sum(repo['stargazerCount'] for repo in data['repositories']['nodes'])
    stats['stars'] = total_stars
    lvl = calculate_level(stats)
    
    # Generate and save SVG
    svg_content = generate_svg(stats, lvl)
    with open("stats.svg", "w", encoding="utf-8") as f:
        f.write(svg_content)

if __name__ == "__main__":
    user = os.getenv('GITHUB_REPOSITORY_OWNER')
    update_stats(user)