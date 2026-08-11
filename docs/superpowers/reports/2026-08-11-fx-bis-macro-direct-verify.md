# 验证报告:fx-bis-macro-direct(BIS 宏观直连 + HTTP 取数封装加固)

| 项 | 值 |
|---|---|
| Change | `fx-bis-macro-direct` |
| 分支 | `feature/20260811/fx-bis-macro-direct` |
| base-ref | `7fa78d8941184714caa31853c0d5740f84469449` |
| 验证日期 | 2026-08-11 |
| verify_mode | **full**(任务 19 > 3、变更文件 13 > 4) |
| 规模 | 17 次提交,13 个文件,+1962 / −289 |

报告中每个计数都来自下方 `sc-evidence` 自执行块,块内输出由脚本自跑自捕获并签哈希。

> **工具缺口**:本机未安装 `openspec-verify-change` skill(仅有 `openspec-apply-change` /
> `openspec-archive-change` / `openspec-explore` / `openspec-propose` / `openspec-sync-specs`)。
> 按本 change open 阶段处理 `openspec-new-change` 缺失时的同一办法,改用 OpenSpec CLI
> (`openspec validate --strict`)加人工逐条核对完成完整验证的 7 项检查。

---

## 一、完整验证 7 项检查

| # | 检查项 | 结果 | 依据 |
|---|---|---|---|
| 1 | tasks.md 全部任务已完成 | **PASS** | 19 项全部 `[x]`,未勾选 0;Superpowers plan 49 个步骤全部勾选 |
| 2 | 实现符合 `openspec/.../design.md`(D1–D7) | **PASS(1 处参数偏差)** | 见 §二 |
| 3 | 实现符合 Design Doc | **PASS(6 处偏差已记录)** | 见 §三 |
| 4 | 能力规格场景全部通过 | **PASS 25/25** | 见 §四 |
| 5 | proposal.md 目标已满足 | **PASS(1 项被 D6 取代)** | 见 §五 |
| 6 | delta spec 与 design doc 无矛盾 | **发现漂移,按选项 A 处理** | 见 §六 |
| 7 | Design Doc 可定位且与本 change 相关 | **PASS** | `docs/superpowers/specs/2026-08-11-fx-bis-macro-direct-design.md`,frontmatter `super_coding_change: fx-bis-macro-direct` |

补充检查:无硬编码密钥(`scripts/` `config/` `tests/` 全量正则扫描无命中;
唯一的密钥入口是 `__main__.py` 从 `os.environ` 读 `FRED_API_KEY`,零 key 为默认路径)。

---

## 二、对照 `design.md` 的 D1–D7

| 决策 | 落点 | 结论 |
|---|---|---|
| D1 批量取数 + 逐指标回落 | `_bis_table` 循环前拉平成查找表;三条降级路径逐指标回落 | 符合 |
| D2 三级优先级 BLS > BIS > DBnomics | `collect()` 三段分支,美国 CPI 仍归 BLS | 符合 |
| D3 `WS_CBPOL` 取最近非 NaN 观测 | `_obs_value` 在转 float **之前**按字符串判 `"NAN"` | 符合 |
| D4 `prev` = 上一个**不同**水平 | `_latest_and_prev_distinct`,窗口内无变动记 `null` | 符合;**但 D4 写的 `lastNObservations=90` 作废**,实测 90 覆盖不到美国上次变动(需 237 个观测),Design Doc 第 1 节据实测改为 400 |
| D5 CSV 按列名取、缺列整体回落 | `csv.DictReader` + `BIS_REQUIRED_COLS` 检测 | 符合 |
| D6 `REF_AREA` 映射写死为模块级常量 | `BIS_AREA = {"US": "US", "EA": "XM", ...}` | 符合 |
| D7 gzip 在响应侧兜底 | `util.fetch_text` 按魔数解压后再 decode,失败即抛 | 符合 |

---

## 三、对照 Design Doc

