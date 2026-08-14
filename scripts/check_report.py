#!/usr/bin/env python3
"""报告校验器:结构 + 数字溯源(文本级逐字比对)。
daily : check_report.py <report.md> <snapshot.json> --brief <brief.md>
        --prior <上一份日报.md> --decision-log <日志.jsonl> [--mode daily]
        (三个溯源入参**必须给**;缺一个即 rc=2 并印出可复制的完整命令行)
weekly: check_report.py <weekly.md> --mode weekly --digest <digest.json>
        --daily <当周日报.md> …(`--daily` 可重复;位置参数快照会被拒收)
退出码 0=合规,1=违规(逐条打印),2=用法错误/输入不可读/快照损坏。"""
import argparse
import datetime
import json
import re
import shlex
import sys

# 复盘材料块的块头:**唯一事实源是产出方 `scripts/review.py`**,这里只导入。
# 两处各写一遍必然漂移(本仓库已栽过多次),而漂移后豁免要么整段失效、要么
# 整段过宽,两种都静默。`scripts.review` 导入期无副作用(只算了一个 ROOT
# 路径常量,不读文件、不写文件、不解析 argv),故直接导入是安全的。
# 两条分支对应两种运行形态:包内导入(测试、`python3 -m`)与
# `python3 scripts/check_report.py` 直跑(此时 sys.path[0] 就是 scripts/)。
# **这里不引入 `os`** —— 校验器不读环境变量是不变量,由
# VerdictGateIsOrthogonalToTheCheckedObjectTest 的 AST 断言钉住。
try:
    from scripts import claims
    from scripts.claims import unchanged_ref_note
    from scripts.review import DECLARATION_FMT, FIRST_RUN_LINE, MATERIAL_FMT
    from scripts.review import PENDING_FMT
    from scripts.review import REVIEW_BLOCK_HEADING
except ImportError:                                  # pragma: no cover - 直跑分支
    import claims
    from claims import unchanged_ref_note
    from review import DECLARATION_FMT, FIRST_RUN_LINE, MATERIAL_FMT
    from review import PENDING_FMT
    from review import REVIEW_BLOCK_HEADING

CURRENCIES = ["USD", "EUR", "PHP", "THB", "BRL"]
MAX_SUMMARY_ITEMS = 6
MAX_SECTION_CJK = 330        # spec"约 300 中文字"+10% 容差
DATE_RE = re.compile(
    r"\d{4}-W\d{2}|\d{4}-\d{2}-\d{2}|\d{4}\s*年|\d{1,2}\s*月\s*\d{1,2}\s*日|\d{1,2}\s*月")
NUM_RE = re.compile(r"\d+(?:\.\d+)?")
CJK_RE = re.compile(r"[一-鿿]")
ALLOWED_SMALL = {str(i) for i in range(0, 13)}   # 序数/条数/月份类小整数
LIST_ITEM_RE = re.compile(r"\s*(?:[-*]|\d+[.、])\s+\S")
# ---- 复盘材料块的行式样:照 `scripts/review.py` 的**实际输出**枚举 ----
# 实跑抄下来的四种(briefs/2026-08-{10,11,13}-brief.md + review.py main()):
#   ``                                                    块前后各一个空行
#   `## 复盘材料(scripts/review.py 生成,勿手改)`        块头(导入的常量)
#   `- 首次运行,无历史观点可复盘`
#   `- 上一运行日(2026-08-10)无未复盘观点`
#   `- PHP | 观点日 2026-08-12 | 情景: … | 触发条件: … | 关注方向: down`
#   ` | 汇率 61.178→61.325 | 方向核对: 未命中`
#   第六段另有一种形态:两侧定盘日期相同时,写 `review.unchanged_ref_note`
#     给出的那一句(带定盘日期)
# 情景/触发条件是 LLM 文本,可能含 `|`(review.flat 只扁平化换行、不转义竖线),
# 故这两段用 `.*` 靠尾部固定串回溯定位;其余每一段都钉死。
# **不匹配 = 照查**(失败关闭):式样收紧只会多查,不会漏查。
#
# 「参考价未更新」那一段的措辞**这里一个字都不重写**:它由产出方
# `review.unchanged_ref_note` 给出,本文件只把其中的定盘日期换成日期式样。
# 理由与 REVIEW_BLOCK_HEADING 同规矩 —— 两处各写一遍必然漂移,而漂移的后果
# (真行一条都认不出、「要点表 ⊆ 快照」那一层的豁免整块失效)不会有人发现。实测就
# 踩过一脚同型的:review.py 那两处括号是 **ASCII** `()`,手抄的正则没转义,
# 式样反而要求「没有括号」。从产出方 re.escape 推出来,括号是全角还是 ASCII
# 都自动对上,这类手抄错误不再可能发生。
_REF_DATE_SLOT = "0000-00-00"                        # re.escape 后再换成日期式样
UNCHANGED_REF_NOTE_PAT = re.escape(unchanged_ref_note(_REF_DATE_SLOT)).replace(
    re.escape(_REF_DATE_SLOT), r"\d{4}-\d{2}-\d{2}")
# ---- 冻结的历史字面量:`cdec7e4` **之前**那一版 review.py 的产出措辞 ----
# 上一段说的「措辞一个字都不重写」管的是**当前**措辞,这一条不归它管:产出方
# 今后一个字都不会再吐出这个串,它按定义永远不变,因此不是会漂移的第二份拷贝。
# 留它只为一件事:`briefs/2026-08-14-brief.md` 那四条材料行是改措辞前产出的,
# 存量产物是既成事实。改措辞当天它们就整体落到豁免式样之外,被「要点表 ⊆ 快照」
# 当成 LLM 手写行照查,行内 08-13 的日涨跌被判 BRIEF_NUMBER_UNTRACEABLE —— 与
# PRIOR_PERIOD_SKIPPED_NO_SECTION 认旧格式日报是同一条原则:
# **存量产物是既成事实,识别器必须认得历史格式。**
# 两种措辞**各自精确匹配**,绝不合并成一个宽式样(比如把括号里改成 `.*`):
# 那等于把「伪造一整条格式完整的复盘行」的成本降到「在那一段写任意话」。
# tests/test_review.py::LegacyUnchangedRefNoteTest 三面钉住:旧行认得、新行仍
# 认得、这个冻结值不得是当前措辞(否则就是借「历史遗留」之名手抄当前式样)。
LEGACY_UNCHANGED_REF_NOTE = "参考价未更新(非工作日)"
LEGACY_REVIEW_MATERIAL_RE = re.compile(
    r"- [A-Z]{3} \| 观点日 \d{4}-\d{2}-\d{2} \| 情景: .* \| 触发条件: .*"
    r" \| 关注方向: [^|]* \| (?:汇率 (?:None|[-+0-9.eE]+)→(?:None|[-+0-9.eE]+)"
    r"|" + UNCHANGED_REF_NOTE_PAT +
    r"|" + re.escape(LEGACY_UNCHANGED_REF_NOTE) +
    r") \| 方向核对: (?:命中|未命中|无法判定)")
# ---- 当前式样:两条都**从产出方的格式串推出来**,这里不手抄一个字 ----
# `MATERIAL_FMT` / `DECLARATION_FMT` 的唯一事实源在 `scripts/review.py`,
# 四档词表的唯一事实源在 `scripts/claims.py`。把槽位填成一个不可能自然出现的
# 记号、re.escape 之后再换成式样,分隔符、括号宽度与全角标点就都自动对上 ——
# 这正是上一轮手抄正则漏掉 ASCII 括号转义那个缺陷不再可能复发的原因。
_SLOT = "\x01%d\x01"
_SLOTS = tuple(_SLOT % i for i in range(6))
_COUNT_SLOT = 424242424242
# 结论词只取"可判"的三档:`未到期` 的条目按定义**不出材料行**(它还没到该看
# 的时候),把它放进式样等于承认脚本会为未到期的观点写复盘。
_CONCLUSIVE = tuple(s for s in claims.STATUSES if s != claims.STATUS_PENDING)
_STATUS_PAT = "(?:%s)" % "|".join(re.escape(s) for s in _CONCLUSIVE)
# 复盘句由 `claims.resolve_claim` 经 `verdicts.join_verdict` 拼出,形如
# `2026-08-10 EUR 命中(时限 T+3、…)`。caveat 段用 `[^|]*` 而不是 `.*`:
# 脚本产出的句子里不会有竖线,放宽到 `.*` 就等于把「伪造一整条格式完整的
# 复盘行」的成本降到「在那一段写任意话」。
_SENTENCE_PAT = (r"\d{4}-\d{2}-\d{2} [A-Z]{3} " + _STATUS_PAT
                 + r"(?:\([^|]*\))?")
REVIEW_MATERIAL_RE = re.compile(
    re.escape(MATERIAL_FMT % _SLOTS)
    .replace(re.escape(_SLOTS[0]), r"[A-Z]{3}")
    .replace(re.escape(_SLOTS[1]), r"\d{4}-\d{2}-\d{2}")
    # 情景/触发条件是 LLM 文本,可能含 `|`(review.flat 只扁平化换行、不转义
    # 竖线),故这两段用 `.*` 靠尾部固定串回溯定位;其余每一段都钉死。
    .replace(re.escape(_SLOTS[2]), r".*")
    .replace(re.escape(_SLOTS[3]), r".*")
    .replace(re.escape(_SLOTS[4]), _SENTENCE_PAT)
    .replace(re.escape(_SLOTS[5]), _STATUS_PAT))
# 顺延登记行:与结论行同样从产出方的格式串推出,唯一的差别是句末那一档
# **只能是「未到期」**,而且行尾没有「结论」段 —— 时限没到就不该有结论,
# 式样上放宽这一点等于允许脚本给未到期的观点写复盘。
REVIEW_PENDING_RE = re.compile(
    re.escape(PENDING_FMT % _SLOTS[:5])
    .replace(re.escape(_SLOTS[0]), r"[A-Z]{3}")
    .replace(re.escape(_SLOTS[1]), r"\d{4}-\d{2}-\d{2}")
    .replace(re.escape(_SLOTS[2]), r".*")
    .replace(re.escape(_SLOTS[3]), r".*")
    .replace(re.escape(_SLOTS[4]),
             r"\d{4}-\d{2}-\d{2} [A-Z]{3} " + re.escape(claims.STATUS_PENDING)
             + r"(?:\([^|]*\))?"))
REVIEW_DECLARATION_RE = re.compile(
    re.escape(DECLARATION_FMT % ((_COUNT_SLOT,) * 4))
    .replace(re.escape(str(_COUNT_SLOT)), r"\d+"))
REVIEW_LINE_RES = (
    re.compile(r"\s*"),                                  # 块内空行
    re.compile(re.escape(FIRST_RUN_LINE)),
    REVIEW_DECLARATION_RE,
    REVIEW_MATERIAL_RE,
    REVIEW_PENDING_RE,
    # ---- 冻结的历史式样 ----
    # 产出方今后一个字都不会再吐出这两种行,它们按定义永远不变,因此不是会
    # 漂移的第二份拷贝。留着只为一件事:briefs/2026-08-{07,08,09}-brief.md 的
    # 材料行是改格式前产出的,**存量产物是既成事实,识别器必须认得历史格式**
    # (与 PRIOR_PERIOD_SKIPPED_NO_SECTION 认旧格式日报同一条原则)。
    re.compile(r"- 上一运行日\(\d{4}-\d{2}-\d{2}\)无未复盘观点"),
    LEGACY_REVIEW_MATERIAL_RE,
)
# 周报复盘汇总必须出现的结论词。**唯一事实源是 `scripts/claims.STATUSES`** ——
# 手抄一份的话,四档改名或增减时这里不会红,而周报会继续只报旧的三档。
# 「未到期」在这张表里是本轮的要害:不写它,读者就还是只看得到「无法判定」,
# 病灶原样保留。
REVIEW_TOKENS = claims.STATUSES
MAX_THEME_ITEMS = 3
WEEKLY_SECTIONS = ["本周主线", "各币种", "复盘汇总", "下周关注", "缺漏汇总"]
COVERAGE_RE = re.compile(r"覆盖日报[::]\s*(\d+)\s*份")
DATE_HEADING_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")
# 结论句字段名**显式枚举**,禁止按 *verdict* 模式扫:digest 顶层的 `verdicts`
# 是计数 dict、`verdict_details` 是 list,模式匹配会把它们扫进字符串比对,
# 然后在 `x in report` 处 TypeError 或静默跳过。
VERDICT_FIELDS_EVENTS = ("articles_verdict", "official_verdict")
VERDICT_FIELDS_RATES = ("fixings_verdict",)
VERDICT_FIELD_DAILY = ("events_verdict",)
# derive.SCHEMA_VERSION 达到此值,才保证快照 derived.events 带结论句字段。
# 判据取 schema 版本而非"这个键在不在":后者会让**新代码产出却漏写该字段**
# 的缺陷与存量快照完全同形,静默通过。
DERIVED_VERDICT_SCHEMA = 2

# ---- 违规处置文案:**唯一事实源在这里,SKILL 不再复述** ----
# 此前两份 SKILL 各写了一遍处置表。散文里的第二份可以被整体反转,而反转的
# 措辞空间无界 —— T8 复验实测三条绕过全部存活:①锚点整句一字不动、句尾追加
# 「但这条其实也是脚本缺陷,照抄只是走个形式」;②bullet 一字不动、在违规节
# 末尾追加「统一口径:本节所有违规码都按脚本缺陷处理」(bullet 级断言结构上
# 看不见它);③把 bullet 拆成两条、第一条标注「旧口径,已废弃」并原样保留
# 锚点整句,第二条写反向口径(非贪婪正则只取首个匹配)。
# 另有一条决定性实测:`grep -rn "改报告|改周报" scripts/` 零命中 —— 那段处置
# 文本没有任何运行时角色,纯粹是提示词里的散文。
# 于是改成:校验器发码时自己把处置打出来。守的东西从"散文里有没有某句话"
# 变成"脚本输出里有没有这句话",后者可被精确断言。
#
# ---- 上一段最后半句「且没有第二份可反转」**已被证伪**,如实记在这里 ----
# T8b 复验对这套修法做了四次改写形态、约 15 条实证绕过,协调者据此裁定:
#   **子串/段落哨兵能守住的是「这句话有没有被删改」,守不住「附近有没有
#   一句话否定它」。反转不需要第二份拷贝,只需要相邻。**
# 段级断言看不见节末追加、bullet 级看不见段内追加、行级看不见相邻行追加、
# SKILL 节内可原地长回一份反向表、节外可用原措辞 —— 每次改写只是把盲区
# 搬了个地方。这一类(下称 A 类)**结构上封不住**,已封为文档化边界,不再
# 为它加哨兵。
# 并且:「把处置收归校验器就没东西可反转」这个判断不但被证伪,**净暴露面
# 还变大了** —— 处置文案搬进脚本后,它同时成了脚本里的可变异对象
# (M12 打的就是它),而 SKILL 那一侧的指向句仍然可以被相邻文字否定
# (M13 打的是它)。这不是一次成功的收口,是一次把风险换了个地方的改法。
#
# 能守住的是**有界**的那部分,本轮补的都在这一侧:
#   ① 码 → 处置的**逐码**对应(CheckerPrintsItsOwnDispositionTest):
#      两串各自 assertEqual 逐字钉死、必须出现在违规行**结尾**、且每个码
#      带的必须是它自己那一条、不得同时出现另一条。
#      (只断言"带了某条处置"时,把**其余 5 处** DISPOSITION_SCRIPT_BUG 换成
#      DISPOSITION_QUOTE 照样全量 OK —— 校验器于是亲口叫运维去人工粉饰一个
#      产出端缺陷。口径与测试侧那句一致:两个常量在本文件里**共 7 个使用点**
#      (DISPOSITION_SCRIPT_BUG 6 处 + DISPOSITION_QUOTE 1 处),T8b 之前逐字
#      钉死的只有 NOT_QUOTED 与 ABSENT 两处,可对调的是**其余 5 处**。
#      T8d 更正:这里此前写「5 个 DISPOSITION_SCRIPT_BUG 使用点」,实为 6 个。
#      复跑:`grep -n "DISPOSITION_SCRIPT_BUG\|DISPOSITION_QUOTE"
#      scripts/check_report.py` —— 去掉本段注释与两行定义,余下 7 行即
#      7 个使用点。)
#   ② 码清单冻结:新增码不入表就红,不再自称"自动被守"。
# 改这里的文案就必须同时改测试里的期望值 —— 显式动作、进 diff。
#
# ---- 本文件**不读环境变量**,这是不变量,不是习惯 ----
# 实测(B8):在模块加载期用一个环境变量翻转常量,测试进程天然取到未翻转
# 的那一支 —— 全量全绿,而真 CLI 在导出该变量后行为变了。环境是**被查对象
# 与运维都够得着、测试进程够不着**的旋钮,闸门读它就等于把钥匙交出去。
# 由 VerdictGateIsOrthogonalToTheCheckedObjectTest 的 AST 静态断言钉住:
# 不得出现 environ/getenv 等名字,也不得 import os/posix/nt。同类还有
# 三条正交不变量:换文件名、给报告/快照/聚合文件追加任意未知字段与注释、
# 清空环境 —— 判定必须一字不变(V7/V8/V12 三条真绕过就死在这里)。
DISPOSITION_QUOTE = ("处置:把上面「期望原文」那一句整句抄进该币种节,"
                     "一个字符都不改;这一条改报告即可,不要动脚本")
