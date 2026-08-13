"""派生指标:脚本确定性计算,LLM 只准逐字引用。

存在理由:数字纪律禁止 LLM 计算任何数(防编造),代价是报告连"跌了多少"
都写不出来。派生量在这里算好落进快照,报告层引用即合法——防编造纪律不放松,
分析密度回来。每一项都必须能由快照原始值复算。
"""
from ..fixings import distinct_fixings, num as _num

from . import events as events_mod
from . import util

SCHEMA_VERSION = 1
RANGE_DAYS = 5
# 历史窗口要比 RANGE_DAYS 宽:周末与假日让相邻快照共享同一次定盘,
# 只读 5 份会让 range_5d 永远凑不满 5 个不同定盘日。
HISTORY_SPAN = RANGE_DAYS + 4
POLICY_INDICATOR = "政策利率"
CPI_INDICATOR = "CPI 同比"
EMPTY_RATE_DERIVED = {
    "chg_pct_1d": None,
    "range_%dd_low" % RANGE_DAYS: None,
    "range_%dd_high" % RANGE_DAYS: None,
    "range_%dd_days" % RANGE_DAYS: 0,
    "deviation_pct_prev": None,
}
EMPTY_REAL_RATE = {"value": None, "policy_rate": None, "policy_period": None,
                   "cpi": None, "cpi_period": None}
EMPTY_EVENTS_DERIVED = {"count": None, "count_prev": None, "count_delta": None,
                        "count_capped": None, "count_prev_capped": None,
                        "channel_changed_from": None,
                        "sample_capped": None, "dropped_malformed": None}
# 以上 EMPTY_* 的值必须保持不可变标量:异常分支用 dict() 浅拷贝隔离,
# 一旦塞入嵌套结构(list/dict),浅拷贝就不够,会让两次异常共享同一对象。


def _entry_of(snap, currency):
    if not isinstance(snap, dict):
        return None
    rates = snap.get("rates")
    if not isinstance(rates, dict):
        return None
    entry = rates.get(currency)
    return entry if isinstance(entry, dict) else None


def _event_entry_of(snap, currency):
    """该币种的**事件**条目。与 _entry_of 分开:后者读 rates,名字相近而定义域
    不同 —— 拿它去取 gnews_filter 会静默返回 None(即"不知道"),把已知的截断
    读成未观测。三处调用共用这一份,避免复制粘贴查找逻辑后各自漂移。"""
    events = snap.get("events") if isinstance(snap, dict) else None
    entry = events.get(currency) if isinstance(events, dict) else None
    return entry if isinstance(entry, dict) else None


def _fixing_key(ref, value):
    """一次定盘的身份。定盘日已知时用它;未知(存量快照)时退回按值去重——
    同值极大概率是同一次定盘被读了两遍(回填,或早于定盘时点的重复运行)。

    两族 key 刻意不互通:已知定盘日走 ref 分支,保证"真实两次定盘恰好同价"
    不被误合并。代价是过渡期(一侧已知、一侧是存量快照)可能把同一次定盘
    多算一次,随存量快照滚出历史窗口自愈。
    """
    return ("ref", ref) if isinstance(ref, str) else ("val", value)


def _chg_pct_1d(entry):
    # 参考价未更新 → 两值必然相等,但那不是价格变动(非工作日),不得算 0%
    ref, prev_ref = entry.get("ref_date"), entry.get("prev_ref_date")
    if isinstance(ref, str) and ref == prev_ref:
        return None
    today, prev = _num(entry.get("primary")), _num(entry.get("prev_primary"))
    if today is None or prev is None or prev == 0:
        return None
    if not isinstance(prev_ref, str) and today == prev:
        # 定盘日未知(存量快照)且两值 bit 级相等:无法区分"真持平"与"没定盘"。
        # 0.0% 会被读成方向结论,null 只是信息缺失——错误代价不对称,取 null。
        return None
    return round((today - prev) / prev * 100, 3)


def _range_nd(entry, history, currency):
    """近 N 次不同定盘的高低区间。同一次定盘的多份快照只算一次
    (回填会产生同值多份,不去重会把"一天"重复计入)。
    去重判定与周度聚合器共用 scripts/fixings,避免两处漂移。"""
    obs = []
    today = _num(entry.get("primary"))
    if today is not None:
        obs.append((entry.get("ref_date"), today))
    for snap in history:
        h = _entry_of(snap, currency)
        if h is None:
            continue
        v = _num(h.get("primary"))
        if v is None:
            continue
        obs.append((h.get("ref_date"), v))
    entries = distinct_fixings(obs)[:RANGE_DAYS]
    if not entries:
        return None, None, 0
    values = [v for _, v in entries]
    return min(values), max(values), len(values)


