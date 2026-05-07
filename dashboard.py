# https://github.com/jihoo12/legendary-enigma/blob/main/main.py
import requests
import math
import os

# --- CONFIGURATION ---
TOKEN = os.getenv('MY_GITHUB_TOKEN')
URL = 'https://api.github.com/graphql'

def calculate_level(stats):
    """
    Calculates XP and a numerical Level.
    Formula: Level = sqrt(XP / 10)
    Weights: PRs (5), Reviews (4), Commits (1), Issues (1), Stars (2)
    """
    # Extract data with defaults
    commits = stats.get('totalCommitContributions', 0)
    prs = stats.get('totalPullRequestContributions', 0)
    issues = stats.get('totalIssueContributions', 0)
    reviews = stats.get('totalPullRequestReviewContributions', 0)
    stars = stats.get('stars', 0)

    # Calculate total XP
    xp = (commits * 1) + (prs * 5) + (reviews * 4) + (issues * 1) + (stars * 2)

    # Calculate Level based on a curve
    # Level 1 = 10 XP | Level 10 = 1000 XP | Level 20 = 4000 XP
    level = int(math.sqrt(xp / 10)) if xp > 0 else 0
    
    # Calculate XP required for the current and next level
    current_lvl_base = (level ** 2) * 10
    next_lvl_base = ((level + 1) ** 2) * 10
    xp_needed = next_lvl_base - xp
    
    # Progress percentage within the current level
    progress_pct = (xp - current_lvl_base) / (next_lvl_base - current_lvl_base) if xp > 0 else 0

    return {
        "level": level,
        "xp": xp,
        "xp_needed": xp_needed,
        "next_lvl_base": next_lvl_base,
        "progress_pct": progress_pct
    }

def get_user_dashboard(username):
    query = """
    query($login: String!) {
      user(login: $login) {
        name
        followers { totalCount }
        repositories(first: 100, ownerAffiliations: OWNER, privacy: PUBLIC) {
          nodes {
            stargazerCount
          }
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
    
    variables = {"login": username}
    headers = {"Authorization": f"Bearer {TOKEN}"}
    
    try:
        response = requests.post(URL, json={'query': query, 'variables': variables}, headers=headers)
        response.raise_for_status()
        res_json = response.json()
        
        if not res_json.get('data') or not res_json['data']['user']:
            print(f"Error: User '{username}' not found.")
            return

        user_data = res_json['data']['user']
        stats = user_data['contributionsCollection']
        
        # Aggregate stars
        total_stars = sum(repo['stargazerCount'] for repo in user_data['repositories']['nodes'])
        stats['stars'] = total_stars 

        # Level Logic
        lvl_data = calculate_level(stats)
        
        # Create Progress Bar
        bar_length = 20
        filled_length = int(bar_length * lvl_data['progress_pct'])
        bar = "█" * filled_length + "░" * (bar_length - filled_length)

        # Output
        print(f"\n{'='*40}")
        print(f" {username.upper()}'S DEVELOPER PROFILE")
        print(f"{'='*40}")
        print(f"Name:         {user_data['name'] or 'N/A'}")
        print(f"Level:        {lvl_data['level']}")
        print(f"XP:           {lvl_data['xp']} / {lvl_data['next_lvl_base']}")
        print(f"Progress:     [{bar}] {int(lvl_data['progress_pct']*100)}%")
        print(f"To Next Lvl:  {lvl_data['xp_needed']} XP")
        print("-" * 40)
        print(f"Commits:      {stats['totalCommitContributions']}")
        print(f"PRs:          {stats['totalPullRequestContributions']}")
        print(f"Reviews:      {stats['totalPullRequestReviewContributions']}")
        print(f"Issues:       {stats['totalIssueContributions']}")
        print(f"Stars:        {total_stars}")
        print(f"Followers:    {user_data['followers']['totalCount']}")
        print(f"{'='*40}\n")

    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    # Replace with your actual GitHub username
    # Ensure TOKEN is set at the top of the script
    target_user = "your-username-here" 
    
    if TOKEN == 'YOUR_GITHUB_TOKEN':
        print("Please set your GitHub Personal Access Token at the top of the script.")
    else:
        get_user_dashboard(target_user)