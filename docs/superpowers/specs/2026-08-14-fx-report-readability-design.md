---
super_coding_change: fx-report-readability
role: technical-design
canonical_spec: openspec
---

# FX 报告可读性改造 · 可实施设计

> 分支 `feature/20260814/fx-report-readability`。本文覆盖任务书全部六项,并在末尾单列不变量论证与非目标。
> **本文引用的每个数字都在本次会话中先跑命令后抄输出**,命令与输出见 §0。

---

## §0 本次会话复跑的基线(先跑后抄)

| 事实 | 命令 | 输出 |
|---|---|---|
| 测试基线 | `python3 -m unittest discover -s tests -t .` | `Ran 715 tests` / `OK` / rc=0 |
| verdict 全量分布 | `python3 scripts/log_decision.py stats --from 2026-01-01 --to 2026-12-31` | `命中 1 / 未命中 1 / 无法判定 33 / 未判定 5` |
| verdict × direction_outcome 交叉 | 读 `state/decision-log.jsonl`(40 条) | `(无法判定,无法判定) 27 / (命中,无法判定) 5 / (未命中,无法判定) 1 / (未命中,未命中) 1 / (命中,命中) 1 / (None,None) 5` |
| 脚本决定性结论采纳率 | 同上 | 决定性 8 条,采纳 **2** 条 |
| 互斥归因 | 同上 | `A1_无方向 21 / A2_无新定盘或等值 6 / B_被否决 6 / C_采纳 2`;USD 的 `watch_direction` 全部为 `None`(8/8) |
| **结论句移进附录仍过闸** | `check_report.py <附录版 08-13> data/2026-08-13.json --brief … --strict-brief` | `CHECK PASSED` rc=0(基线同命令亦 rc=0) |
| **撞串:附录里删掉 THB 那行仍过闸** | 同上,删 `- THB:当日采到 1 条` | `CHECK PASSED` rc=0(08-13 五条结论句去重后只有 4 条) |
| **整块附录包进 HTML 注释仍无 VERDICT 码** | 同上 | 仅 `GAPS_MISMATCH`,rc=1;**零** `VERDICT_NOT_QUOTED` |
| 两份原型过闸 | 日报原型 + 周报原型 | 均 `CHECK PASSED` rc=0 |
| **9 条 `### 主线` 的周报过闸** | 把原型主线五复制成六~九 | `CHECK PASSED` rc=0,`grep -c '^### 主线'` = 9 |
| 正文管道语汇(13 词表,至附录/缺漏节前) | 自写计数脚本 | 原型 08-14 = **0**;生产 08-14 = **33**;生产 08-13 = **18** |
| 原型各节 CJK | `check_report.CJK_RE` | 摘要 132 / 速览 276 / USD 246 / EUR 227 / PHP 209 / THB 208 / BRL 213 / 复盘 176 / 附录A 270 / 附录B 37(上限 330) |

---

## §1 三路诊断的冲突裁定(先裁定,再落设计)

| # | 冲突 | 裁定 | 理由 |
|---|---|---|---|
| C1 | 诊断 1 前半提「管道句/总句 **比例闸门**」,后半自我修正为「管道句一律不进正文」 | **取后者,不做比例闸门** | 比例闸门要先分句再归类,归类只能靠词表或语义判断,两者都不可机械判定;且比例可被「多写几句分析」稀释(`evidence-driven-hardening` 明确点名的坏形态)。改成二元位置规则:管道信息**只允许**出现在附录区。 |
| C2 | 诊断 1 要 `check_verdicts` 收紧成**该币种正文节内**;诊断 3 要**整块附录由脚本生成** | **取诊断 3 方案①**,并把定位判据改为「必须在附录区、且整块逐字」 | ① 诊断 1 的节级方案会把管道句永久钉死在正文,与本次首要目标直接冲突;② 脚本生成整块同时消灭「四币种撞串少写一条照样过」(§0 已实测复现)与转抄错字;③ 更符合最高不变量——LLM 从「逐字转抄」降到**零接触**。 |
| C3 | 诊断 2 的 verdict 五态含 `顺延` | **改为四个终值 + 一个非终值状态**:`命中/未命中/过期未达成/无法判定`,外加 `status=pending`(verdict 为 null) | 把「还在跑」做成一种 verdict,会让计数行里「进行中」与「已裁决」不可分辨——正是诊断 2 自己 R2 要防的形态换个地方复发。 |
| C4 | 诊断 1 要保留 `--verdict` 但只接受脚本值;诊断 2 要物理删除 `set-review` | **取诊断 2,物理删除** | 「只接受脚本算出的值」要求脚本先算一遍再比对,那就没有理由让 LLM 再传一次;多出来的入参本身就是攻击面(值传对、`judgement` 里写反,校验器看不见)。 |
| C5 | 诊断 2 把 `USD_INDEX` 列为**必做项** | **降级为非目标(阶段 3)** | 新 schema 禁止 `direction=null`,USD 的观点改走 `macro_threshold`(`observable = macro.US.CPI 同比`),这条路今天就存在且可机械裁决,不需要 USD 报价。`BASE_CURRENCY_NO_QUOTE` 因此在 add 闸门 G4 就被拒收,运行期应恒为 0 条——比新造一个派生量更省,且不弱。 |
| C6 | 诊断 2 在 resolve 里放 `BASELINE_NOT_REPRODUCIBLE` | **删掉这个枚举码** | R1 的教训是「把观测值抄进条目」;抄了之后 baseline 是条目自己的字段,不存在不可复算。少一个码 = 少一处可静默的分支。 |
| C7 | 诊断 2 让「结构性不可观测」立即判 `无法判定` | **除 `BASE_CURRENCY_NO_QUOTE` 与 `SOURCE_CHANGED` 外,一律先 `pending`,到期才判** | 快照是**可被重采覆盖的当前状态**(R1 实测:`data/2026-08-11.json` 的 EUR primary 由 0.86543 变成 0.86655)。一次采集失败不该永久废掉一条观点。 |
| C8 | 诊断 3 指出 `MAX_THEME_ITEMS=3` 与「3–5 条主线」冲突,而 `### 主线` 写法把闸门整个拆掉 | **取诊断 3 的补法**:在「本周主线」节体内数 `^### 主线`,要求 `3 ≤ n ≤ 5`;并把「本节不得出现列表行」升为硬规则 | §0 实测 9 条 `### 主线` 当前 rc=0。上限从「≤3」变成「3–5 且形态受限」,净效果是**收紧**(9 条从绿变红),不是放宽。 |

---

## §2 日报新模板

**节序不可换(校验器按 `##` 出现序号校验)。共 11 节。**

```
# 外汇日报 DATE
## 执行摘要
## 速览
## 美元(USD)
## 欧元(EUR)
## 菲律宾比索(PHP)
## 泰铢(THB)
## 巴西雷亚尔(BRL)
## 昨日观点复盘
## 附录 A:采集口径与结论句(scripts/appendix.py 生成,勿手改)   ← 正文/附录分界锚点
## 附录 B:出处
## 附录 C:数据缺漏与影响
```

