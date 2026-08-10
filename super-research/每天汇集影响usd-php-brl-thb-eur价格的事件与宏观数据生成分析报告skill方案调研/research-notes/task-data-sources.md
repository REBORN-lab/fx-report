# Task: 数据基础设施盘点 — 免费/开放数据源与 API(汇率、宏观、日历、央行、事件)

AS_OF: 2026-08-10 | 主题属 fast-moving(数据 API / LLM 工具)

## Sources
[s1] Frankfurter (Line of Flight) — Frankfurter | Free exchange rates API | https://frankfurter.dev/ | Type: official | Date: 2026 (© 2018–2026, v2 现行文档) | Freshness: fresh | Path: ddg
[s2] ExchangeRate-API — Open Access Endpoint docs | https://www.exchangerate-api.com/docs/free | Type: official | Date: 2026-07-29 (Published Time) | Freshness: fresh | Path: ddg
[s3] DBnomics (Cepremap) — What is DBnomics? (docs) | https://db.nomics.world/docs/ | Type: official | Date: 2026-08-07 (Published Time) | Freshness: fresh | Path: ddg
[s4] Federal Reserve Bank of St. Louis — FRED® API docs | https://fred.stlouisfed.org/docs/api/fred/ | Type: official | Date: n.d.(在维护的活文档,含 API v2) | Freshness: fresh | Path: direct-fetch
[s5] Banco Central do Brasil — Open Data Portal / API 页 | https://opendata.bcb.gov.br/en/ 与 https://www.bcb.gov.br/api/ | Type: official | Date: n.d. | Freshness: fresh | Path: ddg
[s6] Bank of Thailand — Statistics 门户 | https://www.bot.or.th/en/statistics.html | Type: official | Date: n.d. | Freshness: fresh | Path: ddg
[s7] Bangko Sentral ng Pilipinas — Statistics 门户 | https://www.bsp.gov.ph/SitePages/Statistics/Statistics.aspx | Type: official | Date: n.d. | Freshness: fresh | Path: ddg
[s8] Finnhub — Economic Calendar API docs | https://finnhub.io/docs/api/economic-calendar | Type: official | Date: n.d. | Freshness: fresh | Path: ddg
[s9] Trading Economics — Calendar API | https://tradingeconomics.com/api/calendar.aspx | Type: official | Date: n.d. | Freshness: fresh | Path: ddg
[s10] FXStreet — Economic Calendar API docs / Swagger | https://docs.fxstreet.com/api/calendar/ | Type: official | Date: n.d. | Freshness: fresh | Path: ddg
[s11] ZhuLinsen — daily_stock_analysis (SKILL.md) | https://github.com/ZhuLinsen/daily_stock_analysis/blob/main/SKILL.md | Type: community | Date: 2026 (知乎介绍文 2026-04-03) | Freshness: fresh | Path: ddg
[s12] SidneyBissoli — bcb-br-mcp (BCB SGS 的 MCP server) | https://github.com/SidneyBissoli/bcb-br-mcp | Type: community | Date: n.d. | Freshness: fresh | Path: ddg
[s13] kiprio.com — Best Free Currency Exchange Rate API in 2026 | https://kiprio.com/blog/free-currency-exchange-rate-api/ | Type: secondary | Date: 2026 | Freshness: fresh | Path: ddg
[s14] andrevlima — economic-calendar-api (investing.com 爬虫) | https://github.com/andrevlima/economic-calendar-api | Type: community | Date: n.d. | Freshness: aging(爬虫类项目易失效,从严对待) | Path: ddg
[s15] 知乎专栏 — 2026 全球外汇免费实时行情汇率数据 API 接口大全 | https://zhuanlan.zhihu.com/p/1995957320849585498 | Type: community | Date: 2026 | Freshness: fresh | Path: ddg

