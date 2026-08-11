# SuperCoding Design Handoff

- Change: fx-source-upgrade
- Phase: design
- Mode: compact
- Context hash: f9e51070a44ac0c9abdd68f142d610a56f2c4da03b34e88e98e775835fb4ce52

Generated-by: super-coding-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/fx-source-upgrade/proposal.md

- Source: openspec/changes/fx-source-upgrade/proposal.md
- Lines: 1-39
- SHA256: 78055bfd56a26f0f837dd2d28b55cf1f22cc1d9311645be2ac49187b06f756ae

```md
## Why

2026-08-11 诊断的两条数据源现实:①事件层只有 GDELT,限流时该币种当日归因归零,且"消息源是谁、可信吗"答不出;②DBnomics 镜像的宏观指标全部滞后 219–498 天,`is_new_release` 五天内为 true 的次数是 **0**,"数据发布"栏目对日频报告零增量。

本 change 的取舍由**实测探针**定案(2026-08-11,全部本机实跑):

| 候选源 | 结果 |
|---|---|
| Fed press RSS(press_all / press_monetary) | ✅ 200,monetary feed 首条即 "Federal Reserve issues FOMC statement" |
| ECB press RSS | ✅ 200,10 条 |
| BLS v1 timeseries(零 key) | ✅ 200,最新观测 **2026-06**,比 DBnomics 的 2025-07 新 11 个月 |
| BCB SGS API 与 BCB 新闻 feed | ❌ 全域 HTTP 502,两轮重试一致 |
| BSP RSS / 媒体发布页 | ❌ 404 |
| BOT | ❌ 无 feed,仅 HTML 页 |
| ECB Data Portal HICP | ✅ 200,但最新观测 2025-12 —— **与 DBnomics 同期**,滞后来自源本身,换源无收益 |

## What Changes

- 新增 `scripts/collect/feeds.py`:抓 Fed 与 ECB 官方新闻 RSS(`xml.etree`,零 key),按币种归入 `events[<cur>]["official"]`;失败逐源记 gap,不影响 GDELT 与其余采集
- `macro.py`:美国 CPI 改走 BLS v1(返回指数点位,**同比由脚本按同月同比确定性计算**,不交给 LLM);BLS 失败时回落 DBnomics 并记 gap
- 全部宏观条目新增 `lag_months`(期号相对快照日期的滞后月数,脚本计算):滞后不再隐形,报告可如实说明"该值滞后 N 个月"
- BR/PH/TH/EA **不换源**(探针无更优解),但滞后经 `lag_months` 显式披露
- `skills/fx-daily-report/SKILL.md`:要点表加"官方公告"行(引 `official`,注明发布方);数据发布行要求带滞后月数

## Capabilities

### New Capabilities

无(事件与宏观采集均属既有 `fx-data-collection`)。

### Modified Capabilities

- `fx-data-collection`:事件采集增加央行官方公告通道;宏观采集增加 BLS 主源与滞后披露

## Impact

- 新文件:`scripts/collect/feeds.py`、`tests/test_feeds.py`
- 改动:`scripts/collect/macro.py`、`scripts/collect/__main__.py`、`config/endpoints.json`、`skills/fx-daily-report/SKILL.md`、`tests/test_macro.py`
- `check_report.py` 零改动
```

## openspec/changes/fx-source-upgrade/design.md

- Source: openspec/changes/fx-source-upgrade/design.md
- Lines: 1-27
- SHA256: f56f848a1a208df17a91bbe198fbc3789369a255c36077229e285fec56801cf7

