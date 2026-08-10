"""GDELT DOC 2.0 事件采集:五币种关键词组串行查询,软限速识别+退避重试一次。"""
import json
import time
import urllib.parse

from . import util

KEYWORDS = {
    "USD": '("Federal Reserve" OR "US dollar")',
    "EUR": '("European Central Bank" OR "euro zone")',
    "PHP": '("Philippine peso" OR "Bangko Sentral")',
    "THB": '("Thai baht" OR "Bank of Thailand")',
    "BRL": '("Brazilian real" OR "Banco Central do Brasil" OR Copom)',
}
DEFAULT_DELAY_S = 5      # spec 硬约束:生产串行间隔 ≥5 秒
DEFAULT_BACKOFF_S = 30   # 软限速退避
RATE_LIMIT_MARKERS = ("rate limit", "too many", "quota", "please try again", "throttl")
MAX_RECORDS = 8


def collect(cfg):
    gaps, out = [], {}
    first = True
    for currency, query in KEYWORDS.items():
        if not first:
            time.sleep(cfg["gdelt_delay_s"])
        first = False
        articles, err = _query_with_retry(cfg, query)
        if err is not None:
            gaps.append(util.make_gap("gdelt", currency, err))
            continue
        tones = [a["tone"] for a in articles
                 if isinstance(a.get("tone"), (int, float))
                 and not isinstance(a.get("tone"), bool)]
        out[currency] = {
            "articles": articles,
            "tone_avg": round(sum(tones) / len(tones), 2) if tones else None,
        }
    return out, gaps


def _query_with_retry(cfg, query):
    articles, err = _fetch(cfg, query)
    if err == "soft-rate-limited":
        time.sleep(cfg["gdelt_backoff_s"])
        articles, err = _fetch(cfg, query)
        if err == "soft-rate-limited":
            return None, "rate-limited after retry"
    return articles, err


def _window(cfg):
    """查询时间窗:backfill 用显式 datetime 区间(昨日 00:00 → 当日 00:00);
    默认 timespan=48h(design:覆盖"前一日"并容忍时区/抓取延迟)。"""
    if cfg["backfill"]:
        return {
            "startdatetime": cfg["yesterday"].replace("-", "") + "000000",
            "enddatetime": cfg["date"].replace("-", "") + "000000",
        }
    return {"timespan": "48h"}


def _fetch(cfg, query):
    params = {"query": query, "mode": "artlist", "format": "json",
              "maxrecords": MAX_RECORDS, "sort": "hybridrel"}
    params.update(_window(cfg))
    url = cfg["endpoints"]["gdelt_doc_url"] + "?" + urllib.parse.urlencode(params)
    try:
        text = util.fetch_text(url, cfg["timeout_s"])
    except Exception as e:
        return None, "%s: %s" % (type(e).__name__, e)
    try:
        doc = json.loads(text)
    except ValueError:
        low = text.lower()
        if any(m in low for m in RATE_LIMIT_MARKERS):
            return None, "soft-rate-limited"
        return None, "unparseable response (HTTP 200)"
    # 仓库约定:外部数据每次成员访问前过 isinstance 门(json.loads 可返回 list/标量/None)
    if not isinstance(doc, dict):
        return None, ("unparseable response (HTTP 200): expected object, got %s"
                      % type(doc).__name__)
    raw = doc.get("articles")
    if not isinstance(raw, list):
        raw = []  # articles 非 list → 视为空
    arts = [{"title": a.get("title"), "url": a.get("url"), "domain": a.get("domain"),
             "seendate": a.get("seendate"), "tone": a.get("tone")}
            for a in raw if isinstance(a, dict)]  # 非 dict 元素 → 跳过
    return arts, None
