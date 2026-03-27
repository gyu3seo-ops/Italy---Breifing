import anthropic
import feedparser
import json
import os
import re
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

MILAN_TZ = ZoneInfo("Europe/Rome")
today = datetime.now(MILAN_TZ)
date_str = today.strftime("%Y년 %m월 %d일 (%a)")
date_str_en = today.strftime("%B %d, %Y (%a)")
date_iso = today.strftime("%Y-%m-%d")
date_label = today.strftime("%Y-%m-%d")

client = None

# RSS feeds per section (multiple sources for reliability)
FEEDS = {
    "italy_eco": [
        "https://www.ansa.it/sito/notizie/economia/economia_rss.xml",
        "https://www.ilsole24ore.com/rss/economia--finanza.xml",
        "https://www.corriere.it/rss/economia.xml",
    ],
    "italy_pol": [
        "https://www.ansa.it/sito/notizie/politica/politica_rss.xml",
        "https://www.ansa.it/sito/notizie/cronaca/cronaca_rss.xml",
        "https://www.corriere.it/rss/politica.xml",
    ],
    "europe": [
        "https://www.ansa.it/sito/notizie/mondo/europa/europa_rss.xml",
        "https://euobserver.com/rss.xml",
        "https://www.politico.eu/feed/",
    ],
    "global": [
        "https://feeds.bbci.co.uk/news/world/rss.xml",
        "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
        "https://www.ansa.it/sito/notizie/mondo/mondo_rss.xml",
    ],
}

N_ITEMS = {"italy_eco": 2, "italy_pol": 3, "europe": 4, "global": 4}

CAT_MAP = {
    "italy_eco": ("경제", "Economy"),
    "italy_pol": ("정치", "Politics"),
    "europe": ("유럽", "Europe"),
    "global": ("글로벌", "Global"),
}

STYLES = {
    "경제":   ("#E6F1FB", "#0C447C"),
    "Economy": ("#E6F1FB", "#0C447C"),
    "정치":   ("#EEEDFE", "#3C3489"),
    "Politics": ("#EEEDFE", "#3C3489"),
    "사회":   ("#E1F5EE", "#085041"),
    "Society": ("#E1F5EE", "#085041"),
    "유럽":   ("#FAEEDA", "#633806"),
    "Europe": ("#FAEEDA", "#633806"),
    "글로벌": ("#FAECE7", "#712B13"),
    "Global": ("#FAECE7", "#712B13"),
}


def clean_html(text):
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&quot;", '"', text)
    text = re.sub(r"&#\d+;", "", text)
    return text.strip()


def fetch_rss_articles(section):
    """Fetch today's (or yesterday's) articles from RSS feeds."""
    today_date = datetime.now(MILAN_TZ).date()
    yesterday_date = today_date - timedelta(days=1)

    articles = []
    seen = set()

    for url in FEEDS[section]:
        try:
            feed = feedparser.parse(url, agent="Mozilla/5.0 (compatible; NewsBot/1.0)")
            source_name = feed.feed.get("title", url.split("/")[2])

            for entry in feed.entries[:40]:
                # Parse publication date
                pub_date = None
                for attr in ("published_parsed", "updated_parsed", "created_parsed"):
                    val = getattr(entry, attr, None)
                    if val:
                        try:
                            dt_utc = datetime(*val[:6], tzinfo=ZoneInfo("UTC"))
                            pub_date = dt_utc.astimezone(MILAN_TZ).date()
                        except Exception:
                            pass
                        break

                # Accept today or yesterday (for early morning runs)
                if pub_date not in (today_date, yesterday_date):
                    continue

                title = clean_html(entry.get("title", "")).strip()
                if not title or title in seen:
                    continue
                seen.add(title)

                summary = clean_html(
                    entry.get("summary", entry.get("description", ""))
                ).strip()
                link = entry.get("link", "")

                articles.append({
                    "title": title,
                    "summary": summary[:400],
                    "url": link,
                    "source": source_name,
                    "date": pub_date.isoformat() if pub_date else date_iso,
                })

        except Exception as e:
            print(f"  ⚠️ RSS 오류 ({url}): {e}")

    print(f"  📰 {section}: RSS {len(articles)}개 기사 수집")
    return articles


