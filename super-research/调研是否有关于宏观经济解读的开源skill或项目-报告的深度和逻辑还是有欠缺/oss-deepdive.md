# 源码层深挖:可执行的采纳裁定

> 本轮定位:上一轮只读到 README 层,本轮五路子代理 `git clone` 读到源码层。本文是**裁定**,
> 不是汇总——五路取材是待判断的材料,冲突处由本文给结论并写明理由。
>
> 本文中所有计数均**先跑命令、后抄输出**;逐字原文均带 `文件路径:行号`。
> 「读到了」不等于「验证了它有效」,两者在文中严格分开。

## 0. 本轮复核用到的实跑命令(裁定所依赖的部分,由本文作者亲自重跑)

克隆位置:`…/scratchpad/oss/`(五路子代理已 clone)与 `…/scratchpad/oss2/digital-oracle`(本文重克隆),
均在 `/home/ubuntu/repos-REBORN-lab/macro` **之外**。

```
$ cd scratchpad/oss/econstack && git log --oneline -1
69ebb8e v0.14.0: revive /cost-benefit, fully wired to greenbook
$ git rev-list --count HEAD
139
$ grep -cE '^\| [A-R][0-9]+ \|' econ-audit/SKILL.md          # HEAD 上带编号的检查项
0
$ grep -c '^| \*\*' econ-audit/SKILL.md                      # HEAD 上的类目表行数
14
$ git show 8b7cad3:econ-audit/SKILL.md | grep -cE '^\| [A-R][0-9]+ \|'
124
$ git show 8b7cad3:econ-audit/SKILL.md | grep -oE '^\| ([A-R])[0-9]+ \|' \
    | sed -E 's/^\| ([A-R])[0-9]+ \|/\1/' | sort | uniq -c
     10 A   7 B   7 C   5 D   7 E   8 F  12 G   9 H   6 I  10 J
      7 K   6 L   6 M   5 N   6 O   5 P   8 R          （17 类)
$ grep -rn "audit" bin tests | wc -l                          # cost-benefit 的「自动审计」有无代码
0

$ cd scratchpad/oss2/digital-oracle
$ ls digital_oracle/providers/*.py | wc -l
20
$ PYTHONPATH=. python3 -c "…issubclass(o, SignalProvider)…"   # 具体 provider 类
16
['BisProvider','CMEFedWatchProvider','CftcCotProvider','CoinGeckoProvider','DeribitProvider',
 'EastmoneyProvider','EdgarProvider','FearGreedProvider','KalshiProvider','PolymarketProvider',
 'StooqProvider','USTreasuryProvider','WebSearchProvider','WorldBankProvider',
 'YFinanceProvider','YahooPriceProvider']
$ grep -cE 'https?://' digital_oracle/providers/stooq.py       # Stooq 是否真有上游
0

$ cd /home/ubuntu/repos-REBORN-lab/macro
$ grep -rn "关键假设\|替代解释\|翻转指标\|失效条件" scripts/ --include=*.py
（无输出）                                    ← 本轮最重要的一条本仓事实,见 §3
```

## 1. 两个未决矛盾的裁定

### 第 1 对 — digital-oracle 的数据源数目 · **可以判定**

**裁定:能判定,但答案不是一个数,而是「四个口径各自的数 + 该项目文档内部不自洽」这一事实本身。**
上一轮悬置的原因是「不知道哪些 provider 是真的」,本轮逐个核对后这个障碍已经消除。

实测底数(本文亲自重跑):

| 口径 | 数 | 依据 |
|---|---:|---|
| `providers/` 下 `.py` 文件 | **20** | `ls providers/*.py \| wc -l`(含 `__init__.py` / `base.py` / `_coerce.py` / `prices.py`) |
| 具体 `SignalProvider` 子类 | **16** | `issubclass` 运行时枚举,见 §0 |
| 有独立上游、非兼容桩 | **15** | 16 − `StooqProvider` |
| 当前实际取得到数据 | **14** | 15 − `CMEFedWatchProvider`(上游 403,取材 4 实测) |
| 独立上游机构(两个 Yahoo provider 合一、不含 DuckDuckGo) | **13** | 逐个 URL 归并 |

**`StooqProvider` 是兼容桩,不是数据源** —— `digital_oracle/providers/stooq.py:44-46` 逐字:

```python
@dataclass
class StooqProvider(SignalProvider):
    """Backward-compatible price provider backed by Yahoo Finance."""
```

且 `grep -cE 'https?://' digital_oracle/providers/stooq.py` = **0**(本文重跑),全文零 URL,只做符号映射后转调
`YahooPriceProvider`。而 `README.md:40` 仍把 `Stooq` 单列一行当数据源。

**该项目文档里对同一属性存在 5 个不同的数,分布在 6 处**(本文重跑 `grep`,逐字):

```
README.md:17      它接入了 13 个权威金融数据源
README.md:73      13 个数据源中有 12 个零外部依赖(纯 Python 标准库)
README.md:96      │   └── providers/          # 13 个数据 provider
README.md:106     零依赖优先 — 12/13 个 provider 只用 Python 标准库
README.en.md:73   11 out of 12 data sources have zero external dependencies
README.en.md:96   │   └── providers/          # 12 data providers
SKILL.md:208      **All 14 Providers:**
SKILL.md:228      > 13 out of 15 providers have zero external dependencies and zero API keys.
```

即 **11 / 12 / 13 / 14 / 15** 五个数,且中英文 README 对同一句话给出不同的数(13 vs 12;12/13 vs 11/12)。
上一轮记的「四个数」是低估。

**结论与对报告的处置**:上一轮「不引用其自述数字」的处置**继续有效,且理由从「无法判定」升级为「已判定其自述不可靠」**。
引用该项目时按本文表格用带口径的数(推荐用「16 个 provider 类 / 13 个独立上游」),并可陈述
「其文档对同一属性给出 11/12/13/14/15 五个互不一致的数」这一已实测事实。

**这一对不再是未决。**

### 第 2 对 — econstack `/econ-audit` 是否只做存在性检查 · **可以判定,但结论与原假设都不一样**

上一轮的问法是「124 项里多少是存在性、多少是质量」。本轮取到了清单原文,**发现问题问错了**:

**(a) HEAD 上根本没有那 124 项。** 本文重跑:HEAD(`69ebb8e`)`grep -cE '^\| [A-R][0-9]+ \|' econ-audit/SKILL.md` = **0**;
只剩一张 14 行的类目表(`econ-audit/SKILL.md:117-130`),Checks 列是自然语言问句串,无编号、无严重性、无阈值。
124 项 / 17 类最后存在于 `8b7cad3`(2026-04-07),在 `2877cf6`「Slim tier 2 and 3 skills」中被整体删除。
`README.md:174` 与 `CLAUDE.md:15` 至今仍写「124 checks across 17 categories」——**自述过期了 110 个 commit**。

