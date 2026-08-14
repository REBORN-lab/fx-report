# Task A — 宏观经济解读的开源 skill / 项目 / prompt 框架

AS_OF: 2026-08-14。Freshness 按与 AS_OF 距离标注,并对 LLM/AI 快变主题各降一档(标注中注明「−1」)。

## Sources
[s1] ElmatadorZ (Bunyawat Dechanon) — MoneyAtlas Intelligence OS v2, Claude SKILL.md | https://github.com/ElmatadorZ/MoneyAtlas-ClaudeSkill-Agent | Type: community | Date: 2026-08-04 (last push;53 stars / 13 forks / Apache-2.0) | Freshness: aging (fresh by date, −1 for LLM/AI) | Path: github-search + direct-fetch
[s2] Charles Coverdale — econstack: Claude Code skills for economic analysis | https://github.com/charlescoverdale/econstack | Type: community | Date: 2026-05-08 (last push;4 stars / 1 fork / MIT / 139 commits) | Freshness: aging (fresh by date, −1 for LLM/AI) | Path: ddg + direct-fetch
[s3] tradermonty — Claude Trading Skills | https://github.com/tradermonty/claude-trading-skills | Type: community | Date: 2026-08-13 (last push;2636 stars / 611 forks / MIT) | Freshness: aging (fresh by date, −1 for LLM/AI) | Path: ddg + direct-fetch
[s4] xcbbdg1-maker — macro-economics-suite | https://github.com/xcbbdg1-maker/macro-economics-suite | Type: community | Date: 2026-07-27 (0 stars / MIT) | Freshness: aging (fresh by date, −1 for LLM/AI) | Path: github-search + direct-fetch
[s5] Giulia Iadisernia, Carolina Camassa — Prompting for Policy: Forecasting Macroeconomic Scenarios with Synthetic LLM Personas | https://arxiv.org/abs/2511.02458v1 | Type: academic | Date: 2025-11-04 | Freshness: stale (aging by date ~9mo, −1 for LLM/AI) | Path: arxiv
[s6] Chen Wang (Notre Dame), Kangying Zhou (Texas A&M) — The Macro Alibi: Subjective Risk Attribution in Analyst Scenarios | https://chenwang.one/files/macro_alibi.pdf | Type: academic | Date: 2026-06-11 | Freshness: fresh | Path: ddg + direct-fetch
[s7] brycewang-stanford (Stanford REAP × CoPaper.AI) — Auto-Empirical-Research-Skills (AERS) | https://github.com/brycewang-stanford/Awesome-Agent-Skills-for-Empirical-Research | Type: community | Date: 2026-08-14 (repo updated) | Freshness: aging (fresh by date, −1 for LLM/AI) | Path: ddg + direct-fetch
[s8] zayrhabeeb — macro-toolkit (Claude Skill suite: nowcasting / yield curve / inflation decomposition / Fed event studies) | https://github.com/zayrhabeeb/macro-toolkit | Type: community | Date: 2026-06-30 (0 stars / MIT) | Freshness: aging (fresh by date, −1 for LLM/AI) | Path: github-search
[s9] simonlin1212 — TradingAgents-astock(A 股多 Agent 投研框架,7 位分析师辩论) | https://github.com/simonlin1212/TradingAgents-astock | Type: community | Date: 2026-08-14 (2832 stars / 761 forks / Apache-2.0) | Freshness: aging (fresh by date, −1 for LLM/AI) | Path: github-search
[s10] kkkano — FinSight(多 Agent 会话式金融研究平台,含宏观经济 Agent,自动生成 8 章节报告) | https://github.com/kkkano/FinSight | Type: community | Date: 2026-08-12 (49 stars) | Freshness: aging (fresh by date, −1 for LLM/AI) | Path: github-search