Design Doc 第 9 节「Implementation Divergence」已逐条记录 6 处偏差:§9.1 两个未经实测
的数字(已更正)、§9.2 审查后新增的两条行为、§9.3 与 D4 的参数偏差、§9.4
`config/indicators.json` 未补 `REF_AREA`(被 D6 取代)、§9.5 `_bis_parse` 签名、
§9.6 `tests/test_snapshot.py` 未改。此处不重复,只标结论:**均为有意偏差,已入档**。

---

## 四、25 个验收场景逐条核对

每个场景都跑了对应用例(命名到方法级),25 个场景 PASS 25 / FAIL 0。

| # | 场景 | 用例 |
|---|---|---|
| 1 | 有新数据发布 | `MacroTest.test_latest_prev_and_new_release_flag` |
| 2 | 美国 CPI 走 BLS 主源 | `BlsUsCpiTest.test_yoy_computed_from_index_by_script` |
| 3 | BLS 同月基期缺失 | `BlsUsCpiTest.test_missing_same_month_base_falls_back_with_gap` |
| 4 | BIS 直连取得五经济体指标 | `PriorityTest.test_bis_used_and_dbnomics_not_called` / `test_bls_wins_over_bis_for_us_cpi` |
| 5 | BIS 整体不可达 | `BisTableTest.test_unreachable_endpoint_records_gap_and_empties_that_dataflow` / `PriorityTest.test_partial_fallback_granularity` |
| 6 | BIS 缺少某经济体 | `BisTableTest.test_absent_economy_records_gap_so_the_fallback_is_visible` / `test_economy_absent_from_response_only_that_key_missing` |
| 7 | 未跟踪的指标不请求也不记缺漏 | `BisTableTest.test_untracked_dataflow_is_not_requested` / `test_untracked_economy_absent_records_no_gap` |
| 8 | 日频政策利率序列追加同值观测 | `DailyReleaseSemanticsTest.test_new_day_same_level_is_not_a_release` |
| 9 | 日频政策利率水平变动 | `DailyReleaseSemanticsTest.test_level_change_is_a_release` |
| 10 | 无可比旧值 | `DailyReleaseSemanticsTest.test_first_landing_without_prior_row_is_not_a_release` / `test_unusable_prior_value_is_not_a_release` |
| 11 | BIS 响应缺少必需列 | `BisTableTest.test_missing_column_records_gap` / `BisParseTest.test_missing_required_column_raises` |
| 12 | 政策利率日频序列末端为 NaN | `BisParseTest.test_nan_rows_dropped_not_zeroed` / `BisTableTest.test_all_nan_economy_absent` |
| 13 | 政策利率前值取上一个不同水平 | `PrevSemanticsTest.test_distinct_prev_skips_equal_observations` / `test_prev_period_is_last_day_of_old_level` |
| 14 | 回溯窗口内政策利率未变动 | `PrevSemanticsTest.test_no_change_in_window_yields_none_not_equal_value` |
| 15 | 换源当日标记不可比 | `BlsUsCpiTest.test_source_change_marked_and_not_new_release` / `test_fallback_direction_also_marked` / `PriorityTest.test_source_change_marked_on_switch_day` |
| 16 | 存量快照无来源字段 | `BlsUsCpiTest.test_legacy_prev_row_without_source_key_marks_change` |
| 17 | 滞后月数披露 | `LagMonthsTest.test_attached_to_every_indicator` / `test_month_period` |
| 18 | 期号不可解析 | `LagMonthsTest.test_quarter_and_garbage_periods_are_null` |
| 19 | 零 key 默认路径 | `MacroTest.test_zero_key_default_path_no_fred_gap` |
| 20 | FRED 增强路径失败 | `MacroTest.test_fred_enhancement_failure_recorded` |
| 21 | 源返回 gzip 响应 | `GzipFallbackTest.test_gzip_body_is_decompressed` |
| 22 | 源无视 identity 协商 | `GzipFallbackTest.test_gzip_body_is_decompressed` / `BytesFixtureTest.test_fixture_server_can_serve_raw_bytes` |
| 23 | 压缩体损坏 | `GzipFallbackTest.test_corrupt_gzip_raises_instead_of_returning_mojibake` |
| 24 | 未压缩响应不受影响 | `GzipFallbackTest.test_plain_body_unchanged` / `test_empty_body_does_not_crash` |
| 25 | 自定义请求头 | `HeadersTest.test_extra_headers_are_sent` / `test_default_ua_when_no_headers` / `test_caller_can_override_ua` |

