#!/usr/bin/env python3
"""混合复盘的确定性一半:用两日快照算汇率方向,回填 direction_outcome,
并把复盘材料追加进当日要点表。触发条件是否发生由 LLM 判定(SKILL 第 4 步)。"""
import argparse
import json
import math
import os
import sys

# 结论句的拼装口只有一个(head 与 caveat 列表怎么连,只有 verdicts 说了算)。
# 自己用 % / join 拼会在分隔符(全角顿号)、括号(ASCII)与"没有 caveat 时
# 不得拼出空括号"三处各漂一次,而这三处正是逐字引用检查的比对对象。
# 两条分支对应两种运行形态:包内导入(测试、`python3 -m`)与
# `python3 scripts/review.py` 直跑(此时 sys.path[0] 就是 scripts/)。
try:
    from scripts.verdicts import join_verdict
except ImportError:                                  # pragma: no cover - 直跑分支
    from verdicts import join_verdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EMPTY_REVIEW = {"direction_outcome": None, "trigger_judgement": None, "verdict": None}
# 复盘材料块的块头。**唯一事实源在这里**(本脚本是产出方),
# `scripts/check_report.py` 只许导入 —— 它据此把要点表切成「LLM 手写」与
# 「本脚本生成」两段,后者豁免 `--strict-brief` 的当日快照数字溯源。
# 两处各写一遍必然漂移,而漂移的后果是豁免整段失效或整段过宽,都不会有人发现。
REVIEW_BLOCK_HEADING = "## 复盘材料(scripts/review.py 生成,勿手改)"


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
            return json.load(f)
        except (ValueError, RecursionError):
            return None


def rate_of(snap, currency):
    """isinstance 门逐层下钻: 任一层类型不符 → None。
    primary 为 bool 或非数值 → None(约定 2: 数值比较前排除 bool)。"""
    if not isinstance(snap, dict) or not isinstance(currency, str):
        return None
    rates = snap.get("rates")
    if not isinstance(rates, dict):
        return None
    entry = rates.get(currency)
    if not isinstance(entry, dict):
        return None
    primary = entry.get("primary")
    if isinstance(primary, bool) or not isinstance(primary, (int, float)):
        return None
    if not math.isfinite(primary):
        # NaN/Infinity 穿过数值比较会给出确定性错误结论 → 视为缺失
        return None
    return primary


def ref_date_of(snap, currency):
    """该币种的参考价定盘日期;存量快照(无此字段)或类型不符 → None。"""
    if not isinstance(snap, dict) or not isinstance(currency, str):
        return None
    rates = snap.get("rates")
    if not isinstance(rates, dict):
        return None
    entry = rates.get(currency)
    if not isinstance(entry, dict):
        return None
    ref = entry.get("ref_date")
    return ref if isinstance(ref, str) else None


def unchanged_ref_date_of(prev_snap, today_snap, currency):
    """两侧参考价定盘日期都在且相同 → 返回那个日期(参考价未更新,不是价格
    持平);任一侧缺失(存量快照)或不同 → None,退回按数值比较的旧行为。

    **谓词与日期只留这一个判据**:调用点按 `is not None` 判,不按真值判 ——
    ref_date 为空串时旧的布尔判据认它为「未更新」,按真值判会把这一档静默
    翻面。返回日期而不只返回布尔,是因为那句话必须带上它(见
    `unchanged_ref_note`);两处各算一次必然算岔。
    """
    prev_ref = ref_date_of(prev_snap, currency)
    today_ref = ref_date_of(today_snap, currency)
    return prev_ref if prev_ref is not None and prev_ref == today_ref else None


def unchanged_ref_note(ref_date):
    """两日同定盘时的那句话。**唯一事实源在这里**:两个产出点
    (`direction_sentence` 的 caveat 与材料行的汇率段)共用它,
    `scripts/check_report.py` 的行式样也由它推出、不许自己再写一遍
    —— 与 `REVIEW_BLOCK_HEADING` 同规矩。

    **只陈述事实,不断言原因。** 修前这里写的是「参考价未更新(非工作日)」,
    而本脚本**从不查日历**:它手上只有两个 ref_date,没有任何交易所日程输入。
    实测 2026-08-12 是周三、2026-08-14 是周五,四个币种都不休市,这句假归因
    还经报告复盘节逐字引用流回了正文。脚本有资格说的全部内容,就是「两天的
    定盘日期是同一个,而且是哪一个」;至于为什么没更新(休市?源未刷新?
    采集时点早于定盘?),交给读者据这个日期自己判断。

    措辞里不得出现管道语汇(「快照」等):这句话要落进**正文**,而正文位置
    闸门禁的正是那些词,脚本自己的产出不得触发它(自伤形态)。
    """
    return "参考价未更新(仍为 %s 定盘)" % ref_date


def direction_outcome(prev_rate, today_rate, watch_direction):
    if prev_rate is None or today_rate is None or watch_direction not in ("up", "down"):
        return "无法判定"
    if today_rate == prev_rate:
        return "无法判定"
    actual = "up" if today_rate > prev_rate else "down"
    return "命中" if actual == watch_direction else "未命中"


