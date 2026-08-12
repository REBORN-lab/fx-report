# SuperCoding Design Handoff

- Change: fx-gnews-event-channel
- Phase: design
- Mode: compact
- Context hash: c2394b6318d1087809869d96a254b856b8b577248448df872ca9a417d75a7ccd

Generated-by: super-coding-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/fx-gnews-event-channel/proposal.md

- Source: openspec/changes/fx-gnews-event-channel/proposal.md
- Lines: 1-55
- SHA256: 3633b45c28d775c1d8ea3933da716662a9837257894c7c7432c8a6f93130b39d

```md
## Why

事件通道是日报归因的地基,而它现在**大部分时间是空的**。2026-08-12 用仓库自己的采集器实跑:GDELT **2/5 币种**拿到数据(USD/EUR/BRL 三个 hard-429,各记一条 gap),全天合计 **4 条**文章。这不是偶发——探针记录 2026-08-07..11 五天 25 个槽位缺 18 条,BRL 整周 0 条。事件层空掉的直接后果是日报逐币种写"昨日无明确驱动",而"情景与触发条件"失去可绑定的市场变量。

Google News RSS 同日同窗口实测 **5/5 币种、284 条、`parsedate_to_datetime` 解析 284/284 零失败**。但**裸接会把噪音换进来,那比沉默更危险**:PHP 88 条里 **76 条来自 `bybit.com` 的加密货币换算页**(`Convert 1000 PHP to USTC`),因为 "PHP" 同时是加密交易对代码。沉默是可披露的(gap 机制已覆盖),噪音不可披露——一条换算器条目进了要点表的"昨日事件 top",LLM 没有任何依据判断它不是市场事件,而这正是本仓库反复出现的失效形态。

因此本 change 的主体不是"换个源",是**换源 + 相关性闸门 + 过滤量可见**。

## What Changes

- `scripts/collect/events.py` 新增 Google News RSS 通道,成为事件主通道:
  - 五币种关键词查询 + `when:2d` 服务端窗口,`xml.etree` 解析 `<item>`
  - **本地 `pubDate` 窗口兜底**:服务端 `when:` 不可信(探针实测 `site:` 查询下 5 条里 4 条 `pubDate` 仍是 2023 年),必须按 RFC 2822 解析后本地再过滤一次
  - `domain` 取 `<source url=>`(实测 88/88 全有),复用现有 `_dedupe_titles`
- 新增 `config/news_sources.json` 域名白名单作为相关性闸门(通讯社 + 财经大报 + 五国本地主流财经 + 五家央行官网)
- **过滤量逐层落盘**:快照记录源返回多少条、窗口过滤后多少条、白名单过滤掉多少条、最终留下多少条。缺了这个,"该币种今天没新闻"与"88 条全落在白名单外"在快照里完全同形
- `skills/fx-daily-report/SKILL.md`:事件行须标注 gnews 条目的 `url` 是 Google 跳转链而非原文
- GDELT 的去留(并联 / 降级 fallback)留给 design 决策,但**限流判定与退避逻辑不改**(`HARD_LIMIT_ERR` / 软限速哨兵实测是对的)

### 为什么是白名单而不是黑名单

2026-08-12 同一批数据上四种过滤方案的实测对照:

| 方案 | USD | EUR | PHP | THB | BRL | 合计 | 残余噪音 |
|---|---|---|---|---|---|---|---|
| GDELT(现状) | 0 | 0 | 2 | 2 | 0 | 4 | — |
| gnews 裸接 | 100 | 30 | 88 | 31 | 34 | 284 | PHP 86% 加密换算器 |
| 域名黑名单 + 标题句式 | 94 | 27 | 4 | 28 | 20 | 173 | 汽车促销漏网(`Hyundai Philippines celebrates Hyundai Cup`) |
| 关键词复核 + 标题句式 | 85 | 23 | 5 | 11 | 14 | 138 | 内容农场漏网(BRL 存活 14 条里 6 条是 `tradersunion.com` 自动生成技术分析) |
| **域名白名单** | 10 | 1 | 2 | 5 | 5 | **23** | **当日 0 条** |

白名单那 23 条逐条核对均为可署名真新闻(CNBC 日美联合干预、Reuters 欧元区投资者信心、Interaksyon 比索领跌亚洲货币、Bangkok Post 泰央行、Bloomberg 新兴市场货币)。黑名单是**无界的**——要永远追着新出现的垃圾站跑,且实测已经漏了两类;白名单是**有界、可审计、可单测**的一个 config 文件。日报每币种至多列 3 条,23 条够用,4 条不够。

**代价明说**:白名单外的真新闻会被丢弃。这是有意的"宁可少说",但丢弃量必须落盘可见,否则就退化成静默劣化。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `fx-data-collection`:「事件数据采集」的来源与筛选要求变更——新增 Google News RSS 为事件主通道、确立域名白名单为相关性闸门、要求逐层过滤计数落盘使"源无数据"与"被过滤"可分辨、要求服务端时间窗之外本地再做一次 `pubDate` 窗口过滤。

## Impact

- 代码:`scripts/collect/events.py`
- 配置:新增 `config/news_sources.json`;`config/endpoints.json` 增 `gnews_rss_url`
- 测试:`tests/test_events.py`(RSS 解析、窗口兜底、白名单闸门、过滤计数、畸形输入不上抛)
- 下游:日报「昨日事件 top」的条目来源与数量整体变化;要点表事件行须标注跳转链
- 外部依赖:新增 `news.google.com`(零 key)。**无正式 API 契约,Google 可随时改**;探针实测 20 次 @0.25s 全 200、无限流迹象,但这不是承诺
- 不影响:汇率采集、宏观采集、官方公告 feeds、年历、周度聚合器、决策日志

**已知不可得(不是缺陷)**:gnews 的 `<link>` 是 Base64 包装的跳转页,实测解码得到 364 字节 Google 内部 token,**标准库还原不出原文 URL**;`guid` 同为该 token,`description` 里也只有跳转链。因此快照的 `url` 对 gnews 条目如实标注为跳转链,可回溯的"谁说的"由 `domain` 承担。
```

