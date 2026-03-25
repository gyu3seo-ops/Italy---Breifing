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
# %-d는 Linux 전용이라 제거, date_iso만 사용
date_label = today.strftime("%Y-%m-%d")

client = None

PROMPTS = {
    "italy_eco": f'Today is {date_iso}. Search web for Italy ECONOMY news from {date_iso} only. Return JSON array only, no other text: [{{"category":"경제","category_en":"Economy","title":"한글제목","title_en":"English title","body":"한글 2문장","body_en":"2 sentences","source":"site name","url":"https://...","time":"{date_iso}"}}]. Get exactly 2 items.',
    "italy_pol": f'Today is {date_iso}. Search web for Italy POLITICS and SOCIETY news from {date_iso} only. Return JSON array only, no other text: [{{"category":"정치","category_en":"Politics","title":"한글제목","title_en":"English title","body":"한글 2문장","body_en":"2 sentences","source":"site name","url":"https://...","time":"{date_iso}"}}]. Get 2 politics(정치) and 1 society(사회) items, 3 total.',

    "europe": f'Today is {date_iso}. Search web for Europe/EU news from {date_iso} only. Return JSON array only, no other text: [{{"category":"유럽","category_en":"Europe","title":"한글제목","title_en":"English title","body":"한글 2문장","body_en":"2 sentences","source":"site name","url":"https://...","time":"{date_iso}"}}]. Get 4 items.',

    "global": f'Today is {date_iso}. Search web for global news from {date_iso} only. Return JSON array only, no other text: [{{"category":"글로벌","category_en":"Global","title":"한글제목","title_en":"English title","body":"한글 2문장","body_en":"2 sentences","italy_angle":"이탈리아 시각 한글","italy_angle_en":"Italy perspective English","source":"site name","url":"https://...","time":"{date_iso}"}}]. Get 4 items.'
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
            time.sleep(20)  # rate limit 방지용 충분한 대기
            resp = client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=2000,
                system=f"You are a news curator. Today is {date_iso}. Return ONLY a raw JSON array. No markdown, no explanation, no cite tags, no code blocks.",
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
                print(f"  ⚠️ {section} JSON 없음 (재시도 {attempt+1}/{retries}): {raw[:100]}")
                continue
            result = json.loads(match.group(0))
            if result:
                print(f"  ✓ {section} {len(result)}개 완료")
                return result
            print(f"  ⚠️ {section} 빈 배열 (재시도 {attempt+1}/{retries})")
        except json.JSONDecodeError as e:
            print(f"  ⚠️ {section} JSON 파싱 오류: {e} (재시도 {attempt+1}/{retries})")
        except Exception as e:
            print(f"  ⚠️ {section} 오류: {e} (재시도 {attempt+1}/{retries})")

    # 모두 실패시 기본값
    cat = "유럽" if section == "europe" else ("글로벌" if section == "global" else ("경제" if section == "italy_eco" else "정치"))
    cat_en = "Europe" if section == "europe" else ("Global" if section == "global" else ("Economy" if section == "italy_eco" else "Politics"))
    return [{"category": cat, "category_en": cat_en,
             "title": "뉴스를 불러오지 못했습니다", "title_en": "Failed to load news",
             "body": "잠시 후 다시 시도해주세요.", "body_en": "Please try again later.",
             "source": "", "url": "", "time": date_iso}]

def card(item):
    cat_kr = item.get("category", "글로벌")
    cat_en = item.get("category_en", "Global")
    bg, fg = STYLES.get(cat_kr, ("#FAECE7", "#712B13"))
    t_kr = str(item.get("title","")).replace("<","&lt;").replace(">","&gt;")
    t_en = str(item.get("title_en","")).replace("<","&lt;").replace(">","&gt;")
    b_kr = str(item.get("body","")).replace("<","&lt;").replace(">","&gt;")
    b_en = str(item.get("body_en","")).replace("<","&lt;").replace(">","&gt;")
    a_kr = f'<div class="ia kr">🇮🇹 이탈리아 시각: {item["italy_angle"]}</div>' if item.get("italy_angle") else ""
    a_en = f'<div class="ia en" style="display:none">🇮🇹 Italy\'s perspective: {item.get("italy_angle_en","")}</div>' if item.get("italy_angle_en") else ""
    src = item.get("source","")
    url = item.get("url","")
    src_html = f'<a class="src" href="{url}" target="_blank">↗ {src}</a>' if url and src else (f'<span class="src">{src}</span>' if src else "")
    return f'''<div class="card">
      <div class="ct">
        <span class="pill kr" style="background:{bg};color:{fg}">{cat_kr}</span>
        <span class="pill en" style="display:none;background:{bg};color:{fg}">{cat_en}</span>
        <span class="tm">{item.get("time","오늘")}</span>
      </div>
      <div class="ttl kr">{t_kr}</div><div class="ttl en" style="display:none">{t_en}</div>
      <div class="bdy kr">{b_kr}</div><div class="bdy en" style="display:none">{b_en}</div>
      {a_kr}{a_en}{src_html}
    </div>'''

def build_html(italy, europe, glob):
    css = """*{box-sizing:border-box;margin:0;padding:0}body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#f5f5f0;color:#1a1a1a}.wrap{max-width:720px;margin:0 auto;padding:2rem 1.25rem 4rem}.top{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:.5rem;flex-wrap:wrap;gap:8px}.top h1{font-size:20px;font-weight:600}.top p{font-size:12px;color:#888;margin-top:3px}.update-info{font-size:12px;color:#888;margin-bottom:1.25rem;padding:8px 12px;background:#fff;border-radius:8px;border:1px solid #e0e0e0;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px}.db{font-size:12px;padding:5px 12px;border-radius:8px;background:#fff;border:1px solid #e0e0e0;color:#555}.top-right{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.lang-btn{padding:5px 14px;font-size:12px;font-weight:600;border-radius:8px;border:1px solid #ddd;cursor:pointer;background:#fff;color:#555}.lang-btn.active{background:#1e40af;color:#fff;border-color:#1e40af}.tabs{display:flex;gap:6px;margin-bottom:1.25rem;flex-wrap:wrap}.tab{padding:7px 18px;font-size:13px;font-weight:500;border-radius:8px;border:1px solid #ddd;cursor:pointer;color:#555;background:#fff}.tab.on{background:#dbeafe;color:#1e40af;border-color:transparent}.pane{display:none}.pane.on{display:block}.card{background:#fff;border:1px solid #e8e8e8;border-radius:12px;padding:1rem 1.25rem;margin-bottom:10px}.ct{display:flex;align-items:center;gap:8px;margin-bottom:8px}.pill{font-size:11px;font-weight:600;padding:3px 10px;border-radius:99px}.tm{font-size:11px;color:#aaa;margin-left:auto}.ttl{font-size:14px;font-weight:600;line-height:1.5;margin-bottom:6px}.bdy{font-size:13px;color:#555;line-height:1.65}.ia{margin-top:9px;padding:7px 10px;border-left:2px solid #d4537e;background:#fbeaf0;font-size:12px;color:#72243e;line-height:1.55}.src{display:inline-block;margin-top:8px;font-size:11px;color:#1e40af;text-decoration:none}.disclaimer{margin-top:10px;padding:8px 12px;background:#f8f8f8;border-radius:8px;font-size:11px;color:#999;line-height:1.5;border:1px solid #eee}.ft{text-align:center;font-size:11px;color:#bbb;margin-top:2rem}.arc-link{font-size:12px;color:#1e40af;text-decoration:none;padding:5px 12px;border:1px solid #ddd;border-radius:8px;background:#fff}"""
    js = """function sw(id,el){document.querySelectorAll('.pane').forEach(p=>p.classList.remove('on'));document.querySelectorAll('.tab').forEach(t=>t.classList.remove('on'));document.getElementById(id).classList.add('on');el.classList.add('on');}
function setLang(lang){document.querySelectorAll('.kr').forEach(el=>el.style.display=lang==='kr'?'':'none');document.querySelectorAll('.en').forEach(el=>el.style.display=lang==='en'?'':'none');document.querySelectorAll('.lang-btn').forEach(btn=>btn.classList.remove('active'));document.getElementById('btn-'+lang).classList.add('active');localStorage.setItem('briefing-lang',lang);}
window.onload=function(){setLang(localStorage.getItem('briefing-lang')||'kr');}"""
    it = "".join(card(i) for i in italy)
    eu = "".join(card(i) for i in europe)
    gl = "".join(card(i) for i in glob)
    dis_kr = '<div class="disclaimer kr">⚠️ "이탈리아 시각"은 Claude AI가 추론한 내용으로, 실제 이탈리아 언론 보도와 다를 수 있습니다.</div>'
    dis_en = '<div class="disclaimer en" style="display:none">⚠️ "Italy\'s perspective" is inferred by Claude AI and may differ from actual Italian media coverage.</div>'
    return f"""<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>밀라노 브리핑 {date_str}</title><style>{css}</style></head><body><div class="wrap">
<div class="top"><div><h1>밀라노 주재원 데일리 브리핑</h1><p>이탈리아 · 유럽 · 글로벌</p></div>
<div class="top-right"><div class="db">{date_str}</div><button class="lang-btn active" id="btn-kr" onclick="setLang('kr')">KR</button><button class="lang-btn" id="btn-en" onclick="setLang('en')">EN</button><a class="arc-link" href="archive.html">📂 지난 브리핑</a></div></div>
<div class="update-info"><span>🕕 매일 오전 6시 (밀라노 시간) 자동 업데이트</span><span style="color:#aaa">Daily auto-update at 6:00 AM Milan time</span></div>
<div class="tabs"><div class="tab on" onclick="sw('it',this)"><span class="kr">🇮🇹 이탈리아</span><span class="en" style="display:none">🇮🇹 Italy</span></div><div class="tab" onclick="sw('eu',this)"><span class="kr">🇪🇺 유럽</span><span class="en" style="display:none">🇪🇺 Europe</span></div><div class="tab" onclick="sw('gl',this)"><span class="kr">🌐 글로벌</span><span class="en" style="display:none">🌐 Global</span></div></div>
<div id="it" class="pane on">{it}</div>
<div id="eu" class="pane">{eu}</div>
<div id="gl" class="pane">{gl}{dis_kr}{dis_en}</div>
<div class="ft">자동 생성 — {date_str} · Claude API</div>
</div><script>{js}</script></body></html>"""

def build_archive(archive_dates):
    items = "".join(f'<a class="arc-item" href="{d}.html">📅 {d}</a>\n' for d in sorted(archive_dates, reverse=True))
    return f"""<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>밀라노 브리핑 아카이브</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#f5f5f0;color:#1a1a1a}}.wrap{{max-width:720px;margin:0 auto;padding:2rem 1.25rem 4rem}}h1{{font-size:20px;font-weight:600;margin-bottom:6px}}p{{font-size:13px;color:#888;margin-bottom:1.5rem}}.arc-item{{display:block;background:#fff;border:1px solid #e8e8e8;border-radius:12px;padding:14px 18px;margin-bottom:8px;text-decoration:none;color:#1a1a1a;font-size:14px;font-weight:500}}.arc-item:hover{{background:#f0f4ff}}.today-btn{{display:inline-block;background:#1e40af;color:#fff;border-radius:8px;padding:10px 20px;text-decoration:none;font-size:14px;font-weight:600;margin-bottom:1.5rem}}</style>
</head><body><div class="wrap"><h1>밀라노 주재원 브리핑 아카이브</h1><p>날짜를 클릭하면 해당 날의 브리핑을 볼 수 있습니다</p><a class="today-btn" href="index.html">📰 오늘 브리핑 보기</a>{items}</div></body></html>"""

def main():
    global client
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY 환경변수가 없습니다.")
    client = anthropic.Anthropic(api_key=api_key)

    print("📰 이탈리아 경제 뉴스...")
    italy_eco = fetch_news("italy_eco")
    print("📰 이탈리아 정치/사회 뉴스...")
    italy_pol = fetch_news("italy_pol")
    italy = italy_eco + italy_pol
    print("🇪🇺 유럽 뉴스...")
    europe = fetch_news("europe")
    print("🌐 글로벌 뉴스...")
    glob = fetch_news("global")

    os.makedirs("docs", exist_ok=True)
    html = build_html(italy, europe, glob)

    # index.html은 항상 최신으로 업데이트
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(html)

    # 날짜 파일은 모든 섹션이 실제 뉴스일 때만 저장 (오류 기본값 제외)
    FAIL_TITLES = {"뉴스를 불러오지 못했습니다", "Failed to load news"}
    all_ok = all(
        item.get("title") not in FAIL_TITLES
        for section in [italy, europe, glob]
        for item in section
    )

    if all_ok:
        with open(f"docs/{date_iso}.html", "w", encoding="utf-8") as f:
            f.write(html)
        print(f"✅ 아카이브 저장: {date_iso}.html")
    else:
        print(f"⚠️ 일부 섹션 실패 — {date_iso}.html 아카이브 저장 건너뜀 (index.html만 업데이트)")

    existing = [f.replace(".html","") for f in os.listdir("docs") if re.match(r'\d{4}-\d{2}-\d{2}\.html', f)]
    with open("docs/archive.html", "w", encoding="utf-8") as f:
        f.write(build_archive(existing))

    print(f"✅ 완료! index.html + archive.html")

if __name__ == "__main__":
    main()
