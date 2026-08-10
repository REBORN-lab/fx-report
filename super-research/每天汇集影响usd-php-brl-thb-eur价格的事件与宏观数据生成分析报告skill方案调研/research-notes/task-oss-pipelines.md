# Task: 金融 LLM 报告管线开源项目调研 (task-oss-pipelines)

AS_OF: 2026-08-10

## Sources
[s1] TauricResearch — TradingAgents: Multi-Agents LLM Financial Trading Framework | https://github.com/TauricResearch/TradingAgents | Type: community | Date: 2026-08-10 (updated; v0.3.1 2026-07) | Freshness: fresh | Path: github-search
[s2] AI4Finance-Foundation — FinRobot: An Open-Source AI Agent Platform for Financial Applications using LLMs | https://github.com/AI4Finance-Foundation/FinRobot | Type: community | Date: 2026-08-10 (updated) | Freshness: fresh | Path: github-search
[s3] assafelovic — gpt-researcher: An autonomous agent that conducts deep research on any data using any LLM providers | https://github.com/assafelovic/gpt-researcher | Type: community | Date: 2026-07-18 (PyPI 更新时间线) | Freshness: fresh | Path: ddg
[s4] HKUSTDial — DeepEar ｜ 顺风耳: An open-source framework for Deep Research and Financial Signal Tracking | https://github.com/HKUSTDial/DeepEar | Type: community | Date: 2026-08-08 (updated) | Freshness: fresh | Path: github-search
[s5] RUC-NLPIR — FinSight: Towards Real-World Financial Deep Research (ACL 2026 Main) | https://github.com/RUC-NLPIR/FinSight | Type: academic | Date: 2026-08-04 (updated) | Freshness: fresh | Path: github-search
[s6] AI4Finance-Foundation — FinGPT: Open-Source Financial Large Language Models | https://github.com/AI4Finance-Foundation/FinGPT | Type: community | Date: 2023-06 (论文 arXiv 2306.06031; 项目持续维护) | Freshness: aging (论文侧) | Path: ddg
[s7] DemonDamon — FinnewsHunter: Multi-agent financial intelligence platform | https://github.com/DemonDamon/FinnewsHunter | Type: community | Date: 2026-08-09 (updated) | Freshness: fresh | Path: github-search
[s8] gauss314 — skills: Financial market data consumption skills for claude code and AI agents | https://github.com/gauss314/skills | Type: community | Date: 2026-08-10 (updated) | Freshness: fresh | Path: github-search
[s9] ahmedhawas123 — Show HN: Upticker – financial analysis workflow tool orchestrated by LLMs | https://news.ycombinator.com/item?id=44491686 | Type: community | Date: 2025-07-07 | Freshness: aging | Path: hn

