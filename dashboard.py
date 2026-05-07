# https://github.com/jihoo12/legendary-enigma/blob/main/main.py
import requests
import math
import os
import re
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

def update_readme(username):
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
    
    bar = "█" * int(20 * lvl['progress_pct']) + "░" * (20 - int(20 * lvl['progress_pct']))
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

    # The new stats block
    new_stats = f"""
### 📊 Developer Stats
| Metric | Value |
| :--- | :--- |
| **Level** | {lvl['level']} |
| **XP** | {lvl['xp']} / {lvl['next_lvl_base']} |
| **Stars** | {total_stars} |

**Progress:** `Level {lvl['level']}` **[{bar}]** `Level {lvl['level'] + 1}`
*Last updated: {timestamp}*
"""

    # Read the existing README
    with open("README.md", "r", encoding="utf-8") as f:
        readme_contents = f.read()

    # Use Regex to find the markers and replace only what's inside
    pattern = r"(<!-- START_SECTION:dashboard -->)(.*)(<!-- END_SECTION:dashboard -->)"
    # re.DOTALL allows the .* to match newlines
    new_readme = re.sub(pattern, f"\\1\n{new_stats}\n\\3", readme_contents, flags=re.DOTALL)

    # Write it back
    with open("README.md", "w", encoding="utf-8") as f:
        f.write(new_readme)

if __name__ == "__main__":
    user = os.getenv('GITHUB_REPOSITORY_OWNER')
    update_readme(user)