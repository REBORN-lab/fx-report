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

- 当前 task: **T3**
- 阶段: `implementing`
- 审查-修复轮次: 0 / 3
- 实现提交: (待)
- RED 证据: (待)
- GREEN 证据: (待)
- 未解决反馈: 见下方「已决定的处置」(M2 挂 T5)

### 已决定的处置

- **M2 分隔符收口挂到 T5**:`_verdict:480` 仍自写 `"、".join(caveats)`,顿号
  存在于两处。整条路由进拼装口会改输出(句中嵌入形态,非括注形态);只收口
  分隔符可逐字节相同(已验),但要改 `scripts/verdicts.py`,而 Design Doc
  明写该模块「只含 join_verdict」。T5 让 `derive._events_verdict` 成为第三个
  消费者时才是自然时机
- **不做**:M4(STATS 重复)、M5(断言冗余,逐字节契约下的刻意冗余)、
  M6(`RefactorIsByteIdenticalTest` 改名会让计划正文对不上)
- **明确不做**:把 `_verdict` 兜底句或 `_fixings_verdict` 无 caveat 分支也套进
  拼装口。审查者验过逐字节相同,但那会把「全区间采集完整」这类肯定性条件与
  日期区间当成 caveat 塞进形状门,`caveats` 就从「观测缺口清单」降格成
  「任何要加括号的东西」,形状门失去语义
- T1 遗留 3 条 Minor:前两条已在 `c9601c4` 修掉;第三条(`head=""` 不对称)
  按审查者判断不改

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

### T2 —— weekly_digest 两个 verdict 改经拼装口 ✅

- 提交: `c9601c4`(三处编辑)→ `3950145`(mock 断言 autospec + 边界注释)
- RED: `Ran 21 tests` / `FAILED (errors=2)`,
  `AttributeError: ... does not have the attribute 'join_verdict'`
- GREEN: `Ran 21 tests` / `OK`;全量 `Ran 575 tests` / `OK`
- spec 合规审查 ✅ —— **穷举对拍 4896 组不一致 0**(`_verdict` 4608 +
  `_fixings_verdict` 288),且核过对拍有效性:旧模块源码 `join_verdict` 出现
  0 次、两模块 `__code__` 不同一、被改分支分别走了 1512 / 264 次;
  端到端 `build` 全量 JSON 新旧**逐字节相同**(12289 字符);
  mock 用例经变异证明非假绿
- 代码质量审查 ✅(复审再次变异验证会红);无 Critical
- plan T2 五步 + OpenSpec **2.5** 已勾选并经 `task-checkoff` 验证
- 记一笔:implementer 自述 diff `+9/-8`,实测 `--numstat` 为 `+8/-8`(数字硬规则)
