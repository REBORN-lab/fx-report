# 宏观经济解读的开源 skill 与项目:现状、可抄的机制、以及「加深度」这条路的实测风险

**日期**: 2026-08-14 | **方法**: Claude Research (super-research) | **模式**: Standard

---

## Executive Summary

1. **「宏观经济解读」专用的成熟开源 skill 不存在。** 过 500 stars 的**恰好只有一个** —— `komako-workshop/digital-oracle`(775★),第二名断崖跌到 189★ `[自测 2026-08-14]`。GitHub 上 `claude skill macro economics` 全网只有 3 个仓库、最高 2 stars `[自测 2026-08-14]`。这个品类是空的,不是我们没找到 [36]。

2. **但「报告质量机制」有成熟的现成品可抄,而且最好的一份不在开源社区,在情报体系。** ICD 203 是一份现行有效的**强制性成品评审 rubric**,九条标准里五条直接对上我们的缺口,其中第 7 条(周期性产品必须说明本期判断相对上期有何变化、且不得用模板套话)几乎零成本 [1]。

3. **⚠ 最重要的一条:结构化模板会实测降低推理质量,受损点是字段顺序。** `claude-3-haiku` 在 GSM8K 上由自由文本 86.51 掉到 JSON schema 下 23.44,作者排除了解析错误;机制是 `100% of GPT 3.5 Turbo JSON-mode responses placed the 'answer' key before the 'reason' key` [13]。**我们刚做的四环改造正踩在这条边上** —— 修法零成本,见 §5.1。

4. **「填满了的四环」会被读成「有深度」,包括被 LLM 审计器读成有深度。** IMF WP/26/35 实测 LLM 评分器按关键词与章节存在性打分,`without fully evaluating the depth or quality of that discussion` [12]。这条同时否定了「用 LLM 自动审计报告质量」这条捷径。

5. **同一篇 IMF 论文独立支持了我们已有的做法**:要求直接引语加理由 `acted as a way for the model to 'show its work,' allowing for human oversight to catch these interpretative differences` [12]。**这一条我们已经拿到了**,不需要再投入。

6. **有一个我让对抗任务去找、但文献里站不住的批评**:「把可证伪触发当质量指标会诱导平凡判断」—— Tetlock 诊断的失败模式恰恰是**回避**可证伪性 [27][28]。站得住的窄版本来自 Murphy 分解:可证伪性约束校准度、不约束分辨力,所以触发条件可以完美可判却相对基准率零技能。**修法是给每个触发同时记一条朴素基准(不变/随机游走)。** [confidence: low —— 该推论由子代理标注为自身推断,非已发表批评]

7. **验证方法本身有个坑**:GPT-4o 在训练截止前的 GDP 方向准确率 97.6%、截止后 40%,且明确指示它尊重数据边界**无效** [16]。**拿历史数据做新旧模板 A/B 是无效的,测量只能向前做。**

---

## 1. 这个品类到底有什么 [confidence: high]

### 1.1 宏观解读方向:近乎空白

| 项目 | stars | 定位 | 维护状态(取自 `--gh-activity`,非二手文章) |
|---|---:|---|---|
| `komako-workshop/digital-oracle` [36] | 775 | 中文宏观解读 Skill,从市场定价数据回答宏观问题 | 末次提交 2026-07-26;**36 commits、单一贡献者、零 release** |
| `LLMQuant/skills` | 189 | 泛量化 skill 合集 | 近乎静止(4 commits / 75 天) |
| `zayrhabeeb/macro-toolkit` | 0 | nowcasting / 收益率曲线 / 通胀分解 | 已 Drop(T5,零社区验证) |

**`digital-oracle` 是唯一把宏观解读的「逻辑深度」写成硬性流程的**:分歧分析 / 时间分层 / 信号权重三项作为**独立强制章节**,核心原则 `Don't vote by majority.`,输出模板末尾强制「观察信号 + 触发阈值」表 [36]。

**但有两条限定必须一起说:**
- 它的世界观是 `Never cite analyst opinions.`、刻意拒绝新闻文本,与「引政策新闻做事件面归因」直接冲突。**只能借结构,不能照搬取材口径。**
- 它自己的文档对数据源数目有四处互不一致的表述(README 13 / SKILL.md 表头 14 / 表下正文 15 / 实测 provider 文件 19)`[自测 2026-08-14]`。**其自述数字不可直接引用**(见 §6 第 1 对矛盾)。

