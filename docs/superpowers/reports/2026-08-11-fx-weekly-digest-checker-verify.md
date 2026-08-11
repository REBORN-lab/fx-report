# 验证报告 — fx-weekly-digest-checker

- 日期:2026-08-11
- 分支:feature/20260811/fx-weekly-digest-checker
- base-ref:c3c0431
- 验证模式:full(任务数 > 3、变更文件数 > 4)

## 变更内容

本 change 是"日报周报信息密度提升"四件套的最后一件,交付两件事:

1. **`scripts/weekly_digest.py`** — 周度聚合器。此前周报里"本周涨了多少、区间多宽"
   没有任何脚本级来源,只能由 LLM 从五份日报里捞——而仓库纪律禁止 LLM 算术。
   聚合器把这些跨日量确定性算好落盘 `state/weekly-digest-<week>.json`,周报逐字引用
   即合法(与日报引用快照 `derived` 节同一模式)。
2. **`scripts/check_report.py` 数字溯源** — 新增 `--strict-brief`(日报要点表)与
   `--digest` / `--daily`(周报)。周报里出现的每个数字必须能在 digest 或当周日报里
   逐字找到,否则报 `NUMBER_UNTRACEABLE`;digest 记录的缺漏源若未在周报披露,
   报 `GAP_OMITTED`。

配套抽出 `scripts/fixings.py`,把"两次观测是否同一次定盘"的判定做成采集层与聚合器
的物理共享源——此前是复制粘贴,已因此漂移出一个 Critical。

## 六项检查

| # | 检查项 | 结果 |
|---|--------|------|
| 1 | tasks.md 全部勾选 | PASS(build guard 校验) |
| 2 | 改动文件与 tasks 描述一致 | PASS |
| 3 | 构建/导入通过 | PASS(build guard `Build passes`) |
| 4 | 全量测试通过 | PASS,372 tests(见证据块) |
| 5 | 无硬编码密钥 / 零 API key 约束保持 | PASS |
| 6 | 代码审查 | 六轮,见下 |

## 审查历程:同一个失败模式,十三次

六轮审查(第 4、5、6 轮为多视角并行 + 对抗性证伪工作流)共揪出 **13 个同型缺陷**,
全部是同一件事:**管道状态被当成市场事实,或市场事实被当成管道故障**。
每一个都是一句会公开发布的假话。

| # | 轮次 | 内容 |
|---|------|------|
| 1 | — | 采集失败被写成"事件数 0" |
| 2 | — | 换源造成的期号跳变被叙述成"通胀升至" |
| 3 | — | schema 换代造成的观测交叉被算成两次定盘 → "0.0% 周涨跌" |
| 4 | 二 | `official_total: 3` 是单日封顶样本,写成"本周 Fed 官方公告 3 条" |
| 5 | 三 | RSS 不按发布日过滤——那 3 条全部发布于 7 月,**真值 0**;上一轮补的"实际条数只多不少"还把错数断言成它并不满足的下界 |
| 6 | 四 | 第 5 条的修复新加了 `by_date`,而 `by_date.official` 是采样条数,SKILL 却规定它是"当日有公告"的唯一判据——同一个错从新后门原样复活 |
| 7 | 四 | 采集层落盘前已按标题去重,digest 拿去重后长度比每日上限 → 截断漏报 |
| 8 | 四 | "事件数 8(与前值持平)"是两天都撞上限 8 造成的假象 |
| 9 | 五 | SKILL 的"确实没发公告"授权只查 `undated`,不查采集覆盖与截断——只采到 1/5 天也逐字满足条件 |
| 10 | 五 | `by_date` 的逐日值在通道未采集时硬写 0,与聚合量的 null 自相矛盾 |
| 11 | 六 | `_verdict` 的分母取"载入到的快照份数"而非区间日历天数——漏跑一天会同时缩小分子分母,`missing` 恒为 0,脚本于是对从未被观测的日子说"全区间采集完整" |
| 12 | 六 | `events.py` 把"JSON 能解析但结构不认识"折叠成 `articles: []` 且不记 gap,采集层伪造出干净的空观测 |
| 13 | 六 | 汇率通道没有结论句,`fixings: 2`(脚本自己声明的下界)被写成"全周各仅 2 次不同定盘" |

### 前五轮是枚举补丁,第五轮起换成不变量

第 1–10 次的修法都是**堵一条路**:undated 堵上了,采集覆盖没堵;覆盖堵上了,
截断没堵;事件通道堵上了,汇率通道没堵。第五轮审查者的诊断一针见血——
"把否决权当成了枚举补丁而不是不变量"。

