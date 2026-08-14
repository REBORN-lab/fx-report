# Adversarial Researcher — LLM 做宏观解读的批评、局限与替代路径

- AS_OF: 2026-08-14
- Depth: SCAN
- 角色: Devil's Advocate。目标是**证伪**「给 LLM 外汇报告加更深的分析框架(传导链条/四环结构/情景分析)能提升深度与逻辑」这条路线。
- 检索量(先跑后抄): `search.py` 调用 **28 次**(含指定的 5 条);WebFetch **17 次**,其中 **3 次失败**(cepr.org 403、arstechnica.com 被封、HN item 49243474 返回 429)。
- 立场声明: 本轮**没有**找到「结构化模板必然降低分析质量」的直接实证。找到的是三类更锋利的间接证据(格式约束伤推理、CoT 可流畅地胡说、宏观/汇率本身近乎不可预测),以及一条对消费者现有设计的**正面印证**。下文逐条标注强度,不做拔高。

---

## Sources

| # | 来源 | URL | Path(怎么找到的) |
|---|---|---|---|
| S1 | Ganum & Atashbar, *How Effectively Can Current LLMs Analyze Macrofinancial Issues?*, IMF Working Paper WP/26/35, Feb 2026 | https://www.imf.org/-/media/files/publications/wp/2026/english/wpiea2026035-source-pdf.pdf | `search.py "LLM macroeconomic analysis problems limitations" 10` 第 1 条 → WebFetch(返回 PDF 二进制)→ `pdftotext -layout` 本地抽全文 1616 行 |
| S2 | Zhao, Tan, Ma, Li, Jiang, Wang, Yang, Liu, *Is Chain-of-Thought Reasoning of LLMs a Mirage? A Data Distribution Lens*, arXiv:2508.01191, 2025-08-02 | https://arxiv.org/abs/2508.01191 / https://arxiv.org/html/2508.01191v2 | `search.py "\"fluent nonsense\" LLM plausible sounding confident wrong" 10` → 顺藤摸到 `search.py "Chain-of-Thought Reasoning Mirage Data Distribution Lens Arizona State fluent nonsense" 10` → WebFetch abs + html |
| S3 | Tam, Wu, Tsai, Lin, Lee, Chen, *Let Me Speak Freely? A Study on the Impact of Format Restrictions on Performance of Large Language Models*, EMNLP 2024 Industry Track, pp.1218–1236 | https://aclanthology.org/2024.emnlp-industry.91.pdf / https://arxiv.org/abs/2408.02442 | `search.py "Let Me Speak Freely format restrictions degrade LLM reasoning structured output" 10` → WebFetch abs + PDF → `pdftotext -layout` |
| S4 | Turpin, Michael, Perez, Bowman, *Language Models Don't Always Say What They Think: Unfaithful Explanations in Chain-of-Thought Prompting*, NeurIPS 2023, arXiv:2305.04388 | https://arxiv.org/abs/2305.04388 | `search.py "Turpin Language Models Don't Always Say What They Think biased chain of thought" 10` → WebFetch |
| S5 | Lopez-Lira, Tang, Zhu, *The Memorization Problem: Can We Trust LLMs' Economic Forecasts?*, arXiv:2504.14765(v1 2025-04-15;此版 2026-08-11) | https://arxiv.org/html/2504.14765v1 | `search.py "LLM macroeconomic analysis problems limitations" 10` 第 8 条 → WebFetch |
| S6 | Ahir & Loungani (IMF), *Fail Again? Fail Better? Forecasts by Economists during the Great Recession*, GWU Research Program in Forecasting Seminar, 2014-01-30 | https://www2.gwu.edu/~forcpgm/Ahir_Loungani.pdf | `search.py "IMF Loungani failure to predict recessions forecast record unblemished" 10` 第 4 条 → WebFetch(PDF 二进制)→ `pdftotext -layout` |
| S7 | Kılıç, *Virtue or Mirage? Complexity in Exchange Rate Prediction*, FEDS 2025-089, Federal Reserve Board, 2025-09-16 | https://www.federalreserve.gov/econres/feds/files/2025089pap.pdf | `search.py "exchange rate forecasting random walk Meese Rogoff puzzle no model beats" 10` 第 8 条 → WebFetch → `pdftotext -layout` |
| S8 | Cutler, Poterba, Summers, *What Moves Stock Prices?*, NBER WP w2538, March 1988 | https://www.nber.org/papers/w2538 | `search.py "Cutler Poterba Summers What moves stock prices news explain largest market moves" 10` 第 1 条 → WebFetch |
| S9 | Carriero, Pettenuzzo, Shekhar, *Macroeconomic Forecasting with Large Language Models*, arXiv:2407.00890 | https://arxiv.org/abs/2407.00890 / https://arxiv.org/html/2407.00890v3 | `search.py "LLM macroeconomic analysis problems limitations" 10` 第 2/4 条 → WebFetch abs + html |
| S10 | Benedict Evans, *The Deep Research problem*, 2025-02-18 | https://www.ben-evans.com/benedictevans/2025/2/17/the-deep-research-problem | `search.py --hn "AI slop research" 20` 中 HN 评论 id=43181894 指向该文 → WebFetch |
| S11 | HN 讨论:*Show HN: Soros – AI for geopolitical macro investing*(2026-03-17, 26 points, 10 comments) | https://news.ycombinator.com/item?id=47418553 | `search.py --hn "AI macro research" 20` → WebFetch 讨论页 |
| S12 | HN 评论(macro 建模怀疑论), on story *Economists made a model of the U.S. economy. Our debt crashed the model* | https://news.ycombinator.com/item?id=44592219 | `search.py --hn "LLM economic forecasting" 20` |
| S13 | HN 评论(时序基础模型一律自称 SOTA), on story *Moirai: A time series foundation model for universal forecasting* | https://news.ycombinator.com/item?id=39824334 | `search.py --hn "LLM economic forecasting" 20` |
| S14 | HN 评论(LLM 输出像星座运势), on story *Humanising LLM Outputs Is Dumb* | https://news.ycombinator.com/item?id=49243474 | `search.py 'site:news.ycombinator.com LLM economics analysis issues' 10` 第 3 条(讨论页本身 WebFetch 遇 429,只用搜索返回的片段) |
| S15 | HN 评论(Deep Research 是伪装成研究的 slop), on story *The Deep Research problem* | https://news.ycombinator.com/item?id=43181894 | `search.py --hn "AI slop research" 20` |
| S16 | Good Judgment, *How Distinct Is a "Distinct Possibility"?*(Tetlock 论 vague verbiage) | https://goodjudgment.com/vague-verbiage-forecasting/ | `search.py "Tetlock vague verbiage forecasts falsifiable precision but trivial predictions wrong side of maybe" 10` |
| S17 | Tetlock, *Expert Political Judgment*(PDF 副本) | https://emilkirkegaard.dk/en/wp-content/uploads/Philip_E._Tetlock_Expert_Political_Judgment_HowBookos.org_.pdf | `search.py "Tetlock expert political judgment forecasting accuracy dart-throwing chimpanzee" 10` 第 5 条 |
| S18 | Kay & King, *Radical Uncertainty: Decision-Making Beyond the Numbers*, W.W.Norton | https://wwnorton.com/books/9781324004776 | `search.py "King Kay Radical Uncertainty critique probability forecasting narrative what is going on here" 10` |

