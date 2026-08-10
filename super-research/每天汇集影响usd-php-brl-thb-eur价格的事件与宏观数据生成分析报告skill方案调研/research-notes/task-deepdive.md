# Task: 候选方案深读 (task-deepdive, DEEP)

AS_OF: 2026-08-10。主题属 fast-moving(数据 API / LLM 工具),aging 从严降级。
入选候选 8 个(数据源 4 + 开源项目 4):Frankfurter、fawazahmed0/exchange-api、DBnomics、GDELT DOC 2.0(数据侧);gpt-researcher、TradingAgents、DeepEar、claude-trading-skills(管线借鉴侧)。
GitHub API 用量:--gh-activity 4 次 + --github 1 次 = 5 次,未超 8 次预算,无 403/429。

## Sources
[s1] Frankfurter (Line of Flight) — Frankfurter | Free exchange rates API | https://frankfurter.dev/ | Type: official | Date: 2026 (现行 v2 文档) | Freshness: fresh | Path: ddg
[s2] lineofflight — frankfurter (GitHub 仓库, README + activity) | https://github.com/lineofflight/frankfurter | Type: community | Date: 2026-07-23 (pushed_at) | Freshness: fresh | Path: github-repo
[s3] fawazahmed0 — exchange-api (GitHub 仓库 README + jsDelivr CDN 端点实测) | https://github.com/fawazahmed0/exchange-api | Type: community | Date: 2026-08-09 (最新数据日期) | Freshness: fresh | Path: github-repo
[s4] DBnomics — Web API v22 (providers / search 端点实测) | https://api.db.nomics.world/v22/providers | Type: official | Date: 2026-08-10 (实时返回) | Freshness: fresh | Path: direct-fetch
[s5] GDELT Project — DOC 2.0 API (api.gdeltproject.org 实测) | https://api.gdeltproject.org/api/v2/doc/doc | Type: official | Date: 2026-08-10 (实时返回) | Freshness: fresh | Path: direct-fetch
[s6] assafelovic — gpt-researcher (gh-activity 实测) | https://github.com/assafelovic/gpt-researcher | Type: community | Date: 2026-07-18 (pushed_at / v3.6.0) | Freshness: fresh | Path: github-repo
[s7] TauricResearch — TradingAgents (gh-activity 实测) | https://github.com/TauricResearch/TradingAgents | Type: community | Date: 2026-07-18 (pushed_at) | Freshness: fresh | Path: github-repo
[s8] HKUSTDial — DeepEar (gh-activity 实测) | https://github.com/HKUSTDial/DeepEar | Type: community | Date: 2026-04-16 (pushed_at) | Freshness: fresh (抓取日) | Path: github-repo
[s9] tradermonty — claude-trading-skills (仓库主页 README 补读) | https://github.com/tradermonty/claude-trading-skills | Type: community | Date: 2026-08-10 (pushed_at, 承接 task-gh-scan 实测) | Freshness: fresh | Path: github-repo
[s10] Finnhub — /calendar/economic 端点无 key 实测 | https://finnhub.io/api/v1/calendar/economic | Type: official | Date: 2026-08-10 (实时返回) | Freshness: fresh | Path: direct-fetch

