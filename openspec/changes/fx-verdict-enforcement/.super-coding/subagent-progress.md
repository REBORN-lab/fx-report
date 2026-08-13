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

- 当前 task: **T7**(两个 SKILL 的引用规则 + 文档哨兵)
- 阶段: `implementing`
- 审查-修复轮次: 0 / 3
- 实现提交: (待)
- **T7 必须额外完成**(T6b 质量审查实测):三个 `VERDICT_*` 码在 `skills/` 里
  0 处出现,运维读到码查不到处置。见下方「T7 必须包含的」一节
- **M2 分隔符收口不塞进 T5 实现**:T5 按计划只 import `join_verdict`,
  **不碰** `scripts/verdicts.py`(T1 已双审定稿)。收口要加 `CAVEAT_SEP`
  常量并改 Design Doc「只含 join_verdict」那句,属独立决定。
  **T5 双审后再评估**:若届时 `derive` 确实需要 verdicts.py 的别的东西,
  一并做;否则记为有理由的不做。理由:T5 本身已覆盖 derive + schema 升级 +
  三个测试文件,再塞会重演上一个 change 的七轮循环

### 必须带进后续任务的五条(实测得来)

00. **「让位」类断言极易空过**。T4 实测:计划给的
   `test_currency_not_covered_reports_only_currency_missing` 只删币种名、
   **结论句仍留在正文**,于是 `covered` 恒取全集的变异存活 —— `assertFalse`
   看起来有覆盖,实则毫无鉴别力。**写这类用例必须先断言
   `assertNotIn(<结论句>, bad)`**,让「让位机制」成为不报 VERDICT 的唯一原因。
   T6 的 `test_missing_section_does_not_double_report` 形态不同
   (`make_report()` 本就不含结论句),但**派 T6 时要求实测该变异确被杀**

000. **kill 判定的两个陷阱是不同机制,两个都要防**:
   - **输出污染**:不能 grep `"FAILED"` —— `tests/test_check_report.py` 自身
     会向 stdout 打印 `CHECK FAILED (1):`
   - **退出码被管道吞掉**:`cmd | tail` 拿到的是 `tail` 的退出码。实证:
     同一条必然失败的命令,经管道 `rc=0`、直接 `rc=1`。
     T5 修复轮实际中招一次(已自曝)
   正确做法:输出重定向到文件后取 `$?`,或用 `subprocess.run(...).returncode`。
   **仓库全局硬规则「守卫调用禁止接 `| tail`/`| grep`」是同一根因** ——
   那条规则原本从守卫误报事故来,这里在变异验证上又撞了一次

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

### 待立为新任务:结论句里的上限取值与判定不一致(T5 spec 审查实测)

**不是假设形态**:真实 11 条事件条目里 **6 条缺 `source_cap`**,该句在库内
**5 处实际触发**;同一天 08-11 周报印「上限 8 条」而日报印「上限不可知」。

根因(已自行读码确认):
- `events.landed_count_capped` 内有闭包 `_cap(key, fallback)`,按通道解析
  `caps["gnews_records"]` / `caps["gdelt_records"]`,缺则退模块常量
  `GNEWS_SOFT_CAP=99` / `MAX_RECORDS=8`
- `derive` 的 `cap` 只取 `entry.get("source_cap")`,没有这两级回退
- 注意 `landed_count_capped` 的 `own = entry.get("source_capped")` 分支
  **不查任何 cap 就返回** —— 所以「判定用了哪个 cap」并非总有定义

**质量审查补充的关键点**:**不要**简单改成「读 `meta.caps` 就完事」——
`count_at_cap` 分支下采集层是拿 `source_cap` 算的,**那条路上 `source_cap`
才是对的数**。所以必须由 `landed_count_capped` **自己吐出它用了哪个上限**,
而不是在外面另立一套优先级。

质量审查还实跑出了发散场景(比 spec 审查的更尖锐):
```
count=50 / count_capped=True(判据用了 meta.caps.gnews_records=50)
verdict = 当日采到 50 条(已顶到当日采集上限(99 条),实际篇数只多不少)
```
一句话里「50 条」与「上限 99 条」并列,而这句会被日报**逐字引用**。
今天不可达(`__main__.py` 把 `meta.caps` 写成同一对常量),但
`landed_count_capped` 的签名与 docstring 就是为 caps 可变而存在的;
上限一旦可配置,这条立刻活。

**正确的修法**:在 `events.py` 的 `landed_count_capped` 旁加兄弟函数,
复用同一段 `_cap()` 与通道分支,返回**它实际用来判定的那个上限**;
无分支消费 cap 时(`own = entry.get("source_capped")` 那条路**不查任何 cap
就返回**)回落到 `entry["source_cap"]`,再退模块常量并标 `assumed`
(沿用 `weekly_digest._cap` 的先例)。derive 用与其余五个 helper 同形的
`_source_cap(snap, currency)` 调它,**不复制通道→键映射**。

**为什么不塞进 T5**:`events.py` 不在 T5 的三文件白名单内;在 derive 里复制
映射正是本仓库反复栽跟头的「两处各写一遍」。

### T7 必须包含的(T6b 质量审查实测 grep 得来)

- **三个 `VERDICT_SKIPPED_*` / `VERDICT_*` 码在 `skills/` 里目前 0 处出现**。
  运维读到码却查不到处置。T7 必须让两份 SKILL.md 逐字包含
  `VERDICT_SKIPPED_NO_DERIVED` / `VERDICT_SKIPPED_LEGACY`,并写明各自该做什么:
  前者 = 快照根本没跑过 derive(或 derive 整体失败)→ **重跑采集**;
  后者 = 跑过但版本低于闸门 → **用当前 `derive` 重新派生该日快照**
