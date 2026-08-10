# Task: GitHub 生态扫描 — 经济日历 / 汇率数据 / 宏观监控 / 市场报告生成

AS_OF: 2026-08-10。SCAN 任务。搜索词: "economic calendar"(455 hits) / "exchange rate"(30444 hits) / "macro dashboard"(2373 hits) / "market report"(10077 hits) / "economic data api"(605 hits),各取 stars 排序前 20-30。

## Sources
[s1] tradermonty — claude-trading-skills | https://github.com/tradermonty/claude-trading-skills | Type: community | Date: 2026-08-10 | Freshness: fresh | Path: github-search
[s2] fizahkhalid — forex_factory_calendar_news_scraper | https://github.com/fizahkhalid/forex_factory_calendar_news_scraper | Type: community | Date: 2026-08-07 | Freshness: fresh | Path: github-search
[s3] kjpou1 — forexfactory-mcp | https://github.com/kjpou1/forexfactory-mcp | Type: community | Date: 2026-07-28 | Freshness: fresh | Path: github-search
[s4] gavinHuang — trading_economics_calendar_mcp | https://github.com/gavinHuang/trading_economics_calendar_mcp | Type: community | Date: 2026-04-29 | Freshness: fresh | Path: github-search
[s5] fawazahmed0 — exchange-api | https://github.com/fawazahmed0/exchange-api | Type: community | Date: 2026-08-09 | Freshness: fresh | Path: github-search
[s6] fixerAPI — fixer | https://github.com/fixerAPI/fixer | Type: community | Date: 2026-08-02 | Freshness: fresh | Path: github-search
[s7] exchangeratesapi — exchangeratesapi | https://github.com/exchangeratesapi/exchangeratesapi | Type: community | Date: 2026-08-07 | Freshness: fresh | Path: github-search
[s8] MicroPyramid — forex-python | https://github.com/MicroPyramid/forex-python | Type: community | Date: 2026-07-30 | Freshness: fresh | Path: github-search
[s9] tradingeconomics — notebooks | https://github.com/tradingeconomics/notebooks | Type: official | Date: 2026-08-05 | Freshness: fresh | Path: github-search
[s10] SilentFleetKK — ai-market-pulse | https://github.com/SilentFleetKK/ai-market-pulse | Type: community | Date: 2026-07-29 | Freshness: fresh | Path: github-search
[s11] Benboerba620 — daily-watchlist | https://github.com/Benboerba620/daily-watchlist | Type: community | Date: 2026-04-29 | Freshness: fresh | Path: github-search
[s12] mortada — fredapi | https://github.com/mortada/fredapi | Type: community | Date: 2026-08-09 | Freshness: fresh | Path: github-search
[s13] SunFish98 — MacroDashboard | https://github.com/SunFish98/MacroDashboard | Type: community | Date: 2026-08-07 | Freshness: fresh | Path: github-search
[s14] aistairc — market-reporter | https://github.com/aistairc/market-reporter | Type: academic | Date: 2026-02-27 | Freshness: fresh | Path: github-search
[s15] schoulten — macroview (巴西宏观仪表盘) | https://github.com/schoulten/macroview | Type: community | Date: 2026-03-20 | Freshness: fresh | Path: github-search

注:s1/s5/s11 的维护信号数字来自 --gh-activity 直接调 GitHub API 的返回,标 [自测 2026-08-10]。Date 取仓库 updated 字段。

## Findings
1. 存在成熟的 Claude Code 交易技能包 claude-trading-skills(2602 stars,MIT,Python),自述覆盖 "market analysis, technical charting, economic calendars, screeners, and trading strategy development",与"用 skill 生成每日宏观分析报告"的目标形态直接同构,可作为 skill 结构参照 [s1] [新]
2. claude-trading-skills 维护信号 [自测 2026-08-10]: pushed_at 2026-08-10T04:19:14Z(0 天前),last_commit 2026-08-10,约 694 commits,主要作者 tradermonty(204 contributions)→ derived (non-authoritative): active (<3mo);无 releases [s1] [新]
3. fawazahmed0/exchange-api(2563 stars,CC0)自述 "Free Currency Exchange Rates API with 200+ Currencies & No Rate Limits",200+ 币种意味着大概率覆盖 PHP/THB/BRL(具体币种清单本次未核实,[unverified]),是免费日频汇率数据的头部候选 [s5] [新]
4. exchange-api 维护信号 [自测 2026-08-10]: pushed_at 2026-05-22T21:08:40Z(79 天前),last_commit 同日,107 commits 基本单人维护(fawazahmed0 106/107)→ derived (non-authoritative): active (<3mo,但已近 3 个月无 commit,单点维护风险) [s5] [新]
5. Benboerba620/daily-watchlist(57 stars)自述 "AI-powered stock watchlist and daily market report workflow for Claude Code. Track movers, earnings, macro data, and generate stru[ctured reports]",是与"每日汇集宏观数据生成结构化报告"最接近的 Claude Code 工作流样板 [s11] [新]
6. daily-watchlist 维护信号 [自测 2026-08-10]: pushed_at 2026-04-29T03:16:59Z(103 天前),最近 release v1.1.0 published_at 2026-04-24,单人 34 commits → derived (non-authoritative): maintained (<12mo),非活跃开发 [s11] [新]
7. 经济日历数据的开源获取几乎全部依赖爬虫(ForexFactory / investing.com / babypips / dailyfx),头部如 forex_factory_calendar_news_scraper(96 stars,selenium 爬 ForexFactory 并推送 Discord/Telegram);没有发现高星的官方开放日历 API 仓库——日历数据将是本方案的脆弱环节 [s2] [与已知冲突]
8. 已出现把经济日历包成 MCP server 给 LLM 用的仓库:forexfactory-mcp(12 stars,自述 "exposes ForexFactory economic calendar data as structured tools and resources for agentic workflows...JSON-first access for LLMs")和 trading_economics_calendar_mcp(8 stars,爬 tradingeconomics.com/calendar);星少但形态正是本需求的胶水层,其中 TradingEconomics 日历是少数按国家覆盖新兴市场(PH/TH/BR)的日历源 [s3][s4] [新]
9. TradingEconomics 官方 notebooks 仓库(134 stars)自述 "Trading Economics h[as...]" 提供全球宏观指标 API 的官方示例,但 TradingEconomics API 本身收费;fredapi(1648 stars,Apache-2.0)则是免费 FRED 数据的事实标准 Python 客户端,但 FRED 以美国指标为主,对 PHP/THB/BRL 本国数据覆盖弱 [s9][s12] [新]
10. 自动"时间序列→文字市场评论"已有学术级先例:aistairc/market-reporter(67 stars,产研机构 AIST)自述 "Automatic Generation of Brief Summaries of Time-Series Data",但为前 LLM 时代方法;而 ai-market-pulse(163 stars)自述 "Turn any watchlist into a daily AI market research report",证明 LLM 日报管线是当前活跃形态 [s14][s10] [新]