## openspec/changes/fx-gnews-event-channel/design.md

- Source: openspec/changes/fx-gnews-event-channel/design.md
- Lines: 1-112
- SHA256: a60b9383ef0d71f239425e811b76f1561735ed1435577c4ce2f836d418380acc

[TRUNCATED]

```md
## Context

`scripts/collect/events.py` 现在只有 GDELT DOC 2.0 一个通道:五币种关键词串行查询,默认间隔 20 秒,软/硬限速统一退避重试一次。它的限流判定逻辑经过实测校准(哨兵值而非在错误串里搜 "429",避免 `IncompleteRead(429 bytes)` 误伤),**这部分是对的,本 change 不动**。

坏的是覆盖率。2026-08-12 实跑:2/5 币种有数据,USD/EUR/BRL 各记一条 `rate-limited after retry`。源码注释已经写明"本机限流与位置无关,事件覆盖的主解仍是换机器"——换机器不在本仓库能做的事情里,换通道是。

约束继承自仓库全局:全链路零 API key、Python 标准库 only、报告中文、采集层异常一律转 gap 绝不上抛、缺输入写 `null` 不写 `0`、外部数据每次成员访问前过 `isinstance` 门、脚本算好 LLM 逐字引用。

## Goals / Non-Goals

**Goals:**

- 事件覆盖从 2/5 币种提到 5/5,且**不以引入噪音为代价**
- "该币种今天没新闻"与"抓到 88 条但全部不相关"在快照里可分辨
- 相关性判定完全在脚本侧、确定性、可单测、可变异测试——不交给 LLM

**Non-Goals:**

- 不动汇率 / 宏观 / 官方公告 feeds / 年历 / 周度聚合器
- 不做 P3(BCB 官方通道)、P4(年历自动化);不接 BSP
- 不尝试还原 Google 跳转链背后的原文 URL(见 D5,标准库做不到)
- 不改 GDELT 的限流判定与退避逻辑
- 不做历史回填:只改今后采集

## Decisions

### D1:gnews 为主通道,GDELT 降级为**空洞补位**而非并联

三个候选:

| 方案 | 采集耗时 | 缺漏节信噪比 | 原文 URL |
|---|---|---|---|
| A 并联(两个都打,合并去重) | +100 秒(GDELT 串行 20s×5) | 差:天天多 3 条 429 gap,而事件其实不缺 | 有 |
| **B 空洞补位**(某币种 gnews 过滤后 0 条才打 GDELT) | 好日子 +0 秒 | 好:GDELT 的 gap 只在**两个通道都失败**时出现,那才是真缺口 | 仅补位时有 |
| C 删掉 GDELT | +0 秒 | — | 无 |

**取 B**。理由:并联的成本天天付、收益只在少数日子出现;而 B 直接对准要解决的失效形态(某币种事件为空)。B 还有一个好性质——GDELT 记 gap 时它的含义从"GDELT 被限流了"升级成"**两条通道都没拿到该币种的事件**",这条 gap 才值得进缺漏节。

不取 C:GDELT 代码已经过实测校准且有测试,留着当安全网的边际成本接近零。`query_order` 的确定性轮转保留——补位时仍可能一次打多个币种。

### D2:相关性闸门用**域名白名单**,不是黑名单

2026-08-12 同批数据实测(详表见 proposal):黑名单方案漏了汽车促销,关键词复核方案漏了内容农场(BRL 存活 14 条里 6 条是 `tradersunion.com` 的自动生成技术分析);白名单方案 23 条当日 0 噪音,且 5/5 币种都还有条目。

决定性的不是当日数字,是**有界性**:黑名单要永远追着新出现的垃圾站跑,每次漏网都是一次静默劣化;白名单是一个 config 文件,漏掉什么是**已知的、可数的**——只要丢弃量落盘(D4),漏掉就不是静默的。

白名单落在 `config/news_sources.json`,与 `endpoints.json` / `indicators.json` 同一约定:**配置缺失 = 有意停用**,删掉文件即整通道回滚。

**匹配规则必须是 `d == w or d.endswith("." + w)`,不能用裸 `endswith`**——后者会让 `notreuters.com` 匹配上 `reuters.com`。这是变异靶点。

### D3:服务端 `when:2d` 之外,本地 `pubDate` 窗口再过滤一次

探针实测服务端窗口**不可信**:`site:` 查询下 5 条里 4 条 `pubDate` 仍是 2023 年。今日无 `site:` 的查询下 284/284 都在窗口内,但那是运气不是契约。

`pubDate` 是 RFC 2822,用 `email.utils.parsedate_to_datetime` 解析(实测 284/284 成功、0 失败)。**解析失败的条目不得当成"在窗口内"也不得静默丢弃**——单独计数(`undated`),沿用 `weekly_digest._verdict` 已确立的纪律:观测缺口必须与真实的零可分辨。

无 tzinfo 的 `pubDate` 按 UTC 处理并计数,不猜本地时区。

### D4:逐层过滤计数落盘

快照 `events.<CCY>` 的形状:

```
{
  "articles":            [...],      # 最终留下的(已去重)
  "articles_raw_count":  100,        # 源返回条数(既有字段,语义延续)
  "articles_undated":    0,          # pubDate 无法解析
  "articles_out_window": 0,          # 解析成功但落在 48h 窗口外
  "articles_offlist":    90,         # 在窗口内但域名不在白名单
  "source_capped":       true,       # 源返回条数顶到上限(见下)
  "channel":             "gnews"     # 或 "gdelt"(补位时)
}
```

不这样做的后果是具体的:PHP 88 条经白名单只剩 2 条,若快照只写 2,下游看到的是"菲律宾昨天只有 2 条新闻";若白名单配错把 88 条全丢了,快照写 0,日报会写"菲律宾昨日无明确驱动"——**管道状态被当成市场事实**,本仓库的第 N 次同型缺陷。

`articles_raw_count` 沿用既有字段名与既有语义(源返回条数,不是去重后条数),`derive.py:146` 与 `weekly_digest.py:306` 无需改动。

**截断标记**:实测 Google News RSS 上限 **100 条**(宽查询 `the` / `dollar` 均返回 100;`&num=200` / `&count=200` 返回 99,突破不了)。USD 今日正好 100,即它是被截断的——"白名单内 10 条"是从截断样本里挑的,真值未知且 ≥10。与 GDELT `MAX_RECORDS=8` 同一纪律,顶到上限必须落盘,否则周度聚合器的 `capped_days` 会漏计。

```

