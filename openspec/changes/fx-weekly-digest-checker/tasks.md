# Tasks: fx-weekly-digest-checker

## 1. 周报聚合器

- [x] 1.1 新建 `scripts/weekly_digest.py`:读近 7 日快照 + 决策日志,算周涨跌(首末不同 ref_date)、周区间(不同定盘 min/max)、事件计数、gap 按源统计、verdict 计数;缺输入写 null;写 `state/weekly-digest-<WEEK>.json`。测试:正常、快照缺天、全周同一定盘、坏快照跳过、决策日志为空
- [x] 1.2 `skills/fx-weekly-report/SKILL.md`:第 1 步增"跑 digest",模板数字改为逐字引用 digest,禁令同步

## 2. 校验器强化

- [x] 2.1 `check_report.py` 周报模式增 `--digest`:白名单 = digest ∪ 各日报 ∪ 小整数,启用 `NUMBER_UNTRACEABLE`。测试:合规周报通过、编造数字被拦、未给 --digest 时行为不变
- [x] 2.2 `check_report.py` 日报模式增 `--strict-brief`:校验 brief ⊆ 快照。测试:合规 brief 通过、brief 含快照外数字被拦、不给参数时行为不变

## 3. 回归确认

- [x] 3.1 全量测试通过;真实生成一份周报并过 `--digest` 校验;既有日报重跑 `--strict-brief` 确认通过
