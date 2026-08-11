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
DEFAULT_DELAY_S = 20     # spec 硬约束:生产串行间隔 ≥5 秒;默认 20 秒(429 缓解)
DEFAULT_BACKOFF_S = 30   # 限速退避
RATE_LIMIT_MARKERS = ("rate limit", "too many", "quota", "please try again", "throttl")
MAX_RECORDS = 8


def query_order(date_str):
    """五币种查询顺序,按采集日期确定性轮转。

    限流下总是尾部的几组挂掉;固定顺序会让同一批币种(实测:PHP/THB/BRL)
    天天缺事件。轮转把损失摊到各币种,且同日重跑顺序不变(可断言、可复现)。
    """
    keys = list(KEYWORDS)
    offset = sum(ord(ch) for ch in str(date_str)) % len(keys)
    return keys[offset:] + keys[:offset]


def _dedupe_titles(articles):
    """同币种内标题完全相同的只留首条;标题缺失(None)不构成重复。"""
    seen, out = set(), []
    for a in articles:
        title = a.get("title")
        if isinstance(title, str):
            if title in seen:
                continue
            seen.add(title)
        out.append(a)
    return out


def collect(cfg):
    gaps, out = [], {}
    first = True
    for currency in query_order(cfg["date"]):
        if not first:
            time.sleep(cfg["gdelt_delay_s"])
        first = False
        articles, err = _query_with_retry(cfg, KEYWORDS[currency])
        if err is not None:
            gaps.append(util.make_gap("gdelt", currency, err))
            continue
        out[currency] = {"articles": _dedupe_titles(articles)}
    return out, gaps


def _is_rate_limited(err):
    """软限速(HTTP 200 + 限速正文)与硬限流(HTTP 429)统一走退避重试。"""
    return err == "soft-rate-limited" or (isinstance(err, str) and "429" in err)


def _query_with_retry(cfg, query):
    articles, err = _fetch(cfg, query)
    if _is_rate_limited(err):
        time.sleep(cfg["gdelt_backoff_s"])
        first_err = err
        articles, err = _fetch(cfg, query)
        if _is_rate_limited(err):
            return None, "rate-limited after retry (%s)" % (err or first_err)
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
    except (ValueError, RecursionError):
        # RecursionError:深嵌套 JSON 正文令 json.loads 爆栈,非 ValueError 子类,
        # 必须一并就地转 gap,不得穿透 collect()(硬契约)
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
    # tone 不落盘:artlist 端点不返回该字段(实测 40/40 为 null),留着即误导
    arts = [{"title": a.get("title"), "url": a.get("url"), "domain": a.get("domain"),
             "seendate": a.get("seendate")}
            for a in raw if isinstance(a, dict)]  # 非 dict 元素 → 跳过
    return arts, None
