# Task: Popularity Audit — 宏观经济解读的开源 skill / 项目

**Role**: Popularity Auditor
**Objective**: 按影响力度量(stars / citations)发现语义检索因措辞不同而漏掉的高影响项目
**AS_OF**: 2026-08-14
**Depth**: SCAN(清单式比对,不深读)
**工具**: `python3 "$SR_ROOT/scripts/search.py"`,`SR_ROOT=/home/ubuntu/repos-REBORN-lab/super-research`

> 本文件中所有 star 数、日期、计数均为命令实测输出抄录,无估算、无二手文章引用。
> GitHub 无 token 调用(core 60/h,search 10/min),期间遇到两次 403 限流,已重跑取得完整结果(见 Gaps G4)。

---

## Sources

### Layer 1 — GitHub 宽搜(4 条必跑 + 1 条溢出复查,全部完成)

| # | 命令 | total_available | 返回 | Path |
|---|------|-----------------|------|------|
| A | `--gh-search "macroeconomics" 100 --sort stars` | 5519 | 100 | `github-sweep` |
| B | `--gh-search "macroeconomics in:description" 100 --sort stars` | 4457 | 100 | `github-sweep` |
| C | `--gh-search "topic:macroeconomics" 100 --sort stars` | 745 | 100 | `github-sweep` |
| D | `--gh-search "macroeconomics agent" 30 --sort stars` | 206 | 30 | `github-sweep` |
| A′ | `--gh-search "macroeconomics" 100 --sort updated`(溢出复查) | 5519 | 100 | `github-sweep` |

**溢出处理已触发**:首条查询 `total_available = 5519 > 200`,故按规则追加 `--sort updated` 100 条并合并。

**合并去重结果**:430 行 → **272 个唯一仓库**(按 repo 全名去重)。
分布:stars ≥ 100 共 **18** 个;stars ≥ 50 共 **35** 个;stars ≥ 10 共 **149** 个。

**溢出复查的边际价值(实测)**:`--sort updated` 独家贡献 **93** 个仓库,但全部为长尾——其中最高 star 数仅 **8**(`hibasameen/datadarbar`)。结论:stars 维度上溢出复查未发现任何被 star 排序漏掉的高影响项目,它捕获的是「新建/刚推送但无人关注」的仓库。
其余独家贡献:`macroeconomics agent` 独家 10 个(最高 9 star),`topic:macroeconomics` 独家 31 个(最高 13 star)。

### Layer 2 — DDG 交叉发现(3 条全跑) — Path: `ddg`

| 查询 | 有效产出 |
|------|----------|
| `"macroeconomics github stars" 10` | `wmutschl/quantitative-macroeconomics`(已在 L1) |
| `"macro analysis best open source tools 2025 2026" 10` | **零有效产出** — 返回 OSINT 工具榜、Apify、Synthesia AI 榜、YouTube phonk 混音、Pastebin 脚本、Yahoo Finance、Google 首页。措辞过泛,DDG 完全跑偏 |
| `"awesome macroeconomics" github 10` | `brandonhimpfen/awesome-economics`、`nnguyengiatan/ECBS-6001-Advanced-Macroeconomics`(课程repo) |

### Layer 2.5 — 生态语境查询(3 条全跑,2 条中文) — Path: `ddg`

| 查询 | 有效产出 |
|------|----------|
| `"雪球 宏观 开源 工具" 10` | AKShare(`akfamily/akshare`);其余为雪球用户页、知乎问答、`wbh604/UZI-Skill`(游资题材,不相关) |
| `"聚宽 宏观因子 开源" 10` | `JoinQuant/jqfactor_analyzer`、`JoinQuant/jqdatasdk` |
| `"Bloomberg terminal open source alternative macro" 10` | `OpenBB-finance/OpenBB`、`Lastoneparis/awesome-bloomberg-alternatives` |

### Layer 3 — 学术 — Path: `scholar`

`--scholar "macroeconomic analysis machine learning" 10 --sort cited_by_count:desc`,`total_available = 63595`。

