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