## Findings
1. Frankfurter 仓库为 MIT 许可、Ruby 实现,last commit 2026-07-23(17 天前)、最近 release v2.3.5 2026-06-25、约 1016 commits、多贡献者+bot 自动化 → derived (non-authoritative): active;实测 `GET /v2/rates?base=USD&quotes=PHP,THB,BRL,EUR` 当日(date=2026-08-10)四币齐返 [自测 2026-08-10] [s2][s1] [新]
2. Frankfurter 自托管 README 逐字列出 "`BOT_API_KEY` — Bank of Thailand. Register at [portal.api.bot.or.th]",证实泰国央行确有官方 API 门户(前序笔记标为待查),且 Frankfurter 自身就是"多央行数据聚合器"——自托管时可挂 BOT/FRED 等官方 key [s2] [新]
3. exchange-api 实测覆盖 338 个币种,php/thb/brl/eur/usd 全在列("Philippine Peso"/"Thai Baht"/"Brazilian Real"),README 自述 "200+ Currencies... No Rate limits... Daily Updated",CC0-1.0 许可(引用零负担)[自测 2026-08-10] [s3] [新]
4. exchange-api 的 `@latest` 端点返回 date=2026-08-09(滞后一天),但带版本化历史端点(`currency-api@2026.8.9` 实测可用)与 Cloudflare 双 CDN 兜底("Please include Fallback mechanism in your code");代码仓 last commit 2026-05-22(79 天,单人维护)而数据仍在日更——代码停更 ≠ 数据停更 [自测 2026-08-10] [s3] [新]
5. DBnomics v22 实测共 93 家提供方,巴西央行 BCB 在列,但无 BSP(菲)与 BOT(泰)直连提供方——"DBnomics 单点覆盖五经济体"仅在经 IMF 间接数据集意义上成立 [自测 2026-08-10] [s4] [与已知冲突]
6. DBnomics 搜索实测:"Philippines consumer price index" 命中 12 个数据集(IMF CPI / IMF IFS / ILO CPI 系列),"Thailand policy rate" 命中 2 个(IMF IFS / IMF MFS)——菲/泰宏观指标可取,但均为 IMF/ILO 口径的月度/滞后数据,非央行一手日频 [自测 2026-08-10] [s4] [新]
7. GDELT DOC 2.0 API 无 key 实测可用:query="Philippine peso"&timespan=48h 直接返回 2026-08-09 的菲律宾本地报道《Philippine peso weakens on economic slowdown concerns》,"昨日事件→币种"链路直接打通;连续第二次请求即触发限速提示 "Please limit requests to one every 5 seconds"——五币种日常查询必须串行加 5 秒以上间隔 [自测 2026-08-10] [s5] [新]
8. Finnhub 经济日历端点无 key 实测返回 HTTP 401 `{"error":"Please use an API key."}`,至少必须注册;免费档是否开放该端点仍未定(需拿 key 再测),免费经济日历缺口依旧无解 [自测 2026-08-10] [s10] [印证已知]
9. TradingAgents(96,900★,v0.3.1 2026-07-05)与 gpt-researcher(28,908★,v3.6.0 2026-07-18)均 last push 22 天前、release 节奏月级 → derived (non-authoritative): 两者均 active,作为架构蓝本无维护风险 [s7][s6] [新]
10. DeepEar 实测 last commit 2026-04-16(115 天前)、69 commits 全部来自单一贡献者 RKiding、零 release → derived (non-authoritative): maintained 但非 active,单点维护;前序笔记按 updated 字段标注的 "2026-08-08" 是 GitHub updated(受 star 等事件影响)造成的活跃度高估 [s8] [与已知冲突]

## Trade-offs
8 个候选同轴对比(数据源组 + 管线借鉴组;维护判定均为按 AS_OF 2026-08-10 由原始日期推导,derived (non-authoritative)):

