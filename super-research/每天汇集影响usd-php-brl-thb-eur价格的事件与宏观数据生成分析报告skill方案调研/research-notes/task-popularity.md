# Popularity Audit — 外汇/宏观分析与报告生成工具 (AS_OF: 2026-08-10)

## Sources
[s1] GitHub Search API — query "forex" sort:stars (top 100 / total_count 26,466) | https://github.com/search?q=forex&s=stars | Type: community | Date: 2026-08-10 | Freshness: fresh | Path: github-sweep
[s2] GitHub Search API — query "forex in:description" sort:stars (top 100 / 10,546) | https://github.com/search?q=forex+in%3Adescription&s=stars | Type: community | Date: 2026-08-10 | Freshness: fresh | Path: github-sweep
[s3] GitHub Search API — query "topic:forex" sort:stars (top 100 / 1,917) | https://github.com/topics/forex | Type: community | Date: 2026-08-10 | Freshness: fresh | Path: github-sweep
[s4] GitHub Search API — query "forex analysis" sort:stars (top 30 / 1,429) | https://github.com/search?q=forex+analysis&s=stars | Type: community | Date: 2026-08-10 | Freshness: fresh | Path: github-sweep
[s5] GitHub Search API — FM-3 复查 query "forex" sort:updated (top 100 / 26,466) | https://github.com/search?q=forex&s=updated | Type: community | Date: 2026-08-10 | Freshness: fresh | Path: github-sweep
[s6] DDG — "forex github stars" (RepositoryStats/topic 页等, 无新的高星发现) | https://repositorystats.com/topic/forex-trading | Type: community | Date: 2026-08-10 | Freshness: fresh | Path: ddg
[s7] DDG — "forex best open source tools 2025 2026" (全部为券商/经纪商营销页, 无开源项目) | https://www.forexfactory.com/calendar | Type: journalism | Date: 2026-08-10 | Freshness: fresh | Path: ddg
[s8] DDG — "awesome forex github" (发现 awesome-systematic-trading、awesome-quant、trackawesomelist) | https://github.com/wangzhe3224/awesome-systematic-trading | Type: community | Date: 2026-08-10 | Freshness: fresh | Path: ddg
[s9] AKShare 官方文档 — "AKShare 外汇数据"（DDG "akshare 外汇 汇率 数据" 发现） | https://akshare.akfamily.xyz/data/fx/fx.html | Type: official | Date: 2026-08-10 (文档版本 1.18.81) | Freshness: fresh | Path: ddg
[s10] DDG — "宏观 研报 自动生成 github 开源"（发现 report_gen、FinRobot、GPT-Researcher、tianchi_AFAC_AGENT） | https://github.com/masterlyj/report_gen | Type: community | Date: 2026-08-10 | Freshness: fresh | Path: ddg
[s11] DDG — "外汇 日报 生成 工具"（结果几乎全为 AI 绘图/通用日报工具噪音, 无相关开源项目） | https://www.eahub.cn/thread-206533-1-1.html | Type: community | Date: 2026-08-10 | Freshness: fresh | Path: ddg
[s12] wilsonfreitas/awesome-quant — README（28,609 stars [自测 2026-08-10], pushed 2026-08-10） | https://github.com/wilsonfreitas/awesome-quant | Type: community | Date: 2026-08-10 | Freshness: fresh | Path: awesome-list
[s13] wangzhe3224/awesome-systematic-trading — 项目主页镜像（4,812 stars [自测 2026-08-10]; raw README master/main 均 404, 改抓 GitHub Pages） | https://wangzhe3224.github.io/awesome-systematic-trading/ | Type: community | Date: 2026-08-10 | Freshness: fresh | Path: awesome-list

注: 所有 star 数为本人当日调 GitHub API 实测, 统一标 [自测 2026-08-10]。--github 仅补元数据, 不改写 Path。

