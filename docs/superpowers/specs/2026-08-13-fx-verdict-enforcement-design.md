---
super_coding_change: fx-verdict-enforcement
role: technical-design
canonical_spec: openspec
---

# 结论句强制引用:技术设计

## 1. 问题与现状

仓库的核心原则是「脚本算好、LLM 逐字引用」。前一个 change 用七轮对抗性审查把
「能不能下结论」从 LLM 手里收回脚本,产出 `_verdict` 这类不变量。但执行环节是空的:
`scripts/check_report.py` 全文 `verdict` 零命中,从不校验报告是否真的引用了那些句子。

现有的数字溯源是**无序词袋**:

```python
allowed = numbers_in(digest_text) | ALLOWED_SMALL | ⋃ numbers_in(daily)
for n in sorted(numbers_in(report) - allowed):
    v.append("NUMBER_UNTRACEABLE: ...")
```

只验「这个数在聚合文件的 JSON 文本里出现过」,不问它出现在哪个字段。实测后果:
周报正文写「区间内至少 15 条(3/5 天未采到)」,而配对 digest 里 USD 的
`articles_verdict` 是「区间内至少 26 条(3/6 天未采到、…)」,校验器仍输出
`CHECK PASSED` —— 15 与 5 作为无关数字出现在 digest 别处。

两侧现状不对称(实测 `data/2026-08-12.json` 与 `state/weekly-digest-2026-W33.json`):

| | 结论句字段 | 报告如何得到结论 |
|---|---|---|
| 周报 | 14 条:`events` 五币种各 `articles_verdict` + `official_verdict`;`rates` 四个非美元币种各 `fixings_verdict` | 应逐字引用 digest |
| 日报 | **零条**(`derived.events.<币种>` 只有 count / count_prev / count_delta / count_capped / count_prev_capped / sample_capped / channel_changed_from) | LLM 按 SKILL 模板从布尔拼装 |

## 2. 目标与非目标

**目标**
- 脚本算出的结论句具备强制力:报告改一个字、或整句缺失,校验必须失败
- 两侧用同一套机制,不引入第二处判定
- 结论句之外的散落数字仍有兜底

**非目标**
- 不改结论句的判定逻辑(前一个 change 的成果)
- 日报结论句**只做 `events` 一类**;`rates` 与 `real_rate` 明确不做
- 不做采集层数值精度统一、不做被滤域名落盘(后续 change `fx-collect-precision`)
- 不把报告结构化到「每个数字标注出处字段」的程度——对中文叙事不现实

## 3. 架构:一个核心谓词 + 两份取数说明

核心函数只认一种形状——**`{币种: {字段: 结论句}}` 的两层 dict**:

```python
VERDICT_FIELDS_EVENTS = ("articles_verdict", "official_verdict")
VERDICT_FIELDS_RATES = ("fixings_verdict",)
VERDICT_FIELD_DAILY = ("events_verdict",)

def check_verdicts(report, container, fields, covered, required, label):
    """结论句逐字引用检查。

    container : {币种: {字段: 句子}};非 dict 一律跳过(结构问题由既有检查报告)
    fields    : 要检查的字段名元组(**显式枚举,不按名字模式扫**)
    covered   : 报告已覆盖的币种集合;不在其中者跳过
    required  : 该来源的 schema 是否保证这些字段存在
    label     : 违规信息里的来源前缀,如 "digest.events" / "derived.events"
    """
```

两个调用点只提供**去哪儿取**,判定逻辑只有一份:

```python
# check_daily
check_verdicts(report, snap.get("derived", {}).get("events"),
               VERDICT_FIELD_DAILY, covered_daily, derived_ver >= 2, "derived.events")

# check_weekly
check_verdicts(report, digest.get("events"), VERDICT_FIELDS_EVENTS, covered_weekly,
               True, "digest.events")
check_verdicts(report, digest.get("rates"), VERDICT_FIELDS_RATES, covered_weekly,
               True, "digest.rates")
```

这与 `scripts/collect/events.py` 的 `landed_count_capped` 同构:一个谓词,两个消费者。

### 3.1 为什么字段名要显式枚举

digest 顶层还有 `verdicts`(`{"命中": 0, "未命中": 0, …}` 计数 dict)与
`verdict_details`(list),它们是决策日志复盘统计,**不是结论句**。任何按
`*verdict*` 模式搜集字段的写法都会把它们扫进来,然后在 `x in report` 处
TypeError 或静默跳过。字段名写死成模块级常量元组。

