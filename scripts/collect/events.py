"""事件采集:Google News RSS 为主通道 + 域名白名单闸门,GDELT 只补空洞。

主通道实测 5/5 币种可达而 GDELT 只有 2/5(2026-08-12,三个 hard-429)。但裸接
主通道会把噪音换进沉默——PHP 88 条里 76 条是加密货币换算页("PHP" 同时是交易对
代码)。沉默有 gap 机制可披露,噪音没有,故相关性闸门与逐层过滤计数是本模块主体。
"""
import json
import os
import time
import urllib.error
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

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

# 实测上限在 99–100 摆动(宽查询 the/dollar 返 100,加 num=200 返 99)。取下界:
# 漏报截断会让报告把下界当全量断言,误报只让结论变弱 —— 宁可少说不可错说。
GNEWS_SOFT_CAP = 99
GNEWS_WINDOW_H = 48                # 与 GDELT timespan=48h 对齐
GNEWS_QUERY_SUFFIX = " when:2d"    # 服务端窗口;实测不可信,本地仍要过滤一遍


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


def _host(url):
    """取小写主机名并剥 www. 前缀。取不到返回 None,不返回空串——
    空串会悄悄参与白名单比较,None 不会。"""
    if not isinstance(url, str) or not url:
        return None
    host = url.split("//")[-1].split("/")[0].split("?")[0].strip().lower()
    if not host:
        return None
    return host[4:] if host.startswith("www.") else host


def _gnews_parse(text):
    """Google News RSS → [{title, url, pubdate_raw, domain}]。

    非 XML、空正文、XML 里没有 <item> —— 一律抛 ValueError,由调用方转 gap。
    **绝不返回空列表**:那会让"源改版了"与"该币种确实没新闻"在快照里完全同形,
    下游据此可以得出"昨日无明确驱动"。这与 _fetch 里
    "parsed ok but no usable 'articles' list" 是同一道门。
    """
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        raise ValueError("响应不是合法 XML: %s" % e)
    items = root.findall(".//item")
    if not items:
        raise ValueError("XML 可解析但无 <item>(源可能已改版或返回了错误页)")
    out = []
    for it in items:
        src = it.find("source")
        out.append({
            "title": it.findtext("title"),
            "url": it.findtext("link"),
            "pubdate_raw": it.findtext("pubDate"),
            "domain": _host(src.get("url")) if src is not None else None,
        })
    return out


def _pubdate(raw):
    """RFC 2822 → 带 tzinfo 的 datetime;解析不了返回 None。

    无 tzinfo 时按 UTC 补齐,**不猜本地时区** —— 猜了会让窗口边界随运行机器
    漂移,同一份数据换台机器就得出不同结论。
    """
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        dt = parsedate_to_datetime(raw)
    except (TypeError, ValueError, OverflowError):
        # 3.10 前抛 TypeError、之后抛 ValueError;年份越界抛 OverflowError
        return None
    if not isinstance(dt, datetime):
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _in_whitelist(host, domains):
    """判据必须是「完全相等 或 以点号加白名单项结尾」。

    裸 `host.endswith(d)` 会让 notreuters.com 命中 reuters.com —— 白名单形同虚设,
    而且失效方式是静默的:噪音照进快照,过滤计数还显示"已过滤"。
    """
    if not isinstance(host, str) or not host:
        return False
    return any(host == d or host.endswith("." + d) for d in domains)


def _gnews_filter(items, lo, hi, domains):
    """→ (kept, counts)。counts 含 raw/undated/out_window/offlist/kept,四层账闭合。

    四个计数在同一个函数里出,调用方不各算各的 —— 分头算的东西迟早对不上,
    而对不上的那一刻没人会发现(计数看起来总是"有个数")。

    顺序:时间戳 → 窗口 → 白名单。去重由调用方在**之后**做:先去重会让
    offlist 的分母与 raw 对不上。

    seendate 用 GDELT 的 %Y%m%dT%H%M%SZ 格式落盘(先归一 UTC):
    weekly_digest.SEEN_DATE_RE 只认这个形态,落 ISO 会让它对每条 gnews 文章
    都返回 None,周报据此把整周降级为"有无事件无法判定"。
    """
    counts = {"raw": len(items), "undated": 0, "out_window": 0,
              "offlist": 0, "kept": 0}
    kept = []
    for it in items:
        dt = _pubdate(it.get("pubdate_raw"))
        if dt is None:
            counts["undated"] += 1
            continue
        if not (lo <= dt <= hi):
            counts["out_window"] += 1
            continue
        if not _in_whitelist(it.get("domain"), domains):
            counts["offlist"] += 1
            continue
        kept.append({
            "title": it.get("title"), "url": it.get("url"),
            "domain": it.get("domain"),
            "seendate": dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        })
    counts["kept"] = len(kept)
    # 截断事实记在这一节里:GDELT 补位会覆写条目级的 source_capped,
    # 主通道"抓到 100 条已顶到上限"的事实必须留在主通道自己的账上
    counts["capped"] = counts["raw"] >= GNEWS_SOFT_CAP
    return kept, counts


