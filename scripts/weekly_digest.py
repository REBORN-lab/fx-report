#!/usr/bin/env python3
"""周度聚合器:脚本确定性算出跨日量,周报逐字引用。

存在理由:周报此前 85% 是日报重排——"本周涨了多少、区间多宽"没有任何脚本级
来源,只能由 LLM 从日报里捞,而 LLM 禁算。把这些量在这里算好落盘,周报引用
即合法(与日报引用快照 derived 同一模式),同时给校验器提供数字白名单。

缺输入一律写 null,不写 0:填 0 会被读成"确实是零",那是编造。
"""
import argparse
import glob
import json
import os
import re
import sys
from datetime import date
from email.utils import parsedate_to_datetime

if __package__ in (None, ""):   # 直接 `python3 scripts/weekly_digest.py` 时补 path
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.collect.events import GNEWS_SOFT_CAP, landed_count_capped
from scripts.collect.events import MAX_RECORDS as GDELT_DAILY_CAP
from scripts.collect.feeds import MAX_ITEMS as OFFICIAL_DAILY_CAP
from scripts.fixings import distinct_fixings, num as _num
from scripts.verdicts import join_verdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERDICTS = ["命中", "未命中", "无法判定", "未判定"]
SNAPSHOT_NAME_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
WEEK_RE = re.compile(r"\d{4}-W\d{2}")
SEEN_DATE_RE = re.compile(r"^(\d{4})(\d{2})(\d{2})T")


def _rate_entries(snapshots, currency):
    """按日期顺序取该币种的 (ref_date, primary),同一次定盘只留首次出现。
    去重判定与采集层共用 scripts/fixings —— 曾因两份复制而漂移(见该模块注释)。"""
    obs = []
    for snap in snapshots:
        rates = snap.get("rates")
        if not isinstance(rates, dict):
            continue
        entry = rates.get(currency)
        if not isinstance(entry, dict):
            continue
        value = _num(entry.get("primary"))
        if value is None:
            continue
        ref = entry.get("ref_date")
        obs.append((ref if isinstance(ref, str) else None, value))
    return distinct_fixings(obs)


def _fixings_verdict(n, unknown_ref, first_ref, last_ref, missing_days, window_days,
                     skipped):
    """定盘次数是**下界**,不是计数:distinct_fixings 在定盘日未知时按同值合并,
    其 docstring 明说"只可能低估定盘次数"。周报写"全周仅 N 次定盘"就是把脚本
    刻意保守的下界讲成了市场事实(第六轮 C13)。区间同理——它是被观测到的那些
    价位的高低,不是区间内的真实极值。"""
    caveats = []
    if unknown_ref:
        caveats.append("%d 次观测的定盘日未记录" % unknown_ref)
    if missing_days:
        caveats.append("%d/%d 天未采到" % (missing_days, window_days))
    if skipped:
        caveats.append("另有 %d 份快照损坏被跳过" % skipped)
    if caveats:
        # 只把 head(caveats) 这一段交给拼装口;分号后那句是本函数自己的尾巴
        return (join_verdict("区间内观测到 %d 个不同价位,实际定盘次数只多不少" % n,
                             caveats)
                + ";周区间是这些价位的高低,不是区间内的真实极值")
    return "区间内 %d 次不同定盘(%s 至 %s)" % (n, first_ref, last_ref)


def _rates_digest(snapshots, currencies, window_days, skipped):
    out = {}
    for currency in currencies:
        entries = _rate_entries(snapshots, currency)
        if not entries:
            continue
        values = [v for _, v in entries]
        first_ref, first_v = entries[0]
        last_ref, last_v = entries[-1]
        # 全周只有一次定盘 → 没有新价格,不得算 0%
        chg = None
        if len(entries) >= 2 and first_v != 0:
            chg = round((last_v - first_v) / first_v * 100, 3)
        observed = sum(1 for snap in snapshots
                       if isinstance(snap.get("rates"), dict)
                       and isinstance(snap["rates"].get(currency), dict)
                       and _num(snap["rates"][currency].get("primary")) is not None)
        missing = (window_days - observed) if window_days is not None else None
        out[currency] = {
            "chg_pct_week": chg, "range_low": min(values), "range_high": max(values),
            "fixings": len(entries), "first_ref_date": first_ref,
            "last_ref_date": last_ref, "days_observed": observed,
            "fixings_verdict": _fixings_verdict(
                len(entries), sum(1 for r, _ in entries if not isinstance(r, str)),
                first_ref, last_ref,
                missing if (missing and missing > 0) else 0,
                window_days, skipped),
        }
    return out


