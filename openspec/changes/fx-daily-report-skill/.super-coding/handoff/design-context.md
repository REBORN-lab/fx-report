# SuperCoding Design Handoff

- Change: fx-daily-report-skill
- Phase: design
- Mode: compact
- Context hash: 89a9f5148f0e26da484e5dcaf2e938a322cae9104dbe7a98f9cb6999be8658c5

Generated-by: super-coding-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/fx-daily-report-skill/proposal.md

- Source: openspec/changes/fx-daily-report-skill/proposal.md
- Lines: 1-30
- SHA256: 8b1710572c78c10efb75decfd5efffe488415c8ca8a83edea5e3cdd9e5a9ea8c

```md
# Proposal: fx-daily-report-skill

## Why

公司团队需要每天了解影响 USD/PHP/BRL/THB/EUR 五种法币价格的前一日事件与宏观数据,但目前没有任何自动化手段——市面上也不存在现成的"多币种 FX 宏观日报"开源方案(2026-08-10 调研确认,见 `super-research/…方案调研/report.md`)。需要一个可在 Claude Code 无头模式(`claude -p`)下一条命令运行的 skill:采集前一天数据、生成带叙事逻辑链条的简明中文日报、按周聚合周报,任何数据缺漏在报告中显式说明。

## What Changes

- 新增数据采集脚本层:从 Frankfurter(主)+ exchange-api(交叉校验)取五币种汇率,从 DBnomics/FRED/BCB 取宏观增量,从 GDELT DOC 2.0 取前一日事件(串行限速),对照央行议息静态年历;全部落盘为当日数据快照,采集失败记为缺漏而非中断
- 新增 `fx-daily-report` skill:读数据快照生成中文日报——五币种分节,每节走"事件→定价含义→情景与触发条件"叙事链条;不做方向性预测;报告含执行摘要与数据缺漏节;所有数字来自快照文件,LLM 只写叙事
- 新增决策日志机制:每日报告的币种观点追加存档,次日对照实际走势生成一句话复盘写入新日报
- 新增 `fx-weekly-report` 聚合能力:读最近 7 天日报与决策日志,按主题重聚类(非流水账)生成中文周报
- 输出为本地 markdown 文件(`reports/daily/`、`reports/weekly/`);Slack 推送、定时调度、异机部署明确不在本 change 范围内(用户自行接线)

## Capabilities

### New Capabilities
- `fx-data-collection`: 五币种汇率/宏观/事件数据的每日采集与快照落盘,含双源交叉校验、限速退避、缺漏记录
- `fx-daily-report`: 从数据快照生成带叙事逻辑链条的中文日报,含缺漏披露与决策日志复盘
- `fx-weekly-report`: 从最近 7 天日报与决策日志按主题重聚类生成中文周报

### Modified Capabilities
(无——本仓库尚无既有 spec)

## Impact

- 新增目录:`skills/`(skill 定义)、`scripts/`(数据采集,Python 3 标准库 + 免费无 key API)、`data/`(每日快照)、`reports/`(日报/周报输出)、`state/`(决策日志、静态年历)
- 外部依赖:Frankfurter、exchange-api(jsDelivr CDN)、DBnomics、FRED(需免费 API key,可选)、BCB、GDELT DOC 2.0——全部免费;无付费依赖,无爬虫
- 运行环境:目标机器需装 Claude Code + Anthropic API key(用户自备);skill 本体与脚本无其他运行时依赖
- 无既有代码受影响(全新仓库首个 change)
```

## openspec/changes/fx-daily-report-skill/design.md

- Source: openspec/changes/fx-daily-report-skill/design.md
- Lines: 1-44
- SHA256: 5e12a3638704ffda561622b0c26a369db2c5f7616708814b21acc4b73be32c63

