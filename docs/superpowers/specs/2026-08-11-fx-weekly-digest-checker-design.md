---
super_coding_change: fx-weekly-digest-checker
role: technical-design
canonical_spec: openspec
---

# Technical Design: fx-weekly-digest-checker

需求规格以 OpenSpec delta spec 为准。上游:2026-08-11 四视角诊断 + 前三个 change 审查暴露的校验缝隙。

## Architecture

```
python3 scripts/weekly_digest.py --week YYYY-Www
  → state/weekly-digest-<WEEK>.json      ← 脚本确定性聚合
skills/fx-weekly-report/SKILL.md          ← 数字逐字引用 digest
python3 scripts/check_report.py <weekly.md> --mode weekly --digest <digest.json>
python3 scripts/check_report.py <daily.md> <snap.json> --brief <brief.md> --mode daily --strict-brief
```

## digest schema

```json
{
  "week": "2026-W33", "generated_from": ["2026-08-07", "..."],
  "rates": {"PHP": {"chg_pct_week": -0.19, "range_low": 60.75, "range_high": 60.867,
                    "fixings": 3, "first_ref_date": "2026-08-07", "last_ref_date": "2026-08-10"}},
  "events": {"PHP": {"total": 24, "days_with_data": 3, "days_failed": 2}},
  "gaps_by_source": {"gdelt": 7, "dbnomics": 3},
  "verdicts": {"命中": 0, "未命中": 0, "无法判定": 15, "未判定": 10}
}
```

- `chg_pct_week`:首末两个**不同 ref_date** 的 primary 之比,round 3 位;全周同一定盘 → null
- 缺输入一律 null(前一 change 的 C1 教训:填 0 就是编造)

## Components

**weekly_digest.py**:`build(snapshots, log_entries, week) -> (digest, problems)`;纯函数便于测试,I/O 在 `main()`。坏快照跳过并计入 `problems`(落盘为 `skipped` 字段,可见而非静默)。

**check_report.py**:
- `check_weekly(report, digest_text=None)`:`digest_text` 非空时,`allowed = numbers_in(digest_text) | numbers_in(每份日报) | ALLOWED_SMALL`,追加 `NUMBER_UNTRACEABLE`
- `check_daily(..., strict_brief=False)`:`strict_brief` 时追加 `BRIEF_NUMBER_UNTRACEABLE`(`brief` 数字 − 快照 − 小整数)
- 既有默认路径一字不改,新检查只在传参时生效

## Testing

- digest:正常、缺天、全周同定盘、坏快照跳过、空日志、bool/NaN 输入
- checker:周报合规通过 / 编造数字被拦 / 不传 --digest 行为不变;brief 合规 / 含快照外数字被拦 / 不传 --strict-brief 行为不变
- 回归:既有 check_report 全部用例必须绿(校验器是本序列首次改动)

## Risks

- 改校验器的回归风险 → 新逻辑全部走新增参数,既有用例作为回归网
- digest 与 derived 口径漂移 → 周涨跌同样按 ref_date 去重,与 derived 同源同法