### 1.2 星标最高的两个项目,GitHub 关键词搜索完全看不见

这是本轮覆盖审计的核心发现,也是它存在的理由:

| 项目 | stars | 为什么 Layer 1 看不见 |
|---|---:|---|
| `OpenBB-finance/OpenBB` [38] | **71856** | description 写 "Open Data Platform",从不含 "macroeconomics" |
| `akfamily/akshare` [39] | **22022** | description 写 "financial data interface library" |

**90 倍量级的项目对按关键词 + stars 排序的检索完全不可见**,只有 DDG 与生态语境查询捞得到。这两个是数据层,不是解读层——但它们的存在说明:**问「有没有开源项目」时,按主题词搜 GitHub 会系统性漏掉这个领域最大的东西。**

### 1.3 你给的那个仓库:与预期不符,须更正

`RKiding/Awesome-finance-skills`(2775★ / 362 forks / Apache-2.0)[37] 实测是 **A 股个股导向**,「宏观」只作为新闻信源标签出现。`pushed_at 2026-03-29`、末次提交同日,按 Agent 生态快变主题降档判为 **stale**。README 只文档化 8 个 skill,实际有 10 个目录。

代码层面有三处问题:`report_agent.py` 第 150–174 行与 180–204 行几乎逐字重复、中间夹截断碎片;`alphaear-signal-tracker/SKILL.md` 自承 `This skill is currently a pattern extracted from FinAgent.`;每个 skill 目录各复制一整份代码树。

**它确实有两处值钱的,而且增量在中文源码里、不在英文 `PROMPTS.md`**:`scripts/prompts/report_agent.py` 含「**分歧评估 (Entropy)**:识别各章节中观点冲突或确定性不一之处」,以及「引用规范(稳定 CiteKey)…不要使用 `[[1]]` 这类不稳定编号」。后者正对上「数字白名单是无序词袋」这个老毛病。

**结论:抄 prompt 文本,不装 skill。**

---

## 2. 可抄的机制:按可移植性排序 [confidence: high]

### 2.1 ICD 203 —— 本轮最值钱的一份 [1]

美国情报体系的 Analytic Standards,**强制性成品评审 rubric**,现行有效。九条标准里五条直接可移植:

| 标准 | 内容 | 对上我们的哪个缺口 |
|---|---|---|
| 概率词表 | 概率词绑定数值区间 `01-05% … 95-99%`,**明令禁止**混用不同词表行、禁止把置信度与可能性写进同一句 | 现在的「关注」「可能」无数值锚 |
| Linchpin assumptions | 必须写明关键假设 + 假设不成立时判断会怎样 | 四环的「传导」环没有显式假设层 |
| 翻转指标 | `indicators that, if detected, would alter judgments` | 这是可证伪结构的可执行版,我们的「失效条件」是它的弱化版 |
| 替代性分析 | 必须给替代解释,每个各带翻转指标 | 现在只有单一叙事 + 反向证据一句 |
| **第 7 条** | 周期性产品(原文点名 `daily crisis reports`)**必须说明本期判断相对上期有何变化,且不得使用模板套话** | **直接治「三个币种实际利率四天一字未变却写了四遍」** |

**第 7 条是最便宜的赢**:近乎零增量篇幅,直接产出跨期逻辑链。

**它是外部清单而非又一条提示词禁令** —— 这正是我们自己的教训所说的、唯一管用的形态。

### 2.2 IMF 风险评估矩阵 [3][4][5][6]

五列:`风险来源 | 相对可能性 | 预期影响 | 影响传导来源 | 政策应对`。

**`Source of impact` 那一列是逼出机制而非相关性的关键。**

**一个必须一起说的坑**:它的概率校准**跨版本不稳定** —— UK 2017 版是 low <10% / medium 10–30% / high 30–50% [3],而 Algeria 2014 版写的是「30 percent or more」[4]。**照抄哪一版要写明版本**,否则就是把不同口径的概率当同一把尺。

### 2.3 BoE 情景合成:给「这个情景值不值得写」一个数值答案 [9][10]

2026 年 4 月 MPR 的三个情景覆盖参考风险分布的 **99%**,去掉情景 C 掉到 **87–89%** [9]。