---

## Findings

### F1 `[新]` 结构化模板会伤推理,而且伤害点正好在「字段顺序」上 —— 这是对「四环结构 / 传导链条」最直接的一击

S3(EMNLP 2024 Industry Track)在 GSM8K 等推理任务上直接对比「自由文本」与「受 schema 约束的结构化输出」。摘要逐字:

> "Surprisingly, we observe a significant decline in LLMs reasoning abilities under format restrictions. Furthermore, we find that stricter format constraints generally lead to greater performance degradation in reasoning tasks."

Table 1(GSM8K,无 schema vs 加 schema)逐字数字:

- `gpt-3.5-turbo`:Text **75.99** / JSON **74.70** / XML **60.45** / YAML **71.58**;加 schema constraint 后 JSON 掉到 **49.25**、XML **45.06**。
- `claude-3-haiku`:Text **86.51** / JSON **86.99**;加 schema constraint 后 JSON 掉到 **23.44**(标准差从 0.2 涨到 22.9)。
- `LLaMA-3-8B`:Text **75.13** / JSON **64.67**;加 schema 后 JSON **48.90**、YAML **46.08**。
- 表注逐字:> "Table 1: Comparing results without and with schema constraint, adding schema not only increase the sensitivity to prompt but also degrade in average performance."

