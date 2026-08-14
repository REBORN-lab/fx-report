#!/usr/bin/env python3
"""报告校验器:结构 + 数字溯源(文本级逐字比对)。
daily : check_report.py <report.md> <snapshot.json> --brief <brief.md> --mode daily
退出码 0=合规,1=违规(逐条打印),2=用法错误/输入不可读/快照损坏。"""
import argparse
import json
import re
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
    from scripts.review import REVIEW_BLOCK_HEADING, unchanged_ref_note
except ImportError:                                  # pragma: no cover - 直跑分支
    from review import REVIEW_BLOCK_HEADING, unchanged_ref_note

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
# (真行一条都认不出、--strict-brief 的豁免整块失效)不会有人发现。实测就
# 踩过一脚同型的:review.py 那两处括号是 **ASCII** `()`,手抄的正则没转义,
# 式样反而要求「没有括号」。从产出方 re.escape 推出来,括号是全角还是 ASCII
# 都自动对上,这类手抄错误不再可能发生。
_REF_DATE_SLOT = "0000-00-00"                        # re.escape 后再换成日期式样
UNCHANGED_REF_NOTE_PAT = re.escape(unchanged_ref_note(_REF_DATE_SLOT)).replace(
    re.escape(_REF_DATE_SLOT), r"\d{4}-\d{2}-\d{2}")
REVIEW_MATERIAL_RE = re.compile(
    r"- [A-Z]{3} \| 观点日 \d{4}-\d{2}-\d{2} \| 情景: .* \| 触发条件: .*"
    r" \| 关注方向: [^|]* \| (?:汇率 (?:None|[-+0-9.eE]+)→(?:None|[-+0-9.eE]+)"
    r"|" + UNCHANGED_REF_NOTE_PAT + r") \| 方向核对: (?:命中|未命中|无法判定)")
REVIEW_LINE_RES = (
    re.compile(r"\s*"),                                  # 块内空行
    re.compile(r"- 首次运行,无历史观点可复盘"),
    re.compile(r"- 上一运行日\(\d{4}-\d{2}-\d{2}\)无未复盘观点"),
    REVIEW_MATERIAL_RE,
)
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
INVALIDATION_LABELS = ("失效条件", "不成立时", "不成立则", "不成立")
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


def find_section(secs, key):
    for h, b in secs:
        if key in h:
            return h, b
    return None


def numbers_in(text):
    return set(NUM_RE.findall(DATE_RE.sub(" ", text)))


def list_items(body):
    return [line for line in body.splitlines() if LIST_ITEM_RE.match(line)]


def check_prior_period(report, prior_text, notes=None):
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
    """
    v = []
    cur = find_section(sections(report), PRIOR_PERIOD_SECTION_KEY)
    if cur is None:
        return ["PRIOR_PERIOD_SECTION_MISSING: 缺少「%s的变化」节"
                "(周期性产品必须说明本期判断相对上期有何变化);%s"
                % (PRIOR_PERIOD_SECTION_KEY, DISPOSITION_PRIOR_PERIOD)]
    prior = find_section(sections(prior_text), PRIOR_PERIOD_SECTION_KEY)
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
    """
    cut = -1
    for lab in labels:
        p = sentence.rfind(lab)
        if p >= 0:
            cut = max(cut, p + len(lab))
    tail = sentence if cut < 0 else sentence[cut:]
    return _RING_STRIP_RE.sub("", tail)