def _pub_date(item):
    """RSS pubDate → YYYY-MM-DD。解析不了返回 None,绝不猜——猜错会把上个月的
    公告算进本周。

    取的是**条目自带时区**的本地日期(ECB 写 +0200 就按柏林日历),而窗口两端来自
    快照文件名(UTC 日)。跨零点几小时发布的公告因此可能落到相邻一天;不统一折算成
    UTC,是因为「央行哪天发的公告」在读者心里就是发行方本地的那一天。
    """
    raw = item.get("published")
    if not isinstance(raw, str) or not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw)
    except (AttributeError, TypeError, ValueError, IndexError, OverflowError):
        return None
    if dt is None:      # 3.9 及更早对无法解析的串返回 None 而非抛错
        return None
    try:
        return dt.date().isoformat()
    except (AttributeError, ValueError, OverflowError):
        return None


def _seen_date(item):
    """GDELT seendate(20260809T120000Z)→ YYYY-MM-DD。解析不了返回 None。"""
    raw = item.get("seendate")
    if not isinstance(raw, str):
        return None
    m = SEEN_DATE_RE.match(raw)
    if m is None:
        return None
    try:
        return date(*(int(g) for g in m.groups())).isoformat()
    except (TypeError, ValueError, OverflowError):
        return None


def _official_key(item):
    """同一条公告的身份。不含 pubDate:RSS 改一次时间戳渲染就会让同一条
    公告变成两条,而 (发行方, 标题) 在一周内重复的概率远低于这个。"""
    return (item.get("issuer"), item.get("title"))


def _article_key(item):
    """同一条新闻的身份。多家媒体同标题转述视为同一条(这正是我们想合并的);
    标题缺失时退回 url。"""
    title = item.get("title")
    return ("t", title) if isinstance(title, str) else ("u", item.get("url"))


def _cap(snap, key, fallback):
    """当日采集上限。优先读快照 meta.caps(采集当时的真值);缺失则按当前代码
    常量推定并告知调用方——上限一旦改动,拿新常量去判旧快照会静默错判触顶。
    返回 (cap, assumed)。"""
    meta = snap.get("meta")
    caps = meta.get("caps") if isinstance(meta, dict) else None
    value = caps.get(key) if isinstance(caps, dict) else None
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value, False
    return fallback, True


def _one_cap(caps):
    """全周上限一致才给单值;不一致(期间改过上限)给 null,不取任一个充数。"""
    return next(iter(caps)) if len(caps) == 1 else None


def _cap_phrase(cap):
    """上限的中文括注。cap 为 None = 区间内上限不唯一,此时**不给数值** ——
    直接插值会把字面量 None 印进结论句。"""
    return ("(%s 条)" % cap) if cap is not None else "(区间内上限随通道不同,不给单值)"