## Findings
1. Frankfurter 是本任务最强候选:免费开源、无 API key、"tracks daily exchange rates from 84 central banks, covering 201 currencies back to 1948",且实测 USD 对 PHP/THB/BRL/EUR 一次调用全返回 [s1] [新]
2. Frankfurter 明确无月/日配额("There are no quotas"),商用免费,可自托管 Docker,还提供 llms.txt 和 MCP server,天然适配 LLM 报告管线 [s1] [新]
3. ExchangeRate-API Open Access 端点无需 key、每日更新一次、要求页面注明出处(attribution),实测同样覆盖 PHP/THB/BRL/EUR;注册 Free 档 1.5k 次/月免 attribution [s2] [新]
4. DBnomics 免费聚合 90+ 官方统计机构(IMF/ECB/世行/OECD 等)的宏观时间序列,统一 API,"Daily Automatic Updates"、保留历史修订版本,可作为五币种宏观指标的单一接入点 [s3] [新]
5. FRED API 免费但需注册 API key,覆盖含 World Bank 标签下 16,897 个序列,自带 Release Calendar(发布日历)可用于"前一天发了什么数据"的判定 [s4] [新]
6. 巴西央行 BCB 提供无 key 的开放 SGS 时间序列与 PTAX 官方汇率 API(Selic、IPCA、汇率等),每日更新,BRL 侧官方数据最易机读;社区已有现成 MCP server 封装 [s5][s12] [新]
7. 泰国央行 BOT 与菲律宾央行 BSP 均有统计门户,但搜索结果层面未见像 BCB 那样"无 key 开放 REST API"的直接证据——PHP/THB 官方宏观数据的机读接入是本方案的相对薄弱环节,可用 DBnomics/FRED 兜底 [s6][s7][s3] [与已知冲突]
8. 免费经济日历 API 是最大缺口:FXStreet/Trading Economics 日历 API 面向付费/授权客户,Finnhub 经济日历在其免费档的可用性待验证,社区替代多为 investing.com 爬虫(不稳定、许可存疑) [s8][s9][s10][s14] [新]
9. 免费汇率 API 常见坑:Open Exchange Rates 免费档锁 USD 基准、Fixer 锁 EUR 基准,"Kiprio and ExchangeRate-API let you specify any base currency on the free tier";Frankfurter 无此限制 [s13][s1] [新]
10. 可借鉴的开源项目形态:daily_stock_analysis(2.6k+ star,LLM 驱动多源行情+新闻+定时推送,靠 GitHub Actions 零成本每日运行)与 bcb-br-mcp,均属"免费数据源 + LLM 摘要 + 定时产报"管线,与本 skill 目标同构 [s11][s12] [新]

## Trade-offs
候选按角色分两组同轴对比。

汇率行情源(PHP/THB/BRL/EUR 兑 USD 每日报价):

| 候选 | PHP/THB/BRL 覆盖 | 更新频率 | 免费额度/限流 | 认证 | 许可 | 代价/放弃了什么 |
|---|---|---|---|---|---|---|
| Frankfurter [s1] | 全覆盖 [自测 2026-08-10] | 每日("tracks daily exchange rates")[s1] | 无配额,仅防滥用限速("There are no quotas. Requests are rate-limited to prevent abuse")[s1] | 无 key [s1] | 开源,商用免费("Is the API free for commercial use? Yes, absolutely")[s1] | 只有日频参考价,无盘中价、无买卖价差;数据准确度靠混合多来源,末位小数可能变动 [s1] |
| ExchangeRate-API Open Access [s2] | 全覆盖 [自测 2026-08-10] | "Updates Once Per Day" [s2] | "Rate Limited",超限 429、20 分钟解封 [s2] | 无 key [s2] | 需页面 attribution,"not allowed to re-distribute" [s2] | 强制署名;禁止再分发数据;每日仅一刷,盘中不可用 [s2] |
| ExchangeRate-API Free(注册档)[s2] | 全覆盖(同上数据源) | "Updates Once Per Day" [s2] | "1.5k Requests p/m" [s2] | 需 API key [s2] | 免 attribution [s2] | 月配额低;历史数据端点在免费档的可用性来源未说明("Historical Data" 列于文档目录,免费档权限未写明)[s2] |
| BCB PTAX/SGS [s5] | 仅 BRL(官方 PTAX) | 每日("updated daily by the Banco Central do Brasil")[s5] | 来源未说明(oanor 转述"no key, nothing cached" [s5],官方页未见配额条款) | 无 key [s5][s12] | 开放数据门户 | 单一币种,不能覆盖 PHP/THB/EUR;需另配主汇率源 [s5] |

