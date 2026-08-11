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