def _channel(observations, cap_key, cap_fallback, date_of, key_of, lo, hi):
    """一个事件通道的跨日统计。两个通道**共用这一份实现** —— official 与 GDELT
    曾各写一份,于是 official 有截断披露而 GDELT 没有(第三轮 I10);同一个
    change 里已经因为"复制粘贴判定逻辑"栽过一次(见 scripts/fixings.py)。

    observations: [(snap, items | None, raw_count | None, entry | None)] 按日期序;
    entry 是该币种的快照条目,用于读取采集层算好的 source_capped/source_cap;
    items 为 None
    表示当日该通道无数据(采集失败,或该币种压根没接这个通道)。raw_count 是采集层
    去重**之前**的条数——GDELT 落盘前已按标题去重,只看 len(items) 会把
    "取满 8 条、其中 2 条重复"读成"只有 6 条,没触顶",漏报截断。

    三个量必须分开,混用就是本 change 反复出现的那个失败模式:
    - sampled:采到几条。上限截断过、跨日重复过、含窗口外的旧条目 —— 管道读数
    - distinct:跨日去重后几条。仍含窗口外的旧条目
    - in_window:去重且发布日落在覆盖区间内。唯一能当"本周发生了几件事"读的量

    返回 (stats, per_day, published_by_date)。
    """
    sampled = distinct = in_win = outside = undated = malformed = 0
    filtered_days = filtered_items = filtered_blank_days = 0
    malformed_days = malformed_items = malformed_unknown_days = 0
    days_collected = days_nonempty = capped = assumed = 0
    sample_capped = sample_assumed = main_failed_days = 0
    seen, caps, capped_caps, sample_caps = set(), set(), set(), set()
    per_day, published_by_date = [], {}
    for snap, items, raw_count, entry in observations:
        if items is None:
            per_day.append((False, None))
            continue
        days_collected += 1
        sampled += len(items)
        per_day.append((True, len(items)))
        # 源侧闸门滤掉的条次。判据是 raw - kept,对**每个两数皆知的日子**成立。
        #
        # 第二轮写的是 `raw > 0 且 kept == 0`,只在整日归零时才响;真实数据里
        # 绝大多数天 kept > 0,于是整层滤除量退出了结论判定 —— 实测
        # data/2026-08-12.json 的 BRL(raw=34、offlist=29、kept=5)由"无法判定"
        # 翻成"确实 0 条"。同一个错误第四次:不变量陈述在了太窄的定义域上。
        gf = entry.get("gnews_filter") if isinstance(entry, dict) else None
        # 主通道**跑了但没跑成**:键在、值为 None。此前整条绕过不变量 ——
        # 单调性因此被违反:主通道跑成了、抓到 20 条全被挡掉 → "有无事件无法
        # 判定";主通道整条跑失败(信息严格更少)→ "确实 0 条、全区间采集完整"。
        # 判据必须是"键在且值为 None"而不是"值不是 dict":README 写明的整通道
        # 回滚(删掉白名单文件)下这个键根本不存在,那是有意停用、不是缺口
        if isinstance(entry, dict) and "gnews_filter" in entry and gf is None:
            main_failed_days += 1
        lost = 0
        if isinstance(gf, dict):
            n_raw, n_kept = gf.get("raw"), gf.get("kept")
            if (isinstance(n_raw, int) and not isinstance(n_raw, bool)
                    and isinstance(n_kept, int) and not isinstance(n_kept, bool)
                    and n_raw > n_kept):
                lost = n_raw - n_kept
        if lost:
            filtered_days += 1
            filtered_items += lost
            if not items:
                # 当日最终一条可用条目都没有。与"补位补上了"必须分开措辞:
                # 后者写"无一可用"会和同句的"区间内至少 N 条"自相矛盾
                filtered_blank_days += 1
        # 采集层跳过的"结构不可识别"元素。源改版成 {"articles": ["<a>", ...]}
        # 时逐个被跳过,落盘 articles=[] 而 raw_count=3、gaps 为空 —— 与"确实
        # 一条都没有"完全同形,聚合器据此断言"确实 0 条、全区间采集完整"
        bad = entry.get("articles_dropped_malformed") if isinstance(entry, dict) else None
        if isinstance(bad, int) and not isinstance(bad, bool):
            if bad > 0:
                malformed_days += 1
                malformed_items += bad
        elif isinstance(entry, dict):
            # 本 change 之前落的快照没有这本账 —— 那几天**不知道**有没有被跳过的
            # 元素,不是知道没有。当成 0 会让上面那条不变量在全部存量快照上失效
            # (仓库里 6 份真实快照实测无一带此键)。official 那一路 entry 为 None,
            # 它没有这条路径,不受影响
            malformed_unknown_days += 1
        # 截断是"源返回了多少条"的属性,与最终留下几条无关 —— 这段必须在
        # `if items:` 之外,否则滤空的日子会一边 derive 说触顶、一边周报说无截断。
        # **count_at_cap 才是"落盘条数被上限钉住"**:gnews 的 source_capped 说的
        # 是滤除前样本触顶(raw=100>=99),而落盘的是滤后的 11 条,拿它当"顶到
        # 当日采集上限"会把 11 条说成撞了 99 的上限(第四轮 S2/S3/S4)
        meta = snap.get("meta") if isinstance(snap, dict) else None
        # 判定与 derive 共用 events.landed_count_capped —— 两处各写一遍必然漂移
        flag = landed_count_capped(
            entry, meta.get("caps") if isinstance(meta, dict) else None)
        own_cap = entry.get("source_cap") if isinstance(entry, dict) else None
        # 两个集合分工:caps 是**区间内出现过的采集上限**(daily_cap 字段的含义,
        # 不因某天没触顶而缺席);capped_caps 只收**真触顶那些天**的上限,专供结论
        # 句。混用会让未触顶日的上限稀释掉触顶日的 —— 实测真实 W33 里 USD/EUR/PHP
        # 的触顶日全是上限 8 的 GDELT 日,却因为 08-12 那个没触顶的 gnews 日
        # (上限 99)混进来,结论句把已知的 8 印成"上限随通道不同,不给单值"
        # (第五轮 S4/S8)。assumed 照旧对每个**依赖了推定上限去判断**的日子计数:
        # 没触顶的日子同样是拿那个推定值判出来的,推错了就会漏报触顶
        if isinstance(flag, bool):
            if (isinstance(own_cap, int) and not isinstance(own_cap, bool)
                    and own_cap > 0):
                caps.add(own_cap)          # 条目自带上限即权威值
                if flag:
                    capped_caps.add(own_cap)
            else:
                cap, was_assumed = _cap(snap, cap_key, cap_fallback)
                caps.add(cap)
                assumed += 1 if was_assumed else 0
                if flag:
                    capped_caps.add(cap)
            capped += 1 if flag else 0
        else:
            # 条目缺席(official 那一路)或无从判断。判据不能门在 `items` 上:
            # GDELT 返回 8 个畸形元素时落盘是 articles=[] 而 raw_count=8,
            # 门在 items 上会让 derive 说触顶、周报说无截断
            n = raw_count if raw_count is not None else (len(items) if items else None)
            if n is not None:
                cap, was_assumed = _cap(snap, cap_key, cap_fallback)
                caps.add(cap)
                assumed += 1 if was_assumed else 0
                if n >= cap:
                    capped_caps.add(cap)
                    capped += 1
        # **原始样本触顶**是另一件事:它说"被滤除/未取回的条数是下界",与落盘
        # 几条无关。两条通道各有各的上限,哪一条真的触顶就记哪一条的上限;两条
        # 都触顶时集合有两个值,_one_cap 自然给 None(不给单值)。
        #
        # 用集合而不是计数器累加:纯 gnews 日 entry.source_capped 与
        # gnews_filter.capped 由**同一个** raw >= 99 算出,分别 +1 会把同一次
        # 截断记两遍,结论句于是把一件事说两遍(第四轮 S2/S4)
        # 两个来源必须**各判各的**。第五轮写成"任一为真且 flag 不为 True",
        # 于是补位日(GDELT 取满 8 条 → flag 为 True,而主通道 raw≥99 是另一次
        # 完全独立的截断)整条被吞掉,sample_capped_days 由 7 写成 0,滤除条次
        # 从下界变成了精确值(第六轮 Critical)。
        today_caps = set()
        sample_now = False
        own_flag = entry.get("source_capped") if isinstance(entry, dict) else None
        if own_flag is True and flag is not True:
            # 条目自身的截断,且没被上面那条 caveat 披露过。不过滤的通道上
            # source_capped 与 count_at_cap 由同一个 raw>=cap 算出,不加这个
            # 条件会把同一次截断说两遍(第五轮 S2/S6)
            sample_now = True
            if (isinstance(own_cap, int) and not isinstance(own_cap, bool)
                    and own_cap > 0):
                today_caps.add(own_cap)
        if isinstance(gf, dict) and gf.get("capped") is True:
            # 主通道那次截断**独立成立**:它说的是滤除前的样本,与补位通道
            # 自己有没有取满毫无关系,不能被 flag 吞掉
            sample_now = True
            mcap, m_assumed = _cap(snap, "gnews_records", GNEWS_SOFT_CAP)
            today_caps.add(mcap)
            # 主通道上限的推定单列:并进 cap_assumed_days 会给权威的条目级上限
            # 贴上"上限为推定"的假标注,且让一个"天数"超过它统计的天数
            sample_assumed += 1 if m_assumed else 0
        if sample_now:
            sample_capped += 1
            sample_caps |= today_caps
        if items:
            days_nonempty += 1
        for item in items:
            if not isinstance(item, dict):
                # 看到过、却既进不了窗口账也进不了 undated。此前只是 continue,
                # 于是它们被 sampled 计入、被 dup_dropped 说成"去重掉的重复"
                # (周报 SKILL 让报告直接引这个数),而结论照旧"确实 0 条"
                malformed += 1
                continue
            try:
                key = key_of(item)
                if key in seen:
                    continue        # 同一条连采数日,不得按天累加
                seen.add(key)
            except TypeError:
                pass                # 成员不可哈希 → 无从判重,各算一条
            distinct += 1
            when = date_of(item)
            if when is None:
                # 时间戳缺失或改版:既不是"窗内"也不是"窗外",必须单列。
                # 并进任何一边都会让 in_window 变成一个不能读的数
                undated += 1
            elif lo is not None and lo <= when <= hi:
                in_win += 1
                published_by_date[when] = published_by_date.get(when, 0) + 1
            else:
                # RSS/GDELT 都只给"最新 N 条"、不按日期过滤:实测 2026-08-11
                # 抓到的三条 Fed 公告全部发布于 7 月
                outside += 1
    got = days_collected > 0
    stats = {
        # 一天都没采到 → null:0 会被读成"确实没有新闻"
        "sampled": sampled if got else None,
        "distinct": distinct if got else None,
        # 差值由脚本给出,报告不必自己减(LLM 禁算)。减去 malformed:结构不可
        # 识别的元素不是"重复",把丢弃量伪装成重复量会让报告写出假的去重叙述
        "dup_dropped": (sampled - malformed - distinct) if got else None,
        "in_window": in_win if got else None,
        "outside_window": outside if got else None,
        "undated": undated if got else None,
        "malformed": malformed if got else None,
        "capped_days": capped,
        # 结论句用触顶那些天的上限,daily_cap 仍是"区间内出现过的上限"
        "capped_cap": _one_cap(capped_caps),
        "sample_capped_days": sample_capped,
        "sample_daily_cap": _one_cap(sample_caps),
        "sample_cap_assumed_days": sample_assumed,
        "filtered_days": filtered_days,
        "filtered_items": filtered_items,
        "filtered_blank_days": filtered_blank_days,
        "malformed_days": malformed_days,
        "malformed_items": malformed_items,
        "malformed_unknown_days": malformed_unknown_days,
        "main_failed_days": main_failed_days,
        "daily_cap": _one_cap(caps),
        "cap_assumed_days": assumed,
        "days_collected": days_collected,
        "days_nonempty": days_nonempty,
    }
    return stats, per_day, published_by_date