### 3.2 三态与边界

| 取到的值 | 处置 |
|---|---|
| 非空字符串 | `sentence in report` 为假 → `VERDICT_NOT_QUOTED` |
| 空串或纯空白 | `VERDICT_EMPTY` —— 任意报告都"包含"空串,这是最明显的假绿入口 |
| 非字符串非 None(dict / int / list) | `VERDICT_MALFORMED` |
| 缺失或 `None` | `required` 为真 → `VERDICT_ABSENT`;否则跳过并计入"未校验"计数 |

两道让位,避免同一个缺失刷两条违规:

1. **报告未覆盖该币种**(日报 `find_section(secs, c)` 为空 / 周报 `c not in report`)
   → 跳过,已有 `SECTION_MISSING` / `CURRENCY_MISSING`
2. **容器里没有该币种条目** → 跳过。`digest["rates"]` 没有 USD 是合法形态
   (基准货币无定盘价),不是缺字段;只有**币种条目存在**时才要求其字段齐全

### 3.3 存量快照:用 `derive.SCHEMA_VERSION` 当闸门

`scripts/collect/derive.py` 有独立的 `SCHEMA_VERSION`(现值 1,与快照顶层的
`schema_version` 不是同一个),落在 `snapshot["derived"]["schema_version"]`。
本变更把它**升到 2**,校验器据此分流:

- `derived.schema_version >= 2` → `events_verdict` 必须存在,缺失即 `VERDICT_ABSENT`
- `< 2` 或不可解析 → 跳过该项,并在校验器输出中打印一行
  「N 个币种因快照 schema 过旧(=1)未校验结论句」

为什么不用「这个键在不在」判:那会让一个**新代码产出却漏写该字段**的 bug 与存量
快照不可分辨,静默通过。schema_version 让「这份快照本该有」成为可判定的事实。

注意闸门只读不写:校验器不因 schema 过旧而失败,只降级并如实声明降级了几条。
「跳过」与「通过」在输出上必须可区分——这正是本 change 要解决的同型问题。

## 4. 日报结论句:共享拼装器,不共享判定

`weekly_digest.py` 现有 16 处 `caveats.append`(分属 `_verdict` 与
`_fixings_verdict`),拼装形态固定:

```python
head + "(" + "、".join(caveats) + ")"     # 有 caveat
head                                        # 无 caveat
```

**不共享判定。** 周报的输入是跨日统计(`days_collected` / `window_days` /
`in_window`),日报是单日事实(`count` / `count_capped` / `sample_capped` /
`channel_changed_from` / `dropped_malformed`)。定义域不同,强行复用正是前一个
change 第四轮 `_entry_of` 读 `rates` 却被用于 `events` 那类事故的成因。

**共享拼装。** 会漂移的是措辞与连接方式,把它抽成新模块 `scripts/verdicts.py`:

```python
def join_verdict(head, caveats):
    """head 与 caveat 列表的唯一拼装口。caveats 为空时不得拼出空括号。"""
    if not caveats:
        return head
    return "%s(%s)" % (head, "、".join(caveats))
```

`weekly_digest._verdict` / `_fixings_verdict` 与 `derive` 的日报结论句都经此口。
先例:`scripts/fixings.py` 已为 collect 与 weekly_digest 共用。

**缝在拼装处,不在判定处。**

日报结论句的措辞尽量复用周报已打磨过的用词,head 与 caveat 取自单日事实:

- head:`count` 为 `None` → 「当日事件采集失败,有无事件无法判定」;
  `count == 0` → 「当日未采到事件」;否则「当日采到 N 条」
- caveat:`count_capped` → 「已顶到当日采集上限(M 条),实际篇数只多不少」;
  `sample_capped` → 「源返回的原始样本顶到其上限,滤后条数是下界」;
  `channel_changed_from` → 「前一日取自 X 通道,口径不可比,不给变化量」;
  `dropped_malformed` → 「另有 K 条结构不可识别被跳过」

`derived.events.<币种>` 新增 `events_verdict` 后,`derive.EMPTY_EVENTS_DERIVED`
必须同步——`tests/test_derive.py:543` 的
`assertEqual(set(got), set(derive.EMPTY_EVENTS_DERIVED))` 会红。**那是期望行为**,
它就是防漂移哨兵,不得靠放宽断言消除。

## 5. 分层关系

| 层 | 覆盖 | 判据 |
|---|---|---|
| 结论句整句包含 | 脚本给出的 14 + 5 条结论 | 精确子串,改一字即失败 |
| 数字词袋(保留) | 结论句之外的散落数字(汇率、区间、实际利率) | 集合差 |