> **为什么「出处」排在附录 A 之后而不是之前**:出处行里带域名与采见时间戳(诊断 1 实测正文内联 11 处),它必须在附录区;而分界锚点必须由**产出方脚本**拥有(见 §4),唯一由脚本产出的块是采集口径块,所以它排第一。与 `sections()` 的兼容性已核对:`find_section(secs,"USD")` 仍首先命中 `## 美元(USD)`,`find_section(secs,"复盘")` 仍首先命中 `## 昨日观点复盘`,`find_section(secs,"数据缺漏")` 命中 `## 附录 C:数据缺漏与影响`——三处均无歧义。

### 逐节规格

**① `## 执行摘要`** ·上限 6 条列表行(嵌套子项一起计数,沿用 `MAX_SUMMARY_ITEMS`),CJK ≤ 180
- 内容:3–5 条,每条 = 一个判断 + 时限 `T+N`;**按跨币种相关性排序**,首条必须是当日最强的那条链
- 允许:币种名、`derived` 数字、`T+N`、`[@键]`
- 禁止:任何条数/采集口径/管道状态;一条塞两个判断;裸方向词(必须是「若 X 则关注 Y」形态,沿用禁令 1)

**② `## 速览`** ·CJK ≤ 300;**表格行不计入任何条数闸门,但计入全部字符级扫描**
- 五币种各一行:`| 币种 | 条件方向(时限) | 核心依据 | 失效条件 |`
- 条件方向必须写成「`<可观测触发>` → 关注`<方向>`(T+N)」,且与当日写进决策日志的 `claim` **同源同字**
- 核心依据 ≤2 项,每项带 `[@键]`
- 失效条件必须是价格/指标可观测量
- 禁止:置信度/证据强度列(阶段 3 才加,见 §8);任何管道语汇
- (阶段 3 追加第五列 `置信度(脚本判级)`,整列逐字抄 `derived.confidence.<币种>.verdict`,LLM 不得自拟)

**③–⑦ 五个币种节 `## <中文名>(<币种码>)`** ·CJK ≤ 330(`MAX_SECTION_CJK` 不变)

两种模式,**由脚本决定,不由 LLM 决定**——derive 落 `derived.body_plan.<币种>`:

- `mode = "minimal"`(当日事件与增量数据双缺:该币种 `events.count` 为 null 或 0,且无 `is_new_release=true` 的本地宏观条目,且无新定盘):
  该节正文必须**逐字等于**(strip 后全等,不是包含)`body_plan.<币种>.line`,例如
  `USD:本日无可用增量,不更新判断;口径见附录 A,缺漏见附录 C。`
  三段式/四环式一律不得出现。这条把「2026-08-10 那种四个币种节 100% 管道句」从「程度问题」变成**结构上不可能**。
- `mode = "full"`:四环链条,四个粗体行首**齐全且顺序固定**:

| 环 | 内容要求 | 允许词汇 | 禁止词汇 | 建议预算(CJK) |
|---|---|---|---|---|
| `**驱动**` | 有当日可署名事件 → 写事件 + `[@键]`;无事件 → 写**当前主导变量**(结构项,如「本日主导变量是利差结构本身:实际利率 -1.613 为五经济体最低」)。**不写否定句** | `derived` 数字、`[@键]`、经济体名、指标中文名 | 「无事件/未采到/采集失败/无公告/快照无…条目」 | ≤80 |
| `**传导**` | 必须出现「A → B → 汇率」三段;B 只能取 利差 / 风险溢价 / 资金流 / 政策空间 之一 | 同上 + 机制名词 | 同上 | ≤80 |
| `**是否已反映**` | 必须引至少一个价格证据(参考价 vs 区间边界 / 实际利率 / 双源偏差),回答「这层在价里没有」 | 同上 | 同上 | ≤80 |
| `**分歧与判断**` | 第一句点分歧点;第二句「若 X(可观测)则关注 Y(T+N);Z 即本判断失效」 | 同上 + `T+N` | 同上 | ≤90 |

> 环级预算**只进 SKILL,不进校验器**。四个标签的存在与顺序已由校验器保证(`SECTION_RING_MISSING`),字数在节级已有闸门;再加四个字数闸门只增加误报面,不增加防线。

全节禁止:结论句原文、条数、通道、采集上限、原始样本、缺漏、「不可得」、`seendate` 原文、URL、快照字段名、7 位以上小数。

**⑧ `## 昨日观点复盘`** ·CJK ≤ 220
- 每条待复盘观点一行,该行必须**逐字包含**脚本生成的复盘句(阶段 1 = `review.py` 的方向核对句;阶段 2 = `review.sentence`)
- 允许:引用句原文 + 一句 LLM 补充说明(交代分歧点是否被市场检验)
- **禁止**:LLM 自撰的结论词(`命中/未命中/无法判定/过期未达成/顺延`)——结论词只能来自被引用的整句(`REVIEW_WORD_IN_BODY`)
- 该标题必须**早于**任何其他含「复盘」的标题(`find_section` 取首个匹配)

**⑨ `## 附录 A:…(scripts/appendix.py 生成,勿手改)`** ·无字数上限
- **整块由脚本生成,LLM 一个字符都不写**。块内容:五币种 `events_verdict` 逐字整句、采见日口径、通道口径、公告存量背景说明、双源偏差、(阶段 3)置信度判级输入
- 校验器要求报告**逐字包含该整块**(整块比对,不是逐句包含)

**⑩ `## 附录 B:出处`** ·无字数上限
- `- [@键] 标题 — domain/发布方,发布 <时间戳>`
- 键格式写死 `[@<币种码><小写字母>]` 或 `[@RR-<经济体>]`,**键内不得含数字**(诊断 3 实测:`[@S15]` 会被 `NUMBER_UNTRACEABLE` 当场拦下)

**⑪ `## 附录 C:数据缺漏与影响`**
- 每条 `[source/scope] reason — 影响:<哪一条判断因此降档>`
- 必须是全文**唯一**含「数据缺漏」的标题;快照 `gaps` 为空时正文恰为一个字「无」(沿用 `GAPS_MISMATCH`)

---

## §3 周报新模板

```
# 外汇周报 WEEK
> 覆盖日报:N 份(…);覆盖区间 … 至 …;缺失日期:…
> 复盘图例:…(本行不含数字)
> 全部观测口径、结论句逐字引用与缺漏见附录 A、附录 B

## 本周主线
### 主线一:<标题>(影响 <币种列表>)   … ### 主线五
## 各币种一周落点
## 复盘汇总
## 下周关注
## 附录 A:结论句逐字引用与观测口径(scripts/appendix.py 生成,勿手改)   ← 锚点
## 附录 B:缺漏汇总
```

现有 `WEEKLY_SECTIONS = ["本周主线","各币种","复盘汇总","下周关注","缺漏汇总"]` **无需改动**:`## 各币种一周落点` 含「各币种」,`## 附录 B:缺漏汇总` 含「缺漏汇总」。

