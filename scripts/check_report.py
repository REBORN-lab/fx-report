#!/usr/bin/env python3
"""报告校验器:结构 + 数字溯源(文本级逐字比对)。
daily : check_report.py <report.md> <snapshot.json> --brief <brief.md> --mode daily
退出码 0=合规,1=违规(逐条打印),2=用法错误/输入不可读/快照损坏。"""
import argparse
import json
import re
import sys

CURRENCIES = ["USD", "EUR", "PHP", "THB", "BRL"]
MAX_SUMMARY_ITEMS = 6
MAX_SECTION_CJK = 330        # spec"约 300 中文字"+10% 容差
DATE_RE = re.compile(
    r"\d{4}-W\d{2}|\d{4}-\d{2}-\d{2}|\d{4}\s*年|\d{1,2}\s*月\s*\d{1,2}\s*日|\d{1,2}\s*月")
NUM_RE = re.compile(r"\d+(?:\.\d+)?")
CJK_RE = re.compile(r"[一-鿿]")
ALLOWED_SMALL = {str(i) for i in range(0, 13)}   # 序数/条数/月份类小整数
LIST_ITEM_RE = re.compile(r"\s*(?:[-*]|\d+[.、])\s+\S")
MAX_THEME_ITEMS = 3
WEEKLY_SECTIONS = ["本周主线", "各币种", "复盘汇总", "下周关注", "缺漏汇总"]
COVERAGE_RE = re.compile(r"覆盖日报[::]\s*(\d+)\s*份")
DATE_HEADING_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def sections(md):
    out, cur, buf = [], None, []
    for line in md.splitlines():
        if line.startswith("## "):
            if cur is not None:
                out.append((cur, "\n".join(buf)))
            cur, buf = line[3:].strip(), []
        elif cur is not None:
            buf.append(line)
    if cur is not None:
        out.append((cur, "\n".join(buf)))
    return out


def find_section(secs, key):
    for h, b in secs:
        if key in h:
            return h, b
    return None


def numbers_in(text):
    return set(NUM_RE.findall(DATE_RE.sub(" ", text)))


def list_items(body):
    return [line for line in body.splitlines() if LIST_ITEM_RE.match(line)]


def parse_snapshot(snapshot_text):
    """解析并结构校验快照文本(外部数据,可能损坏)。

    返回 (snap, problems):snap 为解析出的 dict(顶层不是对象时为 None),
    problems 为结构问题描述列表。main 层据此 rc=2 响亮失败;
    check_daily 直调时逐条记为 SNAPSHOT_MALFORMED 违规——两层都不裸崩。
    """
    try:
        snap = json.loads(snapshot_text)
    except (ValueError, RecursionError) as e:
        return None, ["快照 JSON 无法解析: %s" % e]
    if not isinstance(snap, dict):
        return None, ["快照顶层应为对象,实为 %s" % type(snap).__name__]
    problems = []
    gaps = snap.get("gaps", [])
    if not isinstance(gaps, list):
        problems.append("快照 gaps 字段应为列表,实为 %s" % type(gaps).__name__)
    else:
        for i, g in enumerate(gaps):
            if not isinstance(g, dict):
                problems.append("快照 gaps[%d] 应为对象,实为 %s" % (i, type(g).__name__))
    return snap, problems


def check_daily(report, snapshot_text, brief_text, strict_brief=False):
    v = []
    secs = sections(report)
    snap, snap_problems = parse_snapshot(snapshot_text)
    for p in snap_problems:
        v.append("SNAPSHOT_MALFORMED: " + p)

    for c in CURRENCIES:
        if not find_section(secs, c):
            v.append("SECTION_MISSING: 缺少币种节 %s" % c)
    s = find_section(secs, "执行摘要")
    if not s:
        v.append("SECTION_MISSING: 缺少执行摘要")
    elif len(list_items(s[1])) > MAX_SUMMARY_ITEMS:
        v.append("SUMMARY_TOO_LONG: 执行摘要 %d 条 > %d"
                 % (len(list_items(s[1])), MAX_SUMMARY_ITEMS))
    for c in CURRENCIES:
        sec = find_section(secs, c)
        if sec:
            n = len(CJK_RE.findall(sec[1]))
            if n > MAX_SECTION_CJK:
                v.append("SECTION_TOO_LONG: %s 节 %d 中文字 > %d" % (c, n, MAX_SECTION_CJK))
    rev = find_section(secs, "复盘")
    if not rev or not rev[1].strip():
        v.append("SECTION_MISSING: 缺少复盘节(首次运行也须保留并注明)")

    gap_sec = find_section(secs, "数据缺漏")
    if not gap_sec:
        v.append("SECTION_MISSING: 缺少数据缺漏节")
    elif snap is not None:
        gaps_raw = snap.get("gaps", [])
        if isinstance(gaps_raw, list):
            body = gap_sec[1].strip()
            if gaps_raw and (not body or body == "无"):
                v.append("GAPS_NOT_DISCLOSED: 快照有 %d 条缺漏但缺漏节为空/无" % len(gaps_raw))
            if not gaps_raw and body != "无":
                v.append("GAPS_MISMATCH: 快照无缺漏,缺漏节应恰为「无」")
            for g in gaps_raw:
                if not isinstance(g, dict):
                    continue    # 已在 SNAPSHOT_MALFORMED 中逐条报告
                scope = g.get("scope")
                token = scope if isinstance(scope, str) and scope != "all" \
                    else g.get("source")
                if isinstance(token, str) and token and token not in gap_sec[1]:
                    v.append("GAP_OMITTED: 缺漏节未提及 %s/%s"
                             % (g.get("source"), g.get("scope")))
        # gaps 非 list:结构问题已记 SNAPSHOT_MALFORMED,跳过内容比对

    allowed = numbers_in(snapshot_text) | numbers_in(brief_text) | ALLOWED_SMALL
    for n in sorted(numbers_in(report) - allowed):
        v.append("NUMBER_UNTRACEABLE: 数字 %s 不见于快照或要点表" % n)
    if strict_brief:
        # 报告 ⊆ 快照∪要点表 一直有校验,但要点表本身 ⊆ 快照 从来没人查——
        # 要点表环节写错的数字会被下游当作合法来源。此开关堵住这条缝。
        brief_allowed = numbers_in(snapshot_text) | ALLOWED_SMALL
        for n in sorted(numbers_in(brief_text) - brief_allowed):
            v.append("BRIEF_NUMBER_UNTRACEABLE: 要点表数字 %s 不见于快照" % n)
    return v


