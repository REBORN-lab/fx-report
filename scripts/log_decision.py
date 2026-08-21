#!/usr/bin/env python3
"""决策日志唯一写入口(LLM 经此脚本代笔,禁止直接编辑 jsonl)。

add            : stdin 传 JSON 数组,校验后追加(review 两字段置 null)
set-claim      : 给**已登记**条目补结构化观点 `claim`(stdin 传 JSON 对象)
amend-trigger  : 把已登记条目的散文 `trigger` 改成速览表那一格的原文
migrate-review : 旧 review 三字段整体搬进 `review_superseded`,新 review 清空
stats          : 按日期区间输出四档 + 未复盘的计数与明细

**这里没有、也不会再有写结论的入口。** `set-review` 已删除:结论只能由
`scripts/claims.resolve_claim` 给出、经 `scripts/review.py` 写回。本仓库
13 次同型缺陷的根因就是"prompt 禁令堵不住" —— 所以堵法是**让 LLM 没有语法
可以表达结论**,而不是再写一遍"你不得自撰结论词"。
"""
import argparse
import datetime
import json
import os
import sys

try:
    from scripts import claims
except ImportError:                                  # pragma: no cover - 直跑分支
    import claims

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REQUIRED = ("date", "currency", "scenario", "trigger", "watch_direction",
            "claim")
EMPTY_REVIEW = {"status": None, "basis": None}
# 计数栏位。**「未到期」与「未复盘」必须分栏**:前者是"还没到该看的时候",
# 后者是"压根没复盘过",合成一栏正是读者看不清的老毛病换个地方复发。
STATS_ORDER = (claims.STATUS_HIT, claims.STATUS_MISS,
               claims.STATUS_UNDECIDABLE, claims.STATUS_PENDING)
UNREVIEWED = "未复盘"
# 已删除的子命令 → 撞上时给一句说得清的话。argparse 自己只会说 invalid
# choice,而照着旧 SKILL 跑的调用方需要知道结论入口去哪了。
REMOVED_SUBCOMMANDS = {
    "set-review": "该子命令已删除:结论只能由 scripts/claims.resolve_claim 给出,"
                  "经 scripts/review.py 写回 review.status / review.basis。",
}


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


def _read_stdin_json(label):
    try:
        return json.load(sys.stdin), None
    except (ValueError, RecursionError) as e:
        return None, "%s 不是合法 JSON: %s" % (label, e)


def cmd_add(args):
    items, err = _read_stdin_json("stdin")
    if err:
        print(err, file=sys.stderr)
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
            # 输入校验路径: 非 str 值入库会令后续匹配永不命中(argparse 恒 str)、
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
        problems = claims.validate_claim(it["claim"], it["trigger"])
        if problems:
            # 结构化观点是判定的入口,登记时不拦就等于把"判不出"推迟到复盘那天
            print("claim 不合格(%s/%s):\n  %s"
                  % (it["date"], it["currency"], "\n  ".join(problems)),
                  file=sys.stderr)
            return 2
        it["review"] = dict(EMPTY_REVIEW)
    entries = load(args.root)
    entries.extend(items)
    save(args.root, entries)
    print("appended %d entries" % len(items))
    return 0


def cmd_set_claim(args):
    """给已登记条目补 `claim`。**校验与 add 同一份判据**(`validate_claim`):
    两处各写一遍必然漂移,而漂移的后果是一条路放行、另一条打红。"""
    claim, err = _read_stdin_json("stdin")
    if err:
        print(err, file=sys.stderr)
        return 2
    entries = load(args.root)
    for e in entries:
        if e.get("date") == args.date and e.get("currency") == args.currency:
            problems = claims.validate_claim(claim, e.get("trigger"))
            if problems:
                print("claim 不合格(%s/%s):\n  %s"
                      % (args.date, args.currency, "\n  ".join(problems)),
                      file=sys.stderr)
                return 2
            e["claim"] = claim
            save(args.root, entries)
            print("claim set: %s %s" % (args.date, args.currency))
            return 0
    print("未找到条目 %s/%s" % (args.date, args.currency), file=sys.stderr)
    return 2


