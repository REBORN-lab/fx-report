# SuperCoding Design Handoff

- Change: fx-data-quality-derived
- Phase: design
- Mode: compact
- Context hash: 3b7bb68a838656e9bb4c80fd62bb62c1014426c5cd50e0d885363ad92f17efec

Generated-by: super-coding-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/fx-data-quality-derived/proposal.md

- Source: openspec/changes/fx-data-quality-derived/proposal.md
- Lines: 1-28
- SHA256: d704085f53c06573afd149364b7bed38992071d07965d37edb66c0ab97de953e

```md
## Why

2026-08-11 四视角诊断(workflow wf_e1d49d18-70d)实测:12/12 汇率对连平且原因在数据层不可见(采集早于 ECB 定盘、参考日期被丢弃)、gaps 87% 来自 GDELT 硬 429 零重试、tone 是 100% 死字段、报告无任何派生定量(LLM 禁算导致连涨跌幅都写不了)。本 change 是密度提升 4-change 序列的第 1 个:把"脚本算好、LLM 逐字引用"的数据底座建起来。

## What Changes

- rates.py 保存 Frankfurter 响应的参考日期 `ref_date`;review.py 遇 ref_date 未更新时输出"参考价未更新(非工作日)"替代伪连平
- events.py:硬 HTTP 429 也退避重试一次;串行延迟默认提至 20s;查询顺序按日期确定性轮转;币种内标题去重;**删除 tone/tone_avg 死字段**
- 新增快照 `derived` 节(脚本计算、round 后落盘):日涨跌%(按 ref_date 去重)、5 运行日高低区间、实际利率(政策利率−CPI,强制携带双 period 原文)、双源偏差前值、事件计数变化
- 日报 SKILL:要点表加"派生指标"行(逐字抄 derived);砍 tone_avg 行;禁算条款改写为"禁止 LLM 计算;快照 derived 节由脚本计算,可逐字引用";汇率行呈现 ref_date
- README 运行节:cron 建议挪至 ≥17:00 UTC(ECB 参考价定盘后)

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `fx-data-collection`:汇率采集要求带 ref_date;事件采集的限流缓解与字段收缩;快照新增 derived 派生指标
- `fx-daily-report`:数字纪律条款扩展(derived 可引);复盘的"参考价未更新"场景

## Impact

- 代码:scripts/collect/{rates.py,events.py,__main__.py}(或新 derive.py)、scripts/review.py、skills/fx-daily-report/SKILL.md、README、tests/
- check_report.py 零改动(白名单=快照∪要点表,derived 落快照即天然合法)
- 快照 schema 向后兼容:新增字段,不改既有字段语义(tone 删除仅影响新快照;历史快照不回填)
```

## openspec/changes/fx-data-quality-derived/design.md

- Source: openspec/changes/fx-data-quality-derived/design.md
- Lines: 1-29
- SHA256: 6c3a3ad85a3b43c5210323b02592e9c3974e564c693edc99c1842504dcab3835