def summarize_section(section, articles, retries=3):
    """Use Claude to pick and summarize the most important articles."""
    global client
    if client is None:
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    n = N_ITEMS[section]
    cat_kr, cat_en = CAT_MAP[section]

    if not articles:
        print(f"  ⚠️ {section}: 오늘 기사 없음 — 기본값 사용")
        return None

    articles_text = "\n\n".join([
        f"[{i+1}] 제목: {a['title']}\n    내용: {a['summary']}\n    출처: {a['source']}\n    URL: {a['url']}"
        for i, a in enumerate(articles[:12])
    ])

    prompt = (
        f"오늘({date_iso}) 뉴스 기사입니다. 가장 중요한 {n}개를 골라 JSON 배열만 반환하세요.\n\n"
        f"기사 목록:\n{articles_text}\n\n"
        f"반환 형식 (JSON만, 다른 텍스트 없음):\n"
        f'[{{"category":"{cat_kr}","category_en":"{cat_en}",'
        f'"title":"한글 제목","title_en":"English title",'
        f'"body":"한글 2문장 요약","body_en":"2 sentence English summary",'
        f'"source":"출처명","url":"기사URL","time":"{date_iso}"}}]\n\n'
        f"정확히 {n}개만 반환. URL은 위 기사 목록의 실제 URL 사용."
    )

    for attempt in range(retries):
        try:
            resp = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=2000,
                system=(
                    f"You are a bilingual news summarizer. Today is {date_iso}. "
                    "Return ONLY a raw JSON array. No markdown, no explanation, no code blocks."
                ),
                messages=[{"role": "user", "content": prompt}],
            )
            raw = resp.content[0].text if resp.content else ""
            raw = re.sub(r"```[a-z]*\n?", "", raw).strip()
            match = re.search(r"\[.*\]", raw, re.DOTALL)
            if not match:
                print(f"  ⚠️ {section} JSON 없음 (재시도 {attempt+1}/{retries}): {raw[:80]}")
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
        if attempt < retries - 1:
            time.sleep(5)

    cat = cat_kr
    cat_en_val = cat_en
    return [{
        "category": cat, "category_en": cat_en_val,
        "title": "뉴스를 불러오지 못했습니다", "title_en": "Failed to load news",
        "body": "잠시 후 다시 시도해주세요.", "body_en": "Please try again later.",
        "source": "", "url": "", "time": date_iso,
    }]


def card(item):
    cat_kr = item.get("category", "글로벌")
    cat_en = item.get("category_en", "Global")
    bg, fg = STYLES.get(cat_kr, ("#FAECE7", "#712B13"))
    t_kr = str(item.get("title", "")).replace("<", "&lt;").replace(">", "&gt;")
    t_en = str(item.get("title_en", "")).replace("<", "&lt;").replace(">", "&gt;")
    b_kr = str(item.get("body", "")).replace("<", "&lt;").replace(">", "&gt;")
    b_en = str(item.get("body_en", "")).replace("<", "&lt;").replace(">", "&gt;")
    src  = str(item.get("source", "")).replace("<", "&lt;").replace(">", "&gt;")
    url  = str(item.get("url", ""))
    ts   = str(item.get("time", date_iso))

    src_link = f'<a href="{url}" target="_blank" rel="noopener">↗ {src}</a>' if url else src

    return f"""
    <div class="card">
      <div class="card-tag" style="background:{bg};color:{fg};">
        <span class="kr">{cat_kr}</span><span class="en">{cat_en}</span>
      </div>
      <div class="card-date">{ts}</div>
      <div class="card-title kr">{t_kr}</div>
      <div class="card-title en">{t_en}</div>
      <div class="card-body kr">{b_kr}</div>
      <div class="card-body en">{b_en}</div>
      <div class="card-src">{src_link}</div>
    </div>"""