**(b) 124 项在历史版上确实存在,且实测精确匹配自述。** 本文重跑 `git show 8b7cad3` 得 **124 项 / 17 类**(A–R 跳过 Q),
分类计数见 §0。取材 1 的这组数**复核通过**。

**(c) 逐条二分的结论:62 质量 / 60 存在性 / 2 无法判定(取材 1 分类)。本文抽查复核了其中 27 条(A/L/M/N 四类),
26 条同意,1 条存疑。** 复核记录:

- **A 类 10/10 判为质量 —— 同意。** `econ-audit/SKILL.md@8b7cad3:166-170` 逐字:
  `| A2 | Does PV costs + PV benefits = correct NPV? (recompute) | RED |`、
  `| A3 | Does BCR = PV benefits / PV costs? (recompute) | RED |`、
  `| A6 | Do switching values, when applied, actually produce NPV = 0? (recompute) | RED |`。
  明写 `(recompute)`,判据是重算结果而非文本存在,属质量。
- **N 类 5/5 判为质量 —— 同意,且这是全清单最值钱的一类。** `:339-343` 逐字:
  `| N1 | Are cost estimates at the bottom of the plausible range AND benefit estimates at the top? (Pattern consistent with Flyvbjerg's strategic misrepresentation finding.) | AMBER |`
  `| N3 | Are contingencies below 10% of capex at OBC stage or below 5% at FBC stage? (Unusually low for most project types.) | AMBER |`
  `| N5 | Are multiple optimistic assumptions compounded? (Optimistic on costs AND benefits AND timing AND demand.) If yes, compute the combined probability. | RED |`
  全部给出可观测量或显式阈值,零存在性污染。
- **L 类 6/6 判为存在性 —— 同意。** `:317-322` 六条全是 `Are … assessed / documented / justified / considered / provided`,
  连 L1 的严重性阈值(`For projects > GBP 50m PV: RED if absent`)也是**对"缺失"的分级**,不是对"内容"的判据。
- **M 类 5 存在性 + 1 无法判定 —— 部分存疑。** 本文认为 **M5 应判为质量**,`:332` 逐字:
  `| M5 | **Uncertainty-managed:** Is uncertainty quantified, not just acknowledged? (Sensitivity analysis must cover ranges, not just "results are sensitive to assumptions.") | AMBER |`
  它明写 `not just acknowledged`,并给出反例串(`"results are sensitive to assumptions."`),
  这是**对同一节内容的强弱分级**而非有无判定,与 IMF WP/26/35 批评的那一层不同型。
  这一条分歧不改变量级(62→63 / 60→59),但它指向本轮最可迁移的一个写法,见 §3 第 6 条。

**(d) 与 IMF WP/26/35 的关系裁定:`/econ-audit` 不是「恰好落在 IMF 批评的那一类」,但也救不了我们。** 三条理由:

1. **历史版有一半是真质量检查**,不是全存在性——所以不能说它落在 IMF 那一层。
2. **但它是纯提示词,一行代码都没有**。全仓 34 个文件 7720 行,**无任何 `.py/.js/.ts/.R`**;
   `grep -rn "audit" bin tests | wc -l` = **0**(本文重跑)。所谓「`/cost-benefit` 自动追跑 audit」
   (`cost-benefit/SKILL.md:640-650`)是模型被要求自己去调另一个 skill,不调也没有任何东西报错。
3. **HEAD 主动禁用了让质量检查成立的那个动作。** 对照两版逐字:
   - 历史版 `econ-audit/SKILL.md@8b7cad3:680`:`- Cross-check every number you can. Recompute NPV, BCR, and switching values independently and compare.`
   - HEAD `econ-audit/SKILL.md:330`:`- Do NOT re-compute NPV / BCR / EIRR yourself unless the user asks.`
   A 类 10 项(全清单质量项的 16%)在 HEAD 语义下退化为存在性。

**结论:第 2 对不再未决。** 判定为:**「抄 `/econ-audit` 补论证质量校验」不成立**——但不成立的理由不是
「它只做存在性检查」(那是被证伪的),而是「**它要抄的那版已被上游删除,且它从来没有强制力**」。
可抄的是被删掉的那版里的**判据措辞**(尤其 N 类与 A 类),不是它的机制。
原判据「不得在缺证据的情况下把 `/econ-audit` 写成已解决论证质量校验」**依然成立,且现在有了正面证据**。

## 2. 存在性 vs 质量 的总账

### 2.1 计数口径(先声明,再计数,避免事后凑数)

- **台账 A(机制级)**:五路取材中每个**可命名的独立机制**记一行。混合机制按**主导类别**归类并加脚注。
- 分四类,比上一轮的二分多两类——因为二分不够用:
  - **Q 质量**:验「该节论证是否成立」——要求重算、跨产物比对、显式数值阈值、外部基准,或点名分析层面的具体错误模式。
  - **E 存在性**:验「某节/某字段/某关键词是否出现」。**包括那些要求「充分/清晰/恰当」却不给操作化标准的**——
    这类在实践中必然退化为 IMF WP/26/35 描述的 `without fully evaluating the depth or quality of that discussion`。
  - **N 非检查**:文本写成规则的样子,但**源码里没有任何东西对它求值**。上一轮的二分会把这类误记为「存在性检查」,
    从而高估社区的机制密度。单列是本轮的口径修正。
  - **U 无法判定**:源码不足以区分。**如实写,不归入任何一类凑数。**
- 另记一个正交字段 **backing**:`code`(有代码求值)/ `prose`(纯 markdown 文本)。

### 2.2 计数结果(先跑后抄)

台账文件:`…/scratchpad/ledger.tsv`(53 行)。实跑输出逐字:

```
$ wc -l < ledger.tsv
53
$ cut -f4 ledger.tsv | sort | uniq -c
     17 E
      8 N
     20 Q
      8 U
$ cut -f5 ledger.tsv | sort | uniq -c
     13 code
     40 prose
$ awk -F'\t' '$4=="Q"{print $5}' ledger.tsv | sort | uniq -c
      5 code
     15 prose
```

派生比例(脚本算出,逐字抄):

```
质量 20/53 = 37.7%    存在性 17/53 = 32.1%    非检查 8/53 = 15.1%    无法判定 8/53 = 15.1%
质量+存在性(真正是检查的) = 37/53 = 69.8%
  其中 质量 20/37 = 54.1% ; 存在性 17/37 = 45.9%
代码求值 13/53 = 24.5% ; 纯散文 40/53 = 75.5%
质量且代码求值 5/53 = 9.4%
质量且代码求值且实现正确 3/53 = 5.7%
质量机制中纯散文的占比 15/20 = 75.0%
```

### 2.3 台账 A 全表(53 行)

#### Q 质量(20 条)

