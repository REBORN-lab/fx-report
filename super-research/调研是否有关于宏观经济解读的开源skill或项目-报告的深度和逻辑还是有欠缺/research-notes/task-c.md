# Task C — 金融/宏观类 Agent skill 生态盘点

- **Role**: Agent Skill Ecosystem Scout
- **AS_OF**: 2026-08-14
- **Depth**: SCAN(点名仓库 `RKiding/Awesome-finance-skills` 深读)
- **Consumer Constraints**: 硬约束「开源 skill 或项目」+「宏观经济解读」;已否决项 (none);novelty-bar =「能改善报告的深度和逻辑」

**新鲜度分档口径**(先按基准分档,再按「Agent 生态属快变主题,各降一档」统一降档):
基准 ≤1 个月 = fresh / 1–6 个月 = aging / >6 个月 = stale;降一档后写作 `基准→降档后`。
判据一律取 `pushed_at` 或本地 `git log -1`(仓库 `updated` 字段只反映元数据触碰,不能当代码活跃度用,凡只有该字段的条目已标注)。

---

## Sources

已跑命令与逐字计数(命令输出直抄):

| # | 命令 | 输出计数(逐字) |
|---|---|---|
| S1 | `--gh-search "awesome finance skills" 30 --sort stars` | `total_available 18 total 18` |
| S2 | `--gh-search "claude skill finance" 30 --sort stars` | `"total_available": 297,` / `"total": 30,` |
| S3 | DDG `"claude skills" finance macro economics github` 10 | `"total": 8` |
| S4 | DDG `site:juejin.cn 大模型 宏观经济 分析 agent` 10 | `"total": 8` |
| S5 | `--hn "LLM macroeconomic analysis" 20` | `"total": 2` |
| S6 | `--gh-search "macroeconomic agent LLM" 30 --sort stars` | `total_available 19 total 19` |
| S7 | `--gh-search "macro research agent skill" 30 --sort stars` | `total_available 3 total 3` |
| S8 | `--gh-search "economics skill claude code" 30 --sort stars` | `total_available 55 total 30` |
| S9 | `--gh-search "financial report generation agent" 30 --sort stars` | `total_available 91 total 30` |
| S10 | `--gh-search "宏观经济 分析 skill" 30 --sort stars` | `total_available 5 total 5` |
| S11 | `--gh-search "langgraph macro economic research report" 30 --sort stars` | `total_available 0 total 0` |
| S12 | `--hn "prediction markets probability forecasting agent" 20` | `"total": 2` |

主要对象(stars/forks/license/pushed_at 均抄自 `--github` 输出;commit 抄自 `git log -1`):

| 仓库 | URL | stars | forks | license | pushed_at / 末次提交 | 新鲜度 |
|---|---|---|---|---|---|---|
| RKiding/Awesome-finance-skills | https://github.com/RKiding/Awesome-finance-skills | `"stars": 2775` | `"forks": 362` | `Apache-2.0` | `"pushed_at": "2026-03-29T05:03:47Z"` / `853f09b4 2026-03-29 doc: update doc` | aging→**stale** |
| komako-workshop/digital-oracle | https://github.com/komako-workshop/digital-oracle | `"stars": 775` | `"forks": 157` | `MIT` | `"pushed_at": "2026-07-26T22:44:52Z"` / `a63e4c19 2026-07-27` | fresh→**aging** |
| hanlulong/econ-writing-skill | https://github.com/hanlulong/econ-writing-skill | `"stars": 530` | `"forks": 85` | `MIT` | `"pushed_at": "2026-07-20T00:11:11Z"` | fresh→**aging** |
| ElmatadorZ/MoneyAtlas-ClaudeSkill-Agent | https://github.com/ElmatadorZ/MoneyAtlas-ClaudeSkill-Agent | `"stars": 53` | `"forks": 13` | `Apache-2.0` | `"pushed_at": "2026-08-04T15:17:30Z"` | fresh→**aging** |
| rrred0324/senior-analyst | https://github.com/rrred0324/senior-analyst | `"stars": 49` | `"forks": 8` | `MIT` | `"pushed_at": "2026-06-19T09:02:05Z"` | aging→**stale** |
| HaipingXu/social-science-claude-scholar | https://github.com/HaipingXu/social-science-claude-scholar | `"stars": 21` | `"forks": 5` | (空) | `"pushed_at": "2026-03-14T13:40:48Z"` / `955c66d2 2026-03-14` | aging→**stale** |

