# 验证报告:fx-source-upgrade(full)

- 日期:2026-08-11
- 分支:feature/20260811/fx-source-upgrade
- verify_mode:full(scale 判定)

## 完整验证 7 项

| # | 检查项 | 结果 |
|---|--------|------|
| 1 | tasks.md 全部任务 `[x]`(6/6) | PASS |
| 2 | 实现符合 change design.md 决策 | PASS(决策 1「只做探针可达的两家」严格执行) |
| 3 | 实现符合 Design Doc | PASS(两轮修订同步) |
| 4 | delta spec 场景全部通过 | PASS(新增能力 5 场景 + 修改能力 9 场景,逐条有测试) |
| 5 | proposal.md 目标已满足 | PASS |
| 6 | delta spec 与 Design Doc 无矛盾 | PASS |
| 7 | Design Doc 可定位且关联本 change | PASS |

## 探针定案(全部本机实跑,2026-08-11)

| 候选源 | 结果 | 处置 |
|---|---|---|
| Fed press RSS | 200,首条即 FOMC statement | ✅ 接入 |
| ECB press RSS | 200,10 条 | ✅ 接入 |
| BLS v1 timeseries(零 key) | 200,最新 2026-06,比镜像新 11 个月 | ✅ 接入为美国 CPI 主源 |
| BCB SGS API / 新闻 feed | 全域 HTTP 502,两轮重试一致 | ❌ 不写进配置 |
| BSP RSS / 媒体页 | 404 | ❌ 不写进配置 |
| BOT | 无 feed,仅 HTML | ❌ 不写进配置 |
| ECB Data Portal HICP | 200,但最新与镜像同为 2025-12 | ❌ 换源无收益 |

不可达的源刻意不写进 `config/endpoints.json` —— 写了只会每天往 gaps 里刷永久噪音。缺口记在 README 与 proposal。

## 代码审查(两轮 + 变异测试)

**第 1 轮**:**1 Critical + 5 Important + 8 Minor**,结论 With fixes。

- **C1(编造类,发生在报告层)**:美国 CPI 口径由 dbnomics 切到 bls、期号前移 11 个月,数值 2.705 → 3.531。报告把这 0.83pp 的口径差写成「通胀升至 3.531、实际利率被压到 0.844」并据此写触发条件 —— **管道状态变化被叙述成市场事实**,与上一 change 抓到的「采集失败写成事件数 0」同型。`check_report.py` 退出码 0,因为它只校验数字出处,不校验「升/降」的比较基准。
- I1 BLS 路径 `prev` 为 null,诱导 LLM 自找基准(C1 即其后果);I2 换源当日 `is_new_release` 假阳性;I3 `series_id` 沿用 IMF 标识与真实出处不符;I4 已配置但解析出 0 条与「有意停用」不可区分;I5 三个存活变异(round 精度、M13 年均值行、年份优先排序)。
- Minor:url 取值在 try 外、`official` 字段可为 null 与 spec 不符、事件数 null 措辞、`lag_months` 负数、零基期 reason 无断言、**11 个新用例被追加在 `__main__` guard 之后(直接跑该文件静默漏掉)**、末尾换行、未跟踪美国 CPI 仍打 BLS。

**修复后复审**:原 13 项全部 ✅,但发现 **C1 的反向同型漏洞**:`_source_changed_from` 只在 BLS 分支调用,`bls → dbnomics` 回落当日零标记 —— 而这个方向更常发生(BLS 是单一端点,实测两次采集各有超时)。另发现修好 C1 的那一行(`row.get("source", "dbnomics")` 缺省值)完全没有测试保护:去掉它换源标记消失、C1 直接回归,而 33 个测试全绿。

**二轮修复**:标记提到循环体公共位置(两方向都标)、补缺省值测试、跨年 prev 断言、`series_id` 先切 query 再切路径、零条目 gap 措辞区分。四项经变异验证 **4/4 KILLED**(见末尾变异证据块)。

**入待办(不阻塞,非本 change 引入)**:报告里「双源偏差…扩大」与「若 CPI 恢复更新」仍是把管道健康度当市场变量用,与禁令 5 刚立的原则同族,应在后续 change 把该原则扩写到 derived 的数据质量指标与「数据恢复」类 trigger 上;`lag_months` 未来期号返回负数。

## 端到端实跑发现

