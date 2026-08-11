# Brainstorm Summary

- Change: fx-daily-report-skill
- Date: 2026-08-10
- 状态: 已定稿(用户确认设计方案)

## 确认的技术方案

1. **报告两步生成(方案 C)**:第一步从快照 `data/YYYY-MM-DD.json` 提炼结构化要点表并落盘(每币种:昨日事件 top/数据发布/汇率变动/年历命中/复盘材料 + 跨币种共同主线);第二步按模板把要点表写成叙事。数字只准从快照抄进要点表。
2. **混合式复盘判定**:汇率方向核对由脚本用两日快照算符号;触发条件是否发生由 LLM 判定但必须引用当日快照证据,引不出证据判"无法判定"。决策日志 `state/decision-log.jsonl` 每条结构化:`{date, currency, scenario, trigger, watch_direction, review}`。
3. **快照 schema**:每日单文件 JSON,字段 rates(主/副源+偏差+可疑标记)/macro/events(文章+tone)/calendar_hits/gaps[]/meta。双源偏差阈值统一 0.5%,超阈仅标记。
4. **零 key 默认路径(用户确认不配 FRED key)**:美国数据发布判定 = 静态年历 + GDELT 新闻捕捉,不记缺漏;`FRED_API_KEY` 存在时增强。→ Spec Patch 回写。
5. **DBnomics 指标类别清单**(各经济体 CPI 同比/政策利率/外部账户),series ID 在 build 时实测固化进 `config/indicators.json`。
6. **代码组织零依赖**:`scripts/collect/` 分模块(rates/macro/events/calendar + 主入口),Python 3 标准库 only,测试用 unittest;skill 为 `skills/fx-daily-report/SKILL.md` 与 `skills/fx-weekly-report/SKILL.md`。
7. **数字溯源校验器** `scripts/check_report.py`:节齐全/摘要 ≤6 条/币种节字数/缺漏节存在/报告数字 ∈ 快照数字集。skill 生成后必须跑校验器,不过自修一次,再不过则报告标注"未通过自检"照常落盘。

## 关键取舍与风险

- 两步生成多一轮 LLM 但换来可验收的中间产物与数字纪律载体(放弃单遍的简单性)
- 复盘不追求全自动判定,"无法判定"是合法输出(放弃判定覆盖率换可信度)
- 零 key 放弃 FRED release dates 精度,换零配置部署;CPI 数值可能仅新闻转述,报告标"据报道"
- GDELT 目标机器限速风险 → 串行 ≥5s + 单次退避 + 缺漏兜底
- LLM 篇幅/数字违规 → 校验器拦截 + 自修一次

## 测试策略

- 采集层:unittest(零依赖)+ 故障注入(endpoint base URL 可注入指向本地 fixture),覆盖三份 spec 全部采集侧 Scenario
- 报告层:check_report.py 结构+数字溯源校验;端到端真实各跑一次日报/周报验收(tasks 3.3/4.2)

## Spec Patch

- `specs/fx-data-collection/spec.md` 的 "Requirement: 宏观数据增量采集":FRED 从"SHALL 采集,无 key 记缺漏"改为"零 key 为默认路径(静态年历+GDELT 判定,不记缺漏);FRED_API_KEY 存在时用 release dates 增强";对应 Scenario 同步改写。
