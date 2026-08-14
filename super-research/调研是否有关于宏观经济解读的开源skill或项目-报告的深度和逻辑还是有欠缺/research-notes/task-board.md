# Research Task Board

- AS_OF: 2026-08-14
- Mode: Standard
- 原始请求(逐字): `调研是否有关于宏观经济解读的开源skill或项目 报告的深度和逻辑还是有欠缺`

---

## Task A — 语义检索:宏观经济解读的开源项目与 Agent skill

- **Role**: Macro Research Tooling Analyst
- **Objective**: 找出用于宏观经济解读/评论/归因的开源项目、Agent skill、prompt 框架
- **Queries**:
  - DDG(规则 A 种子查询,原始串逐字): `调研是否有关于宏观经济解读的开源skill或项目 报告的深度和逻辑还是有欠缺` 10
  - DDG: `open source macroeconomic analysis agent LLM 2026` 10
  - DDG: `"macro research" LLM agent open source framework` 10
  - DDG: `site:zhihu.com "宏观经济" 大模型 分析 开源` 10
  - `--gh-search "macroeconomic analysis" 30 --sort stars`
- **Depth**: DEEP(取 2–3 篇全文)
- **Output**: `research-notes/task-a.md`
- **Group**: A
- **Consumer Constraints**:
  - 硬约束: 必须是「开源skill或项目」;主题须落在「宏观经济解读」
  - 已试过并否决: (none)
  - 什么才算新: 能改善「报告的深度和逻辑还是有欠缺」的做法才算新

## Task B — 语义检索:宏观叙事的分析框架与推理链方法论

- **Role**: Macro Framework Methodologist
- **Objective**: 找出把宏观数据转成有逻辑链条的解读的公开方法论(传导机制、情景分析、证伪结构),含学术与机构做法
- **Queries**:
  - `--scholar "macroeconomic narrative transmission channel framework" 10`
  - `--scholar "scenario analysis macroeconomic forecasting falsifiable" 10`
  - `--arxiv "large language model macroeconomic forecasting" 10 --cat q-fin.EC`
  - DDG: `central bank "transmission mechanism" analytical framework open methodology` 10
  - DDG(中文): `宏观 传导链条 分析框架 方法论 公开` 10
- **Depth**: DEEP
- **Output**: `research-notes/task-b.md`
- **Group**: A
- **Consumer Constraints**: 同 Task A

## Task C — 语义检索:金融/宏观类 Agent skill 生态(含 Claude skills)

- **Role**: Agent Skill Ecosystem Scout
- **Objective**: 盘点 Claude Code / OpenAI / LangChain 等生态里与金融宏观分析相关的公开 skill 与 awesome 列表
- **Queries**:
  - `--gh-search "awesome finance skills" 30 --sort stars`
  - `--gh-search "claude skill finance" 30 --sort stars`
  - DDG: `"claude skills" finance macro economics github` 10
  - DDG(中文,site 定向): `site:juejin.cn 大模型 宏观经济 分析 agent` 10
  - `--hn "LLM macroeconomic analysis" 20`
- **Depth**: SCAN
- **Output**: `research-notes/task-c.md`
- **Group**: A
- **Consumer Constraints**: 同 Task A

## Task D — Popularity Sweep(强制,画像含 oss/academic)

- **Role**: Popularity Auditor
- **Objective**: 按影响力度量(stars/citations)发现语义检索因措辞不同而漏掉的高影响项目
- **Queries**(Layer 1 全部必跑,首条零修饰):
  - `--gh-search "macroeconomics" 100 --sort stars`
  - `--gh-search "macroeconomics in:description" 100 --sort stars`
  - `--gh-search "topic:macroeconomics" 100 --sort stars`
  - `--gh-search "macroeconomics agent" 30 --sort stars`
  - Layer 2: DDG `macroeconomics github stars` 10 / `macro analysis best open source tools 2025 2026` 10 / `awesome macroeconomics github` 10
  - Layer 2.5 生态语境(≥2 条用用户语言): DDG `雪球 宏观 开源 工具` 10 / `聚宽 宏观因子 开源` 10 / `Bloomberg terminal open source alternative macro` 10
  - Layer 3: `--scholar "macroeconomic analysis machine learning" 10`
  - Layer 4: 发现 awesome-list(stars>1K)必 `--fetch` README 并交叉比对
- **Depth**: SCAN
- **Output**: `research-notes/task-popularity.md`
- **Group**: A
- **Consumer Constraints**: 同 Task A

## Task E — 对抗搜索(强制,本轮产出含推荐)

- **Role**: Devil's Advocate Researcher
- **Objective**: 找 LLM 做宏观解读的批评、局限、失败案例与替代路径
- **Queries**:
  - DDG: `LLM macroeconomic analysis problems limitations` 10
  - DDG: `why LLM cannot forecast macro economy criticism` 10
  - DDG: `site:news.ycombinator.com LLM economics analysis issues` 10
  - `--hn "LLM economic forecasting" 20`
  - `--hn "AI macro research" 20`
- **Depth**: SCAN
- **Output**: `research-notes/task-adversarial.md`
- **Group**: A
- **Consumer Constraints**: 同 Task A

---

Identifiers pinned: skill (1/1)

Evidence profile: oss, academic, factual (依据: 问的是「有没有开源 skill 或项目」需 oss;要改善「深度和逻辑」需 academic 的分析框架证据;需各项目当前维护状态与可得性,故含 factual)

Constraints pinned: "开源skill或项目", "宏观经济解读" | rejected: (none) | novelty-bar: "报告的深度和逻辑还是有欠缺" (2 hard, 0 rejected, 1 novelty-bar)
