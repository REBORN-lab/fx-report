# Task: Adversarial / Devil's Advocate (SCAN)

AS_OF: 2026-08-10. 主题属 fast-moving(数据 API / LLM 工具),aging 从严降级。

## Sources
[s1] BizTech Magazine — LLM Hallucinations: What Are the Implications for Financial Institutions? | https://biztechmagazine.com/article/2025/08/llm-hallucinations-what-are-implications-financial-institutions | Type: journalism | Date: 2025-08-28 | Freshness: aging | Path: ddg
[s2] Man Group — How to Stop LLMs Hallucinating | https://www.man.com/insights/llms-hallucinating | Type: secondary | Date: 2025-10-03 | Freshness: aging | Path: ddg
[s3] Verdence — 2026 Q2 White Paper: Hey AI, Give Me Investment Advice | https://verdence.com/insight/ai-investment-advice-risks-what-llms-cant-do/ | Type: secondary | Date: 2026-06-04 | Freshness: fresh | Path: ddg
[s4] Master of Code — Stop LLM Hallucinations: Reduce Errors by 60–80% | https://masterofcode.com/blog/hallucinations-in-llms-what-you-need-to-know-before-integration | Type: secondary | Date: 2026-05-12 | Freshness: fresh | Path: ddg
[s5] AllRatesToday — 10 Best Free Currency Exchange APIs in 2026 | https://allratestoday.com/blog/best-free-currency-exchange-api-2026/ | Type: secondary | Date: 2026-06-21 | Freshness: fresh | Path: ddg
[s6] AlphaLog Blog — Alpha Vantage API: The Complete 2026 Guide | https://alphalog.ai/blog/alphavantage-api-complete-guide | Type: secondary | Date: 2025-12-01 | Freshness: fresh | Path: ddg
[s7] ExchangeRate-API — Open Access, No Key Required (docs) | https://www.exchangerate-api.com/docs/free | Type: official | Date: n.d. | Freshness: fresh (在线文档,现行) | Path: ddg
[s8] Lamj (Medium) — A Practical Guide to Forex API Integration | https://medium.com/@lamj45198/a-practical-guide-to-forex-api-integration-fetch-real-time-historical-exchange-rates-with-full-a6278ac1e300 | Type: community | Date: 2026-03-10 | Freshness: fresh | Path: ddg
[s9] Moosa (Applied Economics) — Why is it so difficult to outperform the random walk in exchange rate forecasting? | https://www.tandfonline.com/doi/full/10.1080/00036846.2012.709605 | Type: academic | Date: 2012 | Freshness: stale(学术结论仍被后续文献印证) | Path: ddg
[s10] Mendonça et al. (Journal of Forecasting, Wiley) — Fundamentals Models Versus Random Walk: Evidence From an Emerging Economy | https://onlinelibrary.wiley.com/doi/full/10.1002/for.3279 | Type: academic | Date: 2025-04-07 | Freshness: aging | Path: ddg
[s11] The Financial Hacker — Bye Yahoo, and thanks for all the fish | https://financial-hacker.com/bye-yahoo-and-thank-you-for-the-fish/ | Type: community | Date: 2017 | Freshness: stale(作历史案例引用) | Path: ddg
[s12] IPFLY Blog — Google Finance API: What Happened (2026 alternatives) | https://www.ipfly.net/blog/google-finance-api-alternatives-2026/ | Type: secondary | Date: 2026 | Freshness: fresh | Path: ddg
[s13] Stack Overflow — Data scraping from forexfactory.com | https://stackoverflow.com/questions/67068287/data-scraping-from-forexfactory-com | Type: community | Date: 2021-04 | Freshness: stale | Path: ddg
[s14] PyPI — market-calendar-tool | https://pypi.org/project/market-calendar-tool/ | Type: community | Date: n.d. | Freshness: fresh(现行包页面) | Path: ddg
[s15] Apify — ForexFactory Economic Calendar Scraper API | https://apify.com/scrapemint/forexfactory-economic-calendar | Type: community | Date: n.d. | Freshness: fresh(现行商品页) | Path: ddg
[s16] santiagobasulto (HN comment, on MIT Sloan "AI financial advice is surprisingly good") | https://news.ycombinator.com/item?id=49139484 | Type: community | Date: 2026-08-01 | Freshness: fresh | Path: hn
[s17] 1d22a (HN comment) — Gemini FX 换算方向搞反的实例 | https://news.ycombinator.com/item?id=46116643 | Type: community | Date: 2025-12-02 | Freshness: aging | Path: hn
[s18] sunnynagra (HN Show) — Watch 3 AIs compete in real-time stock trading | https://news.ycombinator.com/item?id=42559744 | Type: community | Date: 2024-12-31 | Freshness: stale | Path: hn
[s19] HakiReview — The Narrative Fallacy: Why We Explain Market Movements That Were Actually Random | https://hakireview.com/the-narrative-fallacy-why-we-explain-market-movements-that-were-actually-random/ | Type: secondary | Date: n.d. | Freshness: fresh(概念性内容不受时效影响,按 aging 保守处理) | Path: ddg
[s20] ForageAI — Is Web Scraping Legal? A Compliance Guide (2026) | https://forage.ai/blog/legal-and-ethical-issues-in-web-scraping-what-you-need-to-know/ | Type: secondary | Date: 2026-06 | Freshness: fresh | Path: ddg