场景 22 说明:实现**不**发 `Accept-Encoding: identity`(D7 已论证请求侧协商无效),
因此该场景由"无论请求头如何,响应体是 gzip 就解压"这条行为覆盖,与场景 21 同一用例。

---

## 五、proposal.md 目标核对

| proposal 目标 | 实测结果 |
|---|---|
| 五经济体 CPI 滞后降到 2 个月内 | 达成:BIS 直查五经济体 CPI 期号均为 `2026-06`,快照日 `2026-08-11`,`lag_months = 2` |
| 政策利率滞后降到 7–12 天内 | 达成:实测末期 BR/EA/US `2026-08-04`、PH `2026-07-31`、TH `2026-07-30` |
| 单源失败不扩散 | 达成:三条降级路径逐指标回落且**均记 gap**(本次审查修复的正是"缺席不记 gap"这条) |
| `util.fetch_*` 不再把压缩体读成解析失败 | 达成:魔数解压 + 解压失败抛异常,5 个 gzip/header 场景全绿 |
| 消除方向性错误结论 | 达成:五个政策利率全部换成真值,实测 9/10 指标 `source: bis`(美国 CPI 仍 `bls`) |
| `config/indicators.json` 补 `REF_AREA` 维度键 | **未做,判定为被 D6 取代**——见 Design Doc §9.4 与下方"接受的偏差" |

---

## 六、Spec 漂移处理(用户决策点,按授权取推荐默认值)

检查项 6 发现漂移:build 阶段按代码审查结论给 delta spec 补了 4 个场景与三段规范正文
(逐指标 gap scope、只为被跟踪指标取数、`is_new_release` 判据随频率变),而 Design Doc
写于这些结论之前,未体现。

三个选项中取 **选项 A**:在 Design Doc 追加「Implementation Divergence」节记录偏差原因。
理由——偏差来自审查修复,已实现且有测试与实测证据,不存在需要重新设计的分歧;
选项 B(退回 build 重做设计)对已定型且验证通过的行为是纯开销。
用户本次给出的「自主推进 非必要不停」授权覆盖此类仪式性决策点。

已写入:`docs/superpowers/specs/2026-08-11-fx-bis-macro-direct-design.md` 第 9 节。

---

## 七、代码审查(build 阶段强制门)

三视角并行审查 + 逐条对抗性复核:**20 条发现,6 条被推翻,2 条 Important 幸存**,
均在 `scripts/collect/macro.py`,已在提交 `7ab560d` 修复:

1. **日频政策利率的 `is_new_release` 每逢 BIS 刷新即为 true**。`_is_new` 只比 `period`,
   而 `WS_CBPOL` 每个日历日追加一行——利率纹丝不动的日子期号照样推进,日报据此打出
   「数据发布:政策利率 …」行,把管道刷新说成央行动了利率。
   **实测复现**(真实 BIS 字节 + 把真实快照的政策利率期号回拨一天):

   | 经济体 | 期号 | 值 | 旧判据 | 修复后 |
   |---|---|---|---|---|
   | BR | 2026-08-04 | 14.25 | True | False |
   | EA | 2026-08-04 | 2.25 | True | False |
   | PH | 2026-07-31 | 4.75 | True | False |
   | TH | 2026-07-30 | 1.0 | True | False |
   | US | 2026-08-04 | 3.625 | True | False |

   旧判据 5/5 假阳性,修复后 0/5。判据改为按频率分开:日频比水平(`_is_new_level`),
   月频仍比期号。
2. **BIS 缺某经济体时静默回落、零 gap**,违反 delta spec 正文与 tasks 3.3 的「并记入缺漏」。
   已改为逐指标记 gap(scope = `经济体/指标`)。连带按同一约定确立"只为被跟踪的指标
   取数与记 gap"(审查 Minor 两条)。

审查另指出 README 两个未经实测的数字,已更正(见下)。