| # | 引用数 | 年份 | 标题 |
|---|--------|------|------|
| 1 | 4957 | 1995 | Economic Reform and the Process of Global Integration |
| 2 | 3949 | 2023 | LLaMA: Open and Efficient Foundation Language Models |
| 3 | 3280 | 2000 | Beyond Computation: Information Technology, Organizational Transformation and Business Performance |
| 4 | 2958 | 2011 | The multi-level perspective on sustainability transitions |
| 5 | 2610 | 1991 | Who Benefits from State and Local Economic Development Policies? |
| 6 | 2450 | 2023 | GPT-4 Technical Report |
| 7 | 2438 | 2019 | Digital Economics (J. Econ. Literature) |
| 8 | 2383 | 2020 | Empirical Asset Pricing via Machine Learning (RFS) |
| 9 | 2338 | 2019 | Automation and New Tasks (JEP) |
| 10 | 2092 | 2000 | Economic Analysis of Social Interactions (JEP) |

**判读**:按引用数排序的 OpenAlex 结果对本主题**基本无信号**。命中的是「宏观经济学」与「机器学习」两个高引词各自的通用经典(LLaMA、GPT-4 是纯 ML 论文,Sachs-Warner 是纯经济学论文),没有一篇是「用 LLM/agent 做宏观解读」的工作。唯一勉强相邻的是 #8 Empirical Asset Pricing via Machine Learning(2383 引)。**学术引用维度未能为本主题提供有效的高影响项目线索**(见 Gaps G1)。

### Layer 4 — awesome-list 解析 — Path: `awesome-list`

**强制门槛未触发**:Layer 1/2 发现的两个含 "awesome" 的仓库 star 数均远低于 1K 门槛——
- `brandonhimpfen/awesome-economics` = **14** stars(实测 `--github`)
- `Lastoneparis/awesome-bloomberg-alternatives` = **8** stars(实测 `--github`)

Layer 1 的 272 个合并仓库中**不含任何**名称带 "awesome" 的仓库。

**仍作自选解析**(门槛外,因其为本主题唯一在册 curated list):`--fetch https://raw.githubusercontent.com/brandonhimpfen/awesome-economics/main/README.md`(115 行)。
注:先用 `--fetch` 取 `github.com/...` HTML 页返回的是 GitHub 站点导航栏而非 README 正文,改取 `raw.githubusercontent.com` 才拿到正文(见 Gaps G5)。

该 list 全文仅含 **2 个** GitHub 项目链接,其余全部指向机构/数据门户(FRED、IMF、World Bank、OECD、Dynare、QuantEcon 官网等),**不是仓库清单**:
- `JuliaEconomics` — 是 org 而非 repo
- `jessegrabowski/py-econ` — **死链**,实测 HTTP 404(`github.com` 页 404,`raw` README 404;对照组 `jessegrabowski/gEconpy` 返回 200)。该 list 标注其为 "PyEcon – Python tools for economic simulation",实际不存在
- 由 list 正文(非链接)提到的 **QuantEcon** 反查得 `QuantEcon/QuantEcon.py` = **2388** stars —— 此项不在 Layer 1 的 272 个仓库中,为本层唯一实质增量

---

## Findings

三值标记:**✅ 直接命中**(就是「宏观解读」的 skill/agent 产品) / **⚠️ 相邻可用**(宏观建模或数据底座,可作为解读层的输入) / **❌ 不相关**(仅关键词共现,主要是课程与复现代码)。

### ✅ 直接命中 — 宏观解读类 skill / agent