| 节 | 内容要求 | 允许 | 禁止 | 上限 |
|---|---|---|---|---|
| `## 本周主线` | 3–5 个 `### 主线N:标题(影响 <币种>)`,每个固定五段式:**宏观背景 / 传导机制 / 标的影响 / 证据强度 / 证伪条件(T+N)**。至少一条必须是**跨币种相关性主线** | digest 数字、日报数字、`T+N` | **本节不得出现任何列表行**(`THEME_SHAPE`);管道语汇;把 verdict 里的「至少/只多不少/无法判定」改写成确定说法 | 每主线 CJK ≤ 260 |
| `## 各币种一周落点` | 一张表替代五段散文:`\| 币种 \| 主线归属 \| 周内价格落点 \| 下周判断(时限) \| 失效条件 \|`。USD 行写「基准货币,聚合文件无自身汇率读数」 | digest 逐字数字 | 管道语汇;散文段落 | CJK ≤ 300 |
| `## 复盘汇总` | ① 计数行**逐字引用** digest 的 `review_summary_sentence`(脚本生成,见 §6);② 明细按 `(verdict, 日期)` 归并;③ 一句**结构性读法**:这周为什么是这个分布、下周用什么手段收敛 | 引用句原文 + 结构性读法 | LLM 自撰结论词;把 v1 与 v2 两块计数相加 | CJK ≤ 240 |
| `## 下周关注` | ≤5 条,每条 `日期 + 事件 + 挂靠哪条主线 + 检验主线的哪一环`;只准摘年历里实际存在的条目 | 年历原文 | 凭记忆补条目 | 5 条 |
| `## 附录 A` | **整块脚本生成**:14 条结论句逐字(5×`articles_verdict` + 5×`official_verdict` + 4×`fixings_verdict`,USD 在 rates 容器无条目写明理由)+ 口径差异说明 | — | LLM 手写 | — |
| `## 附录 B:缺漏汇总` | `digest.gaps_by_source` 每个键都要出现(沿用 `GAP_OMITTED`) | — | — | — |

**第 1 步素材阅读顺序同步改**:从「逐份读日报全文」改成「先读 digest 与五份日报的**速览表**,再聚类」——主线聚类的输入应该是各日的判断,不是各日的全文。

---

## §4 正文 / 附录的机器分界

### 4.1 锚点

```python
# scripts/appendix.py —— 唯一事实源(产出方拥有)
APPENDIX_ANCHOR_DAILY  = "## 附录 A:采集口径与结论句(scripts/appendix.py 生成,勿手改)"
APPENDIX_ANCHOR_WEEKLY = "## 附录 A:结论句逐字引用与观测口径(scripts/appendix.py 生成,勿手改)"
```

`scripts/check_report.py` **只许 import,不许再写一份字面量**——与既有 `REVIEW_BLOCK_HEADING` 同规格(`scripts/review.py:16` 拥有、`check_report.py:19-21` 导入,两处各写一遍必然漂移,漂移后豁免要么整段失效、要么整段过宽,两种都静默)。

**分界定义**:锚点行是脚本生成块的**第一行**。
- `正文区 body = 文件开头 … 锚点行起始位置(不含)`
- `附录区 tail = 锚点行 … 文件结尾`

### 4.2 为什么绕不过去

| 绕过手法 | 挡它的规则 |
|---|---|
| **改锚点一个字**(全角冒号→半角、删掉「勿手改」) | 锚点是脚本生成块的第一行,块要求**整块逐字包含**。改一个字符 → `BODY_ANCHOR_MISSING` **与** `APPENDIX_BLOCK_NOT_QUOTED` 两码同出。伪造成本 = 伪造整块。 |
| **把锚点上移**(放到执行摘要之后,让币种节全部落进附录区) | `BODY_ANCHOR_MISPLACED`:锚点的 `##` 序号必须**严格大于**全部必需正文节(执行摘要 / 速览 / 五币种 / 复盘)的序号。 |
| **写两个锚点**,把管道段夹在中间 | 三态的 ≥2 支:`BODY_ANCHOR_DUPLICATED` **且整份文件按正文照扫**(失败关闭,一行都不豁免)——与 `split_brief_review_block` 的 ≥2 支同一处理。 |
| **不写锚点** | 三态的 0 支:`BODY_ANCHOR_MISSING` **且整份文件按正文照扫**;同时 `APPENDIX_BLOCK_NOT_QUOTED` 必红。 |
| **把附录包进 HTML 注释**(§0 实测当前只报 `GAPS_MISMATCH`,零 VERDICT 码) | 新码 `REPORT_HTML_COMMENT`:报告任何位置出现 `<!--` 即违规。 |
| **锚点后再开一个 `## 正文续`** | 附录区内不允许出现锚点之外的、不属于生成块也不属于附录 B/C 的 `##` 节:`APPENDIX_UNKNOWN_SECTION`。 |

### 4.3 三态与「跳过必须打印声明」

| 锚点出现次数 | 行为 | 输出 |
|---|---|---|
| 0 | 全文当正文照扫(失败关闭) | `BODY_ANCHOR_MISSING`(违规,rc=1) |
| 1 | 正常切分 | 无 |
| ≥2 | 全文当正文照扫(失败关闭) | `BODY_ANCHOR_DUPLICATED`(违规,rc=1) |

**唯一的合法跳过**:存量快照没有 `derived.body_plan`(阶段 1 之前采的),此时 minimal 模式检查无法执行。必须走 `notes` 打印
`BODY_PLAN_ABSENT_SKIPPED: 快照无 derived.body_plan(schema_version=%r),本次未校验币种节的 minimal 模式`
——rc 不变,但「跳过」与「通过」在输出上必须可区分,与 `VERDICT_SKIPPED_NO_DERIVED` / `BRIEF_REVIEW_BLOCK_SKIPPED` 同一原则。

---

## §5 `BODY_PLUMBING_LANGUAGE` 完整规格

### 5.1 扫哪一段

正文区 `body` 的**全部字符**:含一级标题、引用行(`>`)、列表行、**表格行与表格单元格**、粗体标签内文本。
不做任何形态豁免。理由:诊断 3 已实测「表格行不进 `list_items` 计数」这一盲区(整张表塞进执行摘要仍 PASS),同类盲区不得复发。

### 5.2 词表怎么定(两层,都不是手写清单)

**P1 —— 运行时导出层(主力)**
不 import 产出端的私有常量(会耦合),而是取**本次运行的事实**:从快照 `derived.events.<币种>.events_verdict` /(周报)digest 的 `articles_verdict`、`official_verdict`、`fixings_verdict` 取出全部结论句,按全角顿号 `、` 与 ASCII 括号 `()` 切成 caveat 片段,得到当次运行的 P1 集合(整句 + 每个片段,长度 ≥6 字符的才入集,避免噪声)。
- 命中 → `BODY_VERDICT_LEAKED`
- **性质**:产出端改措辞,P1 自动跟着改,**结构上不会漂**。这一层守的是「复制粘贴脚本产物进正文」,它是逐字的、完备的。

