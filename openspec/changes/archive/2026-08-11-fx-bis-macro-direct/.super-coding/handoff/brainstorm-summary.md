# Brainstorm Summary

- Change: fx-bis-macro-direct
- Date: 2026-08-11

## 确认的技术方案

BIS 两个 dataflow 批量取数,`detail=dataonly` 参数是决定性的(891KB → 40KB,22 倍)。
CBPOL 取 `lastNObservations=400`(约 19 个月,实测最深回溯需求是美国的 170 个观测),
LONG_CPI 取 4。

`collect()` 形状不变:循环之前把 BIS 结果拉平成 `{(economy, indicator): row}` 查找表,
循环内按 BLS → BIS 查表 → DBnomics 三级命中。这让「逐指标回落」不需要额外分支,
三种降级路径(整体失败/缺列/缺某经济体)共用同一条代码路径。

`_bis_table` 内拆两个纯函数便于免网络单测:`_bis_parse`(CSV → 按 REF_AREA 的观测序列,
缺必需列抛 ValueError)、`_latest_and_prev_distinct`(观测序列 → value/period/prev/prev_period)。

`util.fetch_text` 先按 gzip 魔数解压再 decode;`gzip.decompress` 的异常不捕获,
由既有调用方转 gap。headers 参数以默认 UA 打底再 update,调用方可覆盖 UA。

## 关键取舍与风险

- `NaN` 必须在转 float **之前**按字符串判掉:`float("NaN")` 会成功,随后 NaN 的任何比较
  都是 False,会让「取最新非 NaN」与「找上一个不同值」同时给出错误结果
- 某央行连续持稳超过 19 个月时 `prev` 退化为 null——spec 明文允许的诚实退化
- BIS 落后央行决议数日(BR 停在 08-04 的 14.25,COPOM 08-05 已定 14.00),
  如实呈现不补算;要更快应在 P3 接 BCB 决议通道
- `OBS_VALUE` 实测有 `"1"` 这种无小数点形态,解析不得依赖小数点

## 测试策略

11 条变异靶点已列进 Design Doc 第 6 节,覆盖 NaN 判定、prev 口径、按列名取、
优先级、回落粒度、XM↔EA 映射、gzip 三条路径、prev_period 取末日。
`OBS_VALUE = "1"` 单独用例。

## Spec Patch

无。delta spec 的 16 个场景已覆盖;`prev_period` 由「记录该水平的最后生效日」这条要求覆盖。

## 超出原范围的一处

Design Doc 第 8 节:日频政策利率的前值不带日期即歧义,故 `skills/fx-daily-report/SKILL.md`
的「数据发布」行需加 `prev_period`。一行模板 + 一句说明,是本 change 唯一触及报告层的改动。