DISPOSITION_SCRIPT_BUG = ("处置:这是脚本缺陷,改报告没用;"
                          "重跑产出这份快照/聚合文件的那一步,仍复现就报 bug")
DISPOSITION_PRIOR_PERIOD = ("处置:写明本期相对上期究竟哪里变了;"
                            "若确无变化,写明为什么没变")
DISPOSITION_RING = ("处置:把没写的那件补进该币种节的「分歧与判断」环;"
                    "三件都是不可压缩项,字数紧张时压缩「驱动」与「是否已反映」"
                    "腾字数,不得删掉其中任何一件")
DISPOSITION_FLIP = ("处置:翻转指标写「什么一旦出现就改判」(可观测量带 T+N),"
                    "失效条件写「什么没发生就作废」;二者语义不同,"
                    "不得把后者换个说法当前者交差")
DISPOSITION_ANCHOR = ("处置:在关键假设句里引一个来自快照或要点表的**当前值**;"
                      "不要写阈值 —— 阈值是尚未发生的前瞻价位、不在快照里,"
                      "写进去会被 NUMBER_UNTRACEABLE 当场拦下")
DISPOSITION_WRONG_SECTION = ("处置:换成该币种自己快照切片里的数;"
                             "确是跨币种比较时,在**同一节内**点名那个币种"
                             "(写「比索 61.325」,不要光写 61.325)")
DISPOSITION_SUMMARY_BODY = ("处置:执行摘要只复述正文写过的数;"
                            "要保留这个数就先把它写进对应的币种节/速览/复盘/"
                            "缺漏节,不得只在摘要里出现一次")
DISPOSITION_SUMMARY_CURRENCY = ("处置:在**这一条摘要 bullet 里**点名这个数"
                                "属于哪个币种(写「雷亚尔 5.1049」,"
                                "不要光写 5.1049);"
                                "确实说的是别的币种就换成本条点名的那个币种的数")
DISPOSITION_DECISION_TRIGGER = ("处置:先判哪一份是旧的 —— SKILL 第 387 行"
                                "写明日志由速览表「条件方向」整理而来,表是源、"
                                "日志是抄件;改了表没回写就用 "
                                "`scripts/log_decision.py` 回填日志,"
                                "不要反过来改表")
DISPOSITION_DECISION_CLAIM = ("处置:结构化观点里你只做两件事 —— **抄**与**选**。"
                              "阈值逐字取自速览表那一格已有的那个数(一位小数都"
                              "不许改),时限片段逐字取自同一格;比较方向与字段名"
                              "从固定枚举里选。散文里确实没有可机器求值的阈值时,"
                              "把 legs 写成 null 并在 unstructurable_reason 里"
                              "说明是哪一句 —— **不得编造阈值**;"
                              "改用 `scripts/log_decision.py set-claim` 回填")
DISPOSITION_REVIEW_QUOTE = ("处置:把要点表复盘材料里那条 `复盘句: ` 后面的"
                            "**整句**原样抄进正文的复盘节(一个字符都不改),"
                            "再在它后面补一句你自己的说明;结论词只有这一个"
                            "来源,不得改写、不得只抄大意、也不得自己另写一个")
DISPOSITION_AMBIGUOUS = ("处置:把重名的小节标题改成互不包含的标题,"
                         "或合并成一节;校验器**不猜**哪一节是正主,"
                         "这一条不改,依赖该节的检查就一直不执行")
# **两个降级码(VERDICT_SKIPPED_NO_DERIVED / VERDICT_SKIPPED_LEGACY)的处置
# 仍留在 SKILL,这是有意的**,不是漏改。它们的处置分两支,判别标准是"采集
# 窗口是否还覆盖 DATE" —— 校验器不知道窗口边界(那在 collect/events.py 的
# GNEWS_WINDOW_H 与 GDELT timespan 里,且与运行时刻有关),写不出可执行的
# 单一处置。凡是脚本自己说得出的才搬进来;说不出的搬进来只会变成第三份
# 会漂移的拷贝。守它们的是 SkippedCodeDispositionTest。


# ---- ICD 203 第 7 条的机器强制:跨期不得逐字重复 ----
# 情报体系的强制评审标准点名 `daily crisis reports`:周期性产品必须说明本期
# 判断相对上期有何变化,**且不得使用模板套话**。实测缺陷与它一一对应:
# 三个币种的实际利率四天一字未变,同一句话写了四遍。
# **为什么只加这一条**:调研实测「用 LLM 自动审计报告论证质量」不可行 ——
# IMF 那套评分器按关键词与章节存在性打分,`without fully evaluating the depth
# or quality of that discussion`,于是"填满的四环"会被读成"有深度"。
# 跨期逐字重复是少数**能机械判定、且直接对应真实缺陷**的质量信号,
# 所以这里只装这一条,不顺手加别的码。
PRIOR_PERIOD_SECTION_KEY = "本期相对上期"
# 句末标点(全角与半角)与换行都是句界。**刻意不切逗号**:切得越碎,短片段
# 跨期偶然相同的概率越高,而本码的判据是"过半",误报会直接把它变成噪声。
# 句末标点**留在句子里**(用 findall 而不是 split):判据是"逐字相同",
# 而违规信息要把重复的**原文**打出来 —— 切掉标点的那份不是原文,读者拿它去
# 报告里搜还得自己补一个字。
SENTENCE_RE = re.compile(r"[^。;!?;!?\n]+[。;!?;!?]*")


# ---- 判断环三件的标签。措辞与 skills/fx-daily-report/SKILL.md 的模板同串 ----
ASSUMPTION_LABEL = "关键假设"
FLIP_LABEL = "翻转指标"
RING_LABELS = (ASSUMPTION_LABEL, "替代解释", FLIP_LABEL)
# 失效条件在币种节里有两种落法:显式的「失效条件」,以及关键假设那一环
# 按 SKILL 要求写的后半句「不成立时/则……」。两种都要认 —— 只认前者时,
# 本仓实际产出的报告(逐字见 reports/daily/2026-08-14.md)一条都不匹配,
# 整个 ② 会变成永不触发的空码。
# 「作废」是本轮补的第三种落法。实测(reports/daily/2026-08-13.md 五个币种节)
# 报告写的是「若 4.75 上调,负利差被修复,本判断**作废**。」—— 语义上就是失效
# 条件,措辞不在表里,于是 ② 在那一份上 5/5 判不出、一次都没执行。
# 与 e74134d「识别器认历史措辞」同一形制:**识别器必须认得产出端实际写出来的
# 措辞**,否则码只是看上去存在。补它不放宽任何阈值 —— 多认一种写法只会让 ②
# 多跑几次,不会让任何一条本该红的变绿(实测:补前后在五份产物上新增违规 0 条)。
INVALIDATION_LABELS = ("失效条件", "不成立时", "不成立则", "不成立", "作废")
# 「去除标点与空白」:`\W` 在 unicode 模式下把中英文标点、括号、`*`、`+`、
# 小数点一并去掉,CJK 与字母数字是 word 字符,原样保留。两边同样处理,
# 所以它只影响"标点算不算差异",不影响谁和谁比。
_RING_STRIP_RE = re.compile(r"[\s\W_]+", re.UNICODE)


def split_sentences(text):
    """按句切分,返回去掉首尾空白后的非空句子(**顺序保留**)。

    保留列表标记(`- USD:…`)不做规范化:判据是"逐字重复",规范化会引入
    "改了标记就算改了内容"与"只改标记也算重复"两种争议,而两种都无谓 ——
    真实的套话是整行照抄。
    """
    return [s for s in (p.strip() for p in SENTENCE_RE.findall(text)) if s]


def sections(md):
    out, cur, buf = [], None, []
    for line in md.splitlines():
        if line.startswith("## "):
            if cur is not None:
                out.append((cur, "\n".join(buf)))
            cur, buf = line[3:].strip(), []
        elif cur is not None:
            buf.append(line)
    if cur is not None:
        out.append((cur, "\n".join(buf)))
    return out


def section_hits(secs, key):
    """该键匹配到的**全部**小节。节定位的唯一事实源,`find_section` 只是它的
    「必须恰好一个」包装 —— 两处各写一遍匹配规则必然漂移。"""
    return [(h, b) for h, b in secs if key in h]


def find_section(secs, key):
    """**恰好一个**匹配才返回 (标题, 正文);0 个与 ≥2 个都返回 None。

    ---- ≥2 个返回 None 是**失败关闭**,不是顺手的健壮性 ----
    修前这里取**首个**匹配。于是报告里只要出现一个重名小节,判断环三码与
    数字归属两码定位到的就是错的那一节,五个码**全部悄悄不跑**,输出仍是
    `CHECK PASSED`。**在修掉它之前,这五个码的强制力等于一行报告编辑。**
    决定性实测(本轮,fixture 逐字见 tests 的 `amb_report`):同一份报告
    加两行占位标题(`## 执行摘要(草稿,占位)` 与 `## 菲律宾比索(PHP)——占位`),
    五码命中由 {①1 ②1 ③1 ④1 ⑤1} 变成 {①1 ②0 ③0 ④0 ⑤0} —— ②③④⑤ 全灭,
    而剩下那条 ① 是对着「占位。」那一行的**假**违规,stdout **零声明**。

    修法按**不变量**做,不是在每个调用点加一句提示:**唯一的解析入口**对
    ≥2 个匹配返回 None,任何调用点都拿不到"第一个",失败关闭因此是结构性的。
    响亮的那一半在调用点:`ambiguity_violations` 把 `SECTION_AMBIGUOUS` 打成
    违规,所以"关掉了检查"不会以 rc=0 收场。

    **误报成本先复算再改**(本轮实测,不是抄对抗报告的数):
    8 份日报 × 10 个日报键、8 份要点表 × 6 个要点表键、1 份周报 × 5 个周报键,
    多重匹配**共 0 次**。唯一化是零成本的。

    0 个匹配**沿用既有语义**(调用点报 `SECTION_MISSING`),这一支一字未改。
    """
    hits = section_hits(secs, key)
    return hits[0] if len(hits) == 1 else None


def ambiguous_sections(secs, keys):
    """{键: [重名标题]},只含匹配 ≥2 个的键;顺序按 `keys` 给的顺序。"""
    out = {}
    for key in keys:
        hits = section_hits(secs, key)
        if len(hits) > 1:
            out[key] = [h for h, _ in hits]
    return out


def ambiguity_violations(secs, keys, label):
    """把节定位歧义打成违规行。**重名 ≠ 缺失**,两者的处置完全不同,
    所以它不复用 `SECTION_MISSING`。

    标题原文一起打出来:只说"有重名"不可操作 —— 读者得自己回报告里数标题。
    """
    return ["SECTION_AMBIGUOUS: %s有 %d 个小节标题含「%s」(%s);"
            "节定位不唯一,依赖该节的检查本轮全部按失败关闭、未执行;%s"
            % (label, len(heads), key,
               "、".join("「%s」" % h for h in heads), DISPOSITION_AMBIGUOUS)
            for key, heads in ambiguous_sections(secs, keys).items()]


def numbers_in(text):
    return set(NUM_RE.findall(DATE_RE.sub(" ", text)))


def list_items(body):
    return [line for line in body.splitlines() if LIST_ITEM_RE.match(line)]


def check_prior_period(report, prior_text, notes=None, ambiguous=()):
    """「本期相对上期的变化」节不得与**上一份日报**的同节逐字重复。

    三态,互为对方的静默失败形态:

    - 两份都有该节 → **逐句**比对,整句逐字相同的句子数 ≥ 该节句数的一半
      即 PRIOR_PERIOD_BOILERPLATE。逐句(而不是整节)是要害:实测缺陷的
      形状是"几个币种照抄上期、其余几个真的更新了",整节比对对它完全不敏感。
    - 当前报告**缺**该节 → PRIOR_PERIOD_SECTION_MISSING。整节删掉是绕过本
      不变量最省事的一条路(没有句子就没有重复),必须是违规而不是跳过。
    - 上一份**缺**该节 → 打印跳过声明、不判违规。上一份可能是本次改造之前
      产出的旧格式日报,那不是当前这份报告的缺陷。

    notes : **出参**,同 check_daily。跳过声明必须打印 ——「跳过」与「通过」
            在输出上不可分辨,正是这一族检查要消灭的形态。

    ambiguous : 当前报告里已判为节定位歧义的键集合。含本节的键时整条不判 ——
            `SECTION_AMBIGUOUS` 已经把它打红了,再报一条
            `PRIOR_PERIOD_SECTION_MISSING`(而报告里明明有两节)是自相矛盾。
            **上一份日报**那一侧的歧义在这里单独判:往昨天的报告里塞两个同名
            节,就等于关掉今天的跨期重复检查,那条路必须也是失败关闭。
    """
    v = []
    if PRIOR_PERIOD_SECTION_KEY in (ambiguous or ()):
        return v
    cur = find_section(sections(report), PRIOR_PERIOD_SECTION_KEY)
    if cur is None:
        return ["PRIOR_PERIOD_SECTION_MISSING: 缺少「%s的变化」节"
                "(周期性产品必须说明本期判断相对上期有何变化);%s"
                % (PRIOR_PERIOD_SECTION_KEY, DISPOSITION_PRIOR_PERIOD)]
    prior_secs = sections(prior_text)
    amb = ambiguity_violations(prior_secs, (PRIOR_PERIOD_SECTION_KEY,),
                               "上一份日报")
    if amb:
        return amb
    prior = find_section(prior_secs, PRIOR_PERIOD_SECTION_KEY)
    if prior is None:
        if notes is not None:
            notes.append("PRIOR_PERIOD_SKIPPED_NO_SECTION: 上一份日报没有"
                         "「%s的变化」节(可能是改造前的旧格式),本次未比对"
                         % PRIOR_PERIOD_SECTION_KEY)
        return v
    cur_sents = split_sentences(cur[1])
    prior_sents = set(split_sentences(prior[1]))
    repeated = [s for s in cur_sents if s in prior_sents]
    # `cur_sents` 为空时 0 ≥ 0 恒真 —— 不加这个门,空节会假报违规,
    # 而空节该由谁管不在本码的射程内(本码只判"抄没抄上期")
    if cur_sents and len(repeated) * 2 >= len(cur_sents):
        v.append("PRIOR_PERIOD_BOILERPLATE: 「%s的变化」节 %d/%d 句与上一份"
                 "日报逐字相同(过半即违规);重复的原文:%s;%s"
                 % (PRIOR_PERIOD_SECTION_KEY, len(repeated), len(cur_sents),
                    "、".join("「%s」" % s for s in repeated),
                    DISPOSITION_PRIOR_PERIOD))
    return v


def is_generated_review_line(line):
    """该行是否为 `scripts/review.py` 生成的复盘材料行(块头与块内空行也算)。"""
    if line == REVIEW_BLOCK_HEADING:
        return True
    return any(r.fullmatch(line) for r in REVIEW_LINE_RES)


def split_brief_review_block(brief_text):
    """把要点表切成「纳入数字溯源的行」与「豁免的复盘材料行」。

    返回 (traced_lines, exempt_lines, heading_count)。切法与三态:

    - 块头 0 次:整份要点表照查,豁免不存在 —— 与本开关的既有行为一字不差。
    - 块头 1 次:块头**之前**是 LLM 手写部分,一个字不改照查;块头**之后**
      只豁免匹配 review.py 行式样的行,**不匹配的行照查**。伪造成本因此是
      「伪造一整条格式完整的复盘行」,而不是「写一行假块头」。
    - 块头 ≥2 次:挑一个是静默决策,而被查方正好能靠多写一个块头把选择权
      拿过去 —— 判为违规,且**一行都不豁免**(失败关闭)。
    """
    lines = brief_text.splitlines()
    heads = [i for i, ln in enumerate(lines) if ln == REVIEW_BLOCK_HEADING]
    if len(heads) != 1:
        return lines, [], len(heads)
    start = heads[0]
    traced = list(lines[:start])
    exempt = []
    for ln in lines[start:]:
        (exempt if is_generated_review_line(ln) else traced).append(ln)
    return traced, exempt, 1


def parse_snapshot(snapshot_text):
    """解析并结构校验快照文本(外部数据,可能损坏)。

    返回 (snap, problems):snap 为解析出的 dict(顶层不是对象时为 None),
    problems 为结构问题描述列表。main 层据此 rc=2 响亮失败;
    check_daily 直调时逐条记为 SNAPSHOT_MALFORMED 违规——两层都不裸崩。
    """
    try:
        snap = json.loads(snapshot_text)
    except (ValueError, RecursionError) as e:
        return None, ["快照 JSON 无法解析: %s" % e]
    if not isinstance(snap, dict):
        return None, ["快照顶层应为对象,实为 %s" % type(snap).__name__]
    problems = []
    gaps = snap.get("gaps", [])
    if not isinstance(gaps, list):
        problems.append("快照 gaps 字段应为列表,实为 %s" % type(gaps).__name__)
    else:
        for i, g in enumerate(gaps):
            if not isinstance(g, dict):
                problems.append("快照 gaps[%d] 应为对象,实为 %s" % (i, type(g).__name__))
    return snap, problems