**P2 —— 冻结字面层(残差网)**
写死在 `check_report.py` 模块级常量里,改它必须同时改测试期望值(与 `DISPOSITION_QUOTE` / `DISPOSITION_SCRIPT_BUG` 同规格):

```
PLUMBING_TERMS = ("无明确驱动","采集失败","快照","无公告","官方公告条目","采集上限",
                  "原始样本","通道","条目","不可得","缺漏","口径不可比","下界")   # 13 个
SNAPSHOT_FIELD_NAMES = ("primary","prev_primary","derived","rates 容器","schema","null")
PLUMBING_PATTERNS = (
    ("SEENDATE",  r"\d{8}T\d{6}Z"),                                    # 机读采见时间戳
    ("ENGDATE",   r"(Mon|Tue|Wed|Thu|Fri|Sat|Sun),\s*\d{1,2}\s+(Jan|Feb|…|Dec)"),
    ("RAWPREC",   r"\d+\.\d{7,}"),                                     # 7 位以上小数
)
```
命中 → `BODY_PLUMBING_LANGUAGE`(词元)/ `BODY_MACHINE_ARTIFACT`(正则)。
13 个词的来源可追:它就是任务书给定、并在 §0 被独立复算过的统计词表(生产 08-14=33、08-13=18、原型=0)。

**P3 —— 陈旧复述(与词表正交,防「四天写四遍 -0.499」)**
derive 落 `derived.changed_since_prev`(今天真的变了的数的集合,脚本算)。
该币种的集合为空时,该币种节禁止出现**断言变化**的动词:`升至 / 降至 / 回落 / 走高 / 收窄 / 扩大 / 抬到 / 上行 / 下行`。
命中 → `BODY_STALE_REPEAT`。(「未变」「持平于」不在表内,允许——08-14 原型「较前一日未变」是正确写法。)

### 5.3 三态

规则本身的三态,判据是**结论句容器可用性**:

| 状态 | 条件 | 行为 |
|---|---|---|
| 全查 | 快照 `derived.schema_version >= 2` 且 `derived.events` 是 dict | P1+P2+P3 全跑 |
| 降级 | 快照无 derived / schema 过旧 | **P1 跳过、P2+P3 照跑**,并打印 `BODY_PLUMBING_P1_SKIPPED: 快照无结论句容器,本次未做脚本产物泄漏检查(P2/P3 已执行)` |
| 失败关闭 | 锚点计数 ≠ 1 | 全文按正文扫,规则**不因此放宽** |

### 5.4 错误信息格式(可操作是硬要求)

```
BODY_PLUMBING_LANGUAGE: 正文出现管道语汇「采集失败」;位置 第 27 行 · 节「泰铢(THB)」;
原文:**驱动**:当日事件仅一条,内容为 AI 需求提振泰国数字化景气…(截断至 80 字);处置:…
BODY_VERDICT_LEAKED: 正文出现脚本结论句片段「源返回的原始样本顶到其上限」;位置 第 12 行 · 节「美元(USD)」;
原文:… ;处置:…
```

必须给四件事:①命中的是哪一条(P1 片段原文 / P2 词元 / 正则名)②行号 + 节名(锚点前无节时写「节:文首」)③整行原文截断至 80 字符 ④处置。

新增第三条处置常量,逐码钉死,进 `CheckerPrintsItsOwnDispositionTest`:
```
DISPOSITION_MOVE_TO_APPENDIX = ("处置:把这句话从正文删去;同样的事实已在附录 A 的脚本生成块里,"
                                "不要在正文复述;这一条改报告即可,不要动脚本")
```

### 5.5 这条规则守得住什么、守不住什么(不夸大)

**守得住**
- P1:结论句整句或其 caveat 片段被复制进正文。逐字、运行时导出、随产出端自动跟随,**不会因为产出端改措辞而失效**。
- P2:13 个既有词元、6 个快照字段名、机读时间戳、英文 RFC 日期、7 位以上小数。有界枚举,每一项都可以有一条正向用例。
- P3:`changed_since_prev` 为空时的变化断言。

**守不住(明说)**
- **换个说法**。「本日未取得任何可署名的新增表述」不含任何 P1/P2 词元,照样过闸。词表是**无序词袋**,不是语义空间;本仓库已经在「verdict 白名单是无序词袋」上栽过一次(见 MEMORY `fx-checker-verdict-gap`)。
- **把管道事实包装成分析**。「比索缺乏新增信息,定价回到结构项」——这句其实是**正确**的写法,规则不该拦;而它的坏兄弟(用同样句式掩盖「我们没采到」)规则也拦不住。
- **相邻否定**(A 类):在被引用的整句旁边加一句把它否掉。已被本仓库封为文档化边界(`check_report.py:84-95`),本设计不为它再加哨兵。

**真正压住「换个说法」的不是词表,是三条位置/结构规则**(它们完全不依赖词汇):
1. **minimal 模式**:脚本决定某币种当日只能有一行,且该行必须逐字等于脚本生成的句子——「写三段没数据」从可能变成不可能;
2. **附录 A 整块脚本生成 + 正文禁止出现其中任何整句**——LLM 连转抄的机会都没有;
3. **四环标签齐全且顺序固定**,`是否已反映` 环必须至少引用一个 `derived` 数字——写不出数就只能进 minimal 模式。

词表是这三条之外的**残差网**。它只声称拦下「复制粘贴管道句」,不声称拦下改写。

---

## §6 观点记录 schema v2 与 verdict 的脚本判定

### 6.1 新旧共存(历史 40 条一个字节都不动)

- **v1 = 顶层无 `schema` 键**;**v2 = `"schema": 2`。**
- `scripts/resolve.py` **只处理 `schema == 2`**;遇 v1 跳过并在 stdout 单独计数打印(`跳过 v1 条目 N 条`)。
- **任何写回 v1 条目的代码路径,在 review 中直接判 Critical。** 迁移是**只读**的:不存在迁移脚本。
- 切换日写一份 `state/decision-log-migration.md`(**不进 jsonl**),记明:切换日期、v1 冻结计数逐字(`命中 1 / 未命中 1 / 无法判定 33 / 未判定 5`)、「v1 不再复盘」的决定、v2 第一条的日期。
- **08-14 那 5 条未判定条目永久保持 `未判定`**(选项三)。用新脚本补判 = 用新口径伪造历史(它们从没有过 `baseline`);删除重录 = 改写审计记录。
- 计数桶扩为六栏,且 **v1 / v2 分栏呈现、禁止相加**:
  `v1(LLM 判定,已冻结):命中 / 未命中 / 无法判定 / 未判定`
  `v2(脚本判定):命中 / 未命中 / 过期未达成 / 无法判定 / 进行中`
- **哨兵测试**:扩桶后对现存 40 条 v1 数据跑 `stats`,首行必须**逐字**等于 `命中 1 / 未命中 1 / 无法判定 33 / 未判定 5`。

### 6.2 v2 条目字段

**① LLM 可写(`add` 经 stdin 传入)**