| 候选 | 五币种/日频适配度 | 维护状态 | 接入成本 | 代价/放弃了什么 |
|---|---|---|---|---|
| Frankfurter [s1][s2] | 四对汇率一次调用全返,date=当日 [自测 2026-08-10];"tracks daily exchange rates from 84 central banks, covering 201 currencies back to 1948" [s1] | active(commit 17 天前,v2.3.5 2026-06-25)[s2] | 最低:无 key、无配额("There are no quotas")[s1],MIT 可自托管 [s2] | 只有日频参考价,无盘中价与买卖价差;混合来源末位小数可变 [s1] |
| exchange-api [s3] | 338 币种含 PHP/THB/BRL [自测 2026-08-10];"Daily Updated" [s3];latest 滞后一天(date=2026-08-09)[自测 2026-08-10] | 数据日更但代码 79 天无 commit、单人维护(fawazahmed0 106/107 commits,承接 task-gh-scan 实测)[s3] | 最低:纯静态 CDN、无 key、"No Rate limits" [s3],CC0 | 无官方 SLA;单人项目断更风险;汇率来源口径 README 未说明(来源未说明) |
| DBnomics [s4] | BRL 侧有 BCB 直连;PH/TH 仅 IMF/ILO 间接数据集(CPI 12 个、policy rate 2 个命中)[自测 2026-08-10],月度为主非日频 | 平台在线、providers 端点实时可用 [自测 2026-08-10];平台自身维护节奏来源未说明 | 低:REST 无 key 实测可调 [自测 2026-08-10] | 放弃菲/泰央行一手数据(无 BSP/BOT 提供方 [自测 2026-08-10]);无事件日历概念 |
| GDELT DOC 2.0 [s5] | 事件侧五币种国别新闻全覆盖(实测命中菲律宾本地英文报道)[自测 2026-08-10];15 分钟粒度满足日报节奏(承接 task-events) | API 在线且有活跃限速治理 [自测 2026-08-10];GDELT 官方持续运营 | 低:无 key;但强制串行(实测限速 "one every 5 seconds")[自测 2026-08-10] | 只有文章检索+tone,无事件编码/实际vs预期值;3 个月滚动窗口,无长回溯 |
| gpt-researcher [s6] | 不适用(无金融数据源,承接 task-oss);形态最贴 skill(`npx skills add`) | active(push 22 天前,v3.6.0 2026-07-18,3077 commits,多贡献者)[s6] | 中:pip 两个 async 调用即出报告(承接 task-oss);Apache-2.0 | 无金融叙事结构与投资建议模板;长文倾向与"简明扼要"相反(承接 task-oss) |
| TradingAgents [s7] | 不适用(单 ticker 股票导向,FX 对未证实,承接 task-oss);借鉴其"分析师→辩论→决策"链条 | active(push 22 天前,v0.3.1 2026-07-05)[s7];96,900★ | 高:LangGraph 9 类 agent 全栈,只宜抄架构不宜拿来跑;Apache-2.0 | 改造面大;257 commits 集中于单一核心作者(Yijia-Xiao 201/257)[s7] |
| DeepEar [s8] | 不适用(中文 A 股舆情导向,承接 task-oss);借鉴 ISQ 逻辑链模板与 `--update-from` 逐日追踪 | maintained 非 active(commit 115 天前,单贡献者 69/69,零 release)[s8] | 中:MIT,自带 skills/deepear 目录(承接 task-oss) | 单点维护+社区小(270★),抄概念可以,依赖其代码风险高 [s8] |
| claude-trading-skills [s9] | 不适用(美股导向,"for equity investors and traders" [s9]);借鉴 skill 组织与日/周/月工作流分层 | active(pushed 2026-08-10 当天,694 commits,承接 task-gh-scan [自测 2026-08-10])[s9] | 低:MIT,纯 skill 文本结构可直接仿写;含 "No API Key Starter Path" 无付费依赖路径 [s9] | 无 FX/宏观叙事内容;workflows 需整体重写为五币种宏观版 |

决断:若只能选一个:数据侧选 Frankfurter,因为它是唯一"当日 date、五币种一次调用、无 key 无配额、MIT 可自托管、维护 active"全满足的汇率源,且其自托管形态还能顺带挂 BOT/FRED 官方 key 变成多央行聚合器;当 {需要 CC0 零署名负担的静态历史文件、或要把汇率取数降级为纯 CDN GET 以彻底消除 API 依赖} 成立时改选 exchange-api(接受 latest 滞后一天与单人维护风险)。管线借鉴侧选 claude-trading-skills,因为它是唯一维护 active、形态与目标产物(Claude skill + 日/周分层工作流)完全同构的参照,叙事链条内容缺口用 TradingAgents 的"分析→辩论→结论"结构与 DeepEar 的逻辑传导链概念补(均只抄设计不引代码)。事件侧 GDELT DOC 2.0 与宏观侧 DBnomics+BCB 无竞争者,直接入选;经济日历轴仍无法决断——Finnhub 实测确认需 key,免费档开放性待注册后验证,缺这一手证据。

## Deep Read Notes

### lineofflight/frankfurter (GitHub 仓库) [s2]
- gh-activity 原始数据 [自测 2026-08-10]:pushed_at 2026-07-23T12:33:31Z(17 天前);last_commit 2026-07-23;releases:v2.3.5 (2026-06-25)、v2.3.4 (2026-06-25)、v2.3.3 (2026-06-22)、v2.3.2 (2026-06-13)、v2.3.1 (2026-06-11)——6 月内 5 个 release,节奏密集;commit_count_estimate 1016;top contributors: hakanensari 451、lineoffligbot 427(bot 自动数据更新)、dependabot 71。→ derived (non-authoritative): active。
- --github 元数据:license MIT,language Ruby,stars 1767,created 2018-03-08,homepage frankfurter.dev。
- README 关键原文:"Frankfurter is an open-source currency data API that tracks daily exchange rates from institutional sources.";自托管一行命令 "`docker run -d --init -p 8080:8080 lineofflight/frankfurter`";"Without a mounted volume, the database is ephemeral and some endpoints may return empty data until their initial backfill completes."
- 对本方案最重要的发现:可选数据提供方 key 列表逐字包括 "`BOT_API_KEY` — Bank of Thailand. Register at [portal.api.bot.or.th]" 与 "`FRED_API_KEY` — Federal Reserve"——即 Frankfurter 的上游本来就含泰国央行与美联储,"All are free and optional"。这同时解决了前序 Gaps 里"BOT API portal 之说未证实"的问题。
- 汇率实测 [自测 2026-08-10]:`curl "https://api.frankfurter.dev/v2/rates?base=USD&quotes=PHP,THB,BRL,EUR"` → `[{"date":"2026-08-10","base":"USD","quote":"BRL","rate":5.1052},...EUR 0.866, PHP 60.843, THB 33.056]`;`/v2/currencies` 元数据含各币起讫日期(如 AED start_date 1996-04-11、end_date 2026-08-10),可程序化判断历史深度。