Awesome 列表(仅有 `--gh-search` 的 `updated` 元数据字段,未取 `pushed_at`,新鲜度不判定):

| 仓库 | URL | stars | 一句话 |
|---|---|---|---|
| brycewang-stanford/Awesome-Journal-Skills | https://github.com/brycewang-stanford/Awesome-Journal-Skills | 985 | 期刊导向的 Claude Code/Codex 技能包(AER/QJE/经济研究等) |
| BlockRunAI/awesome-finance-mcp | https://github.com/BlockRunAI/awesome-finance-mcp | 186 | 金融 Agent 的 MCP server 清单 |
| w95/awesome-claude-corporate-skills | https://github.com/w95/awesome-claude-corporate-skills | 155 | 166 个按企业角色分类的 skill,含 finance |
| franklee16/academic-research-skills | https://github.com/franklee16/academic-research-skills | 205 | 经济/金融/社科学术研究 skill 合集 |
| clawpod-app/awesome-openclaw-agent-packs | https://github.com/clawpod-app/awesome-openclaw-agent-packs | 45 | 30 个 OpenClaw agent pack,含 Finance |
| laplace0x/awesome-agent-trading | https://github.com/laplace0x/awesome-agent-trading | 4 | AI agent 交易的工具/skill/API 清单 |
| lj22503/awesome-finai-tools-zn | https://github.com/lj22503/awesome-finai-tools-zn | 4 | 中国金融 AI 工具全景(行情 MCP/量化/券商 skills) |
| agentpit-io/awesome-finance-agent | https://github.com/agentpit-io/awesome-finance-agent | 0 | MCP + agent skill + 金融研究工具清单 |

HN(引讨论页 `hn_url`,两条命中均为评论、`title` 为空,属正常):
- https://news.ycombinator.com/item?id=48497908 (评论,2026-06-11,作者 oudlys)
- https://news.ycombinator.com/item?id=46280579 (评论,2025-12-15,作者 SilentM68)
- https://news.ycombinator.com/item?id=46211009 (评论,2025-12-09,作者 mardariya)
两次 HN 检索各只回 `"total": 2`,且无一条讨论「LLM 做宏观解读」本身。

---

## Findings

### F1 [新] `digital-oracle` 是本次盘点里唯一一个把「宏观解读」当作主题、并且把「逻辑深度」写成硬性流程的 skill

`komako-workshop/digital-oracle`,MIT,775 stars,topics 逐字含 `"macroeconomics"`、`"prediction-markets"`。SKILL.md 共 352 行(`wc -l` 输出 `352`),frontmatter `version: 1.0.3`。

它的「五条铁律」直接对着「深度和逻辑欠缺」下药,逐字:

> 3. **Multi-signal cross-validation** — never conclude from a single signal. At least 3 independent dimensions.
> 4. **Label the time horizon of each signal** — options price 3 months, equipment orders price 3 years — don't mix them in the same vote.
> 5. **Structured output** — the final report must follow the Step 5 template: layered signal tables → contradiction analysis → probability scenarios → signal consistency assessment. Do not substitute prose for structured reporting.

Step 5「数据分析」四维度,逐字要点:

> This is the key to report quality. Don't just summarize data — derive judgment from data.
> 1. **Signal interpretation**: What is each data point saying? Derive meaning from price. Not "gold up 3%" but "the market is pricing in tail risk."
> 2. **Cross-validation**: Which signals point in the same direction (resonance)? Which signals disagree (divergence)? Divergence itself is a high-value signal. e.g., gold says "disaster" but equities say "fine" → two markets pricing different time windows.
> 3. **Time alignment**: Group signals by their pricing horizon. Don't mix signals from different time windows in the same vote.
> 4. **Weight judgment**: Not all signals are equally reliable. Signals backed by real money > surveys. Liquid markets > illiquid markets. Direct pricing > indirect proxies.

以及一条反「多数决」的原则,逐字:

> **Core principle: Don't vote by majority.** When signals diverge:
> - Check the time dimension first — different signals price different future windows
> - Look for "two things happening at once" — old economy Japanification + new economy boom can coexist
> - Consider "direction right but timing wrong" — long-term bullish but short-term overheated → wait for a pullback