| ID | 项目 | 机制 | backing | 判定依据 |
|---|---|---|---|---|
| A2 | econstack | econ-audit@8b7cad3 A 类数值一致性 10 项 | prose | 明写 `(recompute)`,判据是重算结果 |
| A3 | econstack | econ-audit@8b7cad3 N 类 Flyvbjerg 5 项 | prose | 显式阈值(10%/5% 应急金)+ 对照历史趋势 + 复合乐观计数 |
| A6 | econstack | `--fix` 闭环(历史版) | prose | `修→重算受影响数字→重跑审计确认 RED 归零→存 diff`,自验证回路 |
| A9 | econstack | cost-benefit Step 6.5 写盘前 validation gate | prose | 对**结构化 spec 的字段值**做谓词判断,有 abort 语义 |
| A10 | econstack | 历史版机械评级 + RED 封顶 | prose | 评级由计数规则导出,不由措辞导出 |
| A12 | econstack | econstack-data 57 个参数 JSON | code | 机器可读外部基准(HMT Table 1 乐观偏差矩阵等) |
| B6 | MoneyAtlas | first_principle_codex 矛盾检测 | code | 对内容求值——**但实现错误**,见 §3 排除项 |
| C1 | econ-writing | review-checklist 三审查者 24 条 | prose | 判据措辞要求「论证是否成立/是否过度宣称」,非有无 |
| C2 | econ-writing | SKILL.md:388 效应量对外部基准 | prose | 要求外部可比量级 |
| C3 | econ-writing | SKILL.md:395 精确零 vs 测不准 | prose | 把「无」拆成「测准的零」与「测不准」两种,可判 |
| C4 | econ-writing | SKILL.md:391 系数稳定性 / Oster 界 | prose | 要求报 R² 变动,拒绝以稳定性代替证据 |
| C5 | econ-writing | evals 18 用例 113 判据 + Failure modes | prose | 每条判据配一条**可搜索的已知失效串** |
| D3 | senior-analyst | council.md:25 零反驳 ⇒ 移出判断列表 | prose | 是**结构不变量**(判断数与实质反驳数的关系),可脚本化 |
| D5 | senior-analyst | council.md:232 全通过则反思提取标准 | prose | D3 的对偶,同为结构约束 |
| E3 | scholar | Tolerance Thresholds 因果推断 4 行 | prose | 要求**两份产物对照**并给出数值容差 |
| E6 | scholar | verify-citations.py 三外部 API 核对 | code | 打 crossref / arxiv / semantic scholar 核对外部事实 |
| F2 | digital-oracle | 时间分层:信号 → 时间桶预绑定 | prose | 信号类型与时间桶事先绑定,误置**可被外部核对并判错** |
| F5 | digital-oracle | Signals to monitor 表(current value + threshold) | prose | 两列合起来产出**跨期可证伪的对象** |
| G4 | dual-axis | test_health(pytest 退出码 20 分) | code | 分数挂在进程退出码上,评审者措辞影响不了 |
| G5 | dual-axis | execution_safety `output_dir` 谓词 | code | 对**提取出的实参值**做谓词判断,而非对文本做存在性判断 |

#### E 存在性(17 条)

| ID | 项目 | 机制 | backing | 判定依据 |
|---|---|---|---|---|
| A1 | econstack | econ-audit HEAD 类目表(14 类 / 18 问号) | prose | 自然语言问句串,无编号无阈值 |
| A4 | econstack | econ-audit@8b7cad3 L 类分配 6 项 | prose | 六条全是 `assessed / documented / justified / considered` |
| A5 | econstack | econ-audit@8b7cad3 M 类 RIGOUR 6 项 | prose | RIGOUR 六字母全落在「有没有写」;M5 本文存疑,见 §1 |
| A7 | econstack | `--fix`(HEAD:提议 + 逐条确认 + 编辑) | prose | 历史版的重算与重跑审计已被删,只剩编辑 |
| B3 | MoneyAtlas | validate_skill.py 18 项 | code | **比存在性更弱**:正则搜的是 SKILL.md 自己的提示词正文,不是产物 |
| B4 | MoneyAtlas | tests/ 21 用例 | code | 7 个是 B3 的 pytest 复刻(重言),7 个测未接入的信号引擎 |
| C6 | econ-writing | test_plugin_package.py 25 用例 | code | 24 个测安装/打包,1 个查 frontmatter 有无 4 个触发词 |
| D2 | senior-analyst | 7 类认知谬误表 | prose | 有「检查点 + 识别信号」两列,但验证是同一次生成里自问自答 |
| D6 | senior-analyst | completeness_checklist Council 10 项 | prose | 10 项全是「是否出现某节/某标注」 |
| E1 | scholar | quality-gates 论文扣分表 12 行 | prose | 12 条中 11 条形如 `X not stated / missing / no Y` |
| E2 | scholar | quality-gates 脚本扣分表 8 行 | prose | 机器可判(编译日志 / 正则),但判的仍是有无 |
| E5 | scholar | paper-self-review 35 条扣分表 | prose | 主导为存在性;含少数质量条(effect size benchmarked) |
| F1 | digital-oracle | 分歧分析(divergence)章节 | prose | 只要求写出「A 说 X、B 说 Y + 谁更可信」,无成立条件 |
| G3 | dual-axis | workflow_coverage(正则标题 5 分/节) | code | `has_heading()` 正则匹配标题行,标题下写什么都给满分 |
| G7 | Awesome-Journal | quality_scorecard.py 5 维 | code | 评的是技能包**包装质量**;`evidence` 维是来源新鲜度 |
| G8 | Awesome-Journal | Decision ledger(claim/evidence/blocker/next edit) | prose | 无分档无判据无脚本消费;150 个包逐字相同 |
| G9 | Awesome-Journal | Verification floor(命名一个未决事实) | prose | 同上;措辞接近质量,但无判据、无消费者 |

#### N 非检查:写成规则但源码零求值(8 条)

| ID | 项目 | 机制 | 判定依据 |
|---|---|---|---|
| A8 | econstack | cost-benefit Step 8 auto-audit hook | `grep -rn "audit" bin tests \| wc -l` = 0(本文重跑) |
| B1 | MoneyAtlas | FAILURE SYSTEM 四条否决 | `grep -rniI "insufficient edge"` 全仓 2 命中,均为自述,无 `.py` |
| B2 | MoneyAtlas | `[UNVERIFIED]` 禁入 entry/exit 结论区 | 全仓 1 次出现,无测试无校验无 CI |
| B5 | MoneyAtlas | discernment_engine / skeptic_agent | 参数从未被读取,返回常量字符串 |
| E4 | scholar | Enforcement Protocol `<80 阻断` | `/commit` 命令文件零命中;5 个 hook 无一跑评分;全仓 34 个脚本无一计算分数 |
| F7 | digital-oracle | `Never cite analyst opinions.` | 禁令,零实现(取材 4 对其「破例」部分被截断,见 §5) |
| G1 | Awesome-finance | 分歧评估 Entropy + `market_entropy` 字段 | 字段 3 次出现全为声明,**0 处赋值 0 处读取**;`InvestmentReport` 0 处实例化 |
| G6 | dual-axis | LLM 轴 0.5 权重照单全收 | 穷举搜索确认无抗漂移机制;不是「读不到」,是「不存在」 |