**修复过程中发现测试自身的一处假绿**:用例的 `prev_snapshot` 写了 config 里的 DBnomics
标识 `BIS/WS_CBPOL/D.BR`,而 BIS 分支真实落盘的是 `BIS/WS_CBPOL/BR`,`_is_new*` 查不到行
恒返回 False——用例以错误的理由通过。已改为真实 `series_id` 并在 fixture 注明。

---

## 八、数字更正(仓库数字硬规则)

设计与 README 里两个"约"字打头的数字未经实测,verify 阶段实跑后逐字更正入档,不静默改:

| 项 | 原写 | 实测(2026-08-11 直查 BIS) |
|---|---|---|
| `lastNObservations=400` 覆盖时长 | 约 19 个月 | 400 个观测跨 **399 天 ≈ 13.1 个月**(按日历日出行,美国区间内 0 行 NaN) |
| 美国回溯到上次利率变动所需观测数 | 约 170 | **237**(上次变动 2025-12-10) |

参数取值 400 与"够用"的结论均不变,余量 163 个观测(≈ 5 个月)。

---

## 九、证据块

### 9.1 全量测试

```sc-evidence
$ python3 -m unittest discover -s tests -t .
exit: 0
.......................................--daily 需与 --digest 同用(单独给日报不会启用数字溯源)
.周度聚合文件无法解析: Expecting value: line 1 column 1 (char 0)
.周度聚合文件无法解析: Expecting value: line 1 column 1 (char 0)
..周度聚合文件结构不符(需含 week 与 generated_from)
周度聚合文件结构不符(需含 week 与 generated_from)
..........................................................................................................................................................................................................................................................................................................................................................................................
----------------------------------------------------------------------
Ran 421 tests in 10.594s

OK
CHECK PASSED
CHECK PASSED
CHECK FAILED (1):
 - SECTION_MISSING: 缺少币种节 THB
snapshot: /tmp/tmpfzanomdz/data/2026-08-10.json
gaps: 2
  - [frankfurter/all] URLError: <urlopen error [Errno 111] Connection refused>
  - [exchange-api/all] URLError: <urlopen error [Errno 111] Connection refused>
snapshot: /tmp/tmpk6genz35/data/2026-08-10.json
gaps: 1
  - [calendar/all] calendar expired (valid_until=2026-01-01), 请按 README 年历维护说明更新
snapshot: /tmp/tmp3afdd0mk/data/2026-08-10.json
gaps: 1
  - [dbnomics/X] URLError: <urlopen error [Errno 111] Connection refused>
snapshot: /tmp/tmpp2_abogh/data/2026-08-10.json
gaps: 1
  - [exchange-api/all] URLError: <urlopen error [Errno 111] Connection refused>
snapshot: /tmp/tmp616tuf43/data/2026-08-10.json
gaps: 1
  - [frankfurter/all] URLError: <urlopen error [Errno 111] Connection refused>
snapshot: /tmp/tmptthu1xw6/data/2026-08-10.json
gaps: 5
  - [gdelt/THB] URLError: <urlopen error [Errno 111] Connection refused>
  - [gdelt/BRL] URLError: <urlopen error [Errno 111] Connection refused>
  - [gdelt/USD] URLError: <urlopen error [Errno 111] Connection refused>
  - [gdelt/EUR] URLError: <urlopen error [Errno 111] Connection refused>
  - [gdelt/PHP] URLError: <urlopen error [Errno 111] Connection refused>
snapshot: /tmp/tmpziaw6cld/data/2026-08-10.json
gaps: 1
  - [derive/all] internal error RuntimeError: boom
snapshot: /tmp/tmpm8b277de/data/2026-08-10.json
gaps: 0
snapshot: /tmp/tmpydj53cu3/data/2026-08-10.json
gaps: 0
snapshot: /tmp/tmplhdir2vx/data/2026-08-10.json
gaps: 5
  - [gdelt/THB] HTTPError: HTTP Error 404: Not Found
  - [gdelt/BRL] HTTPError: HTTP Error 404: Not Found
  - [gdelt/USD] HTTPError: HTTP Error 404: Not Found
  - [gdelt/EUR] HTTPError: HTTP Error 404: Not Found
  - [gdelt/PHP] HTTPError: HTTP Error 404: Not Found
snapshot: /tmp/tmpzl4mm6o8/data/2026-08-10.json
gaps: 0
snapshot: /tmp/tmpfs2pcrms/data/2026-08-10.json
gaps: 5
  - [gdelt/THB] HTTPError: HTTP Error 404: Not Found
  - [gdelt/BRL] HTTPError: HTTP Error 404: Not Found
  - [gdelt/USD] HTTPError: HTTP Error 404: Not Found
  - [gdelt/EUR] HTTPError: HTTP Error 404: Not Found
  - [gdelt/PHP] HTTPError: HTTP Error 404: Not Found
snapshot: /tmp/tmp65z87f40/data/2026-08-10.json
gaps: 0
snapshot: /tmp/tmpzv8y4ee8/data/2026-08-10.json
gaps: 1
  - [snapshot/prev] corrupt prev snapshot 2026-08-09: JSONDecodeError: Expecting property name enclosed in double quotes: line 1 column 2 (char 1)
snapshot: /tmp/tmpwbl9wxvv/data/2026-08-10.json
gaps: 1
  - [snapshot/prev] corrupt prev snapshot 2026-08-09: RecursionError: maximum recursion depth exceeded while decoding a JSON array from a unicode string
snapshot: /tmp/tmpulux__dt/data/2026-08-10.json
gaps: 1
  - [macro/all] internal error RuntimeError: boom
snapshot: /tmp/tmptknhe8w3/data/2026-08-10.json
gaps: 1
  - [dbnomics/X] URLError: <urlopen error [Errno 111] Connection refused>
snapshot: /tmp/tmpw74qulvr/data/2026-08-10.json
gaps: 0
snapshot: /tmp/tmpzifzoyxi/data/2026-08-10.json
gaps: 1
  - [snapshot/prev] corrupt prev snapshot 2026-08-09: top-level list, expected dict
sc-evidence: sha256:638d4c7d038cfc67e49ed3fae78ac401acd70353a9430cd04abaa0255d877ac7 kind:automated
```