def check_judgement_ring(secs, derived, covered, allowed, notes=None):
    """判断环三码。**走 `full` 体裁的币种节**才查,体裁由脚本给,不由 LLM 给。

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

    notes : **出参**,同 check_daily。跳过三态各自出声:
            没有 `derived.body_plan`(存量快照,合法)、某币种 `mode` 判不出
            (derive 单币种异常)、`minimal` 体裁豁免。不出声就与「全查过且
            全过」逐字不可分辨。
    """
    v = []
    body_plan = derived.get("body_plan")
    if not isinstance(body_plan, dict):
        # 存量快照(阶段 1 之前采的)合法地没有这个键 —— 判不了体裁就不判,
        # 但必须留下一行。声明里带上 schema_version:读者据它自己分辨
        # 「旧快照」与「新代码产出却漏写了 body_plan」(后者是脚本缺陷)。
        if notes is not None:
            notes.append("JUDGEMENT_RING_SKIPPED_NO_BODY_PLAN: 快照无可用的 "
                         "derived.body_plan(schema_version=%r,实为 %s),"
                         "本次未校验任何币种节的判断环"
                         % (derived.get("schema_version"),
                            type(body_plan).__name__))
        return v
    minimal = []
    for c in sorted(covered):
        entry = body_plan.get(c)
        mode = entry.get("mode") if isinstance(entry, dict) else None
        if mode == "minimal":
            minimal.append(c)
            continue
        if mode != "full":
            # 猜 full 会对着一行正文假报三条违规,猜 minimal 会把有增量的一天
            # 整节放过 —— 两种猜法都是编造。只声明,不判。
            if notes is not None:
                notes.append("JUDGEMENT_RING_SKIPPED_NO_MODE: %s 的 "
                             "derived.body_plan 未给出 minimal/full 体裁"
                             "(实为 %r),该币种节的判断环未校验" % (c, mode))
            continue
        v.extend(_check_one_ring(c, find_section(secs, c)[1], allowed))
    if minimal and notes is not None:
        notes.append("JUDGEMENT_RING_MINIMAL_EXEMPT: %d/%d 个覆盖币种节走 "
                     "minimal 体裁(该节只准写一行,本就没有判断环),未校验"
                     % (len(minimal), len(covered)))
    return v


def _check_one_ring(currency, body, allowed):
    """单个 full 体裁币种节的三码判定。见 check_judgement_ring 的诚实标注。"""
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
        if ASSUMPTION_LABEL not in s:
            continue
        if not (numbers_in(s) & allowed):
            v.append("ASSUMPTION_UNANCHORED: %s 节的关键假设句里没有可溯源"
                     "数字:「%s」;%s" % (currency, s, DISPOSITION_ANCHOR))
    return v


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
# 「正文」的范围:币种节 ∪ 这三节。**冻结的清单**,不是"报告的其余部分" ——
# 后者会让这条码退化成"摘要的数只要在报告里出现过就行",附录里随手一提就算
# 数。缺漏节在列是实测要求的:reports/daily/2026-08-07.md 的摘要写
# 「五币种 GDELT 事件采集均为 429」,429 在报告里只出现于缺漏节。
SUMMARY_BODY_SECTION_KEYS = ("速览", "复盘", "数据缺漏")


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


def shared_number_pool(snap, brief_text):
    """共享池 —— 逐元素定义见 SHARED_SNAPSHOT_KEYS / SHARED_BRIEF_HEADINGS。

    ALLOWED_SMALL 整体在池内:序数/条数/月份类小整数没有币种归属,把它们
    纳进映射约束会把每一句「第 3 条」「T+3」都打红。
    """
    nums = set(ALLOWED_SMALL)
    nums |= numbers_in(json.dumps({k: snap.get(k) for k in SHARED_SNAPSHOT_KEYS},
                                  ensure_ascii=False))
    secs = sections(brief_text)
    for heading in SHARED_BRIEF_HEADINGS:
        sec = find_section(secs, heading)
        if sec:
            nums |= numbers_in(sec[1])
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
    for c in sorted(covered):
        if not currency_snapshot_slice(snap, c):
            no_slice.append(c)
            continue
        body = find_section(secs, c)[1]
        pool = own[c] | shared
        for other in CURRENCIES:
            if other == c:
                continue
            if any(a in body for a in CURRENCY_ALIASES[other]):
                pool |= own[other]
        for n in sorted((numbers_in(body) & allowed) - pool):
            src = sorted(o for o in CURRENCIES if o != c and n in own[o])
            v.append("NUMBER_WRONG_SECTION: %s 节写了 %s,它只出自 %s 的快照"
                     "切片,而本节没有点名 %s;%s"
                     % (c, n, "/".join(src) or "别处", "/".join(src) or "它",
                        DISPOSITION_WRONG_SECTION))
    if no_slice and notes is not None:
        notes.append("NUMBER_WRONG_SECTION_SKIPPED_NO_SLICE: %s 在快照里没有"
                     "任何自有切片(rates/events/derived/macro 都没有该币种或"
                     "其经济体的条目),这些节的数字归属未校验"
                     % "、".join(no_slice))
    return v