## Findings
1. econstack 把「挑毛病」独立成一个 skill `/econ-audit`:跑 124 项检查 / 17 个类别,输出 RAG(红黄绿)评级 + A–F 字母分 + `--fix` 自动修复方案,并在 `/cost-benefit` 产出 markdown 后**自动追跑一遍 audit**;检查靶点是具名的(numerical consistency、double counting、framing、distributional analysis、strategic misrepresentation patterns 等)。[s2] [新]
2. econstack `/macro-briefing` 的两条硬机制:每项指标给 GREEN/AMBER/RED 交通灯并绑定「quantitative thresholds」;每个输出带 vintage 戳(greenbook 版本、STPR vintage、GDP deflator vintage、carbon/VPF/QALY vintage),使一年后重跑能对同一参数集复现。[s2] [新]
3. MoneyAtlas SKILL.md 用「FAILURE SYSTEM」把报告质量写成输出前的**否决式不变量**:无替代情景 / 未提风险 / 无证据却过度确定 / 无失效点 → 判定 output invalid,强制重评;仍弱则输出 `⚠️ INSUFFICIENT EDGE` 而非硬编一个结论。[s1] [新]
4. MoneyAtlas 对无法溯源的定量声明不只是标记,而是**隔离**:标 `[UNVERIFIED]` 且明令「keep it out of the entry/exit zones」——结论区只能建立在已声明输入之上;并把「abstention 是合法输出」写进 skill。[s1] [新]
5. MoneyAtlas 的推理骨架是四层 Micro→Meso→Macro→Meta,Meta 层专门追问「市场在构建什么叙事、谁从中受益」,把叙事识别当成结构化步骤而非文风。[s1] [新]
6. tradermonty/claude-trading-skills(2636 stars,MIT,2026-08-13 仍在推)带三个可直接借鉴的质检件:`dual-axis-skill-reviewer`(确定性代码检查 + LLM 深度审查双轴)、`data-quality-checker`(发布前校验分析文档数据质量)、`scenario-analyzer`(产出一级/二级/三级影响 + strategy-reviewer 出第二意见)。[s3] [新]
7. 同仓的 `edge-strategy-reviewer` 把「批评者」做成**有固定靶点清单**的角色——edge plausibility / overfitting risk / sample size adequacy / execution realism 四项,而不是泛泛"review 一下"。[s3] [新]
8. 实测检索口径:GitHub 全网 `claude skill macro economics` 仅命中 3 个仓库(最高 2 stars);`macroeconomic analysis` 命中 1316 个仓库,按星排前 30 中只有 1 个是面向宏观**解读**的 Claude Skill(MoneyAtlas,53 stars),其余为计量/DSGE/教学/复现代码。[自测 2026-08-14,命令 `search.py --gh-search ... --sort stars`] [新]
9. macro-economics-suite 的架构主张是「两条互相独立的腿互相印证」:基本面 briefing 答"经济好不好",跨资产比价 regime detector 答"资金在什么风口",由 orchestrator 综合;README 明写"单看一个都可能片面",并诚实列出免费档做不到的项(经济日历 Restricted、10Y-2Y spread 只能用 SHY/TLT 价格比代理)。[s4] [新]
10. arXiv 2511.02458 用 2368 个 persona 提示 vs 100 个无 persona 基线复现 ECB SPF 50 个季度,结论是 persona 描述带来 "no measurable forecasting advantage",可直接省掉以省算力;真正让 GPT-4o 与人类专家 panel 精度 "remarkably similar" 的是"provided with relevant context data"。这与「加厚 prompt 角色设定能提升报告质量」的直觉相反。[s5] [与已知冲突]

## Trade-offs

四个可比候选(均为开源、可直接装进 Claude Code / Claude Skills 的宏观相关 skill 套件)。