- **加一条哨兵测试**:遍历 `check_report.py` 里所有 `VERDICT_*` 前缀,
  断言每一个都在某份 SKILL.md 中出现。这是「码与文档同步」的唯一自动防线

### `check_daily` 的拆分边界(verify 待办,T8 归档后才动)

现 114 行 = 九件事顺序拼接。切成 **4 个私有函数 + 15 行编排壳**:

| 新函数 | 吃什么 | 返回 |
|---|---|---|
| `_daily_structure(secs)` | covered/SECTION_MISSING、摘要条数、币种节字数、复盘节 | `(violations, covered)` |
| `_daily_gaps(secs, snap)` | `GAPS_NOT_DISCLOSED` / `GAPS_MISMATCH` / `GAP_OMITTED` | violations |
| `_daily_verdicts(report, snap, covered, notes)` | 三档兜底 + `check_verdicts` + 两条声明 | violations |
| `_daily_numbers(report, snapshot_text, brief_text, strict_brief)` | 两条数字溯源 | violations |

**三条必须一并写进待办的约束**,否则拆分会把本 change 刚建立的性质拆没:
1. **`covered` 必须由产出 `SECTION_MISSING` 的那个函数返回**(二元组)——
   3a 的全部价值就是「两者物理同源」,单独算一遍就回退了
2. **`notes` 只能是 `_daily_verdicts` 的出参**,保持「声明只有一个产地」
3. 拆前先把 T8 的 9 条变异锚点原文抄进新 change 的 plan(锚点是行文本,
   拆分后需逐条重新定位)

### 留给 verify 阶段的待办(T4 质量审查提出,不在 T4 处理)

- **退出码不对称**:digest 整体不是 JSON / 不是 dict → `main` 报 rc=2;
  而 `events` / `rates` 容器坏掉 → `check_weekly` 出违规、rc=1。
  运行层后果:SKILL 规定「非 0 → 按违规改一次、二次仍非 0 就盖 ⚠ 出稿」,
  而 LLM 改不动聚合文件,于是烧掉唯一一次重试后盖章出稿。
  完全对称的做法是在 `main` 里补两个容器的 `isinstance` 门 → rc=2,
  同时保留库层违规给直调者。审查已验证对真实产出安全(两容器恒为 dict)。
  **理由不在 T4 做**:计划里没有 `main` 层校验;rc=1 已是响亮失败,
  核心诉求已达成
- **拆 `scripts/check_report.py`:阈值已实测越线,本 change 内不拆**。
  T6b 后实测 `check_daily` + `check_weekly` = **181 行**(阈值 150),
  文件 **428** 行(阈值 450)。**不在本 change 内拆的理由**:
  ①T8 的变异电池有 **9 条靶点锚在这个文件里**,拆了全部 STALE
  ②本 change 的范围是「结论句强制引用」,不是「重构校验器」
  ③临近收尾动结构,风险与收益不成比例。
  拆法(质量审查给的,已验证 SKILL 命令行与测试全按 `scripts/check_report.py`
  这个路径写,须保留薄壳再导出):
  `scripts/check/{common,verdicts,daily,weekly}.py` + `check_report.py` 保留
  `main()` 并再导出。顺带把 `check_weekly` 挪到 `main` 之前(现在定义在
  `main` 之后,是这个文件唯一真正碍眼的地方,既有问题非本 change 引入)

- ~~拆 `scripts/check_report.py` 的阈值(现 364 行 / 20 个违规码)~~(下同,已合并到上一条):
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

### T4 —— check_weekly 接入三类结论句 ✅

- 提交: `e5d8873`(接线 + 16 测试)→ `96192ec`(四条 Minor)
- RED: `Ran 84 tests` / `FAILED (failures=9)`
- GREEN: `Ran 85 tests` / `OK`;全量 `Ran 613 tests` / `OK`
- **真实周报按预期从「词袋放行」变为响亮失败**:`CHECK FAILED (22)` rc=1,
  违规差集**恰好** +11 条 `VERDICT_NOT_QUOTED`(无意外增减);
  实测 digest 14 条结论句、**已逐字引用仅 3 条**(events 的 PHP/THB/BRL
  `official_verdict`,且那 3 条是静态串);日报 `CHECK PASSED` rc=0 不变
- spec 合规审查 ✅ —— 并**证伪了「计划原用例够用」**:M5 变异在全部 85 条下
  KILLED,禁用那条自补用例后 **SURVIVED**(`Ran 84 / OK` rc=0),
  证明增补必要;另加跑 8 条变异全杀
- 代码质量审查 ✅ —— 14 条变异 13 杀,存活 1 条经证明是**等价变异**
  (`continue` 与 `pass` 在 T3 契约下行为相同)。4 条 Minor 已修:
  违规码改名让 4 条过滤式断言完备、`covered` 与 `CURRENCY_MISSING` 收进
  同一循环(互为补集,物理上保证一起改)、fixture 噪声、文案
- plan T4 五步 + OpenSpec **1.1 / 1.2 / 1.4 / 1.6**(第 1 组全完)已勾选并验证

### T5 —— derive 落 events_verdict + SCHEMA_VERSION 升 2 ✅

- 提交: `d85f357`(实现 + 14 测试)→ `df4dd0a`(改名 + 关键字调用 + bool 直测)
- RED: `Ran 79 tests` / `FAILED (failures=3, errors=10)`(14 条新用例 13 红;
  第 14 条是非目标守卫,天然从绿开始)
