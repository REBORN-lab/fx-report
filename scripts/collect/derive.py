"""派生指标:脚本确定性计算,LLM 只准逐字引用。

存在理由:数字纪律禁止 LLM 计算任何数(防编造),代价是报告连"跌了多少"
都写不出来。派生量在这里算好落进快照,报告层引用即合法——防编造纪律不放松,
分析密度回来。每一项都必须能由快照原始值复算。
"""
import math

from . import util

SCHEMA_VERSION = 1
RANGE_DAYS = 5
POLICY_INDICATOR = "政策利率"
CPI_INDICATOR = "CPI 同比"


def _num(v):
    """数值门:bool 不是数(约定 2),NaN/Inf 穿过比较会给出确定性错误结论。"""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return v if math.isfinite(v) else None


def _entry_of(snap, currency):
    if not isinstance(snap, dict):
        return None
    rates = snap.get("rates")
    if not isinstance(rates, dict):
        return None
    entry = rates.get(currency)
    return entry if isinstance(entry, dict) else None


def _chg_pct_1d(entry):
    # 参考价未更新 → 两值必然相等,但那不是价格变动(非工作日),不得算 0%
    ref, prev_ref = entry.get("ref_date"), entry.get("prev_ref_date")
    if isinstance(ref, str) and ref == prev_ref:
        return None
    today, prev = _num(entry.get("primary")), _num(entry.get("prev_primary"))
    if today is None or prev is None or prev == 0:
        return None
    return round((today - prev) / prev * 100, 3)


def _range_nd(entry, history, currency):
    """近 N 个不同定盘日期的高低区间。同一 ref_date 的多份快照只算一次
    (回填会产生同日多份,不去重会把"一天"重复计入)。"""
    values, seen_refs = [], set()
    today = _num(entry.get("primary"))
    if today is not None:
        values.append(today)
        ref = entry.get("ref_date")
        seen_refs.add(ref if isinstance(ref, str) else None)
    for snap in history:
        if len(values) >= RANGE_DAYS:
            break
        h = _entry_of(snap, currency)
        if h is None:
            continue
        ref = h.get("ref_date")
        key = ref if isinstance(ref, str) else None
        if key is not None and key in seen_refs:
            continue
        v = _num(h.get("primary"))
        if v is None:
            continue
        values.append(v)
        seen_refs.add(key)
    if not values:
        return None, None, 0
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
            gaps.append(util.make_gap("derive", currency,
                                      "%s: %s" % (type(e).__name__, e)))
    return out


def _events_derived(payload, history, gaps):
    out = {}
    rates = payload.get("rates")
    currencies = list(rates) if isinstance(rates, dict) else []
    for currency in currencies:
        try:
            count = _article_count(payload, currency) or 0
            prev = _article_count(history[0], currency) if history else None
            out[currency] = {
                "count": count,
                "count_prev": prev,
                "count_delta": (count - prev) if prev is not None else None,
            }
        except Exception as e:
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
            policy, cpi = pair.get(POLICY_INDICATOR), pair.get(CPI_INDICATOR)
            if policy is None or cpi is None:
                continue
            pv, cv = _num(policy.get("value")), _num(cpi.get("value"))
            pp, cp = policy.get("period"), cpi.get("period")
            if pv is None or cv is None or not isinstance(pp, str) or not isinstance(cp, str):
                continue    # 任一缺失 → 整项不出,不给半截数据
            out[economy] = {"value": round(pv - cv, 3), "policy_rate": pv,
                            "policy_period": pp, "cpi": cv, "cpi_period": cp}
        except Exception as e:
            gaps.append(util.make_gap("derive", economy,
                                      "%s: %s" % (type(e).__name__, e)))
    return out


def derive(payload, history):
    """payload: 已组装的当日快照 dict;history: 按日期倒序的近若干份历史快照。"""
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