| 字段 | 类型 | 语义 |
|---|---|---|
| `date` | `YYYY-MM-DD` | 同现行 |
| `currency` | ∈ CURRENCIES | 同现行 |
| `claim.kind` | `fx_direction` \| `macro_threshold` | 必填,**无第三态、无 null** |
| `claim.observable` | 脚本可解析路径,如 `rates.EUR.primary` / `macro.US.CPI 同比` | 必填 |
| `claim.direction` | `up` \| `down` | **必填,禁止 null**——直接消灭现行 21/35 的 A1 归因 |
| `claim.baseline` | number | 必填,逐字抄自当日快照 |
| `claim.baseline_ref` | `ref_date` 或 `period` | 必填 |
| `claim.threshold` | number \| null | `macro_threshold` 时必填,且**必须等于该序列当日 `value`**;`fx_direction` 时必须为显式 `null` |
| `claim.horizon_fixings` | int 1..10 | 时限,**以定盘/新发布次数计,不是自然日** |
| `claim.mechanism` | `real_rate` \| `rate_differential` \| `policy_path` \| `risk_premium` | 必填,显式命名传导变量 |
| `claim.implied_fx_direction` | `up` \| `down` \| null | `macro_threshold` 时必填(USD 填 null);`fx_direction` 时必须为 null |
| `reason` | str | LLM 唯一的散文字段 |

`trigger` 与 `watch_direction` 在 v2 中**不存在**(被 `claim` 取代);`scenario` 并入 `reason`。

**② 脚本在 `add` 时补齐**:`claim.opened_ref`(建仓时该 observable 的 `ref_date`/`period`)、`claim.deadline_note`。

**③ 脚本在 `resolve` 时回填(LLM 永不可写)**

| 字段 | 取值 |
|---|---|
| `review.status` | `pending` \| `resolved` \| `expired` \| `unobservable` |
| `review.verdict` | `命中` \| `未命中` \| `过期未达成` \| `无法判定` \| null(**null 只表示尚未裁决**) |
| `review.resolved_on` / `observed` / `observed_ref` | 裁决所用快照日期 / 观测值 / 观测值的定盘日或期号 |
| `review.evidence_path` | `data/2026-08-17.json#rates.EUR.primary` |
| `review.seen_refs` | 已计入的 ref/period 列表(保证 `fixings_seen` 幂等) |
| `review.unobservable_code` | `BASE_CURRENCY_NO_QUOTE` \| `SNAPSHOT_MISSING_AT_DEADLINE` \| `FIELD_NULL_AT_DEADLINE` \| `SOURCE_CHANGED` |
| `review.sentence` | **脚本生成的复盘结论句**,经 `scripts/verdicts.join_verdict` 拼装,供报告逐字引用 |

### 6.3 `add` 侧写入闸门(任一不过 → **rc=2 拒收整批**,不是跳过单条)

| 闸门 | 判据 |
|---|---|
| G1 | `claim.direction ∈ {up, down}` |
| G2 | `claim.baseline` 与当日快照对应路径的值**逐字节相等**(LLM 仍禁止计算,这只是抄写校验) |
| G3 | **非同义反复**:当日快照里该 claim 尚未满足。`macro_threshold` 要求 `not crossed(当日值, threshold, direction)`;`fx_direction` 天然满足 |
| G3b | `threshold` 必须等于该序列**当日 `value`**(禁止用 `prev`)。这直接堵住 08-12 那条锚错期的缺陷(`.macro[0].value=3.531` / `.prev=4.249`,门槛被抬高 0.718 个百分点,全周唯一一次有效方向判断因此做废) |
| G4 | `claim.observable` 能在当日快照里解析出**有限数值**(bool / NaN / Inf 视为不可解析,与 `review.rate_of` 同门)。`rates.USD.*` 因此在这里被拒 |
| G5 | `claim.horizon_fixings ∈ 1..10` |
| G6 | `reason` 不含 `命中/未命中/无法判定/过期未达成/顺延`(`REVIEW_WORD_IN_REASON`) |
| G7 | **机制符号一致性**(固定符号表,`scripts/verdicts.py` 内):`macro_threshold` 且 `implied_fx_direction` 非 null 时,`(指标符号 × direction) → 本币方向 → USD/XXX 方向` 必须与 `implied_fx_direction` 相等。符号表:`INDICATOR_SIGN = {"CPI 同比": -1, "政策利率": +1}`(对实际利率的符号),本币方向 = 符号 × direction,USD/XXX = 反号 |
| G7b | `fx_direction` 的 `mechanism` 必须指向当日快照里存在有限数值的 derived 量(如 `derived.real_rate.<经济体>`) |

> G7 在**写入时**就抓住 2026-08-12 那条 BRL 反向 trigger:机制写「实际利率最高构成套息支撑」,而 trigger 写「CPI 低于上期 → USD/BRL 上行」。CPI↓ → 实际利率↑ → 雷亚尔↑ → USD/BRL **↓**,与填的 `up` 冲突 → rc=2。

### 6.4 verdict 由哪个函数算

**唯一产地:`scripts/verdicts.py::resolve_claim(claim, obs, fixings_seen)` —— 纯函数、零 IO、可穷举测试。**
`scripts/resolve.py` 只负责:读快照 → 调纯函数 → 写日志 → 打印。入口 `python3 scripts/resolve.py --date DATE`,**参数只有 `--date` / `--root`,没有任何可让 LLM 表达结论的入参**。

输入:
- `claim`:条目里冻结的 claim(baseline 已在条目内,无需回查历史快照)
- `obs`:从**当日**快照按 `claim.observable` 逐层 isinstance 下钻得到的 `{value, ref, is_new_release, source_changed_from, suspect, absent_by_schema}`
- `fixings_seen`:已计入的新观测次数(由 `review.seen_refs` 去重后算出)

判定顺序(每一步都可复算):

```
0. 快照缺失
     → 未到期: pending
     → 到期  : unobservable / 无法判定 + SNAPSHOT_MISSING_AT_DEADLINE
1. obs.absent_by_schema(rates 容器无该币种)
     → unobservable / 无法判定 + BASE_CURRENCY_NO_QUOTE   【立即判;G4 之后应恒为 0 条】
2. obs.source_changed_from 非 null,或 rates.<c>.suspect 为 true
     → unobservable / 无法判定 + SOURCE_CHANGED           【立即判:口径已污染,再等无益】
3. obs.value 为 None
     → 未到期: pending;到期: unobservable / 无法判定 + FIELD_NULL_AT_DEADLINE
4. 时间是否前进(只认定盘/期号推进,不认自然日)
     fx_direction    : obs.ref not in seen_refs 才 +1
     macro_threshold : obs.is_new_release 且 obs.ref not in seen_refs 才 +1
     无新观测 → 未到期: pending;到期: expired / 过期未达成
5. 裁决(**产生 命中/未命中 的唯一位置**)
     fx_direction    : obs.value == baseline → 不决定性,回到步骤 4 的到期判断
                       moved = up if obs.value > baseline else down
                       命中 iff moved == claim.direction,否则 未命中
     macro_threshold : crossed = (obs.value > threshold) if direction=="up"
                                 else (obs.value < threshold)
                       命中 iff crossed,否则 未命中
```

