"""快照聚合主入口:python3 -m scripts.collect --date YYYY-MM-DD(默认今天,UTC)。
单源失败绝不中断;全部结果 + gaps 落盘 data/YYYY-MM-DD.json,退出码 0。"""
import argparse
import glob
import json
import os
import sys
from datetime import date, timedelta

from . import calendar as calendar_mod
from . import events, macro, rates, util

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
COLLECTOR_VERSION = "0.1.0"


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
        except (OSError, ValueError) as e:
            prev_gap = util.make_gap(
                "snapshot", "prev",
                "corrupt prev snapshot %s: %s: %s" % (yesterday, type(e).__name__, e))
    cals = sorted(glob.glob(os.path.join(root, "state", "calendar-*.json")))
    return {
        "date": date_str,
        "yesterday": yesterday,
        "backfill": date_str != date.today().isoformat(),
        "endpoints": endpoints,
        "indicators": indicators,
        "data_dir": data_dir,
        "calendar_path": cals[-1] if cals else os.path.join(root, "state", "calendar-2026.json"),
        "prev_snapshot": prev_snapshot,
        "prev_snapshot_gap": prev_gap,
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
    hits = call(calendar_mod, "calendar", [])
    snapshot = {
        "date": cfg["date"], "run_at": util.now_iso(), "schema_version": 1,
        "rates": rates_p, "macro": macro_p["indicators"], "events": events_p,
        "calendar_hits": hits, "gaps": gaps,
        "meta": {"collector_version": COLLECTOR_VERSION},
    }
    if macro_p.get("us_release_dates") is not None:
        snapshot["us_release_dates"] = macro_p["us_release_dates"]
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
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)
    print("snapshot: %s" % out_path)
    print("gaps: %d" % len(snapshot["gaps"]))
    for g in snapshot["gaps"]:
        print("  - [%s/%s] %s" % (g["source"], g["scope"], g["reason"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