**前提**:需要一个外部可观测的参考分布(期权隐含或调查分位数)。**我们目前没有,所以这条暂时用不了** —— 记为待办而非可抄项。

### 2.4 开源社区里三个可直接迁移的条目

| 来源 | 机制 | 为什么值钱 |
|---|---|---|
| `MoneyAtlas` [31] | **FAILURE SYSTEM**:无替代情景 / 未提风险 / 无证据却过度确定 / 无失效点 → 判 invalid **强制重评**,仍弱则输出 `⚠️ INSUFFICIENT EDGE` | 把质量写成**输出前的否决式不变量**;另有一条比我们的 `[unverified]` 更硬:标记后**禁止进入结论区**,是隔离不是仅标注 |
| `senior-analyst` [32] | **双轨修复:分析缺口必须同时补内容 + 修方法论,不可只补报告** | 逐字对上我们「同型缺陷反复复发」「先写修复后补靶点」的教训 —— 外部生态对同一失败模式的独立处方 |
| `social-science-claude-scholar` [33] | `devils-advocate`:5–7 条对抗挑战,每条带 Severity(Fatal/Major/Minor)+ **必附解法**;扣分制质量门(`| Critical | Identification assumption not stated | -25 |`,<80 阻断提交) | 可直接迁成校验器条目 |

`econstack` 的 `/econ-audit`(124 项检查 / 17 类,RAG 评级 + A–F 字母分,且 `/cost-benefit` 产出后**自动追跑一遍 audit**)[30] 机制上最贴,但**本轮未取到那 124 项的清单原文**,而它是否只查「存在性」正是第 3 对未决矛盾的核心(见 §6)。**在拿到清单前不得宣称它解决了论证质量校验。**

---

## 3. ECB 官方口径与我们的四环冲突 [confidence: medium]

ECB 官方传导机制页给出 7 节点渠道分解 [8]。**值得注意的是:汇率在 ECB 的官方分类里不是一级渠道**,它挂在「影响资产价格」之下。

我们四环的「传导」环把机制限定为四类(利差 / 风险溢价 / 资金流 / 政策空间),**把汇率当成与利率并列的渠道,与 ECB 自己的框架冲突**。

这不必然是错的——做汇率报告时以汇率为中心是合理的视角——但**当报告引用 ECB 政策传导做归因时,应当采用 ECB 的层级**,否则是在用它的权威支撑一个它不认的结构。

---

## 4. 「加深度」这条路的实测风险 [confidence: high]

### 4.1 结构化格式实测降低推理质量 [13]

| 模型 | 自由文本 | JSON schema |
|---|---:|---:|
| `claude-3-haiku`(GSM8K) | 86.51 | **23.44** |
| `gpt-3.5-turbo`(GSM8K) | 75.99 | **49.25** |

作者排除了解析错误:`parsing error rate ... is only 0.148%, yet there exists a substantial 38.15% performance gap`。

机制是字段顺序:`100% of GPT 3.5 Turbo JSON-mode responses placed the 'answer' key before the 'reason' key, resulting in zero-shot direct answering instead of zero-shot chain-of-thought reasoning`。

### 4.2 「fluent nonsense」是有名有姓的已发表结论,而且点名金融 [14][15]

> `plausible but logically flawed reasoning chains ... can be more deceptive and damaging than an outright incorrect answer, as it projects a false aura of dependability`
>
> `CoT should not be treated as a 'plug-and-play' module ... especially in high-stakes domains like medicine, finance, or legal analysis` [14]

Turpin 等量化到最多 **36%** 准确率下降,且模型**系统性地略去真正的驱动因素** [15]。

### 4.3 三条量化的失败模式 [12][18][19]

| 证据 | 数字 | 对我们的含义 |
|---|---|---|
| EconCausal [18] | 需修正符号方向的语境下 73.9% → 41.3%(**降 32.6pp**);零效应识别率仅 **13.8%** | 「这条消息其实不影响汇率」是最难写对的一类判断 |
| GERB [19] | **一段无关文字**就让准确率降 **12.3pp**,且「回应的形式被保留,实质却已失效」 | 每天吃噪声新闻的报告正踩在这里 |
| IMF WP/26/35 [12] | LLM 评分器按关键词/章节存在性打分,不评估深度质量;且「逐份孤立评估,缺乏跨样本归一化机制」 | **填满的四环会被读成有深度**;模型没有「今天到底重不重要」的量感 |

