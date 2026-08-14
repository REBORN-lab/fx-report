## 1. 周报侧:结论句逐字引用

- [x] 1.1 先写会红的用例:digest 的 `articles_verdict` 改一个字后校验必须失败;整句缺失必须失败;完整引用必须通过
- [x] 1.2 `check_weekly` 新增 `VERDICT_NOT_QUOTED` 检查,覆盖 `articles_verdict` / `official_verdict` / `fixings_verdict` 三类
- [x] 1.3 三态处理:digest 中该字段缺失或非字符串时不得当成空串通过(空串会让任意报告都"包含"它)
- [x] 1.4 只对报告实际覆盖的币种要求引用;digest 有而报告未覆盖的币种走既有 `CURRENCY_MISSING`,不重复报错
- [x] 1.5 字段名显式枚举为模块级常量,不按 `*verdict*` 模式扫(digest 顶层的 `verdicts` 是计数 dict、`verdict_details` 是 list,会被模式匹配扫进字符串比对)
- [x] 1.6 容器中不存在某币种条目时跳过(`digest["rates"]` 没有 USD 是合法形态,不是缺字段);未提供 `--digest` 时不得报 `VERDICT_ABSENT`

## 2. 日报侧:derive 落同构结论句

- [x] 2.1 先写会红的用例:`derived.events.<币种>` 必须含结论句字段,且其内容随 `count`/`count_capped`/`sample_capped`/`channel_changed_from` 变化
- [x] 2.2 `derive.py` 新增事件类结论句(仅 `events` 一类;`rates` 与 `real_rate` 明确非目标)
- [x] 2.3 存量快照无该字段时的三态:校验器判为"该日不可校验"而非"通过",并在输出中区分于"引用错误"
- [x] 2.4 `check_daily` 接入同一套整句包含检查,复用周报侧的实现(禁止两处各写一遍)
- [x] 2.5 新建 `scripts/verdicts.py`,只含 `join_verdict(head, caveats)`;`weekly_digest._verdict` 与 `_fixings_verdict` 的拼装改经它,判定逻辑一行不改(共享拼装,不共享判定)
- [x] 2.6 `derive.SCHEMA_VERSION` 升到 2,同步 `EMPTY_EVENTS_DERIVED`;`tests/test_derive.py` 的键集断言会红,那是防漂移哨兵,不得靠放宽断言消除
- [x] 2.7 校验器按 `derived.schema_version >= 2` 分流存量快照,并在输出中打印「N 个币种因快照 schema 过旧未校验结论句」——「跳过」与「通过」必须可区分

- [x] 2.9 日报侧三档兜底(T6b):①`derived.events` 非 dict 出 `VERDICT_CONTAINER_MALFORMED` ②`covered` 里缺条目的币种出 `VERDICT_ENTRY_MISSING` ③无 `derived` 节出声明 `VERDICT_SKIPPED_NO_DERIVED`(不判违规、rc 不变)。①②只对 `schema_version >= 2` 的快照生效;③堵的是最后一个静默口子——实测 `data/2026-08-07..10.json` 四天跑出裸 `CHECK PASSED`、零声明:`derived.schema_version >= 2` 时,`derived.events` 非 dict 出 `VERDICT_CONTAINER_MALFORMED`、`covered` 里缺条目的币种出 `VERDICT_ENTRY_MISSING`;闸门只对声称带结论句的快照生效,存量快照照旧跳过

## 3. SKILL 引用规则

- [x] 3.1 `skills/fx-daily-report/SKILL.md`:事件结论改为「逐字引用 `derived.events.<币种>` 的结论句」,删去让 LLM 按布尔拼话术的段落
- [x] 3.2 `skills/fx-weekly-report/SKILL.md`:确认三类 verdict 的引用规则写明「整句逐字」,补上此前未明确的部分

## 4. 历史产物处置

- [x] 4.1 重生成 `reports/weekly/2026-W33.md` 使其与当前 digest 配对,并通过新校验
- [x] 4.2 确认不引入任何"历史产物豁免"开关(豁免机制会成为下一个绕过点)

## 5. 变异靶点与回归