## Layer 1 合并去重 Top-30（5 条查询合并, 共 289 个唯一仓库, stars 降序, [自测 2026-08-10]）
1. nautechsystems/nautilus_trader — 25,389 ★ — Rust 交易引擎
2. QuantConnect/Lean — 21,141 ★ — 算法交易引擎
3. NoFxAiOS/nofx — 12,723 ★ — AI trading terminal（股/商品/forex/crypto）
4. StockSharp/StockSharp — 10,541 ★ — 算法交易平台
5. OpenByteInc/QuantDinger — 10,438 ★ — AI 量化平台（crypto/stocks/forex）
6. kernc/backtesting.py — 8,774 ★ — 回测框架
7. TraderAlice/OpenAlice — 6,467 ★ — AI trading agent（含 forex）
8. atilaahmettaner/tradingview-mcp — 3,904 ★ — TradingView MCP server
9. fawazahmed0/exchange-api — 2,563 ★ — 免费汇率 API（200+ 货币）
10. ta4j/ta4j — 2,480 ★ — Java 技术分析库
11. blankly-finance/blankly — 2,464 ★ — 算法交易框架
12. AminHP/gym-anytrading — 2,380 ★ — RL 交易环境
13. joshyattridge/smart-money-concepts — 1,923 ★ — SMC 指标库
14. Lumiwealth/lumibot — 1,900 ★ — AI 交易 agent/回测
15. lineofflight/frankfurter — 1,767 ★ — 货币数据 API
16. lit26/finvizfinance — 1,551 ★ — Finviz 分析库
17. mnemox-ai/tradememory-protocol — 1,408 ★ — AI 交易 agent 记忆协议
18. florianv/swap — 1,339 ★ — PHP 汇率转换库（30 providers）
19. deepentropy/tvscreener — 1,303 ★ — TradingView Screener API
20. kieran-mackle/AutoTrader — 1,270 ★ — 自动交易平台
21. EA31337/EA31337 — 1,260 ★ — MT4/MT5 forex 机器人
22. facioquo/stock-indicators-dotnet — 1,227 ★ — .NET 指标库
23. shner-elmo/TradingView-Screener — 1,079 ★ — TradingView 筛选器
24. TheSnowGuru/PyTrader-python-mt4-mt5-trading-api-connector — 1,034 ★ — MT 连接器
25. JECSand/yahoofinancials — 968 ★ — Yahoo Finance 数据模块
26. mhallsmoore/qsforex — 856 ★ — Forex 回测/实盘
27. Leo4815162342/dukascopy-node — 844 ★ — Dukascopy tick 数据下载（含 Forex）
28. twelvedata/twelvedata-python — 765 ★ — Twelve Data 金融数据 API 客户端
29. MicroPyramid/forex-python — 709 ★ — 汇率/货币转换库
30. saidsurucu/borsapy — 703 ★ — 土耳其市场数据库（含 forex）
（[s1][s2][s3][s4][s5]; total_count 26,466 > 200 已触发 FM-3, sort:updated 复查已并入以上合并表）