- GREEN: `Ran 96 tests` / `OK`;全量 `Ran 628 tests` / `OK`
- **真实数据上第一次产出日报结论句**(五句,修复前后逐字不变):
  USD「当日采到 11 条(源返回的原始样本顶到其上限,滤后条数是下界)」/
  EUR「当日采到 1 条」/ PHP「当日采到 12 条」/ THB「当日采到 7 条」/
  BRL「当日采到 5 条」;`schema_version: 2`,`gaps: []`
  —— USD 句自洽:`sampled=True` 且 `capped=False`,说的是「原始样本触顶」
  而非「已达采集上限」(这两句话在本仓库被混用过六次)
- spec 合规审查 ✅ —— **键集哨兵断言原文一字未改**(无 diff hunk 覆盖),
  靠两侧同步补键转绿;`_events_verdict` 跑 **432 组全组合**,caveat 与
  传入事实 **0 处不一致**。**注意:那 432 组是审查者的一次性 sweep,
  不在提交代码里,不构成回归保护**
- 代码质量审查 ✅ —— 7 变异 6 杀;实证「采集失败走**正常分支**、只有派生层
  真异常才落 except」,推翻了「一个问题两处报」的疑虑
- 已修:`_cap_phrase` → `_daily_cap_phrase` + 禁止合并的 docstring
  (原 docstring 建立关联却没写禁止,**反而在助推合并**);调用改关键字;
  bool 守卫直测(两名审查者各自独立复现过这条幸存变异)
- plan T5 五步 + OpenSpec **2.1 / 2.2 / 2.6** 已勾选并验证

### T6 —— check_daily 接入 + schema 闸门 + 跳过声明 ✅

- 提交: `3088b5d`;base `7a0660a`
- RED: `Ran 103 tests` / `FAILED (failures=6, errors=5)`
- GREEN: `Ran 103` / `OK`;全量 `Ran 646` / `OK`
- 六天逐日:07–10 `CHECK PASSED` **无声明**(那四天 `derived` 是 `null`,
  确实什么都没跳过);11 声明 + 既有 `GAP_OMITTED` rc=1(基线同样 rc=1);
  12 声明 + `CHECK PASSED`
- 闸门九态分流全对(`True` / `2.0` / `"2"` 都正确走跳过)
- 让位变异 `covered = set(CURRENCIES)` **被杀**,两名审查者各自复现
- spec 合规审查 ✅;代码质量审查 ✅(自建 7 条变异,5 杀 2 存活)
- **两轮审查合并出 T6b**:①②③ 三档兜底 + I1(covered 收进
  `SECTION_MISSING` 循环)+ I2(`check_daily` 补 docstring)+ I3(`%s`→`%r`)
  + I5(`test_bool_schema_version_is_not_a_number` 是恒真用例,变异存活)
  + I6(`notes is not None` 门无测试,变异存活)+ I7(让位断言补反向锚)
  + I8(subTest)
- ~~拆分阈值确认不会触线:143(收口后 146)是本 change 终值,阈值 150~~
  **此条已被 T6b 实测证伪,逐字更正**:实测 `check_daily` 76 → **114** 行、
  `check_weekly` 67 行不变,**合计 181,超阈值 150 共 31 行**;文件
  390 → **428** 行(仍在 450 内)。质量审查估的是 +3,实际 +38 ——
  光 3b 的 docstring 就 10 行、3e 净增 22 行。
  **处置见下方 verify 待办,本 change 内不拆**
- **T8 前置情报**:电池 10 条靶点里落在 `check_report.py` 的 9 条已逐条
  `count()` 验过,**每条恰好匹配 1 处**,不会 STALE
- plan T6 五步 + OpenSpec **2.4 / 2.7** 已勾选;**2.3 留给 T6b**

### T6b —— 日报侧三档兜底(闸门自己的缝)✅

**这个任务不在原计划里,是 T6 两轮审查合并出来的。**

- 提交: `adbb36d`(三档 + T6 的 2 Important + 4 Minor)→ `75c9e51`(同族剩余三口子)
- RED: `Ran 116` / `FAILED (failures=6, errors=4)`;修复轮 `Ran 116` / `failures=10`
- GREEN: `Ran 117` / `OK`;全量 `Ran 660` / `OK`(基线 554 → 660)
- **六天 rc 全程未变**(`0,0,0,0,1,0`),零新增违规,只多出声明
- **协调者复验:十种形态静默通过数 = 0**(此前 4 种静默)
- 审查共堵掉**同族四个口子**:
  ①容器非 dict ②缺币种条目 ③无 derived 节
  ④(修复轮)条目在但不是 dict / schema 旧且无可查条目
- 两条声明现带分母:`5/5 个覆盖币种因快照 schema 过旧(derived.schema_version=1)`
- spec 合规审查 ✅ —— 三条既有测试变更**逐条判定为期望行为**;审查者把
  fixture 默认值改回 `("USD",)` 反证,恰好只有那两条失败
- 代码质量审查 ✅ —— 8 变异 6 杀,2 条存活项(O1/O2)已在修复轮关掉并配哨兵
- **关键克制**:`check_verdicts` 全程一字节未动。O2 那种缝的诱惑是去改共享
  谓词,但那个沉默在周报侧是**必需的**(基准货币在 `rates` 里本就没条目)
- plan T6b 五步 + OpenSpec **2.3 / 2.9** 已勾选并验证

### T7 —— SKILL 引用规则 + 文档哨兵 🔄 修复轮进行中

- 实现提交: `c80d95c`,全量 **667 通过**(基线 660)
- implementer 三处超出指令的正确判断:①自查出计划里禁令表编号已过期
  (实为 8 条不是 7 条)②先跑松正则,发现它会扫到 3 个常量名与
  `VERDICT_SCHEMA`(`DERIVED_VERDICT_SCHEMA` 的子串),收紧为
  `"(VERDICT_[A-Z_]+):` 后恰好 8 个码,**并加了差集哨兵** ③如实自报有一条
  测试没有 RED 阶段