- [x] 5.1 逐条列出必须被杀掉的变异靶点(Design Doc §7 已定 10 条:空串放行、`in` 方向反、只查一侧、三类只查一类、schema 闸门反向、只查第一个币种、覆盖让位失效、`join_verdict` 空括号、非字符串未拦、`digest is None` 误报)
- [x] 5.2 跑变异电池,全部 KILLED;电池脚本归档至 `docs/superpowers/evidence/` 并自带基线自检与 STALE 硬失败
- [x] 5.3 全量测试通过(基线 554),真实产物端到端复核(日报 + 周报各跑一次校验器)

## 6. delta spec

- [x] 6.1 `specs/fx-daily-report/spec.md`:MODIFY `### Requirement: 数字纪律`,补结论句逐字引用条文与场景
- [x] 6.2 `specs/fx-weekly-report/spec.md`:MODIFY `### Requirement: 周报跨日聚合与数字溯源`,同上

## 7. 要点表溯源与复盘材料块

`--strict-brief` 的白名单是「**当日**快照 ∪ 小整数」,而 `scripts/review.py` 往要点表尾部追加的复盘材料写的是**观点日**的定盘价与观点原文里的数字——结构性互斥。实测 2026-08-10 与 2026-08-13 各 `CHECK FAILED (4)`,报告正文零违规,炸的全是脚本自己写进要点表的行。且必然复发:SKILL 要求 trigger 绑市场可观测变量,合规的 trigger 必然带数字;以前不发作只因为历史 trigger 全是「采集恢复」这类**违规的**自指形态。

- [x] 7.1 先写会红的用例(先跑确认红,再写实现):块头之前的手写数字照查、块后不合式样的行照查、声明行必须在、块头两次必须出违规且不豁免、块头与行式样两处漂移即红
- [x] 7.2 块头抽为 `scripts/review.py` 的 `REVIEW_BLOCK_HEADING`(产出方是唯一事实源),`check_report.py` 只导入;导入期已确认 `review.py` 无副作用(只算一个路径常量,不读写文件、不解析 argv),且不引入 `os`——校验器不读环境变量的 AST 不变量不得被绕过
- [x] 7.3 行式样照 `review.py` 的**实际输出**枚举(先跑一遍抄下来):空行、块头、`- 首次运行,…`、`- 上一运行日(D)无未复盘观点`、`- <币种> | 观点日 D | 情景: … | 触发条件: … | 关注方向: … | <汇率 a→b 或 参考价未更新(非工作日)> | 方向核对: …`。凭印象写的正则当场被端到端用例抓到(那两处括号是 ASCII,不转义就成了捕获组)
- [x] 7.4 `check_daily` 按块头切段:块前判定一字不改;块后只豁免匹配行式样的行,不匹配的照查(伪造成本 = 伪造一整条格式完整的复盘行,不是一行假块头)
- [x] 7.5 豁免打印声明 `BRIEF_REVIEW_BLOCK_SKIPPED: 复盘材料块 N 行未纳入要点表数字溯源`;不是违规、不改退出码——「跳过」与「通过」在输出上必须可区分
- [x] 7.6 块头次数三态:0 次行为一字不变;1 次按上述豁免;≥2 次出 `BRIEF_REVIEW_BLOCK_MALFORMED` 且一行都不豁免(失败关闭),不得静默取第一个
- [x] 7.7 变异电池 6/6 KILLED(不切段 / 不校验行式样 / 删声明 / 两块头静默取第一个 / 块头在校验器里再写一遍 / 行式样凭印象写)
- [x] 7.8 全量 701 通过 rc=0(基线 687);2026-08-07..13 七天生产命令逐条 rc=0;08-10 与 08-13 报告首行的「未通过自动自检」声明已删除并复跑确认仍 rc=0
- [x] 7.9 `specs/fx-daily-report/spec.md` 的 `### Requirement: 数字纪律` 补条文与 7 条验收场景;`openspec validate fx-verdict-enforcement --strict` rc=0

## 8. weekly 静默放行路径