## Findings
1. OpenBB（OpenBB-finance/OpenBB, 71,704 ★ [自测 2026-08-10]）自述 "Open Data Platform for analysts, quants and AI agents", 是被全部 forex 关键词 Layer-1 查询漏掉的最高星相关项目, 经 awesome-quant 交叉发现; 货币/宏观数据 + AI agent 定位可直接借鉴到 LLM 日报数据层 [s12] [新]
2. HKUDS/Vibe-Trading（30,487 ★ [自测 2026-08-10]）被 awesome-quant 描述为 "Natural-language multi-agent finance research agent … 7 backtest engines covering A-shares/US/Crypto/Futures/Forex/Options … 5-source auto-fallback data layer (tushare/okx/yfinance/akshare/ccxt); 17-tool MCP server", 是与"LLM 驱动的外汇研究管线"最接近的高星项目 [s12] [新]
3. assafelovic/gpt-researcher（28,908 ★ [自测 2026-08-10]）为自主研究报告生成 agent（"自动进行信息检索、事实验证与报告撰写"）, 其检索→验证→撰写流水线可直接借鉴到"叙事逻辑链条"日报/周报生成 [s10] [新]
4. akfamily/akshare（21,914 ★ [自测 2026-08-10]）官方文档设"AKShare 外汇数据"专章（"人民币汇率中间价"、"人民币外汇即期报价"）, 但外汇章以人民币对为中心, PHP/THB/BRL 兑 USD/EUR 的直接覆盖未在文档摘要中确认, 需验证后才能作为五币种数据源 [s9] [与已知冲突]
5. fawazahmed0/exchange-api（2,563 ★ [自测 2026-08-10]）自述 "Free Currency Exchange Rates API with 200+ Currencies & No Rate Limits", 是 Layer-1 内最贴合"免费 + 每日 + 覆盖 PHP/THB/BRL 类小币种"约束的数据源候选 [s1] [新]
6. lineofflight/frankfurter（1,767 ★ [自测 2026-08-10], 自述 "Currency data API"）与 MicroPyramid/forex-python（709 ★）构成免费汇率 API 的次选梯队; frankfurter 可自托管, 适配每日定时抓取 [s1] [新]
7. AI4Finance-Foundation/FinRobot（7,758 ★ [自测 2026-08-10]）自述 "An Open-Source AI Agent Platform for Financial Applications using LLMs", 中文社区明确将其定位为"股票预测、财务分析、研报撰写"平台, 是研报生成 agent 的可借鉴参照 [s10] [新]
8. Layer-1 头部（nautilus_trader 25,389 ★、Lean 21,141 ★、StockSharp 10,541 ★）全部是交易/回测引擎而非分析报告工具, 说明 forex 高星生态与本需求（日报叙事生成）错位, 语义检索若只看 top 星标会引向错误方向 [s1] [新]
9. 宏观数据工具层: JerBouma/FinanceToolkit（5,206 ★ [自测 2026-08-10], awesome-quant 描述含 "50+ macro indicators which pulls from Financial Modeling Prep, Yahoo Finance, OECD, GMBD and more"）与 cuemacro/findatapy（2,095 ★）/finmarketpy（3,800 ★, Cuemacro 系 FX 宏观背景）可作宏观指标数据层 [s12] [新]
10. 机制层小星标但形态高度对口: fizahkhalid/forex_factory_calendar_news_scraper（96 ★, "Forex Factory economic calendar scraper with rule-based pre-event alerts"）与 sahilgupta/sbi-fx-ratekeeper（213 ★, "downloads and stores the daily SBI forex rates in a CSV file"）演示了"每日抓取经济日历/汇率→存档"的最小管线形态, 星标低但可直接抄结构 [s1][s2] [新]

## Trade-offs
可比候选按两条轴分组（数据源层 / 报告生成层）, 星数均 [自测 2026-08-10]:

| 候选 | 定位 | PHP/THB/BRL 覆盖 | 日更适配 | LLM 日报管线可借鉴度 | 代价/放弃了什么 |
|---|---|---|---|---|---|
| exchange-api (2,563★) | 免费汇率 API | "200+ Currencies" [s1], 具体币种清单来源未说明 | "No Rate Limits" [s1] | 仅数据, 无分析 | 只有汇率价格, 无事件/宏观数据, 无叙事能力 [s1] |
| frankfurter (1,767★) | 货币数据 API | 来源未说明（GH 描述仅 "💱 Currency data API" [s1]） | 来源未说明 | 仅数据 | 覆盖范围与更新频率需自行验证; 无宏观事件 [s1] |
| akshare (21,914★) | 财经数据接口库 | 外汇章以"人民币汇率中间价/即期报价"为主 [s9], 五币种交叉盘覆盖来源未说明 | 库本身支持日频调用 [s9] | 数据层可借鉴 | 以中国市场为中心, 非 RMB 交叉盘与英文宏观事件覆盖不明 [s9] |
| OpenBB (71,704★) | "Open Data Platform for analysts, quants and AI agents" [自测 API 描述] | 来源未说明 | 来源未说明 | 数据层+agent 接口均可借鉴 | 平台体量大, 作为单一 skill 的依赖偏重; 具体货币数据依赖上游 provider [s12] |
| gpt-researcher (28,908★) | 自主研究报告 agent | 不适用（不含金融数据源） | 可定时驱动 | 报告叙事流水线直接可借鉴（"信息检索、事实验证与报告撰写" [s10]） | 非金融专用, 数据源与外汇宏观日历需自建 [s10] |
| FinRobot (7,758★) | LLM 金融 agent 平台 | 来源未说明 | 来源未说明 | 研报撰写模块可借鉴 [s10] | 以股票/财报为主场景, 外汇宏观场景来源未说明 [s10] |
| Vibe-Trading (30,487★) | 多 agent 金融研究平台 | 来源未说明（数据层为 tushare/okx/yfinance/akshare/ccxt [s12]） | 来源未说明 | 多 agent 研究编排 + 数据 fallback 设计可借鉴 [s12] | 面向交易回测而非日报叙事; 数据 fallback 里无小币种专用源 [s12] |

