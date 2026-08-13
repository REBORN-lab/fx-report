"""fx-verdict-enforcement 变异电池 —— Design Doc §7 的 10 条靶点 + BOUND 一条。

在**仓库根目录**运行:python3 docs/superpowers/evidence/2026-08-13-fx-verdict-mutations.py

自带三道自检,每一条都来自上一个 change 的实际事故:
1. **基线自检** —— 基线不绿就拒跑并非零退出。一次超时留下的变异体让
   「15/15 KILLED」全部为假杀。
2. **逐字节校验** —— 变异体应用后校验落盘内容与预期逐字节相同,还原后
   校验与原文逐字节相同。写坏或没写进去必须就地炸,不能悄悄跑完。
3. **STALE 硬失败** —— 靶点原文与源码不匹配(0 处或多处)时非零退出。
   归档电池曾在干净副本上只有 26/35,9 个陈旧靶点静默 PATCH-FAIL 却退出 0。

汇总行格式:KILLED k / 执行 n / 登记 m。三者不相等即非零退出。

M11(BOUND)由 T7 代码质量复审移交,计划里没有:「在文件尾部追加内容,
喂饱段级断言」是本仓库同型缺陷最新的一种伪装 —— 段级正则若贪婪到 EOF
(`.*\\Z`),尾部追加任何一节都会被吞进该段,于是「本段丢了某关键串」的
断言可被后加的无关内容喂饱。故变异对象是 **Markdown 文档**而非 .py,
备份/还原集合与逐字节校验一并覆盖它。
"""
import os
import subprocess
import sys

C = "scripts/check_report.py"
D = "scripts/collect/derive.py"
V = "scripts/verdicts.py"
# M11 的变异对象是文档而非源码。它同样要进备份/还原集合,还原校验同样逐字节。
S = "skills/fx-daily-report/SKILL.md"
FILES = (C, D, V, S)

M = [
    ("M1 空串放行", C,
     "            if not s.strip():",
     "            if s is None:"),
    ("M2 in 方向写反", C,
     "            if s not in report:",
     "            if report not in s:"),
    # M3 锚点已在 T6b 随 check_daily 重写而变更(旧锚点 derived.get("events")
    # 内联传参,现改为局部变量 events)。协调者于 T8 前置复验时实测 0 处匹配
    # 并按当前源码校正;勿凭记忆改回。
    ("M3 日报侧根本不查", C,
     "    found, skipped = check_verdicts(report, events,",
     "    found, skipped = check_verdicts(report, None,"),
    ("M4 三类只查一类", C,
     '                (digest.get("events"), VERDICT_FIELDS_EVENTS, "digest.events"),\n'
     '                (digest.get("rates"), VERDICT_FIELDS_RATES, "digest.rates")):',
     '                (digest.get("events"), ("articles_verdict",), "digest.events"),):'),
    ("M5 schema 闸门反向", C,
     "              and ver >= DERIVED_VERDICT_SCHEMA)",
     "              and ver < DERIVED_VERDICT_SCHEMA)"),
    ("M6 只查第一个币种", C,
     "    for c in CURRENCIES:\n        if c not in covered:",
     "    for c in CURRENCIES[:1]:\n        if c not in covered:"),
    ("M7 覆盖让位失效", C,
     "        if c not in covered:\n            continue",
     "        if False:\n            continue"),
    ("M8 join_verdict 空括号", V,
     "    if not caveats:\n        return head",
     "    if False:\n        return head"),
    ("M9 非字符串未拦住", C,
     "            if not isinstance(s, str):",
     "            if isinstance(s, str) and False:"),
    ("M10 未给 digest 仍校验", C,
     "    if isinstance(digest, dict):\n"
     "        # 与日报的 GAP_OMITTED 对称",
     "    if digest is None or isinstance(digest, dict):\n"
     "        # 与日报的 GAP_OMITTED 对称"),
    # M11:BOUND —— 删掉违规节里真正那一条 bullet,同时在文件尾部追加一节,
    # 内容含 `VERDICT_NOT_QUOTED` 与 `改报告`。日报违规节眼下正好是文件最后
    # 一节,所以锚点从那条 bullet 一路取到 EOF,一次替换即完成「删 + 追加」。
    # 当前 DAILY_VIOLATION_RE 是有界写法(`.*?` 到 `\n\n` 或 `\Z`),追加的一节
    # 被空行挡在段外 → 应当 KILLED;若改成贪婪到 EOF 的 `.*\Z`,追加的一节会
    # 被吞进段内把断言喂饱 → 会 SURVIVED。
    ("M11 尾部追加喂饱段级断言", S,
     "- `VERDICT_NOT_QUOTED`:报告未逐字引用结论句 → **改报告**,把违规信息里\n"
     "  「期望原文」那一句整句抄进该币种节,一个字符都不改。\n"
     "- `VERDICT_ABSENT` / `VERDICT_EMPTY` / `VERDICT_MALFORMED` /\n"
     "  `VERDICT_ENTRY_MISSING` / `VERDICT_CONTAINER_MALFORMED`:快照里该有的结论句\n"
     "  缺失、为空、类型不对,或条目/容器不成形 → **这几条是脚本缺陷,改报告没用**;\n"
     "  重跑第 1 步采集,仍复现就报 bug。\n",
     "- `VERDICT_ABSENT` / `VERDICT_EMPTY` / `VERDICT_MALFORMED` /\n"
     "  `VERDICT_ENTRY_MISSING` / `VERDICT_CONTAINER_MALFORMED`:快照里该有的结论句\n"
     "  缺失、为空、类型不对,或条目/容器不成形 → **这几条是脚本缺陷,改报告没用**;\n"
     "  重跑第 1 步采集,仍复现就报 bug。\n"
     "\n"
     "## 附录:违规码速查\n"
     "\n"
     "- `VERDICT_NOT_QUOTED` → **改报告**\n"),
]

