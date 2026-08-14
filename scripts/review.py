#!/usr/bin/env python3
"""混合复盘的确定性一半:用两日快照算汇率方向,回填 direction_outcome,
并把复盘材料追加进当日要点表。触发条件是否发生由 LLM 判定(SKILL 第 4 步)。"""
import argparse
import json
import math
import os
import sys

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


def fixing_unchanged(prev_snap, today_snap, currency):
    """两侧参考价定盘日期都在且相同 → 参考价未更新(非工作日),不是价格持平。
    任一侧缺失(存量快照)→ False,退回按数值比较的旧行为。"""
    prev_ref = ref_date_of(prev_snap, currency)
    today_ref = ref_date_of(today_snap, currency)
    return prev_ref is not None and prev_ref == today_ref


def direction_outcome(prev_rate, today_rate, watch_direction):
    if prev_rate is None or today_rate is None or watch_direction not in ("up", "down"):
        return "无法判定"
    if today_rate == prev_rate:
        return "无法判定"
    actual = "up" if today_rate > prev_rate else "down"
    return "命中" if actual == watch_direction else "未命中"


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
            # 否则 LLM 会把休市日写成价格观察(诊断实测:12/12 汇率对连平全属此类)
            rate_desc = ("参考价未更新(非工作日)"
                         if fixing_unchanged(prev_snap, today_snap, currency)
                         else "汇率 %s→%s" % (prev_r, today_r))
            lines.append(
                "- %s | 观点日 %s | 情景: %s | 触发条件: %s | 关注方向: %s"
                " | %s | 方向核对: %s"
                % (flat(currency), target, flat(e.get("scenario")),
                   flat(e.get("trigger")), flat(e.get("watch_direction")),
                   rate_desc, oc))
        if pending:
            # 无回填发生时不重写文件: 避免丢弃坏行、放大并发窗口
            save_log(log_path, entries)
    with open(brief_path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("review material appended to %s" % brief_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
