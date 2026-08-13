## 1. 周报侧:结论句逐字引用

- [ ] 1.1 先写会红的用例:digest 的 `articles_verdict` 改一个字后校验必须失败;整句缺失必须失败;完整引用必须通过
- [ ] 1.2 `check_weekly` 新增 `VERDICT_NOT_QUOTED` 检查,覆盖 `articles_verdict` / `official_verdict` / `fixings_verdict` 三类
- [x] 1.3 三态处理:digest 中该字段缺失或非字符串时不得当成空串通过(空串会让任意报告都"包含"它)
- [ ] 1.4 只对报告实际覆盖的币种要求引用;digest 有而报告未覆盖的币种走既有 `CURRENCY_MISSING`,不重复报错
- [x] 1.5 字段名显式枚举为模块级常量,不按 `*verdict*` 模式扫(digest 顶层的 `verdicts` 是计数 dict、`verdict_details` 是 list,会被模式匹配扫进字符串比对)
- [ ] 1.6 容器中不存在某币种条目时跳过(`digest["rates"]` 没有 USD 是合法形态,不是缺字段);未提供 `--digest` 时不得报 `VERDICT_ABSENT`

## 2. 日报侧:derive 落同构结论句

- [ ] 2.1 先写会红的用例:`derived.events.<币种>` 必须含结论句字段,且其内容随 `count`/`count_capped`/`sample_capped`/`channel_changed_from` 变化
- [ ] 2.2 `derive.py` 新增事件类结论句(仅 `events` 一类;`rates` 与 `real_rate` 明确非目标)
- [ ] 2.3 存量快照无该字段时的三态:校验器判为"该日不可校验"而非"通过",并在输出中区分于"引用错误"
- [ ] 2.4 `check_daily` 接入同一套整句包含检查,复用周报侧的实现(禁止两处各写一遍)
- [x] 2.5 新建 `scripts/verdicts.py`,只含 `join_verdict(head, caveats)`;`weekly_digest._verdict` 与 `_fixings_verdict` 的拼装改经它,判定逻辑一行不改(共享拼装,不共享判定)
- [ ] 2.6 `derive.SCHEMA_VERSION` 升到 2,同步 `EMPTY_EVENTS_DERIVED`;`tests/test_derive.py` 的键集断言会红,那是防漂移哨兵,不得靠放宽断言消除
- [ ] 2.7 校验器按 `derived.schema_version >= 2` 分流存量快照,并在输出中打印「N 个币种因快照 schema 过旧未校验结论句」——「跳过」与「通过」必须可区分

## 3. SKILL 引用规则

- [ ] 3.1 `skills/fx-daily-report/SKILL.md`:事件结论改为「逐字引用 `derived.events.<币种>` 的结论句」,删去让 LLM 按布尔拼话术的段落
- [ ] 3.2 `skills/fx-weekly-report/SKILL.md`:确认三类 verdict 的引用规则写明「整句逐字」,补上此前未明确的部分

## 4. 历史产物处置

- [ ] 4.1 重生成 `reports/weekly/2026-W33.md` 使其与当前 digest 配对,并通过新校验
- [ ] 4.2 确认不引入任何"历史产物豁免"开关(豁免机制会成为下一个绕过点)

## 5. 变异靶点与回归

- [ ] 5.1 逐条列出必须被杀掉的变异靶点(Design Doc §7 已定 10 条:空串放行、`in` 方向反、只查一侧、三类只查一类、schema 闸门反向、只查第一个币种、覆盖让位失效、`join_verdict` 空括号、非字符串未拦、`digest is None` 误报)
- [ ] 5.2 跑变异电池,全部 KILLED;电池脚本归档至 `docs/superpowers/evidence/` 并自带基线自检与 STALE 硬失败
- [ ] 5.3 全量测试通过(基线 554),真实产物端到端复核(日报 + 周报各跑一次校验器)

## 6. delta spec

- [ ] 6.1 `specs/fx-daily-report/spec.md`:MODIFY `### Requirement: 数字纪律`,补结论句逐字引用条文与场景
- [ ] 6.2 `specs/fx-weekly-report/spec.md`:MODIFY `### Requirement: 周报跨日聚合与数字溯源`,同上