**四种取值各在什么条件下产生:**

| verdict | 产生条件 |
|---|---|
| `命中` | 到了一次**新的**定盘/新发布,观测方向(或阈值越过)与 `claim.direction` 一致 |
| `未命中` | 到了一次**新的**定盘/新发布,方向(或越过与否)与 `claim.direction` 相反 |
| `过期未达成` | `fixings_seen ≥ horizon_fixings`,期间每一次新观测都不决定性(价格恰等 / 阈值未越过且非新发布)。**这是有信息的结果**:市场在你给的时限内没动到你说的方向 |
| `无法判定` | 且仅且 status = `unobservable`,必带四个枚举码之一,且**必须同时进当日「数据缺漏」节** |

`pending` 不是 verdict,是 `status`,`verdict` 保持 null。

`review.sentence` 由 `verdicts.join_verdict` 拼(与 `events_verdict` 完全同一条通道):
```
head    = "2026-08-13 EUR 观点复盘:命中"
caveats = ["基准 0.867(2026-08-13)", "观测 0.869(2026-08-17)",
           "证据 data/2026-08-17.json#rates.EUR.primary"]
→ 「2026-08-13 EUR 观点复盘:命中(基准 0.867(2026-08-13)、观测 0.869(2026-08-17)、证据 data/2026-08-17.json#rates.EUR.primary)」
```
`无法判定` 时 caveats 追加 `不可判定原因 SOURCE_CHANGED`。

### 6.5 「无法判定」的诚实下界与防洗数条款

- 滚动 4 周窗口内,`无法判定` 占**已到期条目**(`resolved + expired + unobservable`,**不含 pending**)的比例 **≤ 10%**,且每条必带枚举码;
- 超过 10% **不许调口径**,必须当作采集缺陷进日报缺漏节与周报缺漏汇总;
- 分母固定为「已到期条目」,**禁止把 pending 塞进分母稀释**——测试断言分母表达式只含这三个状态;
- `horizon_fixings` 硬上限 10,禁止用无限顺延把不利结果养成永久 pending;
- 周报复盘汇总必须同时打印五个数(v2)+ `无法判定` 的枚举码明细,少打任何一个即 `REVIEW_TOKEN_MISSING`;
- **明确不算 `无法判定`**:「到期仍无新定盘 / 未越过阈值」= `过期未达成`,单列第三栏。把它并进 `无法判定` 是把「没动」洗成「看不见」;并进 `未命中` 是把「没到期」洗成「错了」。**两种合并都禁止。**

### 6.6 LLM 在这套流程里还剩什么职责

1. **提出观点的内容**:选哪个 `observable`、什么 `direction`、什么 `horizon_fixings`、什么 `mechanism`。这是「提出假设」,不是「下结论」。
2. **写 `reason`**(为什么这么看),不得出现任何结论词。
3. **在报告正文逐字引用**脚本给的 `review.sentence`(与阶段 3 的 `confidence.verdict`),并在旁边写一句不含结论词的补充说明。
4. 在要点表给条目打 `〔反向信号〕` 定性标记(**计数与判级仍由脚本做**,LLM 禁止报出这个数)。

**不再有的职责**:判断触发是否发生、写 verdict、数任何数、转抄管道结论句(附录 A 由脚本生成)。

---

## §7 必须被测试杀掉的变异清单(15 条)

判定一律**只看返回码与 stdout 逐字断言**,禁止 `grep "FAILED"`,禁止接管道判成败。

| # | 变异 | 若无对策的后果 | 杀它的断言(行为级) |
|---|---|---|---|
| **M1** | 把附录 A 锚点行整体挪到「## 执行摘要」之后 | 正文只剩摘要,五个币种节全部落进附录区,管道语汇一条不扫 | 生产命令行跑改造后报告 → stdout 含 `BODY_ANCHOR_MISPLACED` 且 rc=1;断言判据是「锚点 `##` 序号 > 全部必需正文节序号」 |
| **M2** | 写**两行**锚点,把管道段夹在两者之间 | 挑一个是静默决策,被查方拿走选择权 | 断言**两件事**:①出 `BODY_ANCHOR_DUPLICATED` rc=1;②原本在「第二锚点之后」的那句管道话**仍被** `BODY_PLUMBING_LANGUAGE` 报出来。只断言出码,会让「计数对了但豁免范围仍被拿走」存活 |
| **M3** | 锚点被改一个字符(全角冒号→半角 / 删「勿手改」) | 分界失效,静默 | ①源码扫描:`check_report.py` 内**不得**出现锚点字面量的第二份拷贝(与 `REVIEW_BLOCK_HEADING` 同规格);②改一字符 → `BODY_ANCHOR_MISSING` **与** `APPENDIX_BLOCK_NOT_QUOTED` 两码**同出** |
| **M4** | 附录 A 块被手改一个字符 / **少写一行**(撞串共用) | §0 实测:08-13 五条结论句去重后仅 4 条,删掉 THB 那行**当前 rc=0** | 用这条**已被证实存活的真绕过**做用例:同一份输入在新规则下必须 rc=1,码为 `APPENDIX_BLOCK_NOT_QUOTED`;判据是「整块逐字」,不是「逐句包含」 |
| **M5** | 整块附录塞进 HTML 注释 | §0 实测:当前只报 `GAPS_MISMATCH`,**零** VERDICT 码——结论句写在不渲染的注释里也算引用 | `REPORT_HTML_COMMENT`:报告任何位置出现 `<!--` 即 rc=1 |
| **M6** | P2 冻结词表被清空 / 删掉其中一个词 | 词表整体或局部静默失效 | ①逐元素 `assertEqual`(与 `DISPOSITION_*` 同规格);②**每个词各有一条正向用例**——一份只含该词的正文必须出码。只断言「表非空」会让删一个词存活 |
| **M7** | P1 由运行时导出改成硬编码清单 | 产出端一改措辞,泄漏检查静默失效 | 构造一份**结论句措辞与 P2 完全不重叠**的 fixture(如 `events_verdict = "本日入库 3 篇"`),把该句抄进正文 → 必须出 `BODY_VERDICT_LEAKED`。硬编码实现会静默放行 |
| **M8** | 扫描范围被缩成「只扫币种节」 | 表格与摘要成为盲区(诊断 3 已实测表格行不进 `list_items` 计数) | 把同一句管道话分别放进 `## 执行摘要` 与 `## 速览` 的表格单元格 → **两条**违规都必须出现 |
| **M9** | `log_decision.py` 重新长出 `set-review` / `--verdict` / 任何能表达结论的入参 | verdict 退回由 LLM 决定,整套改造归零 | ①负向 CLI:`set-review …` 必须 rc=2 且 stderr 含「该子命令已删除」;②**参数表冻结**:枚举全部子命令与选项名(读 `parser._actions`,**不是 `--help`**,以覆盖 `argparse.SUPPRESS` 隐藏项)逐字 `assertEqual`;③加**位置参数**与 `parse_known_args` 的禁用断言(`build_parser` docstring 里记着这四条真绕过) |
| **M10** | verdict 在 `resolve_claim` 之外的地方被赋值 | 出现第二个判定源,与现行「两个结论字段打架」同型复发 | AST 断言:全仓库 `review["verdict"]` 的赋值点唯一,且值只能来自 `verdicts.resolve_claim` 的返回;第二处赋值即红 |
| **M11** | `resolve` 改写历史 v1 条目 | 静默翻面已归档判定(R1 实测:重算 35 条有 1 条与归档值不符,根因是快照被重采) | ①跑 `resolve --date <任意日>` 后,断言 jsonl 中**无 `schema` 键的那 40 条逐字节不变**(含字段顺序);②stdout 必须打印「跳过 v1 条目 40 条」;③哨兵:`stats` 首行逐字等于 `命中 1 / 未命中 1 / 无法判定 33 / 未判定 5` |
| **M12** | 计数桶把 `过期未达成` / `pending` 静默并进「未判定」 | 「还在跑」与「压根没复盘」混成一栏,读者看不清的老毛病换地方复发 | 构造含两种新状态的 v2 条目,断言 `stats` 与 `weekly_digest` 各自输出 **v1 四栏 + v2 五栏、两块分开**;断言输出中**不存在**两块相加的那个数 |
| **M13** | **判定类**结论句被搬进附录(本次改造的自伤形态) | 「把管道语汇搬出正文」顺手把脚本结论也搬出去,而没有任何检查会红 | 把 `review.sentence` 从复盘节剪出、放到锚点之后 → 必须 rc=1,码 `REVIEW_VERDICT_NOT_QUOTED_IN_BODY`。**这条与 M4 方向相反,两条必须同时存在**,否则「位置无关」会从另一头回来 |
| **M14** | 「顺延」被当成 verdict 写进报告;或 `horizon` 无限顺延;或把 pending 塞进分母稀释 | 不利结果被养到永远 pending,`无法判定` 占比靠改口径变好看 | ①`horizon_fixings = 11` 的 add 负向用例 rc=2;②正文出现「顺延」即 `REVIEW_WORD_IN_BODY`;③断言占比分母表达式**只含** `resolved + expired + unobservable`;④占比 >10% 时 `resolve --report` 非零码 |
| **M15** | minimal 模式被绕过(某币种无增量却写了四环) | 2026-08-10 那种「三个标题承诺,三段交付『我们没采到』」原样复活 | 用 `data/2026-08-10.json`(四币种双缺)做 fixture:`body_plan.mode == "minimal"` 时该节正文必须**逐字等于**生成行(strip 后全等),多写一个字即 `BODY_SECTION_NOT_MINIMAL` rc=1 |

