# P3.7 数字出处清点 — 本轮要写进报告的数字(AS_OF 2026-08-10)

分类:cited = 引自源(字面出现在被引来源);self = 本轮子代理实测([自测 2026-08-10]);derived = 计数/换算([推导])。

- [cited] Frankfurter "daily exchange rates from 84 central banks, covering 201 currencies back to 1948" [1]
- [cited] ExchangeRate-API Free 档 "1.5k Requests p/m" [3]
- [cited] ExchangeRate-API 限流 429 后 "After 20 minutes the rate limit will finish" [3]
- [cited] ExchangeRate-API Pro "$10/mo ... Updates Every 60 Minutes / 30k Requests p/m" [3]
- [cited] exchange-api README "200+ Currencies ... No Rate limits ... Daily Updated" [4]
- [cited] GDELT "live datasets updated every 15 minutes" [16]
- [cited] GDELT 监控 100+ 语言、300+ 类 CAMEO 事件编码 [16]
- [cited] GDELT "Just the 2015 GKG dataset alone weighs in at over 2.5TB" [16]
- [cited] GDELT DOC 2.0 机器翻译 65 语言、覆盖 "98.4% of GDELT's daily non-English monitoring volume" [17]
- [cited] GDELT DOC 2.0 滚动窗口最近 3 个月、最小粒度 15 分钟 [17]
- [cited] GDELT Cloud "Data updates every hour" [18]
- [cited] GDELT Cloud 历史 "spotty before March 2026" [18]
- [cited] ING: NFP 预测 70k vs 共识 80k、失业率 4.3% [21]
- [cited] ING: 降息定价 "remarkably stable at 14-17bp since the July FOMC" [21]
- [cited] ING: "EUR/USD to stick to a 1.150-1.155 range ... 1.16 one-month and 1.18 year-end targets" [21]
- [cited] ING: NFP 后一小时 EUR/USD 平均动 0.2%、最近两次 0.4% [21]
- [cited] Agility: "Headline CPI would rose 2.4% y/y (forecast 2.5%, previous 2.3%)" [23]
- [cited] 幻觉率 "from nearly 38% in 2021 to about 8.2% in 2026 ... as low as 0.7%" [41]
- [cited] FinRobot "~184k lines" 全栈规模 [29]
- [cited] FinRobot "1 Lead Agent + 5 role-based sub-agents + 3 debate agents" [29]
- [cited] gpt-researcher deep research "~5 minutes ... ~$0.4 per research" [30]
- [cited] gpt-researcher "Generate detailed reports exceeding 2,000 words" [30]
- [cited] DeepEar 接 15+ 中文/财经新闻源 [31]
- [cited] claude-trading-skills "15-minute daily market check" 日/周/月工作流 [32]
- [cited] awesome-quant 对 Vibe-Trading 描述 "7 backtest engines ... 17-tool MCP server" [34]
- [cited] awesome-quant 对 FinanceToolkit 描述 "50+ macro indicators" [34]
- [cited] Stack Overflow: ForexFactory 抓取遇 503 + Cloudflare 检查页 [49]
- [self] Frankfurter /v2/rates?base=USD&quotes=PHP,THB,BRL,EUR 返回 date=2026-08-10: BRL 5.1052 / EUR 0.866 / PHP 60.843 / THB 33.056(五币种一次调用齐返)
- [self] exchange-api /v1/currencies.json 共 338 个币种键,php/thb/brl/eur/usd 全在列
- [self] exchange-api @latest 返回 date=2026-08-09(滞后一天);版本化端点 currency-api@2026.8.9 可用
- [self] DBnomics v22 providers 实测 93 家,含 BCB,无 BSP/BOT
- [self] DBnomics 搜索: "Philippines consumer price index" 命中 12 个数据集、"Thailand policy rate" 命中 2 个
- [self] Finnhub /calendar/economic 无 key 实测 HTTP 401
- [self] GDELT DOC 2.0 第二次连续请求返回限速文本 "one every 5 seconds"
- [self] GDELT DOC 2.0 实测 48h 窗口命中 2026-08-09 菲律宾比索走弱本地报道(seendate 20260809)
- [self] 维护: frankfurter pushed 2026-07-23,v2.3.5 release 2026-06-25
- [self] 维护: exchange-api 代码仓 pushed 2026-05-22;数据 npm 包 2026-08-09 仍在发
- [self] 维护: DeepEar pushed 2026-04-16,69/69 commits 单人,零 release
- [self] 维护: claude-trading-skills pushed 2026-08-10(AS_OF 当天),694 commits
- [self] 维护: TradingAgents 与 gpt-researcher 均 pushed 2026-07-18
- [derived] 报告引用来源分层统计 T1×11 / T2×21 / T3×17 / T4×1、官方+学术 21/50=42.0% [推导 registry.md 各 Tier/Type 行计数]
- [derived] github.com 域占比 12/50=24.0% [推导 registry.md Approved 行按 host 计数]

- [cited] 星标快照(GitHub 页面显示值,2026-08-10): TradingAgents 96.9k★ [28]
- [cited] 星标快照: FinRobot 7.8k★ [29]
- [cited] 星标快照: gpt-researcher 28.9k★ [30]
- [cited] 星标快照: DeepEar 270★ [31]
- [cited] 星标快照: claude-trading-skills 2.6k★ [32]
- [self] 星标: OpenBB 71.7k★ / Vibe-Trading 30.5k★(GitHub API 实测,[34] 正文不含该数)
Number provenance: 32 cited, 14 self-measured, 2 derived (48 total)