#### U 无法判定(8 条)

| ID | 项目 | 机制 | 为什么判不了 |
|---|---|---|---|
| A11 | econstack | HEAD 评级(文字描述 + critical 封顶 C) | `A (no fails, few warnings)` 无阈值,但 `:372` 仍保留封顶规则,机械/主观混杂 |
| D1 | senior-analyst | 规则 #35 双轨修复 + 缺口二分 | 它是修复协议不是校验器;且「记入 CLAUDE.md」的落点在该仓库**不存在**(`ls CLAUDE.md` 报无此文件) |
| D4 | senior-analyst | council.md:31-34 反虚假对称 | 逻辑上是质量检查(要求论据强度匹配证据分布),但无任何判定装置 |
| E7 | scholar | devils-advocate 5-7 条挑战 | 取材 3 的原文在此处被截断,本文未读到全文 |
| F3 | digital-oracle | 信号权重三条偏序 | 未定义如何合成权重,也未说偏序冲突时怎么办 |
| F4 | digital-oracle | `Don't vote by majority.` | 作为否定式规则可核对,但三条正向替代无终止条件 |
| F6 | digital-oracle | `volume < $100K should be discounted` | `$100K` 是硬的,`discounted` 无量化 |
| G2 | Awesome-finance | 稳定 CiteKey sha1 | 生成端是内容寻址(真机制),消费端零校验(`grep dangling\|unresolved\|validate_cit` = 0) |

### 2.4 台账 B — econstack 124 项逐条(单独计,不并入台账 A)

取材 1 的分类:**质量 62(50.0%)/ 存在性 60(48.4%)/ 无法判定 2(1.6%)**。
本文抽查复核 27 条(A/L/M/N 四类),26 条同意、1 条存疑(M5,见 §1)。剩余 97 条未逐条复核。

对本轮结论最关键的三个读数(全部复核通过):

- **N 类 5/5 全是质量检查,零存在性污染** —— 全清单唯一一个,最值得直接抄。
- **L 类 6/6 全是存在性、M 类 5/6 存在性** —— 最像「验论证质量」的两个类目(分配公平、分析质量保证),
  在源码层**一条质量检查都没有**。这是 IMF WP/26/35 那条结论在开源实现里的直接复现证据。
- **A 类 10/10 质量,但全部依赖重算,而 HEAD 明文禁止重算** —— 在 HEAD 语义下实际可用质量项降到 52/124 = 41.9%。

### 2.5 回答那个问题:社区的「质量机制」有多大比例其实只是存在性检查?

**四个数,一起看才有意义。**

1. **按机制条数,质量 37.7%(20/53),存在性 32.1%(17/53)。**
   如果只看这一层,结论是「社区机制并非大多停在存在性那一层」——**上一轮的悲观假设被部分证伪**。

2. **但另有 15.1%(8/53)根本不是检查**——写成规则的样子、源码里零求值。
   上一轮的二分口径会把这 8 条误记为「存在性检查」,从而**高估社区的机制密度**。
   把 N 与 E 合起来看(「至多只能验有无、甚至连有无都不验」):**25/53 = 47.2%**。

3. **决定性的一刀在 backing 上:75.5%(40/53)是 markdown 里的散文,一行代码都不对它求值。**
   质量机制里这个比例更高:**质量机制中 75.0%(15/20)是纯散文**。

4. **由代码求值、且实现正确的质量检查,全社区 53 个机制里只有 3 个(5.7%)**:
   `verify-citations.py` 的外部 API 核对(E6)、`test_health` 的 pytest 退出码(G4)、
   `execution_safety` 的实参谓词(G5)。第 4 个(B6 矛盾检测)实测有假阳性;
   第 5 个(A12 参数 JSON)是数据文件,不是求值器。

**裁定:「抄开源」这条路的天花板不在判据设计上,在强制力上。**

社区**不缺**好的质量判据措辞——A2/A3/A6 的重算、N1–N5 的复合乐观、E3 的两产物容差对照、
C2 的外部基准、C3 的精确零 vs 测不准、F5 的当前值+阈值两列,这六组措辞都值得抄,
而且它们**恰好都是我们的校验器现在没有的**。

社区**极度缺**的是把这些判据接到脚本上。53 个机制里 40 个是散文;
最像"审计器"的那两个(econstack `/econ-audit` 124 项、scholar `<80 阻断`)恰恰**一行代码都没有**。
MoneyAtlas 的 `validate_skill.py` 甚至比 IMF 批评的那一层还要低一级——
IMF 那个评分器至少在**读产物**、只是不评质量;它正则搜索的是 **SKILL.md 自己的提示词正文**,
唯一能失败的场景是有人编辑规则手册删掉某个词。

**所以本轮对本仓库的真正结论,和"抄什么"无关,和"我们自己缺什么"有关:**

```
$ cd /home/ubuntu/repos-REBORN-lab/macro
$ grep -rn "关键假设\|替代解释\|翻转指标\|失效条件" scripts/ --include=*.py
（无输出)
```

**本仓库已落地的判断环(关键假设 / 替代解释 / 翻转指标)在 `scripts/` 下零强制。**
`skills/fx-daily-report/SKILL.md:262-272` 把它写得很细
(`翻转指标 | **什么一旦出现就改判**……必须是价格或指标的可观测量,带 T+N`),
但 `scripts/check_report.py` 763 行里对这三件事**一次都没提**——
校验器查的是 `SECTION_MISSING` / `SECTION_TOO_LONG` / `GAPS_NOT_DISCLOSED` / 数字溯源 / 结论句逐字引用。
按本文台账口径,**我们自己的判断环目前是 N 类(非检查)**,和 econstack `/econ-audit`、
scholar `<80 阻断` 同型。这正是 MEMORY 里那条「13 次同型缺陷的根因:prompt 禁令堵不住,要改成不变量」
在本仓库尚未被堵住的一个出口。

§3 的排序即由此得出:**优先级不是引进新判据,是把已有判据从散文升级为脚本不变量。**

## 3. 可采纳清单(按 收益/代价 排序)

排除条款:四环链条、正文零管道语汇、ICD 203 关键假设/替代解释/翻转指标(**判据本身**)、
生成顺序与呈现顺序解耦、`PRIOR_PERIOD_BOILERPLATE`、附录整块脚本生成 —— 已落地,不重复推荐。
注意:**"判据已落地"不等于"强制已落地"**,§3.1 正是补后者。

