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
# 结论句字段名**显式枚举**,禁止按 *verdict* 模式扫:digest 顶层的 `verdicts`
# 是计数 dict、`verdict_details` 是 list,模式匹配会把它们扫进字符串比对,
# 然后在 `x in report` 处 TypeError 或静默跳过。
VERDICT_FIELDS_EVENTS = ("articles_verdict", "official_verdict")
VERDICT_FIELDS_RATES = ("fixings_verdict",)
VERDICT_FIELD_DAILY = ("events_verdict",)
# derive.SCHEMA_VERSION 达到此值,才保证快照 derived.events 带结论句字段。
# 判据取 schema 版本而非"这个键在不在":后者会让**新代码产出却漏写该字段**
# 的缺陷与存量快照完全同形,静默通过。
DERIVED_VERDICT_SCHEMA = 2


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


def check_verdicts(report, container, fields, covered, required, label):
    """结论句逐字引用检查。**日报与周报共用这一份判定**,两个调用点只提供
    「到哪个容器取哪些字段」—— 判定逻辑复制两份后漂移是本仓库栽过的坑
    (见 scripts/fixings.py);与 events.landed_count_capped 同构。

    container : {币种: {字段: 句子}};非 dict 一律返回空结果 —— 谓词不判结构。
                **注意目前没有别处兜底**:容器缺失/类型错时本检查静默失效,
                调用方必须自己确认容器存在(T4 已在 check_weekly 加 isinstance
                门并出 VERDICT_CONTAINER_MALFORMED)
    fields    : 要检查的字段名元组(显式枚举,不按名字模式扫)
    covered   : 报告已覆盖的币种集合;不在其中者跳过,由 SECTION_MISSING /
                CURRENCY_MISSING 单独报告 —— 同一处缺失不得产生两条违规
    required  : 该来源的 schema 是否保证这些字段存在
    label     : 违规信息里的来源前缀,如 "digest.events" / "derived.events"

    返回 (violations, skipped_currencies)。**required=True 时 skipped 恒为 0**
    (缺字段直接进 violations),调用方可以安全丢弃;required=False 时
    skipped 必须被如实打印 ——「跳过」与「通过」在输出上不可分辨,正是本
    检查要解决的问题。
    """
    v, skipped = [], 0
    if not isinstance(container, dict):
        return v, skipped
    for c in CURRENCIES:
        if c not in covered:
            continue
        entry = container.get(c)
        if not isinstance(entry, dict):
            # 容器里没有该币种条目是合法形态(基准货币在定盘类容器中本就没有
            # 条目),不是缺字段;只有条目存在时才要求其结论句字段齐全
            continue
        skip_this_currency = False
        for field in fields:
            s = entry.get(field)
            if s is None:
                if required:
                    v.append("VERDICT_ABSENT: %s.%s 缺少结论句 %s(字段不存在或为 null)"
                             % (label, c, field))
                else:
                    skip_this_currency = True
                continue
            if not isinstance(s, str):
                v.append("VERDICT_MALFORMED: %s.%s 的 %s 应为字符串,实为 %s"
                         % (label, c, field, type(s).__name__))
                continue
            if not s.strip():
                # 任意报告都"包含"空串 —— 最直接的假绿入口
                v.append("VERDICT_EMPTY: %s.%s 的 %s 为空串或纯空白"
                         % (label, c, field))
                continue
            # 逐字节精确子串。前提:产出端(verdicts.join_verdict /
            # _fixings_verdict)从不产生首尾空白,纯空白已由上一分支拦下 ——
            # 若哪天产出端会带首尾空白,这里应改成 s.strip() not in report,
            # 因为 markdown 无法可靠复现首尾空格
            if s not in report:
                v.append("VERDICT_NOT_QUOTED: %s.%s 的 %s 未逐字出现在报告中;"
                         "期望原文:「%s」" % (label, c, field, s))
        if skip_this_currency:
            skipped += 1        # 按币种计一次,不按字段——T6 打印的是「N 个币种」
    return v, skipped