def build_html(italy, europe, glob):
    cards_it = "".join(card(i) for i in italy)
    cards_eu = "".join(card(i) for i in europe)
    cards_gl = "".join(card(i) for i in glob)

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>밀라노 브리핑 {date_str}</title>
<style>
  :root{{--bg:#f5f5f0;--card:#fff;--txt:#1a1a1a;--sub:#666;--border:#e5e5e5;}}
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:'Apple SD Gothic Neo','Malgun Gothic',sans-serif;background:var(--bg);color:var(--txt);padding:24px 16px;}}
  .wrap{{max-width:680px;margin:0 auto}}
  header{{margin-bottom:24px}}
  h1{{font-size:1.5rem;font-weight:700;margin-bottom:4px}}
  .sub{{color:var(--sub);font-size:.85rem;margin-bottom:12px}}
  .meta{{font-size:.8rem;color:var(--sub);background:#fff;border:1px solid var(--border);border-radius:8px;padding:8px 14px;display:flex;justify-content:space-between;flex-wrap:wrap;gap:4px}}
  .lang-btn{{display:flex;gap:6px;margin-bottom:20px}}
  .lang-btn button{{padding:6px 18px;border:none;border-radius:20px;cursor:pointer;font-size:.85rem;font-weight:600;transition:.2s}}
  .lang-btn button.active{{background:#1a1a1a;color:#fff}}
  .lang-btn button:not(.active){{background:#e5e5e5;color:#555}}
  .tabs{{display:flex;gap:8px;margin-bottom:20px;flex-wrap:wrap}}
  .tab{{padding:8px 18px;border-radius:20px;border:1.5px solid #ddd;background:#fff;cursor:pointer;font-size:.85rem;font-weight:600;transition:.2s}}
  .tab.active{{border-color:#1a1a1a;background:#1a1a1a;color:#fff}}
  .section{{display:none}}.section.active{{display:block}}
  .card{{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:18px;margin-bottom:12px}}
  .card-tag{{display:inline-block;border-radius:6px;padding:3px 10px;font-size:.78rem;font-weight:700;margin-bottom:8px}}
  .card-date{{font-size:.75rem;color:var(--sub);margin-bottom:6px}}
  .card-title{{font-size:1.05rem;font-weight:700;line-height:1.4;margin-bottom:8px}}
  .card-body{{font-size:.9rem;line-height:1.6;color:#333;margin-bottom:10px}}
  .card-src{{font-size:.8rem;color:var(--sub)}}.card-src a{{color:#0066cc;text-decoration:none}}
  .en{{display:none}}.en-mode .kr{{display:none}}.en-mode .en{{display:block}}
  .archive-link{{text-align:center;margin-top:24px;font-size:.85rem}}
  .archive-link a{{color:#0066cc;text-decoration:none}}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>밀라노 주재원 데일리 브리핑</h1>
    <div class="sub">이탈리아 · 유럽 · 글로벌</div>
    <div class="meta">
      <span class="kr">📅 매일 오전 6시 (밀라노 시간) 자동 업데이트</span>
      <span class="en">📅 Daily auto-update at 6:00 AM Milan time</span>
      <span>{date_str} &nbsp;|&nbsp; {date_str_en}</span>
    </div>
  </header>

  <div class="lang-btn">
    <button id="btn-kr" class="active" onclick="setLang('kr')">KR</button>
    <button id="btn-en" onclick="setLang('en')">EN</button>
    <a href="archive.html" style="margin-left:auto;padding:6px 14px;border-radius:20px;border:1.5px solid #ddd;background:#fff;font-size:.82rem;font-weight:600;color:#555;text-decoration:none;">🗂 지난 브리핑</a>
  </div>

  <div class="tabs">
    <button class="tab active" onclick="showTab('italy',this)">🇮🇹 이탈리아</button>
    <button class="tab" onclick="showTab('europe',this)">🇪🇺 유럽</button>
    <button class="tab" onclick="showTab('global',this)">🌐 글로벌</button>
  </div>

  <div id="italy" class="section active">{cards_it}</div>
  <div id="europe" class="section">{cards_eu}</div>
  <div id="global" class="section">{cards_gl}</div>
</div>

<script>
function setLang(l){{
  document.body.classList.toggle('en-mode', l==='en');
  document.getElementById('btn-kr').classList.toggle('active', l==='kr');
  document.getElementById('btn-en').classList.toggle('active', l==='en');
}}
function showTab(id, el){{
  document.querySelectorAll('.section').forEach(s=>s.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  el.classList.add('active');
}}
</script>
</body>
</html>"""


def build_archive(dates):
    items = "".join(
        f'<li><a href="{d}.html">📄 {d}</a></li>' for d in sorted(dates, reverse=True)
    )
    return f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="UTF-8">
<title>브리핑 아카이브</title>
<style>body{{font-family:sans-serif;max-width:480px;margin:40px auto;padding:0 16px}}
h1{{margin-bottom:20py}}ul{{list-style:none;padding:0}}
li{{padding:10px 0;border-bottom:1px solid #eee}}
a{{color:#0066cc;text-decoration:none;font-size:1rem}}</style>
</head><body>
<h1>🗂 브리핑 아카이브</h1>
<ul>{items}</ul>
<p style="margin-top:20px"><a href="index.html">← 오늘 브리핑</a></p>
</body></html>"""


def main():
    print(f"🗓 {date_str} ({date_iso}) 브리핑 시작")

    # Step 1: Fetch RSS articles for all sections
    print("\n[1/2] RSS 피드 수집...")
    rss_italy_eco = fetch_rss_articles("italy_eco")
    time.sleep(2)
    rss_italy_pol = fetch_rss_articles("italy_pol")
    time.sleep(2)
    rss_europe = fetch_rss_articles("europe")
    time.sleep(2)
    rss_global = fetch_rss_articles("global")

    # Step 2: Summarize with Claude (no web search tool — just summarization)
    print("\n[2/2] Claude 요약...")
    eco  = summarize_section("italy_eco", rss_italy_eco)
    time.sleep(10)
    pol  = summarize_section("italy_pol", rss_italy_pol)
    time.sleep(10)
    eu   = summarize_section("europe",    rss_europe)
    time.sleep(10)
    glob = summarize_section("global",    rss_global)

    # Fallbacks
    def fallback(cat_kr, cat_en):
        return [{"category": cat_kr, "category_en": cat_en,
                 "title": "뉴스를 불러오지 못했습니다", "title_en": "Failed to load news",
                 "body": "잠시 후 다시 시도해주세요.", "body_en": "Please try again later.",
                 "source": "", "url": "", "time": date_iso}]

    if not eco:  eco  = fallback("경제", "Economy")
    if not pol:  pol  = fallback("정치", "Politics")
    if not eu:   eu   = fallback("유럽", "Europe")
    if not glob: glob = fallback("글로벌", "Global")

    italy = eco + pol
    html = build_html(italy, eu, glob)

    os.makedirs("docs", exist_ok=True)
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(html)

    FAIL_TITLES = {"뉴스를 불러오지 못했습니다", "Failed to load news"}
    all_ok = all(
        item.get("title") not in FAIL_TITLES
        for section in [italy, eu, glob]
        for item in section
    )

    if all_ok:
        with open(f"docs/{date_iso}.html", "w", encoding="utf-8") as f:
            f.write(html)
        print(f"\n✅ 아카이브 저장: {date_iso}.html")
    else:
        print(f"\n⚠️ 일부 섹션 실패 — 아카이브 저장 건너뜀")

    existing = [f.replace(".html", "") for f in os.listdir("docs")
                if re.match(r"\d{4}-\d{2}-\d{2}\.html", f)]
    with open("docs/archive.html", "w", encoding="utf-8") as f:
        f.write(build_archive(existing))

    print(f"✅ 완료! index.html + archive.html")


if __name__ == "__main__":
    main()
