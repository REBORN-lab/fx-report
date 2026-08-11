---
name: fx-weekly-report
description: 聚合最近 7 个自然日的外汇日报与决策日志,按主题重聚类生成中文周报(本周主线/各币种归因/复盘汇总/下周关注/缺漏汇总),结构强制校验。
---

# 外汇周报生成

设 TODAY = 今天(UTC),WEEK = TODAY 的 ISO 周号(格式 YYYY-Www,如 2026-W33,
用 `date -u +%G-W%V` 取得)。输出 `reports/weekly/WEEK.md`。

## 第 1 步:收集素材(脚本辅助,数字禁止心算)

1. 列出最近 7 个自然日(TODAY-6 … TODAY)中存在的日报:
   `ls reports/daily/ | sort`(对照日期清点)
   记录:覆盖日报 N 份、日期列表、缺失日期列表。
2. (复盘计数已由第 4 步的 digest 提供,不再单独跑 stats —— 两处窗口定义不同,
   并存会让同一份周报有两个都"合法"的计数。)
3. 逐份读取这 N 份日报全文(含各自的"数据缺漏"节)。
4. 跑周度聚合器,输出原样照抄:
   `python3 scripts/weekly_digest.py --week WEEK`
   它写出 `state/weekly-digest-WEEK.json`,内含各币种周涨跌/周区间/定盘次数、
   事件计数、缺漏按源统计、verdict 计数。**周报里的跨日数字一律逐字引用它**,
   不得自己从日报里心算(与日报引用快照 derived 同一模式);某项为 null 时
   写"不可得",禁止补算。
5. 读 `state/calendar-*.json`(多个文件时取文件名字典序最大者,与采集层一致),
   摘出未来 2-3 周内(TODAY+1 … TODAY+21)的日程条目供"下周关注"引用——只准
   摘文件里实际存在的条目,文件没有的类别不得凭记忆补;年历过期或缺失时记入
   缺漏汇总。

**N 为 0 时终止并报错(无素材不生成周报)。N < 3 时照常生成,但覆盖声明
必须写明缺失日期(spec"日报不足"场景)。**

## 第 2 步:生成周报(LLM)

只依据第 1 步素材写 `reports/weekly/WEEK.md`,模板:

    # 外汇周报 WEEK

    > 覆盖日报:N 份(<日期列表>);缺失日期:<列表,无则写"无">
    > (digest 的 `skipped` 非 0 时,本行须追加"另有 <skipped> 份快照因损坏被
    >  跳过"——`days` 分母是过滤后的份数,不说明会让读者把削过的分母当全周)
    > 复盘图例:命中/未命中=触发发生且方向核对有果;无法判定=已复盘但触发
    > 条件未发生或证据不足;未判定=尚未复盘。本行不含数字。

    ## 本周主线
    -(≤3 条,主题式,跨币种归纳)

    ## 各币种一周归因
    (五币种各一小段:USD/EUR/PHP/THB/BRL,基于日报内容做一周归因;
     跨日数字逐字引 digest:周涨跌 <chg_pct_week>%、周区间 <range_low>–<range_high>
     (基于 <fixings> 次不同定盘)、GDELT 事件 <articles_distinct> 条去重后
     (<days_gdelt_failed>/<days> 天采集失败;<articles_capped_days> 天顶到每日上限
     <articles_daily_cap> 条,那些天的实际条数只多不少)、本周官方公告
     <official_in_window> 条(<days_official_collected>/<days> 天采到该通道)。

     **事件计数的三条硬规则** —— 前四轮审查连续五次栽在这里:
     1. 官方公告只准引 `official_in_window`(已按发布日过滤到覆盖区间、并跨日
        去重)。**禁止引用 `official_sampled`** ——RSS 只给"最新 N 条"、不按日期
        过滤,该字段实测混着上个月的公告(2026-08-11 抓到的三条 Fed 公告全部
        发布于 7 月)。`official_outside_window` 非零时须写明"另有 N 条为窗口外
        (更早发布)的公告"。`official_in_window` 为 0 而 `days_official_collected`
        非零 = 本周该央行确实没发公告,不是采集失败,必须这样写。
     2. GDELT 的 `articles_distinct` 同样是**封顶样本**,不是"本周新闻总数":
        `articles_capped_days` 非零的那些天被上限截断了。任何一处引用都要带上
        截断披露,与官方通道同等对待。
     3. `days_official_collected`(采到该通道)与 `days_with_official`(采到且非空)
        是两件事。写"仅 N/M 天有采集"只准用前者;把后者说成"没采到"就是把
        "央行本周没发公告"这个市场事实伪装成管道故障。
     `*_cap_assumed_days` 非零表示那几天的快照没记录采集上限、是按当前代码推定的,
     引用触顶结论时须注明"上限为推定"。

     两个通道口径不同,禁止相加,也禁止把 GDELT 失败说成"该币种无事件";
     **禁止在未逐日核对的情况下断言"官方通道在限流日提供了兜底"** ——
     `days_with_official` 与 `days_gdelt_failed` 都非零也不等于两者是同几天。
     要做这个判断,逐字读 digest 的 `by_date`:每个日期下 `articles` 为 null
     即当日 GDELT 失败,`official` 为正即当日有公告。只有两者在同一天成立,
     才能说兜底发生过;`by_date` 是唯一可引的依据,不得翻原始快照自行推断。)

    ## 复盘汇总
    - <digest verdicts 的四项计数,原样照抄>
    - 明细逐条:<日期> <币种> <verdict>(照抄 digest 的 verdict_details;
      该字段为 null 时写「决策日志不可用,本周复盘无法统计」,不得写成全 0)

    ## 下周关注
    -(基于各日报"情景与触发条件"与年历,≤5 条)

    ## 缺漏汇总
    - [<source>] <缺失内容简述> 波及 <日期列表>/<币种范围> — 影响:<一句话>
    (按源聚类各日报缺漏节条目,同源多日合并一行,日期列表不得省略;
     第 1 步发现的年历过期/缺失单列一行 [calendar],日期填 valid_until 或
     TODAY;本节无任何条目时才写"无")

**禁令:**
1. 一级/二级结构禁止按日期组织(不得出现 `## 2026-08-05` 式标题)。
   正文里提日期一律写完整形式 `YYYY-MM-DD`:写成 `08-07` 会被数字溯源当成
   两个裸数字拦下(校验器只识别完整日期形态)。
2. 数字只准逐字来自周度聚合文件(digest)、日报原文与年历文件原文;
   禁止自行计算或汇总数字。
3. 复盘汇总的计数行必须与 digest 的 verdicts 逐字一致。
4. 不得引用缺失日期的任何"数据"。

## 第 3 步:校验(脚本,不可跳过)

运行(**必须带 --digest 与全部当周日报**,否则数字溯源不生效):

    python3 scripts/check_report.py reports/weekly/WEEK.md --mode weekly \
      --digest state/weekly-digest-WEEK.json \
      --daily reports/daily/<日期1>.md --daily reports/daily/<日期2>.md ...

- 退出码 0:完成。
- 非 0:按违规项修改一次,重跑。
- 二次仍非 0:报告首行前插入 `> ⚠ 本报告未通过自动自检:<违规摘要>`,
  保留落盘,如实结束。
