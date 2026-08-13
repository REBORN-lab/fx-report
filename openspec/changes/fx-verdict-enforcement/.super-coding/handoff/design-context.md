# SuperCoding Design Handoff

- Change: fx-verdict-enforcement
- Phase: design
- Mode: compact
- Context hash: afeae2f96f8438e56484ff156580796d215f278f348c75b500b32fd10a5103cc

Generated-by: super-coding-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/fx-verdict-enforcement/proposal.md

- Source: openspec/changes/fx-verdict-enforcement/proposal.md
- Lines: 1-65
- SHA256: 6e057a27b352030d86df300bec74682e61e4e51a6105f9f2ee3ee11ef1fa9cad

```md
## Why

仓库用七轮对抗性审查把「能不能下结论」从 LLM 手里收回脚本(见归档 change
`2026-08-13-fx-gnews-event-channel`),但**执行环节是空的**:`scripts/check_report.py`
里 `verdict` 零命中,从不校验报告是否逐字引用了脚本算好的结论句。

实测(2026-08-13):周报正文写「区间内至少 15 条(3/5 天未采到)」,而配对的
`state/weekly-digest-2026-W33.json` 里 USD 的 `articles_verdict` 是「区间内至少
26 条(3/6 天未采到、…)」,

```
python3 scripts/check_report.py reports/weekly/2026-W33.md \
        state/weekly-digest-2026-W33.json --mode weekly
→ CHECK PASSED
```

原因:数字白名单是**无序词袋**——`numbers_in(report) - allowed`,只验「这个数在
聚合文件的 JSON 文本里出现过」,不验它出现在哪个字段。15 与 5 作为无关数字出现
在别处即通过。

后果:脚本算得再对,报告不引用也没人拦。前一个 change 建立的全部不变量因此没有
强制力。这是当前最高优先级的缺口。

## What Changes

- 校验器新增**结论句逐字引用检查**:聚合文件/快照中每个「脚本给出的结论」字段,
  其字符串必须整句出现在报告正文中,改一个字即失败
- `scripts/collect/derive.py` 为日报侧落**同构的结论句字段** —— 日报的 `derived`
  目前全是数值与布尔(`count_capped`/`sample_capped`/`channel_changed_from` 等),
  没有任何 `*_verdict`,结论句由 LLM 按 SKILL 模板拼装
- 两个 SKILL 的引用规则改为「逐字引用该字段」,删去让 LLM 自行按布尔拼话术的段落
- 保留既有的数字词袋检查作为**外层弱网**(覆盖结论句之外的散落数字),
  保留 `--strict-brief` 现有行为不变

**不做**(拆为后续 change `fx-collect-precision`):采集层数值精度统一;
被白名单滤除的域名落盘。

**不做**:不改结论句的措辞与判定逻辑——那是前一个 change 的成果,本次只补强制力。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `fx-daily-report`:`### Requirement: 数字纪律` —— 新增「结论由脚本给出、报告
  逐字引用」的强制条文;日报侧此前只有「报告 ⊆ 快照 ∪ 要点表」的集合式溯源
- `fx-weekly-report`:`### Requirement: 周报跨日聚合与数字溯源` —— 同上;此前
  只有「周报 ⊆ 聚合文件 ∪ 当周日报 ∪ 小整数」

两个能力属同一执行机制的两半,**刻意不拆**为两个 change:拆开会让其中一侧在
交付后一段时间内仍无强制力,而「一侧接上、另一侧没接」正是前一个 change 里
反复出现的失败模式(第五轮 Critical:字段落盘了、周报接上了、日报那侧没接)。

## Impact

- `scripts/check_report.py`(新增检查;既有检查不变)
- `scripts/collect/derive.py`(新增结论句字段;判定逻辑不变)
- `skills/fx-daily-report/SKILL.md`、`skills/fx-weekly-report/SKILL.md`(引用规则)
- **既有交付产物**:`reports/weekly/2026-W33.md` 在新校验下会变红——它与配对的
  digest 确实已不一致(digest 被重算过)。处置方式在 design 阶段决定:重生成该
  周报,或为历史产物提供明确的「不可校验」标记。这是本 change 的关键未知项之一。