## Findings
1. TradingAgents(96.9k stars, Apache-2.0)是最成熟的多智能体金融分析管线,叙事链条为固定角色流水线:Fundamentals/Sentiment/News/Technical 四类分析师 → 多空研究员结构化辩论 → Trader 汇总成报告 → 风控团队 → Portfolio Manager 终审,直接可借鉴为"数据→分析→叙事→结论"的链条骨架 [s1] [新]
2. TradingAgents v0.3.0 起内置 FRED 数据源("FRED and Polymarket data vendors"),且支持"any market Yahoo Finance covers",宏观数据接入模式可借鉴;但 README 只列股票/加密 ticker,未提及外汇对(如 USDPHP=X),FX 覆盖属 [unverified] [s1] [新]
3. TradingAgents 的"decision log"持续记忆机制(每次运行把决策追加到 markdown,下次运行取实际回报生成一段反思并注入 prompt)是实现"周报回顾日报结论"连续性的现成参考实现 [s1] [新]
4. FinRobot(7.8k stars)核心设计原则是"确定性计算与 LLM 叙事严格分离":"Numbers are code-calculated. Narratives are LLM-assisted. Every output is provenance-tracked",直接回应用户"避免流水账、只要关键信息"的可信度需求 [s2] [新]
5. FinRobot 管线为 Lead Agent 编排 Data→Analysis→Modeling→Synthesis→Report 五个角色 agent,再加 Bull/Bear/Judge 三个辩论 agent,数据层含 7 个带 failover 的 provider,其中明确包括 FX("including FMP, Finnhub, yfinance, SEC EDGAR, Adanos, NewsAggregator, and FX") [s2] [新]
6. gpt-researcher(28.9k stars)是 planner/execution 双层架构的通用报告生成器:planner 生成研究问题→并行 crawler 逐题检索→逐源摘要与出处追踪→聚合成终稿,可导出 PDF/Word,且可作为 Claude Skill 安装(`npx skills add assafelovic/gpt-researcher`)——与用户的"skill 方案"形态最贴近 [s3] [新]
7. DeepEar(顺风耳,270 stars,港科大)是唯一把"叙事逻辑链条"作为一等公民的项目:定位为"transforms Public Opinion into actionable Investment Logic Chains",FinAgent 用 ISQ(Investment Signal Quality)评分模板"formulates transmission chains",输出含 Draw.io 交互逻辑传导图,并有 Logic Evolution Tracking 跨运行追踪论点演变(`--update-from` 参数) [s4] [新]
8. DeepEar 的报告生成用 Map-Reduce(分节起草→Hybrid RAG 统一编辑→终稿 .md/.html),接 15+ 中文/财经新闻源(微博、财联社、华尔街见闻等),但数据源以中国 A 股/中文舆情为主,对 PHP/THB/BRL 货币无现成覆盖 [s4] [与已知冲突]
9. 调研范围内没有任何一个头部开源项目内置"每日定时调度"环节——TradingAgents/FinRobot/gpt-researcher/DeepEar 均为按需触发(CLI/API/skill 调用),日更节奏需自行外加 cron/GitHub Actions;"完整管线含调度"的假设在现有开源生态中不成立 [s1][s2][s3][s4] [与已知冲突]
10. 生态里已出现"金融数据获取做成 Claude Code skills"的先例:gauss314/skills(175 stars)提供 FRED、TradingView、SEC、finviz 等数据消费 skill;DeepEar 也提供 skills/deepear 目录可拷入 `~/.claude/skills/`,证明用户设想的 skill 形态有多个可参考实现 [s8][s4] [新]

## Trade-offs
可比候选 4 个(TradingAgents / FinRobot / gpt-researcher / DeepEar):

| 决策轴 | TradingAgents [s1] | FinRobot [s2] | gpt-researcher [s3] | DeepEar [s4] |
|---|---|---|---|---|
| 叙事逻辑链条组织 | 固定角色流水线+多空结构化辩论("bullish and bearish researchers…Through structured debates")[s1] | 五角色管线+Bull/Bear/Judge 辩论,数字全部代码算、LLM 只写叙事 [s2] | planner 生成问题→并行执行→聚合;无金融专属叙事结构("planner generates research questions, while the execution agents gather relevant information")[s3] | 显式"Investment Logic Chains"+ISQ 评分模板+传导链 Draw.io 图+跨期 Logic Evolution Tracking [s4] |
| 宏观/FX 数据接入 | FRED 内置;Yahoo Finance 全市场;FX 对未明说(来源未说明,仅列 "US…Crypto: BTC-USD")[s1] | 7 provider 含 "FX" 与 NewsAggregator,带 failover [s2] | 无金融数据源,靠 web 检索+MCP 接任意 API("RETRIEVER=tavily,mcp")[s3] | 15+ 新闻源但偏中文舆情/A 股;FX 宏观数据来源未说明 [s4] |
| 日更/定时适配 | 无内置调度;有 checkpoint resume 与 decision log 利于日更连续性 [s1] | 无内置调度;CLI 两步命令易于 cron 化 [s2] | 无内置调度;pip 包 3 行代码即一次研究,最易 cron 化 [s3] | 无内置调度;有 `--update-from` 增量更新既有 run,天然贴合"逐日追踪" [s4] |
| 报告输出 | 决策文本+decision log(markdown)[s1] | "13-chapter research output, IC memos, evidence links, and numeric provenance";HTML/PDF 15+ 图表 [s2] | ">2,000 words" 报告,PDF/Word 导出 [s3] | .md/.html 报告+交互逻辑图 [s4] |
| 代价/放弃了什么 | 面向单 ticker 交易决策而非多币种宏观日报,改造面大;96.9k stars 但重(9 类 agent、LangGraph)[s1] | 放弃轻量:~184k 行全栈,桌面版仅 Apple Silicon;equity 研报导向,FX 只是数据 provider 之一 [s2] | 放弃金融领域结构:无叙事链条/投资建议模板,每次研究 ~$0.4、~5 分钟(deep research 模式),事实性依赖检索质量 [s3] | 放弃通用性:中文 A 股舆情导向,270 stars 社区小,数据源需为五币种全部重写 [s4] |

