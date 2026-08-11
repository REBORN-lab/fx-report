# Scenario 覆盖核对表(tasks 5.2 / plan Task 17)

- 核对日期: 2026-08-10,分支 feature/20260810/fx-daily-report-skill
- TDD 记录: 本任务为纯核对文档,无生产代码,RED/GREEN 标 **N/A**(流程要求记录)
- 取证纪律: 每格证据均为核对当场重跑命令后抄录的实际输出或真实文件路径,先跑后填
- Scenario 清单来源: 三份 delta spec 原文逐份核读(`openspec/changes/fx-daily-report-skill/specs/{fx-data-collection,fx-daily-report,fx-weekly-report}/spec.md`),实际清单 11+8+4=23 条,与 plan 骨架 23 行**完全一致,无出入**

## Step 1: 全量测试当场重跑取证

命令: `python3 -m unittest discover -s tests -t . -v`(stderr 摘要,exit=0):

```
----------------------------------------------------------------------
Ran 141 tests in 5.410s

OK
```

(注: 直接 `2>&1 | tail -5` 时摘要行被测试自身 stdout 缓冲顶掉,故将 stderr 单独落盘后取尾;摘要原文如上,退出码实测 `exit=0`。)

## 核对表(23 行)

证据列缩写: 「单跑」= `python3 -m unittest <用例> -v` 当场单跑抄录的 `... ok` 输出行;「实跑」= 当场重跑脚本/引真实产物路径。

