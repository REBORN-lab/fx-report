## Context

上游是 2026-08-11 四视角诊断(workflow wf_e1d49d18-70d),已完成问题空间探索、机制定位(文件:行号级)与方案分层,本 change 取其中"数据底座"一层。现状约束不变:零 API key、Python 标准库 only、check_report 白名单 = 快照∪要点表∪小整数。

## Goals / Non-Goals

- Goals:让跨日对比在数据层可判定(ref_date)、让事件采集在限流下有存活率、让报告有脚本算好的派生定量可引
- Non-Goals:不改校验器(留给第 4 个 change)、不换宏观源、不接 RSS(留给第 3 个)、不放松防编造纪律

## Decisions

1. **ref_date 存快照顶层 `rates_ref_date`,并在每币种 entry 存 `prev_ref_date`**。Frankfurter v1 响应含 `date` 字段(参考价定盘日),整档一个值,顶层存最省;prev 侧从上一份快照读取,使 review.py 无需再打开第三个文件。相比"每币种各存一份"省重复,相比"只存顶层不存 prev"让 review 判定自足。
2. **review.py 的连平判定改为三分支**:ref_date 均存在且相等 → 输出"参考价未更新(非工作日)",不参与方向核对(既有 `direction_outcome` 保持"无法判定",但材料行文案区分);ref_date 不同 → 正常比较;任一 ref_date 缺失(历史快照)→ 退回旧行为。向后兼容存量快照。
3. **硬 429 与软限速统一走退避重试**:`_query_with_retry` 判定条件从 `err == "soft-rate-limited"` 扩为"软标记 or 错误串含 429";重试仍只一次(避免把单次运行拖成小时级)。延迟默认 5→20s(五币种串行总耗时约 80s,可接受),`FX_GDELT_DELAY_S` 覆盖机制保留。
4. **查询顺序按日期确定性轮转**:`offset = sum(ord) of date % 5`,五币种循环右移。确定性保证同一天重跑顺序一致(测试可断言),轮转保证限流的"后几个必挂"不总砸同一批币种。
5. **derived 由新模块 `scripts/collect/derive.py` 在快照组装末尾计算**,输入是已成型的 rates/macro/events + 近 N 份历史快照,输出 `derived` 节。放采集层而非 review.py:要点表(第 2 步)就要用,而 review.py 在第 3 步。
6. **派生值一律 round 后落盘**,且实际利率强制携带 `rate_period`/`cpi_period` 两个原文期号——期错配是编造风险最大处,让 LLM 引用时无法隐藏。
7. **tone 直接删除而非置空**:artlist 端点不返回该字段(实测 40/40 为 null),留着即误导。

## Risks / Trade-offs

- [延迟 20s 令单次采集变慢] → 五币种约 80s,cron 场景可接受;`FX_GDELT_DELAY_S` 可下调
- [derived 计算引入新的错误面] → 全部走 isinstance 门 + 数值有限性检查,任一输入不可用即该项写 null 并记 gap,不抛异常
- [历史快照无 ref_date/derived] → 所有读取路径带缺失回退,测试覆盖"存量快照"场景
- [round 精度选择] → 涨跌% 保留 3 位、区间保留原值精度、实际利率保留 3 位;写进 spec 避免漂移

## Migration Plan

新增字段,不改既有字段语义;历史快照不回填(报告只读当日+近 N 日,缺失即降级)。回滚 = git revert。