```md
## Context

延续 `fx-data-quality-derived` 的底座:脚本算好、LLM 逐字引用。本 change 补的是**输入侧**——事件多一个高可信通道,宏观少 11 个月滞后。约束不变:零 API key、标准库 only、任何模块内部异常转 gap 绝不上抛。

## Goals / Non-Goals

- Goals:GDELT 限流时仍有可署名的官方事件;美国 CPI 用得上今年的数;所有宏观值的滞后可见
- Non-Goals:不为 BCB/BSP/BOT 找替代抓取路径(探针已证不可达,反复试探是浪费);不改校验器;不引入第三方库

## Decisions

1. **RSS 只做 Fed 与 ECB**。探针是唯一依据:这两家 200 且结构规整,其余三家 404/502。**不写"将来可能可用"的占位代码**——不可达的源写进 config 只会在每天的 gaps 里刷噪音。BCB/BSP/BOT 的缺口写进 proposal 与 README。
2. **官方公告归入 `events[<cur>]["official"]` 而非新建顶层节**。报告层"昨日事件"本就按币种组织,同处一个币种命名空间省一次结构转换;`articles`(GDELT)与 `official`(RSS)并列,来源可辨。Fed → USD,ECB → EUR。
3. **BLS 返回指数点位,同比由 `macro.py` 计算**。`(idx[m,y] / idx[m,y-1] - 1) * 100`,round 到 3 位。这是脚本的确定性计算,与"LLM 禁算"不冲突;同月缺失则该指标记 gap 并回落 DBnomics,**不用近似月份凑**(错配一个月的 CPI 同比会得出可信但错误的结论)。
4. **BLS 失败回落 DBnomics 并记 gap**,而非直接失败:美国 CPI 是五币种共同的锚,宁可用旧值 + 显式滞后,也不要整项空缺。
5. **`lag_months` 按期号首尾解析**。`YYYY-MM` 与 `YYYY-MM-DD` 两种形态都出现在现有快照里,统一解析到年月后按月差计算;无法解析则记 null(不猜)。

## Risks / Trade-offs

- [BLS 无 key 的公共 API 有日配额] → 每日一次五指标以内,远低于配额;失败有 DBnomics 回落
- [RSS 条目与币种的映射是硬编码的两条] → 只有两家,硬编码比配置更直白;新增发布方时再抽象
- [`official` 让事件节变长] → 每币种至多取 3 条,与 GDELT top-3 同量级
- [BLS 指数同比与 IMF 口径不同] → 快照保留 `series_id` 与 `source` 字段,口径可追溯;报告引用时带期号

## Migration Plan

新增字段与新增 payload 键,历史快照不回填;`lag_months` 缺失即视为未知。回滚 = git revert。
```

## openspec/changes/fx-source-upgrade/tasks.md

- Source: openspec/changes/fx-source-upgrade/tasks.md
- Lines: 1-16
- SHA256: 4bc8bb1bbed8aa5136d705038d92997cbfb6c6ecb412c09845ea715227b55bd6

```md
# Tasks: fx-source-upgrade

## 1. 央行官方公告通道

- [ ] 1.1 新建 `scripts/collect/feeds.py`:用 `xml.etree` 解析 Fed / ECB 官方 RSS,每源至多取 3 条(title/link/pubDate/issuer),Fed→USD、ECB→EUR;单源失败记 gap 不影响其余;非 XML/结构异常/深嵌套一律转 gap 不上抛。`config/endpoints.json` 增两个 feed URL。测试:正常解析、单源 404、非 XML 正文、items 缺字段、条数上限
- [ ] 1.2 `__main__.py` 接线:feeds 结果并入 `events[<cur>]["official"]`,GDELT 失败的币种也能有 official;`derived.events.count` 语义不变(仍只数 GDELT `articles`)。测试:端到端快照含 official、GDELT 全挂时 official 仍在

## 2. 宏观源升级与滞后披露

- [ ] 2.1 `macro.py` 美国 CPI 走 BLS v1:解析指数序列,按同月同比计算同比(round 3 位),记 `source: "bls"`;同月缺失或请求失败 → 记 gap 并回落 DBnomics。测试:正常同比计算、同月缺失、BLS 失败回落、bool/非数值输入
- [ ] 2.2 全部宏观条目加 `lag_months`(期号相对快照日期的滞后月数,支持 `YYYY-MM` 与 `YYYY-MM-DD`,不可解析记 null)。测试:两种期号形态、跨年、不可解析

## 3. 报告侧与回归

- [ ] 3.1 `skills/fx-daily-report/SKILL.md`:要点表加"官方公告"行(引 `official`,注明发布方与日期);数据发布行要求带 `lag_months`;README 数据源节补 Fed/ECB RSS 与 BLS,并写明 BCB/BSP/BOT 探针失败
- [ ] 3.2 全量测试通过;真实跑一次采集确认 official 与 lag_months 落盘;既有报告重跑 `check_report.py` 退出码不变
```

## openspec/changes/fx-source-upgrade/specs/fx-data-collection/spec.md

- Source: openspec/changes/fx-source-upgrade/specs/fx-data-collection/spec.md
- Lines: 1-70
- SHA256: 14b8e05c2c6ce034888890ccfdef4bdc425b2a8c6d9a7e08c6c52a8b02b1a05d

