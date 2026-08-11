## Why

诊断的两项遗留:①周报 85% 是日报重排,没有任何脚本级跨日聚合可供引用,"本周涨了多少/区间多宽"全靠 LLM 从日报里捞;②周报模式的 `check_report.py` **完全没有数字溯源**(只查结构),数字纪律纯靠 prompt 禁令 —— 日报有白名单硬约束,周报没有。此外前三个 change 的审查暴露了同一条缝隙:`brief ⊆ 快照` 无人校验(校验器只查 `报告 ⊆ 快照 ∪ brief`),LLM 在要点表里写错数字不会被发现。

## What Changes

- 新增 `scripts/weekly_digest.py`:读近 7 日快照与决策日志,**脚本确定性算出**周涨跌、周区间、事件计数、gap 按源统计、复盘 verdict 计数,写 `state/weekly-digest-<WEEK>.json`
- `skills/fx-weekly-report/SKILL.md`:第 1 步增"跑 digest",数字改为逐字引用 digest(与日报引用 derived 同一模式)
- `check_report.py` 周报模式接 `--digest`:数字白名单 = digest ∪ 各日报 ∪ 小整数,启用与日报同级的 `NUMBER_UNTRACEABLE` 溯源
- `check_report.py` 日报模式接 `--strict-brief`:校验 `brief ⊆ 快照`,堵住要点表环节的数字缝隙

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `fx-weekly-report`:周报数字来源与溯源校验
- `fx-daily-report`:要点表数字的溯源校验(brief ⊆ 快照)

## Impact

- 新文件:`scripts/weekly_digest.py`、`tests/test_weekly_digest.py`
- 改动:`scripts/check_report.py`(本序列首次改校验器)、两份 SKILL、`tests/test_check_report.py`、README
