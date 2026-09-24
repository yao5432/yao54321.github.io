#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日自动生成 · iOS 风格资讯网站 (GitHub Pages 适用)
---------------------------------------------------
两大板块：
  1) AI 科技类  —— Hacker News / arXiv / 科技媒体 RSS
  2) 竞技体育类  —— ESPN 新闻 / BBC Sport RSS / Reddit 体育社区
（所有来源均无需 API Key）

运行： python generate.py  ->  生成 index.html
GitHub Actions 每日定时运行本脚本并提交，GitHub Pages 即自动更新。
"""

import os
import sys
import json
import html
import re
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone, timedelta

# ----------------------------- 配置 -----------------------------
HN_KEYWORDS = [
    "AI", "artificial intelligence", "machine learning", "LLM",
    "GPT", "OpenAI", "deep learning", "neural network", "transformer",
    "large language model", "diffusion model", "AI agent", "Claude", "Gemini",
]
HN_PER_KW = 12
HN_TOTAL = 18
PRODUCT_KEYWORDS = [
    "AI tool", "GPT", "LLM", "machine learning", "open source AI",
    "AI agent", "chatbot", "AI app", "diffusion", "vector database",
]
PRODUCT_PER_KW = 10
ARXIV_MAX = 10
RSS_MAX_PER = 8
# 每个板块最终保留的条数上限（目标 20~30 区间）
TARGET_PER_CAT = 28
RSS_FEEDS = [
    ("The Verge AI", "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"),
    ("Ars Technica", "http://feeds.arstechnica.com/arstechnica/index"),
    ("Wired AI", "https://www.wired.com/feed/tag/ai/latest/rss"),
]

# 竞技体育源（RSS，无需 Key；Reddit 作为补充）
SPORTS_RSS_FEEDS = [
    ("ESPN 足球", "https://www.espn.com/espn/rss/soccer/news", "soccer"),
    ("ESPN NBA", "https://www.espn.com/espn/rss/nba/news", "basketball"),
    ("ESPN NFL", "https://www.espn.com/espn/rss/nfl/news", "general"),
    ("ESPN MLB", "https://www.espn.com/espn/rss/mlb/news", "general"),
    ("ESPN 网球", "https://www.espn.com/espn/rss/tennis/news", "general"),
    ("BBC Sport", "http://feeds.bbci.co.uk/sport/rss.xml", "general"),
]
REDDIT_SPORTS = [("soccer", "soccer"), ("nba", "basketball"), ("sports", "general")]

# 军事政治源（RSS，无需 Key）
MIL_RSS_FEEDS = [
    ("BBC 国际", "http://feeds.bbci.co.uk/news/world/rss.xml", "world"),
    ("BBC 政治", "http://feeds.bbci.co.uk/news/politics/rss.xml", "politics"),
    ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml", "world"),
    ("Google 军事", "https://news.google.com/rss/search?q=military+OR+defense+OR+geopolitics+OR+election&hl=en-US&gl=US&ceid=US:en", "military"),
]
REDDIT_MIL = [("worldnews", "world"), ("geopolitics", "politics"), ("military", "military")]

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}

# 每日一句优美英文短句（按生成日期轮换，实现“每日更新一句”）
DAILY_QUOTES = [
    ("The best way to predict the future is to invent it.", "Alan Kay"),
    ("Stay hungry, stay foolish.", "Steve Jobs"),
    ("Simplicity is the ultimate sophistication.", "Leonardo da Vinci"),
    ("What we think, we become.", "Buddha"),
    ("Well done is better than well said.", "Benjamin Franklin"),
    ("The only way to do great work is to love what you do.", "Steve Jobs"),
    ("In the middle of difficulty lies opportunity.", "Albert Einstein"),
    ("Do not go where the path may lead; go instead where there is no path.", "Ralph W. Emerson"),
    ("Wisdom begins in wonder.", "Socrates"),
    ("The future belongs to those who believe in the beauty of their dreams.", "Eleanor Roosevelt"),
    ("Quality is not an act, it is a habit.", "Aristotle"),
    ("Light tomorrow with today.", "Elizabeth Barrett Browning"),
    ("We are what we repeatedly do.", "Aristotle"),
    ("Nothing in life is to be feared, it is only to be understood.", "Marie Curie"),
    ("A journey of a thousand miles begins with a single step.", "Lao Tzu"),
    ("Dream big and dare to fail.", "Norman Vaughan"),
    ("Creativity is intelligence having fun.", "Albert Einstein"),
    ("The quieter you become, the more you are able to hear.", "Rumi"),
    ("Make each day your masterpiece.", "John Wooden"),
    ("Kindness is a language the deaf can hear and the blind can see.", "Mark Twain"),
    ("Whatever you can do, begin it. Boldness has genius in it.", "Goethe"),
    ("The secret of getting ahead is getting started.", "Mark Twain"),
    ("Happiness is not something ready-made. It comes from your own actions.", "Dalai Lama"),
    ("To love what you do and feel that it matters — how could anything be more fun?", "Katharine Graham"),
    ("Overflowing with quiet joy, the mind becomes luminous.", "Buddhist Saying"),
    ("Peace comes from within. Do not seek it without.", "Buddha"),
    ("The beautiful thing about learning is that no one can take it away.", "B.B. King"),
    ("Turn your face to the sun and the shadows fall behind you.", "Maori Proverb"),
    ("Small steps every day lead to big changes over time.", "Anonymous"),
    ("A calm mind is the ultimate weapon against life's storms.", "Naval Ravikant"),
]

def pick_daily_quote():
    """按当前日期（一年中的第几天）稳定选取当日短句，实现每日更新一句。"""
    doy = (datetime.now(timezone.utc)).timetuple().tm_yday
    q, a = DAILY_QUOTES[doy % len(DAILY_QUOTES)]
    return q, a


# ----------------------------- 抓取工具 -----------------------------
def fetch_json(url, timeout=15):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_text(url, timeout=15):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="ignore")


def clean(text):
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)          # 去 HTML 标签
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_time(s):
    if not s:
        return None
    s = s.strip()
    fmts = (
        "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%S.%f%z",
        "%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%d %H:%M:%S", "%Y-%m-%d",
    )
    for fmt in fmts:
        try:
            dt = datetime.strptime(s, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


# ----------------------------- AI 科技类数据源 -----------------------------
def fetch_hn():
    items = {}
    for kw in HN_KEYWORDS:
        try:
            q = urllib.parse.quote(kw)
            url = (f"https://hn.algolia.com/api/v1/search_by_date?query={q}"
                   f"&tags=story&hitsPerPage={HN_PER_KW}")
            data = fetch_json(url)
            for h in data.get("hits", []):
                oid = h.get("objectID")
                if not oid or oid in items:
                    continue
                title = h.get("title") or h.get("story_title")
                if not title:
                    continue
                link = h.get("url") or f"https://news.ycombinator.com/item?id={oid}"
                pts = h.get("points") or 0
                cms = h.get("num_comments") or 0
                items[oid] = {
                    "title": clean(title),
                    "summary": f"Hacker News 社区热议话题，当前热度 ▲{pts} · 💬{cms}。",
                    "full": (f"社区热门讨论：在 Hacker News 上获得 {pts} 赞、{cms} 条评论，"
                             f"属于近期 AI 领域关注度较高的话题之一。\n\n"
                             f"原标题：{clean(title)}"),
                    "url": link,
                    "source": "Hacker News", "sub": "news", "category": "ai",
                    "points": pts, "comments": cms,
                    "author": h.get("author") or "",
                    "published": h.get("created_at"),
                }
        except Exception as e:
            print(f"  [HN] 关键词 '{kw}' 抓取失败: {e}", file=sys.stderr)
    lst = list(items.values())
    lst.sort(key=lambda x: (x["points"] or 0), reverse=True)
    return lst[:HN_TOTAL]


def fetch_hn_products():
    """抓取 Hacker News 的 show_hn（AI 产品 / 工具发布），作为 AI 科技下的「产品」栏目。"""
    items = {}
    for kw in PRODUCT_KEYWORDS:
        try:
            q = urllib.parse.quote(kw)
            url = (f"https://hn.algolia.com/api/v1/search?query={q}"
                   f"&tags=story,show_hn&hitsPerPage={HN_PER_KW}")
            data = fetch_json(url)
            for h in data.get("hits", []):
                oid = h.get("objectID")
                if not oid or oid in items:
                    continue
                title = h.get("title") or h.get("story_title")
                if not title:
                    continue
                link = h.get("url") or f"https://news.ycombinator.com/item?id={oid}"
                pts = h.get("points") or 0
                cms = h.get("num_comments") or 0
                items[oid] = {
                    "title": clean(title),
                    "summary": f"AI 产品 / 工具新发布，HN 社区热度 ▲{pts} · 💬{cms}。",
                    "full": (f"这是 Hacker News Show HN 上分享的 AI 产品 / 工具，"
                             f"获得 {pts} 赞、{cms} 条评论。\n\n原标题：{clean(title)}"),
                    "url": link,
                    "source": "Hacker News · Show HN", "sub": "product", "category": "ai",
                    "points": pts, "comments": cms,
                    "author": h.get("author") or "",
                    "published": h.get("created_at"),
                }
        except Exception as e:
            print(f"  [HN 产品] 关键词 '{kw}' 抓取失败: {e}", file=sys.stderr)
    lst = list(items.values())
    lst.sort(key=lambda x: (x["points"] or 0), reverse=True)
    return lst[:HN_TOTAL]


def fetch_rss():
    try:
        import feedparser
    except ImportError:
        print("  [RSS] 未安装 feedparser，已跳过媒体源", file=sys.stderr)
        return []
    out = []
    for name, url in RSS_FEEDS:
        try:
            d = feedparser.parse(url)
            for e in d.entries[:RSS_MAX_PER]:
                out.append({
                    "title": clean(e.get("title", "")),
                    "summary": clean(e.get("summary") or e.get("description") or ""),
                    "full": clean(e.get("summary") or e.get("description") or ""),
                    "url": e.get("link", ""),
                    "source": name, "sub": "media", "category": "ai",
                    "points": 0, "comments": 0, "author": "",
                    "published": e.get("published") or e.get("updated") or "",
                })
        except Exception as ex:
            print(f"  [RSS] {name} 抓取失败: {ex}", file=sys.stderr)
    return out


# ----------------------------- 竞技体育类数据源 -----------------------------
def fetch_sports_rss():
    try:
        import feedparser
    except ImportError:
        print("  [RSS] 未安装 feedparser，已跳过体育媒体源", file=sys.stderr)
        return []
    out = []
    for name, url, stype in SPORTS_RSS_FEEDS:
        try:
            d = feedparser.parse(url)
            for e in d.entries[:5]:
                title = clean(e.get("title", ""))
                if not title:
                    continue
                desc = clean(e.get("summary") or e.get("description") or "")
                out.append({
                    "title": title,
                    "summary": desc,
                    "full": desc or "（体育资讯，暂无详细正文。）",
                    "url": e.get("link", ""),
                    "source": name, "sub": stype, "category": "sports",
                    "points": 0, "comments": 0, "author": "",
                    "published": e.get("published") or e.get("updated") or "",
                })
        except Exception as ex:
            print(f"  [RSS {name}] 抓取失败: {ex}", file=sys.stderr)
    return out


def fetch_reddit_sports():
    out = []
    for sub_name, stype in REDDIT_SPORTS:
        try:
            url = f"https://www.reddit.com/r/{sub_name}/.json?limit=6"
            data = fetch_json(url)
            for c in (data.get("data", {}) or {}).get("children", []):
                d = c.get("data", {})
                title = clean(d.get("title"))
                if not title:
                    continue
                selftext = clean(d.get("selftext"))[:600]
                cu = d.get("created_utc") or 0
                pub = (datetime.utcfromtimestamp(cu).isoformat() + "Z") if cu else ""
                out.append({
                    "title": title,
                    "summary": selftext,
                    "full": selftext or "（社区讨论帖，暂无正文摘要。）",
                    "url": "https://www.reddit.com" + (d.get("permalink") or ""),
                    "source": "Reddit r/" + sub_name, "sub": stype, "category": "sports",
                    "points": d.get("score") or 0, "comments": d.get("num_comments") or 0,
                    "author": d.get("author") or "", "published": pub,
                })
        except Exception as e:
            print(f"  [Reddit r/{sub_name}] 抓取失败: {e}", file=sys.stderr)
    return out


# ----------------------------- 军事政治类数据源 -----------------------------
def fetch_military():
    try:
        import feedparser
    except ImportError:
        print("  [RSS] 未安装 feedparser，已跳过军事政治媒体源", file=sys.stderr)
        return []
    out = []
    for name, url, stype in MIL_RSS_FEEDS:
        try:
            d = feedparser.parse(url)
            for e in d.entries[:6]:
                title = clean(e.get("title", ""))
                if not title:
                    continue
                desc = clean(e.get("summary") or e.get("description") or "")
                out.append({
                    "title": title,
                    "summary": desc,
                    "full": desc or "（时事资讯，暂无详细正文。）",
                    "url": e.get("link", ""),
                    "source": name, "sub": stype, "category": "mil",
                    "points": 0, "comments": 0, "author": "",
                    "published": e.get("published") or e.get("updated") or "",
                })
        except Exception as ex:
            print(f"  [RSS {name}] 抓取失败: {ex}", file=sys.stderr)
    return out


def fetch_reddit_mil():
    out = []
    for sub_name, stype in REDDIT_MIL:
        try:
            url = f"https://www.reddit.com/r/{sub_name}/.json?limit=6"
            data = fetch_json(url)
            for c in (data.get("data", {}) or {}).get("children", []):
                d = c.get("data", {})
                title = clean(d.get("title"))
                if not title:
                    continue
                selftext = clean(d.get("selftext"))[:600]
                cu = d.get("created_utc") or 0
                pub = (datetime.utcfromtimestamp(cu).isoformat() + "Z") if cu else ""
                out.append({
                    "title": title,
                    "summary": selftext,
                    "full": selftext or "（社区讨论帖，暂无正文摘要。）",
                    "url": "https://www.reddit.com" + (d.get("permalink") or ""),
                    "source": "Reddit r/" + sub_name, "sub": stype, "category": "mil",
                    "points": d.get("score") or 0, "comments": d.get("num_comments") or 0,
                    "author": d.get("author") or "", "published": pub,
                })
        except Exception as e:
            print(f"  [Reddit r/{sub_name}] 抓取失败: {e}", file=sys.stderr)
    return out


# ----------------------------- 翻译 & 摘要生成 -----------------------------
import time
import re

def clean_url(s):
    s = (s or "").strip()
    if not s:
        return ""
    if not s.lower().startswith(("http://", "https://")):
        s = "https://" + s
    # 只保留主站：去掉 query string / fragment / anchor
    for sep in ("#", "/?", "?"):
        s = s.split(sep)[0]
    return s


def translate_en_zh(text, retries=2):
    """调用 Google 免费翻译接口（sl=auto 自动识别，中文原文不会被破坏）。"""
    if not text or not text.strip():
        return ""
    try:
        q = urllib.parse.quote(text.strip())
        url = ("https://translate.googleapis.com/translate_a/single?client=gtx"
               f"&sl=auto&tl=zh-CN&dt=t&q={q}")
        data = fetch_json(url)
        return "".join(seg[0] for seg in data[0] if seg[0]).strip()
    except Exception as e:
        if retries > 0:
            time.sleep(0.6)
            return translate_en_zh(text, retries - 1)
        return ""


SEP = "[[S]]"
def is_cjk(s):
    return bool(re.search(r'[\u4e00-\u9fff]', s or ''))


def summarize(raw_text, max_chars=600):
    """简单结构化摘要：去 HTML、砍掉链接、合并换行、截断到 max_chars。"""
    if not raw_text:
        return ""
    s = raw_text.strip()
    # 剥离 HTML 标签（标题/正文可能夹带）
    s = re.sub(r'<[^>]+>', '', s)
    # 去除 URL 行（如 https://... 单独成行的）
    s = re.sub(r'(?:^|\n)\s*https?://\S+\s*(?:\n|$)', '\n', s)
    # 把多个空白（空格/Tab/换行）折叠为一个换行
    s = re.sub(r'[\t ]+', ' ', s)
    s = re.sub(r'\n{3,}', '\n\n', s)
    s = s.strip()
    # 限制长度，断点尽量在换行或标点处
    if len(s) > max_chars:
        s = s[:max_chars]
        for p in ('。', '.', '!', '?', '\n'):
            i = s.rfind(p, max(0, max_chars - 20))
            if i >= 0:
                s = s[:i + 1]
                break
        s = s.rstrip()
    return s


def summarize_ai(raw_title, raw_url, raw_summary):
    """专为 HN / AI 媒体构建的摘要：含标题 + 来源要点 + 短摘要。"""
    url_root = clean_url(raw_url) or ""
    src = url_root.split("//")[-1].split("/")[0] if url_root else ""
    parts = []
    if raw_title:
        parts.append(raw_title.strip())
    if src and "news.ycombinator.com" not in src:
        parts.append(f"[{src}]")
    if raw_summary:
        parts.append(summarize(raw_summary, max_chars=400))
    return "\n\n".join(parts) if parts else ""


def summarize_sports(raw_summary, raw_title):
    """体育：从 RSS 描述里抽取一两句话，避免直接贴冗长新闻稿。"""
    if raw_summary:
        t = summarize(raw_summary, max_chars=320)
        if t:
            return t
    if raw_title:
        return raw_title.strip()
    return "（体育快讯，暂无详细描述。）"


def summarize_mil(raw_summary, raw_title):
    """军事政治：同上，更克制。"""
    if raw_summary:
        t = summarize(raw_summary, max_chars=320)
        if t:
            return t
    if raw_title:
        return raw_title.strip()
    return "（时事资讯，暂无详细描述。）"


def summarize_hn(raw_title, raw_url, pts, cms):
    """HN 热帖：一句话概括 + 热度 + 原文链接。"""
    url_root = clean_url(raw_url) or ""
    src = url_root.split("//")[-1].split("/")[0] if url_root else "news.ycombinator.com"
    parts = [f"HN 热帖，{pts or 0} 赞 · {cms or 0} 条评论。"]
    if raw_title:
        parts.append(raw_title.strip())
    if url_root:
        parts.append(f"原文链接：{url_root}")
    return "\n".join(parts)


def summary_and_translate_it(it):
    """生成规范化的 summary / full，并翻译；已译字段保留。
    关键修复：HN 热帖不再把原始 URL/domain 拼进 full 字段（避免 [www.reddit.com] 这种低质量输出），
    只把 HN 热度写在 summary 里，正文用 clean 后的 RSS 描述或默认中文话术。"""
    sub = it.get("sub", "")
    cat = it.get("category", "")
    raw_title = it.get("title", "")
    raw_url = it.get("url", "") or ""
    raw_full = it.get("full", "") or ""
    pts = it.get("points", 0) or 0
    cms = it.get("comments", 0) or 0
    is_hn = (it.get("source") or "").lower().startswith("hacker news")

    # 如果 full 里被旧逻辑塞过 "[domain]" 形式（如 [www.reddit.com]），先清洗掉
    if is_hn and re.search(r"\[(?:www\.)?(?:reddit|news\.ycombinator)\.com\]", raw_full):
        raw_full = re.sub(r"\[(?:www\.)?[a-z0-9.]+\.[a-z]{2,}\]", "", raw_full)
        raw_full = re.sub(r"\s+", " ", raw_full).strip()

    # 生成 summary：
    # - HN 热帖：「HN 热帖，{pts} 赞 · {cms} 条评论。」（不再拼 URL）
    # - 其他：从 full/summary 中提取前 320 字符的人话摘要
    if is_hn:
        summary = f"HN 热帖，{pts} 赞 · {cms} 条评论。"
    else:
        summary = summarize(raw_full or it.get("summary", ""), max_chars=320)
        if not summary and raw_title:
            summary = raw_title.strip()

    # 生成 full：
    # - 非 HN：clean 后的 full 正文（已截断 600 字）
    # - HN：中文话术（"在 Hacker News 上获得 X 赞、Y 条评论，属于近期 AI 领域关注度较高的话题之一"）+ 标题
    if is_hn:
        full = (f"在 Hacker News 上获得 {pts} 赞、{cms} 条评论，"
                f"属于近期{'AI' if cat=='ai' else '该'}领域关注度较高的话题之一。\n\n"
                f"原标题：{raw_title.strip()}")
        if raw_full and not re.search(r"^(?:Hacker News 社区热议|社区热门讨论)", raw_full.strip()):
            # 若有真实的第三方描述（非模板中文），优先保留
            full = raw_full
    else:
        full = summarize(raw_full, max_chars=600) or it.get("summary", "")

    it["summary"] = summary.strip()
    it["full"] = full.strip() or it["summary"]
    it["title_zh"] = translate_en_zh(it.get("title", ""))
    it["summary_zh"] = (translate_en_zh(summary) if not is_cjk(summary) else summary)
    it["full_zh"] = it["summary_zh"]
    return it


# ----------------------------- 离线兜底数据 -----------------------------
SAMPLE_AI = [
    {
        "title": "示例：OpenAI 发布新一代多模态推理模型",
        "summary": "社区热议话题，当前热度 ▲1280 · 💬342。",
        "full": "社区热门讨论：在 Hacker News 上获得 1280 赞、342 条评论，属于近期 AI 领域关注度较高的话题之一。\n\n原标题：OpenAI 发布新一代多模态推理模型",
        "url": "https://github.com", "source": "Hacker News", "sub": "news", "category": "ai",
        "points": 1280, "comments": 342, "author": "demo",
        "published": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
    },
    {
        "title": "示例：Show HN — 一款本地运行的轻量级 AI 写作助手",
        "summary": "AI 产品 / 工具新发布，HN 社区热度 ▲642 · 💬88。",
        "full": "这是 Hacker News Show HN 上分享的 AI 产品 / 工具，获得 642 赞、88 条评论。\n\n原标题：Show HN: A lightweight locally-running AI writing assistant",
        "url": "https://github.com", "source": "Hacker News · Show HN", "sub": "product", "category": "ai",
        "points": 642, "comments": 88, "author": "demo",
        "published": (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat(),
    },
    {
        "title": "示例：科技媒体报道 AI 芯片竞争格局变化",
        "summary": "行业观察：新入局者正在重塑 AI 加速器的供应格局。",
        "full": "行业观察：新入局者正在重塑 AI 加速器的供应格局。多家初创公司宣布自研推理芯片，试图在能效比上挑战传统 GPU 方案，预计将影响未来数据中心的成本结构。",
        "url": "https://example.com", "source": "The Verge AI", "sub": "media", "category": "ai",
        "points": 0, "comments": 0, "author": "",
        "published": (datetime.now(timezone.utc) - timedelta(hours=9)).isoformat(),
    },
]

SAMPLE_SPORTS = [
    {
        "title": "示例：英超焦点战 — 争冠关键轮次悬念升级",
        "summary": "联赛进入尾声，多支球队积分胶着，本轮结果或将直接决定冠军归属与欧战席位。",
        "full": "联赛进入尾声，多支球队积分胶着，本轮结果或将直接决定冠军归属与欧战席位。主队近期状态回暖，客队则依赖核心前锋的终结效率。赛前数据显示双方控球率接近，比赛很可能被拖入高强度对抗的拉锯战。",
        "url": "https://www.espn.com", "source": "ESPN · 英超", "sub": "soccer", "category": "sports",
        "points": 0, "comments": 0, "author": "",
        "published": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
    },
    {
        "title": "示例：NBA 季后赛 — 巨星对决引爆社交媒体",
        "summary": "一场高强度对攻让系列赛大比分被扳平，球迷讨论度创下赛季新高。",
        "full": "一场高强度对攻让系列赛大比分被扳平，球迷讨论度创下赛季新高。双方在末节多次交替领先，关键回合的防守选择成为赛后分析的重点。伤病情况与轮换深度，将成为接下来客场之旅的最大变数。",
        "url": "https://www.espn.com", "source": "ESPN · NBA", "sub": "basketball", "category": "sports",
        "points": 0, "comments": 0, "author": "",
        "published": (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat(),
    },
    {
        "title": "示例：F1 新规则季前测试引爆话题",
        "summary": "各车队在季前测试中展现全新空气动力学方案，围场内外猜测不断。",
        "full": "各车队在季前测试中展现全新空气动力学方案，围场内外猜测不断。动力单元可靠性和轮胎管理成为媒体聚焦的两条主线，而中游集团的竞争被认为将是本赛季最激烈的看点。",
        "url": "https://www.espn.com", "source": "ESPN · F1", "sub": "general", "category": "sports",
        "points": 0, "comments": 0, "author": "",
        "published": (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat(),
    },
]

SAMPLE_MIL = [
    {
        "title": "示例：主要国家就地区安全局势举行多边磋商",
        "summary": "多国代表围绕地区稳定与防务合作展开闭门会谈，外界关注后续联合声明。",
        "full": "多国代表围绕地区稳定与防务合作展开闭门会谈，外界关注后续联合声明。分析认为，此次磋商将影响未来数月的外交走向与军事部署节奏。",
        "url": "https://example.com", "source": "BBC 国际", "sub": "world", "category": "mil",
        "points": 0, "comments": 0, "author": "",
        "published": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
    },
    {
        "title": "示例：国会就新财年国防预算案进入辩论阶段",
        "summary": "预算分配成为两党焦点，争议集中在装备采购与海外驻军规模。",
        "full": "预算分配成为两党焦点，争议集中在装备采购与海外驻军规模。支持方强调战略竞争需要持续投入，反对方则呼吁将资金更多转向民生领域。",
        "url": "https://example.com", "source": "BBC 政治", "sub": "politics", "category": "mil",
        "points": 0, "comments": 0, "author": "",
        "published": (datetime.now(timezone.utc) - timedelta(hours=4)).isoformat(),
    },
    {
        "title": "示例：海军舰艇编队完成远洋联合训练",
        "summary": "多型主力舰参与演训，重点检验远海补给与协同指挥能力。",
        "full": "多型主力舰参与演训，重点检验远海补给与协同指挥能力。官方通报称，训练达到预期目标，提升了复杂电磁环境下的体系作战水平。",
        "url": "https://example.com", "source": "Google 军事", "sub": "military", "category": "mil",
        "points": 0, "comments": 0, "author": "",
        "published": (datetime.now(timezone.utc) - timedelta(hours=7)).isoformat(),
    },
]


# ----------------------------- 处理 & 主流程 -----------------------------
def process(items):
    for it in items:
        it["_dt"] = parse_time(it["published"])
    items.sort(key=lambda x: x["_dt"] or datetime.min.replace(tzinfo=timezone.utc),
               reverse=True)
    MAX_SUM = 120
    for it in items:
        raw = (it.get("summary") or "").strip()
        it["full"] = it.get("full") or raw
        s = raw
        if len(s) > MAX_SUM:
            s = s[:MAX_SUM].rstrip() + "…"
        if not s:
            s = "热门话题精选，点击查看完整内容。"
        it["summary"] = s
    return [{k: v for k, v in it.items() if k != "_dt"} for it in items]


def balance(items, caps, total):
    """按 sub 配额取数，保证每个子栏目都有内容；不足配额的部分再用最新条目补齐。
    items 需已按时间倒序排列。"""
    counts = {}
    out = []
    for it in items:
        s = it["sub"]
        cap = caps.get(s, 10**9)
        if counts.get(s, 0) < cap:
            out.append(it); counts[s] = counts.get(s, 0) + 1
        if len(out) >= total:
            break
    if len(out) < total:
        seen = {id(x) for x in out}
        for it in items:
            if id(it) not in seen:
                out.append(it)
            if len(out) >= total:
                break
    return out


RAW_FILE = "items_raw.json"

def fetch_all():
    """抓取三类资讯（真实源）；任一为空时回退到示例数据。"""
    print("→ 正在抓取 AI 科技资讯 ...")
    ai = fetch_hn() + fetch_hn_products() + fetch_rss()
    if not ai:
        print("! AI 在线源不可用，使用离线兜底数据。", file=sys.stderr); ai = SAMPLE_AI
    print("→ 正在抓取竞技体育资讯 ...")
    sports = fetch_sports_rss() + fetch_reddit_sports()
    if not sports:
        print("! 体育在线源不可用，使用离线兜底数据。", file=sys.stderr); sports = SAMPLE_SPORTS
    print("→ 正在抓取军事政治资讯 ...")
    mil = fetch_military() + fetch_reddit_mil()
    if not mil:
        print("! 军事政治在线源不可用，使用离线兜底数据。", file=sys.stderr); mil = SAMPLE_MIL
    ai = balance(process(ai), {"news": 12, "product": 10, "media": 6}, TARGET_PER_CAT)
    sports = balance(process(sports), {"soccer": 12, "basketball": 8, "general": 8}, TARGET_PER_CAT)
    mil = balance(process(mil), {"world": 12, "politics": 8, "military": 8}, TARGET_PER_CAT)
    return ai, sports, mil

def save_raw(ai, sports, mil):
    with open(RAW_FILE, "w", encoding="utf-8") as f:
        json.dump({"ai": ai, "sports": sports, "mil": mil}, f, ensure_ascii=False)

def load_raw():
    with open(RAW_FILE, encoding="utf-8") as f:
        d = json.load(f)
    return d["ai"], d["sports"], d["mil"]

def translate_items(ai, sports, mil, checkpoint=True):
    """逐条翻译；已译（含 title_zh）跳过。checkpoint=True 时每完成一条即落盘，可断点续译。"""
    groups = [("AI", ai), ("体育", sports), ("军事", mil)]
    total = sum(len(g[1]) for g in groups)
    done0 = sum(1 for g in groups for it in g[1] if it.get("title_zh"))
    print(f"→ 翻译进度 {done0}/{total}，开始续译 ...")
    for _label, items in groups:
        for it in items:
            if it.get("title_zh"):
                continue
            try:
                summary_and_translate_it(it)
            except Exception as e:
                print(f"  [翻译跳过] {it.get('title','')[:30]}: {e}", file=sys.stderr)
            time.sleep(0.12)
            if checkpoint:
                save_raw(ai, sports, mil)
    return ai, sports, mil

def build_html(ai, sports, mil):
    data = {
        "generated_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
        "ai": {"count": len(ai), "items": ai},
        "sports": {"count": len(sports), "items": sports},
        "mil": {"count": len(mil), "items": mil},
    }
    safe = (json.dumps(data, ensure_ascii=False)
            .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"))
    q, qa = pick_daily_quote()
    out_html = (HTML_TEMPLATE
                .replace("__DATA_JSON__", safe)
                .replace("__DAILY_QUOTE__", q)
                .replace("__DAILY_AUTHOR__", qa))
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(out_html)
    print(f"✓ 已生成 index.html（AI 科技 {len(ai)} 条 · 竞技体育 {len(sports)} 条 · 军事政治 {len(mil)} 条）")

def main():
    MODE = os.environ.get("MODE", "").lower()
    OFFLINE = os.environ.get("OFFLINE")
    if OFFLINE:
        print("→ 离线模式：使用内置示例数据。")
        ai, sports, mil = SAMPLE_AI, SAMPLE_SPORTS, SAMPLE_MIL
        ai = process(ai)[:TARGET_PER_CAT]; sports = process(sports)[:TARGET_PER_CAT]; mil = process(mil)[:TARGET_PER_CAT]
        translate_items(ai, sports, mil, checkpoint=False)
        build_html(ai, sports, mil)
        return
    if MODE == "fetch":
        ai, sports, mil = fetch_all()
        save_raw(ai, sports, mil)
        print(f"✓ 已抓取并保存原始数据（AI {len(ai)} · 体育 {len(sports)} · 军事 {len(mil)}）")
        return
    if MODE == "translate":
        ai, sports, mil = load_raw()
        translate_items(ai, sports, mil, checkpoint=True)
        return
    if MODE == "build":
        ai, sports, mil = load_raw()
        build_html(ai, sports, mil)
        return
    # 默认（GitHub Actions）：一次跑完
    ai, sports, mil = fetch_all()
    translate_items(ai, sports, mil, checkpoint=False)
    build_html(ai, sports, mil)


# ----------------------------- 页面模板 (iOS 风格) -----------------------------
HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
<meta name="theme-color" content="#f2f2f7" media="(prefers-color-scheme: light)" />
<meta name="theme-color" content="#000000" media="(prefers-color-scheme: dark)" />
<title>丫丫资讯</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Crect width='100' height='100' rx='22' fill='%23ff6a00'/%3E%3Ctext x='50' y='72' font-size='60' font-family='PingFang SC,Arial' font-weight='700' fill='white' text-anchor='middle'%3E丫%3C/text%3E%3C/svg%3E" />
<style>
  :root{
    --bg:#f2f2f7; --card:#ffffff; --text:#1c1c1e; --sub:#8e8e93;
    --line:rgba(60,60,67,.12); --accent:#ff6a00; --accent-soft:rgba(255,106,0,.12);
    --news:#ff9500; --paper:#5e5ce6; --media:#34c759; --sport:#ff3b30; --mil:#30b0c7;
    --shadow:0 1px 2px rgba(0,0,0,.06),0 10px 30px rgba(0,0,0,.07);
    --radius:20px;
  }
  @media (prefers-color-scheme: dark){
    :root{
      --bg:#000; --card:#1c1c1e; --text:#f2f2f7; --sub:#98989f;
      --line:rgba(255,255,255,.12); --accent-soft:rgba(255,138,30,.18);
      --shadow:0 1px 2px rgba(0,0,0,.5),0 12px 32px rgba(0,0,0,.45);
    }
  }
  *{box-sizing:border-box;-webkit-tap-highlight-color:transparent;}
  html,body{margin:0;padding:0;}
  body{
    background:var(--bg); color:var(--text);
    font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text","SF Pro Display",
      "Helvetica Neue","PingFang SC","Microsoft YaHei",sans-serif;
    line-height:1.45; -webkit-font-smoothing:antialiased;
    padding-bottom:48px;
  }
  .wrap{max-width:680px;margin:0 auto;padding:0 16px;}

  /* 毛玻璃导航 */
  .nav{
    position:sticky;top:0;z-index:20;
    backdrop-filter:saturate(180%) blur(20px);
    -webkit-backdrop-filter:saturate(180%) blur(20px);
    background:rgba(242,242,247,.72);
    border-bottom:.5px solid var(--line);
  }
  @media (prefers-color-scheme: dark){ .nav{background:rgba(0,0,0,.72);} }
  .nav-in{max-width:680px;margin:0 auto;padding:10px 16px;
    display:flex;align-items:center;justify-content:space-between;gap:12px;}
  .nav-title{font-weight:800;font-size:17px;letter-spacing:.3px;white-space:nowrap;
    background:linear-gradient(120deg,#ff9a00,#ff6a00 55%,#ffb84d);
    -webkit-background-clip:text;background-clip:text;color:transparent;}
  .nav-right{margin-left:auto;display:flex;align-items:center;gap:14px;min-width:0;}
  .nav-up{font-size:12px;color:var(--sub);display:flex;align-items:center;gap:6px;white-space:nowrap;}
  .dot{width:7px;height:7px;border-radius:50%;background:var(--media);
    box-shadow:0 0 0 0 rgba(52,199,89,.6);animation:pulse 2s infinite;}
  @keyframes pulse{0%{box-shadow:0 0 0 0 rgba(52,199,89,.5);}70%{box-shadow:0 0 0 7px rgba(52,199,89,0);}100%{box-shadow:0 0 0 0 rgba(52,199,89,0);}}

  /* 头部每日一句优美英文短句（上方） */
  .hero-quote{
    text-align:left;
    font-family:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,"Times New Roman",serif;
    font-style:italic;font-size:27px;line-height:1.55;color:var(--text);letter-spacing:.4px;
    display:flex;flex-direction:column;align-items:flex-start;gap:7px;
  }
  .hero-quote .qtxt{opacity:.95;}
  .hero-quote .qtxt .mark{color:var(--accent);font-style:normal;font-weight:700;font-size:30px;line-height:0;}
  .hero-quote .qby{font-size:14px;font-style:normal;opacity:.6;letter-spacing:.6px;}

  /* 头部 */
  .hero{padding:30px 0 6px;display:flex;flex-direction:column;gap:14px;}
  .hero .date{color:var(--sub);font-size:17px;font-weight:500;}
  .hero .cnt{color:var(--accent);font-weight:700;}

  /* 分段控制器 */
  .seg{
    display:flex;gap:4px;background:var(--accent-soft);
    padding:4px;border-radius:14px;margin:14px 0 0;
    position:relative;overflow:hidden;
  }
  .seg.seg-cat{margin-top:16px;}
  .seg button{
    flex:1;border:0;background:transparent;color:var(--text);
    font-size:14px;font-weight:600;padding:9px 0;border-radius:10px;
    cursor:pointer;transition:color .25s;font-family:inherit;position:relative;z-index:2;
  }
  .seg button.active{color:var(--accent);}
  .seg .pill{
    position:absolute;top:4px;bottom:4px;left:4px;width:calc((100% - 8px)/4 - 0px);
    background:var(--card);border-radius:10px;box-shadow:var(--shadow);
    transition:transform .3s cubic-bezier(.4,1.3,.5,1);z-index:1;
  }
  .seg.seg-cat{background:rgba(255,106,0,.10);}
  .seg.seg-cat .pill{background:linear-gradient(120deg,#ff9a00,#ff6a00);box-shadow:0 4px 14px rgba(255,106,0,.35);}
  .seg.seg-cat button.active{color:#fff;}

  /* 卡片 */
  .card{
    background:var(--card);border-radius:var(--radius);padding:16px 18px;
    margin-bottom:14px;box-shadow:var(--shadow);cursor:pointer;
    text-decoration:none;color:inherit;display:block;
    transition:transform .18s ease,box-shadow .18s ease;
    animation:rise .5s both;
  }
  .card:hover{transform:translateY(-3px);box-shadow:0 2px 6px rgba(0,0,0,.1),0 16px 40px rgba(0,0,0,.1);}
  @keyframes rise{from{opacity:0;transform:translateY(14px);}to{opacity:1;transform:none;}}
  .card-top{display:flex;align-items:center;gap:8px;margin-bottom:9px;flex-wrap:wrap;}
  .badge{display:inline-flex;align-items:center;gap:6px;font-size:12px;font-weight:600;
    padding:3px 9px;border-radius:999px;background:var(--accent-soft);color:var(--accent);}
  .badge .bdot{width:7px;height:7px;border-radius:50%;background:var(--accent);}
  .badge.news{background:rgba(255,149,0,.14);color:var(--news);} .badge.news .bdot{background:var(--news);}
  .badge.paper{background:rgba(94,92,230,.16);color:var(--paper);} .badge.paper .bdot{background:var(--paper);}
  .badge.product{background:rgba(94,92,230,.16);color:var(--paper);} .badge.product .bdot{background:var(--paper);}
  .badge.media{background:rgba(52,199,89,.16);color:var(--media);} .badge.media .bdot{background:var(--media);}
  .badge.sports{background:rgba(255,59,48,.15);color:var(--sport);} .badge.sports .bdot{background:var(--sport);}
  .badge.mil{background:rgba(48,176,199,.16);color:var(--mil);} .badge.mil .bdot{background:var(--mil);}
  .time{margin-left:auto;font-size:12px;color:var(--sub);}
  .card h2{margin:0 0 4px;font-size:17px;font-weight:700;line-height:1.35;letter-spacing:-.2px;}
  .zh-title{font-size:14.5px;font-weight:600;color:var(--text);opacity:.82;margin:0 0 7px;line-height:1.4;}
  .card p{margin:0;font-size:14.5px;color:var(--sub);line-height:1.5;
    display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;}
  .zh{font-size:13.5px;color:var(--sub);line-height:1.55;margin-top:6px;opacity:.95;}
  .card-foot{margin-top:11px;display:flex;align-items:center;gap:14px;font-size:12.5px;color:var(--sub);}
  .card-foot .go{margin-left:auto;color:var(--accent);font-weight:600;display:inline-flex;align-items:center;gap:3px;}

  .empty{text-align:center;color:var(--sub);padding:60px 20px;font-size:15px;}

  footer{text-align:center;color:var(--sub);font-size:12.5px;margin-top:30px;line-height:1.8;}
  footer .foot-sub{display:block;margin-top:5px;opacity:.7;font-size:11.5px;letter-spacing:.3px;}

  /* 底部详情面板 (iOS sheet) */
  .sheet-backdrop{position:fixed;inset:0;background:rgba(0,0,0,.42);
    backdrop-filter:blur(3px);-webkit-backdrop-filter:blur(3px);
    opacity:0;visibility:hidden;transition:opacity .3s,visibility .3s;z-index:50;}
  .sheet-backdrop.show{opacity:1;visibility:visible;}
  .sheet{position:absolute;left:0;right:0;bottom:0;background:var(--card);
    border-radius:22px 22px 0 0;padding:10px 20px calc(26px + env(safe-area-inset-bottom));
    max-height:84vh;overflow-y:auto;transform:translateY(100%);
    transition:transform .35s cubic-bezier(.3,1,.4,1);}
  .sheet-backdrop.show .sheet{transform:none;}
  .sheet-grip{width:38px;height:5px;border-radius:3px;background:var(--line);margin:4px auto 14px;}
  .sheet-close{position:absolute;top:10px;right:12px;border:0;background:transparent;
    color:var(--sub);font-size:26px;line-height:1;cursor:pointer;padding:2px 8px;}
  .sheet .badge{margin-bottom:10px;}
  .sheet h2{margin:0 0 12px;font-size:21px;font-weight:800;line-height:1.35;letter-spacing:-.3px;padding-right:30px;}
  .sheet .s-body{font-size:15.5px;color:var(--text);line-height:1.75;white-space:pre-wrap;word-break:break-word;}
  .sheet .s-foot{margin-top:18px;font-size:13px;color:var(--sub);display:flex;gap:16px;flex-wrap:wrap;}
</style>
</head>
<body>
  <div class="nav">
    <div class="nav-in">
      <div class="nav-title">丫丫资讯</div>
      <div class="nav-right">
        <div class="nav-up"><span class="dot"></span><span id="upd">更新中…</span></div>
      </div>
    </div>
  </div>

  <div class="wrap">
    <div class="hero">
      <div class="hero-quote">
        <span class="qtxt"><span class="mark">“</span>__DAILY_QUOTE__<span class="mark">”</span></span>
        <span class="qby">— __DAILY_AUTHOR__</span>
      </div>
      <div class="date" id="herodate">—</div>
    </div>

    <!-- 一级板块切换 -->
    <div class="seg seg-cat" id="segCat">
      <span class="pill" id="pillCat"></span>
      <button data-cat="ai" class="active">AI 科技</button>
      <button data-cat="sports">竞技体育</button>
      <button data-cat="mil">军事政治</button>
    </div>

    <!-- 二级筛选（按板块动态生成） -->
    <div class="seg" id="segSub"></div>

    <div id="feed"></div>

    <footer>
      由丫丫科技团队运营<br/>
      <span class="foot-sub">于信息洪流中，为你留住值得凝视的微光 · 每天一分钟，与世界同步思考</span>
    </footer>
  </div>

  <div class="sheet-backdrop" id="sheetBackdrop">
    <div class="sheet" id="sheetCard">
      <div class="sheet-grip"></div>
      <button class="sheet-close" id="sheetClose" aria-label="关闭">×</button>
      <div id="sheetBody"></div>
    </div>
  </div>

<script>
const DATA = __DATA_JSON__;
const WEEK = ["星期日","星期一","星期二","星期三","星期四","星期五","星期六"];

function fmtDate(d){
  return `${d.getFullYear()}年${d.getMonth()+1}月${d.getDate()}日 ${WEEK[d.getDay()]}`;
}
function relTime(iso){
  const t = new Date(iso).getTime();
  if (isNaN(t)) return "";
  const s = (Date.now()-t)/1000;
  if (s < 3600) return Math.max(1,Math.floor(s/60)) + " 分钟前";
  if (s < 86400) return Math.floor(s/3600) + " 小时前";
  if (s < 86400*7) return Math.floor(s/86400) + " 天前";
  const d = new Date(t);
  return `${d.getMonth()+1}月${d.getDate()}日`;
}

// 板块配置：一级板块 -> 二级筛选标签
const CATS = {
  ai: {
    label: "AI 科技",
    tabs: [
      {f:"all", label:"全部"}, {f:"news", label:"资讯"},
      {f:"product", label:"产品"}, {f:"media", label:"媒体"}
    ]
  },
  sports: {
    label: "竞技体育",
    tabs: [
      {f:"all", label:"全部"}, {f:"soccer", label:"足球"},
      {f:"basketball", label:"篮球"}, {f:"general", label:"综合"}
    ]
  },
  mil: {
    label: "军事政治",
    tabs: [
      {f:"all", label:"全部"}, {f:"world", label:"国际"},
      {f:"politics", label:"政治"}, {f:"military", label:"军事"}
    ]
  }
};
let cat = "ai";
let sub = "all";

// 导航更新时间
(() => {
  const ga = new Date(DATA.generated_at);
  document.getElementById("upd").textContent =
    "更新于 " + String(ga.getHours()).padStart(2,"0") + ":" + String(ga.getMinutes()).padStart(2,"0");
})();

function updateHero(){
  const c = (DATA[cat] && DATA[cat].count) || 0;
  document.getElementById("herodate").innerHTML =
    fmtDate(new Date()) + " · " + CATS[cat].label + " 收录国内外最新资讯 <span class='cnt'>" + c + "</span> 条";
}

// 渲染卡片
function render(){
  const feed = document.getElementById("feed");
  feed.innerHTML = "";
  const items = ((DATA[cat] && DATA[cat].items) || []).filter(it => sub==="all" || it.sub===sub);
  if (!items.length){ feed.innerHTML = "<div class='empty'>暂无相关内容</div>"; return; }
  items.forEach((it, i) => {
    const a = document.createElement("div");
    a.className = "card";
    a.style.animationDelay = (i*40) + "ms";

    const top = document.createElement("div"); top.className = "card-top";
    const badge = document.createElement("span");
    badge.className = "badge " + (it.category==="sports" ? "sports" : it.category==="mil" ? "mil" : it.sub);
    const bdot = document.createElement("span"); bdot.className = "bdot";
    badge.appendChild(bdot);
    badge.appendChild(document.createTextNode(it.source || (it.category==="sports"?"体育":it.category==="mil"?"军事政治":"资讯")));
    const time = document.createElement("span"); time.className = "time";
    time.textContent = relTime(it.published);
    top.appendChild(badge); top.appendChild(time);

    const h = document.createElement("h2"); h.textContent = it.title;
    const zhT = document.createElement("div"); zhT.className = "zh-title";
    zhT.textContent = it.title_zh || "";

    const p = document.createElement("p");
    p.textContent = it.summary || "热门话题精选，点击查看完整内容。";
    const zh = document.createElement("div"); zh.className = "zh";
    zh.textContent = it.summary_zh || "";

    const foot = document.createElement("div"); foot.className = "card-foot";
    if ((it.points||0) || (it.comments||0)){
      const m = document.createElement("span");
      m.textContent = `▲ ${it.points||0}  ·  💬 ${it.comments||0}`;
      foot.appendChild(m);
    } else if (it.author){
      const au = document.createElement("span"); au.textContent = it.author;
      foot.appendChild(au);
    }
    a.appendChild(top); a.appendChild(h);
    if (it.title_zh) a.appendChild(zhT);
    a.appendChild(p);
    if (it.summary_zh) a.appendChild(zh);
    a.appendChild(foot);
    a.addEventListener("click", () => openSheet(it));
    feed.appendChild(a);
  });
}

// 详情面板（点击卡片展开，不跳转外链）
const sheetBackdrop = document.getElementById("sheetBackdrop");
function openSheet(it){
  const body = document.getElementById("sheetBody");
  body.innerHTML = "";
  const badge = document.createElement("span");
  badge.className = "badge " + (it.category==="sports" ? "sports" : it.category==="mil" ? "mil" : it.sub);
  const bd = document.createElement("span"); bd.className = "bdot";
  badge.appendChild(bd);
  badge.appendChild(document.createTextNode(it.source || (it.category==="sports"?"体育":it.category==="mil"?"军事政治":"资讯")));
  const h = document.createElement("h2"); h.textContent = it.title;
  const zhT = document.createElement("div"); zhT.className = "zh-title";
  zhT.textContent = it.title_zh || "";
  const p = document.createElement("p"); p.className = "s-body";
  p.textContent = it.full || it.summary || "热门话题精选，点击查看完整内容。";
  const zh = document.createElement("div"); zh.className = "zh s-body";
  zh.textContent = (it.full_zh || it.summary_zh || "");
  body.appendChild(badge);
  body.appendChild(h);
  if (it.title_zh) body.appendChild(zhT);
  body.appendChild(p);
  if (it.full_zh || it.summary_zh) body.appendChild(zh);
  const foot = document.createElement("div"); foot.className = "s-foot";
  if ((it.points||0) || (it.comments||0)){
    const m = document.createElement("span");
    m.textContent = "▲ " + (it.points||0) + "  ·  💬 " + (it.comments||0);
    foot.appendChild(m);
  }
  if (it.author){ const au = document.createElement("span"); au.textContent = it.author; foot.appendChild(au); }
  const t = document.createElement("span"); t.textContent = relTime(it.published) || ""; foot.appendChild(t);
  body.appendChild(foot);
  sheetBackdrop.classList.add("show");
  document.body.style.overflow = "hidden";
}
function closeSheet(){
  sheetBackdrop.classList.remove("show");
  document.body.style.overflow = "";
}
document.getElementById("sheetClose").addEventListener("click", closeSheet);
sheetBackdrop.addEventListener("click", e => { if (e.target === sheetBackdrop) closeSheet(); });
document.addEventListener("keydown", e => { if (e.key === "Escape") closeSheet(); });

// 二级筛选（按当前板块重建）
function buildSub(){
  const seg = document.getElementById("segSub");
  seg.innerHTML = '<span class="pill" id="pillSub"></span>';
  CATS[cat].tabs.forEach((t, i) => {
    const btn = document.createElement("button");
    btn.textContent = t.label; btn.dataset.f = t.f;
    if (i === 0) btn.classList.add("active");
    seg.appendChild(btn);
  });
  const pill = seg.querySelector("#pillSub");
  const btns = [...seg.querySelectorAll("button")];
  function move(){
    const i = btns.findIndex(b => b.classList.contains("active"));
    pill.style.transform = `translateX(calc(${i} * 100%))`;
    pill.style.width = `calc((100% - 8px) / ${btns.length})`;
  }
  btns.forEach(b => b.addEventListener("click", () => {
    btns.forEach(x => x.classList.remove("active"));
    b.classList.add("active");
    sub = b.dataset.f; move(); render();
  }));
  window.addEventListener("resize", move);
  move();
}

// 一级板块切换
const segCat = document.getElementById("segCat");
const pillCat = document.getElementById("pillCat");
const catBtns = [...segCat.querySelectorAll("button")];
function moveCat(){
  const i = catBtns.findIndex(b => b.classList.contains("active"));
  pillCat.style.transform = `translateX(calc(${i} * 100%))`;
  pillCat.style.width = `calc((100% - 8px) / ${catBtns.length})`;
}
catBtns.forEach(b => b.addEventListener("click", () => {
  catBtns.forEach(x => x.classList.remove("active"));
  b.classList.add("active");
  cat = b.dataset.cat; sub = "all";
  moveCat(); buildSub(); updateHero(); render();
}));

moveCat();
buildSub();
updateHero();
render();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # 任何意外错误都不再中断：打印错误，保证上一次生成的页面仍在。
        print(f"! 生成过程中出现异常（已尽量保留现有页面）: {e}", file=sys.stderr)