def cmd_amend_trigger(args):
    """把已登记条目的 `trigger` 改成速览表「条件方向」那一格的原文。

    ---- 为什么要有它 ----
    `skills/fx-daily-report/SKILL.md` 写明日志由速览表整理而来:
    **表是源、日志是抄件**。改了表没回写时两者漂移,而
    `scripts/check_report.py` 的 `DECISION_TRIGGER_NOT_SOURCED` 会把它打红。

    ---- 非破坏:旧值搬进 `trigger_superseded` ----
    这些条目的判词是对着**旧** trigger 写的,并且可能已经逐字发布在下游日报里
    (实测:reports/daily/2026-08-12.md 的复盘节原样引了 2026-08-11 五条判词)。
    直接覆盖会让那段判词失去它评判的对象。旧值留在条目里:契约修好,审计链
    也保住。**只写一次** —— 第二次改动时 `trigger_superseded` 仍是最初那一版,
    因为它记的是"判词当时在评判哪一句",不是"上次改之前是什么"。

    ---- 新增:不许把 claim 改成孤儿 ----
    改了散文却让结构化阈值失去出处,正是「同源同字」要防的事。此时报错、
    不改动:让调用方先想清楚是表错了还是 claim 错了。
    """
    entries = load(args.root)
    for e in entries:
        if e.get("date") == args.date and e.get("currency") == args.currency:
            old = e.get("trigger")
            if old == args.trigger:
                print("trigger 已是该值,未改动: %s %s"
                      % (args.date, args.currency))
                return 0
            if "claim" in e:
                problems = claims.validate_claim(e["claim"], args.trigger)
                if problems:
                    print("新 trigger 会让已登记的 claim 失去出处(%s/%s):\n  %s"
                          % (args.date, args.currency, "\n  ".join(problems)),
                          file=sys.stderr)
                    return 2
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


def cmd_amend_scenario(args):
    """更正已登记条目的 `scenario`。与 `amend-trigger` 同规格。

    ---- 为什么需要它(2026-08-21)----
    `scenario` 与 `trigger` 一样被 `scripts/review.py` **逐字**抄进复盘材料,
    因此也会逐字进入往后每一天的要点表。而在此之前全仓只有 `trigger` 与
    `claim` 有更正入口:当天 USD 那条把「美元是回购计划的最大输家」写反成
    「回购计划是美元的最大输家」,报告改得了、日志改不了,错的那一句会跟着
    复盘材料一路传下去。手工编辑 jsonl 是禁止的,所以缺的是命令。

    **不做 claim 校验**:`scenario` 里不含阈值与时限,claim 不挂在它上面 ——
    在这里跑一遍 `validate_claim` 会把"改一句描述"卡在一条与它无关的判据上。
    """
    entries = load(args.root)
    for e in entries:
        if e.get("date") == args.date and e.get("currency") == args.currency:
            old = e.get("scenario")
            if old == args.scenario:
                # 值没变就不留"改过"的痕迹:审计链里多一条假记录比少一条更难查
                print("scenario 已是该值,未改动: %s %s"
                      % (args.date, args.currency))
                return 0
            if "scenario_superseded" not in e and isinstance(old, str):
                e["scenario_superseded"] = old
            e["scenario"] = args.scenario
            save(args.root, entries)
            print("scenario amended: %s %s" % (args.date, args.currency))
            return 0
    print("未找到条目 %s/%s" % (args.date, args.currency), file=sys.stderr)
    return 2


def cmd_migrate_review(args):
    """旧 review(direction_outcome / trigger_judgement / verdict)整体搬进
    `review_superseded`,新 review 置空,等 `resolve_claim` 重新给结论。

    **旧判词不得静默丢弃**:`reports/daily/2026-08-12.md` 的复盘节已经逐字
    发布了 2026-08-11 五条的 `trigger_judgement`,直接删会让那段发布过的
    判词失去它评判的对象 —— 与 `trigger_superseded` 同一条非破坏原则。
    **只搬一次**:再跑时 `review_superseded` 仍是最初那一版。
    """
    entries = load(args.root)
    migrated = kept = 0
    for e in entries:
        rev = review_of(e)
        if rev is not None and "status" in rev:
            kept += 1
            continue
        if rev is not None and "review_superseded" not in e:
            e["review_superseded"] = rev
        e["review"] = dict(EMPTY_REVIEW)
        migrated += 1
    save(args.root, entries)
    # 带计数的声明:静默迁移与"从来没跑过"不可分辨
    print("migrated %d entries; %d already migrated and left untouched"
          % (migrated, kept))
    return 0