def _window_days(lo, hi):
    """覆盖区间的**日历天数**。

    分母曾经取"载入到的快照份数"——某天根本没跑采集时,它同时缩小分子和分母,
    missing 恒为 0,于是脚本对一个从未被观测的日子说出"全区间采集完整"。
    不变量必须陈述在日历这个定义域上:分母是区间里有多少天,不是我们手上有几份。
    """
    if not (isinstance(lo, str) and isinstance(hi, str)):
        return None
    try:
        d0, d1 = date.fromisoformat(lo), date.fromisoformat(hi)
    except (TypeError, ValueError):
        return None
    return (d1 - d0).days + 1 if d1 >= d0 else None


def _verdict(stats, window_days, skipped, unit):
    """把「能不能下结论」从 LLM 手里收回脚本。

    前九次同型全部卡在同一步:报告拿着一堆计数自己推「有没有」。每加一条 prompt
    禁令,下一轮审查就找到一条绕过去的路径 —— undated 堵上了,采集覆盖没堵;
    覆盖堵上了,截断没堵。枚举补丁永远差一条,所以这里改成脚本给结论、报告
    逐字引用,与「脚本算好、LLM 逐字引用」的数字纪律同构。

    不变量:只有**全区间每天都采到、无截断、时间戳全部可解析**时,才允许说
    「确实 0 条」;任何一处观测缺口一律退化成「无法判定」。
    """
    if stats["days_collected"] == 0:
        return "未接入或全区间采集失败,有无%s无法判定" % unit
    caveats = []
    if window_days is None:
        caveats.append("覆盖区间不可知")
    else:
        missing = window_days - stats["days_collected"]
        if missing > 0:
            caveats.append("%d/%d 天未采到" % (missing, window_days))
    if skipped:
        # 损坏被跳过的快照,其日期不可知 —— 那几天同样没被观测
        caveats.append("另有 %d 份快照损坏被跳过" % skipped)
    if stats["undated"]:
        caveats.append("%d 条时间戳无法解析" % stats["undated"])
    if stats["capped_days"]:
        # daily_cap 为 None = 区间内上限不唯一(两条通道混用)。直接插值会把
        # 字面量 None 印进中文结论句
        caveats.append("%d 天顶到当日采集上限%s"
                       % (stats["capped_days"],
                          _cap_phrase(stats.get("capped_cap", stats["daily_cap"]))))
    if stats.get("sample_capped_days"):
        # 与上一条分开:触顶的是**滤除前的原始样本**,上限是它自己的那个数。
        # 纯 gnews 日两者由同一个 raw>=99 算出,上面那条不会响,只出这一条
        caveats.append("%d 天源返回的原始样本顶到其上限%s,已采到的条数是下界"
                       % (stats["sample_capped_days"],
                          _cap_phrase(stats.get("sample_daily_cap"))))
    if stats.get("malformed_items"):
        caveats.append("%d 天共 %d 条次结构不可识别被跳过(源可能已改版)"
                       % (stats["malformed_days"], stats["malformed_items"]))
    if stats.get("main_failed_days"):
        caveats.append("%d 天主通道未跑成(补位通道的读数是下界)"
                       % stats["main_failed_days"])
    if stats.get("malformed_unknown_days"):
        caveats.append("%d 天的不可识别条数不可知(存量快照无此账)"
                       % stats["malformed_unknown_days"])
    if stats.get("malformed"):
        caveats.append("另有 %d 条次落盘后结构不可识别" % stats["malformed"])
    if stats.get("filtered_items"):
        # 说"条次"不说"条":同一批条目连采数日会被每天数一遍,700 条次可能
        # 只是 100 条新闻被数了 7 遍。落盘的是逐日计数,去重信息不存在
        n_days, n_items = stats["filtered_days"], stats["filtered_items"]
        blank = stats.get("filtered_blank_days") or 0
        if blank == n_days:
            caveats.append("%d 天抓到共 %d 条次但无一可用(窗口外/时间戳不可解析/"
                           "来源不可署名)" % (n_days, n_items))
        else:
            # 不能写"由补位通道取得条目":kept > 0 的日子条目来自主通道自己,
            # 补位压根没触发。这里只陈述能从账上读出来的事 —— 当日仍有条目
            caveats.append("%d 天主通道抓到共 %d 条次未通过逐层过滤(其中 %d 天"
                           "当日仍有条目可用)" % (n_days, n_items, n_days - blank))
    if stats["outside_window"]:
        # 采到了、却一条都放不进区间 —— 这不是"区间内确实没有",是我们压根
        # 没观测到区间内那几天。实测 data/2026-08-12.json 的 BRL:5 条真实条目
        # 发布日全是 08-10/08-11,窗口是 08-12,六条 caveat 一条不响,直接断言
        # "确实 0 条、全区间采集完整"。判据陈述在 _channel 自己的窗口账上,
        # 纯 GDELT 条目(根本没有 gnews_filter)同样被覆盖
        caveats.append("另有 %d 条发布于区间外" % stats["outside_window"])
    if stats["in_window"]:
        head = "区间内至少 %d 条" % stats["in_window"]
        return join_verdict(head, caveats)
    # 下面两条不是 head(caveats) 形态:caveat 嵌在句中/纯字面量,套拼装口会改输出
    if caveats:
        return "区间内未见%s,但 %s,有无%s无法判定" % (unit, "、".join(caveats), unit)
    return "区间内确实 0 条(全区间采集完整、无截断、时间戳均可解析)"