- **spec 合规审查 ❌**,发现五项(F1–F5),已派修复 agent:
  - F1/F2/F3 三处「教 LLM 按布尔拼话术」残留,**F3 是 implementer 未自报的**
  - **F2 是字面冲突**:89 行要求读 `count_capped` 决定措辞,
    79-80 行刚禁止「据 `count_capped` 等自行拼装任何话术」。
    不是死文本——85 行仍允许引用 `count_delta`,而 verdict 的 caveat
    没说 delta=0 是上限产物,直删会留真实缺口 → **改写不删**
  - **F4 最重**:禁令 9 无条件要求逐字引用,但第 2 步规定存量快照写
    「结论句不可得(存量快照)」——**此时没有句子可引**。
    `data/` 下 6 份快照**全部**走这条路;LLM 最可能的行为是自己编一句,
    正是本 change 要杜绝的;而校验器处于 LEGACY 跳过档,
    **没有任何测试能抓到这条矛盾**
  - F5 `VERDICT_SKIPPED_LEGACY` 的处置「用当前 derive 重新派生」无命令可执行

#### 本轮协调者核实与决策(证据已跑)

1. **08-11 的违规数分歧已澄清,两个数都对,只是命令不同**:
   T6/T6b 报 `CHECK FAILED (1)` 跑的是**不带** `--strict-brief` 的形式;
   审查报 `CHECK FAILED (29)` 跑的是 SKILL 第 5 步规定的**带** `--strict-brief`
   形式,多出的 28 条全是 `BRIEF_NUMBER_UNTRACEABLE`(实测分类计数
   28 + 1 `GAP_OMITTED`)。**此后凡引用真实产物校验结果必须同时写明有无该开关。**
   审查另一判断成立:T7 是纯文档改动,这两次运行**对 T7 零证明力**
2. **F5 取「改文案」而非「加 derive-only 入口」**。已实测 `derive(payload, history)`
   的输入全在快照内(`events`/`rates`/`macro` + 历史快照),重新派生**完全离线**,
   技术上可行;**但不做**——重新派生会改写 `data/*.json` 的 `derived` 节,
   而 derive 自采集日以来多次变更,重算可能改动数值,进而让 **6 份已交付日报**
   变红。为一句文案换六份产物返工不划算,且越出本 change 声明的文件范围
3. **由此补出一个审查未点破的缺口,记入 T9**:日报侧结论句闸门**至今只在
   fixture 上验证过**,真实快照一份都到不了闸门,闸门一次都没真正开火。
   T9 增加一项:正常跑一次当日采集(今日 08-13 尚未采集),产出的即是
   **schema 2 真实快照**,让日报侧强制第一次在真实数据上生效。
   不新增 CLI 面、不动任何存量产物

#### 协调者派工书里的错误数字(逐字更正入档)

我在 T7 修复派工书里写「`data/` 下当前 6 份快照**全部**是 schema 1」——**错**。
修复 agent 实测并当场更正,协调者独立复跑确认:

| 快照 | `derived` 实测 | 落到哪个降级码 |
|---|---|---|
| `data/2026-08-07..10`(4 份) | **整节为 null** | `VERDICT_SKIPPED_NO_DERIVED` |
| `data/2026-08-11..12`(2 份) | `schema_version=1` | `VERDICT_SKIPPED_LEGACY` |

6 份**都没有** `events_verdict`,所以 F4 的矛盾确实覆盖全部 6 份,但**分两个码**。
修复 agent 据此把禁令 9 的豁免口扩成同时点名两个码 —— 判断正确,已保留:
只点名一个,另一个码的持有者会以为豁免与自己无关。

### T7 修复第一轮 —— F1–F5 ✅ `e4b646d`

- RED 逐项有实测输出;最终 **670 通过 rc=0**(667 + 3 条新用例)
- 新增 `block()` 段落提取器:整文件断言判不了「这句话有没有落在该落的段里」
  ——「存量快照」在该文件出现多处,只查全文会让禁令 9 缺豁免口也照样绿。
  这是「打印 PASS ≠ 查过了」在测试层的同一形态
- **F3 核实结论(推翻了审查的前提)**:`source_capped` 与 `sample_capped`
  **不是同一信号**。前者是**条目级**(`events.py:232/251/383`,GDELT 补位会覆写);
  后者是 derive 层 `any([source_capped, gnews_filter.capped])`(`derive.py:191-207`),
  **主通道与补位取并**。蕴含单向:`source_capped` ⟹ `sample_capped`,反之不成立

### T7 修复第二轮 —— F6/F7 🔄 进行中

**F6 是第一轮修复自己引入的新矛盾**,不是遗留:禁令 9 新写的豁免口点名
`VERDICT_SKIPPED_NO_DERIVED` 是合法跳过档、无句可引;而降级码表仍写它的处置是
「重跑第 1 步采集」。对那 4 份存量快照该指令跑不通,**理由与 F5 被否掉的完全一样**
(采集窗口已移动)。同一文档一处「不必补救」一处「重跑采集」,「哪一句算数」
无处可判。**这条缝长在本 change 新建的闸门里**,判断同 T6b,当轮修。

F7:`count == 1` 改段落级(每处提及都须落在禁令段内)。原断言的脆点是
implementer 自报的:将来正当地再次提及该布尔时,最省事的「修法」是放宽断言,
而「靠放宽断言消除」在计划里是明令禁止的。

#### 两条判定为超范围、已记入 verify 阶段待办

1. **F2 的替代规则仍只是散文,无强制力**(implementer 自报,判定成立)。
   `count_delta` 作为裸数字仍在要点表里,「不得据它下持平判断」靠提示词纪律,
   校验器不查。真正的不变量修法是让 derive 把变化量折进 `events_verdict`,
   或把 `count_delta` 整个从要点表拿掉 —— 那要改结论句措辞,会连带推翻
   T2–T6 已定的判定与其测试,属于重开已收口的设计。
   **如实记为「缺口收窄但未消除」**