## Findings
1. LLM 幻觉在金融场景直接构成合规风险:"If an AI hallucination produces inaccurate disclosures, guidance or advice, it could result in noncompliance and trigger penalties" [s1] [新]
2. 2026 年买方白皮书指出 LLM 投资建议的核心缺陷是迎合性——"confirmation bias dressed up as investment advice, an answer that feels validated when the user has talked the model into it",外加幻觉 [s3] [新]
3. 幻觉率在下降但非零:"The average rate of hallucinations across major models fell from nearly 38% in 2021 to about 8.2% in 2026, with the best systems now reaching rates as low as 0.7%" [s4]——日报每天生成,即使 1% 错误率也意味着每季度会出几次事实错误 [新]
4. LLM 连最简单的 FX 数字都会搞错方向:HN 用户实测 Gemini 回答 "What's 1 USD in AUD" 时 "note the conversion in the wrong direction"(给出 $0.65 即 AUD→USD 方向)——生成叙事时的汇率数字必须来自 API 而非模型 [s17] [新]
5. 免费汇率 API 普遍存在硬伤:"a service that caps at 100 requests per month, requires a credit card for signup, or returns stale data cached from yesterday" [s5];Alpha Vantage 免费档 "Free users are capped at 100 data points per request",全量历史仅付费 [s6] [新]
6. 免费 API 有停服前科且可无预告:Yahoo Finance API 2017 年 "Without prior announcement, Yahoo has abandoned" 该服务 [s11];Google Finance API 2012 年关闭,"Unofficial libraries like yfinance (Python) exist but offer inconsistent reliability" [s12]——方案必须内置数据源降级/备份链 [与已知冲突]
7. 学术共识:短期汇率预测跑不赢随机游走是 "the rule rather than the exception"(Meese-Rogoff puzzle)[s9];2025 年新兴市场(巴西)研究仍以该 puzzle 为前提——"'atheoretical' models, especially the random walk...perform better than those that consider economic fundamentals" [s10]——用户想要的"五币种投资建议"若隐含方向性预测,学术上站不住,建议定位为"事件解读+风险提示"而非预测 [与已知冲突]
8. ForexFactory 等经济日历站有反爬:抓取者遇 "503 'Service Temporarily Unavailable'...you can see a Cloudflare check page" [s13];现成抓取包自身声明 "scraping data from websites must comply with the site's terms of service and legal requirements" [s14],商业化 scraper 也只敢说 "Respect ForexFactory's terms and rate limit sensibly" [s15]——日历数据合规抓取无人背书,ToS 风险自担 [新]
9. 叙事化日报的固有陷阱:narrative fallacy "combines powerfully with hindsight bias...to create a particularly dangerous retrospective illusion in financial markets"——"完整且明确的叙事逻辑链条"这一需求本身会系统性制造对随机波动的马后炮因果解释 [s19] [与已知冲突]
10. HN 社区对 AI 金融建议的祛魅:被认为"好"的 AI 理财建议其实是通用保守套话("'good' financial advice is extremely simple. A conservative approach gets you there 80% of the time")[s16];公开的 LLM 实盘交易项目定位更接近观赏性对比实验而非可靠信号 [s18] [新]

## Trade-offs
免费汇率数据源的"坑"对比(本任务视角=风险,非功能全面对比):

| 候选 | 免费额度限制 | 数据新鲜度风险 | 停服/条款风险 | 代价/放弃了什么 |
|---|---|---|---|---|
| Alpha Vantage 免费档 | "Free users are capped at 100 data points per request",全量历史 premium only [s6] | 来源未说明("returns stale data cached from yesterday" 是对该类免费 API 的泛指 [s5]) | 来源未说明 | 放弃长历史回溯;逼近限额后无法补数 [s6] |
| ExchangeRate-API open 端点 | "our open access free exchange rate API has to be rate limited"(因 DDoS 与失控循环)[s7] | 来源未说明 | 官方自述限流属防御性,策略可变 [s7] | 放弃 SLA;限流阈值不透明,管线可能随机失败 [s7] |
| yfinance(非官方 Yahoo) | 无官方额度概念(非官方)[s12] | "inconsistent reliability" [s12] | 前科:官方 API 2017 无预告停服 [s11] | 放弃一切官方保障;随时可能因 Yahoo 端变更整体断供 [s11][s12] |

若只能选一个:Alpha Vantage 免费档,因为它是三者中唯一有明文额度契约的(限制可预算,失败可预期);当日报只需"前一日收盘价、每天 1 次拉取"且币种对齐(USD/PHP/BRL/THB/EUR 单次批量可得)成立时,ExchangeRate-API open 端点的低频调用反而更省事。注意:三者对 PHP/THB/BRL 覆盖质量本轮来源均未说明,决断前需实测(见 Gaps)。

## Gaps
- `site:reddit.com free financial data API problems` 查询返回全是无关噪音(DDG 对 site: 过滤失效),未获得 Reddit 一手踩坑帖;若需社区证据,建议改走 HN Algolia 或直接 fetch r/algotrading 具体帖。
- 没有找到免费 API 对 PHP/THB/BRL 等非 G10 货币的数据质量/覆盖度的直接反面证据(如交叉盘拼接、离岸/在岸口径混淆)——这是用户需求的关键假设,本轮完全未被验证或证伪。
- 没有找到经济日历抓取被实际起诉/封号的判例级证据;Investing.com 与 ForexFactory 的 ToS 原文未读取,仅有二手转述与工具方免责声明。
- 没有专门针对"LLM 自动化日报流水账/马后炮"的直接文献,narrative fallacy 证据是通用行为金融内容,针对 LLM 生成日报的实证研究可能需要走 arXiv 搜索(本轮未做)。
- HN "financial data API" 搜索命中多为产品发布帖,反面证据密度低;更好的角度可能是搜 "yfinance broken" / "Alpha Vantage rate limit" 等具体故障关键词。