```md
# fx-data-collection Delta Spec

## ADDED Requirements

### Requirement: 央行官方公告采集
系统 SHALL 从央行官方新闻 RSS 采集公告条目,作为 GDELT 之外的高可信事件通道,并按发布方归入对应币种的 `official` 列表;每源至多保留 3 条,条目 SHALL 含标题、链接、发布时间与发布方。任一源失败 MUST 记为缺漏且 MUST NOT 影响其余源与其余采集模块。仅纳入实测可达的官方源;不可达的源 MUST NOT 写入配置(避免每日缺漏噪音),其缺口 SHALL 记录在文档中。

#### Scenario: 官方源正常
- **WHEN** Fed 与 ECB 的 RSS 均可访问
- **THEN** 快照 `events.USD.official` 与 `events.EUR.official` 各含至多 3 条(标题/链接/时间/发布方)

#### Scenario: 单个官方源失败
- **WHEN** 某官方源请求失败或返回非 XML
- **THEN** 该源记为缺漏,其余官方源与 GDELT 采集照常完成

#### Scenario: GDELT 失败时官方通道仍在
- **WHEN** 某币种 GDELT 采集被限流而其官方源可用
- **THEN** 该币种仍有 `official` 条目可供报告引用,GDELT 缺漏照常披露

#### Scenario: 官方公告不计入事件计数
- **WHEN** 派生指标计算某币种事件计数
- **THEN** 计数只统计 GDELT `articles`,`official` 不计入(两个通道口径不同,合并会让计数不可比)

## MODIFIED Requirements

### Requirement: 宏观数据增量采集
系统 SHALL 从 DBnomics(五经济体;provider 以实测可用为准,当前为 IMF/BIS/ECB 口径)采集关键宏观指标的最新值与前值。美国 CPI SHALL 优先取自 BLS 公共 API(零 key);该 API 返回指数点位时,同比 SHALL 由采集脚本按同月同比确定性计算,MUST NOT 用相邻月份近似替代;BLS 路径失败或同月基期缺失时 SHALL 回落 DBnomics 并记入缺漏。每个宏观条目 SHALL 携带 `lag_months`——期号相对当日快照日期的滞后月数;期号形态无法解析时记为 null。零 key 为默认运行路径:"前一日发布了哪些数据"的判定 SHALL 由静态年历与 GDELT 事件流承担,该路径 MUST NOT 记为缺漏;当环境变量 FRED_API_KEY 存在时,系统 SHALL 额外调用 FRED release dates 端点增强前一日美国数据发布判定,该增强调用失败时记入缺漏但不中断其余采集。

#### Scenario: 有新数据发布
- **WHEN** 前一日某跟踪指标发布了新值
- **THEN** 快照列出该指标的名称、最新值、前值与发布日期

#### Scenario: 美国 CPI 走 BLS 主源
- **WHEN** BLS 公共 API 可用且返回的指数序列含同月基期
- **THEN** 美国 CPI 同比由脚本按同月同比计算并落盘,条目标注来源为 BLS

#### Scenario: BLS 同月基期缺失
- **WHEN** BLS 返回的序列不含同月基期
- **THEN** 记入缺漏并回落 DBnomics 数值,MUST NOT 用相邻月份近似计算同比

#### Scenario: 滞后月数披露
- **WHEN** 某宏观条目的期号可解析
- **THEN** 该条目含 `lag_months`,报告层可据此说明数值的陈旧程度

#### Scenario: 期号不可解析
- **WHEN** 某宏观条目的期号形态无法解析为年月
- **THEN** `lag_months` 记为 null,不做猜测

#### Scenario: 零 key 默认路径
- **WHEN** 环境变量中无 FRED_API_KEY
- **THEN** 采集按默认路径完成(静态年历与 GDELT 承担发布判定),gaps 中不出现 FRED 相关条目

#### Scenario: FRED 增强路径失败
- **WHEN** FRED_API_KEY 存在但 FRED 请求失败
- **THEN** FRED 失败记入缺漏,DBnomics 与其余采集照常进行

### Requirement: 央行议息静态年历对照
系统 SHALL 维护一份含五家央行(Fed/ECB/BSP/BOT/BCB)议息会议日程与可验证的统计发布日程的静态年历文件,采集时 SHALL 标注前一日与当日是否命中日历事件。日程条目 SHALL 仅录入可从官方来源验证的日期,来源 URL 与抓取日期 SHALL 记录在文件内;无法验证的日程 MUST NOT 录入推测值,其缺口 SHALL 记录在文件的维护说明中。

#### Scenario: 昨日为议息日
- **WHEN** 静态年历中前一日存在某央行议息会议
- **THEN** 快照标记该事件(央行名/事件类型/日期)供日报引用

#### Scenario: 命中统计发布日
- **WHEN** 静态年历中当日或前一日存在某项统计发布(如美国 CPI)
- **THEN** 快照同样标记该事件,报告可据此写出具体的催化剂日期

#### Scenario: 无法验证的日程不录入
- **WHEN** 某经济体的官方发布日历无法从本机验证
- **THEN** 该经济体的发布日期一条不录,缺口写入维护说明
```