Full source: openspec/changes/fx-gnews-event-channel/design.md

## openspec/changes/fx-gnews-event-channel/tasks.md

- Source: openspec/changes/fx-gnews-event-channel/tasks.md
- Lines: 1-37
- SHA256: 75bf7679016902953b7e7e966b146e594a25ab379cafaa2f6499ea17852d95a3

```md
## 1. 配置与端点

- [ ] 1.1 `config/endpoints.json` 增 `gnews_rss_url`(带 `hl` / `gl` / `ceid` 参数的模板,查询词由采集层填入并 `urlencode`)
- [ ] 1.2 新增 `config/news_sources.json` 域名白名单:通讯社与财经大报、五国本地主流财经、五家央行官网;初始名单来自 2026-08-12 实测存活域名,文件内注明"配置缺失 = 有意停用,删掉即回滚"

## 2. RSS 解析与窗口过滤(纯函数,单测不打网络)

- [ ] 2.1 `_gnews_parse(text)`:`xml.etree` 解析 `<item>`,逐条取 `title` / `link` / `pubDate` / `source@url`;非 XML、空正文、无 `<item>` 一律抛错由上层转 gap,MUST NOT 返回空列表冒充"源确实无数据"
- [ ] 2.2 `_pubdate(raw)`:`email.utils.parsedate_to_datetime` 解析 RFC 2822;解析失败返回 `None`;无 tzinfo 按 UTC 处理,不猜本地时区
- [ ] 2.3 本地窗口过滤:窗口外条目排除并计数;`pubDate` 不可解析的条目单独计数,既不计窗口内也不静默丢弃
- [ ] 2.4 域名提取与白名单匹配 `_in_whitelist(domain, wl)`:匹配规则为 `d == w or d.endswith("." + w)`;**必须有用例钉死 `notreuters.com` 不命中 `reuters.com`、`interaksyon.philstar.com` 命中 `philstar.com`**

## 3. 通道装配与计数落盘

- [ ] 3.1 `_gnews_collect(cfg, currency)`:取数 → 解析 → 窗口 → 白名单 → 复用现有 `_dedupe_titles`,返回条目与逐层计数
- [ ] 3.2 快照条目落盘 `articles` / `articles_raw_count` / `articles_undated` / `articles_out_window` / `articles_offlist` / `source_capped` / `channel`;`articles_raw_count` 沿用既有语义(源返回条数,非去重后条数),确认 `derive.py:146` 与 `weekly_digest.py:306` 无需改动
- [ ] 3.3 `source_capped`:源返回条数等于通道上限(实测 100)时置 true,使周度聚合器的 `capped_days` 不漏计
- [ ] 3.4 gnews 条目的 `url` 原样落跳转链、`domain` 取 `<source url=>`;`channel` 标注取数通道

## 4. 与 GDELT 的衔接(空洞补位)

- [ ] 4.1 `collect()` 改为:先跑 gnews;仅对过滤后 0 条的币种按既有 `query_order` 轮转发起 GDELT 补位;未出现空洞的币种不发 GDELT 请求(用例须断言"未发起请求")
- [ ] 4.2 两条通道都无所得时记缺漏,原因文本须体现**两条通道均已尝试**,不得只写 GDELT 限流
- [ ] 4.3 GDELT 的限流判定、退避重试、`query_order` 一行不改;既有 GDELT 用例全部保持通过
- [ ] 4.4 gnews 端点或白名单未配置 → 静默回落 GDELT-only(即现状),不记缺漏

## 5. 健壮性与回归

- [ ] 5.1 畸形输入不上抛:空正文、HTML 错误页、非 XML、`<item>` 缺字段、`source` 缺 `url`、超长正文——逐项用例,采集层只转 gap
- [ ] 5.2 变异测试:白名单裸后缀匹配、去掉本地窗口过滤、过滤计数漏记、`source_capped` 恒 false、空洞判定用过滤前条数——逐条须被测试杀掉
- [ ] 5.3 全量回归通过(基线 421),`python3 -m unittest discover -s tests -t .`

## 6. 报告层与文档

- [ ] 6.1 `skills/fx-daily-report/SKILL.md` 事件行标注:gnews 条目的 `url` 是 Google 跳转链、来源以 `domain` 为准;核对 `check_report.py` 白名单与结构检查不受影响
- [ ] 6.2 跑一次真实采集,逐条核对五币种的通道标注、过滤计数与截断标记与直查一致
- [ ] 6.3 README 数据源一节补 Google News RSS(含 100 条上限、无 API 契约、白名单闸门与回滚方式)
```

