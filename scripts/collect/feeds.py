"""央行官方新闻 RSS 采集:GDELT 之外的高可信事件通道(零 key,标准库 only)。

存在理由:GDELT 限流时该币种当日归因归零,且转述标题答不出"消息源是谁"。
官方公告可署名、可追溯,是限流日的兜底。

源表只列 2026-08-11 本机探针实测可达的两家(Fed 200 / ECB 200)。
BCB(全域 502)、BSP(404)、BOT(无 feed)刻意不写进来——不可达的源只会
每天往 gaps 里刷噪音,缺口记在 README 与 proposal。
"""
import xml.etree.ElementTree as ET

from . import util

MAX_ITEMS = 3
FEEDS = [
    {"issuer": "Fed", "currency": "USD", "endpoint": "fed_press_rss"},
    {"issuer": "ECB", "currency": "EUR", "endpoint": "ecb_press_rss"},
]


def collect(cfg):
    gaps, out = [], {}
    for f in FEEDS:
        if not _configured(cfg, f):
            # 未配置 = 有意停用(spec:不可达的源不写进配置),不是数据缺漏。
            # 记 gap 会让每份快照都带一条永久噪音,淹没真正的采集失败。
            continue
        items, err = _fetch_feed(cfg, f)
        if err is not None:
            gaps.append(util.make_gap("feeds", f["currency"], err))
            continue
        if not items:
            # 健康 feed 恒有条目;零条目通常意味着源改版(如换成带默认命名空间
            # 的 RDF/Atom,root.iter("item") 就取不到)。不记 gap 会与"未配置"
            # 的静默归零无法区分,静默劣化。
            gaps.append(util.make_gap("feeds", f["currency"],
                                      "parsed ok but no <item> found (源可能已改版)"))
            continue
        out[f["currency"]] = items
    return out, gaps


def _configured(cfg, f):
    endpoints = cfg.get("endpoints")
    if not isinstance(endpoints, dict):
        return False
    url = endpoints.get(f["endpoint"])
    return isinstance(url, str) and bool(url)


def _fetch_feed(cfg, f):
    try:
        url = cfg["endpoints"][f["endpoint"]]
        text = util.fetch_text(url, cfg["timeout_s"])
    except Exception as e:
        return None, "%s: %s" % (type(e).__name__, e)
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        return None, "unparseable feed: %s" % e
    except Exception as e:   # 深嵌套等意外一并转 gap,绝不上抛(采集层硬契约)
        return None, "unparseable feed: %s: %s" % (type(e).__name__, e)
    items = []
    for node in root.iter("item"):
        if len(items) >= MAX_ITEMS:
            break
        title = _text(node, "title")
        if title is None:
            continue    # 缺标题的条目跳过,不让整源失败
        items.append({"title": title, "link": _text(node, "link"),
                      "published": _text(node, "pubDate"),
                      "issuer": f["issuer"]})
    return items, None


def _text(node, tag):
    child = node.find(tag)
    if child is None or not isinstance(child.text, str):
        return None
    value = child.text.strip()
    return value or None