| # | Spec | Scenario | 覆盖方式 | 实测证据(当场取证) |
|---|------|----------|----------|----------|
| 1 | fx-data-collection | 双源正常 | tests/test_rates.py 对应用例 | 单跑 `test_dual_source_ok (tests.test_rates.RatesTest.test_dual_source_ok) ... ok` |
| 2 | fx-data-collection | 主源失败降级 | test_rates + test_fault_injection::test_frankfurter_down | 单跑 `test_primary_fail_degrades_to_secondary (tests.test_rates.RatesTest.test_primary_fail_degrades_to_secondary) ... ok`;`test_frankfurter_down (tests.test_fault_injection.FaultMatrixTest.test_frankfurter_down) ... ok` |
| 3 | fx-data-collection | 双源偏差超阈 | test_rates 对应用例 | 单跑 `test_deviation_over_threshold_marks_suspect (tests.test_rates.RatesTest.test_deviation_over_threshold_marks_suspect) ... ok` |
| 4 | fx-data-collection | 有新数据发布 | test_macro.py::test_latest_prev_and_new_release_flag | 单跑 `test_latest_prev_and_new_release_flag (tests.test_macro.MacroTest.test_latest_prev_and_new_release_flag) ... ok` |
| 5 | fx-data-collection | 零 key 默认路径 | test_macro.py::test_zero_key_default_path_no_fred_gap | 单跑 `test_zero_key_default_path_no_fred_gap (tests.test_macro.MacroTest.test_zero_key_default_path_no_fred_gap) ... ok` |
| 6 | fx-data-collection | FRED 增强路径失败 | test_macro.py::test_fred_enhancement_failure_recorded | 单跑 `test_fred_enhancement_failure_recorded (tests.test_macro.MacroTest.test_fred_enhancement_failure_recorded) ... ok` |
| 7 | fx-data-collection | 正常采集(GDELT) | test_events.py::test_normal_collection_all_currencies | 单跑 `test_normal_collection_all_currencies (tests.test_events.EventsTest.test_normal_collection_all_currencies) ... ok` |
| 8 | fx-data-collection | 限速软失败退避 | test_events.py::test_soft_rate_limit_*(2 个用例) | 单跑 `test_soft_rate_limit_retry_succeeds (...) ... ok`;`test_soft_rate_limit_persistent_becomes_gap (...) ... ok`(均属 tests.test_events.EventsTest) |
| 9 | fx-data-collection | 端点不可用 | test_events.py::test_endpoint_* + fault_injection::test_gdelt_down | 单跑 `test_endpoint_error_single_currency (...) ... ok`;`test_endpoint_down_entirely (...) ... ok`;`test_gdelt_down (tests.test_fault_injection.FaultMatrixTest.test_gdelt_down) ... ok` |
| 10 | fx-data-collection | 昨日为议息日 | test_calendar.py::test_yesterday_meeting_hit | 单跑 `test_yesterday_meeting_hit (tests.test_calendar.CalendarTest.test_yesterday_meeting_hit) ... ok` |
| 11 | fx-data-collection | 部分源失败时快照完整 | test_snapshot + test_fault_injection 全矩阵 | 单跑 `test_one_source_down_others_intact (tests.test_snapshot.SnapshotTest.test_one_source_down_others_intact) ... ok`;整模块实跑 `python3 -m unittest tests.test_fault_injection -v` → `Ran 6 tests ... OK`(6/6 全 ok) |
| 12 | fx-daily-report | 数据齐全的正常日 | Task 13 端到端 + check_report 结构检查 | 实跑产物 `reports/daily/2026-08-10.md`;当场重跑 `python3 scripts/check_report.py reports/daily/2026-08-10.md data/2026-08-10.json --brief briefs/2026-08-10-brief.md` → `CHECK PASSED` `exit=0`;结构规则单跑 `test_valid_report_passes (...) ... ok`、`test_missing_currency_section (...) ... ok`。注: 真实运行日 gaps=5(GDELT 429 等),纯净"gaps 为空"形态未在端到端出现,见遗留事项 ② |
| 13 | fx-daily-report | 无明确驱动的币种 | SKILL 禁令 6 + Task 13 人工抽查 | `skills/fx-daily-report/SKILL.md:87`:"6. 无明确驱动的币种如实写"昨日无明确驱动",不编造归因。";实跑产物抽查 `reports/daily/2026-08-10.md:11`:"**昨日发生**:昨日无美元事件数据(采集失败),也无新数据发布或年历命中,昨日无明确驱动。" |
| 14 | fx-daily-report | 数字可溯源 | check_report NUMBER_UNTRACEABLE + Task 13 抽查 | 单跑 `test_untraceable_number (tests.test_check_report.CheckDailyTest.test_untraceable_number) ... ok`;人工抽查: 日报引用的 60.75/33.013/5.0856 三个数字经 `grep -o` 均在 `data/2026-08-10.json` 逐字命中(各 1 次);真实产物校验 `CHECK PASSED` `exit=0` |
| 15 | fx-daily-report | 缺漏日披露 | check_report GAPS_NOT_DISCLOSED/GAP_OMITTED | 单跑 `test_gaps_not_disclosed (...) ... ok`;`test_gap_scope_must_be_mentioned (...) ... ok`;实跑产物 `reports/daily/2026-08-08.md` "## 数据缺漏"节逐条列出(如 "[gdelt/USD] HTTPError: HTTP Error 429: Too Many Requests — 影响:美元节无事件归因…") |
| 16 | fx-daily-report | 无缺漏日 | check_report GAPS_MISMATCH(test_empty_gaps_section_must_say_none) | 单跑 `test_empty_gaps_section_must_say_none (tests.test_check_report.CheckDailyTest.test_empty_gaps_section_must_say_none) ... ok` |
| 17 | fx-daily-report | 存在前日日志 | test_review.py::test_direction_hit/miss + Task 15 实跑 | 单跑 `test_direction_hit (tests.test_review.ReviewTest.test_direction_hit) ... ok`;`test_direction_miss (...) ... ok`;实跑产物 `reports/daily/2026-08-08.md:36` "## 复盘"节逐币种一句话对照 2026-08-07 观点(五币种均有,判定"无法判定") |
| 18 | fx-daily-report | 首次运行无日志 | test_review.py::test_first_run_no_log + Task 13 实跑 | 单跑 `test_first_run_no_log (tests.test_review.ReviewTest.test_first_run_no_log) ... ok`;实跑产物 `reports/daily/2026-08-07.md:8` 与 `reports/daily/2026-08-10.md:8`:"首次运行,无历史观点可复盘。" |
| 19 | fx-daily-report | 篇幅合规 | check_report SUMMARY_TOO_LONG/SECTION_TOO_LONG | 单跑 `test_summary_too_long (...) ... ok`;`test_section_too_long (...) ... ok`(均属 tests.test_check_report.CheckDailyTest);真实日报当场重跑校验含篇幅规则 → `CHECK PASSED` `exit=0` |
| 20 | fx-weekly-report | 正常周聚合 | Task 15 端到端 + check_weekly DATE_STRUCTURE | 实跑产物 `reports/weekly/2026-W33.md`(头部声明"覆盖日报:4 份",≥3 满足前置);当场重跑 `python3 scripts/check_report.py --mode weekly reports/weekly/2026-W33.md` → `CHECK PASSED` `exit=0`;单跑 `test_date_heading_forbidden (tests.test_check_report.CheckWeeklyTest.test_date_heading_forbidden) ... ok` |
| 21 | fx-weekly-report | 日报不足 | check_weekly COVERAGE_GAP_DATES(test_low_coverage_needs_missing_dates) | 单跑 `test_low_coverage_needs_missing_dates (tests.test_check_report.CheckWeeklyTest.test_low_coverage_needs_missing_dates) ... ok`;辅证 `test_coverage_declaration_required (...) ... ok`;真实周报头部亦声明缺失日期(2026-08-04、2026-08-05、2026-08-06) |
| 22 | fx-weekly-report | 周内有缺漏日 | 周报缺漏汇总节 + Task 15 复核第 3 步 | 实跑产物 `reports/weekly/2026-W33.md:52` "## 缺漏汇总"节按日期逐条列出(如 "- 2026-08-07: [gdelt/USD] HTTPError: HTTP Error 429: Too Many Requests — 影响:美元节无事件归因…") |
| 23 | fx-weekly-report | 观点复盘汇总 | log_decision stats + check_weekly REVIEW_TOKEN_MISSING + Task 15 复核 | 当场实跑 `python3 scripts/log_decision.py stats --from 2026-08-04 --to 2026-08-10` → 首行 `命中 0 / 未命中 0 / 无法判定 10 / 未判定 10`,`exit=0`;单跑 `test_review_tokens_required (tests.test_check_report.CheckWeeklyTest.test_review_tokens_required) ... ok`;实跑产物 `reports/weekly/2026-W33.md:22` 复盘汇总同一计数行并逐条标注判定 |

