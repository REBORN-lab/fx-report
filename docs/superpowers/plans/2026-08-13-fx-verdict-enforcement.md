---
change: fx-verdict-enforcement
design-doc: docs/superpowers/specs/2026-08-13-fx-verdict-enforcement-design.md
base-ref: 799f3f75c1dcae00e67d92e301a9ea2e3a2b7f4a
---

# 结论句强制引用 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让脚本算好的结论句具备强制力 —— 报告改一个字符、或整句缺失,校验器必须失败;日报与周报共用同一份判定。

**Architecture:** 新增**一个核心谓词** `check_report.check_verdicts(report, container, fields, covered, required, label)`,只认 `{币种: {字段: 句子}}` 的两层 dict;`check_daily` 与 `check_weekly` 只提供「到哪个容器取哪些字段」,判定逻辑全仓只有一份(与 `events.landed_count_capped`、`scripts/fixings.py` 同构)。日报侧由 `derive` 落一条同构的 `events_verdict`,并把 `derive.SCHEMA_VERSION` 升到 2 作为存量快照闸门。结论句的**拼装**(head 与 caveat 怎么连)抽成新模块 `scripts/verdicts.py:join_verdict`,**判定不共享** —— 周报的定义域是跨日统计,日报是单日事实。

**Tech Stack:** Python 标准库 only(`argparse`/`json`/`re`/`unittest`/`unittest.mock`);零新增依赖、零 API key;测试不打真实网络(需要 HTTP 时用 `tests/helpers.py:FixtureServer`)。

## 全局约束(每个任务都适用,不再重复)

**TDD 模式 `tdd_mode: tdd`**:每个任务都是「先写会红的测试 → 跑它确认红 → 最小实现 → 跑它确认绿 → 提交」。**禁止先改代码后补测试** —— 上一个 change 的七轮审查里「修复本身零覆盖」被单列成 Critical **四次**,每一次的根因都是这个顺序反了。

**全量回归命令(每处都写全,不许简写)**:

```bash
find . -name __pycache__ -type d -exec rm -rf {} +
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -t .
```

清 `__pycache__` 是硬要求:同长度替换后 `.pyc` 复用曾骗过审查者一次。

**基线**:`Ran 554 tests` / `OK`(2026-08-13 实测)。本计划里出现的任何测试计数都是**预期值**;执行时以实跑输出为准,跑出不符就逐字更正入档,不得静默改。

**仓库硬约束**:零 API key;Python 标准库 only;报告中文。**防编造纪律**:缺输入写 `null` 不写 `0`;访问外部数据前先 `isinstance` 门;`bool` 排除在数值比较之外;JSON 的 `except` 元组含 `RecursionError`;落盘走 `.tmp` + `os.replace` 原子替换;采集层异常转 gap,绝不上抛。

**提交约定**:每个任务验收后立刻勾选 `openspec/changes/fx-verdict-enforcement/tasks.md` 的对应项并 `git commit`,**不得积攒**。勾选用文件编辑工具做定向替换(把该行的 `- [ ]` 改成 `- [x]`),然后验证:

```bash
bash ~/.claude/skills/super-coding/scripts/super-coding-state.sh task-checkoff \
  openspec/changes/fx-verdict-enforcement/tasks.md "<该 task 的唯一文本>"
```

**禁止**写「同一表达式里对同一文件先开写模式再读」的代码 —— 写模式先求值会清空文件(该事故已发生两次)。commit message 用中文,末尾带:

```
Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
```

## 文件结构

| 文件 | 责任 | 动作 |
|---|---|---|
| `scripts/verdicts.py` | 结论句的**唯一拼装口** `join_verdict(head, caveats)`;只此一个函数 | 创建 |
| `scripts/check_report.py` | 核心谓词 `check_verdicts` + 四个违规码 + 三个字段名常量 + 两个调用点 + 跳过声明 | 修改 |
| `scripts/collect/derive.py` | `_events_verdict` + `events_verdict` 落盘;`SCHEMA_VERSION` 1→2;同步 `EMPTY_EVENTS_DERIVED` | 修改 |
| `scripts/weekly_digest.py` | `_verdict` / `_fixings_verdict` 的拼装改经 `join_verdict`,**判定一行不改** | 修改 |
| `skills/fx-daily-report/SKILL.md` | 事件结论改为逐字引用 `events_verdict`,删掉按布尔拼话术的段落 | 修改 |
| `skills/fx-weekly-report/SKILL.md` | 三类 verdict 的引用规则写明「整句逐字 + 精确子串包含」 | 修改 |
| `tests/test_verdicts.py` | `join_verdict` 单测 + weekly_digest 接线测试 | 创建 |
| `tests/test_skill_docs.py` | SKILL 文档哨兵(四处同步少一处即漂移,而文档漂移没有任何单测会发现) | 创建 |
| `tests/test_check_report.py` | 核心谓词三态/两道让位、周报三类、日报 schema 闸门、CLI 开关冻结 | 修改 |
| `tests/test_derive.py` | `events_verdict` 内容与键集哨兵;`schema_version` 断言改 2 | 修改 |
| `tests/test_snapshot.py` | `derived.schema_version` 断言改 2 | 修改 |
| `reports/weekly/2026-W33.md` | 与重算后的 digest 配对,重生成 | 修改 |
| `docs/superpowers/evidence/2026-08-13-fx-verdict-mutations.py` | 变异电池(自带基线自检 / 逐字节校验 / STALE 硬失败) | 创建 |

**不做**(Design Doc §2 非目标,不要顺手加):日报侧 `rates` 与 `real_rate` 的结论句;采集层数值精度统一;被滤域名落盘;任何形式的「历史产物豁免」开关。

---

## Task 1:`scripts/verdicts.py` —— 结论句的唯一拼装口

对应 tasks.md **2.5(前半)**。

**Files:**
- Create: `scripts/verdicts.py`
- Create: `tests/test_verdicts.py`

- [x] **T1 Step 1: 写会红的测试**

创建 `tests/test_verdicts.py`,内容为:

```python
"""结论句拼装口(Design Doc §4:共享拼装,不共享判定)。"""
import unittest

from scripts.verdicts import join_verdict


class JoinVerdictTest(unittest.TestCase):
    """会漂移的是措辞与连接方式,不是判定 —— 所以抽出来的只有这一层。"""

    def test_no_caveats_returns_head_unchanged(self):
        """空括号是最明显的漂移入口:「区间内至少 3 条()」会让读者无从判断
        是脚本漏填了,还是确实没有任何观测缺口 —— 而后者是最强的一条结论。"""
        self.assertEqual(join_verdict("区间内至少 3 条", []), "区间内至少 3 条")

    def test_empty_tuple_also_returns_head(self):
        self.assertEqual(join_verdict("当日未采到事件", ()), "当日未采到事件")

    def test_single_caveat_wrapped_in_parens(self):
        self.assertEqual(join_verdict("区间内至少 3 条", ["1/5 天未采到"]),
                         "区间内至少 3 条(1/5 天未采到)")

    def test_multiple_caveats_joined_with_ideographic_comma(self):
        self.assertEqual(
            join_verdict("区间内至少 3 条",
                         ["1/5 天未采到", "2 天顶到当日采集上限"]),
            "区间内至少 3 条(1/5 天未采到、2 天顶到当日采集上限)")

    def test_parens_follow_the_repo_convention(self):
        """括号沿用仓库既有写法 —— 实测真实 digest 的 articles_verdict、
        weekly_digest._verdict 的输出、tests/test_weekly_digest.py 的期望串
        三者的括号都是 ASCII 0x28/0x29,分隔符是全角顿号 0x3001。
        整句包含检查是逐字节的,换成全角括号会让同一条结论在两处不相等,
        而 Task 2 的硬要求正是「输出与重构前逐字节相同」。"""
        got = join_verdict("头", ["尾甲", "尾乙"])
        self.assertEqual(got, "头(尾甲、尾乙)")
        self.assertEqual([hex(ord(c)) for c in got if c in "()（）、"],
                         ["0x28", "0x3001", "0x29"])

    def test_byte_identical_with_the_existing_weekly_wording(self):
        """地面事实锚点:同样的 head 与 caveat,拼装口的输出必须与
        weekly_digest._verdict 重构前的输出逐字节相同。这条用例存在的意义
        是——括号宽度这类差异肉眼看不出来,只有逐字节比对能抓住。
        此刻 weekly_digest 还不含 join_verdict,故这是跨模块的地面事实
        比对,不存在自我循环。"""
        from scripts import weekly_digest as wd
        stats = {"days_collected": 2, "undated": 0, "capped_days": 0,
                 "daily_cap": None, "outside_window": 0, "in_window": 3,
                 "malformed": 0}
        self.assertEqual(join_verdict("区间内至少 3 条", ["3/5 天未采到"]),
                         wd._verdict(stats, 5, 0, "事件"))


if __name__ == "__main__":
    unittest.main()
```

- [x] **T1 Step 2: 跑测试确认失败**

```bash
find . -name __pycache__ -type d -exec rm -rf {} +
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_verdicts -v
```

Expected: 收集阶段即报 `ModuleNotFoundError: No module named 'scripts.verdicts'`(5 个用例一个都跑不起来)。

- [x] **T1 Step 3: 最小实现**

创建 `scripts/verdicts.py`:

```python
"""结论句的唯一拼装口:head 与 caveat 列表怎么连,只有这一处说了算。

**共享拼装,不共享判定。** 周报的判定输入是跨日统计(days_collected /
window_days / in_window),日报是单日事实(count / count_capped /
sample_capped / channel_changed_from);两者定义域不同,强行复用判定正是
`_entry_of` 读 rates 却被用于 events 那类事故的成因(上一个 change 第四轮)。
会漂移的只有措辞与连接方式,抽出来的也只有这一层。

先例:scripts/fixings.py 已为采集层与周度聚合器共用。
"""


def join_verdict(head, caveats):
    """head 与 caveat 列表的唯一拼装口。

    caveats 为空时**不得拼出空括号**:「区间内至少 3 条()」会把"没有任何
    观测缺口"这条最强的结论渲染成一个像是漏填的括号。

    括号沿用仓库既有写法(ASCII 0x28/0x29),分隔符用全角顿号(0x3001)——
    整句包含检查是逐字节的,任何一处改宽度都会让同一条结论在两处不相等。
    """
    if not caveats:
        return head
    return "%s(%s)" % (head, "、".join(caveats))
```

- [x] **T1 Step 4: 跑测试确认通过**

```bash
find . -name __pycache__ -type d -exec rm -rf {} +
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_verdicts -v
```

Expected: `OK`,`Ran 6 tests`。

- [x] **T1 Step 5: 勾选并提交**

把 `openspec/changes/fx-verdict-enforcement/tasks.md` 里 `- [ ] 2.5` 那一行的 `- [ ]` 改成 `- [x]`(该 task 同时覆盖 Task 2,两个任务都完成后再勾;本步先只提交代码)。

```bash
git add scripts/verdicts.py tests/test_verdicts.py
git commit -m "feat(verdicts): 结论句唯一拼装口 join_verdict(无 caveat 不拼空括号)

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 2:`weekly_digest` 的两个 verdict 函数改经 `join_verdict`

对应 tasks.md **2.5(后半)**。**判定逻辑一行不改**,输出必须与重构前逐字节相同。

**Files:**
- Modify: `scripts/weekly_digest.py`(import 段;`_fixings_verdict` 第 66-70 行;`_verdict` 第 476 行)
- Modify: `tests/test_verdicts.py`

- [x] **T2 Step 1: 写会红的测试**

在 `tests/test_verdicts.py` 的 `if __name__` **之前**插入(同时把文件顶部的 import 段补成下面这样):

```python
"""结论句拼装口(Design Doc §4:共享拼装,不共享判定)。"""
import unittest
from unittest import mock

from scripts import weekly_digest as wd
from scripts.verdicts import join_verdict
```

新增两个类:

```python
class WeeklyRoutesThroughJoinVerdictTest(unittest.TestCase):
    """周报两个 verdict 函数必须经同一个拼装口。各写一遍括号与顿号,
    迟早漂移成两种写法,而整句包含检查是逐字节的。"""

    STATS = {"days_collected": 2, "undated": 0, "capped_days": 0,
             "daily_cap": None, "outside_window": 0, "in_window": 3,
             "malformed": 0}

    def test_verdict_uses_join_verdict(self):
        with mock.patch.object(wd, "join_verdict", return_value="SENTINEL") as m:
            got = wd._verdict(dict(self.STATS), 5, 0, "事件")
        self.assertEqual(got, "SENTINEL")
        m.assert_called_once()
        self.assertEqual(m.call_args[0][0], "区间内至少 3 条")
        self.assertEqual(m.call_args[0][1], ["3/5 天未采到"])

    def test_fixings_verdict_uses_join_verdict(self):
        with mock.patch.object(wd, "join_verdict", return_value="SENTINEL") as m:
            got = wd._fixings_verdict(3, 2, None, None, 0, 5, 0)
        self.assertEqual(got,
                         "SENTINEL;周区间是这些价位的高低,不是区间内的真实极值")
        self.assertEqual(m.call_args[0][0],
                         "区间内观测到 3 个不同价位,实际定盘次数只多不少")
        self.assertEqual(m.call_args[0][1], ["2 次观测的定盘日未记录"])


