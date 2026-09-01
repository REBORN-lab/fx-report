#!/usr/bin/env python3
"""从已发布的报告里**抽取**要点,供趋势页展示。

存在理由与 `scripts/trend.py` 同源:凡是要出现在派生界面上的字句与数字,
都必须能指回一份已经过校验的产物,不能由我重述一遍。报告本身已经过
`scripts/check_report.py`(数字溯源、结论句逐字引用、判断环三件齐全),
所以**抽取**是安全的、**转述**不是 —— 转述一次就等于在校验之外新造了一份
说法,而那份说法没有任何闸门守着。

本模块因此只做三件事:切节、切表、按标签切句。它不判断、不归纳、不改写:
- 「本期相对上期的变化」的四种类型不是这里分的类,是报告自己用
  `**触发位变了**` 这样的粗体写在行首的,这里只把它读出来;
- 区间与定盘的前后对比只做**比较**(谁高谁低),不做减法 —— 浮点差值会在
  末位造出假精度,而这个结果要印到页面上。

抽不到就如实留空(`None` / 空列表),不猜:页面上一处空白,比一处编出来的
话安全得多。
"""
import argparse
import json
import os
import re
import sys

try:                                                 # pragma: no cover - 包内分支
    from scripts import trend
    from scripts.appendix import CURRENCIES
except ImportError:                                  # pragma: no cover - 直跑分支
    import trend
    from appendix import CURRENCIES

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 「本期相对上期的变化」的四种类型。**唯一事实源是 SKILL 的那张表**,
# 这里按报告行首的粗体标签匹配;报告没标或标了别的,一律记 None ——
# 猜一个类型出来,页面就会用一个报告没说过的判断给读者分类。
CHANGE_KINDS = ("方向变了", "触发位变了", "依据变了", "无实质变化")
RING_LABELS = ("驱动", "传导", "是否已反映", "分歧与判断")
JUDGEMENT_LABELS = ("关键假设", "替代解释", "翻转指标")
HEAD_RE = re.compile(r"^##\s+(.+?)\s*$", re.M)
CCY_IN_HEAD_RE = re.compile(r"[（(]([A-Z]{3})[）)]")
THEME_RE = re.compile(r"^###\s+(主线[一二三四五六七八九十]+)[:：](.+?)$", re.M)
SCOPE_RE = re.compile(r"[（(]影响\s*([^）)]+)[）)]")
FLIP_RE = re.compile(r"^\*\*翻转指标[（(]([^）)]+)[）)]\*\*[:：](.+)$", re.M)
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
WEEK_RE = re.compile(r"^\d{4}-W\d{2}$")


# ------------------------------------------------------------ 通用切分

def sections(text):
    """`## 标题` → 正文。标题重名时**后一节不覆盖前一节**,而是整个键作废。

    覆盖是最坏的一种:页面会拿着两节里的一节当"那一节",而读者无从分辨
    拿到的是哪一份。作废至少在页面上表现为空白。
    """
    heads = list(HEAD_RE.finditer(text))
    out, dupes = {}, set()
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        key = m.group(1)
        if key in out:
            dupes.add(key)
        out[key] = text[m.end():end].strip("\n")
    for k in dupes:
        out.pop(k, None)
    return out


def find_section(secs, needle):
    """标题**包含** needle 的那一节;命中不唯一时返回 None(同上,不猜)。"""
    hits = [v for k, v in secs.items() if needle in k]
    return hits[0] if len(hits) == 1 else None


def table_rows(body):
    """markdown 表 → [[单元格, …], …],已去掉表头与分隔行。"""
    rows = []
    for line in (body or "").splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if all(set(c) <= set("-: ") for c in cells):
            continue
        rows.append(cells)
    return rows[1:] if rows else []


def bullets(body):
    return [ln[2:].strip() for ln in (body or "").splitlines()
            if ln.startswith("- ")]


def _labelled(text, labels):
    """把 `标签:内容;标签:内容` 切成 dict。标签缺席即不进 dict(不补空串)。"""
    out, hits = {}, []
    for lab in labels:
        m = re.search(r"\*\*%s\*\*\s*[:：]|(?<![^\s;；。])%s\s*[:：]"
                      % (re.escape(lab), re.escape(lab)), text or "")
        if m:
            hits.append((m.start(), m.end(), lab))
    hits.sort()
    for i, (_s, e, lab) in enumerate(hits):
        end = hits[i + 1][0] if i + 1 < len(hits) else len(text)
        out[lab] = text[e:end].strip().strip(";；").strip()
    return out


# ------------------------------------------------------------ 日报

def daily_facts(text):
    secs = sections(text)
    ccy_body = {}
    for head, body in secs.items():
        m = CCY_IN_HEAD_RE.search(head)
        if m and m.group(1) in CURRENCIES:
            ccy_body[m.group(1)] = body

    overview = {}
    for row in table_rows(find_section(secs, "速览")):
        if len(row) >= 4 and row[0] in CURRENCIES:
            overview[row[0]] = {"trigger": row[1], "basis": row[2],
                                "invalidation": row[3]}

    rings = {}
    for ccy, body in ccy_body.items():
        one = _labelled(body, RING_LABELS)
        judged = _labelled(one.get("分歧与判断", ""), JUDGEMENT_LABELS)
        one.update(judged)
        rings[ccy] = one

    changes = {}
    for line in bullets(find_section(secs, "本期相对上期的变化")):
        m = re.match(r"^([A-Z]{3})\s*[:：]\s*(.*)$", line, re.S)
        if not m or m.group(1) not in CURRENCIES:
            continue
        rest = m.group(2)
        kind = next((k for k in CHANGE_KINDS
                     if rest.startswith("**%s**" % k)), None)
        # `body` 是去掉行首那个粗体标签之后的**同一句话**。展示端把类型做成
        # 了一枚标签,标签与句首连着印就是同一个词说两遍。裁剪放在这里而不是
        # 展示端:裁的是本模块自己刚匹配上的那个前缀,别处没有第二份判断。
        body = rest[len("**%s**" % kind):].lstrip("。.;;、 ") if kind else rest
        changes[m.group(1)] = {"kind": kind, "text": rest, "body": body}

    review_lines = bullets(find_section(secs, "复盘"))
    declaration = next((x for x in review_lines if "到期复盘" in x), None)
    return {
        "summary": bullets(find_section(secs, "执行摘要")),
        "overview": overview,
        "rings": rings,
        "changes": changes,
        "review": {"declaration": declaration,
                   "lines": [x for x in review_lines if x != declaration]},
    }