def _load_domains(cfg, gaps):
    """→ domains 列表,或 None 表示「gnews 通道停用」。

    三级处置,沿用仓库既有约定:
      未配置 / 文件不存在  → None,**不记 gap**(有意停用,删掉文件即整通道回滚)
      JSON 解析失败        → 记 gap 后 None(配置了但坏了)
      domains 非 list/为空 → 记 gap 后 None

    最后一条尤其要响:空白名单会把一切过滤成 0 条,五个币种同时"没有事件",
    而日报会把这写成五国昨日均无驱动 —— 管道状态被当成市场事实。
    """
    path = cfg.get("news_sources_path")
    if not isinstance(path, str) or not path or not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, ValueError, RecursionError) as e:
        # RecursionError:深嵌套 JSON 令 json.load 爆栈,非 ValueError 子类
        gaps.append(util.make_gap("gnews", "whitelist",
                                  "%s: %s" % (type(e).__name__, e)))
        return None
    raw = doc.get("domains") if isinstance(doc, dict) else None
    # 归一成裸主机名:写成 www.reuters.com / https://ft.com / .cnbc.com 的项
    # 对任何主机名都永远返回 False —— "加了源却没生效"必须变成可见事件
    clean, bad = [], []
    for d in (raw if isinstance(raw, list) else []):
        h = _host(d.strip().lstrip(".")) if isinstance(d, str) else None
        if h:
            if h not in clean:
                clean.append(h)
        elif isinstance(d, str) and d.strip():
            bad.append(d)
    if bad:
        gaps.append(util.make_gap("gnews", "whitelist",
                                  "以下白名单项无法归一成主机名,已忽略:%s"
                                  % "、".join(bad[:5])))
    if not clean:
        gaps.append(util.make_gap(
            "gnews", "whitelist",
            "domains 缺失/非列表/无有效项——空白名单会把全部条目过滤掉,拒绝启用"))
        return None
    return clean