**而且作者排除了「只是解析失败」这个良性解释**,逐字:

> "In the LLaMA 3 8B setting, the parsing error rate for the Last Letter task in JSON format is only 0.148%, yet there exists a substantial 38.15% performance gap as seen in Table 1."
> "This finding suggests that the performance differences between formats are not primarily due to parsing errors, but rather to the impact of format restrictions on the LLM's reasoning and generation processes."

**最关键的机制**,逐字:

> "we found that 100% of GPT 3.5 Turbo JSON-mode responses placed the "answer" key before the "reason" key, resulting in zero-shot direct answering instead of zero-shot chain-of-thought reasoning."

对消费者的直接含义:如果「四环结构」或「传导链条」模板里,**结论/判断字段排在推理字段之前**,模型是先答后编理由 —— 拿到的不是更深的分析,是更工整的事后合理化。这条可以立刻在现有 skill 里自查(检查 SKILL.md 里模板字段的书写顺序),成本近乎为零。

同一篇也给了反向证据,不能只取一半 —— 分类类任务上结构化反而更好:
> "These findings suggest format restrictions' impact on LLM performance is task-dependent: stringent formats may hinder reasoning-intensive tasks but enhance accuracy in classification tasks requiring structured outputs."

所以准确结论是:**「把事实抽取/打标做成结构化」是安全的;「把因果推演做成填空题」是有代价的**。消费者现有的「数字逐字溯源 + 要点表」属于前者,而拟议中的「传导链条」属于后者。

---

### F2 `[新]` 「让胡说更像样」这个担忧有正式论文命名,而且原文点名了金融

S2(arXiv:2508.01191)摘要逐字:

> "we reveal that CoT reasoning is a 'brittle mirage' when it is pushed beyond training distributions, emphasizing the ongoing challenge of achieving genuine and generalizable reasoning."