def _events_one(snapshots, currency, lo, hi, skipped):
    art_obs, off_obs = [], []
    for snap in snapshots:
        events = snap.get("events")
        entry = events.get(currency) if isinstance(events, dict) else None
        arts = entry.get("articles") if isinstance(entry, dict) else None
        official = entry.get("official") if isinstance(entry, dict) else None
        raw = entry.get("articles_raw_count") if isinstance(entry, dict) else None
        if not (isinstance(raw, int) and not isinstance(raw, bool) and raw >= 0):
            raw = None
        art_obs.append((snap, arts if isinstance(arts, list) else None, raw,
                        entry if isinstance(entry, dict) else None))
        # official 落盘前不去重,采到几条就是几条;它没有 per-entry 上限字段
        off_obs.append((snap, official if isinstance(official, list) else None,
                        None, None))
    a, a_days, a_pub = _channel(art_obs, "gdelt_records", GDELT_DAILY_CAP,
                                _seen_date, _article_key, lo, hi)
    o, o_days, o_pub = _channel(off_obs, "official_daily", OFFICIAL_DAILY_CAP,
                                _pub_date, _official_key, lo, hi)
    by_date, fallback_days = {}, 0
    for i, snap in enumerate(snapshots):
        date_ = snap.get("date")
        if not isinstance(date_, str):
            continue
        a_ok, a_n = a_days[i]
        o_ok, o_n = o_days[i]
        if not a_ok and o_ok and o_n:
            # 兜底是**管道属性**:当日 GDELT 没采到,而官方通道当日采到了东西。
            # 它与那些公告的发布日无关 —— 一条发布于 08-07 的公告要到 08-11
            # 才被采到,08-07 当天并没有任何兜底发生
            fallback_days += 1
        by_date[date_] = {
            # 管道读数:当日采到没有、采到几条
            "gdelt_collected": a_ok, "articles_sampled": a_n,
            "official_collected": o_ok, "official_sampled": o_n,
            # 已采到的、发布日/采见日为当天的去重条数。**是下界,不是当日总数**:
            # 没采的那些天可能还有;采了的那天也可能被上限截断。通道整个没采到
            # 时写 null —— 写 0 会和"确实没有"混为一谈
            "articles_seen": a_pub.get(date_, 0) if a["days_collected"] else None,
            "official_published": (o_pub.get(date_, 0)
                                   if o["days_collected"] else None),
        }
    return {
        # 唯一可以用来陈述"有没有、有几条"的字段。脚本已把观测缺口(未采到的
        # 天数、截断、无法解析的时间戳)折进结论,报告逐字引用即可,禁止自行推断
        "articles_verdict": _verdict(a, _window_days(lo, hi), skipped, "事件"),
        "official_verdict": _verdict(o, _window_days(lo, hi), skipped, "公告"),
        "fallback_days": fallback_days,
        "articles_sampled": a["sampled"], "articles_distinct": a["distinct"],
        "articles_dup_dropped": a["dup_dropped"],
        "articles_in_window": a["in_window"],
        "articles_outside_window": a["outside_window"],
        "articles_undated": a["undated"],
        "articles_capped_days": a["capped_days"],
        "articles_daily_cap": a["daily_cap"],
        "articles_cap_assumed_days": a["cap_assumed_days"],
        # 原始样本触顶的账:上限与条目级那份不同(99 / 8),压成一个数就会
        # 印出"顶到当日采集上限(8 条)"而当天只采到 3 条
        "articles_sample_capped_days": a["sample_capped_days"],
        "articles_sample_daily_cap": a["sample_daily_cap"],
        "articles_sample_cap_assumed_days": a["sample_cap_assumed_days"],
        # 结构不可识别被跳过的条次:采集层跳过的 + 落盘后仍不可识别的
        "articles_malformed_dropped": a["malformed_items"],
        "articles_malformed_unknown_days": a["malformed_unknown_days"],
        "articles_main_failed_days": a["main_failed_days"],
        "articles_malformed_items": a["malformed"],
        # 源侧闸门逐层滤除的条次(raw - kept 逐日累加)。整日归零的天数单列:
        # 补位成功的日子不能写"无一可用"
        "articles_filtered_days": a["filtered_days"],
        "articles_filtered_items": a["filtered_items"],
        "articles_filtered_blank_days": a["filtered_blank_days"],
        "days_with_data": a["days_collected"],
        "days_gdelt_failed": (_window_days(lo, hi) or len(snapshots))
                             - a["days_collected"],
        "official_sampled": o["sampled"], "official_distinct": o["distinct"],
        "official_dup_dropped": o["dup_dropped"],
        "official_in_window": o["in_window"],
        "official_outside_window": o["outside_window"],
        "official_undated": o["undated"],
        "official_capped_days": o["capped_days"],
        "official_daily_cap": o["daily_cap"],
        "official_cap_assumed_days": o["cap_assumed_days"],
        # 采到 ≠ 有内容:前者说管道通,后者说发布方确实发了东西。混用会把
        # "央行本周没发公告"这个市场事实伪装成管道故障
        "days_official_collected": o["days_collected"],
        "days_with_official": o["days_nonempty"],
        # 区间日历天数(分母);载入到的快照份数另记,两者不等就意味着有整天缺采
        "days": _window_days(lo, hi) or len(snapshots),
        "snapshots_loaded": len(snapshots),
        # 逐日交叉表:让"哪天 GDELT 失败、哪天真有公告发布"成为可逐字引用的
        # 事实,而不是写报告时翻原始快照得出的、下次无法复现的结论
        "by_date": by_date,
    }