## 结论

**结论: 23/23 覆盖**(结论前实数表格行数: fx-data-collection 11 行 + fx-daily-report 8 行 + fx-weekly-report 4 行 = 23 行,逐行均有当场实测证据)。

## 遗留事项

1. **spec 措辞漂移**: delta spec `specs/fx-data-collection/spec.md:21` "宏观数据增量采集"写"五经济体,IMF/BCB 口径",而实测最终 provider 组合为 **IMF/BIS/ECB**(`config/indicators.json` 实查: CPI 用 IMF/ECB、政策利率用 BIS/WS_CBPOL、经常账户用 IMF/BOP,全文件无 BCB 系列)。Task 5 审查已发现;归档同步 main spec 前修正措辞,本表如实记录、不改 spec。
2. **"数据齐全的正常日"(第 12 行)在两次端到端中均为缺漏日形态覆盖**: Task 13(2026-08-10,实测快照 gaps=5,GDELT 429 限流等)与 Task 15 回填日均带缺漏;"快照存在且 gaps 为空 → 完整日报"的纯净形态由 `test_valid_report_passes`/`test_empty_gaps_section_must_say_none` 等单测覆盖,真实世界纯净正常日待真实运行自然出现。
3. **核对过程新发现(取证方法备注,非覆盖缺口)**: ① plan 骨架第 23 行写的 `log_decision stats` 裸命令实测退出码 2(`--from/--to` 为必填参数),本表以 `stats --from 2026-08-04 --to 2026-08-10` 实跑取证;② 全量测试 `2>&1 | tail -5` 会因 stdout 缓冲看不到 `Ran N tests` 摘要行,取证时需将 stderr 单独截取(已在 Step 1 注明);③ 第 17 行真实产物复盘节判定均为"无法判定"(事件源全失败所致),"命中/未命中"两形态由单测覆盖,与遗留事项 2 同根因。