## openspec/changes/fx-gnews-event-channel/specs/fx-data-collection/spec.md

- Source: openspec/changes/fx-gnews-event-channel/specs/fx-data-collection/spec.md
- Lines: 1-78
- SHA256: 8b8e2d828cf39b45ed52ab572eab7a72868929c9a7c7aeed757f7929040bcdb8

```md
## MODIFIED Requirements

### Requirement: 前一日事件采集(GDELT)
系统 SHALL 以 Google News RSS 为事件主通道,按五币种关键词组查询前一日窗口的文章列表;GDELT DOC 2.0 SHALL 降级为**空洞补位**通道——仅当某币种经主通道取得的条目数为 0 时才对该币种发起 GDELT 查询,未出现空洞的币种 MUST NOT 发起 GDELT 请求。

主通道 SHALL 在服务端时间窗之外**本地再做一次窗口过滤**:逐条按 RFC 2822 解析 `pubDate`,落在采集窗口外的条目 SHALL 排除,MUST NOT 依赖服务端时间参数——实测服务端过滤在部分查询形态下不生效。`pubDate` 无法解析的条目 SHALL 单独计数,MUST NOT 计为窗口内,也 MUST NOT 静默丢弃。

主通道 SHALL 以**域名白名单**作为相关性闸门:仅 `<source url=>` 主机名命中白名单的条目进入快照。白名单匹配 SHALL 为「完全相等或以点号加白名单项结尾」,MUST NOT 使用裸后缀匹配——后者会让 `notreuters.com` 命中 `reuters.com`。白名单 SHALL 存放于配置文件;配置缺失时该通道视为有意停用并回落 GDELT,MUST NOT 记为缺漏。

每币种的快照条目 SHALL 逐层记录过滤计数:源返回条数、`pubDate` 不可解析条数、窗口外条数、白名单外条数,并 SHALL 标注取数通道。源返回条数顶到通道上限时 SHALL 落盘截断标记。**缺少这些计数时,「该币种确实无事件」与「抓到大量条目但全部被过滤」在快照中不可分辨**,报告层会把管道状态叙述成市场事实。

条目的 `url` 为跳转链而非原文直链时,SHALL 由通道标注使下游可辨,可回溯的来源归属由 `domain` 承担。

GDELT 补位查询 MUST 保留既有的限流处理:系统 MUST 识别"HTTP 200 但正文为限速提示"的软失败形态**与 HTTP 429 硬限流**,退避后重试一次,仍失败则记为缺漏。查询顺序 SHALL 按采集日期确定性轮转,使限流造成的缺失不恒定落在同一批币种(公平性措施;实测表明本机限流与查询位置无关,轮转不构成 429 缓解手段)。同一币种内标题重复的文章 SHALL 只保留一条。快照 MUST NOT 包含 tone 字段——所使用的 artlist 端点不返回该字段。

#### Scenario: 正常采集
- **WHEN** 五组关键词经主通道查询完成且各有白名单内条目
- **THEN** 快照含每币种的前一日文章列表(标题/URL/来源域名/时间)与通道标注,不含 tone 字段,且不发起任何 GDELT 请求

#### Scenario: 主通道条目被相关性闸门滤除
- **WHEN** 某币种主通道返回大量条目,但其中只有少数命中域名白名单
- **THEN** 快照仅含命中白名单的条目,并记录被白名单滤除的条数,使「源无数据」与「源有数据但不相关」可分辨

#### Scenario: 相关性闸门滤空后 GDELT 补位
- **WHEN** 某币种经主通道过滤后剩余 0 条
- **THEN** 系统对该币种发起 GDELT 查询;取得条目则落盘并标注通道为 GDELT,仍无所得则该币种事件记为缺漏

#### Scenario: 两条通道都无所得
- **WHEN** 某币种主通道过滤后为 0 条且 GDELT 补位亦失败
- **THEN** 该币种事件记为缺漏,缺漏原因 SHALL 体现两条通道均已尝试,其余币种不受影响

#### Scenario: 白名单匹配不得误命中相似域名
- **WHEN** 条目来源域名是白名单项的**后缀相似域名**(如白名单含 `reuters.com`,条目来自 `notreuters.com`)
- **THEN** 该条目 MUST NOT 命中白名单

#### Scenario: 白名单收录子域
- **WHEN** 条目来源域名是白名单项的子域(如白名单含 `philstar.com`,条目来自 `interaksyon.philstar.com`)
- **THEN** 该条目命中白名单

#### Scenario: 服务端时间窗不可信
- **WHEN** 主通道响应中含 `pubDate` 落在采集窗口之外的条目
- **THEN** 这些条目被排除并单独计数,MUST NOT 因服务端已声明时间窗而放行

#### Scenario: 发布时间不可解析
- **WHEN** 某条目的 `pubDate` 无法按 RFC 2822 解析
- **THEN** 该条目不计入窗口内、不进入快照,并单独计数落盘

#### Scenario: 源返回条数顶到上限
- **WHEN** 主通道某币种返回的条数等于该通道的条数上限
- **THEN** 快照标注该币种的取数被截断,使下游知道白名单内条数是从截断样本中得出的下界

#### Scenario: 主通道未配置
- **WHEN** 配置中没有主通道端点或白名单文件
- **THEN** 系统静默回落 GDELT(与既有「未配置 = 有意停用」约定一致),MUST NOT 记为缺漏

#### Scenario: 主通道响应畸形
- **WHEN** 主通道返回非 XML、空正文或结构不符的响应
- **THEN** 记入缺漏并让该币种走 GDELT 补位,采集层 MUST NOT 向上抛出异常

#### Scenario: 限速软失败退避
- **WHEN** GDELT 补位请求的响应为 HTTP 200 但正文是限速提示文本
- **THEN** 系统识别为软失败,等待后重试一次;重试成功则正常记录,再失败则该币种事件记为缺漏

#### Scenario: 硬限流退避
- **WHEN** GDELT 补位请求返回 HTTP 429
- **THEN** 系统等待后重试一次;重试成功则正常记录,再失败则该币种事件记为缺漏

#### Scenario: 查询顺序轮转
- **WHEN** 以不同采集日期运行且存在多个币种需要 GDELT 补位
- **THEN** 补位查询顺序按日期确定性轮转;同一日期重复运行顺序一致

#### Scenario: 标题去重
- **WHEN** 某币种返回的文章中存在标题完全相同的多条
- **THEN** 快照中该币种只保留其中一条

#### Scenario: 端点不可用
- **WHEN** GDELT 补位请求超时或返回错误
- **THEN** 该币种事件记为缺漏(含原因),其余币种查询继续,管线不中断
```

