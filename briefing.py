import anthropic
import json
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

MILAN_TZ = ZoneInfo("Europe/Rome")
today = datetime.now(MILAN_TZ)
date_str = today.strftime("%Y년 %m월 %d일 (%a)")h
date_iso = today.strftime("%Y-%m-%d")

SYSTEM_PROMPT = "이탈리아 밀라노 주재원을 위한 뉴스 큐레이터. 반드시 순수 JSON 배열만 반환. 코드블록 금지."

PROMPTS = {
    "italy": f"오늘({date_iso}) 이탈리아 뉴스를 웹검색해서 경제2개 정치2개 사회1개 총5개 선별. JSON만: [{{\"category\":\"경제\",\"title\":\"제목\",\"body\":\"2문장\",\"time\":\"오늘\"}}]",
    "europe": f"오늘({date_iso}) 유럽 주요뉴스 4개 웹검색. JSON만: [{{\"category\":\"유럽\",\"title\":\"제목\",\"body\":\"2문장\",\"time\":\"오늘\"}}]",
    "global": f"오늘({date_iso}) 글로벌 주요뉴스 4개 웹검색하고 각 이탈리아 관점 추가. JSON만: [{{\"category\":\"글로벌\",\"title\":\"제목\",\"body\":\"2문장\",\"italy_angle\":\"이탈리아 시각\",\"time\":\"오늘\"}}]"
}

STYLES = {
    "경제": ("#E6F1FB", "#0C447C"),
    "정치": ("#EEEDFE", "#3C3489"),
    "사회": ("#E1F5EE", "#085041"),
    "유럽": ("#FAEEDA", "#633806"),
    "글로벌": ("#FAECE7", "#712B13"),
}

def fetch_news(client, section):
    time.sleep(8)
    resp = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": PROMPTS[section]}]
    )
    text = "".join(b.text for b in resp.content if hasattr(b, "text")).strip()
    text = text.replace("```json", "").replace("```", "").strip()
    return json.loads(text)

def card(item):
    cat = item.get("category", "글로벌")
    bg, fg = STYLES.get(cat, ("#FAECE7", "#712B13"))
    angle = f'<div class="ia">🇮🇹 이탈리아 시각: {item["italy_angle"]}</div>' if item.get("italy_angle") else ""
    return f'<div class="card"><div class="ct"><span class="pill" style="background:{bg};color:{fg}">{cat}</span><span class="tm">{item.get("time","오늘")}</span></div><div class="ttl">{item["title"]}</div><div class="bdy">{item["body"]}</div>{angle}</div>'

def build_html(italy, europe, glob):
    css = """*{box-sizing:border-box;margin:0;padding:0}body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#f5f5f0;color:#1a1a1a}.wrap{max-width:720px;margin:0 auto;padding:2rem 1.25rem 4rem}.top{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:1.5rem;flex-wrap:wrap;gap:8px}.top h1{font-size:20px;font-weight:600}.top p{font-size:12px;color:#888;margin-top:3px}.db{font-size:12px;padding:5px 12px;border-radius:8px;background:#fff;border:1px solid #e0e0e0;color:#555}.tabs{display:flex;gap:6px;margin-bottom:1.25rem}.tab{padding:7px 18px;font-size:13px;font-weight:500;border-radius:8px;border:1px solid #ddd;cursor:pointer;color:#555;background:#fff}.tab.on{background:#dbeafe;color:#1e40af;border-color:transparent}.pane{display:none}.pane.on{display:block}.card{background:#fff;border:1px solid #e8e8e8;border-radius:12px;padding:1rem 1.25rem;margin-bottom:10px}.ct{display:flex;align-items:center;gap:8px;margin-bottom:8px}.pill{font-size:11px;font-weight:600;padding:3px 10px;border-radius:99px}.tm{font-size:11px;color:#aaa;margin-left:auto}.ttl{font-size:14px;font-weight:600;line-height:1.5;margin-bottom:6px}.bdy{font-size:13px;color:#555;line-height:1.65}.ia{margin-top:9px;padding:7px 10px;border-left:2px solid #d4537e;background:#fbeaf0;font-size:12px;color:#72243e;line-height:1.55}.ft{text-align:center;font-size:11px;color:#bbb;margin-top:2rem}"""
    js = "function sw(id,el){document.querySelectorAll('.pane').forEach(p=>p.classList.remove('on'));document.querySelectorAll('.tab').forEach(t=>t.classList.remove('on'));document.getElementById(id).classList.add('on');el.classList.add('on');}"
    it = "".join(card(i) for i in italy)
    eu = "".join(card(i) for i in europe)
    gl = "".join(card(i) for i in glob)
    return f"""<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>밀라노 브리핑 — {date_str}</title><style>{css}</style></head><body><div class="wrap"><div class="top"><div><h1>밀라노 주재원 데일리 브리핑</h1><p>이탈리아 · 유럽 · 글로벌</p></div><div class="db">{date_str}</div></div><div class="tabs"><div class="tab on" onclick="sw('it',this)">🇮🇹 이탈리아</div><div class="tab" onclick="sw('eu',this)">🇪🇺 유럽</div><div class="tab" onclick="sw('gl',this)">🌐 글로벌</div></div><div id="it" class="pane on">{it}</div><div id="eu" class="pane">{eu}</div><div id="gl" class="pane">{gl}</div><div class="ft">자동 생성 — {date_str} · Claude API</div></div><script>{js}</script></body></html>"""

def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다.")
    client = anthropic.Anthropic(api_key=api_key)
    print("📰 이탈리아 뉴스...")
    italy = fetch_news(client, "italy")
    print("🇪🇺 유럽 뉴스...")
    europe = fetch_news(client, "europe")
    print("🌐 글로벌 뉴스...")
    glob = fetch_news(client, "global")
    os.makedirs("docs", exist_ok=True)
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(build_html(italy, europe, glob))
    print("✅ 완료!")

if __name__ == "__main__":
    main()