def _deviation_prev(history, currency):
    for snap in history:
        h = _entry_of(snap, currency)
        if h is not None and _num(h.get("deviation_pct")) is not None:
            return h["deviation_pct"]
    return None


def _article_count(snap, currency):
    if not isinstance(snap, dict):
        return None
    events = snap.get("events")
    if not isinstance(events, dict):
        return None
    entry = events.get(currency)
    if not isinstance(entry, dict):
        return None
    arts = entry.get("articles")
    return len(arts) if isinstance(arts, list) else None


def _rates_derived(payload, history, gaps):
    out = {}
    rates = payload.get("rates")
    if not isinstance(rates, dict):
        return out
    for currency, entry in rates.items():
        if not isinstance(entry, dict):
            continue
        try:
            low, high, days = _range_nd(entry, history, currency)
            out[currency] = {
                "chg_pct_1d": _chg_pct_1d(entry),
                "range_%dd_low" % RANGE_DAYS: low,
                "range_%dd_high" % RANGE_DAYS: high,
                "range_%dd_days" % RANGE_DAYS: days,
                "deviation_pct_prev": _deviation_prev(history, currency),
            }
        except Exception as e:   # 单币种失败不牵连其余;绝不向上抛(采集层硬契约)
            out[currency] = dict(EMPTY_RATE_DERIVED)   # 缺输入写 null,不省略键
            gaps.append(util.make_gap("derive", currency,
                                      "%s: %s" % (type(e).__name__, e)))
    return out


def _channel_of(snap, currency):
    """该币种当日事件的取数通道。条目存在但无 channel 字段 → 视为 "gdelt"。

    存量快照(本变更之前生成的)全部来自 GDELT,把它们当成"未知、所以视同相同"
    会让换通道当日照常相减 —— 实测 2026-08-12 的 USD(gnews 11 条)与 08-11
    (GDELT 顶到 8 条)因此给出 count_delta: 3,而两者上限与筛选口径都不同。
    与 macro._source_changed_from 的 row.get("source", "dbnomics") 同一约定。

    条目本身不存在 → None(那天压根没这个币种的事件,谈不上通道)。
    """
    entry = _event_entry_of(snap, currency)
    if entry is None:
        return None
    # 没有文章列表就没有通道:__main__ 把官方公告并进同一命名空间,于是
    # "当天事件采集彻底失败、只剩 official" 的条目照样存在(实测
    # data/2026-08-11.json 的 EUR)。对它返回 "gdelt" 会让日报写出
    # "前一日取自 gdelt 通道",而那天一条 GDELT 条目都没采到
    if not isinstance(entry.get("articles"), list):
        return None
    chan = entry.get("channel")
    return chan if isinstance(chan, str) and chan else "gdelt"


def _count_capped(snap, currency):
    """当日该币种的**落盘条数**是否被通道上限钉住。判定与周度聚合器共用
    events.landed_count_capped —— 两处各写一遍必然漂移。无法判断时返回 None。"""
    entry = _event_entry_of(snap, currency)
    if entry is None:
        return None
    meta = snap.get("meta") if isinstance(snap, dict) else None
    caps = meta.get("caps") if isinstance(meta, dict) else None
    return events_mod.landed_count_capped(entry, caps)


def _sample_capped(snap, currency):
    """当日**任一条通道**返回的原始样本是否触顶。含义是"被滤除/未取回的条数是
    下界",与最终落盘几条无关 —— 与 _count_capped 是两个问题。

    不叫 main_channel_capped:补位日里触顶的可能是主通道(gnews 的 99),也可能
    是补位通道自己(GDELT 的 8),两者取并。两个来源都不知道时返回 None。"""
    entry = _event_entry_of(snap, currency)
    if entry is None:
        return None
    flags = []
    own = entry.get("source_capped")
    if isinstance(own, bool):
        flags.append(own)
    gf = entry.get("gnews_filter")
    if isinstance(gf, dict) and isinstance(gf.get("capped"), bool):
        flags.append(gf["capped"])
    return any(flags) if flags else None


def _dropped_malformed(snap, currency):
    """当日被跳过的结构不可识别元素数。存量快照无此账 → None(不知道 ≠ 知道是 0)。"""
    entry = _event_entry_of(snap, currency)
    if entry is None:
        return None
    n = entry.get("articles_dropped_malformed")
    return n if isinstance(n, int) and not isinstance(n, bool) else None