2. **F3 维持改写不删**(与 implementer 的倾向相反,理由入档):它不是第二个
   判定点而是**护栏文本**,且写明了「为什么不能用这个布尔」。删掉只剩「不许用」
   的空白,下一个人会把判定重新加回来;留着「`sample_capped` 覆盖面更宽,
   判定归 `events_verdict`」这条因果,才挡得住同型复发

#### F6/F7 第二轮 ✅ `1b7a234` —— 671 通过 rc=0

- **F6 有真 RED**;RED 时打印的 seg 同时证明 `block()` 停在相邻 bullet 之前
  (`contains LEGACY bullet? False`),四条断言是在 NO_DERIVED 自己那段上过的,
  **不是借邻居文字假绿**
- **F7 是重构既有断言,天然绿 → implementer 用两次变异补出判据**:
  杀伤力变异(冲突句塞回模板段)rc=1 被杀;反向变异(新增一处**正当的**禁令式
  提及)rc=0 保持绿,而旧的 `count == 1` 在此会误红 —— 这正是换判据要买的东西
- 段落级不够细:禁令句与冲突句同处一个 markdown 列表项内、中间无空行,
  按空行切段会把两者判成同一段而**永远为真**。故新增 `sentences()` 按句号切

#### implementer 自报:修这类缺陷时又犯了同一类缺陷(值得单记)

F6 初稿写「窗口长度见 `config/endpoints.json`」—— 实测该文件只有 URL 模板,
**没有任何窗口字段**;真正的窗口在 `scripts/collect/events.py:35`
(`GNEWS_WINDOW_H = 48`)。提交前自查改成指向该源位置。

**这与 F5/F6 修的是同一类缺陷(写一条读者跑不通/查不到的指引),发生在修它的
过程中。** 结论不是「某人疏忽」,而是:此类失效是文档工作的**常态**,
只能靠机械核查兜住,不能靠自觉。

#### 判定为文档哨兵固有天花板,不修,如实入档

- F7 判据 `"禁止" in s and "拼装" in s` 是**散文启发式**:一条措辞不含「拼装」的
  正当禁令(如「不得据 count_capped 造句」)会误红。比 `count == 1` 松,但仍是
  prose-shaped
- `sentences()` 只按 `。` 切:提及若落在无句号收尾的片段(表格单元格、裸 bullet
  尾)会并进相邻句,可能继承邻居的「禁止/拼装」→ 假绿。窄,但真实存在

这类哨兵挡的是「大摇大摆写回判定话术」,挡不住刻意绕。**写清楚边界比假装它严密有用。**

### T7 修复第三轮 —— F8 🔄 进行中

**由 implementer 自己抓出,协调者采纳。** 禁令覆盖 5 个布尔
(`count_capped` / `sample_capped` / `main_sample_capped` / `channel_changed_from` /
`dropped_malformed`),而 F7 的哨兵**只盯住第一个**。implementer 实测另外四个
当前干净(`not-in-a-ban=0`),但没有测试盯着 —— 将来谁把
「`channel_changed_from` 非 null 时改写为……」这类模板句写回去,**全绿照过**。

**同型判定:这就是本 change 被单列四次的「修复本身零覆盖」。
当前状态干净 ≠ 有东西在守着它。**

协调者附加的硬要求:**不许 green-from-start 就算数**。必须逐个布尔各做一次变异
(往模板段塞该布尔的判定话术),证明扩后的哨兵对**每一个**都真能红;
5 个全部 KILLED 才算这次加固有覆盖。

**结果 ✅ `d9277fd`:五个全部 KILLED,每次 `git diff --stat` 还原为空。**
协调者**独立复跑**确认(不采信转述):`Ran 671 tests` / `OK` / `rc=0`。

- **implementer 自查挑明一处会让表读得比实际强的地方**:`main_sample_capped` 是
  `sample_capped` 的**子串**,循环先撞上后者就中止,那一格的失败消息张冠李戴。
  补跑独立循环体确认判据自身成立(`mentions=2 not-in-a-ban=1`,红点正是变异体)
- F3 那段**未动**:`sample_capped` 在第 45 行的提及本就落在
  「**禁止**据它自行拼装任何关于条数多寡的话术」句内。
  **两条放宽路径(改文档措辞迁就测试 / 给判据补等价词集合)都没走**

### T7 修复第四轮 —— F9 🔄 进行中(协调者改口加的最后一轮)

**由 implementer 的残留第 1 条触发,协调者判定为「必修而非可选」。**

`BANNED_BOOLEANS` 是 derive 那五个字段在测试侧的**第二份手抄名单** ——
整个 fx-verdict-enforcement 从头到尾在证「同一份判定不许有第二份拷贝」,
带着手抄名单把哨兵归档,等于在自己刚造好的闸门上留同型缝。判断同 T6b、F6。

漂移方向是**静默失守**:derive 新增第六个布尔、SKILL 禁令写上了,而测试表没跟上
→ 哨兵不守它,全绿照过。**「打印 PASS ≠ 查过了」在本 change 里已出现在第七个层面。**

改法:①循环主语从禁令句正则抽取,无手抄名单驱动哨兵 ②`BANNED_BOOLEANS`
降级为**最小集地板**(抽出集合 ⊇ 这五个),只防「靠删禁令句里的布尔来放绿」
③匹配须子串安全(`main_sample_capped` ⊂ `sample_capped`)。

两次变异证两个方向:**A** 往禁令句加第六个布尔 + 模板段写它的判定话术 → 须红
(证自动跟上);**B** 从禁令句删掉一个现有布尔 → 须红(证地板生效)。