若只能选一个:借鉴对象选 TradingAgents 的"分析师→辩论→决策"链条骨架 + FinRobot 的"数字代码算、LLM 只叙事"原则作为架构蓝本(二者均不直接复用代码);当用户更看重"逻辑传导链的显式建模与逐日演化追踪"(即报告要画出 事件→渠道→币种影响 的传导图并跨日对比)时,改以 DeepEar 的 ISQ 模板 + Logic Evolution Tracking 为主要参考。gpt-researcher 则是"skill 形态 + 报告聚合"的工程参照。此决断基于 README 层面证据;各项目对 FX 五币种的实际适配深度未验证,是残余不确定性。

## Deep Read Notes

### TradingAgents (TauricResearch) [s1]
- 定位:"TradingAgents is a multi-agent trading framework that mirrors the dynamics of real-world trading firms." 96.9k stars / 18.7k forks,Apache-2.0,基于 LangGraph。
- 叙事链条(可直接映射到日报结构):Analyst Team(Fundamentals / Sentiment / News / Technical;其中 News Analyst "Monitors global news and macroeconomic indicators, interpreting the impact of events on market conditions")→ Researcher Team("both bullish and bearish researchers…Through structured debates, they balance potential gains against inherent risks")→ Trader Agent("Composes reports from the analysts and researchers to make informed trading decisions")→ Risk Management → Portfolio Manager 终审。
- 数据:v0.3.0 加入 "FRED and Polymarket data vendors";v0.3.1 有 "Alpha Vantage look-ahead filtering"(防前视偏差,对回看"前一天事件"的日报有借鉴意义)。市场覆盖 "any market Yahoo Finance covers"。
- 工程点:`ta.propagate("NVDA", "2026-01-15")` 单函数出决策;`max_debate_rounds` 可配;decision log "always on. Each completed run appends its decision to ~/.tradingagents/memory/trading_memory.md. On the next run…fetches the realised return…generates a one-paragraph reflection";LangGraph checkpoint resume(SQLite,按 ticker)。structured-output agents(v0.2.4)保证结论字段化。
- 局限:入口以单 ticker 为单位;README 无 FX 对示例、无调度。

### FinRobot (AI4Finance-Foundation) [s2]
- 定位:"an AI Agent platform tailored for financial applications, surpassing FinGPT's single-model approach"。7.8k stars,Apache-2.0。
- 架构原文:"1 Lead Agent for orchestration and task routing / 5 role-based sub-agents for data, analysis, modeling, synthesis, and report generation / 3 debate agents for bull case, bear case, and judge-style investment reasoning"。流程图:User Request → Lead Agent → Data→Analysis→Modeling→Synthesis→Report Agent → Bull↔Bear→Judge → "Traceable Investment Research Output"。
- 核心原则(对"避免流水账/可信叙事"最有借鉴价值):"All financial numbers are generated by pure-Python compute operators, not by the language model. The LLM is used for reasoning, synthesis, explanation, and report writing…In short: Numbers are code-calculated. Narratives are LLM-assisted. Every output is provenance-tracked."
- 规模数字(README 自述):"~184k lines";"9 agents";"7 pipelines";"30 pure-Python operators and 7 coordinators";"7 providers with failover, including FMP, Finnhub, yfinance, SEC EDGAR, Adanos, NewsAggregator, and FX"。
- 概念分层:Perception(多模态数据感知)/ Brain(Financial Chain-of-Thought)/ Action(报告、告警),外加 Smart Scheduler(Director Agent 按任务分配最合适的 LLM——注意这是 LLM 调度,不是定时调度)。
- CLI 两步:`generate_financial_analysis.py`(取数+预测)→ `create_equity_report.py`(渲染 HTML/PDF, "15+ chart types"),这种"分析产物落 CSV → 报告渲染读 CSV"的两段式便于 cron 化与调试。