def check_verdicts(report, container, fields, covered, required, label):
    """结论句逐字引用检查。**日报与周报共用这一份判定**,两个调用点只提供
    「到哪个容器取哪些字段」—— 判定逻辑复制两份后漂移是本仓库栽过的坑
    (见 scripts/fixings.py);与 events.landed_count_capped 同构。

    container : {币种: {字段: 句子}};非 dict 一律返回空结果 —— 谓词不判结构。
                **注意目前没有别处兜底**:容器缺失/类型错时本检查静默失效,
                调用方必须自己确认容器存在(T4 已在 check_weekly 加 isinstance
                门并出 VERDICT_CONTAINER_MALFORMED)
    fields    : 要检查的字段名元组(显式枚举,不按名字模式扫)
    covered   : 报告已覆盖的币种集合;不在其中者跳过,由 SECTION_MISSING /
                CURRENCY_MISSING 单独报告 —— 同一处缺失不得产生两条违规
    required  : 该来源的 schema 是否保证这些字段存在
    label     : 违规信息里的来源前缀,如 "digest.events" / "derived.events"

    返回 (violations, skipped_currencies)。**required=True 时 skipped 恒为 0**
    (缺字段直接进 violations),调用方可以安全丢弃;required=False 时
    skipped 必须被如实打印 ——「跳过」与「通过」在输出上不可分辨,正是本
    检查要解决的问题。
    """
    v, skipped = [], 0
    if not isinstance(container, dict):
        return v, skipped
    for c in CURRENCIES:
        if c not in covered:
            continue
        entry = container.get(c)
        if not isinstance(entry, dict):
            # 容器里没有该币种条目是合法形态(基准货币在定盘类容器中本就没有
            # 条目),不是缺字段;只有条目存在时才要求其结论句字段齐全
            continue
        skip_this_currency = False
        for field in fields:
            s = entry.get(field)
            if s is None:
                if required:
                    v.append("VERDICT_ABSENT: %s.%s 缺少结论句 %s(字段不存在或为 null);%s"
                             % (label, c, field, DISPOSITION_SCRIPT_BUG))
                else:
                    skip_this_currency = True
                continue
            if not isinstance(s, str):
                v.append("VERDICT_MALFORMED: %s.%s 的 %s 应为字符串,实为 %s;%s"
                         % (label, c, field, type(s).__name__,
                            DISPOSITION_SCRIPT_BUG))
                continue
            if not s.strip():
                # 任意报告都"包含"空串 —— 最直接的假绿入口
                v.append("VERDICT_EMPTY: %s.%s 的 %s 为空串或纯空白;%s"
                         % (label, c, field, DISPOSITION_SCRIPT_BUG))
                continue
            # 逐字节精确子串。前提:产出端(verdicts.join_verdict /
            # _fixings_verdict)从不产生首尾空白,纯空白已由上一分支拦下 ——
            # 若哪天产出端会带首尾空白,这里应改成 s.strip() not in report,
            # 因为 markdown 无法可靠复现首尾空格
            if s not in report:
                v.append("VERDICT_NOT_QUOTED: %s.%s 的 %s 未逐字出现在报告中;"
                         "期望原文:「%s」;%s"
                         % (label, c, field, s, DISPOSITION_QUOTE))
        if skip_this_currency:
            skipped += 1        # 按币种计一次,不按字段——T6 打印的是「N 个币种」
    return v, skipped


def _ring_payload(sentence, labels):
    """取**最后一个**标签之后的内容,再去掉标点与空白。

    为什么要剥标签:两句各自带着必然不同的标签(一句写「翻转指标」、另一句
    写「不成立时」),不剥就永远不可能逐字相同,② 会退化成一条从不触发的
    码 —— 那正是本轮要消灭的「非检查」形态。剥掉标签后比的是标签**之后**
    那段话,也就是作弊时被原样搬过去的那一段。
    取最后一个:替代解释那一句写成「……(其翻转指标:X)」,要的是 X。

    ---- 后缀式回退(本轮补)----
    上面那套只认**前缀式**「不成立时X」。实测 reports/daily/2026-08-14.md 的
    EUR 节写的是**后缀式**「若下月加息后仍留有余地,-0.499 会被后续路径改写,
    这条弱势腿**不成立**。」—— 标签落在句尾,标签之后是空的,于是这一句被当成
    「没有载荷」整句丢掉,② 在该节因此没有执行(那一天 2/5 判不出失效条件句,
    这是其中一条)。
    回退规则:标签之后剥完为空时,取**第一个**标签之前的那一段。后缀式里
    要比的内容正好在标签前面。只在"之后为空"时才回退,所以前缀式一字不受影响
    (由 test_prefix_form_still_yields_the_clause_after_the_label 钉住)。
    这不是放宽:回退只把**原本被丢掉**的句子还回来参与比较,② 因此**多判**
    而不是少判(test_restated_flip_is_still_caught_through_the_suffix_form
    正是拿后缀式写的失效条件去钓 ②,要求它照样红)。
    """
    cuts = sorted({sentence.rfind(lab) + len(lab) for lab in labels
                   if sentence.rfind(lab) >= 0}, reverse=True)
    if not cuts:
        return _RING_STRIP_RE.sub("", sentence)
    # 由后往前取第一个**非空**载荷。只取"最靠后那一个"会在同一句里同时出现
    # 前缀式与后缀式标签时取空:实测「不成立时这条线整条作废。」两个标签都
    # 在,最靠后的「作废」之后只剩句号,而要比的内容在它前面。
    for cut in cuts:
        out = _RING_STRIP_RE.sub("", sentence[cut:])
        if out:
            return out
    # 纯后缀式(「……这条弱势腿不成立。」):标签之后全空,内容在第一个标签之前
    heads = [sentence.find(lab) for lab in labels if sentence.find(lab) >= 0]
    return _RING_STRIP_RE.sub("", sentence[:min(heads)] if heads else "")


def check_judgement_ring(secs, covered, allowed, notes=None):
    """判断环三码。**每个被报告覆盖的币种节都查**,没有豁免路径。

    ---- 2026-08-14:三条「快照说这节不用查」的豁免整族删除 ----
    此前这里有一道体裁闸门:`derived.body_plan.<币种>.mode` 为 `minimal` 的
    节整节不查,声明写作 `JUDGEMENT_RING_MINIMAL_EXEMPT: …(该节只准写一行,
    本就没有判断环)`。**那条依据是假的**:实测 reports/daily/2026-08-10.md
    的 USD/PHP/THB/BRL 四节各写着 270–322 中文字的完整四环,而校验器从不核对
    「是不是真的只写了一行」。豁免于是只是"这四节不查"的另一种说法,五份产物
    上判断环的实际执行节数因此是 21/25。
    处置不是把豁免执行起来 —— 执行它等于把 `body_plan.<币种>.line` 那句
    「本日无可用增量,不更新判断」写进正文,而正文禁止出现这一类措辞
    (SKILL 第 7 条)。**处置是删掉豁免本身**:数据薄的那一天,币种节仍要从
    存量事实(政策利率、实际利率、区间上下沿)拉出判断环,采集口径与缺漏
    一律只落附录。`body_plan` 随之整块从快照删除(见 collect/derive.py)。
    同时删掉的还有 `JUDGEMENT_RING_SKIPPED_NO_MODE` 与
    `JUDGEMENT_RING_SKIPPED_NO_BODY_PLAN` —— 两条都只是同一道闸门的另外两态,
    闸门没了它们就无所指。判断环是**报告结构**的要求:①② 一个快照字段都不读,
    ③ 读的是 `allowed`,存量快照照样建得起来。

    删掉跳过声明之后,「这一层跑没跑」在 stdout 上会失去痕迹,所以补一条
    **正向回执** `JUDGEMENT_RING_CHECKED`:它不是豁免,是"覆盖 N 节、查了
    N 节"的计数,分母取**实际覆盖到的**币种(写死 5 会在缺节那天谎报全查)。

    背景:判断环(关键假设 / 替代解释 / 翻转指标)此前只写在
    `skills/fx-daily-report/SKILL.md` 的散文里,`scripts/` 下**零强制** ——
    实测 `grep -rn "关键假设\\|替代解释\\|翻转指标\\|失效条件" scripts/ --include=*.py`
    无输出。按调研台账的口径,那样的判断环是「非检查」,与我们批评社区的
    那 10 行提示词同型。这个函数只把它抬到「有强制」,并且**逐条标明**
    抬到了哪一层:

    ① `JUDGEMENT_RING_INCOMPLETE` —— **存在性检查**。
       判定依据:只查三个标签串在不在该币种节的正文里。它保证不了标签后面
       写的是不是真的假设/解释/指标,更不保证三者互相推得出来。
       替代解释自带的「其翻转指标」也算数(同一个标签串),这是已知弱点。

    ② `FLIP_INDICATOR_IS_INVALIDATION_RESTATED` —— **质量检查**。
       判定依据:它比的是同一节内**两句之间的关系**,不是「某物出没出现」。
       ICD 203 里翻转指标是「什么**出现**就改判」,失效条件是「什么**没发生**
       就无效」,两者语义不同;而最省事的作弊写法就是把失效条件换个说法当
       翻转指标交差。去标点空白后逐字相同、或其一是另一句的子串 → 违规。
       **诚实边界:只做逐字/子串比较,不做语义判断。** 同义改写(「收窄」
       写成「回落」)绕得过去 —— 它挡的是最省事的那条路,不是语义等价。
       语义判断做不了,不假装能做。

    ③ `ASSUMPTION_UNANCHORED` —— **存在性检查**。
       判定依据:只查关键假设句里有没有出现一个落在既有 `NUMBER_UNTRACEABLE`
       白名单(`allowed`)里的数字 token。它保证不了那个数字和假设有关系。
       **只要「当前值」类的可溯源数,绝不要求阈值**:阈值按定义是尚未发生的
       前瞻价位、不在快照里,要求它必然触发 `NUMBER_UNTRACEABLE`
       (判据见 check_daily 里 `allowed` 的构成)。两条规则会直接互斥,
       本仓四个月前撞过这一次。

    三条不都是质量检查 —— 把存在性说成质量,就是复现 IMF 那套评分器的病
    (`without fully evaluating the depth or quality of that discussion`)。

    **真实产物上的实测**(把 data/2026-08-14.json 复制一份、强行给五个币种
    都填 mode=full,再对 reports/daily/2026-08-14.md 跑一次):
    ③ 抓到两条真缺陷(USD 与 EUR 的关键假设句里一个可溯源数字都没有),
    ① 与 ② **零命中**。所以 ② 在真实产物上的拦截力**尚未被实测证实**,
    目前只有 fixture 与变异测试证明它会响 —— 不得把它说成"已经拦下过"。
    豁免删除后的复测(2026-08-14,五份产物一次跑完)证实了同一条:③ 在
    reports/daily/2026-08-10.md 上抓到 4 条真缺陷(USD/PHP/THB/BRL 的关键
    假设句里一个可溯源数字都没有),① 与 ② 仍是零命中。

    notes : **出参**,同 check_daily。只剩一条正向回执
            `JUDGEMENT_RING_CHECKED`,以及 ② 判不出失效条件句时的
            `FLIP_INDICATOR_CHECK_UNREACHABLE`。**没有跳过态** —— 覆盖到的
            节就是查过的节,两者相等由回执自己打出来。
    """
    v = []
    checked, unreachable = [], []
    for c in sorted(covered):
        checked.append(c)
        found, flip_unreachable = _check_one_ring(
            c, find_section(secs, c)[1], allowed)
        v.extend(found)
        if flip_unreachable:
            unreachable.append(c)
    if notes is not None:
        notes.append("JUDGEMENT_RING_CHECKED: %d/%d 个覆盖币种节的判断环已校验"
                     "(本层无豁免路径)" % (len(checked), len(covered)))
    if unreachable and notes is not None:
        # ② 要**同一节里两句都判得出**才比得起来。判不出失效条件句就整条
        # 跳过 —— 而这一跳过此前零声明,与「比过了、没重复」逐字不可分辨。
        # 实测口径(2026-08-14 本轮修完,reports/daily/2026-08-10..14 五份
        # 产物):25 个币种节全部写了「翻转指标」,判不出失效条件句的 0 个。
        notes.append("FLIP_INDICATOR_CHECK_UNREACHABLE: %d/%d 个币种节(%s)"
                     "写了「%s」但判不出失效条件句"
                     "(找的标签:%s),② 在这些节未执行"
                     % (len(unreachable), len(checked), "、".join(unreachable),
                        FLIP_LABEL, "/".join(INVALIDATION_LABELS)))
    return v


# ---- 速览表:按**表头列名**解析,不按列序号硬取 ----
# 表结构逐字见 reports/daily/2026-08-14.md:11-16:
#   | 币种 | 条件方向(时限) | 核心依据 | 失效条件 |
# 键按**包含**匹配表头单元格(表头写的是「条件方向(时限)」,带括号补语)。
# **为什么不按序号**:列序一变,按序号取就静默错位 —— 把「核心依据」当成
# 「失效条件」比对,判定照跑、结论全错,而 stdout 上一个字都不会变。按列名
# 解析时"列序变了"要么自动跟上(列还在,换了位置),要么变成一条带计数的
# 声明(列没了),两种都不是错位取值。
OVERVIEW_SECTION_KEY = "速览"
OVERVIEW_COL_CURRENCY = "币种"
OVERVIEW_COL_TRIGGER = "条件方向"
OVERVIEW_COL_INVALIDATION = "失效条件"
OVERVIEW_COLUMNS = (OVERVIEW_COL_CURRENCY, OVERVIEW_COL_TRIGGER,
                    OVERVIEW_COL_INVALIDATION)


def _pipe_rows(body):
    """markdown 管道表 → [[单元格]]。分隔行(`| --- |`)剔除。"""
    rows = []
    for line in body.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if cells and all(set(c) <= set("-: ") and c for c in cells):
            continue                                  # 分隔行
        rows.append(cells)
    return rows


def overview_rows(secs, notes=None):
    """速览表 → {币种: {列名: 单元格}}。解析不出时返回 `{}` 并出声。

    三态,每一态都带计数 —— 「跳过」与「通过」在输出上必须可区分:

    - 没有速览节 / 节里没有表 → `OVERVIEW_TABLE_SKIPPED`
    - 表头找不到某个要用的列名 → `OVERVIEW_TABLE_COLUMN_MISMATCH`,**整表不用**
      (失败关闭:少一列时按剩下的列硬取就是错位)
    - 某些币种没有行 → `OVERVIEW_ROW_MISSING`,其余币种照常返回

    notes : **出参**,同 check_daily。
    """
    sec = find_section(secs, OVERVIEW_SECTION_KEY)
    rows = _pipe_rows(sec[1]) if sec else []
    if not rows:
        if notes is not None:
            notes.append("OVERVIEW_TABLE_SKIPPED: 报告没有可解析的「%s」表"
                         "(节%s、表行 %d 行),%d 个币种的速览表判据未校验"
                         % (OVERVIEW_SECTION_KEY, "在" if sec else "缺失",
                            len(rows), len(CURRENCIES)))
        return {}
    header = rows[0]
    idx = {}
    for key in OVERVIEW_COLUMNS:
        hits = [i for i, h in enumerate(header) if key in h]
        if len(hits) == 1:
            idx[key] = hits[0]
    missing = [k for k in OVERVIEW_COLUMNS if k not in idx]
    if missing:
        if notes is not None:
            notes.append("OVERVIEW_TABLE_COLUMN_MISMATCH: 速览表表头的 %d 列"
                         "(%s)里,%d 个要用的列名(%s)不是恰好一列;"
                         "整表按失败关闭不取值,%d 个币种的速览表判据未校验"
                         % (len(header), "、".join(header), len(missing),
                            "、".join(missing), len(CURRENCIES)))
        return {}
    out = {}
    for cells in rows[1:]:
        if max(idx.values()) >= len(cells):
            continue
        cur = cells[idx[OVERVIEW_COL_CURRENCY]]
        if cur in CURRENCIES:
            out[cur] = {k: cells[i] for k, i in idx.items()}
    absent = [c for c in CURRENCIES if c not in out]
    if absent and notes is not None:
        notes.append("OVERVIEW_ROW_MISSING: 速览表缺少 %d/%d 个币种的行(%s),"
                     "这些币种的速览表判据未校验"
                     % (len(absent), len(CURRENCIES), "、".join(absent)))
    return out


