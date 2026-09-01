#!/usr/bin/env python3
"""把最新的趋势序列重新嵌进 `reports/trend/fx-trend.html`。

页面是**自包含**的:数据内联在 `<script id="series">` 里,外部只有一处
Google Fonts。这样它才是"一个文件就能搬走"的东西 —— 换一个账号发布时
不必带数据文件、不必配服务、不必改任何路径。

本脚本只做一件事:把那一段 JSON 换成当前的。页面结构与样式一个字符都不动。
数据仍然只有一个来源(`scripts/trend.py --mode series`),页面自己不算数。
"""
import argparse
import json
import os
import re
import sys

try:                                                 # pragma: no cover - 包内分支
    from scripts import trend
except ImportError:                                  # pragma: no cover - 直跑分支
    import trend

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(ROOT, "reports", "trend", "fx-trend.html")
# 开闭标记分开写:用一个正则跨整段贪婪匹配,页面里再出现一个 `</script>`
# 就会把中间所有内容一起吞掉。
OPEN_RE = re.compile(r'(<script id="series" type="application/json">)')
CLOSE = "</script>"


def rebuild(html, payload):
    """把 `payload` 序列化后替换掉页面里那一段 JSON,返回新页面文本。"""
    m = OPEN_RE.search(html)
    if not m:
        raise ValueError("页面里找不到 <script id=\"series\"> 段")
    end = html.index(CLOSE, m.end())
    # `sort_keys=True` 与 `scripts/trend.py --mode series` 的 CLI 输出一致 ——
    # 两处序列化口不同的话,同一份数据会生成两种字节序,"页面有没有变"
    # 就在 git diff 上变成噪声。
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"),
                      sort_keys=True)
    if CLOSE.lower() in text.lower():
        # JSON 里出现 `</script>` 会**提前关闭**这个标签,页面当场散架。
        # 本仓的数据不含 HTML,但"不含"是数据的性质、不是代码的保证。
        raise ValueError("序列里含 </script>,不能直接内联")
    return html[:m.end()] + text + html[end:]


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
    payload = trend.series_payload(
        snapshots, trend.load_decisions(args.decision_log, upto=args.date),
        trend.load_digests(args.state_dir), skipped)
    with open(args.page, encoding="utf-8") as f:
        html = f.read()
    with open(args.page, "w", encoding="utf-8") as f:
        f.write(rebuild(html, payload))
    print("已刷新 %s(%d 份日度读数,截至 %s)"
          % (args.page, len(snapshots), snapshots[-1][0]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
