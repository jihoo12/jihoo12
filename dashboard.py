# https://github.com/jihoo12/legendary-enigma/blob/main/main.py
import requests
import math
import os
from datetime import datetime

# Environment Variables
TOKEN = os.getenv('MY_GITHUB_TOKEN')
URL = 'https://api.github.com/graphql'

def calculate_level(stats):
    """
    Calculates XP and Level. 
    Formula: Level = sqrt(XP / 10)
    """
    commits = stats.get('totalCommitContributions', 0)
    prs = stats.get('totalPullRequestContributions', 0)
    issues = stats.get('totalIssueContributions', 0)
    reviews = stats.get('totalPullRequestReviewContributions', 0)
    stars = stats.get('stars', 0)

    xp = (commits * 1) + (prs * 5) + (reviews * 4) + (issues * 1) + (stars * 2)
    level = int(math.sqrt(xp / 10)) if xp > 0 else 0
    
    current_lvl_base = (level ** 2) * 10
    next_lvl_base = ((level + 1) ** 2) * 10
    
    # Calculate progress safely
    denom = next_lvl_base - current_lvl_base
    progress_pct = (xp - current_lvl_base) / denom if denom > 0 else 0

    return {
        "level": level, 
        "xp": xp, 
        "next_lvl_base": next_lvl_base, 
        "progress_pct": progress_pct
    }

def update_readme(username):
    query = """
    query($login: String!) {
      user(login: $login) {
        name
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
    try:
        response = requests.post(URL, json={'query': query, 'variables': {"login": username}}, headers=headers)
        response.raise_for_status()
        
        data = response.json().get('data', {}).get('user')
        if not data:
            print("Error: Could not find user data.")
            return

        stats = data['contributionsCollection']
        total_stars = sum(repo['stargazerCount'] for repo in data['repositories']['nodes'])
        stats['stars'] = total_stars

        lvl = calculate_level(stats)
        
        # Build the visual progress bar
        bar_size = 20
        filled = int(bar_size * lvl['progress_pct'])
        bar = "█" * filled + "░" * (bar_size - filled)
        
        # Clean timestamp using Python's datetime (replaces deprecated os.popen)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

        # Markdown Template
        content = f"""# 🚀 Dashboard: {username}

### 📊 My Stats
| Metric | Value |
| :--- | :--- |
| **Current Level** | {lvl['level']} |
| **Total XP** | {lvl['xp']} / {lvl['next_lvl_base']} |
| **Commits** | {stats['totalCommitContributions']} |
| **PRs** | {stats['totalPullRequestContributions']} |
| **Reviews** | {stats['totalPullRequestReviewContributions']} |
| **Issues** | {stats['totalIssueContributions']} |
| **Stars** | {total_stars} |

### 📈 Level Progress
`Level {lvl['level']}` **[{bar}]** `Level {lvl['level'] + 1}`

*Last updated on: {timestamp}*
"""
        with open("README.md", "w", encoding="utf-8") as f:
            f.write(content)
        print("Successfully updated README.md")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    # GITHUB_REPOSITORY_OWNER is automatically provided by GitHub Actions
    target_user = os.getenv('GITHUB_REPOSITORY_OWNER')
    
    if not TOKEN:
        print("Error: DASHBOARD_TOKEN environment variable is not set.")
    elif not target_user:
        print("Error: Could not determine GitHub username.")
    else:
        update_readme(target_user)