协调者划的边界:**若禁令句格式不足以稳定抽取,不许改禁令句措辞去迁就测试**
—— 那是让文档给测试让路,方向反了;如实停下来报告,由协调者定。

**结果 ✅ `10094b8`。边界起了作用**:implementer 先验格式,发现**天真锚点会抽错** ——
按「含禁止 + 拼装」抽会命中 2 句,把 F3 那句的 `events_verdict` **一并抽成被禁布尔**,
那会要求全文每处 `events_verdict` 提及都落在禁令内,**整个循环失去意义**。
故锚点收紧为 `自行拼装任何话术` 整串(F3 那句是「关于条数多寡的话术」,不含本串)。
**SKILL 措辞一个字未动**,两条让路都没走。

协调者独立复核该论断(未采信转述):严格锚点命中 **1 句**、反引号内容**恰好 5 个字段**;
天真锚点命中 **2 句**并拖进 `events_verdict` —— 与 implementer 所报一致。

- 变异 A(禁令句加第六个布尔 + 模板段写它的判定话术)rc=1 KILLED,
  **测试一个字没改**就自动守住了新布尔
- 变异 B(从禁令句删掉 `dropped_malformed`)rc=1 KILLED,地板断言接住
  「靠削禁令句放绿」这条反向路
- 匹配改**标识符边界**而非最长优先:反引号/空白/中文标点都不是标识符字符,
  `main_sample_capped` 里那一段因前一位是下划线被排除,**不依赖表内先后顺序**
  —— 这正是 F8 那次张冠李戴的根因

#### T7 四轮累计(协调者独立复跑核实)

- `Ran 671 tests` / `OK` / `rc=0`
- 累计只动两个文件:`skills/fx-daily-report/SKILL.md`(+36/-11 区间)、
  `tests/test_skill_docs.py`;`scripts/` 零改动
- implementer 新自报一个耦合点:`BAN_ANCHOR = "自行拼装任何话术"` 是测试对文档
  措辞的硬依赖。**失败方向是安全的**(禁令句改写 → 抽取返空 → 断言报红,
  而非静默放绿),留给代码质量审查评估

### T7 spec 合规复审 🔄 进行中

首轮为 ❌,四轮修复后必须**先复审 spec 合规再进代码质量审查**(不得跳序)。
派工时明确要求:**默认还有第 N 处同型残留没被点名** —— 前两次审查各漏一处
(F3 是首轮 implementer 未自报,F6 是首轮修复自身引入),并要求实跑核对
tasks.md **3.2 周报侧**,不得采信「首轮实现者说过了」。

**结果 ❌ 不通过:2 Critical / 3 Important / 3 Minor,全部带变异证据**
(审查跑 19 个变异,13 KILLED / 6 SURVIVED)。那条「默认还有」的前提押中了。

- **C1(Critical)F6 的修复本身零有效覆盖**。`test_skill_docs.py:179` 的
  `assertIn("重跑", seg)` **空转** —— 「重跑」二字由**另一支**供给。
  实测把 F6 新加的分支一**整段删除**,全量 **rc=0 存活**:F6 被完整回退而测试全绿
- **C2(Critical)tasks.md 3.2 零覆盖**。周报侧断言仍是**全文级**,F7 升段落级时
  没同步。决定性变异:纪律第 1 条改成「`fixings_verdict` 与 `official_verdict`
  **可自行改写**」,与 delta spec「三类结论句全覆盖」**直接相反**,671 全绿
- I1 禁令 9 的**主规则**无覆盖(只有 F4 补的豁免口有):把「该币种节」削成
  「美元节」→ 存活
- I2 F6 只修了第 5 步一侧:第 2 步与禁令 9 仍把 `NO_DERIVED` 等同于「存量快照」。
  后果链条:**同日 derive 崩溃** → 第 2 步贴上事实错误的「(存量快照)」标签 →
  禁令 9 豁免按该字面串生效 → 该币种免除逐字引用,校验器此档只出声明(rc 0),
  **没有第二道拦**
- M-b 与 C1 同因;M-c `source_capped` 不在 F9 守备范围

#### 协调者两处自我更正(逐字入档)

1. **我对用户说过「F9 之后被禁布尔名单不再有任何手抄拷贝」——说过头了。**
   审查实测:F3 那句为避开 `BAN_ANCHOR` 特意写成「关于**条数多寡**的话术」,
   `source_capped` 因此**不被抽取**,只由字面短语黑名单兜着。
   F9 的「唯一事实源」实际只覆盖禁令那一句里的 **5 个**
2. **C1 的疏漏在协调者一侧。** 我要求 F7/F8/F9 逐个做变异证明,**唯独 F6 那轮
   只看了「有真 RED」就放过**。RED 只证明断言当时能红,**不证明它守得住回退** ——
   这两件事的区别正是本 change 的命题本身,而我在自己的验收上漏了它

#### 「测试通过」与「测试能抓住回归」是两回事(第八个层面)

协调者独立复跑的 671 / OK / rc=0 **抓不到 C1 与 C2** —— 通过完全不说明能守住。
本 change 的同一命题至此出现在第八个层面。

### T7 修复第五轮 —— C1/C2/I1/I2/M-b/M-c 🔄 进行中

协调者上一轮说「不再加轮」,此处改口。理由不是反悔:审查用变异证明了两处零覆盖,
而「修复本身零覆盖」是本仓库被单列 Critical 四次的根因,放行即第五次复发。

**本轮硬要求:每条修复都必须配一个能杀掉「该修复被回退」的变异**,
不是只证明断言当时能红。

**结果 ✅ `8e9f752`,9/9 变异全 KILLED。** 协调者独立复跑 `Ran 672 tests` / `OK` / `rc=0`。

