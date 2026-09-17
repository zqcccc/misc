#!/usr/bin/env python3
"""AI 量化信息源扫描器（EP006 清单）。

只用标准库。单个源失败不影响其他源。
用法见 references/fetch-recipes.md。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

# 各站对 UA 挑剔且方向相反（实测 2026-09-02）：
#   quantocracy 只认裸 "Mozilla/5.0"，带括号说明或 curl/* 一律 400；
#   old.reddit 相反，裸 "Mozilla/5.0" 被 403，带说明的自定义 UA 才放行。
UA_BROWSER = "Mozilla/5.0"
UA_SCRIPT = "quant-source-scan/1.0 (research script)"
TIMEOUT = 25

DEFAULT_ARXIV_CATS = ["q-fin.TR", "q-fin.PM", "q-fin.ST", "cs.LG"]
ALL_SOURCES = ["quantocracy", "arxiv", "hf", "alphaarchitect", "mlquant", "quantitativo", "reddit"]
REDDIT_SUBS = ["algotrading", "quant"]

RSS_FEEDS = {
    "quantocracy": "https://quantocracy.com/feed/",
    "alphaarchitect": "https://alphaarchitect.com/feed/",
    "mlquant": "https://blog.ml-quant.com/feed",
    "quantitativo": "https://www.quantitativo.com/feed",
}

ATOM_NS = "{http://www.w3.org/2005/Atom}"


def fetch(url: str, ua: str = UA_BROWSER) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read()


def parse_date(raw: str) -> datetime | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    fmts = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d",
    ]
    for fmt in fmts:
        try:
            dt = datetime.strptime(raw.replace("GMT", "+0000"), fmt)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def clean(text: str, limit: int = 300) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def item(source: str, title: str, url: str, date: datetime | None, summary: str = "", extra: str = "") -> dict:
    return {
        "source": source,
        "title": clean(title, 200),
        "url": url,
        "date": date.strftime("%Y-%m-%d") if date else "",
        "_dt": date,
        "summary": clean(summary),
        "extra": extra,
        # 配额分组：同一个源里各组独立计 limit（arXiv 按请求的分类分组）
        "group": source,
    }


# --- 各源 ------------------------------------------------------------------

def scan_rss(name: str) -> list[dict]:
    root = ET.fromstring(fetch(RSS_FEEDS[name]))
    out = []
    for node in root.iter("item"):
        title = (node.findtext("title") or "").strip()
        link = (node.findtext("link") or "").strip()
        date = parse_date(node.findtext("pubDate") or "")
        desc = node.findtext("description") or ""
        out.append(item(name, title, link, date, desc))
    if not out:  # Atom fallback
        for node in root.iter(f"{ATOM_NS}entry"):
            link_el = node.find(f"{ATOM_NS}link")
            out.append(item(
                name,
                node.findtext(f"{ATOM_NS}title") or "",
                link_el.get("href") if link_el is not None else "",
                parse_date(node.findtext(f"{ATOM_NS}updated") or ""),
                node.findtext(f"{ATOM_NS}summary") or "",
            ))
    return out


def scan_arxiv(cats: list[str], query: str | None, limit: int) -> list[dict]:
    # 逐个分类查，不用一条 OR 查询：cs.LG 的日投稿量比 q-fin 大两个数量级，
    # 合在一起按日期排序会把 q-fin 整个挤出结果。
    out = []
    for cat in cats:
        search = "cat:%s" % cat
        if query:
            search = "%s AND all:%s" % (search, json.dumps(query))
        url = "http://export.arxiv.org/api/query?" + urllib.parse.urlencode({
            "search_query": search,
            "start": 0,
            "max_results": max(limit, 20),
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        })
        root = ET.fromstring(fetch(url))
        for entry in root.iter(f"{ATOM_NS}entry"):
            cat_el = entry.find("{http://arxiv.org/schemas/atom}primary_category")
            primary = cat_el.get("term") if cat_el is not None else ""
            row = item(
                "arxiv",
                entry.findtext(f"{ATOM_NS}title") or "",
                (entry.findtext(f"{ATOM_NS}id") or "").strip(),
                parse_date(entry.findtext(f"{ATOM_NS}published") or ""),
                entry.findtext(f"{ATOM_NS}summary") or "",
                primary,
            )
            row["group"] = cat
            out.append(row)
    return out


def scan_hf(limit: int) -> list[dict]:
    data = json.loads(fetch("https://huggingface.co/api/daily_papers?limit=%d" % max(limit * 2, 40)))
    out = []
    for row in data:
        paper = row.get("paper", {})
        pid = paper.get("id", "")
        out.append(item(
            "hf",
            paper.get("title", ""),
            "https://huggingface.co/papers/%s" % pid if pid else "",
            parse_date((row.get("publishedAt") or "")[:10]),
            paper.get("summary", ""),
            "▲%s" % paper.get("upvotes", 0),
        ))
    return out


def scan_reddit(query: str | None, limit: int) -> list[dict]:
    out = []
    for sub in REDDIT_SUBS:
        if query:
            url = "https://old.reddit.com/r/%s/search.json?%s" % (sub, urllib.parse.urlencode(
                {"q": query, "restrict_sr": 1, "sort": "top", "t": "all", "limit": limit}))
        else:
            url = "https://old.reddit.com/r/%s/top.json?%s" % (sub, urllib.parse.urlencode(
                {"t": "week", "limit": limit}))
        raw = fetch(url, UA_SCRIPT)
        if not raw.lstrip().startswith(b"{"):
            # Reddit 常返回 200 + 反爬过渡页而不是 JSON，脚本层没法绕
            raise RuntimeError("返回的不是 JSON（反爬过渡页），改用 web-access 的 CDP 模式访问 r/%s" % sub)
        data = json.loads(raw)
        for child in data.get("data", {}).get("children", []):
            d = child.get("data", {})
            out.append(item(
                "r/%s" % sub,
                d.get("title", ""),
                "https://www.reddit.com" + d.get("permalink", ""),
                datetime.fromtimestamp(d.get("created_utc", 0), tz=timezone.utc),
                d.get("selftext", ""),
                "↑%s" % d.get("score", 0),
            ))
    return out


# --- 主流程 ----------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="扫描 EP006 量化信息源")
    ap.add_argument("--days", type=int, default=14, help="只保留 N 天内的条目（0 = 不限）")
    ap.add_argument("--sources", default=",".join(ALL_SOURCES), help="逗号分隔：%s" % ",".join(ALL_SOURCES))
    ap.add_argument("--arxiv-cats", default=",".join(DEFAULT_ARXIV_CATS))
    ap.add_argument("--query", default=None, help="定向模式：关键词过滤 + arXiv/Reddit 全文检索")
    ap.add_argument("--limit", type=int, default=20, help="每个源最多输出多少条")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    wanted = [s.strip() for s in args.sources.split(",") if s.strip()]
    cats = [c.strip() for c in args.arxiv_cats.split(",") if c.strip()]
    cutoff = datetime.now(timezone.utc) - timedelta(days=args.days) if args.days else None

    results: dict[str, list[dict]] = {}
    errors: list[str] = []

    for name in wanted:
        try:
            if name in RSS_FEEDS:
                rows = scan_rss(name)
            elif name == "arxiv":
                rows = scan_arxiv(cats, args.query, args.limit)
            elif name == "hf":
                rows = scan_hf(args.limit)
            elif name == "reddit":
                rows = scan_reddit(args.query, args.limit)
            else:
                errors.append("%s: 未知源" % name)
                continue
        except (urllib.error.URLError, urllib.error.HTTPError, ET.ParseError,
                json.JSONDecodeError, TimeoutError, RuntimeError) as exc:
            errors.append("%s: %s" % (name, exc))
            continue

        if cutoff:
            rows = [r for r in rows if r["_dt"] is None or r["_dt"] >= cutoff]
        if args.query:
            kw = args.query.lower()
            rows = [r for r in rows if kw in r["title"].lower() or kw in r["summary"].lower()]
        rows.sort(key=lambda r: r["_dt"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        for row in rows:
            row.pop("_dt", None)
        # 按 group 分别计配额：cs.LG 的投稿量比 q-fin 大两个数量级，
        # 统一截断会把 q-fin 整个挤掉
        used: dict[str, int] = {}
        seen: set[str] = set()
        kept = []
        for row in rows:
            if row["url"] in seen:  # 同一篇会在多个分类里重复出现
                continue
            seen.add(row["url"])
            g = row["group"]
            if used.get(g, 0) >= args.limit:
                continue
            used[g] = used.get(g, 0) + 1
            kept.append(row)
        results[name] = kept

    if args.json:
        print(json.dumps({"results": results, "errors": errors}, ensure_ascii=False, indent=2))
        return 0

    total = 0
    for name, rows in results.items():
        print("\n=== %s (%d) ===" % (name, len(rows)))
        for row in rows:
            total += 1
            tag = " [%s]" % row["extra"] if row["extra"] else ""
            print("- %s%s %s" % (row["date"] or "????-??-??", tag, row["title"]))
            print("  %s" % row["url"])
    print("\n共 %d 条。" % total)
    if errors:
        print("\n失败的源：")
        for err in errors:
            print("  ! %s" % err)
    return 0


if __name__ == "__main__":
    sys.exit(main())