| 候选 | 深度/逻辑靠什么保证 | 是否自带独立「挑毛病」环节 | 宏观数据接入 | 成熟度 / 维护 | 代价 / 放弃了什么 |
|---|---|---|---|---|---|
| econstack [s2] | 框架化方法论:HM Treasury Green Book / EU Better Regulation / World Bank / ADB / AU-VIC 各自的参数与惯例内置,交通灯 + 阈值 + vintage 戳 [s2] | 有,且是最强的一项:`/econ-audit` 124 checks / 17 categories,RAG + A–F 分 + `--fix`,`/cost-benefit` 后自动追跑 [s2] | 有:ONS / FRED / ECB / ABS / OBR 实时拉取,UK/US/EU/AU 四地口径 [s2] | 弱:4 stars / 1 fork,最后 push 2026-05-08,创建 2026-04-02 [s2] | 口径绑死在政策评估(CBA/briefing note/Green Book),不覆盖跨资产与市场解读;单人项目、三个多月未推,复用等于接手维护 [s2] |
| MoneyAtlas [s1] | 三步 Genesis Protocol(First Principle Codex → Micro/Meso/Macro/Meta System Thinking → AI Fluency 4D)+ SMC 五层市场结构 [s1] | 无独立审计 skill,但有输出前的 FAILURE SYSTEM 否决闭环(四条 invalid 条件 → 重评 → `⚠️ INSUFFICIENT EDGE`) [s1] | 无:`requires_tools: false`,自述"no live price feed",无数据时只给推理框架并点名缺哪些输入 [s1] | 中:53 stars / 13 forks / Apache-2.0,2026-08-04 有推送,99 commits [s1] | 放弃了数据落地——它是纯推理层,数字要自己喂;SMC/Smart Money 那套市场结构语汇偏交易叙事,对政策/基本面解读是噪声 [s1] |
| claude-trading-skills [s3] | 不靠单个大 skill,靠 workflow manifest 把多 skill 串成有决策门的流水线(`workflows/*.yaml` 为 canonical,validator 强制) [s3] | 有三件:`dual-axis-skill-reviewer`(代码检查 + LLM 深审双轴)、`data-quality-checker`、`edge-strategy-reviewer`(4 项固定靶点) [s3] | 部分:`macro-regime-detector` 走 yfinance/FMP,`economic-calendar-fetcher` 需 FMP;主体是股票/ETF 数据 [s3] | 最强:2636 stars / 611 forks / MIT,2026-08-13 仍在推,24 open issues [s3] | 宏观只是其中一个 skill(`macro-regime-detector`),整仓重心是个股/择时/仓位/交易日志;要拿它的宏观解读能力得先接受一个 60+ skill 的交易框架 [s3] |
| macro-economics-suite [s4] | 结构性交叉验证:基本面与跨资产 regime 两条独立腿由 orchestrator 综合,理由是"单看一个都可能片面" [s4] | 无(README 未提任何审计/复核 skill;来源未说明) [s4] | 有:FRED 免 key CSV(墙内直连)+ yfinance ETF + FMP 免费档国债 [s4] | 最弱:0 stars,创建与最后更新同为 2026-07-27,MIT [s4] | 明确只做美国口径(FOMC/CPI/非农),中国宏观"不在本仓库范围";免费档下经济日历缺失、10Y-2Y spread 只能用 SHY/TLT 价格比代理 [s4] |

**若只能选一个:econstack [s2]**,因为消费者的痛点是「报告的深度和逻辑欠缺」,而四者中只有它把方法论审计做成了带 124 条具名靶点、RAG 评级、字母分和自动追跑的**独立可执行环节**——这正好补上消费者已知的缺口(校验器只查数字白名单、不验 verdict);其余三者要么只有输出前的软性自检 [s1],要么把宏观当配角 [s3],要么根本没有复核环节 [s4]。

**当以下条件成立时改选 claude-trading-skills [s3]**:当你判定「审计清单」不是主要瓶颈,而「审计本身不可信/会漂移」才是——即需要一个能对 skill 自身做确定性代码检查 + LLM 深审双轴复核的元层(`dual-axis-skill-reviewer`),或者需要一个 validator 强制的多 skill 流水线 manifest 而非单体 skill。判据可操作化为:econstack 的 `/econ-audit` 在你自己的周报上跑三次,若三次给出的 RAG/字母分对同一份未改动文档不一致,说明审计器本身不稳定,应转向 [s3] 的双轴方案。

## Deep Read Notes (DEEP)

### MoneyAtlas Intelligence OS v2 — SKILL.md [s1]