def _events_digest(snapshots, currencies, lo, hi, skipped):
    """两个通道分别计数:GDELT articles 与官方 RSS official 口径不同,
    合并会让计数不可比;而只数 articles 又会让"GDELT 挂了但 RSS 成功"
    被记成纯粹的采集失败,夸大停摆。"""
    return {c: _events_one(snapshots, c, lo, hi, skipped) for c in currencies}


def _gaps_by_source(snapshots):
    out = {}
    for snap in snapshots:
        gaps = snap.get("gaps")
        if not isinstance(gaps, list):
            continue
        for g in gaps:
            if not isinstance(g, dict):
                continue
            source = g.get("source")
            if isinstance(source, str) and source:
                out[source] = out.get(source, 0) + 1
    return out


def _verdict_details(log_entries, dates):
    """明细行的脚本来源:删掉 stats 后若不提供,周报的逐条明细将无出处。"""
    if not dates:
        return []
    lo, hi = min(dates), max(dates)
    out = []
    for e in log_entries:
        if not isinstance(e, dict):
            continue
        date_, currency = e.get("date"), e.get("currency")
        if not isinstance(date_, str) or not (lo <= date_ <= hi):
            continue
        review = e.get("review")
        verdict = review.get("verdict") if isinstance(review, dict) else None
        out.append({"date": date_,
                    "currency": currency if isinstance(currency, str) else None,
                    "verdict": verdict if isinstance(verdict, str) and verdict in VERDICTS
                    else "未判定"})
    return sorted(out, key=lambda r: (r["date"], r["currency"] or ""))


