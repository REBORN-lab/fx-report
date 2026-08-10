# Task: 事件数据与叙事方法论调研 (task-events)

AS_OF: 2026-08-10。主题属 fast-moving(数据 API / LLM 工具),aging 从严降级。

## Sources
[s1] GDELT Project — Data: Querying, Analyzing and Downloading | https://www.gdeltproject.org/data.html | Type: official | Date: 2022-09-03 (page timestamp) | Freshness: aging | Path: ddg
[s2] GDELT Project Blog — GDELT DOC 2.0 API Debuts! | https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/ | Type: official | Date: 2017-06-20 | Freshness: stale (API 至今仍在服务,机制描述仍有效) | Path: ddg
[s3] GDELT Cloud — Welcome to GDELT Cloud (docs) | https://docs.gdeltcloud.com/ | Type: official | Date: 2026 (snippet 标 2026-06-30) | Freshness: fresh | Path: ddg
[s4] ING THINK (Pesole/Taborsky/Turner) — FX Daily: High-stakes payrolls | https://think.ing.com/articles/fx-daily-high-stakes-payrolls/ | Type: secondary (银行研究) | Date: 2026-08-07 | Freshness: fresh | Path: ddg
[s5] Agility Forex (Michael O'Neill) — Agility Daily FX Commentary | https://agilityforex.com/market-news/agility-daily-fx-commentary-39/ | Type: secondary | Date: 2025-06-11 | Freshness: aging | Path: ddg
[s6] ING THINK — FX 栏目页(FX Daily / FX Talking 列表,含 Asia/Latam/EMEA FX Talking) | https://think.ing.com/market/fx/ | Type: secondary | Date: 2026-08-08 (页面滚动更新) | Freshness: fresh | Path: ddg
[s7] Expert Systems with Applications — Commentary generation for financial markets (MCG problem) | https://www.sciencedirect.com/science/article/abs/pii/S0957417422014798 | Type: academic | Date: 2022-08-17 | Freshness: stale | Path: ddg
[s8] UK ONS — Global Database of Events, Language and Tone (GDELT) appendix | https://www.ons.gov.uk/peoplepopulationandcommunity/birthsdeathsandmarriages/deaths/methodologies/globaldatabaseofeventslanguageandtonegdeltappendix | Type: official | Date: 2020-01-09 | Freshness: stale | Path: ddg
[s9] Capital Economics — FX Markets Weekly Wrap | https://www.capitaleconomics.com/publication-group/fx-markets-weekly-wrap | Type: secondary | Date: undated (持续出版) | Freshness: fresh | Path: ddg
[s10] alex9smith — gdeltdoc: A client for the GDELT 2.0 Doc API (PyPI) | https://pypi.org/project/gdeltdoc/ | Type: community | Date: undated | Freshness: aging | Path: ddg
[s11] Finance Context — morning-note (equity research skills) | https://financecontext.com/en/equity-research/skills/morning-note | Type: secondary | Date: undated | Freshness: aging | Path: ddg
[s12] HN (homarp) — Gdelt Project: Global Database of Events, Language, and Tone | https://news.ycombinator.com/item?id=30577040 | Type: community | Date: 2022-03-06 | Freshness: stale | Path: hn
[s13] Hofmann, Shim & Shin — Emerging Market Economy Exchange Rates and Local Currency Bond Markets Amid the COVID-19 Pandemic | https://doi.org/10.2139/ssrn.3761875 | Type: academic | Date: 2021 | Freshness: stale (机制性结论,非工具类) | Path: scholar
[s14] Evans & Lyons — Order Flow and Exchange Rate Dynamics | https://doi.org/10.3386/w7317 | Type: academic | Date: 1999 | Freshness: stale (经典机制文献) | Path: scholar
[s15] 中国银行 — 金融市场·外汇市场分析(汇市观察,每日) | https://www.boc.cn/fimarkets/foreignx/ | Type: official | Date: 2026-08-07 (最新一期) | Freshness: fresh | Path: ddg
[s16] Babypips — FX Weekly Recap: May 1-5, 2023 | https://www.babypips.com/news/forex-weekly-recap-2023-05-05 | Type: secondary | Date: 2023-05-05 | Freshness: stale | Path: ddg
[s17] Xing, Cambria & Welsch — Natural language based financial forecasting: a survey | https://doi.org/10.1007/s10462-017-9588-9 | Type: academic | Date: 2017 | Freshness: stale | Path: scholar

## Findings
1. GDELT 是免费开放的全球事件库,监控 100+ 语言全球新闻、300+ 类 CAMEO 事件编码,BigQuery 上的实时表每 15 分钟更新一次,完全满足"每天汇集前一天事件"的节奏;PHP/THB/BRL 等非 G10 货币所在国事件同样被覆盖(按国家/actor 编码,无 G10 偏向) [s1][s2] [新]
2. GDELT DOC 2.0 API(免费全文检索 API)可按英文关键词跨 65 种机器翻译语言检索最近 3 个月新闻,支持 JSON 输出、tone(情绪)直方图与 volume timeline 模式,最小时间粒度 15 分钟——这是 LLM 日报管线里最容易接的"昨日事件"入口,且有现成 Python 客户端 gdeltdoc [s2][s10] [新]
3. GDELT 原始 Event 库的已知限制:同类事件折叠(如"俄罗斯某天所有抗议合并为一条")、机器编码存在错误率,ONS 官方附录专门列出"数据不准确的例子";直接把 GDELT 事件行当作事实需要二次核验,更稳的用法是用它做"线索发现",再让 LLM 读原文 URL [s1][s8] [新]
4. GDELT Cloud(2026 年推出的第三方商业层)把 GDELT 文章流加工成结构化 Events/Stories/Entities,带 REST API + MCP server、每小时更新,并内置 market_sensitivity、systemic_importance 等事件指标和 "Brief Output Format" 指南——几乎就是为 LLM agent 生成简报设计的;但历史数据"2026 年 3 月以前不完整",且需 API key(付费计划) [s3] [新]
5. 专业银行 FX 日评(ING FX Daily)的叙事范式是固定的三段链条:昨日/今日事件 → 政策定价含义(央行会怎么解读、市场 pricing 变化多少 bp)→ 具体汇率区间与方向观点,按币种分节(USD/EUR/CAD/CEE),每节末尾给出明确点位(如 "EUR/USD stick to a 1.150-1.155 range"、"1.16 one-month and 1.18 year-end targets")——这正是用户要的"完整且明确的叙事逻辑链条"的成熟模板 [s4] [新]
6. 非银行侧日评(Agility Daily FX Commentary)提供另一种可自动化程度更高的模板:每币对固定给 open/overnight range/close 数字 + 一段事件归因 + 技术位(支撑/阻力/今日区间),外加 2-3 段跨市场主题(贸易谈判、CPI、股市风险情绪);结构高度公式化,适合程序化生成 [s5] [新]
7. 日评与周/月评的分工在 ING 体系里是现成范式:FX Daily(每日、事件驱动)之上有 FX Talking(每月、按区域拆 G10/EMEA/Latam/Asia 分册,给中期观点与预测表);周报类产品(Capital Economics FX Markets Weekly Wrap、Babypips FX Weekly Recap)的通用结构 = 本周主导主题一句话 + 各币种一周走势归因 + 下周前瞻,即"把每日事件按主题重新聚类"而非逐日流水账——直接对应用户"避免流水账"的要求 [s6][s9][s16] [新]
8. "市场评论自动生成"(Market Commentary Generation)在学术上已被形式化定义并算法化求解(2022, Expert Systems with Applications),其定位就是把每日海量资产变动压缩成"compact market commentaries...with key pieces of information";NLP 金融预测综述(400+ 引用)则梳理了新闻→价格的建模谱系——说明"事件+数据→简明日评"是有文献支撑的任务,不是空想 [s7][s17] [新]
9. 新兴市场货币的叙事链条与 G10 有结构性差异:BIS 研究表明 EM 汇率与本币债市资本流动、风险情绪高度联动(汇率贬值→债券抛售→进一步贬值的放大机制),因此 PHP/THB/BRL 的日评除本国事件外必须纳入美元/美债与全球风险情绪这条外生主线;ING 实践也是把 EM 按区域(Asia/Latam)与美元主题挂钩来写 [s13][s6] [新]
10. 用免费 GDELT 原始数据直接喂 LLM 会遇到量级问题——仅 2015 年 GKG 就超过 2.5TB、"nearly three quarters of a trillion emotional snapshots",可行路径是 DOC 2.0 API 按币种关键词拉少量高相关文章,而非批量下载事件表 [s1][s2] [与已知冲突]

## Trade-offs
事件数据获取路径 ≥3 个可比候选:

| 决策轴 | GDELT 原始数据 (BigQuery/CSV) [s1] | GDELT DOC 2.0 API [s2][s10] | GDELT Cloud [s3] |
|---|---|---|---|
| 成本 | 数据"100% free and open",但 BigQuery 查询费自付 [s1] | 免费,无 key [s2] | 需 API key + 付费计划("Plans & Data Modules") [s3] |
| 更新频率 | "live datasets updated every 15 minutes" [s1] | 最小窗口 15 分钟("minimum of 15 minutes") [s2] | "Data updates every hour" [s3] |
| 结构化程度 | CAMEO 事件行(actor/geo/tone/Goldstein),300+ 类 [s1] | 文章级检索 + tone/volume 聚合,非事件编码 [s2] | 去重 Stories + 结构化 Events + 实体链接 + market_sensitivity 等指标 [s3] |
| 历史深度 | "archives span more than 215 years" [s1] | 滚动最近 3 个月 [s2] | "spotty before March 2026" [s3] |
| LLM 管线友好度 | 差:2015 年 GKG 即 >2.5TB,需自建 ETL [s1] | 好:JSON 输出、Python 客户端 gdeltdoc [s2][s10] | 最好:MCP server + "Brief Output Format" 指南 [s3] |
| 代价/放弃了什么 | 放弃开发速度:自担编码噪声(ONS 列出实际不准确案例 [s8])与海量 ETL | 放弃事件编码与实体消歧:只有文章检索+tone,事实抽取要 LLM 自己做;放弃 >3 个月回溯 | 放弃零成本与长历史;引入第三方商业依赖(非 GDELT 官方) |

若只能选一个:DOC 2.0 API,因为免费、JSON、15 分钟粒度、跨 65 语言检索足以支撑"昨日事件→LLM 日评"且不需要事件表级精度;当 {需要现成的事件级 market_sensitivity 指标与 MCP 集成、且接受付费与 2026-03 后的历史起点} 成立时改选 GDELT Cloud。

## Deep Read Notes

### Data: Querying, Analyzing and Downloading (GDELT) [s1]
- 定位与规模:"The GDELT Project is the largest, most comprehensive, and highest resolution open database of human society ever created. Just the 2015 data alone records nearly three quarters of a trillion emotional snapshots and more than 1.5 billion location references, while its total archives span more than 215 years"。
- 免费开放:"The entire GDELT database is 100% free and open and you can download the raw datafiles, visualize it using the GDELT Analysis Service, or analyze it at limitless scale with Google BigQuery."
- 更新频率:"all GDELT datasets are available in Google BigQuery, with live datasets updated every 15 minutes",标准 SQL 可查全量。
- 体量警示:"Just the 2015 GKG dataset alone weighs in at over 2.5TB";Raw Data Files"over 2.5TB for last year alone"(CSV)。
- 三条访问路径:Analysis Service(浏览器可视化/导出,注意"currently searches only GDELT 1.0")、BigQuery、原始 CSV;文档页汇总 codebook/lookup 文件。
- 对本项目含义:事件字段体系(CAMEO 类别、actor、地理、tone)按国家编码,PHP/THB/BRL 所在国无覆盖障碍;但量级决定了日报管线应走 API 检索而非全量拉取。

### GDELT DOC 2.0 API Debuts! [s2]
- 检索窗口:"the API now searches a rolling window of the last 3 months of coverage, rather than just the last 24 hours of the original API";搜索粒度可窄化,搜索结果页原话:"You can narrow this range by using this option to specify the number of months, weeks, days, hours or minutes (minimum of 15 minutes)"。
- 跨语言:"GDELT's Translingual infrastructure machine translates 100% of all monitored coverage in 65 languages comprising 98.4% of GDELT's daily non-English monitoring volume"——用英文关键词即可命中菲律宾语/泰语/葡语本地报道,这对 PHP/THB/BRL 覆盖是关键能力。
- 输出模式:JSON/JSONP;内置可嵌入可视化;示例模式包括 timelinevolinfo(声量时间线+每步 top10 文章)与 tonechart("displays a histogram of how many articles...fell into each tone bin, from extremely negative to extremely positive")。
- 示例 URL 形如 `https://api.gdeltproject.org/api/v2/doc/doc?query=...&mode=timelinevolinfo&TIMELINESMOOTH=5`,无鉴权。
- 对本项目含义:每日跑 5 组币种关键词查询(timespan=24h~48h),取 tone + top 文章列表交给 LLM 归因,是最低成本的"昨日事件"采集器。

### Welcome to GDELT Cloud (docs.gdeltcloud.com) [s3]
- 定位:"GDELT Cloud turns the upstream GDELT Project article stream into a real-time structured Events database, with clustered Stories, linked Entities, summaries, API, and MCP tools around it."
- 更新:"Data updates every hour, giving you near real-time access to what's happening around the world."
- 历史限制(原文警示框):"GDELT Cloud Events and Stories data is spotty before March 2026. We will gradually backfill earlier history soon; current coverage is strongest from March 2026 onward"。
- 端点:`GET /api/v2/events`(coded events: actors, geography, category, metrics, sources)、`/stories`(去重聚类)、`/entities`、`/search`(名称→entity_id)、`/intelligence/gpr`、`/posture`(地缘指数)。鉴权:`Authorization: Bearer gdelt_sk_...`(搜索摘录)。
- 事件指标体系专设文档:magnitude、systemic_importance、propagation_potential、market_sensitivity,以及 "Limits and error bars" 页;Workflow Guides 有 "Brief Output Format" 与 "Multi-Surface Synthesis"——面向 agent 生成简报的现成方法论。
- 商业化:Developer Resources 下有 "Plans & Data Modules";Atlas Roadmap 部分 "describe work that is not built yet and have no endpoint to call"。

### FX Daily: High-stakes payrolls (ING THINK, 2026-08-07) [s4]
- 结构:导语(3 句话给出当日核心矛盾与观点)→ 按币种/区域分节:USD、EUR、CAD、CEE,每节署名分析师,末尾免责声明。
- 叙事链条示范(USD 节):驱动识别("short-term rate differentials have become increasingly the predominant driver of USD moves")→ 事件("Our macro team's call is 70k for July's payrolls today, a tad below the 80k consensus. We expect a modest rise in unemployment to 4.3%")→ 市场定价锚("Pricing has been remarkably stable at 14-17bp since the July FOMC")→ 结论("This scenario could result in a slightly softer dollar")→ 持仓期观点("our call remains one of USD weakness in the next couple of months")。
- 量化叙事:"In the past year, EUR/USD has moved on average 0.2% in the hour after the NFP release. The past two prints both saw moves of 0.4%"——用历史反应幅度校准事件重要性。
- 明确点位:"we expect EUR/USD to stick to a 1.150-1.155 range into next week's US CPI...1.16 one-month and 1.18 year-end targets";CEE 节同样落到 "EUR/CZK rose 0.2% to 24.235...the 24.250–24.300 range, which we see as the likely landing zone"。
- EM/次要货币写法(CEE 节):央行会议结果 → 利率市场重新定价("markets priced out roughly half a hike")→ 汇率区间 → 下一个催化剂(明日央行分析师会议)。可直接移植到 PHP/THB/BRL(BSP/BOT/BCB 会议与通胀数据)。

### Agility Daily FX Commentary (2025-06-11) [s5]
- 结构:主币对 USDCAD 深写(开盘/隔夜区间/收盘数字 + 事件归因 + 技术分析 + 当日区间预测 + 日线图)→ "FX at a Glance" 汇总表(截图)→ 3 个跨市场主题段(US/China "Framework" Light on Details、Inflation Numbers More Noise Than Trend、Equities in the "Green")→ 其余币对每对一段(EURUSD/GBPUSD/USDJPY/AUDUSD/NZDUSD),格式统一为 "NY Open: X, Overnight Range: Y–Z" + 3-4 句归因。
- 数字纪律示例:"USDCAD: open 1.3682, overnight range 1.3665-1.3689, close 1.3674";"Headline CPI would rose 2.4% y/y (forecast 2.5%, previous 2.3%). Core CPI rose 2.8% y/y (forecast 2.9%, previous 2.8% y/y)"——每个数据点带 forecast/previous 对照,叙事由"实际 vs 预期"差值驱动。
- 技术位格式:"For today, USDCAD support is at 1.3650 and 1.3610. Resistance is at 1.3710 and 1.3750. Today's Range: 1.3630-1.3730"。
- 跨资产快照:"Gold (XAUUSD) is 3336.21 and the US 10-year Treasury yield dropped to 4.433, post-CPI from 4.50% earlier. (as of 6:00 am PDT)"。
- 对本项目含义:这套"每币对固定字段 + 实际vs预期 + 支撑阻力"模板比银行长文更接近可程序化生成的形态;该站同时维护 Daily(Market Insights)与 Weekly FX Market Outlook 两个栏目,日/周分层与用户需求一致。

## Gaps
- 未找到专门研究"新闻事件→PHP/THB 汇率"的论文(scholar 检索被通用 EM 文献淹没);BRL 有 Latam FX Talking 等实践范例,但 PHP/THB 的公开日评范例(如本地银行 Metrobank/Kasikorn 晨报)没有深读——后续可定向抓 Metrobank Research / Kasikornbank Capital Markets 的每日报告页。
- GDELT Cloud 的具体定价数字没拿到(Plans & Data Modules 页未抓),免费层是否存在 [unverified]。
- GDELT DOC 2.0 API 的官方限流/配额没有文档化数字;社区普遍用 gdeltdoc 客户端但未验证当前可用性 [unverified]。
- 周报聚合只拿到结构范式(主题聚类 + 下周前瞻),没有找到"从每日 LLM 报告自动汇总周报"的现成开源实现;更好的角度可能是搜 "LLM daily digest weekly rollup pipeline github"。
- ScienceDirect MCG 论文只读到摘要(付费墙),其算法细节未入笔记。
- Sucden Financial 日报页抓取只返回 cookie 弹窗,未获得正文(未计入深读)。