def _read_file(path, label):
    """读取输入文件;失败返回 (None, rc=2 前的 stderr 说明)。"""
    try:
        with open(path, encoding="utf-8") as f:
            return f.read(), None
    except (OSError, UnicodeDecodeError) as e:
        return None, "无法读取%s %s: %s" % (label, path, e)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("report")
    ap.add_argument("snapshot", nargs="?")
    ap.add_argument("--brief", default=None)
    ap.add_argument("--mode", choices=["daily", "weekly"], default="daily")
    ap.add_argument("--strict-brief", action="store_true",
                    help="daily:同时校验 要点表 ⊆ 快照")
    ap.add_argument("--digest", default=None,
                    help="weekly:周度聚合文件,启用周报数字溯源")
    ap.add_argument("--daily", action="append", default=[],
                    help="weekly:当周日报路径,可重复;并入数字白名单")
    args = ap.parse_args(argv)
    report, err = _read_file(args.report, "报告文件")
    if err:
        print(err, file=sys.stderr)
        return 2
    if args.mode == "daily":
        if not args.snapshot:
            print("daily 模式需要快照路径", file=sys.stderr)
            return 2
        snapshot_text, err = _read_file(args.snapshot, "快照文件")
        if err:
            print(err, file=sys.stderr)
            return 2
        snap, problems = parse_snapshot(snapshot_text)
        if snap is None or problems:
            for p in problems:
                print("快照损坏: " + p, file=sys.stderr)
            return 2
        brief_text = ""
        if args.brief:
            brief_text, err = _read_file(args.brief, "要点表文件")
            if err:
                print(err, file=sys.stderr)
                return 2
        violations = check_daily(report, snapshot_text, brief_text,
                                 strict_brief=args.strict_brief)
    else:
        digest_text = None
        if args.digest:
            digest_text, err = _read_file(args.digest, "周度聚合文件")
            if err:
                print(err, file=sys.stderr)
                return 2
        daily_texts = []
        for path in args.daily:
            text, err = _read_file(path, "日报文件")
            if err:
                print(err, file=sys.stderr)
                return 2
            daily_texts.append(text)
        violations = check_weekly(report, digest_text, daily_texts)
    if violations:
        print("CHECK FAILED (%d):" % len(violations))
        for x in violations:
            print(" - " + x)
        return 1
    print("CHECK PASSED")
    return 0


def check_weekly(report, digest_text=None, daily_texts=()):
    v = []
    secs = sections(report)
    for key in WEEKLY_SECTIONS:
        if not find_section(secs, key):
            v.append("SECTION_MISSING: 缺少 %s 节" % key)
    ml = find_section(secs, "本周主线")
    if ml and len(list_items(ml[1])) > MAX_THEME_ITEMS:
        v.append("THEME_TOO_MANY: 本周主线 %d 条 > %d"
                 % (len(list_items(ml[1])), MAX_THEME_ITEMS))
    for h, _ in secs:
        if DATE_HEADING_RE.match(h):
            v.append("DATE_STRUCTURE: 一级结构含日期标题 %s(必须按主题组织)" % h)
    m = COVERAGE_RE.search(report)
    if not m:
        v.append("COVERAGE_MISSING: 缺少「覆盖日报:N 份」声明")
    elif int(m.group(1)) < 3 and "缺失日期" not in report:
        v.append("COVERAGE_GAP_DATES: 覆盖不足 3 份但未注明缺失日期")
    for c in CURRENCIES:
        if c not in report:
            v.append("CURRENCY_MISSING: 周报未覆盖 %s" % c)
    rs = find_section(secs, "复盘汇总")
    if rs:
        for tok in ("命中", "未命中", "无法判定"):
            if tok not in rs[1]:
                v.append("REVIEW_TOKEN_MISSING: 复盘汇总缺少「%s」" % tok)
    if digest_text:
        # 周报此前完全没有数字溯源(只查结构),数字纪律纯靠 prompt 禁令。
        # 白名单 = 聚合文件 ∪ 当周日报 ∪ 小整数:日报本身已过溯源,链条完整。
        allowed = numbers_in(digest_text) | ALLOWED_SMALL
        for text in daily_texts:
            allowed |= numbers_in(text)
        for n in sorted(numbers_in(report) - allowed):
            v.append("NUMBER_UNTRACEABLE: 数字 %s 不见于周度聚合文件或当周日报" % n)
    return v


if __name__ == "__main__":
    sys.exit(main())