- 零新增依赖(Python 标准库);零 API key 影响
```

## openspec/changes/fx-verdict-enforcement/design.md

- Source: openspec/changes/fx-verdict-enforcement/design.md
- Lines: 1-91
- SHA256: 16514998235fe6717aad2432dbc6033c3d6f444ca1d52faec3334f3789edb488

[TRUNCATED]

```md
## Context

`scripts/check_report.py` 现有两层检查:结构检查(节是否齐、币种是否覆盖、缺漏是否
披露)与**数字溯源**。数字溯源的实现是集合差:

```python
allowed = numbers_in(digest_text) | ALLOWED_SMALL | ⋃ numbers_in(daily)
for n in sorted(numbers_in(report) - allowed):
    v.append("NUMBER_UNTRACEABLE: ...")
```

即「报告里的每个数,必须在聚合文件的 JSON 文本里出现过」。这是**无序词袋**:不问
它出现在哪个字段、更不问脚本算好的整句结论是否被引用。

两侧的现状不对称(实测):

| | 结论句字段 | 报告如何得到结论 |
|---|---|---|
| 周报 | `articles_verdict` / `official_verdict` / `fixings_verdict` | 应逐字引用 digest |
| 日报 | **无** | LLM 按 SKILL 模板,从 `count_capped`/`sample_capped`/`channel_changed_from` 等布尔拼装 |

## Goals / Non-Goals

**Goals:**
- 脚本算出的结论句具备强制力:报告改一个字、或整句缺失,校验必须失败
- 两侧用**同一套机制**,不引入第二处判定
- 结论句之外的散落数字仍有兜底

**Non-Goals:**
- 不改结论句的措辞与判定逻辑(前一个 change 的成果)
- 不做采集层数值精度统一、不做被滤域名落盘(后续 change)
- 不把报告结构化到「每个数字标注出处字段」的程度——那对中文叙事不现实

## Decisions

### D1:统一成一套,而不是两套机制

考虑过的方案:

| | A:两套 | B:统一(**采用**) |
|---|---|---|
| 周报 | digest 的 `*_verdict` 整句包含 | 同左 |
| 日报 | 校验器硬编码「布尔→固定话术」条件表 | `derive` 也落结论句,同样整句包含 |
| 代价 | 小 | 需要为日报设计结论句 |
| 风险 | 话术在 SKILL(散文)与校验器(代码)**两处各写一遍** | 单一事实来源 |

A 方案技术上可行——已在 2026-08-12 实报上跑通条件式检查,3 个条件触发全部一致。
但它的风险正是本仓库反复栽跟头的失败模式:**同一判定两处各写一遍而漂移**
(`scripts/fixings.py` 的注释记录过一次;前一个 change 的第四、七轮各记录过一次)。
故取 B。

### D2:「整句包含」而非「相似度」或「结构化标注」

判据为 `digest[field] in report_text`(精确子串)。理由:
- 改一个字即失败,没有阈值可争
- 句内所有数字因此被自动绑定,是词袋问题对结论句的直接解药
- 对报告行文自由度的约束是「必须原样引一句」,而非「整段照抄」——报告仍可在
  句子前后加自己的叙述

### D3:词袋检查保留为外层弱网

结论句之外仍有散落数字(汇率、区间、实际利率)。整句检查不覆盖它们,故保留现有
集合差检查。两层是「与」关系,不互相替代。

### D4:日报结论句的覆盖范围 —— 先做事件一类

日报 `derived` 有三类:`events`(事件数与截断)、`rates`(涨跌与区间)、
`real_rate`(实际利率)。本次**只为 `events` 落结论句**,理由:
- 事件那一类正是前一个 change 七轮审查的战场,判定最复杂、最容易被叙述错
- `rates` 与 `real_rate` 是纯数值,词袋弱网对它们已基本够用
- 范围过大会重演七轮循环 —— 前车之鉴就在同一个仓库

`rates` / `real_rate` 的结论句留待后续 change,在 tasks 里明确记为非目标。

### D5:历史产物的处置

`reports/weekly/2026-W33.md` 与其配对 digest 已不一致(digest 被重算过),新校验下
必然变红。**这是正确行为**,不是校验过严。处置取「重生成该周报」而非「给历史产物
开豁免口子」——豁免机制本身会成为下一个绕过点。