`--mode weekly` 下位置参数 `snapshot` 被接受却**完全不读**(修前 `build_parser()` 的 docstring 自己把这件事当"绕过手法之二"写着),而 `--digest` 缺席时结论句闸门与数字溯源**整层不跑**,却照样 `CHECK PASSED` rc=0。决定性实测(HEAD `eef783e`,真实产物,未改任何报告):把位置参数换成 `/does/not/exist.json`,**仍然 `CHECK PASSED` rc=0** —— 那个参数一个字节都没被读过。这条路径同时污染了本 change proposal 里记录的复现命令(见 proposal「## 更正(2026-08-14 实测)」)。

- [x] 8.1 先写会红的用例并实跑确认红:weekly + 位置参数须 rc=2;提示写成 warning 却跑完 rc=0 须红;无 `--digest` 时声明行缺失须红;声明行被做成违规(改 rc)须红;daily 模式被波及须红。实跑 RED:8 处失败,失败原因逐条为 `rc 0 != 2` 与「声明行 not found in 'CHECK PASSED\n'」
- [x] 8.2 weekly 分支收到非空位置参数即 rc=2 + stderr 可操作提示(点名 `--digest` 与 `--daily`);**不猜测意图**,不把它当 digest 用,`--digest` 同时给了也一律拒收——猜测正是这条缺陷的来源
- [x] 8.3 weekly 未提供 `--digest` 时打印声明行 `WEEKLY_DIGEST_ABSENT_SKIPPED: 未提供 --digest,本次未校验结论句与数字溯源`;**不是违规、不改退出码**(「未提供聚合文件」是 delta spec 里既有的合法形态),但必须出现在输出里且先于结论行——与 `VERDICT_SKIPPED_*` / `BRIEF_REVIEW_BLOCK_SKIPPED` 同一套原则
- [x] 8.4 daily 模式行为一个字不改(位置参数仍必需且仍被读),由 `test_daily_mode_still_takes_its_positional_snapshot` 与 `test_daily_mode_never_prints_it` 两侧钉住
- [x] 8.5 `NoLegacyExemptionSwitchTest._bases()` 删去 weekly 的 `snap_slot` 维:weekly 拒收位置参数后那条 base 自己就是 rc=2、跑不出任何码(实测全量 `FAILED (failures=1)`,消息为「base「weekly daily=2 snapslot=1」的基线码集合与写死的期望不符」)。**这不是放宽断言,是那条 argv 已不再是合法输入**;它守的绕过手法 ② 由 `test_no_exemption_token_survives_the_positional_slot` 接管并守得更死(逐个 `EXEMPTION_TOKEN` 塞进位置参数,全部要求 rc=2 且无结论行)
- [x] 8.6 更正 `build_parser()` docstring 里「weekly 模式下 `args.snapshot` 不读」那半句:原文保留、追加更正,说明它当时描述的是一条真缺陷而非假想绕过
- [x] 8.7 proposal.md 追加「## 更正(2026-08-14 实测)」:①那条 `CHECK PASSED` 来自位置参数形态、根本没加载 digest;②「15 与 5 出现在别处即通过」与实测相反——base-ref `799f3f7` 上 `--digest` 形态 `CHECK FAILED (11)` 恰含「数字 15 不见于…」,而 `5` 属 `ALLOWED_SMALL` 小整数白名单,从不在争议范围。原文一字不删;核心命题(`verdict` 零命中,`grep -c -i verdict` = 0)仍成立
- [x] 8.8 delta spec 补条文与 4 条验收场景(未提供聚合文件时须声明 / 提供了则不得声明 / weekly 拒位置参数 / 位置参数不得被当作聚合文件);`openspec validate fx-verdict-enforcement --strict` rc=0
- [x] 8.9 变异电池补本次修复(M16-M20)与上一次修复(M21-M25,`BRIEF_REVIEW_BLOCK_*`)的靶点,地板 15→25,实跑全部 KILLED:`KILLED 25 / 执行 25 / 登记 25(地板 25)` rc=0(跑在提交 `1665e8c`,`BASELINE OK — Ran 715 tests`);电池跑完另用 `git status --porcelain` 独立复核工作树已还原(空输出)
- [x] 8.10 全量 `Ran 715 tests` / `OK` / rc=0(基线 701);五天日报生产命令 2026-08-10…08-14 逐条 rc=0,周报 SKILL 形态 rc=0;修复前后对照:位置参数形态由 `CHECK PASSED` rc=0 变为 rc=2 + 可操作提示,无 `--digest` 形态由裸 `CHECK PASSED` 变为带 `WEEKLY_DIGEST_ABSENT_SKIPPED` 声明行且仍 rc=0