def check_summary_numbers_in_body(secs, notes=None):
    """`SUMMARY_NUMBER_NOT_IN_BODY` —— **质量检查**(一致性级)。

    移植自 econstack 被删版本的 A1 检查项,逐字:
    `| A1 | Do all numbers in the executive summary match the tables? | RED |`
    比的是**同一个数在两个位置的一致性**,不是"某物有没有出现",所以它不是
    **存在性**检查;既有的 `NUMBER_UNTRACEABLE` 才是存在性那一层。

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
    """
    v = []
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


def check_daily(report, snapshot_text, brief_text, strict_brief=False, notes=None,
                prior_text=None):
    """日报结构 + 数字溯源 + 结论句逐字引用检查,返回违规列表。

    prior_text : 上一份日报正文;`None` 表示**没提供**,跨期逐字重复整条
            不检查(声明由 CLI 层打印,见 `main`)。空串是"提供了但内容为空"
            的合法形态,走 check_prior_period 的第三态。

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

    covered = set()
    for c in CURRENCIES:
        if find_section(secs, c):
            covered.add(c)
        else:
            # covered 与 SECTION_MISSING 必须互为补集 —— check_verdicts 的
            # 「让位 ①」依赖这一点。建在同一个循环里,物理上保证两者一起改
            # (check_weekly 的注释这么写,而日报侧此前分两处算)
            v.append("SECTION_MISSING: 缺少币种节 %s" % c)
    s = find_section(secs, "执行摘要")
    if not s:
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
    if not rev or not rev[1].strip():
        v.append("SECTION_MISSING: 缺少复盘节(首次运行也须保留并注明)")

    gap_sec = find_section(secs, "数据缺漏")
    if not gap_sec:
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
    v.extend(check_judgement_ring(secs, derived, covered, allowed, notes=notes))
    # 数字归属两码同样排在 `allowed` 之后:映射检查的候选集是**已可溯源**的
    # 那些数,编造的数由 NUMBER_UNTRACEABLE 单独管,同一个 token 不得吃两条。
    if isinstance(snap, dict):
        v.extend(check_number_section_mapping(secs, snap, brief_text, covered,
                                              allowed, notes=notes))
    elif notes is not None:
        # 快照顶层不是对象:已记 SNAPSHOT_MALFORMED,但归属这一层确实一条
        # 都没查过,不出声就与"全查过且全过"同形
        notes.append("NUMBER_WRONG_SECTION_SKIPPED_NO_SLICE: 快照顶层不是对象,"
                     "所有币种节的数字归属未校验")
    v.extend(check_summary_numbers_in_body(secs, notes=notes))
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
    if prior_text is not None:
        v.extend(check_prior_period(report, prior_text, notes=notes))
    return v


def _read_file(path, label):
    """读取输入文件;失败返回 (None, rc=2 前的 stderr 说明)。"""
    try:
        with open(path, encoding="utf-8") as f:
            return f.read(), None
    except (OSError, UnicodeDecodeError) as e:
        return None, "无法读取%s %s: %s" % (label, path, e)


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
    在**生产命令行的完整形状**(含 `--brief`/`--strict-brief`/`--daily`)
    及其每个开关的取反组合上枚举豁免味 token,要求基线上出现过的那组码
    一个都不许少。冻结注册表形状只是辅助。

    **这条断言不是全称命题**,名字里的 "listed" 就是它的边界:守的是
    `EXEMPTION_TOKENS` 词表 × 句法位置 × 开关取反。旧名字写成
    "no argv can …" 时,三条有界缺口逐条被真绕过打穿(T8b 复验):
    base argv 从不带 `--strict-brief` 而生产调用每次都带(于是
    `if args.strict_brief: 滤掉 VERDICT_*` 这一行只在真实运行时生效);
    判据只看"stdout 里还有 VERDICT_"而两份输入的违规恰好全是同一个码;
    以及守卫跑在进程内、`sys.argv` 对它天然不可见。
    第三条现在由 `test_production_shapes_stay_red_in_a_real_subprocess`
    用真子进程补上。
    """
    ap = argparse.ArgumentParser()
    ap.add_argument("report")
    ap.add_argument("snapshot", nargs="?")
    ap.add_argument("--brief", default=None)
    ap.add_argument("--mode", choices=["daily", "weekly"], default="daily")
    ap.add_argument("--strict-brief", action="store_true",
                    help="daily:同时校验 要点表 ⊆ 快照")
    ap.add_argument("--digest", default=None,
                    help="weekly:周度聚合文件,启用周报数字溯源")
    ap.add_argument("--daily", action="append", default=[],
                    help="weekly:当周日报路径,可重复;并入数字白名单")
    ap.add_argument("--prior", default=None,
                    help="daily:上一份日报路径,启用「本期相对上期的变化」节"
                         "的跨期逐字重复检查")
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
        snapshot_text, err = _read_file(args.snapshot, "快照文件")
        if err:
            print(err, file=sys.stderr)
            return 2
        snap, problems = parse_snapshot(snapshot_text)
        if snap is None or problems:
            for p in problems:
                print("快照损坏: " + p, file=sys.stderr)
            return 2
        brief_text = ""
        if args.brief:
            brief_text, err = _read_file(args.brief, "要点表文件")
            if err:
                print(err, file=sys.stderr)
                return 2
        prior_text = None
        if args.prior:
            prior_text, err = _read_file(args.prior, "上一份日报")
            if err:
                print(err, file=sys.stderr)
                return 2
        else:
            # 「没给上一份日报」是设计内的合法形态(第一份日报、手动重跑),
            # 不是违规、不改退出码 —— 但它若跑出**裸 CHECK PASSED**,就与
            # 「比对过且没有套话」逐字不可分辨。「跳过」与「通过」在输出上
            # 必须可区分,与 VERDICT_SKIPPED_NO_DERIVED /
            # WEEKLY_DIGEST_ABSENT_SKIPPED / BRIEF_REVIEW_BLOCK_SKIPPED 同一原则。
            notes.append("PRIOR_PERIOD_ABSENT_SKIPPED: 未提供 --prior,"
                         "本次未校验「本期相对上期的变化」节的跨期逐字重复")
        violations = check_daily(report, snapshot_text, brief_text,
                                 strict_brief=args.strict_brief, notes=notes,
                                 prior_text=prior_text)
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
                                  digest if args.digest is not None else None)
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


def check_weekly(report, digest_text=None, daily_texts=(), digest=None):
    v = []
    secs = sections(report)
    for key in WEEKLY_SECTIONS:
        if not find_section(secs, key):
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
        for tok in ("命中", "未命中", "无法判定"):
            if tok not in rs[1]:
                v.append("REVIEW_TOKEN_MISSING: 复盘汇总缺少「%s」" % tok)
    if digest_text:
        # 周报此前完全没有数字溯源(只查结构),数字纪律纯靠 prompt 禁令。
        # 白名单 = 聚合文件 ∪ 当周日报 ∪ 小整数:日报本身已过溯源,链条完整。
        allowed = numbers_in(digest_text) | ALLOWED_SMALL
        for text in daily_texts:
            allowed |= numbers_in(text)
        for n in sorted(numbers_in(report) - allowed):
            v.append("NUMBER_UNTRACEABLE: 数字 %s 不见于周度聚合文件或当周日报" % n)
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