```

Full source: openspec/changes/fx-verdict-enforcement/design.md

## openspec/changes/fx-verdict-enforcement/tasks.md

- Source: openspec/changes/fx-verdict-enforcement/tasks.md
- Lines: 1-39
- SHA256: e0847d6550b58959e4099d2fb0df3a56f8a0b6c5aad3e9b592f3c9f24e246f7e

```md
## 1. 周报侧:结论句逐字引用

- [ ] 1.1 先写会红的用例:digest 的 `articles_verdict` 改一个字后校验必须失败;整句缺失必须失败;完整引用必须通过
- [ ] 1.2 `check_weekly` 新增 `VERDICT_NOT_QUOTED` 检查,覆盖 `articles_verdict` / `official_verdict` / `fixings_verdict` 三类
- [ ] 1.3 三态处理:digest 中该字段缺失或非字符串时不得当成空串通过(空串会让任意报告都"包含"它)
- [ ] 1.4 只对报告实际覆盖的币种要求引用;digest 有而报告未覆盖的币种走既有 `CURRENCY_MISSING`,不重复报错
- [ ] 1.5 字段名显式枚举为模块级常量,不按 `*verdict*` 模式扫(digest 顶层的 `verdicts` 是计数 dict、`verdict_details` 是 list,会被模式匹配扫进字符串比对)
- [ ] 1.6 容器中不存在某币种条目时跳过(`digest["rates"]` 没有 USD 是合法形态,不是缺字段);未提供 `--digest` 时不得报 `VERDICT_ABSENT`

## 2. 日报侧:derive 落同构结论句

- [ ] 2.1 先写会红的用例:`derived.events.<币种>` 必须含结论句字段,且其内容随 `count`/`count_capped`/`sample_capped`/`channel_changed_from` 变化
- [ ] 2.2 `derive.py` 新增事件类结论句(仅 `events` 一类;`rates` 与 `real_rate` 明确非目标)
- [ ] 2.3 存量快照无该字段时的三态:校验器判为"该日不可校验"而非"通过",并在输出中区分于"引用错误"
- [ ] 2.4 `check_daily` 接入同一套整句包含检查,复用周报侧的实现(禁止两处各写一遍)
- [ ] 2.5 新建 `scripts/verdicts.py`,只含 `join_verdict(head, caveats)`;`weekly_digest._verdict` 与 `_fixings_verdict` 的拼装改经它,判定逻辑一行不改(共享拼装,不共享判定)
- [ ] 2.6 `derive.SCHEMA_VERSION` 升到 2,同步 `EMPTY_EVENTS_DERIVED`;`tests/test_derive.py` 的键集断言会红,那是防漂移哨兵,不得靠放宽断言消除
- [ ] 2.7 校验器按 `derived.schema_version >= 2` 分流存量快照,并在输出中打印「N 个币种因快照 schema 过旧未校验结论句」——「跳过」与「通过」必须可区分

## 3. SKILL 引用规则

- [ ] 3.1 `skills/fx-daily-report/SKILL.md`:事件结论改为「逐字引用 `derived.events.<币种>` 的结论句」,删去让 LLM 按布尔拼话术的段落
- [ ] 3.2 `skills/fx-weekly-report/SKILL.md`:确认三类 verdict 的引用规则写明「整句逐字」,补上此前未明确的部分

## 4. 历史产物处置

- [ ] 4.1 重生成 `reports/weekly/2026-W33.md` 使其与当前 digest 配对,并通过新校验
- [ ] 4.2 确认不引入任何"历史产物豁免"开关(豁免机制会成为下一个绕过点)

## 5. 变异靶点与回归

- [ ] 5.1 逐条列出必须被杀掉的变异靶点(Design Doc §7 已定 10 条:空串放行、`in` 方向反、只查一侧、三类只查一类、schema 闸门反向、只查第一个币种、覆盖让位失效、`join_verdict` 空括号、非字符串未拦、`digest is None` 误报)
- [ ] 5.2 跑变异电池,全部 KILLED;电池脚本归档至 `docs/superpowers/evidence/` 并自带基线自检与 STALE 硬失败
- [ ] 5.3 全量测试通过(基线 554),真实产物端到端复核(日报 + 周报各跑一次校验器)

## 6. delta spec