def check_overview_invalidation_column(rows, bodies, notes=None):
    """速览「失效条件」列**不是** ② 可用的失效条件来源 —— 把这件事出声。

    ---- 为什么不从这一列取(本轮实测,先跑后抄)----
    `skills/fx-daily-report/SKILL.md:181-182` 与 `:278` 两处逐字要求:速览表
    「失效条件」那一格必须与该币种节判断环的**翻转指标同源同字**。
    在 reports/daily/2026-08-10..14 五份产物上逐条比对,两侧去掉标点空白后
    **逐字相同 20/20**(2026-08-13 那一份五个节没有独立的翻转指标句,不计入)。
    所以"从速览表取失效条件喂给 ②"= 拿翻转指标和它自己比:按构造 25/25 全红,
    一条真缺陷都不代表。**判据放错地方的修法不能是换一个更错的地方。**
    ② 真正该比的失效条件在币种节正文里 —— 关键假设那一句的「不成立/作废」
    后半句,`INVALIDATION_LABELS` 认的就是它;本轮修的是那个识别器
    (见 `_ring_payload` 的后缀式回退与 `INVALIDATION_LABELS` 的「作废」)。

    这一条**不判违规**:20/20 相同正是 SKILL 要求的形态,报告没有错。
    它只把"该列与翻转指标同字、因此不能当独立来源"打成一条带计数的声明,
    让这个事实出现在 stdout 里,而不是只留在某个人的汇报里。
    报告与 SKILL 之间这处口径矛盾(一边定义翻转指标为"出现即改判"、一边要求
    它与"失效条件"同字)已由 reports/daily/2026-08-14.md 的附录 D 登记,
    须在 SKILL 层裁决后统一改,不在校验器里单方面裁定。

    rows   : `overview_rows` 的返回值
    bodies : {币种: 币种节正文}
    """
    if notes is None:
        return
    same = []
    for c in CURRENCIES:
        cell = (rows.get(c) or {}).get(OVERVIEW_COL_INVALIDATION)
        body = bodies.get(c)
        if not cell or not body:
            continue
        col = _RING_STRIP_RE.sub("", cell)
        flips = [s for s in split_sentences(body) if FLIP_LABEL in s]
        pays = [p for p in (_ring_payload(f, (FLIP_LABEL,)) for f in flips) if p]
        if col and any(col == p or col in p or p in col for p in pays):
            same.append(c)
    both = [c for c in CURRENCIES
            if (rows.get(c) or {}).get(OVERVIEW_COL_INVALIDATION)
            and bodies.get(c)]
    if same:
        notes.append("FLIP_INDICATOR_TABLE_COLUMN_IS_FLIP: 速览表「%s」列在 "
                     "%d/%d 个币种上与该币种节的翻转指标去标点后逐字相同"
                     "(SKILL 第 181/278 行要求二者同源同字),该列因此不是"
                     "独立的失效条件来源,② 不从该列取数"
                     % (OVERVIEW_COL_INVALIDATION, len(same), len(both)))


def _check_one_ring(currency, body, allowed):
    """单个币种节的三码判定。见 check_judgement_ring 的诚实标注。

    返回 (violations, flip_unreachable)。`flip_unreachable` 为真 = 本节写了
    翻转指标句、却判不出任何带载荷的失效条件句,② 因此**没有执行** ——
    调用点必须把它计数打印出来,不出声就与「比过了、没重复」不可分辨。

    allowed : 可溯源数字白名单。**`None` 表示这一轮建不起白名单**(周报侧
            未提供 `--digest`),此时 ③ 整条不判 —— 拿一个只有小整数的空
            白名单去判锚点,会把每一句关键假设都打成假红。调用点必须为这
            一态打带计数的声明(`WEEKLY_ASSUMPTION_ANCHOR_SKIPPED_NO_DIGEST`)。

    **本函数是判断环三码字面量的唯一产地**,日报与周报两条路径都落到它上面 ——
    判定复制两份后漂移是本仓库栽过的坑(见 scripts/fixings.py)。由
    WeeklyJudgementRingTest::test_the_ring_judgement_has_exactly_one_implementation
    的 AST 断言钉住:三个码只许在这个函数里出现。
    """
    v = []
    missing = [lab for lab in RING_LABELS if lab not in body]
    if missing:
        v.append("JUDGEMENT_RING_INCOMPLETE: %s 节的判断环没写 %s;"
                 "三件(%s)必须齐全;%s"
                 % (currency, "、".join(missing), "/".join(RING_LABELS),
                    DISPOSITION_RING))
    sents = split_sentences(body)
    flips = [s for s in sents if FLIP_LABEL in s]
    invalids = [s for s in sents
                if any(lab in s for lab in INVALIDATION_LABELS)]
    flip_payloads = [p for p in (_ring_payload(f, (FLIP_LABEL,)) for f in flips)
                     if p]
    inv_payloads = [p for p in (_ring_payload(i, INVALIDATION_LABELS)
                                for i in invalids) if p]
    # ② 的可达条件:两侧都得有带载荷的句子。只有一侧时下面的双重循环一次都
    # 不进,而"没进过循环"与"比过了、没重复"在返回值上完全同形 —— 所以把它
    # 显式算出来交给调用点声明,不留在这里当沉默的第三态。
    flip_unreachable = bool(flip_payloads) and not inv_payloads
    for f in flips:
        fn = _ring_payload(f, (FLIP_LABEL,))
        if not fn:
            continue
        for i in invalids:
            inv = _ring_payload(i, INVALIDATION_LABELS)
            # 空载荷不比:`"" in x` 恒真,会把「标签后面什么都没写」误判成
            # 「改写自失效条件」—— 两件事不同因不同果,不得同判
            if not inv:
                continue
            if fn in inv or inv in fn:
                v.append("FLIP_INDICATOR_IS_INVALIDATION_RESTATED: "
                         "%s 节的翻转指标句与失效条件句去掉标点与空白后重复"
                         "(逐字相同或互为子串);翻转指标原文:「%s」;"
                         "失效条件原文:「%s」;%s"
                         % (currency, f, i, DISPOSITION_FLIP))
    for s in sents:
        if ASSUMPTION_LABEL not in s or allowed is None:
            continue
        if not (numbers_in(s) & allowed):
            v.append("ASSUMPTION_UNANCHORED: %s 节的关键假设句里没有可溯源"
                     "数字:「%s」;%s" % (currency, s, DISPOSITION_ANCHOR))
    return v, flip_unreachable


# ---- 数字的**归属**:两条映射级检查 ----
# 既有 `NUMBER_UNTRACEABLE` 的判据是 `allowed` 三行并集上的**集合成员**判定,
# 然后做集合差。它是一个**无序词袋**:把美元的数字写进雷亚尔那一节,两个数
# 都在 `allowed` 里,校验器逐字放行。下面两张表把"数字属于谁"显式建起来。
#
# 币种 → 经济体。macro 行与 derived.real_rate 按经济体分键,rates/events 与
# derived.rates/derived.events 按币种分键 —— 两套键都要走这张表才对得上。
ECONOMY_OF_CURRENCY = {"USD": "US", "EUR": "EA", "PHP": "PH",
                       "THB": "TH", "BRL": "BR"}
# 快照里**按币种/经济体分键**的容器:rates / events / macro / derived。
# 归属就在这四处取,别处不取。
CURRENCY_SNAPSHOT_CONTAINERS = ("rates", "events")
DERIVED_CURRENCY_CONTAINERS = ("rates", "events")
# ---- 共享池:**显式枚举**,不是"其余都算" ----
# 「其余都算共享」等于没有约束,所以这里只列两类来源,并在测试里逐元素冻结:
#   ① 快照里**不按币种分键**的顶层字段。刻意**不含** run_at 与 schema_version:
#      run_at 是 `2026-08-14T04:56:51+00:00` 这种串,DATE_RE 剥掉日期后留下
#      04/56/51/00 四个二位数,等于给任意两位数开一张免票;schema_version 是
#      个位数,已经在 ALLOWED_SMALL 里。实测:这两个键对现有八份产物的判定
#      **零影响**(加与不加,炸出的条数都是 0),所以不加。
#   ② 要点表里**显式的**跨币种块。跨币种比较是本仓报告的正常写法,而这个块
#      正是产出流程给跨币种量指定的落点 —— 它是"共享"的唯一声明处,不是
#      "凡是我认不出归属的都算共享"。
SHARED_SNAPSHOT_KEYS = ("date", "calendar_hits", "gaps", "meta")
SHARED_BRIEF_HEADINGS = ("跨币种共同主线",)
# 币种别名:节内点名判据。别名少一个就等于把该币种的引用全判成违规,
# 多一个(如把「元」也算 EUR)就等于把约束整体放掉 —— 逐元素冻结在测试里。
CURRENCY_ALIASES = {"USD": ("USD", "美元"), "EUR": ("EUR", "欧元"),
                    "PHP": ("PHP", "比索"), "THB": ("THB", "泰铢"),
                    "BRL": ("BRL", "雷亚尔")}
SUMMARY_SECTION_KEY = "执行摘要"
# 年-月式样。**只给 check_summary_number_attribution 用**,理由见那里的
# 诚实边界 4:`DATE_RE` 不认 `2026-08`,而改 `DATE_RE` 会连带放松两个既有的
# `*_UNTRACEABLE` 闸门。负向断言 `(?!\d)` 挡住 `2026-0812` 这种非日期串。
YEAR_MONTH_RE = re.compile(r"\d{4}-\d{2}(?!\d)")
# 「正文」的范围:币种节 ∪ 这三节。**冻结的清单**,不是"报告的其余部分" ——
# 后者会让这条码退化成"摘要的数只要在报告里出现过就行",附录里随手一提就算
# 数。缺漏节在列是实测要求的:reports/daily/2026-08-07.md 的摘要写
# 「五币种 GDELT 事件采集均为 429」,429 在报告里只出现于缺漏节。
SUMMARY_BODY_SECTION_KEYS = ("速览", "复盘", "数据缺漏")


def _dedup(keys):
    """保序去重。三份键清单里有重复项(`复盘`/`数据缺漏` 既是结构必需节、
    又在摘要正文清单里),去重后才好逐元素冻结。"""
    seen, out = set(), []
    for k in keys:
        if k not in seen:
            seen.add(k)
            out.append(k)
    return tuple(out)


# ---- 需要唯一化的节键:**三份冻结清单**,见 find_section 的失败关闭说明 ----
# 清单里少一个键,就等于把那个键的唯一化悄悄关掉(而那正是 Fatal 1 的形状),
# 所以与 SHARED_SNAPSHOT_KEYS 同规格逐元素冻结,并由
# `test_every_key_reachable_by_find_section_is_in_a_frozen_list` 做闭合:
# 源码里传给 `find_section`/`section_hits` 的**字面量**键必须都在清单里。
DAILY_REPORT_SECTION_KEYS = _dedup(
    tuple(CURRENCIES) + ("执行摘要", "复盘", "数据缺漏", PRIOR_PERIOD_SECTION_KEY)
    + SUMMARY_BODY_SECTION_KEYS)
BRIEF_SECTION_KEYS = _dedup(tuple(CURRENCIES) + SHARED_BRIEF_HEADINGS)
WEEKLY_REPORT_SECTION_KEYS = _dedup(tuple(WEEKLY_SECTIONS))


def _macro_rows(snap):
    rows = snap.get("macro")
    return [m for m in rows if isinstance(m, dict)] if isinstance(rows, list) else []


def currency_snapshot_slice(snap, currency):
    """该币种在快照里的**自有切片**,返回 JSON 片段列表(缺的不进列表)。

    取处**显式枚举**,不做模式扫描:rates/events 按币种分键,
    derived.rates/derived.events 按币种分键,derived.real_rate 与 macro 行按
    经济体分键。空列表 = 该币种在快照里没有任何切片(判不了归属,见调用点
    的第三态)。
    """
    econ = ECONOMY_OF_CURRENCY.get(currency)
    parts = []
    for key in CURRENCY_SNAPSHOT_CONTAINERS:
        box = snap.get(key)
        if isinstance(box, dict) and box.get(currency) is not None:
            parts.append(box[currency])
    derived = snap.get("derived")
    if isinstance(derived, dict):
        for key in DERIVED_CURRENCY_CONTAINERS:
            box = derived.get(key)
            if isinstance(box, dict) and box.get(currency) is not None:
                parts.append(box[currency])
        rr = derived.get("real_rate")
        if isinstance(rr, dict) and rr.get(econ) is not None:
            parts.append(rr[econ])
    rows = [m for m in _macro_rows(snap) if m.get("economy") == econ]
    if rows:
        parts.append(rows)
    return parts


def currency_number_pool(snap, brief_text, currency):
    """该币种自有的数字集合 = 快照切片 ∪ 要点表里该币种那一节 ∪ 复盘材料里
    该币种那几行。

    要点表**按币种切**(生产要点表逐字如此,见 briefs/2026-08-14-brief.md),
    而不是整份进池 —— 整份进池就等于把要点表的跨币种词袋又搬回来一次,本码
    要消灭的正是词袋。这相对既有 `allowed` 只会**更严**,不会更松。
    """
    text = json.dumps(currency_snapshot_slice(snap, currency), ensure_ascii=False)
    nums = numbers_in(text)
    sec = find_section(sections(brief_text), currency)
    if sec:
        nums |= numbers_in(sec[1])
    for line in brief_text.splitlines():
        if line.startswith("- %s |" % currency):
            nums |= numbers_in(line)
    return nums


def brief_attributed_numbers(brief_text):
    """要点表里**已经有币种归属**的数字 —— `## <币种>` 那几节的并集。"""
    secs = sections(brief_text)
    nums = set()
    for c in CURRENCIES:
        sec = find_section(secs, c)
        if sec:
            nums |= numbers_in(sec[1])
    return nums


def shared_number_pool(snap, brief_text):
    """共享池 —— 逐元素定义见 SHARED_SNAPSHOT_KEYS / SHARED_BRIEF_HEADINGS。

    ALLOWED_SMALL 整体在池内:序数/条数/月份类小整数没有币种归属,把它们
    纳进映射约束会把每一句「第 3 条」「T+3」都打红。

    ---- 要点表那一部分先过**归属减法**,快照那一部分不过 ----
    共享池有两个来源,而其中一个(要点表的跨币种块)**由被查方撰写**:
    要点表是 LLM 写的,于是"想让某个数在某节合法,只要把它写进跨币种块" ——
    闸门的输入被被查对象控制,与 V7/V8/V12 那三条真绕过同型。
    减法把这条路封上:凡是在要点表 `## <币种>` 那节出现过的数,**只解锁该
    币种**,不进共享池。抄进跨币种块也没用 —— 它已经有归属了。
    快照侧的 SHARED_SNAPSHOT_KEYS **不参与减法**:那一侧不由被查方撰写,
    减它没有理由,而且会把 gaps 里的 HTTP 状态码之类整体判死。

    **减法的上界**:跨币种块里那些**没有**任何币种块认领的数仍是共享的 ——
    跨币种比较是本仓报告的正常写法,减过头等于把这条写法整体判死。
    实测口径(本轮,reports/daily/2026-08-10..14 五份产物):
    跨币种块共 32 个数字,其中 28 个可归属到具体币种块;减法把
    `NUMBER_WRONG_SECTION` 由 0 条变成 6 条,全部落在
    reports/daily/2026-08-13.md 的美元节 —— 逐条判定为**真缺陷**并改了报告
    (那一节把四条交叉盘的步幅 1.493/0.24/0.076/0.052 并排列出却一个币种都
    没点名,而列出的顺序与要点表里的顺序不同,读者按位置对应必然对错)。
    """
    nums = set(ALLOWED_SMALL)
    nums |= numbers_in(json.dumps({k: snap.get(k) for k in SHARED_SNAPSHOT_KEYS},
                                  ensure_ascii=False))
    secs = sections(brief_text)
    attributed = brief_attributed_numbers(brief_text)
    for heading in SHARED_BRIEF_HEADINGS:
        sec = find_section(secs, heading)
        if sec:
            nums |= numbers_in(sec[1]) - attributed
    return nums