所以第五、六轮改成了与"脚本算好、LLM 逐字引用"同构的做法:
**把"能不能下结论"从 LLM 手里收回脚本**。

`scripts/weekly_digest.py` 现在为每个币种的每个通道产出一句结论:
`fixings_verdict` / `articles_verdict` / `official_verdict`。不变量是——

> 只有**区间内每个日历天都采到、无截断、时间戳全部可解析、无损坏快照**时,
> 才允许出现「确实 0 条」;任何一处观测缺口一律退化成「有无××无法判定」。

SKILL 相应改为「只准照抄这三句,禁止自行从计数推出'有没有'」,并把规则从模板
缩进块里搬出来独立成节(第五轮审查指出规则密度已超 LLM 可靠遵守的上限)。

第六轮修正了这个不变量最初的致命缺陷:它被陈述在了**错误的定义域**上——
分母是"我们手上有几份快照",而结论说的是"区间里每一天"。现改为按日历天数计算。

测试里有一条**总断言**而非若干场景用例:
`test_no_caveat_means_no_observation_gap` 断言 verdict 含「确实」当且仅当三类
观测缺口全部为零。逐个场景的用例挡不住"再开一条新路径",这条才是不变量本身。

## 交付产物在本轮被更正的假陈述

| 产物 | 修正前 | 修正后(真值) |
|------|--------|----------------|
| 周报 USD | Fed 官方公告 3 条 → 后改"0 条…这是事实" | 区间内未见公告,但 4/5 天未采到、1 天顶到每日上限 3 条,**有无公告无法判定** |
| 周报 EUR | 官方通道在 GDELT 限流日提供了兜底 | `fallback_days` 五币种全为 0;那条公告发布于 08-07,08-11 才被采到 |
| 周报主线 | 四者全周各仅 2 次不同定盘 | 区间内观测到 2 个不同价位,**实际定盘次数只多不少** |
| 周报缺漏 | 捏造 BR 缺口、漏掉 PH 缺口 | 实测三条 dbnomics 缺口为 PH 经常账户 / TH CPI / EA 经常账户 |
| 要点表 THB | 三条均为区域汇率转述,**无泰国本地政策信号** | top-3 漏掉了快照里唯一的泰国央行消息(BoT 将现金购房者纳入监管视野,采见 20260810),已按"货币政策相关优先"重选 |
| 日报 USD/EUR | 7 月的 Fed/ECB 公告写在"昨日发生" | 移入"定价含义"并标注发布日与"存量背景" |
| 日报 EUR | 事件数 8(与前值持平) | 两日均达采集上限,变化 0 是上限造成的,不表示事件面持平 |

## 校验器自证有效

校验器在本 change 内三次拦下我自己写错的数字,都不是演练——是真写进报告后被
`NUMBER_UNTRACEABLE` 挡回来的:change 1 的 "0.2%"、本 change 的 "0.3%"、
以及第四轮里 "48h" 的 `48`。

## 接受的偏差(backlog,已记录不修)

- **I7 白名单是无序 token 袋**:符号翻转(`-0.192%` → `+0.192%`)、跨币种数值互换、
  null 替换成小整数、删掉"(N 天采集失败)"免责句,四种篡改都能通过校验。
  修复需 `NUM_RE` 接受 `[-+]?`、`DATE_RE` 增加 `\d{4}-\d{2}`。
  **硬约束:在 `DATE_RE` 修好之前,不得从 SKILL 默认命令里移除 `--daily`** ——
  否则合规周报会因"参考月 2026-07"被切成裸数字 `2026` 和 `07` 而失败。
- **N4 ISO 周标签与滚动窗口不一致**:`weekly-digest-2026-W33.json` 覆盖的
  08-07/08/09 属于 ISO W32。已由 `window_from`/`window_to` 与"一律说覆盖区间、
  不说本周"部分缓解;周号标签本身仍是滚动窗口的标签,未改。
- **`data/` 下就地重算 derived**:`range_5d_days` 3→2、新增 `count_capped` 两次
  重算都是当前代码的确定性产物(逐字核对过其余字段未变),但在归档快照里就地改
  派生字段,等于把 `data/` 从审计留痕降级成可变缓存。
- **`_pub_date` 取发行方本地时区日历**,而窗口两端来自 UTC 快照文件名;跨零点
  几小时发布的公告可能落到相邻一天。已在 docstring 说明,不折算成 UTC。
- 现存 5 份快照都没有 `meta.caps`,聚合器按当前常量推定并计入
  `*_cap_assumed_days`;下一次采集起自动带上。