def check_daily(report, snapshot_text, brief_text, strict_brief=False, notes=None):
    """日报结构 + 数字溯源 + 结论句逐字引用检查,返回违规列表。

    notes : **出参**。传入的 list 会被追加「非违规的降级声明」
            (VERDICT_SKIPPED_LEGACY / VERDICT_SKIPPED_NO_DERIVED)。
            不传等于放弃这些声明 —— 此时退出码 0 既可能表示「全查过了」
            也可能表示「一条都没查」,两者不可分辨,正是本检查要消灭的形态。
            CLI 调用方必须传并打印。
            check_weekly 没有对应参数:那一侧 required 恒为 True,缺字段
            直接进 violations,不会产生跳过。
    """
    v = []
    secs = sections(report)
    snap, snap_problems = parse_snapshot(snapshot_text)
    for p in snap_problems:
        v.append("SNAPSHOT_MALFORMED: " + p)

    covered = set()
    for c in CURRENCIES:
        if find_section(secs, c):
            covered.add(c)
        else:
            # covered 与 SECTION_MISSING 必须互为补集 —— check_verdicts 的
            # 「让位 ①」依赖这一点。建在同一个循环里,物理上保证两者一起改
            # (check_weekly 的注释这么写,而日报侧此前分两处算)
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

    # 结论句逐字引用。闸门只读不写:schema 过旧不让校验失败,只降级并如实
    # 声明降级了几条 —— 「跳过」与「通过」在输出上必须可区分。
    # 判据取 schema 版本而非"这个键在不在":后者会让**新代码产出却漏写该
    # 字段**的缺陷与存量快照完全同形,静默通过。
    derived = snap.get("derived") if isinstance(snap, dict) else None
    has_derived = isinstance(derived, dict)
    derived = derived if has_derived else {}
    ver = derived.get("schema_version")
    ver_ok = (isinstance(ver, int) and not isinstance(ver, bool)
              and ver >= DERIVED_VERDICT_SCHEMA)
    events = derived.get("events")
    # ③ 没有派生节:不是违规,但**必须出声明** —— 此前这一形态跑出裸
    # CHECK PASSED、零声明,与「全部结论句已核验」不可分辨,而实测
    # data/2026-08-07..10.json 四天都是它,六天里占了四天
    if not has_derived and notes is not None:
        notes.append("VERDICT_SKIPPED_NO_DERIVED: 快照无 derived 节,"
                     "本次未校验任何结论句")
    # ①② 只对「声称带结论句」的快照生效:ver_ok 为假时照旧跳过,否则
    # 存量快照(derived 为 null 或 schema=1)会集体变红。
    # ver_ok 为真时容器与条目都不再是可选的 —— 与 check_weekly 对称,
    # 谓词不越权判结构,兜底在调用点(见 check_verdicts 的 docstring)。
    if ver_ok and not isinstance(events, dict):
        v.append("VERDICT_CONTAINER_MALFORMED: 快照的 derived.events 不是对象"
                 "(实为 %s),derived.events 下的结论句一条都未校验"
                 % type(events).__name__)
    elif ver_ok:
        # 日报五个币种都应有事件派生量(derive 按 rates ∪ events.KEYWORDS
        # 逐币种填充),整条缺失不是合法形态 —— 与周报的 rates 容器不同,
        # 那里基准货币本就没有条目
        present = {k for k, entry in events.items()
                   if isinstance(entry, dict)}
        # 判据必须是「值为 dict 的键集」而不是键存在性:check_verdicts 对非
        # dict 条目静默 continue(周报侧基准货币在 rates 里本就没条目,那是
        # 必需的),用 set(events) 会让「条目在、但是 null/字符串/列表」
        # 原样静默通过 —— 与「条目缺失」同因同果,必须同判
        for c in sorted(covered - present):
            v.append("VERDICT_ENTRY_MISSING: derived.events 缺少 %s 的条目;"
                     "该币种的结论句一条都未校验" % c)
    found, skipped = check_verdicts(report, events,
                                    VERDICT_FIELD_DAILY, covered,
                                    required=ver_ok, label="derived.events")
    v.extend(found)
    checked = {c for c in covered
               if isinstance(events, dict) and isinstance(events.get(c), dict)}
    if skipped and notes is not None:
        notes.append("VERDICT_SKIPPED_LEGACY: %d/%d 个覆盖币种因快照 schema 过旧"
                     "(derived.schema_version=%r)未校验结论句"
                     % (skipped, len(covered), ver))
    elif (has_derived and not ver_ok and covered and not checked
            and notes is not None):
        # schema 旧、且连一个可查条目都没有:skipped 恒为 0,上一条不会触发。
        # 不补这一档,「derived 在但空」会退回裸 CHECK PASSED、零声明 ——
        # 与 ③ 档要消灭的形态一字不差,只是分支不同
        notes.append("VERDICT_SKIPPED_LEGACY: %d/%d 个覆盖币种因快照 schema 过旧"
                     "(derived.schema_version=%r)未校验结论句"
                     % (len(covered), len(covered), ver))

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
    notes = []
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
                                 strict_brief=args.strict_brief, notes=notes)
    else:
        if args.daily and not args.digest:
            print("--daily 需与 --digest 同用(单独给日报不会启用数字溯源)",
                  file=sys.stderr)
            return 2
        digest_text = None
        if args.digest is not None:
            digest_text, err = _read_file(args.digest, "周度聚合文件")
            if err:
                print(err, file=sys.stderr)
                return 2
            # 校验器打印 PASS 却什么都没查,是最坏的失败模式:digest 为空、
            # 非 JSON、或指向别的文件时必须响亮失败(与快照同规格 rc=2)
            try:
                digest = json.loads(digest_text)
            except (ValueError, RecursionError) as e:
                print("周度聚合文件无法解析: %s" % e, file=sys.stderr)
                return 2
            if not isinstance(digest, dict) or "week" not in digest \
                    or "generated_from" not in digest:
                print("周度聚合文件结构不符(需含 week 与 generated_from)",
                      file=sys.stderr)
                return 2
        daily_texts = []
        for path in args.daily:
            text, err = _read_file(path, "日报文件")
            if err:
                print(err, file=sys.stderr)
                return 2
            daily_texts.append(text)
        violations = check_weekly(report, digest_text, daily_texts,
                                  digest if args.digest is not None else None)
    # 降级声明先于结论打印:退出码 0 却跳过了几条,读者必须看得见
    for note in notes:
        print(note)
    if violations:
        print("CHECK FAILED (%d):" % len(violations))
        for x in violations:
            print(" - " + x)
        return 1
    print("CHECK PASSED")
    return 0