- [ ] 6.1 `specs/fx-daily-report/spec.md`:MODIFY `### Requirement: 数字纪律`,补结论句逐字引用条文与场景
- [ ] 6.2 `specs/fx-weekly-report/spec.md`:MODIFY `### Requirement: 周报跨日聚合与数字溯源`,同上
```

## openspec/changes/fx-verdict-enforcement/specs/fx-daily-report/spec.md

- Source: openspec/changes/fx-verdict-enforcement/specs/fx-daily-report/spec.md
- Lines: 1-62
- SHA256: 3dbad32113696eab94d438df9bf71bc0550681519c56c610d2f52975321822bd

```md
## MODIFIED Requirements

### Requirement: 数字纪律
日报中的全部汇率与指标数字 MUST 逐字来自数据快照文件;LLM MUST NOT 自行计算、估算或回忆任何行情数字。派生定量(涨跌百分比、区间、实际利率等)SHALL 由采集层脚本确定性计算并落入快照 `derived` 节,日报与要点表 MAY 逐字引用该节数值——该路径不构成 LLM 计算;快照未提供的派生量 MUST NOT 由 LLM 补算。要点表本身 SHALL 可被校验为其数字均出自快照:校验器 SHALL 提供开关对 `要点表 ⊆ 快照` 做溯源检查,新生成的报告流程 MUST 启用该开关。

采集层 SHALL 为每个币种的事件类判定落盘一条**面向读者的结论句**,置于快照 `derived` 节;该句 SHALL 由当日事实(事件条数、是否顶到当日采集上限、源返回样本是否触顶、通道是否更换、结构不可识别的条数)确定性组合而成,MUST NOT 由报告层按布尔字段自行拼装话术。理由:同一判定若在提示词(散文)与脚本(代码)两处各写一遍,两份措辞必然漂移,而「哪一份才算数」无处可判。

日报 SHALL **逐字整句引用**该结论句;校验器 SHALL 对报告正文做精确子串包含检查,结论句被改动一个字符或整句缺失时 SHALL 判为违规。数字词袋溯源(`报告 ⊆ 快照 ∪ 要点表`)SHALL 保留为外层弱网,覆盖结论句之外的散落数字;两层是「与」关系,MUST NOT 互相替代——词袋检查只验「这个数在快照文本里出现过」,不验它出现在哪个字段,因此单靠它,一句数字全错的结论仍可通过。

结论句字段的取值 SHALL 分三态处理:非空字符串按整句包含判定;**空串或纯空白 SHALL 判为违规而非通过**(任意报告都「包含」空串,这是最直接的假绿入口);非字符串的值 SHALL 判为结构违规。字段缺失或为空值时,SHALL 依快照 `derived` 自身的 schema 版本分流——版本已保证该字段存在的,缺失即违规;版本早于本能力的存量快照,SHALL **跳过并在校验输出中如实声明跳过了几条**,MUST NOT 与「通过」在输出上不可分辨。判据 SHALL 为 schema 版本而非「这个键在不在」:后者会让**新代码产出却漏写该字段**的缺陷与存量快照完全同形,静默通过。

结论句字段名 SHALL 显式枚举,MUST NOT 按名字模式搜集——聚合文件与快照中另有以 verdict 命名的**统计计数**结构,模式匹配会把它们扫进字符串比对。

报告未覆盖某币种时 SHALL 跳过该币种的结论句检查,由既有的「缺少币种节」检查报告;同一处缺失 MUST NOT 产生两条违规。

#### Scenario: 数字可溯源
- **WHEN** 日报正文引用某汇率或指标值
- **THEN** 该数值能在当日快照文件中逐字找到

#### Scenario: 引用派生指标
- **WHEN** 日报引用日涨跌百分比、近 5 运行日区间或实际利率
- **THEN** 该数值逐字取自快照 `derived` 节,且实际利率同时给出政策利率与 CPI 的期号

#### Scenario: 派生量缺失时不补算
- **WHEN** 快照 `derived` 中某项为 null
- **THEN** 日报如实说明该派生量不可得,MUST NOT 由 LLM 自行计算替代

#### Scenario: 要点表数字溯源
- **WHEN** 启用要点表溯源开关校验日报
- **THEN** 要点表中不在 快照 ∪ 小整数 之内的数字被判为不可溯源

