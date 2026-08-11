---
change: fx-data-quality-derived
design-doc: docs/superpowers/specs/2026-08-11-fx-data-quality-derived-design.md
base-ref: e19541d2e4d3b2e368c35620f595a862bde36bb3
---

# 实施计划:fx-data-quality-derived

对照 `openspec/changes/fx-data-quality-derived/tasks.md` 的 9 个任务,TDD 逐个执行(先写失败测试再实现),每任务一次提交。测试命令:`python3 -m unittest discover -s tests -t .`(基线 141 通过)。

## 任务 1.1 rates ref_date

- 测试(tests/test_rates.py 追加):正常响应 → 快照顶层 `rates_ref_date` 等于响应 `date`;响应无 `date` → null;prev 快照含/不含 `rates_ref_date` → 每币种 `prev_ref_date` 相应为值/null
- 实现:`_fetch_primary` 返回 `(rates, ok, ref_date)`;`collect` 输出增顶层键;新增 `_prev_ref_date(cfg)`;`__main__` 把顶层键并入快照

## 任务 1.2 review 三分支

- 测试(tests/test_review.py 追加):两侧 ref_date 相等 → 材料行含"参考价未更新(非工作日)";不同 → 走既有比较;任一缺失 → 旧文案
- 实现:`ref_date_of(snap)` helper;材料行分支拼装;`direction_outcome` 语义不动

## 任务 2.1 硬 429 重试

- 测试(tests/test_events.py 追加):首次 429 二次成功 → 有文章无 gap;两次 429 → gap 且原因可辨;软限速路径不回归;`DEFAULT_DELAY_S == 20`
- 实现:`_query_with_retry` 触发条件加 429 判定;常量改 20

## 任务 2.2 顺序轮转 + 去重

- 测试:同日期两次 `_query_order(date)` 相同;两个不同日期得到不同顺序;含重复标题的响应 → 只留一条
- 实现:`_query_order(date)` 纯函数(便于断言);`collect` 遍历改用它;`_dedupe_titles(arts)`

## 任务 2.3 删除 tone

- 测试:快照 events 条目不含 `tone`;`tone_avg` 不出现在输出
- 实现:events.py 去字段与均值计算;SKILL 模板同步(与 4.1 合并提交亦可,但测试先行)

## 任务 3.1 derive 汇率类

- 测试(tests/test_derive.py 新建):正常 chg_pct_1d 精度 3 位;ref_date 相等 → null;历史不足 5 → `range_5d_days` 为实际数;坏输入(NaN/bool/字符串/prev=0)→ null 不抛
- 实现:`scripts/collect/derive.py` 的 `_rates_derived`

## 任务 3.2 实际利率

- 测试:双值齐全 → value 与双期号;缺 CPI/缺政策利率/缺任一期号 → 整项 null
- 实现:`_real_rate`,按 economy 聚合 macro 列表

## 任务 3.3 接线

- 测试:端到端快照含 `derived`;derive 抛异常 → 快照仍落盘且 gaps 含 derive 条目
- 实现:`__main__` 读近 N 份历史快照并调用 `derive`;顶层 try 兜底

## 任务 4.1 SKILL + README

- 要点表加"派生指标"行、汇率行带 ref_date、砍 tone_avg;禁算条款改写;README cron ≥17:00 UTC
- 无自动化断言,靠 4.2 端到端

## 任务 4.2 回归

- 全量测试;真实跑当日采集 + 生成要点表;`check_report.py` 不报 NUMBER_UNTRACEABLE
