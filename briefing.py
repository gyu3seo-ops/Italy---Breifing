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
    "italy_eco": f'Today is {date_iso}. Search web for Italy ECONOMY news. CRITICAL: Only include articles with publication date {date_iso}. Check each article date. Discard anything not from {date_iso}. EXCLUDE: Do not include any Olympics, Paralympics, Winter Olympics, Milan-Cortina 2026, opening ceremony, or closing ceremony news. These events are already over. Return JSON array only, no other text: [{{"category":"경제","category_en":"Economy","title":"한글제목","title_en":"English title","body":"한글 2문장","body_en":"2 sentences","source":"site name","url":"https://...","time":"{date_iso}"}}]. Get exactly 2 items.',
    "italy_pol": f'Today is {date_iso}. Search web for Italy POLITICS and SOCIETY news. CRITICAL: Only include articles with publication date {date_iso}. Check each article date. Discard anything not from {date_iso}. EXCLUDE: Do not include any Olympics, Paralympics, Winter Olympics, Milan-Cortina 2026, opening ceremony, or closing ceremony news. These events are already over. Return JSON array only, no other text: [{{"category":"정치","category_en":"Politics","title":"한글제목","title_en":"English title","body":"한글 2문장","body_en":"2 sentences","source":"site name","url":"https://...","time":"{date_iso}"}}]. Get 2 politics(정치) and 1 society(사회) items, 3 total.',


    "europe": f'Today is {date_iso}. Search web for Europe/EU news. CRITICAL: Only include articles with publication date {date_iso}. Check each article date. Discard anything not from {date_iso}. EXCLUDE: Do not include any Olympics, Paralympics, Winter Olympics, Milan-Cortina 2026, opening ceremony, or closing ceremony news. These events are already over. Return JSON array only, no other text: [{{"category":"유럽","category_en":"Europe","title":"한글제목","title_en":"English title","body":"한글 2문장","body_en":"2 sentences","source":"site name","url":"https://...","time":"{date_iso}"}}]. Get 4 items.',


    "global": f'Today is {date_iso}. Search web for global news. CRITICAL: Only include articles with publication date {date_iso}. Check each article date. Discard anything not from {date_iso}. EXCLUDE: Do not include any Olympics, Paralympics, Winter Olympics, Milan-Cortina 2026, opening ceremony, or closing ceremony news. These events are already over. Return JSON array only, no other text: [{{"category":"글로벌","category_en":"Global","title":"한글제목","title_en":"English title","body":"한글 2문장","body_en":"2 sentences","italy_angle":"이탈리아 시각 한글","italy_angle_en":"Italy perspective English","source":"site name","url":"https://...","time":"{date_iso}"}}]. Get 4 items.'
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
