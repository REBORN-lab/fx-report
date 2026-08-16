# macro — 五币种外汇日报/周报管线

零 API key、零第三方依赖(Python 3 标准库 only)的外汇报告管线:
每日用免费公开数据源(Frankfurter / exchange-api / BIS / IMF / BLS / Google News / 静态央行年历)
采集 USD 兑 PHP/THB/BRL/EUR 的汇率、宏观指标与事件快照,
再由 Claude Code skill 两步生成中文日报(快照 → 要点表 → 叙事),
报告数字经 `scripts/check_report.py` 强制溯源校验;周报按主题聚合最近 7 天日报。
Slack 推送与 cron 调度由使用者自行接线(范围外)。

(运行文档见下文,由实施任务 16 补全。)

## 运行

以下 claude 无头命令的形态经 2026-08-10 端到端实测确认(实测推翻了早期草案的
仅 `--permission-mode acceptEdits` 形态)。

日报(无头模式;cron 接线自理):

    cd <仓库根>
    claude -p "/fx-daily-report" --permission-mode acceptEdits --allowedTools "Bash(python3 *)" "Bash(python3*)"
    # 指定日期回填: claude -p "/fx-daily-report 2026-08-08" --permission-mode acceptEdits --allowedTools "Bash(python3 *)" "Bash(python3*)"

**定时时点(重要)**:主汇率源 Frankfurter 转发的是 ECB 参考价,每工作日约
16:00 CET(夏令时 14:00 UTC / 冬令时 15:00 UTC)才定盘一次,周末与欧盟假日不发布。
cron **须排在 17:00 UTC 之后**;早于定盘时点跑会取到前一日的价,连续多日"汇率没动"
其实是同一次定盘被重复读取(2026-08 试运行即因 03:04 UTC 的时点产生 12/12 连平)。
快照逐币种记录 `ref_date`,报告层据此区分"参考价未更新"与"价格持平"。

周报(建议每周一跑,聚合最近 7 天;另需放宽 ls/date):

    claude -p "/fx-weekly-report" --permission-mode acceptEdits --allowedTools "Bash(python3 *)" "Bash(python3*)" "Bash(ls *)" "Bash(date *)"

说明:仅 `--permission-mode acceptEdits` 时,无头会话内的 python3 命令无人可批,
skill 会按"无快照不生成报告"前置约束正确终止(零产物)——`--allowedTools`
白名单参数是必需的。

已知行为:无头 + 白名单环境下 heredoc 可能被命令安全解析器拦截,skill 的
决策日志步骤会自动改用临时 JSON 文件经 stdin 重定向(等效、数据正确,无需干预)。

## 数据源(2026-08-11 本机探针实测定案)

| 用途 | 源 | 状态 |
|---|---|---|
| 汇率主源 | Frankfurter(ECB 参考价) | ✅ 每工作日约 16:00 CET 定盘 |
| 汇率副源 | exchange-api(jsDelivr / Cloudflare) | ✅ |
| 事件主通道 | Google News RSS(零 key)+ 域名白名单闸门 | ✅ 2026-08-12 实测 5/5 币种、零 gap |
| 事件补位 | GDELT DOC 2.0 | ⚠ 本机 IP 长期 429(同日 2/5 币种);仅在主通道某币种落空时才请求 |
| 官方公告 | Fed press RSS、ECB press RSS | ✅ 零 key |
| 美国 CPI | BLS 公共 API v1(零 key) | ✅ 滞后 2 个月;同比由脚本按同月计算 |
| CPI 同比 ×5、政策利率 ×5 | BIS Stats API 直连(零 key,`text/csv`) | ✅ CPI 滞后 2 个月、政策利率 7–12 天 |
| 经常账户 ×5 | IMF 官方 SDMX 直连(零 key,SDMX-CSV) | ✅ 2026-08-16 实测 5/5 经济体、零 gap;滞后 1 个季度 |

### 事件通道:主通道 + 白名单闸门 + 空洞补位

主通道是 Google News RSS(`gnews_rss_url`),每币种 1 次 GET、无间隔;**仅当某币种
经过滤后剩 0 条时**才对该币种发起 GDELT 补位(未落空的币种一次 GDELT 请求都不发)。
GDELT 的限流判定与退避逻辑未改动。

**为什么必须有白名单闸门**:裸接会把噪音换进沉默。2026-08-12 实测 PHP 88 条里
76 条来自 `bybit.com` 的加密货币换算页——"PHP" 同时是加密交易对代码。沉默有缺漏
机制可披露,噪音没有。四种过滤方案实测对照后取**域名白名单**(`config/news_sources.json`):
黑名单漏汽车促销、关键词复核漏内容农场,而白名单当日 0 噪音;决定性理由是**有界性**
——黑名单要永远追着新垃圾站跑,白名单是一个可审计的文件。