- **C2d 是 implementer 自己加的,也是本轮最有价值的一处自查**:发现 C2a 是被
  「摘不到第 1 条」的**提取守卫**杀掉的,而不是被 `assertNotIn("可自行改写")` 杀的
  —— 那条断言当时**等于白写**。遂补一个保留标题、只加例外从句的变体专验它。
  与 C1 同形态(断言被别的机制满足、自己空转),这次是实现者自己抓出来的
- **M-c 需要一处协调者未预见的文档改动**,implementer 停下来问而非自行扩大范围:
  第 2 步含 `source_capped` 的那句原本**不带禁止语**,判据只看句内,照原方案实现
  会立刻红。它把两句合成一句显式禁令。协调者复核实际文本后**接受** ——
  方向是**把描述改成禁止(收紧)**,不是为迁就断言弱化措辞;
  且实测 `BAN_ANCHOR` 抽取仍恰 1 句恰 5 字段,`source_capped` 未被拖进、
  `events_verdict` 未被误抽成被禁布尔
- implementer 一处纪律自我更正:原用 `git diff --stat -- skills/` 判还原得
  `revert_clean=NO`,那是判据写错(本轮改动尚未提交,与 HEAD 有差是应然),
  改用 `diff -q` 与备份比对

#### implementer 的一次自伤(记档,附协调者的准确定性)

docstring 外的说明文字导致 `test_skill_docs` **整模块 ImportError**,
测试数 **671 → 661** 而 unittest 只报 `errors=1`。

协调者定性:仓库判据是**看返回码**,这种情况 `rc=1` 会被抓到;**真正会漏的是
grep "FAILED" 式判法** —— 它看不到「10 个哨兵一个都没跑」。
这恰是仓库那条硬规则(判定只看 rc、禁止 grep FAILED、禁止接管道)的又一实例。

### T7 修复第六轮 —— I2 标签按站点断言 🔄 进行中

由 implementer 疑虑 3 触发。新标签串 `结论句不可得(快照未落结论句)` 实测全文
**4 处**(第 86 定义 / 176 禁令 9 触发 / 247、252 第 5 步引用),而断言只锁
「≥2 次」——**漏改其中一处仍可全绿**。与 C1 同缝:断言被**别处**文字满足。

implementer 提的 `count == 4` **不采纳**:退回 F7 已否掉的计数式脆断言,
将来正当地多写一处引用就误红,而最省事的「修法」又是放宽。
改为**按站点断言**(复用已有的 `block()`),并要求**每站各做一次变异**。

**结果 ✅ `ec6749c`,四站变异 4/4 KILLED,四条失败消息各自指名不同站点。**
协调者独立复跑 `Ran 672 tests` / `OK` / `rc=0`;本轮**纯断言重构,SKILL 文档一字未动**。

**implementer 在变异设计上做了一处协调者没要求的收紧,理由正确:**
协调者建议「改回旧串或换成"不可得"三字」二选一,它**只用后者** ——
改回旧串会被全文那条 `assertNotIn` 接住,那样每站都红,但**红的是全文断言**,
证明不了按站点断言本身有效(正是 C2a 那种「被别的机制杀掉」的形态)。
换成三字后全文 `assertIn` 仍被另外三站满足、`assertNotIn` 不触发,
**只有该站断言会红**,每次变异精确只考一件事。

**这是把 C2d 的教训主动用在下一次变异设计上,而不是等审查再抓一次。**

#### 又一条已知边界(implementer 自报,协调者接受)

7. 按站点断言守的是「这四站都用同一串」,**不守「不存在第五个未登记的站点」**:
   将来在别处新写一处引用而忘了登记进 `LABEL_SITES`,那一处不会被守。
   与 F9「手抄名单」同族,但此处名单是**正则站点表**、无法从文档自动导出

### T7 spec 合规复审第二次 🔄 进行中

派给同一审查者(上下文还在)。要求**独立复验**实现者报的变异结果,
并**重跑上一轮那几个存活的变异**(M13/M17/M11/M16/M18)确认现已全杀。

派工书写明:**默认还有第 N+1 处同型残留** —— 前三次审查各漏一处
(F3、F6、C1/C2);且「这已经是 T7 的第六轮修复,但**轮数不是放行的理由**」。

**结果 ❌,只剩一项必修。** 上轮六项**五项修实**,I1 只修实了一半。
审查复验上轮 6 个存活变异:**5 个转 KILLED**,第 6 个(R-M6)判为**等价变异非缺陷**
—— M-b 的锚点由「存量快照」换成「窗口已移过」后,分支二删掉那个括注语义完整无损。
协调者接受该判定。另实测:旧标签串全文 **0 次**、新标签 **4 次**且与 4 个站点
一一对应无第 5 处;`LABEL_SITES` 四个正则各匹配恰 1 次。

- **I-1(Important)`assertIn("逐字", seg)` 被同段另一句喂饱**。禁令 9 段内
  "逐字" **有两处**:主规则的「必须在该币种节内**逐字**出现」与豁免口的
  「不是免除**逐字引用**的理由」。变异把主规则改成「**可在该币种节内按大意复述**」
  → **存活,672 全绿**;文档字面变成「可按大意复述:校验器做精确子串包含检查,
  改动一个字符即判违规」,自相矛盾,且**直接违反 delta spec「日报 SHALL 逐字
  整句引用」与 tasks 3.1**
- I-2(Minor)第 2 步的指针句无覆盖;删掉后**链条不重开**(三条拦截各有 KILLED
  变异),损失的是冗余提示而非拦截能力

**这是同一形态的第四次(C1、M-b、I1 的一半),且就出现在协调者刚承认过那条
教训的同一个修复里。** 审查原话:「轮数不构成放行理由」。

