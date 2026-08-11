# 验证报告:fx-data-quality-derived(full)

- 日期:2026-08-11
- 分支:feature/20260811/fx-data-quality-derived(base-ref e19541d)
- verify_mode:full(scale:任务 10 / delta spec 2 能力 / 变更 21+ 文件)

## 完整验证 7 项

| # | 检查项 | 结果 |
|---|--------|------|
| 1 | tasks.md 全部任务 `[x]`(9/9) | PASS |
| 2 | 实现符合 change design.md 决策 | PASS(决策 1 在实现期修正为逐币种存储,见"实现偏差") |
| 3 | 实现符合 Design Doc | PASS(Design Doc 已随两轮修订同步) |
| 4 | delta spec 场景全部通过 | PASS(24 个场景,新增 8 个,逐条有单元测试) |
| 5 | proposal.md 目标已满足 | PASS |
| 6 | delta spec 与 Design Doc 无矛盾 | PASS |
| 7 | Design Doc 可定位且关联本 change | PASS |

## 代码审查(两轮 + 变异测试)

**第 1 轮**:0 Critical? 否 —— **1 Critical + 5 Important + 9 Minor**,结论 No。

- **C1(编造类)**:`count = _article_count(...) or 0` 把"事件采集失败"与"确实 0 篇"压成同一个值;已提交的 08-11 要点表据此写出"事件数 0"。一个立论为防编造的 change 自身在造数,不可带入 main。
- **I1**:`prev_ref_date` 未知且两值 bit 级相等时算出 `0.0%` —— 把"没定盘"重新包装成日涨跌,还带上"脚本算的"免检光环。
- **I2**:`_range_nd` 对 ref_date 为 None 的历史条目不去重,把三份同价存量快照当三天,`range_5d_days` 虚报 5(真相 2 次定盘);且历史窗口等于 RANGE_DAYS,周末会让区间永远凑不满。
- **I3**:`derived.events` 漏基准货币 USD,而 SKILL 让 LLM 写这个不存在的数——结构性诱导它自己去数文章。
- **I4**:缺输入时省略键而非写 null,与 delta spec 明文和 SKILL 引用契约都对不上。
- **I5**:`_prev_ref_date` 取全快照共用值,与 review.py 的逐币种判定可对同一币种给出相反结论。
- Minor:429 字符串匹配可被 `IncompleteRead(429 bytes)` 误伤、死变量、历史文件名无校验、口径注释缺失、模板漏 `deviation_pct_prev`、轮转措辞传播了被证伪的因果模型。
- 变异测试 8 个,**4 个存活**,对应 4 处空洞/自指断言(轮转顺序拿被测函数当预期、`_load_history` 排除当日自身零覆盖、坏输入断言恒真、`_deviation_prev` 向后扫描零覆盖)。

**修复**:C1 + I1–I5 + 全部 Minor 逐条修复,delta spec 增 4 个场景,Design Doc 同步;4 个空洞用例改写。

**第 2 轮复审**:逐条 ✅,**Ready to merge: Yes**。上轮 4 个存活变异全部 KILLED;针对新代码补做 10 个变异,其中 5 个"回退到修前行为"的(N3/N6/N7/N9/N10)全部 KILLED。三项定向核查(按值去重是否误合并真实同价定盘 / `events_mod` 循环依赖 / `EMPTY_*` 浅拷贝)实测均无问题。

**复审残留项处理**:R2 建议的 5 条判别用例已补(逐币种 `prev_ref_date`、`_fixing_key` 两个分支、`count_delta` 双侧守卫、`HISTORY_SPAN` 加宽),并逐个变异验证 **5/5 KILLED**(见证据块 2);R1 docstring、R3 `fullmatch`、R4 `EMPTY_EVENTS_DERIVED` 常量化一并落地。R5(葡语标题里的 `5,02%` 转录排版)不由本 change 引入,留待后续。

## 实现偏差(build 期发现,已回写 spec 与 Design Doc)

change design.md 决策 1 原定"顶层 `rates_ref_date` + 每币种 `prev_ref_date`"。实现时发现:某币种因主源失败降级到 exchange-api 时,Frankfurter 的定盘日期对该币种数值并不成立,顶层单值无法表达。改为逐币种 `ref_date`(降级或双源皆失败时为 null),delta spec 增加场景"降级到副源时无参考日期",Design Doc 同步修订。

