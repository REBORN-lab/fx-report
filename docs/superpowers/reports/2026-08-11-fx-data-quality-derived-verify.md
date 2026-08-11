# 验证报告:fx-data-quality-derived(full)

- 日期:2026-08-11
- 分支:feature/20260811/fx-data-quality-derived(base-ref e19541d)
- verify_mode:full(scale:任务 10 / delta spec 2 能力 / 变更 21 文件)

## 完整验证 7 项

| # | 检查项 | 结果 |
|---|--------|------|
| 1 | tasks.md 全部任务 `[x]`(9/9) | PASS |
| 2 | 实现符合 change design.md 决策 | PASS(决策 1 在实现期修正为逐币种存储,见下"实现偏差") |
| 3 | 实现符合 Design Doc | PASS(同上,Design Doc 已同步修订) |
| 4 | delta spec 场景全部通过 | PASS(逐场景对照见下) |
| 5 | proposal.md 目标已满足 | PASS |
| 6 | delta spec 与 Design Doc 无矛盾 | PASS(逐币种 ref_date 的修订同时写入两处) |
| 7 | Design Doc 可定位且关联本 change | PASS |

## delta spec 场景对照

`fx-data-collection`:双源正常 / 主源失败降级 / 双源偏差超阈 / **参考价定盘日期落盘** / **降级到副源时无参考日期** / **存量快照无参考日期** / 正常采集(不含 tone)/ 限速软失败退避 / **硬限流退避** / **查询顺序轮转** / **标题去重** / 端点不可用 / 部分源失败时快照完整 / **派生指标落盘** / **参考价未更新时不计涨跌** / **实际利率携带双期号** / **派生计算异常不阻断** —— 加粗为本次新增,全部有对应单元测试。

`fx-daily-report`:数字可溯源 / **引用派生指标** / **派生量缺失时不补算** / 存在前日日志 / 首次运行无日志 / **参考价未更新** / **参考日期缺失退回旧行为**。报告层场景由 SKILL 模板约束 + 端到端实跑验证(见证据块 2-4)。

## 实现偏差(build 期发现,已回写 spec 与 Design Doc)

change design.md 决策 1 原定"顶层 `rates_ref_date` + 每币种 `prev_ref_date`"。实现时发现:某币种因主源失败降级到 exchange-api 时,Frankfurter 的定盘日期对该币种数值并不成立,顶层单值无法表达这一差异。改为逐币种 `ref_date`(降级或双源皆失败时为 null),delta spec 增加场景"降级到副源时无参考日期",Design Doc 同步修订。属边界条件级增量,按 build 阶段 spec 分级处理规则直接编辑。

## 端到端实跑发现(诚实记录)

1. **核心行为已验证**:2026-08-11 03:45 UTC 真实采集,四币种 `ref_date` 全为 `2026-08-10` —— 采集早于欧央行当日定盘,取到的是昨日价。这正是试运行期 12/12 连平的根因,现在在数据层可见。
2. **legacy 过渡期的残留误导**:本次 `prev_ref_date` 为 null(上一份快照是变更前生成),`fixing_unchanged` 判否,于是 `chg_pct_1d` 算出 `0.0%` —— 仍是本 change 想消灭的那种误导。该条件在下一次运行自愈(届时 prev 快照已含 ref_date)。已列入代码审查重点核查项,待审查结论决定是否加固。
3. **429 缓解效果有限**:延迟 5s→20s + 顺序轮转后,本机本轮仍 3/5 被限流(BRL/PHP/THB),且轮转把 BRL 排到首位它依然首个 429。说明本机 IP 的限流不是纯粹的间隔问题,轮转的公平性收益也未在单轮体现。不改变本 change 的正确性,但"换机器"仍是事件覆盖的主解。
4. **校验器有效性获实证**:首轮生成的报告里我自算了"区间宽度不足 0.2%",`check_report.py` 立即报 `NUMBER_UNTRACEABLE: 数字 0.2`,改正后 PASS —— 禁算条款不是纸面约束。

## 证据块