## Trade-offs
可比候选(按"可借鉴到 LLM 日报/周报生成管线"筛选):claude-trading-skills [s1]、daily-watchlist [s11]、ai-market-pulse [s10]、forexfactory-mcp [s3]。

| 决策轴 | claude-trading-skills [s1] | daily-watchlist [s11] | ai-market-pulse [s10] | forexfactory-mcp [s3] |
|---|---|---|---|---|
| 与本需求形态匹配 | Claude Code skill 集,含 economic calendars 与 market analysis [s1] | "daily market report workflow for Claude Code...macro data" 最贴合日报节奏 [s11] | "daily AI market research report",偏 watchlist/quant [s10] | 只做日历数据供给,不生成报告 [s3] |
| 非 G10 币种(PHP/THB/BRL)覆盖 | 来源未说明(描述只提 equity investors and traders)[s1] | 来源未说明(描述提 stock watchlist)[s11] | 来源未说明("any watchlist")[s10] | ForexFactory 日历以主要货币为主,来源未说明是否含 PHP/THB/BRL [s3] |
| 社区/维护信号 | 2602 stars,pushed 2026-08-10,694 commits [自测 2026-08-10] → active [s1] | 57 stars,pushed 2026-04-29(103 天)→ maintained [自测 2026-08-10] [s11] | 163 stars,updated 2026-07-29(仅搜索元数据,未跑 activity)[s10] | 12 stars,updated 2026-07-28(未跑 activity)[s3] |
| 代价/放弃了什么 | 面向美股交易者,FX/新兴市场货币需自行改造;体量大,抽取成本高 [s1] | 单人项目、3 个月无 commit,拿来即用风险高,只能当模板抄 [s11] | 偏量化 cockpit 而非叙事报告,"quant research cockpit" [s10] | 只解决五分之一问题(日历),且上游是爬 ForexFactory,随时可能被封 [s3] |

若只能选一个:claude-trading-skills,因为它维护最活跃、skill 组织方式与目标产物(Claude skill)同构,可直接借鉴其 economic calendar + 分析报告的 skill 写法;当你确认需要的是端到端可跑的最小日报流水线模板(而非 skill 写法参考)时改选 daily-watchlist。注意四者均未证明覆盖 PHP/THB/BRL——币种覆盖必须在数据源层(exchange-api [s5] / TradingEconomics 日历 [s4][s9])解决,不能指望报告层仓库自带。

## Gaps
- 未找到任何"多币种 FX 日报/周报生成"现成开源项目;现有报告生成类仓库全部以美股/加密为中心,PHP/THB/BRL 视角为空白,方案需自行组装
- "economic calendar" 搜索未见覆盖新兴市场且非爬虫的免费日历 API 仓库;TradingEconomics 官方 API 收费,免费层限制未核实
- exchange-api 的 200+ 币种具体清单、更新频率(日频 vs 更高)未核实,需 fetch 其 README 确认 PHP/THB/BRL 三币种在列
- ai-market-pulse 与 forexfactory-mcp 未跑 --gh-activity(限流预算留给 top3),其维护结论仅基于搜索元数据 updated 字段
- 可能更好的角度:直接搜 "central bank" / "BSP BOT BCB" 官方数据 SDK、"currency news LLM"、以及 awesome-list 类(本次仅撞见 awesome-japan-finance-data,提示存在按国别整理的 awesome 金融数据清单,值得后续按 PH/TH/BR 检索)
