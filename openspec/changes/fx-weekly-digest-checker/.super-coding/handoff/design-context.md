# SuperCoding Design Handoff

- Change: fx-weekly-digest-checker
- Phase: design
- Mode: compact
- Context hash: 514aa149d0c9b90106cc3883ca080200624334a9eccbde5f4a889804aa917dba

Generated-by: super-coding-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/fx-weekly-digest-checker/proposal.md

- Source: openspec/changes/fx-weekly-digest-checker/proposal.md
- Lines: 1-26
- SHA256: 7aa82ee75c66bdffdf1a85e06033585fe7eb0f0b94e199a005bfaae546e8669a

```md
## Why

诊断的两项遗留:①周报 85% 是日报重排,没有任何脚本级跨日聚合可供引用,"本周涨了多少/区间多宽"全靠 LLM 从日报里捞;②周报模式的 `check_report.py` **完全没有数字溯源**(只查结构),数字纪律纯靠 prompt 禁令 —— 日报有白名单硬约束,周报没有。此外前三个 change 的审查暴露了同一条缝隙:`brief ⊆ 快照` 无人校验(校验器只查 `报告 ⊆ 快照 ∪ brief`),LLM 在要点表里写错数字不会被发现。

## What Changes

- 新增 `scripts/weekly_digest.py`:读近 7 日快照与决策日志,**脚本确定性算出**周涨跌、周区间、事件计数、gap 按源统计、复盘 verdict 计数,写 `state/weekly-digest-<WEEK>.json`
- `skills/fx-weekly-report/SKILL.md`:第 1 步增"跑 digest",数字改为逐字引用 digest(与日报引用 derived 同一模式)
- `check_report.py` 周报模式接 `--digest`:数字白名单 = digest ∪ 各日报 ∪ 小整数,启用与日报同级的 `NUMBER_UNTRACEABLE` 溯源
- `check_report.py` 日报模式接 `--strict-brief`:校验 `brief ⊆ 快照`,堵住要点表环节的数字缝隙

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `fx-weekly-report`:周报数字来源与溯源校验
- `fx-daily-report`:要点表数字的溯源校验(brief ⊆ 快照)

## Impact

- 新文件:`scripts/weekly_digest.py`、`tests/test_weekly_digest.py`
- 改动:`scripts/check_report.py`(本序列首次改校验器)、两份 SKILL、`tests/test_check_report.py`、README
```

## openspec/changes/fx-weekly-digest-checker/design.md

- Source: openspec/changes/fx-weekly-digest-checker/design.md
- Lines: 1-26
- SHA256: e47dae4c4a01871fc50a404bcef75a6f1550c7520526fddc1c8bdad36d3a143e

```md
## Context

本序列前三个 change 建立了"脚本算好、LLM 逐字引用"的模式并在日报侧闭环。本 change 把同一模式复制到周报,并补上校验器的两处缝隙。这是唯一需要改 `check_report.py` 的 change。

## Goals / Non-Goals

- Goals:周报有真跨日聚合;周报数字可溯源;要点表数字可溯源
- Non-Goals:不改采集层;不动日报既有白名单语义(只增校验,不放松)

## Decisions

1. **digest 落盘为 JSON 而非直接注入 SKILL 文本**。与 `log_decision.py stats` 的"脚本输出、报告照抄"同构,但 JSON 便于校验器读取白名单 —— 这正是周报溯源的前提。
2. **周报白名单 = digest ∪ 各日报 ∪ 小整数**。日报本身已过数字溯源,把它并入白名单等于承认"日报里出现过的数字周报可以引用",链条完整;不并入会逼 LLM 只能用 digest,丢掉叙述性引用。
3. **`--strict-brief` 做成可选开关而非默认**。存量 brief(本变更之前生成)未必满足 `⊆ 快照`,默认开启会让历史产物一律失败;SKILL 在新流程里显式带上该参数,新产物强制受约束。
4. **digest 只算能确定性算的**:周涨跌用首末两个不同 `ref_date` 的 primary;周区间取全周不同定盘的 min/max;事件计数按币种求和;gap 按 source 计数;verdict 计数直接读决策日志。不做加权、不做归因。
5. **digest 缺输入即写 null**,与 derived 同一约定(上一 change 的 C1 教训:缺失被填成 0 就是编造)。

## Risks / Trade-offs

- [改校验器有回归风险] → 新校验全部走新增参数,不改既有 daily/weekly 路径的默认行为;既有 check_report 测试必须全绿
- [digest 与 derived 口径可能不一致] → digest 的周涨跌同样按 ref_date 去重,与 derived 的 `chg_pct_1d` 同源同法
- [`--strict-brief` 可能误伤合法引用] → brief 允许引用日报模板里的固定小整数,白名单沿用 `ALLOWED_SMALL`

## Migration Plan

新增脚本与可选参数,既有调用不受影响。回滚 = git revert。
```

