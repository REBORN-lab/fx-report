## Why

仓库用七轮对抗性审查把「能不能下结论」从 LLM 手里收回脚本(见归档 change
`2026-08-13-fx-gnews-event-channel`),但**执行环节是空的**:`scripts/check_report.py`
里 `verdict` 零命中,从不校验报告是否逐字引用了脚本算好的结论句。

实测(2026-08-13):周报正文写「区间内至少 15 条(3/5 天未采到)」,而配对的
`state/weekly-digest-2026-W33.json` 里 USD 的 `articles_verdict` 是「区间内至少
26 条(3/6 天未采到、…)」,

```
python3 scripts/check_report.py reports/weekly/2026-W33.md \
        state/weekly-digest-2026-W33.json --mode weekly
→ CHECK PASSED
```

原因:数字白名单是**无序词袋**——`numbers_in(report) - allowed`,只验「这个数在
聚合文件的 JSON 文本里出现过」,不验它出现在哪个字段。15 与 5 作为无关数字出现
在别处即通过。

后果:脚本算得再对,报告不引用也没人拦。前一个 change 建立的全部不变量因此没有
强制力。这是当前最高优先级的缺口。

## What Changes

- 校验器新增**结论句逐字引用检查**:聚合文件/快照中每个「脚本给出的结论」字段,
  其字符串必须整句出现在报告正文中,改一个字即失败
- `scripts/collect/derive.py` 为日报侧落**同构的结论句字段** —— 日报的 `derived`
  目前全是数值与布尔(`count_capped`/`sample_capped`/`channel_changed_from` 等),
  没有任何 `*_verdict`,结论句由 LLM 按 SKILL 模板拼装
- 两个 SKILL 的引用规则改为「逐字引用该字段」,删去让 LLM 自行按布尔拼话术的段落
- 保留既有的数字词袋检查作为**外层弱网**(覆盖结论句之外的散落数字),
  保留 `--strict-brief` 现有行为不变

**不做**(拆为后续 change `fx-collect-precision`):采集层数值精度统一;
被白名单滤除的域名落盘。

**不做**:不改结论句的措辞与判定逻辑——那是前一个 change 的成果,本次只补强制力。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `fx-daily-report`:`### Requirement: 数字纪律` —— 新增「结论由脚本给出、报告
  逐字引用」的强制条文;日报侧此前只有「报告 ⊆ 快照 ∪ 要点表」的集合式溯源
- `fx-weekly-report`:`### Requirement: 周报跨日聚合与数字溯源` —— 同上;此前
  只有「周报 ⊆ 聚合文件 ∪ 当周日报 ∪ 小整数」

两个能力属同一执行机制的两半,**刻意不拆**为两个 change:拆开会让其中一侧在
交付后一段时间内仍无强制力,而「一侧接上、另一侧没接」正是前一个 change 里
反复出现的失败模式(第五轮 Critical:字段落盘了、周报接上了、日报那侧没接)。

## Impact

- `scripts/check_report.py`(新增检查;既有检查不变)
- `scripts/collect/derive.py`(新增结论句字段;判定逻辑不变)
- `skills/fx-daily-report/SKILL.md`、`skills/fx-weekly-report/SKILL.md`(引用规则)
- **既有交付产物**:`reports/weekly/2026-W33.md` 在新校验下会变红——它与配对的
  digest 确实已不一致(digest 被重算过)。处置方式在 design 阶段决定:重生成该
  周报,或为历史产物提供明确的「不可校验」标记。这是本 change 的关键未知项之一。
- 零新增依赖(Python 标准库);零 API key 影响
