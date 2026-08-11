# SuperCoding Design Handoff

- Change: fx-bis-macro-direct
- Phase: design
- Mode: compact
- Context hash: 8324719df824aa28a11b9d269eab2cc6fcc3beed62c87de71c43a21ddcb262d6

Generated-by: super-coding-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/fx-bis-macro-direct/proposal.md

- Source: openspec/changes/fx-bis-macro-direct/proposal.md
- Lines: 1-58
- SHA256: d63958916f8c7bcf2b2225d934034445886ccb7a60cf53187e41bdd4ba0cdf7e

```md
## Why

日报当前印出的"实际利率梯队"里,**五个经济体的政策利率全部是错的,三个经济体的实际利率符号是反的**。

`config/indicators.json` 里政策利率的 `series_id` 本来就是 `BIS/WS_CBPOL/D.XX` —— 我们一直在读 BIS 的数据,只是隔着一层滞后 13 个月的 DBnomics 镜像。这不是"换源",是**去掉中间商**。

2026-08-11 实测对照(BIS Stats API 直连 vs 当前快照):

| 经济体 | 政策利率 现状 → 真值 | CPI 同比 现状 → 真值 | 日报印的实际利率 | 真值 |
|---|---|---|---|---|
| 巴西 | 15.0(2025-07)→ **14.25**(2026-08-04) | 5.225(2025-07)→ 4.641(2026-06) | 9.775 | 9.609 |
| 菲律宾 | 5.25(2025-07)→ **4.75**(2026-07-31) | 1.274(2025-05)→ **6.363**(2026-06) | 3.976 | **−1.613** |
| 泰国 | 1.75(2025-07)→ **1.0**(2026-07-30) | 0.235(2025-03)→ **2.420**(2026-06) | 1.515 | **−1.420** |
| 美国 | 4.375(2025-07)→ **3.625**(2026-08-04) | 3.531(2026-06,BLS) | 0.844 | 0.094 |
| 欧元区 | 2.0(2025-07)→ **2.25**(2026-08-04) | 1.9(2025-12)→ **2.749**(2026-06) | 0.1 | **−0.499** |

日报写的是"实际利率梯队:巴西 9.775、菲律宾 3.976、泰国 1.515、美国 0.844、欧元区 0.1",五个全为正,并据此写了"菲律宾……套息支撑""巴西……构成雷亚尔的套息支撑"。真实情况是**菲律宾、泰国、欧元区的实际利率都是负的**,比索的套息叙事完全讲反。

防编造纪律本身没有失效——报告如实标注了"CPI 滞后 15 个月,套息结论应据此打折"。但它仍然印出了那个数并在上面搭了结论。这说明陈旧镜像的代价不止"不新鲜",而是**能产出方向性错误的结论**。

**口径已交叉验证,非假设**:BIS `WS_LONG_CPI` 的 `UNIT_MEASURE=771`,美国 2026-06 = `3.531425`,与快照中已可信的 BLS 值 `3.531`(`source: bls`)逐位吻合,证实该维度为同比百分比。

顺带修一个 P3/P4 的硬前置:`scripts/collect/util.py` 的 `fetch_text` 用 `decode("utf-8", errors="replace")`,遇到 gzip 响应会把压缩体变成乱码,伪装成"解析失败"落成 gap,与真实故障不可区分——属静默劣化。

## What Changes

- `scripts/collect/util.py`
  - `fetch_text` / `fetch_json` 按 gzip 魔数(`raw[:2] == b"\x1f\x8b"`)自动解压;解压失败抛出可被上层转成 gap 的异常,**不得**再让 `errors="replace"` 把压缩体伪装成解析失败
  - 两者接受可选 `headers` 参数(后续 Eurostat 需 `Referer` + `X-Requested-With`);默认 `User-Agent: macro-fx-collector/0.1` 不变
- `scripts/collect/macro.py`
  - 新增 BIS 分支:一次 GET 取 `WS_CBPOL`(政策利率,日频)与 `WS_LONG_CPI`(CPI 同比,月频),`csv.DictReader` 按列名取 `REF_AREA` / `TIME_PERIOD` / `OBS_VALUE`
  - 指标来源优先级确定为 **BLS > BIS > DBnomics**;美国 CPI 仍归 BLS,BIS 不得覆盖
  - BIS 缺某经济体或整体不可达时,**逐指标**回落 DBnomics,复用现有 `_mark_source_change` 标出回落方向
  - 政策利率的 `prev` 取**上一个不同的利率水平**及其生效日;窗口内无变动时 `prev` 为 `null`
- `config/endpoints.json` 增 `bis_cbpol_url`、`bis_cpi_url`
- `config/indicators.json` 增 BIS 维度键(`REF_AREA`),保留现有 `series_id` 作 DBnomics 回落用
- 经常账户 5 条不动(BIS 不覆盖,实测 US/EA/PH/TH 停在 2025-Q1、BR 2025-Q2),继续走 DBnomics

**预期降级(不是 bug)**:换源当日 10 个指标会同时带上 `source_changed_from`,`is_new_release` 被强制置 `false`。按 `skills/fx-daily-report/SKILL.md` 禁令 5,当日这些指标一律禁止用于同比叙述,报告会显得偏空。这是防编造纪律的正确行为,验证阶段不得当成缺陷。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `fx-data-collection`:「宏观数据增量采集」的来源与新鲜度要求变更——新增 BIS 直连为主源、明确三级优先级与逐指标回落、政策利率前值口径改为"上一个不同水平";并新增 HTTP 响应压缩兜底要求(压缩体不得被静默读成解析失败)。

## Impact

- 代码:`scripts/collect/util.py`、`scripts/collect/macro.py`
- 配置:`config/endpoints.json`、`config/indicators.json`
- 测试:`tests/test_macro.py`、`tests/test_snapshot.py`,新增 util 的压缩兜底回归测试
- 下游:日报「数据发布」「定价含义」两行的数值会整体变化;换源当日按禁令 5 降级
- 外部依赖:新增 `stats.bis.org`(零 key,`text/csv`)。BIS 无公开 SLA 与速率限制说明;CSV 列名可能随 SDMX 版本变,故强制按列名取
- 不影响:汇率采集、事件采集、官方公告、年历、周度聚合器、校验器
```

