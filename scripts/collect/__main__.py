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


def _latest_prior_path(data_dir, date_str):
    """早于 DATE 的**最近**一份快照路径;一份都没有时返回 None。

    这里刻意按**文件名**取最近的那一份、不跳过坏文件:坏文件被跳过、拿更旧的
    那一份当 prev,会把"损坏"伪装成"正常",与本函数存在的理由正相反。
    """
    best = None
    for path in glob.glob(os.path.join(data_dir, "*.json")):
        name = os.path.basename(path)[:-len(".json")]
        if not SNAPSHOT_NAME_RE.fullmatch(name):
            continue    # 误放的非快照文件不得冒充前一份快照
        if name >= date_str:
            continue    # 排除当日自身:重跑当天时它已存在
        if best is None or name > best[0]:
            best = (name, path)
    return best


def _prev_snapshot(data_dir, date_str, yesterday):
    """(前一份快照, gap)。前一份快照是外部持久化数据:损坏/不可读不该让当日
    采集崩掉(硬契约精神),置 None 继续并记一条 source="snapshot" 的 gap
    —— `prev_primary`/`is_new_release`/`source_changed_from` 会静默退化,
    不记 gap 则无从察觉。

    **取的是最近一份早于 DATE 的快照,不是严格的 DATE-1。** 严格取 DATE-1 时,
    日更只要断一天,这三个字段就一起失效而快照里毫无痕迹;2026-08-18 实际发生:
    上一份快照是 08-14,经常账户当天由 dbnomics 换到 imf(计价单位由百万美元
    变美元,PH 从 -4247 跳到 -5663843363),`source_changed_from` 一个都没打。

    它不是 DATE-1 时**出声**:比对基准不相邻,是读者判断"这两个数可不可比"
    的前提。一份都没有(首次运行)不出声 —— 那时没有可比对象,也不可能
    产生假比较,记 gap 只是噪音。
    """
    found = _latest_prior_path(data_dir, date_str)
    if found is None:
        return None, None
    name, path = found
    try:
        with open(path, encoding="utf-8") as f:
            snap = json.load(f)
    except (OSError, ValueError, RecursionError) as e:
        return None, util.make_gap(
            "snapshot", "prev",
            "corrupt prev snapshot %s: %s: %s" % (name, type(e).__name__, e))
    if not isinstance(snap, dict):
        # 合法 JSON 但顶层非 dict:同样属于"prev 退化",必须可见,不得静默
        return None, util.make_gap(
            "snapshot", "prev",
            "corrupt prev snapshot %s: top-level %s, expected dict"
            % (name, type(snap).__name__))
    if name != yesterday:
        return snap, util.make_gap(
            "snapshot", "prev",
            "前一份快照为 %s、非 %s:比对基准与本日不相邻,"
            "prev_primary / prev_ref_date / source_changed_from 均以 %s 为准"
            % (name, yesterday, name))
    return snap, None


def build_cfg(date_str, root=ROOT):
    with open(os.path.join(root, "config", "endpoints.json"), encoding="utf-8") as f:
        endpoints = json.load(f)
    with open(os.path.join(root, "config", "indicators.json"), encoding="utf-8") as f:
        indicators = json.load(f)
    d = date.fromisoformat(date_str)
    yesterday = (d - timedelta(days=1)).isoformat()
    data_dir = os.path.join(root, "data")
    prev_snapshot, prev_gap = _prev_snapshot(data_dir, date_str, yesterday)
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