若只能选一个: gpt-researcher, 因为用户核心痛点是"完整且明确的叙事逻辑链条"的日报/周报生成, 它是唯一以"检索→验证→成文"为主干的高星项目, 数据层缺口可用 exchange-api（免费、200+ 货币、无限流）补齐; 当消费者验证发现 exchange-api/frankfurter 无法提供 PHP/THB/BRL 的历史序列或前一日宏观事件时, 改选 OpenBB 作数据层（provider 生态更全, 但依赖更重）。报告层证据不足以在 gpt-researcher 与 FinRobot 间做终局决断——缺 FinRobot 外汇/宏观场景支持度的一手证据（本轮为 SCAN, 未深读其 README）。

## Cross-check: DDG + Ecosystem vs GitHub
Projects found in DDG/Layer 2.5 results but NOT in GitHub Layer 1 合并去重列表:
- awesome-systematic-trading → --github wangzhe3224/awesome-systematic-trading → 4,812 stars → relevant（索引仓库, 已按 Layer 4 解析 [s13]）
- awesome-quant → --github wilsonfreitas/awesome-quant → 28,609 stars → relevant（索引仓库, 已按 Layer 4 解析 [s12]）
- akshare → --github akfamily/akshare → 21,914 stars → relevant（已入 Findings #4）
- FinRobot → --github AI4Finance-Foundation/FinRobot → 7,758 stars → relevant（已入 Findings #7）
- gpt-researcher → --github assafelovic/gpt-researcher → 28,908 stars → relevant（已入 Findings #3）
- report_gen → --github masterlyj/report_gen → 1 star → irrelevant（题材完全对口——"全流程自动化生成宏观经济、行业分析等多维度的金融研究报告" [s10]——但 1 星、2025-09 后无更新, 不入 Findings; 可作题材参考）

Layer 4 awesome-list 交叉（不在 Layer-1 top-100 的相关项目, --github 共 5 次）:
- JerBouma/FinanceToolkit → 5,206 stars → relevant（Findings #9）
- cuemacro/findatapy → 2,095 stars → relevant（Findings #9）
- cuemacro/finmarketpy → 3,800 stars → relevant（Findings #9）
- OpenBB-finance/OpenBB → 71,704 stars → relevant（Findings #1）
- HKUDS/Vibe-Trading → 30,487 stars → relevant（Findings #2）
- FXMacroData（awesome-quant 原文: "Real-time forex macroeconomic API for all major currency pairs sourced from central bank announcements. GitHub (⭐3)" [s12]）→ 3 stars（引自清单标注, 未另查）→ 题材对口但星数过低, 不入 Findings

## Gaps
- Layer 3 Scholar 按任务指令跳过: 本轮证据画像为 oss+factual（开源工具盘点+事实性数据源核查）, 非学术主题, 学术检索对"哪个仓库高星且可借鉴"无增益。
- wangzhe3224/awesome-systematic-trading 的 raw README（master 与 main 分支）均 404, 改抓其 GitHub Pages 镜像成功 [s13]; 内容与 README 同源, 但行内 star 徽章数字未能提取。
- DDG "外汇 日报 生成 工具" 与 "forex best open source tools 2025 2026" 两条查询几乎全是噪音（AI 绘图站、券商营销页）, 说明中文"外汇日报生成"方向没有形成开源生态——用户需求大概率要自建, 无现成轮子。
- 未验证 exchange-api / frankfurter 对 PHP/THB/BRL 的具体覆盖与历史数据深度（SCAN 不深读）; 这是下一轮 DEEP 的首要验证点, 直接决定数据层选型。
- 未搜 "economic calendar api"、"central bank" 等非 forex 关键词的 GitHub sweep; forex 关键词生态偏交易, 宏观事件数据源（经济日历类）可能另有高星仓库被本轮口径漏掉。
- GitHub 无 token 限速下 --github 共 11 次（Layer4 前置 2 + Layer4 交叉 5 + Layer5 交叉 4）, 未超预算, 无 403/429。
