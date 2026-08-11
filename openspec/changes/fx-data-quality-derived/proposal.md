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
