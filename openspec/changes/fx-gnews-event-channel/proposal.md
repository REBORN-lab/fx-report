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
