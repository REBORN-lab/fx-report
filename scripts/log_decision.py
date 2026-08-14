#!/usr/bin/env python3
"""决策日志唯一写入口(LLM 经此脚本代笔,禁止直接编辑 jsonl)。
add        : stdin 传 JSON 数组,校验后追加(review 三字段置 null)
set-review : 回填指定 date+currency 的 trigger_judgement 与 verdict
stats      : 按日期区间输出 命中/未命中/无法判定/未判定 计数与明细"""
import argparse
import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REQUIRED = ("date", "currency", "scenario", "trigger", "watch_direction")
VERDICTS = ("命中", "未命中", "无法判定")
EMPTY_REVIEW = {"direction_outcome": None, "trigger_judgement": None, "verdict": None}


def log_path(root):
    return os.path.join(root, "state", "decision-log.jsonl")


def load(root):
    """读回日志。jsonl 由本脚本独占写入,但文件可能被外部损坏:
    坏 JSON 行(含深嵌套 RecursionError)与非 dict 行跳过(容错路径)。"""
    p = log_path(root)
    if not os.path.exists(p):
        return []
    entries = []
    with open(p, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except (ValueError, RecursionError):
                continue
            if isinstance(obj, dict):
                entries.append(obj)
    return entries


def save(root, entries):
    p = log_path(root)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    os.replace(tmp, p)


def review_of(e):
    """e['review'] 的 isinstance 门: 非 dict(缺失/外部损坏为 None)返回 None。"""
    rev = e.get("review")
    return rev if isinstance(rev, dict) else None


def cmd_add(args):
    try:
        items = json.load(sys.stdin)
    except (ValueError, RecursionError) as e:
        print("stdin 不是合法 JSON: %s" % e, file=sys.stderr)
        return 2
    if not isinstance(items, list):
        print("需要 JSON 数组", file=sys.stderr)
        return 2
    for it in items:
        if not isinstance(it, dict):
            # 输入校验路径: 报错优于跳过
            print("数组元素须为对象,收到非 dict: %r" % (it,), file=sys.stderr)
            return 2
        missing = [k for k in REQUIRED if k not in it]
        if missing:
            print("缺字段 %s: %s" % (missing, it), file=sys.stderr)
            return 2
        for k in ("date", "currency", "scenario", "trigger"):
            # 输入校验路径: 非 str 值入库会令 set-review 永不匹配(argparse 恒 str)、
            # stats isinstance 门跳过 → 复盘能力静默丢失。报错优于跳过。
            if not isinstance(it[k], str):
                print("%s 须为字符串,收到: %r" % (k, it[k]), file=sys.stderr)
                return 2
        try:
            datetime.date.fromisoformat(it["date"])
        except ValueError:
            print("date 须为 ISO 格式(YYYY-MM-DD): %r" % it["date"], file=sys.stderr)
            return 2
        if it["watch_direction"] not in ("up", "down", None):
            print("watch_direction 须为 up/down/null: %s" % it, file=sys.stderr)
            return 2
        it["review"] = dict(EMPTY_REVIEW)
    entries = load(args.root)
    entries.extend(items)
    save(args.root, entries)
    print("appended %d entries" % len(items))
    return 0


def cmd_set_review(args):
    if args.verdict not in VERDICTS:
        print("verdict 须为 %s" % (VERDICTS,), file=sys.stderr)
        return 2
    entries = load(args.root)
    for e in entries:
        rev = review_of(e)
        verdict = rev.get("verdict") if rev is not None else None
        if (e.get("date") == args.date and e.get("currency") == args.currency
                and verdict is None):
            if rev is None:
                rev = dict(EMPTY_REVIEW)
                e["review"] = rev
            rev["trigger_judgement"] = args.judgement
            rev["verdict"] = args.verdict
            save(args.root, entries)
            print("review set: %s %s -> %s" % (args.date, args.currency, args.verdict))
            return 0
    print("未找到待复盘条目 %s/%s" % (args.date, args.currency), file=sys.stderr)
    return 2


def cmd_amend_trigger(args):
    """把已登记条目的 `trigger` 改成速览表「条件方向」那一格的原文。

    ---- 为什么要有它 ----
    `skills/fx-daily-report/SKILL.md:374` 写明日志由速览表整理而来:
    **表是源、日志是抄件**。改了表没回写时两者漂移,而
    `scripts/check_report.py` 的 `DECISION_TRIGGER_NOT_SOURCED` 会把它打红。
    既有三个子命令(add / set-review / stats)都改不了 trigger,而 SKILL
    第 373 行禁止直接编辑 jsonl —— 于是"回填"这条路此前根本不存在。

    ---- 非破坏:旧值搬进 `trigger_superseded` ----
    这些条目的 `review.trigger_judgement` 是对着**旧** trigger 写的,并且
    可能已经逐字发布在下游日报里(实测:reports/daily/2026-08-12.md 的复盘
    节原样引了 2026-08-11 五条判词)。直接覆盖会让那段判词失去它评判的对象。
    旧值留在条目里:契约修好,审计链也保住。
    **只写一次** —— 第二次改动时 `trigger_superseded` 仍是最初那一版,
    因为它记的是"判词当时在评判哪一句",不是"上次改之前是什么"。

    `review` 一个字都不改:那是当时做出的判断,事后重写等于伪造记录。
    """
    entries = load(args.root)
    for e in entries:
        if e.get("date") == args.date and e.get("currency") == args.currency:
            old = e.get("trigger")
            if old == args.trigger:
                print("trigger 已是该值,未改动: %s %s"
                      % (args.date, args.currency))
                return 0
            if "trigger_superseded" not in e and isinstance(old, str):
                e["trigger_superseded"] = old
            e["trigger"] = args.trigger
            save(args.root, entries)
            print("trigger amended: %s %s" % (args.date, args.currency))
            return 0
    # 找不到就报错,不静默 no-op:静默成功的回填与"从来没跑过"不可分辨,
    # 而调用方会以为契约已经修好了
    print("未找到条目 %s/%s" % (args.date, args.currency), file=sys.stderr)
    return 2


def cmd_stats(args):
    counts = {"命中": 0, "未命中": 0, "无法判定": 0, "未判定": 0}
    detail = []
    for e in load(args.root):
        d = e.get("date")
        if not isinstance(d, str):
            continue
        if args.date_from <= d <= args.date_to:
            rev = review_of(e)
            v = rev.get("verdict") if rev is not None else None
            # 可哈希门: dict/list 等 unhashable verdict 做 `in counts` 会 TypeError
            key = v if isinstance(v, str) and v in counts else "未判定"
            counts[key] += 1
            detail.append("  - %s %s %s" % (d, e.get("currency"), v or "未判定"))
    print("命中 %(命中)d / 未命中 %(未命中)d / 无法判定 %(无法判定)d / 未判定 %(未判定)d"
          % counts)
    for line in detail:
        print(line)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("add")
    p.add_argument("--root", default=ROOT)
    p.set_defaults(fn=cmd_add)
    p = sub.add_parser("set-review")
    p.add_argument("--date", required=True)
    p.add_argument("--currency", required=True)
    p.add_argument("--judgement", required=True)
    p.add_argument("--verdict", required=True)
    p.add_argument("--root", default=ROOT)
    p.set_defaults(fn=cmd_set_review)
    p = sub.add_parser("amend-trigger")
    p.add_argument("--date", required=True)
    p.add_argument("--currency", required=True)
    p.add_argument("--trigger", required=True)
    p.add_argument("--root", default=ROOT)
    p.set_defaults(fn=cmd_amend_trigger)
    p = sub.add_parser("stats")
    p.add_argument("--from", dest="date_from", required=True)
    p.add_argument("--to", dest="date_to", required=True)
    p.add_argument("--root", default=ROOT)
    p.set_defaults(fn=cmd_stats)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