class RefactorIsByteIdenticalTest(unittest.TestCase):
    """判定一行不改 —— 两个函数的输出必须与重构前逐字节相同。
    本类在重构前后都应为绿,它是安全网不是红灯。"""

    def test_verdict_output_unchanged(self):
        stats = {"days_collected": 2, "undated": 0, "capped_days": 0,
                 "daily_cap": None, "outside_window": 0, "in_window": 3,
                 "malformed": 0}
        self.assertEqual(wd._verdict(stats, 5, 0, "事件"),
                         "区间内至少 3 条(3/5 天未采到)")

    def test_verdict_without_caveats_has_no_parens(self):
        stats = {"days_collected": 5, "undated": 0, "capped_days": 0,
                 "daily_cap": None, "outside_window": 0, "in_window": 3,
                 "malformed": 0}
        self.assertEqual(wd._verdict(stats, 5, 0, "事件"), "区间内至少 3 条")

    def test_fixings_verdict_output_unchanged(self):
        self.assertEqual(
            wd._fixings_verdict(3, 2, None, None, 0, 5, 0),
            "区间内观测到 3 个不同价位,实际定盘次数只多不少(2 次观测的定盘日未记录);"
            "周区间是这些价位的高低,不是区间内的真实极值")

    def test_fixings_verdict_no_caveat_branch_unchanged(self):
        self.assertEqual(
            wd._fixings_verdict(2, 0, "2026-08-10", "2026-08-11", 0, 2, 0),
            "区间内 2 次不同定盘(2026-08-10 至 2026-08-11)")
```

- [x] **T2 Step 2: 跑测试确认失败**

```bash
find . -name __pycache__ -type d -exec rm -rf {} +
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_verdicts -v
```

Expected: `WeeklyRoutesThroughJoinVerdictTest` 的 2 个用例 ERROR,报 `AttributeError: <module 'scripts.weekly_digest'> does not have the attribute 'join_verdict'`;`RefactorIsByteIdenticalTest` 的 4 个用例已经是 PASS(安全网),`JoinVerdictTest` 6 个 PASS(Task 1 修复轮追加了逐字节锚点用例)。

- [x] **T2 Step 3: 实现 —— 三处编辑**

3a. `scripts/weekly_digest.py` 第 25 行 `from scripts.fixings import distinct_fixings, num as _num` **之后**加一行:

```python
from scripts.verdicts import join_verdict
```

3b. `_fixings_verdict` 的结尾(现第 66-70 行),把

```python
    if caveats:
        return ("区间内观测到 %d 个不同价位,实际定盘次数只多不少(%s);"
                "周区间是这些价位的高低,不是区间内的真实极值"
                % (n, "、".join(caveats)))
    return "区间内 %d 次不同定盘(%s 至 %s)" % (n, first_ref, last_ref)
```

改为

```python
    if caveats:
        # 只把 head(caveats) 这一段交给拼装口;分号后那句是本函数自己的尾巴
        return (join_verdict("区间内观测到 %d 个不同价位,实际定盘次数只多不少" % n,
                             caveats)
                + ";周区间是这些价位的高低,不是区间内的真实极值")
    return "区间内 %d 次不同定盘(%s 至 %s)" % (n, first_ref, last_ref)
```

3c. `_verdict` 的 `in_window` 分支(现第 474-476 行),把

```python
    if stats["in_window"]:
        head = "区间内至少 %d 条" % stats["in_window"]
        return head if not caveats else "%s(%s)" % (head, "、".join(caveats))
```

改为

```python
    if stats["in_window"]:
        head = "区间内至少 %d 条" % stats["in_window"]
        return join_verdict(head, caveats)
```

**不要动** `_verdict` 的其余三个 return(第 418、478、479 行):它们不是 `head(caveats)` 形态,硬套拼装口会改变输出。

- [x] **T2 Step 4: 跑测试确认通过**

```bash
find . -name __pycache__ -type d -exec rm -rf {} +
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_verdicts tests.test_weekly_digest -v 2>&1 | tail -5
```

Expected: `OK`。`tests.test_weekly_digest` 里既有的 `VerdictTest` / `VerdictInvariantTest` / `VerdictDomainTest` / `FixingsVerdictTest` 全部保持绿 —— 它们断言的是逐字原文,是这次重构最强的安全网。任一变红说明输出被改了,按 `systematic-debugging` 定位,**不要改断言**。

- [x] **T2 Step 5: 勾选并提交**

把 tasks.md 里 `- [ ] 2.5 新建 \`scripts/verdicts.py\`` 那一行改成 `- [x] 2.5 ...`,然后:

