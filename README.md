# macro — 五币种外汇日报/周报管线

零 API key、零第三方依赖(Python 3 标准库 only)的外汇报告管线:
每日用免费公开数据源(Frankfurter / exchange-api / DBnomics / GDELT / 静态央行年历)
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
| 事件 | GDELT DOC 2.0 | ✅ 但本机 IP 长期 429,覆盖不稳定 |
| 官方公告 | Fed press RSS、ECB press RSS | ✅ 零 key |
| 美国 CPI | BLS 公共 API v1(零 key) | ✅ 滞后 2 个月;同比由脚本按同月计算 |
| CPI 同比 ×5、政策利率 ×5 | BIS Stats API 直连(零 key,`text/csv`) | ✅ CPI 滞后 2 个月、政策利率 7–12 天 |
| 经常账户 ×5 | DBnomics(IMF 口径) | ⚠ BIS 不覆盖,仍滞后;快照 `lag_months` 显式披露 |

**宏观来源优先级:BLS > BIS > DBnomics。** 三者逐指标独立命中——BIS 整体不可达、
缺必需列、或缺某经济体时,只有受影响的指标回落 DBnomics,其余保持 BIS。
删掉 `endpoints.json` 里两个 `bis_*_url` 即整体回滚(未配置 = 有意停用)。

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

**为什么直连**:DBnomics 是 IMF/BIS 的镜像,2026-08-11 实测滞后 8–17 个月,
且五经济体政策利率**全部给出过期值**(如巴西 15.0 vs 实际 14.25)。
`config/indicators.json` 里政策利率的 `series_id` 本来就是 `BIS/WS_CBPOL/D.XX` ——
上游一直是 BIS,直连只是去掉中间商。

**探针失败或有意未接入的源**(不写进 `config/endpoints.json`,避免每日缺漏噪音):

- BSP(菲律宾央行):SharePoint REST 实测可达,但 `robots.txt` 对非搜索引擎 UA
  写的是 `Disallow: /` —— **出于合规有意不接入**,非技术障碍
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

校验(新流程必须带溯源参数):

    python3 scripts/check_report.py reports/daily/DATE.md data/DATE.json \
      --brief briefs/DATE-brief.md --mode daily --strict-brief
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

    config/    endpoints.json(全部外部 URL 模板)与 indicators.json(DBnomics series)
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
