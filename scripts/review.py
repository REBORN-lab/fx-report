#!/usr/bin/env python3
"""复盘节的确定性来源:把**时限已到**的观点交给 `scripts/claims.resolve_claim`
判定,把结论与依据句写回决策日志,并把复盘材料追加进当日要点表。

---- 修前是什么样 ----

`target = prior_dates[-1]` —— 永远只复盘"上一个记过的日子",而速览表的触发
条件写的是 `(T+3)` / `(T+5)`。于是一条"三个运行日内升破 33.13"的观点,**第二天**
就被拿去判;判据还只是两次定盘的高低,参考价没更新的那天两值相等 → 直接
「无法判定」。实测 40 条里 33 条落在这一档,而它们绝大多数的诚实答案是
「未到期」。

---- 现在是什么样 ----

每天扫全部**尚未定论**的结构化观点,逐条按它自己登记的时限判定:
时限没到 → 顺延(不写日志、不出材料行,只进那条带计数的声明);
时限已到 → 结论与依据句由 `resolve_claim` 给出,写回日志、出一行材料。
结论词与依据句本文件一个字都不自己拼 —— 它只负责选出该判哪些条目。
"""
import argparse
import json
import os
import sys

# 判定与结论句的唯一来源。两条分支对应两种运行形态:包内导入(测试、
# `python3 -m`)与 `python3 scripts/review.py` 直跑(此时 sys.path[0] 就是
# scripts/)。
try:
    from scripts import claims
except ImportError:                                  # pragma: no cover - 直跑分支
    import claims

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EMPTY_REVIEW = {"status": None, "basis": None}
# 复盘材料块的块头。**唯一事实源在这里**(本脚本是产出方),
# `scripts/check_report.py` 只许导入 —— 它据此把要点表切成「LLM 手写」与
# 「本脚本生成」两段,后者豁免「要点表 ⊆ 当日快照」那一层的数字溯源。
# 两处各写一遍必然漂移,而漂移的后果是豁免整段失效或整段过宽,都不会有人发现。
REVIEW_BLOCK_HEADING = "## 复盘材料(scripts/review.py 生成,勿手改)"
# 带计数的声明。**唯一事实源同样在这里**,校验器只许据它推出行式样。
# 这一行**每天都打**,不是"没东西可复盘时才打":读者要能分辨"今天没有到期的"
# 与"今天这一层根本没跑"。
DECLARATION_FMT = ("- 到期复盘 %d 条;未到期 %d 条顺延;已定论 %d 条不再复盘;"
                   "结构化字段之前的历史观点 %d 条不在本节复盘范围")
FIRST_RUN_LINE = "- 首次运行,无历史观点可复盘"
MATERIAL_FMT = ("- %s | 观点日 %s | 情景: %s | 触发条件: %s | 复盘句: %s"
                " | 结论: %s")
# 顺延登记行:时限没到的观点**不出结论**,但它的原文要留在要点表里。
# 两个理由,后一个是实测出来的:
# ① 读者(与次日的写作者)要看得见"还在观察的是哪几条";
# ② 报告的「本期相对上期的变化」节要引用这些观点登记时的数,而报告的数字
#    白名单是「当日快照 ∪ 当日要点表」—— 这些条目一旦不出现在要点表里,
#    那些数就无处可溯。实测 2026-08-13 的 0.094 / 4.249 / 9.609 三个数
#    正是这么被判 NUMBER_UNTRACEABLE 的。
# 行尾**没有**「| 结论:」那一段,与结论行在式样上一眼可分。
PENDING_FMT = "- 顺延 | %s | 观点日 %s | 情景: %s | 触发条件: %s | 复盘句: %s"


def load_log(path):
    """读回日志。坏 JSON 行(含深嵌套 RecursionError)与非 dict 行跳过(容错路径)。"""
    if not os.path.exists(path):
        return []
    entries = []
    with open(path, encoding="utf-8") as f:
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


def save_log(path, entries):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def load_snapshot(data_dir, date_str):
    p = os.path.join(data_dir, date_str + ".json")
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        try:
            snap = json.load(f)
        except (ValueError, RecursionError):
            return None
    # isinstance 门:顶层不是对象的快照读不出任何读数,与"当天没跑采集"同形。
    # 判定侧对入参形状是**失败关闭**(形状不对就抛),那条严格是给调用方的
    # 缺陷用的;外部损坏的存量文件属于容错路径,在这里收口。
    return snap if isinstance(snap, dict) else None


