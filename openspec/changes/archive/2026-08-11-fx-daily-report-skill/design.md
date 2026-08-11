# Design: fx-daily-report-skill(高层架构)

## Context

全新仓库的首个 change。方案调研已完成并经引用验证(`super-research/…方案调研/report.md`,50 来源):数据源全部实测可用,无现成开源轮子,借鉴对象与叙事范式已定案。运行形态由用户确认:Claude Code CLI 无头模式(`claude -p`),中文报告,本地 markdown 输出;交付渠道与调度由用户自行接线。

## Goals / Non-Goals

**Goals:**
- 一条命令产出一份可信的五币种中文日报;一条命令产出周报
- 任何数据源失败都优雅降级并显式披露,管线永不因单源失败而中断
- 报告数字 100% 可溯源到当日快照文件

**Non-Goals:**
- Slack/邮件等推送、定时调度、异机部署(用户自理)
- 方向性汇率预测;盘中行情;付费数据源;网页爬虫

## Decisions

1. **两段式管线,快照文件为唯一接口**:数据采集是确定性 Python 脚本(标准库,无第三方依赖),产出 `data/YYYY-MM-DD.json` 快照;报告生成是 Claude skill,只读快照写叙事。理由:FinRobot 验证过的"数字代码算、LLM 只叙事"纪律,是防幻觉的结构性保障。备选"LLM 直接调 API 采数"被否:数字纪律无法保证,GDELT 串行限速在对话式调用里难以控制。
2. **skill 组织仿 claude-trading-skills**:`skills/fx-daily-report/SKILL.md` 与 `skills/fx-weekly-report/SKILL.md` 各自独立,skill 内先跑采集脚本再生成报告,`claude -p "/fx-daily-report"` 即完整一轮。备选"单一 Python 脚本直调 Anthropic API"被否:用户明确选择 Claude Code CLI 形态。
3. **数据源按调研定案**:Frankfurter(主,无 key)+ exchange-api 版本化端点(交叉校验,CC0)/ DBnomics(五经济体宏观,provider 实测定案为 IMF/BIS/ECB)+ FRED release dates(可选 key,缺失降级)/ GDELT DOC 2.0(串行 ≥5s,识别 200 软限速)/ 五央行议息静态年历(仓库内维护的数据文件)。全部免费,零爬虫。
4. **决策日志 append-only**:`state/decision-log.jsonl`,每日追加各币种情景观点;次日读取并对照快照汇率变动生成一句话复盘(借鉴 TradingAgents decision log 机制)。
5. **叙事模板取 ING 三段链条**:事件→定价含义→情景与触发条件;观点一律"若 X 则关注 Y"形态。周报按主题重聚类,禁止按日流水。

## Risks / Trade-offs

- [免费 API 无预告停服/变更] → 双源交叉 + 逐源降级 + 缺漏披露;Frankfurter 可自托管是终极兜底
- [GDELT 软限速(200 + 限速正文)] → 串行 sleep≥5s + 正文识别 + 单次退避重试,失败记缺漏
- [LLM 编造或改写数字] → 快照数字纪律写入 spec;验收时抽查报告数字与快照逐字一致
- [静态年历过期] → 年历文件带"有效期至"字段,过期时报告缺漏节自动提示更新
- [市场共识预期值免费拿不到] → 报告用"实际 vs 前值",事件文中若含记者转引的共识值可引用并标注转引

## Migration Plan

全新仓库,无迁移;回滚 = git revert。部署(范围外)只需:目标机器 clone 仓库 + 装 Claude Code + 配 key + 用户自建 cron。

## Open Questions(留给 design 阶段 brainstorming)

- 快照 JSON schema 的具体字段设计(含 gaps 结构)
- 五经济体各跟踪哪些 DBnomics 指标(CPI/政策利率/贸易差额…清单与序列 ID)
- 汇率双源偏差阈值 0.5% 的合理性(是否按币种流动性分层)
- 复盘"命中/未命中/无法判定"的判定规则(观点是情景式的,判定需要触发条件是否发生 + 方向是否兑现两步)
- 日报执行摘要与币种节的确切模板字段
