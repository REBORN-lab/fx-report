# Tasks: fx-data-quality-derived

## 1. 参考日期与连平可判定

- [x] 1.1 rates.py 逐币种保存 Frankfurter 响应 `date` 为 `ref_date`,每币种 entry 增 `prev_ref_date`(取自上一份快照);缺失时为 null。测试覆盖:正常响应、响应无 date 字段、prev 快照无该字段(存量兼容)
- [x] 1.2 review.py 三分支判定:ref_date 相等 → 材料行输出"参考价未更新(非工作日)";不同 → 正常比较;任一缺失 → 旧行为。测试覆盖三分支 + 存量快照

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