def check_number_section_mapping(secs, snap, brief_text, covered, allowed,
                                 notes=None):
    """`NUMBER_WRONG_SECTION` —— **质量检查**(映射级)。

    判据是「这个数出自**哪个**币种的切片」对上「它写在**哪个**币种节」,
    比的是两个位置之间的关系,不是某个 token 在不在一个大词袋里 ——
    所以它不是**存在性**检查。既有的 `NUMBER_UNTRACEABLE` 才是存在性那一层
    (`allowed` 三行并集上的集合成员判定),而它对"美元的数写进雷亚尔节"
    完全不敏感:两个数都在并集里。

    **诚实边界,三条,写在这里而不是只写在汇报里:**

    1. 归属的判定单位是**节**,不是句。节内点名了别的币种(别名表见
       CURRENCY_ALIASES),该币种的整个数字池就在本节放行。收紧到"同一句
       必须点名"会误报:实测 reports/daily/2026-08-10.md 的美元节那句
       「四条本币对美元的参考价……0.86693→0.86543、60.867→60.75、
       33.055→33.013、5.0998→5.0856」一句点名不到四个币种,句级判定在八份
       产物上炸出 15 条,全是正常写法;节级判定炸出 0 条。
       代价说清楚:美元在非美元节里几乎必然被点名(报价的另一条腿就是它),
       实测八份产物 160 个"节 × 别的币种"里 71 个被点名 —— 也就是说
       **约 44% 的跨币种引用本码放行**,其中美元那一列几乎全放行。
       本码拦得住的是没有点名的那 89 个。
    2. 它只判"这个数出自谁",判不了"这个数用得对不对"。从本币种切片里挑一个
       无关的数编一句话,本码放行。
    3. 候选集**只取已可溯源的数**(`allowed`)。编造的数由
       `NUMBER_UNTRACEABLE` 管 —— 同一个 token 不得同时吃两条违规。

    三态:该币种在快照里一个切片都没有 → 打印跳过声明、不判违规
    (`currency_snapshot_slice` 返回空,判不了归属就不判)。
    macro 行没有可识别的 `economy` → 该行并入共享池,并打印声明:那是一条
    真实的豁免(存量快照的 macro 行没有这个字段),不出声就与"全查过"同形。

    notes : **出参**,同 check_daily。
    """
    v = []
    unattributed = [m for m in _macro_rows(snap)
                    if m.get("economy") not in set(ECONOMY_OF_CURRENCY.values())]
    shared = shared_number_pool(snap, brief_text)
    if unattributed:
        shared |= numbers_in(json.dumps(unattributed, ensure_ascii=False))
        if notes is not None:
            notes.append("NUMBER_WRONG_SECTION_MACRO_UNATTRIBUTED: 快照 macro 有 "
                         "%d 行没有可识别的 economy,这些行的数字并入共享池、"
                         "不判归属" % len(unattributed))
    own = {c: currency_number_pool(snap, brief_text, c) for c in CURRENCIES}
    no_slice = []
    named_pairs = total_pairs = released = sentence_bad = 0
    for c in sorted(covered):
        if not currency_snapshot_slice(snap, c):
            no_slice.append(c)
            continue
        body = find_section(secs, c)[1]
        pool = own[c] | shared
        strict = set(pool)          # 不含点名放行的那一份,只用来数放行量
        for other in CURRENCIES:
            if other == c:
                continue
            total_pairs += 1
            if any(a in body for a in CURRENCY_ALIASES[other]):
                named_pairs += 1
                pool |= own[other]
        here = numbers_in(body) & allowed
        bad = sorted(here - pool)
        released += len((here - strict) - set(bad))
        # 「收到句会多炸多少」——**只统计,不判定**。判定单位仍是节(理由见
        # 诚实边界 1 与下面 NUMBER_WRONG_SECTION_NAMED_PASS 的实测口径)。
        for sent in split_sentences(body):
            spool = set(strict)
            for other in CURRENCIES:
                if other != c and any(a in sent
                                      for a in CURRENCY_ALIASES[other]):
                    spool |= own[other]
            sentence_bad += len((numbers_in(sent) & allowed) - spool)
        for n in bad:
            src = sorted(o for o in CURRENCIES if o != c and n in own[o])
            v.append("NUMBER_WRONG_SECTION: %s 节写了 %s,它只出自 %s 的快照"
                     "切片,而本节没有点名 %s;%s"
                     % (c, n, "/".join(src) or "别处", "/".join(src) or "它",
                        DISPOSITION_WRONG_SECTION))
    if named_pairs and notes is not None:
        # 诚实边界 1 说的那 44%(本轮在五份产物上复算为 59/100)此前**零声明**:
        # 「放行了大半」与「全查过且全过」在 stdout 上逐字不可分辨。
        # 声明带两个计数 ——「有跳过」不可操作,得说跳过了多少。
        # ---- 本轮补的第三个数:**收到句会多炸多少** ----
        # 「放行了大半」上一轮已经出声,但读者据它判断不了"收紧一档能换来
        # 多少检出力" —— 而那正是决定要不要收紧的那个数。不给它,"保留节级"
        # 就是一句无法复核的断言。
        # 实测口径(本轮,reports/daily/2026-08-10..14 五份产物):
        # 节级 0 条 → 句级 22 条,新增 22。逐条核下来 **22 条全部来自 6 个
        # 句子、且是同一个结构类**:句子用**集合指代**点名其余币种
        # (「四条本币对美元的参考价……」「三条同时越过 61.178、33.105、
        # 5.1049」「四者未同次同向升破 0.867、61.325、33.13、5.1811」
        # 「0.705%、0.279%、0.129% 与 -1.613、-1.42、-0.499 顺序一一对上」),
        # 再按固定次序并列列出各自的值。别名表按构造看不见「四条」「四者」
        # 「三条」这类**集合量词**,所以句级判定对这一类必然误报 —— 22 条里
        # 真缺陷 0 条。据此**保留节级判定**,把这个数打出来代替收紧。
        notes.append("NUMBER_WRONG_SECTION_NAMED_PASS: %d/%d 个「币种节 × 别的"
                     "币种」组合因节内点名了对方而整池放行,其中 %d 个数字实例"
                     "因此未判归属(归属的判定单位是节,不是句,见 "
                     "check_number_section_mapping 的诚实边界 1);"
                     "同一批输入把判定单位收到句会多炸 %d 条"
                     % (named_pairs, total_pairs, released,
                        max(sentence_bad - len(v), 0)))
    if no_slice and notes is not None:
        notes.append("NUMBER_WRONG_SECTION_SKIPPED_NO_SLICE: %s 在快照里没有"
                     "任何自有切片(rates/events/derived/macro 都没有该币种或"
                     "其经济体的条目),这些节的数字归属未校验"
                     % "、".join(no_slice))
    return v


def check_summary_number_attribution(secs, snap, brief_text, allowed,
                                     notes=None, ambiguous=()):
    """`SUMMARY_NUMBER_WRONG_CURRENCY` —— **关系判定**(归属级)。

    判据:摘要 bullet 点名了币种 X,这一条里的数就必须出自 X 的切片(或共享
    池);只出自 Y 的数写在点名 X 的那一条里 = 归属错。比的是**数与币种之间
    的对应**,不是某个 token 在不在另一个池里 —— 所以它不是**存在性**判定,
    与 `check_number_section_mapping` 是同一形制,只是判定单位由「节」换成
    「bullet」。

    ---- 它为什么存在:Major 4 的更正 ----
    `SUMMARY_NUMBER_NOT_IN_BODY` 此前自称「质量检查」,而实现是**换了参照池
    的集合差存在性判定**,docstring 在同一页里既说"不是存在性"又说"只查出现
    过",自相矛盾。二选一里选的是 (b)「把实现升级成真正的关系判定」——
    (a) 只改标注是诚实的下策。升级落在这一层;旧码一条都没删,它退回它本来
    的身份(存在性层),标注同步改正。

    **诚实边界,三条:**

    1. 判定单位是 **bullet**,点名即放行 —— 与 NUMBER_WRONG_SECTION 的节级
       点名同规矩。跨币种对照是摘要的正常写法。
    2. 只判「这个数出自谁」,判不了「这个数用得对不对」。
    3. 归属不到**任何**币种的数不归本码管 —— 那一类由存在性层与
       `NUMBER_UNTRACEABLE` 管,同一个 token 不得吃两条违规。
    4. **年-月碎片先剥掉**(`YEAR_MONTH_RE`,只在本层剥)。`DATE_RE` 认
       `2026-08-10` 与「8 月」,**不认 `2026-08`**;于是摘要写「参考月
       2026-08」时 `numbers_in` 吐出 `2026` 与 `08` 两个 token,而快照的
       `"period": "2026-07"` 让它们真的落在某个币种的切片里 —— 边界 3 那道门
       挡不住。实测:不剥,reports/daily/2026-08-13.md 的摘要当场炸出
       `08`(「只出自 USD」)与 `2026`(「只出自 PHP/USD」)两条假红。
       **刻意不去改 `DATE_RE`**:那会同时放松 `NUMBER_UNTRACEABLE`
       与 `BRIEF_NUMBER_UNTRACEABLE` 这两个既有闸门,而本轮不放宽任何既有
       判据。剥这一下只收窄**新码自己**的射程,既有行为一字不动。

    **真实产物上的实测**(本轮,reports/daily/2026-08-10..14 五份):
    抓到 1 条真缺陷 —— 2026-08-11 摘要首条点名了比索/泰铢/欧元,却写了
    `5.1049`(雷亚尔的触发位),读者按位置对应必然对错。已改报告。

    ambiguous : 见 check_prior_period。摘要节重名时整条不判(SECTION_AMBIGUOUS
            已经把它打红,而 `find_section` 这时返回 None)。
    """
    v = []
    if SUMMARY_SECTION_KEY in ambiguous:
        return v
    s = find_section(secs, SUMMARY_SECTION_KEY)
    if s is None:
        return v          # 缺节由存在性层的 SUMMARY_NUMBER_SKIPPED_NO_SECTION 声明
    own = {c: currency_number_pool(snap, brief_text, c) for c in CURRENCIES}
    shared = shared_number_pool(snap, brief_text)
    unnamed = 0
    for item in list_items(s[1]):
        nums = (numbers_in(YEAR_MONTH_RE.sub(" ", item)) & allowed) \
            - ALLOWED_SMALL
        if not nums:
            continue
        named = [c for c in CURRENCIES
                 if any(a in item for a in CURRENCY_ALIASES[c])]
        if not named:
            unnamed += 1
            continue
        pool = set(shared)
        for c in named:
            pool |= own[c]
        for n in sorted(nums - pool):
            src = sorted(o for o in CURRENCIES if o not in named and n in own[o])
            if not src:
                continue                      # 诚实边界 3
            v.append("SUMMARY_NUMBER_WRONG_CURRENCY: 执行摘要该条点名 %s,"
                     "却写了 %s —— 它只出自 %s 的快照切片;原文:「%s」;%s"
                     % ("/".join(named), n, "/".join(src), item.strip(),
                        DISPOSITION_SUMMARY_CURRENCY))
    if unnamed and notes is not None:
        notes.append("SUMMARY_NUMBER_SKIPPED_NO_CURRENCY_NAMED: %d 条带数字的"
                     "摘要 bullet 没有点名任何币种(别名表:%s),这些条的数字"
                     "归属未校验"
                     % (unnamed, "/".join(
                         "".join(CURRENCY_ALIASES[c]) for c in CURRENCIES)))
    return v


def check_summary_numbers_in_body(secs, notes=None, ambiguous=()):
    """`SUMMARY_NUMBER_NOT_IN_BODY` —— **存在性检查**(参照池换成了正文)。

    移植自 econstack 被删版本的 A1 检查项,逐字:
    `| A1 | Do all numbers in the executive summary match the tables? | RED |`

    ---- 标注更正(Major 4):这一条**不是**质量检查 ----
    此前它自称「质量检查(一致性级)」,理由写的是"比的是同一个数在两个位置
    的一致性"。那句话与它自己的诚实边界 1「只查这个 token 在正文里出现过」
    在**同一页里自相矛盾**,而实现是后者:`nums(摘要) - nums(正文)` 的集合差
    —— 换了参照池的存在性判定,与 `NUMBER_UNTRACEABLE` 只差参照池是谁。
    把存在性说成质量,就是复现 IMF 那套评分器的病,所以标注改正,不含糊。
    **真正的关系判定另建一层**,见 `check_summary_number_attribution`
    (`SUMMARY_NUMBER_WRONG_CURRENCY`);本码一条没删,只是回到它本来的身份。

    **方向只有一个:摘要 ⊆ 正文。** 反过来(正文的数必须进摘要)会把每一份
    正常报告打成几十条红 —— 摘要按 spec 最多 6 条,本就装不下正文的数。

    **诚实边界,两条:**

    1. 它只查这个 token 在正文里**出现过**,不查两处说的是不是同一件事。
       摘要写「参考价 60.843 已升破」而正文写「60.843 未更新」,本码放行 ——
       那是语义,做不了,不假装能做。
    2. `ALLOWED_SMALL` 整体豁免,与 `check_number_section_mapping` 同一理由:
       序数/条数(「摘要第 3 条」「T+3」「四盘」)不是 A1 说的那种数,而它们
       在正文里没有对应是常态。不豁免时,tests 里 `make_report` 的
       「摘要第 1/2/3 条」当场炸出 3 条、连带 17 个既有用例变红 —— 那是这一类
       的真实形状。实测口径:在 reports/daily/2026-08-07..14 八份产物上,
       豁免与不豁免炸出的条数**都是 0**,这条豁免不换取任何已知的检出力。

    三态:没有执行摘要节(SECTION_MISSING 另有一条,这里不重复判违规)、
    摘要里没有需要溯源的数 —— 两种都打印跳过声明。

    notes : **出参**,同 check_daily。
    ambiguous : 见 check_prior_period。摘要节或任一正文节重名时整条不判 ——
            重名会让 `find_section` 返回 None,正文池随之**少掉一整节**,
            于是这一层会对着残缺的正文池假报一串违规。失败关闭在这里的形态
            是"不判并出声",红由 SECTION_AMBIGUOUS 出。
    """
    v = []
    blocking = sorted(set(ambiguous or ())
                      & ({SUMMARY_SECTION_KEY} | set(CURRENCIES)
                         | set(SUMMARY_BODY_SECTION_KEYS)))
    if blocking:
        if notes is not None:
            notes.append("SUMMARY_NUMBER_SKIPPED_AMBIGUOUS: 摘要或正文的 %d 个"
                         "节键(%s)在报告里重名,节定位不唯一,摘要数字与正文"
                         "的存在性未校验" % (len(blocking), "、".join(blocking)))
        return v
    s = find_section(secs, SUMMARY_SECTION_KEY)
    if s is None:
        if notes is not None:
            notes.append("SUMMARY_NUMBER_SKIPPED_NO_SECTION: 报告没有「%s」节,"
                         "摘要数字与正文的一致性未校验" % SUMMARY_SECTION_KEY)
        return v
    nums = numbers_in(s[1]) - ALLOWED_SMALL
    if not nums:
        if notes is not None:
            notes.append("SUMMARY_NUMBER_SKIPPED_NO_NUMBERS: 执行摘要里没有"
                         "需要溯源的数字(序数/条数类小整数已整体豁免),"
                         "与正文的一致性无可校验")
        return v
    body = []
    for key in tuple(CURRENCIES) + SUMMARY_BODY_SECTION_KEYS:
        sec = find_section(secs, key)
        if sec:
            body.append(sec[1])
    in_body = numbers_in("\n".join(body))
    for n in sorted(nums - in_body):
        v.append("SUMMARY_NUMBER_NOT_IN_BODY: 执行摘要写了 %s,正文(币种节/%s)"
                 "一处都没有;%s"
                 % (n, "/".join(SUMMARY_BODY_SECTION_KEYS),
                    DISPOSITION_SUMMARY_BODY))
    return v


def parse_decision_log(text):
    """决策日志(jsonl)→ ({(日期, 币种): 条目}, problems)。

    与 `parse_snapshot` 同规格:**外部数据,可能损坏**,所以解析问题逐条
    返回而不是抛。调用点(`main`)据此 rc=2 响亮失败 —— 这一条刻意**不走
    fail-open**:"给了 `--decision-log` 却读不成 → 静默不查" 正是上一轮
    weekly 位置参数那条缺陷的形状(调用方以为查了、脚本以为没传,两边都
    不出声)。给了就必须读成,读不成就报错。

    **本文件不做路径解析**:日志路径由 `--decision-log` 传入。校验器不读
    环境变量是不变量(见文件头),而"自己去仓库根目录找 state/…"要么得
    import os、要么得靠 `__file__` 猜仓库布局,两条都在把闸门的输入交给
    校验器自己拼 —— 与 `--digest` / `--prior` 同规矩,路径由调用方给。
    """
    entries, problems = {}, []
    for i, line in enumerate(text.splitlines()):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except (ValueError, RecursionError) as e:
            problems.append("决策日志第 %d 行无法解析: %s" % (i + 1, e))
            continue
        if not isinstance(obj, dict):
            problems.append("决策日志第 %d 行应为对象,实为 %s"
                            % (i + 1, type(obj).__name__))
            continue
        date, cur = obj.get("date"), obj.get("currency")
        if isinstance(date, str) and isinstance(cur, str):
            entries[(date, cur)] = obj
    return entries, problems


def check_decision_trigger(secs, date, entries, notes=None):
    """`DECISION_TRIGGER_NOT_SOURCED` —— 速览「条件方向」格 ⊇ 日志 `trigger`。

    ---- 为什么新增(本轮实测,先跑后抄)----
    `skills/fx-daily-report/SKILL.md:180` 与 `:388` 两处写明速览表「条件方向」
    那一格与当日写进决策日志的 `trigger` **同源同字**,而校验器对它零提及:
    `grep -n "decision\\|决策日志" scripts/check_report.py` 无输出。
    散文规则、零强制。本周实测违约率(判据:log 的 trigger 整串是否出现在
    当日速览「条件方向」那一格里):2026-08-10 五币种全 False、2026-08-11
    五币种全 False、08-12/08-13/08-14 各五条全 True —— **25 条里 10 条当前
    就是违反的,而六份产物全绿**。
    更刺眼的一条:`reports/daily/2026-08-14.md:21` 逐字写着「与
    state/decision-log.jsonl 当日五条 trigger 逐字同源(本期实跑比对:
    五条全中)」—— 报告在自证一条没有裁判的规则。

    ---- 判据:包含,不是相等 ----
    速览那一格按模板写的是 `<可观测触发> → 关注<方向>(T+N)`,而日志的
    `trigger` 只登记触发那一半(SKILL 第 388 行:「把速览表五行的"条件方向"
    整理成 JSON 数组」)。所以判的是**格里逐字包含 trigger 整串**,不是相等 ——
    要求相等会把每一条合规的都打红。

    ---- 方向:表是源,日志是抄件 ----
    SKILL 第 387 行写明日志由速览表整理而来,所以两者不一致时**错的是日志**
    (处置文案照此写)。git 证据(本轮实测):日志最后一次写入 `eef783e`,
    五份日报重生成于 `ee7a2c6`,`git merge-base --is-ancestor eef783e ee7a2c6`
    为真 —— 日志确实是旧的那一份。

    date : 当日日期。**取自快照的 `date` 字段**(脚本产出),不从报告正文里
           抓 —— 报告是被查对象,让它自己说"我是哪一天"就等于把闸门的输入
           交给被查方(与 V7/V8/V12 三条真绕过同型)。

    notes : **出参**,同 check_daily。日志里没有当日/该币种条目 → 带计数声明。
    """
    v = []
    rows = overview_rows(secs)
    if not rows:
        return v          # overview_rows 已出 OVERVIEW_TABLE_* 声明,不重复
    checked, absent = 0, []
    for c in CURRENCIES:
        cell = (rows.get(c) or {}).get(OVERVIEW_COL_TRIGGER)
        if cell is None:
            continue      # 该币种没有速览行,OVERVIEW_ROW_MISSING 已声明
        entry = entries.get((date, c))
        trigger = entry.get("trigger") if isinstance(entry, dict) else None
        if not isinstance(trigger, str) or not trigger.strip():
            absent.append(c)
            continue
        checked += 1
        if trigger not in cell:
            v.append("DECISION_TRIGGER_NOT_SOURCED: 速览表 %s 行的「%s」格"
                     "没有逐字包含决策日志 %s/%s 的 trigger;"
                     "日志原文:「%s」;速览原文:「%s」;%s"
                     % (c, OVERVIEW_COL_TRIGGER, date, c, trigger, cell,
                        DISPOSITION_DECISION_TRIGGER))
    if absent and notes is not None:
        notes.append("DECISION_LOG_NO_ENTRY: 决策日志里没有 %s 的 %d/%d 个币种"
                     "条目(%s,或条目的 trigger 缺失/为空),这些币种的"
                     "「条件方向」同源同字未校验(已校验 %d 个)"
                     % (date, len(absent), len(CURRENCIES),
                        "、".join(absent), checked))
    return v