def _verdicts(log_entries, dates):
    """按覆盖区间(首末快照日期之间)过滤,而非按快照日期精确匹配——
    某天没跑采集不代表那天没有观点,精确匹配会让这些记录静默消失。"""
    counts = {v: 0 for v in VERDICTS}
    if not dates:
        return counts
    lo, hi = min(dates), max(dates)
    for e in log_entries:
        if not isinstance(e, dict):
            continue
        date = e.get("date")
        if not isinstance(date, str) or not (lo <= date <= hi):
            continue
        review = e.get("review")
        verdict = review.get("verdict") if isinstance(review, dict) else None
        # 可哈希门 + 词表白名单:外部日志可能是 list(unhashable → TypeError)
        # 或表外字符串(会凭空多出一个 JSON 键)。与 log_decision.py 同规格。
        key = verdict if isinstance(verdict, str) and verdict in counts else "未判定"
        counts[key] += 1
    return counts


def build(snapshots, log_entries, week, currencies=("USD", "EUR", "PHP", "THB", "BRL")):
    """纯函数:snapshots 快照 list(内部按 date 排序);log_entries 为 None
    表示决策日志不可用(与"日志为空"区分)。返回 (digest, problems)。"""
    good, problems = [], []
    for s in snapshots:
        if not isinstance(s, dict):
            problems.append("skipped non-dict snapshot: %s" % type(s).__name__)
        elif not isinstance(s.get("date"), str):
            # 无日期的快照排序键会退化成空串、排到所有真实日期之前,
            # 成为"周首价"——一个不存在的一天在驱动周涨跌。排除并记录。
            problems.append("skipped snapshot without str date: %r" % (s.get("date"),))
        else:
            good.append(s)
    skipped_snapshots = len(problems)
    # 首末取值依赖时间序;不能只靠调用方保证(main 的文件名序曾经就不是日期序)
    good.sort(key=lambda s: s.get("date") if isinstance(s.get("date"), str) else "")
    dates = [s.get("date") for s in good if isinstance(s.get("date"), str)]
    if log_entries is None:
        # 日志不可用 ≠ 本周没有观点:写 0 会让周报断言"复盘全 0"
        verdicts, verdict_details = None, None
        problems.append("decision log unavailable; verdicts recorded as null")
    else:
        entries = log_entries if isinstance(log_entries, list) else []
        verdicts = _verdicts(entries, dates)
        verdict_details = _verdict_details(entries, dates)
    digest = {
        "week": week,
        "generated_from": dates,
        "skipped": skipped_snapshots,
        "rates": _rates_digest(good, currencies,
                               _window_days(min(dates), max(dates))
                               if dates else None, skipped_snapshots),
        "window_from": min(dates) if dates else None,
        "window_to": max(dates) if dates else None,
        "events": (_events_digest(good, currencies,
                                  min(dates) if dates else None,
                                  max(dates) if dates else None,
                                  skipped_snapshots)
                   if good else {}),
        "gaps_by_source": _gaps_by_source(good),
        "verdicts": verdicts,
        "verdict_details": verdict_details,
    }
    return digest, problems