def direction_sentence(date, currency, outcome, watch_direction,
                       prev_rate, today_rate, unchanged_ref_date):
    """方向核对的**完整一句**,供报告复盘节逐字引用。

    存在理由:`direction_outcome` 由脚本机械算出,却实测**零个下游消费者** ——
    它只以"方向核对: X"三个字躺在要点表里,而流向读者的 verdict 是 LLM 自己
    写的。这一句是它的第一个消费者:脚本给整句,报告只准整句照抄。

    三条纪律:
    ① 经 `verdicts.join_verdict` 拼装,与 events_verdict 走同一条通道;
    ② `watch_direction` 是 LLM 文本,只认 up/down 两个值 —— 原样插进来会把
       任意字符(竖线、伪造的字段名、换行)带进这条要被逐字引用的话;
    ③ 句内不出现快照字段名/文件路径/管道语汇:这句要落进**正文**,而正文
       位置闸门禁的正是那些词,脚本自己的产出不得触发它(自伤形态);
    ④ 句内**只给事实,不给原因** —— 脚本手上只有读数与定盘日期,任何"为什么"
       都是它无从判断的(修前那句「非工作日」就是这么进的正文,见
       `unchanged_ref_note`)。
    """
    head = "%s %s 方向核对:%s" % (date, currency, outcome)
    caveats = ["关注方向 %s" % watch_direction
               if watch_direction in ("up", "down") else "关注方向未记录"]
    if unchanged_ref_date is not None:
        # 两值相等是"没有新定盘"而非"市场持平",这一条替代两个读数。
        # 措辞只从 unchanged_ref_note 取:句内不得自己拼(见该函数的说明)
        caveats.append(unchanged_ref_note(unchanged_ref_date))
    else:
        caveats.append("观点日读数 %s" % prev_rate if prev_rate is not None
                       else "观点日无读数")
        caveats.append("当日读数 %s" % today_rate if today_rate is not None
                       else "当日无读数")
    return join_verdict(head, caveats)


def review_of(e):
    """e['review'] 的 isinstance 门: 非 dict(缺失/外部损坏为 None)返回 None。"""
    rev = e.get("review")
    return rev if isinstance(rev, dict) else None


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
    prior_dates = sorted({e.get("date") for e in entries
                          if isinstance(e.get("date"), str) and e.get("date") < args.date})
    if not prior_dates:
        lines.append("- 首次运行,无历史观点可复盘")
    else:
        target = prior_dates[-1]
        prev_snap = load_snapshot(data_dir, target)
        today_snap = load_snapshot(data_dir, args.date)
        pending = []
        for e in entries:
            if e.get("date") != target:
                continue
            rev = review_of(e)
            oc = rev.get("direction_outcome") if rev is not None else None
            if oc is None:
                pending.append(e)
        if not pending:
            lines.append("- 上一运行日(%s)无未复盘观点" % target)
        for e in pending:
            currency = e.get("currency")
            prev_r = rate_of(prev_snap, currency)
            today_r = rate_of(today_snap, currency)
            oc = direction_outcome(prev_r, today_r, e.get("watch_direction"))
            rev = review_of(e)
            if rev is None:
                rev = dict(EMPTY_REVIEW)
                e["review"] = rev
            rev["direction_outcome"] = oc
            # 参考价未更新时,两值相等是"没有新定盘"而非"市场持平"——必须区分,
            # 否则 LLM 会把没有新定盘的一天写成价格观察(诊断实测:12/12 汇率对
            # 连平全属此类)。**为什么没更新,脚本不知道**,故只报同定盘日这个事实。
            unchanged_ref = unchanged_ref_date_of(prev_snap, today_snap, currency)
            rate_desc = (unchanged_ref_note(unchanged_ref) if unchanged_ref is not None
                         else "汇率 %s→%s" % (prev_r, today_r))
            # 方向核对句嵌在**既有行内**,不新起一行:块内每一行都必须落在
            # `check_report.REVIEW_LINE_RES` 的式样里才拿得到 --strict-brief
            # 的豁免,新起一行会被当成 LLM 手写行照查(实测的 4 条
            # BRIEF_NUMBER_UNTRACEABLE 就是这么来的)。字段插在"触发条件"与
            # "关注方向"之间:前两段是 `.*`,吃得下这一段;"关注方向"那段是
            # `[^|]*`,插在它后面会把式样撑破。
            lines.append(
                "- %s | 观点日 %s | 情景: %s | 触发条件: %s | 方向核对句: %s"
                " | 关注方向: %s | %s | 方向核对: %s"
                % (flat(currency), target, flat(e.get("scenario")),
                   flat(e.get("trigger")),
                   direction_sentence(target, flat(currency), oc,
                                      e.get("watch_direction"), prev_r,
                                      today_r, unchanged_ref),
                   flat(e.get("watch_direction")), rate_desc, oc))
        if pending:
            # 无回填发生时不重写文件: 避免丢弃坏行、放大并发窗口
            save_log(log_path, entries)
    with open(brief_path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("review material appended to %s" % brief_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