### 9.2 构建(全部 `scripts/` 编译)

```sc-evidence
$ python3 -c import\ compileall\,sys\;\ sys.exit\(0\ if\ compileall.compile_dir\(\'scripts\'\,\ quiet=2\,\ force=True\)\ else\ 1\)
exit: 0
sc-evidence: sha256:abe5082900c1427e17c11792cf366c89707f0cc285c558dc1f3917d73e19da76 kind:automated
```

### 9.3 OpenSpec 严格校验

```sc-evidence
$ openspec validate fx-bis-macro-direct --strict
exit: 0
Change 'fx-bis-macro-direct' is valid
sc-evidence: sha256:6965f2f5249bc110c1c5f027b21ebfc946d73f5d5e5609fe6a187f878783bc00 kind:automated
```

### 9.4 变异测试(21 个靶点)

Design Doc 第 6 节列了 11 条必须被杀掉的变异(M1–M11);审查修复新增的两条判断
再加 10 条(M12–M21)。

```sc-evidence
$ timeout 560 python3 /tmp/claude-1000/-home-ubuntu-repos-REBORN-lab-macro/0a91e423-4443-48c6-a5c1-42bfb719e0a6/scratchpad/mut_all.py
exit: 0
SURVIVED  M1  去掉 NaN 字符串判定               
KILLED    M2  prev 取上一个观测                test_distinct_prev_skips_equal_observations, test_no_change_in_window_yields_non
KILLED    M3  无变动时 prev = value          test_no_change_in_window_yields_none_not_equal_value, test_single_observation
KILLED    M4  按列位置取 OBS_VALUE            test_bom_before_required_column, test_column_order_does_not_matter
KILLED    M5  删掉必需列检测                    test_empty_and_header_only, test_missing_column_records_gap
KILLED    M6  BIS 覆盖美国 CPI               test_annual_average_row_m13_not_selected, test_bls_wins_over_bis_for_us_cpi
KILLED    M7  回落粒度改为全有或全无                test_all_nan_economy_absent, test_bom_before_required_column
KILLED    M8  XM/EA 映射互换                 test_bis_used_and_dbnomics_not_called, test_euro_area_maps_from_xm
KILLED    M9  去掉 gzip 魔数判定               test_corrupt_gzip_raises_instead_of_returning_mojibake, test_fixture_server_can_
KILLED    M10 解压失败回退有损解码                 test_corrupt_gzip_raises_instead_of_returning_mojibake
KILLED    M11 prev_period 取旧水平首日         test_distinct_prev_skips_equal_observations, test_prev_period_is_last_day_of_old
KILLED    M12 日频回退成期号比对                  test_new_day_same_level_is_not_a_release, test_unusable_prior_value_is_not_a_rel
KILLED    M13 _is_new_level 恒 True       test_new_day_same_level_is_not_a_release
KILLED    M14 _is_new_level 比较取反         test_level_change_is_a_release, test_new_day_same_level_is_not_a_release
KILLED    M15 去掉旧值类型门                    test_unusable_prior_value_is_not_a_release
KILLED    M16 月频也套日频规则                   test_monthly_cpi_still_keyed_on_period_not_level
KILLED    M17 缺席经济体不记 gap                test_absent_economy_records_gap_so_the_fallback_is_visible, test_all_nan_economy
KILLED    M18 gap scope 退化成 dataflow 级   test_absent_economy_records_gap_so_the_fallback_is_visible, test_all_nan_economy
KILLED    M19 不按跟踪清单过滤经济体                test_absent_economy_records_gap_so_the_fallback_is_visible, test_bis_used_and_db
KILLED    M20 未跟踪的 dataflow 照样发 GET      test_untracked_dataflow_is_not_requested
KILLED    M21 频率判据写死成日频前值口径              test_monthly_cpi_still_keyed_on_period_not_level

变异分数 KILLED 20 / 21(SURVIVED 1)
sc-evidence: sha256:0afc9fc358fef487aa7b545ef97ebbd0502b497a2ecbd5dc10dd958f71f949d2 kind:automated
```

