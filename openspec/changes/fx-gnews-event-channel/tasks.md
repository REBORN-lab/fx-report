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
