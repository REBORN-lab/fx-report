# Subagent 进度检查点

- Change: fx-verdict-enforcement
- Plan: docs/superpowers/plans/2026-08-13-fx-verdict-enforcement.md(10 个任务)
- base-ref: 799f3f75c1dcae00e67d92e301a9ea2e3a2b7f4a
- build_mode: subagent-driven-development / tdd_mode: tdd / isolation: branch

## 任务映射(plan task → OpenSpec task)

| Plan | 标题 | OpenSpec tasks.md |
|---|---|---|
| T1 | `scripts/verdicts.py` 唯一拼装口 | 2.5(前半,与 T2 合并勾选) |
| T2 | weekly_digest 两个 verdict 改经 join_verdict | 2.5 |
| T3 | 核心谓词 check_verdicts + 三个字段名常量 | 1.1 / 1.3 / 1.5 |
| T4 | check_weekly 接入三类结论句 | 1.2 / 1.4 / 1.6 |
| T5 | derive 落 events_verdict + SCHEMA_VERSION 升 2 | 2.1 / 2.2 / 2.6 |
| T6 | check_daily 接入 + schema 闸门 + 跳过声明 | 2.3 / 2.4 / 2.7 |
| T7 | 两个 SKILL 引用规则 + 文档哨兵 | 3.1 / 3.2 |
| T8 | 变异电池(10 条靶点) | 4.2 / 5.1 / 5.2 |
| T9 | 重生成 2026-W33 周报 + 端到端复核 | 4.1 / 5.3 |
| T10 | delta spec 校验与收口 | 6.1 / 6.2 |

## 当前状态

- 当前 task: **T2**
- 阶段: `implementing`
- 审查-修复轮次: 0 / 3
- 实现提交: (待)
- RED 证据: (待)
- GREEN 证据: (待)
- 未解决反馈: T1 遗留 3 条 Minor,已并入 T2 一并处理(见下)

### T1 遗留 Minor(在 T2 顺手修,那个文件本来就要动)

1. `tests/test_verdicts.py:32` 仍写「整句包含检查是逐字节的」,缺
   `scripts/verdicts.py:27` 已加的「Task 3 起」限定,两处措辞不一致
2. 无用例冻结 `"%r" % (caveats,)` 的元组包装 —— 只有 2 元素以上的 tuple
   能暴露(少了包装会抛 `TypeError: not all arguments converted` 而非
   ValueError);顺带补 `[True]`(bool 是仓库纪律点却无用例)
3. `head=""` 被放行,与 caveat 的非空要求不对称:`join_verdict("", ["甲"])`
   → `(甲)`,一个没有主句的结论句。计划中 head 全是字面量,不可达,
   审查者判为「取舍不大,可不改」

## 已完成

### T1 —— `scripts/verdicts.py` 唯一拼装口 ✅

- 提交: `7747aee`(初版)→ `bc02925`(括号 Critical)→ `ee592bf`(形状门 + 4 Minor)
- RED: 初版 `ModuleNotFoundError`;括号轮 `Ran 6 tests` / `FAILED (failures=4)`;
  形状门轮 `Ran 13 tests` / `FAILED (failures=5, errors=1)`
- GREEN: `Ran 13 tests` / `OK`;全量 `Ran 567 tests` / `OK`(基线 554)
- spec 合规审查 ✅(独立复现全部数字 + 另跑 3 个变异全灭)
- 代码质量审查 ✅(复审独立回退源码复现 RED;确认形状门未过度收紧、
  空序列仍合法;确认与「采集层异常转 gap」纪律**无冲突** ——
  `derive._events_derived` 每币种一个 try/except,`events_verdict` 的调用点在其内)
- plan T1 五步已勾选并经 `task-checkoff` 逐条验证
- OpenSpec 2.5 **暂不勾选**(它同时覆盖 T1 与 T2,T2 完成后一并勾)
