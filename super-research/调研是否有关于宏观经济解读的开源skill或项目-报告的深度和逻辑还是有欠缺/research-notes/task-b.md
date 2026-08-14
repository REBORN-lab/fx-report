# Task B: 语义检索 — 宏观叙事的分析框架与推理链方法论

AS_OF 2026-08-14. 目标:找出把宏观数据转成**有逻辑链条**的解读的公开方法论(传导机制拆解、情景分析、证伪结构、推理质量评分),含学术与机构做法。
落点约束:消费者已有五币种日报/周报,弱点是「深度和逻辑欠缺」——因此只收**可直接搬进 SKILL.md 的结构**,不收纯理论综述。

Freshness 判定基准(AS_OF 2026-08-14):fresh = 发布日 > 2026-02-14;aging = 2023-08-14 ~ 2026-02-14;stale = < 2023-08-14。
LLM/AI 与政策类各降一档;方法论与经济学理论属稳定主题,标注 stale 时附「稳定主题/现行有效」说明。

## Sources

[s1] ICD 203 — Analytic Standards(美国情报体系分析标准,含 9 条 Analytic Tradecraft Standards + 概率词表) | https://archive.dni.gov/files/documents/ICD/ICD-203.pdf | 正文签署 2015-01-02,技术修订 2022-01-21;PDF HTTP `Published Time: Tue, 13 Jan 2026` | **stale(>3yr)** —— 稳定主题 + 现行有效强制标准,可用性不受年份影响 | 已 `--fetch --full` 全文
[s2] IMF United Kingdom 2017 Article IV Consultation Staff Report(含 Risk Assessment Matrix 与其脚注定义) | https://www.astrid-online.it/static/upload/imf_/imf_uk_artiv_02_18.pdf | 2017/2018 | **stale(>3yr)** —— 但 RAM 结构在 2025 年 Article IV 仍在用(见 [s3]) | 已 `--fetch --full` 全文
[s3] IMF Republic of Latvia: 2025 Article IV Consultation | https://www.imf.org/-/media/files/publications/cr/2025/english/1lvaea2025001-source-pdf.pdf | 2025 | **aging(6mo–3yr)** | 仅 DDG 摘要(证明 RAM 仍是现行附录格式,目录含 `I. Risk Assessment Matrix ___ 39`)
[s4] IMF Algeria 2014 Article IV Consultation(RAM 列头实例) | https://www.imf.org/external/pubs/ft/scr/2014/cr14341.pdf | 2014 | **stale(>3yr)** | 已 `--fetch --full` 全文
[s5] IMF Technical Notes and Manuals 17/08 — Assessing Country Risk: Selected Approaches | https://www.imf.org/-/media/Files/Publications/TNM/2017/tnm1708.ashx | June 2017 | **stale(>3yr)** —— 稳定主题 | 已 `--fetch`(目录+执行摘要;正文被 limit 截断)
[s6] Bank of England — Making scenarios add up: spanning risks with scenario synthesis | https://www.bankofengland.co.uk/bank-insights/2026/making-scenarios-add-up-spanning-risks-with-scenario-synthesis | 2026-07-16 | **fresh(<6mo)** | 已 `--fetch --full` 全文
[s7] Adrian, Giannone, Luciani & West — Scenario Synthesis and Macroeconomic Risk(Fed FEDS 2025-036,[s6] 的方法论母本) | https://ideas.repec.org/p/fip/fedgfe/2025-36.html / https://www.federalreserve.gov/econres/feds/scenario-synthesis-and-macroeconomic-risk.htm | 2025 | **aging(6mo–3yr)** | 仅书目 + [s6] 引用
[s8] ECB — Transmission mechanism of monetary policy(官方传导渠道分解页) | https://www.ecb.europa.eu/mopo/intro/transmission/html/index.en.html | 页面 `Published Time: 2016-08-08` | **stale(>3yr)** —— 稳定主题,现行官方口径 | 已 `--fetch --full` 全文
[s9] Bernanke Review — Forecasting for monetary policy making and communication at the Bank of England | https://www.bankofengland.co.uk/independent-evaluation-office/forecasting-for-monetary-policy-making-and-communication-at-the-bank-of-england-a-review/forecasting-for-monetary-policy-making-and-communication-at-the-bank-of-england-a-review | 2024-04-12 | **aging(6mo–3yr)** | 仅 DDG 摘要 + 二手评论
[s10] Shiller — Narrative Economics(AER 107(4)) | https://fairmodel.econ.yale.edu/ec439/shiller1.pdf | 2017 | **stale(>3yr)** —— 稳定主题,叙事经济学奠基文献 | 仅 DDG 摘要
[s11] Roos & Reccius — Narratives in economics(arXiv 2109.02331v2) | https://arxiv.org/abs/2109.02331 | v1 2021-09-06 / v2 2022-12-21 | **stale(>3yr)** —— 稳定主题 | 已 `--fetch` 摘要页
[s12] Gueta et al. — Can LLMs Learn Macroeconomic Narratives from Social Media?(arXiv 2406.12109v2) | https://arxiv.org/abs/2406.12109 | v1 2024-06-17 / v2 2025-02-11 | aging → **LLM 降一档 = stale** | arXiv API 摘要
[s13] Lee et al. — EconCausal: A Context-Aware Economic Reasoning Benchmark for LLMs(arXiv 2510.07231v4) | https://arxiv.org/abs/2510.07231 | v1 2025-10-08 / v4 2026-05-26 | fresh → **LLM 降一档 = aging** | arXiv API 摘要
[s14] Akimitsu — Wrong and More Confident: A Field Experiment on LLMs Taking a Graduate Economics Exam(GERB,arXiv 2607.23424v3) | https://arxiv.org/abs/2607.23424 | v1 2026-07-26 / v3 2026-07-31 | fresh → **LLM 降一档 = aging** | arXiv API 摘要
[s15] Burton — Analysis-of-Competing-Hypotheses(开源 ACH 实现,CIA Heuer 方法) | https://github.com/Burton/Analysis-of-Competing-Hypotheses | 109★,`pushed_at` 2012-01-08,GPL-3.0,PHP | **stale(>3yr,事实上已停更 14 年)** | GitHub API [自测 2026-08-14]
[s16] twschiller/open-synthesis — Open platform for CIA-style intelligence analysis(ACH 协作平台) | https://github.com/twschiller/open-synthesis | 213★,`pushed_at` 2026-05-27,AGPL-3.0,Python | **fresh(<6mo,活跃)** | GitHub API [自测 2026-08-14]
[s17] ropensci/dfms — Dynamic Factor Models for R(含 news decomposition) | https://github.com/ropensci/dfms | 46★,`pushed_at` 2026-06-18,GPL-3.0,R | **fresh(<6mo,活跃)** | GitHub API [自测 2026-08-14]
[s18] SermetPekin/nowcasting-dfm — Python DFM nowcasting,扩展 FRBNY 框架,含 Kalman-based news decomposition | https://github.com/SermetPekin/nowcasting-dfm | 3★,`pushed_at` 2026-08-13,BSD-3-Clause,Python | **fresh(<6mo,活跃但极小众)** | GitHub API [自测 2026-08-14]
[s19] NY Fed Staff Report 1152 — Component-Based Dynamic Factor Nowcast Model(news/impact 分解方法) | https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr1152.pdf | **发布日未核实** | 未定级(日期未核实) | 仅 DDG 摘要
[s20] IMF WP/19/36 — Growth at Risk: Concept and Application in IMF Country Surveillance | https://www.imf.org/-/media/files/publications/wp/2019/wpiea2019036.pdf | 2019-02 | **stale(>3yr)** —— 稳定主题 | 仅 DDG 摘要
[s21] IPCC AR5 Guidance Note on Consistent Treatment of Uncertainties(校准语言:likelihood × confidence 二维) | https://klimareporter.de/images/dokumente/2023/05/AR5_Uncertainty_Guidance_Note.pdf | 2010 | **stale(>3yr)** —— 稳定主题 | 仅 DDG 摘要
[s22] 天风证券 — 货币传导机制与利率分析框架(中文机构版传导链条框架) | http://pdf.dfcfw.com/pdf/H3_AP201808021173410146_1.pdf | 2018-08 | **stale(>3yr)** | 仅 DDG 摘要
[s23] Wikipedia — Monetary transmission mechanism | https://en.wikipedia.org/wiki/Monetary_transmission_mechanism | 持续更新 | **fresh(索引类)** | 仅 DDG 摘要(仅作渠道清单交叉校验)

