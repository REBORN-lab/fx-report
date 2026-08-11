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
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERDICTS = ["命中", "未命中", "无法判定", "未判定"]


def _num(v):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return v if math.isfinite(v) else None


def _fixing_key(ref, value):
    """一次定盘的身份;与 collect/derive.py 同法(ref 已知用 ref,未知按值)。"""
    return ("ref", ref) if isinstance(ref, str) else ("val", value)


def _rate_entries(snapshots, currency):
    """按日期顺序取该币种的 (ref_date, primary),同一次定盘只留首次出现。"""
    out, seen = [], set()
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
        key = _fixing_key(ref, value)
        if key in seen:
            continue
        seen.add(key)
        out.append((ref if isinstance(ref, str) else None, value))
    return out


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


def _events_digest(snapshots, currencies):
    out = {}
    for currency in currencies:
        total, with_data, failed = 0, 0, 0
        for snap in snapshots:
            events = snap.get("events")
            entry = events.get(currency) if isinstance(events, dict) else None
            arts = entry.get("articles") if isinstance(entry, dict) else None
            if isinstance(arts, list):
                total += len(arts)
                with_data += 1
            else:
                failed += 1
        out[currency] = {
            # 一天都没采到 → null:0 会被读成"确实没有新闻"
            "total": total if with_data else None,
            "days_with_data": with_data, "days_failed": failed,
        }
    return out


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
        counts["未判定" if verdict is None else verdict] = \
            counts.get("未判定" if verdict is None else verdict, 0) + 1
    return counts


def build(snapshots, log_entries, week, currencies=("USD", "EUR", "PHP", "THB", "BRL")):
    """纯函数:snapshots 按日期升序的快照 list;返回 (digest, problems)。"""
    good, problems = [], []
    for s in snapshots:
        if isinstance(s, dict):
            good.append(s)
        else:
            problems.append("skipped non-dict snapshot: %s" % type(s).__name__)
    dates = [s.get("date") for s in good if isinstance(s.get("date"), str)]
    entries = log_entries if isinstance(log_entries, list) else []
    digest = {
        "week": week,
        "generated_from": dates,
        "skipped": len(problems),
        "rates": _rates_digest(good, currencies),
        "events": _events_digest(good, currencies) if good else {},
        "gaps_by_source": _gaps_by_source(good),
        "verdicts": _verdicts(entries, dates),
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
    data_dir = os.path.join(args.root, "data")
    paths = sorted(glob.glob(os.path.join(data_dir, "*.json")))[-args.days:]
    snapshots = [_load_json(p) for p in paths]
    log_path = os.path.join(args.root, "state", "decision-log.jsonl")
    entries = []
    if os.path.exists(log_path):
        with open(log_path, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    entries.append(json.loads(line))
                except (ValueError, RecursionError):
                    continue
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