---

## §8 非目标(本次不做什么)

本仓库「七轮审查未收敛」的教训是**先写修复、后补靶点**。下列各项**明确不在本次范围**,写进 proposal 的 Non-Goals,评审时任何一项被顺手带进来,直接判范围失控。

1. **不做 `derived.confidence` 判级 / `USD_INDEX` / `changed_since_prev` 之外的新派生量**(阶段 3)。阶段 1、2 的速览表**只有四列**,不含置信度列;阶段 3 才追加第五列。`changed_since_prev` 是例外,因为 P3 规则依赖它,且它是纯脚本计算、不改结论。
2. **不回填、不重算、不删除任何 v1 条目;不写迁移脚本**,只写一份 `state/decision-log-migration.md`。08-14 那 5 条未判定条目永久保持 `未判定`。
3. **不动 `briefs/` 要点表模板**。它是管道面数据单,报告才是读者面;动它会牵连 `--strict-brief` 的数字白名单与 `split_brief_review_block` 的豁免切分。
4. **不动采集层**(`events/macro/rates/feeds/calendar`)与 `weekly_digest` 的既有判定逻辑,只加只读消费者与新字段。
5. **不做管道句比例闸门**(裁定 C1)。
6. **不追求词表覆盖改写**;不为 A 类(相邻文字否定)再加哨兵——已封为文档化边界。
7. **不改 `MAX_SECTION_CJK` 数值、不改 `ALLOWED_SMALL` 范围、不改 `NUMBER_UNTRACEABLE` 判据。**
8. **不在同一个 change 内同时做阶段 1 与阶段 2。** 删 `set-review` 会让 `tests/test_log_decision.py` 的 12 处引用与 `tests/test_review.py` 的 15 处 `direction_outcome` 整体重写(**不得靠放宽断言消除**,应改写成负向用例);混在一起就是七轮审查的复发条件。
9. **不接新数据源、不动全链路零 API key / 标准库 only / 测试不打真实网络 三条硬约束。**

**落地顺序(两个 change):**

- **阶段 1(纯加强,零 schema 变动,决策日志一个字节不改)**:正文/附录分界锚点 + `scripts/appendix.py` + 管道句位置闸门(必须在附录、禁止在正文)+ `BODY_PLUMBING_LANGUAGE`(P1/P2/P3)+ `REPORT_HTML_COMMENT` + minimal 模式(`derived.body_plan`)+ 四环标签检查 + 周报 `### 主线` 3–5 与 `THEME_SHAPE` + 两份模板改写 + 三处措辞同步。
  **另加一件小事,不可省**:让 `review.py` 用 `verdicts.join_verdict` 输出一条**方向核对句**进要点表复盘块,并由 `REVIEW_LINE_NOT_QUOTED` 要求它逐字进正文复盘节。这是零成本地给现有 `direction_outcome` 接上**第一个下游消费者**(实测今天是 0 个)。
  > 诚实标注:阶段 1 之后 SKILL 仍允许 LLM 写 `verdict=无法判定`,它可以在被引用的整句旁边写一句否定(A 类)。阶段 1 只保证**读者看得见脚本结论**,根治要等阶段 2。
- **阶段 2**:schema v2 + `verdicts.resolve_claim` + `scripts/resolve.py` + 删除 `set-review` + 计数分栏 + `REVIEW_VERDICT_NOT_QUOTED_IN_BODY` / `REVIEW_WORD_IN_BODY` / `REVIEW_WORD_IN_REASON` + 占比闸门。

**必须同步改的三处措辞**(不改就会出现「照 SKILL 写必违反模板、照模板写必违反 SKILL」的死结):
- `skills/fx-daily-report/SKILL.md:171` 禁令 9 →「事件结论句由 `scripts/appendix.py` 写进附录 A,**正文禁止出现该句**;你不转抄、不改动」
- `skills/fx-weekly-report/SKILL.md:86-92` 计数与结论纪律第 1 条 → 同改
- `scripts/check_report.py:121` `DISPOSITION_QUOTE` →「把上面「期望原文」那一句整句抄进**正文的复盘节**」(该处置从此**只**服务判定类结论句;管道类结论句已由脚本生成,不需要人抄,其处置是新的 `DISPOSITION_MOVE_TO_APPENDIX`)

---

## §9 论证:本设计**没有**削弱「结论由脚本给出、LLM 逐字引用」

