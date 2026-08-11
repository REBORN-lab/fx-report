## Why

2026-08-11 诊断的两项实测:①`state/calendar-2026.json` 只有 15 条央行议息、零条数据发布日程,五天内 `calendar_hits` 全空,报告答不出读者最痛的"下个催化剂是哪天";②决策日志 25 条里 20 条(80%)的触发条件写的是"若采集恢复",押注管道健康度而非市场,导致 0 命中 0 未命中——复盘机制从设计上就判不出对错。两项都是纯数据/纯 prompt 改动。

## What Changes

- **年历扩充**(`state/calendar-2026.json`):加入 2026 年美国 CPI 发布日(12 条)、非农就业报告发布日(12 条)、已公布的 FOMC 纪要发布日(4 条),均取自 BLS 与美联储官网并记录来源与抓取日期。PH/TH/BR/EA 的统计发布日历官网返回 403 无法验证,**不录入**,在 `maintenance` 字段写明缺口与人工补录方式
- **trigger 反自指**(`skills/fx-daily-report/SKILL.md`):决策日志模板要求触发条件绑定市场可观测变量(价格越过区间边界、指标相对上期值、年历事件落地),**禁止**绑定"采集恢复/事件源恢复"这类系统自身状态;复盘判定条款同步说明为何自指触发不可证伪

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `fx-data-collection`:静态年历的覆盖范围从"央行议息"扩展到"央行议息 + 可验证的统计发布日程"
- `fx-daily-report`:决策日志的触发条件约束

## Impact

- 改动文件:`state/calendar-2026.json`、`skills/fx-daily-report/SKILL.md`(2 个)
- `scripts/collect/calendar.py` 零改动:匹配逻辑本就是通用的 `{date, bank, event}`,新增条目自动生效
- `check_report.py` 零改动