| Stars | 仓库 | 说明 | Path |
|-------|------|------|------|
| **775** | [`komako-workshop/digital-oracle`](https://github.com/komako-workshop/digital-oracle) | **本次调研最重要的发现。**中文开源 Skill,面向 OpenClaw / Claude Code / Cursor / Codex。README 自述:接入 13 个金融数据源(Polymarket、Kalshi、Stooq、Deribit、US Treasury、CFTC COT、CoinGecko、SEC EDGAR 等),**只用市场定价数据、不读新闻文章**,回答房价/黄金/BTC/地缘冲突概率类宏观问题,输出结构化概率估计与推理链 | `github-sweep` |
| **189** | [`LLMQuant/skills`](https://github.com/LLMQuant/skills) | Reusable Skills for LLMQuant Agent / Claude Code / Claude.ai / Cursor / Hermes Agent / OpenClaw | `github-sweep` |
| **53** | [`ElmatadorZ/MoneyAtlas-ClaudeSkill-Agent`](https://github.com/ElmatadorZ/MoneyAtlas-ClaudeSkill-Agent) | Money Atlas Skill.md(Claude Skill),Genesis Protocol 驱动 | `github-sweep` |
| **43** | [`viczommers/CentralBank-LLM`](https://github.com/viczommers/CentralBank-LLM) | 自述为首个开源 RAG-LLM 工具,分析宏观数据与预测 | `github-sweep` |
| **21** | [`garroshub/ai-economist-skill`](https://github.com/garroshub/ai-economist-skill) | "Structural AI for Macroeconomic Intelligence" | `github-sweep` |
| **16** | [`EconSolider/dynare-copilot`](https://github.com/EconSolider/dynare-copilot) | 把宏观直觉转成校验过的 Dynare .mod 文件的 coding agent skill | `github-sweep` |
| **12** | [`aleksey-karasev/Ultimate-Macroeconomics-Dashboard`](https://github.com/aleksey-karasev/Ultimate-Macroeconomics-Dashboard) | AI 驱动的宏观数据交互式仪表盘 | `github-sweep` |
| **10** | [`lambda-capture/mcp-server`](https://github.com/lambda-capture/mcp-server) | 面向 quant AI agent 的宏观数据语义检索 MCP Server | `github-sweep` |
| **9** | [`SimulacraBusiness/econsimulacra`](https://github.com/SimulacraBusiness/econsimulacra) | 基于 LLM agent、锚定宏观环境的仿真平台 | `github-sweep` |
| **3** | [`J-King-Dottie/aus-data-agent-mcp`](https://github.com/J-King-Dottie/aus-data-agent-mcp) | 澳洲公共数据统一 MCP(ABS/RBA/OECD/World Bank/IMF) | `github-sweep` |

**关键判读**:整个 GitHub 上「宏观解读 skill/agent」这一品类**只有 1 个项目越过 500 star**(digital-oracle, 775),第二名断崖跌至 189。这是一个**极不成熟、几乎无赢家**的赛道——对比同处金融数据领域的 OpenBB(71856)与 AKShare(22022),差了两个数量级。

### ⚠️ 相邻可用 — 宏观建模 / 数据底座

| Stars | 仓库 | 说明 | Path |
|-------|------|------|------|
| **71856** | [`OpenBB-finance/OpenBB`](https://github.com/OpenBB-finance/OpenBB) | Open Data Platform,自述面向 analysts / quants / **AI agents** | `ddg` → cross-check |
| **22022** | [`akfamily/akshare`](https://github.com/akfamily/akshare) | Python 金融数据接口库,含中国宏观数据接口 | `ddg` → cross-check |
| **2388** | [`QuantEcon/QuantEcon.py`](https://github.com/QuantEcon/QuantEcon.py) | 社区计算经济学 Python 库 | `awesome-list` → cross-check |
| **1366** | [`JoinQuant/jqdatasdk`](https://github.com/JoinQuant/jqdatasdk) | 聚宽量化金融数据包(中国市场) | `ddg` → cross-check |
| **955** | [`FRBNY-DSGE/DSGE.jl`](https://github.com/FRBNY-DSGE/DSGE.jl) | 纽约联储 DSGE 模型求解与估计(Julia) | `github-sweep` |
| **269** | [`R-CoderDotCom/econocharts`](https://github.com/R-CoderDotCom/econocharts) | ggplot2 宏微观经济图表 | `github-sweep` |
| **234** | [`FRBNY-TimeSeriesAnalysis/Nowcasting`](https://github.com/FRBNY-TimeSeriesAnalysis/Nowcasting) | 纽约联储 Nowcasting | `github-sweep` |
| **203** | [`dkgaraujo/OpenSourcedMacroModels`](https://github.com/dkgaraujo/OpenSourcedMacroModels) | 各国央行与国际机构开源宏观模型的汇总目录 | `github-sweep` |
| **142** | [`thorek1/MacroModelling.jl`](https://github.com/thorek1/MacroModelling.jl) | DSGE 建模 Julia 包 | `github-sweep` |
| **137** | [`uwol/computational-economy`](https://github.com/uwol/computational-economy) | 基于 agent 的计算经济体 | `github-sweep` |
| **121** | [`bancaditalia/BeforeIT.jl`](https://github.com/bancaditalia/BeforeIT.jl) | 意大利央行,高性能 agent-based 宏观 | `github-sweep` |
| **103** | [`vfitoolkit/VFIToolkit-matlab`](https://github.com/vfitoolkit/VFIToolkit-matlab) | 值函数迭代宏观模型工具箱 | `github-sweep` |
| **98** | [`IRIS-Solutions-Team/IRIS-Toolbox`](https://github.com/IRIS-Solutions-Team/IRIS-Toolbox) | 宏观建模工具箱 | `github-sweep` |
| **43** | [`shashankvemuri/economic-dashboard`](https://github.com/shashankvemuri/economic-dashboard) | Python/Dash 宏观与股市仪表盘 | `github-sweep` |
| **41** | [`epogrebnyak/weo-reader`](https://github.com/epogrebnyak/weo-reader) | IMF WEO 数据读取 | `github-sweep` |
| **36** | [`HelloThereMatey/tedata`](https://github.com/HelloThereMatey/tedata) | Trading Economics 抓取 | `github-sweep` |
| **33** | [`Moritz-Pfeifer/CentralBankRoBERTa`](https://github.com/Moritz-Pfeifer/CentralBankRoBERTa) | 央行沟通文本的经济主体分类 LLM | `github-sweep` |
| **26** | [`palewire/fed-dot-plot-scraper`](https://github.com/palewire/fed-dot-plot-scraper) | 抓取 Fed 点阵图经济预测 | `github-sweep` |
| **24** | [`AFAN-LIFE/macropage`](https://github.com/AFAN-LIFE/macropage) | 中国宏观经济仪表盘 | `github-sweep` |
| **19** | [`bis-med-it/BIS_Multisector_Model`](https://github.com/bis-med-it/BIS_Multisector_Model) | BIS 多部门模型 | `github-sweep` |

### ❌ 不相关 — 关键词共现的长尾

**这是 272 个合并结果的绝对主体**。抽样特征:
- **大学课程仓库**(单一最大类别):实测 stars ≥ 50 的 35 个仓库中,**12 个(34%)** 为课程/讲义/训练营仓库 —— `pmichaillat/math-for-macro`(151)、`yangycpku/macro_ML`(135)、`jdingel/econ35101`(134)、`pmichaillat/intermediate-macro`(116)、`wmutschl/Computational-Macroeconomics`(105)、`wmutschl/Quantitative-Macroeconomics`(89)、`steliostsiaras/Financial-Frictions-Course`(84)、`jstac/nyu_macro_fall_2018`(61)、`yangycpku/ML_Macro_Finance_Summer2026`(58)、`OpenSourceEcon/BootCamp2017`(56)、`ecampiglio/Climate-macro-course`(51)、`mrognlie/econ411-3`(50)
- **单篇论文复现代码**:`dkaenzig/replicationOilSupplyNews`(20)、`dkaenzig/micc_replication`(13)、`yukimasano/rck_abm`(13)
- **DDG 噪声**:`wbh604/UZI-Skill`(游资题材)、Apify、Synthesia AI 工具榜、YouTube phonk 混音、Pastebin 脚本 —— 全部来自 `"macro analysis best open source tools 2025 2026"` 这条过泛查询
- **`--sort updated` 长尾**:93 个独家仓库全部 ≤ 8 star,多为当日新建的个人 dashboard(`hibasameen/datadarbar`、`blocknine0/geomacro`、`nickzhuchen66/kairos-atlas` 等)

---

## Cross-check: DDG + Ecosystem vs GitHub

在 DDG(Layer 2)/ 生态语境(Layer 2.5)/ awesome-list(Layer 4)结果中出现、但**不在 Layer 1 合并列表(272 项)**里的项目。每项均实测 star 数:

- **OpenBB** → `--github OpenBB-finance/OpenBB` → **71856** stars → **relevant**(⚠️ 相邻可用;Open Data Platform,自述面向 AI agents,含 economy 数据模块)→ **纳入 findings**
- **AKShare** → `--github akfamily/akshare` → **22022** stars → **relevant**(⚠️ 相邻可用;含中国宏观数据接口)→ **纳入 findings**
- **QuantEcon.py** → `--gh-search "repo:QuantEcon/QuantEcon.py"` → **2388** stars → **relevant**(⚠️ 相邻可用;计算经济学库)→ **纳入 findings**
- **jqdatasdk** → `--github JoinQuant/jqdatasdk` → **1366** stars → **relevant**(⚠️ 相邻可用;中国量化数据包,含宏观)→ **纳入 findings**
- **jqfactor_analyzer** → `--github JoinQuant/jqfactor_analyzer` → **683** stars → **irrelevant**(单因子分析工具,面向股票截面因子 IC/收益/换手,与宏观解读无关;虽 > 500 但主题不符,依规则不纳入)
- **awesome-economics** → `--github brandonhimpfen/awesome-economics` → **14** stars → relevant 但**远低于 500 门槛**,不纳入 findings(仅作 Layer 4 解析对象)
- **awesome-bloomberg-alternatives** → `--github Lastoneparis/awesome-bloomberg-alternatives` → **8** stars → relevant 但**远低于 500 门槛**,不纳入
- **py-econ**(awesome-economics 列为 "PyEcon") → `--gh-search "repo:jessegrabowski/py-econ"` → **HTTP 422**;curl 复核 `github.com` 页与 raw README 均 **404** → **仓库不存在(死链)**,无 star 数可取。其现存对应物 `jessegrabowski/gEconpy`(40 stars)已在 Layer 1 列表内
- **UZI-Skill** → 未跑 `--github`:标题为「冰冷的钱就这样流进我温暖的口袋-游资」,系游资选股题材,与宏观解读无语义关联,判为 **irrelevant**
- **ECBS-6001-Advanced-Macroeconomics** → 未跑 `--github`:DDG 命中的是 ecosyste.ms 镜像页而非 GitHub 本体,且为个人课程作业仓库,判为 **irrelevant**

**交叉核对结论**:DDG + 生态语境层**确实补上了 Layer 1 的系统性盲区**。GitHub 关键词搜 "macroeconomics" 完全搜不到 OpenBB(71856)与 AKShare(22022)——因为二者的仓库描述用 "Open Data Platform" / "financial data interface library" 措辞,不含 "macroeconomics" 一词。**仅靠 Layer 1 会漏掉本领域 star 数最高的两个项目,量级差距达 90 倍。**这正是本 Popularity Audit 的核心价值所在。

---

## 维护状态(全部引 `--gh-activity` 实测日期,AS_OF 2026-08-14;无二手文章)

| 仓库 | stars | pushed_at | 最后提交 | 提交数估计 | open issues+PRs | 最近 release | 判读 |
|------|-------|-----------|----------|-----------|-----------------|--------------|------|
| `komako-workshop/digital-oracle` | 775 | 2026-07-26(18 天前) | 2026-07-26(18 天前) | 36 | 1 | **无 release** | **活跃但极年轻**。36 次提交、**单一贡献者**(komako-workshop 独占全部 36 次),无发布版本。775 star 与 36 提交的比例说明是近期爆红项目,**巴士因子 = 1** |
| `FRBNY-DSGE/DSGE.jl` | 955 | 2026-07-23(21 天前) | 2026-07-23(21 天前) | 7327 | 124 | v1.3.0 @ **2021-11-23** | **代码活跃、发布停滞**。提交仍在推进但最近 tag 已 4 年 9 个月未更新;124 个未关闭 issue/PR。机构背书(纽约联储),贡献者 chenwilliam77 / pearlzli / ethanmatlin |
| `OpenBB-finance/OpenBB` | 71856 | 2026-07-30(14 天前) | 2026-07-20(24 天前) | 6863 | 109 | Open-Data-Platform-v1.0.2 @ 2026-04-25(约 3.6 个月前) | **健康活跃**。提交与发布双线在跑,多贡献者(jmaslek / deeleeramone / montezdesousa) |
| `dkgaraujo/OpenSourcedMacroModels` | 203 | 2025-07-16(**393 天前**) | 2025-07-16(**393 天前**) | 33 | 0 | 无 release | **已停更**。超过一年无任何推送,作为「央行开源宏观模型目录」其内容时效性存疑 |
| `LLMQuant/skills` | 189 | 2026-05-30(75 天前) | 2026-05-30(75 天前) | 4 | 2 | 无 release | **近乎静止**。仅 4 次提交,2.5 个月无更新;189 star 对 4 提交,属「星标远超实际投入」型 |

---

## Gaps

- **G1 — 学术层对本主题零信号(方法论级缺口)**:Layer 3 按引用数排序返回的 10 篇全部是「宏观经济学」或「机器学习」各自的通用高引经典(含 LLaMA、GPT-4 两篇纯 ML 论文),**无一篇涉及 LLM/agent 做宏观解读**。原因是本主题是 2024–2026 年的工程实践,尚未沉淀为高引论文;按引用排序必然被历史经典淹没。**引用数维度无法为本主题提供高影响项目线索**,若需学术侧覆盖,应改用 `--arxiv` 按 `submittedDate` 排序或 `--scholar --sort publication_date:desc`。本次按指令仅跑规定的一条 scholar 查询,未做补充。

- **G2 — 单点依赖风险未量化**:`digital-oracle` 是本主题唯一越过 500 star 的直接命中项目,但实测为**单一贡献者、36 次提交、零 release**。将其作为「本领域已有成熟开源方案」的论据是不安全的;下游报告若引用它,须同时引这三个数字。

- **G3 — 措辞盲区已证实但可能未穷尽**:已证实 GitHub 关键词层搜不到 OpenBB / AKShare(描述措辞不含 "macroeconomics")。同类盲区可能仍有残留——本次未跑 `economic data`、`central bank`、`FRED`、`nowcasting`、`宏观` 等替代措辞的 gh-search(指令未列),故**不能断言 500+ star 区间已被穷尽**。

- **G4 — GitHub 限流影响过程但未影响结论**:无 token 调用,search 限 10/min、core 限 60/h。查询 B 首次返回 `HTTP 403: rate limit exceeded`(0 结果),重跑第 2 次取得完整 100 条(total_available 4457),已计入合并。审计末段 core 配额耗尽(60/60),故 `QuantEcon.py` 改用 search API 的 `repo:` 限定符取数(2388,与 core API 同源)。**所有已记录数字均来自成功返回的响应,无一为限流态下的残值。**

- **G5 — `--fetch` 对 GitHub HTML 页不可用**:`--fetch https://github.com/<owner>/<repo>` 返回的是 GitHub 站点导航栏(Copilot / Codespaces / Solutions 等菜单文本),不是 README 正文。必须改用 `raw.githubusercontent.com/<owner>/<repo>/{main,master}/README.md`。本次 Layer 4 与 digital-oracle 正文均按后者取得。

- **G6 — awesome-list 层几乎无产出且含死链**:本主题**不存在** 1K+ star 的 awesome list(强制门槛未触发)。唯一在册的 `awesome-economics`(14 star)全文仅 2 个 GitHub 链接,其中 `jessegrabowski/py-econ` 实测 404 为死链。该 list 本质是数据门户书签集而非仓库清单,**对 popularity audit 的增量仅 QuantEcon.py 一项**。中文生态侧未发现任何对标的 awesome 宏观列表。

- **G7 — issue/PR 未拆分**:`--gh-activity` 返回的 `open_issues_count` 按 GitHub API 语义**包含 PR**,工具自身注明 "issue/PR split deferred to a later batch"。上表「open issues+PRs」列如此标注,未单独给出 issue 数。

- **G8 — DDG 查询 `"macro analysis best open source tools 2025 2026"` 完全失效**:8 条结果零有效产出(OSINT 工具榜、Apify、Synthesia、YouTube 音乐、Pastebin、Yahoo Finance、Google 首页)。措辞过泛导致 DDG 落入通用 SEO 内容农场。该条查询对本次审计的贡献为 0。