以及一条时间分层的判据,逐字:`Short-term bearish + long-term bullish ≠ contradiction, = S-curve inflection`。

输出模板(Step 6)强制四段不可合并成散文,末尾还带一张「观察信号 + 触发阈值」表,逐字表头与示例行:

> ### Signals to monitor
> | Signal | Current value | Threshold | Meaning |
> |--------|--------------|-----------|---------|
> | ... | ... | if crosses X | then Y |
> (3-5 concrete signals with specific trigger levels and what they would imply)

**为什么算新**:consumer 现有周报体系已有「五段式主线 / 一周落点表 / 下周关注」,但**分歧分析(divergence)、时间分层(time alignment)、信号权重(weight judgment)三项作为独立强制章节**,以及「观察信号必须带触发阈值」的写法,是现有做法之外的增量。

### F2 [印证已知] `digital-oracle` 的 BIS 用法逐字印证了「BIS 直连」这一路径,并给出一个易错点

SKILL.md Notes 段逐字:

> BIS `get_credit_to_gdp()` returns the **gap** (deviation from long-run trend, e.g. US ≈ -12pp), not the raw credit-to-GDP ratio (≈ 140%). Pass `series=CREDIT_GAP_SERIES["ratio"]` if you want the level instead. A double-digit positive gap is the classic credit-bubble warning

另一条与利率路径相关的逐字提醒:

