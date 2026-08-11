---
name: fx-daily-report
description: 生成五币种(USD/EUR/PHP/THB/BRL)中文外汇日报。先跑采集脚本得数据快照,再两步生成(快照→要点表→叙事),数字强制溯源校验。可选参数:日期 YYYY-MM-DD,默认今天(UTC)。
---

# 外汇日报生成

严格按五步顺序执行,任何一步不得跳过。数字纪律条款不可协商。
设 DATE = 参数给出的日期(YYYY-MM-DD);未给参数时 DATE = 今天(UTC)。
全部命令在仓库根目录执行。

## 第 1 步:采集快照(脚本)

运行:`python3 -m scripts.collect --date DATE`

确认 `data/DATE.json` 已生成;**若不存在,立即终止并报错**——采集是前置步骤,
禁止在无快照时生成报告。命令输出的 gaps 列表记下,后面缺漏节要用。

## 第 2 步:生成要点表(LLM,产物落盘)

只读 `data/DATE.json`,写 `briefs/DATE-brief.md`,模板:

    # 要点表 DATE

    ## 跨币种共同主线
    -(≤3 条候选,基于快照事件与年历命中归纳)

    ## USD
    - 昨日事件 top:<title>(<domain>)……至多 3 条;tone_avg: <值或 无>
    - 数据发布:<indicator> 最新 <value> 前值 <prev> 期 <period>(只列 is_new_release
      为 true 或与年历命中相关的;没有写"无")
    - 汇率变动:primary <primary>,prev <prev_primary>(USD 为基准货币,本行写"—")
    - 年历命中:<bank> <event>(<date>)(没有写"无")
    - 缺漏:<gaps 中 scope 为本币种或 all 的条目>(没有写"无")

    ## EUR
    (同 USD 结构;汇率行填 EUR 的 primary/prev_primary)

    ## PHP / ## THB / ## BRL
    (同上,各一节)

    ## 快照缺漏总表
    - [<source>/<scope>] <reason>(逐条照抄快照 gaps;为空写"无")

**数字纪律:要点表中每个数字必须从快照 JSON 逐字复制**(60.843 就写 60.843,
不得写 60.84)。禁止计算涨跌幅、百分比、差值;禁止写快照里不存在的任何数字。
rates 中 suspect 为 true 的币种,汇率行须注明"(双源偏差超阈,数据可疑,
主源 <primary> / 副源 <secondary>)"。

## 第 3 步:注入复盘材料(脚本)

运行:`python3 scripts/review.py --date DATE`

它把"## 复盘材料"追加到要点表末尾,并回填决策日志的 direction_outcome。

## 第 4 步:生成日报(LLM)

**只依据 `briefs/DATE-brief.md`(含复盘材料)**写 `reports/daily/DATE.md`,模板:

    # 外汇日报 DATE

    ## 执行摘要
    -(≤6 条,每条一句话;跨币种共同主线优先)

    ## 美元(USD)
    **昨日发生**:……
    **定价含义**:……
    **情景与触发条件**:若 <触发条件>,则关注 <方向/影响>。

    ## 欧元(EUR)
    (同结构;随后 ## 菲律宾比索(PHP)、## 泰铢(THB)、## 巴西雷亚尔(BRL))

    ## 复盘
    -(逐币种一句话:对照复盘材料中前一运行日观点、触发判定与方向核对结果;
      复盘材料写"首次运行"时,本节正文写"首次运行,无历史观点可复盘")

    ## 数据缺漏
    - [<source>/<scope>] <reason> — 影响:<对哪些结论打折扣>
    (逐条对应要点表"快照缺漏总表";总表为"无"时本节正文恰为一个字:无)

**禁令(违反任何一条即校验失败):**
1. 禁止无条件方向预测——所有观点必须是"若 X 发生则关注 Y"的情景+触发条件式。
2. 数字只准逐字抄自要点表(其唯一源头是快照);禁止计算、估算、回忆任何行情数字。
3. 缺漏节列出的数据,正文禁止引用或臆测(该币种如实写"昨日无××数据(采集失败)")。
4. 市场共识/预期值只在 GDELT 文章标题明说时可用,且必须标"据报道"转引。
5. 禁止逐条罗列快照原始数据(流水账);只呈现驱动结论的关键数字。
6. 无明确驱动的币种如实写"昨日无明确驱动",不编造归因。
7. 每币种节正文不超过约 300 中文字;执行摘要不超过 6 条。

**决策日志(写完报告立即执行,经脚本代笔,禁止直接编辑 jsonl):**
把当日五币种"情景与触发条件"整理成 JSON 数组,经 stdin 传入:

    python3 scripts/log_decision.py add <<'EOF'
    [{"date": "DATE", "currency": "PHP", "scenario": "<情景一句话>",
      "trigger": "<触发条件一句话>", "watch_direction": "up|down"},
     {"date": "DATE", "currency": "USD", "scenario": "…", "trigger": "…",
      "watch_direction": null}]
    EOF

watch_direction 语义:USD/该币汇率方向,"up"=该币对美元走弱;USD 自身填 null。

**复盘判定(要点表含复盘材料时执行):**对复盘材料中每条观点,依据**当日要点表
里的证据**判断触发条件是否发生,逐条运行:

    python3 scripts/log_decision.py set-review --date <观点日> --currency <币> \
      --judgement "<引用要点表证据的一句话>" --verdict <命中|未命中|无法判定>

verdict 规则:触发条件未发生 → 无法判定;触发发生且方向核对=命中 → 命中;
触发发生且方向核对=未命中 → 未命中;引不出证据 → 无法判定。

## 第 5 步:校验(脚本,不可跳过)

运行:
`python3 scripts/check_report.py reports/daily/DATE.md data/DATE.json --brief briefs/DATE-brief.md --mode daily`

- 退出码 0:完成,输出报告路径,结束。
- 非 0:按输出的违规项修改报告**一次**(仍只准用要点表数字),重跑校验。
- 第二次仍非 0:在报告首行前插入一行
  `> ⚠ 本报告未通过自动自检:<违规项摘要>`,保留落盘,如实结束。