- SKILL 规则密度仍然偏高。第五、六轮已把推断从 prompt 移进脚本、把规则搬出模板
  独立成节,但两份 SKILL 加起来仍是长文档。

## 诚实的收敛判断

第六轮是**定向验证**"不变量能否被攻破",结论是 `broke_invariant: true`——三条
Critical 全部成立。这说明:每一轮审查都还在找到真问题,不能声称已经收敛。

与前五轮不同的是,第六轮的三条都指向**同一个已经建立的结构**的边界条件
(分母定义域、采集层前置条件、未覆盖的第三个通道),而不是"又一条绕过 prompt
禁令的路径"。修完之后三个通道共用同一套 verdict 机制,并有一条总断言测住不变量
本身。第七轮大概率仍能找到东西,但性质应当从"假陈述"降级为"边界与措辞"。

## 验证证据(sc-evidence 脚本自执行签名)

```sc-evidence
$ python3 -m unittest discover -s tests -t .
exit: 0
.......................................--daily 需与 --digest 同用(单独给日报不会启用数字溯源)
.周度聚合文件无法解析: Expecting value: line 1 column 1 (char 0)
.周度聚合文件无法解析: Expecting value: line 1 column 1 (char 0)
..周度聚合文件结构不符(需含 week 与 generated_from)
周度聚合文件结构不符(需含 week 与 generated_from)
.........................................................................................................................................................................................................................................................................................................................................
----------------------------------------------------------------------
Ran 372 tests in 8.529s

OK
CHECK PASSED
CHECK PASSED
CHECK FAILED (1):
 - SECTION_MISSING: 缺少币种节 THB
snapshot: /tmp/tmp2tpzs2qa/data/2026-08-10.json
gaps: 2
  - [frankfurter/all] URLError: <urlopen error [Errno 111] Connection refused>
  - [exchange-api/all] URLError: <urlopen error [Errno 111] Connection refused>
snapshot: /tmp/tmp056njkle/data/2026-08-10.json
gaps: 1
  - [calendar/all] calendar expired (valid_until=2026-01-01), 请按 README 年历维护说明更新
snapshot: /tmp/tmpt0egzmhy/data/2026-08-10.json
gaps: 1
  - [dbnomics/X] URLError: <urlopen error [Errno 111] Connection refused>
snapshot: /tmp/tmporj4yg6g/data/2026-08-10.json
gaps: 1
  - [exchange-api/all] URLError: <urlopen error [Errno 111] Connection refused>
snapshot: /tmp/tmpuzx01d1u/data/2026-08-10.json
gaps: 1
  - [frankfurter/all] URLError: <urlopen error [Errno 111] Connection refused>
snapshot: /tmp/tmpg042ui0g/data/2026-08-10.json
gaps: 5
  - [gdelt/THB] URLError: <urlopen error [Errno 111] Connection refused>
  - [gdelt/BRL] URLError: <urlopen error [Errno 111] Connection refused>
  - [gdelt/USD] URLError: <urlopen error [Errno 111] Connection refused>
  - [gdelt/EUR] URLError: <urlopen error [Errno 111] Connection refused>
  - [gdelt/PHP] URLError: <urlopen error [Errno 111] Connection refused>
snapshot: /tmp/tmpi9h62e__/data/2026-08-10.json
gaps: 1
  - [derive/all] internal error RuntimeError: boom
snapshot: /tmp/tmpesq05zud/data/2026-08-10.json
gaps: 0
snapshot: /tmp/tmpovqng2ra/data/2026-08-10.json
gaps: 0
snapshot: /tmp/tmpk2dcf1qi/data/2026-08-10.json
gaps: 5
  - [gdelt/THB] HTTPError: HTTP Error 404: Not Found
  - [gdelt/BRL] HTTPError: HTTP Error 404: Not Found
  - [gdelt/USD] HTTPError: HTTP Error 404: Not Found
  - [gdelt/EUR] HTTPError: HTTP Error 404: Not Found
  - [gdelt/PHP] HTTPError: HTTP Error 404: Not Found
snapshot: /tmp/tmpjvz278fm/data/2026-08-10.json
gaps: 0
snapshot: /tmp/tmphwoo67m9/data/2026-08-10.json
gaps: 5
  - [gdelt/THB] HTTPError: HTTP Error 404: Not Found
  - [gdelt/BRL] HTTPError: HTTP Error 404: Not Found
  - [gdelt/USD] HTTPError: HTTP Error 404: Not Found
  - [gdelt/EUR] HTTPError: HTTP Error 404: Not Found
  - [gdelt/PHP] HTTPError: HTTP Error 404: Not Found
snapshot: /tmp/tmpvzh58dkp/data/2026-08-10.json
gaps: 0
snapshot: /tmp/tmpxeybkkox/data/2026-08-10.json
gaps: 1
  - [snapshot/prev] corrupt prev snapshot 2026-08-09: JSONDecodeError: Expecting property name enclosed in double quotes: line 1 column 2 (char 1)
snapshot: /tmp/tmphdgva_33/data/2026-08-10.json
gaps: 1
  - [snapshot/prev] corrupt prev snapshot 2026-08-09: RecursionError: maximum recursion depth exceeded while decoding a JSON array from a unicode string
snapshot: /tmp/tmp1j81915a/data/2026-08-10.json
gaps: 1
  - [macro/all] internal error RuntimeError: boom
snapshot: /tmp/tmptnlvn4do/data/2026-08-10.json
gaps: 1
  - [dbnomics/X] URLError: <urlopen error [Errno 111] Connection refused>
snapshot: /tmp/tmp5h5u2zsu/data/2026-08-10.json
gaps: 0
snapshot: /tmp/tmpn7894faa/data/2026-08-10.json
gaps: 1
  - [snapshot/prev] corrupt prev snapshot 2026-08-09: top-level list, expected dict
sc-evidence: sha256:7ea0fd6e6e8916c91c83ac58b4bbe667231ca3d6b27a3d336554846fabdaba0c kind:automated
```
```sc-evidence
$ python3 scripts/check_report.py reports/weekly/2026-W33.md --mode weekly --digest state/weekly-digest-2026-W33.json --daily reports/daily/2026-08-07.md --daily reports/daily/2026-08-08.md --daily reports/daily/2026-08-09.md --daily reports/daily/2026-08-10.md --daily reports/daily/2026-08-11.md
exit: 0
CHECK PASSED
sc-evidence: sha256:ad2625a04bfee7ae12c0609e2a5a370c99d6356f5be1cd397e65f81deaa1a67f kind:automated
```
```sc-evidence
$ python3 scripts/check_report.py reports/daily/2026-08-11.md data/2026-08-11.json --brief briefs/2026-08-11-brief.md --mode daily --strict-brief
exit: 0
CHECK PASSED
sc-evidence: sha256:17c8c27a7793fbeeedda19e43be20244be30cb2acae639181d59219c73613228 kind:automated
```
```sc-evidence
$ git diff --stat c3c0431...HEAD
exit: 0
 .gitignore                                         |    1 +
 README.md                                          |   11 +
 briefs/2026-08-11-brief.md                         |   24 +-
 data/2026-08-11.json                               |   28 +-
 .../plans/2026-08-11-fx-weekly-digest-checker.md   |   15 +
 .../2026-08-11-fx-weekly-digest-checker-design.md  |   55 ++
 .../fx-weekly-digest-checker/.openspec.yaml        |    2 +
 .../fx-weekly-digest-checker/.super-coding.yaml    |   22 +
 .../.super-coding/handoff/design-context.json      |   15 +
 .../.super-coding/handoff/design-context.md        |  175 ++++
 .../changes/fx-weekly-digest-checker/design.md     |   26 +
 .../changes/fx-weekly-digest-checker/proposal.md   |   26 +
 .../specs/fx-daily-report/spec.md                  |   26 +
 .../specs/fx-weekly-report/spec.md                 |   46 +
 openspec/changes/fx-weekly-digest-checker/tasks.md |   15 +
 reports/daily/2026-08-11.md                        |   16 +-
 reports/weekly/2026-W33.md                         |   79 +-
 scripts/check_report.py                            |   67 +-
 scripts/collect/__main__.py                        |    6 +-
 scripts/collect/derive.py                          |   59 +-
 scripts/collect/events.py                          |   27 +-
 scripts/fixings.py                                 |   58 ++
 scripts/weekly_digest.py                           |  548 +++++++++++
 skills/fx-daily-report/SKILL.md                    |   40 +-
 skills/fx-weekly-report/SKILL.md                   |   82 +-
 state/weekly-digest-2026-W33.json                  |  549 +++++++++++
 tests/test_check_report.py                         |  144 +++
 tests/test_derive.py                               |   88 ++
 tests/test_events.py                               |   34 +-
 tests/test_snapshot.py                             |    7 +
 tests/test_weekly_digest.py                        | 1014 ++++++++++++++++++++
 31 files changed, 3159 insertions(+), 146 deletions(-)
sc-evidence: sha256:dbac2383a99bf81526381a1041ae3d4ef3dc071cd1e48611d3e59e3c08e6619f kind:automated
```