正文逐字(WebFetch 自 https://arxiv.org/html/2508.01191v2):

> "The ability of LLMs to produce 'fluent nonsense'—plausible but logically flawed reasoning chains—can be more deceptive and damaging than an outright incorrect answer, as it projects a false aura of dependability."

> "CoT should not be treated as a 'plug-and-play' module for robust reasoning, especially in high-stakes domains like medicine, finance, or legal analysis."

这是本轮**最贴靶心**的一条:作者的结论不是「CoT 无效」,而是「CoT 在分布外时产出的是流畅的错误,比直接答错更难被发现,因为它披着可靠的外壳」。一套「传导链条 / 四环结构」模板恰恰是在**强制**模型对每一个事件都生成一条完整的推理链 —— 包括那些根本没有可靠传导关系的事件。模板保证了链条的**形式**总是完整的,不保证链条**存在**。

S4(Turpin et al., NeurIPS 2023)给出这个现象的量化版本,摘要逐字:

> "we find that CoT explanations can systematically misrepresent the true reason for a model's prediction."
> "This causes accuracy to drop by as much as **36%** on a suite of 13 tasks from BIG-Bench Hard, when testing with GPT-3.5 from OpenAI and Claude 1.0 from Anthropic."
> "CoT explanations can be plausible yet misleading, which risks increasing our trust in LLMs without guaranteeing their safety."

Turpin 的实验设计对消费者尤其刺眼:偏置是通过**改变 prompt 里选项的排列顺序**注入的,模型系统性地**不提**这个偏置,却给出了看起来合理的推理。换到外汇场景:如果模板里的「四环」顺序本身暗示了某种因果方向(比如总是「政策→利差→资金流→汇率」),模型会顺着模板铺出链条,而不会说「这次其实是流动性/仓位驱动,和政策无关」。

---

### F3 `[印证已知 + 新]` IMF 自己做过「LLM 分析宏观金融」的实测:能用,但有系统性乐观偏差,且开放式判断题上明显失灵

S1 是本轮唯一一篇**直接测量 LLM 做宏观金融分析质量**的权威实证(IMF WP/26/35, 2026-02)。用 2016–2024 的 Article IV staff reports、以人类经济学家评分为基准。摘要逐字:

> "our findings indicate that the latest models can meaningfully assist economists, achieving an average accuracy of **71-75%** on ratings and an average exact match rate of **76-81%** on binary questions in 2024 across advanced GPT models. However, we find that LLMs tend to assign higher, less-dispersed ratings than human experts and struggle with open-ended questions that require deep contextual judgment."

结论章逐字:

> "A consistent upward bias in ratings indicates that models tend to provide more favorable assessments than human counterparts, underscoring the risk of systematic optimism. Additionally, the models struggle with nuanced, open-ended questions where context, interpretation, and judgment are essential. These shortcomings make it clear that LLMs cannot yet substitute for expert economic analysis."

**三条对「加深度」路线的具体反证:**

(a) 模型是按**关键词/章节是否出现**打分,不是按论述深度打分。逐字:
> "the LLM might be giving significant weight to the mere presence of certain keywords or sections (e.g., a discussion of systemic risk) without fully evaluating the depth or quality of that discussion—a task that human experts may be better equipped to handle."

→ 直接推论:引入「四环结构」后,**「四环都写满了」会被误读为「分析变深了」**,包括被 LLM 自评/自查环节误读。这正是「结构化幻觉」的机制。

(b) 模型逐份文档孤立评估,缺少跨样本归一化。逐字:
> "while human reviewers may implicitly 'grade on a curve,' naturally aiming for a normal distribution of scores relative to the peer group, the LLM evaluates each document in isolation against the prompt's criteria, lacking the internal mechanism to normalize the distribution across the sample."

→ 对日报/周报的直接含义:模型没有「今天到底算不算重要」的横向尺度。每天都会给出「结构完整、语气笃定」的一份,哪怕当天什么都没发生。**体裁本身逼着它每天产出等量的分析。**

(c) 开放式题目上的劣势是统计显著的。回归表里逐字:`Type = 2, Open-ended  -0.2968***` 与另一规格下 `-0.5083***`(两处均为 `***`)。

(d) 精度指标的定义里,IMF 自己用了「hallucinating quality」这个词,逐字:
> "Precision is critical in this context as it measures the model's trustworthiness—specifically, how often the LLM avoids 'hallucinating quality' (i.e., rating a weak report as high)."

**`[印证已知]` 的一半 —— 这条对消费者是好消息**,逐字:

> "The requirement to provide a direct quote and justification acted as a way for the model to "show its work," allowing for human oversight to catch these interpretative differences."

IMF 独立地得出了和消费者现有设计相同的结论:**强制引原文 + 强制给理由,是能实际抓到错误的**。消费者的「数字逐字溯源」不是过度工程,是这篇论文明确背书的做法。反过来说,这也说明消费者已经拿到了这条路线上最主要的那份收益;再往上叠模板,边际收益未必在同一个量级。

---

### F4 `[新]` 被解读的对象本身近乎不可预测 —— 汇率尤其如此,「加复杂度」在 FX 上有专门的失败记录

S7 是美联储 2025 年的工作论文,做的正是「把复杂度加上去能不能改善汇率预测」这个实验。摘要逐字:

> "Our results offer a cautionary perspective. Complexity delivers only modest, localized gains: in very small samples with rich predictor sets, Ridge–RFF can outperform linear regression. Yet these improvements never translate into systematic gains over the random walk."
> "Market-timing analyses reinforce these findings: complexity-based strategies yield occasional short-sample gains but are unstable and prone to sharp drawdowns, whereas simpler linear and random walk strategies provide more robust and consistent economic value."
> "we show that apparent gains from complexity are fragile and rarely statistically significant. Overall, our evidence points to a limited virtue of complexity in FX forecasting: complexity may help under narrowly defined conditions, but parsimony and the random walk benchmark remain more reliable across samples, predictor sets, and economic evaluations."

正文逐字:
> "This 'random walk benchmark' — typically a no-change forecast — remains notoriously difficult to outperform in out-of-sample tests."

这是**方法论上的同构警告**:该论文测的是数学复杂度(Random Fourier Features),消费者拟议的是叙事复杂度(传导链条/四环/情景)。二者共享同一个失败模式 —— 在小样本上看起来有增益,在样本外不稳定,且增益「rarely statistically significant」。要用它反驳我,消费者需要拿出「加了框架之后判断准确率在样本外提升」的证据;目前的设计里没有这个测量装置(见 Gaps G1)。

宏观拐点同样如此。S6(Ahir & Loungani, IMF)逐字:

> "The record of failure to predict recessions is virtually unblemished"(引自 Loungani, 2001, *International Journal of Forecasting*)
> "Fail Again: Economists were not able to predict too many recessions over this period, particularly in advance. Generally, recessions arrived before they were forecast"
> "Fail Better: though recessions occurring in 2009 were not predicted a year in advance, the number of recessions was actually over-predicted over the course of 2009."

样本:77 个国家,2008–12。图表标注的衰退实际发生数逐年为 **13 / 49 / 7 / 4 / 15**(2008–2012)。「Number of recessions predicted by April of the year in which the recession occurred」图中 2009 年标注为 **54** —— 即当年 4 月已经**过度**预测(54 > 49),而年前预测数接近零。
> ⚠️ 数字来源是柱状图上的数据标签,经 `pdftotext -layout` 抽取。49 与 54 两个标签位置无歧义;**年前(t-1)那张图的逐年数值 OCR 有歧义,我不引用**。定性结论以上面那段逐字正文为准,不以 OCR 出的柱值为准。

S8(Cutler-Poterba-Summers, NBER w2538, 1988)从另一头切:即使事后,新闻也解释不了市场波动。逐字:
> "First, we consider macroeconomic news and show that it is difficult to explain more than **one third** of the return variance from this source."

→ 这条是对「宏观日报体裁」最直接的价值质疑:**日报的默认动作是把当天的价格变动归因到当天的新闻上。有 2/3 以上的方差原则上归不上去。** 一个每天都产出因果叙事的体裁,结构上被迫在大多数日子里生成无法证成的归因。这不是 LLM 的毛病,是体裁的毛病 —— 换人来写也一样。

---

### F5 `[与已知冲突]` 「可证伪触发条件」当质量指标:我**没找到**说它诱导平凡判断的实证;文献主流恰恰站在它这边

靶子里问「把可证伪触发条件当质量指标是否会诱导写出平凡但必然可判的判断」。我按要求找了(`Tetlock vague verbiage...`、`Goodhart law forecasting tournament easy questions gaming Brier score`、`Brier score decomposition calibration resolution climatology`),**结论是找不到强批评,而且现有文献是反方向的**:

Tetlock 的立场逐字(S16 引 Tetlock):
> "Vague expectations about indefinite futures are not helpful"
> "Fuzzy thinking can never be proven wrong."

以及(同源报道 Tetlock 论组织内预测):
> "They're also interested in making forecasts that are going to be difficult to falsify so they can't be embarrassed. So a lot of the forecasting inside organizations doesn't involve numbers. It involves a lot of vague verbiage."

即:Tetlock 认定的失败模式是**回避可证伪**,不是滥用可证伪。消费者现有的「触发条件 + 时限」设计,方向上和 Tetlock 一致。**这条我不为了让批评成立而夸大。**

真正成立的那个更窄的批评,是从评分规则的分解来的,不是从 Tetlock 来的:Brier score 可分解为 **reliability(校准)/ resolution(分辨力)/ uncertainty**(Murphy 分解,S: `search.py "Brier score decomposition calibration resolution climatology forecast no skill" 10`,如 https://rmets.onlinelibrary.wiley.com/doi/10.1002/qj.2985 「The decomposition of the Brier score into Reliability, Resolution and Uncertainty has become a standard method in forecast verification.」)。

含义是:一条「必然可判」的预测,可以做到**校准完美而分辨力为零** —— 即永远吐出基准率、从不做区分。可证伪性只约束 reliability 那一项,不约束 resolution。所以风险不是「触发条件是坏指标」,而是「**只看触发条件是否被判定,不看它有没有偏离基准率**」。这落到 Goodhart 的一般形式上:当「可判定率」成为目标,它就不再衡量「判断力」。

**给消费者的可执行版本**:除了记录「触发条件是否命中」,还要记录「命中时,该判断相对无脑基准(汇率取 no-change / 随机游走;事件取历史基准率)是否有增量」。没有这第二项,现有的可证伪机制在数学上无法区分「有洞察」和「说了句必然发生的话」。这一步是把 F4 里那个「缺失的测量装置」补上。

⚠️ 强度声明:上述 Murphy 分解的论证是我从文献做的推演,**不是**某篇论文针对 LLM 报告写的批评。我没有找到任何直接针对「LLM 报告 + 可证伪触发条件」的实证研究。

---

### F6 `[新]` 一条相邻的、已知的重灾区:回测「加了框架之后更准了」会被记忆污染

如果消费者打算用历史数据验证「加框架后判断更准」,S5 是必须先读的。摘要逐字:

> "Large language models (LLMs) cannot be trusted for economic forecasts during periods covered by their training data."
> "when testing forecasting capabilities before their knowledge cutoff dates, we cannot distinguish whether LLMs are forecasting or simply accessing memorized data."
> "Explicit instructions to respect historical data boundaries fail to prevent LLMs from achieving recall-level accuracy in forecasting tasks."

数字逐字(WebFetch 自 https://arxiv.org/html/2504.14765v1):
- GPT-4o 在人为设定 2010 cutoff 下的 GDP 方向性准确率 **97.6%**;cutoff 之后掉到 **40%**(仅 5 个观测)。
- S&P 500 指数复现的 MAPE:cutoff 前 **0.61%** vs cutoff 后 **16.70%**。
- 新闻标题日期识别:cutoff 前 **90.38%** 月+年准确率 vs cutoff 后 **20.71%**。

→ 直接含义:**任何在训练截止日之前的时间段上做的 A/B(旧模板 vs 新模板)都是无效的**。要证明框架有用,只能做前瞻(forward)评估。这也把 F5 里那个「补测量装置」的建议钉死成了「只能向前测,不能回测」。

---

### F7 `[新]` 同类产品已经把这条路线走到头了,而且被同一个问题问倒

S11 是最接近消费者拟议方案的公开产品:HN Show 帖 *Soros – AI for geopolitical macro investing*(2026-03-17)。作者描述的流程,逐字节选:

> "(1) first analyze and perform deep research on it, running scores of searches in parallel to gather deep context…identify the landscape of key decisions…generate forward-looking scenarios…engage a full-blown Monte Carlo simulation engine and generate thousands of trajectories to estimate relative probabilities…analyze each scenario to generate likely capital flows and identify the sectors, industries, companies, currencies, and commodities most affected"

这就是「传导链条 + 情景分析」的极致版本 —— 八步流水线、蒙特卡洛、上千条轨迹。HN 上第一条实质回应(用户 Reubend)逐字:

> "Where's the data on accuracy? Backtesting is difficult to do correctly with LLMs, but because this is marketed as being for macro investing, I would expect to see a level of rigor and quantitative analysis consistent with that."
> "is there evidence to indicate that it generates superior results to expert predictions, or to LLMs alone?"

作者回复逐字:
> "we don't have any formal calibration data yet"

(引用页:https://news.ycombinator.com/item?id=47418553)

**这就是本轮最实用的一条**:框架深度可以无限堆(八步、蒙特卡洛、上千轨迹),但堆到头之后,被问的还是同一个问题 —— 校准数据在哪。**「更深的框架」不产生这个问题的答案,它只是把这个问题往后推。** 消费者现在做「更深的框架」,一年后会站在 Soros 作者今天站的位置。

S10(Benedict Evans, 2025-02-18)从消费端说同一件事,逐字:
> "If there are mistakes in the table, it doesn't matter how many there are—I can't trust it."
> "Deep Research will be mostly right, but only mostly."
> "We're asking for a deterministic answer from a probabilistic question, and there it looks like the model really is failing."

HN 上对同一篇的评论(id=43181894)逐字:
> "AI slop already produces many plausible-sounding articles used as infotainment and in academia. We already know this slop adds much noise to the signal and that poor signal slows actual research in both cases. But until now, the slop wasn't masquerading specifically as research!"

(引用页:https://news.ycombinator.com/item?id=43181894)

S14(HN,on *Humanising LLM Outputs Is Dumb*)对「结构化空话」的口语化描述,逐字:
> "If you've ever looked over the shoulder of somebody naively prompting an LLM about some broad issue, they're being fed this horoscope-like analysis where a bunch of vague stuff gets thrown at the prompter, and whatever they respond to is what the machine starts iterating on."

(引用页:https://news.ycombinator.com/item?id=49243474。⚠️ 该讨论页 WebFetch 返回 429,上述逐字文本取自 `search.py 'site:news.ycombinator.com LLM economics analysis issues' 10` 返回的 snippet,**未能核到原页**,按低置信度对待。)

---

### F8 `[印证已知]` 「LLM 做宏观预测」在纯数值维度上也没有跑赢传统方法

S9(Carriero, Pettenuzzo, Shekhar)在 FRED-MD 上系统评测。正文逐字(https://arxiv.org/html/2407.00890v3):

> "only two of the five models we evaluated, Salesforce's Moirai and Google's TimesFM, consistently outperform a simple autoregressive benchmark."
> "struggle to deliver consistently superior forecasts compared to established macroeconomic forecasting methods such as Bayesian Vector Autoregressions (BVARs) and Factor Models."
> "the forecasting gains achieved by the econometric models tend to be more stable while TSLMs can perform very well for a handful of series but also show less reliability at times."

数据污染的自认,逐字:
> "three out of five of them (including the best performing one, Moirai) list in their training data a large subset of the series we set out to forecast in this paper."
> "even including the dataset of interest in real time would not remove the issue of a contaminated training set, i.e. including information that the forecaster would not have access to in real-time."

⚠️ 重要限定:**这篇测的是时序基础模型(TSFM/TSLM,如 Moirai、TimesFM),不是对话式 LLM。** 标题里的 "Large Language Models" 容易误读。它对消费者的相关性是间接的:说明即使在最有利于机器的纯数值赛道上,增益也不稳定且被污染问题笼罩。

HN 上一条更早的同调评论(S13)逐字:
> "There are over a dozen transformers-based foundation time series model released in the past year and without fail, every one of them claims to be at or near SOTA."

(引用页:https://news.ycombinator.com/item?id=39824334)

---

### F9 `[新]` 替代路径:三条,按落地成本排序

从上面的证据反推,而不是从「什么听起来更高级」反推:

**替代 A(最低成本,最高确定性)—— 改字段顺序,而不是加字段。**
依据 F1:JSON-mode 100% 把 `answer` 排在 `reason` 前导致「先答后编」。检查现有 SKILL.md 模板,确保**任何结论/判断字段在其依据字段之后**。若已如此,记录为已满足;若否,这是零成本的真实改进,且效果方向有实证支持。

**替代 B(中成本)—— 加测量,而不是加框架。**
依据 F4 + F5 + F6:现在缺的不是分析深度,是「深度是否有用」的判据。具体做法:
1. 每条带触发条件的判断,同时记录一个**无脑基准**(汇率:no-change / 随机游走;事件:历史基准率)。
2. 到期结算时记录三元组:判断是否命中、基准是否命中、二者是否不同。
3. 只在**前瞻**样本上统计(F6:回测被记忆污染,无效)。
积累若干周之后,才有资格回答「框架有没有用」。**没有这一步,「加框架」和「不加框架」在证据上不可区分**,只能靠观感判断 —— 而观感正是 F2/F3 说的、最容易被结构化幻觉欺骗的通道。

**替代 C(体裁层面)—— 承认日报里大多数天没有可归因的因果,并让格式允许「今天没有」。**
依据 F3(b)(模型缺跨样本尺度,每天都会给出等量笃定的分析)+ F8/S8(新闻解释不了 2/3 以上的方差)。可操作形式:让脚本(不是模型)基于波动阈值/日历事件判定「今天是否值得写因果段」,不达标的日子只出数据与基准,不出叙事。这与消费者已有的「结论由脚本给出」不变量同构 —— 是把同一个不变量从「结论」扩展到「是否该有结论」。

**一条我不推荐的替代**:S18(Kay & King, *Radical Uncertainty*)主张用叙事("What is going on here?")替代概率化预测。这条路线和消费者现有的「可证伪触发条件」直接冲突,且 Tetlock 一方的证据(F5)更硬。列出仅为完整性,不建议采纳。

---

## Gaps

**G1 — 最大的缺口:没有任何研究直接测过「结构化分析模板对金融/宏观报告质量的影响」。**
F1(S3)测的是数学与符号推理任务,不是宏观叙事;F2(S2)在 DataAlchemy 合成环境里训练模型,不是真实金融文本;F3(S1)测的是 LLM 给报告**打分**的能力,不是 LLM **写**报告的能力。三者都需要一步外推才能落到消费者的场景上。**我没有找到「给 LLM 财经报告加传导链条模板,前后对比质量」的实证。**这个缺口是真实的,不应该被上面的论证掩盖 —— 换句话说,F1/F2 是强烈的**警告**,不是**定论**。

**G2 — 「宏观日报体裁价值有限」缺少直接论证。**
最接近的是 S8(新闻解释不了 1/3 以上方差,1988 年,标的是美股不是外汇)。我搜了 `daily market commentary narrative post-hoc explanation worthless financial news noise` 和 `--hn "financial newsletter daily market commentary useless"`(后者返回 **0 条结果**),没有找到任何直接论证「每日宏观评论体裁本身无价值」的严肃来源。**如实报告:这条批评我找不到强支撑。**

HN 上能找到的只是泛泛的宏观怀疑论,而且发言者自己承认它已成为套话 —— S12 逐字:
> "I feel it's kind of become a cliche trend now driven by the likes of Naval et al to shit on macroeconomics. While I never took the models I studied or created to be scientific, I always found them useful to frame the economic world we lived in. Even if those assumptions rarely predicted outcome or achieved repeatability."

(引用页:https://news.ycombinator.com/item?id=44592219)这条**不能**当作支持「日报无价值」的证据 —— 它恰恰说的是「即使预测力差,框架仍有用」,方向上对消费者是中性偏正面的。列在这里是为了不让读者以为 HN 上存在我没引的强批评。

**G3 — 三次抓取失败,相关证据未能核实。**
(a) cepr.org VoxEU 专栏「There will be growth in the spring: How well do economists predict turning points」返回 **403**,该文里的转折点预测统计未取到,只能用 S6 的会议 slides 代替;
(b) arstechnica.com 被本地策略拒绝,S2 的媒体解读未取到 —— 但 "fluent nonsense" / "false aura of dependability" 两句已在**论文原文**(arxiv.org/html/2508.01191v2)核到,不依赖二手报道;
(c) HN item 49243474 返回 **429**,S14 的逐字文本仅有搜索 snippet,**未核到原页**。

**G4 — S6 的柱状图数值有 OCR 歧义。**
「recessions predicted by April of the previous year」那张图的逐年数值我读不确定,已在 F4 中明确标注不引用。若这个数字对最终报告重要,需要人工看原 PDF 第 6 页确认。

**G5 — Tetlock 的原始统计未逐字核到。**
「284 experts / 27,450 judgments」等数字来自二手来源(Irish Times 等),S17 的 PDF 我没有下载核对。F5 只引用了立场性表述,未引用统计数字。若最终报告要用「dart-throwing chimpanzee」的具体数字,需要另行核实。

**G6 — 没有找到任何「LLM 报告加框架后被独立第三方评估」的开源项目或 benchmark。**
S11(Soros)是最接近的产品,但作者自认无校准数据。这意味着即使消费者做了替代 B,也没有外部基线可比。
