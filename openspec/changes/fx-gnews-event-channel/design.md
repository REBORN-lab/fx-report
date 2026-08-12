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

### D5:`url` 如实标注跳转链,`domain` 取 `<source url=>`

实测 `<link>` 形如 `https://news.google.com/rss/articles/CBMirwFB...`,Base64 解码得 **364 字节 Google 内部 token**,里面没有原文 URL;`guid` 是同一 token(`isPermaLink="false"`),`description` 里也只有跳转链。**标准库还原不出原文 URL,这是事实不是待办。**

因此 gnews 条目:
- `url` = 跳转链原样落盘,并由 `channel: "gnews"` 标明它不是原文直链
- `domain` = `<source url=>` 的主机名(实测 88/88 全有),承担"谁说的"这条可回溯性
- 日报 SKILL 的事件行相应标注,避免读者(和 LLM)把跳转链当原文引用

### D6:查询词与白名单都是配置,不是代码常量

`KEYWORDS` 现在写死在 `events.py`。gnews 查询沿用同一组关键词(它们已经过 GDELT 时代验证),但白名单必须是配置。查询词暂留代码内——改查询词会改变召回集合,属于需要走 change 的行为变更;白名单增删一个域名不改变行为语义,属于运维。

## Risks / Trade-offs

- **无正式 API 契约,Google 可随时改** → gnews 解析失败一律转 gap 并让该币种走 GDELT 补位(D1);`config/endpoints.json` 删掉 `gnews_rss_url` 即整通道回滚到现状
- **白名单外的真新闻被丢弃** → 有意的"宁可少说";丢弃量由 `articles_offlist` 落盘可见,不是静默劣化。白名单饿死某币种(0 条)时 GDELT 补位兜底
- **白名单需要长期维护** → 有界且可审计;比黑名单的无界追赶好。初始名单来自实测存活域名 + 五国主流财经 + 五家央行官网
- **100 条截断** → `source_capped` 落盘;查询已按币种拆分,单币种顶到 100 的只有 USD
- **`pubDate` 解析失败** → 单独计数,不当成窗口内也不静默丢弃(D3)
- **限流未知** → 探针 20 次 @0.25s 全 200 无限流迹象,但这不是承诺。采集每天每币种 1 次 GET,共 5 次,远低于任何合理阈值;若日后遇限流,按现有 GDELT 的 gap 机制处理,不新建退避
- **两个通道的条目形状必须一致** → 都产出 `{title, url, domain, seendate}`;`channel` 字段区分来源,下游(brief 模板、`check_report.py` 白名单)无需按通道分支

## Migration Plan

无需迁移:采集层改动只影响今后生成的快照,已归档 `data/*.json` 不动,历史日报不重算。

回滚:删掉 `config/endpoints.json` 的 `gnews_rss_url` → gnews 通道静默停用(与 `feeds.py`「未配置 = 有意停用」同一约定)→ 全部币种回到 GDELT-only,即现状。

## Open Questions

无。GDELT 去留已由 D1 定为空洞补位;白名单 vs 黑名单已由 D2 的实测对照定案;原文 URL 不可得已由 D5 实测确认为事实而非待办。