## Findings

> 三值标记见每条末尾。凡带数字处按「引自源无标注 / `[自测 YYYY-MM-DD]` / `[推导 …]`」三分标注。

### F1 — ICD 203 的 9 条 Analytic Tradecraft Standards:**目前找到的唯一一份公开、可直接当 rubric 用的推理质量标准** 【stale(>3yr),稳定主题+现行有效】

这是本次调研对「深度和逻辑欠缺」最直接的答案。ICD 203 不是学术论文,是一份**强制性产品评审标准**,ODNI 用它逐条打分每一份分析产品。9 条标准里有 5 条正好对应外汇报告当前的缺口:

1. **Std (2) 不确定性必须显式表达,且概率词绑定数值区间**。原文给出强制词表(引自源):
   `almost no chance / very unlikely / unlikely / roughly even chance / likely / very likely / almost certain(ly)`
   对应 `01-05% | 05-20% | 20-45% | 45-55% | 55-80% | 80-95% | 95-99%`。
   原文并规定:"Analysts are strongly encouraged not to mix terms from different rows. Products that do mix terms must include a disclaimer clearly noting the terms indicate the same assessment of probability."
   并强制区分 likelihood 与 confidence:"products that express an analyst's confidence in an assessment or judgment using a 'confidence level' (e.g., 'high confidence') must not combine a confidence level and a degree of likelihood, which refers to an event or development, in the same sentence."