#### Scenario: 未启用要点表溯源
- **WHEN** 未启用该开关
- **THEN** 校验行为与既有一致(只查 报告 ⊆ 快照 ∪ 要点表)

#### Scenario: 事件结论句落盘
- **WHEN** 采集层为某币种产出事件类派生量
- **THEN** `derived` 节同时含一条完整的中文结论句,其内容随事件条数、采集上限触顶、样本触顶、通道更换与不可识别条数而变化

#### Scenario: 结论句被改动一个字
- **WHEN** 日报把结论句中的任一字符改写(含数字、标点、措辞)
- **THEN** 校验失败并指出该币种、该字段与期望的整句原文

#### Scenario: 结论句整句缺失
- **WHEN** 日报正文完全没有出现某币种的结论句
- **THEN** 校验失败,MUST NOT 因该句的各个数字分别在快照中出现过而通过

#### Scenario: 结论句为空串
- **WHEN** 快照中某币种的结论句字段为空串或纯空白
- **THEN** 校验失败,MUST NOT 因「任意文本都包含空串」而通过

#### Scenario: 存量快照无结论句字段
- **WHEN** 校验的快照 `derived` schema 版本早于本能力
- **THEN** 跳过结论句检查,并在输出中声明因 schema 过旧跳过了几个币种;MUST NOT 判为通过,也 MUST NOT 判为违规

#### Scenario: 新 schema 快照漏写结论句
- **WHEN** 快照 `derived` schema 版本已保证该字段存在,但某币种的结论句字段缺失或为空值
- **THEN** 校验失败——该形态是脚本缺陷,MUST NOT 与存量快照同等对待

#### Scenario: 报告未覆盖某币种
- **WHEN** 日报缺少某币种的整节
- **THEN** 只报告「缺少币种节」一条违规,MUST NOT 同时再报该币种的结论句未引用
```

## openspec/changes/fx-verdict-enforcement/specs/fx-weekly-report/spec.md

- Source: openspec/changes/fx-verdict-enforcement/specs/fx-weekly-report/spec.md
- Lines: 1-82
- SHA256: af76539cdce6dc0e617ecfa355beb2fde8a2fc5f5b34bdfa9f16fd5ab0d8d437

[TRUNCATED]

```md
## MODIFIED Requirements

### Requirement: 周报跨日聚合与数字溯源
系统 SHALL 提供脚本级的周度聚合器,读取近 7 日快照与决策日志,确定性计算周涨跌、周高低区间、事件计数、缺漏按源统计与复盘结论计数,并落盘为结构化文件;任一输入缺失时该项 SHALL 记为 null 而非省略或填零。周报中的数字 MUST 逐字来自该聚合文件或当周日报原文;校验器 SHALL 在提供聚合文件时对周报执行与日报同级的数字溯源。

聚合器为事件类与定盘类判定产出的**面向读者的结论句** SHALL 具备强制力:周报 SHALL 逐字整句引用,校验器 SHALL 对周报正文做精确子串包含检查,结论句被改动一个字符或整句缺失时 SHALL 判为违规。数字词袋溯源(`周报 ⊆ 聚合文件 ∪ 当周日报 ∪ 小整数`)SHALL 保留为外层弱网;两层是「与」关系,MUST NOT 互相替代。实测本能力之前的形态:周报正文写「区间内至少 15 条(3/5 天未采到)」而聚合文件的对应结论句是「区间内至少 26 条(3/6 天未采到、…)」,校验仍打印通过——15 与 5 作为无关数字出现在聚合文件别处即被放行。

结论句的整句包含检查 SHALL 与日报侧**共用同一份实现**,MUST NOT 在两处各写一遍判定逻辑;两个调用点只提供「到哪个容器取哪些字段」。

被检查的结论句字段名 SHALL 显式枚举,MUST NOT 按名字模式搜集——聚合文件顶层另有复盘结论的**计数字典**与**明细列表**同样以 verdict 命名,模式匹配会把非字符串结构送进字符串比对。

结论句取值的三态处理与日报侧一致:非空字符串按整句包含判定;空串或纯空白 SHALL 判为违规而非通过;非字符串的值 SHALL 判为结构违规。

