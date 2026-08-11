# 验证报告:fx-calendar-trigger(light)

- 日期:2026-08-11
- 分支:tweak/20260811/fx-calendar-trigger
- verify_mode:light(源改动 2 文件:`state/calendar-2026.json`、`skills/fx-daily-report/SKILL.md`;另有测试与 change 产物)

## 轻量验证 6 项

| # | 检查项 | 结果 |
|---|--------|------|
| 1 | tasks.md 全部任务 `[x]`(3/3) | PASS |
| 2 | 改动文件与 tasks 描述一致 | PASS |
| 3 | 构建通过(全量 unittest) | PASS(证据块 1) |
| 4 | 相关测试通过(新增 6 条随仓库年历的完整性测试) | PASS(证据块 1) |
| 5 | 无安全问题(纯数据与 prompt) | PASS |
| 6 | 简化代码审查 | PASS(自审:`calendar.py` 零改动,新条目走通用 `{date,bank,event}` 匹配;新增测试断言 schema 合法性、无重复、事件不超 `valid_until`、发布方均有 source、维护说明记录缺口) |

## 数据来源与诚实边界

录入的 28 条全部来自官网并记录 URL 与抓取日期(2026-08-11):

- BLS CPI 2026 全年 12 条 —— https://www.bls.gov/schedule/news_release/cpi.htm
- BLS Employment Situation(非农)2026 全年 12 条 —— https://www.bls.gov/schedule/news_release/empsit.htm
- Fed 已公布的 FOMC 纪要 4 条 —— https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm

**未录入的(如实记录,已写进年历 `maintenance` 字段并有测试断言)**:

1. PH(PSA)、BR(IBGE)的发布日历官网对本机返回 **HTTP 403**,TH(MOC)与 EA(Eurostat)未取得可验证来源 —— 四经济体的统计发布日期**一条未录**。年历的价值全在可信,推测日期比空白更糟。
2. 未公布的 FOMC 纪要日期**不按"决议后三周"规则外推**。该规则见于美联储页面,据此 7 月会议纪要约在 8 月 19 日,但页面对这几场标注 "not yet posted";规则值与官方值可能差一天,而本文件的用途正是给报告写"具体哪天",错一天即误导。

## 效果验证

`calendar.collect` 在 2026-08-11/08-12 窗口命中 `{"date": "2026-08-12", "bank": "BLS", "event": "美国 CPI 发布(参考月 2026-07)"}`(证据块 2)——"下个催化剂是哪天"从恒空变为有确定答案,且这条恰好是次日事件。

## 证据块

(以下全部由 sc-evidence.sh 自执行生成并签名)
```sc-evidence
$ python3 -m unittest discover -s tests -t .
exit: 0
..............................................................................................................................................................................................................
----------------------------------------------------------------------
Ran 206 tests in 6.675s

OK
CHECK PASSED
CHECK FAILED (1):
 - SECTION_MISSING: 缺少币种节 THB
snapshot: /tmp/tmppnhexqwq/data/2026-08-10.json
gaps: 2
  - [frankfurter/all] URLError: <urlopen error [Errno 111] Connection refused>
  - [exchange-api/all] URLError: <urlopen error [Errno 111] Connection refused>
snapshot: /tmp/tmprcjvba5t/data/2026-08-10.json
gaps: 1
  - [calendar/all] calendar expired (valid_until=2026-01-01), 请按 README 年历维护说明更新
snapshot: /tmp/tmpc60wz8l4/data/2026-08-10.json
gaps: 1
  - [dbnomics/X] URLError: <urlopen error [Errno 111] Connection refused>
snapshot: /tmp/tmpbcbyfs97/data/2026-08-10.json
gaps: 1
  - [exchange-api/all] URLError: <urlopen error [Errno 111] Connection refused>
snapshot: /tmp/tmpspkng_t0/data/2026-08-10.json
gaps: 1
  - [frankfurter/all] URLError: <urlopen error [Errno 111] Connection refused>
snapshot: /tmp/tmp80g6qbg0/data/2026-08-10.json
gaps: 5
  - [gdelt/THB] URLError: <urlopen error [Errno 111] Connection refused>
  - [gdelt/BRL] URLError: <urlopen error [Errno 111] Connection refused>
  - [gdelt/USD] URLError: <urlopen error [Errno 111] Connection refused>
  - [gdelt/EUR] URLError: <urlopen error [Errno 111] Connection refused>
  - [gdelt/PHP] URLError: <urlopen error [Errno 111] Connection refused>
snapshot: /tmp/tmpvu2fbjqs/data/2026-08-10.json
gaps: 1
  - [derive/all] internal error RuntimeError: boom
snapshot: /tmp/tmp7zhv_mtc/data/2026-08-10.json
gaps: 0
snapshot: /tmp/tmpg3o5rmt2/data/2026-08-10.json
gaps: 0
snapshot: /tmp/tmpdj5ypy5a/data/2026-08-10.json
gaps: 0
snapshot: /tmp/tmp89wmo9xw/data/2026-08-10.json
gaps: 1
  - [snapshot/prev] corrupt prev snapshot 2026-08-09: JSONDecodeError: Expecting property name enclosed in double quotes: line 1 column 2 (char 1)
snapshot: /tmp/tmpu0_ml3j5/data/2026-08-10.json
gaps: 1
  - [snapshot/prev] corrupt prev snapshot 2026-08-09: RecursionError: maximum recursion depth exceeded while decoding a JSON array from a unicode string
snapshot: /tmp/tmp5kuzm25c/data/2026-08-10.json
gaps: 1
  - [macro/all] internal error RuntimeError: boom
snapshot: /tmp/tmptsgsgs_3/data/2026-08-10.json
gaps: 1
  - [dbnomics/X] URLError: <urlopen error [Errno 111] Connection refused>
snapshot: /tmp/tmpfjxfcc9a/data/2026-08-10.json
gaps: 0
snapshot: /tmp/tmppjux6sl2/data/2026-08-10.json
gaps: 1
  - [snapshot/prev] corrupt prev snapshot 2026-08-09: top-level list, expected dict
sc-evidence: sha256:90a995065c34cc1c44a64a96f4d02ea80f2c1ba7a786bfe7ea7fca637ff8f85a kind:automated
```
```sc-evidence
$ python3 -c $'\nfrom scripts.collect import calendar as c\nfrom tests.helpers import make_test_cfg\nhits, gaps = c.collect(make_test_cfg(calendar_path=\'state/calendar-2026.json\', date=\'2026-08-12\', yesterday=\'2026-08-11\'))\nprint(\'hits:\', hits); print(\'gaps:\', gaps)'
exit: 0
hits: [{'date': '2026-08-12', 'bank': 'BLS', 'event': '美国 CPI 发布(参考月 2026-07)'}]
gaps: []
sc-evidence: sha256:e06396bca8664b235d5089c763b57987aacf28090234f321dfab99eff1dbebf6 kind:automated
```
```sc-evidence
$ git diff --stat main...HEAD
exit: 0
 .../changes/fx-calendar-trigger/.super-coding.yaml |   1 +
 openspec/changes/fx-calendar-trigger/tasks.md      |   6 +-
 skills/fx-daily-report/SKILL.md                    |  16 ++
 state/calendar-2026.json                           | 279 +++++++++++++++++++--
 tests/test_calendar.py                             |  57 +++++
 5 files changed, 333 insertions(+), 26 deletions(-)
sc-evidence: sha256:71eed77357cc869febe30766154621ac4b21f46465b4c8c1de9ab3d67b3de85d kind:automated
```
