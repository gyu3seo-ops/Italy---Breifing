import anthropic
import json
import os
import time
import re
from datetime import datetime
from zoneinfo import ZoneInfo

MILAN_TZ = ZoneInfo("Europe/Rome")
today = datetime.now(MILAN_TZ)
date_str = today.strftime("%Y년 %m월 %d일 (%a)")
date_iso = today.strftime("%Y-%m-%d")

client = None

PROMPTS = {
    "italy": f"Search web for today({date_iso}) Italy news. Return ONLY a JSON array, no other text: [{{\"category\":\"정치\",\"title\":\"title\",\"body\":\"2 sentence summary\",\"time\":\"today\"}}]. Include 2 economy, 2 politics, 1 society items.",
    "europe": f"Search web for today({date_iso}) Europe/EU news. Return ONLY a JSON array, no other text: [{{\"category\":\"유럽\",\"title\":\"title\",\"body\":\"2 sentence summary\",\"time\":\"today\"}}]. Include 4 items.",
    "global": f"Search web for today({date_iso}) global news. Return ONLY a JSON array, no other text: [{{\"category\":\"글로벌\",\"title\":\"title\",\"body\":\"2 sentence summary\",\"italy_angle\":\"Italy perspective 1 sentence\",\"time\":\"today\"}}]. Include 4 items."
}

STYLES = {
    "경제": ("#E6F1FB", "#0C447C"),
    "정치": ("#EEEDFE", "#3C3489"),
    "사회": ("#E1F5EE", "#085041"),
    "유럽": ("#FAEEDA", "#633806"),
    "글로벌": ("#FAECE7", "#712B13"),
}

def fetch_news(section, retries=3):
    for attempt in range(retries):
        try:
            time.sleep(10)
            resp = client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=1500,
                system="You are a news curator. Return ONLY valid JSON array. No markdown, no explanation, no code blocks. Just the raw JSON array starting with [ and ending with ].",
                tools=[{"type": "web_search_20250305", "name": "web_search"}],
                messages=[{"role": "user", "content": PROMPTS[section]}]
            )
            # 텍스트 블록만 추출
            text = ""
            for block in resp.content:
                if hasattr(block, "text") and block.text:
                    text += block.text

            text = text.strip()
            # JSON 배열 부분만 추출
            match = re.search(r'\[.*\]', text, re.DOTALL)
            if match:
                text = match.group(0)

            if not text:
                print(f"  ⚠️ {section} 응답 비어있음, 재시도 {attempt+1}/{retries}")
                continue

            result = json.loads(text)
            if result:
                return result
            print(f"  ⚠️ {section} 빈 배열, 재시도 {attempt+1}/{retries}")

        except json.JSONDecodeError as e:
            print(f"  ⚠️ {section} JSON 파싱 오류: {e}, 재시도 {attempt+1}/{retries}")
        except Exception as e:
            print(f"  ⚠️ {section} 오류: {e}, 재시도 {attempt+1}/{retries}")

    # 재시도 모두 실패시 기본값 반환
    cat = "유럽" if section == "europe" else ("글로벌" if section == "global" else "정치")
    return [{"category": cat, "title": f"{section} 뉴스를 불러오지 못했습니다", "body": "잠시 후 다시 시도해주세요.", "time": "오늘"}]

def card(item):
    cat = item.get("category", "글로벌")
    bg, fg = STYLES.get(cat, ("#FAECE7", "#712B13"))
    angle = f'<div class="ia">🇮🇹 이탈리아 시각: {item["italy_angle"]}</div>' if item.get("italy_angle") else ""
    title = str(item.get("title", "")).replace("<", "&lt;").replace(">", "&gt;")
    body = str(item.get("body", "")).replace("<", "&lt;").replace(">", "&gt;")
    return f'<div class="card"><div class="ct"><span class="pill" style="background:{bg};color:{fg}">{cat}</span><span class="tm">{item.get("time","오늘")}</span></div><div class="ttl">{title}</div><div class="bdy">{body}</div>{angle}</div>'

def build_html(italy, europe, glob):
    css = """*{box-sizing:border-box;margin:0;padding:0}body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#f5f5f0;color:#1a1a1a}.wrap{max-width:720px;margin:0 auto;padding:2rem 1.25rem 4rem}.top{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:1.5rem;flex-wrap:wrap;gap:8px}.top h1{font-size:20px;font-weight:600}.top p{font-size:12px;color:#888;margin-top:3px}.db{font-size:12px;padding:5px 12px;border-radius:8px;background:#fff;border:1px solid #e0e0e0;color:#555}.tabs{display:flex;gap:6px;margin-bottom:1.25rem}.tab{padding:7px 18px;font-size:13px;font-weight:500;border-radius:8px;border:1px solid #ddd;cursor:pointer;color:#555;background:#fff}.tab.on{background:#dbeafe;color:#1e40af;border-color:transparent}.pane{display:none}.pane.on{display:block}.card{background:#fff;border:1px solid #e8e8e8;border-radius:12px;padding:1rem 1.25rem;margin-bottom:10px}.ct{display:flex;align-items:center;gap:8px;margin-bottom:8px}.pill{font-size:11px;font-weight:600;padding:3px 10px;border-radius:99px}.tm{font-size:11px;color:#aaa;margin-left:auto}.ttl{font-size:14px;font-weight:600;line-height:1.5;margin-bottom:6px}.bdy{font-size:13px;color:#555;line-height:1.65}.ia{margin-top:9px;padding:7px 10px;border-left:2px solid #d4537e;background:#fbeaf0;font-size:12px;color:#72243e;line-height:1.55}.ft{text-align:center;font-size:11px;color:#bbb;margin-top:2rem}"""
    js = "function sw(id,el){document.querySelectorAll('.pane').forEach(p=>p.classList.remove('on'));document.querySelectorAll('.tab').forEach(t=>t.classList.remove('on'));document.getElementById(id).classList.add('on');el.classList.add('on');}"
    it = "".join(card(i) for i in italy)
    eu = "".join(card(i) for i in europe)
    gl = "".join(card(i) for i in glob)
    return f"""<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>밀라노 브리핑 {date_str}</title><style>{css}</style></head><body><div class="wrap"><div class="top"><div><h1>밀라노 주재원 데일리 브리핑</h1><p>이탈리아 · 유럽 · 글로벌</p></div><div class="db">{date_str}</div></div><div class="tabs"><div class="tab on" onclick="sw('it',this)">🇮🇹 이탈리아</div><div class="tab" onclick="sw('eu',this)">🇪🇺 유럽</div><div class="tab" onclick="sw('gl',this)">🌐 글로벌</div></div><div id="it" class="pane on">{it}</div><div id="eu" class="pane">{eu}</div><div id="gl" class="pane">{gl}</div><div class="ft">자동 생성 — {date_str}</div></div><script>{js}</script></body></html>"""

def main():
    global client
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다.")
    client = anthropic.Anthropic(api_key=api_key)

    print("📰 이탈리아 뉴스...")
    italy = fetch_news("italy")
    print(f"  ✓ {len(italy)}개")

    print("🇪🇺 유럽 뉴스...")
    europe = fetch_news("europe")
    print(f"  ✓ {len(europe)}개")

    print("🌐 글로벌 뉴스...")
    glob = fetch_news("global")
    print(f"  ✓ {len(glob)}개")

    os.makedirs("docs", exist_ok=True)
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(build_html(italy, europe, glob))
    print("✅ 완료! docs/index.html 생성됨")

if __name__ == "__main__":
    main()