1. **官方通道兑现设计意图**:某轮采集中 EUR 的 GDELT 被 429,ECB 官方 RSS 仍取到 3 条,该币种没有变成信息真空,且是可署名的一手来源。
2. **BLS 的收益是实的**:美国 CPI 拿到 2026-06(滞后 2 个月),镜像口径滞后 13 个月。
3. **补上 prev 后揭出一个方向性反转**:BLS 序列内部同比是 4.249 → 3.531,**在下降**;原报告「通胀升至」不只是基准错了,方向也是反的。这条单独说明了 I1 为什么必须修。
4. **滞后差异巨大**:泰国 CPI 滞后 17 个月、菲律宾 15 个月、欧元区 8 个月 —— 现在报告必须带着这个数字说话。

## 证据块

(以下全部由 sc-evidence.sh 自执行生成并签名)
```sc-evidence
$ python3 -m unittest discover -s tests -t .
exit: 0
................................................................................................................................................................................................................................................
----------------------------------------------------------------------
Ran 240 tests in 7.859s

OK
CHECK PASSED
CHECK FAILED (1):
 - SECTION_MISSING: 缺少币种节 THB
snapshot: /tmp/tmp5i4x5prd/data/2026-08-10.json
gaps: 2
  - [frankfurter/all] URLError: <urlopen error [Errno 111] Connection refused>
  - [exchange-api/all] URLError: <urlopen error [Errno 111] Connection refused>
snapshot: /tmp/tmpkdvy08po/data/2026-08-10.json
gaps: 1
  - [calendar/all] calendar expired (valid_until=2026-01-01), 请按 README 年历维护说明更新
snapshot: /tmp/tmpkbgign0q/data/2026-08-10.json
gaps: 1
  - [dbnomics/X] URLError: <urlopen error [Errno 111] Connection refused>
snapshot: /tmp/tmpmythc85i/data/2026-08-10.json
gaps: 1
  - [exchange-api/all] URLError: <urlopen error [Errno 111] Connection refused>
snapshot: /tmp/tmpyq1gte25/data/2026-08-10.json
gaps: 1
  - [frankfurter/all] URLError: <urlopen error [Errno 111] Connection refused>
snapshot: /tmp/tmps3xtlyhd/data/2026-08-10.json
gaps: 5
  - [gdelt/THB] URLError: <urlopen error [Errno 111] Connection refused>
  - [gdelt/BRL] URLError: <urlopen error [Errno 111] Connection refused>
  - [gdelt/USD] URLError: <urlopen error [Errno 111] Connection refused>
  - [gdelt/EUR] URLError: <urlopen error [Errno 111] Connection refused>
  - [gdelt/PHP] URLError: <urlopen error [Errno 111] Connection refused>
snapshot: /tmp/tmpktr8rxwa/data/2026-08-10.json
gaps: 1
  - [derive/all] internal error RuntimeError: boom
snapshot: /tmp/tmp819v7gdu/data/2026-08-10.json
gaps: 0
snapshot: /tmp/tmpjliz4jo9/data/2026-08-10.json
gaps: 0
snapshot: /tmp/tmpcbpwj5hw/data/2026-08-10.json
gaps: 5
  - [gdelt/THB] HTTPError: HTTP Error 404: Not Found
  - [gdelt/BRL] HTTPError: HTTP Error 404: Not Found
  - [gdelt/USD] HTTPError: HTTP Error 404: Not Found
  - [gdelt/EUR] HTTPError: HTTP Error 404: Not Found
  - [gdelt/PHP] HTTPError: HTTP Error 404: Not Found
snapshot: /tmp/tmpanoltwr8/data/2026-08-10.json
gaps: 0
snapshot: /tmp/tmpew5zy0ls/data/2026-08-10.json
gaps: 5
  - [gdelt/THB] HTTPError: HTTP Error 404: Not Found
  - [gdelt/BRL] HTTPError: HTTP Error 404: Not Found
  - [gdelt/USD] HTTPError: HTTP Error 404: Not Found
  - [gdelt/EUR] HTTPError: HTTP Error 404: Not Found
  - [gdelt/PHP] HTTPError: HTTP Error 404: Not Found
snapshot: /tmp/tmp57gzheh9/data/2026-08-10.json
gaps: 0
snapshot: /tmp/tmpvfjnzlgo/data/2026-08-10.json
gaps: 1
  - [snapshot/prev] corrupt prev snapshot 2026-08-09: JSONDecodeError: Expecting property name enclosed in double quotes: line 1 column 2 (char 1)
snapshot: /tmp/tmp1jl5wm9a/data/2026-08-10.json
gaps: 1
  - [snapshot/prev] corrupt prev snapshot 2026-08-09: RecursionError: maximum recursion depth exceeded while decoding a JSON array from a unicode string
snapshot: /tmp/tmph2ivx798/data/2026-08-10.json
gaps: 1
  - [macro/all] internal error RuntimeError: boom
snapshot: /tmp/tmpyrbv2prj/data/2026-08-10.json
gaps: 1
  - [dbnomics/X] URLError: <urlopen error [Errno 111] Connection refused>
snapshot: /tmp/tmp65nvcx6p/data/2026-08-10.json
gaps: 0
snapshot: /tmp/tmpriibvihi/data/2026-08-10.json
gaps: 1
  - [snapshot/prev] corrupt prev snapshot 2026-08-09: top-level list, expected dict
sc-evidence: sha256:70e73cbcc81365751be79369818fe57336d663240a1610a166ba7f653a88fc42 kind:automated
```
```sc-evidence
$ python3 -c $'\nimport json;s=json.load(open(\'data/2026-08-11.json\'))\nus=[m for m in s[\'macro\'] if m[\'economy\']==\'US\' and m[\'indicator\']==\'CPI 同比\'][0]\nprint(\'US CPI row:\', json.dumps(us, ensure_ascii=False))\nprint(\'official issuers:\', {c: [i[\'issuer\'] for i in v.get(\'official\',[])] for c,v in s[\'events\'].items()})\nprint(\'lag_months:\', {(m[\'economy\'],m[\'indicator\']): m[\'lag_months\'] for m in s[\'macro\'] if m[\'indicator\']==\'CPI 同比\'})'
exit: 0
US CPI row: {"value": 3.531, "prev": 4.249, "period": "2026-06", "source": "bls", "series_id": "BLS/CUUR0000SA0", "economy": "US", "indicator": "CPI 同比", "is_new_release": false, "lag_months": 2, "source_changed_from": "dbnomics"}
official issuers: {'USD': ['Fed', 'Fed', 'Fed'], 'EUR': ['ECB', 'ECB', 'ECB'], 'PHP': [], 'THB': []}
lag_months: {('US', 'CPI 同比'): 2, ('EA', 'CPI 同比'): 8, ('PH', 'CPI 同比'): 15, ('TH', 'CPI 同比'): 17, ('BR', 'CPI 同比'): 13}
sc-evidence: sha256:34e5f09295ea6f0ba05ae39a2daf3a6f9ed679706a7d9dbe9ed1f6a26a9d9ff7 kind:automated
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
 README.md                                          |  20 ++
 briefs/2026-08-11-brief.md                         |  55 ++---
 config/endpoints.json                              |   5 +-
 data/2026-08-11.json                               | 221 ++++++++++++-------
 .../plans/2026-08-11-fx-source-upgrade.md          |  16 ++
 .../changes/fx-source-upgrade/.super-coding.yaml   |  11 +-
 .../specs/fx-data-collection/spec.md               |  20 +-
 openspec/changes/fx-source-upgrade/tasks.md        |  12 +-
 reports/daily/2026-08-11.md                        |  40 ++--
 scripts/collect/__main__.py                        |   6 +-
 scripts/collect/feeds.py                           |  83 ++++++++
 scripts/collect/macro.py                           | 165 ++++++++++++++-
 skills/fx-daily-report/SKILL.md                    |  29 ++-
 tests/test_feeds.py                                | 115 ++++++++++
 tests/test_macro.py                                | 235 +++++++++++++++++++++
 tests/test_snapshot.py                             |  47 +++++
 16 files changed, 930 insertions(+), 150 deletions(-)
sc-evidence: sha256:a7f1b1a8deeb0c2527a216675b4dde98cfb8a77ae85c18fb7d73b1e37097bf28 kind:automated
```
```sc-evidence
$ bash /tmp/mut3.sh
exit: 0
baseline: OK
N1 _prev_month 跨年不减年: FAILED (failures=1)
N4 去掉 source 缺省值: FAILED (errors=1)
NEW 回落方向不标记: FAILED (errors=1)
N5 series_id query 顺序退回: FAILED (failures=1)
restored: OK
sc-evidence: sha256:416dc61e04bc21ecc0aef207ab9c3d601ae6aa4e1441fc01439f84455324828f kind:automated
```