# ------------------------------------------------------------ 周报

def weekly_facts(text):
    secs = sections(text)
    themes_body = find_section(secs, "本周主线") or ""
    marks = list(THEME_RE.finditer(themes_body))
    themes = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(themes_body)
        body = themes_body[m.end():end]
        title = m.group(2)
        scope = SCOPE_RE.search(title)
        flip = FLIP_RE.search(body)
        themes.append({
            "id": m.group(1),
            "title": SCOPE_RE.sub("", title).strip(),
            "scope": [s.strip() for s in re.split(r"[、,,]", scope.group(1))
                      if s.strip() in CURRENCIES] if scope else [],
            "horizon": flip.group(1) if flip else None,
            "flip": flip.group(2).strip() if flip else None,
        })

    landing = {}
    for row in table_rows(find_section(secs, "各币种一周落点")):
        if len(row) >= 5 and row[0] in CURRENCIES:
            landing[row[0]] = {"theme": row[1], "level": row[2],
                               "call": row[3], "invalidation": row[4]}
    return {"themes": themes, "landing": landing}


# ------------------------------------------------------- 前后对比(只比较)

def deltas(snapshots):
    """每对货币的「上期 → 本期」对比。**只用比较,不做减法**。"""
    out = {}
    for ccy in trend.PAIR_CURRENCIES:
        series = trend.fixing_series(snapshots, ccy)
        bands = [b for b in trend.series_payload(snapshots, [], [])["bands"][ccy]
                 if b["low"] is not None and b["high"] is not None]
        row = {"prior_fixing": None, "latest_fixing": None, "direction": None,
               "prior_band": None, "band": None, "band_move": None,
               "at_high": None, "at_low": None}
        if len(series) >= 1:
            row["latest_fixing"] = {"ref_date": series[-1][0],
                                    "value": series[-1][1]}
        if len(series) >= 2:
            row["prior_fixing"] = {"ref_date": series[-2][0],
                                   "value": series[-2][1]}
            a, b = series[-2][1], series[-1][1]
            row["direction"] = "weak" if b > a else ("strong" if b < a
                                                     else "flat")
        if bands:
            row["band"] = {"low": bands[-1]["low"], "high": bands[-1]["high"]}
            if row["latest_fixing"]:
                v = row["latest_fixing"]["value"]
                row["at_high"] = v >= bands[-1]["high"]
                row["at_low"] = v <= bands[-1]["low"]
        if len(bands) >= 2:
            row["prior_band"] = {"low": bands[-2]["low"],
                                 "high": bands[-2]["high"]}
            hi, phi = bands[-1]["high"], bands[-2]["high"]
            row["band_move"] = "up" if hi > phi else ("down" if hi < phi
                                                     else "flat")
        out[ccy] = row
    return out


# ------------------------------------------------------------ 汇总

def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _latest(dirpath, pattern):
    try:
        names = sorted(n for n in os.listdir(dirpath)
                       if n.endswith(".md") and pattern.match(n[:-3]))
    except OSError:
        return []
    return names


def build(root=ROOT, date=None, week=None):
    dailies = _latest(os.path.join(root, "reports", "daily"), DATE_RE)
    if date:
        dailies = [n for n in dailies if n[:-3] <= date]
    weeklies = _latest(os.path.join(root, "reports", "weekly"), WEEK_RE)
    if week:
        weeklies = [n for n in weeklies if n[:-3] <= week]
    if not dailies:
        raise ValueError("reports/daily/ 下没有可用日报")

    cur = dailies[-1][:-3]
    prior = dailies[-2][:-3] if len(dailies) >= 2 else None
    facts = daily_facts(_read(os.path.join(root, "reports", "daily",
                                           dailies[-1])))
    facts["date"] = cur
    facts["prior_date"] = prior
    facts["currencies"] = list(CURRENCIES)
    facts["change_kinds"] = list(CHANGE_KINDS)
    snapshots, _skipped = trend.load_snapshots(os.path.join(root, "data"),
                                               upto=cur)
    facts["deltas"] = deltas(snapshots)
    if weeklies:
        w = weekly_facts(_read(os.path.join(root, "reports", "weekly",
                                            weeklies[-1])))
        w["week"] = weeklies[-1][:-3]
        facts["week"] = w
    else:
        facts["week"] = None
    return facts


def main(argv=None):
    ap = argparse.ArgumentParser(description="抽取报告要点为 JSON")
    ap.add_argument("--date", help="截止日期 YYYY-MM-DD")
    ap.add_argument("--week", help="截止周号 YYYY-Www")
    ap.add_argument("--root", default=ROOT)
    args = ap.parse_args(argv)
    try:
        payload = build(args.root, args.date, args.week)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2
    print(json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