2. **Std (3) 必须把「情报事实」与「分析师假设/判断」在文本层面分开**,并且:"Products should state assumptions explicitly when they serve as the linchpin of an argument or when they bridge key information gaps. Products should explain the implications for judgments if assumptions prove to be incorrect. Products also should, as appropriate, identify indicators that, if detected, would alter judgments."
   —— 这就是**证伪结构**的可执行版本:linchpin 假设 + 假设被证伪时结论怎么变 + 可观测的翻转指标。
3. **Std (4) 必须做 alternatives 分析**:"Analytic products should identify and assess plausible alternative hypotheses. This is particularly important when major judgments must contend with significant uncertainties, or complexity (e.g., forecasting future trends), or when low probability events could produce high-impact results… Products also should identify indicators that, if detected, would affect the likelihood of identified alternatives."
4. **Std (6) 逻辑论证**:"present a clear main analytic message up front… Products containing multiple judgments should have a main analytic message that is drawn collectively from those judgments. All analytic judgments should be effectively supported by relevant intelligence information and coherent reasoning… should be internally consistent and acknowledge significant supporting and contrary information affecting judgments."
5. **Std (7) 变化说明——直接命中日报/周报这种连载体裁**:"Analytic products should state how their major judgments on a topic are consistent with or represent a change from those in previously published analysis… They should avoid using boilerplate language, however, and should make clear how new information or different reasoning led to the judgments expressed in them. **Recurrent products such as daily crisis reports should note any changes in judgments;** absent changes, recurrent products need not confirm consistency with previous editions."

另有 Std (1) 源质量与可信度描述、Std (5) 客户相关性与 implications、Std (8) "should not avoid difficult judgments in order to minimize the risk of being wrong"、Std (9) 有效可视化。[s1]

