# fx-daily-report Specification

## Purpose
TBD - created by archiving change fx-daily-report-skill. Update Purpose after archive.
## Requirements
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

