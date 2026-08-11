## Why

2026-08-09 ~ 08-11 试运行暴露报告质量缺口:采集失败日(GDELT 全缺)币种节失去数值锚点、周报漏列未来议息(08-26 BOT / 08-27 BSP 曾被漏)、复盘"无法判定/未判定"读者无从区分、缺漏汇总逐条转录冗长。五条改进已在归档 change `2026-08-11-fx-daily-report-skill` 验证阶段记档(检查点全局备忘),用户 2026-08-11 决定落地。

## What Changes

仅改两份 skill prompt 文本,不改采集层/校验器源码:

- **日报 `skills/fx-daily-report/SKILL.md`**
  - ① 缺漏日回退:某币种"昨日事件 top"为空时,数据发布行允许引快照存量政策利率/最新 CPI 作背景参照(仍逐字抄快照,数字纪律不变),让失联币种的触发条件有数值锚点
  - ② brief 事件 top-3 选取准则:FX/货币政策相关优先;与主线方向相反的标题至少保留一条
- **周报 `skills/fx-weekly-report/SKILL.md`**
  - ③ 第 1 步素材清单补"读 `state/calendar-*.json` 未来 2-3 周窗口"(修复与第 2 步模板行"与年历"的自相矛盾),并同步修订禁令 2 允许年历原文
  - ④ 复盘汇总加一行不含数字的 verdict 图例(区分"无法判定"与"未判定")
  - ⑤ 缺漏汇总改按源聚类(源 + 波及日期/币种 + 一句影响),替代逐日逐条转录

## Capabilities

### New Capabilities

无。

### Modified Capabilities

无。已逐条核对 `openspec/specs/fx-daily-report/spec.md` 与 `openspec/specs/fx-weekly-report/spec.md`:①不破坏"昨日无明确驱动"场景(背景参照非事件归因);⑤聚类格式仍"列出对应日期与缺失内容";③④为素材/图例补充,不改验收行为。无需 delta spec。

## Impact

- 改动文件:`skills/fx-daily-report/SKILL.md`、`skills/fx-weekly-report/SKILL.md`(共 2 个)
- 校验器兼容(改动前已核对源码):日报数字白名单 = 快照∪要点表∪小整数,存量值逐字出自快照即可溯源;周报 `check_weekly` 仅做节存在性/主题条数/日期标题/覆盖声明/币种覆盖/复盘 token 检查,无数字溯源,③④⑤均不触碰
- 采集层、`scripts/check_report.py`、测试套件:零改动