## openspec/changes/fx-bis-macro-direct/design.md

- Source: openspec/changes/fx-bis-macro-direct/design.md
- Lines: 1-90
- SHA256: d8a6425f65e9909eb7694f405a1de93fa9a77fdaf14afadda1e658d9662c5fd8

[TRUNCATED]

```md
## Context

`scripts/collect/macro.py` 现在按 `config/indicators.json` 逐条打 DBnomics 的 `series/{series_id}` 端点,每条一次 GET,15 条指标 15 次请求。美国 CPI 已在 `fx-source-upgrade` 中改走 BLS 公共 API,其余 14 条仍走 DBnomics。

问题在于 DBnomics 是**镜像**:它转发 IMF 与 BIS 的序列,但更新节奏远慢于上游。实测滞后 8–17 个月,并且政策利率五条**全部给出过期值**(见 proposal 的对照表)。而 `indicators.json` 里政策利率的 `series_id` 写的就是 `BIS/WS_CBPOL/D.XX` —— 上游本来就是 BIS。

`scripts/collect/util.py` 只有 22 行,`fetch_text` 固定 UA、无 header 参数、`decode("utf-8", errors="replace")`。后者对 gzip 响应会产出乱码而非异常,使"压缩没解开"与"源返回了垃圾"在 gap 里不可区分。

## Goals / Non-Goals

**Goals:**
- 五经济体 CPI 同比与政策利率取自 BIS 直连,滞后从 8–17 个月降到 2 个月内(CPI)、7–12 天内(政策利率)
- 单源失败不扩散:BIS 不可达或缺某经济体时,该指标独立回落 DBnomics,并留下可见的换源标记
- `util.fetch_*` 不再把压缩体静默读成解析失败,并为后续 P3/P4 留出自定义 header 通道

**Non-Goals:**
- 不接 BSP(用户已决定尊重其 `robots.txt`)
- 不动事件通道、年历、经常账户
- 不做历史回填:只改今后采集,已归档快照不动
- 不引入缓存层或本地数据库

## Decisions

### D1:批量取数 + 逐指标回落,而不是逐指标取数

BIS 的 SDMX key 支持 `D.US+XM+PH+TH+BR` 一次覆盖五经济体,两个 dataflow 共 2 次 GET(现状 DBnomics 是 14 次)。

**代价**:一次 GET 覆盖五经济体 = 单点故障。故回落粒度必须仍是**逐指标**——BIS 整体失败时 10 个指标各自回落 DBnomics,BIS 只缺某经济体时只有那一条回落。

**备选**:逐经济体分别请求 BIS(10 次 GET)。否决——请求数翻五倍换不来更细的失败隔离,因为批量响应里"缺某经济体"本来就能识别。

### D2:三级优先级 BLS > BIS > DBnomics

美国 CPI 在 `fx-source-upgrade` 已确立走 BLS(带 `lag_months` 与同月同比确定性计算),BIS 的 US CPI 虽然逐位吻合,但引入第二权威只会制造"两个都合法"的歧义。

实现上维持 `macro.py` 现有形态:先算 `bls_row`,再取 BIS 批量结果,最后对仍缺的指标打 DBnomics。

### D3:`WS_CBPOL` 取最近一个非 NaN 观测

BIS 政策利率是日频,非工作日 `OBS_VALUE` 是字符串 `"NaN"`(实测 15 行里 2 行)。取"最后一行"会拿到 `NaN`。

判定必须显式:`str(v).strip().upper() == "NAN"` 或空串即跳过。**不能**依赖 `float("NaN")` 成功转换后再判——那会把 NaN 悄悄带进数值比较,违反仓库的"NaN/Inf 不得穿过比较"约定。

### D4:政策利率的 `prev` = 上一个**不同**的利率水平

日频序列绝大多数日子与前一日相同,取"上一个观测"会永远产出 `14.25 → 14.25`,对报告零信息。改为向前扫描到第一个与当前值不同的非 NaN 观测,同时记录该水平的**最后生效日**,让报告能写出"上次变动在 X 日,从 A 降到 B"。

窗口内始终没有变动时 `prev` 为 `null`,**不得**等于 `value` —— 那会被读成"持平",而真相是"窗口内没看到变动"。这与本仓库已有的 `count_capped`、`fixings_verdict` 是同一条纪律:**下界与观测缺口必须可辨**。

`lastNObservations` 取多少决定了能回溯多远。取 90(约三个月工作日)——对多数央行足够覆盖上一次变动,取不到就如实给 `null`。

### D5:CSV 按列名取,缺列即整体回落

两个 dataflow 的列集合不同(`WS_CBPOL` 有 `TITLE`/`COMPILATION`,`WS_LONG_CPI` 有 `TITLE_TS`/`COVERAGE`),只有 `FREQ`/`REF_AREA`/`TIME_PERIOD`/`OBS_VALUE`/`UNIT_MEASURE` 是共有的。

用 `csv.DictReader` 按列名取。三个必需列任一缺失 → 记 gap 并让该 dataflow 整体回落,**禁止按位置索引**——SDMX 版本升级时列序变化不会报错,只会静默取错列。

### D6:`REF_AREA` 映射表显式写死

BIS 用 `XM` 表示欧元区,仓库内部用 `EA`。映射写成模块级常量并双向可查,不做字符串启发式。

### D7:gzip 在响应侧兜底,不在请求侧规避

实测发 `Accept-Encoding: identity` 无效(同一 URL 连测 4 次 4/4 仍返回 gzip)。故按响应体魔数判定:`raw[:2] == b"\x1f\x8b"` → `gzip.decompress`。

解压失败必须抛异常(由调用方转 gap),**不得**回退成 `errors="replace"`。当前行为的问题正是"看起来解析失败"掩盖了"压缩没解开"。

BIS 自身返回 `Content-Encoding: None`,不走这条路径;本项是为 P3/P4 铺路,并顺手消除一个已存在的静默劣化。

## Risks / Trade-offs

- **BIS 单点故障** → 逐指标回落 DBnomics(D1);回落方向由现有 `_mark_source_change` 标记,不新写逻辑
- **换源当日 10 指标同时标 `source_changed_from`,当日报告降级** → 已在 proposal 明确为预期行为;验证阶段以"是否正确标记并禁止同比叙述"为准,而非"报告是否好看"
- **BIS 落后央行决议数日**(实测 BR 停在 2026-08-04 = 14.25,而 COPOM 2026-08-05 已定 14.00)→ 如实呈现 `period`,不补算、不外推。若后续要更快,应在 P3 接 BCB COPOM 决议通道,而不是在这里猜
- **CSV 列名随 SDMX 版本变** → D5 的缺列检测把静默取错变成显式 gap
- **`"NaN"` 字符串混入数值比较** → D3 的显式字符串判定
- **BIS 无速率限制说明** → 每次采集只 2 次 GET,远低于任何合理阈值;若日后遇限流,按现有 gdelt 的 gap 机制处理,不新建退避
- **`prev` 语义变更影响下游** → 日报 SKILL 的「数据发布」行已有 `前值 <prev>` 占位;`prev` 为 `null` 时模板已要求写"不可得",无需改 SKILL

## Migration Plan
```