def _load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError, RecursionError):
        return None


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python3 scripts/weekly_digest.py")
    ap.add_argument("--week", required=True, help="ISO 周号,如 2026-W33")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--root", default=ROOT)
    args = ap.parse_args(argv)
    if not WEEK_RE.fullmatch(args.week):
        ap.error("--week 需形如 YYYY-Www(如 2026-W33)")
    if args.days < 1:
        ap.error("--days 需为正整数")
    data_dir = os.path.join(args.root, "data")
    today = date.today().isoformat()
    names = []
    for path in glob.glob(os.path.join(data_dir, "*.json")):
        name = os.path.basename(path)[:-len(".json")]
        # 误放的非快照文件不得进入窗口(字典序会让 zz-*.json 冒充"最新一天");
        # 未来日期同样排除
        if SNAPSHOT_NAME_RE.fullmatch(name) and name <= today:
            names.append(name)
    selected = sorted(names)[-args.days:]
    snapshots = [_load_json(os.path.join(data_dir, n + ".json")) for n in selected]
    log_path = os.path.join(args.root, "state", "decision-log.jsonl")
    entries = None
    if os.path.exists(log_path):
        entries = []
        try:
            with open(log_path, encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        entries.append(json.loads(line))
                    except (ValueError, RecursionError):
                        continue
        except (OSError, UnicodeDecodeError):
            entries = None
    digest, problems = build(snapshots, entries, args.week)
    out_dir = os.path.join(args.root, "state")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "weekly-digest-%s.json" % args.week)
    with open(out_path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(digest, f, ensure_ascii=False, indent=2)
    os.replace(out_path + ".tmp", out_path)
    print("digest: %s" % out_path)
    print("covered: %d 份(%s)" % (len(digest["generated_from"]),
                                  ", ".join(digest["generated_from"]) or "无"))
    for p in problems:
        print("  - %s" % p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