```md
# Design: fx-daily-report-skill(高层架构)

## Context

全新仓库的首个 change。方案调研已完成并经引用验证(`super-research/…方案调研/report.md`,50 来源):数据源全部实测可用,无现成开源轮子,借鉴对象与叙事范式已定案。运行形态由用户确认:Claude Code CLI 无头模式(`claude -p`),中文报告,本地 markdown 输出;交付渠道与调度由用户自行接线。

## Goals / Non-Goals

**Goals:**
- 一条命令产出一份可信的五币种中文日报;一条命令产出周报
- 任何数据源失败都优雅降级并显式披露,管线永不因单源失败而中断
- 报告数字 100% 可溯源到当日快照文件

**Non-Goals:**
- Slack/邮件等推送、定时调度、异机部署(用户自理)
- 方向性汇率预测;盘中行情;付费数据源;网页爬虫

## Decisions

1. **两段式管线,快照文件为唯一接口**:数据采集是确定性 Python 脚本(标准库,无第三方依赖),产出 `data/YYYY-MM-DD.json` 快照;报告生成是 Claude skill,只读快照写叙事。理由:FinRobot 验证过的"数字代码算、LLM 只叙事"纪律,是防幻觉的结构性保障。备选"LLM 直接调 API 采数"被否:数字纪律无法保证,GDELT 串行限速在对话式调用里难以控制。
2. **skill 组织仿 claude-trading-skills**:`skills/fx-daily-report/SKILL.md` 与 `skills/fx-weekly-report/SKILL.md` 各自独立,skill 内先跑采集脚本再生成报告,`claude -p "/fx-daily-report"` 即完整一轮。备选"单一 Python 脚本直调 Anthropic API"被否:用户明确选择 Claude Code CLI 形态。
3. **数据源按调研定案**:Frankfurter(主,无 key)+ exchange-api 版本化端点(交叉校验,CC0)/ DBnomics(五经济体宏观)+ FRED release dates(可选 key,缺失降级)+ BCB / GDELT DOC 2.0(串行 ≥5s,识别 200 软限速)/ 五央行议息静态年历(仓库内维护的数据文件)。全部免费,零爬虫。
4. **决策日志 append-only**:`state/decision-log.jsonl`,每日追加各币种情景观点;次日读取并对照快照汇率变动生成一句话复盘(借鉴 TradingAgents decision log 机制)。
5. **叙事模板取 ING 三段链条**:事件→定价含义→情景与触发条件;观点一律"若 X 则关注 Y"形态。周报按主题重聚类,禁止按日流水。

## Risks / Trade-offs

- [免费 API 无预告停服/变更] → 双源交叉 + 逐源降级 + 缺漏披露;Frankfurter 可自托管是终极兜底
- [GDELT 软限速(200 + 限速正文)] → 串行 sleep≥5s + 正文识别 + 单次退避重试,失败记缺漏
- [LLM 编造或改写数字] → 快照数字纪律写入 spec;验收时抽查报告数字与快照逐字一致
- [静态年历过期] → 年历文件带"有效期至"字段,过期时报告缺漏节自动提示更新
- [市场共识预期值免费拿不到] → 报告用"实际 vs 前值",事件文中若含记者转引的共识值可引用并标注转引

## Migration Plan

全新仓库,无迁移;回滚 = git revert。部署(范围外)只需:目标机器 clone 仓库 + 装 Claude Code + 配 key + 用户自建 cron。

## Open Questions(留给 design 阶段 brainstorming)

- 快照 JSON schema 的具体字段设计(含 gaps 结构)
- 五经济体各跟踪哪些 DBnomics 指标(CPI/政策利率/贸易差额…清单与序列 ID)
- 汇率双源偏差阈值 0.5% 的合理性(是否按币种流动性分层)
- 复盘"命中/未命中/无法判定"的判定规则(观点是情景式的,判定需要触发条件是否发生 + 方向是否兑现两步)
- 日报执行摘要与币种节的确切模板字段
```

## openspec/changes/fx-daily-report-skill/tasks.md

- Source: openspec/changes/fx-daily-report-skill/tasks.md
- Lines: 1-30
- SHA256: e7d3c22d20c5a5b63e0b91f588c04ba6f290a064d0151687c3edf0cec9b56c70

