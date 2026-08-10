# Research Task Board — AS_OF 2026-08-10 — Mode: Standard

主题:每天汇集影响 USD PHP BRL THB EUR 价格的前一天事件与宏观经济数据、生成带叙事逻辑链条与五币种投资建议的日报/周报 skill 方案调研(信息获取途径 + 开源项目借鉴)。

## Task A1 — data-sources
- **Role**: 宏观与外汇数据基础设施分析师
- **Objective**: 盘点能支撑「每天汇集影响五币种价格的前一天事件与宏观数据」的免费/开放数据源与 API,记录币种覆盖(尤其 PHP/THB/BRL)、更新频率、免费额度、认证要求
- **Queries**:
  1. DDG(规则 A 种子,逐字原始请求串): "我需要一个生成分析报告skill的方案 每天汇集影响USD PHP BRL THB EUR价格 前一天发生的事件和宏观经济数据结合 报告需要有完整且明确的叙事逻辑链条和五种法币的投资建议 并且有生成周报的能力 报告要求简明扼要 只需要关键信息 避免流水账 调研信息获取的途径和相关的开源项目作为借鉴"
  2. DDG: "free API exchange rates USD PHP BRL THB EUR daily"(承载全部 5 个标识符)
  3. DDG: "economic calendar API free forex events"
  4. DDG: "FRED DBnomics World Bank API macroeconomic data free"
  5. DDG: "central bank API Philippines BSP Brazil BCB Bank of Thailand statistics"
  6. DDG: site:zhihu.com 外汇数据 API 免费(非英文 site: 定向)
  7. DDG: 宏观经济数据 API 免费 汇率 接口(用户语言并行查询)
- **Depth**: DEEP(fetch 2-3 份 API 文档)
- **Output**: research-notes/task-data-sources.md
- **Group**: A
- **Consumer Constraints**: 硬约束 = "每天汇集" / "USD PHP BRL THB EUR" / "前一天发生的事件和宏观经济数据结合" / "完整且明确的叙事逻辑链条" / "五种法币的投资建议" / "生成周报的能力" / "简明扼要" / "只需要关键信息" / "避免流水账";已否决 = (none stated);什么才算新 = (none stated)

## Task A2 — oss-pipelines
- **Role**: 金融 LLM 报告管线开源项目调研员
- **Objective**: 找出用 LLM 自动生成金融/市场分析报告(日报/研报/晨报)的开源完整管线,重点看数据接入→分析→叙事生成→报告输出的架构可借鉴点
- **Queries**:
  1. gh-search: "LLM financial report" 30 --sort stars
  2. gh-search: "financial agent" 30 --sort stars
  3. DDG: "FinGPT FinRobot open source LLM financial report generation"
  4. DDG: "gpt-researcher open source automated research report"
  5. HN: "LLM financial analysis" 15
  6. DDG: 开源 大模型 研报 自动生成 github(用户语言并行查询)
- **Depth**: DEEP(fetch top 2-3 仓库 README)
- **Group**: A
- **Output**: research-notes/task-oss-pipelines.md
- **Consumer Constraints**: 同 A1

## Task A3 — popularity sweep(强制,画像含 oss)
- **Role**: Popularity Auditor
- **Objective**: 按影响力指标(stars)发现语义检索会漏掉的高影响项目,5 层法
- **Queries**:
  - Layer 1(全部必跑,串行): gh-search "forex" 100 --sort stars;gh-search "forex in:description" 100 --sort stars;gh-search "topic:forex" 100 --sort stars;gh-search "forex analysis" 30 --sort stars;FM-3 溢出复查 gh-search "forex" 100 --sort updated
  - Layer 2: "forex github stars" 10;"forex best open source tools 2025 2026" 10;"awesome forex github" 10
  - Layer 2.5 生态语境(≥2 条中文): "akshare 外汇 汇率 数据" 10;"宏观 研报 自动生成 github 开源" 10;"外汇 日报 生成 工具" 10
  - Layer 3: 跳过(证据画像无 academic,非学术主题)——笔记中记录依据
  - Layer 4: 发现 awesome-list(stars>1K)必须 fetch README 解析交叉比对
  - Layer 5: 强制 Cross-check 段
