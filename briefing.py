"""
Italy Expat Daily News Briefing
매일 아침 자동으로 뉴스를 검색하고 인터랙티브 HTML 브리핑을 생성합니다.
"""

import anthropic
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

MILAN_TZ = ZoneInfo("Europe/Rome")
today = datetime.now(MILAN_TZ)
date_str = today.strftime("%Y년 %m월 %d일 (%a)")
date_iso = today.strftime("%Y-%m-%d")

SYSTEM_PROMPT = f"""당신은 이탈리아 밀라노 주재원을 위한 뉴스 큐레이터입니다.
오늘 날짜는 {date_iso}입니다. 반드시 순수 JSON만 반환하세요. 마크다운 코드블록, 설명, 주석은 절대 금지.
각 뉴스는 반드시 {date_iso} 기준 최근 48시간 이내에 보도된 뉴스만 선택하세요.
절대 금지 주제: 올림픽(동계/하계/패럴림픽 포함), 폐막식, 개막식, 밀라노-코르티나 등 이미 종료된 스포츠 이벤트. 후속 기사/결산 포함 어떤 형태로도 절대 포함 금지.
이탈리아어/영어 소스(ANSA, Corriere della Sera, La Repubblica, Reuters, BBC 등)를 웹 검색해서 사용하세요."""

PROMPTS = {
    "italy": f"""오늘({date_iso}) 이탈리아 주요 뉴스를 웹에서 검색해서 경제 2개, 정치 2개, 사회 1개, 총 5개를 선별해줘.
반드시 {date_iso} 기준 48시간 이내 뉴스여야 함. 절대 포함 금지: 올림픽, 패럴림픽, 밀라노-코르티나, 폐막식, 개막식 관련 뉴스는 단 1개도 포함하지 말 것.
JSON 배열만 반환:
[{{"category":"경제","title":"제목","body":"2-3문장 요약","time":"오늘"}}]""",

    "europe": f"""오늘({date_iso}) 유럽(EU 포함) 주요 뉴스를 웹에서 검색해서 4개 선별해줘.
반드시 {date_iso} 기준 48시간 이내 뉴스여야 함.
절대 포함 금지: 올림픽, 패럴림픽, 폐막식, 개막식 관련 뉴스는 단 1개도 포함하지 말 것.
JSON 배열만 반환:
[{{"category":"유럽","title":"제목","body":"2-3문장 요약","time":"오늘"}}]""",

    "global": f"""오늘({date_iso}) 글로벌 주요 뉴스를 웹에서 검색해서 4개 선별하고, 각각 이탈리아의 반응/관점을 추가해줘.
반드시 {date_iso} 기준 48시간 이내 뉴스여야 함.
절대 포함 금지: 올림픽, 패럴림픽, 폐막식, 개막식 관련 뉴스는 단 1개도 포함하지 말 것.
JSON 배열만 반환:
[{{"category":"글로벌","title":"제목","body":"2-3문장 요약","italy_angle":"이탈리아 시각 1문장","time":"오늘"}}]"""
}

CATEGORY_STYLE = {
    "경제":   ("p-eco", "#E6F1FB", "#0C447C"),
    "정치":   ("p-pol", "#EEEDFE", "#3C3489"),
    "사회":   ("p-soc", "#E1F5EE", "#085041"),
    "유럽":   ("p-eu",  "#FAEEDA", "#633806"),
    "글로벌": ("p-glb", "#FAECE7", "#712B13"),
}

def fetch_news(client, section: str) -> list:
    """Claude API + web_search로 뉴스를 가져옵니다."""
    resp = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": PROMPTS[section]}]
    )
    text = "".join(b.text for b in resp.content if hasattr(b, "text")).strip()
    text = text.replace("```json", "").replace("```", "").strip()
    return json.loads(text)

def render_card(item: dict) -> str:
    cat = item.get("category", "글로벌")
    cls, bg, fg = CATEGORY_STYLE.get(cat, ("p-glb", "#FAECE7", "#712B13"))
    pill = f'<span class="pill" style="background:{bg};color:{fg}">{cat}</span>'
    time_badge = f'<span class="card-time">{item.get("time","오늘")}</span>'
    angle_html = ""
    if item.get("italy_angle"):
        angle_html = f'<div class="it-angle">🇮🇹 이탈리아 시각: {item["italy_angle"]}</div>'
    return f"""
    <div class="card">
      <div class="card-top">{pill}{time_badge}</div>
      <div class="card-title">{item["title"]}</div>
      <div class="card-body">{item["body"]}</div>
      {angle_html}
    </div>"""

