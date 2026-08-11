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

无需迁移:采集层改动只影响今后生成的快照。已归档的 `data/*.json` 不动,历史日报不重算。

首次采集后,当日快照的 10 个宏观条目会带 `source_changed_from: "dbnomics"`;这是识别切换是否生效的直接证据。

回滚:把 `config/endpoints.json` 里两个 BIS URL 删掉即可——`_bis` 分支在端点未配置时静默跳过(与 `feeds.py` 的"未配置 = 有意停用"同一约定),全部指标自动回到 DBnomics。

## Open Questions

无。两个原本待定的设计点(`prev` 口径、换源首日降级)已由用户在 open 阶段拍板,分别落为 D4 与 proposal 的「预期降级」段。