两层是「与」关系,不互相替代。`--strict-brief` 现有行为不变。

判据取精确子串而非相似度:代价是报告一个标点写错即失败,收益是没有阈值可讨价
还价。本仓库历史表明,任何可讨价还价的判据最终都会被绕过。对行文自由度的约束
是「必须原样引一句」,而非「整段照抄」——报告仍可在句子前后加自己的叙述。

## 6. 历史产物

`reports/weekly/2026-W33.md` 与其配对 digest 已不一致(digest 被重算过),新校验下
必然变红。**这是正确行为**,不是校验过严。处置取**重生成该周报**,不开
「历史产物豁免」开关——豁免机制本身会成为下一个绕过点。

`reports/daily/*.md` 对应的快照 `derived.schema_version` 均为 1,由 §3.3 的闸门
降级跳过,不会大面积变红。

## 7. 测试策略与变异靶点

**先写会红的用例再改代码。** 这是前一个 change 的直接教训:七轮审查里
「修复本身零覆盖」被单列成 Critical **四次**——每一次都是我先改代码、后补测试。
本 change 每个任务都必须先有失败测试。

变异靶点(每条必须被至少一条用例杀掉):

1. 空串放行(`if s:` 写成 `if s is not None:`)
2. `in` 方向写反(`report in sentence`)
3. 只查一侧(`check_daily` 不调 `check_verdicts`)
4. 三类 verdict 只查一类(`fields` 元组少一项)
5. 存量快照当成通过(schema 闸门反向:`>= 2` 写成 `< 2`)
6. 只查第一个币种(循环写成 `next(iter(container))`)
7. 币种未覆盖时仍报 verdict 错(与 `SECTION_MISSING` 重复)
8. `join_verdict` 在无 caveat 时仍拼出空括号
9. 非字符串值(dict/int)未被拦住,直接进 `in` 判断
10. `check_weekly` 在 `digest is None`(未给 `--digest`)时误报 `VERDICT_ABSENT`

变异电池脚本归档至 `docs/superpowers/evidence/`,必须自带**基线自检**(基线不绿
拒跑)与 **STALE 硬失败**(靶点已不匹配源码时非零退出)。这两条同样来自前一个
change 的实际事故:一次超时留下的变异体让「15/15 KILLED」全部为假杀;一次归档
电池在干净副本上只有 26/35,9 个陈旧靶点静默 PATCH-FAIL 却退出 0。

回归基线:554 通过。命令先清 `__pycache__`,再
`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -t .`。
测试不得打真实网络。

## 8. 影响面与风险

**改动文件**
- `scripts/check_report.py`:新增 `check_verdicts` 与四个违规码;既有检查不变
- `scripts/verdicts.py`:新建,只含 `join_verdict`
- `scripts/weekly_digest.py`:两个 `_verdict` 函数改经 `join_verdict`,判定不变
- `scripts/collect/derive.py`:新增 `events_verdict`,`SCHEMA_VERSION` 升 2,
  同步 `EMPTY_EVENTS_DERIVED`
- `skills/fx-daily-report/SKILL.md`、`skills/fx-weekly-report/SKILL.md`:引用规则
- `reports/weekly/2026-W33.md`:重生成

**风险**
- 整句包含使结论句措辞被脚本锁死。缓解:只锁结论句本身,前后可自由叙述
- 结论句变长后可读性下降(真实 W33 的 USD 结论句含 5 条 caveat)。已知代价,
  可读性改善属另一议题
- 日报新增字段后四处要同步(derive / EMPTY_EVENTS_DERIVED / SKILL / 校验器)。
  缓解:键集断言是天然哨兵,漏一处即红
- `VERDICT_ABSENT` 让存量快照的日报全部变红。由 §3.3 的 schema 闸门挡住

零新增依赖(Python 标准库);零 API key 影响。

## 9. Spec Patch

回写两份 delta spec(open 阶段未创建):

- `openspec/changes/fx-verdict-enforcement/specs/fx-daily-report/spec.md`:
  MODIFY `### Requirement: 数字纪律`
- `openspec/changes/fx-verdict-enforcement/specs/fx-weekly-report/spec.md`:
  MODIFY `### Requirement: 周报跨日聚合与数字溯源`

各含结论句逐字引用的 SHALL 条文,与 §3.2 三态、§3.3 schema 闸门、两道让位的
验收场景。