frontmatter 自述定位:"Apply Genesis Protocol (First Principle + System Thinking) combined with SMC Layer analysis to produce structured insights with explicit scenarios, entry/exit zones, and uncertainty."`produces` 字段写死了产出契约:"Structured market scenarios with explicit entry/exit zones, stated confidence, and an invalidation condition for every scenario."

`compatibility` 自述:"Any instruction-following model. Reasoning is model-independent — the SKILL.md is self-contained and needs no tools to run."`requires_tools: false`。

**范围局限(来源自述)**:`not_for` 明写 "Real-time price feeds, execution/order placement, or personalized investment advice. It is a reasoning framework, not a signal service or a broker."

**否决式不变量(FAILURE SYSTEM 原文)**:
> Output invalid if:
> - No alternative scenario
> - No risk mentioned
> - Too certain without evidence
> - No invalidation point
> → Re-evaluate before outputting
> → If still weak: `⚠️ INSUFFICIENT EDGE`

**信息不足时的降级契约(原文)**:
> - **No live data provided** → state the reasoning *framework* for the asset and name exactly which inputs would resolve it. Do not invent a current price, level, or figure. An invented number is worse than an admitted gap.
> - **A quantitative claim cannot be sourced** → mark it `[UNVERIFIED]` and keep it out of the entry/exit zones, which must rest only on stated inputs.
>
> An abstention is a valid output. A confident answer built on data the skill does not have is not.

**CONSTRAINTS — Non-negotiable(原文)**:"Never give single prediction — always scenarios / Always include uncertainty and confidence level / Avoid narrative bias — question the consensus / Highlight missing data explicitly / Human = final decision. Always."

FULL MODE 输出骨架固定八段:SITUATION MAP → FIRST PRINCIPLE BREAKDOWN → SYSTEM MAP(原文 "Macro → Liquidity → Asset → Price chain")→ SMC LAYER MAP → NARRATIVE INTELLIGENCE(原文 "What Smart Money wants retail to believe vs. reality")→ SCENARIOS(Bull/Bear/Base 各带 entry zone | target | condition)→ DECISION FRAMEWORK(原文 "IF your timeframe is X → do Y")→ RISK & FAILURE MODE,末尾强制 `CONFIDENCE: [X%] | KEY UNKNOWNS: [list]`。

仓库统计:53 stars / 13 forks / Apache-2.0 / 99 commits,created 2026-03-19,last push 2026-08-04 [自测 2026-08-14,`search.py --github ElmatadorZ/MoneyAtlas-ClaudeSkill-Agent`]。

### econstack — README [s2]

自我定位:"econstack handles the first 80% of economic analysis, so you can focus on the interpretation and key decisions"。7 个 skill:`/longlist`、`/cost-benefit`、`/macro-briefing`、`/fiscal-briefing`、`/market-research`、`/briefing-note`、`/econ-audit`。

`/econ-audit` 原文:"Think of it as a senior partner and an economics professor going through your work and poking holes in it. Full methodology audit ... Runs 124 checks across 17 categories and produces a RAG (red, amber, green) rating on how your methods and assumptions compare to best practice."检查覆盖面原文列举:"numerical consistency, discount rates, additionality, multiplier plausibility, double counting, framing, Five Case Model completeness, distributional analysis, Aqua Book RIGOUR compliance, and strategic misrepresentation patterns."另注 "Letter grade A-F, with auto-fix option."(`/econ-audit . --fix`)

`/macro-briefing` 原文:"Pulls live data from official government databases (ONS, FRED, ECB, ABS) ... Every number is traceable: full methodology, data sources, and vintage dates included. Traffic-light macro assessment (GREEN/AMBER/RED) with quantitative thresholds."覆盖 UK / US / Euro area / Australia。

可复现性原文:"Every output carries a vintage stamp: greenbook version, STPR vintage, GDP deflator vintage, OB / METB / carbon / VPF / QALY / WELLBY vintages. So an appraisal you ran today can be re-run a year from now and the numbers will still be reproducible against the same parameter set."