def snapshot_series(data_dir, from_date, to_date):
    """`[(日期, 快照), …]` 升序,含两端,**第一项恒为观点日当日**。

    只列**跑过采集的那些天**(数据目录里实际存在的文件)。这既是唯一能拿到的
    事实,也正好是判定要的东西:窗口的外沿按快照日数算,而不去猜哪天该有定盘
    —— 猜就等于查日程表,而本脚本手上没有任何日程输入。
    """
    dates = set()
    if os.path.isdir(data_dir):
        for name in os.listdir(data_dir):
            if name.endswith(".json"):
                stem = name[:-len(".json")]
                if from_date < stem <= to_date:
                    dates.add(stem)
    series = [(from_date, load_snapshot(data_dir, from_date))]
    series.extend((d, load_snapshot(data_dir, d)) for d in sorted(dates))
    return series


def review_of(e):
    """e['review'] 的 isinstance 门: 非 dict(缺失/外部损坏为 None)返回 None。"""
    rev = e.get("review")
    return rev if isinstance(rev, dict) else None


# 定论 = 三档**可判的**结论。「未到期」不在其中:它是每天重算的当前状态,
# 不是定论 —— 把它算成定论就等于把不利结果养到永远不判。
CONCLUSIVE = tuple(s for s in claims.STATUSES if s != claims.STATUS_PENDING)


def is_concluded(e):
    """已定论的条目不再复盘第二次:事后重写等于伪造记录。"""
    rev = review_of(e)
    status = rev.get("status") if rev is not None else None
    return isinstance(status, str) and status in CONCLUSIVE


def flat(v):
    """材料行单点收口: 字段值中的换行扁平化为空格,防伪造节标题/伪列表行。
    (LLM 文本含换行属正常输入,add 不拒绝,写入 brief 时扁平化即可。)"""
    return str(v).replace("\r", " ").replace("\n", " ")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True)
    ap.add_argument("--root", default=ROOT)
    args = ap.parse_args(argv)
    log_path = os.path.join(args.root, "state", "decision-log.jsonl")
    data_dir = os.path.join(args.root, "data")
    brief_path = os.path.join(args.root, "briefs", args.date + "-brief.md")
    if not os.path.exists(brief_path):
        print("要点表不存在: %s(须先执行 SKILL 第 2 步)" % brief_path, file=sys.stderr)
        return 1

    entries = load_log(log_path)
    lines = ["", REVIEW_BLOCK_HEADING, ""]
    prior = [e for e in entries
             if isinstance(e.get("date"), str) and e["date"] < args.date]
    if not prior:
        lines.append(FIRST_RUN_LINE)
    else:
        # 结构化字段之前登记的条目没有 `claim`,判不出时限也判不出观测量。
        # 它们**不进本节**,但要进声明:静默排除与"全都复盘过了"不可分辨。
        legacy = [e for e in prior if "claim" not in e]
        settled = [e for e in prior if "claim" in e and is_concluded(e)]
        open_entries = [e for e in prior
                        if "claim" in e and not is_concluded(e)]
        due, pending = [], []
        for e in open_entries:
            res = claims.resolve_claim(
                e, snapshot_series(data_dir, e["date"], args.date))
            (pending if res.status == claims.STATUS_PENDING else due).append(
                (e, res))
        lines.append(DECLARATION_FMT
                     % (len(due), len(pending), len(settled), len(legacy)))
        changed = False
        # 未到期的也写回日志:日志要能回答"这条现在什么状态",否则 stats 与
        # 周报的「未到期」栏永远是 0,拆出这一档等于白拆。但它**不出材料行**
        # —— 复盘节只放到期的,没到该看的时候就不该占读者的注意力。
        for e, res in pending + due:
            rev = review_of(e)
            if rev is None:
                rev = dict(EMPTY_REVIEW)
                e["review"] = rev
            if rev.get("status") != res.status or rev.get("basis") != res.sentence:
                rev["status"] = res.status
                rev["basis"] = res.sentence
                changed = True
        for e, res in pending:
            lines.append(PENDING_FMT
                         % (flat(e.get("currency")), e["date"],
                            flat(e.get("scenario")), flat(e.get("trigger")),
                            res.sentence))
        for e, res in due:
            # 复盘句嵌在**既有行内**,不新起一行:块内每一行都必须落在
            # `check_report.REVIEW_LINE_RES` 的式样里才拿得到「要点表 ⊆ 快照」
            # 那一层的豁免,新起一行会被当成 LLM 手写行照查(实测的 4 条
            # BRIEF_NUMBER_UNTRACEABLE 就是这么来的)。
            lines.append(MATERIAL_FMT
                         % (flat(e.get("currency")), e["date"],
                            flat(e.get("scenario")), flat(e.get("trigger")),
                            res.sentence, res.status))
        if changed:
            # 无回填发生时不重写文件: 避免丢弃坏行、放大并发窗口
            save_log(log_path, entries)
    with open(brief_path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    for line in lines:
        if line.strip() and line != REVIEW_BLOCK_HEADING:
            print(line)
    print("review material appended to %s" % brief_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