### 3.1 判断环的结构不变量化(收益最高,代价最低)

| 项 | 内容 |
|---|---|
| 机制名 | 零反驳 ⇒ 移出判断列表 / 全通过则反思提取标准 |
| 出处 | senior-analyst `skill/council.md:25` 与 `skill/council.md:232` |
| 逐字原文 | `**底线**:"没什么问题"不是合格的审查结果。如果确实找不到反驳,说明这个结论本身就是事实而非判断,应从关键判断列表中移除。`<br>`(如果所有结论都通过审查,需反思:是否提取标准过松,把事实当成了判断?)` |
| 类别 | **质量**(它是结构不变量,不是措辞禁令) |
| 迁移动作 | 在 `scripts/check_report.py` 加一组检查:①「分歧与判断」段必须三件齐全(关键假设 / 替代解释 / 翻转指标)——目前 `grep` 实测**零检查**;②翻转指标必须含至少一个数值 token 与一个 `T+N` 形态的时限,否则报 `FLIP_NOT_OBSERVABLE`;③替代解释必须自带它自己的翻转指标(SKILL.md:269 已这么要求,校验器没查);④若某币种节的替代解释与主判断**指向同一方向**,报 `FALSE_ALTERNATIVE`——这是 council.md:25 的直接翻译:找不到真反驳的判断不配叫判断。 |
| 代价 | 低。①–③是纯文本结构检查,复用现有 `find_section` / `numbers_in` / `SENTENCE_RE`;④需要一个方向词表,中等。建议先做 ①–③。 |
| 为什么值得 | 这是本轮唯一一条**同时满足**「社区源码里存在」「本仓库已有对应判据但零强制」「可脚本化为不变量」的机制。它把已落地的判断环从台账 N 类升到 E/Q 类。与 MEMORY「结论必须由脚本给出」同族。 |

### 3.2 翻转指标补「当前值 + 数值阈值」两列

| 项 | 内容 |
|---|---|
| 机制名 | Signals to monitor 表 |
| 出处 | digital-oracle `SKILL.md:315-319` |
| 逐字原文 | `### Signals to monitor`<br>`| Signal | Current value | Threshold | Meaning |`<br>`|--------|--------------|-----------|---------|`<br>`| ... | ... | if crosses X | then Y |`<br>`(3-5 concrete signals with specific trigger levels and what they would imply)` |
| 类别 | **质量** —— `Current value` 列强制填当前可观测量,`Threshold` 列强制填 `if crosses X` 形式的具体数;两列合起来使该表**跨期可证伪**。 |
| 迁移动作 | `skills/fx-daily-report/SKILL.md:270` 的翻转指标目前要求「可观测量,带 T+N」,但**没有要求写当前值**。补一列「当前值」,并在 `check_report.py` 里要求翻转指标句同时含「当前值」与「阈值」两个数——**这两个数天然可纳入既有的数字溯源白名单校验**,当前值必须来自快照。 |
| 代价 | 低。SKILL.md 改一行模板;校验器加一条正则 + 复用现有数字溯源。 |
| 为什么值得 | 把翻转指标从「有没有写」升级为「下期能不能拿真数据判它兑没兑现」。且成本极低,因为溯源基础设施已有。**部分已有(翻转指标本身),但「当前值」这一列是新的,不算重复采纳。** |

### 3.3 两份产物对照 + 数值容差

| 项 | 内容 |
|---|---|
| 机制名 | Tolerance Thresholds (Causal Inference) |
| 出处 | social-science-claude-scholar `rules/quality-gates.md:61-68` |
| 逐字原文 | `## Tolerance Thresholds (Causal Inference)`<br>`| Quantity | Tolerance | Rationale |`<br>`| Point estimates | < 0.01 | Rounding in paper display |`<br>`| Standard errors | < 0.05 | Bootstrap/clustering variation |`<br>`| P-values | Same significance level | Exact p may differ |`<br>`| Coverage rates | ±0.01 | Monte Carlo variability |` |
| 类别 | **质量** —— 全仓唯一要求**两份产物互相对照**的规则(脚本重跑的估计 vs 论文里印的数)。 |
| 本仓现状(实测) | `check_report.py:726-732` 已有 `NUMBER_UNTRACEABLE`,但逐字是:`allowed = numbers_in(digest_text) \| ALLOWED_SMALL` / `for text in daily_texts: allowed \|= numbers_in(text)` / `for n in sorted(numbers_in(report) - allowed):` —— **这是集合成员判定,不是映射判定**。周报把 USD 节的数字写进 BRL 节、把周一的收盘写成周五的,全部通过。MEMORY 里那条「数字白名单是无序词袋」在这里逐字成立。 |
| 迁移动作 | 把词袋升级为映射:每个数字不仅要在白名单里,还要**来自同一个上下文键**(币种 × 指标)。实现上给 `numbers_in` 加一个带键版本 `numbers_by_key(text)`,周报侧按币种节比对,不匹配报 `NUMBER_CONTEXT_DRIFT`。容差取 0(都是同一快照的抄录),不需要 scholar 那种浮点容差表——**可迁移的是"两份产物对照"这个形态,不是它的具体阈值**。 |
| 代价 | 中低。`check_weekly` 已持有 `daily_texts` 与 `covered`,`find_section` 已有;主要工作是数字归一化(千分位、百分号、小数位)与键抽取。 |
| 为什么值得 | 这是「跨产物比对」这一族里最便宜的一条,且直接堵住周报最可能的失真形态:聚合时把数字挪了位置。**它是把已有机制从"能过"改成"能判",不是新增一层。** |

### 3.4 复合乐观检测(Flyvbjerg N 类的宏观移植)

| 项 | 内容 |
|---|---|
| 机制名 | Strategic misrepresentation checks N1 / N5 |
| 出处 | econstack `econ-audit/SKILL.md@8b7cad3:339` 与 `:343` |
| 逐字原文 | `| N1 | Are cost estimates at the bottom of the plausible range AND benefit estimates at the top? (Pattern consistent with Flyvbjerg's strategic misrepresentation finding.) | AMBER |`<br>`| N5 | Are multiple optimistic assumptions compounded? (Optimistic on costs AND benefits AND timing AND demand.) If yes, compute the combined probability. | RED |` |
| 类别 | **质量** —— 判的是**多个判断之间的联合模式**,不是任一节的有无。 |
| 迁移动作 | 宏观版:检测「五个币种节的方向判断是否全部同向」「所有关键假设是否都指向同一结论」「替代解释是否全部被同一理由驳回」。任一成立则输出一条**非阻断的提示**(不是违规),要求报告显式说明为何联合方向一致。 |
| 代价 | 中。需要从币种节抽方向词,这是本仓库目前没有的能力。 |
| 为什么值得 | 这是唯一一条**检查判断之间关系**而非单条判断的机制。宏观日报最典型的退化形态就是五个币种讲同一个故事。但代价高于 3.1–3.3,建议排在后面。 |

