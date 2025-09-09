import os, re, sys, json, yaml, datetime
from pathlib import Path
import feedparser
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "output"
FEEDS_FILE = ROOT / "feeds.txt"
KW_FILE = ROOT / "keywords.yml"

KST = datetime.timezone(datetime.timedelta(hours=9))
today = datetime.datetime.now(KST).date()

def load_keywords():
    with open(KW_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def load_feeds():
    with open(FEEDS_FILE, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]

def score(title, summary, kw):
    text = f"{title} {summary or ''}"
    s = 0
    for rule in kw.get("include", []):
        if rule["term"] in text:
            s += rule["weight"]
    for rule in kw.get("exclude", []):
        if rule["term"] in text:
            s += rule["weight"]
    return s

def clean(text, limit=220):
    if not text:
        return ""
    t = re.sub(r"\s+", " ", re.sub(r"<.*?>", " ", text)).strip()
    if len(t) > limit:
        t = t[:limit].rstrip() + "…"
    return t

def summarize(entry):
    # 아주 얕은 규칙 요약(원문 복제 금지, 메타정보 바탕의 한두 문장)
    title = entry.get("title", "").strip()
    summ = clean(entry.get("summary") or entry.get("description") or "")
    # 요약 템플릿(출고정보만으로 재작성)
    if "투자" in f"{title} {summ}":
        tag = "투자"
    elif "공모" in f"{title} {summ}" or "모집" in f"{title} {summ}":
        tag = "모집/공모"
    elif "정책" in f"{title} {summ}" or "지원" in f"{title} {summ}":
        tag = "정책/지원"
    else:
        tag = "일반"
    return tag, summ

def to_md(items):
    header = f"# 창업가 데일리 브리핑 – {today.isoformat()}\n\n" \
             f"> 제공 시각: {datetime.datetime.now(KST).strftime('%Y-%m-%d %H:%M KST')}\n" \
             f"> 기준: 공개 RSS/보도자료 메타데이터 요약, 기사 본문 비수록\n\n" \
             f"**주의**: 각 항목의 저작권은 해당 언론사/기관에 있습니다. 링크 방문 시 원문 저작권 및 이용약관을 준수하세요.\n\n" \
             f"---\n\n"
    body = []
    for it in items:
        line = (
            f"### {it['title']}\n"
            f"- 분류: `{it['tag']}`\n"
            f"- 출처: {it['source']} | 발행: {it['published']}\n"
            f"- 요약: {it['summary']}\n"
            f"- 링크: {it['link']}\n"
            f"- 저작권: © {it['copyright']}\n\n"
        )
        body.append(line)
    if not items:
        body.append("_해당일 선별 결과가 없습니다._\n")
    footer = "---\n\n" \
             "※ 수집 기준: 공개 RSS/보도자료. 본 리포지토리는 기사의 전문을 저장하지 않으며, 메타데이터 기반 자체 요약만 제공합니다.\n"
    return header + "".join(body) + footer

def main():
    kw = load_keywords()
    feeds = load_feeds()
    collected = []
    for url in feeds:
        try:
            d = feedparser.parse(url)
        except Exception as e:
            print(f"[WARN] feed error: {url} {e}", file=sys.stderr)
            continue
        for e in d.entries:
            title = e.get("title", "").strip()
            summary_raw = e.get("summary") or e.get("description") or ""
            s = score(title, summary_raw, kw)
            if s < kw.get("score_threshold", 3):
                continue
            pub = e.get("published") or e.get("updated") or ""
            dom = urlparse(e.get("link", "")).hostname or "unknown"
            tag, summ = summarize(e)
            collected.append({
                "title": title,
                "summary": summ,
                "link": e.get("link", ""),
                "published": pub,
                "source": dom,
                "tag": tag,
                "copyright": dom
            })
    # 최신순 정렬
    collected.sort(key=lambda x: x["published"] or "", reverse=True)
    # 상한
    collected = collected[:kw.get("max_items", 12)]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_file = OUT_DIR / f"{today.isoformat()}.md"
    out_file.write_text(to_md(collected), encoding="utf-8")
    print(f"[INFO] wrote {out_file}")

if __name__ == "__main__":
    main()