def build_html(italy: list, europe: list, global_: list) -> str:
    it_cards  = "".join(render_card(i) for i in italy)
    eu_cards  = "".join(render_card(i) for i in europe)
    gl_cards  = "".join(render_card(i) for i in global_)

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>밀라노 주재원 브리핑 — {date_str}</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
         background: #f5f5f0; color: #1a1a1a; min-height: 100vh; }}
  .wrap {{ max-width: 720px; margin: 0 auto; padding: 2rem 1.25rem 4rem; }}
  .top {{ display: flex; justify-content: space-between; align-items: flex-start;
          margin-bottom: 1.5rem; flex-wrap: wrap; gap: 8px; }}
  .top h1 {{ font-size: 20px; font-weight: 600; }}
  .top p  {{ font-size: 12px; color: #888; margin-top: 3px; }}
  .datebadge {{ font-size: 12px; padding: 5px 12px; border-radius: 8px;
                background: #fff; border: 1px solid #e0e0e0; color: #555; white-space: nowrap; }}
  .tabs {{ display: flex; gap: 6px; margin-bottom: 1.25rem; }}
  .tab {{ padding: 7px 18px; font-size: 13px; font-weight: 500; border-radius: 8px;
          border: 1px solid #ddd; cursor: pointer; color: #555;
          background: #fff; transition: all .12s; user-select: none; }}
  .tab.on {{ background: #dbeafe; color: #1e40af; border-color: transparent; }}
  .tab:hover:not(.on) {{ background: #f0f0f0; }}
  .pane {{ display: none; }}
  .pane.on {{ display: block; }}
  .card {{ background: #fff; border: 1px solid #e8e8e8; border-radius: 12px;
           padding: 1rem 1.25rem; margin-bottom: 10px; }}
  .card-top {{ display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }}
  .pill {{ font-size: 11px; font-weight: 600; padding: 3px 10px; border-radius: 99px; }}
  .card-time {{ font-size: 11px; color: #aaa; margin-left: auto; }}
  .card-title {{ font-size: 14px; font-weight: 600; line-height: 1.5; margin-bottom: 6px; }}
  .card-body {{ font-size: 13px; color: #555; line-height: 1.65; }}
  .it-angle {{ margin-top: 9px; padding: 7px 10px; border-left: 2px solid #d4537e;
               background: #fbeaf0; font-size: 12px; color: #72243e; line-height: 1.55; }}
  .footer {{ text-align: center; font-size: 11px; color: #bbb; margin-top: 2rem; }}
</style>
</head>
<body>
<div class="wrap">
  <div class="top">
    <div>
      <h1>밀라노 주재원 데일리 브리핑</h1>
      <p>이탈리아 · 유럽 · 글로벌</p>
    </div>
    <div class="datebadge">{date_str}</div>
  </div>

  <div class="tabs">
    <div class="tab on" onclick="sw('it',this)">🇮🇹 이탈리아</div>
    <div class="tab" onclick="sw('eu',this)">🇪🇺 유럽</div>
    <div class="tab" onclick="sw('gl',this)">🌐 글로벌</div>
  </div>

  <div id="it" class="pane on">{it_cards}</div>
  <div id="eu" class="pane">{eu_cards}</div>
  <div id="gl" class="pane">{gl_cards}</div>

  <div class="footer">자동 생성 — {date_str} · Claude API + web search</div>
</div>
<script>
function sw(id, el) {{
  document.querySelectorAll('.pane').forEach(p => p.classList.remove('on'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('on'));
  document.getElementById(id).classList.add('on');
  el.classList.add('on');
}}
</script>
</body>
</html>"""

def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다.")

    client = anthropic.Anthropic(api_key=api_key)

    print("📰 이탈리아 뉴스 검색 중...")
    italy = fetch_news(client, "italy")

    print("🇪🇺 유럽 뉴스 검색 중...")
    europe = fetch_news(client, "europe")

    print("🌐 글로벌 뉴스 검색 중...")
    global_ = fetch_news(client, "global")

    html = build_html(italy, europe, global_)

    os.makedirs("docs", exist_ok=True)
    out = f"docs/index.html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✅ 완료! → {out}")

if __name__ == "__main__":
    main()