宏观指标/日历源:

| 候选 | PHP/THB/BRL 经济体覆盖 | 更新频率 | 免费额度 | 认证 | 代价/放弃了什么 |
|---|---|---|---|---|---|
| DBnomics [s3] | 覆盖(聚合 IMF/世行/OECD 等 90+ 提供方,含新兴市场)[s3] | "Daily Automatic Updates...updated as soon as providers publish" [s3] | 免费平台;具体限流来源未说明("without dealing with...rate limits"仅指代用户免于处理上游限流)[s3] | 文档未提及 key(来源未说明) | 无"事件日历/预期值/实际值"概念,只有时间序列;新兴市场指标滞后取决于上游提供方 [s3] |
| FRED [s4] | 部分(以美国为主,World Bank 标签 16,897 序列可补国别年度指标)[s4] | 随上游 release;自带 Release Calendar [s4] | 免费,配额来源未说明 | 需注册 API key("API Keys"文档)[s4] | 非美经济体高频数据弱;PHP/THB 月度 CPI 类指标覆盖不保证 [s4] |
| Finnhub 经济日历 [s8] | 待验证(自称"Free APIs for realtime stock, forex"含 Economic data)[s8] | 来源未说明 | 免费档对该端点的开放性来源未说明 | 需 API key(Finnhub 通例) | 免费档很可能不含该端点或仅限主要经济体,需实测;条款限制再分发(来源未说明,需查 ToS)[s8] |
| Trading Economics 日历 [s9] | 覆盖广(其站覆盖全球日历) | 实时,含 Point-In-Time 修订前原值 [s9] | 来源未说明(API 为商业授权产品) | 需 client key | 免费额度基本为试用性质;成本高,与"免费/开放"约束冲突 [s9] |
| investing.com 爬虫类(andrevlima 等)[s14] | 覆盖全球日历 | 爬取即更新 | 无官方额度概念 | 无 | 违反目标站 ToS 风险、随时被反爬失效、许可不清,不宜进生产管线 [s14] |

决断:若只能选一个汇率源:Frankfurter,因为无 key、无配额、开源可自托管、实测覆盖全部五币种且对 LLM 管线有 llms.txt/MCP 原生支持;当需要"盘中/更高频报价"或希望响应里自带下次更新时间戳做调度锚点时改选 ExchangeRate-API(Open Access 每日一刷 + time_next_update 字段)。宏观侧:若只能选一个:DBnomics,因为单点聚合能同时覆盖 PH/TH/BR/EU/US 五个经济体;当需要美国数据深度 + 数据发布日历(判定"前一天发生了什么")时叠加 FRED。经济日历轴证据不足以决断:免费且合规覆盖五经济体的事件日历 API 尚未找到确证,缺 Finnhub 免费档实测与 MQL5 Economic Calendar 条款核查。

## Deep Read Notes

### Frankfurter | Free exchange rates API [s1]
- 覆盖与历史:"Frankfurter tracks daily exchange rates from 84 central banks, covering 201 currencies back to 1948."
- 认证:"The public API lives at api.frankfurter.dev. It requires no API key. The project is open source, so you can also self-host for full control."
- 限流:"Does the API have any call limits? There are no quotas. Requests are rate-limited to prevent abuse, but there are no monthly or daily caps."
- 商用:"Is the API free for commercial use? Yes, absolutely. See each provider's terms for details on the underlying data."
- LLM 适配:"Working with an AI agent? Point it at llms.txt, or add the MCP server."
- 关键端点:`/v2/rates?base=USD&quotes=...`(最新)、`?date=`(历史)、`from/to`(时间序列)、`group=week|month`(降采样,可直接服务周报)、`providers=ECB`(合规场景取单一官方参考价)、CSV/NDJSON 输出。
- 准确度口径:"For compliance, filter by a specific provider to get official reference rates. For general use, the default blended rates work well, though the last decimal places may shift as new data comes in."
- [自测 2026-08-10] `GET /v2/rates?base=USD&quotes=PHP,THB,BRL,EUR` 返回 date=2026-08-10 的 BRL 5.1052 / EUR 0.866 / PHP 60.843 / THB 33.056,四币齐全。

