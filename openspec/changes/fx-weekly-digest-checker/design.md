## Context

本序列前三个 change 建立了"脚本算好、LLM 逐字引用"的模式并在日报侧闭环。本 change 把同一模式复制到周报,并补上校验器的两处缝隙。这是唯一需要改 `check_report.py` 的 change。

## Goals / Non-Goals

- Goals:周报有真跨日聚合;周报数字可溯源;要点表数字可溯源
- Non-Goals:不改采集层;不动日报既有白名单语义(只增校验,不放松)

## Decisions

1. **digest 落盘为 JSON 而非直接注入 SKILL 文本**。与 `log_decision.py stats` 的"脚本输出、报告照抄"同构,但 JSON 便于校验器读取白名单 —— 这正是周报溯源的前提。
2. **周报白名单 = digest ∪ 各日报 ∪ 小整数**。日报本身已过数字溯源,把它并入白名单等于承认"日报里出现过的数字周报可以引用",链条完整;不并入会逼 LLM 只能用 digest,丢掉叙述性引用。
3. **`--strict-brief` 做成可选开关而非默认**。存量 brief(本变更之前生成)未必满足 `⊆ 快照`,默认开启会让历史产物一律失败;SKILL 在新流程里显式带上该参数,新产物强制受约束。
4. **digest 只算能确定性算的**:周涨跌用首末两个不同 `ref_date` 的 primary;周区间取全周不同定盘的 min/max;事件计数按币种求和;gap 按 source 计数;verdict 计数直接读决策日志。不做加权、不做归因。
5. **digest 缺输入即写 null**,与 derived 同一约定(上一 change 的 C1 教训:缺失被填成 0 就是编造)。

## Risks / Trade-offs

- [改校验器有回归风险] → 新校验全部走新增参数,不改既有 daily/weekly 路径的默认行为;既有 check_report 测试必须全绿
- [digest 与 derived 口径可能不一致] → digest 的周涨跌同样按 ref_date 去重,与 derived 的 `chg_pct_1d` 同源同法
- [`--strict-brief` 可能误伤合法引用] → brief 允许引用日报模板里的固定小整数,白名单沿用 `ALLOWED_SMALL`

## Migration Plan

新增脚本与可选参数,既有调用不受影响。回滚 = git revert。