def _gnews_window(cfg):
    """(lo, hi)。与 GDELT 的 backfill / timespan=48h 两种形态对齐。"""
    if cfg["backfill"]:
        lo = datetime.strptime(cfg["yesterday"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        hi = datetime.strptime(cfg["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return lo, hi
    now = datetime.now(timezone.utc)
    # hi 留 5 分钟余量容忍源侧时钟略快;不留会把刚发布的条目判成"未来条目"丢掉
    return now - timedelta(hours=GNEWS_WINDOW_H), now + timedelta(minutes=5)


def _gnews_entry(articles, raw_count, counts):
    """gnews 条目的统一形状。截断由采集层算好落盘,下游只读不比 ——
    两条通道上限不同,下游拿单一上限去比必然错位。

    **两个截断是两个问题,不可共用一个布尔**:
    - `source_capped`:源返回的**原始样本**触顶(raw >= 99)。含义是"被滤除的
      原始条数是下界",与最终留下几条无关。
    - `count_at_cap`:**落盘条数**被上限钉住(kept >= 99)。只有它才允许下游说
      "已达当日采集上限,实际篇数只多不少"。

    GDELT 上两者恒等(不过滤),gnews 上不等:实测 data/2026-08-12.json 的 USD
    是 raw=100、kept=11 —— 顶到 99 的是滤除**前**的样本,落盘的 11 条离 99 差 88。
    共用一个布尔会让日报把"事件数 11"写成"已达当日采集上限"。

    articles 为 None 表示**没采到**(观测缺口),为 [] 表示**采到了、可用的 0 条**。
    两者绝不可混:混了之后彻底的管道停摆会被周度聚合器读成"区间内确实 0 条,
    全区间采集完整、无截断" —— 本仓库的招牌失效形态。同理 raw_count 为 None 时
    两个截断标记也都是 None(不知道),不是 False(知道没截断)。
    """
    known = isinstance(raw_count, int) and not isinstance(raw_count, bool)
    kept = counts.get("kept") if isinstance(counts, dict) else None
    kept_known = isinstance(kept, int) and not isinstance(kept, bool)
    return {"articles": articles, "articles_raw_count": raw_count,
            "source_cap": GNEWS_SOFT_CAP,
            "source_capped": (raw_count >= GNEWS_SOFT_CAP) if known else None,
            "count_at_cap": (kept >= GNEWS_SOFT_CAP) if kept_known else None,
            # 主通道自己造条目 dict,不存在"元素结构不可识别"这一路
            "articles_dropped_malformed": 0 if articles is not None else None,
            "channel": "gnews", "gnews_filter": counts}


def landed_count_capped(entry, caps):
    """落盘条数是否被通道上限钉住。**两个下游消费者共用这一份**(周度聚合器与
    派生量),复制粘贴判定逻辑后漂移是本仓库栽过的坑(见 scripts/fixings.py)。

    caps: {"gnews_records": n, "gdelt_records": n} —— 采集当时的真值,缺则用常量。

    存量快照没有 count_at_cap,须按通道回退:
    - GDELT 不过滤,source_capped 与"落盘条数被钉住"恒等,直接用
    - gnews 的 source_capped 说的是**滤除前**样本触顶(raw=100>=99),落盘的是
      滤后的 kept 条 —— 拿它当"条数触顶"会把 11 条说成撞了 99 的上限
    无从判断时返回 None(不知道 ≠ 知道没触顶)。
    """
    if not isinstance(entry, dict):
        return None
    flag = entry.get("count_at_cap")
    if isinstance(flag, bool):
        return flag
    def _cap(key, fallback):
        v = caps.get(key) if isinstance(caps, dict) else None
        return v if isinstance(v, int) and not isinstance(v, bool) and v > 0 else fallback
    if entry.get("channel") == "gnews":
        gf = entry.get("gnews_filter")
        kept = gf.get("kept") if isinstance(gf, dict) else None
        if isinstance(kept, int) and not isinstance(kept, bool):
            return kept >= _cap("gnews_records", GNEWS_SOFT_CAP)
        # 没有过滤账就没有"滤后条数"可比,退回条目自己的权威布尔
    own = entry.get("source_capped")
    if isinstance(own, bool):
        return own
    raw = entry.get("articles_raw_count")
    if not (isinstance(raw, int) and not isinstance(raw, bool)):
        arts = entry.get("articles")
        if not isinstance(arts, list):
            return None
        raw = len(arts)
    return raw >= _cap("gdelt_records", MAX_RECORDS)


def _gnews_one(cfg, currency, domains):
    """→ (entry, err)。err 非 None 表示该币种 gnews 没跑成,应进 holes。

    失败时 entry 仍返回(articles 空、gnews_filter 为 None),使"没跑成"
    在快照里与"跑了但一条没留下"可分辨。异常一律转 err,绝不上抛。
    """
    try:
        # 模板组装也在 try 内:endpoints.json 是 README 里写明可手改的旋钮,
        # 多一个占位符就会让 .format 抛 KeyError —— 那会穿透 collect() 上抛,
        # 把五个币种的事件连同 GDELT 回落一起吞掉(违反采集层硬契约)
        url = cfg["endpoints"]["gnews_rss_url"].format(
            query=urllib.parse.quote(KEYWORDS[currency] + GNEWS_QUERY_SUFFIX))
        items = _gnews_parse(util.fetch_text(url, cfg["timeout_s"]))
        lo, hi = _gnews_window(cfg)
        # 过滤阶段同样碰外部数据(pubDate / source url 都来自响应),留在 try 外
        # 等于给采集层留了一条上抛的路
        kept, counts = _gnews_filter(items, lo, hi, domains)
    except Exception as e:
        # articles=None 而非 []:没采到与"采到了但 0 条"必须可分辨
        return _gnews_entry(None, None, None), "%s: %s" % (type(e).__name__, e)
    return _gnews_entry(_dedupe_titles(kept), counts["raw"], counts), None


def collect(cfg):
    """两趟:gnews 主通道 → GDELT 只补空洞。

    holes 是显式列表而不是隐含条件:让"没出现空洞就一次 GDELT 请求都不发"
    能被直接断言(测试计请求数),而不是靠观察副作用推断。
    """
    gaps, out = [], {}
    domains = _load_domains(cfg, gaps)
    endpoints = cfg.get("endpoints")
    gnews_url = endpoints.get("gnews_rss_url") if isinstance(endpoints, dict) else None
    gnews_on = bool(domains) and isinstance(gnews_url, str) and bool(gnews_url)

    # gnews 停用 → 全是空洞 → 全部走 GDELT,即接入前的现状
    holes = list(KEYWORDS)
    if gnews_on:
        holes = []
        for currency in KEYWORDS:   # 无 sleep:每币种 1 次 GET,共 5 次
            entry, err = _gnews_one(cfg, currency, domains)
            if err is not None:
                gaps.append(util.make_gap("gnews", currency, err))
            out[currency] = entry
            if not entry["articles"]:   # None(没采到)与 [](全被滤掉)都算空洞
                holes.append(currency)

    first = True
    for currency in query_order(cfg["date"]):
        if currency not in holes:
            continue
        if not first:
            time.sleep(cfg["gdelt_delay_s"])
        first = False
        articles, err = _query_with_retry(cfg, KEYWORDS[currency])
        if err is not None:
            # 主通道也没取到时,这条 gap 的含义是"两条通道都空",比单说 GDELT
            # 限流更重要 —— 前者才是真缺口,后者在补位模式下只是过程
            gaps.append(util.make_gap(
                "gdelt", currency,
                "两条通道均未取得条目(gnews 无可用条目;GDELT %s)" % err
                if gnews_on else err))
            continue
        # 去重前条数一并落盘:只留去重后的长度,下游就无法判断"是否顶到
        # 每日上限"——同一批里删掉两条重复,8 条会变成 6 条,截断被漏报
        arts, raw_count, dropped = articles
        prior = out.get(currency)
        known = isinstance(raw_count, int) and not isinstance(raw_count, bool)
        entry = {
            "articles": _dedupe_titles(arts), "articles_raw_count": raw_count,
            "source_cap": MAX_RECORDS,
            # 本通道不过滤,故"原始样本触顶"与"落盘条数被钉住"恒等 —— 但仍分两个
            # 字段落盘:下游不该靠"当前是哪条通道"去猜某个布尔是哪个含义
            "source_capped": known and raw_count >= MAX_RECORDS,
            "count_at_cap": known and raw_count >= MAX_RECORDS,
            "articles_dropped_malformed": dropped,
            "channel": "gdelt",
        }
        # 保留主通道那一趟的账:丢了它,"gnews 抓到 88 条但白名单挡了 86 条"
        # 这个唯一能判断白名单是否配得过严的信息就消失了
        if isinstance(prior, dict) and "gnews_filter" in prior:
            entry["gnews_filter"] = prior["gnews_filter"]
        out[currency] = entry
    # 「有没有拿到可署名来源的报道」由脚本给结论,SKILL 只引用这个布尔。
    # 让 LLM 自己组合「gnews_filter.kept == 0 且 articles 为空」两个条件,
    # 补位成功那天就会一边列着 GDELT 条目、一边写"未取得可署名来源",自相矛盾
    #
    # 三态陈述在 articles 自己的定义域上,与它的三态一一对应:
    #   None(没采到)  → None,不知道
    #   []  (采到了、可用 0 条) → True,确实一条可署名来源都没有
    #   非空                    → False,取得了
    # 第二轮把它挂在 gnews_filter 上,于是 README 写明的整通道回滚(删掉
    # config/news_sources.json、gnews 静默停用、GDELT 正常取回条目、零 gap)
    # 下五币种恒为 null —— 完全健康的形态被写成"没观测过"。
    for currency, entry in out.items():
        arts = entry.get("articles")
        entry["attributable_source_absent"] = (
            None if not isinstance(arts, list) else not arts)
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
    endpoints = cfg.get("endpoints")
    base = endpoints.get("gdelt_doc_url") if isinstance(endpoints, dict) else None
    if not isinstance(base, str) or not base:
        return None, "gdelt_doc_url 未配置"
    url = base + "?" + urllib.parse.urlencode(params)
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
    # 原始条数含被丢弃的元素:用过滤后的长度比每日上限会漏报截断。
    # dropped 必须一路落到快照:源改版成 {"articles": ["<a>", ...]} 时这里
    # 逐个跳过、raw_count 仍是 3、gaps 为空,落盘与"确实一条都没有"完全同形,
    # 聚合器据此断言"区间内确实 0 条、全区间采集完整"(第四轮 S1)
    return (arts, len(raw), dropped), None