```md
## Context

上游是 2026-08-11 四视角诊断(workflow wf_e1d49d18-70d),已完成问题空间探索、机制定位(文件:行号级)与方案分层,本 change 取其中"数据底座"一层。现状约束不变:零 API key、Python 标准库 only、check_report 白名单 = 快照∪要点表∪小整数。

## Goals / Non-Goals

- Goals:让跨日对比在数据层可判定(ref_date)、让事件采集在限流下有存活率、让报告有脚本算好的派生定量可引
- Non-Goals:不改校验器(留给第 4 个 change)、不换宏观源、不接 RSS(留给第 3 个)、不放松防编造纪律

## Decisions

1. **ref_date 存快照顶层 `rates_ref_date`,并在每币种 entry 存 `prev_ref_date`**。Frankfurter v1 响应含 `date` 字段(参考价定盘日),整档一个值,顶层存最省;prev 侧从上一份快照读取,使 review.py 无需再打开第三个文件。相比"每币种各存一份"省重复,相比"只存顶层不存 prev"让 review 判定自足。
2. **review.py 的连平判定改为三分支**:ref_date 均存在且相等 → 输出"参考价未更新(非工作日)",不参与方向核对(既有 `direction_outcome` 保持"无法判定",但材料行文案区分);ref_date 不同 → 正常比较;任一 ref_date 缺失(历史快照)→ 退回旧行为。向后兼容存量快照。
3. **硬 429 与软限速统一走退避重试**:`_query_with_retry` 判定条件从 `err == "soft-rate-limited"` 扩为"软标记 or 错误串含 429";重试仍只一次(避免把单次运行拖成小时级)。延迟默认 5→20s(五币种串行总耗时约 80s,可接受),`FX_GDELT_DELAY_S` 覆盖机制保留。
4. **查询顺序按日期确定性轮转**:`offset = sum(ord) of date % 5`,五币种循环右移。确定性保证同一天重跑顺序一致(测试可断言),轮转保证限流的"后几个必挂"不总砸同一批币种。
5. **derived 由新模块 `scripts/collect/derive.py` 在快照组装末尾计算**,输入是已成型的 rates/macro/events + 近 N 份历史快照,输出 `derived` 节。放采集层而非 review.py:要点表(第 2 步)就要用,而 review.py 在第 3 步。
6. **派生值一律 round 后落盘**,且实际利率强制携带 `rate_period`/`cpi_period` 两个原文期号——期错配是编造风险最大处,让 LLM 引用时无法隐藏。
7. **tone 直接删除而非置空**:artlist 端点不返回该字段(实测 40/40 为 null),留着即误导。

## Risks / Trade-offs

- [延迟 20s 令单次采集变慢] → 五币种约 80s,cron 场景可接受;`FX_GDELT_DELAY_S` 可下调
- [derived 计算引入新的错误面] → 全部走 isinstance 门 + 数值有限性检查,任一输入不可用即该项写 null 并记 gap,不抛异常
- [历史快照无 ref_date/derived] → 所有读取路径带缺失回退,测试覆盖"存量快照"场景
- [round 精度选择] → 涨跌% 保留 3 位、区间保留原值精度、实际利率保留 3 位;写进 spec 避免漂移

## Migration Plan

新增字段,不改既有字段语义;历史快照不回填(报告只读当日+近 N 日,缺失即降级)。回滚 = git revert。
```

## openspec/changes/fx-data-quality-derived/tasks.md

- Source: openspec/changes/fx-data-quality-derived/tasks.md
- Lines: 1-23
- SHA256: e9329d7644fdf6f5de51886d11164ce03ecd16936babd48cea8cff09ee22fb06

```md
# Tasks: fx-data-quality-derived

## 1. 参考日期与连平可判定

- [ ] 1.1 rates.py 保存 Frankfurter 响应 `date` 为快照顶层 `rates_ref_date`,每币种 entry 增 `prev_ref_date`(取自上一份快照);缺失时为 null。测试覆盖:正常响应、响应无 date 字段、prev 快照无该字段(存量兼容)
- [ ] 1.2 review.py 三分支判定:ref_date 相等 → 材料行输出"参考价未更新(非工作日)";不同 → 正常比较;任一缺失 → 旧行为。测试覆盖三分支 + 存量快照

## 2. GDELT 限流缓解

- [ ] 2.1 events.py 硬 429 纳入退避重试(一次);默认延迟 5→20s(`FX_GDELT_DELAY_S` 覆盖保留)。测试覆盖:429 首次失败重试成功、429 两次失败记 gap、软限速路径不回归
- [ ] 2.2 events.py 按日期确定性轮转查询顺序 + 币种内标题去重。测试覆盖:同日期两次调用顺序一致、不同日期顺序不同、重复标题只保留一条
- [ ] 2.3 删除 tone/tone_avg 字段(events.py 与日报 SKILL 要点表模板)。测试覆盖:快照 events 条目不含 tone 键

## 3. 派生指标

- [ ] 3.1 新建 scripts/collect/derive.py:日涨跌%(按 ref_date 去重,ref_date 未更新时为 null)、5 运行日高低区间、双源偏差前值、事件计数变化;全部 isinstance 门 + 有限性检查,输入不可用即该项 null。测试覆盖:正常、ref_date 未更新、历史不足 5 日、坏输入(NaN/bool/非数值)
- [ ] 3.2 derive.py 实际利率(政策利率−CPI)强制携带 `rate_period`/`cpi_period` 双期号原文;任一缺失即整项 null。测试覆盖:双值齐全、缺一、期号缺失
- [ ] 3.3 __main__.py 在快照组装末尾调用 derive 并写入 `derived` 节(读近 N 份历史快照);derive 内部异常一律转 gap 不上抛。测试覆盖:端到端快照含 derived、derive 抛异常时快照仍落盘且记 gap

## 4. 报告侧与文档

- [ ] 4.1 日报 SKILL:要点表加"派生指标"行(逐字抄 derived)、汇率行呈现 ref_date、砍 tone_avg 行;禁算条款改写为"禁止 LLM 计算;快照 derived 节由脚本计算,可逐字引用";README 运行节加 cron ≥17:00 UTC 建议(ECB 参考价定盘后)
- [ ] 4.2 全量测试通过;真实跑一次当日采集与要点表生成,确认 derived 落盘且 check_report.py 数字溯源不报 NUMBER_UNTRACEABLE
```