### 3.5 效应量必须对外部基准

| 项 | 内容 |
|---|---|
| 机制名 | Benchmark the effect size |
| 出处 | econ-writing-skill `skills/econ-write/SKILL.md:388` |
| 逐字原文 | `- Compare your effect size to: (a) the mean of the dependent variable, (b) the effect of a well-known intervention, or (c) a policy-relevant threshold. Example: "The effect equals 40% of the black-white test score gap"` |
| 类别 | **质量** —— 要求外部可观测基准,不是自洽。 |
| 迁移动作 | SKILL.md 规则:凡在正文中判某个变动「显著/明显/大幅」,必须紧跟一个量级对比(如「相当于近 60 日波动区间的 X%」「约为上一次同类事件的 Y 倍」)。校验器侧可做弱检查:形容词词表命中且同句无百分比/倍数 token → 报 `MAGNITUDE_UNANCHORED`。 |
| 代价 | 低(SKILL.md)+ 低(词表正则)。 |
| 为什么值得 | 直接打击「显著/明显」这类无锚形容词,这是 LLM 报告最稳定的注水点。校验器侧是弱检查(会有假阴性),但假阳性可控。 |

### 3.6 「不是有没有,是够不够」的判据写法(M5 / C3 两处同型)

| 项 | 内容 |
|---|---|
| 机制名 | 强弱分级判据 + 反例串 |
| 出处 | econstack `econ-audit/SKILL.md@8b7cad3:332`;econ-writing `skills/econ-write/SKILL.md:395` |
| 逐字原文 | `| M5 | **Uncertainty-managed:** Is uncertainty quantified, not just acknowledged? (Sensitivity analysis must cover ranges, not just "results are sensitive to assumptions.") | AMBER |`<br>`- Distinguish between "no effect" (precisely estimated zero) and "imprecisely estimated" (wide confidence intervals that include both zero and meaningful effects) -- failing to reject zero is not the same as establishing zero; only a tight interval that excludes economically meaningful effects is informative about absence` |
| 类别 | **质量**(M5 与取材 1 的分类有分歧,见 §1(c)) |
| 迁移动作 | 两件事。①**判据写法**:本仓 SKILL.md 里凡写「必须包含 X」的地方,改写成「X 必须 <强形态>,而不是 <弱形态:附一句可搜索的反例串>」。②**具体条款**:禁止把「数据未显示变化」写成「无变化」——要求区分「区间窄到可排除有意义变动」与「信息不足」。数据缺漏节已有「无」的严格形态,可扩到判断句。 |
| 代价 | 低。①是文案改写;②是词表 + 与「数据缺漏」节的交叉校验。 |
| 为什么值得 | ①这个**写法**本身可能比任何单条判据更值钱:它把抽象要求锚到一个可 grep 的字符串上,从而让存在性检查有机会变成质量检查。②对应本仓一个真实风险:采集失败时把「没数据」写成「平稳」。 |

### 3.7 每条判据配一条已知失效模式

| 项 | 内容 |
|---|---|
| 机制名 | `**Failure modes**:` 行 |
| 出处 | econ-writing-skill `skills/econ-write/evals/test-cases.md:20` |
| 逐字原文 | `**Failure modes**: Vague findings ("significant effects"), passive voice ("it was found"), exceeds 150 words, missing identification strategy` |
| 类别 | **质量(判据设计)**;执行者是人,`grep -rn "evals" --include='*.py' --include='*.sh'` **零命中**。 |
| 迁移动作 | 本仓 `check_report.py` 已有 `DISPOSITION_QUOTE` / `DISPOSITION_SCRIPT_BUG` / `DISPOSITION_PRIOR_PERIOD` 三条处置话术,形态相近但方向相反(处置是"发现后怎么办",failure mode 是"长什么样")。建议给 SKILL.md 每条硬要求补一行失效串,并把其中可正则化的直接接进校验器。 |
| 代价 | 低。 |
| 为什么值得 | 它是 3.1–3.6 的**通用施工方法**,不是一条独立机制。收益体现在后续每条规则上。 |

### 3.8 已有,不重复采纳(逐条说明重叠面)

| 社区机制 | 出处 | 与本仓已有的什么重叠 |
|---|---|---|
| 结论挂在退出码上 | dual-axis `run_dual_axis_review.py:852-854` | `scripts/verdicts.py` + 校验器退出码,已实现「结论由脚本给出」 |
| 写盘前 abort 闸门 | econstack `cost-benefit/SKILL.md:435-437`(`Before writing anything to disk, run the validation gate`) | `check_report.py` 已是产出闸门。**唯一新意是"写盘前"而非"写盘后"**;本仓 skill 流程若已在落盘后跑,可考虑前移,但收益有限 |
| 机械评级 + RED 封顶 | econstack `econ-audit/SKILL.md@8b7cad3:423-426` | `verdicts.py` 已把结论从模型手里拿走 |
| Verification floor(命名一个会改变结论的未决事实) | Awesome-Journal 各包 SKILL.md:55 | 与 ICD 203 翻转指标同义,**已有** |
| Decision ledger(claim / evidence / blocker / next edit) | Awesome-Journal 各包 SKILL.md:53 | 与四环链条(驱动→传导→是否已反映→分歧与判断)同构且更弱,**已有** |
| 稳定 CiteKey `sha1(url)[:8]` | Awesome-finance `report_agent.py:23-27` | 附录已由脚本整块生成、数字已溯源。**唯一可补的是它缺的那半**:「正文出现的键 ⊆ 附录键集合」的断言;若本仓附录引用已是脚本产出则天然成立,无需采纳 |

## 4. 明确不采纳的,及理由

### 4.1 看起来像质量机制、实为存在性检查的(重点)