def review_sentences_in_brief(brief_text):
    """要点表复盘材料块里每条**结论行**的复盘句。顺序保留,便于逐条报错。

    只取结论行(`… | 复盘句: … | 结论: …`):顺延登记行按定义没有结论,
    要求把它抄进复盘节等于要求给未到期的观点写复盘。
    """
    out = []
    _, exempt, _ = split_brief_review_block(brief_text)
    for line in exempt:
        m = REVIEW_MATERIAL_RE.fullmatch(line.rstrip())
        if not m:
            continue
        head, _, tail = line.rstrip().partition(" | 复盘句: ")
        sentence, _, _ = tail.rpartition(" | 结论: ")
        if sentence:
            out.append(sentence)
    return out


def check_review_sentence_quoted(secs, brief_text, notes=None):
    """`REVIEW_SENTENCE_NOT_QUOTED` —— 复盘句必须逐字落在**正文的复盘节**。

    ---- 为什么必须有这一码 ----
    「结论由脚本给出、报告逐字引用」此前**只是 SKILL 里的散文**:脚本算出的
    结论走到报告边界就没人看着了,改一个字、漏抄一条、或者自己另写一个结论词,
    六份产物照样全绿。本仓库为此栽过 13 次同型,教训写在案上 ——
    prompt 禁令堵不住,要改成不变量。

    ---- 判据 ----
    整句**逐字包含**,且必须落在复盘节里,不是整份文件里随便哪儿。位置这一半
    不可省:判定类结论要在正文被读者看见,抄进附录等于没抄。
    """
    v = []
    sentences = review_sentences_in_brief(brief_text)
    sec = find_section(secs, "复盘")
    body = sec[1] if sec else ""
    for sentence in sentences:
        if sentence not in body:
            v.append("REVIEW_SENTENCE_NOT_QUOTED: 复盘节没有逐字包含要点表"
                     "复盘材料给出的这一句:「%s」;%s"
                     % (sentence, DISPOSITION_REVIEW_QUOTE))
    if notes is not None:
        notes.append("REVIEW_SENTENCE_CHECKED: 要点表给出 %d 条复盘句,"
                     "已逐句比对是否逐字落在复盘节" % len(sentences))
    return v


def check_decision_claim(date, entries, notes=None):
    """`DECISION_CLAIM_NOT_SOURCED` —— 结构化观点必须逐字溯源到散文 trigger。

    ---- 为什么必须由校验器管 ----
    `claim` 是**判定入口**:`scripts/claims.resolve_claim` 只读结构化字段,
    读者却只看得到散文 trigger。两者一旦不同源,同一条观点在"写出来的话"与
    "拿去判的量"上各说各话,而这种漂移没有任何自然后果会暴露它 —— 判定照常
    给出四档之一,只是判的不是读者以为的那件事。

    ---- 判据与登记入口共用一份 ----
    `claims.validate_claim` 同时是 `log_decision.py add / set-claim` 的入口
    校验。两处各写一遍必然漂移,而漂移的后果是一条路放行、另一条打红,
    两种都会被当成"另一边的 bug"绕过去。

    date : 当日日期,取自**快照**的 `date` 字段(脚本产出),不从报告正文里
           抓 —— 让被查对象自己说"我是哪一天"就是把闸门输入交给被查方。

    notes : **出参**。结构化字段之前登记的条目没有 `claim`,判不了也不该判红;
            但"没查"与"查过且全过"必须可分辨,故带计数声明。
    """
    v = []
    checked, absent = 0, []
    for c in CURRENCIES:
        entry = entries.get((date, c))
        if not isinstance(entry, dict):
            continue      # 该币种当日无条目,DECISION_LOG_NO_ENTRY 已声明
        if "claim" not in entry:
            absent.append(c)
            continue
        checked += 1
        for problem in claims.validate_claim(entry.get("claim"),
                                             entry.get("trigger")):
            # 问题串自己已经带上 trigger 原文,这里不再重复一遍 ——
            # 同一句话在一行违规里出现两次,读者会以为是两处不同的证据。
            v.append("DECISION_CLAIM_NOT_SOURCED: 决策日志 %s/%s 的结构化观点"
                     "与散文 trigger 对不上 —— %s;%s"
                     % (date, c, problem, DISPOSITION_DECISION_CLAIM))
    if absent and notes is not None:
        notes.append("DECISION_CLAIM_ABSENT_SKIPPED: 决策日志 %s 有 %d/%d 个"
                     "币种条目没有结构化观点字段(%s,结构化字段之前登记的),"
                     "这些条目的阈值溯源未校验(已校验 %d 个)"
                     % (date, len(absent), len(CURRENCIES),
                        "、".join(absent), checked))
    return v


# ---- 周报侧判断环的宿主:`## 本周主线` 之下的 `### 主线N` 子节 ----
# 实测 reports/weekly/2026-W33.md 的结构:五个 `### 主线N:…(影响 …)` 子节,
# 每个自带 **关键假设 / 替代解释 / 翻转指标** 三件(实测 27 处标签)。
# 币种在周报里**没有自己的节**(`## 各币种一周落点` 是一张表),所以判断环的
# 宿主只能是主线段 —— 按币种取会一个都取不到,那正是"整层不查"的来源。
WEEKLY_THEME_SECTION_KEY = "本周主线"


def theme_subsections(secs):
    """`## 本周主线` 之下的 `### ` 子节 → [(标题, 正文)];没有则空列表。

    `sections()` 只在 `## ` 处切,`### ` 行原样留在节正文里,所以这里在
    节正文上再切一层。节定位仍走 `find_section`(重名返回 None → 空列表,
    失败关闭与别处同规矩)。
    """
    sec = find_section(secs, WEEKLY_THEME_SECTION_KEY)
    if sec is None:
        return []
    out, cur, buf = [], None, []
    for line in sec[1].splitlines():
        if line.startswith("### "):
            if cur is not None:
                out.append((cur, "\n".join(buf)))
            cur, buf = line[4:].strip(), []
        elif cur is not None:
            buf.append(line)
    if cur is not None:
        out.append((cur, "\n".join(buf)))
    return out


def check_weekly_judgement_ring(secs, report, allowed, notes=None):
    """判断环三码在**周报模式**的执行入口。

    ---- 修前:整层不查 ----
    实测(先跑后抄)周报模式打出的是
      `WEEKLY_JUDGEMENT_LAYER_SKIPPED: …本份周报里有 27 处判断环标签
       (关键假设 8、替代解释 5、翻转指标 14)未校验`
    也就是三码在周报上的执行次数是 **0**,而周报里照样写满了判断环。
    声明本身是上一轮补的,它照出的洞就是这一条。

    ---- 闸门:结构闸门 ----
    日报侧**没有闸门**:覆盖到的币种节全查(2026-08-14 起,见
    `check_judgement_ring`)。周报侧的段落不像币种节那样有固定清单,所以
    这里用**结构闸门**:`## 本周主线` 之下的 `### ` 子节。理由:判断环写在
    哪里与主线段在哪里是同一件事 —— 有主线段才有判断环,没有主线段时三码
    无处可判,不是"查过且全过"。闸门不成立时照旧出
    `WEEKLY_JUDGEMENT_LAYER_SKIPPED` 并带计数(标签数就是"漏掉了多少"的度量)。
    凭标题猜"这一段该不该有判断环"那条路刻意不选:猜就是编造。

    allowed : 见 `_check_one_ring`。`None`(未提供 --digest)时 ③ 不判并出声。
    """
    v = []
    themes = theme_subsections(secs)
    if not themes:
        if notes is not None:
            notes.append("WEEKLY_JUDGEMENT_LAYER_SKIPPED: 周报没有可用的"
                         "「%s」H3 主线子节,判断环三码(%s)无处可判;"
                         "本份周报里有 %d 处判断环标签(%s)未校验"
                         % (WEEKLY_THEME_SECTION_KEY,
                            "/".join(("JUDGEMENT_RING_INCOMPLETE",
                                      "FLIP_INDICATOR_IS_INVALIDATION_RESTATED",
                                      "ASSUMPTION_UNANCHORED")),
                            sum(report.count(lab) for lab in RING_LABELS),
                            "、".join("%s %d" % (lab, report.count(lab))
                                      for lab in RING_LABELS)))
        return v
    if allowed is None and notes is not None:
        notes.append("WEEKLY_ASSUMPTION_ANCHOR_SKIPPED_NO_DIGEST: 未提供 "
                     "--digest,可溯源数字白名单建不起来,%d 个主线段的 "
                     "ASSUMPTION_UNANCHORED 未校验(另两码照常执行)"
                     % len(themes))
    unreachable = []
    for heading, body in themes:
        # 段名取标题里冒号之前那一截(`主线一:…` → `主线一`),违规行要靠它
        # 定位到具体哪一段;整条标题太长,打出来读者反而找不到重点
        name = re.split(r"[::]", heading, 1)[0].strip() or heading
        found, flip_unreachable = _check_one_ring(name, body, allowed)
        v.extend(found)
        if flip_unreachable:
            unreachable.append(name)
    if unreachable and notes is not None:
        notes.append("FLIP_INDICATOR_CHECK_UNREACHABLE: %d/%d 个主线段(%s)"
                     "写了「%s」但判不出失效条件句(找的标签:%s),② 在这些段未执行"
                     % (len(unreachable), len(themes), "、".join(unreachable),
                        FLIP_LABEL, "/".join(INVALIDATION_LABELS)))
    return v


