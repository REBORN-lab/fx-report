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

- 当前 task: **T4**
- 阶段: `implementing`
- 审查-修复轮次: 0 / 3
- 实现提交: (待)
- RED 证据: (待)
- GREEN 证据: (待)
- **T4 必须额外完成**(T3 质量审查 I1 的调用点配套,已写进计划文本):
  `digest.get("events")` / `("rates")` 非 dict 时出
  `DIGEST_CONTAINER_MALFORMED`,并补 label 正向断言
- **OpenSpec 1.1 由 T4 勾选**,不在 T3 勾 —— 它写的是「digest 的
  `articles_verdict` 改一个字后**校验**必须失败」,那是 `check_weekly` 层面的
  行为,T3 明确不接线,只有谓词层覆盖。在 T3 勾就是假勾选

### 必须带进后续任务的五条(实测得来)

00. **「让位」类断言极易空过**。T4 实测:计划给的
   `test_currency_not_covered_reports_only_currency_missing` 只删币种名、
   **结论句仍留在正文**,于是 `covered` 恒取全集的变异存活 —— `assertFalse`
   看起来有覆盖,实则毫无鉴别力。**写这类用例必须先断言
   `assertNotIn(<结论句>, bad)`**,让「让位机制」成为不报 VERDICT 的唯一原因。
   T6 的 `test_missing_section_does_not_double_report` 形态不同
   (`make_report()` 本就不含结论句),但**派 T6 时要求实测该变异确被杀**

0. **变异还原禁用 `git checkout HEAD -- <file>`,除非改动已提交**。
   T3 修复轮实际事故:修复尚未提交时用它还原,`HEAD` 是修复前的提交,
   整个未提交的修复被清空(测试文件因单独跟踪幸免)。
   正确做法:**先备份文件、每次变异后从备份恢复**;或先 commit 再变异。
   **T8 电池的 `finally` 还原用的正是内存里的原文快照,符合这条**;
   派发任何「自己跑变异」的任务时必须写明

1. **T8 电池的 kill 判定必须用进程返回码,不能 grep `"FAILED"`** ——
   `tests/test_check_report.py` 自身会向 stdout 打印 `CHECK FAILED (1):`,
   grep 会被污染。T3 审查者的第一版脚本就中招,改用 rc 才修正
2. **变异锚点必须先验唯一**(`grep -c -F`)。`for c in CURRENCIES:` 在
   `check_report.py` 出现 **4 次**,单行锚点不生效且**静默**,跑出的绿是对
   未变异代码跑的。T3 implementer 与审查者各自独立踩到并自曝
3. **代码块里的括号一律 ASCII `(` `)`,顿号才是全角 `、`**。派发时不要写
   「全角括号」——已实测:计划 T3 区段 ASCII 括号 145/143 个、全角 0 个;
   真实 digest 结论句同理。写错会让 T4/T6 逐字比对全线失败

### T3 审查留给 T4/T6 的两条 Minor(T3 不返工)

- **`label` 无测试钉住**:去掉违规信息里的 `%s.%s` 来源前缀,66 个测试全绿
  (变异 M11 存活)。T6 会有三个 label(`digest.events` / `digest.rates` /
  `derived.events`)靠它区分来源,**在 T4/T6 的测试里补一条 label 断言**
- `if s not in report:` 放宽成 `s.strip() not in report` 存活(M12)。
  `join_verdict` 产出的句子首尾从无空白,可达输入域上近似等价变异,风险极低

### 留给 verify 阶段的待办(T4 质量审查提出,不在 T4 处理)

- **退出码不对称**:digest 整体不是 JSON / 不是 dict → `main` 报 rc=2;
  而 `events` / `rates` 容器坏掉 → `check_weekly` 出违规、rc=1。
  运行层后果:SKILL 规定「非 0 → 按违规改一次、二次仍非 0 就盖 ⚠ 出稿」,
  而 LLM 改不动聚合文件,于是烧掉唯一一次重试后盖章出稿。
  完全对称的做法是在 `main` 里补两个容器的 `isinstance` 门 → rc=2,
  同时保留库层违规给直调者。审查已验证对真实产出安全(两容器恒为 dict)。
  **理由不在 T4 做**:计划里没有 `main` 层校验;rc=1 已是响亮失败,
  核心诉求已达成
- **拆 `scripts/check_report.py` 的阈值**(现 364 行 / 20 个违规码):
  文件 > 450 行,或 `check_daily` + `check_weekly` 合计 > 150 行
  (现 121,T6 后约 145,**即将触线**),或出现第三个 `--mode`。
  **必须等 T9 全部落地后再拆** —— T5–T9 每步都嵌了 `check_report.py` 的
  逐字代码块,提前拆会让锚点全部对不上。拆法见审查记录:
  `scripts/check/{common,verdicts,daily,weekly}.py` + 保留
  `scripts/check_report.py` 薄壳再导出(SKILL 命令行与测试全按该路径写)

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

### T3 —— 核心谓词 check_verdicts + 四个常量 ✅

- 提交: `eda00d0`(谓词 + 19 测试)→ `b878f30`(契约表述 + 覆盖补强)
- RED: `Ran 19 tests` / `FAILED (errors=19)`
- GREEN: `Ran 69 tests` / `OK`;全量 `Ran 597 tests` / `OK`
- spec 合规审查 ✅ —— **全角括号 0**;行为对拍 `WEEKLY IDENTICAL` +
  `DAILY IDENTICAL`;未接线(全仓仅一处定义、零调用);变异 14 施加 / 12 杀
- 代码质量审查 ✅ —— 2 Important 已修:①docstring 用假事实为 fail-open 背书
  ②写出不变量 `required=True ⟹ skipped==0`,让 T4 的 `found, _ =` 可证明无损。
  复审:九项无遗漏、不变量破坏组合数 **0**、变异 **4/4**
- **「RED 不红」判定成立**:复审把生产代码换回修复前、测试不变重跑,6 条新
  测试全绿 —— 它们锁的是**已正确但未覆盖**的行为,牙齿由变异杀灭证明
- plan T3 五步 + OpenSpec **1.3 / 1.5** 已勾选;**1.1 留给 T4**(见上)