## 端到端实跑发现(诚实记录)

1. **根因坐实**:2026-08-11 采集,四币种 `ref_date` 全为 `2026-08-10` —— 采集早于欧央行当日定盘,取到的是昨日价。这正是试运行期 12/12 连平的根因,现在数据层可见。
2. **修复在真实数据上同时展示了两种情形**:USD 事件被 429 → `count: null`;PHP/THB/BRL/EUR 采到 → `count: 8/6/8/8`。`chg_pct_1d` 四币种全为 null(不再给 0.0%),`range_5d_days` 由虚报的 5 变为 3,`real_rate.BR.value` 为 null 但 `cpi`/`cpi_period` 保留,报告因此能写出"实际利率不可得(政策利率采集失败,仅 CPI 可引)"。
3. **429 缓解效果有限,轮转的前提被证伪**:延迟 5s→20s 后本机仍被限流;顺序轮转把 BRL 排到首位它依然首个 429,而位置 2、3 成功 —— "限流总落在尾部"的假设不成立。已把 events.py docstring、delta spec、proposal、Design Doc 四处措辞降格为"公平性措施,非 429 缓解手段"。两轮实跑事件覆盖分别为 2/5 与 4/5,损失确实被摊开,但换机器仍是主解。
4. **`range_5d_days: 3` 仍非真值(真相 2 次定盘)**:今日条目有 ref_date、历史条目是存量快照(无 ref_date),两族 key 刻意不互通以保护"真实两次定盘同价必须算 2"这一不变量,代价是过渡期多算一次。随存量快照滚出 9 份窗口自愈(约 2026-08-20),已写入 `_fixing_key` docstring。
5. **校验器有效性获实证**:首轮生成的报告里自算了"区间宽度不足 0.2%",`check_report.py` 立即报 `NUMBER_UNTRACEABLE: 数字 0.2`,改正后 PASS —— 禁算条款不是纸面约束。

## 证据块

