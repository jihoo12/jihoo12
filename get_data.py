import requests
import json
import os

TOKEN = ""
headers = {'Authorization': f'token {TOKEN}'}

def save_github_data():
    repos_url = "https://api.github.com/user/repos?per_page=100"
    repos = requests.get(repos_url, headers=headers).json()
    
    all_data = []
    for repo in repos:
        if repo['fork']: continue
        
        print(f"Fetching data for {repo['name']}...")
        lang_url = repo['languages_url']
        langs = requests.get(lang_url, headers=headers).json()
        
        all_data.append({
            "name": repo['name'],
            "languages": langs
        })
    
    # 데이터를 로컬 JSON 파일로 저장
    with open("github_data.json", "w", encoding="utf-8") as f:
        json.dump(all_data, f, indent=4)
    print("\n✅ 성공! 'github_data.json' 파일이 생성되었습니다.")

if __name__ == "__main__":
    save_github_data()