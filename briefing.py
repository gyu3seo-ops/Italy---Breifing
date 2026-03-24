import anthropic
import json
import os
import re
import time
from datetime import datetime
from zoneinfo import ZoneInfo

MILAN_TZ = ZoneInfo("Europe/Rome")
today = datetime.now(MILAN_TZ)
date_str = today.strftime("%Y년 %m월 %d일 (%a)")
date_str_en = today.strftime("%B %d, %Y (%a)")
date_iso = today.strftime("%Y-%m-%d")
date_ita = today.strftime("%-d %B %Y")

client = None

PROMPTS = {
    "italy": f"""Today is {date_iso} ({date_ita}). Search for Italian news published TODAY only.
Do NOT include news older than today. Search queries must include today's date.
Return ONLY a valid JSON array. No markdown, no explanation, no cite tags.
Include: 2 economy, 2 politics, 1 society items.
[{{"category":"경제","category_en":"Economy","title":"한글 제목","title_en":"English title","body":"한글 2문장 요약","body_en":"2 sentence summary in English","source":"출처 사이트명","url":"https://...","time":"{date_iso}"}}]""",

    "europe": f"""Today is {date_iso} ({date_ita}). Search for European/EU news published TODAY only.
Do NOT include news older than today. Search queries must include today's date.
Return ONLY a valid JSON array. No markdown, no explanation, no cite tags. Include 4 items.
[{{"category":"유럽","category_en":"Europe","title":"한글 제목","title_en":"English title","body":"한글 2문장 요약","body_en":"2 sentence summary in English","source":"출처 사이트명","url":"https://...","time":"{date_iso}"}}]""",

    "global": f"""Today is {date_iso} ({date_ita}). Search for global news published TODAY only.
Do NOT include news older than today. Search queries must include today's date.
Return ONLY a valid JSON array. No markdown, no explanation, no cite tags. Include 4 items.
[{{"category":"글로벌","category_en":"Global","title":"한글 제목","title_en":"English title","body":"한글 2문장 요약","body_en":"2 sentence summary in English","italy_angle":"이탈리아 시각 1문장 (한글)","italy_angle_en":"Italy perspective 1 sentence (English)","source":"출처 사이트명","url":"https://...","time":"{date_iso}"}}]"""
}

STYLES = {
    "경제":  ("#E6F1FB", "#0C447C"),
    "Economy": ("#E6F1FB", "#0C447C"),
    "정치":  ("#EEEDFE", "#3C3489"),
    "Politics": ("#EEEDFE", "#3C3489"),
    "사회":  ("#E1F5EE", "#085041"),
    "Society": ("#E1F5EE", "#085041"),
    "유럽":  ("#FAEEDA", "#633806"),
    "Europe": ("#FAEEDA", "#633806"),
    "글로벌": ("#FAECE7", "#712B13"),
    "Global": ("#FAECE7", "#712B13"),
}

def clean_text(text):
    text = re.sub(r'<cite[^>]*>(.*?)</cite>', r'\1', text, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'```[\w]*\n?', '', text)
    return text.strip()

def fetch_news(section, retries=3):
    for attempt in range(retries):
        try:
            time.sleep(10)
            resp = client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=2000,
                system=f"You are a news curator. Today is {date_iso}. Only include news from today. Return ONLY raw JSON array starting with [ and ending with ]. No markdown, no cite tags, no explanation.",
                tools=[{"type": "web_search_20250305", "name": "web_search"}],
                messages=[{"role": "user", "content": PROMPTS[section]}]
            )
            raw = ""
            for block in resp.content:
                if hasattr(block, "text") and block.text:
                    raw += block.text
            raw = clean_text(raw)
            match = re.search(r'\[.*\]', raw, re.DOTALL)
            if not match:
                print(f"  ⚠️ {section} JSON 없음, 재시도 {attempt+1}/{retries}")
                continue
            result = json.loads(match.group(0))
            if result:
                print(f"  ✓ {len(result)}개")
                return result
        except json.JSONDecodeError as e:
            print(f"  ⚠️ JSON 오류: {e}, 재시도 {attempt+1}/{retries}")
        except Exception as e:
            print(f"  ⚠️ 오류: {e}, 재시도 {attempt+1}/{retries}")
    cat = "유럽" if section == "europe" else ("글로벌" if section == "global" else "정치")
    cat_en = "Europe" if section == "europe" else ("Global" if section == "global" else "Politics")
    return [{"category": cat, "category_en": cat_en, "title": "뉴스를 불러오지 못했습니다", "title_en": "Failed to load news", "body": "잠시 후 다시 시도해주세요.", "body_en": "Please try again later.", "source": "", "url": "", "time": date_iso}]