**过滤量逐层落盘**:快照每币种记 `gnews_filter{raw, undated, out_window, offlist, kept}`,
四层账闭合。没有它,"该币种确实无事件"与"抓到 88 条但全部不相关"在快照里完全同形。
白名单外的真新闻确实会被丢弃,这是有意的"宁可少说",丢弃量由 `offlist` 逐日可见。

**两道时间过滤**:查询带服务端 `when:2d`,但它不可信(实测 `site:` 查询下 5 条里
4 条 `pubDate` 仍是 2023 年),故本地按 RFC 2822 解析 `pubDate` 再过滤一次;
解析不了的单独计入 `undated`,既不算窗口内也不静默丢弃。

**已知不可得**:`<link>` 是 Base64 包装的跳转页,解码得 364 字节 Google 内部 token,
标准库还原不出原文 URL。故快照的 `url` 对该通道是跳转链,可回溯的"谁说的"由
`domain`(取自 `<source url=>`,实测 88/88 全有)承担。

**条数上限 99–100**:实测宽查询返回 100、加 `num=200` 返回 99,不是契约值。判据取
下界 `>= 99` 落 `source_capped`——漏报截断会让报告把下界当全量断言,误报只让结论变弱。

**回滚**:删掉 `config/endpoints.json` 的 `gnews_rss_url` 或 `config/news_sources.json`
任一,整通道静默停用,全部币种回到 GDELT-only(即接入前的现状)。

**宏观来源:三个官方直连,没有回落层。** 美国 CPI 走 BLS(优先于 BIS);
CPI 同比与政策利率走 BIS;经常账户走 IMF。三者逐指标独立命中,一个源出事
只影响它自己覆盖的那几条。删掉 `endpoints.json` 里对应的 `*_url` 即停用该源
(未配置 = 有意停用)。

**没有回落层是有意的**:原先的 DBnomics 回落已整只删除——它的 **API 域**
robots.txt 是 `User-agent: *` / `Disallow: /`(2026-08-16 实测 HTTP 200,26 字节),
整站禁爬。这与 BSP、CME 出局适用的是同一把尺子(见下文"有意未接入的源")。
删的是路径本身,不是"默认关闭的开关":陈旧调用点会静默地什么都不做,而 grep
仍看得见它,复核者以为还在用。

去掉回落后"取不到就没有这一行"成了常态路径,于是采集层有一条硬不变量:
**每个被跟踪的指标,要么产出一行,要么产出一条 scope 定位到它(`经济体/指标`)
的缺漏**。否则"整块消失"与"这一期确实没有发布"在快照里同形,下游结论句
会把前者说成后者。

BIS 两个 dataflow:

| dataflow | 内容 | 参数 |
|---|---|---|
| `WS_CBPOL` | 五经济体政策利率(日频) | `detail=dataonly&lastNObservations=400` |
| `WS_LONG_CPI` | 五经济体 CPI 同比(月频,`UNIT_MEASURE=771`) | `detail=dataonly&lastNObservations=4` |

`detail=dataonly` 是必需的:实测同一查询 891 KB → 40 KB(22 倍)。`WS_CBPOL` 按**日历日**
出行(2026-08-11 实测 400 个观测跨 399 天,美国区间内无 `NaN`),故 `lastNObservations=400`
≈ 13.1 个月;覆盖实测最深的回溯需求——美国上次利率变动 2025-12-10,需回溯 **237** 个观测,
余量 163 个(≈ 5 个月)。政策利率的"前值"取的是**上一次变动之前的水平**,不是上一个观测。
同理,政策利率的"新发布"判据是**水平变了**,不是序列多了一行。
BIS 用 `XM` 表示欧元区,采集层映射到仓库内部的 `EA`。

IMF 经常账户(`imf_bop_url`):dataflow `IMF.STA,BOP,21.0.0`,键
`USA+G163+PHL+THA+BRA.NETCD_T.CAB.USD.Q`,`lastNObservations=4`。两点实测坑:
`api.imf.org` **无视 `?format=csv`**,只认 `Accept: application/vnd.sdmx.data+csv`
(不发这个头拿回来的是 SDMX-ML);欧元区代码是 **`G163`**(codelist 名称
"Euro Area (EA)"),`U2` / `XM` / `EA` 在该 dataflow 里都查无此码。SDMX-CSV
实测 53 列,一律按**列名**取。

**IMF 侧 robots 实测(2026-08-16)**:`www.imf.org/robots.txt` HTTP 200,Disallow
列表里**没有** `/external/sdmx/`(即我们走的路径未被禁);`api.imf.org/robots.txt`
HTTP 502(Azure 网关),该主机**未发布** robots 限制 —— 如实记为"未发布",
不当作"已放行"或"已禁止"。

**采集层 User-Agent**:`fx-macro-report/1.0 (+https://github.com/REBORN-lab/macro)`。
自报项目名与可联系出处;**永不**写 `Mozilla/...` 或 `Googlebot` —— 伪装成浏览器
或搜索引擎爬虫是在规避源站按 UA 作出的准入判断,与尊重 `robots.txt` 是同一条纪律。