```md
# Tasks: fx-daily-report-skill

## 1. 仓库骨架与静态数据

- [ ] 1.1 建立目录结构(`scripts/`、`skills/`、`data/`、`reports/daily/`、`reports/weekly/`、`state/`)与 `.gitignore`,README 写一段目标概述
- [ ] 1.2 制作五央行(Fed/ECB/BSP/BOT/BCB)议息静态年历数据文件,含"有效期至"字段与维护说明

## 2. 数据采集层(fx-data-collection)

- [ ] 2.1 汇率采集模块:Frankfurter 主源取 USD 兑 PHP/THB/BRL/EUR,exchange-api 版本化端点交叉校验,偏差 >0.5% 标记可疑,主源失败降级并记缺漏
- [ ] 2.2 宏观采集模块:按 design 阶段确定的指标清单从 DBnomics 取最新值/前值,FRED release dates 判定前日美国数据发布(无 key 时降级记缺漏)
- [ ] 2.3 GDELT 事件采集模块:五币种关键词组串行查询(间隔 ≥5s),识别"200 但正文为限速提示"软失败并退避重试一次,失败记缺漏
- [ ] 2.4 快照聚合:年历对照标注 + 全部采集结果落盘 `data/YYYY-MM-DD.json`(含逐源状态与 gaps 结构),单源失败不中断
- [ ] 2.5 采集层故障注入测试:逐源模拟失败,验证其余源照常采集且 gaps 记录符合 spec 场景

## 3. 日报生成(fx-daily-report skill)

- [ ] 3.1 编写 `skills/fx-daily-report/SKILL.md`:先跑采集脚本再生成报告;模板含执行摘要(≤6 条)、五币种节(事件→定价含义→情景与触发条件,≤约 300 字/节)、数据缺漏节、复盘节;数字只准引快照;禁止方向性预测
- [ ] 3.2 决策日志:每日观点追加 `state/decision-log.jsonl`;次日读取并对照快照汇率变动生成逐币种一句话复盘;首次运行优雅跳过
- [ ] 3.3 端到端验收:真实跑一次 `claude -p` 生成当日日报,抽查全部数字与快照逐字一致、缺漏节如实、篇幅合规

## 4. 周报生成(fx-weekly-report skill)

- [ ] 4.1 编写 `skills/fx-weekly-report/SKILL.md`:读最近 7 天日报与决策日志,按主题重聚类(本周主线 ≤3 条/各币种归因/复盘汇总/下周关注),日报不足 3 份时注明覆盖范围
- [ ] 4.2 端到端验收:用 ≥3 份日报真实跑一次周报,验证一级结构为主题而非日期、缺漏与复盘汇总正确

## 5. 收尾

- [ ] 5.1 README 运行文档:无头模式命令、环境变量(FRED key 可选)、目录说明、年历维护方式、"交付/调度自行接线"边界说明
- [ ] 5.2 对照三份 spec 的全部 Scenario 逐条核对已覆盖,记录核对结果
```

## openspec/changes/fx-daily-report-skill/specs/fx-daily-report/spec.md

- Source: openspec/changes/fx-daily-report-skill/specs/fx-daily-report/spec.md
- Lines: 1-50
- SHA256: f07e9bb611d79dc1f03148700b016d4ede20b18552b0803b633d274203c0c668

