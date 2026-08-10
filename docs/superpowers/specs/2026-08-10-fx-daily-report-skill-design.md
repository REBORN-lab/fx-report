---
super_coding_change: fx-daily-report-skill
role: technical-design
canonical_spec: openspec
---

# Technical Design: fx-daily-report-skill

日期 2026-08-10。需求规格以 OpenSpec delta spec 为准(`openspec/changes/fx-daily-report-skill/specs/`);本文档回答 HOW。上游依据:方案调研报告 `super-research/…方案调研/report.md`(50 来源,引用已验证)与 brainstorming 确认记录(`.super-coding/handoff/brainstorm-summary.md`)。

## Context

全新仓库首个 change。用户确认:Claude Code CLI 无头模式运行、中文报告、本地 markdown 输出、**全链路零 API key**;Slack/调度/部署范围外。

## Architecture

两段式管线,快照文件为唯一接口;报告生成内部再分两步:

```
cron(用户自理)
  └─ claude -p "/fx-daily-report"
       ├─ [脚本段] python3 scripts/collect.py
       │     ├─ collect/rates.py     Frankfurter 主源 + exchange-api 交叉校验
       │     ├─ collect/macro.py     DBnomics 指标(config/indicators.json)
       │     ├─ collect/events.py    GDELT DOC 2.0,五组关键词串行 ≥5s
       │     └─ collect/calendar.py  静态年历命中判定
       │           → data/YYYY-MM-DD.json(rates/macro/events/calendar_hits/gaps/meta)
       ├─ [LLM 第一步] 快照 → 结构化要点表 briefs/YYYY-MM-DD-brief.md 落盘
       │     每币种:昨日事件 top/数据发布/汇率变动/年历命中/复盘材料;跨币种共同主线
       │     数字纪律:要点表中数字只准逐字抄自快照
       ├─ [脚本段] python3 scripts/review.py  两日快照算汇率方向 → 复盘材料注入要点表
       ├─ [LLM 第二步] 要点表 → reports/daily/YYYY-MM-DD.md(ING 三段叙事模板)
       │     并追加观点到 state/decision-log.jsonl
       └─ [脚本段] python3 scripts/check_report.py 结构+数字溯源校验
             不过 → LLM 自修一次 → 再校验;仍不过 → 报告头部标注"未通过自检"照常落盘
```

`/fx-weekly-report` 独立 skill:读最近 7 天 `reports/daily/` 与 decision-log → 按主题重聚类生成 `reports/weekly/YYYY-Www.md` → 同样过校验器(周报规则子集)。

## Components

**1. 采集模块(Python 3 标准库 only,urllib+json)**
- 每模块暴露 `collect(cfg) -> (payload, gaps)`;任何异常捕获后转 gap 记录,绝不向上抛
- endpoint base URL 全部从 `config/endpoints.json` 读取——故障注入测试用注入本地 fixture URL 实现
- rates:`GET frankfurter /v2/rates?base=USD&quotes=PHP,THB,BRL,EUR`;副源 exchange-api 版本化日期端点(jsDelivr 主 + Cloudflare 兜底);偏差 = |主-副|/主,>0.5% 置 `suspect: true` 保留两源值
- macro:DBnomics series API 按 `config/indicators.json`(五经济体 × CPI 同比/政策利率/外部账户;series ID 在 build 任务 2.2 实测确定后固化);记录 最新值/前值/period/发布判定
- events:每币种一组关键词(如 "Philippine peso" OR "BSP"),`timespan=48h`、`maxrecords≈8`、`sort=hybridrel`;串行 sleep 5s;响应 200 但正文含限速提示 → 视为软失败,退避 30s 重试一次;记录 title/url/domain/seendate/tone
- calendar:`state/calendar-2026.json`(五央行议息日程 + 主要统计发布,含 `valid_until` 字段);过期时写入 gap 提示更新

**2. 快照 schema(data/YYYY-MM-DD.json)**