`/cost-benefit` 自带 "validation gate that aborts on broken counterfactuals or missing METB" 和 "an automatic `/econ-audit` pass on the produced markdown" —— 即**审计不是可选后置步骤,而是产出管线的一环**。

数据后备原文:"Backed by 57 audited parameter files and 20+ R packages on CRAN"(README 结尾另处写 "16 R packages on CRAN and a 57-file parameter database and 8 reference case templates" —— 同一 README 内 20+ 与 16 两处口径不一致,记录如实)。另有 "391 UK local authority datasets",放在第二个仓库 `econstack-data`。

**局限**:4 stars / 1 fork,created 2026-04-02,last push 2026-05-08,open_issues 0 [自测 2026-08-14,`search.py --github charlescoverdale/econstack`] —— 单人项目且已三个多月未推。框架清单全为英美澳欧政策评估口径,无中国口径。README 未给出 124 项检查的清单本身(需读仓库内文件)。

### The Macro Alibi: Subjective Risk Attribution in Analyst Scenarios [s6]

Chen Wang(Notre Dame)、Kangying Zhou(Texas A&M),2026-06-11,85 页。关键词自列含 "large language model"。

样本原文:"the institutional setting of the Morgan Stanley Risk-Reward Framework reports from 2007 to 2025, comprising 63,191 firm-quarter analyst scenario-based reports."

方法原文:"We use large language models to extract, from each scenario narrative, the share of analyst attention allocated to macroeconomic, industry-level, and firm-specific drivers."事后基准用 "realized CAPM 𝑅 2 within the corresponding market-state-by-realized-scenario subsample",依据 "Roll's (1988) canonical approach of using 𝑅 2 to attribute return variation to market-wide forces"。

核心数字(引自源):"Bear-case narratives devote significantly more (6.3 percentage points) attention to macroeconomic forces than base-case narratives—a within-report gap that absorbs all analyst-, firm-, and time-level heterogeneity by construction. The corresponding bull–base gap is essentially zero, an order of magnitude smaller."

反证原文:"Conditional on the same forward market state, the bear–base difference in realized CAPM 𝑅 2 is close to zero in weak market states and turns negative in good market states. Realized downside outcomes are therefore not disproportionately explained by market-wide variation; bear narratives describe them as if they were."

失效模式定性原文:"Belief formation about the downside therefore appears to follow a default script rather than a state-specific calculation."机制检验 "favor a cognitive availability-heuristic explanation—analysts anchor downside narratives on salient macro-crisis templates—over a strategic career-concerns explanation."

经济后果原文:"The bear–base macro-attention gap predicts systematic pessimism in subsequent base-case forecasts, and portfolios formed on a nonlinear bias-adjusted signal earn monthly CAPM alphas of up to 1.9%."

**对本任务的可操作含义**:给出了一个可检的具名失效模式 —— 下行情景里"归因给宏观"的份额若不随市场状态变化,就是模板化叙事而非分析。这可以直接做成周报的一条不变量检查(bear/base 两段的宏观归因占比之差应随市场状态变动,常年恒定即报警)。

**范围局限(来源自述)**:样本仅 Morgan Stanley Risk-Reward 一套报告体系;宏观/行业/公司三分的 attention share 由 LLM 抽取,论文正文(本次仅取到前 ~4 页)未在已读部分给出抽取器的验证细节。

### Claude Trading Skills — README + skills catalog [s3]

2636 stars / 611 forks / MIT / 24 open issues,created 2025-10-19,last push 2026-08-13 [自测 2026-08-14,`search.py --github tradermonty/claude-trading-skills`]。

自述定位原文:"The goal is not to outsource buy/sell decisions to AI. The goal is to structure market review, risk management, trade planning, journaling, and continuous improvement."

**单一事实源约定(原文)**:"**Canonical source:** `skills-index.yaml` is the authoritative index of all skills. If this README, `CLAUDE.md`, or docs disagree with the index, the index is correct. The same applies to multi-skill workflows — `workflows/*.yaml` is canonical." —— 即文档与索引冲突时索引为准,且 workflow manifest 受 `--strict-workflows` validator 强制。