**为什么直连**:镜像源 2026-08-11 实测滞后 8–17 个月,且五经济体政策利率
**全部给出过期值**(如巴西 15.0 vs 实际 14.25);经常账户那一侧,此前记录的
「TH 整行缺失」也不是 IMF 没数据,而是镜像的问题 —— 直连下五国全有观测。
注意直连与镜像的**计价单位不同**(镜像百万美元、直连美元),换源当日由
快照的 `source_changed_from` 字段标出两值不可比。

**探针失败或有意未接入的源**(不写进 `config/endpoints.json`,避免每日缺漏噪音):

- BSP(菲律宾央行):SharePoint REST 实测可达,但 `robots.txt` 对非搜索引擎 UA
  写的是 `Disallow: /` —— **出于合规有意不接入**,非技术障碍
- DBnomics **API 域**:2026-08-16 实测 `robots.txt` 为 `User-agent: *` /
  `Disallow: /`(HTTP 200,26 字节),整站禁爬 —— 与 BSP 同一把尺子,已于
  本轮把回落路径整只删除(网页域放行,被禁的是我们在打的 API 域)
- BOT(泰国央行)`apigw1.bot.or.th`:DNS 无 A 记录,且本就需要 client key
- PSA(菲律宾统计局):Cloudflare JS 挑战,标准库不可达
- 泰国 MOC:`price.moc.go.th` 403 / CPI 文件 500 / `dataapi.moc.go.th` 全路径 404
- IMF `dataservices.imf.org`:DNS 已下线
- ECB Data Portal 旧 `ICP` dataflow:上游 2026-02-04 自行停更,停在 2025-12

完整探针记录(99 个候选源、52 可用)见
`super-research/2026-08-11-数据源扩展探针/`。

只跑采集(不生成报告):

    python3 -m scripts.collect --date 2026-08-10

周度聚合(周报前置步骤):

    python3 scripts/weekly_digest.py --week 2026-W33

校验(日报模式下三个溯源入参是**必给项**,缺一个即退出码 2 并打印可复制的
正确命令行;「要点表 ⊆ 快照」默认开启,唯一弱化入口是 `--no-strict-brief`,
它会打印带计数的降级声明):

    python3 scripts/check_report.py reports/daily/DATE.md data/DATE.json \
      --brief briefs/DATE-brief.md \
      --prior reports/daily/<前一日>.md --decision-log state/decision-log.jsonl
    python3 scripts/check_report.py reports/weekly/WEEK.md --mode weekly \
      --digest state/weekly-digest-WEEK.json --daily reports/daily/<每一天>.md

测试:

    python3 -m unittest discover -s tests -t . -v

## 环境变量

- `FRED_API_KEY`(可选):存在时用 FRED release dates 增强前一日美国数据发布判定;
  不设时走零 key 默认路径(静态年历 + GDELT 承担判定,不记缺漏)。
- `FX_GDELT_DELAY_S` / `FX_GDELT_BACKOFF_S`:仅测试提速用,生产禁止设置
  (默认串行 5s / 退避 30s,是 GDELT 限速约束的一部分)。

## 目录

    config/    endpoints.json(全部外部 URL 模板)与 indicators.json(跟踪的经济体×指标)
    state/     calendar-<年>.json 静态央行年历;decision-log.jsonl 决策日志(脚本代笔)
    data/      每日快照 YYYY-MM-DD.json(报告数字的唯一来源)
    briefs/    每日要点表(LLM 第一步产物 + review.py 注入复盘材料)
    reports/   daily/YYYY-MM-DD.md 与 weekly/YYYY-Www.md
    scripts/   collect 采集包、review.py、log_decision.py、check_report.py
    skills/    fx-daily-report 与 fx-weekly-report(.claude/skills 有同名链接)
    tests/     单元/集成/故障注入测试(含 fixtures)

## 年历维护

`state/calendar-<年>.json` 含五家央行(Fed/ECB/BSP/BOT/BCB)各自的全年议息 events。
维护方式:每年 12 月**创建新文件** `state/calendar-<次年>.json`(不修改本年文件),
按文件内 `sources` 列出的各央行官网抄录次年日程,并设置次年的 `valid_until`;
旧文件保留存档。采集自动选取文件名排序最后的年历;`valid_until` 过期后,
采集会在快照 gaps 中持续告警提示更新。

硬性格式约束:日期与 `valid_until` 必须是带横线的 ISO 格式(YYYY-MM-DD)。
非 ISO 形态(如 "20270101")会使过期告警静默失效(字符串比较层面),代码不校验,
由本说明约束。日期必须来自官网,禁止凭记忆填写。

## 边界

本仓库交付到"本地 markdown 报告落盘"为止:Slack/邮件推送、cron 调度、部署
由使用者自行接线。报告数字均逐字来自快照,LLM 不做任何计算——校验器
(`scripts/check_report.py`)在每次生成后强制执行该纪律。