```md
# fx-daily-report — 五币种中文日报生成

## ADDED Requirements

### Requirement: 日报生成与叙事逻辑链条
系统 SHALL 从当日数据快照生成中文日报文件,五币种各一节,每节按"昨日事件 → 定价含义 → 情景与触发条件"的链条组织;报告 MUST NOT 输出无条件的方向性汇率预测,币种观点 MUST 以"若 X 发生则关注 Y"的情景+触发条件形式表述。

#### Scenario: 数据齐全的正常日
- **WHEN** 当日快照存在且 gaps 为空
- **THEN** 生成日报文件,含执行摘要与五币种分节,每节具备完整叙事链条

#### Scenario: 无明确驱动的币种
- **WHEN** 某币种前一日无显著事件且无数据发布
- **THEN** 该节如实写明"昨日无明确驱动",不编造事件归因

### Requirement: 数字纪律
日报中的全部汇率与指标数字 MUST 逐字来自数据快照文件;LLM MUST NOT 自行计算、估算或回忆任何行情数字。

#### Scenario: 数字可溯源
- **WHEN** 日报正文引用某汇率或指标值
- **THEN** 该数值能在当日快照文件中逐字找到

### Requirement: 数据缺漏显式披露
日报 SHALL 含"数据缺漏"节:快照 gaps 非空时逐条列出缺失数据源、失败原因与对当日结论可信度的影响;gaps 为空时该节写"无"。

#### Scenario: 缺漏日披露
- **WHEN** 快照 gaps 含至少一条失败记录
- **THEN** 日报"数据缺漏"节逐条列出缺什么、为什么、影响哪些结论,正文不得引用缺失数据

#### Scenario: 无缺漏日
- **WHEN** 快照 gaps 为空
- **THEN** "数据缺漏"节内容为"无"

### Requirement: 决策日志与次日复盘
系统 SHALL 把每日各币种的情景观点追加写入决策日志;生成第 N+1 天日报时,SHALL 对照第 N 天观点与实际汇率变动,在日报中给出每币种一句话复盘。

#### Scenario: 存在前日日志
- **WHEN** 生成日报时决策日志含前一运行日的观点记录
- **THEN** 日报含复盘小节,逐币种一句话对照观点与实际走势

#### Scenario: 首次运行无日志
- **WHEN** 决策日志不存在或为空
- **THEN** 日报跳过复盘小节并注明"首次运行,无历史观点可复盘"

### Requirement: 简明扼要约束
执行摘要 MUST 不超过 6 条;每币种节正文 MUST 不超过约 300 中文字;报告 MUST NOT 逐条罗列快照原始数据(流水账),仅呈现驱动结论的关键数字。

#### Scenario: 篇幅合规
- **WHEN** 日报生成完成
- **THEN** 执行摘要 ≤ 6 条且各币种节不超过约 300 中文字
```

## openspec/changes/fx-daily-report-skill/specs/fx-data-collection/spec.md

- Source: openspec/changes/fx-daily-report-skill/specs/fx-data-collection/spec.md
- Lines: 1-62
- SHA256: b8e35f61d9dba15642d2637caf1d2b430f8c84593c27e1b40d10c5cf8451a71b