def check_daily(report, snapshot_text, brief_text, strict_brief=True, notes=None,
                prior_text=None, decision_entries=None):
    """日报结构 + 数字溯源 + 结论句逐字引用检查,返回违规列表。

    strict_brief : 「要点表数字 ⊆ 快照」这一层。**默认 True** —— 强判定是
            默认,弱化必须是显式动作(CLI 侧唯一入口是 `--no-strict-brief`)。
            修前默认是 False,于是"忘了传"与"决定不查"在调用点上不可分辨,
            与 CLI 侧那三条 fail-open 是同一个病、只低一层。
            传 False 时会往 notes 追加 STRICT_BRIEF_DISABLED(带计数)。

    prior_text : 上一份日报正文;`None` 表示**没提供**,跨期逐字重复整条
            不检查,并往 notes 追加 PRIOR_PERIOD_ABSENT_SKIPPED。空串是
            "提供了但内容为空"的合法形态,走 check_prior_period 的第三态。
            **CLI 走不到 `None` 这一支**:`--prior` 已是必给,缺席即 rc=2。
            声明留在这一层而不是 CLI 层,理由是"跳过的那一层负责出声" ——
            放在 CLI 层时,任何别的调用方传 None 都会静默跳过。

    decision_entries : 决策日志条目;`None` 同上,追加
            DECISION_LOG_ABSENT_SKIPPED。CLI 侧同样已收成 rc=2。

    notes : **出参**。传入的 list 会被追加「非违规的降级声明」
            (VERDICT_SKIPPED_LEGACY / VERDICT_SKIPPED_NO_DERIVED)。
            不传等于放弃这些声明 —— 此时退出码 0 既可能表示「全查过了」
            也可能表示「一条都没查」,两者不可分辨,正是本检查要消灭的形态。
            CLI 调用方必须传并打印。
            check_weekly 没有对应参数:那一侧 required 恒为 True,缺字段
            直接进 violations,不会产生跳过。
    """
    v = []
    secs = sections(report)
    snap, snap_problems = parse_snapshot(snapshot_text)
    for p in snap_problems:
        v.append("SNAPSHOT_MALFORMED: " + p)

    # ---- 节定位唯一化,**最先做**:见 find_section 的失败关闭说明 ----
    # 下面每一处 `find_section` 都依赖"恰好一个匹配";重名时它返回 None,
    # 而 None 在既有分支里的含义是"缺失" —— 所以歧义键必须在这里先拦住,
    # 否则会打出「缺少币种节 PHP」而报告里明明有两节,自相矛盾。
    amb = ambiguous_sections(secs, DAILY_REPORT_SECTION_KEYS)
    v.extend(ambiguity_violations(secs, DAILY_REPORT_SECTION_KEYS, "报告"))
    brief_secs = sections(brief_text)
    brief_amb = ambiguous_sections(brief_secs, BRIEF_SECTION_KEYS)
    v.extend(ambiguity_violations(brief_secs, BRIEF_SECTION_KEYS, "要点表"))

    covered = set()
    for c in CURRENCIES:
        if c in amb:
            # 失败关闭:歧义币种不进 covered,判断环/归属/结论句三层都不查它。
            # SECTION_AMBIGUOUS 已经把这一处打红,不再叠一条 SECTION_MISSING
            continue
        if find_section(secs, c):
            covered.add(c)
        else:
            # covered 与 SECTION_MISSING 必须互为补集 —— check_verdicts 的
            # 「让位 ①」依赖这一点。建在同一个循环里,物理上保证两者一起改
            # (check_weekly 的注释这么写,而日报侧此前分两处算)
            v.append("SECTION_MISSING: 缺少币种节 %s" % c)
    s = find_section(secs, "执行摘要")
    if "执行摘要" in amb:
        pass                                  # 已出 SECTION_AMBIGUOUS
    elif not s:
        v.append("SECTION_MISSING: 缺少执行摘要")
    elif len(list_items(s[1])) > MAX_SUMMARY_ITEMS:
        v.append("SUMMARY_TOO_LONG: 执行摘要 %d 条 > %d"
                 % (len(list_items(s[1])), MAX_SUMMARY_ITEMS))
    for c in CURRENCIES:
        sec = find_section(secs, c)
        if sec:
            n = len(CJK_RE.findall(sec[1]))
            if n > MAX_SECTION_CJK:
                v.append("SECTION_TOO_LONG: %s 节 %d 中文字 > %d" % (c, n, MAX_SECTION_CJK))
    rev = find_section(secs, "复盘")
    if "复盘" not in amb and (not rev or not rev[1].strip()):
        v.append("SECTION_MISSING: 缺少复盘节(首次运行也须保留并注明)")

    gap_sec = find_section(secs, "数据缺漏")
    if "数据缺漏" in amb:
        pass                                  # 已出 SECTION_AMBIGUOUS
    elif not gap_sec:
        v.append("SECTION_MISSING: 缺少数据缺漏节")
    elif snap is not None:
        gaps_raw = snap.get("gaps", [])
        if isinstance(gaps_raw, list):
            body = gap_sec[1].strip()
            if gaps_raw and (not body or body == "无"):
                v.append("GAPS_NOT_DISCLOSED: 快照有 %d 条缺漏但缺漏节为空/无" % len(gaps_raw))
            if not gaps_raw and body != "无":
                v.append("GAPS_MISMATCH: 快照无缺漏,缺漏节应恰为「无」")
            for g in gaps_raw:
                if not isinstance(g, dict):
                    continue    # 已在 SNAPSHOT_MALFORMED 中逐条报告
                scope = g.get("scope")
                token = scope if isinstance(scope, str) and scope != "all" \
                    else g.get("source")
                if isinstance(token, str) and token and token not in gap_sec[1]:
                    v.append("GAP_OMITTED: 缺漏节未提及 %s/%s"
                             % (g.get("source"), g.get("scope")))
        # gaps 非 list:结构问题已记 SNAPSHOT_MALFORMED,跳过内容比对

    # 结论句逐字引用。闸门只读不写:schema 过旧不让校验失败,只降级并如实
    # 声明降级了几条 —— 「跳过」与「通过」在输出上必须可区分。
    # 判据取 schema 版本而非"这个键在不在":后者会让**新代码产出却漏写该
    # 字段**的缺陷与存量快照完全同形,静默通过。
    derived = snap.get("derived") if isinstance(snap, dict) else None
    has_derived = isinstance(derived, dict)
    derived = derived if has_derived else {}
    ver = derived.get("schema_version")
    ver_ok = (isinstance(ver, int) and not isinstance(ver, bool)
              and ver >= DERIVED_VERDICT_SCHEMA)
    events = derived.get("events")
    # ③ 没有派生节:不是违规,但**必须出声明** —— 此前这一形态跑出裸
    # CHECK PASSED、零声明,与「全部结论句已核验」不可分辨,而实测
    # data/2026-08-07..10.json 四天都是它,六天里占了四天
    if not has_derived and notes is not None:
        notes.append("VERDICT_SKIPPED_NO_DERIVED: 快照无 derived 节,"
                     "本次未校验任何结论句")
    # ①② 只对「声称带结论句」的快照生效:ver_ok 为假时照旧跳过,否则
    # 存量快照(derived 为 null 或 schema=1)会集体变红。
    # ver_ok 为真时容器与条目都不再是可选的 —— 与 check_weekly 对称,
    # 谓词不越权判结构,兜底在调用点(见 check_verdicts 的 docstring)。
    if ver_ok and not isinstance(events, dict):
        v.append("VERDICT_CONTAINER_MALFORMED: 快照的 derived.events 不是对象"
                 "(实为 %s),derived.events 下的结论句一条都未校验;%s"
                 % (type(events).__name__, DISPOSITION_SCRIPT_BUG))
    elif ver_ok:
        # 日报五个币种都应有事件派生量(derive 按 rates ∪ events.KEYWORDS
        # 逐币种填充),整条缺失不是合法形态 —— 与周报的 rates 容器不同,
        # 那里基准货币本就没有条目
        present = {k for k, entry in events.items()
                   if isinstance(entry, dict)}
        # 判据必须是「值为 dict 的键集」而不是键存在性:check_verdicts 对非
        # dict 条目静默 continue(周报侧基准货币在 rates 里本就没条目,那是
        # 必需的),用 set(events) 会让「条目在、但是 null/字符串/列表」
        # 原样静默通过 —— 与「条目缺失」同因同果,必须同判
        for c in sorted(covered - present):
            v.append("VERDICT_ENTRY_MISSING: derived.events 缺少 %s 的条目;"
                     "该币种的结论句一条都未校验;%s"
                     % (c, DISPOSITION_SCRIPT_BUG))
    found, skipped = check_verdicts(report, events,
                                    VERDICT_FIELD_DAILY, covered,
                                    required=ver_ok, label="derived.events")
    v.extend(found)
    checked = {c for c in covered
               if isinstance(events, dict) and isinstance(events.get(c), dict)}
    if skipped and notes is not None:
        notes.append("VERDICT_SKIPPED_LEGACY: %d/%d 个覆盖币种因快照 schema 过旧"
                     "(derived.schema_version=%r)未校验结论句"
                     % (skipped, len(covered), ver))
    elif (has_derived and not ver_ok and covered and not checked
            and notes is not None):
        # schema 旧、且连一个可查条目都没有:skipped 恒为 0,上一条不会触发。
        # 不补这一档,「derived 在但空」会退回裸 CHECK PASSED、零声明 ——
        # 与 ③ 档要消灭的形态一字不差,只是分支不同
        notes.append("VERDICT_SKIPPED_LEGACY: %d/%d 个覆盖币种因快照 schema 过旧"
                     "(derived.schema_version=%r)未校验结论句"
                     % (len(covered), len(covered), ver))

    allowed = numbers_in(snapshot_text) | numbers_in(brief_text) | ALLOWED_SMALL
    for n in sorted(numbers_in(report) - allowed):
        v.append("NUMBER_UNTRACEABLE: 数字 %s 不见于快照或要点表" % n)
    # 判断环三码必须在 `allowed` 算完之后:③ 的锚点判据逐字复用同一个白名单,
    # 它自己不另建一份 —— 另建就等于给报告开了第二条数字来源。
    v.extend(check_judgement_ring(secs, covered, allowed, notes=notes))
    # 数字归属两码同样排在 `allowed` 之后:映射检查的候选集是**已可溯源**的
    # 那些数,编造的数由 NUMBER_UNTRACEABLE 单独管,同一个 token 不得吃两条。
    if brief_amb:
        # 要点表按 `## <币种>` 切池;那一侧重名时数字池会**少掉一整节**,
        # 归属这一层于是对着残缺的池假报一串违规。失败关闭 = 不判并出声,
        # 红由 SECTION_AMBIGUOUS 出(它已经在 v 里了)
        if notes is not None:
            notes.append("NUMBER_WRONG_SECTION_SKIPPED_NO_SLICE: 要点表有 %d 个"
                         "节键(%s)重名,数字池切不出来,所有币种节的数字归属"
                         "未校验" % (len(brief_amb), "、".join(brief_amb)))
    elif isinstance(snap, dict):
        v.extend(check_number_section_mapping(secs, snap, brief_text, covered,
                                              allowed, notes=notes))
        v.extend(check_summary_number_attribution(secs, snap, brief_text,
                                                  allowed, notes=notes,
                                                  ambiguous=amb))
    elif notes is not None:
        # 快照顶层不是对象:已记 SNAPSHOT_MALFORMED,但归属这一层确实一条
        # 都没查过,不出声就与"全查过且全过"同形
        notes.append("NUMBER_WRONG_SECTION_SKIPPED_NO_SLICE: 快照顶层不是对象,"
                     "所有币种节的数字归属未校验")
    v.extend(check_summary_numbers_in_body(secs, notes=notes, ambiguous=amb))
    if strict_brief:
        # 报告 ⊆ 快照∪要点表 一直有校验,但要点表本身 ⊆ 快照 从来没人查——
        # 要点表环节写错的数字会被下游当作合法来源。此开关堵住这条缝。
        #
        # 但白名单是「**当日**快照 ∪ 小整数」,而 scripts/review.py 往要点表
        # 尾部追加的复盘材料写的是**观点日**的定盘价与观点原文里的数字——
        # 两条规则结构性互斥,且必然复发:SKILL 要求 trigger 绑市场可观测
        # 变量,合规的 trigger 必然带数字。以前不发作,只因为历史 trigger 全是
        # 「采集恢复」这类**违规的**自指形态。实测 2026-08-10 与 08-13 各
        # 4 条 BRIEF_NUMBER_UNTRACEABLE,报告正文零违规,炸的全是脚本自己
        # 写进要点表的行。故按块头切段,只豁免生成行。
        traced, exempt, heads = split_brief_review_block(brief_text)
        if heads > 1:
            v.append("BRIEF_REVIEW_BLOCK_MALFORMED: 要点表出现 %d 个复盘材料块头"
                     "(应为 0 或 1),本次不豁免任何行" % heads)
        elif heads == 1 and notes is not None:
            # 豁免必须出声——「跳过」与「通过」在输出上必须可区分,与
            # VERDICT_SKIPPED_LEGACY / VERDICT_SKIPPED_NO_DERIVED 同一原则。
            # 它不是违规,不改退出码。
            notes.append("BRIEF_REVIEW_BLOCK_SKIPPED: 复盘材料块 %d 行未纳入"
                         "要点表数字溯源" % len(exempt))
        brief_allowed = numbers_in(snapshot_text) | ALLOWED_SMALL
        for n in sorted(numbers_in("\n".join(traced)) - brief_allowed):
            v.append("BRIEF_NUMBER_UNTRACEABLE: 要点表数字 %s 不见于快照" % n)
    elif notes is not None:
        # 弱化是**显式动作**(CLI 侧唯一入口 `--no-strict-brief`),但显式不等于
        # 静默:退出码回到 0 时,"这一层没跑"与"跑了且全过"在 stdout 上必须
        # 可分辨 —— 与 WEEKLY_DIGEST_ABSENT_SKIPPED / BRIEF_REVIEW_BLOCK_SKIPPED
        # 同一原则。声明必须带计数,否则读者不知道放过了多大一块。
        traced, exempt, _ = split_brief_review_block(brief_text)
        notes.append("STRICT_BRIEF_DISABLED: 显式关闭了「要点表 ⊆ 快照」校验,"
                     "要点表 %d 个数字未校验是否见于快照"
                     "(BRIEF_NUMBER_UNTRACEABLE 整层不跑);"
                     "另有复盘材料块 %d 行本就在豁免内"
                     % (len(numbers_in("\n".join(traced))), len(exempt)))
    if prior_text is not None:
        v.extend(check_prior_period(report, prior_text, notes=notes,
                                    ambiguous=amb))
    elif notes is not None:
        # 「没给上一份日报」在**库这一层**仍是合法形态,不是违规、不改退出码
        # —— 但它若跑出裸 CHECK PASSED,就与「比对过且没有套话」逐字不可分辨。
        # CLI 侧已把它收成 rc=2(`--prior` 必给),这条声明守的是别的调用方。
        notes.append("PRIOR_PERIOD_ABSENT_SKIPPED: 未提供上一份日报,"
                     "本次未校验「本期相对上期的变化」节的跨期逐字重复")
    if decision_entries is None and notes is not None:
        # 与上一条同规矩:CLI 侧 `--decision-log` 已必给(缺席 rc=2),
        # 这条声明守的是别的调用方,并且必须带计数。
        notes.append("DECISION_LOG_ABSENT_SKIPPED: 未提供决策日志,"
                     "%d 个币种的速览「%s」与决策日志 trigger 的同源同字"
                     "未校验" % (len(CURRENCIES), OVERVIEW_COL_TRIGGER))
    # ---- 速览表那一层:先解析一次,两个用途共用 ----
    # ① 决策日志同源同字(`check_decision_trigger`);
    # ② 「失效条件」列与翻转指标同字的声明(`check_overview_invalidation_column`)。
    # 解析放在这里而不是各自解析:两处各解析一次会各打一遍
    # OVERVIEW_TABLE_* 声明,读者看到的是同一件事说两遍。
    if OVERVIEW_SECTION_KEY not in amb:
        rows = overview_rows(secs, notes=notes)
        bodies = {c: find_section(secs, c)[1] for c in sorted(covered)}
        check_overview_invalidation_column(rows, bodies, notes=notes)
        if decision_entries is not None:
            date = snap.get("date") if isinstance(snap, dict) else None
            if isinstance(date, str) and date:
                v.extend(check_decision_trigger(secs, date, decision_entries,
                                                notes=notes))
                v.extend(check_decision_claim(date, decision_entries,
                                              notes=notes))
            elif notes is not None:
                # 快照没有可用的 date:判不出该查日志的哪一天。猜"今天"就是
                # 编造(校验器不读时钟,与不读环境同一条理由),所以只声明。
                notes.append("DECISION_LOG_NO_ENTRY: 快照没有可用的 date 字段"
                             "(实为 %r),判不出该比对哪一天的决策日志,"
                             "%d 个币种的「%s」同源同字未校验"
                             % (date, len(CURRENCIES), OVERVIEW_COL_TRIGGER))
    # ---- 复盘句逐字进正文 ----
    # 放在最后是有意的:它是「要点表 → 报告」这一族的检查,与 strict_brief
    # 同源;而既有多条用例按**位置**断言 notes[0],插在前面会把它们全打乱,
    # 那是改测试而不是改行为。
    if "复盘" not in amb:
        v.extend(check_review_sentence_quoted(secs, brief_text, notes=notes))
    elif notes is not None:
        notes.append("REVIEW_SENTENCE_SKIPPED_AMBIGUOUS: 复盘节标题重名,"
                     "切不出唯一的复盘节,%d 条复盘句的逐字引用未校验"
                     % len(review_sentences_in_brief(brief_text)))
    return v


def _read_file(path, label):
    """读取输入文件;失败返回 (None, rc=2 前的 stderr 说明)。"""
    try:
        with open(path, encoding="utf-8") as f:
            return f.read(), None
    except (OSError, UnicodeDecodeError) as e:
        return None, "无法读取%s %s: %s" % (label, path, e)


# ==================== 日报模式:强判定是默认(2026-08-14)====================
#
# 本仓第 15 次同型缺陷(「打印通过,但守的不是它声称的东西」)的修法。
# 修前三个溯源入参都是「不给就自动弱化」:`--prior` 与 `--decision-log` 各打
# 一条降级声明后 **rc=0**,`--brief` 连声明都没有 —— `BRIEF_NUMBER_UNTRACEABLE`
# 整层静默蒸发。上一轮给 `--decision-log` 配的强制力是
# `skills/fx-daily-report/SKILL.md` 里一句「这一条**必须带上**」的散文,
# 而散文对返回码没有任何作用:忘带参数 = 闸门消失 = rc=0。
# 现在与 weekly 拒收位置参数那一轮同规格:**缺一个即 rc=2**。
DAILY_DECISION_LOG_DEFAULT = "state/decision-log.jsonl"
# (选项, 它守的那道闸门)。**这份清单只有一份**:main() 判缺、消息列项、
# 补全命令行三处都读它,不许在别处再抄一遍(第二份拷贝必然漂移,本仓已栽过)。
DAILY_REQUIRED_OPTIONS = (
    ("--brief",
     "守「要点表数字 ⊆ 快照」(BRIEF_NUMBER_UNTRACEABLE / "
     "BRIEF_REVIEW_BLOCK_MALFORMED),并把要点表并入报告数字白名单"),
    ("--prior",
     "守「本期相对上期的变化」节不得逐字重复上期(PRIOR_PERIOD_BOILERPLATE)"),
    ("--decision-log",
     "守速览「条件方向」格逐字包含决策日志同日同币种的 trigger"
     "(DECISION_TRIGGER_NOT_SOURCED)"),
)
# 只用来从路径里认出日期,**与 DATE_RE 无关**(那一条服务正文里的日期措辞,
# 本轮一个字符都不动)。
ISO_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _iso_date_in(path):
    m = ISO_DATE_RE.search(path or "")
    return m.group(0) if m else None


def daily_default_paths(report, snapshot):
    """三个必给入参的**可执行默认值**,按仓库标准布局推。

    日期取自报告路径,取不到再取快照路径。`--prior` 落在报告**自己那个
    目录**下(不写死 `reports/daily/`),所以对着任意目录里的一份日报跑,
    补出来的上一份也在同一处。
    两处都认不出日期时给尖括号占位符:猜一个日期出来会让人把命令粘到
    **别的日子**那份报告上,比看得见的占位符危险得多。
    """
    date = _iso_date_in(report) or _iso_date_in(snapshot)
    if not date:
        return {"--brief": "briefs/<YYYY-MM-DD>-brief.md",
                "--prior": "reports/daily/<前一日>.md",
                "--decision-log": DAILY_DECISION_LOG_DEFAULT}
    try:
        prev = (datetime.date.fromisoformat(date)
                - datetime.timedelta(days=1)).isoformat()
    except ValueError:                       # 形如 2026-13-45 的假日期
        prev = "<前一日>"
    head = report.rsplit("/", 1)[0] + "/" if "/" in (report or "") else ""
    return {"--brief": "briefs/%s-brief.md" % date,
            "--prior": "%s%s.md" % (head, prev),
            "--decision-log": DAILY_DECISION_LOG_DEFAULT}


def daily_required_options_error(report, snapshot, brief, prior, decision_log,
                                 missing):
    """rc=2 的消息:**必须可执行**,不是「缺少参数」四个字。

    「缺少参数」不可执行 —— 运维得回去翻 SKILL 才知道该写什么、以及少掉的
    是哪一道闸门。所以这里给三样:缺了谁、每个入参守的是哪条码、以及
    **一整行能直接复制粘贴的正确命令行**(已给的值原样带回,缺的按仓库
    标准布局补齐)。测试对这一行的判据不是"提到了缺什么",而是把它切开
    原样跑一遍必须 rc=0 —— 只断言"提到了"时,印一条跑不通的命令行照样全绿。
    """
    given = {"--brief": brief, "--prior": prior,
             "--decision-log": decision_log}
    default = daily_default_paths(report, snapshot)
    argv = [report, snapshot]
    lines = ["DAILY_REQUIRED_OPTION_MISSING: 日报模式的三个溯源入参必须显式给,"
             "本次缺少 %s。缺席不再等于「自动弱化」,而是用法错误 rc=2 —— "
             "此前它们缺席时最多打一条降级声明、退出码仍是 0,"
             "于是忘带参数与闸门整层不跑在输出上不可分辨。" % "、".join(missing)]
    for opt, guard in DAILY_REQUIRED_OPTIONS:
        value = given[opt] or default[opt]
        lines.append("  [%s] %s %s —— %s"
                     % ("缺" if opt in missing else "已给", opt, value, guard))
        argv += [opt, value]
    lines.append("`--decision-log` 的默认路径就是 %s(全仓只有这一份日志)。"
                 % DAILY_DECISION_LOG_DEFAULT)
    lines.append("把下面这一整行复制粘贴执行"
                 "(已给的值原样保留,缺的按仓库标准布局补齐):")
    lines.append("python3 scripts/check_report.py "
                 + " ".join(shlex.quote(a) for a in argv))
    lines.append("要弱化「要点表 ⊆ 快照」那一层,唯一入口是 `--no-strict-brief`,"
                 "它会打印带计数的声明;少写一个参数不再是弱化的入口。")
    return "\n".join(lines)


