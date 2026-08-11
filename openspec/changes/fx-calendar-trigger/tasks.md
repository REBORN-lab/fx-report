# Tasks: fx-calendar-trigger

## 1. 年历扩充

- [ ] 1.1 `state/calendar-2026.json` 加入可验证的美国统计发布日程:BLS CPI 12 条、BLS Employment Situation 12 条、美联储已公布的 FOMC 纪要 4 条;`sources` 补 BLS 两个日程页与 FOMC 日历页(含抓取日期);`maintenance` 写明 `bank` 字段复用为发布方、PH/TH/BR/EA 日历因官网 403 未录入及人工补录方式。测试覆盖:新条目能被 `calendar.py` 命中、schema 校验(date/bank/event 均为 str 且日期格式合法、无重复 date+event)

## 2. trigger 反自指

- [ ] 2.1 `skills/fx-daily-report/SKILL.md`:决策日志模板要求触发条件绑市场可观测变量(价格越过区间边界/指标相对上期值/年历事件落地),禁止绑"采集恢复"类系统自身状态;复盘判定条款同步说明自指触发不可证伪

## 3. 回归确认

- [ ] 3.1 全量测试通过;真实跑一次采集确认 `calendar_hits` 命中新条目(2026-08-11 与 08-12 窗口应命中 8 月 12 日美国 CPI 发布);既有报告重跑 `check_report.py` 退出码不变