| 不采纳项 | 出处 | 为什么不值得抄 |
|---|---|---|
| **`/econ-audit` 的整套机制** | econstack `econ-audit/SKILL.md` | HEAD 上那 124 项**已被上游删除**(实测 `grep -cE '^\| [A-R][0-9]+ \|'` = 0),剩下的 14 行类目表是无编号无阈值的问句串;全项目**零代码**。可抄的只有历史版里 A/N 两类的**判据措辞**(已列入 §3.4),不是机制。 |
| **Aqua Book RIGOUR 六字母** | `econ-audit/SKILL.md@8b7cad3:328-333` | 名字最像"分析质量保证",实测 6 条里 5 条只验「有没有写」。这是本轮最强的反面样本:**类目名与判据强度无关**。 |
| **分配分析 L 类 6 项** | `:317-322` | 同上,6/6 全存在性。 |
| **dual-axis `workflow_coverage`(占自动轴 1/4,25 分)** | `run_dual_axis_review.py:612-614` + `has_heading():149-151` | `return any(re.search(pattern, text, ...) for pattern in patterns)` —— 正则匹配标题行,标题下写什么都给满 5 分。逐字对应 IMF 那句 `without fully evaluating the depth or quality of that discussion`。本仓 `SECTION_MISSING` 已是同一层,再抄是复制同一个天花板。 |
| **MoneyAtlas `validate_skill.py` 18 项** | `tools/validate_skill.py:76-86` | 逐字:`check("output requires an invalidation point", re.search(r"invalidation", body, re.I) is not None)`,而 `body` 是 **SKILL.md 自己的提示词正文**。它验的是「规则手册里写了 invalidation 这个词」。**比 IMF 批评的那一层还低一级**——IMF 那个评分器至少在读产物。绝对不能抄。 |
| **Awesome-Journal `quality_scorecard.py` 的 `evidence` 维** | `tools/quality_scorecard.py:438` | `freshness_points = 6 if age_days <= 60 else (5 if age_days <= 120 else ...)` —— 名叫 evidence,实测是来源新鲜度。名字与内容不符的典型。 |
| **`Decision ledger` / `Verification floor` 模板** | Awesome-Journal,150 / 139 个包逐字相同 | 无分档、无判据、无脚本消费;且是模板批量注入的产物。与本仓已有的四环/翻转指标同构且更弱。 |

### 4.2 源码里根本不存在的(README 与调研转述夸大)

| 不采纳项 | 出处 | 实测 |
|---|---|---|
| MoneyAtlas FAILURE SYSTEM「the system flags ⚠️ INSUFFICIENT EDGE」 | `README.md:125` | **不存在「the system」**。该字符串全仓仅出现于 SKILL.md 提示词与这句自述本身;21 个 pytest 用例中 **0 个**断言那四条否决条件。 |
| MoneyAtlas「`[UNVERIFIED]` 禁止进入结论区」 | `SKILL.md:145-146` | 全仓 1 次出现,纯提示词,无测试无校验无 CI。 |
| scholar「`<80` 阻断 commit」 | `rules/quality-gates.md:76` | `/commit` 命令文件 grep **零命中**;5 个 hook 无一跑评分;全仓 34 个脚本无一计算分数。**扣分表是可迁移的评分语义,阻断阈值是不可迁移的愿望。** |
| Awesome-finance「分歧评估 Entropy」 | `prompts/report_agent.py:96` + `schema/models.py:96` | `market_entropy` 字段 3 次出现**全为声明,0 处赋值 0 处读取**;`InvestmentReport` **0 处实例化**。 |
| dual-axis「审查者漂移的备选方案」(上一轮调研的转述) | — | 穷举搜索确认**无任何抗漂移机制**;`--seed` 的用途是随机挑 skill。LLM 轴默认占最终分 50% 且照单全收。**这是"不存在",不是"读不到"。** |
| `/cost-benefit` 自动追跑 audit | `cost-benefit/SKILL.md:640-650` | `grep -rn "audit" bin tests \| wc -l` = **0**(本文重跑)。模型不调也不会有任何东西报错。 |

### 4.3 有实现但实现是错的

| 不采纳项 | 出处 | 逐字原文 + 实测 |
|---|---|---|
| MoneyAtlas 矛盾检测 | `first_principle_codex.py:96-99` | `if ">" in truths[i].statement and "<" in truths[j].statement:` —— **不比较变量名**,任意「某量 >」与「另一量 <」都判冲突。取材 2 用探针实测 `price > 100` 与 `volume < 1000` 被判为矛盾。仓库自带的反向用例恰好用了两个 `>` 绕开该假阳性。 |

### 4.4 判据方向与本仓相反,不但不采纳,还要防

| 不采纳项 | 出处 | 理由 |
|---|---|---|
| **`Don't vote by majority.` 的三条消解路径** | digital-oracle `SKILL.md:255-258` | 逐字:`- Check the time dimension first — different signals price different future windows` / `- Look for "two things happening at once"` / `- Consider "direction right but timing wrong"`。三条**全部是消解分歧**的路径,没有一条是**裁决**的路径;它没给出"解释不掉时按什么定"。在宏观里这容易滑向万能辩护:任何两个矛盾信号都能用「时间窗不同」糊过去。**本仓的「分歧与判断」环必须保留"存在真正无法调和的分歧"这一合法结局**,不要引进这三条。 |
| **`Never cite analyst opinions.`** | digital-oracle `SKILL.md:18` | 本仓 gnews 事件主通道与官方口径通道都会引用官方与媒体表述,该禁令与本仓数据栈直接冲突。 |
| **信号权重三条偏序** | digital-oracle `SKILL.md:253` | 未定义合成方式、未定义偏序冲突时的处理(高流动的间接代理 vs 低流动的直接定价)。抄进来只会多一条无判据的散文。其中唯一硬的 `volume < $100K` 与本仓数据源无关。 |
| **senior-analyst 规则 #35 的「记入 CLAUDE.md」** | `skill/council.md` 体系 | 该仓库 `ls CLAUDE.md` 报 **No such file**,`grep "从错误中学到的"` 全仓零命中——**它自己的落点不存在**。可取的只有一句概念:缺口先分类为「已定义但未执行(执行门控缺失)」与「完全未定义(定义缺失)」,两类修复策略不同(`skill/SKILL.md:495`)。这句话对本仓有用——§2.5 的发现正属于第一类(判断环已定义、执行门控缺失)——但它是认识,不是可采纳的机制。 |

## 5. 本轮读不到的

1. **econstack 124 项中未逐条复核的 97 条。** 本文只复核了 A/L/M/N 四类共 27 条;
   台账 B 的 62/60/2 分类**采自取材 1**,本文未独立重跑其分类脚本。已知一处分歧(M5)。
2. **scholar `devils-advocate` 的完整 prompt。** 取材 3 的原文在 `skills/devils-advocate/SKILL.md:1-11` 处被截断,
   只知全文 105 行、产出 `5-7 specific adversarial challenges`。台账记为 U。
3. **digital-oracle `Never cite analyst opinions.` 的「自己的破例」。** 取材 4 在该处被截断,
   本文只读到禁令原文与理由,**未读到取材 4 声称的破例证据**。故 §4.4 只按禁令与本仓冲突来判,不引用破例。
4. **econstack `cost-benefit` Step 6.5 委托给 R 包 `gb_validate()` 的实际实现。**
   `cost-benefit/SKILL.md:439` 写 `When BACKEND=greenbook: pass the appraisal spec through bridge action validate.`,
   但 greenbook R 包不在本仓库内,**该闸门究竟有多硬读不到**。台账把 A9 记为 Q/prose,
   若 `gb_validate()` 是真代码,它应升为 Q/code——**本文不做这个推断**。