def build_parser():
    """选项的注册处。单独成函数是为了让测试查得到注册表本身:从 `--help` 的
    输出反推开关集合守不住 `help=argparse.SUPPRESS` 的隐藏开关(argparse 根本
    不打印它),而"悄悄加一个豁免开关"正是 Design Doc §6 点名要挡的绕过点。
    实测:以 SUPPRESS 注册 `--tolerant` 并在 main 里据它滤掉整类 `VERDICT_*`
    违规,rc 由 1 变 0,而全量 674 全绿。

    **它不是"CLI 开关的唯一注册处"** —— 这句旧说法已被四条实测证伪
    (T8b 复验,四种各自一行的改法都让同一份输入 rc 1→0):
    ① 这里加一个**位置参数**(`option_strings` 为空,冻结选项名集合的断言
    收不到它);② 根本不动注册表,直接复用既有参数的**魔法值**
    (weekly 模式下 `args.snapshot` 不读);③ 只给 `--mode` 加一个 choices
    (`option_strings` 逐字不变);④ 在 main 里把 `parse_args` 换成
    `parse_known_args` 并读 `_rest`(**零注册**,而 `--tolerant` 字面可用)。

    **更正(2026-08-14):② 括号里那半句已不再成立,而它当时描述的是一条真
    缺陷,不只是一条假想绕过。** 「weekly 模式下 `args.snapshot` 不读」在这里
    被当作"可以拿来当豁免扳机的性质"写了下来,却没人把它当缺陷修掉 —— 于是
        check_report.py <weekly.md> <digest.json> --mode weekly
    这条形态一直静默放行:`--digest` 缺席 → 结论句闸门与数字溯源整层不跑,
    照样 `CHECK PASSED` rc=0。决定性实测(HEAD eef783e):把那个位置参数换成
    `/does/not/exist.json`,**仍然 CHECK PASSED rc=0**。
    现在 weekly 分支收到非空位置参数即 rc=2(见 `main`),所以 ② 这条路已封;
    ①③④ 三条依旧成立,原文保留不删。
    能挡住这四条的是 `tests/test_check_report.py` 里的行为级断言
    (`test_listed_exemption_tokens_cannot_make_verdict_codes_disappear`):
    在**生产命令行的完整形状**(含 `--brief`/`--prior`/`--decision-log`/`--daily`)
    及其每个开关的取反组合上枚举豁免味 token,要求基线上出现过的那组码
    一个都不许少。冻结注册表形状只是辅助。

    **这条断言不是全称命题**,名字里的 "listed" 就是它的边界:守的是
    `EXEMPTION_TOKENS` 词表 × 句法位置 × 开关取反。旧名字写成
    "no argv can …" 时,三条有界缺口逐条被真绕过打穿(T8b 复验):
    base argv 从不带 `--strict-brief` 而生产调用每次都带(于是
    `if args.strict_brief: 滤掉 VERDICT_*` 这一行只在真实运行时生效;
    该开关 2026-08-14 已删除、强判定成为默认,这条实测作为历史记录保留);
    判据只看"stdout 里还有 VERDICT_"而两份输入的违规恰好全是同一个码;
    以及守卫跑在进程内、`sys.argv` 对它天然不可见。
    第三条现在由 `test_production_shapes_stay_red_in_a_real_subprocess`
    用真子进程补上。
    """
    ap = argparse.ArgumentParser()
    ap.add_argument("report")
    ap.add_argument("snapshot", nargs="?")
    ap.add_argument("--brief", default=None,
                    help="daily:要点表路径,**必给**,缺席即 rc=2")
    ap.add_argument("--mode", choices=["daily", "weekly"], default="daily")
    # `--strict-brief` 已**删除**,不留成无操作的兼容开关:no-op 开关等于新造
    # 一个「注册了却没人读」的选项(它会同时进两个 mode 的不读选项表,豁免
    # 扳机面翻倍),而陈旧调用点会**静默地什么都不做** —— 正是本轮要消灭的
    # 形态。删掉之后,任何还带着它的调用点在 argparse 层就 rc=2 响亮死掉。
    ap.add_argument("--no-strict-brief", dest="strict_brief",
                    action="store_false",
                    help="daily:关闭「要点表 ⊆ 快照」校验(默认开启);"
                         "这是**唯一**的弱化入口,且会打印带计数的降级声明")
    ap.add_argument("--digest", default=None,
                    help="weekly:周度聚合文件,启用周报数字溯源")
    ap.add_argument("--daily", action="append", default=[],
                    help="weekly:当周日报路径,可重复;并入数字白名单")
    ap.add_argument("--prior", default=None,
                    help="daily:上一份日报路径,**必给**,缺席即 rc=2;"
                         "启用「本期相对上期的变化」节的跨期逐字重复检查")
    ap.add_argument("--decision-log", default=None,
                    help="daily:决策日志 jsonl 路径(默认布局 %s),**必给**,"
                         "缺席即 rc=2;启用速览「条件方向」与日志 trigger 的"
                         "同源同字检查" % DAILY_DECISION_LOG_DEFAULT)
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    report, err = _read_file(args.report, "报告文件")
    if err:
        print(err, file=sys.stderr)
        return 2
    notes = []
    if args.mode == "daily":
        if not args.snapshot:
            print("daily 模式需要快照路径", file=sys.stderr)
            return 2
        # ---- 强判定是默认:三个溯源入参缺一个即 rc=2 ----
        # 修前这里是三条「不给就自动弱化」的路径。判缺的清单只有
        # `DAILY_REQUIRED_OPTIONS` 一份,消息与补全命令行读的也是它。
        # **必须写在 daily 分支体内**:挪到分支外会让这三个 dest 变成
        # "两个 mode 都读"的,weekly 侧的「不读选项」表随之塌掉一半,
        # 第六族变异整类失去输入(见 tests 的 unread_option_specs)。
        given = {"--brief": args.brief, "--prior": args.prior,
                 "--decision-log": args.decision_log}
        missing = [opt for opt, _ in DAILY_REQUIRED_OPTIONS if not given[opt]]
        if missing:
            print(daily_required_options_error(
                args.report, args.snapshot, args.brief, args.prior,
                args.decision_log, missing), file=sys.stderr)
            return 2
        snapshot_text, err = _read_file(args.snapshot, "快照文件")
        if err:
            print(err, file=sys.stderr)
            return 2
        snap, problems = parse_snapshot(snapshot_text)
        if snap is None or problems:
            for p in problems:
                print("快照损坏: " + p, file=sys.stderr)
            return 2
        brief_text, err = _read_file(args.brief, "要点表文件")
        if err:
            print(err, file=sys.stderr)
            return 2
        prior_text, err = _read_file(args.prior, "上一份日报")
        if err:
            print(err, file=sys.stderr)
            return 2
        log_text, err = _read_file(args.decision_log, "决策日志")
        if err:
            print(err, file=sys.stderr)
            return 2
        decision_entries, problems = parse_decision_log(log_text)
        if problems:
            # 给了却读不成 = 响亮失败,与 --digest 同规格。**不 fail-open**:
            # 静默跳过时调用方以为查了、脚本以为没传,两边都不出声。
            for p in problems:
                print("决策日志损坏: " + p, file=sys.stderr)
            return 2
        violations = check_daily(report, snapshot_text, brief_text,
                                 strict_brief=args.strict_brief, notes=notes,
                                 prior_text=prior_text,
                                 decision_entries=decision_entries)
    else:
        # ---- weekly **不接受位置参数**:那是本文件最后一条静默放行路径 ----
        # `snapshot` 是 `nargs="?"` 的位置参数,而这一支从来不读它 —— 修前
        # `build_parser()` 的 docstring 自己把这件事当"绕过手法之二"写着
        # (「复用既有参数的魔法值(weekly 模式下 `args.snapshot` 不读)」),
        # 却没人把它当缺陷修掉。于是
        #   check_report.py reports/weekly/W.md state/weekly-digest-W.json --mode weekly
        # 看上去把聚合文件传进去了,实际上 `--digest` 缺席 → 结论句闸门与数字
        # 溯源**整层不跑**,照样 `CHECK PASSED` rc=0。
        # 决定性实测(HEAD eef783e,真实产物,未改任何报告):把位置参数换成
        # `/does/not/exist.json` —— **仍然 CHECK PASSED rc=0**,连"文件在不在"
        # 都没查过。
        # **刻意不猜意图**:不把它当 digest 用,哪怕 `--digest` 没给。猜测正是
        # 这条缺陷的来源(调用方以为传了、脚本以为没传,两边都不出声);
        # 猜对一次,下一个人还会只传位置参数。所以只要它非空就 rc=2。
        if args.snapshot:
            print("weekly 模式不接受位置参数快照;周度聚合文件请用 `--digest` "
                  "传入,并用 `--daily` 传入当周全部日报", file=sys.stderr)
            return 2
        if args.daily and not args.digest:
            print("--daily 需与 --digest 同用(单独给日报不会启用数字溯源)",
                  file=sys.stderr)
            return 2
        if args.digest is None:
            # 「未提供聚合文件」是 delta spec 里的**合法**形态(退回结构检查),
            # 不是违规、不改退出码 —— 但它此前跑出的是**裸 CHECK PASSED**,
            # 与"结论句与数字溯源全查过且全过"逐字不可分辨。
            # 「跳过」与「通过」在输出上必须可区分,与 VERDICT_SKIPPED_LEGACY /
            # VERDICT_SKIPPED_NO_DERIVED / BRIEF_REVIEW_BLOCK_SKIPPED 同一原则。
            notes.append("WEEKLY_DIGEST_ABSENT_SKIPPED: 未提供 --digest,"
                         "本次未校验结论句与数字溯源")
        digest_text = None
        if args.digest is not None:
            digest_text, err = _read_file(args.digest, "周度聚合文件")
            if err:
                print(err, file=sys.stderr)
                return 2
            # 校验器打印 PASS 却什么都没查,是最坏的失败模式:digest 为空、
            # 非 JSON、或指向别的文件时必须响亮失败(与快照同规格 rc=2)
            try:
                digest = json.loads(digest_text)
            except (ValueError, RecursionError) as e:
                print("周度聚合文件无法解析: %s" % e, file=sys.stderr)
                return 2
            if not isinstance(digest, dict) or "week" not in digest \
                    or "generated_from" not in digest:
                print("周度聚合文件结构不符(需含 week 与 generated_from)",
                      file=sys.stderr)
                return 2
        daily_texts = []
        for path in args.daily:
            text, err = _read_file(path, "日报文件")
            if err:
                print(err, file=sys.stderr)
                return 2
            daily_texts.append(text)
        violations = check_weekly(report, digest_text, daily_texts,
                                  digest if args.digest is not None else None,
                                  notes=notes)
    # 降级声明先于结论打印:退出码 0 却跳过了几条,读者必须看得见
    for note in notes:
        print(note)
    if violations:
        print("CHECK FAILED (%d):" % len(violations))
        for x in violations:
            print(" - " + x)
        return 1
    print("CHECK PASSED")
    return 0


def check_weekly(report, digest_text=None, daily_texts=(), digest=None,
                 notes=None):
    """周报结构 + 数字溯源 + 结论句逐字引用检查,返回违规列表。

    notes : **出参**,同 check_daily。此前这一侧**没有**这个参数,理由写的是
            「required 恒为 True,缺字段直接进 violations,不会产生跳过」——
            那句话只覆盖了结论句那一层,漏掉了更大的一块:
            **判断环三码与数字归属两码在周报模式下一个都不跑**,而周报里
            照样写满了判断环(reports/weekly/2026-W33.md 实测 27 处标签)。
            于是周报的 stdout 是**裸 `CHECK PASSED`**,与「五层全查过且全过」
            逐字不可分辨 —— 正是这一族检查要消灭的形态。
            整层不查同样要出声,并带计数,见 WEEKLY_JUDGEMENT_LAYER_SKIPPED。
    """
    v = []
    secs = sections(report)
    if notes is not None:
        # ---- 数字归属两码:**结构性不适用**,而"为什么"必须带计数出声 ----
        # 两码的判据是"这个数出自**哪个币种的快照切片**"(见
        # `currency_snapshot_slice`:rates/events/derived.rates/derived.events
        # 按币种分键,derived.real_rate 与 macro 行按经济体分键)。周报的输入
        # 里没有这种东西:`--digest` 是周度聚合、`--daily` 是**已过溯源**的
        # 日报正文,两者都不提供按币种分键的快照切片;`SUMMARY_NUMBER_*` 那一
        # 侧还要一份按 `## <币种>` 分节的要点表,周报流程根本不产出要点表。
        # 没有切片就判不出归属 —— 硬搬过来只会造出一层判不准的红。
        # 「不适用」与「忘了跑」在 stdout 上必须可区分,所以这里不是沉默,
        # 是一条带计数的声明。
        nums = len(numbers_in(report))
        notes.append("WEEKLY_NUMBER_ATTRIBUTION_NOT_APPLICABLE: 数字归属两码"
                     "(%s)在周报模式结构性不适用 —— 周报输入没有按币种分键的"
                     "快照切片、也没有按币种分节的要点表,归属判不出;本份周报"
                     "里 %d 个数字因此只过 NUMBER_UNTRACEABLE 那一层存在性校验,"
                     "%d 个币种的归属未校验"
                     % ("/".join(("NUMBER_WRONG_SECTION",
                                  "SUMMARY_NUMBER_WRONG_CURRENCY",
                                  "SUMMARY_NUMBER_NOT_IN_BODY")),
                        nums, len(CURRENCIES)))
    # 节定位唯一化,理由与 check_daily 同(见 find_section)。周报侧 `本周主线`
    # 重名会让 THEME_TOO_MANY 数错那一节,`缺漏汇总` 重名会让 GAP_OMITTED
    # 对着空节比 —— 两种都是静默放行。
    amb = ambiguous_sections(secs, WEEKLY_REPORT_SECTION_KEYS)
    v.extend(ambiguity_violations(secs, WEEKLY_REPORT_SECTION_KEYS, "周报"))
    for key in WEEKLY_SECTIONS:
        if key not in amb and not find_section(secs, key):
            v.append("SECTION_MISSING: 缺少 %s 节" % key)
    ml = find_section(secs, "本周主线")
    if ml and len(list_items(ml[1])) > MAX_THEME_ITEMS:
        v.append("THEME_TOO_MANY: 本周主线 %d 条 > %d"
                 % (len(list_items(ml[1])), MAX_THEME_ITEMS))
    for h, _ in secs:
        if DATE_HEADING_RE.match(h):
            v.append("DATE_STRUCTURE: 一级结构含日期标题 %s(必须按主题组织)" % h)
    m = COVERAGE_RE.search(report)
    if not m:
        v.append("COVERAGE_MISSING: 缺少「覆盖日报:N 份」声明")
    elif int(m.group(1)) < 3 and "缺失日期" not in report:
        v.append("COVERAGE_GAP_DATES: 覆盖不足 3 份但未注明缺失日期")
    covered = set()
    for c in CURRENCIES:
        if c in report:
            covered.add(c)
        else:
            # covered 与 CURRENCY_MISSING 必须互为补集 —— T3 的「让位 ①」
            # 依赖这一点。建在同一个循环里,物理上保证两者一起改
            v.append("CURRENCY_MISSING: 周报未覆盖 %s" % c)
    rs = find_section(secs, "复盘汇总")
    if rs:
        for tok in REVIEW_TOKENS:
            if tok not in rs[1]:
                v.append("REVIEW_TOKEN_MISSING: 复盘汇总缺少「%s」" % tok)
    allowed = None
    if digest_text:
        # 周报此前完全没有数字溯源(只查结构),数字纪律纯靠 prompt 禁令。
        # 白名单 = 聚合文件 ∪ 当周日报 ∪ 小整数:日报本身已过溯源,链条完整。
        allowed = numbers_in(digest_text) | ALLOWED_SMALL
        for text in daily_texts:
            allowed |= numbers_in(text)
        for n in sorted(numbers_in(report) - allowed):
            v.append("NUMBER_UNTRACEABLE: 数字 %s 不见于周度聚合文件或当周日报" % n)
    # 判断环三码必须排在 `allowed` 之后:③ 的锚点判据逐字复用同一个白名单,
    # 它自己不另建一份 —— 与日报侧同规矩。`allowed` 为 None(未给 --digest)
    # 时 ③ 不判并出声,另两码照常执行。
    v.extend(check_weekly_judgement_ring(secs, report, allowed, notes=notes))
    if isinstance(digest, dict):
        # 与日报的 GAP_OMITTED 对称:聚合出的每个缺漏源都必须在缺漏汇总里出现
        by_source = digest.get("gaps_by_source")
        gap_sec = find_section(secs, "缺漏汇总")
        if isinstance(by_source, dict) and gap_sec:
            for source in sorted(by_source):
                if isinstance(source, str) and source and source not in gap_sec[1]:
                    v.append("GAP_OMITTED: 缺漏汇总未提及 %s" % source)
        # 结论句逐字引用。digest 为 None(未给 --digest)时整块不执行 ——
        # 取不到结论句不等于漏写,不得报 VERDICT_ABSENT。
        # 聚合器的 _rates_digest / _events_one 对每个落盘的币种条目都必写这些
        # 字段,故 required=True:缺失即脚本缺陷。
        for container, fields, label in (
                (digest.get("events"), VERDICT_FIELDS_EVENTS, "digest.events"),
                (digest.get("rates"), VERDICT_FIELDS_RATES, "digest.rates")):
            if not isinstance(container, dict):
                # check_verdicts 对非 dict 容器静默返回空 —— 谓词不越权判结构。
                # 但**没有别处兜底**:main 只校验 week 与 generated_from,
                # 容器坏掉时会打印 CHECK PASSED 而一条结论句都没查,正是本
                # change 要消灭的形态。响亮失败在这里。
                v.append("VERDICT_CONTAINER_MALFORMED: 聚合文件的 %s 不是对象"
                         "(实为 %s),%s 下的结论句一条都未校验;%s"
                         % (label, type(container).__name__, label,
                            DISPOSITION_SCRIPT_BUG))
                continue
            found, _ = check_verdicts(report, container, fields, covered,
                                      required=True, label=label)
            v.extend(found)
    return v


if __name__ == "__main__":
    sys.exit(main())
