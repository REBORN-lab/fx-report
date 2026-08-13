# Brainstorm Summary

- Change: fx-verdict-enforcement
- Date: 2026-08-13

## 实跑核实的事实(非记忆)

- `check_daily(report, snapshot_text, brief_text, strict_brief=False)` —— 收的是
  快照**文本**,内有 `parse_snapshot(snapshot_text)` 可得 dict
- `check_weekly(report, digest_text=None, daily_texts=(), digest=None)` —— 文本与
  已解析 dict 都收
- `scripts/weekly_digest.py` 全文共 16 处 `caveats.append`(分属 `_verdict` 与
  `_fixings_verdict` 两个函数),拼装形态为
  `head + "(" + "、".join(caveats) + ")"`,无 caveat 时只出 head
- `derive.py` 有独立的 `SCHEMA_VERSION = 1`(与快照顶层 `schema_version` 不是同一个)
- 既有键集断言:`tests/test_derive.py:543` 的
  `assertEqual(set(got), set(derive.EMPTY_EVENTS_DERIVED))` —— 新增字段必须同步
  `EMPTY_EVENTS_DERIVED`,否则该用例红(这是**期望行为**,它就是防漂移的)
- 币种覆盖检查两侧都已有:日报 `SECTION_MISSING: 缺少币种节 X`,周报
  `CURRENCY_MISSING: 周报未覆盖 X`
- 现有违规码 15 个,无任何与 verdict 相关
- 实测 W33 digest 共 **14 条结论句**:`events` 五币种各有
  `articles_verdict` + `official_verdict`(10 条);`rates` 只有四个非美元币种有
  `fixings_verdict`(USD 是基准货币,**`digest["rates"]` 里根本没有 USD 键**)
- digest 顶层另有 `verdicts`(`{"命中":0,…}` 计数 dict)与 `verdict_details`
  (list),那是决策日志复盘统计,**不是结论句**

## 确认的技术方案

### T1 共享实现的形状:一个核心 + 两份「取数说明」

核心函数只认一种形状 —— **`{币种: {字段: 句子}}` 的两层 dict**:

```
check_verdicts(report, groups) -> [violation]
  groups: [(container, fields, covered_predicate)]
```

- 日报:`[(snap["derived"]["events"], ("events_verdict",), 日报的币种节判定)]`
- 周报:`[(digest["events"], ("articles_verdict","official_verdict"), ...),
          (digest["rates"], ("fixings_verdict",), ...)]`

两个调用点只提供**去哪儿取**,判定逻辑只有一份。这与 `landed_count_capped` 的
先例同构(两个消费者共用一个谓词)。

### T2 日报结论句由谁算:共享**拼装器**,不共享**判定**

- 不共享判定:周报的输入是跨日统计(`days_collected`/`window_days`/`in_window`),
  日报是单日事实(`count`/`count_capped`/`sample_capped`/`channel_changed_from`/
  `dropped_malformed`)。定义域不同,强行复用正是第四轮 `_entry_of` 读 `rates`
  那类事故的成因
- 共享拼装:`head + caveats` 的连接与「无 caveat 时只出 head」这条规则抽成
  `join_verdict(head, caveats, undecidable_tpl)`,放进新模块 `scripts/verdicts.py`
  (先例:`scripts/fixings.py` 为 collect 与 weekly_digest 共用)

**缝在拼装处,不在判定处** —— 会漂移的是措辞与连接方式,不能强行合并的是领域逻辑。

### T3 三态边界

| `derived`/`digest` 里的值 | 处置 |
|---|---|
| 非空字符串 | 必须整句出现在报告中,否则 `VERDICT_NOT_QUOTED` |
| **空串或纯空白** | 一律 `VERDICT_EMPTY` —— 任意报告都"包含"空串,这是最明显的假绿入口 |
| 字段缺失 / `null` | 按 `derived.schema_version` 分流(见 T4) |

### T4 存量快照:用 `derive.SCHEMA_VERSION` 当闸门,不用「有没有这个键」

- `derived.schema_version >= 2` → 该字段**必须存在**,缺失即 `VERDICT_ABSENT`
- `< 2`(本变更之前落的快照)→ 跳过该项,并在输出中打印一行「N 个币种因快照
  schema 过旧未校验结论句」

理由:靠「键在不在」判会让一个**新代码产出却漏写该字段**的 bug 静默通过 —— 与
存量快照不可分辨。schema_version 让「这份快照本该有」成为可判定的事实。

### T4b 字段名**显式枚举**,不按 `*verdict*` 模式扫

digest 顶层的 `verdicts` 是计数 dict、`verdict_details` 是 list。任何按名字模式
搜集"结论句字段"的写法都会把它们扫进来,然后在 `x in report` 处 TypeError 或
静默跳过。字段名写死成常量元组。

### T5 币种覆盖 + 容器缺项:两道让位

1. **报告未覆盖该币种**(日报 `find_section` 为空 / 周报 `c not in report`)→
   跳过,两侧都已有 `SECTION_MISSING` / `CURRENCY_MISSING`,重复报错会让同一个
   缺失刷两条违规
2. **容器里没有该币种**(如 `digest["rates"]` 没有 USD)→ 跳过。这是合法形态,
   不是缺字段;只有**币种条目存在**时才要求其字段齐全

## 关键取舍与风险

- **取舍:精确子串,不做相似度。** 代价是报告一个标点写错即失败;收益是没有阈值
  可讨价还价。本仓库历史表明,任何可讨价还价的判据最终都会被绕过。
- **风险:新增 `events_verdict` 后四处要同步**(derive、EMPTY_EVENTS_DERIVED、
  SKILL、校验器)。缓解:`EMPTY_EVENTS_DERIVED` 的键集断言已经会红,是天然哨兵。
- **风险:日报结论句的措辞需要新设计**,可能重演上一个 change 的打磨循环。
  缓解:D4 已把范围限定在 `events` 一类;措辞尽量复用周报已打磨过的用词。
- **风险:`VERDICT_ABSENT` 让所有存量快照的日报变红。** 由 T4 的 schema 闸门挡住。

## 测试策略

先写会红的用例再改代码(上一个 change 的教训:「修复本身零覆盖」被单列成
Critical 四次)。变异靶点清单:

1. 空串放行(`if s:` 写成 `if s is not None:`)
2. `in` 方向写反(`report in s`)
3. 只查一侧(`check_daily` 不调 `check_verdicts`)
4. 三类 verdict 只查一类(`fields` 元组少一项)
5. 存量快照当成通过(schema 闸门反向:`>= 2` 写成 `< 2`)
6. 只查第一个币种(循环写成 `next(iter(container))`)
7. 币种未覆盖时仍报 verdict 错(与 `SECTION_MISSING` 重复)
8. `join_verdict` 在无 caveat 时仍拼出空括号
9. 非字符串值(dict/int)未被拦住,直接进 `in` 判断
10. `check_weekly` 在 `digest is None`(未给 `--digest`)时误报 `VERDICT_ABSENT`

## Spec Patch

delta spec 尚未创建(open 阶段只出了 proposal/design/tasks)。将新建两份:

- `specs/fx-daily-report/spec.md`:MODIFY `### Requirement: 数字纪律`
- `specs/fx-weekly-report/spec.md`:MODIFY `### Requirement: 周报跨日聚合与数字溯源`

各含结论句逐字引用的 SHALL 条文与上述三态、schema 闸门、币种覆盖让位的场景。
