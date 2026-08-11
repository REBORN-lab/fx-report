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

from scripts.collect.events import MAX_RECORDS as GDELT_DAILY_CAP
from scripts.collect.feeds import MAX_ITEMS as OFFICIAL_DAILY_CAP
from scripts.fixings import distinct_fixings, num as _num

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERDICTS = ["命中", "未命中", "无法判定", "未判定"]
SNAPSHOT_NAME_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
WEEK_RE = re.compile(r"\d{4}-W\d{2}")


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


def _rates_digest(snapshots, currencies):
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
        out[currency] = {
            "chg_pct_week": chg, "range_low": min(values), "range_high": max(values),
            "fixings": len(entries), "first_ref_date": first_ref,
            "last_ref_date": last_ref,
        }
    return out


def _pub_date(item):
    """RSS pubDate → YYYY-MM-DD。解析不了返回 None,绝不猜——猜错会把上个月的
    公告算进本周。"""
    raw = item.get("published") if isinstance(item, dict) else None
    if not isinstance(raw, str) or not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw)
    except (TypeError, ValueError, IndexError, OverflowError):
        return None
    if dt is None:      # 3.9 及更早版本对无法解析的串返回 None 而非抛错
        return None
    try:
        return dt.date().isoformat()
    except (AttributeError, ValueError, OverflowError):
        return None


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


def _events_one(snapshot_dates, snapshots, currency, lo, hi):
    arts_total = arts_distinct = arts_days = gdelt_failed = 0
    arts_capped = arts_assumed = 0
    arts_titles, arts_caps = set(), set()
    off_sampled = off_collected = off_nonempty = off_capped = off_assumed = 0
    in_window = outside = undated = 0
    off_seen, off_caps = set(), set()
    by_date = {}
    for date_, snap in zip(snapshot_dates, snapshots):
        events = snap.get("events")
        entry = events.get(currency) if isinstance(events, dict) else None
        arts = entry.get("articles") if isinstance(entry, dict) else None
        official = entry.get("official") if isinstance(entry, dict) else None
        day = {"articles": None, "official": None}
        if isinstance(arts, list):
            arts_total += len(arts)
            arts_days += 1
            day["articles"] = len(arts)
            for a in arts:
                title = a.get("title") if isinstance(a, dict) else None
                # GDELT 查询窗 48h、每日跑一次 → 相邻两天重叠约 24h,同一条
                # 新闻会被数两遍。按标题跨日去重;无标题者无从判重,各算一条
                if isinstance(title, str):
                    if title in arts_titles:
                        continue
                    arts_titles.add(title)
                arts_distinct += 1
            cap, assumed = _cap(snap, "gdelt_records", GDELT_DAILY_CAP)
            arts_caps.add(cap)
            arts_assumed += 1 if assumed else 0
            if len(arts) >= cap:
                arts_capped += 1
        else:
            gdelt_failed += 1
        if isinstance(official, list):
            off_collected += 1
            day["official"] = len(official)
            if official:
                off_nonempty += 1
                off_sampled += len(official)
                cap, assumed = _cap(snap, "official_daily", OFFICIAL_DAILY_CAP)
                off_caps.add(cap)
                off_assumed += 1 if assumed else 0
                if len(official) >= cap:
                    off_capped += 1
            for item in official:
                if not isinstance(item, dict):
                    continue
                key = (item.get("issuer"), item.get("title"), item.get("published"))
                try:
                    if key in off_seen:
                        continue    # 同一条公告连采数日,不得按天累加
                    off_seen.add(key)
                except TypeError:
                    pass            # 成员不可哈希 → 无从判重,各算一条
                pub = _pub_date(item)
                if pub is None:
                    undated += 1
                elif lo is not None and lo <= pub <= hi:
                    in_window += 1
                else:
                    # RSS 只给"最新 N 条",不按日期过滤:实测 2026-08-11 抓到的
                    # 三条 Fed 公告全部发布于 7 月。不分窗就会把它们当本周公告
                    outside += 1
        if isinstance(date_, str):
            by_date[date_] = day
    return {
        # 一天都没采到 → null:0 会被读成"确实没有新闻"
        "articles_total": arts_total if arts_days else None,
        "articles_distinct": arts_distinct if arts_days else None,
        "articles_capped_days": arts_capped,
        "articles_daily_cap": _one_cap(arts_caps),
        "articles_cap_assumed_days": arts_assumed,
        # 采到的原始条数;不是"本周公告数",两者差着日期过滤与跨日去重
        "official_sampled": off_sampled if off_collected else None,
        # 唯一可以当"本周公告数"引用的字段
        "official_in_window": in_window if off_collected else None,
        "official_outside_window": outside,
        "official_undated": undated,
        "official_capped_days": off_capped,
        "official_daily_cap": _one_cap(off_caps),
        "official_cap_assumed_days": off_assumed,
        "days_with_data": arts_days,
        "days_gdelt_failed": gdelt_failed,
        # 采到 ≠ 有内容:前者说管道通,后者说央行确实发了东西。混用会把
        # "央行本周没发公告"写成"我们没采到"
        "days_official_collected": off_collected,
        "days_with_official": off_nonempty,
        "days": len(snapshots),
        # 逐日交叉表:让"官方只在某日有、当日 GDELT 是否正常"成为可逐字引用的
        # 事实,而不是写报告时临时翻原始快照得出的、下次无法复现的结论
        "by_date": by_date,
    }


def _events_digest(snapshot_dates, snapshots, currencies, lo, hi):
    """两个通道分别计数:GDELT articles 与官方 RSS official 口径不同,
    合并会让计数不可比;而只数 articles 又会让"GDELT 挂了但 RSS 成功"
    被记成纯粹的采集失败,夸大停摆。"""
    return {c: _events_one(snapshot_dates, snapshots, c, lo, hi)
            for c in currencies}


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
        "rates": _rates_digest(good, currencies),
        "events": (_events_digest(dates, good, currencies,
                                  min(dates) if dates else None,
                                  max(dates) if dates else None)
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