> Kalshi `KXFED` series: FOMC rate-decision contracts. (Use this for the rate path — CMEFedWatchProvider is currently 403-blocked by CME's bot protection from every host tested.)

以及一条排版硬伤规避,逐字:

> When reporting dollar amounts, use `USD` instead of `$` to avoid markdown renderers interpreting `$...$` as LaTeX

### F3 [与已知冲突] `digital-oracle` 自身文档三处数字/指向不一致,直接引用其「13 个数据源」的说法会出错

跑数(命令后抄输出):
- `ls digital_oracle/providers/*.py | grep -v __init__ | wc -l` → `19`
- SKILL.md provider 表 `grep -c "^| .*Provider"` → `16`(含表头 1 行,即 **15 个数据行**)
- README 数据源表 `grep -c "^| [A-Z].* | .* | .* |$"` → `14`(含表头 1 行,即 **13 个数据行**)

三处彼此不符:
1. README 中文正文逐字称「它接入了 13 个权威金融数据源」,表也是 13 行:**不含** FearGreedProvider,且列了一行 `Stooq`(SKILL.md 全文未提 Stooq,价格走 `YahooPriceProvider`)。
2. SKILL.md 表头逐字写 `**All 14 Providers:**`,但表下有 15 个数据行。
3. 同页下一行逐字写 `> 13 out of 15 providers have zero external dependencies and zero API keys.` —— 与自己的「14」表头矛盾。
4. 铁律第 5 条逐字指向 `the Step 5 template`,但模板实际在 `### Step 6: Output report`(Step 5 是 Data analysis)。

**含义**:该仓库可借鉴的是**方法论骨架**,不是它的数字自述;任何抄进我方文档的计数必须自己 `ls`/`grep` 复核。

### F4 [新] 点名仓库 `RKiding/Awesome-finance-skills` 深读:8 个已文档化 skill,但仓库里实际有 10 个目录

`--github` 输出逐字:`"stars": 2775`、`"forks": 362`、`"license": "Apache-2.0"`、`"created": "2026-01-31T06:04:45Z"`、`"pushed_at": "2026-03-29T05:03:47Z"`、`"topics": ["agent","agent-skills","finances","fintech"]`。本地 `git log -1` 输出逐字:`853f09b4d0baae747759ed31e21ed5c5b2316a5f 2026-03-29 doc: update doc`。

计数(命令后抄输出):`ls -d skills/*/ | wc -l` → `10`;README 技能表 `grep -c "^| \*\*alphaear"` → `16`(中英双表各 8 行,即 **README 只文档化了 8 个**)。未进表的两个目录是 `alphaear-deepear-lite` 与 `skill-creator`。

README 收录的 8 个 skill 与用途(逐字抄中文表):

| 技能 | 功能描述 | 核心特性 |
|---|---|---|
| **alphaear-news** | 实时财经新闻与热点趋势 | 10+ 信源,Polymarket 数据 |
| **alphaear-stock** | A股/港股/美股行情与基本面 | 股票搜索、OHLCV、个股基本面 |
| **alphaear-sentiment** | FinBERT / LLM 情感分析 | 评分范围: -1.0 ~ +1.0 |
| **alphaear-predictor** | Kronos 时序预测模型 | 结合新闻情绪动态调整 |
| **alphaear-signal-tracker** | 投资信号演化追踪 | 强化 / 弱化 / 证伪 |
| **alphaear-logic-visualizer** | 传导链路图生成 | 输出 Draw.io XML |
| **alphaear-reporter** | 专业研报生成 | 规划 → 撰写 → 编辑 → 图表 |
| **alphaear-search** | 全网搜索与本地 RAG | 支持 Jina / DDG / 百度 |

`alphaear-news/references/sources.md` 的信源里,与宏观直接相关的两条逐字:`| cls | 财联社 | Finance | Real-time financial news, focus on A-shares and macro. |`、`| wallstreetcn | 华尔街见闻 | Finance | Global markets, macroeconomics, and detailed analysis. |`。

**定性**:这是一个**A 股/个股导向**的 skill 套件,「宏观」只作为新闻信源的一个标签出现,不是分析主题。它对本课题的价值在**报告工序**,不在宏观内容本身。

### F5 [新] `alphaear-reporter` 的「聚类 → 撰写 → 编辑」三段工序,以及一条「稳定 CiteKey」纪律

`skills/alphaear-reporter/references/PROMPTS.md` 逐字:

Planner:
> You are a senior financial report editor. Your task is to cluster the following scattered financial signals into 3-5 core logical themes for a structured report.
> 1. **Theme Aggregation**: Group highly correlated signals (e.g., all related to "supply chain restructuring" or "policy tightening").

Writer:
> 1. **Narrative**: Weave signals into a coherent story. Start with Macro/Industry background, then transmission mechanism, finally stock impact.
> 2. **Quantification**: Cite ISQ scores (Confidence, Intensity) to support views.
> 3. **Citations**: Use `[@CITE_KEY]` format. Keys are provided in input.

Editor:
> 1. **Structure**: Ensure H2/H3 hierarchy is correct.
> 2. **References**: Generate `## References` section from source list.
> 3. **Risk**: Generate `## Risk Factors`.
> 4. **Summary**: Generate `## Executive Summary` with a "Quick Scan" table.

更完整的中文版在 `skills/alphaear-reporter/scripts/prompts/report_agent.py`(415 行,`wc -l` 输出 `415`),其中两条比英文 PROMPTS.md 更值得抄:

> 2. **分歧评估 (Entropy)**: 识别各章节中观点冲突或确定性不一之处,规划如何在正文中呈现这些"分歧点"。

> 3. **引用规范(稳定 CiteKey)**: 关键论断必须标注来源引用,使用 `[@CITE_KEY]` 格式。
>     - CiteKey 已在输入信号块中以 `引用: [@KEY]` 提供,请直接复制使用。
>     - 不要使用 `[[1]]` 这类不稳定编号。

以及一条「先定情景再出图」的纪律:

> **【推荐写法:多情景 → 最终归因 → 产出唯一预测图】**
> 你可以在正文里描述多种情景(如:基准/乐观/悲观),但在插入预测图之前,必须明确给出"本报告最终选择的最可能情景"及其归因,然后用 `forecast` 图表做最终总结。

**为什么算新**:consumer 已有「数字溯源校验(白名单)」,memory 里也记着「数字白名单是无序词袋」这一缺陷。**`[@CITE_KEY]` 这种稳定命名键、并明令禁用 `[[1]]` 序号**,正是把「无序词袋」换成「可定位引用」的一条现成写法;「分歧评估(Entropy)」把冲突当规划对象而非事后补丁,也是增量。

**质量警告(实读到的缺陷)**:`report_agent.py` 第 150–174 行(「✅ 正确示例」→「关键要求」→「### 核心:图表叙事」)与第 180–204 行**几乎逐字重复**,中间第 176–178 行还夹着一段截断碎片(`### 宏观背景` / `...` / 孤立的 ` ``` `)。这段 prompt 本身有拼接损坏,照抄前需要人工清洗。

### F6 [新] `alphaear-signal-tracker`:把「上一期的判断是被证伪还是被强化」做成显式状态机

SKILL.md frontmatter description 逐字:

> Track finance investment signal evolution and update logic based on new finance market information. Use when monitoring finance signals and determining if they are strengthened, weakened, or falsified.

`references/PROMPTS.md` 第三段逐字:

> 1. **Evolution Detection**:
>    - Has logic changed? (Falsified? Realized? strengthened?)
>    - Mark `reasoning` with "Logic Evolution: ...".
> 2. **Parameter Correction**:
>    - Update `sentiment_score`, `confidence`, `expectation_gap`.
> 3. **Output**:
>    - Keep `signal_id`.

**为什么算新**:consumer 的周报已有「复盘汇总」,但那是叙述性的。这里是**带 ID 的信号对象 + 三态判定 + 置信度/预期差参数修正**,复盘从「写一段回顾」变成「对上期结构化对象打状态」。这是把「逻辑欠缺」变成可检查项的一条具体路径。

### F7 [新] `alphaear-logic-visualizer`:传导链路图作为强制产物,逼出显式因果链

`references/PROMPTS.md` 逐字要点:

> 4. **Auto-layout Strategy**:
>    - Identify "layers" or "stages" in the logic.
>    - Assign X coordinates based on layers (e.g., 0, 200, 400).

> Use different colors for 'Positive' (Green/fillColor=#d5e8d4), 'Negative' (Red/fillColor=#f8cecc), and 'Neutral' (Grey/fillColor=#f5f5f5) impacts.

产物是 Draw.io/MxGraph 纯 XML(`Output ONLY the XML code. Start with `<mxGraphModel>` and end with `</mxGraphModel>`.`),再由 `scripts/visualizer.py` 的 `render_drawio_to_html(xml_content, filename)` 落成可看的 HTML。

**为什么算新**:画链路图这件事本身是**结构约束**——节点必须分层、边必须有向、影响必须三色标注方向。它让「A 导致 B」这类含糊表述无处藏身。consumer 目前的周报是纯文本,没有这一层强制。

### F8 [新] `MoneyAtlas-ClaudeSkill-Agent`:把「必须有失效条件」写成单测,是「结论由脚本给出」的同源做法

`ElmatadorZ/MoneyAtlas-ClaudeSkill-Agent`,Apache-2.0,53 stars,topics 含 `"macro"`。README 逐字:

> ## Non-Negotiable Constraints
> Every output must include:
> - **Multiple scenarios** — no single prediction
> - **Explicit uncertainty** — confidence level + key unknowns
> - **Invalidation point** — what breaks the entire analysis
> - **Human decision primacy** — the skill advises, the human decides
> Violation of any constraint → output is invalid → re-evaluate.

以及一条「够不着就拒答」的闸门,逐字:

> If output violates any of these → the system flags `⚠️ INSUFFICIENT EDGE` and re-evaluates before responding.

关键在于它**不止写在 prompt 里**,逐字:

> The tests are not decorative. They pin the gates that would cost money if they drifted — a BUY signal only on high-confidence accumulation, risk raised on distribution, First Principle truths kept separate from inference — and the skill's own promises: every scenario carries an invalidation condition, and the skill abstains rather than invent a price when it has no data.

> ```bash
> python tools/validate_skill.py   # frontmatter, license, and safety structure intact
> python -m pytest -q              # unit tests over the reasoning engines + skill contract
> ```

agents 目录里有一个 `skeptic_agent.py`(与 `macro_agent.py`、`risk_agent.py` 并列)。

**[印证已知]**:这与 memory 里「结论必须由脚本给出——prompt 禁令堵不住,要改成不变量」完全同源,是同一结论的外部独立印证。
**[新]** 的部分是它的具体不变量清单:**每个情景必须携带失效条件(invalidation condition)**、**无数据时必须弃权而不是编造数字**——后者恰好对上 memory 里「校验器 fail-open」的教训。

### F9 [新] `senior-analyst`:Council 对抗审查 + 7 类认知谬误清单 + 概率赋值禁止无锚

`rrred0324/senior-analyst`,MIT,49 stars,是 S10(`--gh-search "宏观经济 分析 skill"`,`total_available 5`)里唯一有实质方法论的一个。README 逐字:

> 引入Council 对抗审查,有效对抗 AI 7 类认知谬误(叙事谬误、线性外推、确认偏误等),防止过度自信。交叉验证 + 置信度评分 ,减少AI幻觉。三级分析递进:L1 速查(<5秒)→ L2 定量分析 → L3 完整尽调。

三角色分工逐字(表格):

> | **Red Team** | 证伪结论、暴露隐性假设、找遗漏变量 | 5 项快速审查 | 7 类谬误全覆盖 |
> | **Bull/Bear** | 乐观/悲观推演,显性化方向性假设 | 1-2 个关键判断 | 全覆盖 |
> | **Chairman** | 仲裁分歧,事实分歧回查数据源,判断分歧不强行统一 | — | 有 |

> **7 类分析谬误**:叙事谬误、锚定效应、确认偏误、线性外推、幸存者偏差、单一归因、范围忽视

三条对本课题最有用的纪律,逐字:

> - **驱动因子分解法**:概率赋值禁止无锚主观判断,必须分解关键条件独立概率后联合计算
> - **双轨修复**:分析缺口必须同时补内容+修方法论,不可只补报告
> - **执行门控**:财报分析5步顺序变为强制前置门控,不可跳步(数据不可得留空位标注缺口)

置信度分档逐字(节选首尾两档):

> | ≥ 0.9 | 多源一致,无异常 | 直接引用 |
> | < 0.5 | 数据不可信 | 不引用 |

**为什么算新**:
- 「7 类谬误」是一份**可枚举、可逐条打勾的审查清单**,比泛泛的「多视角审查」更能落成校验器条目;
- 「Chairman:判断分歧不强行统一」明确允许结论保留分歧,而不是硬凑一个 verdict;
- 「**双轨修复:分析缺口必须同时补内容+修方法论,不可只补报告**」逐字对上 memory 里「13 次同型缺陷」「七轮审查未收敛,教训是先写修复后补靶点」——这是外部生态里对同一失败模式给出的独立处方。

**注意**:该仓库 `pushed_at` 为 `2026-06-19`,README 里所有 v1.7–v2.3 的能力描述均未在本次调研中读源码验证,以上仅为 README 自述。

### F10 [新] 学术侧的对抗审查基建可直接迁移:devils-advocate + 数值质量门

`HaipingXu/social-science-claude-scholar`(21 stars,`pushed_at 2026-03-14`,末次提交 `955c66d2 2026-03-14`)。计数:`ls -d skills/*/ | wc -l` → `41`(README 自述 `42 specialized skills`,**差 1**)。

`skills/devils-advocate/SKILL.md`(104 行)逐字:

> Produces 5-7 specific adversarial challenges targeting the identification strategy, theoretical mechanism, and empirical design of a research project.

> **Philosophy:** "We arrive at the best possible research through active adversarial dialogue. A challenge is a gift — it identifies what needs to be fixed or pre-empted."

七类挑战分别是 Identification / External Validity / Mechanism / Measurement / Specification / Literature / Magnitude。输出格式强制每条带四段,逐字:

> **Question:** [The specific adversarial question]
> **Why it matters:** [How this threatens the paper — what a referee would write]
> **Suggested pre-emption:** [How to address this proactively in the paper]
> **Severity:** [Fatal / Major / Minor]

原则里两条逐字:

> - Every challenge must include a suggested resolution
> - Distinguish fatal (would reject) from addressable (would request revision)

`rules/quality-gates.md`(77 行)把「好不好」变成扣分制,逐字:

> | 80+ | Commit | Good enough to save |
> | 85+ | Submission | Ready for advisor / co-author |
> | 90+ | Journal | Ready for submission |
> Score < 80 → Block commit. List blocking issues explicitly.

扣分表里与「逻辑欠缺」最相关的几条逐字:`| Critical | Identification assumption not stated | -25 |`、`| Major | No robustness checks | -10 |`、`| Major | Abstract missing key result with magnitude | -8 |`。

README 里两条设计原则逐字:

> **Adversarial QA** | Critic+Fixer loop (max 5 rounds) on papers and analysis
> 4. **Numeric Quality Gates**: No subjective "looks good" — scores block commits and submissions

**[印证已知] + [新]**:「不用主观 looks good、用分数卡门」印证 memory 的「结论由脚本给出」;**新**在于它给了一份**可迁移的扣分细则**——把「主线缺失识别假设」「无稳健性检验」「摘要缺量级」这类逻辑漏洞折算成具体分值并阻断提交,而不是靠 prompt 提醒。

### F11 [新] `econ-writing-skill`(530 stars)提供了「三评审 + 100 分制 + 经济显著性」这一套写作侧的深度约束

`hanlulong/econ-writing-skill`,MIT,530 stars/85 forks。README 逐字:

> - **Paper review and audit mode** -- Simulated 3-reviewer feedback (Methodologist, Field Expert, Writing Critic) with a 100-point scoring rubric
> - **Economic significance framework** -- Translate coefficients into meaningful units, policy benchmarks, and back-of-envelope calculations
> - **Evaluation test suite** -- 18 test cases for benchmarking skill output quality
> - **Field-specific conventions** -- Macro (calibration tables, IRFs, DSGE), trade (gravity, PPML), development (CONSORT, cost-effectiveness), finance (Fama-MacBeth, winsorization)
> - **Citation integrity** -- Anti-hallucination guidance for verifying references, distinguishing working paper vs. published versions

配套还有两个同作者 skill,README 逐字:`[**econ-paper-review-skill**](https://github.com/hanlulong/econ-paper-review-skill) reviews the finished draft like a journal referee`。

**为什么算新**:`Economic significance framework`(把系数翻译成有意义的单位、政策基准、信封背面估算)是**直接对症「解读深度不足」**的一条方法——不是「CPI 环比 0.3%」而是「这相当于…」。`18 test cases for benchmarking skill output quality` 也说明 skill 输出质量可以被基准化,而不是只能靠人眼。

**限制**:全套面向**学术论文写作**,不是市场评论;迁移时需要重做题材映射。

### F12 [新] 生态形状:宏观解读集中在 SKILL.md 类技能包,LangChain/LangGraph 一侧近乎空白

- S11 `--gh-search "langgraph macro economic research report" 30 --sort stars` 输出逐字 `total_available 0 total 0`。
- S9(`financial report generation agent`,`total_available 91`)前 30 名里 star 最高的相关项仅 `Bigdata-com/bigdata-cookbook`(33 stars)与 `shiyidege/Financial-Research-Report-Auto-Generation-Agent`(8 stars),其余大量 LangGraph/CrewAI 项目 stars ≤ 6,多为个人练习。
- S6(`macroeconomic agent LLM`,`total_available 19`)前列是 `SimulacraBusiness/econsimulacra`(9 stars)这类**宏观模拟(EconAgent 复现)**,与「宏观解读」不同题。
- S4(juejin 定向,`"total": 8`)全部命中泛 AI/Agent 行业综述,无一篇讲宏观解读 agent。
- S5/S12 两次 HN 检索各 `"total": 2`,无一条相关。

**含义**:这个题目上,**能抄的东西几乎全在 Claude-Code 风格的 `SKILL.md` 技能包里**,不在 LangChain/OpenAI 的示例仓库里。对抗性地说:如果期待从 LangChain 生态找到成熟的宏观研报 agent,这次检索的证据不支持。

### F13 [印证已知] 「finance skill」这个词面下的绝对多数是数据接入,不是解读方法

S1 `total_available 18` 的 awesome-finance-skills 系列、S2 `total_available 297` 的 claude-skill-finance,主流内容是行情/财报/MCP server 接入(`BlockRunAI/awesome-finance-mcp` 186 stars 就是纯 MCP server 清单)。S10 中文侧 `total_available 5`,其中 3 个(`jie-zhao/skill-financial-analysis`、`jasonpro22/baostock-tt-skills`、`15773302681/Investment-Skill`)描述都是数据源接入或爬研报。

**含义**:consumer 现有 FX 体系的数据侧(BIS 直连、gnews 事件通道)在生态里并不落后;真正稀缺、也正好是 consumer 短板的,是 F1/F8/F9/F10 那一类**推理与审查的不变量**。

---

## Trade-offs(条件性)

- **若目标是给周报补一层「分歧 / 时间分层 / 权重」的结构**:抄 `digital-oracle` 的 Step 5 四维度 + Step 6 模板最省事,它是纯 Markdown 约束,不引入依赖。**代价**是它的方法论前提是「只用交易数据、不引观点」(逐字:`Never cite analyst opinions.`),与 FX 周报需要引用政策/新闻的现状**直接冲突**——只能借结构,不能连世界观一起搬。
- **若目标是让「结论」有强制力**:`MoneyAtlas` 的「用单测钉住不变量」和 `social-science-claude-scholar` 的「扣分卡门」是两条路。前者**代价**是需要为每条不变量写可判定的测试(该仓库 53 stars,规模小,未验证其测试实际覆盖度);后者**代价**是分值权重本质是主观标定,容易变成新的「看起来严谨」。二者都比 prompt 禁令强,但都需要先把「什么算 verdict 违规」定义成可判定谓词——这正是 memory 记录的 `校验器不验 verdict` 缺口所在。
- **若目标是复盘可检查**:`alphaear-signal-tracker` 的「带 ID 的信号 + 强化/弱化/证伪三态」最直接。**代价**是要给周报引入持久化的信号对象与 ID 分配,是数据模型改动,不是文案改动。
- **若只想低成本试一处**:`[@CITE_KEY]` 稳定引用键(F5)改动面最小,且直接改善现有「数字白名单是无序词袋」的问题。**代价**是需要在采集侧就给每条事实分配稳定键,采集脚本要改。
- **若考虑直接安装 `Awesome-finance-skills`**:它支持 `npx skills add RKiding/Awesome-finance-skills@alphaear-news`。**代价**有三:(a) `pushed_at 2026-03-29`,按本报告口径为 **stale**;(b) 每个 skill 目录各自复制了一整份代码树(`alphaear-reporter` 与 `alphaear-signal-tracker` 下都有完整的 `utils/predictor/model/kronos.py` 等),磁盘与上下文成本高;(c) 依赖 `agno` 框架与 `sqlite3`(`alphaear-signal-tracker/SKILL.md` 逐字:`Ensure DatabaseManager is initialized correctly.`),且 `alphaear-signal-tracker/SKILL.md` 自己承认 `# This skill is currently a pattern extracted from FinAgent.` / `In a future refactor, it should be a standalone utility class.` —— 即它是**提取出来的模式而非可独立运行的工具**。**结论倾向:抄 prompt 文本,不装 skill。**

---

## Gaps

1. **没有一个「宏观经济解读」专用的成熟开源 skill**。最接近的 `digital-oracle` 是「用市场价格回答概率问题」,题材覆盖宏观但方法论刻意排斥新闻与政策文本;`Awesome-finance-skills` 的宏观只是新闻标签。**中文宏观周报/宏观解读**这一格,本次检索(S10 `total_available 5`)未见对应物。
2. **F9 的 `senior-analyst` 只读了 README,未读源码**。Council 三阶段、7 类谬误的实际实现质量、`macro_data` MCP 的数据口径均未验证。若要采用,需要单独深读。
3. **awesome 列表只取了 `--gh-search` 的 `updated` 元数据,未逐个取 `pushed_at` 或抓 README**。8 个列表的实际收录内容与新鲜度未核。其中 `BlockRunAI/awesome-finance-mcp`(186 stars)与 `lj22503/awesome-finai-tools-zn` 值得后续为「宏观数据源扩源」单独跑一遍。
4. **`MoneyAtlas` 的测试未实跑**。README 声称 `python -m pytest -q` 会钉住「每个情景带失效条件」「无数据则弃权」两条不变量,但本次未 clone 该仓库、未跑测试,故「测试确实覆盖这两条」属**未验证的自述**。
5. **GitHub Search API 在本次调研中触发过 `HTTP Error 403: rate limit exceeded`**,S1/S10 各重跑过一次。所有已记录计数均来自成功返回的那次调用;但这意味着**部分组合查询未做**(例如 `topic:agent-skills macro`、`"宏观周报" skill`),覆盖不能宣称穷尽。
6. **HN 与掘金两条渠道对本题零产出**(S4/S5/S12 分别 8/2/2 条、无一相关)。「LLM 做宏观解读」在这两个社区没有可引用的讨论,观点类证据需另找渠道(Task E 的对抗搜索)。
