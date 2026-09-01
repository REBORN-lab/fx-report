#!/usr/bin/env python3
"""把最新的趋势序列与报告要点重新嵌进 `reports/trend/fx-trend.html`。

页面是**自包含**的:数据内联在 `<script id="series">` 里,外部只有一处
Google Fonts。这样它才是"一个文件就能搬走"的东西 —— 换一个账号发布时
不必带数据文件、不必配服务、不必改任何路径。

本脚本只做一件事:把两段内联 JSON 换成当前的 —— `series`(定盘/利率/复盘
序列,出自 `scripts/trend.py`)与 `facts`(报告要点,出自 `scripts/highlights.py`)。
页面结构与样式一个字符都不动,页面自己不算数、也不重述任何一句话。
"""
import argparse
import json
import os
import re
import sys

try:                                                 # pragma: no cover - 包内分支
    from scripts import highlights, trend
except ImportError:                                  # pragma: no cover - 直跑分支
    import highlights
    import trend

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(ROOT, "reports", "trend", "fx-trend.html")
# 开闭标记分开写:用一个正则跨整段贪婪匹配,页面里再出现一个 `</script>`
# 就会把中间所有内容一起吞掉。
OPEN_FMT = '<script id="%s" type="application/json">'
CLOSE = "</script>"
BLOCKS = ("series", "facts")


def rebuild(html, block_id, payload):
    """把 `payload` 序列化后替换掉页面里 `block_id` 那一段 JSON。"""
    head = OPEN_FMT % block_id
    start = html.find(head)
    if start < 0:
        raise ValueError("页面里找不到 <script id=\"%s\"> 段" % block_id)
    open_end = start + len(head)
    close_at = html.index(CLOSE, open_end)
    # `sort_keys=True` 与 `scripts/trend.py --mode series` 的 CLI 输出一致 ——
    # 两处序列化口不同的话,同一份数据会生成两种字节序,"页面有没有变"
    # 就在 git diff 上变成噪声。
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"),
                      sort_keys=True)
    if CLOSE.lower() in text.lower():
        # JSON 里出现 `</script>` 会**提前关闭**这个标签,页面当场散架。
        # 报告正文不含 HTML,但"不含"是数据当下的性质、不是代码的保证 ——
        # 而这一段内联的是**报告里的句子**,它的字符集不由本仓决定。
        raise ValueError("载荷里含 </script>,不能直接内联")
    return html[:open_end] + text + html[close_at:]


def main(argv=None):
    ap = argparse.ArgumentParser(description="刷新趋势页内联的序列数据")
    ap.add_argument("--date", help="截止日期 YYYY-MM-DD(默认取全部快照)")
    ap.add_argument("--page", default=PAGE)
    ap.add_argument("--data-dir", default=os.path.join(ROOT, "data"))
    ap.add_argument("--state-dir", default=os.path.join(ROOT, "state"))
    ap.add_argument("--decision-log",
                    default=os.path.join(ROOT, "state", "decision-log.jsonl"))
    args = ap.parse_args(argv)

    snapshots, skipped = trend.load_snapshots(args.data_dir, upto=args.date)
    for s in skipped:
        print("跳过 %s" % s, file=sys.stderr)
    if not snapshots:
        print("没有可读快照", file=sys.stderr)
        return 2
    payloads = {
        "series": trend.series_payload(
            snapshots, trend.load_decisions(args.decision_log, upto=args.date),
            trend.load_digests(args.state_dir), skipped),
        "facts": highlights.build(ROOT, date=args.date),
    }
    with open(args.page, encoding="utf-8") as f:
        html = f.read()
    for block in BLOCKS:
        html = rebuild(html, block, payloads[block])
    with open(args.page, "w", encoding="utf-8") as f:
        f.write(html)
    print("已刷新 %s(%d 份日度读数,截至 %s;要点取自 %s 那份日报)"
          % (args.page, len(snapshots), snapshots[-1][0],
             payloads["facts"]["date"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