def card(item):
    cat_kr = item.get("category", "글로벌")
    cat_en = item.get("category_en", "Global")
    bg, fg = STYLES.get(cat_kr, ("#FAECE7", "#712B13"))

    title_kr = str(item.get("title","")).replace("<","&lt;").replace(">","&gt;")
    title_en = str(item.get("title_en","")).replace("<","&lt;").replace(">","&gt;")
    body_kr  = str(item.get("body","")).replace("<","&lt;").replace(">","&gt;")
    body_en  = str(item.get("body_en","")).replace("<","&lt;").replace(">","&gt;")

    angle_kr = f'<div class="ia kr">🇮🇹 이탈리아 시각: {item["italy_angle"]}</div>' if item.get("italy_angle") else ""
    angle_en = f'<div class="ia en" style="display:none">🇮🇹 Italy\'s perspective: {item["italy_angle_en"]}</div>' if item.get("italy_angle_en") else ""

    source = item.get("source","")
    url    = item.get("url","")
    source_html = f'<a class="src" href="{url}" target="_blank">↗ {source}</a>' if url and source else (f'<span class="src">{source}</span>' if source else "")

    return f'''<div class="card">
      <div class="ct">
        <span class="pill kr" style="background:{bg};color:{fg}">{cat_kr}</span>
        <span class="pill en" style="display:none;background:{bg};color:{fg}">{cat_en}</span>
        <span class="tm">{item.get("time","오늘")}</span>
      </div>
      <div class="ttl kr">{title_kr}</div>
      <div class="ttl en" style="display:none">{title_en}</div>
      <div class="bdy kr">{body_kr}</div>
      <div class="bdy en" style="display:none">{body_en}</div>
      {angle_kr}{angle_en}
      {source_html}
    </div>'''

def build_html(italy, europe, glob):
    css = """
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#f5f5f0;color:#1a1a1a}
.wrap{max-width:720px;margin:0 auto;padding:2rem 1.25rem 4rem}
.top{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:0.5rem;flex-wrap:wrap;gap:8px}
.top h1{font-size:20px;font-weight:600}
.top p{font-size:12px;color:#888;margin-top:3px}
.update-info{font-size:12px;color:#888;margin-bottom:1.25rem;padding:8px 12px;background:#fff;border-radius:8px;border:1px solid #e0e0e0;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px}
.db{font-size:12px;padding:5px 12px;border-radius:8px;background:#fff;border:1px solid #e0e0e0;color:#555}
.top-right{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.lang-btn{padding:5px 14px;font-size:12px;font-weight:600;border-radius:8px;border:1px solid #ddd;cursor:pointer;background:#fff;color:#555;transition:all .12s}
.lang-btn.active{background:#1e40af;color:#fff;border-color:#1e40af}
.tabs{display:flex;gap:6px;margin-bottom:1.25rem;flex-wrap:wrap}
.tab{padding:7px 18px;font-size:13px;font-weight:500;border-radius:8px;border:1px solid #ddd;cursor:pointer;color:#555;background:#fff}
.tab.on{background:#dbeafe;color:#1e40af;border-color:transparent}
.pane{display:none}.pane.on{display:block}
.card{background:#fff;border:1px solid #e8e8e8;border-radius:12px;padding:1rem 1.25rem;margin-bottom:10px}
.ct{display:flex;align-items:center;gap:8px;margin-bottom:8px}
.pill{font-size:11px;font-weight:600;padding:3px 10px;border-radius:99px}
.tm{font-size:11px;color:#aaa;margin-left:auto}
.ttl{font-size:14px;font-weight:600;line-height:1.5;margin-bottom:6px}
.bdy{font-size:13px;color:#555;line-height:1.65}
.ia{margin-top:9px;padding:7px 10px;border-left:2px solid #d4537e;background:#fbeaf0;font-size:12px;color:#72243e;line-height:1.55}
.src{display:inline-block;margin-top:8px;font-size:11px;color:#1e40af;text-decoration:none}
.disclaimer{margin-top:10px;padding:8px 12px;background:#f8f8f8;border-radius:8px;font-size:11px;color:#999;line-height:1.5;border:1px solid #eee}
.ft{text-align:center;font-size:11px;color:#bbb;margin-top:2rem}
.arc-link{font-size:12px;color:#1e40af;text-decoration:none;padding:5px 12px;border:1px solid #ddd;border-radius:8px;background:#fff}
"""
    js = """
function sw(id,el){
  document.querySelectorAll('.pane').forEach(p=>p.classList.remove('on'));
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('on'));
  document.getElementById(id).classList.add('on');
  el.classList.add('on');
}
function setLang(lang){
  document.querySelectorAll('.kr').forEach(el=>el.style.display = lang==='kr' ? '' : 'none');
  document.querySelectorAll('.en').forEach(el=>el.style.display = lang==='en' ? '' : 'none');
  document.querySelectorAll('.lang-btn').forEach(btn=>btn.classList.remove('active'));
  document.getElementById('btn-'+lang).classList.add('active');
  localStorage.setItem('briefing-lang', lang);
}
window.onload = function(){
  const saved = localStorage.getItem('briefing-lang') || 'kr';
  setLang(saved);
}
"""
    it = "".join(card(i) for i in italy)
    eu = "".join(card(i) for i in europe)
    gl = "".join(card(i) for i in glob)

    disclaimer_kr = '<div class="disclaimer">⚠️ "이탈리아 시각"은 Claude AI가 이탈리아의 외교·경제적 입장을 바탕으로 추론한 내용으로, 실제 이탈리아 언론 보도와 다를 수 있습니다.</div>'
    disclaimer_en = '<div class="disclaimer" style="display:none">⚠️ "Italy\'s perspective" is generated by Claude AI based on Italy\'s general diplomatic and economic stance, and may differ from actual Italian media coverage.</div>'

    return f"""<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>밀라노 브리핑 {date_str}</title><style>{css}</style></head><body><div class="wrap">
<div class="top">
  <div><h1>밀라노 주재원 데일리 브리핑</h1><p>이탈리아 · 유럽 · 글로벌</p></div>
  <div class="top-right">
    <div class="db">{date_str}</div>
    <button class="lang-btn active" id="btn-kr" onclick="setLang('kr')">KR</button>
    <button class="lang-btn" id="btn-en" onclick="setLang('en')">EN</button>
    <a class="arc-link" href="archive.html">📂 지난 브리핑</a>
  </div>
</div>
<div class="update-info">
  <span>🕕 매일 오전 6시 (밀라노 시간) 자동 업데이트</span>
  <span style="color:#aaa">수동 업데이트: GitHub Actions → Run workflow</span>
</div>
<div class="tabs">
  <div class="tab on" onclick="sw('it',this)"><span class="kr">🇮🇹 이탈리아</span><span class="en" style="display:none">🇮🇹 Italy</span></div>
  <div class="tab" onclick="sw('eu',this)"><span class="kr">🇪🇺 유럽</span><span class="en" style="display:none">🇪🇺 Europe</span></div>
  <div class="tab" onclick="sw('gl',this)"><span class="kr">🌐 글로벌</span><span class="en" style="display:none">🌐 Global</span></div>
</div>
<div id="it" class="pane on">{it}</div>
<div id="eu" class="pane">{eu}</div>
<div id="gl" class="pane">{gl}{disclaimer_kr}{disclaimer_en}</div>
<div class="ft">자동 생성 — {date_str} · Claude API</div>
</div><script>{js}</script></body></html>"""