## openspec/changes/fx-data-quality-derived/specs/fx-daily-report/spec.md

- Source: openspec/changes/fx-data-quality-derived/specs/fx-daily-report/spec.md
- Lines: 1-37
- SHA256: 930929921903717edf1dfb0a7999c00919a9f8730bca264e1f79e8b1ff5f3f35

```md
# fx-daily-report Delta Spec

## MODIFIED Requirements

### Requirement: 数字纪律
日报中的全部汇率与指标数字 MUST 逐字来自数据快照文件;LLM MUST NOT 自行计算、估算或回忆任何行情数字。派生定量(涨跌百分比、区间、实际利率等)SHALL 由采集层脚本确定性计算并落入快照 `derived` 节,日报与要点表 MAY 逐字引用该节数值——该路径不构成 LLM 计算;快照未提供的派生量 MUST NOT 由 LLM 补算。

#### Scenario: 数字可溯源
- **WHEN** 日报正文引用某汇率或指标值
- **THEN** 该数值能在当日快照文件中逐字找到

#### Scenario: 引用派生指标
- **WHEN** 日报引用日涨跌百分比、近 5 运行日区间或实际利率
- **THEN** 该数值逐字取自快照 `derived` 节,且实际利率同时给出政策利率与 CPI 的期号

#### Scenario: 派生量缺失时不补算
- **WHEN** 快照 `derived` 中某项为 null
- **THEN** 日报如实说明该派生量不可得,MUST NOT 由 LLM 自行计算替代

### Requirement: 决策日志与次日复盘
系统 SHALL 把每日各币种的情景观点追加写入决策日志;生成第 N+1 天日报时,SHALL 对照第 N 天观点与实际汇率变动,在日报中给出每币种一句话复盘。当当日与被复盘日的汇率参考价定盘日期相同时,复盘 SHALL 说明"参考价未更新(非工作日)",MUST NOT 将其表述为价格持平的市场观察。

#### Scenario: 存在前日日志
- **WHEN** 生成日报时决策日志含前一运行日的观点记录
- **THEN** 日报含复盘小节,逐币种一句话对照观点与实际走势

#### Scenario: 首次运行无日志
- **WHEN** 决策日志不存在或为空
- **THEN** 日报跳过复盘小节并注明"首次运行,无历史观点可复盘"

#### Scenario: 参考价未更新
- **WHEN** 当日快照与被复盘日快照的 `rates_ref_date` 相同
- **THEN** 复盘材料与日报复盘节写明"参考价未更新(非工作日)",不据此得出价格持平的结论

#### Scenario: 参考日期缺失退回旧行为
- **WHEN** 任一侧快照不含参考日期字段
- **THEN** 复盘按既有的数值比较逻辑进行
```

## openspec/changes/fx-data-quality-derived/specs/fx-data-collection/spec.md

- Source: openspec/changes/fx-data-quality-derived/specs/fx-data-collection/spec.md
- Lines: 1-76
- SHA256: 94dceddcacbd645bb6b0d1af3d1eb70c5bb11c911cb0ecb188209972b3b3441a