def cmd_stats(args):
    counts = {k: 0 for k in STATS_ORDER}
    counts[UNREVIEWED] = 0
    detail = []
    for e in load(args.root):
        d = e.get("date")
        if not isinstance(d, str):
            continue
        if args.date_from <= d <= args.date_to:
            rev = review_of(e)
            s = rev.get("status") if rev is not None else None
            # 可哈希门: dict/list 等 unhashable status 做 `in counts` 会 TypeError
            key = s if isinstance(s, str) and s in counts else UNREVIEWED
            counts[key] += 1
            detail.append("  - %s %s %s" % (d, e.get("currency"), key))
    print(" / ".join("%s %d" % (k, counts[k])
                     for k in STATS_ORDER + (UNREVIEWED,)))
    for line in detail:
        print(line)
    return 0


def build_parser():
    """子命令与选项的**唯一定义处**。

    三条禁令,由 `tests/test_log_decision.py::SetReviewIsGoneTest` 钉住:
    ① 不得有任何名字里带 verdict / status / judgement 的选项 —— 那就是结论
       入口重新长出来;
    ② 不得有位置参数(位置参数在参数表冻结里最容易被漏看);
    ③ 不得用 `parse_known_args`(它静默吞掉未知参数,等于给未来留门)。
    """
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("add")
    p.add_argument("--root", default=ROOT)
    p.set_defaults(fn=cmd_add)
    p = sub.add_parser("set-claim")
    p.add_argument("--date", required=True)
    p.add_argument("--currency", required=True)
    p.add_argument("--root", default=ROOT)
    p.set_defaults(fn=cmd_set_claim)
    p = sub.add_parser("amend-trigger")
    p.add_argument("--date", required=True)
    p.add_argument("--currency", required=True)
    p.add_argument("--trigger", required=True)
    p.add_argument("--root", default=ROOT)
    p.set_defaults(fn=cmd_amend_trigger)
    p = sub.add_parser("amend-scenario")
    p.add_argument("--date", required=True)
    p.add_argument("--currency", required=True)
    p.add_argument("--scenario", required=True)
    p.add_argument("--root", default=ROOT)
    p.set_defaults(fn=cmd_amend_scenario)
    p = sub.add_parser("migrate-review")
    p.add_argument("--root", default=ROOT)
    p.set_defaults(fn=cmd_migrate_review)
    p = sub.add_parser("stats")
    p.add_argument("--from", dest="date_from", required=True)
    p.add_argument("--to", dest="date_to", required=True)
    p.add_argument("--root", default=ROOT)
    p.set_defaults(fn=cmd_stats)
    return ap


def _subparsers_action(parser):
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action
    raise AssertionError("参数表里没有子命令")


def subcommand_names():
    """参数表冻结用:读 `parser._actions` 而不是 `--help`,
    以覆盖 `argparse.SUPPRESS` 隐藏项。"""
    return sorted(_subparsers_action(build_parser()).choices)


def option_names():
    """每个子命令的选项名(位置参数以 dest 名出现,因此"没有位置参数"
    这条断言是可判的)。`-h/--help` 不计。"""
    out = {}
    for name, sub in _subparsers_action(build_parser()).choices.items():
        names = []
        for action in sub._actions:
            if isinstance(action, argparse._HelpAction):
                continue
            names.extend(action.option_strings or [action.dest])
        out[name] = sorted(names)
    return out


def main(argv=None):
    args_list = sys.argv[1:] if argv is None else list(argv)
    if args_list and args_list[0] in REMOVED_SUBCOMMANDS:
        print(REMOVED_SUBCOMMANDS[args_list[0]], file=sys.stderr)
        return 2
    args = build_parser().parse_args(args_list)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