def check_weekly(report, digest_text=None, daily_texts=(), digest=None):
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
    covered = set()
    for c in CURRENCIES:
        if c in report:
            covered.add(c)
        else:
            # covered 与 CURRENCY_MISSING 必须互为补集 —— T3 的「让位 ①」
            # 依赖这一点。建在同一个循环里,物理上保证两者一起改
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
    if isinstance(digest, dict):
        # 与日报的 GAP_OMITTED 对称:聚合出的每个缺漏源都必须在缺漏汇总里出现
        by_source = digest.get("gaps_by_source")
        gap_sec = find_section(secs, "缺漏汇总")
        if isinstance(by_source, dict) and gap_sec:
            for source in sorted(by_source):
                if isinstance(source, str) and source and source not in gap_sec[1]:
                    v.append("GAP_OMITTED: 缺漏汇总未提及 %s" % source)
        # 结论句逐字引用。digest 为 None(未给 --digest)时整块不执行 ——
        # 取不到结论句不等于漏写,不得报 VERDICT_ABSENT。
        # 聚合器的 _rates_digest / _events_one 对每个落盘的币种条目都必写这些
        # 字段,故 required=True:缺失即脚本缺陷。
        for container, fields, label in (
                (digest.get("events"), VERDICT_FIELDS_EVENTS, "digest.events"),
                (digest.get("rates"), VERDICT_FIELDS_RATES, "digest.rates")):
            if not isinstance(container, dict):
                # check_verdicts 对非 dict 容器静默返回空 —— 谓词不越权判结构。
                # 但**没有别处兜底**:main 只校验 week 与 generated_from,
                # 容器坏掉时会打印 CHECK PASSED 而一条结论句都没查,正是本
                # change 要消灭的形态。响亮失败在这里。
                v.append("VERDICT_CONTAINER_MALFORMED: 聚合文件的 %s 不是对象"
                         "(实为 %s),%s 下的结论句一条都未校验"
                         % (label, type(container).__name__, label))
                continue
            found, _ = check_verdicts(report, container, fields, covered,
                                      required=True, label=label)
            v.extend(found)
    return v


if __name__ == "__main__":
    sys.exit(main())