### 4.4 这条路已经有人走到头并公开了 [44]

HN "Show HN: Soros – AI for geopolitical macro investing" 跑八阶段、蒙特卡洛、上千条轨迹。第一条实质回复是 "Where's the data on accuracy?",作者答 `we don't have any formal calibration data yet`。

**更深的框架不回答这个问题,只是推迟它。**

---

## 5. 可执行结论 [confidence: medium]

### 5.1 立刻做,零成本

1. **生成顺序与呈现顺序解耦。** 先写五个币种节的证据环(驱动 → 传导 → 是否已反映),再写判断环,最后由它们导出速览表与执行摘要;读者看到的顺序不变。当前模板的呈现顺序(执行摘要 → 速览表 → 币种节)若被直接当生成顺序,就是 §4.1 的失败形态 [13]。
2. **加 ICD 203 第 7 条**:每份日报必须写明本期判断相对上期有何变化,禁止模板套话 [1]。

### 5.2 值得做,有明确代价

3. **概率词绑数值区间**,并禁止在同一句里混用置信度与可能性 [1]。代价:要为五币种各定一套词表并长期守住。
4. **把 MoneyAtlas 的否决式不变量搬进校验器** [31]:无替代情景 / 无失效点 / 无证据却过度确定 → 判 invalid。代价:会显著提高出稿失败率,初期需要人盯。
5. **每个触发条件同时记一条朴素基准**(不变 / 随机游走),这样「可判定」不会被误读成「有技能」。[confidence: low,依据为推断而非已发表批评]

### 5.3 不要做

6. **不要用 LLM 自动审计报告的论证质量** —— IMF 实测它按关键词与章节存在性打分 [12]。在拿到 `econstack` 那 124 项清单并按「存在性 / 质量」二分归类之前,这条不改。
7. **不要加厚 persona 与角色设定** —— 2368 条 persona 提示对 100 条无 persona 基线,复现 ECB SPF 50 个季度,结论是 `no measurable forecasting advantage`;真正让 GPT-4o 追平人类专家 panel 的是 `provided with relevant context data` [17]。**喂对数据才提升,加厚人设不提升。**
8. **不要拿历史数据做新旧模板 A/B** —— GPT-4o 训练截止前 GDP 方向准确率 97.6%、截止后 40%,且明确指示它尊重数据边界无效 [16]。**测量只能向前做。**

---

## 6. Key Controversies

**1. 结构化模板:是解药还是毒药?(已调和)**
§2 推荐 ICD 203 等结构,§4.1 的证据说结构化格式实测降低推理质量 [1] vs [13]。两者适用范围不重叠:**ICD 203 是产出之后的评审清单,F1 批评的是产出之时的生成格式约束**。把 ICD 203 当事后清单没有 F1 的问题;把四环当生成时的填空模板则正落在射程内。这对矛盾的实际产出就是 §5.1 第 1 条。

**2. 自动审计器能否测出「深度」?(未决)**
`econstack` 的 124 项检查被推荐为补「只查数字不验论证」的手段 [30],而 IMF 实测 LLM 评分器只查存在性 [12]。**本轮未取到那 124 项的原文**,无法判定它是否恰好落在被批评的那一类里。**要判定还缺**:`econ-audit/` 目录下 124 项检查的逐条原文,按「存在性 / 质量」二分归类。

**3. digital-oracle 的数据源数目(未决)**
其 README 说 13、SKILL.md 表头说 14、表下正文说 15,实测 provider 文件 19 个 `[自测 2026-08-14]`。**同一对象的同一属性有四个数,其自述不可引用。** 要判定还缺:逐个 provider 文件核对哪些真实可用。

**4. 事件面 vs 定价面(结构性分歧,非本轮可裁)**
`digital-oracle` 刻意拒绝新闻文本、只用市场定价数据 [36];我们的日报重心在事件面归因。这是同一问题的两条相反路线。它不是本轮的矛盾对(两份笔记对该项目的描述一致),但它对「新闻事件作为归因基础」构成实质质疑,记在此处。

---

## Risks and Limitations

