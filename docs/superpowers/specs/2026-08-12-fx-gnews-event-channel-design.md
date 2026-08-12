---
super_coding_change: fx-gnews-event-channel
role: technical-design
canonical_spec: openspec
---

# 技术设计:Google News 事件主通道 + 域名白名单闸门

OpenSpec 是需求的唯一权威(`openspec/changes/fx-gnews-event-channel/`)。本文只写**怎么实现**。
`design.md` 的 D1–D6 是已由 2026-08-12 实测锁定的方向;本文把它们落到函数边界、
字段形状、参数取值与变异靶点上。

## 1. 循环形状:两趟,`holes` 是显式列表

`events.collect()` 现在是「按 `query_order` 串行 + 每次 sleep 20 秒」的单趟形状。
gnews 不需要间隔(每币种 1 次 GET,共 5 次,远低于任何合理阈值),GDELT 需要。
两种节奏塞进同一个循环会让函数分叉,改成两趟:

```
collect(cfg)
  ├─ 第一趟 gnews:for currency in KEYWORDS(无 sleep)
  │     entry, err = _gnews_one(cfg, currency)
  │     err 非 None            → 记 gap、holes.append、entry 的计数节写 null
  │     entry["articles"] 为空 → holes.append(currency)   # 计数照样落盘
  │     out[currency] = entry
  └─ 第二趟 GDELT 补位:for currency in query_order(date) if currency in holes
        沿用既有 _query_with_retry / sleep / 退避,一行不改
        取到 → 覆写 out[currency] 的 articles/raw_count/cap/channel,**保留 gnews_filter**
        没取到 → 记 gap,原因体现「两条通道均已尝试」
```

`holes` 是显式列表而不是隐含条件,是为了让「没出现空洞就一次 GDELT 请求都不发」
能被测试直接断言(fixture server 计请求数 == 0),而不是靠观察副作用推断。

第二趟仍走 `query_order` 轮转:补位时可能一次涉及多个币种,轮转的公平性理由
(限流造成的缺失不恒定落在同一批币种)依然成立。

## 2. 字段形状:嵌套计数 + 条目自描述上限

```jsonc
"events": {
  "PHP": {
    "articles":           [...],     // 最终采用的条目(来自 channel 指明的通道)
    "articles_raw_count": 8,         // 采用通道的源返回条数 —— 既有语义不变
    "source_cap":         8,         // 该条目所属通道的上限
    "source_capped":      true,      // 脚本算好的布尔,下游只读不比
    "channel":            "gdelt",
    "gnews_filter": {                // gnews 那一趟的逐层账,补位成功也保留
      "raw": 88, "undated": 0, "out_window": 0, "offlist": 86, "kept": 0
    }
  }
}
```

### 2.1 为什么 `source_cap` 写进条目而不是查 `meta.caps`

`derive.py:_count_capped` 与 `weekly_digest._channel` 现在都按
`articles_raw_count >= meta.caps.gdelt_records`(缺失退回 `MAX_RECORDS=8`)判截断。
两条通道混用后这个比较会**错位**:GDELT 补位来的条目 `raw=8`(真的顶到了)去跟
gnews 的上限 100 比,`8 >= 100` 为假 —— **截断漏报**。

替代方案是让下游按 `channel` 去 `meta.caps` 查表。否决:那需要在 `derive.py` 与
`weekly_digest.py` 两处各写一遍 channel→cap 映射,而 `_channel` 的 docstring 自己
就记着这个教训——「official 与 GDELT 曾各写一份,于是 official 有截断披露而
GDELT 没有(第三轮 I10)」。

更进一步:连布尔也由采集层算好(`source_capped`),下游只读。这是本仓库
`weekly_digest._verdict` 已确立的不变量形态——**把「能不能下结论」从下游手里收回脚本**。

`meta.caps` 仍写 `gnews_records`(与既有 `gdelt_records` / `official_daily` 同格式),
用于存量快照的回退与人工审计。

### 2.2 下游的兼容改法(本 change 必须一并做)

`derive.py:_count_capped` 与 `weekly_digest._channel` 改为**优先读条目的
`source_capped`**,缺失时才退回既有的 `raw >= cap` 逻辑。存量快照没有该字段,
行为与现在完全一致;新快照走权威布尔。

这一条修正了 `tasks.md` 3.2 里「确认 `derive.py:146` 与 `weekly_digest.py:306`
无需改动」的判断——design 阶段实查后确认它们**需要改动**,tasks 已相应更新。

### 2.3 `gnews_filter` 为什么在补位成功后也要保留

补位成功意味着 `articles` 来自 GDELT。若此时丢掉 gnews 的账,「gnews 抓到 88 条
但白名单把 86 条挡在外面」这个信息就消失了——而它恰恰是判断白名单是否配得太严的
唯一依据。保留它,快照才能同时回答「最后用了什么」和「主通道发生了什么」。

gnews **整体失败**(取数异常 / 非 XML / 无 `<item>`)时 `gnews_filter` 写 `null`
而非各项写 0:缺输入写 null 不写 0 是仓库硬纪律,写 0 会让「跑了但一条都没留下」
与「压根没跑成」在快照里同形。

## 3. 纯函数边界(单测不打网络)

- `_gnews_parse(text)` → `[{title, url, pubdate_raw, domain}]`。`xml.etree` 解析;
  非 XML、空正文、无 `<item>` 一律 **抛 ValueError**,由上层转 gap。
  **绝不返回空列表** —— 那会冒充「源确实无数据」,是本仓库反复栽的形态
  (events.py 现有的 `parsed ok but no usable 'articles' list` 分支就是同一道门)。