```json
{
  "date": "2026-08-10", "run_at": "…", "schema_version": 1,
  "rates": {"PHP": {"primary": 60.843, "secondary": 60.834, "deviation_pct": 0.01, "suspect": false, "prev_primary": 60.9}, "…": {}},
  "macro": [{"economy": "PH", "indicator": "CPI 同比", "series_id": "…", "value": 3.1, "prev": 3.4, "period": "2026-07", "is_new_release": true}],
  "events": {"PHP": {"articles": [{"title": "…", "url": "…", "domain": "…", "seendate": "…"}], "tone_avg": -2.1}, "…": {}},
  "calendar_hits": [{"date": "2026-08-09", "bank": "BCB", "event": "COPOM 议息"}],
  "gaps": [{"source": "gdelt", "scope": "THB", "reason": "rate-limited after retry", "at": "…"}],
  "meta": {"collector_version": "…"}
}
```

**3. 决策日志(state/decision-log.jsonl,append-only)**
每行:`{"date", "currency", "scenario", "trigger", "watch_direction", "review": {"direction_outcome": 脚本填, "trigger_judgement": LLM 填(须引快照证据), "verdict": "命中|未命中|无法判定"}}`。方向核对 = `sign(今日 primary − 昨日 primary)` vs `watch_direction`,由 `scripts/review.py` 确定性计算;LLM 只判断触发条件是否发生。

**4. skill 文件**
- `skills/fx-daily-report/SKILL.md`:编排上述五步;内嵌日报模板(执行摘要 ≤6 条 → 五币种节[昨日发生→定价含义→情景与触发条件,≤约 300 字/节] → 复盘节 → 数据缺漏节)与禁令(不做无条件方向预测/数字只抄要点表/缺失数据不引用/共识值仅可标"据报道"转引)
- `skills/fx-weekly-report/SKILL.md`:周报模板(本周主线 ≤3 条 → 各币种一周归因 → 复盘汇总[命中/未命中/无法判定计数与明细] → 下周关注 → 缺漏汇总);一级结构禁止按日期

**5. 校验器(scripts/check_report.py)**
检查:五币种节齐全/摘要条数 ≤6/币种节字数 ≤约 300 中文字/缺漏节存在且与快照 gaps 一致/报告中数字(剔除日期)∈ 快照+要点表数字集合。退出码非 0 时 skill 触发自修一次。周报模式检查主题结构与覆盖天数声明。

## Error Handling

逐源降级矩阵:主汇率源挂 → 副源顶上+记缺漏;双源全挂 → 当日无汇率,报告缺漏节说明且币种节不写点位;GDELT 单币种挂 → 该币种"昨日无事件数据(采集失败)";DBnomics 挂 → 宏观节降级为年历+新闻;快照文件缺失 → skill 直接报错退出(采集是前置步骤,不允许无快照生成报告)。

## Testing

- 采集层:unittest + 本地 fixture(`tests/fixtures/*.json` + `file://`/本地 HTTP 注入),逐源故障注入覆盖 delta spec 全部采集侧 Scenario(含软限速正文识别、双源偏差、年历过期)
- review.py:两日快照构造用例覆盖 方向命中/未命中/昨日无观点/首次运行
- check_report.py:构造违规报告样例(缺节/超长/数字不在快照)验证拦截
- 端到端:真实跑一次日报(task 3.3)与一次周报(task 4.2),人工抽查数字溯源与叙事质量
- LLM 生成质量不做自动化断言,由校验器结构约束 + 端到端人工验收兜底

## Risks

- GDELT 在目标机器 IP 上限速更严 → 已设计串行+退避+缺漏兜底;极端情况当日事件全缺,报告如实披露
- 免费 API 变更/停服 → endpoints.json 集中配置便于替换;Frankfurter 可自托管为终极兜底
- 静态年历过期 → valid_until 检查 + 缺漏提示;维护方式写入 README
- LLM 报告风格漂移 → 模板+校验器硬约束;软性质量靠周度人工抽查(范围外)

## Spec Patch(已回写)

`specs/fx-data-collection/spec.md`·"宏观数据增量采集":零 key 改为默认路径(静态年历+GDELT 承担发布判定,不记缺漏);`FRED_API_KEY` 存在时 release dates 增强,增强路径失败才记缺漏。Scenario 相应改写为 零 key 默认路径/FRED 增强路径失败 两个场景。