### ExchangeRate-API — Open Access Endpoint [s2]
- 三档对比原文:Open API — "No API Key / Attribution Required / Updates Once Per Day / Rate Limited";Free API — "API Key Required / No Attribution / Updates Once Per Day / 1.5k Requests p/m";Pro — "Only $10/mo! ... Updates Every 60 Minutes / 30k Requests p/m"。
- 限流细节:"Rate limited IP's will receive HTTP code 429 responses. After 20 minutes the rate limit will finish";建议"request once every hour and never get rate limited",因"The data only refreshes once every 24 hours anyway."
- 许可:"requires attribution ... You're welcome to cache the data ... You are, however, not allowed to re-distribute it."
- 调度友好:响应含 `time_next_update_unix/utc` 字段;弃用预警字段 "the time_eol field will start showing the unix time of expected deprecation"。
- 端点:`GET https://open.er-api.com/v6/latest/USD` 一次返回全部支持币种。
- [自测 2026-08-10] 实测返回 PHP 60.834 / THB 33.024 / BRL 5.089 / EUR 0.8655,time_last_update_utc = "Mon, 10 Aug 2026 00:02:31 +0000"(UTC 零点后刷新,适合"前一天"日报节奏)。

### DBnomics documentation — What is DBnomics? [s3]
- 定位:"DBnomics is a free platform that aggregates publicly available economic data from national and international statistical institutions ... All data is standardized into a common format."
- 更新:"Daily Automatic Updates — Our daily data pipeline runs dedicated fetchers — one per provider — to collect new releases and archive every revision. Your indicators are updated as soon as providers publish new data."
- 修订史:"Every change from providers is archived, so that past revisions of time series remain accessible."(可支撑"数据修正也是事件"的叙事)
- LLM 适配:"LLM-friendly versions of this documentation are available at /llms.txt ... and /llms-full.txt"。
- 工具链:Web API + Python/R 客户端;搜索结果中另证提供方超 90 家含 IMF/ECB/Eurostat/World Bank/OECD/BLS/BEA(api-evangelist 转述)。
- 文档页未提及 API key 或配额数字——免费额度按"来源未说明"处理。

### FRED® API docs(部分,页面截断)[s4]
- "The FRED® API, Version 2 is ideal for anyone who is interested to retrieve observations for all series on a release in bulk and obtain the entire history."
- 需注册 key(General Documentation 列有 "API Keys" 条目);具体速率限制数字在截断页外,记 [unverified](常引为 120 req/min,但本次未取到原文,不采用)。
- 对本方案最有价值的是 Releases 端点族:`fred/releases/dates — Get release dates for all releases of economic data`,可程序化判断"昨天发布了哪些数据"。
- World Bank 标签下 "16,897 economic data series with tag: World Bank"(FRED 站内页 [s4] 同域搜索结果),可补五经济体年度/低频指标。

## Gaps
- 未找到"免费 + 无爬虫 + 覆盖 PH/TH/BR 的经济日历 API"的确证:Finnhub 免费档是否开放 economic-calendar 端点未实测;MQL5/forexfactory 免费日历方案(2023 帖,aging)条款未核查。这是数据管线最大空洞,建议下一步实测 Finnhub key 和评估 FXStreet 公开 swagger 端点是否可匿名调用。
- BSP(菲)与 BOT(泰)是否有机读 REST/SDMX API 未深挖:只确认统计门户存在;BOT 实际有需注册的 BOT API portal(apiportal.bot.or.th)之说未经本次搜索证实,记为待查角度。
- 新闻/事件源(GDELT、央行 RSS、路透免费层)本轮未覆盖——"前一天事件"的叙事素材除数据日历外还需新闻流,建议补一轮 "GDELT API / central bank RSS feeds" 搜索。
- 知乎中文结果多为营销性 API 大全(iTick 等),未提供可核验的额度原文,未采信。
- DBnomics 对 BSP/BOT 是否直接收录(即 PH/TH 央行序列能否经 DBnomics 取到)未逐一验证,可用其 providers 端点实测。