Full source: openspec/changes/fx-bis-macro-direct/design.md

## openspec/changes/fx-bis-macro-direct/tasks.md

- Source: openspec/changes/fx-bis-macro-direct/tasks.md
- Lines: 1-33
- SHA256: 7ac9328f4e101c781053113929168c72e5c04855f80caebf894573f6677d4192

```md
## 1. HTTP 取数封装(P2,后续 P3/P4 的硬前置)

- [ ] 1.1 `scripts/collect/util.py` 的 `fetch_text` 按 gzip 魔数(`raw[:2] == b"\x1f\x8b"`)解压后再解码;解压失败抛异常,不得回退为有损解码。`fetch_json` 复用之
- [ ] 1.2 `fetch_text` / `fetch_json` 增加可选 `headers` 参数,与默认 `User-Agent: macro-fx-collector/0.1` 合并(调用方可覆盖,未传时行为不变)
- [ ] 1.3 回归测试:gzip 响应正常解压、`Accept-Encoding: identity` 被无视时仍解压、压缩体损坏时抛异常而非返回乱码、未压缩响应行为不变、自定义 header 随请求发出

## 2. BIS 取数与解析

- [ ] 2.1 `config/endpoints.json` 增 `bis_cbpol_url`、`bis_cpi_url`;`config/indicators.json` 为五经济体的 CPI 与政策利率补 BIS 维度键(`REF_AREA`),保留现有 `series_id` 供 DBnomics 回落
- [ ] 2.2 `scripts/collect/macro.py` 新增 BIS CSV 解析:`csv.DictReader` 按列名取 `REF_AREA` / `TIME_PERIOD` / `OBS_VALUE`;三个必需列任一缺失即抛错由上层转 gap,禁止按列位置索引
- [ ] 2.3 `REF_AREA` 映射(BIS `XM` ↔ 仓库 `EA`)写成模块级常量,不做字符串启发式
- [ ] 2.4 `WS_CBPOL` 日频序列取最近一个非 `NaN` 观测;`"NaN"` 按字符串显式判定,不得先转 float 再判,避免 NaN 穿过数值比较

## 3. 前值与优先级

- [ ] 3.1 政策利率的 `prev` 取上一个**与当前值不同**的利率水平及其最后生效日;回溯窗口内无变动时 `prev` 为 `null`,不得等于当前值
- [ ] 3.2 来源优先级接成 BLS > BIS > DBnomics:美国 CPI 保持 BLS 且 BIS 不得覆盖;BIS 取得的指标不再打 DBnomics
- [ ] 3.3 逐指标回落:BIS 整体失败 / 缺必需列 / 缺某经济体时,受影响指标各自回落 DBnomics 并记 gap,未受影响的保持 BIS;经常账户 5 条始终走 DBnomics 不受影响
- [ ] 3.4 端点未配置时静默跳过 BIS 分支(与 `feeds.py` 的"未配置 = 有意停用"同一约定),使删掉两个 URL 即可整体回滚

## 4. 测试

- [ ] 4.1 `tests/test_macro.py` 覆盖 BIS 正常路径:五经济体 CPI 与政策利率取自 BIS、`source` 为 `bis`、美国 CPI 仍为 `bls`
- [ ] 4.2 覆盖三条降级路径:BIS 整体不可达、缺必需列、缺某经济体——各自的回落粒度与 gap 记录
- [ ] 4.3 覆盖 `NaN` 处理与 `prev` 口径:末端 NaN、全 NaN、有变动、无变动(`prev` 为 null 而非等值)
- [ ] 4.4 覆盖换源标记:切换当日 10 个指标带 `source_changed_from`、`is_new_release` 为 false;回落方向同样标记
- [ ] 4.5 畸形输入不崩:CSV 空响应、列名大小写变化、`OBS_VALUE` 非数值、`REF_AREA` 含未知经济体、CSV 体积异常

## 5. 收尾

- [ ] 5.1 `skills/fx-daily-report/SKILL.md` 的「数据发布」行在 `prev` 后加 `prev_period`,写成「前值 <prev>(截至 <prev_period>)」;`prev` 为 null 时写「前值 不可得(回溯窗口内未观测到变动)」——日频序列的前值不带日期即歧义
- [ ] 5.2 跑一次真实采集,核对五经济体的 `value` / `period` / `lag_months` / `source` 与 BIS 端点直查结果逐条一致
- [ ] 5.3 `README.md` 数据源一节补 BIS 两个 dataflow 与三级优先级;注明经常账户仍走 DBnomics、BSP 因 robots.txt 不接入
```

