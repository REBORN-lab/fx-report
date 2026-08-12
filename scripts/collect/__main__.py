"""快照聚合主入口:python3 -m scripts.collect --date YYYY-MM-DD(默认今天,UTC)。
单源失败绝不中断;全部结果 + gaps 落盘 data/YYYY-MM-DD.json,退出码 0。"""
import argparse
import glob
import json
import os
import re
import sys
from datetime import date, timedelta

from . import calendar as calendar_mod
from . import derive as derive_mod
from . import events, feeds, macro, rates, util

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
COLLECTOR_VERSION = "0.1.0"


SNAPSHOT_NAME_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _load_history(data_dir, date_str, limit=derive_mod.HISTORY_SPAN):
    """派生指标要的近若干份历史快照,按日期倒序。坏文件跳过——历史缺失只让
    派生量降级(区间变窄),不值得为此中断当日采集。

    `name >= date_str` 同时排除当日自身:重跑当天时 data/<date>.json 已存在,
    放进来会让"前值"变成今早自己的产物(count_delta 恒 0)。"""
    out = []
    for path in sorted(glob.glob(os.path.join(data_dir, "*.json")), reverse=True):
        if len(out) >= limit:
            break
        name = os.path.basename(path)[:-len(".json")]
        if not SNAPSHOT_NAME_RE.fullmatch(name):
            continue    # 误放的非快照文件不得占用历史窗口
        if name >= date_str:
            continue
        try:
            with open(path, encoding="utf-8") as f:
                snap = json.load(f)
        except (OSError, ValueError, RecursionError):
            continue
        if isinstance(snap, dict):
            out.append(snap)
    return out


def build_cfg(date_str, root=ROOT):
    with open(os.path.join(root, "config", "endpoints.json"), encoding="utf-8") as f:
        endpoints = json.load(f)
    with open(os.path.join(root, "config", "indicators.json"), encoding="utf-8") as f:
        indicators = json.load(f)
    d = date.fromisoformat(date_str)
    yesterday = (d - timedelta(days=1)).isoformat()
    data_dir = os.path.join(root, "data")
    # 前日快照是外部持久化数据:损坏/不可读不该让当日采集崩掉(硬契约精神)。
    # 置 None 继续,并记一条 source="snapshot" 的 gap 让报告可见
    # (prev_primary/is_new_release 会静默退化,不记 gap 则无从察觉)。
    prev_snapshot, prev_gap = None, None
    prev_path = os.path.join(data_dir, yesterday + ".json")
    if os.path.exists(prev_path):
        try:
            with open(prev_path, encoding="utf-8") as f:
                prev_snapshot = json.load(f)
        except (OSError, ValueError, RecursionError) as e:
            prev_gap = util.make_gap(
                "snapshot", "prev",
                "corrupt prev snapshot %s: %s: %s" % (yesterday, type(e).__name__, e))
        else:
            # 合法 JSON 但顶层非 dict:同样属于"prev 退化",必须可见,不得静默
            if not isinstance(prev_snapshot, dict):
                prev_gap = util.make_gap(
                    "snapshot", "prev",
                    "corrupt prev snapshot %s: top-level %s, expected dict"
                    % (yesterday, type(prev_snapshot).__name__))
                prev_snapshot = None
    cals = sorted(glob.glob(os.path.join(root, "state", "calendar-*.json")))
    return {
        "date": date_str,
        "yesterday": yesterday,
        "backfill": date_str != date.today().isoformat(),
        "endpoints": endpoints,
        "indicators": indicators,
        "data_dir": data_dir,
        "calendar_path": cals[-1] if cals else os.path.join(root, "state", "calendar-2026.json"),
        # 白名单缺失 = 有意停用整个 gnews 通道(全部币种回落 GDELT),删掉即回滚
        "news_sources_path": os.path.join(root, "config", "news_sources.json"),
        "prev_snapshot": prev_snapshot,
        "prev_snapshot_gap": prev_gap,
        "history": _load_history(data_dir, date_str),
        "fred_api_key": os.environ.get("FRED_API_KEY"),
        # FX_GDELT_*_S 仅测试提速用;生产不设,落在 spec 要求的默认值上
        "gdelt_delay_s": float(os.environ.get("FX_GDELT_DELAY_S", events.DEFAULT_DELAY_S)),
        "gdelt_backoff_s": float(os.environ.get("FX_GDELT_BACKOFF_S", events.DEFAULT_BACKOFF_S)),
        "timeout_s": 20,
    }


def run(cfg):
    gaps = []
    if cfg.get("prev_snapshot_gap") is not None:
        gaps.append(cfg["prev_snapshot_gap"])

    def call(mod, name, default):
        try:
            payload, g = mod.collect(cfg)
            gaps.extend(g)
            return payload
        except Exception as e:  # 模块级兜底:绝不让一个源的意外中断其余源
            gaps.append(util.make_gap(name, "all",
                                      "internal error %s: %s" % (type(e).__name__, e)))
            return default

    rates_p = call(rates, "rates", {})
    macro_p = call(macro, "macro", {"indicators": [], "us_release_dates": None})
    events_p = call(events, "gdelt", {})
    # 官方公告并入同一币种命名空间:articles(GDELT)与 official(RSS)并列,
    # 来源可辨;GDELT 挂掉的币种也能有 official
    for currency, items in call(feeds, "feeds", {}).items():
        events_p.setdefault(currency, {})["official"] = items
    hits = call(calendar_mod, "calendar", [])
    snapshot = {
        "date": cfg["date"], "run_at": util.now_iso(), "schema_version": 1,
        "rates": rates_p, "macro": macro_p["indicators"], "events": events_p,
        "calendar_hits": hits, "gaps": gaps,
        # caps 随快照落盘:两个事件通道都按上限截断,不记下当时的上限,
        # 日后常量一改,聚合器拿新上限去判旧快照就会静默错判"是否触顶"
        "meta": {"collector_version": COLLECTOR_VERSION,
                 "caps": {"official_daily": feeds.MAX_ITEMS,
                          "gdelt_records": events.MAX_RECORDS,
                          "gnews_records": events.GNEWS_SOFT_CAP}},
    }
    if macro_p.get("us_release_dates") is not None:
        snapshot["us_release_dates"] = macro_p["us_release_dates"]
    # 派生在快照成型后算(输入是已落定的 rates/macro/events);同样绝不中断落盘
    try:
        derived, derive_gaps = derive_mod.derive(snapshot, cfg.get("history") or [])
        gaps.extend(derive_gaps)
        snapshot["derived"] = derived
    except Exception as e:
        gaps.append(util.make_gap("derive", "all",
                                  "internal error %s: %s" % (type(e).__name__, e)))
    return snapshot


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python3 -m scripts.collect")
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--root", default=ROOT, help=argparse.SUPPRESS)  # 测试注入用
    args = ap.parse_args(argv)
    cfg = build_cfg(args.date, args.root)
    snapshot = run(cfg)
    os.makedirs(cfg["data_dir"], exist_ok=True)
    out_path = os.path.join(cfg["data_dir"], args.date + ".json")
    # 原子落盘:先写 .tmp 再 os.replace,避免中途被杀留半个 JSON 给下游
    with open(out_path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)
    os.replace(out_path + ".tmp", out_path)
    print("snapshot: %s" % out_path)
    print("gaps: %d" % len(snapshot["gaps"]))
    for g in snapshot["gaps"]:
        print("  - [%s/%s] %s" % (g["source"], g["scope"], g["reason"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