- **来源质量**:T1–T2 共 29 条,T3 共 16 条,T4 共 1 条(实测按 registry Tier 字段计)。
- **单域门实测 FAIL**:`github.com` 占 14/46 = **30.4%**,超 ≤25% 阈值。未删来源凑数、未把 github.com 当多租户主机重算。详见 registry.md 的处置说明。
- **`scholar` 路径贡献 0 条入册来源**:OpenAlex 按引用数排序对本主题零信号。该主题是 2024–26 的工程实践,没有高引足迹,引用排序结构上找不到它。
- **§4 的三项证据都需要一步外推**:F1 测的是符号推理,F2 用合成训练环境,F3 测的是 LLM **评分**报告 —— 没有任何一项直接测「结构化模板对金融/宏观**报告写作**的影响」。**这是强警告,不是判决。**
- **不存在专门评判宏观/金融研究推理质量的公开 rubric**;ICD 203 是从情报分析借来的。
- **AS_OF 新鲜度**:LLM 类证据按快变主题各降一档后,[13][15][20][21] 已属 stale;结论在 6 个月内应重核。

---

## References

[1] ODNI — ICD 203 Analytic Standards — https://archive.dni.gov/files/documents/ICD/ICD-203.pdf (official, 2015-01-02 / 2022 修订)
[2] IPCC — AR5 Guidance Note on Consistent Treatment of Uncertainties — https://klimareporter.de/images/dokumente/2023/05/AR5_Uncertainty_Guidance_Note.pdf (official, 2010)
[3] IMF — United Kingdom 2017 Article IV Staff Report — https://www.astrid-online.it/static/upload/imf_/imf_uk_artiv_02_18.pdf (official, 2018-02)
[4] IMF — Algeria 2014 Article IV Consultation — https://www.imf.org/external/pubs/ft/scr/2014/cr14341.pdf (official, 2014)
[5] IMF — Republic of Latvia 2025 Article IV Consultation — https://www.imf.org/-/media/files/publications/cr/2025/english/1lvaea2025001-source-pdf.pdf (official, 2025)
[6] IMF — Technical Notes and Manuals 17/08: Assessing Country Risk — https://www.imf.org/-/media/Files/Publications/TNM/2017/tnm1708.ashx (official, 2017-06)
[7] IMF — WP/19/36 Growth at Risk — https://www.imf.org/-/media/files/publications/wp/2019/wpiea2019036.pdf (official, 2019-02)
[8] ECB — Transmission mechanism of monetary policy — https://www.ecb.europa.eu/mopo/intro/transmission/html/index.en.html (official)
[9] Bank of England — Making scenarios add up: spanning risks with scenario synthesis — https://www.bankofengland.co.uk/bank-insights/2026/making-scenarios-add-up-spanning-risks-with-scenario-synthesis (official, 2026-07-16)
[10] Adrian, Giannone, Luciani & West — Scenario Synthesis and Macroeconomic Risk (FEDS 2025-036) — https://www.federalreserve.gov/econres/feds/scenario-synthesis-and-macroeconomic-risk.htm (official, 2025)
[11] Bernanke — Forecasting for monetary policy making and communication at the BoE: a review — https://www.bankofengland.co.uk/independent-evaluation-office/forecasting-for-monetary-policy-making-and-communication-at-the-bank-of-england-a-review/forecasting-for-monetary-policy-making-and-communication-at-the-bank-of-england-a-review (official, 2024-04-12)
[12] Ganum & Atashbar — How Effectively Can Current LLMs Analyze Macrofinancial Issues? (IMF WP/26/35) — https://www.imf.org/-/media/files/publications/wp/2026/english/wpiea2026035-source-pdf.pdf (academic, 2026-02)
[13] Tam et al. — Let Me Speak Freely? A Study on the Impact of Format Restrictions on Performance of LLMs — https://aclanthology.org/2024.emnlp-industry.91.pdf (academic, 2024-11)
[14] Zhao et al. — Is Chain-of-Thought Reasoning of LLMs a Mirage? A Data Distribution Lens — https://arxiv.org/abs/2508.01191 (academic, 2025-08-02)
[15] Turpin et al. — Language Models Don't Always Say What They Think — https://arxiv.org/abs/2305.04388 (academic, 2023-05)
[16] Lopez-Lira, Tang & Zhu — The Memorization Problem: Can We Trust LLMs' Economic Forecasts? — https://arxiv.org/html/2504.14765v1 (academic, 2025-04-15)
[17] Iadisernia & Camassa — Prompting for Policy: Forecasting Macroeconomic Scenarios with Synthetic LLM Personas — https://arxiv.org/abs/2511.02458 (academic, 2025-11-04)
[18] Lee et al. — EconCausal: A Context-Aware Economic Reasoning Benchmark for LLMs — https://arxiv.org/abs/2510.07231 (academic, 2026-05-26)
[19] Akimitsu — Wrong and More Confident: A Field Experiment on LLMs Taking a Graduate Economics Exam — https://arxiv.org/abs/2607.23424 (academic, 2026-07-31)
[20] Carriero, Pettenuzzo & Shekhar — Macroeconomic Forecasting with Large Language Models — https://arxiv.org/abs/2407.00890 (academic, 2024-07)
[21] Gueta et al. — Can LLMs Learn Macroeconomic Narratives from Social Media? — https://arxiv.org/abs/2406.12109 (academic, 2025-02-11)
[22] Wang & Zhou — The Macro Alibi: Subjective Risk Attribution in Analyst Scenarios — https://chenwang.one/files/macro_alibi.pdf (academic, 2026-06-11)
[23] Kılıç — Virtue or Mirage? Complexity in Exchange Rate Prediction (FEDS 2025-089) — https://www.federalreserve.gov/econres/feds/files/2025089pap.pdf (official, 2025-09-16)
[24] Cutler, Poterba & Summers — What Moves Stock Prices? (NBER w2538) — https://www.nber.org/papers/w2538 (academic, 1988-03)
[25] Ahir & Loungani — Fail Again? Fail Better? Forecasts by Economists during the Great Recession — https://www2.gwu.edu/~forcpgm/Ahir_Loungani.pdf (academic, 2014-01-30)
[26] Shiller — Narrative Economics (AER 107(4)) — https://fairmodel.econ.yale.edu/ec439/shiller1.pdf (academic, 2017)
[27] Tetlock — Expert Political Judgment — https://emilkirkegaard.dk/en/wp-content/uploads/Philip_E._Tetlock_Expert_Political_Judgment_HowBookos.org_.pdf (academic, 2005;非授权副本,仅作书目定位)
[28] Good Judgment — How Distinct Is a "Distinct Possibility"? — https://goodjudgment.com/vague-verbiage-forecasting/ (secondary)
[29] Kay & King — Radical Uncertainty — https://wwnorton.com/books/9781324004776 (secondary, 2020)
[30] charlescoverdale/econstack — https://github.com/charlescoverdale/econstack (community, 2026-05-08, 4★)
[31] ElmatadorZ/MoneyAtlas-ClaudeSkill-Agent — https://github.com/ElmatadorZ/MoneyAtlas-ClaudeSkill-Agent (community, 2026-08-04, 53★)
[32] rrred0324/senior-analyst — https://github.com/rrred0324/senior-analyst (community, 2026-06-19, 49★)
[33] HaipingXu/social-science-claude-scholar — https://github.com/HaipingXu/social-science-claude-scholar (community, 2026-03-14, 21★)
[34] tradermonty/claude-trading-skills — https://github.com/tradermonty/claude-trading-skills (community, 2026-08-13, 2636★)
[35] hanlulong/econ-writing-skill — https://github.com/hanlulong/econ-writing-skill (community, 2026-07-20, 530★)
[36] komako-workshop/digital-oracle — https://github.com/komako-workshop/digital-oracle (community, 2026-07-26, 775★)
[37] RKiding/Awesome-finance-skills — https://github.com/RKiding/Awesome-finance-skills (community, 2026-03-29, 2775★)
[38] OpenBB-finance/OpenBB — https://github.com/OpenBB-finance/OpenBB (community, release 2026-04-25, 71856★)
[39] akfamily/akshare — https://github.com/akfamily/akshare (community, 2026, 22022★)
[40] QuantEcon/QuantEcon.py — https://github.com/QuantEcon/QuantEcon.py (community, 2026, 2388★)
[41] twschiller/open-synthesis — https://github.com/twschiller/open-synthesis (community, 2026-05-27, 213★)
[42] Burton/Analysis-of-Competing-Hypotheses — https://github.com/Burton/Analysis-of-Competing-Hypotheses (community, 2012-01-08, 109★)
[43] brycewang-stanford/Awesome-Journal-Skills — https://github.com/brycewang-stanford/Awesome-Journal-Skills (community, 2026, 985★)
[44] HN — Show HN: Soros – AI for geopolitical macro investing — https://news.ycombinator.com/item?id=47418553 (community, 2026-03-17)
[45] HN — 讨论 The Deep Research problem — https://news.ycombinator.com/item?id=43181894 (community, 2025-02)
[46] Benedict Evans — The Deep Research problem — https://www.ben-evans.com/benedictevans/2025/2/17/the-deep-research-problem (journalism, 2025-02-18)

