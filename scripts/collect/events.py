"""GDELT DOC 2.0 事件采集:五币种关键词组串行查询,软限速识别+退避重试一次。"""
import json
import time
import urllib.error
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
SOFT_LIMIT_ERR = "soft-rate-limited"     # HTTP 200 + 限速正文
HARD_LIMIT_ERR = "hard-rate-limited-429"  # HTTP 429


def query_order(date_str):
    """五币种查询顺序,按采集日期确定性轮转。

    这是**公平性措施,不是 429 缓解手段**:固定顺序下若限流按位置发生,同一批
    币种会天天缺事件,轮转把损失摊开。2026-08-11 实测证伪了"限流总落在尾部"
    的假设(轮转把 BRL 排到首位,它仍首个 429,而位置 2、3 成功)——本机限流
    与位置无关,事件覆盖的主解仍是换机器。同日重跑顺序不变(可断言、可复现)。
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
        # 去重前条数一并落盘:只留去重后的长度,下游就无法判断"是否顶到
        # 每日上限"——同一批里删掉两条重复,8 条会变成 6 条,截断被漏报
        arts, raw_count = articles
        out[currency] = {"articles": _dedupe_titles(arts),
                         "articles_raw_count": raw_count}
    return out, gaps


def _is_rate_limited(err):
    """软限速(HTTP 200 + 限速正文)与硬限流(HTTP 429)统一走退避重试。
    判定用哨兵值而非在错误串里搜 "429" —— 后者会被 IncompleteRead(429 bytes)
    这类携带字节数的异常误伤。"""
    return err in (SOFT_LIMIT_ERR, HARD_LIMIT_ERR)


def _query_with_retry(cfg, query):
    articles, err = _fetch(cfg, query)
    if _is_rate_limited(err):
        first_err = err
        time.sleep(cfg["gdelt_backoff_s"])
        articles, err = _fetch(cfg, query)
        if _is_rate_limited(err):
            return None, "rate-limited after retry (%s, first: %s)" % (err, first_err)
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
    except urllib.error.HTTPError as e:
        # 硬限流在源头认出来(拿 e.code),不靠在错误串里搜数字
        if e.code == 429:
            return None, HARD_LIMIT_ERR
        return None, "%s: %s" % (type(e).__name__, e)
    except Exception as e:
        return None, "%s: %s" % (type(e).__name__, e)
    try:
        doc = json.loads(text)
    except (ValueError, RecursionError):
        # RecursionError:深嵌套 JSON 正文令 json.loads 爆栈,非 ValueError 子类,
        # 必须一并就地转 gap,不得穿透 collect()(硬契约)
        low = text.lower()
        if any(m in low for m in RATE_LIMIT_MARKERS):
            return None, SOFT_LIMIT_ERR
        return None, "unparseable response (HTTP 200)"
    # 仓库约定:外部数据每次成员访问前过 isinstance 门(json.loads 可返回 list/标量/None)
    if not isinstance(doc, dict):
        return None, ("unparseable response (HTTP 200): expected object, got %s"
                      % type(doc).__name__)
    raw = doc.get("articles")
    if not isinstance(raw, list):
        # 「JSON 能解析但结构不认识」曾被折叠成空列表且不记 gap —— 落盘后与
        # 「GDELT 确实一条都没索引到」在结构上完全不可区分,聚合器据此可以
        # 得出「区间内确实 0 条」。源改版/字段改名/HTTP 200 错误信封都走这条路。
        # feeds.py 对完全同类的危害是显式记 gap 的(见其 collect 的零条目分支),
        # 这里补上同一道门。
        return None, ("parsed ok but no usable 'articles' list (got %s;"
                      "源可能已改版或返回了 HTTP 200 错误信封)" % type(raw).__name__)
    # tone 不落盘:artlist 端点不返回该字段(实测 40/40 为 null),留着即误导
    arts, dropped = [], 0
    for a in raw:
        if not isinstance(a, dict):
            dropped += 1        # 非 dict 元素 → 跳过,但要计入原始条数
            continue
        arts.append({"title": a.get("title"), "url": a.get("url"),
                     "domain": a.get("domain"), "seendate": a.get("seendate")})
    # 原始条数含被丢弃的元素:用过滤后的长度比每日上限会漏报截断
    return (arts, len(raw)), None