与「报告深度/逻辑」直接相关的四个 skill(catalog 原文摘录):
- `dual-axis-skill-reviewer` — "Review skills in any project using a dual-axis method: (1) deterministic code-based checks (structure, scripts, tests, execution safety) and (2) LLM deep review findings."
- `data-quality-checker` — "Validate data quality in market analysis documents and blog articles before publication."
- `edge-strategy-reviewer` — "Critically review strategy drafts from edge-strategy-designer for edge plausibility, overfitting risk, sample size adequacy, and execution realism."
- `scenario-analyzer` — "Analyze 18-month scenarios from news headlines via scenario-analyst agent with strategy-reviewer second opinion; outputs primary/secondary/tertiary impact analysis and stock picks."(整仓中少数明确要求 `websearch` 的 skill 之一)

宏观相关件:`macro-regime-detector` — "Detect structural macro regime transitions (1-2 year horizon) using cross-asset ratio analysis.",集成 `yfinance` **required** / `fmp` optional;`economic-calendar-fetcher` 需 `fmp`;`market-news-analyst`、`market-environment-analysis` 需 `websearch`。另有 `us-market-bubble-detector` 用 "revised Minsky/Kindleberger framework v2.1"。

`edge-signal-aggregator` 明确把"矛盾"当一等公民:"Aggregate and rank signals from multiple edge-finding skills ... into a prioritized conviction dashboard with weighted scoring, deduplication, and contradicti[on]..."(catalog 该行被截断)。

**范围局限(来源自述)**:"It is not designed for fully automated trading, signal outsourcing, or short-term scalping.";免付费 API 的 starter path 只有 5 个 skill,且 README 特别澄清 "'no API' does not mean 'no external data' — these skills still need public CSVs, chart screenshots, or local files."

## Gaps
- **没找到任何专做「宏观经济解读/评论/归因」的中文开源 skill**。GitHub `claude skill macro economics` 全网仅 3 个仓库(最高 2 stars)[自测 2026-08-14];中文侧命中的 [s9][s10] 及若干个人项目都是**个股/投研**框架,宏观只是其中一个 sub-analyst。macro-economics-suite [s4] 是唯一中文文档的宏观 skill,但明写"中国宏观(社融/PMI/M2/LPR)是另一套逻辑,不在本仓库范围"。
- **没找到针对宏观报告的「逻辑质量」评测集或基准**。arXiv 用 `all:"..."` 精确短语检索,`LLM agent macroeconomic forecasting reasoning`、`large language models macroeconomic analysis`、`economic reasoning benchmark language models`、`LLM forecasting economic indicators` 四条查询均返回 0 结果 [自测 2026-08-14];econ.GN 分类下 2025-06 起的 LLM 论文多为行为/劳动力市场议题,与"报告论证质量"无关。找到的最接近物是 [s5](预测精度,非论证质量)与 [s6](分析师归因偏差,非工具)。
- **没找到 econstack 124 项检查的清单原文**。README 只给类别名,清单需 clone 仓库读 `econ-audit/` 目录;本轮未做仓库内文件级抓取。
- **可能更有收获的其他角度**:(a) 把 [s6] 的 Macro Bear Bias 反过来做成周报不变量(下行段宏观归因占比 vs 市场状态的相关性检验),这是本轮唯一带量化阈值(6.3pp)的可执行靶点;(b) 抓 `tradermonty/claude-trading-skills` 的 `dual-axis-skill-reviewer/SKILL.md` 与 `data-quality-checker/SKILL.md` 原文,看双轴审查的具体 checklist 结构;(c) 检索央行/IMF/BIS 官方是否发布过 macro commentary 的写作规范(本轮 `--gh-search "central bank policy analysis LLM"` 返回 0,未从官方侧入手);(d) 检索通用的"论证质量/批判性审查" skill(如 DDG 顺带命中的 `mattpocock/skills` 的 `grill-me`,自述 "stress-tests plans and designs through systematic questioning"),它们不落在宏观主题内,但机制可迁移——本轮按硬约束未展开。