## openspec/changes/fx-bis-macro-direct/specs/fx-data-collection/spec.md

- Source: openspec/changes/fx-bis-macro-direct/specs/fx-data-collection/spec.md
- Lines: 1-107
- SHA256: d1a2ace7526a98e7107685c66fd3f6fddf487d6dfdfc0d392e428ea6618a6641

[TRUNCATED]

```md
## MODIFIED Requirements

### Requirement: 宏观数据增量采集
系统 SHALL 采集五经济体关键宏观指标的最新值与前值,来源优先级为 **BLS > BIS > DBnomics**。

美国 CPI SHALL 优先取自 BLS 公共 API(零 key);该 API 返回指数点位时,同比 SHALL 由采集脚本按同月同比确定性计算,MUST NOT 用相邻月份近似替代;上月同比 SHALL 由同一份响应算出作为 `prev`(基期缺失时记 null),使报告不必自找比较基准;BLS 路径失败或同月基期缺失时 SHALL 回落后续来源并记入缺漏。BIS MUST NOT 覆盖已由 BLS 取得的美国 CPI。

五经济体的 CPI 同比与政策利率 SHALL 直连 BIS Stats API 取得(`WS_LONG_CPI` 与 `WS_CBPOL`),MUST NOT 经由 DBnomics 镜像——实测该镜像滞后 8–17 个月且政策利率给出过期值。BIS 响应 SHALL 按列名解析(`REF_AREA` / `TIME_PERIOD` / `OBS_VALUE`),MUST NOT 按列位置索引。BIS 整体不可达、缺少必需列、或缺少某经济体时,受影响的指标 SHALL **逐条**回落 DBnomics 并记入缺漏,未受影响的指标保持 BIS 来源。

政策利率取自日频序列时,非交易日的观测值为 `NaN`;系统 SHALL 取最近一个非 `NaN` 观测作为当前值,`NaN` MUST NOT 参与数值比较。政策利率的 `prev` SHALL 为**上一个与当前值不同的利率水平**及其生效日,MUST NOT 取"上一个观测"——日频序列绝大多数相邻观测相同,后者会恒等于当前值而不含信息;回溯窗口内未出现变动时 `prev` SHALL 为 null,MUST NOT 等于当前值。

条目的 `series_id` SHALL 指向实际取数的源,MUST NOT 沿用其他 provider 的标识。每个宏观条目 SHALL 携带 `lag_months`——期号相对当日快照日期的滞后月数;期号形态无法解析时记为 null。

零 key 为默认运行路径:"前一日发布了哪些数据"的判定 SHALL 由静态年历与 GDELT 事件流承担,该路径 MUST NOT 记为缺漏;当环境变量 FRED_API_KEY 存在时,系统 SHALL 额外调用 FRED release dates 端点增强前一日美国数据发布判定,该增强调用失败时记入缺漏但不中断其余采集。

#### Scenario: 有新数据发布
- **WHEN** 前一日某跟踪指标发布了新值
- **THEN** 快照列出该指标的名称、最新值、前值与发布日期

#### Scenario: 美国 CPI 走 BLS 主源
- **WHEN** BLS 公共 API 可用且返回的指数序列含同月基期
- **THEN** 美国 CPI 同比由脚本按同月同比计算并落盘,条目标注来源为 BLS

#### Scenario: BLS 同月基期缺失
- **WHEN** BLS 返回的序列不含同月基期
- **THEN** 记入缺漏并回落后续来源,MUST NOT 用相邻月份近似计算同比

#### Scenario: BIS 直连取得五经济体指标
- **WHEN** 两个 BIS dataflow 均可达且含必需列
- **THEN** 五经济体的 CPI 同比与政策利率取自 BIS,条目标注来源为 BIS,美国 CPI 仍标注来源为 BLS

#### Scenario: BIS 整体不可达
- **WHEN** BIS 请求失败或响应无法解析
- **THEN** 受影响的 10 个指标逐条回落 DBnomics,每次失败记入缺漏,经常账户等未走 BIS 的指标不受影响

#### Scenario: BIS 缺少某经济体
- **WHEN** BIS 响应中某经济体没有任何可用观测
- **THEN** 仅该经济体的对应指标回落 DBnomics,其余经济体保持 BIS 来源

#### Scenario: BIS 响应缺少必需列
- **WHEN** BIS CSV 不含 `REF_AREA` / `TIME_PERIOD` / `OBS_VALUE` 中的任一列
- **THEN** 该 dataflow 整体回落并记入缺漏,MUST NOT 按列位置猜测取值

#### Scenario: 政策利率日频序列末端为 NaN
- **WHEN** 政策利率序列最新若干观测的值为 `NaN`(非交易日)
- **THEN** 取最近一个非 `NaN` 观测作为当前值;全部观测均为 `NaN` 时该经济体回落 DBnomics

#### Scenario: 政策利率前值取上一个不同水平
- **WHEN** 回溯窗口内出现过利率变动
- **THEN** `prev` 为变动前的利率水平,并记录该水平的最后生效日

#### Scenario: 回溯窗口内政策利率未变动
- **WHEN** 回溯窗口内所有非 `NaN` 观测的值都相同
- **THEN** `prev` 为 null,MUST NOT 等于当前值(等值会被读成"持平",而事实是窗口内未观测到变动)

#### Scenario: 换源当日标记不可比
- **WHEN** 某指标当日的数据源与上一份快照不同(**两个方向都算**:切到新源,以及新源失败回落旧源)
- **THEN** 该条目含 `source_changed_from` 标记且 `is_new_release` 为 false(期号跳变来自换源而非新发布),报告据此禁用比较表述

#### Scenario: 存量快照无来源字段
- **WHEN** 上一份快照的条目不含 `source` 字段(本变更之前生成)
- **THEN** 视其为 `dbnomics`,据此正确识别出换源

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

## ADDED Requirements
```

Full source: openspec/changes/fx-bis-macro-direct/specs/fx-data-collection/spec.md

