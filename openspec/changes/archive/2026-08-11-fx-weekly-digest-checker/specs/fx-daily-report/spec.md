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