def _events_derived(payload, history, gaps):
    """count 为 null 表示"没采到"(该币种事件采集失败),0 表示"确实 0 篇"——
    两者绝不可合并:把采集失败写成 0 就是在报"没发生",属编造。"""
    out = {}
    rates = payload.get("rates")
    currencies = list(rates) if isinstance(rates, dict) else []
    # 事件覆盖的币种由 events 模块的关键词表定义(含基准货币 USD,它不在 rates 里)
    currencies += [c for c in events_mod.KEYWORDS if c not in currencies]
    for currency in currencies:
        try:
            count = _article_count(payload, currency)
            prev = _article_count(history[0], currency) if history else None
            # 跨通道相减没有意义:GDELT 上限 8 且不过白名单,gnews 上限 99 且过
            # 白名单。实测 08-11 PHP=8(GDELT 顶到上限)与 08-12 PHP=2(gnews 81
            # 条滤剩 2)相减得 -6,会被报告写成"事件面变化"
            chan = _channel_of(payload, currency)
            chan_prev = _channel_of(history[0], currency) if history else chan
            switched = (chan is not None and chan_prev is not None
                        and chan != chan_prev)
            out[currency] = {
                "count": count,
                "count_prev": prev,
                "count_delta": (count - prev)
                               if (count is not None and prev is not None
                                   and not switched) else None,
                "channel_changed_from": chan_prev if switched else None,
                # 两天都触顶时 count_delta 恒为 0,"与前值持平"就成了上限造成的
                # 假象而非事件面平稳 —— 必须让报告能看见这一点
                "count_capped": _count_capped(payload, currency),
                "count_prev_capped": (_count_capped(history[0], currency)
                                      if history else None),
                # 原始样本触顶。与 count_capped 是两件事:被截断的是滤除前的
                # 样本,而 count 是滤后的数,可能离上限还差得远。合并成一个布尔
                # 会让"事件面确实持平"被写成"上限假象"
                "sample_capped": _sample_capped(payload, currency),
                # 源返回但结构不可识别被跳过的元素数。只落进周报是不够的:
                # 源改版当日日报的 count 会是 0 而正文无任何依据可引(第五轮 S1)
                "dropped_malformed": _dropped_malformed(payload, currency),
            }
        except Exception as e:
            out[currency] = dict(EMPTY_EVENTS_DERIVED)
            gaps.append(util.make_gap("derive", currency,
                                      "%s: %s" % (type(e).__name__, e)))
    return out


def _real_rate(payload, gaps):
    """政策利率 − CPI 同比。双期号原文强制携带:期错配是编造风险最大处,
    让引用方无法隐藏"用一年前的 CPI 配今天的利率"。"""
    out = {}
    macro = payload.get("macro")
    if not isinstance(macro, list):
        return out
    by_economy = {}
    for item in macro:
        if not isinstance(item, dict):
            continue
        economy, indicator = item.get("economy"), item.get("indicator")
        if not isinstance(economy, str) or indicator not in (POLICY_INDICATOR, CPI_INDICATOR):
            continue
        by_economy.setdefault(economy, {})[indicator] = item
    for economy, pair in by_economy.items():
        try:
            policy = pair.get(POLICY_INDICATOR) or {}
            cpi = pair.get(CPI_INDICATOR) or {}
            pv, cv = _num(policy.get("value")), _num(cpi.get("value"))
            pp, cp = policy.get("period"), cpi.get("period")
            pp = pp if isinstance(pp, str) else None
            cp = cp if isinstance(cp, str) else None
            # 任一缺失 → value 为 null(不给半截算式),但期号/单值照常暴露,
            # 便于报告说明"缺的是哪一半";键始终存在(spec: 记为 null 而非省略)
            complete = None not in (pv, cv, pp, cp)
            out[economy] = {"value": round(pv - cv, 3) if complete else None,
                            "policy_rate": pv, "policy_period": pp,
                            "cpi": cv, "cpi_period": cp}
        except Exception as e:
            out[economy] = dict(EMPTY_REAL_RATE)
            gaps.append(util.make_gap("derive", economy,
                                      "%s: %s" % (type(e).__name__, e)))
    return out


def derive(payload, history):
    """payload: 已组装的当日快照 dict;history: 按日期倒序的近若干份历史快照。

    注意"前值"的口径:`count_prev` / `deviation_pct_prev` 取自 history 里最近
    一份**存在**的快照,缺天时它不是昨天(与 rates 的 prev_primary 口径不同,
    后者严格取昨日文件)。
    """
    gaps = []
    if not isinstance(payload, dict):
        payload = {}
    history = [s for s in history if isinstance(s, dict)] if isinstance(history, list) else []
    return {
        "schema_version": SCHEMA_VERSION,
        "rates": _rates_derived(payload, history, gaps),
        "events": _events_derived(payload, history, gaps),
        "real_rate": _real_rate(payload, gaps),
    }, gaps