(以下全部由 sc-evidence.sh 自执行生成并签名)
```sc-evidence
$ python3 -m unittest discover -s tests -t .
exit: 0
........................................................................................................................................................................................................
----------------------------------------------------------------------
Ran 200 tests in 6.535s

OK
CHECK PASSED
CHECK FAILED (1):
 - SECTION_MISSING: 缺少币种节 THB
snapshot: /tmp/tmp4470z8pc/data/2026-08-10.json
gaps: 2
  - [frankfurter/all] URLError: <urlopen error [Errno 111] Connection refused>
  - [exchange-api/all] URLError: <urlopen error [Errno 111] Connection refused>
snapshot: /tmp/tmpibkskmgc/data/2026-08-10.json
gaps: 1
  - [calendar/all] calendar expired (valid_until=2026-01-01), 请按 README 年历维护说明更新
snapshot: /tmp/tmp_2u3sopw/data/2026-08-10.json
gaps: 1
  - [dbnomics/X] URLError: <urlopen error [Errno 111] Connection refused>
snapshot: /tmp/tmpdrmlw4ao/data/2026-08-10.json
gaps: 1
  - [exchange-api/all] URLError: <urlopen error [Errno 111] Connection refused>
snapshot: /tmp/tmpl93bciik/data/2026-08-10.json
gaps: 1
  - [frankfurter/all] URLError: <urlopen error [Errno 111] Connection refused>
snapshot: /tmp/tmp2z342z4p/data/2026-08-10.json
gaps: 5
  - [gdelt/THB] URLError: <urlopen error [Errno 111] Connection refused>
  - [gdelt/BRL] URLError: <urlopen error [Errno 111] Connection refused>
  - [gdelt/USD] URLError: <urlopen error [Errno 111] Connection refused>
  - [gdelt/EUR] URLError: <urlopen error [Errno 111] Connection refused>
  - [gdelt/PHP] URLError: <urlopen error [Errno 111] Connection refused>
snapshot: /tmp/tmp2wwuj1a6/data/2026-08-10.json
gaps: 1
  - [derive/all] internal error RuntimeError: boom
snapshot: /tmp/tmpqb4m77r5/data/2026-08-10.json
gaps: 0
snapshot: /tmp/tmp9b6ch1hy/data/2026-08-10.json
gaps: 0
snapshot: /tmp/tmpzpjcot5e/data/2026-08-10.json
gaps: 0
snapshot: /tmp/tmpejukiuul/data/2026-08-10.json
gaps: 1
  - [snapshot/prev] corrupt prev snapshot 2026-08-09: JSONDecodeError: Expecting property name enclosed in double quotes: line 1 column 2 (char 1)
snapshot: /tmp/tmpm2_ss18r/data/2026-08-10.json
gaps: 1
  - [snapshot/prev] corrupt prev snapshot 2026-08-09: RecursionError: maximum recursion depth exceeded while decoding a JSON array from a unicode string
snapshot: /tmp/tmpfedtt09r/data/2026-08-10.json
gaps: 1
  - [macro/all] internal error RuntimeError: boom
snapshot: /tmp/tmp8a04r7nd/data/2026-08-10.json
gaps: 1
  - [dbnomics/X] URLError: <urlopen error [Errno 111] Connection refused>
snapshot: /tmp/tmphw9q1b69/data/2026-08-10.json
gaps: 0
snapshot: /tmp/tmpoqm52srs/data/2026-08-10.json
gaps: 1
  - [snapshot/prev] corrupt prev snapshot 2026-08-09: top-level list, expected dict
sc-evidence: sha256:e9381b84dfc9aba45cbe49ff3c5e14c63b1bdd648dff693c9f5188b7d8af7dba kind:automated
```
```sc-evidence
$ bash /tmp/mutcheck.sh
exit: 0
baseline: OK
N5 prev_ref_date 退回全快照共用值: FAILED (failures=1)
N1/N2 _fixing_key -> return ("val", value): FAILED (failures=1)
N1/N2 _fixing_key -> return ("ref", ref): FAILED (failures=1)
N4 count_delta 单侧守卫: FAILED (failures=1)
N8 HISTORY_SPAN 退回 RANGE_DAYS: FAILED (failures=1)
restored: OK
sc-evidence: sha256:0c1e9364c437d51f9217264d362fd18c30488c560db4d694be86de72d5857298 kind:automated
```
```sc-evidence
$ python3 scripts/check_report.py reports/daily/2026-08-11.md data/2026-08-11.json --brief briefs/2026-08-11-brief.md --mode daily
exit: 0
CHECK PASSED
sc-evidence: sha256:ee8471adc0f2a244c76bcdad71545a26195e45ae8611fd2c6da0eb7de78c5921 kind:automated
```
```sc-evidence
$ git diff --stat main...HEAD
exit: 0
 README.md                                          |   6 +
 briefs/2026-08-11-brief.md                         |  49 ++-
 data/2026-08-11.json                               | 331 ++++++++++++++++-----
 .../plans/2026-08-11-fx-data-quality-derived.md    |  58 ++++
 .../2026-08-11-fx-data-quality-derived-verify.md   | 141 +++++++++
 .../2026-08-11-fx-data-quality-derived-design.md   |  17 +-
 .../fx-data-quality-derived/.super-coding.yaml     |  13 +-
 .../changes/fx-data-quality-derived/proposal.md    |   2 +-
 .../specs/fx-daily-report/spec.md                  |   4 +-
 .../specs/fx-data-collection/spec.md               |  28 +-
 openspec/changes/fx-data-quality-derived/tasks.md  |  20 +-
 reports/daily/2026-08-11.md                        |  54 ++--
 scripts/collect/__main__.py                        |  39 +++
 scripts/collect/derive.py                          | 225 ++++++++++++++
 scripts/collect/events.py                          |  69 ++++-
 scripts/collect/rates.py                           |  38 ++-
 scripts/review.py                                  |  38 ++-
 skills/fx-daily-report/SKILL.md                    |  24 +-
 tests/test_derive.py                               | 252 ++++++++++++++++
 tests/test_events.py                               | 120 +++++++-
 tests/test_rates.py                                |  59 ++++
 tests/test_review.py                               |  40 +++
 tests/test_snapshot.py                             |  57 ++++
 23 files changed, 1473 insertions(+), 211 deletions(-)
sc-evidence: sha256:e4c640bae5190f83944d64598f21ec5368145cd929a26c5450fb2d9bc3b93dde kind:automated
```