---

## 十、接受的偏差

以下三项判定为可接受,记录在此,不阻塞归档:

1. **M1「去掉 `"NaN"` 字符串判定」是等价变异,不是覆盖缺口。** `float("NaN")` 转换成功
   后被 `math.isfinite` 挡住,行为不变,故任何测试都杀不掉它。保留该判定是纵深防御:
   真正的危险是 NaN 逃出 `_obs_value`——它的任何比较都是 False,会同时毁掉"取最新
   非 NaN"与"找上一个不同水平"两处判定;`isfinite` 若日后被当成冗余删掉,字符串门
   就是最后一层。代码注释已写明这一点,避免后人把它当死代码删掉。
2. **`config/indicators.json` 未补 `REF_AREA` 维度键**(proposal「What Changes」与
   tasks 2.1 后半),但 tasks 2.1 已勾选。判定为被 D6 取代:映射已是模块级常量
   `BIS_AREA`,它同时充当"BIS 覆盖哪些经济体"的闸门;在 config 里再放一份等价映射会
   制造两个可能互相矛盾的真相源,且 `REF_AREA` 拼错会静默停用该经济体的 BIS 分支。
   影响:新增经济体需改代码而非改配置。已入 Design Doc §9.4。
3. **BIS 落后央行决议数日。** 实测 BR 政策利率停在 `2026-08-04` = 14.25,而 COPOM
   2026-08-05 已定 14.00。如实呈现 `period` 与 `lag_months`,不补算、不外推。
   要更快只能在后续 P3 接 BCB COPOM 决议通道,不在本 change 范围内。

## 十一、结论

7 项完整验证检查全部通过(其中检查项 6 的漂移按选项 A 处理并入档),25/25 验收场景
有对应用例且全绿,421 个测试通过,21 个变异靶点 KILLED 20 / SURVIVED 1(该 1 条为已论证
的等价变异)。无 CRITICAL、无未修复的 IMPORTANT。

**建议进入归档。**
