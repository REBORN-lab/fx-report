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

## 更正(2026-08-14 实测)

**上面那段复现有两处与实测不符,原文保留不删,逐条更正在此。**
核心命题不受影响(见本节末),错的是复现命令与那两个数字的说法。

### 更正一:那条 `CHECK PASSED` 来自「位置参数形态」,它根本没加载 digest

上面展示的命令把聚合文件放在**位置参数**上。而 `--mode weekly` 下 `main()` 的
weekly 分支**从来不读 `args.snapshot`** —— 数字溯源与结论句检查都挂在 `--digest`
上,`--digest` 缺席时**整层不跑**。所以那条 `CHECK PASSED` 不是「词袋放行」演示
出来的,**报告里写什么都会通过**。

决定性实测(HEAD `eef783e`,本仓库真实产物,未改动任何报告):

```
$ python3 scripts/check_report.py reports/weekly/2026-W33.md \
        state/weekly-digest-2026-W33.json --mode weekly
CHECK PASSED                                                    # rc=0

$ python3 scripts/check_report.py reports/weekly/2026-W33.md \
        /does/not/exist.json --mode weekly
CHECK PASSED                                                    # rc=0
```

第二条把位置参数换成一个**根本不存在的路径**,仍然 `CHECK PASSED` rc=0 ——
那个参数一个字节都没被读过,连「文件在不在」都没查。

这条静默放行路径已在本 change 内修掉(weekly 收到位置参数即 rc=2;未提供
`--digest` 时打印 `WEEKLY_DIGEST_ABSENT_SKIPPED` 声明行),见 tasks §8。

### 更正二:「15 与 5 出现在别处即通过」与实测相反 —— 15 恰恰被判为不可溯源

在 base-ref `799f3f7`(即写下这段 proposal 的那棵树)上,用 `git archive` 展开
干净副本,拿**当时的**校验器跑**当时的**产物:

```
$ python3 scripts/check_report.py reports/weekly/2026-W33.md \
        state/weekly-digest-2026-W33.json --mode weekly
CHECK PASSED                                                    # rc=0(位置参数形态)

$ python3 scripts/check_report.py reports/weekly/2026-W33.md \
        --mode weekly --digest state/weekly-digest-2026-W33.json
CHECK FAILED (11):                                              # rc=1
 - NUMBER_UNTRACEABLE: 数字 0.127 不见于周度聚合文件或当周日报
 - NUMBER_UNTRACEABLE: 数字 0.173 不见于周度聚合文件或当周日报
 - NUMBER_UNTRACEABLE: 数字 0.192 不见于周度聚合文件或当周日报
 - NUMBER_UNTRACEABLE: 数字 0.278 不见于周度聚合文件或当周日报
 - NUMBER_UNTRACEABLE: 数字 07 不见于周度聚合文件或当周日报
 - NUMBER_UNTRACEABLE: 数字 15 不见于周度聚合文件或当周日报
 - NUMBER_UNTRACEABLE: 数字 18 不见于周度聚合文件或当周日报
 - NUMBER_UNTRACEABLE: 数字 2026 不见于周度聚合文件或当周日报
 - NUMBER_UNTRACEABLE: 数字 33.055 不见于周度聚合文件或当周日报
 - NUMBER_UNTRACEABLE: 数字 5.0998 不见于周度聚合文件或当周日报
 - NUMBER_UNTRACEABLE: 数字 60.867 不见于周度聚合文件或当周日报
```

也就是说:**只要真的把聚合文件传进去,旧的词袋检查就把 15 判成了不可溯源**,
与原文断言正好相反。而 **5 从来不在争议范围内**:`ALLOWED_SMALL =
{str(i) for i in range(0, 13)}`,`"5"` 是小整数白名单成员,与它「出现在别处」
无关,任何报告写 5 都不会被拦。

### 核心命题仍然成立

上面两条更正打的是**复现方式与举例数字**,不是结论。`verdict` 在旧校验器里
确实零命中,可独立复跑验证:

```
$ grep -c -i verdict <799f3f7 的 scripts/check_report.py>
0
```

零命中意味着:**结论句整句被改写(而不只是改一个数字)不会被任何检查拦住** ——
数字词袋只看「这个数在不在白名单里」,不看它出现在哪个字段、更不看句子本身。
本 change 要补的强制力因此依然是必要的,优先级不变。

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