```bash
bash ~/.claude/skills/super-coding/scripts/super-coding-state.sh task-checkoff \
  openspec/changes/fx-verdict-enforcement/tasks.md "新建 \`scripts/verdicts.py\`"
git add scripts/weekly_digest.py tests/test_verdicts.py openspec/changes/fx-verdict-enforcement/tasks.md
git commit -m "refactor(digest): 两个 verdict 函数改经 join_verdict,判定与输出逐字节不变

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 3:核心谓词 `check_verdicts` + 三个字段名常量

对应 tasks.md **1.1 / 1.3 / 1.5**。本任务只建谓词与常量,**还不接线**(接线在 Task 4 与 Task 6)。

**Files:**
- Modify: `scripts/check_report.py`(常量区第 22 行后;函数插在 `def check_daily(` 之前)
- Modify: `tests/test_check_report.py`(追加到文件末尾)

- [x] **T3 Step 1: 写会红的测试**

在 `tests/test_check_report.py` **文件末尾**追加:

```python
class CheckVerdictsCoreTest(unittest.TestCase):
    """核心谓词的三态与两道让位。日报与周报共用这一份判定,两处各写一遍
    必然漂移(见 scripts/fixings.py 的模块注释)。

    delta spec 场景:结论句被改动一个字 / 结论句整句缺失 / 结论句为空串 /
    报告未覆盖某币种 / 基准货币在定盘容器中无条目。"""

    FIELDS = ("articles_verdict",)

    def _run(self, report, container, required=True, covered=None):
        return check_report.check_verdicts(
            report, container, self.FIELDS,
            set(check_report.CURRENCIES) if covered is None else covered,
            required, "digest.events")

    def test_quoted_sentence_passes(self):
        s = "区间内至少 26 条(3/6 天未采到)"
        got = self._run("前言。%s。后话。" % s, {"USD": {"articles_verdict": s}})
        self.assertEqual(got, ([], 0))

    def test_one_character_changed_is_not_quoted(self):
        s = "区间内至少 26 条(3/6 天未采到)"
        v, _ = self._run(s.replace("26", "15"), {"USD": {"articles_verdict": s}})
        self.assertTrue(any(x.startswith("VERDICT_NOT_QUOTED") and "USD" in x
                            for x in v), v)

    def test_expected_sentence_is_echoed_in_the_violation(self):
        """违规信息必须给出期望的整句原文,否则报告作者无从修。"""
        s = "区间内至少 26 条(3/6 天未采到)"
        v, _ = self._run("完全无关的正文", {"USD": {"articles_verdict": s}})
        self.assertTrue(any(s in x for x in v), v)

    def test_whole_sentence_absent_is_not_quoted(self):
        """数字词袋放行的正是这一形态:26、3、6 都在别处出现过。"""
        s = "区间内至少 26 条(3/6 天未采到)"
        v, _ = self._run("正文写了 26 与 3 与 6,但没有整句",
                         {"USD": {"articles_verdict": s}})
        self.assertTrue(any("VERDICT_NOT_QUOTED" in x for x in v), v)

    def test_empty_string_is_a_violation_not_a_pass(self):
        """任意报告都"包含"空串 —— 最直接的假绿入口。"""
        for bad in ("", "   ", "　", "\n\t "):
            v, skipped = self._run("任意报告", {"USD": {"articles_verdict": bad}})
            self.assertTrue(any("VERDICT_EMPTY" in x for x in v), (repr(bad), v))
            self.assertEqual(skipped, 0)

    def test_non_string_is_malformed_and_does_not_crash(self):
        for bad in ({"a": 1}, 7, ["x"], True, 1.5):
            v, _ = self._run("任意报告", {"USD": {"articles_verdict": bad}})
            self.assertTrue(any("VERDICT_MALFORMED" in x for x in v), (bad, v))

    def test_absent_field_when_required_is_a_violation(self):
        v, skipped = self._run("任意报告", {"USD": {}}, required=True)
        self.assertTrue(any("VERDICT_ABSENT" in x and "USD" in x for x in v), v)
        self.assertEqual(skipped, 0)

    def test_none_value_counts_as_absent(self):
        v, _ = self._run("任意报告", {"USD": {"articles_verdict": None}},
                         required=True)
        self.assertTrue(any("VERDICT_ABSENT" in x for x in v), v)

    def test_absent_field_when_not_required_is_counted_not_reported(self):
        """存量快照:跳过,但必须被计数 —— 「跳过」与「通过」不可同形。"""
        v, skipped = self._run("任意报告", {"USD": {}}, required=False)
        self.assertEqual(v, [])
        self.assertEqual(skipped, 1)

    def test_currency_not_covered_by_report_is_skipped(self):
        """让位 ①:已有 SECTION_MISSING / CURRENCY_MISSING,同一处缺失
        不得产生两条违规。"""
        got = self._run("报告只写了 EUR", {"USD": {}}, required=True,
                        covered={"EUR"})
        self.assertEqual(got, ([], 0))

    def test_currency_absent_from_container_is_legal(self):
        """让位 ②:digest["rates"] 没有 USD 是合法形态(基准货币无定盘价),
        不是缺字段;只有币种条目存在时才要求其字段齐全。"""
        got = self._run("任意报告", {"PHP": {"articles_verdict": "任意报告"}},
                        required=True, covered={"USD", "PHP"})
        self.assertEqual(got, ([], 0))

    def test_non_dict_container_is_skipped(self):
        for bad in (None, [], "x", 7, True):
            self.assertEqual(self._run("任意报告", bad), ([], 0))

    def test_non_dict_entry_is_skipped(self):
        for bad in ("not a dict", 7, [], None):
            self.assertEqual(self._run("任意报告", {"USD": bad}), ([], 0))

    def test_every_currency_is_checked_not_just_the_first(self):
        """只查 next(iter(container)) 的变异必须被杀 —— 错的是最后一个币种。"""
        good = "区间内至少 3 条"
        container = {c: {"articles_verdict": good}
                     for c in check_report.CURRENCIES}
        container["BRL"]["articles_verdict"] = "区间内至少 9 条"
        v, _ = self._run(good, container)
        self.assertTrue(any("VERDICT_NOT_QUOTED" in x and "BRL" in x for x in v), v)

    def test_all_fields_in_the_tuple_are_checked(self):
        """fields 元组少一项的变异必须被杀。"""
        container = {"USD": {"articles_verdict": "甲句", "official_verdict": "乙句"}}
        v, _ = check_report.check_verdicts(
            "正文只有甲句", container, check_report.VERDICT_FIELDS_EVENTS,
            {"USD"}, True, "digest.events")
        self.assertTrue(any("official_verdict" in x for x in v), v)
        self.assertFalse([x for x in v if "articles_verdict" in x], v)


class VerdictFieldConstantsTest(unittest.TestCase):
    """字段名 SHALL 显式枚举,MUST NOT 按名字模式搜集 —— digest 顶层的
    `verdicts` 是计数 dict、`verdict_details` 是 list,模式匹配会把非字符串
    结构送进字符串比对。"""

    def test_constants_are_explicit_tuples(self):
        self.assertEqual(check_report.VERDICT_FIELDS_EVENTS,
                         ("articles_verdict", "official_verdict"))
        self.assertEqual(check_report.VERDICT_FIELDS_RATES, ("fixings_verdict",))
        self.assertEqual(check_report.VERDICT_FIELD_DAILY, ("events_verdict",))

    def test_counting_structures_are_not_enumerated(self):
        every = (check_report.VERDICT_FIELDS_EVENTS
                 + check_report.VERDICT_FIELDS_RATES
                 + check_report.VERDICT_FIELD_DAILY)
        self.assertNotIn("verdicts", every)
        self.assertNotIn("verdict_details", every)

    def test_counting_dict_fed_to_the_predicate_is_inert(self):
        """把 digest 顶层的计数 dict 直接喂进核心谓词也不能崩或误报。"""
        v, skipped = check_report.check_verdicts(
            "任意报告", {"命中": 0, "未命中": 0, "无法判定": 15},
            check_report.VERDICT_FIELDS_EVENTS,
            set(check_report.CURRENCIES), True, "digest.verdicts")
        self.assertEqual((v, skipped), ([], 0))

    def test_detail_list_fed_to_the_predicate_is_inert(self):
        v, skipped = check_report.check_verdicts(
            "任意报告", [{"date": "2026-08-10", "verdict": "命中"}],
            check_report.VERDICT_FIELDS_EVENTS,
            set(check_report.CURRENCIES), True, "digest.verdict_details")
        self.assertEqual((v, skipped), ([], 0))
```

- [x] **T3 Step 2: 跑测试确认失败**

```bash
find . -name __pycache__ -type d -exec rm -rf {} +
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_check_report.CheckVerdictsCoreTest tests.test_check_report.VerdictFieldConstantsTest -v 2>&1 | tail -8
```

Expected: 全部 ERROR,报 `AttributeError: module 'scripts.check_report' has no attribute 'check_verdicts'` 与 `... has no attribute 'VERDICT_FIELDS_EVENTS'`。

- [x] **T3 Step 3: 实现**

3a. `scripts/check_report.py` 常量区,在第 22 行 `DATE_HEADING_RE = ...` **之后**加:

```python
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
```

3b. 在 `def check_daily(` **之前**插入核心谓词:

```python
def check_verdicts(report, container, fields, covered, required, label):
    """结论句逐字引用检查。**日报与周报共用这一份判定**,两个调用点只提供
    「到哪个容器取哪些字段」—— 判定逻辑复制两份后漂移是本仓库栽过的坑
    (见 scripts/fixings.py);与 events.landed_count_capped 同构。

    container : {币种: {字段: 句子}};非 dict 一律跳过(结构问题由既有检查报告)
    fields    : 要检查的字段名元组(显式枚举,不按名字模式扫)
    covered   : 报告已覆盖的币种集合;不在其中者跳过,由 SECTION_MISSING /
                CURRENCY_MISSING 单独报告 —— 同一处缺失不得产生两条违规
    required  : 该来源的 schema 是否保证这些字段存在
    label     : 违规信息里的来源前缀,如 "digest.events" / "derived.events"

    返回 (violations, skipped_currencies)。skipped 不是违规,但**必须被调用方
    如实打印**:「跳过」与「通过」在输出上不可分辨,正是本检查要解决的问题。
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
        missing = False
        for field in fields:
            s = entry.get(field)
            if s is None:
                if required:
                    v.append("VERDICT_ABSENT: %s.%s 缺少结论句字段 %s"
                             % (label, c, field))
                else:
                    missing = True
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
            if s not in report:
                v.append("VERDICT_NOT_QUOTED: %s.%s 的 %s 未逐字出现在报告中;"
                         "期望原文:%s" % (label, c, field, s))
        if missing:
            skipped += 1
    return v, skipped
```

- [x] **T3 Step 4: 跑测试确认通过**

```bash
find . -name __pycache__ -type d -exec rm -rf {} +
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_check_report -v 2>&1 | tail -5
```

Expected: `OK`。既有的 `CheckDailyTest` / `CheckWeeklyTest` 等全部保持绿(本任务未接线,行为零变化)。

- [x] **T3 Step 5: 勾选并提交**

把 tasks.md 的 `1.1`、`1.3`、`1.5` 三行分别改成 `- [x]`,逐条验证后提交:

```bash
bash ~/.claude/skills/super-coding/scripts/super-coding-state.sh task-checkoff \
  openspec/changes/fx-verdict-enforcement/tasks.md "字段名显式枚举为模块级常量"
git add scripts/check_report.py tests/test_check_report.py openspec/changes/fx-verdict-enforcement/tasks.md
git commit -m "feat(check): 结论句核心谓词 check_verdicts(三态 + 两道让位 + 字段名显式枚举)

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 4:`check_weekly` 接入三类结论句

对应 tasks.md **1.2 / 1.4 / 1.6**。

**注意:本任务会让一个既有用例变红** —— `DigestFailClosedTest.test_valid_digest_still_passes` 的 digest fixture 里 `rates.PHP` 没有 `fixings_verdict`,而真实 digest 的 `_rates_digest` 永远会写这个字段。**处置是把 fixture 补成真实形态,不是放宽检查**。

**Files:**
- Modify: `scripts/check_report.py`(`check_weekly` 的 `if isinstance(digest, dict):` 块)
- Modify: `tests/test_check_report.py`(第 317-340 行的 `DIGEST` / `WEEKLY_OK` fixture;第 422 行的 `test_valid_digest_still_passes`;末尾追加新类)

- [ ] **T4 Step 1: 改 fixture 并写会红的测试**

4a. 把 `tests/test_check_report.py` 第 317-340 行的 `DIGEST` 与 `WEEKLY_OK` 两个常量整体替换为:

```python
FIX_PHP = "区间内 2 次不同定盘(2026-08-07 至 2026-08-10)"
ART_PHP = "区间内至少 3 条(1/5 天未采到)"
OFF_PHP = "未接入或全区间采集失败,有无公告无法判定"

DIGEST_OBJ = {"week": "2026-W33",
              "generated_from": ["2026-08-07", "2026-08-10"],
              "rates": {"PHP": {"chg_pct_week": -0.192, "range_low": 60.75,
                                "range_high": 60.867, "fixings": 2,
                                "fixings_verdict": FIX_PHP}},
              "events": {"PHP": {"articles_verdict": ART_PHP,
                                 "official_verdict": OFF_PHP}},
              "verdicts": {"命中": 1, "未命中": 0, "无法判定": 15, "未判定": 10},
              "verdict_details": [{"date": "2026-08-07", "currency": "PHP",
                                   "verdict": "命中"}]}
DIGEST = json.dumps(DIGEST_OBJ, ensure_ascii=False)

WEEKLY_OK = """# 外汇周报 2026-W33

> 覆盖日报:3 份(2026-08-07, 2026-08-08, 2026-08-10);缺失日期:无

## 本周主线
- 比索本周走强

## 各币种一周归因
USD / EUR / PHP 周涨跌 -0.192%%,区间 60.75–60.867;%s。事件:%s;公告:%s / THB / BRL

## 复盘汇总
- 命中 1、未命中 0、无法判定 15、未判定 10

## 下周关注
- 关注定盘更新

## 缺漏汇总
- 无
""" % (FIX_PHP, ART_PHP, OFF_PHP)
```

**为什么可以这么改**:`WEEKLY_OK` 新增的三句里所有数字(2、3、1、5)都是 `ALLOWED_SMALL` 小整数,日期被 `DATE_RE` 剥掉,`60.75`/`60.867`/`-0.192` 原本就在 digest 里 —— 数字溯源行为不变。`test_fabricated_number_caught` 用 `replace("60.867", "61.999")`,而三句里都不含 `60.867`,替换点仍唯一。注意 `%%` 转义:整串走了 `%` 格式化。

4b. 把 `DigestFailClosedTest.test_valid_digest_still_passes`(现第 422-431 行)整体替换为:

```python
    def test_valid_digest_still_passes(self):
        """fixture 必须是**真实 digest 形态** —— _rates_digest 与 _events_one
        永远会写结论句字段,缺了就是脚本缺陷,不该由校验器放行。"""
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(self._run(tmp, DIGEST), 0)
```

4c. 在 `tests/test_check_report.py` **文件末尾**追加:

```python
class WeeklyVerdictQuotingTest(unittest.TestCase):
    """周报三类结论句的逐字引用(delta spec:结论句与聚合文件不一致 /
    三类结论句全覆盖 / 基准货币在定盘容器中无条目 / 未提供聚合文件 /
    周报未覆盖某币种 / 结论句为空串)。"""

    def _run(self, report, digest_obj=None):
        return check_report.check_weekly(
            report, DIGEST, (), digest_obj if digest_obj is not None else DIGEST_OBJ)

    def test_fully_quoted_weekly_passes(self):
        self.assertEqual(self._run(WEEKLY_OK), [])

    def test_articles_verdict_reworded_is_caught(self):
        """实测形态:正文写「至少 15 条(3/5 天未采到)」而 digest 是
        「至少 26 条(3/6 天未采到、…)」,词袋检查照样打印通过。"""
        bad = WEEKLY_OK.replace(ART_PHP, "区间内至少 3 条")
        v = self._run(bad)
        self.assertTrue(any("VERDICT_NOT_QUOTED" in x and "articles_verdict" in x
                            for x in v), v)

    def test_official_verdict_missing_is_caught(self):
        bad = WEEKLY_OK.replace(OFF_PHP, "公告方面本周平静")
        v = self._run(bad)
        self.assertTrue(any("VERDICT_NOT_QUOTED" in x and "official_verdict" in x
                            for x in v), v)

    def test_fixings_verdict_missing_is_caught(self):
        """三类只查一类的变异必须被杀:定盘类在 rates 容器,与 events 分开取。"""
        bad = WEEKLY_OK.replace(FIX_PHP, "全周仅 2 次定盘")
        v = self._run(bad)
        self.assertTrue(any("VERDICT_NOT_QUOTED" in x and "fixings_verdict" in x
                            for x in v), v)

    def test_base_currency_absent_from_rates_container_is_legal(self):
        """digest["rates"] 没有 USD 是合法形态(基准货币无定盘价)。
        WEEKLY_OK 覆盖了 USD,但 rates 容器里没有它 —— 不得报字段缺失。"""
        v = self._run(WEEKLY_OK)
        self.assertFalse([x for x in v if "USD" in x and "VERDICT" in x], v)

    def test_currency_not_covered_reports_only_currency_missing(self):
        bad = WEEKLY_OK.replace("USD / EUR / PHP", "EUR / 比索")
        self.assertNotIn("PHP", bad)
        v = self._run(bad)
        self.assertTrue(any("CURRENCY_MISSING" in x and "PHP" in x for x in v), v)
        self.assertFalse([x for x in v if "VERDICT" in x and "PHP" in x], v)

    def test_currency_wholly_absent_is_not_double_reported(self):
        """上一条对「covered 恒取全集」的变异无鉴别力:那里只删掉币种名,
        三句结论句还留在正文里,两种取法结果相同(自跑变异实测存活)。
        这条把整行归因删掉 —— PHP 的三句一并消失,让位机制成了不报
        VERDICT 的唯一原因,同一处缺失才真的只产生一条违规。"""
        line = [x for x in WEEKLY_OK.splitlines() if x.startswith("USD / EUR / PHP")]
        self.assertEqual(len(line), 1)
        bad = WEEKLY_OK.replace(line[0], "USD / EUR / THB / BRL")
        self.assertNotIn("PHP", bad)
        self.assertNotIn(ART_PHP, bad)
        v = self._run(bad)
        self.assertTrue(any("CURRENCY_MISSING" in x and "PHP" in x for x in v), v)
        self.assertFalse([x for x in v if "VERDICT" in x], v)

    def test_empty_verdict_string_is_a_violation(self):
        obj = json.loads(DIGEST)
        obj["events"]["PHP"]["articles_verdict"] = "   "
        v = self._run(WEEKLY_OK, obj)
        self.assertTrue(any("VERDICT_EMPTY" in x for x in v), v)

    def test_non_string_verdict_is_malformed(self):
        obj = json.loads(DIGEST)
        obj["rates"]["PHP"]["fixings_verdict"] = {"text": FIX_PHP}
        v = self._run(WEEKLY_OK, obj)
        self.assertTrue(any("VERDICT_MALFORMED" in x for x in v), v)

    def test_missing_field_on_existing_entry_is_absent(self):
        obj = json.loads(DIGEST)
        del obj["events"]["PHP"]["official_verdict"]
        v = self._run(WEEKLY_OK, obj)
        self.assertTrue(any("VERDICT_ABSENT" in x and "official_verdict" in x
                            for x in v), v)

    def test_without_digest_object_no_verdict_check(self):
        """未提供 --digest 时 digest 为 None:不执行结论句检查,
        更不得因取不到而报「字段缺失」。"""
        v = check_report.check_weekly(WEEKLY_OK.replace(ART_PHP, "改写过"), DIGEST)
        self.assertFalse([x for x in v if "VERDICT" in x], v)

    def test_top_level_counting_structures_are_not_scanned(self):
        """digest 顶层的 verdicts(计数 dict)与 verdict_details(list)
        不得被当成结论句 —— 按 *verdict* 模式扫就会。"""
        v = self._run(WEEKLY_OK)
        self.assertFalse([x for x in v if "verdict_details" in x
                          or "digest.verdicts" in x], v)

    def test_violation_carries_the_source_label(self):
        """label 是三个调用点唯一的区分手段(digest.events / digest.rates /
        derived.events)。抹掉它,三类违规就分不出来源,而其余断言只看
        字段名与币种名,照样全绿 —— 代码质量审查实测该变异存活。"""
        bad = WEEKLY_OK.replace(ART_PHP, "改写过").replace(FIX_PHP, "也改写过")
        v = self._run(bad)
        self.assertTrue(any("digest.events.PHP" in x for x in v), v)
        self.assertTrue(any("digest.rates.PHP" in x for x in v), v)

    def test_missing_container_fails_loudly(self):
        """产出端坏掉时,校验器 MUST NOT 打印通过却一条都没查。
        谓词对非 dict 容器静默返回空(不越权判结构),兜底在调用点。"""
        for bad in (None, [], "x", 7):
            obj = json.loads(DIGEST)
            obj["events"] = bad
            v = self._run(WEEKLY_OK, obj)
            self.assertTrue(any("DIGEST_CONTAINER_MALFORMED" in x
                                and "digest.events" in x for x in v), (bad, v))

    def test_missing_container_key_fails_loudly(self):
        obj = json.loads(DIGEST)
        del obj["rates"]
        v = self._run(WEEKLY_OK, obj)
        self.assertTrue(any("DIGEST_CONTAINER_MALFORMED" in x
                            and "digest.rates" in x for x in v), v)


class NoLegacyExemptionSwitchTest(unittest.TestCase):
    """豁免机制本身会成为下一个绕过点(Design Doc §6)。校验器的 CLI 开关
    集合被钉死:想加豁免开关就得先改掉这条断言,而那是显式动作。"""

    def test_cli_option_set_is_frozen(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), self.assertRaises(SystemExit):
            check_report.main(["--help"])
        opts = set(re.findall(r"--[a-z][a-z-]*", buf.getvalue()))
        self.assertEqual(opts, {"--help", "--brief", "--mode", "--strict-brief",
                                "--digest", "--daily"})
```

4d. `tests/test_check_report.py` 顶部的 import 段(第 1-4 行)替换为:

```python
import contextlib
import io
import json
import os
import re
import tempfile
import unittest
```

- [ ] **T4 Step 2: 跑测试确认失败**

```bash
find . -name __pycache__ -type d -exec rm -rf {} +
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_check_report -v 2>&1 | tail -20
```

Expected: `WeeklyVerdictQuotingTest` 里 `test_articles_verdict_reworded_is_caught` / `test_official_verdict_missing_is_caught` / `test_fixings_verdict_missing_is_caught` / `test_empty_verdict_string_is_a_violation` / `test_non_string_verdict_is_malformed` / `test_missing_field_on_existing_entry_is_absent` 共 6 个 FAIL(违规列表为空);`NoLegacyExemptionSwitchTest` PASS(现有开关集合已符合)。其余为 PASS。

- [ ] **T4 Step 3: 实现**

`scripts/check_report.py` 的 `check_weekly`,把现有的

```python
    if isinstance(digest, dict):
        # 与日报的 GAP_OMITTED 对称:聚合出的每个缺漏源都必须在缺漏汇总里出现
        by_source = digest.get("gaps_by_source")
        gap_sec = find_section(secs, "缺漏汇总")
        if isinstance(by_source, dict) and gap_sec:
            for source in sorted(by_source):
                if isinstance(source, str) and source and source not in gap_sec[1]:
                    v.append("GAP_OMITTED: 缺漏汇总未提及 %s" % source)
    return v
```

改为

```python
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
        covered = {c for c in CURRENCIES if c in report}
        for container, fields, label in (
                (digest.get("events"), VERDICT_FIELDS_EVENTS, "digest.events"),
                (digest.get("rates"), VERDICT_FIELDS_RATES, "digest.rates")):
            if not isinstance(container, dict):
                # check_verdicts 对非 dict 容器静默返回空 —— 谓词不越权判结构。
                # 但**没有别处兜底**:main 只校验 week 与 generated_from,
                # 容器坏掉时会打印 CHECK PASSED 而一条结论句都没查,正是本
                # change 要消灭的形态。响亮失败在这里。
                v.append("DIGEST_CONTAINER_MALFORMED: 聚合文件的 %s 不是对象"
                         "(实为 %s),该类结论句一条都未校验"
                         % (label, type(container).__name__))
                continue
            found, _ = check_verdicts(report, container, fields, covered,
                                      required=True, label=label)
            v.extend(found)
    return v
```

- [ ] **T4 Step 4: 跑测试确认通过**

```bash
find . -name __pycache__ -type d -exec rm -rf {} +
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_check_report -v 2>&1 | tail -5
```

Expected: `OK`。若 `DigestFailClosedTest.test_valid_digest_still_passes` 仍红,说明 Step 1 的 4b 没做 —— 回去补,**不要**放宽 `required`。

再跑一次全量确认没有波及别处:

```bash
find . -name __pycache__ -type d -exec rm -rf {} +
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -t . 2>&1 | tail -3
```

Expected: `OK`,总数 > 554(预期 +25 左右;**实跑数字为准,不要预填**)。

- [ ] **T4 Step 5: 勾选并提交**

把 tasks.md 的 `1.2`、`1.4`、`1.6` 三行改成 `- [x]`,逐条验证后:

```bash
bash ~/.claude/skills/super-coding/scripts/super-coding-state.sh task-checkoff \
  openspec/changes/fx-verdict-enforcement/tasks.md "容器中不存在某币种条目时跳过"
git add scripts/check_report.py tests/test_check_report.py openspec/changes/fx-verdict-enforcement/tasks.md
git commit -m "feat(check): check_weekly 接入三类结论句逐字引用检查

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 5:`derive` 落 `events_verdict` + `SCHEMA_VERSION` 升 2

对应 tasks.md **2.1 / 2.2 / 2.6**。**仅 `events` 一类**;`rates` 与 `real_rate` 明确非目标,不要顺手加。

**本任务会让三个既有断言变红,三条都是期望行为**:
1. `tests/test_derive.py:543` 的 `assertEqual(set(got), set(derive.EMPTY_EVENTS_DERIVED))` —— 它是**防漂移哨兵**,新增的键只落在一侧时立刻红。**处置是把 `EMPTY_EVENTS_DERIVED` 同步补上 `events_verdict`,更新该断言的期望键集;绝不放宽或删除断言。**
2. `tests/test_derive.py:248` 的 `assertEqual(d["schema_version"], 1)` → 改 `2`。
3. `tests/test_snapshot.py:177` 的 `assertEqual(snap["derived"]["schema_version"], 1)` → 改 `2`。
   **注意** `tests/test_snapshot.py:45` 的 `snap["schema_version"] == 1` 是**快照顶层**的版本号,与 `derived` 的不是同一个,**保持 1 不动**。

**Files:**
- Modify: `scripts/collect/derive.py`
- Modify: `tests/test_derive.py`
- Modify: `tests/test_snapshot.py:177`

- [ ] **T5 Step 1: 写会红的测试**

在 `tests/test_derive.py` **文件末尾**追加:

```python
class EventsVerdictTest(unittest.TestCase):
    """日报侧结论句(delta spec:事件结论句落盘)。

    判定用的是**单日事实**(count / count_capped / sample_capped /
    channel_changed_from / dropped_malformed),与周报的跨日统计定义域不同 ——
    刻意不共用判定,只共用 verdicts.join_verdict 这一个拼装口。"""

    def _derive(self, entry, history=(), caps=None):
        snap = {"date": "2026-08-12", "rates": {"PHP": rate_entry(56.0)},
                "events": {"PHP": entry},
                "meta": {"caps": caps or {"gdelt_records": 8, "gnews_records": 99}}}
        return derive.derive(snap, list(history))[0]["events"]["PHP"]

    def test_key_present_in_normal_branch(self):
        got = self._derive({"articles": [{"title": "t"}], "channel": "gdelt",
                            "source_cap": 8, "source_capped": False,
                            "count_at_cap": False})
        self.assertIn("events_verdict", got)
        self.assertIsInstance(got["events_verdict"], str)

    def test_plain_count_head(self):
        got = self._derive({"articles": [{"title": "t%d" % i} for i in range(3)],
                            "channel": "gdelt", "source_cap": 8,
                            "source_capped": False, "count_at_cap": False})
        self.assertEqual(got["events_verdict"], "当日采到 3 条")

    def test_zero_is_not_the_same_as_failure(self):
        """0 是"确实 0 篇",null 是"没采到" —— 把采集失败写成 0 就是在报
        "没发生",属编造。两句话必须不同。"""
        zero = self._derive({"articles": [], "channel": "gdelt", "source_cap": 8,
                             "source_capped": False, "count_at_cap": False})
        failed = self._derive({"official": [{"title": "o"}]})
        self.assertEqual(zero["events_verdict"], "当日未采到事件")
        self.assertEqual(failed["events_verdict"],
                         "当日事件采集失败,有无事件无法判定")
        self.assertNotEqual(zero["events_verdict"], failed["events_verdict"])

    def test_count_capped_caveat_carries_the_cap(self):
        # source_capped 刻意为 False:本用例只隔离"落盘条数触顶"这一条 caveat,
        # 两者同真时会各出一句(见 test_caveats_joined_in_declared_order)
        got = self._derive({"articles": [{"title": "t%d" % i} for i in range(8)],
                            "articles_raw_count": 8, "channel": "gdelt",
                            "source_cap": 8, "source_capped": False,
                            "count_at_cap": True})
        self.assertEqual(got["events_verdict"],
                         "当日采到 8 条(已顶到当日采集上限(8 条),实际篇数只多不少)")

    def test_unknown_cap_does_not_print_none(self):
        """上限不可知时直接插值会把字面量 None 印进中文结论句(周报侧栽过)。"""
        got = self._derive({"articles": [{"title": "t"}], "channel": "gdelt",
                            "count_at_cap": True})
        self.assertIn("上限不可知", got["events_verdict"])
        self.assertNotIn("None", got["events_verdict"])

    def test_sample_capped_is_a_separate_caveat(self):
        """滤除前样本触顶与落盘条数触顶是两件事,不得互相代用。"""
        got = self._derive({"articles": [{"title": "t"}] * 11,
                            "articles_raw_count": 100, "channel": "gnews",
                            "source_cap": 99, "source_capped": True,
                            "count_at_cap": False,
                            "gnews_filter": {"raw": 100, "undated": 0,
                                             "out_window": 0, "offlist": 89,
                                             "kept": 11, "capped": True}})
        self.assertEqual(got["events_verdict"],
                         "当日采到 11 条(源返回的原始样本顶到其上限,滤后条数是下界)")

    def test_channel_change_caveat(self):
        prev = {"date": "2026-08-11", "rates": {"PHP": rate_entry(56.1)},
                "events": {"PHP": {"articles": [{"title": "p"}] * 8,
                                   "channel": "gdelt"}}}
        got = self._derive({"articles": [{"title": "t"}] * 11, "channel": "gnews",
                            "source_cap": 99, "source_capped": False,
                            "count_at_cap": False}, history=[prev])
        self.assertIn("前一日取自 gdelt 通道,口径不可比,不给变化量",
                      got["events_verdict"])

    def test_dropped_malformed_caveat(self):
        got = self._derive({"articles": [{"title": "t"}], "channel": "gdelt",
                            "source_cap": 8, "source_capped": False,
                            "count_at_cap": False,
                            "articles_dropped_malformed": 7})
        self.assertEqual(got["events_verdict"],
                         "当日采到 1 条(另有 7 条结构不可识别被跳过)")

    def test_dropped_malformed_zero_adds_no_caveat(self):
        """0 条被跳过就是没有这件事,不该多出一句 caveat。"""
        got = self._derive({"articles": [{"title": "t"}], "channel": "gdelt",
                            "source_cap": 8, "source_capped": False,
                            "count_at_cap": False,
                            "articles_dropped_malformed": 0})
        self.assertEqual(got["events_verdict"], "当日采到 1 条")

    def test_caveats_joined_in_declared_order(self):
        prev = {"date": "2026-08-11", "rates": {"PHP": rate_entry(56.1)},
                "events": {"PHP": {"articles": [{"title": "p"}], "channel": "gdelt"}}}
        got = self._derive({"articles": [{"title": "t"}] * 99,
                            "articles_raw_count": 100, "channel": "gnews",
                            "source_cap": 99, "source_capped": True,
                            "count_at_cap": True,
                            "articles_dropped_malformed": 2,
                            "gnews_filter": {"raw": 100, "undated": 0,
                                             "out_window": 0, "offlist": 1,
                                             "kept": 99, "capped": True}},
                           history=[prev])
        self.assertEqual(
            got["events_verdict"],
            "当日采到 99 条(已顶到当日采集上限(99 条),实际篇数只多不少、"
            "源返回的原始样本顶到其上限,滤后条数是下界、"
            "前一日取自 gdelt 通道,口径不可比,不给变化量、"
            "另有 2 条结构不可识别被跳过)")

    def test_no_empty_parens_when_no_caveat(self):
        got = self._derive({"articles": [{"title": "t"}], "channel": "gdelt",
                            "source_cap": 8, "source_capped": False,
                            "count_at_cap": False})
        self.assertNotIn("()", got["events_verdict"])

    def test_empty_events_derived_carries_the_key(self):
        """四处同步(derive / EMPTY_EVENTS_DERIVED / SKILL / 校验器)少一处即
        漂移。键集断言只保证两侧一致,这条另外保证不是两侧一起被删掉。"""
        self.assertIn("events_verdict", derive.EMPTY_EVENTS_DERIVED)
        self.assertIsNone(derive.EMPTY_EVENTS_DERIVED["events_verdict"])

    def test_schema_version_is_two(self):
        """校验器按 derived.schema_version >= 2 分流存量快照 —— 这个数不是
        装饰,改了它就等于宣布"这份快照本该有结论句"。"""
        self.assertEqual(derive.SCHEMA_VERSION, 2)
        d, _ = derive.derive(payload(), [])
        self.assertEqual(d["schema_version"], 2)

    def test_rates_and_real_rate_get_no_verdict(self):
        """非目标:日报结论句只做 events 一类。"""
        d, _ = derive.derive(payload({"PHP": rate_entry(60.75)},
                                     macro=[{"economy": "PH",
                                             "indicator": "政策利率",
                                             "value": 5.0, "period": "2026-07"}]), [])
        self.assertFalse([k for k in d["rates"]["PHP"] if "verdict" in k])
        self.assertFalse([k for k in derive.EMPTY_RATE_DERIVED if "verdict" in k])
        self.assertFalse([k for k in derive.EMPTY_REAL_RATE if "verdict" in k])
```

- [ ] **T5 Step 2: 跑测试确认失败**

```bash
find . -name __pycache__ -type d -exec rm -rf {} +
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_derive -v 2>&1 | tail -20
```

Expected: `EventsVerdictTest` 里除 `test_rates_and_real_rate_get_no_verdict` 外全部 FAIL(`KeyError: 'events_verdict'` / `assertIn` 失败 / `2 != 1`);另外 `test_schema_version_present` 仍是绿(它断言 1)。

- [ ] **T5 Step 3: 实现 —— `scripts/collect/derive.py` 四处编辑**

3a. 第 7 行 `from ..fixings import distinct_fixings, num as _num` **之后**加一行:

```python
from ..verdicts import join_verdict
```

3b. 第 12 行 `SCHEMA_VERSION = 1` 改为:

```python
# 2:derived.events.<币种> 起带 events_verdict 结论句。校验器按这个数分流
# 存量快照 —— 判据是"这份快照本该有",不是"这个键在不在"。
SCHEMA_VERSION = 2
```

3c. `EMPTY_EVENTS_DERIVED`(第 28-32 行)补上新键:

```python
EMPTY_EVENTS_DERIVED = {"count": None, "count_prev": None, "count_delta": None,
                        "count_capped": None, "count_prev_capped": None,
                        "channel_changed_from": None,
                        "sample_capped": None, "dropped_malformed": None,
                        "main_sample_capped": None,
                        # 异常分支写 None 而非兜底句:schema 已升到 2,
                        # 校验器会据此报 VERDICT_ABSENT —— 那正是想要的,
                        # 该形态是脚本缺陷,必须响亮,不该与存量快照同形
                        "events_verdict": None}
```

3d. 在 `_main_sample_capped` 之后、`_events_derived` 之前插入两个函数:

```python
def _cap_phrase(cap):
    """上限的中文括注。上限不可知时**不给数值** —— 直接插值会把字面量 None
    印进中文结论句(周报侧的 _cap_phrase 因同一原因存在)。"""
    if isinstance(cap, int) and not isinstance(cap, bool) and cap > 0:
        return "(%d 条)" % cap
    return "(上限不可知)"


def _events_verdict(count, count_capped, sample_capped, channel_changed_from,
                    dropped_malformed, cap):
    """当日事件的结论句 —— 日报唯一可以用来陈述"有没有、有几条"的字段。

    **不与周报共用判定**:周报的输入是跨日统计(days_collected / window_days /
    in_window),这里是单日事实;定义域不同,强行复用判定正是上一个 change
    第四轮那类事故的成因。共用的只有 verdicts.join_verdict 这一个拼装口。

    count 为 None 表示该币种当日事件采集失败,0 表示确实 0 篇 —— 两者绝不可
    合并:把采集失败写成"未采到事件"以外的任何说法都是在报"没发生"。
    """
    if count is None:
        head = "当日事件采集失败,有无事件无法判定"
    elif count == 0:
        head = "当日未采到事件"
    else:
        head = "当日采到 %d 条" % count
    caveats = []
    if count_capped is True:
        caveats.append("已顶到当日采集上限%s,实际篇数只多不少" % _cap_phrase(cap))
    if sample_capped is True:
        # 与上一条分开:触顶的是**滤除前**的原始样本,落盘条数可能离上限还差
        # 得远(实测 raw=100 而 count=11)。合并会把"事件面确实持平"写成假象
        caveats.append("源返回的原始样本顶到其上限,滤后条数是下界")
    if isinstance(channel_changed_from, str) and channel_changed_from:
        caveats.append("前一日取自 %s 通道,口径不可比,不给变化量"
                       % channel_changed_from)
    if isinstance(dropped_malformed, int) and not isinstance(dropped_malformed, bool) \
            and dropped_malformed > 0:
        caveats.append("另有 %d 条结构不可识别被跳过" % dropped_malformed)
    return join_verdict(head, caveats)
```

3e. `_events_derived` 的 `try` 块,把

```python
            chan = _channel_of(payload, currency)
            chan_prev = _channel_of(history[0], currency) if history else chan
            switched = (chan is not None and chan_prev is not None
                        and chan != chan_prev)
            out[currency] = {
```

改为

```python
            chan = _channel_of(payload, currency)
            chan_prev = _channel_of(history[0], currency) if history else chan
            switched = (chan is not None and chan_prev is not None
                        and chan != chan_prev)
            # 三个布尔与上限提前算出来:落盘的键与结论句必须读同一份事实,
            # 各算一遍就会出现"字段说 false、句子说触顶"的自相矛盾
            changed_from = chan_prev if switched else None
            capped = _count_capped(payload, currency)
            sampled = _sample_capped(payload, currency)
            dropped = _dropped_malformed(payload, currency)
            entry = _event_entry_of(payload, currency)
            cap = entry.get("source_cap") if isinstance(entry, dict) else None
            out[currency] = {
```

并把同一 dict 字面量里的四行

```python
                "channel_changed_from": chan_prev if switched else None,
```
```python
                "count_capped": _count_capped(payload, currency),
```
```python
                "sample_capped": _sample_capped(payload, currency),
```
```python
                "dropped_malformed": _dropped_malformed(payload, currency),
```

分别改为

```python
                "channel_changed_from": changed_from,
```
```python
                "count_capped": capped,
```
```python
                "sample_capped": sampled,
```
```python
                "dropped_malformed": dropped,
```

最后在该 dict 的 `"main_sample_capped": _main_sample_capped(payload, currency),` **之后**加一项(注意它必须是这个 dict 的最后一项,与 `EMPTY_EVENTS_DERIVED` 键集一致):

```python
                # 报告唯一可以用来陈述"有没有、有几条"的字段:脚本已把上限
                # 触顶、样本触顶、通道更换、不可识别条数折进结论,日报逐字
                # 整句引用即可,禁止自行按布尔拼话术
                "events_verdict": _events_verdict(count, capped, sampled,
                                                  changed_from, dropped, cap),
```

3f. 更新两个既有断言(它们断言的版本号确实变了):
- `tests/test_derive.py:248`:`self.assertEqual(d["schema_version"], 1)` → `self.assertEqual(d["schema_version"], 2)`
- `tests/test_snapshot.py:177`:`self.assertEqual(snap["derived"]["schema_version"], 1)` → `self.assertEqual(snap["derived"]["schema_version"], 2)`

**不要动** `tests/test_snapshot.py:45`(快照顶层版本号,保持 1)。

- [ ] **T5 Step 4: 跑测试确认通过**

```bash
find . -name __pycache__ -type d -exec rm -rf {} +
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_derive tests.test_snapshot -v 2>&1 | tail -5
```

Expected: `OK`。第 543 行的键集哨兵此时应为绿 —— 它绿的**唯一合法原因**是 `EMPTY_EVENTS_DERIVED` 与 `_events_derived` 的输出都补上了 `events_verdict`。若它仍红,回到 3c 与 3e 补齐;**不得**用放宽断言的方式消除。

```bash
find . -name __pycache__ -type d -exec rm -rf {} +
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -t . 2>&1 | tail -3
```

Expected: `OK`(**实跑数字为准**)。

- [ ] **T5 Step 5: 勾选并提交**

把 tasks.md 的 `2.1`、`2.2`、`2.6` 改成 `- [x]`,逐条验证后:

```bash
bash ~/.claude/skills/super-coding/scripts/super-coding-state.sh task-checkoff \
  openspec/changes/fx-verdict-enforcement/tasks.md "\`derive.SCHEMA_VERSION\` 升到 2"
git add scripts/collect/derive.py tests/test_derive.py tests/test_snapshot.py openspec/changes/fx-verdict-enforcement/tasks.md
git commit -m "feat(derive): 落 events_verdict 结论句,SCHEMA_VERSION 升 2 并同步 EMPTY_EVENTS_DERIVED

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 6:`check_daily` 接入 + schema 闸门 + 跳过声明

对应 tasks.md **2.3 / 2.4 / 2.7**。

**Files:**
- Modify: `scripts/check_report.py`(`check_daily` 签名与函数体;`main` 的 notes 打印)
- Modify: `tests/test_check_report.py`(追加到文件末尾)

- [ ] **T6 Step 1: 写会红的测试**

在 `tests/test_check_report.py` **文件末尾**追加:

```python
DAILY_VERDICT = "当日采到 11 条(前一日取自 gdelt 通道,口径不可比,不给变化量)"


def snap_with_derived(schema_version=2, verdict=DAILY_VERDICT,
                      currencies=("USD",)):
    """在既有 SNAP 上挂一个 derived 节。SNAP 本身不变(浅拷贝后加键)。"""
    snap = dict(SNAP)
    snap["derived"] = {
        "schema_version": schema_version,
        "rates": {}, "real_rate": {},
        "events": {c: ({} if verdict is None else {"events_verdict": verdict})
                   for c in currencies},
    }
    return json.dumps(snap, ensure_ascii=False)


def report_quoting(sentence, heading="美元(USD)", **kw):
    """把结论句原样塞进某币种节 —— 前后可以有自己的叙述,句子本身不动。"""
    r = make_report(**kw)
    return r.replace("## %s\n" % heading,
                     "## %s\n事件方面,%s。\n" % (heading, sentence))


class DailyVerdictQuotingTest(unittest.TestCase):
    """日报侧结论句(delta spec:结论句被改动一个字 / 结论句整句缺失 /
    结论句为空串 / 存量快照无结论句字段 / 新 schema 快照漏写结论句 /
    报告未覆盖某币种)。"""

    def test_quoted_sentence_passes(self):
        v = check_report.check_daily(report_quoting(DAILY_VERDICT),
                                     snap_with_derived(), BRIEF)
        self.assertEqual(v, [])

    def test_one_character_changed_is_caught(self):
        bad = report_quoting(DAILY_VERDICT.replace("11", "12"))
        v = check_report.check_daily(bad, snap_with_derived(), BRIEF)
        self.assertTrue(any("VERDICT_NOT_QUOTED" in x and "USD" in x for x in v), v)

    def test_whole_sentence_missing_is_caught(self):
        """数字词袋放行的正是这一形态:11 与 gdelt 都在快照里出现过。"""
        v = check_report.check_daily(make_report(), snap_with_derived(), BRIEF)
        self.assertTrue(any("VERDICT_NOT_QUOTED" in x for x in v), v)

    def test_empty_verdict_is_a_violation(self):
        v = check_report.check_daily(make_report(),
                                     snap_with_derived(verdict="  "), BRIEF)
        self.assertTrue(any("VERDICT_EMPTY" in x for x in v), v)

    def test_new_schema_missing_field_is_absent(self):
        """新 schema 却漏写字段 = 脚本缺陷,必须响亮。"""
        v = check_report.check_daily(make_report(),
                                     snap_with_derived(verdict=None), BRIEF)
        self.assertTrue(any("VERDICT_ABSENT" in x and "events_verdict" in x
                            for x in v), v)

    def test_legacy_schema_is_skipped_not_passed(self):
        """存量快照 derived.schema_version=1:跳过,不判违规,但必须计数。"""
        notes = []
        v = check_report.check_daily(
            make_report(), snap_with_derived(schema_version=1, verdict=None),
            BRIEF, notes=notes)
        self.assertFalse([x for x in v if "VERDICT" in x], v)
        self.assertEqual(len(notes), 1)
        self.assertIn("VERDICT_SKIPPED_LEGACY", notes[0])
        self.assertIn("1 个币种", notes[0])

    def test_legacy_count_covers_every_currency(self):
        notes = []
        check_report.check_daily(
            make_report(),
            snap_with_derived(schema_version=1, verdict=None,
                              currencies=check_report.CURRENCIES),
            BRIEF, notes=notes)
        self.assertIn("5 个币种", notes[0])

    def test_missing_schema_version_is_treated_as_legacy(self):
        snap = dict(SNAP)
        snap["derived"] = {"rates": {}, "real_rate": {}, "events": {"USD": {}}}
        notes = []
        v = check_report.check_daily(make_report(),
                                     json.dumps(snap, ensure_ascii=False),
                                     BRIEF, notes=notes)
        self.assertFalse([x for x in v if "VERDICT" in x], v)
        self.assertEqual(len(notes), 1)

    def test_bool_schema_version_is_not_a_number(self):
        """True >= 2 在 Python 里是 False,但 True 也不该被当成版本号。"""
        snap = dict(SNAP)
        snap["derived"] = {"schema_version": True, "events": {"USD": {}}}
        notes = []
        v = check_report.check_daily(make_report(),
                                     json.dumps(snap, ensure_ascii=False),
                                     BRIEF, notes=notes)
        self.assertFalse([x for x in v if "VERDICT" in x], v)
        self.assertEqual(len(notes), 1)

    def test_legacy_snapshot_with_a_sentence_is_still_checked(self):
        """闸门只放行"缺字段",不放行"字段在但引错了"。"""
        v = check_report.check_daily(make_report(),
                                     snap_with_derived(schema_version=1), BRIEF)
        self.assertTrue(any("VERDICT_NOT_QUOTED" in x for x in v), v)

    def test_missing_section_does_not_double_report(self):
        """让位 ①:缺币种节只报 SECTION_MISSING 一条。"""
        v = check_report.check_daily(
            make_report(missing="THB"),
            snap_with_derived(currencies=("THB",)), BRIEF)
        self.assertTrue(any("SECTION_MISSING" in x and "THB" in x for x in v), v)
        self.assertFalse([x for x in v if "VERDICT" in x], v)

    def test_snapshot_without_derived_is_inert(self):
        """既有快照(无 derived 节)行为完全不变。"""
        notes = []
        v = check_report.check_daily(make_report(), SNAP_TEXT, BRIEF, notes=notes)
        self.assertEqual(v, [])
        self.assertEqual(notes, [])

    def test_derived_not_a_dict_does_not_crash(self):
        for bad in ("oops", [1], 7, None):
            snap = dict(SNAP)
            snap["derived"] = bad
            v = check_report.check_daily(make_report(),
                                         json.dumps(snap, ensure_ascii=False),
                                         BRIEF)
            self.assertFalse([x for x in v if "VERDICT" in x], (bad, v))


class DailySkipNoticeIsPrintedTest(unittest.TestCase):
    """「跳过」与「通过」在输出上必须可区分 —— 这正是本 change 要解决的
    同型问题,所以跳过声明本身必须有测试。"""

    def _write(self, tmp, report_text, snap_text):
        rp = os.path.join(tmp, "r.md")
        sp = os.path.join(tmp, "s.json")
        for path, text in ((rp, report_text), (sp, snap_text)):
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
        return rp, sp

    def test_legacy_notice_printed_alongside_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            rp, sp = self._write(tmp, make_report(),
                                 snap_with_derived(schema_version=1,
                                                   verdict=None))
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = check_report.main([rp, sp])
            out = buf.getvalue()
        self.assertEqual(rc, 0)
        self.assertIn("VERDICT_SKIPPED_LEGACY", out)
        self.assertIn("CHECK PASSED", out)

    def test_no_notice_when_schema_is_current(self):
        with tempfile.TemporaryDirectory() as tmp:
            rp, sp = self._write(tmp, report_quoting(DAILY_VERDICT),
                                 snap_with_derived())
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = check_report.main([rp, sp])
            out = buf.getvalue()
        self.assertEqual(rc, 0)
        self.assertNotIn("VERDICT_SKIPPED_LEGACY", out)


class VerdictFieldSyncTest(unittest.TestCase):
    """常量元组与产出端字段名同步 —— 常量里拼错一个字母,检查会静默地
    什么都不查,而所有既有测试照样全绿(本仓库的典型失败形态)。"""

    def test_daily_field_exists_in_derive_output(self):
        for f in check_report.VERDICT_FIELD_DAILY:
            self.assertIn(f, derive.EMPTY_EVENTS_DERIVED)

    def test_weekly_fields_exist_in_digest_output(self):
        snaps = [{"date": "2026-08-10", "gaps": [],
                  "rates": {"PHP": {"primary": 60.867, "ref_date": "2026-08-10"}},
                  "events": {"PHP": {"articles": [], "official": []}}},
                 {"date": "2026-08-11", "gaps": [],
                  "rates": {"PHP": {"primary": 60.75, "ref_date": "2026-08-11"}},
                  "events": {"PHP": {"articles": [], "official": []}}}]
        d = weekly_digest.build(snaps, [], "2026-W33")[0]
        for f in check_report.VERDICT_FIELDS_EVENTS:
            self.assertIn(f, d["events"]["PHP"])
        for f in check_report.VERDICT_FIELDS_RATES:
            self.assertIn(f, d["rates"]["PHP"])

    def test_schema_gate_matches_derive_version(self):
        """闸门常量落后于 derive.SCHEMA_VERSION 时,新快照会被当成存量跳过。"""
        self.assertLessEqual(check_report.DERIVED_VERDICT_SCHEMA,
                             derive.SCHEMA_VERSION)
```

同时把 `tests/test_check_report.py` 顶部 import 段补成:

```python
import contextlib
import io
import json
import os
import re
import tempfile
import unittest

from scripts import check_report
from scripts import weekly_digest
from scripts.collect import derive
```

- [ ] **T6 Step 2: 跑测试确认失败**

```bash
find . -name __pycache__ -type d -exec rm -rf {} +
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_check_report -v 2>&1 | tail -20
```

Expected:`DailyVerdictQuotingTest` 里带 `notes=` 的用例 ERROR(`TypeError: check_daily() got an unexpected keyword argument 'notes'`),其余期望捕获违规的用例 FAIL(违规列表为空);`DailySkipNoticeIsPrintedTest` 2 个 FAIL;`VerdictFieldSyncTest` 3 个 PASS。

- [ ] **T6 Step 3: 实现 —— `scripts/check_report.py` 两处编辑**

3a. `check_daily` 签名与函数体。把

```python
def check_daily(report, snapshot_text, brief_text, strict_brief=False):
```

改为

```python
def check_daily(report, snapshot_text, brief_text, strict_brief=False, notes=None):
```

并在函数体里、`allowed = numbers_in(snapshot_text) | ...` 那一行**之前**插入:

```python
    # 结论句逐字引用。闸门只读不写:schema 过旧不让校验失败,只降级并如实
    # 声明降级了几条 —— 「跳过」与「通过」在输出上必须可区分。
    # 判据取 schema 版本而非"这个键在不在":后者会让**新代码产出却漏写该
    # 字段**的缺陷与存量快照完全同形,静默通过。
    derived = snap.get("derived") if isinstance(snap, dict) else None
    derived = derived if isinstance(derived, dict) else {}
    ver = derived.get("schema_version")
    ver_ok = (isinstance(ver, int) and not isinstance(ver, bool)
              and ver >= DERIVED_VERDICT_SCHEMA)
    covered = {c for c in CURRENCIES if find_section(secs, c)}
    found, skipped = check_verdicts(report, derived.get("events"),
                                    VERDICT_FIELD_DAILY, covered, ver_ok,
                                    "derived.events")
    v.extend(found)
    if skipped and notes is not None:
        notes.append("VERDICT_SKIPPED_LEGACY: %d 个币种因快照 schema 过旧"
                     "(derived.schema_version=%s)未校验结论句" % (skipped, ver))
```

3b. `main` 里打印 notes。把

```python
    if args.mode == "daily":
```

改为

```python
    notes = []
    if args.mode == "daily":
```

把

```python
        violations = check_daily(report, snapshot_text, brief_text,
                                 strict_brief=args.strict_brief)
```

改为

```python
        violations = check_daily(report, snapshot_text, brief_text,
                                 strict_brief=args.strict_brief, notes=notes)
```

把

```python
    if violations:
        print("CHECK FAILED (%d):" % len(violations))
```

改为

```python
    # 降级声明先于结论打印:退出码 0 却跳过了几条,读者必须看得见
    for note in notes:
        print(note)
    if violations:
        print("CHECK FAILED (%d):" % len(violations))
```

- [ ] **T6 Step 4: 跑测试确认通过**

```bash
find . -name __pycache__ -type d -exec rm -rf {} +
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_check_report -v 2>&1 | tail -5
```

Expected: `OK`。

```bash
find . -name __pycache__ -type d -exec rm -rf {} +
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -t . 2>&1 | tail -3
```

Expected: `OK`(**实跑数字为准**)。

- [ ] **T6 Step 5: 勾选并提交**

把 tasks.md 的 `2.3`、`2.4`、`2.7` 改成 `- [x]`,逐条验证后:

```bash
bash ~/.claude/skills/super-coding/scripts/super-coding-state.sh task-checkoff \
  openspec/changes/fx-verdict-enforcement/tasks.md "校验器按 \`derived.schema_version >= 2\` 分流存量快照"
git add scripts/check_report.py tests/test_check_report.py openspec/changes/fx-verdict-enforcement/tasks.md
git commit -m "feat(check): check_daily 接入同一份结论句判定,schema 闸门 + 跳过声明

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 7:两个 SKILL 的引用规则 + 文档哨兵

对应 tasks.md **3.1 / 3.2**。

**Files:**
- Create: `tests/test_skill_docs.py`
- Modify: `skills/fx-daily-report/SKILL.md`(第 75-94 行的事件段;第 4 步禁令表)
- Modify: `skills/fx-weekly-report/SKILL.md`(「计数与结论纪律」第 1 条)

- [ ] **T7 Step 1: 写会红的测试**

创建 `tests/test_skill_docs.py`:

```python
"""SKILL 文档哨兵。

新增一个结论句字段要同步四处(derive / EMPTY_EVENTS_DERIVED / SKILL /
校验器)。前三处漏一处会被键集断言或单测抓住,唯独 SKILL 是散文 —— 漏改
不会让任何测试变红,而它恰恰是"第二处判定"的藏身处:同一判定在提示词与
脚本各写一遍,两份措辞必然漂移,"哪一份算数"无处可判。
"""
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DAILY = os.path.join(ROOT, "skills", "fx-daily-report", "SKILL.md")
WEEKLY = os.path.join(ROOT, "skills", "fx-weekly-report", "SKILL.md")


def flat(path):
    """去掉所有空白后比对 —— 断言不该被折行位置绑架。"""
    with open(path, encoding="utf-8") as f:
        return "".join(f.read().split())


class DailySkillTest(unittest.TestCase):
    def test_points_at_the_verdict_field(self):
        t = flat(DAILY)
        self.assertIn("events_verdict", t)
        self.assertIn("逐字整句照抄", t)

    def test_boolean_assembly_wording_is_gone(self):
        """让 LLM 按布尔拼话术的原句必须删干净 —— 留着就是第二处判定。"""
        t = flat(DAILY)
        for phrase in ("已达当日采集上限,实际篇数只多不少",
                       "两日均达采集上限,变化0是上限造成的",
                       "源返回的原始样本触顶,滤除后的条数是下界",
                       "主通道当日返回条数触顶,其滤除后的条数是下界",
                       "另有N条源返回的元素结构不可识别被跳过"):
            self.assertNotIn(phrase, t, phrase)

    def test_states_the_exact_substring_rule(self):
        t = flat(DAILY)
        self.assertIn("精确子串包含", t)
        self.assertIn("改动一个字符", t)


class WeeklySkillTest(unittest.TestCase):
    def test_three_verdict_fields_named(self):
        t = flat(WEEKLY)
        for field in ("fixings_verdict", "articles_verdict", "official_verdict"):
            self.assertIn(field, t, field)

    def test_states_the_exact_substring_rule(self):
        t = flat(WEEKLY)
        self.assertIn("整句逐字", t)
        self.assertIn("精确子串包含", t)
        self.assertIn("改动一个字符", t)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **T7 Step 2: 跑测试确认失败**

```bash
find . -name __pycache__ -type d -exec rm -rf {} +
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_skill_docs -v
```

Expected: 5 个用例中 `DailySkillTest` 3 个全 FAIL、`WeeklySkillTest.test_states_the_exact_substring_rule` FAIL;`WeeklySkillTest.test_three_verdict_fields_named` PASS。

- [ ] **T7 Step 3: 实现 —— 三处文档编辑**

3a. `skills/fx-daily-report/SKILL.md`,把「派生指标」那一条里从 `事件数 <count>(前值 <count_prev>,` 开始、到 `**禁止**使用上面任何一句关于变化量的话术)` 结束的整段(现第 75-94 行)替换为:

```
      事件结论:**逐字整句照抄** `derived.events.<币种>.events_verdict`。
      它已经把当日条数、采集上限触顶、原始样本触顶、通道更换、结构不可识别
      的条数全部折算进一句话;照抄整句,不要摘出其中的数字另行造句。
      **禁止**据 `count_capped` / `sample_capped` / `main_sample_capped` /
      `channel_changed_from` / `dropped_malformed` 自行拼装任何话术 ——
      同一判定在提示词与脚本两处各写一遍,两份措辞必然漂移,而"哪一份才
      算数"无处可判(前十二次同型事故的共同根因)。
      该键不存在或为 null(存量快照)时,本行写"结论句不可得(存量快照)",
      并且**禁止**自行补一句结论。
      前值 <count_prev> 与变化 <count_delta> 仍可引用,为 null 时写"不可得"。
```

3b. 同一文件「第 4 步:生成日报(LLM)」的禁令表末尾(现第 7 条之后)追加一条:

```
8. **事件结论句必须整句照抄进正文。** 要点表里 `events_verdict` 那一句,
   必须在该币种节内**逐字**出现:校验器对报告正文做**精确子串包含**检查,
   改动一个字符(含数字、标点、全角半角)或整句缺失即判违规。
   句子前后可以加你自己的叙述,句内一个字符都不能动。
```

3c. `skills/fx-weekly-report/SKILL.md`「计数与结论纪律」第 1 条(现第 86-89 行),把

```
1. **三条结论句只准照抄,不准改写**:`fixings_verdict`(定盘与区间)、
   `articles_verdict`(事件)、`official_verdict`(公告)。它们已经把观测缺口
   (未采到的日历天数、损坏被跳过的快照、每日上限截断、无法解析的时间戳、
   未记录的定盘日)折算进结论。照抄整句,不要摘出其中的数字另行造句。
```

替换为

```
1. **三条结论句只准照抄,不准改写**:`fixings_verdict`(定盘与区间)、
   `articles_verdict`(事件)、`official_verdict`(公告)。它们已经把观测缺口
   (未采到的日历天数、损坏被跳过的快照、每日上限截断、无法解析的时间戳、
   未记录的定盘日)折算进结论。**整句逐字**照抄,不要摘出其中的数字另行造句。
   校验器对周报正文做**精确子串包含**检查:改动一个字符(含数字、标点、
   全角半角)或整句缺失即判违规。句子前后可以加你自己的叙述,句内一个字符
   都不能动。digest 里有条目的每个币种、每一类结论句都要照抄到位 ——
   `rates` 容器里没有 USD 是正常的(基准货币无定盘价),那一条不用写。
```

- [ ] **T7 Step 4: 跑测试确认通过**

```bash
find . -name __pycache__ -type d -exec rm -rf {} +
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_skill_docs -v
```

Expected: `OK`,`Ran 5 tests`。

- [ ] **T7 Step 5: 勾选并提交**

把 tasks.md 的 `3.1`、`3.2` 改成 `- [x]`,逐条验证后:

```bash
bash ~/.claude/skills/super-coding/scripts/super-coding-state.sh task-checkoff \
  openspec/changes/fx-verdict-enforcement/tasks.md "\`skills/fx-daily-report/SKILL.md\`"
git add skills/fx-daily-report/SKILL.md skills/fx-weekly-report/SKILL.md tests/test_skill_docs.py openspec/changes/fx-verdict-enforcement/tasks.md
git commit -m "docs(skill): 结论句改为逐字整句引用,删掉按布尔拼话术的段落

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 8:变异电池(Design Doc §7 的 10 条靶点)

对应 tasks.md **4.2 / 5.1 / 5.2**。

**Files:**
- Create: `docs/superpowers/evidence/2026-08-13-fx-verdict-mutations.py`

- [ ] **T8 Step 1: 写电池脚本**

创建 `docs/superpowers/evidence/2026-08-13-fx-verdict-mutations.py`:

```python
"""fx-verdict-enforcement 变异电池 —— Design Doc §7 的 10 条靶点。

在**仓库根目录**运行:python3 docs/superpowers/evidence/2026-08-13-fx-verdict-mutations.py

自带三道自检,每一条都来自上一个 change 的实际事故:
1. **基线自检** —— 基线不绿就拒跑并非零退出。一次超时留下的变异体让
   「15/15 KILLED」全部为假杀。
2. **逐字节校验** —— 变异体应用后校验落盘内容与预期逐字节相同,还原后
   校验与原文逐字节相同。写坏或没写进去必须就地炸,不能悄悄跑完。
3. **STALE 硬失败** —— 靶点原文与源码不匹配(0 处或多处)时非零退出。
   归档电池曾在干净副本上只有 26/35,9 个陈旧靶点静默 PATCH-FAIL 却退出 0。

汇总行格式:KILLED k / 执行 n / 登记 m。三者不相等即非零退出。
"""
import os
import subprocess
import sys

C = "scripts/check_report.py"
D = "scripts/collect/derive.py"
V = "scripts/verdicts.py"
FILES = (C, D, V)

M = [
    ("M1 空串放行", C,
     "            if not s.strip():",
     "            if s is None:"),
    ("M2 in 方向写反", C,
     "            if s not in report:",
     "            if report not in s:"),
    ("M3 日报侧根本不查", C,
     '    found, skipped = check_verdicts(report, derived.get("events"),',
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
```

- [ ] **T8 Step 2: 跑电池**

```bash
find . -name __pycache__ -type d -exec rm -rf {} +
python3 docs/superpowers/evidence/2026-08-13-fx-verdict-mutations.py; echo "exit=$?"
```

Expected: 先打印 `BASELINE OK — Ran NNN tests in ...`,再 10 行 `KILLED`,最后 `KILLED 10 / 执行 10 / 登记 10` 与 `exit=0`。

**任何一条 SURVIVED 都必须补测试,不得放过** —— 存活即该分支没被测住。补完测试重跑,直到三个数相等。
**任何一条 STALE** 说明靶点原文与实现不一致:核对 Task 3/4/6 的实现是否逐字照抄了本计划的代码块,或按实际源码重写靶点原文;**不得**把 STALE 当成跳过。

- [ ] **T8 Step 3: 确认没有豁免开关**

```bash
grep -n "legacy\|exempt\|skip.*verdict\|--no-" scripts/check_report.py || echo "无豁免开关"
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest \
  tests.test_check_report.NoLegacyExemptionSwitchTest -v
```

Expected: 第一条只命中 `VERDICT_SKIPPED_LEGACY`(那是**声明**不是开关);第二条 `OK`。CLI 开关集合被 `NoLegacyExemptionSwitchTest` 冻结在 `{--help, --brief, --mode, --strict-brief, --digest, --daily}`。

- [ ] **T8 Step 4: 全量回归**

```bash
find . -name __pycache__ -type d -exec rm -rf {} +
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -t . 2>&1 | tail -3
```

Expected: `OK`(**实跑数字为准,不要预填**)。

- [ ] **T8 Step 5: 勾选并提交**

把 tasks.md 的 `4.2`、`5.1`、`5.2` 改成 `- [x]`,逐条验证后:

```bash
bash ~/.claude/skills/super-coding/scripts/super-coding-state.sh task-checkoff \
  openspec/changes/fx-verdict-enforcement/tasks.md "跑变异电池,全部 KILLED"
git add docs/superpowers/evidence/2026-08-13-fx-verdict-mutations.py openspec/changes/fx-verdict-enforcement/tasks.md
git commit -m "test(mutations): 10 条靶点变异电池,自带基线自检与 STALE 硬失败

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 9:重生成 `reports/weekly/2026-W33.md` + 真实产物端到端复核

对应 tasks.md **4.1 / 5.3**。

历史周报与其配对 digest 已不一致(digest 被重算过,窗口从 5 天变 6 天)。**新校验下它变红是正确行为**,处置是重生成,**不开豁免开关**。

**Files:**
- Modify: `state/weekly-digest-2026-W33.json`(重跑聚合器)
- Modify: `reports/weekly/2026-W33.md`

- [ ] **T9 Step 1: 确认它现在确实红(改之前先看见问题)**

```bash
python3 scripts/weekly_digest.py --week 2026-W33
python3 scripts/check_report.py reports/weekly/2026-W33.md --mode weekly \
  --digest state/weekly-digest-2026-W33.json \
  --daily reports/daily/2026-08-07.md --daily reports/daily/2026-08-08.md \
  --daily reports/daily/2026-08-09.md --daily reports/daily/2026-08-10.md \
  --daily reports/daily/2026-08-11.md --daily reports/daily/2026-08-12.md
echo "rc=$?"
```

Expected: `CHECK FAILED (N)`,`rc=1`,违规里含多条 `VERDICT_NOT_QUOTED`(旧正文写的是 5 天窗口的结论句)与若干 `NUMBER_UNTRACEABLE`。**把实际输出记下来**,后面要逐条消掉。

- [ ] **T9 Step 2: 导出必须逐字出现的全部结论句**

```bash
python3 - <<'PY'
import json
d = json.load(open("state/weekly-digest-2026-W33.json", encoding="utf-8"))
print("窗口 %s .. %s;覆盖 %d 份:%s;skipped=%s"
      % (d["window_from"], d["window_to"], len(d["generated_from"]),
         ", ".join(d["generated_from"]), d["skipped"]))
print("verdicts:", json.dumps(d["verdicts"], ensure_ascii=False))
print("gaps_by_source:", json.dumps(d["gaps_by_source"], ensure_ascii=False))
n = 0
for kind, fields in (("events", ("articles_verdict", "official_verdict")),
                     ("rates", ("fixings_verdict",))):
    for c in sorted(d.get(kind) or {}):
        for f in fields:
            n += 1
            print("\n[%s.%s.%s]\n%s" % (kind, c, f, d[kind][c][f]))
print("\n共 %d 句,全部必须在周报正文里逐字整句出现" % n)
PY
```

Expected: 打印出 14 句(events 5 币种 × 2 + rates 4 币种 × 1)。**这些句子必须原样粘贴进周报,一个字符都不能改** —— 包括全角括号与顿号。

- [ ] **T9 Step 3: 重写周报**

按 `skills/fx-weekly-report/SKILL.md` 第 2 步的模板重写 `reports/weekly/2026-W33.md`。硬性要求:

1. 覆盖声明用 Step 2 打印的实际份数、日期列表与 `window_from`/`window_to`,写成
   `> 覆盖日报:N 份(<日期列表>);覆盖区间 <window_from> 至 <window_to>;缺失日期:无`。
   **N 与日期一律从 Step 2 的输出抄,不许心算。**
2. 五个币种节各自逐字整句包含该币种的 `articles_verdict` 与 `official_verdict`;
   EUR/PHP/THB/BRL 四节各自逐字整句包含其 `fixings_verdict`。
   **USD 在 `rates` 里没有条目(基准货币无定盘价),不写定盘结论句。**
3. 复盘汇总的计数行与 `verdicts` 逐字一致;缺漏汇总必须提及 `gaps_by_source` 的每一个源。
4. 本周主线 ≤ 3 条;一级/二级标题禁止出现日期形式(`## 2026-08-XX`);
   正文提日期一律写完整 `YYYY-MM-DD`。
5. 除结论句里的数字外,**不要引入任何新数字**;需要展开细节时只能引 digest 里已有的值。

- [ ] **T9 Step 4: 先自查 14 句都在,再跑校验器**

```bash
python3 - <<'PY'
import json, sys
d = json.load(open("state/weekly-digest-2026-W33.json", encoding="utf-8"))
r = open("reports/weekly/2026-W33.md", encoding="utf-8").read()
bad = []
for kind, fields in (("events", ("articles_verdict", "official_verdict")),
                     ("rates", ("fixings_verdict",))):
    for c in sorted(d.get(kind) or {}):
        for f in fields:
            s = d[kind][c][f]
            if s not in r:
                bad.append("%s.%s.%s" % (kind, c, f))
print("缺失:", bad or "无")
sys.exit(1 if bad else 0)
PY
echo "quote-check rc=$?"
```

Expected: `缺失: 无`,`quote-check rc=0`。

```bash
python3 scripts/check_report.py reports/weekly/2026-W33.md --mode weekly \
  --digest state/weekly-digest-2026-W33.json \
  --daily reports/daily/2026-08-07.md --daily reports/daily/2026-08-08.md \
  --daily reports/daily/2026-08-09.md --daily reports/daily/2026-08-10.md \
  --daily reports/daily/2026-08-11.md --daily reports/daily/2026-08-12.md
echo "rc=$?"
```

Expected: `CHECK PASSED`,`rc=0`。仍有 `NUMBER_UNTRACEABLE` 就是正文引了 digest 与日报之外的数,删掉那个数,**不要**去放宽白名单。

- [ ] **T9 Step 5: 日报侧端到端复核(存量快照走降级路径)**

```bash
for d in 2026-08-07 2026-08-08 2026-08-09 2026-08-10 2026-08-11 2026-08-12; do
  echo "--- $d ---"
  python3 scripts/check_report.py reports/daily/$d.md data/$d.json \
    --brief briefs/$d-brief.md
  echo "rc=$?"
done
```

Expected: 六天全部 `CHECK PASSED` / `rc=0`,且每天都打印一行 `VERDICT_SKIPPED_LEGACY: N 个币种因快照 schema 过旧(derived.schema_version=1)未校验结论句`。
**「跳过」与「通过」在输出上可区分,这一行就是证据** —— 看不到它说明 Task 6 的 3b 没接上。

再验证新采集的快照走的是强制路径(用临时目录,不落进 `data/`):

```bash
python3 - <<'PY'
import json, sys
sys.path.insert(0, ".")
from scripts.collect import derive
snap = {"date": "2026-08-13",
        "rates": {"PHP": {"primary": 56.0, "ref_date": "2026-08-13"}},
        "events": {"PHP": {"articles": [{"title": "t"}], "channel": "gdelt",
                           "source_cap": 8, "source_capped": False,
                           "count_at_cap": False}},
        "meta": {"caps": {"gdelt_records": 8}}}
d, gaps = derive.derive(snap, [])
print("schema_version:", d["schema_version"])
print("PHP events_verdict:", d["events"]["PHP"]["events_verdict"])
print("gaps:", gaps)
PY
```

Expected: `schema_version: 2`,`PHP events_verdict: 当日采到 1 条`,`gaps: []`。

- [ ] **T9 Step 6: 全量回归 + 勾选提交**

```bash
find . -name __pycache__ -type d -exec rm -rf {} +
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -t . 2>&1 | tail -3
```

Expected: `OK`(**实跑数字为准**)。

把 tasks.md 的 `4.1`、`5.3` 改成 `- [x]`,逐条验证后:

```bash
bash ~/.claude/skills/super-coding/scripts/super-coding-state.sh task-checkoff \
  openspec/changes/fx-verdict-enforcement/tasks.md "重生成 \`reports/weekly/2026-W33.md\`"
git add reports/weekly/2026-W33.md state/weekly-digest-2026-W33.json openspec/changes/fx-verdict-enforcement/tasks.md
git commit -m "fix(report): 重生成 2026-W33 周报,与重算后的 digest 逐句配对

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 10:delta spec 校验与收口

对应 tasks.md **6.1 / 6.2**。两份 delta spec 已在 design 阶段随 `799f3f7` 落盘,本任务负责**验证它们与实现一致**并收口。

**Files:**
- Verify(通常无需修改): `openspec/changes/fx-verdict-enforcement/specs/fx-daily-report/spec.md`、`.../fx-weekly-report/spec.md`

- [ ] **T10 Step 1: 结构校验**

```bash
openspec validate fx-verdict-enforcement --strict; echo "rc=$?"
```

Expected: `Change 'fx-verdict-enforcement' is valid`,`rc=0`。

- [ ] **T10 Step 2: 逐场景核对实现**

对照下表逐条确认,每个 `#### Scenario:` 都能指到一个已通过的测试:

| delta spec 场景 | 落点 |
|---|---|
| 事件结论句落盘 | `tests/test_derive.py::EventsVerdictTest`(全类) |
| 结论句被改动一个字(日报) | `DailyVerdictQuotingTest::test_one_character_changed_is_caught` |
| 结论句整句缺失(日报) | `DailyVerdictQuotingTest::test_whole_sentence_missing_is_caught` |
| 结论句为空串(日报) | `DailyVerdictQuotingTest::test_empty_verdict_is_a_violation` |
| 存量快照无结论句字段 | `DailyVerdictQuotingTest::test_legacy_schema_is_skipped_not_passed`、`DailySkipNoticeIsPrintedTest::test_legacy_notice_printed_alongside_pass` |
| 新 schema 快照漏写结论句 | `DailyVerdictQuotingTest::test_new_schema_missing_field_is_absent` |
| 报告未覆盖某币种(日报) | `DailyVerdictQuotingTest::test_missing_section_does_not_double_report` |
| 数字可溯源 / 引用派生指标 / 派生量缺失时不补算 / 要点表数字溯源 / 未启用要点表溯源 | 既有 `CheckDailyTest`、`StrictBriefTest`(行为不变,保持绿) |
| 结论句与聚合文件不一致 | `WeeklyVerdictQuotingTest::test_articles_verdict_reworded_is_caught` |
| 三类结论句全覆盖 | `WeeklyVerdictQuotingTest` 的 articles / official / fixings 三个用例 |
| 基准货币在定盘容器中无条目 | `WeeklyVerdictQuotingTest::test_base_currency_absent_from_rates_container_is_legal`、`CheckVerdictsCoreTest::test_currency_absent_from_container_is_legal` |
| 结论句为空串(周报) | `WeeklyVerdictQuotingTest::test_empty_verdict_string_is_a_violation` |
| 周报未覆盖某币种 | `WeeklyVerdictQuotingTest::test_currency_not_covered_reports_only_currency_missing` |
| 未提供聚合文件 | `WeeklyVerdictQuotingTest::test_without_digest_object_no_verdict_check`、既有 `test_without_digest_behaviour_unchanged` |
| 历史周报与重算后的聚合文件不配对 | Task 9 Step 1/Step 4 的实跑证据 + `NoLegacyExemptionSwitchTest` |
| 聚合器正常产出 / 跨快照代际 / 决策日志不可用 / 聚合文件不可用时校验必须失败 / 两个事件通道分别计数 / 缺漏源收口 / 全周参考价未更新 / 缺天与坏快照 / 周报数字溯源 | 既有 `tests/test_weekly_digest.py`、`DigestFailClosedTest`、`WeeklyGapOmittedTest`(行为不变,保持绿) |

任一行找不到落点 → 补测试,**不要**改 spec 迁就实现。

- [ ] **T10 Step 3: 最终全量回归 + 电池复跑**

```bash
find . -name __pycache__ -type d -exec rm -rf {} +
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -t . 2>&1 | tail -3
python3 docs/superpowers/evidence/2026-08-13-fx-verdict-mutations.py; echo "exit=$?"
git status --short
```

Expected: 测试 `OK`;电池 `KILLED 10 / 执行 10 / 登记 10` 且 `exit=0`;`git status --short` 干净(电池的 `finally` 已把源码逐字节还原 —— 有残留就是还原失败,立刻 `git checkout` 并查电池)。

- [ ] **T10 Step 4: 勾选并提交**

把 tasks.md 的 `6.1`、`6.2` 改成 `- [x]`。此时 tasks.md 应无剩余未勾选项:

```bash
grep -c '^- \[ \]' openspec/changes/fx-verdict-enforcement/tasks.md || echo "0 项未勾选"
git add openspec/changes/fx-verdict-enforcement/tasks.md
git commit -m "chore(fx-verdict-enforcement): delta spec 校验通过,tasks 收口

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review 记录

**1. delta spec 场景覆盖(28 个 `#### Scenario:` → 任务)**

`fx-daily-report/spec.md` 12 个场景:数字可溯源→既有(T4/T6 保持绿);引用派生指标→既有;派生量缺失时不补算→既有;要点表数字溯源→既有 `StrictBriefTest`;未启用要点表溯源→既有;事件结论句落盘→**T5**;结论句被改动一个字→**T6**;结论句整句缺失→**T6**;结论句为空串→**T6**;存量快照无结论句字段→**T6**(含跳过声明的独立断言);新 schema 快照漏写结论句→**T6**;报告未覆盖某币种→**T6**。

`fx-weekly-report/spec.md` 16 个场景:聚合器正常产出/跨快照代际/决策日志不可用/聚合文件不可用时校验必须失败/两个事件通道分别计数/缺漏源收口/全周参考价未更新/缺天与坏快照/周报数字溯源→既有 `test_weekly_digest.py` 与 `DigestFailClosedTest`/`WeeklyGapOmittedTest`(T4 保证它们保持绿,并把 `test_valid_digest_still_passes` 的 fixture 补成真实形态);未提供聚合文件→**T4**;结论句与聚合文件不一致→**T4**;三类结论句全覆盖→**T4**;基准货币在定盘容器中无条目→**T3+T4**;结论句为空串→**T3+T4**;周报未覆盖某币种→**T4**;历史周报与重算后的聚合文件不配对→**T9**(重生成)+**T8**(开关集合冻结,确认无豁免)。

**无对应任务的场景:0 个。**

**2. 占位符扫描**

全文无 TBD / TODO / 「类似 Task N」/「补充适当的错误处理」/「为上面写测试」。每个改代码的步骤都给了完整可粘贴代码块;每个跑测试的步骤都给了确切命令与预期输出。三处刻意不给字面数字的地方已显式标注理由(全量测试计数、W33 周报正文的实际数值、电池 BASELINE 行的测试数)——按「报告数字硬规则」,这些必须先跑后抄,预填就是错误。

**3. 名称与签名一致性**

- `join_verdict(head, caveats)`:T1 定义;T2 在 `weekly_digest` 两处调用(签名一致);T5 在 `derive._events_verdict` 调用(签名一致);T8 的 M8 靶点指向 T1 的实现原文。
- `check_verdicts(report, container, fields, covered, required, label) -> (violations, skipped)`:T3 定义;T4 用 `found, _ =` 解包;T6 用 `found, skipped =` 解包 —— 返回元组一致。
- 常量 `VERDICT_FIELDS_EVENTS` / `VERDICT_FIELDS_RATES` / `VERDICT_FIELD_DAILY` / `DERIVED_VERDICT_SCHEMA`:T3 定义,T4/T6 引用,T3 与 T6 各有一条断言钉死其字面值与产出端字段名;命名在 T3–T8 全文一致(单数 `VERDICT_FIELD_DAILY` 与复数两个是 Design Doc §3 的原名,刻意保留)。
- 违规码四个:`VERDICT_NOT_QUOTED` / `VERDICT_EMPTY` / `VERDICT_MALFORMED` / `VERDICT_ABSENT`,加一个**非违规**的声明前缀 `VERDICT_SKIPPED_LEGACY`;T3 产出,T4/T6/T8/T9 引用,拼写一致。
- `derive._events_verdict(count, count_capped, sample_capped, channel_changed_from, dropped_malformed, cap)` 与 `derive._cap_phrase(cap)`:T5 定义并在同任务内调用;`events_verdict` 键名与 `VERDICT_FIELD_DAILY[0]` 一致(T6 的 `VerdictFieldSyncTest` 把这一致性变成断言)。
- 测试 fixture:`DIGEST_OBJ` / `DIGEST` / `WEEKLY_OK` / `FIX_PHP` / `ART_PHP` / `OFF_PHP`(T4 定义,T4 内部引用)、`DAILY_VERDICT` / `snap_with_derived` / `report_quoting`(T6 定义,T6 内部引用)—— 无跨任务的悬空引用。
- 电池 10 条靶点的 `old` 原文逐条对应 T1/T3/T4/T6 代码块里的**原样文本**(含缩进与全角标点);任一处实现与计划不符,电池会以 STALE 非零退出,而不是静默跳过。

**4. 已知会红的既有断言(全部是期望行为,处置已写进对应任务)**

| 断言 | 任务 | 处置 |
|---|---|---|
| `tests/test_check_report.py::DigestFailClosedTest::test_valid_digest_still_passes` | T4 Step 1(4b) | fixture 补成真实 digest 形态(带三条结论句),**不放宽 `required`** |
| `tests/test_derive.py:543` 键集哨兵 | T5 Step 3(3c/3e) | 同步 `EMPTY_EVENTS_DERIVED`,**不放宽/不删除断言**;另加 `test_empty_events_derived_carries_the_key` 防两侧一起被删 |
| `tests/test_derive.py:248` `schema_version == 1` | T5 Step 3(3f) | 改 2 |
| `tests/test_snapshot.py:177` `derived.schema_version == 1` | T5 Step 3(3f) | 改 2;**`tests/test_snapshot.py:45` 的顶层 `schema_version` 保持 1** |