### T7 修复第七轮 —— I-1/I-2 + 机械普查 🔄 进行中

协调者判定:**不做打地鼠,这个缺陷有机械判据** ——

> 断言的锚点串若在它所摘的段落里出现**超过一次**,就可能被另一处喂饱,
> 该断言守不住「它本该守的那一句被回退」。

要求对 `tests/test_skill_docs.py` **每一条** `assertIn` 数锚点在对应段/全文的出现
次数,**逐条列表**;count > 1 的要么换成该句独有的整串,要么在注释里写明
**为什么被喂饱也不影响它要守的东西**,不许含糊带过。**普查表本身是交付物** ——
下次改这个文件的人有据可依,不必再跑一轮审查。

**结果 ✅ `cf01ef0`,3/3 变异 KILLED。** 协调者独立复跑 `Ran 672 tests` / `OK` / `rc=0`;
实测 `git diff 8e9f752..HEAD -- skills/ scripts/` **输出为空**,纯锚点重构。

**普查方法本身值得记**:它没有人工比对「我以为这条断言摘的是哪一段」,而是
**把 `assertIn` 换成探针,记录运行时真正传进去的 haystack**。原话:
「**普查本身也不该有第二份判定**」—— 把本 change 的命题用在了审计工具自己身上。

**普查捞出一条协调者与审查都没点到的**:#9 第 2 步那条断言原本是**全文级**,
而 `events_verdict` 在全文有 **4 处**,同样被喂饱;已降到段级并换成整条指令
`**逐字整句照抄**\`derived.events.<币种>.events_verdict\`` 作锚点(count=1)。

全 40 条断言,修前 **11 条** count>1,修后余 **9 条**,分两类书面说明:
- **#13 标签串(4 次)**:只是「标签整个消失」时给一条干脆的失败消息;真正的守卫
  是按站点那四条(各 count=1)。**它自己承认任一站被改写时这条确实会被另外三站
  喂饱**,主张该站自己的断言会红
- **#26–33 八个码(2–4 次)**:契约就是「**至少有一份** skill 写了它」,多处出现
  正是想要的语义;「某一处处置被删」由各自处置段的 `block()` + `assertIsNotNone` 守

变异 M1 **刻意保留**「该币种节」与豁免口的「逐字引用」—— 即被喂饱的那个形态,
现在被抓住。

#### implementer 自报两类普查判据够不到的形态(本轮未改)

- `assertTrue("禁止" in s and "拼装" in s)` 不是 `assertIn`,其「段」单位是**句子**
  而非段落;称已由 F8/F9 的 9 次变异逐字段验过
- `assertFalse(missing, ...)`(F9 地板)不是成员断言,称由 C2b/C2c/变异 B 守着

### T7 spec 合规复审第三次 🔄 进行中

派工要求独立复验普查表,**重点验它「保留」的那 9 条是论证成立还是自我开脱** ——
特别是 #13 那条自认会被喂饱的;并核 implementer 关于两类判据外形态「已被变异验过」
的说法。前四次审查各漏一处(F3、F6、C1/C2、I1 一半),**默认还有第 N+2 处**。

#### verify 待办新增(审查提的权重升级,协调者接受)

8. **「窗口是否仍覆盖 DATE」现在是纯散文,却成了禁令 9 是否适用的开关。**
   校验器只发不分支的 `VERDICT_SKIPPED_NO_DERIVED`(`check_report.py:229`),
   **从不告诉运维属哪一支**;而文档(有意地)拒绝抄窗口数值,要求读者自己去
   `events.py` 读 `GNEWS_WINDOW_H` / GDELT `timespan` 再做日期比较。
   **本轮之后它从「一条建议」升级为「一条硬规则的触发条件」,风险等级变了。**
   修法要动 `scripts/`(`check_report` 已拿得到 DATE,可直接在声明里印出属哪一支),
   不在 T7 内。这不是重议已决事项,是该事项的权重变了

审查复核后**同意**另三条已知边界均非 Critical:黑名单只挡一种措辞、C2a 依赖提取
失败、站点表无法自动导出 —— 三者的**正面断言都已实测有效**,失效模式是
**误红而非漏红**。

#### 判定为已知边界,不修,如实入档

5. `assertNotIn("可自行改写", seg)` 是**黑名单**,只挡这一种措辞;换成
   「该条可径行归纳」之类同义表达即可绕过。**正面断言(三字段名 + 不准改写)
   是主防线,它只是补丁 —— 不读成「摘字段的路已封死」**
6. C2a 的 kill **依赖 block 提取失败**:将来有人改写第 1 条标题但保持三字段与
   规则完整,会因「没摘到」而误红。修法是调锚点,**注意别顺手把段落级降回全文级**

#### 判定为超范围、记入 verify 待办(本轮不碰)

3. **I3 `attributable_source_absent`**(`SKILL.md:39-44`):同型第 N 处,仍在教
   LLM 按三态自己组织判定话术,且比 F3 更硬(F3 改写后只剩禁令,这处仍在**教怎么写**)。
   审查判定**不算 T7 违反 spec** —— delta spec 对结论句输入穷举五项、不含它,
   tasks 2.2 明写「仅 events 一类」。修法需采集层补 `attributable_verdict`
   或并进 `events_verdict` → 下一 change
4. **M-a `scripts/collect/derive.py:326-327`**:注释仍写「报告**只引用**这个布尔
   (`main_sample_capped`)」,而 SKILL 现已把它列入禁止清单 —— **代码注释与提示词
   直接矛盾**,正是本 change 要消灭的「两处各写一遍」,只是这次落在注释里。
   附带:`main_sample_capped` 落盘后**已无消费者**。要动 `scripts/`,超范围