## openspec/changes/fx-weekly-digest-checker/tasks.md

- Source: openspec/changes/fx-weekly-digest-checker/tasks.md
- Lines: 1-15
- SHA256: 7230b7146a4e54105118450e3c8d6ac53e8c034b9573d9f32d10554cacaf7c7c

```md
# Tasks: fx-weekly-digest-checker

## 1. 周报聚合器

- [ ] 1.1 新建 `scripts/weekly_digest.py`:读近 7 日快照 + 决策日志,算周涨跌(首末不同 ref_date)、周区间(不同定盘 min/max)、事件计数、gap 按源统计、verdict 计数;缺输入写 null;写 `state/weekly-digest-<WEEK>.json`。测试:正常、快照缺天、全周同一定盘、坏快照跳过、决策日志为空
- [ ] 1.2 `skills/fx-weekly-report/SKILL.md`:第 1 步增"跑 digest",模板数字改为逐字引用 digest,禁令同步

## 2. 校验器强化

- [ ] 2.1 `check_report.py` 周报模式增 `--digest`:白名单 = digest ∪ 各日报 ∪ 小整数,启用 `NUMBER_UNTRACEABLE`。测试:合规周报通过、编造数字被拦、未给 --digest 时行为不变
- [ ] 2.2 `check_report.py` 日报模式增 `--strict-brief`:校验 brief ⊆ 快照。测试:合规 brief 通过、brief 含快照外数字被拦、不给参数时行为不变

## 3. 回归确认

- [ ] 3.1 全量测试通过;真实生成一份周报并过 `--digest` 校验;既有日报重跑 `--strict-brief` 确认通过
```

## openspec/changes/fx-weekly-digest-checker/specs/fx-daily-report/spec.md

- Source: openspec/changes/fx-weekly-digest-checker/specs/fx-daily-report/spec.md
- Lines: 1-26
- SHA256: 22f1d451e306554fd1f1cd20540c33bf832666f5a2a288eeb204b21247136907

```md
# fx-daily-report Delta Spec

## MODIFIED Requirements

### Requirement: 数字纪律
日报中的全部汇率与指标数字 MUST 逐字来自数据快照文件;LLM MUST NOT 自行计算、估算或回忆任何行情数字。派生定量(涨跌百分比、区间、实际利率等)SHALL 由采集层脚本确定性计算并落入快照 `derived` 节,日报与要点表 MAY 逐字引用该节数值——该路径不构成 LLM 计算;快照未提供的派生量 MUST NOT 由 LLM 补算。要点表本身 SHALL 可被校验为其数字均出自快照:校验器 SHALL 提供开关对 `要点表 ⊆ 快照` 做溯源检查,新生成的报告流程 MUST 启用该开关。

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
```

## openspec/changes/fx-weekly-digest-checker/specs/fx-weekly-report/spec.md

- Source: openspec/changes/fx-weekly-digest-checker/specs/fx-weekly-report/spec.md
- Lines: 1-26
- SHA256: c60be3f2fc0a4e998eb545830849d3fad0fc3b7a4b6e4cac3a5f2804fc336019

```md
# fx-weekly-report Delta Spec

## ADDED Requirements

### Requirement: 周报跨日聚合与数字溯源
系统 SHALL 提供脚本级的周度聚合器,读取近 7 日快照与决策日志,确定性计算周涨跌、周高低区间、事件计数、缺漏按源统计与复盘结论计数,并落盘为结构化文件;任一输入缺失时该项 SHALL 记为 null 而非省略或填零。周报中的数字 MUST 逐字来自该聚合文件或当周日报原文;校验器 SHALL 在提供聚合文件时对周报执行与日报同级的数字溯源。

#### Scenario: 聚合器正常产出
- **WHEN** 近 7 日存在若干份快照与决策日志
- **THEN** 聚合文件含各币种周涨跌、周区间、事件计数,以及缺漏按源计数与 verdict 计数

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
- **THEN** 校验退回既有的结构检查,行为不变
```