def build_index(archive_dates):
    items = ""
    for d in sorted(archive_dates, reverse=True):
        items += f'<a class="arc-item" href="{d}.html">📅 {d}</a>\n'
    return f"""<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>밀라노 브리핑 아카이브</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#f5f5f0;color:#1a1a1a}}.wrap{{max-width:720px;margin:0 auto;padding:2rem 1.25rem 4rem}}h1{{font-size:20px;font-weight:600;margin-bottom:6px}}p{{font-size:13px;color:#888;margin-bottom:1.5rem}}.arc-item{{display:block;background:#fff;border:1px solid #e8e8e8;border-radius:12px;padding:14px 18px;margin-bottom:8px;text-decoration:none;color:#1a1a1a;font-size:14px;font-weight:500}}.arc-item:hover{{background:#f0f4ff}}.today-btn{{display:inline-block;background:#1e40af;color:#fff;border-radius:8px;padding:10px 20px;text-decoration:none;font-size:14px;font-weight:600;margin-bottom:1.5rem}}</style>
</head><body><div class="wrap"><h1>밀라노 주재원 브리핑 아카이브</h1><p>날짜를 클릭하면 해당 날의 브리핑을 볼 수 있습니다</p><a class="today-btn" href="index.html">📰 오늘 브리핑 보기</a>{items}</div></body></html>"""

def main():
    global client
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다.")
    client = anthropic.Anthropic(api_key=api_key)

    print("📰 이탈리아 뉴스...")
    italy = fetch_news("italy")
    print("🇪🇺 유럽 뉴스...")
    europe = fetch_news("europe")
    print("🌐 글로벌 뉴스...")
    glob = fetch_news("global")

    os.makedirs("docs", exist_ok=True)
    html_content = build_html(italy, europe, glob)

    with open(f"docs/{date_iso}.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(html_content)

    existing = [
        f.replace(".html", "")
        for f in os.listdir("docs")
        if re.match(r'\d{4}-\d{2}-\d{2}\.html', f)
    ]
    with open("docs/archive.html", "w", encoding="utf-8") as f:
        f.write(build_index(existing))

    print(f"✅ 완료! index.html + {date_iso}.html + archive.html 생성됨")

if __name__ == "__main__":
    main()
