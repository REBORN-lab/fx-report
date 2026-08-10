# P3.6 跨笔记事实矛盾核对 — AS_OF 2026-08-10

逐对比较 7 份笔记中涉及同一对象的事实,找出不相容项。角度不同/范围不同不算;只计同一对象事实对不上的。

## Pair 1 — DeepEar 维护活跃度(调和)
- task-oss-pipelines: Date "2026-08-08 (updated)",Freshness fresh,呈现为活跃项目
- task-deepdive 实测: pushed_at 2026-04-16(115 天前),69/69 commits 单人,零 release
- 处置:调和。GitHub `updated` 字段受 star/fork 事件刷新,不代表开发活跃;以 `pushed_at`/last_commit 为准 → DeepEar 判 maintained 非 active。报告统一采信 deepdive 实测,并在 OSS 对比表注明单点维护风险。

## Pair 2 — DBnomics 对五经济体的覆盖(调和)
- task-data-sources: "可作为五币种宏观指标的单一接入点"(聚合 90+ 提供方)
- task-deepdive 实测: 93 家提供方中有 BCB、无 BSP/BOT;菲/泰仅 IMF/ILO 间接月度数据集
- 处置:调和。两者适用范围不同:「单一接入点」在 IMF 口径兜底意义上成立;央行一手数据意义上不成立(BRL 有 BCB 直连,PH/TH 必须另接)。报告按后一口径写明。

## Pair 3 — exchange-api 的"日更"口径(调和)
- task-popularity / task-gh-scan: README "Daily Updated...No Rate limits",代码仓 79 天无 commit(单点风险)
- task-deepdive 实测: `@latest` 返回 date=2026-08-09(滞后一天),但 2026-08-09 数据存在 → 数据发布管线(GitHub Actions→npm)独立于人工 commit 存活
- 处置:调和。"代码停更"与"数据日更"并存,两说法都对但对象不同;latest 滞后一天恰与"前一天"日报口径咬合。报告写明:用版本化日期端点、备 Cloudflare 兜底、并保留单人维护风险标注。

## Pair 4 — "开源生态无内置定时调度"(调和)
- task-oss-pipelines: "调研范围内没有任何一个头部开源项目内置每日定时调度环节"
- task-deepdive: claude-trading-skills 仓库含 launchd/ 目录(macOS 定时调度)
- 处置:调和。原命题限定在四个头部管线(TradingAgents/FinRobot/gpt-researcher/DeepEar)内成立;claude-trading-skills 是 skill 生态的局部反例(launchd 属外挂调度配置而非管线内置)。报告表述改为"头部管线均无内置调度,需外加 cron/GitHub Actions/launchd"。

## Pair 5 — GDELT DOC 2.0 的限流(调和)
- task-events: 免费无 key,"官方限流/配额没有文档化数字 [unverified]"
- task-deepdive 实测: 连续第二次请求即返回 "Please limit requests to one every 5 seconds"(HTTP 200 软限速)
- 处置:调和。免费无 key 成立,但存在未见于文档的运行时限速;实测值(5 秒/次)以 [自测 2026-08-10] 入报,工程上要求串行 + 识别"200 但正文是限速提示"的软失败。

同段落内矛盾扫描:未发现(各笔记内部 [与已知冲突] 标记均为对用户需求假设的冲突,非事实自相矛盾)。

Contradictions checked: 5 pairs (5 调和, 0 标注未决)