- **Depth**: SCAN
- **Group**: A
- **Output**: research-notes/task-popularity.md
- **Consumer Constraints**: 同 A1

## Task A4 — adversarial(强制,产出含推荐)
- **Role**: Devil's Advocate Researcher
- **Objective**: 找反面证据:LLM 生成投资建议的可靠性问题、免费金融数据 API 的坑(限流/停服/数据质量)、FX 预测的失败案例、经济日历抓取的合规风险
- **Queries**:
  1. DDG: "LLM investment advice reliability problems hallucination"
  2. DDG: "free forex API shut down limitations rate limit"
  3. DDG: "FX forecasting why it fails random walk"
  4. DDG: site:reddit.com free financial data API problems
  5. HN: "LLM investment advice" 20
  6. HN: "financial data API" 15
  7. DDG: "economic calendar scraping legal terms of service"
- **Depth**: SCAN
- **Group**: A
- **Output**: research-notes/task-adversarial.md
- **Consumer Constraints**: 同 A1

## Task A5 — events-narrative
- **Role**: 事件数据与叙事方法论调研员
- **Objective**: 调研「前一天事件 + 宏观数据 → 有叙事逻辑链条的外汇日评」实现路径:事件数据源(GDELT 等)、新闻→汇率影响分析方法、自动化 FX 晨报结构范式、日报→周报聚合模式
- **Queries**:
  1. DDG: "GDELT API event database documentation forex"
  2. DDG: "automated daily FX market commentary structure"
  3. DDG: "FX daily morning note template narrative"
  4. scholar: "news events exchange rate impact emerging market currencies" 8
  5. HN: "GDELT" 15
  6. DDG: 外汇 晨报 结构 央行 数据 解读(用户语言并行查询)
- **Depth**: DEEP(fetch GDELT 文档 + 1-2 份晨报范例)
- **Group**: A
- **Output**: research-notes/task-events.md
- **Consumer Constraints**: 同 A1

## Task A6 — gh-scan(强制,技术/OSS 主题;子批次 A2,避免 GitHub 限流碰撞)
- **Role**: GitHub 生态扫描员
- **Objective**: 用关键词变体系统性发现「经济日历/汇率数据/宏观监控/报告生成」相关仓库,top 3 跑 --gh-activity 取维护信号
- **Queries**(串行):
  1. gh-search "economic calendar" 30 --sort stars
  2. gh-search "exchange rate" 30 --sort stars
  3. gh-search "macro dashboard" 20 --sort stars
  4. gh-search "market report" 30 --sort stars
  5. gh-search "economic data api" 20 --sort stars
  6. top 3 相关仓库 --gh-activity
- **Depth**: SCAN
- **Group**: A(子批次 A2)
- **Output**: research-notes/task-gh-scan.md
- **Consumer Constraints**: 同 A1

## Task B1 — deepdive(依赖 Group A 全部笔记)
- **Role**: 候选方案深读员
- **Objective**: 从 Group A 笔记中选 top 5-8 候选(数据源 + 开源项目混合),逐个验证:license、维护状态(--gh-activity 原始日期)、PHP/THB/BRL 币种覆盖(允许 curl 公开端点实测,标 [自测 2026-08-10]),产出同轴 Trade-offs 表 + 决断行
- **Queries**: 依 Group A 结果动态定;--gh-activity ≤5 仓库;--github ≤5;公开 API 端点实测若干
- **Depth**: DEEP
- **Group**: B
- **Output**: research-notes/task-deepdive.md
- **Consumer Constraints**: 同 A1

---

Identifiers pinned: USD, PHP, BRL, THB, EUR (5/5)

Evidence profile: oss, factual (依据: 用户要求"调研信息获取的途径和相关的开源项目作为借鉴"——所需证据是开源项目实现与数据源 API 的当前可得性、免费额度、币种覆盖等现况事实;academic 非本轮必需,popularity sweep 由 oss 触发仍强制执行,无强制任务被免除)

Constraints pinned: "每天汇集", "USD PHP BRL THB EUR", "前一天发生的事件和宏观经济数据结合", "完整且明确的叙事逻辑链条", "五种法币的投资建议", "生成周报的能力", "简明扼要", "只需要关键信息", "避免流水账" | rejected: (none) | novelty-bar: (none) (9 hard, 0 rejected, 0 novelty-bar)
