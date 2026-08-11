"""静态央行年历命中判定:标注昨日/今日议息等日历事件,valid_until 过期告警。"""
import json

from . import util


def collect(cfg):
    gaps, hits = [], []
    try:
        with open(cfg["calendar_path"], encoding="utf-8") as f:
            cal = json.load(f)
    except Exception as e:
        gaps.append(util.make_gap("calendar", "all", "%s: %s" % (type(e).__name__, e)))
        return hits, gaps
    # 仓库约定:外部数据每次成员访问前过 isinstance 门(JSON 顶层可为 list/标量/null)
    if not isinstance(cal, dict):
        gaps.append(util.make_gap(
            "calendar", "all",
            "unparseable calendar: expected object, got %s" % type(cal).__name__))
        return hits, gaps
    valid_until = cal.get("valid_until")
    if not isinstance(valid_until, str):
        # valid_until 缺失或非 str → 视为缺失:有效期不可确认,走过期告警路径;
        # isinstance 门先行,避免与 cfg["date"] 比较时 TypeError(硬契约)
        gaps.append(util.make_gap(
            "calendar", "all",
            "calendar valid_until missing or not a string (got %s), "
            "请按 README 年历维护说明更新" % type(valid_until).__name__))
    elif cfg["date"] > valid_until:
        gaps.append(util.make_gap(
            "calendar", "all",
            "calendar expired (valid_until=%s), 请按 README 年历维护说明更新"
            % valid_until))
    watch = {cfg["yesterday"], cfg["date"]}
    events = cal.get("events")
    if not isinstance(events, list):
        events = []  # events 非 list → 视为空
    for ev in events:
        if not isinstance(ev, dict):
            continue  # 元素非 dict → 跳过
        date = ev.get("date")
        if not isinstance(date, str) or date not in watch:
            continue  # date 非 str(含 unhashable)先拦,再做 set 成员判断
        bank, event = ev.get("bank"), ev.get("event")
        if not isinstance(bank, str) or not isinstance(event, str):
            continue  # 命中元素缺 bank/event(或非 str)→ 跳过
        hits.append({"date": date, "bank": bank, "event": event})
    return hits, gaps