**容器中不存在某币种条目**(如基准货币在定盘类容器中本就没有条目)SHALL 视为合法形态并跳过,MUST NOT 判为字段缺失;只有币种条目存在时才要求其结论句字段齐全。周报未覆盖某币种时 SHALL 跳过该币种的结论句检查,由既有的「周报未覆盖」检查报告,同一处缺失 MUST NOT 产生两条违规。

未提供聚合文件时 SHALL 不执行结论句检查,MUST NOT 因取不到结论句而报「字段缺失」。

历史产物与当前聚合文件不配对时 SHALL 如实判为违规,MUST NOT 为历史产物提供豁免开关——豁免机制本身会成为下一个绕过点。

#### Scenario: 聚合器正常产出
- **WHEN** 近 7 日存在若干份快照与决策日志
- **THEN** 聚合文件含各币种周涨跌、周区间、事件计数,以及缺漏按源计数与 verdict 计数

#### Scenario: 跨快照代际的同一次定盘
- **WHEN** 同一次定盘在两份快照中一份带参考日期、一份不带(schema 换代)
- **THEN** 视为一次定盘,MUST NOT 计为两次(计两次会让"没有新定盘"变成 0.0% 周涨跌与虚高的定盘次数)

#### Scenario: 决策日志不可用
- **WHEN** 决策日志缺失或不可读
- **THEN** verdict 计数记为 null 并记入 problems,MUST NOT 记为全 0

#### Scenario: 聚合文件不可用时校验必须失败
- **WHEN** 校验周报时提供的聚合文件为空、非 JSON、或结构不符
- **THEN** 校验以错误码 2 失败,MUST NOT 打印通过(打印通过却未执行溯源是最坏的失败模式)

#### Scenario: 两个事件通道分别计数
- **WHEN** 某币种同时有 GDELT 文章与官方公告
- **THEN** 聚合分别给出两者计数,MUST NOT 相加(口径不同,合并后不可比)

#### Scenario: 缺漏源收口
- **WHEN** 聚合文件的缺漏统计含某数据源
- **THEN** 周报缺漏汇总必须提及该源,否则判为遗漏

#### Scenario: 全周参考价未更新
- **WHEN** 当周全部快照的某币种参考价定盘日相同
- **THEN** 该币种周涨跌记为 null(没有新定盘,不构成价格变动)

#### Scenario: 缺天与坏快照
- **WHEN** 当周部分日期无快照,或某份快照不可解析
- **THEN** 聚合按现有份数计算,坏快照跳过,不中断产出

#### Scenario: 周报数字溯源
- **WHEN** 校验周报时提供了聚合文件
- **THEN** 周报中不在 聚合文件 ∪ 当周日报 ∪ 小整数 之内的数字被判为不可溯源

#### Scenario: 未提供聚合文件
- **WHEN** 校验周报时未提供聚合文件
- **THEN** 校验退回既有的结构检查,行为不变,且 MUST NOT 报结论句字段缺失

#### Scenario: 结论句与聚合文件不一致
- **WHEN** 周报写「区间内至少 15 条(3/5 天未采到)」而聚合文件的对应结论句为「区间内至少 26 条(3/6 天未采到、…)」
- **THEN** 校验失败,MUST NOT 因这些数字在聚合文件别处出现过而通过

#### Scenario: 三类结论句全覆盖
- **WHEN** 校验周报时提供了聚合文件
- **THEN** 事件类的两种结论句与定盘类的结论句都被检查,MUST NOT 只检查其中一类

#### Scenario: 基准货币在定盘容器中无条目
- **WHEN** 定盘类容器中不存在基准货币的条目
- **THEN** 跳过该币种,MUST NOT 判为结论句字段缺失

#### Scenario: 结论句为空串
- **WHEN** 聚合文件中某条结论句为空串或纯空白
- **THEN** 校验失败,MUST NOT 因「任意文本都包含空串」而通过

#### Scenario: 周报未覆盖某币种
- **WHEN** 周报正文完全未提及某币种
- **THEN** 只报告「周报未覆盖」一条违规,MUST NOT 同时再报该币种的结论句未引用

#### Scenario: 历史周报与重算后的聚合文件不配对
```

Full source: openspec/changes/fx-verdict-enforcement/specs/fx-weekly-report/spec.md