### gpt-researcher (assafelovic) [s3]
- 28.9k stars,Apache-2.0。定位:"the first open deep research agent…produces detailed, factual, and unbiased research reports with citations"。
- 架构原文:"The core idea is to utilize 'planner' and 'execution' agents. The planner generates research questions, while the execution agents gather relevant information. The publisher then aggregates all findings into a comprehensive report." 步骤:建任务专属 agent → 生成问题集 → 每题 crawler 检索 → "Summarize and source-track each resource" → 过滤聚合成报告。
- 特性:"Aggregate over 20 sources";"Generate detailed reports exceeding 2,000 words";导出 PDF/Word;MCP retriever 混合模式(`RETRIEVER=tavily,mcp`)可把金融数据 API 当检索器接入。Deep Research 模式:"Takes ~5 minutes per deep research / Costs ~$0.4 per research (using o3-mini…)"。
- 与本需求最相关的形态:官方支持装成 Claude Skill——"npx skills add assafelovic/gpt-researcher";pip 包用法 `conduct_research()` + `write_report()` 两个 async 调用,极易包进每日 cron 脚本。
- 局限:无金融叙事结构、无投资建议模板、无调度;报告长文倾向与用户"简明扼要"要求相反,需强 prompt 约束。

### DeepEar (HKUSTDial) [s4]
- 270 stars,MIT。定位原文:"An open-source Deep Research framework that transforms Public Opinion into actionable Investment Logic Chains with skills."
- 管线(mermaid 图):Intent Agent → Trend Agent(Discovery)→ Logic Filter → Fin Agent(接 Stock/Search Toolkit + ISQ 评分模板)→ Report Agent;Prediction Layer 为 Forecast Agent + News Projection Layer + Kronos 时序模型;Output Layer:"Draft Sections →(Hybrid RAG)Unified Edit → Final Report .md/.html"(Map-Reduce 写报告)。
- 叙事链条机制(全场最贴合"完整且明确的叙事逻辑链条"):FinAgent "Validates investment logic, checks stock data, and formulates transmission chains using ISQ templates";"Logic Evolution Tracking: Active tracking of how investment theses evolve as new market news and price data arrive";"Signal-Based Comparison: Deep side-by-side analysis of signal changes, drift in sentiment, and logic updates between different runs";报告带 "interactive Draw.io diagrams for logic transmission"。
- 日更相关参数:`--update-from`("Update an existing run (provide base run ID) to track signal evolution")、`--resume`、`--template default_isq_v1`(ISQ 评分模板可换)。
- Skill 集成:自带 `skills/deepear` 可拷入 `~/.claude/skills/`,并提供 skill server(`analyze`/`status` 工具);另指向 Awesome-finance-skills 单件 skill 集。
- 局限:数据源 "Weibo, Cailian Press, Wall Street News" 等偏中文;时序模型面向个股价格冲击,非 FX。

## Gaps
- 没有找到任何"FX/多币种宏观日报"专用的开源 LLM 管线——所有头部项目都是股票/加密 ticker 导向;PHP/THB/BRL 等非 G10 货币的数据接入在全部候选中均无现成方案,需在方案里单独解决(FRED/央行 API/Yahoo `XXXYYY=X`)。
- "定时调度"环节全生态缺席:未发现内置 cron/daily-run 的完整管线项目,只能借调度外壳(GitHub Actions、schedule skill 等)。
- 中文查询("开源 大模型 研报 自动生成 github")返回噪声,未命中国内研报自动生成专项仓库;可换关键词(如 "晨报 agent"、"宏观日报 LLM site:github.com")再探。
- 未深读 FinSight [s5](ACL 2026,"One ticker, one click, one publication-ready report")与 FinnewsHunter [s7]——前者研报生成质量可能最高但强绑定单 ticker,后者偏 alpha 因子挖掘;时间盒内让位给四个更贴题的深读对象。
- 所有结论基于 README 层面;各项目 prompt 内的叙事组织细节(辩论 prompt、报告模板原文)需读源码才能确认,本轮未做。