### 9.1 现状:这条不变量在复盘环上强制力为 0,且数据流方向是反的

三条实测,全部在本次会话复跑:

1. `scripts/review.py:98` 的 `direction_outcome` 由脚本机械算出,但 **grep 全仓,除 `review.py` 自身的 pending 判定外无任何消费者**——它只以「方向核对: X」出现在要点表的一行文本里。
2. LLM 经 `log_decision.py set-review` 写的 `verdict` 是**唯一**流向读者的字段(`weekly_digest.py:615/637/685-686` → 周报复盘汇总)。
3. `check_report.py` **从不打开** `state/decision-log.jsonl`(`grep -n 'decision-log' scripts/check_report.py` → 0 行)。文件里 42 处 `verdict` 全属 `events_verdict` 那套事件结论句闸门。

结果:脚本给出 8 条决定性结论,只有 **2** 条被采纳(§0)。脚本算的那半截接不上任何输出,LLM 写的那半截独占输出。

### 9.2 逐项论证本设计是净加强

| 改动 | 现状 | 改后 | 是加强的证据 |
|---|---|---|---|
| 管道结论句的位置 | `if s not in report`,`report` 是**整份文件**;实测移进附录 rc=0、包进 HTML 注释无 VERDICT 码、四币种撞串删一行 rc=0 | 保留原判据**不删**,在其上追加:必须在**附录区**、必须**整块逐字**、报告不得含 HTML 注释 | §0 三条现存绕过在新规则下全部变红 |
| 结论句的转抄环节 | LLM 逐字转抄,可改一字、可漏一条 | **整块由脚本生成,LLM 零接触** | 从「逐字引用」升级为「不经手」——不变量的最强形态 |
| 判定类结论的位置 | 无任何位置约束 | **必须逐字出现在正文**(M13),与管道句方向相反的第二道位置闸门 | 这是任务书点名的自伤风险,本设计**先于**去管道语汇落地它 |
| `direction_outcome` 的消费者 | 0 个 | 阶段 1 起有 1 个(正文复盘节逐字引用);阶段 2 起合并为唯一的 `review.verdict` | 「6/35 不一致」这一形态在新结构下**不可表达** |
| verdict 的写入口 | `log_decision.py set-review --verdict`,LLM 有语法表达结论 | **物理删除**;`resolve.py` 的入参只有 `--date/--root` | LLM 从此**没有语法**可以写 verdict——prompt 禁令换成不变量,与本仓库既有教训(`fx-verdict-invariant`)一致 |
| 触发是否发生 | `SKILL.md:211` 让 LLM 判定的「触发未发生」**一票否决**脚本结论 | 整段删除;`trigger_fired` 由 `resolve_claim` 第 4 步机械求值(claim 必须绑可观测量,才可机械求值) | 6/8 的覆盖率归零 |
| `MAX_THEME_ITEMS` | 「≤3 条列表行」;实测 9 条 `### 主线` rc=0 | 「本节禁列表行 + `3 ≤ ### 主线 ≤ 5`」 | 上限数值放宽,但形态与下限收紧;**净效果实测为收紧**(9 条从 rc=0 变 rc=1) |
| `MAX_SECTION_CJK` / `ALLOWED_SMALL` / `NUMBER_UNTRACEABLE` | — | **一个字符不改** | 见 §8 非目标 7 |

### 9.3 唯一一处名义上的「放宽」及其辩护

`SKILL.md:171`「事件结论句必须在**该币种节内**逐字出现」→「禁止出现在正文,由脚本写进附录 A」。

它不是放宽,因为**那句散文从来没有对应的脚本判据**:实测判据是 `s not in report`(整文件子串),节级要求只存在于提示词里,而提示词里的第二份表述可以被相邻文字否定(本仓库 T8b 已实证约 15 条绕过)。改造后,这句话第一次拥有一个可精确断言的分区判据(附录区 + 整块逐字 + 正文禁现),并且**执行主体由 LLM 换成了脚本**。

### 9.4 单调性自查表(实现者提 PR 时逐条勾)

- [ ] 没有删除任何既有违规码
- [ ] 没有放宽任何既有阈值(`MAX_SUMMARY_ITEMS` / `MAX_SECTION_CJK` / `ALLOWED_SMALL` / `DERIVED_VERDICT_SCHEMA`)
- [ ] 没有新增任何豁免开关(含 `argparse.SUPPRESS` 隐藏项、位置参数、`parse_known_args`、既有参数的魔法值)
- [ ] `check_report.py` 仍**不读环境变量**(`VerdictGateIsOrthogonalToTheCheckedObjectTest` 的 AST 断言)
- [ ] 每一处新增的「跳过」都进 `notes` 并被打印(`BODY_PLAN_ABSENT_SKIPPED` / `BODY_PLUMBING_P1_SKIPPED`)
- [ ] 每一个新码都进码清单冻结表与 `CheckerPrintsItsOwnDispositionTest` 的逐码处置对应
- [ ] 基线 `Ran 715 tests / OK / rc=0` 之上只增不减;新用例中 M1–M15 各至少一条,且**先红后绿**

---

**相关文件(绝对路径)**
`/home/ubuntu/repos-REBORN-lab/macro/scripts/check_report.py`(分界锚点导入、全部新码)
`/home/ubuntu/repos-REBORN-lab/macro/scripts/appendix.py`(**新建**,锚点常量与附录块的唯一事实源)
`/home/ubuntu/repos-REBORN-lab/macro/scripts/verdicts.py`(新增纯函数 `resolve_claim` 与符号表 `INDICATOR_SIGN`)
`/home/ubuntu/repos-REBORN-lab/macro/scripts/resolve.py`(**新建**,阶段 2)
`/home/ubuntu/repos-REBORN-lab/macro/scripts/log_decision.py`(阶段 2 删 `set-review`、加 G1–G7b)
`/home/ubuntu/repos-REBORN-lab/macro/scripts/review.py`(阶段 1 追加方向核对句)
`/home/ubuntu/repos-REBORN-lab/macro/scripts/collect/derive.py`(`body_plan` / `changed_since_prev`)
`/home/ubuntu/repos-REBORN-lab/macro/skills/fx-daily-report/SKILL.md`(禁令 9、第 4 步模板、第 4 步决策日志段、删 211-217)
`/home/ubuntu/repos-REBORN-lab/macro/skills/fx-weekly-report/SKILL.md`(第 1 步阅读顺序、第 2 步模板、纪律第 1 条)
`/home/ubuntu/repos-REBORN-lab/macro/state/decision-log-migration.md`(**新建**,阶段 2)
原型(可照抄):`/tmp/claude-1000/-home-ubuntu-repos-REBORN-lab-macro/0a91e423-4443-48c6-a5c1-42bfb719e0a6/scratchpad/proto-daily-2026-08-14.md`、`…/proto-weekly-2026-W33.md`
本次实测产物:`…/scratchpad/RB_appendix_0813.md`、`RB_appendix_dropTHB_0813.md`、`RB_appendix_commented_0813.md`、`RB_weekly_9themes.md`、`RB_tests.err`