- `_pubdate(raw)` → `datetime | None`。`email.utils.parsedate_to_datetime`;
  解析失败返回 `None`;无 tzinfo 按 UTC 补齐,不猜本地时区。
- `_host(url)` → 小写主机名,剥 `www.` 前缀。
- `_in_whitelist(host, domains)` → bool。判据 `host == d or host.endswith("." + d)`。
- `_gnews_filter(items, lo, hi, domains)` → `(kept, counts)`。四层账在这一个函数里出,
  避免调用方各算各的。

## 4. 白名单文件

`config/news_sources.json`,扁平数组:

```json
{"comment": "…配置缺失 = 有意停用,删掉即整通道回滚…", "domains": ["reuters.com", "…"]}
```

按币种分组被否决:5 倍维护量,而查询词已经按币种圈定了召回集——Bangkok Post
不会出现在 BRL 的结果里,分组防的是不存在的问题。

加载分级(与仓库既有「未配置 = 有意停用」/「配置了但失败 = 记 gap」两级约定一致):

| 情形 | 处置 |
|---|---|
| 文件不存在 | gnews 通道静默停用,全部币种走 GDELT(即现状),**不记 gap** |
| 文件存在但 JSON 解析失败 | 记 gap,回落 GDELT |
| `domains` 不是 list 或为空 | 记 gap,回落 GDELT |

第三条尤其重要:空白名单会把一切过滤成 0 条,是最危险的形态。若它静默通过,
五个币种会同时"没有事件",而日报会把这写成五国昨日均无驱动。

## 5. `source_capped` 取 `>= 99`

实测:宽查询 `the` / `dollar` 均返回 **100** 条;加 `&num=200` / `&count=200` 返回 **99**。
上限不是契约化的精确值,是"约 100"。

两种错法二选一:
- 漏报截断 → 报告把下界当全量断言(「白名单内 10 条」被读成"总共就 10 条")
- 误报截断 → 报告多说一句"可能被截断",结论只会变弱

按仓库「宁可少说,不可错说」,取下界:`GNEWS_SOFT_CAP = 99`,判据 `raw >= GNEWS_SOFT_CAP`。
**代价明说**:恰好 99 条的真实完整结果会被误标为截断。用 `>=` 而非 `==` 是为了
容忍源返回 101 条。

## 6. 变异靶点

本仓库以变异测试为审查标准(存活即未测住)。以下判断**必须**有测试杀掉对应变异:

| # | 变异 | 必须失败的测试 |
|---|---|---|
| M1 | 白名单用裸 `endswith(d)` | `notreuters.com` 不得命中 `reuters.com` |
| M2 | 白名单不匹配子域(仅 `==`) | `interaksyon.philstar.com` 命中 `philstar.com` |
| M3 | 去掉本地 pubDate 窗口过滤 | 含窗口外 `pubDate` 的响应,该条不进快照 |
| M4 | pubDate 不可解析当成窗口内 | 坏 `pubDate` 条目不进快照且 `undated` 计数为 1 |
| M5 | `offlist` 计数恒 0 | 88 进 2 出的响应,`offlist` 为 86 |
| M6 | `source_capped` 恒 False | 返回 100 条时为 true |
| M7 | `source_capped` 用 `==` 而非 `>=` | 返回 99 条时仍为 true |
| M8 | 空洞判定用过滤**前**条数 | 88 条全被过滤时仍触发 GDELT 补位 |
| M9 | 没有空洞也发 GDELT | 五币种都有条目时 GDELT 请求数为 0 |
| M10 | `_gnews_parse` 失败返回 `[]` 而非抛错 | 非 XML 正文记 gap,不落成"源无数据" |
| M11 | 空 `domains` 不记 gap | 空白名单记 gap 并回落 GDELT |
| M12 | 补位成功后丢掉 `gnews_filter` | 补位后 `gnews_filter.raw` 仍为 88 |
| M13 | gnews 失败时 `gnews_filter` 写 0 而非 null | 取数异常时该节为 null |
| M14 | 下游忽略 `source_capped` 仍按 raw≥cap 比 | GDELT 补位条目 raw=8 时截断被识别 |

M14 覆盖 §2.2 的下游改动:构造一份 `channel: "gdelt"`、`raw=8`、`source_capped: true`
的快照,断言 `derive._count_capped` 与周度聚合器都认它,而不是拿 100 去比。

## 7. 边界条件清单

- `<item>` 缺 `<source>` 或 `source` 无 `url` → 该条 domain 不可得 → 不可能命中白名单
  → 计入 `offlist`(不另设第五个计数;它确实是"不在白名单内")
- 同一标题在 gnews 与 GDELT 补位结果里都出现 → 不会发生,两者互斥(补位只在 gnews 为空时)
- 五币种全部空洞 → GDELT 被打满 5 次,采集耗时回到现状水平,可接受
- `pubDate` 有 tzinfo 且为非 UTC → `parsedate_to_datetime` 已归一化,直接比较
- 响应含重复标题 → 复用既有 `_dedupe_titles`,在白名单过滤**之后**去重
  (先去重会让 `offlist` 的分母与 `raw` 对不上)
- 查询词含 `"` 与空格 → `urllib.parse.quote` 编码;查询词仍写死在 `KEYWORDS`(D6)

## Spec Patch

无。delta spec 的 16 个场景已覆盖上述全部行为:`source_cap` / `source_capped` 由
「源返回条数顶到通道上限时 SHALL 落盘截断标记」要求,`gnews_filter` 由「每币种的
快照条目 SHALL 逐层记录过滤计数」要求,白名单加载分级由「配置缺失时该通道视为
有意停用并回落 GDELT,MUST NOT 记为缺漏」与「主通道响应畸形 → 记入缺漏并走补位」
两条共同覆盖。