### fawazahmed0/exchange-api (README + CDN 实测) [s3]
- README 原文四特性:"Free & Blazing Fast response / No Rate limits / 200+ Currencies, Including Common Cryptocurrencies & Metals / Daily Updated";许可 CC0-1.0。
- URL 结构:"`https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@{date}/{apiVersion}/{endpoint}`",date 取 `latest` 或 `YYYY-MM-DD`;另有 Cloudflare 兜底 "`https://{date}.currency-api.pages.dev/...`",README 警告 "Please include Fallback mechanism in your code"。
- 币种实测 [自测 2026-08-10]:`/v1/currencies.json` 共 338 个键,php→"Philippine Peso"、thb→"Thai Baht"、brl→"Brazilian Real"、eur→"Euro" 全在。
- 汇率实测 [自测 2026-08-10]:`/v1/currencies/usd.json` 返回 date=2026-08-09(latest 滞后一天),php 60.83432001 / thb 33.04805197 / brl 5.08518303 / eur 0.86502508;版本化历史端点 `currency-api@2026.8.9/v1/currencies/usd.min.json` 实测可用(npm 版本号即日期)。
- 维护画像(承接 task-gh-scan [自测 2026-08-10]):pushed_at 2026-05-22(79 天前),107 commits 中 fawazahmed0 占 106 → 单人维护;但数据由 GitHub Actions 自动发 npm 包,2026-08-09 数据仍在,证明发布管线独立于人工 commit 存活。

### DBnomics Web API v22 (providers / search 实测) [s4]
- providers 实测 [自测 2026-08-10]:`GET /v22/providers` 返回 total providers: 93;按 Thailand/Philipp/Brazil/BCB/BOT/BSP 正则过滤仅命中 1 条:"BCB | Banco Central do Brasil"。BSP、BOT 均不在提供方列表。
- 菲律宾指标实测 [自测 2026-08-10]:`/v22/search?q=Philippines+consumer+price+index` → num_found: 12,前五为 IMF CPI("Consumer Price Index (CPI)")、IMF IFS("International Financial Statistics (IFS)")、ILO CPI 三个系列。
- 泰国指标实测 [自测 2026-08-10]:`/v22/search?q=Thailand+policy+rate` → num_found: 2,IMF IFS 与 IMF MFS("Monetary and Financial Statistics")。
- 结论:DBnomics 作为五经济体宏观兜底可行(IMF 口径),BRL 侧还有 BCB 直连;但菲/泰的央行一手序列(BSP/BOT)必须绕开 DBnomics 另接(BOT 走 portal.api.bot.or.th [s2],BSP 待查)。API 全程无 key 实测可调。

### GDELT DOC 2.0 API (无 key 实测) [s5]
- 实测命令 [自测 2026-08-10]:`GET https://api.gdeltproject.org/api/v2/doc/doc?query="Philippine peso"&mode=artlist&maxrecords=4&timespan=48h&format=json`。
- 返回逐字节选:`{"url": "http://www.philippinetimes.com/news/279226463/philippine-peso-weakens-on-economic-slowdown-concerns", "title": "Philippine peso weakens on economic slowdown concerns", "seendate": "20260809T234500Z", "sourcecountry": "Philippines"}`——48 小时窗口内直接命中"昨日比索走弱"的本地报道,连同一条马来西亚林吉特周展望(引擎会带回相邻币种噪声,需 query 加排除词)。
- 限速实测 [自测 2026-08-10]:紧接着的第二次请求(Thai baht)未返回 JSON,而是限速文本:"Please limit requests to one every 5 seconds or contact ... for larger queries. All high-traffic users should switch to our ngrams dataset"。→ 工程含义:五币种每日 5 组查询完全可行,但必须串行 sleep≥5s,且失败重试要识别"200 但正文是限速提示"的软失败形态(HTTP 层不报错)。
- Finnhub 对照实测 [自测 2026-08-10][s10]:`GET https://finnhub.io/api/v1/calendar/economic` → HTTP 401,`{"error":"Please use an API key."}`。