(以下全部由 sc-evidence.sh 自执行生成并签名)
```sc-evidence
$ python3 -m unittest discover -s tests -t .
exit: 0
..........................................................................................................................................................................................
----------------------------------------------------------------------
Ran 186 tests in 6.355s

OK
CHECK PASSED
CHECK FAILED (1):
 - SECTION_MISSING: 缺少币种节 THB
snapshot: /tmp/tmpppcda5ar/data/2026-08-10.json
gaps: 2
  - [frankfurter/all] URLError: <urlopen error [Errno 111] Connection refused>
  - [exchange-api/all] URLError: <urlopen error [Errno 111] Connection refused>
snapshot: /tmp/tmp67q4tvny/data/2026-08-10.json
gaps: 1
  - [calendar/all] calendar expired (valid_until=2026-01-01), 请按 README 年历维护说明更新
snapshot: /tmp/tmpuuskgtv7/data/2026-08-10.json
gaps: 1
  - [dbnomics/X] URLError: <urlopen error [Errno 111] Connection refused>
snapshot: /tmp/tmpp3lmqgwe/data/2026-08-10.json
gaps: 1
  - [exchange-api/all] URLError: <urlopen error [Errno 111] Connection refused>
snapshot: /tmp/tmpr4xuc8bx/data/2026-08-10.json
gaps: 1
  - [frankfurter/all] URLError: <urlopen error [Errno 111] Connection refused>
snapshot: /tmp/tmprefh5xeb/data/2026-08-10.json
gaps: 5
  - [gdelt/THB] URLError: <urlopen error [Errno 111] Connection refused>
  - [gdelt/BRL] URLError: <urlopen error [Errno 111] Connection refused>
  - [gdelt/USD] URLError: <urlopen error [Errno 111] Connection refused>
  - [gdelt/EUR] URLError: <urlopen error [Errno 111] Connection refused>
  - [gdelt/PHP] URLError: <urlopen error [Errno 111] Connection refused>
snapshot: /tmp/tmpuxwzim_v/data/2026-08-10.json
gaps: 1
  - [derive/all] internal error RuntimeError: boom
snapshot: /tmp/tmp2wvep0c7/data/2026-08-10.json
gaps: 0
snapshot: /tmp/tmp65tuxkph/data/2026-08-10.json
gaps: 0
snapshot: /tmp/tmpy0n_5tov/data/2026-08-10.json
gaps: 0
snapshot: /tmp/tmp5xcgt9ja/data/2026-08-10.json
gaps: 1
  - [snapshot/prev] corrupt prev snapshot 2026-08-09: JSONDecodeError: Expecting property name enclosed in double quotes: line 1 column 2 (char 1)
snapshot: /tmp/tmpr1hrpkxz/data/2026-08-10.json
gaps: 1
  - [snapshot/prev] corrupt prev snapshot 2026-08-09: RecursionError: maximum recursion depth exceeded while decoding a JSON array from a unicode string
snapshot: /tmp/tmp8kusf5k8/data/2026-08-10.json
gaps: 1
  - [macro/all] internal error RuntimeError: boom
snapshot: /tmp/tmpolzu2ghl/data/2026-08-10.json
gaps: 1
  - [dbnomics/X] URLError: <urlopen error [Errno 111] Connection refused>
snapshot: /tmp/tmp7awv5vbt/data/2026-08-10.json
gaps: 0
snapshot: /tmp/tmpw0en69ul/data/2026-08-10.json
gaps: 1
  - [snapshot/prev] corrupt prev snapshot 2026-08-09: top-level list, expected dict
sc-evidence: sha256:aba7bb0dbaa438c7ad5abfb87991dd8a916c93daa086dfda1142451e91caeac9 kind:automated
```
```sc-evidence
$ python3 scripts/check_report.py reports/daily/2026-08-11.md data/2026-08-11.json --brief briefs/2026-08-11-brief.md --mode daily
exit: 0
CHECK PASSED
sc-evidence: sha256:ee8471adc0f2a244c76bcdad71545a26195e45ae8611fd2c6da0eb7de78c5921 kind:automated
```
```sc-evidence
$ python3 -c import\ json\;s=json.load\(open\(\'data/2026-08-11.json\'\)\)\;print\(\'ref_date:\'\,\{c:s\[\'rates\'\]\[c\]\[\'ref_date\'\]\ for\ c\ in\ s\[\'rates\'\]\}\)\;print\(\'derived\ keys:\'\,sorted\(s\[\'derived\'\]\)\)\;print\(\'real_rate\ economies:\'\,sorted\(s\[\'derived\'\]\[\'real_rate\'\]\)\)
exit: 0
ref_date: {'PHP': '2026-08-10', 'THB': '2026-08-10', 'BRL': '2026-08-10', 'EUR': '2026-08-10'}
derived keys: ['events', 'rates', 'real_rate', 'schema_version']
real_rate economies: ['BR', 'PH', 'TH', 'US']
sc-evidence: sha256:e2cfa3db2f29cab0f5adf1657942733739f95de295a46d0a0f57faeafb26e85f kind:automated
```
```sc-evidence
$ git diff --stat main...HEAD
exit: 0
 README.md                                          |   6 +
 briefs/2026-08-11-brief.md                         |  41 ++---
 data/2026-08-11.json                               | 197 ++++++++++++++-------
 .../plans/2026-08-11-fx-data-quality-derived.md    |  58 ++++++
 .../2026-08-11-fx-data-quality-derived-design.md   |   6 +-
 .../fx-data-quality-derived/.super-coding.yaml     |   9 +-
 .../specs/fx-daily-report/spec.md                  |   4 +-
 .../specs/fx-data-collection/spec.md               |  10 +-
 openspec/changes/fx-data-quality-derived/tasks.md  |  20 +--
 reports/daily/2026-08-11.md                        |  54 +++---
 scripts/collect/__main__.py                        |  30 ++++
 scripts/collect/derive.py                          | 180 +++++++++++++++++++
 scripts/collect/events.py                          |  55 ++++--
 scripts/collect/rates.py                           |  35 +++-
 scripts/review.py                                  |  38 +++-
 skills/fx-daily-report/SKILL.md                    |  21 ++-
 tests/test_derive.py                               | 162 +++++++++++++++++
 tests/test_events.py                               | 114 ++++++++++--
 tests/test_rates.py                                |  46 +++++
 tests/test_review.py                               |  40 +++++
 tests/test_snapshot.py                             |  45 +++++
 21 files changed, 999 insertions(+), 172 deletions(-)
sc-evidence: sha256:52f3f957918dec362d0028ae633ef83d4de3f3d4208fb6048675f436dba05e8d kind:automated
```