**为什么这条算「新」**:这是一套**外部的、逐条可勾选的**评分表,而不是又一个 prompt 里的自然语言禁令。已有前车之鉴(本仓库 `fx-verdict-invariant` 教训:prompt 禁令堵不住,要改成不变量)——ICD 203 的 9 条正好能当「校验器要检查什么」的清单。学界已有人把它操作化成打分表:PMC 论文称 "These standards are operationalized by AIS in a 'Rating Scale for Evaluating Analytic Tradecraft Standards,' an assessment rubric with nine criteria (Table 1). The rubric is very detailed."(https://pmc.ncbi.nlm.nih.gov/articles/PMC6330287/,DDG 摘要,未 fetch)

### F2 — IMF Risk Assessment Matrix(RAM):把「风险」写成**可校验的四列表**,且概率词有硬数值口径 【stale(>3yr)源文,但结构 aging/现行】

RAM 是 IMF Article IV 报告的固定附录。列头(引自源,Algeria 2014):
`Source of Risks | Relative Likelihood | Expected impact | Source of impact | Policy response`。[s4]

关键在脚注的**口径定义**(引自源,UK 2017 Article IV):
> "The Risk Assessment Matrix (RAM) shows events that could materially alter the baseline path (the scenario most likely to materialize in the view of IMF staff). The relative likelihood is the staff's subjective assessment of the risks surrounding the baseline ("low" is meant to indicate a probability below 10 percent, "medium" a probability between 10 and 30 percent, and "high" a probability between 30 and 50 percent). The RAM reflects staff views on the source of risks and overall level of concern as of the time of discussions with the authorities. **Non-mutually exclusive risks may interact and materialize jointly.**" [s2]

注意口径**不是恒定的**:2014 年版本(elibrary 摘要,https://www.elibrary.imf.org/downloadpdf/view/journals/002/2014/231/article-A002-en.pdf)写的是 "'high' a probability of 30 percent or more",UK 2017 版收成了 "between 30 and 50 percent"。要引用时必须指明用的是哪一版口径。[s2][s4 + elibrary 摘要]

RAM 仍是现行格式:Latvia 2025 Article IV 目录仍列 `I. Risk Assessment Matrix ___ 39`。[s3]

**可搬进外汇报告的最小结构**:每条风险 = 风险源 + 概率档(绑定数值区间) + 对本组合的预期影响 + **影响通过哪条渠道传导** + 触发后怎么办。第四列 `Source of impact` 是当前报告最缺的一列——它强制作者写出**机制**而不是相关性。

IMF 自己的风险评估架构(部门维度)也可直接当外汇报告的「渠道清单」:External Sector / Public Sector / Financial Sector / Real Sector / Contagion,再加 "Supplementary Indicators: Event And Policy Implementation Risks"。[s5]

### F3 — BoE Scenario Synthesis:情景分析**可被量化验收**,「这组情景够不够覆盖风险」有数字答案 【fresh(<6mo)】

这是本次最新、也是最能治「情景写了但没意义」的做法。BoE 用 Adrian et al.(Fed FEDS 2025-036,[s7])的方法,把每个情景表达成 density forecast,再对一个外部 reference distribution 做预测综合,输出两个东西:**每个情景的权重**、**这组情景覆盖了参考分布多少百分比的风险(spanning share)**。

2026 年 4 月 MPR 的实测数字(全部引自源):
- 三个情景 A/B/C,合起来 "spans 99% of risks to inflation in the central region (25th–75th percentiles) of the DMP-implied reference, as well as the right (50th–90th percentiles) and left-sides (10th–50th percentiles)"。
- 去掉情景 C 后:"the synthesis spans only 87%–89% of risks in the three regions of the reference"。
- 情景权重:"The synthesis places nearly two thirds of the weight on Scenario B, one third on Scenario C, and near zero on Scenario A."
- 换到 Bank Rate 维度:仅 A+B 的综合 "spans 84% of the 10th–50th percentiles and 74% of the 25th–75th, but just 41% of the right side (50th–90th percentiles)";加入 C 后右尾覆盖率升到 "94% (50th–90th percentiles)",权重变成 A+B 合计 "three fifths"、C "two fifths"。

参考分布来自**外部可观测的市场/调查数据**,不是自己编的:通胀用 Decision Maker Panel 调查(对 10/25/50/75/90 分位拟合 skew-t),Bank Rate 用 "the option-implied density for 12-month SONIA rate three months ahead"。

BoE 自己划的边界(引自源):"The synthesis will, of course, only ever be **one input** to such deliberations, since its statistical grounding leaves it less well suited to exploring judgemental or narrative aspects of scenario design." 且权重 "do not speak to the appropriate stance of monetary policy"。[s6]

**为什么这条算「新」**:它给了「情景是否值得写」的**可证伪判据**——如果去掉某个情景,覆盖率不掉,那个情景就是废话。这正是「深度不够」的一种可测形式。

背景动因:Bernanke Review(2024-04-12)对 BoE 的建议之一就是弃用 fan chart、改用替代情景("What Bernanke did recommend is ditching fan charts showing forecast uncertainty, and instead look at alternative scenarios to the main forecast",socialscience.international 评论,DDG 摘要),以及 "the Bank should undertake a thorough review and updating of" 其模型体系(economicsobservatory 摘要)。[s9]

### F4 — ECB 传导机制的官方分解:一条链拆成 7 个可挂证据的节点 【stale(>3yr),稳定主题、现行官方口径】

ECB 官方页面把政策利率→价格的链条明确切成命名节点(引自源的小标题):
`Change in official interest rates` → `Affects banks and money-market interest rates` / `Affects expectations` / `Affects asset prices` → `Affects saving and investment decisions` / `Affects the supply of credit` / `Affects the supply of bank loans` → `Leads to changes in aggregate demand and prices`。

对外汇报告最有用的两句(引自源):
- 汇率被明确挂在 asset-price 节点下:"may lead to adjustments in asset prices (e.g. stock market prices) **and the exchange rate**. Changes in the exchange rate can affect inflation directly, insofar as imported goods are directly used in consumption, but they may also work through other channels."
- 链条的固有不确定性被官方写死:"The transmission mechanism is characterised by long, variable and uncertain time lags. Thus it is difficult to predict the precise effect of monetary policy actions on the economy and price level."

页面还单列 risk-taking channel 的两条机制:"First, low interest rates boost asset and collateral values… Second, low interest rates make riskier assets more attractive, as agents search for higher yields."[s8]

**可搬进外汇报告的用法**:任何「央行 X 导致货币 Y 走弱」的句子,强制标注它走的是哪个节点(利率差 / 预期 / 资产价格 / 信贷供给),并且强制标注 lag 是未知的——这直接把「相关性叙述」变成「渠道叙述」。中文机构版可对照天风《货币传导机制与利率分析框架》:"央行货币操作一般对象是商业银行,通过商业银行传导到全金融市场,并最终传导至…"(DDG 摘要)[s22]

学术层面,渠道拆解的经典引用可用于给每条渠道挂文献强度:cost channel(Barth & Ramey,354 引)、bank balance-sheet channel(Jiménez, Ongena, Peydró & Saurina, AER 2012,1069 引)、shadow-bank transmission(Xiao, RFS 2019,253 引)、international channels & Mundellian trilemma(Rey, NBER 2016,114 引)。引用数为 OpenAlex `cited_by_count` [自测 2026-08-14,`--scholar` 查询 "macroeconomic narrative transmission channel framework"]。

### F5 — 叙事强度的量化:**有方法论定义,但预测力尚未被证实** 【s10 stale / s11 stale / s12 stale(LLM 降档)】

- Shiller 的原始立场(引自源):"Even the simplest epidemic model shows that no narratives reach everyone, and whom a particular narrative reaches and whom it does not is largely random. Such measures relate to the contagion importance of narratives beyond the mere count of numbers of mention."(即:**单纯统计提及次数不构成叙事强度**)[s10]
- Roos & Reccius 给了可操作的判别式(引自源):"for a narrative to be economically relevant, it must be a sense-making story that emerges in a social context and suggests action to a social group",并 "isolating five important characteristics";同时明确 topic modeling 不够:"the complementary use of other canonical methods from the natural language processing toolkit and the development of new methods is inevitable to go beyond identifying topics"。[s11]
- **反证**:Gueta et al. 用 X/Twitter 语料抽宏观叙事、送进下游金融预测任务,结论是负面的(引自源):"Our work highlights the challenges in improving macroeconomic models with narrative data, paving the way for the research community to realistically address this important challenge."[s12]

**结论**:叙事**结构**(是不是一个"suggests action"的完整故事)可以用来做**报告质量检查**;叙事**强度**用来做**预测**目前证据不支持。对外汇报告的正确用法是前者——检查「本周主线」是不是一个真故事(有主体、有行动、有传导),而不是把叙事指数当因子。

### F6 — News decomposition:把「预测为什么变了」拆成每条数据的贡献,**有现成开源实现** 【s17/s18 fresh,s19 日期未核实】

DFM nowcasting 的 news decomposition 回答的正是「这周的判断相比上周变了多少、是被哪条数据推动的」。第三方文档(DDG 摘要)表述为:"The news decomposition breaks this revision down into the individual contributions ('impacts') of each new data point, allowing analysts to understand which specific releases (e.g., an unexpected jump in Industrial Production) drove the update in the nowcast."(deepwiki/ropensci/dfms);MacroEconometricModels.jl 文档把方法归到 "Banbura and Modugno 2014"。NY Fed SR 1152 自述 "decomposes each weekly GDP nowcast revision into impacts stemming from surprises in data releases (relative to the model's prediction), as well as data and parameter revisions"(DDG 摘要)。[s19]

开源实现(星数与推送日 [自测 2026-08-14,GitHub API]):
- `ropensci/dfms`(R,46★,2026-06-18 推送,GPL-3.0)—— rOpenSci 同行评审过,最稳的一个。[s17]
- `SermetPekin/nowcasting-dfm`(Python,3★,2026-08-13 推送,BSD-3-Clause)—— 明确写了 "Kalman-based news decomposition",但 3★,属于实验性。[s18]
- ECB 也发了 "Nowcasting Made Easier: a toolbox for economists"(https://www.ecb.europa.eu/pub/pdf/scpwps/ecb.wp3004~3ce9d0d8ca.en.pdf),自述 "the toolbox quantifies the impact of each recent data releases, showing how predictions change as new data becomes available"(DDG 摘要;**发布日未核实,未定级**)。

**对周报的直接用法**:周报的「复盘汇总」目前多半是定性的;news decomposition 给出的是「本周判断修正 = Σ 各条数据的 impact」这种**加总必须闭合**的结构,天然适合做成校验不变量。

### F7 — 开源的 ACH(Analysis of Competing Hypotheses):可用的证伪矩阵实现只有一个还活着 【s16 fresh / s15 stale】

ACH 是 Heuer 在 CIA 提出的对抗确认偏误的方法:列全部竞争假设 × 列全部证据,逐格标 consistent/inconsistent,然后**淘汰不一致证据最多的假设**(而不是挑支持证据最多的)。
- `twschiller/open-synthesis`:213★,`pushed_at` 2026-05-27,AGPL-3.0,Python,自述 "Open platform for CIA-style intelligence analysis"。**活跃**。[s16] [自测 2026-08-14]
- `Burton/Analysis-of-Competing-Hypotheses`:109★,`pushed_at` **2012-01-08**,GPL-3.0,PHP。原始 competinghypotheses.org 的代码,**已停更 14 年,不可用作依赖**。[s15] [自测 2026-08-14]

对本项目的价值不在于跑这两个软件,而在于**矩阵形式本身**:把「本周主线」写成 2–3 个竞争解释 × 本周证据的表,证据栏标 consistent/inconsistent。这与 ICD 203 Std (4) 是同一件事的两种表达。

### F8 — 反面证据:LLM 在宏观推理上的**已量化**失败模式,决定了框架必须外置 【s13 aging(降档后)/ s14 aging(降档后)】

这两条是本任务对「深度和逻辑欠缺」病因的直接证据,也是「为什么不能靠 prompt 说服模型多想一层」的实证:

- **EconCausal**(10,490 条 context-annotated causal triplets,取自 2,595 篇顶刊实证研究)。引自源:"While top models reach 88% accuracy in fixed, explicit contexts, accuracy falls by 32.6~pp on cases that require revising the sign across contexts (73.9% to 41.3%), and drops below 50% once misleading signed evidence is introduced. Models also over-commit to directional (+/-) signs, recognizing null effects only 13.8% of the time while remaining poorly calibrated on these categories."[s13]
  —— 直译到外汇报告:模型**倾向于给方向**,即便正确答案是「没影响」;而且**语境一变就不改口**。这正是「逻辑欠缺」的机器成因。
- **GERB**(60 道研究生微观题 × 38 个模型 × 2×2 组内设计)。引自源:"The clean problems (the control group) are already hard, with the models answering under sixty percent correctly on average. The red herring lowers the probability of a correct final answer by 12.3 percentage points, about a quarter of the models' mean accuracy of 0.525… Reasoning ability confers no protection, as the red herring's effect does not differ detectably across models with and without reasoning ability… The form of the response is preserved even as its substance fails."[s14]
  —— 直译:**一段无关材料就能让结论错掉,而报告的外形完好如初**。对一个每天抓一堆新闻喂进去的外汇日报,这是最贴切的失效模型:噪声新闻不会让报告"看起来变差",只会让结论悄悄变错。

**推论(方法论层面,非源文断言)**:既然「形式完好、实质失败」是可复现的失效模式,那么改善深度就不能靠让模型「写得更详细」——必须靠 F1/F2/F3 这类**外置的、逐条可勾选、且加总必须闭合**的结构。

### F9 — 其余可选结构(优先级较低但已核实存在)

- **Growth-at-Risk(GaR)**:用分位数回归把当前金融条件映射到未来 GDP 增长的**整条分布**,IMF 自述 "Its main strength is its ability to assess the entire distribution of future GDP growth (in contrast to point forecasts)"(DDG 摘要)。[s20] **stale(>3yr),稳定主题**。对外汇报告的可迁移形式:不写点估计,写「本币未来 3 个月的 5% 分位」。存在一篇开源 GaR 模型文章(https://www.sciencedirect.com/science/article/pii/S2666143822000229,自述 "the construction of an open-source growth-at-risk (GaR) model … together with its related online repository"),但 **ScienceDirect 被 CAPTCHA 拦截,`[fetch-failed]`,仓库地址未取到,不作为可用结论**。
- **IPCC 校准语言**:likelihood × confidence 二维,与 ICD 203 属同类但更学术;若已采用 ICD 203 词表则**不必重复引入**。[s21] **stale(>3yr),稳定主题**。
- **Tetlock / Good Judgment 的可解析问题范式**:"Time-bound questions with clear resolution criteria. 'Will X happen by Y date?' can be scored."(ideasthesia.org,DDG 摘要,二手)。对周报「下周关注」的直接约束:每条必须写成有日期、有阈值、事后可判定对错的问句。**未找到权威一手公开 rubric**(GJP 的评分靠 Brier score,不是文本 rubric)。

## Trade-offs(条件性)

- **ICD 203 概率词表 vs IMF RAM 概率档**:若报告要**逐句**标注判断强度 → 用 ICD 203 七档(01-05% … 95-99%),因为它对词形有强制约束、能被字符串校验器检查;若只在**风险表**里标注 → 用 IMF 三档(<10% / 10–30% / 30–50%),因为档位少、主观标注一致性更高。**两套不要混用**——ICD 203 自己就禁止跨行混词。
- **BoE scenario synthesis vs 直接写 2–3 个情景**:若手上已有**外部可观测的参考分布**(期权隐含分布、调查分位数、市场一致预期分位数)→ 值得做 synthesis,能给出「某情景是否多余」的数字答案;若没有参考分布 → 做不了,强行做只是给自编的情景配自编的权重,**比不做更糟**(BoE 自己承认 "statistical grounding leaves it less well suited to exploring judgemental or narrative aspects")。外汇场景下 FX option-implied distribution 是天然的参考分布,但需要期权数据源——本项目当前数据栈是否有,未核实。
- **叙事量化 vs 叙事结构检查**:若目标是**预测** → 证据不支持(Gueta et al. 的负面结论),不要投入;若目标是**报告质量** → 用 Roos & Reccius 的判别式("sense-making story… suggests action to a social group")当检查项,零数据成本。
- **news decomposition 上不上**:若日报已有稳定的多指标快照且要回答「本周判断为何变」→ 值得上,`ropensci/dfms`(46★,rOpenSci 评审过)是唯一够稳的选择,但引入 R 依赖;若只是想让周报「看起来有复盘」→ 不值得,DFM 需要 vintage 数据管理,工程成本远高于收益。
- **ACH 矩阵 vs ICD 203 Std (4)**:两者要求同一件事。若要**轻量落地** → 只做 Std (4)(列 2–3 个替代假设 + 每个的翻转指标);若「本周主线」经常被事后打脸、需要机制性纠偏 → 才值得上完整 ACH 矩阵(证据 × 假设逐格标注),成本高得多。
- **Std (7) 变化说明是低成本高收益项**:日报/周报是 recurrent product,ICD 203 明确要求 recurrent products 必须 note 判断变化且禁止 boilerplate。这一条几乎不增加篇幅,但直接产生跨期的逻辑链条——是所有发现里**成本最低的一条**。

## Deep Read Notes

**[s1] ICD 203(`--fetch --full` 全文,8 页)**
- 结构:5 条 Analytic Standards(Objective / Independent of political consideration / Timely / Based on all available sources / Implements Analytic Tradecraft Standards),第 5 条下挂 9 条 Tradecraft Standards。
- 强制性表述:"All IC analytic products shall be consistent with the following five Analytic Standards, including the nine Analytic Tradecraft Standards.";"The IC Analytic Standards are the foundational assessment criteria for a regular program of review of IC analytic products. Each IC element shall maintain a program of product evaluation using the IC Analytic Standards as the core elements for assessment criteria."
- 概率词表完整原文(引自源,含两行同义词组):第一行 `almost no chance / very unlikely / unlikely / roughly even chance / likely / very likely / almost certain(ly)`;第二行 `remote / highly improbable / improbable (improbably) / roughly even odds / probable (probably) / highly probable / nearly certain`;数值行 `01-05% 05-20% 20-45% 45-55% 55-80% 80-95% 95-99%`。
- Std (8) 有一句反「不敢下判断」的硬话:"should not avoid difficult judgments in order to minimize the risk of being wrong… should express judgments as clearly and precisely as possible, reducing ambiguity by addressing the likelihood, timing, and nature of the outcome or development."
- **注意**:ICD 203 只规定「必须做什么」,不规定「怎么打分」。可打分的 rating scale 是 ODNI 的 AIS 内部工具,公开版需另找(见 Gaps)。

**[s2] IMF UK 2017 Article IV(`--fetch --full`,196,116 字符)**
- RAM 脚注全文已在 F2 逐字引用。RAM 正文列头在 UK 版是三列(`Source of Risks and Relative Likelihood | Expected Impact of Risk | Policy Recommendations`),Algeria 2014 版是五列(多出 `Source of impact`)——**列数各国报告不统一**,五列版对讲机制更有用。
- 概率档的写法值得抄:风险条目正文里直接在括号内挂档位,例如 "Tighter global financial conditions. Fed normalization and tapering by ECB increase global rates and term premia, strengthen the U.S. dollar and the euro vis-à-vis the other currencies, and correct market valuations. Adjustments could be disruptive if there are policy surprises. ( High )" —— 一个风险源下可以有多个子项、各自带档位。
- "Non-mutually exclusive risks may interact and materialize jointly." 这句是 RAM 唯一处理风险相关性的地方,**只是免责声明,没有给方法**。这是 RAM 的真实上限。

**[s6] BoE Scenario Synthesis(`--fetch --full`)**
- 方法链条:情景 → density forecast → 对 reference distribution 做 Bayesian predictive synthesis → 输出 (权重, spanning share)。
- 一个重要的实现细节(引自源脚注 1):"The original work of Adrian et al (2025) distinguishes between the central projection and scenarios, as distinct inputs. However, given that the April 2026 MPR did not contain a central projection, Bank staff have adapted the methodology. In practice, this has been done by removing the constraint that the central projection has a weakly higher weight in the predictive synthesis distribution than the scenarios."
  —— 即:**没有中心预测也能做**,只要放开「中心预测权重不低于情景」这条约束。对没有 baseline forecast 的外汇报告很关键。
- spanning share 的语义(引自源):"if you observed a random inflation outcome drawn from a segment of the reference, it would look statistically consistent with the outcomes implied by the scenario mixture 99 times out of 100."
- BoE 自陈的两个待改进方向:改进 reference distribution 的构造工具;把通胀、增长、Bank Rate 的风险**联合**评估(目前是分开做的,而且两个维度给出的情景权重不一致——通胀维度 A 近零权重,Bank Rate 维度 A+B 合计三分之二)。**同一组情景在不同目标变量上权重不同,这本身是个需要人来解释的信号。**

**[s8] ECB Transmission mechanism(`--fetch --full`)**
- 页面结构本身就是模板:一个总入口节点 + 6 个 `Affects …` 中间节点 + 1 个 `Leads to …` 终点节点,每节点 1–2 段说明机制。
- 汇率在 ECB 官方图里**不是独立渠道**,而是挂在 "Affects asset prices" 之下,且明确给了两条子路径(直接经进口消费品影响通胀 / 经其他渠道)。做外汇报告时若把汇率当成与利率并列的一级渠道,与 ECB 官方口径不符——这是个容易被审查者抓的口径问题。
- 页面同时列了 bank lending channel(量)与 risk-taking channel(风险偏好)的区分:"In addition to the traditional bank lending channel, which focuses on the quantity of loans supplied, a risk-taking channel may exist when banks' incentive to bear risk related to the provision of loans is affected."

## Gaps

- **ICD 203 的公开评分表(Rating Scale)没拿到**。ICD 203 本体只列标准不给分档。学界论文(PMC6330287、alexandrumarcoci.com/ins_icd203.pdf)称使用了 "a modified version of the Rating Scale",两篇都**只有 DDG 摘要,未 fetch**。若要做成可打分的校验器,还需要把这两篇取回来看 Table 1 的具体分档。
- **IMF elibrary 与 ScienceDirect 都被反爬拦住**。`https://www.elibrary.imf.org/view/journals/005/2017/008/article-A001-en.xml` 返回 405 + CAPTCHA;`https://www.sciencedirect.com/science/article/pii/S2666143822000229` 返回 CAPTCHA。两处均 `[fetch-failed]`,相关内容(IMF 内部 Global RAM 的完整说明、开源 GaR 仓库地址)**未取到,未写入结论**。
- **arXiv 短语匹配对本主题几乎无效**。`--arxiv "large language model macroeconomic forecasting"` 与 `--arxiv "macroeconomic forecasting LLM"` 均返回 `total: 0`;换成两词短语 `"narrative economics"`(4 篇)、`"economic reasoning benchmark"`(3 篇)才有结果 [自测 2026-08-14]。宏观 × LLM 的 arXiv 覆盖大概率**仍有遗漏**,本任务的 LLM 侧证据(F8)只建立在 3 篇上。
- **没找到专门评判「宏观/金融研究报告」推理质量的公开 rubric**。F1 的 ICD 203 是从情报分析领域借来的;金融研究侧只找到 CFA/MiFID II 之类的**披露合规**要求,不是推理质量标准。这是本次调研最大的空白——也意味着若要做,只能自建(以 ICD 203 为骨架)。
- **BoE scenario synthesis 的代码未公开**。文章只给方法与结果,没有仓库链接;Adrian et al. FEDS 2025-036 也只查到书目页,**论文正文与附录代码未 fetch**。要复现需要自己实现 Bayesian predictive synthesis。
- **中文侧机构方法论只拿到摘要**。天风《货币传导机制与利率分析框架》[s22]、YY 团队《宏观分析框架:PMI 分析方法》、雪球那份提到 "用金融市场去证伪理论假设和预测" 的 PDF,三者均**只有 DDG 摘要,未 fetch**,不能作为方法论细节的依据。中文机构框架是否有比 F1–F4 更贴外汇场景的东西,**未验证**。
- **NY Fed SR 1152 与 ECB WP 3004 的发布日期未核实**,故 [s19] 与 F6 里的 ECB toolbox 未给 fresh/aging/stale 定级。
- **未覆盖的角度**:BIS 的分析框架(只在 DDG 里出现 BIS Papers No 35,2008,未深读)、FSB 的风险沟通框架、以及各国央行「key judgements」体裁的横向比较,本轮均**未做**。
