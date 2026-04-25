import requests
import os

# 1. 환경 변수에서 토큰 가져오기 (GitHub Actions 설정 필요)
TOKEN = os.environ.get('MY_GITHUB_TOKEN')
headers = {'Authorization': f'token {TOKEN}'}

LANG_COLORS = {
    "Python": "#3572A5", "JavaScript": "#f1e05a", "TypeScript": "#3178c6",
    "Rust": "#dea584", "OCaml": "#ef7a08", "Assembly": "#6E4C13",
    "WGSL": "#42ffc9", "C++": "#f34b7d", "Go": "#00ADD8", "Swift": "#F05138",
    "Shell": "#89e051", "Makefile": "#427819", "Haskell": "#5e5086",
    "Agda": "#31566a", "CMake": "#064F8C", "Rocq Prover": "#7d503f",
    "C": "#A8B9CC",
}
DEFAULT_COLOR = "#8b949e"
EXCLUDE = ["Jupyter Notebook", "HTML", "CSS"]

def get_github_stats():
    # 저장소 목록 가져오기
    repos_url = "https://api.github.com/user/repos?per_page=100"
    response = requests.get(repos_url, headers=headers)
    if response.status_code != 200:
        print(f"API Error: {response.status_code}")
        return None

    repos = response.json()
    stats = {}
    
    for repo in repos:
        if repo['fork']: continue
        # 각 저장소의 언어 데이터 호출
        lang_url = repo['languages_url']
        langs = requests.get(lang_url, headers=headers).json()
        for lang, bytes_count in langs.items():
            if lang in EXCLUDE: continue
            stats[lang] = stats.get(lang, 0) + bytes_count
    return stats

def make_svg(stats):
    if not stats: return
    
    sorted_stats = sorted(stats.items(), key=lambda x: x[1], reverse=True)
    total_bytes = sum(stats.values())

    # 디자인 설정
    width = 720
    height = 300 # 언어가 많을 경우를 대비해 넉넉히 설정
    svg = f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">'
    svg += f'<rect width="{width}" height="{height}" rx="15" fill="#0d1117" stroke="#30363d" stroke-width="1"/>'
    svg += f'<text x="25" y="35" fill="#58a6ff" font-family="Segoe UI, Arial" font-size="16" font-weight="bold">Language Proficiency</text>'

    start_x, start_y = 25, 65
    current_x, current_y = start_x, start_y
    GAP_BETWEEN_NAME_AND_PERCENT = 12
    PADDING_INTERNAL = 30
    
    for lang, b_count in sorted_stats:
        percentage = (b_count / total_bytes) * 100
        if percentage < 0.1: continue # 너무 적은 비중은 제외
        
        percent_text = f"{percentage:.1f}%"
        color = LANG_COLORS.get(lang, DEFAULT_COLOR)
        
        name_width = len(lang) * 8.5
        percent_width = len(percent_text) * 7
        badge_width = name_width + GAP_BETWEEN_NAME_AND_PERCENT + percent_width + PADDING_INTERNAL
        
        if current_x + badge_width > width - 25:
            current_x = start_x
            current_y += 45

        svg += f'<rect x="{current_x}" y="{current_y}" width="{badge_width}" height="32" rx="16" fill="{color}15" stroke="{color}" stroke-width="1.5"/>'
        svg += f'<text x="{current_x + 15}" y="{current_y + 21}" fill="{color}" font-family="Segoe UI, Arial" font-size="14" font-weight="bold">{lang}</text>'
        
        percent_x_pos = current_x + 15 + name_width + GAP_BETWEEN_NAME_AND_PERCENT
        svg += f'<text x="{percent_x_pos}" y="{current_y + 21}" fill="{color}aa" font-family="Segoe UI, Arial" font-size="12">{percent_text}</text>'
        
        current_x += badge_width + 12

    svg += '</svg>'
    
    with open("stats.svg", "w", encoding="utf-8") as f:
        f.write(svg)

if __name__ == "__main__":
    github_stats = get_github_stats()
    if github_stats:
        make_svg(github_stats)
        print("✅ SVG file has been created successfully!") # 이 로그가 찍히는지 확인
    else:
        print("❌ Failed to fetch stats. API token might be invalid.")