```md
# fx-data-collection — 五币种数据每日采集与快照

## ADDED Requirements

### Requirement: 五币种汇率双源采集与交叉校验
系统 SHALL 从 Frankfurter(主源)获取 USD 兑 PHP/THB/BRL/EUR 的日频汇率,并 SHALL 用 exchange-api 版本化日期端点做异源交叉校验;同一币种两源偏差超过 0.5% 时 SHALL 在快照中标记该币种数据可疑并保留两源数值。

#### Scenario: 双源正常
- **WHEN** Frankfurter 与 exchange-api 均可用且各币种偏差 ≤ 0.5%
- **THEN** 快照含四对汇率、两源数值与校验通过标记

#### Scenario: 主源失败降级
- **WHEN** Frankfurter 请求失败(超时/非 200/无数据)
- **THEN** 系统采用 exchange-api 数据作为当日汇率,并把主源失败记入缺漏记录(含原因),采集继续

#### Scenario: 双源偏差超阈
- **WHEN** 某币种两源偏差 > 0.5%
- **THEN** 快照标记该币种"数据可疑"并保留两源数值,日报层可引用该标记

### Requirement: 宏观数据增量采集
系统 SHALL 从 DBnomics(五经济体,IMF/BCB 口径)采集关键宏观指标的最新值与前值。零 key 为默认运行路径:"前一日发布了哪些数据"的判定 SHALL 由静态年历与 GDELT 事件流承担,该路径 MUST NOT 记为缺漏;当环境变量 FRED_API_KEY 存在时,系统 SHALL 额外调用 FRED release dates 端点增强前一日美国数据发布判定,该增强调用失败时记入缺漏但不中断其余采集。

#### Scenario: 有新数据发布
- **WHEN** 前一日某跟踪指标发布了新值
- **THEN** 快照列出该指标的名称、最新值、前值与发布日期

#### Scenario: 零 key 默认路径
- **WHEN** 环境变量中无 FRED_API_KEY
- **THEN** 采集按默认路径完成(静态年历与 GDELT 承担发布判定),gaps 中不出现 FRED 相关条目

#### Scenario: FRED 增强路径失败
- **WHEN** FRED_API_KEY 存在但 FRED 请求失败
- **THEN** FRED 失败记入缺漏,DBnomics 与其余采集照常进行

### Requirement: 前一日事件采集(GDELT)
系统 SHALL 按五币种关键词组串行查询 GDELT DOC 2.0 API(请求间隔 ≥ 5 秒),采集前一日窗口的 top 文章列表与 tone;系统 MUST 识别"HTTP 200 但正文为限速提示"的软失败形态,退避后重试一次,仍失败则记为缺漏。

#### Scenario: 正常采集
- **WHEN** 五组关键词查询串行完成
- **THEN** 快照含每币种的前一日文章列表(标题/URL/来源/时间)与 tone 值

#### Scenario: 限速软失败退避
- **WHEN** 响应为 HTTP 200 但正文是限速提示文本
- **THEN** 系统识别为软失败,等待后重试一次;重试成功则正常记录,再失败则该币种事件记为缺漏

#### Scenario: 端点不可用
- **WHEN** GDELT 请求超时或返回错误
- **THEN** 该币种事件记为缺漏(含原因),其余币种查询继续,管线不中断

### Requirement: 央行议息静态年历对照
系统 SHALL 维护一份含五家央行(Fed/ECB/BSP/BOT/BCB)议息会议日程的静态年历文件,采集时 SHALL 标注前一日与当日是否命中日历事件。

#### Scenario: 昨日为议息日
- **WHEN** 静态年历中前一日存在某央行议息会议
- **THEN** 快照标记该事件(央行名/事件类型/日期)供日报引用

### Requirement: 快照落盘与缺漏记录
系统 SHALL 把当日全部采集结果写入按日期命名的快照文件,内含逐数据源的成功/失败状态与失败原因;任一数据源失败 MUST NOT 中断其余数据源的采集。

#### Scenario: 部分源失败时快照完整
- **WHEN** 任一数据源采集失败
- **THEN** 其余源照常采集落盘,快照的 gaps 字段逐条列出失败源与原因
```

## openspec/changes/fx-daily-report-skill/specs/fx-weekly-report/spec.md

- Source: openspec/changes/fx-daily-report-skill/specs/fx-weekly-report/spec.md
- Lines: 1-25
- SHA256: 22b4ebf10cff1b9271277661b91d63d9716d0a97c7073d889938fec5ee360478

```md
# fx-weekly-report — 周报聚合

## ADDED Requirements

### Requirement: 周报按主题重聚类生成
系统 SHALL 读取最近 7 个自然日内的全部日报与决策日志,生成中文周报,结构为:本周主线(≤3 条)、各币种一周走势归因、观点复盘汇总、下周关注;周报一级结构 MUST 按主题组织,MUST NOT 按日期逐日罗列。

#### Scenario: 正常周聚合
- **WHEN** 最近 7 天内存在至少 3 份日报
- **THEN** 生成周报文件,一级结构为主题分节而非日期列表

#### Scenario: 日报不足
- **WHEN** 最近 7 天内日报少于 3 份
- **THEN** 周报照常生成但开头注明覆盖天数与缺失日期,聚合仅基于现有日报

### Requirement: 周报缺漏与复盘传递
周报 SHALL 汇总本周各日的缺漏记录(哪些天缺了什么),并 SHALL 汇总决策日志中本周观点的复盘结果(命中/未命中/无法判定)。

#### Scenario: 周内有缺漏日
- **WHEN** 本周任一日报的缺漏节非"无"
- **THEN** 周报的缺漏汇总节列出对应日期与缺失内容

#### Scenario: 观点复盘汇总
- **WHEN** 决策日志含本周多日观点及其次日复盘
- **THEN** 周报含复盘汇总,标明各观点命中/未命中/无法判定
```