missing = [p for p in FILES if not os.path.exists(p)]
if missing:
    print("必须在仓库根目录运行;找不到:%s" % ", ".join(missing))
    raise SystemExit(2)

orig = {}
for p in FILES:
    with open(p, encoding="utf-8") as f:
        orig[p] = f.read()
env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")


def write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def suite():
    # 清 pyc 是硬要求:同长度替换后 .pyc 复用曾骗过审查者一次
    subprocess.run("find . -name __pycache__ -type d -exec rm -rf {} +",
                   shell=True, capture_output=True)
    return subprocess.run([sys.executable, "-m", "unittest", "discover",
                           "-s", "tests", "-t", "."],
                          capture_output=True, text=True, env=env)


base = suite()
if base.returncode:
    print("BASELINE 不干净,拒绝跑电池(不绿时的 KILLED 全是假杀):")
    print("\n".join(l for l in base.stderr.splitlines()
                    if l.startswith(("FAIL: ", "ERROR: "))))
    raise SystemExit(1)
print("BASELINE OK — %s\n" % base.stderr.strip().splitlines()[-3])

killed = executed = 0
stale = []
try:
    for name, path, old, new in M:
        hits = orig[path].count(old)
        if hits != 1:
            stale.append(name)
            print("%-9s %-26s (匹配 %d 处)" % ("STALE", name, hits))
            continue
        want = orig[path].replace(old, new, 1)
        write(path, want)
        assert read(path) == want, "变异未逐字节落盘:" + path
        run = suite()
        write(path, orig[path])
        assert read(path) == orig[path], "还原未逐字节复原:" + path
        fails = sorted({l.split(" ")[1] for l in run.stderr.splitlines()
                        if l.startswith(("FAIL: ", "ERROR: "))})
        outcome = "KILLED" if run.returncode else "SURVIVED"
        killed += outcome == "KILLED"
        executed += 1
        print("%-9s %-26s %s" % (outcome, name, ", ".join(fails[:2])[:58]))
finally:
    for p, text in orig.items():
        write(p, text)
    subprocess.run("find . -name __pycache__ -type d -exec rm -rf {} +",
                   shell=True, capture_output=True)

print("\nKILLED %d / 执行 %d / 登记 %d" % (killed, executed, len(M)))
if stale:
    print("靶点已失效(原文与源码不匹配),必须重写或删除:%s" % ", ".join(stale))
    raise SystemExit(1)
if killed != executed:
    raise SystemExit(1)