### tradermonty/claude-trading-skills (README 补读) [s9]
- 定位原文:"Claude Trading Skills is a Claude Skills-based trading workflow toolkit for time-constrained individual investors.";MIT;免责声明明确 "not financial advice"。
- 与本需求同构的三个结构(均为可直接仿写的形态而非内容):(a) 日/周/月分层工作流表——"15-minute daily market check → market-regime-daily"、"Weekly long-term portfolio review → core-portfolio-weekly"、"Review monthly performance and adjust rules → monthly-performance-review",每条指向 workflows/ 下 "machine-readable manifest that names the exact skills, decision gates, and artifacts in order";(b) 仓库目录含 skills/、skillsets/、workflows/、skills-index.yaml、launchd/(macOS 定时调度目录——前序笔记"全生态无内置调度"的说法在此有一个反例级别的局部例外);(c) "No API Key Starter Path":五个无 key skill(public CSV + 本地 YAML journaling)构成零付费依赖路径,"does not require a paid market-data API subscription"。
- 维护(承接 task-gh-scan [自测 2026-08-10]):pushed_at 2026-08-10T04:19:14Z(当天),694 commits → derived (non-authoritative): active。页面显示 2.6k star / 603 fork / 21 issues。
- 局限:内容全部面向美股("equity investors and traders"),FX/宏观叙事为零;可借鉴其 manifest+decision gate 组织法,内容层需全新编写。

### gpt-researcher / TradingAgents / DeepEar (gh-activity 维护画像) [s6][s7][s8]
- gpt-researcher [自测 2026-08-10]:pushed_at 2026-07-18(22 天前),v3.6.0 2026-07-18(近 5 个 release 跨 2026-03~07,月更节奏),3077 commits,贡献者分布健康(assafelovic 1513、ElishaKay 566、另有 3 人 40+)→ derived (non-authoritative): active。stars 28,908。
- TradingAgents [自测 2026-08-10]:pushed_at 2026-07-18(22 天前),v0.3.1 2026-07-05(近 5 个 release 跨 2026-03~07),257 commits 但 Yijia-Xiao 占 201——星数 96,900 与贡献者集中度形成反差,核心开发实质单人 → derived (non-authoritative): active(带单点作者风险)。
- DeepEar [自测 2026-08-10]:pushed_at 2026-04-16(115 天前),69 commits 全部来自 RKiding(69/69),releases 为空,open issues 4 → derived (non-authoritative): maintained(3-12 个月窗口),非 active。前序 oss 笔记的 Date "2026-08-08 (updated)" 来自 GitHub updated 字段(star/fork 事件也会刷新),不能作为开发活跃证据——以 pushed_at/last_commit 为准。

## Gaps
- Finnhub 免费档是否开放 economic-calendar 端点仍未定:本轮只确认了无 key 必 401,注册免费 key 后的实测(以及其对 PH/TH/BR 事件的国别覆盖)是遗留的最后一块日历拼图。
- BSP(菲律宾央行)机读 API 仍无一手证据:BOT 已经由 Frankfurter README 证实有官方门户,BSP 侧本轮未再消耗预算;下一步可直接 fetch bsp.gov.ph 的 API/SDMX 页面验证。
- GDELT 限速实测揭示了"HTTP 200 + 限速文本"的软失败形态,但其官方配额上限没有文档化数字(前序 [unverified] 维持);gdeltdoc Python 客户端的当前可用性也未验证。
- DBnomics 的 IMF CPI/IFS 序列对菲/泰的具体更新滞后(月度数据几号可得)未实测到序列级;若日报要引"最新 CPI",需再查单序列的 last update 字段。
- TradingAgents/FinRobot 等对 FX ticker(如 USDPHP=X)的实际支持度仍停留在 README 证据层,未跑代码验证;本轮判断"只抄架构不引代码"部分基于此不确定性。
- exchange-api 的汇率上游来源(哪家行情商)README 未披露,数据质量口径(离岸/在岸、参考价类型)无从核验——若入选生产管线,建议与 Frankfurter 双源交叉校验偏差。