```md
# fx-data-collection Delta Spec

## MODIFIED Requirements

### Requirement: 五币种汇率双源采集与交叉校验
系统 SHALL 从 Frankfurter(主源)获取 USD 兑 PHP/THB/BRL/EUR 的日频汇率,并 SHALL 用 exchange-api 版本化日期端点做异源交叉校验;同一币种两源偏差超过 0.5% 时 SHALL 在快照中标记该币种数据可疑并保留两源数值。系统 SHALL 保存主源响应中的参考价定盘日期(`rates_ref_date`)与上一份快照的对应日期(每币种 `prev_ref_date`),使"汇率是否真的变化过"在数据层可判定;主源响应缺该字段时记为 null,采集继续。

#### Scenario: 双源正常
- **WHEN** Frankfurter 与 exchange-api 均可用且各币种偏差 ≤ 0.5%
- **THEN** 快照含四对汇率、两源数值与校验通过标记

#### Scenario: 主源失败降级
- **WHEN** Frankfurter 请求失败(超时/非 200/无数据)
- **THEN** 系统采用 exchange-api 数据作为当日汇率,并把主源失败记入缺漏记录(含原因),采集继续

#### Scenario: 双源偏差超阈
- **WHEN** 某币种两源偏差 > 0.5%
- **THEN** 快照标记该币种"数据可疑"并保留两源数值,日报层可引用该标记

#### Scenario: 参考价定盘日期落盘
- **WHEN** Frankfurter 响应含参考价定盘日期字段
- **THEN** 快照顶层记录 `rates_ref_date`,各币种记录上一份快照的 `prev_ref_date`

#### Scenario: 存量快照无参考日期
- **WHEN** 上一份快照不含参考日期字段(本变更之前生成)
- **THEN** `prev_ref_date` 记为 null,采集与后续比对退回按数值比较的既有行为

### Requirement: 前一日事件采集(GDELT)
系统 SHALL 按五币种关键词组串行查询 GDELT DOC 2.0 API(请求间隔 SHALL ≥ 5 秒,默认 20 秒),采集前一日窗口的 top 文章列表;系统 MUST 识别"HTTP 200 但正文为限速提示"的软失败形态**与 HTTP 429 硬限流**,退避后重试一次,仍失败则记为缺漏。查询顺序 SHALL 按采集日期确定性轮转,使限流导致的尾部失败不恒定落在同一批币种;同一币种内标题重复的文章 SHALL 只保留一条。快照 MUST NOT 包含 tone 字段——所使用的 artlist 端点不返回该字段。

#### Scenario: 正常采集
- **WHEN** 五组关键词查询串行完成
- **THEN** 快照含每币种的前一日文章列表(标题/URL/来源/时间),且不含 tone 字段

#### Scenario: 限速软失败退避
- **WHEN** 响应为 HTTP 200 但正文是限速提示文本
- **THEN** 系统识别为软失败,等待后重试一次;重试成功则正常记录,再失败则该币种事件记为缺漏

#### Scenario: 硬限流退避
- **WHEN** 请求返回 HTTP 429
- **THEN** 系统等待后重试一次;重试成功则正常记录,再失败则该币种事件记为缺漏

#### Scenario: 查询顺序轮转
- **WHEN** 以不同采集日期运行
- **THEN** 五币种查询顺序按日期确定性轮转;同一日期重复运行顺序一致

#### Scenario: 标题去重
- **WHEN** 某币种返回的文章中存在标题完全相同的多条
- **THEN** 快照中该币种只保留其中一条

#### Scenario: 端点不可用
- **WHEN** GDELT 请求超时或返回错误
- **THEN** 该币种事件记为缺漏(含原因),其余币种查询继续,管线不中断

### Requirement: 快照落盘与缺漏记录
系统 SHALL 把当日全部采集结果写入按日期命名的快照文件,内含逐数据源的成功/失败状态与失败原因;任一数据源失败 MUST NOT 中断其余数据源的采集。快照 SHALL 含由脚本确定性计算的 `derived` 派生指标节,其每一项 MUST 可由快照与近若干份历史快照的原始值复算得出;任一输入缺失或非有限数值时该项 SHALL 记为 null 而非省略,派生计算的内部异常 MUST 转为缺漏记录且不阻断快照落盘。

#### Scenario: 部分源失败时快照完整
- **WHEN** 任一数据源采集失败
- **THEN** 其余源照常采集落盘,快照的 gaps 字段逐条列出失败源与原因

#### Scenario: 派生指标落盘
- **WHEN** 当日与历史快照提供了足够输入
- **THEN** 快照 `derived` 节含日涨跌百分比、近 5 运行日高低区间、双源偏差前值、事件计数变化与实际利率

#### Scenario: 参考价未更新时不计涨跌
- **WHEN** 当日 `rates_ref_date` 与上一份快照相同
- **THEN** 该币种日涨跌百分比记为 null(参考价未更新,不构成价格变动)

#### Scenario: 实际利率携带双期号
- **WHEN** 某经济体政策利率与 CPI 同比均可用
- **THEN** 派生的实际利率同时携带政策利率与 CPI 各自的期号原文;任一缺失时整项记为 null

#### Scenario: 派生计算异常不阻断
- **WHEN** 派生计算过程抛出异常
- **THEN** 异常转为缺漏记录,快照其余部分照常落盘
```