---

## Coverage Self-Assessment

本报告用 5 个子代理、约 40 条检索查询覆盖以下维度:

| 维度 | 覆盖 | 来源数 | 置信度 |
|---|---|---:|---|
| 官方分析标准与 rubric | ✅ | 7 | High |
| 央行/IMF 传导与情景方法 | ✅ | 4 | High |
| LLM 做宏观分析的学术实证 | ✅ | 10 | High |
| 顶级开源项目(stars > 1K) | ✅ | 4 | High |
| 中小开源项目(stars 100–1K) | ✅ | 6 | Medium |
| 长尾项目(stars < 100) | ⚠️ | 4 | Low |
| 批评与局限 | ✅ | 8 | High |
| 非英文来源 | ⚠️ | 2 | Low |
| 商业产品 | ❌ | 0 | — |

### Known Blind Spots

- **单域门实测 FAIL 且未消除**:`github.com` 占 46 条入册来源的 **30.4%**,超 ≤25% 阈值。处置是记录理由而非删来源凑数,该门在本主题上误报的论证见 registry.md,但**门的失败状态未被消除**。
- **`econstack` 的 124 项检查清单原文未取到**。它是否只做「存在性检查」是本报告第 2 条未决矛盾的核心,在拿到前不得宣称它解决了论证质量校验。
- **§4 的三项核心证据均需一步外推**:没有任何一项直接测「结构化模板对金融/宏观报告写作的影响」。F1 测符号推理、F2 用合成训练环境、F3 测 LLM 评分报告。
- **ICD 203 的实际评分量表(AIS Rating Scale)未取到**,两篇描述它的论文只见到检索片段。
- **IMF elibrary(405 + CAPTCHA)与 ScienceDirect(CAPTCHA)被挡**,Growth-at-Risk 的开源仓库地址**未取到,不作为结论陈述**。
- **中文机构框架(天风传导框架、YY PMI 框架)只有检索片段,未取全文**,已从入册来源中 Drop。
- **`scholar` 路径贡献 0 条入册来源**:引用排序对 2024–26 的工程实践主题结构上无信号。
- **商业产品维度完全未搜**(Bloomberg、彭博终端的宏观解读功能、卖方研究平台),本轮范围只覆盖开源。
- **未系统扫描 stars < 50 的项目**。
- **付费通讯与封闭社区讨论未搜索**。
- **本轮引用验证状态(实测)**:`--deep` 通过(`pass: true`、`verified_nothing: false`、深抓 22/22 成功);Layer C `failed: 0`,但 `partial: 5` —— 其中 4 条为 `weak_support`,即被引来源正文支持该主题但未逐字含该声明的全部要素:[27][28] 的 Murphy 分解推论、[36] 的三强制章节描述、[8] 的「汇率非一级渠道」层级判读、[14] 的引语归属。**这四条应视为「主题相关但未逐字核实」,不是已验证。**
- **首轮引用验证 FAIL 的三处已修,记录在案**:①`71,856`/`22,022` 带千分位与源(GitHub API 报 `71856`/`22022`)不逐字;②把**我们自己仓库**的「13 次同型缺陷」挂在了 [32] 名下——那不是该来源的数,已删该数字;③[16] 原引 abs 摘要页而所引数字在全文页,已改引 HTML 全文版。

### Coverage Audit Results
- Mentioned-but-not-found 检查项:9,新增入册:4
- 初检遗漏的高影响项目:4,新增入册:4
- 系统性盲区:**是** —— GitHub 关键词检索对本领域两个最高星项目(OpenBB 71856★、AKShare 22022★)完全不可见,量级差 90 倍

如果你知道本报告遗漏的重要项目或视角,请指出 —— 你的领域知识是任何搜索引擎都替代不了的验证层。
