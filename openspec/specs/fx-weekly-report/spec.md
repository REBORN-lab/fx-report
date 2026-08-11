# fx-weekly-report Specification

## Purpose
TBD - created by archiving change fx-daily-report-skill. Update Purpose after archive.
## Requirements
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