5. **dual-axis LLM 轴在真实使用中的分数离散程度。** 脚本只生成 prompt 并读取人工回填的 JSON,
   不自行调用模型;离散度源码里读不到,需实跑多轮。
6. **Awesome-Journal 的 4154 个 `SKILL.md` 未逐一阅读。** 结论基于全仓 grep(`rubric` 100 命中)与抽样精读,
   存在极小概率某个未被词表命中的包藏有论证质量 rubric。
7. **Awesome-finance `build_bibliography` / `render_references_section` 是否死代码。**
   全仓只有定义、无调用点,SKILL.md 零处提及;「未被调用」是静态事实,「是否死代码」读不出来。
8. **本仓 `check_report.py` 除 `check_daily` 与 `check_weekly` 之外的部分未逐行读完。**
   本文实读了 `check_daily`(:354-430 段)与 `check_weekly`(:692-763 全文)以支撑 §2.5 与 §3.3 的判断;
   `check_verdicts` / `check_prior_period` / `parse_snapshot` 只读了签名与文档串。
   §3.1 的「零强制」结论依据是全目录 grep 无输出(判断环四个关键词在 `scripts/**.py` 中一次都不出现),
   这一条是可靠的;但**具体新增检查该挂在哪个函数上,落地前仍需通读**。

---

# 更正与降级(2026-08-14 对抗证伪,原文一律保留不删)

对本文的裁定做了一轮独立证伪,**2 条 Fatal、8 条 Major**。以下逐条更正。
先记录活下来的部分:§2.5 的本仓发现完全复现;§3.3 对数字白名单「是集合成员判定不是映射判定」的诊断复现且正确;
`8b7cad3` 的 124 项分类计数、`stooq.py:44-46`、`HEAD:330` 禁重算、senior-analyst `council.md`、
MoneyAtlas `body = text[m.end():]`、digital-oracle 全部 8 处自述数字 —— 逐字核对全部通过。

## F1(Fatal)§3.2 与 §3.1② 与本仓数字溯源不变量正面冲突,须降级

本文原写「翻转指标句同时含当前值与阈值两个数——这两个数**天然可纳入**既有的数字溯源白名单校验」。
**错。** `scripts/check_report.py:481-483` 实测 `allowed = numbers_in(snapshot_text) | numbers_in(brief_text) | ALLOWED_SMALL`;
「当前值」可溯源,而**「阈值」按定义是尚未发生的前瞻价位,不在快照里**,必然触发 `NUMBER_UNTRACEABLE`。

**更要命的是:本仓已经撞过这个坑并把结论写在源码注释里** —— `check_report.py:490-493` 逐字记着
「两条规则结构性互斥,且必然复发:SKILL 要求 trigger 绑市场可观测变量,合规的 trigger 必然带数字」。
本文 §5.8 自称「实读了 `check_daily`(:354-430 段)」,而这段注释在 **481-507**,在其自述阅读范围之外 ——
**是在没读过冲突记录的情况下断言不存在冲突。**

**处置**:§3.2 与 §3.1② 由「代价 低」降级为「**需先设计阈值豁免通道**」。落地前必须二选一:
(a) 复用 `split_brief_review_block` 的分块豁免形态,给翻转指标句单独开一个已切分的豁免段;
(b) 要求阈值表述为对快照已有数的**相对偏移**,并由脚本派生后写回 `derived`,使其成为可溯源数。

## F2(Fatal)§3.5 要求 LLM 做计算,直接违反 SKILL 禁令

本文原写「必须紧跟一个量级对比(如『相当于近 60 日波动区间的 X%』『约为上一次同类事件的 Y 倍』)」。
`skills/fx-daily-report/SKILL.md:307-308` 逐字:「数字只准逐字抄自要点表……**你自己禁止计算、估算、回忆任何行情数字**」。
比值必须由 LLM 算,且算出的数不在快照 → 同时触发 `NUMBER_UNTRACEABLE`。本文把代价写成「低」,冲突一字未提。

**处置**:**反转责任方**。锚定量必须由采集脚本预先算好落进 `derived`(如 `derived.<币种>.range_60d_pct`),
LLM 只逐字抄。这样它才与「结论由脚本给出」同族;否则不可采纳。

## M1(Major)分类口径与施行不一致 —— 本文犯了它指控别人的那类错

本文把 N 类定义为「文本写成规则的样子,但源码里没有任何东西对它求值」,又另设正交字段
`backing`(`code` / `prose`)。**这两句话把 N 定义成了 `backing == prose`。**
实跑:`cut -f4 ledger.tsv | sort | uniq -c` → `N=8`;`cut -f5` → `prose=40`。
**32 行 prose 被判成了 Q 或 E,尽管按写下来的定义它们全都是 N。**

于是头条数「质量 20/53 = 37.7%」在**自身定义下**应归零到 **5 条(仅 code 背书的 Q)**。

**处置**:取消 N 类,只保留 Q/E × code/prose 四格,直接报 **Q∧code = 5/53 = 9.4%**;
或把 N 重定义为「项目**自称**被强制、实测无强制」的 claim-vs-reality gap。任一种都要重跑 §2.5 的四个数。

## M2(Major)Q/E 边界按感觉划,「一条质量检查都没有」这条证据作废

本文把 M5 由存在性升为质量,理由是「它明写 `not just acknowledged`……是对同一节内容的强弱分级」,
而 §2.1 的 Q 定义里**根本没有「强弱分级」这一条**。实跑
`grep -nE '^\| [A-R][0-9]+ \|' EA_HIST.md | grep -ciE 'not just|rather than|not merely'` → **9**,
其中 `:330` 的 M3 与 M5 同一文件、同一类目、同一「not just X」形态,却被留在存在性。

于是本文的头条读数「**L 类 6/6 全是存在性、M 类 5/6 存在性……在源码层一条质量检查都没有。
这是 IMF WP/26/35 那条结论在开源实现里的直接复现证据**」——**按本文自己的判据就是错的**,该证据作废。

## M3(Major)E3 的判定依据不在它引的行里,「全仓唯一」被证伪

本文称 `rules/quality-gates.md:61-68` 是「全仓唯一要求两份产物互相对照的规则」。
逐行核对:**那是一张纯容差数字表,一个字都没说要比对什么**。真正说了比对的是
`rules/single-source-of-truth.md:26`。

## 未受影响、且仍是本轮最有行动价值的一条

```
$ grep -rn "关键假设\|替代解释\|翻转指标\|失效条件" scripts/ --include=*.py
（无输出)
```

**我们自己刚落地的判断环,在 `scripts/` 下零强制。** SKILL.md:262-272 写得很细,`check_report.py` 763 行一次都没提。
按本文台账口径,**我们自己的判断环目前也是 N 类(非检查)**,与 econstack `/econ-audit`、scholar `<80 阻断` 同型 ——
这正是本轮从社区身上照出来的同一个病。
