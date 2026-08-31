"""SKILL 文档哨兵。

新增一个结论句字段要同步四处(derive / EMPTY_EVENTS_DERIVED / SKILL /
校验器)。前三处漏一处会被键集断言或单测抓住,唯独 SKILL 是散文 —— 漏改
不会让任何测试变红,而它恰恰是"第二处判定"的藏身处:同一判定在提示词与
脚本各写一遍,两份措辞必然漂移,"哪一份算数"无处可判。

**本文件的注释承担不寻常的分量,不要在重构时顺手删掉。**每条断言的锚点
为什么是现在这个串,几乎都对应一次"断言当时能红、却守不住回退"的实测:
裸短串会被同段另一处喂饱,于是它本该守的那一句被整句删掉时照样全绿。
删掉理由,下一个人就会把锚点改回短串。
"""
import os
import re
import unittest

from scripts import claims, review
from tests.test_review import UNCHANGED_REF_CAUSE_WORDS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DAILY = os.path.join(ROOT, "skills", "fx-daily-report", "SKILL.md")
WEEKLY = os.path.join(ROOT, "skills", "fx-weekly-report", "SKILL.md")


def raw(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def flat(path):
    """去掉所有空白后比对 —— 断言不该被折行位置绑架。"""
    return "".join(raw(path).split())


def plain(path):
    """在 flat 之上再去掉 markdown 强调号(`*`)。

    为什么要单独有这一层:被删的那条旧要求写作「与本环的翻转指标**同源同字**」,
    星号正好落在「翻转指标」与「同源同字」中间,于是 flat 之后子串
    「翻转指标同源同字」**并不存在** —— 拿它当反向锚点会静默失守(实测:
    flat(DAILY) 里该子串 0 次命中,而那一句原封不动地在文件里)。
    强调号是排版,不是语义;比对前一律剥掉。
    """
    return "".join(raw(path).split()).replace("*", "")


def block(text, start_re):
    """摘出一个段落并压平。整文件断言判不了"这句话有没有落在该落的段里":
    「存量快照」在本文件里出现好几处,只查全文会让禁令 9 缺豁免口也照样绿。"""
    m = re.search(start_re, text, re.S)
    return "".join(m.group(0).split()) if m else None


def sentences(flat_text):
    """按句号切句。**这里不能用空行切段**:禁令那句与曾经教着按布尔拼话术的
    那句同处一个 markdown 列表项(- 派生指标:)之内,中间一个空行都没有,
    按空行切会把两者判成同一段,于是"提及落在哪儿"永远为真。"""
    return [s for s in flat_text.split("。") if s]


# 段落正则集中一处。散在各测试里会变成逐字节相同的第二份拷贝 —— 在一个
# 专门消灭"同一份东西有两份拷贝"的 change 里尤其不该留。
STEP2_DERIVED_RE = r"(?m)^    - 派生指标:.*?(?=\n    - )"
BAN9_RE = r"(?m)^9\. \*\*事件结论句.*?(?=\n\n)"
NO_DERIVED_RE = r"(?m)^- `VERDICT_SKIPPED_NO_DERIVED`.*?(?=\n\n|\n- `|\Z)"
LEGACY_RE = r"(?m)^- `VERDICT_SKIPPED_LEGACY`.*?(?=\n\n|\n- `|\Z)"
# 有界(`.*?` 到空行或 EOF),不是 `.*\Z`。日报的违规节眼下恰好是文件最后一节,
# 两种写法当前抓到的字节完全相同;但贪婪到 EOF 意味着**将来在文件尾部追加任何
# 内容都会被吞进这一段**,于是"违规节丢了 VERDICT_NOT_QUOTED"可以被后面新加的
# 无关章节喂饱 —— 正是本轮在修的那个形态,只是把它埋成了将来时。
DAILY_VIOLATION_RE = r"(?m)^违规\(退出码非 0\):.*?(?=\n\n|\Z)"
WEEKLY_VIOLATION_RE = (r"(?m)^\*\*结论句相关的违规码\(退出码非 0\):\*\*"
                       r".*?(?=\n\n|\Z)")
WEEKLY_BAN_ONE_RE = r"(?m)^1\. \*\*三条结论句.*?(?=\n\n|\n\d+\. )"
# NOT_QUOTED_BULLET_RE 已删。它是 T8 那版"bullet 级断言"的取段器,而 T8b 复验
# 用三条绕过证明了 bullet 级子串哨兵的结构上限:M-B(在违规节末尾追加"统一
# 口径")落在 bullet 之外、断言看不见;M-C(拆成"旧口径已废弃"+新口径)靠这条
# 正则非贪婪 + re.search 只取首个匹配直接躲过。处置文案已搬进校验器,
# SKILL 侧不再有 bullet 可摘 —— 详见 ViolationDispositionTest 的类注释。

# ---- 2026-08-14 可读性/论证深度改造(依据 ①②③④⑤⑨)新增的段落正则 ----
# 全部**有界**(`.*?` 到下一个已知锚点),理由同 DAILY_VIOLATION_RE:贪婪到 EOF
# 会让"这一段被删掉"可以由后面追加的任意内容喂饱。
#
# 这批规则全是**散文**,没有任何运行时判据 —— 校验器不认识"关键假设""翻转
# 指标""写作顺序"。本仓库的实测教训是:没有哨兵的散文规则会被下一次重构
# 顺手删掉且无人知晓(ViolationDispositionTest 的类注释记了三次这样的存活)。
# 所以每条规则都钉在**它自己那一段**里,锚点取该段独有的整串。
D_WRITE_ORDER_RE = r"(?m)^### 写作顺序.*?(?=\n\*\*读者要的是)"
D_RING_BUDGET_RE = r"(?m)^\*\*任何一环与上一环无关.*?(?=\n#### )"
D_TRANSMISSION_RE = r"(?m)^#### 传导环.*?(?=\n#### )"
D_ECB_RE = r"(?m)^#### 引 ECB 政策传导.*?(?=\n#### )"
D_JUDGEMENT_RE = r"(?m)^#### 判断环.*?(?=\n#### )"
D_CHANGE_SPEC_RE = r"(?m)^#### 「本期相对上期的变化」怎么写.*?(?=\n\*\*禁令)"
D_CHANGE_TMPL_RE = r"(?m)^    ## 本期相对上期的变化.*?(?=\n\n)"
D_BAN11_RE = r"(?m)^11\. \*\*零效应判断.*?(?=\n\n)"
D_BAN12_RE = r"(?m)^12\. \*\*无关素材.*?(?=\n\n)"
# ---- 2026-08-15 失效条件 / 翻转指标解耦(A 案)新增的段落正则 ----
# 两份 SKILL 的**表模板段**各一条:第 4 列的语义定义必须写在表旁边,
# 写作时读者眼睛落在哪里、定义就得在哪里。
D_OVERVIEW_TMPL_RE = r"(?m)^    \| 币种 \| 条件方向.*?(?=\n\n)"
W_LANDING_TMPL_RE = r"(?m)^    \| 币种 \| 主线归属.*?(?=\n\n)"
# 两条定义并列的那一段(周报侧)。日报侧并列段落在 `#### 判断环` 小节内,
# 由 D_JUDGEMENT_RE 覆盖,不另开正则。
W_INVALIDATION_RE = r"(?m)^\*\*失效条件与翻转指标.*?(?=\n\n)"

W_WRITE_ORDER_RE = r"(?m)^### 写作顺序.*?(?=\n只依据第 1 步素材)"
W_THEME_TMPL_RE = r"(?m)^    ### 主线一:.*?(?=\n\n    \(### 主线二)"
W_HARD_FORM_RE = r"(?m)^\*\*本周主线的硬形态:\*\*.*?(?=\n\n)"
W_ECB_RE = r"(?m)^\*\*引 ECB 政策传导做归因时.*?(?=\n\n)"
W_CHANGE_SPEC_RE = r"(?m)^## 「上周相对上上周的变化」怎么写.*?(?=\n## )"
W_CHANGE_TMPL_RE = r"(?m)^    ## 上周相对上上周的变化.*?(?=\n\n)"
W_BAN7_RE = r"(?m)^7\. \*\*零效应判断.*?(?=\n8\. )"
W_BAN8_RE = r"(?m)^8\. \*\*无关素材.*?(?=\n\n)"

# 「快照里没有结论句」这一形态的标签串。它不是文案 —— 第 2 步写下它,禁令 9
# 把它当作豁免的**触发条件**,第 5 步两个降级码各引用一次。四站必须逐字同串:
# 任一站漏改,那一站的读者就按另一套口径行事,而这正是 I2 那条链的起点。
NO_VERDICT_LABEL = "结论句不可得(快照未落结论句)"

LABEL_SITES = (
    ("第 2 步「派生指标」项(定义处)", STEP2_DERIVED_RE),
    ("禁令 9 豁免口(拿它当触发条件)", BAN9_RE),
    ("第 5 步 VERDICT_SKIPPED_NO_DERIVED 分支二", NO_DERIVED_RE),
    ("第 5 步 VERDICT_SKIPPED_LEGACY", LEGACY_RE),
)

# 禁令句的句式:`**禁止**据 <字段们> 自行拼装 …`。只取"据"与"自行拼装"
# **之间**那一段,所以写在冒号之后的权威字段(`events_verdict`)天然被排除 ——
# 早先担心的"放宽锚点会把 events_verdict 抽成被禁布尔"在这个锚点下不成立。
BAN_RE = re.compile(r"禁止\*\*据(.*?)自行拼装")


def banned_booleans(flat_text):
    """从禁令句本身抽出被点名的字段 —— **哨兵的主语只能有这一个来源**。

    在测试里另抄一份名单,就是本 change 从头到尾在消灭的形态:同一份判定
    有两份拷贝,两份必然漂移,而"哪份算数"无处可判。这里漂移的方向还是
    静默失守:derive 新增一个布尔、SKILL 禁令也写上了它,而手抄名单没
    跟上 → 哨兵根本不守它,全绿照过。

    **抽全部禁令句,不是只抽一句。**早先只认"自行拼装任何话术"那一句,于是
    `source_capped` 那条禁令(句式相同、话术描述不同)抽不出来,只好在测试里
    另开一张 EXTRA_BANNED 表 —— 那张表走的是"每一处提及都得在禁令里"的循环,
    禁令整句删掉后该字段全文 0 次提及,**循环空转通过**(实测存活)。
    两条禁令句式本就一致,一条正则抽全,地板一比就红。
    """
    out = []
    for s in sentences(flat_text):
        for seg in BAN_RE.findall(s):
            out += re.findall(r"`([^`]+)`", seg)
    return out


def mentions(flat_text, field):
    """字段名现在来自文档,子串包含关系更容易咬人:`sample_capped` 是
    `main_sample_capped` 的后缀,裸用 `in` 会把后者的每一处提及都算成前者的。
    两者判据相同所以不出错判,但"某个字段到底被守住没有"就说不清了 ——
    F8 那轮的失败消息正是这样张冠李戴的。

    改按**标识符边界**判定:前后一位都不能是 [A-Za-z0-9_]。反引号、空白、
    中文标点都不是标识符字符,故 `sample_capped` 照常命中,而
    main_sample_capped 里的那一段因前一位是下划线被排除。比"最长优先"稳:
    不依赖字段在表里的先后顺序。
    """
    pat = re.compile(r"(?<![A-Za-z0-9_])%s(?![A-Za-z0-9_])" % re.escape(field))
    return [s for s in sentences(flat_text) if pat.search(s)]


class SkillDocTestCase(unittest.TestCase):
    def seg_or_fail(self, path, pattern, name):
        """摘不到就给预备好的消息,而不是让后续断言抛 TypeError。

        注意:摘得到**不等于**内容还在。小节标题就能让 block() 命中,所以
        每个调用点都必须再断言段内的具体锚点 —— 只写 assertIsNotNone 时,
        删掉小节里某一条 bullet 照样全绿(实测)。
        """
        seg = block(raw(path), pattern)
        self.assertIsNotNone(seg, "没摘到「%s」,正则或文档结构变了" % name)
        return seg


class DailySkillTest(SkillDocTestCase):
    def test_points_at_the_verdict_field(self):
        """锚点取"照抄哪个字段"的**整条指令**,而不是 `events_verdict` 五个字。

        普查:`events_verdict` 在全文出现 4 次(还有两处"判定以它为准"的指路),
        裸断言字段名会被那几处喂饱 —— 把第 2 步的照抄指令整条换掉、只剩别处的
        指路,断言照样绿。整条指令在段内 count=1。
        """
        seg = self.seg_or_fail(DAILY, STEP2_DERIVED_RE, "第 2 步「派生指标」项")
        self.assertIn("**逐字整句照抄**`derived.events.<币种>.events_verdict`", seg,
                      "第 2 步不再要求逐字整句照抄那个字段")

    def test_boolean_assembly_wording_is_gone(self):
        """让 LLM 按布尔拼话术的原句必须删干净 —— 留着就是第二处判定。"""
        t = flat(DAILY)
        for phrase in ("已达当日采集上限,实际篇数只多不少",
                       "两日均达采集上限,变化0是上限造成的",
                       "源返回的原始样本触顶,滤除后的条数是下界",
                       "主通道当日返回条数触顶,其滤除后的条数是下界",
                       "另有N条源返回的元素结构不可识别被跳过",
                       # 以下三条是 T7 漏删的同型残留。前两条指向已被删掉的
                       # 模板项(事件数),第三条与 events_verdict 的 caveat
                       # 同义;第二条更与"禁止据布尔拼话术"那一段字面冲突。
                       "事件数为null表示该币种事件采集失败",
                       "count_capped为true时禁止把count_delta为0写成",
                       "该币种条目取自被截断的样本,任何条数都是下界"):
            self.assertNotIn(phrase, t, phrase)

    # **这张表不驱动任何检查**,只当地板:断言"禁令句里抽出来的集合 ⊇ 它"。
    # 循环的主语一律从禁令句里抽(见 banned_booleans),否则它就成了第二份
    # 手抄拷贝。地板防的是反向绕过 —— 把字段从禁令句里删掉,抽出来的集合
    # 随之缩小,循环少守一个甚至空转,测试反而变绿。
    BANNED_FLOOR = ("count_capped", "sample_capped", "main_sample_capped",
                    "channel_changed_from", "dropped_malformed",
                    "source_capped")

    def test_every_mention_of_a_banned_boolean_sits_inside_a_ban(self):
        """一边禁止据这些布尔拼话术、一边教着按它们拼话术,两句字面冲突,
        而"哪一句算数"无处可判。

        判据是**每一处提及所在的那一句都得是禁令**,不是"全文只准出现 N 次"。
        计数式断言脆:将来正当地再提一次(比如新增一条禁令)它就红,而最省事
        的"修法"是把断言改松 —— 靠放宽断言消除红是本仓库明令禁止的。句子级
        判定则相反:新增正当禁令自然通过,把判定话术写回模板段必红。

        主语从禁令句抽,所以 SKILL 禁令新点名一个布尔时,哨兵**不改测试就
        自动守它**;地板断言则挡住反向绕过。两条合起来才让禁令句成为唯一
        事实源 —— 缺了地板,"删掉整条禁令"这个最彻底的回退会让循环空转通过。

        最后一条断言防的是相反的过头修法 —— 直接删掉冲突句会留下真实缺口:
        `count_delta` 仍可引用,而 `events_verdict` 的 caveat 并没有说"delta 为 0
        是上限造成的",LLM 于是可以合法引用 delta=0 并自行解读成"持平"。
        替代规则必须还在,只是不再依赖布尔字段。"""
        t = flat(DAILY)
        fields = banned_booleans(t)
        self.assertTrue(fields, "一条禁令句都没抽到(句式变了?)")
        missing = sorted(set(self.BANNED_FLOOR) - set(fields))
        self.assertFalse(
            missing, "禁令句里少了这些布尔 —— 靠削禁令句放绿?%s" % missing)
        # 句式对账:`BAN_RE` 认的是 `**禁止**据 … 自行拼装` 这一个句式,换个句式
        # 写第三条禁令、点名一个新布尔,字段抽不出来、地板也不缺 —— 静默失守
        # (实测:抽出仍是原来那些,缺失为 [],全绿)。这里用**下面循环本来就在
        # 用的那个判据**("禁止"且"拼装")独立数一遍禁令句,两种识别方式对不上
        # 就响亮地红,不引入任何需要人工维护的第七份名单。
        #
        # **这不是根治**:既不含"禁止"也不含"拼装"的禁令仍然漏得掉。真正的根治
        # 是让 derive 导出字段清单供测试读(verify 待办第 10 条),那要动
        # scripts/,不在本 change 范围 —— 别因为有了这四行就把那条待办划掉。
        ban_sentences = [s for s in sentences(t) if "禁止" in s and "拼装" in s]
        self.assertEqual(
            len([s for s in ban_sentences if BAN_RE.search(s)]),
            len(ban_sentences),
            "有禁令句没用 `**禁止**据 … 自行拼装` 句式,里面的字段抽不出来")
        for field in sorted(set(fields)):
            for s in mentions(t, field):
                self.assertTrue(
                    "禁止" in s and "拼装" in s,
                    "%s 的这一处提及不是禁止拼装、而是在教着按布尔拼话术:%s"
                    % (field, s))
        # 段级:该串全文 count=1 且就落在第 2 步「派生指标」项里,所以钉在那一段
        # 上零成本 —— 全文级会让"把这条规则挪到别处"照样绿。
        self.assertIn(
            "与前值持平",
            self.seg_or_fail(DAILY, STEP2_DERIVED_RE, "第 2 步「派生指标」项"),
            "堵 delta=0 → 持平 的规则不能被一删了之,也不能挪出该段")

    def test_the_no_verdict_label_is_neutral(self):
        """第 2 步那个标签串是禁令 9 豁免口的**触发条件**,四站必须逐字一致,
        而且它不能叫"(存量快照)"。

        叫"(存量快照)"时形成这条链:**当日 derive 崩了**的快照也走第 2 步这一行
        → 被贴上事实错误的"存量"标签 → 禁令 9 的豁免正按这个字面串生效、该币种
        免除逐字引用 → 校验器此档只出 VERDICT_SKIPPED_NO_DERIVED 声明(rc 0),
        没有第二道拦。第 5 步已经把"不是快照旧不旧"写进判别标准了,第 2 步和
        禁令 9 却还按"NO_DERIVED = 存量快照"写 —— 同一形态三处口径打架。
        """
        t = flat(DAILY)
        self.assertNotIn(
            "结论句不可得(存量快照)", t,
            "标签把「快照里没有这一句」当成了「快照旧」——当日 derive 崩了的"
            "快照会被错误豁免")
        # 普查 count=4(四站各一)。**保留且无害**:它只是"标签整个消失"时给一条
        # 干脆的失败消息,真正的守卫是下面按站点那四条(各 count=1)。任一站被
        # 改写时,这一条确实会被另外三站喂饱 —— 但那一站自己的断言会红,守的
        # 东西没有落空。
        self.assertIn(NO_VERDICT_LABEL, t, "中性标签不见了")
        # **按站点断言,不数次数**:计数式("≥2 次"或"==4 次")会被别处的
        # 引用满足 —— 漏改其中一站,另外三站的字样照样把断言喂饱,那一站就
        # 悄悄按旧口径行事。这与"断言被别处文字满足"是同一个缝。定成 ==4 又会
        # 在正当地多写一处引用时误红,而最省事的"修法"就是放宽 —— 那条路已否掉。
        for name, pattern in LABEL_SITES:
            seg = self.seg_or_fail(DAILY, pattern, name)
            self.assertIn(NO_VERDICT_LABEL, seg,
                          "「%s」这一站没用同一个标签串 —— 该站会按旧口径行事"
                          % name)
        # 定义处还得留着那句指路,否则读者拿到标签却不知道属哪一种情形。删掉它
        # 不会重新打开那条链(标签仍中性、禁令 9 仍限定那一支、第 5 步分支一
        # 仍要求重跑并重做第 2/4 步,三条各有自己的变异守着),丢的是冗余提示,
        # 所以这条按 Minor 补,不与上面四站的断言合并。
        seg = self.seg_or_fail(DAILY, STEP2_DERIVED_RE, "第 2 步「派生指标」项")
        self.assertIn("由第5步的判别标准决定", seg,
                      "定义处丢了「属哪一种情形由第 5 步判别」那句指路")

    def test_ban_nine_carves_out_the_legacy_snapshot_case(self):
        """禁令 9 规定结论句**不经 LLM 的手**,而第 2 步规定该键不存在或为 null
        时该行写 "结论句不可得(快照未落结论句)" —— 此时根本没有句子可引。LLM
        面对"必须交付一句不存在的话"最可能的动作就是自己编一句,而校验器此时正处于
        跳过档,一个字都抓不到,没有任何测试能碰到它。

        不是边角情况:data/ 下 6 份快照没有一份带 events_verdict —— 其中
        2026-08-07..10 这 4 份连 derived 节都没有(走 VERDICT_SKIPPED_NO_DERIVED),
        2026-08-11/12 这 2 份 schema_version=1 低于闸门 2(走
        VERDICT_SKIPPED_LEGACY)。**两个码都要在豁免口里点名**:只写一个,
        另一个码的持有者会以为豁免不适用于自己。

        主规则也要守。**主规则本身在 2026-08-14 换了形态,这里同步换锚点:**
        旧规则是"该句必须在**该币种节**内**逐字**出现",新规则是"该句由
        `scripts/appendix.py` 写进附录 A 整块、报告原样贴、**正文禁止出现该句**"。
        换的理由不是放宽:旧规则把管道类结论句(有几条、顶没顶到上限、走的哪条
        通道)永久钉死在正文里,与"正文零管道语汇"直接冲突,照 SKILL 写必违反
        模板、照模板写必违反 SKILL;而它对应的脚本判据一直只是 `s not in report`
        (整份文件子串),"在该币种节内"这半句从来没有可执行的判据。新规则把
        执行主体从 LLM 换成脚本,LLM 从"逐字转抄"降到**零接触** —— 不变量是
        净加强,弱的是 LLM 的自由度,不是闸门。
        因此三条正向锚点改成新规则**各自独有**的整串(产出方、零接触、位置),
        并补一条反向锚点挡旧规则长回来 —— 旧规则一旦回来,冲突随之回来。

        豁免口对 `VERDICT_SKIPPED_NO_DERIVED` 必须**限定在窗口已移过那一支**:
        当日 derive 崩了的快照也发这个码,若无条件豁免,第 2 步给它贴上标签 →
        禁令 9 按字面免除该币种的逐字引用 → 校验器此档只出声明(rc 0),
        没有第二道拦。

        校验器口径("精确子串包含""改动一个字符")必须留在**本段**:早先它走
        全文级断言,把这两句从禁令 9 挪到第 5 步照样全绿(实测存活)。禁令 9 的
        核心约束另有段级断言守着,挪走的是加强说明 —— 但"说得比实际宽"正是
        本仓库反复栽的形态,而修法零成本:seg 本来就摘出来了。"""
        seg = self.seg_or_fail(DAILY, BAN9_RE, "禁令 9 段落")
        # ① 产出方:这半句被删掉时,读者会退回"自己把那句抄进报告",而正文
        # 位置规则(禁令 7)紧接着就会把它判违规 —— 两条规则互相打架的老形态。
        # 锚点取脚本路径而不是"附录 A"三个字:后者在模板段与禁令 10 里都有,
        # 段级断言虽已隔开,但脚本路径在段内 count=1,更不易被同段别处喂饱。
        self.assertIn("`scripts/appendix.py`", seg,
                      "禁令 9 不再点名结论句的产出方 —— 它会退回 LLM 手抄")
        # ② 零接触:主规则的整串。只断言"原样贴"会被第 3 步的同款措辞喂饱,
        # 所以取"不转抄、不改写"这一串(段内 count=1),它同时挡住"允许改一个
        # 字""允许摘出数字另行造句"两种削法。
        self.assertIn("不转抄、不改写", seg,
                      "主规则被改写(LLM 又拿回了转抄/改写结论句的权限)")
        # ③ 位置:正文禁止出现该句。这一串是本次可读性改造的核心 —— 缺了它,
        # 附录 A 照贴不误,而正文照样可以复述一遍管道结论句。
        self.assertIn("正文禁止出现该句", seg,
                      "禁令 9 丢了位置约束 —— 管道结论句会回到正文")
        # ④ 反向:旧规则(要求该句逐字出现在该币种节内)不得长回来。它与禁令 7
        # 的"正文零管道语汇"字面冲突,而"哪一句算数"无处可判 —— 正是本仓库反复
        # 栽的形态。写成子串"在该币种节内"是为了同时挡住"必须/应当/尽量"各种
        # 情态词的变体。
        self.assertNotIn("在该币种节内", seg,
                         "旧规则长回来了:它要求管道结论句进正文,与禁令 7 冲突")
        self.assertIn("精确子串包含", seg, "禁令 9 丢了校验器口径")
        self.assertIn("改动一个字符", seg, "禁令 9 丢了严格度说明")
        # 豁免口
        self.assertIn("本条不适用", seg, "禁令 9 缺豁免口")
        self.assertIn("禁止自行补造", seg, "禁令 9 没堵住「自己编一句」")
        self.assertIn("窗口已移过", seg,
                      "豁免口没把 NO_DERIVED 限定在窗口已移过那一支")
        for code in ("VERDICT_SKIPPED_NO_DERIVED", "VERDICT_SKIPPED_LEGACY"):
            self.assertIn(code, seg, "豁免口漏点名 %s" % code)


class SkippedCodeDispositionTest(SkillDocTestCase):
    """两个**跳过档**码的处置必须是仓库里跑得动的动作。写一条没有入口的指令,
    运维照做时只会退回"随便跑点什么",比不写更坏。

    不叫 Legacy*:本仓库语境里 legacy 特指 schema 低于闸门那一支,与
    NO_DERIVED(整个 derived 节缺失)被明确区分 —— 两者的处置分支也不同。
    """

    def test_no_derived_disposition_splits_the_two_cases(self):
        """`VERDICT_SKIPPED_NO_DERIVED` 原先只有"重跑第 1 步采集"这一支处置,
        而它只对采集窗口还覆盖 DATE 的快照成立。对 data/2026-08-07..10 那 4 份
        (窗口已移过),重跑拿到的不是当日那批条目 —— 与 VERDICT_SKIPPED_LEGACY
        被否掉"重新派生"的理由一模一样。

        同一份文档一处说"不必补救"、一处说"重跑",「哪一句算数」无处可判 ——
        正是本 change 要消灭的形态。两支都必须在,且判别标准要可执行
        (采集窗口是否还覆盖该日)。

        锚点必须取两支**各自独有**的整串。原先断言的是"重跑"与"存量快照",
        两个词在段内都由**另一支**供给,于是整支删掉照样绿 —— 实测把分支一
        整段删除,全量 rc=0、变异存活,该修复被完整回退而无人知晓。
        断言当时能红 ≠ 断言守得住回退。"""
        seg = self.seg_or_fail(DAILY, NO_DERIVED_RE,
                               "VERDICT_SKIPPED_NO_DERIVED 的处置段")
        self.assertIn("采集窗口", seg, "缺可执行的判别标准,读者判不出自己属哪支")
        self.assertIn("窗口仍覆盖", seg, "分支一(重跑采集)整支没了")
        # seg 已压平,断言串不能带空格
        self.assertIn("重跑第1步采集", seg, "分支一丢了可执行动作")
        self.assertIn("重做第2步与第4步", seg,
                      "分支一只说重跑采集,没说要回头重做要点表与报告")
        self.assertIn("窗口已移过", seg, "分支二(无补救)整支没了")
        self.assertIn("禁止自行补造", seg, "分支二没堵住「自己编一句」")

    def test_legacy_disposition_names_no_nonexistent_derive_entry(self):
        seg = self.seg_or_fail(DAILY, LEGACY_RE,
                               "VERDICT_SKIPPED_LEGACY 的处置段")
        self.assertNotIn("重新派生该日快照", seg,
                         "仓库没有 derive-only 入口,这条指令跑不了")
        self.assertIn("derive-only", seg, "须写明当前没有 derive-only 入口")
        self.assertIn("重新采集", seg,
                      "须写明重跑 scripts.collect 是重新采集、不是重新派生")


class ViolationDispositionTest(SkillDocTestCase):
    """违规码的处置**不再写在 SKILL 里** —— 这里只断言"两份文档都指向校验器输出"。

    ## 为什么从内容断言退成指向断言(别把它加回去)

    T8 的修法是"锚点取该处置独有的整句 + bullet 级 assertNotIn("没用")"。
    T8b 的四个独立复验者各自发明了绕过,**三条全部存活**(全量 rc=0 /
    Ran 674 / OK):

    - **M-A**:锚点整句一字不动,**句尾追加**「但这条其实也是脚本缺陷,照抄
      只是走个形式,改了也白搭;真正的处置是重跑第 1 步采集」。正面锚点仍在,
      `assertNotIn("没用")` 也躲开了(它写的是"白搭")。
    - **M-B**:bullet 一字不动,在**违规节末尾**追加「(统一口径:本节**所有**
      违规码——含上面的 `VERDICT_NOT_QUOTED`——都按脚本缺陷处理,改报告没用)」。
      实测段长 257→337、段内"没用"1→2,而 **bullet 长度仍 73、bullet 内
      "没用"仍 0** —— bullet 级断言**结构上看不见它**。
    - **M-C**:把 bullet 拆成两条,第一条标注「(旧口径,已废弃)…本条自
      2026-08 起不再执行」并**原样保留锚点整句**,第二条写反向口径。根因是
      当时那条 bullet 取段正则非贪婪 + `re.search` 只取**首个**匹配。

    另有一条决定性实测:`grep -rn "改报告|改周报" scripts/` **零命中** ——
    这段处置文本**没有任何运行时角色**,纯粹是 SKILL 里的散文。

    结论:追加矛盾文字的措辞空间无界,这是子串哨兵的结构上限,加锚点堵不住。
    改法是**消灭第二份拷贝**:处置由 `scripts/check_report.py` 的
    `DISPOSITION_QUOTE` / `DISPOSITION_SCRIPT_BUG` 打进每一条违规行,SKILL 只
    留一句指向。真正的守卫因此搬到了
    `tests/test_check_report.py::CheckerPrintsItsOwnDispositionTest` ——
    那里断言的是**脚本 stdout**,措辞空间有界、可精确断言、且没有第二份可反转。

    本类剩下的这两条是**弱断言**,只保证"指向还在、码名还在"。

    ## 已知残留(实测,别拿"再加一个锚点"去补)

    在指向那句后面**追加一段反话**(「校验器那一行只是模板文案,照它执行只是
    走个形式;结论句相关的违规码一律按脚本缺陷处理」)—— 本轮实测**存活**:
    全量 `Ran 680 / OK / rc=0`。与 M-A 同型,原因同样是散文的措辞空间无界。

    但**危害已经降级**:处置内容本身在 `check_report.py` 里,这段追加改不动
    校验器打印的那一行(那一行由 `CheckerPrintsItsOwnDispositionTest` 逐字
    钉死,连"句尾追加"都堵死了 —— 实测在 `DISPOSITION_QUOTE` 末尾追加一句
    否定,3 条断言变红)。它能做的只是劝运维别读那一行。真正的修法是继续
    减少 SKILL 里可反转的散文,不是再往这里加锚点。
    """

    POINTER = "处置以校验器打印的那一行为准"

    def test_daily_violation_section_points_at_the_checker_output(self):
        seg = self.seg_or_fail(DAILY, DAILY_VIOLATION_RE, "日报「违规」节")
        self.assertIn("VERDICT_NOT_QUOTED", seg, "违规节不再点名可操作的那个码")
        self.assertIn(self.POINTER, seg,
                      "日报违规节没有指向校验器输出 —— 处置会退回散文第二份拷贝")
        # 反向:一旦这里又开始复述处置内容,第二份拷贝就回来了。
        # 「改报告」是那份被删掉的处置表里唯一的可操作动词,拿它当探针。
        self.assertNotIn("改报告", seg,
                         "违规节又开始复述处置内容了 —— 唯一事实源在校验器里")

    def test_weekly_violation_section_points_at_the_checker_output(self):
        seg = self.seg_or_fail(WEEKLY, WEEKLY_VIOLATION_RE, "周报「违规码」节")
        self.assertIn("VERDICT_NOT_QUOTED", seg, "违规节不再点名可操作的那个码")
        self.assertIn(self.POINTER, seg,
                      "周报违规节没有指向校验器输出 —— 处置会退回散文第二份拷贝")
        self.assertNotIn("改周报", seg,
                         "违规节又开始复述处置内容了 —— 唯一事实源在校验器里")


class WeeklySkillTest(SkillDocTestCase):
    """周报侧必须与日报侧同级:段落级,不是全文级。

    三个字段名在模板节与纪律第 4 条另有出现,「整句逐字」「精确子串包含」也
    在别处出现,所以全文级 assertIn 证明不了它们落在同一条规则里。实测:
    把纪律第 1 条整条改成「`articles_verdict` 只准照抄……`fixings_verdict` 与
    `official_verdict` 可自行改写」—— 与 delta spec 的「三类结论句全覆盖」直接
    相反 —— 全量仍然全绿;单独摘掉 `official_verdict`、单独摘掉
    `fixings_verdict` 也各自存活。
    """

    def ban_one(self):
        return self.seg_or_fail(WEEKLY, WEEKLY_BAN_ONE_RE,
                                "「计数与结论纪律」第 1 条")

    def test_all_three_verdicts_are_quote_only_in_one_rule(self):
        seg = self.ban_one()
        self.assertIn("不准改写", seg, "第 1 条的「只准照抄,不准改写」被换掉了")
        for field in ("fixings_verdict", "articles_verdict", "official_verdict"):
            self.assertIn(field, seg, "%s 不在第 1 条的照抄范围内" % field)
        # 正面锁住规则本身,负面这条挡的是更隐蔽的变体:保留标题、另加一句
        # 「某某可自行改写」把个别字段摘出去。delta spec 要求三类全覆盖,
        # 「可自行改写」在这一条里没有任何合法用法。
        self.assertNotIn("可自行改写", seg, "有字段被摘出照抄范围")

    def test_states_the_exact_substring_rule(self):
        seg = self.ban_one()
        for rule in ("整句逐字", "精确子串包含", "改动一个字符"):
            self.assertIn(rule, seg, "%s 不在第 1 条内" % rule)

    def test_the_three_verdicts_come_from_the_script_and_stay_out_of_the_body(self):
        """与日报禁令 9 同规格的两条,周报侧此前**一条都没有**。

        2026-08-14 起三类结论句由 `scripts/appendix.py` 写进附录 A 整块,
        周报原样贴;第 1 条同步改成"不经你的手 + 正文禁止出现该句"。
        没有这两条断言,把第 1 条改回"逐字抄进各币种节"照样全绿 —— 而那个
        写法正是周报正文里 57 处管道语汇的来源(实测:生产版 2026-W33 全文
        命中 57 次,按新模板重写的同周报告正文命中 0 次)。

        两条锚点各自独有:产出方(脚本路径,段内 count=1)与位置(正文禁令)。
        既有的"不准改写 / 三个字段名 / 整句逐字"三条继续守"照抄"这一面,
        本条守的是"谁来抄"与"抄到哪儿"—— 三面齐了,第 1 条才不能被单向削弱。
        """
        seg = self.ban_one()
        self.assertIn("`scripts/appendix.py`", seg,
                      "第 1 条不再点名结论句的产出方 —— 它会退回 LLM 手抄")
        self.assertIn("正文禁止出现该句", seg,
                      "第 1 条丢了位置约束 —— 管道结论句会回到周报正文")

    def test_no_nonexistent_derive_entry_in_disposition(self):
        """日报侧那条处置("重新派生该日快照")曾是不可执行的指令。周报侧只做
        交叉引用,不该出现同款文案。"""
        self.assertNotIn("重新派生该日快照", flat(WEEKLY),
                         "周报侧若有同一处置文案须一并同步")


class WritingOrderIsDecoupledTest(SkillDocTestCase):
    """依据 ①:**生成顺序**必须与**呈现顺序**解耦,且写作顺序清单要在第 4 步
    (周报第 2 步)开头。

    守的是什么:模板从上往下是 执行摘要 → 速览 → 币种节,而那正是"先答后编
    理由"的排布。实测里这不是风格问题 —— 同一模型自由文本 86.51、受约束
    结构化格式 23.44,而解析错误率只有 0.148%(即差距不是解析造成的);
    机制是 100% 的响应把 answer 键排在 reason 键之前,于是零样本思维链退化
    成零样本直答。

    锚点为什么是这几个:
    - "故意不同" —— 解耦这件事的**声明**。删掉它,清单会被读成"模板的另一种
      写法",顺序冲突时读者按模板走,规则等于不存在。
    - 禁令整句 —— 清单本身是描述性的,只有这一句是**禁止性**的;没有它,
      "先写摘要再回填"不违反任何字面。
    - 顺序断言(index 比较)—— 只断言"这几个词都在"会被任意重排喂饱,而重排
      恰恰就是这条规则唯一要防的事。所以比的是位置,不是存在性。
    - "0.148%" —— 依据里最容易被当成废话删掉的那半句(它排除了"格式解析
      出错"这个替代解释)。留着它,下一个人才知道这条规则不能靠"改改格式"
      绕过。
    """

    def test_daily_writing_order_is_stated_and_ordered(self):
        seg = self.seg_or_fail(DAILY, D_WRITE_ORDER_RE, "日报第 4 步写作顺序")
        self.assertIn("故意不同", seg,
                      "写作顺序不再声明它与呈现顺序解耦 —— 会被读成模板的复述")
        self.assertIn("禁止先写执行摘要或速览表、再回填币种节", seg,
                      "写作顺序丢了禁止性条款,只剩描述性清单")
        # 生成顺序:证据三环 → 判断环 → 速览表 → 执行摘要。逐对比较相邻两档的
        # 出现位置,任何一次重排都会红。
        for earlier, later in (("证据三环", "判断环"),
                               ("判断环", "速览表"),
                               ("速览表", "执行摘要")):
            self.assertLess(
                seg.index(earlier), seg.index(later),
                "写作顺序被重排:「%s」不再排在「%s」之前" % (earlier, later))
        self.assertIn("0.148%", seg,
                      "删掉了「差距不是解析错误造成的」那半句依据 —— 这条规则"
                      "会被误当成格式问题绕过")

    def test_weekly_writing_order_is_stated_and_ordered(self):
        seg = self.seg_or_fail(WEEKLY, W_WRITE_ORDER_RE, "周报第 2 步写作顺序")
        self.assertIn("故意不同", seg, "周报写作顺序不再声明解耦")
        self.assertIn("禁止先写落点表或覆盖声明、再回填主线", seg,
                      "周报写作顺序丢了禁止性条款")
        for earlier, later in (("证据三段", "判断段"),
                               ("判断段", "各币种一周落点表"),
                               ("各币种一周落点表", "覆盖声明")):
            self.assertLess(
                seg.index(earlier), seg.index(later),
                "周报写作顺序被重排:「%s」不再排在「%s」之前" % (earlier, later))
        self.assertIn("0.148%", seg, "周报侧同样删掉了那半句依据")


class PeriodOverPeriodChangeTest(SkillDocTestCase):
    """依据 ②(情报体系评审标准第 7 条):周期性产品**必须**说明本期判断相对
    上期有何变化,**且不得使用模板套话**。

    守的是什么:本仓库实测的原缺陷 —— 三个币种的实际利率四天一字未变,
    却被原样写了四遍。只加一个"写变化"的节治不了它,因为"无实质变化"是
    最省事的出口;真正吃劲的是**必须写明为什么没变**加上**套话禁令**,
    所以这两条各有自己的断言,不合并。

    模板与细则**分两处断言**:模板给出节的位置与五行形态,细则给出四选一
    与禁令。只断言其中一处时,另一处可以被整段删掉而全绿(与 LABEL_SITES
    分站断言同一理由)。
    """

    def test_daily_section_is_in_the_template(self):
        seg = self.seg_or_fail(DAILY, D_CHANGE_TMPL_RE, "日报模板「本期相对上期」节")
        self.assertIn("五币种五行", seg, "模板不再要求逐币种各占一行")
        # 首次运行的出口必须写在模板里:没有它,第一份日报无从落笔,而最可能
        # 的动作是把整节省掉 —— 那样这条规则在第一份报告上就已经名存实亡。
        self.assertIn("首次运行,无上期可比", seg, "模板缺首次运行的出口")

    def test_daily_change_rules_forbid_boilerplate_and_blanks(self):
        seg = self.seg_or_fail(DAILY, D_CHANGE_SPEC_RE, "日报「本期相对上期」细则")
        for opt in ("方向变了", "触发位变了", "依据变了", "无实质变化"):
            self.assertIn(opt, seg, "四选一少了「%s」" % opt)
        # 这一条是整节的承重墙:允许"无实质变化"但必须给理由,否则该节退化成
        # 一列"无变化"。
        self.assertIn("必须写明为什么没变", seg,
                      "「无实质变化」不再需要给理由 —— 该节会退化成一列无变化")
        self.assertIn("不得留空,不得写套话", seg, "套话禁令没了")
        # 套话得有**具名样例**:只写"不得写套话"是无法执行的判据,而这几个词
        # 正是实测里反复出现的那几句。
        self.assertIn("维持原判", seg, "套话禁令丢了具名样例,变成无法执行的judgement")
        self.assertIn("禁止与上一份日报的同节逐字重复", seg,
                      "跨期逐字重复禁令没了 —— 这是评审标准点名的那一条")
        # 数字白名单那条是**可执行性**保障:上一份日报不在白名单里,照直引用
        # 上期数字会被 NUMBER_UNTRACEABLE 当场拦下,规则与校验器冲突。
        self.assertIn("上一份日报不在白名单里", seg,
                      "丢了数字硬约束 —— 照写会当场炸 NUMBER_UNTRACEABLE")

    def test_weekly_section_is_in_the_template(self):
        seg = self.seg_or_fail(WEEKLY, W_CHANGE_TMPL_RE, "周报模板「上周相对上上周」节")
        self.assertIn("每条主线一行", seg, "模板不再要求逐主线各占一行")
        self.assertIn("首次运行,无上期可比", seg, "模板缺首次运行的出口")

    def test_weekly_change_rules_forbid_boilerplate_and_blanks(self):
        seg = self.seg_or_fail(WEEKLY, W_CHANGE_SPEC_RE, "周报「上周相对上上周」细则")
        for opt in ("方向变了", "翻转位变了", "依据变了", "无实质变化"):
            self.assertIn(opt, seg, "四选一少了「%s」" % opt)
        self.assertIn("必须写明为什么没变", seg, "「无实质变化」不再需要给理由")
        self.assertIn("不得留空,不得写套话", seg, "套话禁令没了")
        self.assertIn("维持原判", seg, "套话禁令丢了具名样例")
        self.assertIn("禁止与上一份周报的同节逐字重复", seg, "跨期逐字重复禁令没了")
        self.assertIn("上一份周报不在白名单里", seg,
                      "丢了数字硬约束 —— 照写会当场炸 NUMBER_UNTRACEABLE")


class JudgementRingHasThreePartsTest(SkillDocTestCase):
    """依据 ③:判断环必须三件齐全 —— 关键假设 / 替代解释 / 翻转指标。

    守的是什么:旧形态只要求"失效条件",而失效条件是**消极**判据("没发生
    即作废"),常常等不到;评审标准要的是**翻转指标**("什么一旦出现就改判",
    积极、可观测)。两者字面相近,最容易的回退就是把翻转指标又写回失效条件,
    所以"出现即改判"这一串单独断言。

    "替代解释自带翻转指标"也单独断言:少了这半句,替代解释会退化成一句
    "也可能是别的原因",既不可证伪也不影响任何动作。

    预算那条(不可压缩)守的是与校验器的**硬冲突**:币种节有 330 中文字的
    硬上限(check_report.MAX_SECTION_CJK),判断环变重之后,最省事的解法
    就是删掉三件里的一件来腾字数 —— 而那正好把这条规则完整回退掉。
    """

    def test_daily_judgement_ring_names_all_three(self):
        seg = self.seg_or_fail(DAILY, D_JUDGEMENT_RE, "日报判断环细则")
        for part in ("关键假设", "替代解释", "翻转指标"):
            self.assertIn(part, seg, "判断环少了「%s」" % part)
        self.assertIn("假设不成立时判断会怎样", seg,
                      "关键假设只剩「假设是什么」,没交代假设不成立的后果")
        self.assertIn("它自己也要带一个翻转指标", seg,
                      "替代解释不再自带翻转指标 —— 会退化成「也可能是别的原因」")
        self.assertIn("出现即改判", seg,
                      "翻转指标被写回了消极的失效条件语义")

    def test_daily_ring_budget_protects_the_three_parts(self):
        seg = self.seg_or_fail(DAILY, D_RING_BUDGET_RE, "日报四环预算段")
        self.assertIn("判断环的三件是不可压缩项", seg,
                      "预算段不再保护判断环三件 —— 字数一紧就会被删掉一件")
        # 硬上限必须写出来:预算之和(320)与校验器上限(330)的关系是这条
        # 规则可执行的前提,漏写就会有人把四环预算加回到 330 以上。
        self.assertIn("校验器硬上限330", seg, "预算段丢了校验器硬上限")

    def test_weekly_theme_has_seven_segments_with_the_three(self):
        seg = self.seg_or_fail(WEEKLY, W_THEME_TMPL_RE, "周报主线模板")
        for part in ("关键假设", "替代解释", "翻转指标"):
            self.assertIn(part, seg, "周报主线少了「%s」段" % part)
        self.assertIn("它自己的翻转指标", seg, "周报替代解释不再自带翻转指标")
        self.assertIn("一旦出现就改判", seg, "周报翻转指标被写回消极语义")
        # 反向:旧的五段式用「证伪条件」收尾。它一旦长回主线模板,就与新的
        # 翻转指标并存,而"哪一段算数"无处可判 —— 本仓库反复栽的形态。
        self.assertNotIn("证伪条件", seg,
                         "旧的「证伪条件」段长回主线模板了,与翻转指标口径冲突")

    def test_weekly_hard_form_protects_the_three_segments(self):
        seg = self.seg_or_fail(WEEKLY, W_HARD_FORM_RE, "周报主线硬形态")
        self.assertIn("七段齐全", seg, "硬形态还在说五段 —— 新增三段不受约束")
        self.assertIn("不可压缩项", seg, "硬形态不再保护后三段")


class InvalidationAndFlipAreDecoupledTest(SkillDocTestCase):
    """2026-08-15:速览/落点表第 4 列「失效条件」与判断环「翻转指标」**解耦**。

    ---- 修前的病灶(实测,先跑后抄)----
    同一份 SKILL 给两个词下了**相反**的定义,又要求两处**同源同字**:
    - `#### 判断环` 的表行:失效条件 =「没发生就作废」(消极),
      翻转指标 =「出现即改判」(积极);
    - 速览表模板段与 `#### 判断环` 段末各有一句要求二者**同源同字**。
    照后者写,前者那条区分就不存在;照前者写,后者必违反。两句字面冲突,
    「哪一句算数」无处可判 —— 本仓库反复栽的形态。

    后果落到校验器上是一条**只能声明、不能判定**的码:
    `FLIP_INDICATOR_TABLE_COLUMN_IS_FLIP: 速览表「失效条件」列在 5/5 个币种上
     与该币种节的翻转指标去标点后逐字相同(…),该列因此不是独立的失效条件
     来源,② 不从该列取数`
    —— 按规定两处本就该是同一句,任何"两者不得相同"的检查都会恒红,于是
    校验器只好把事实打印出来、不判。

    ---- 本类守什么 ----
    ① 反向:**一句要求二者同字的旧句都不许留**。留一句就等于矛盾没解,
       而下游那条新违规码会与 SKILL 直接冲突。判据不是"某两个字面串不见了"
       —— 那种锚点换个措辞就绕过 —— 而是**全文每一处「同源同字」都必须
       是「条件方向 ↔ 决策日志 trigger」那一条**(它由
       `DECISION_TRIGGER_NOT_SOURCED` 守着,是仓库里唯一正当的同字要求)。
    ② 正向:第 4 列的语义写成「什么没发生就作废」,可观测量 + `T+N`;
    ③ 正向:两条定义**并列写在一处并互相点名**,且写明两处不得写成同一句。
    三条缺一不可:只有 ① 时读者不知道第 4 列该写什么;只有 ②③ 时旧要求
    可以原地长回来。
    """

    HOSTS = (("日报", DAILY), ("周报", WEEKLY))

    def test_every_same_wording_rule_is_about_the_decision_log(self):
        """全文普查式反向锚点。

        为什么不逐字禁那两句:措辞空间无界(ViolationDispositionTest 的类注释
        记了三次靠改写措辞存活的实测)。这里改成**枚举全部命中并逐个验明
        身份** —— 新写一条要求"失效条件与翻转指标同源同字"的句子,不管措辞
        怎么变,只要还用"同源同字"这个词就会被这一条抓住;换词写(如"逐字
        相同")则会被下面 ③ 的"两处不得写成同一句"直接矛盾,进 diff 时看得见。
        """
        t = plain(DAILY)
        hits = [m.start() for m in re.finditer("同源同字", t)]
        # 地板:日报侧的「条件方向 ↔ 决策日志 trigger」是仓库里**唯一正当**的
        # 同字要求(由 DECISION_TRIGGER_NOT_SOURCED 守着,实测两处:速览表模板段
        # 与第 5 步的决策日志段)。少了它,下面的循环就会空转通过 —— 而"把这个词
        # 从文档里删干净"正是最省事的绕过。
        self.assertGreaterEqual(len(hits), 2,
                                "日报侧的决策日志同字要求少了 —— 循环会空转")
        for i in hits:
            win = t[max(0, i - 60):i]
            self.assertTrue(
                "trigger" in win or "决策日志" in win,
                "日报里这一处「同源同字」不是「条件方向 ↔ 决策日志 trigger」"
                "那一条 —— 失效条件与翻转指标的解耦被推翻了:…%s同源同字"
                % win[-40:])
        # 周报侧**一处都不该有**:它此前唯一那处就是被删掉的「落点表失效条件 ↔
        # 主线翻转指标」,而周报流程里没有决策日志。这里写死 0 而不是复用上面
        # 那套窗口判定 —— 窗口判定要求"每一处都得是决策日志那条",在一个根本
        # 没有决策日志的文件里它恒真,等于不设防。
        self.assertEqual(plain(WEEKLY).count("同源同字"), 0,
                         "周报里又出现了同字要求 —— 周报没有决策日志,"
                         "任何同字要求都只可能是被删掉的那条长回来了")

    def test_the_old_coupling_sentences_are_gone_verbatim(self):
        """逐字锚点是**补充**,不是主力(主力是上面那条普查)。

        三串各自是被删掉那两句的**唯一开头**,留着任何一串都说明旧句只是被
        改了半截。剥掉 `*` 之后比对,理由见 `plain` 的注释。
        """
        for phrase in ("并与该币种节判断环的翻转指标同源同字",
                       "与本环的翻转指标同源同字",
                       "与它归属主线的翻转指标同源同字"):
            for name, path in self.HOSTS:
                self.assertNotIn(phrase, plain(path),
                                 "%s 里旧的同字要求还在:%s" % (name, phrase))

    def test_daily_overview_column_means_what_must_not_happen(self):
        seg = self.seg_or_fail(DAILY, D_OVERVIEW_TMPL_RE, "日报速览表模板段")
        self.assertIn("什么没发生这条判断就作废", seg,
                      "速览第 4 列没写明语义是「什么没发生就作废」")
        self.assertIn("可观测量", seg, "速览第 4 列不再要求可观测量")
        # 2026-08-15 第二轮:时限口径由「并带 `T+N`」改成「`T+N` 或年历发布日」。
        # 旧写法与 reports/daily/2026-08-14.md 附录 D 的年历规则(触发绑某期数据
        # 发布时**不得写 T+N**)互斥,实测 30 格里 3 格写的正是年历日期。
        self.assertIn("时限(`T+N`或年历发布日)", seg,   # seg 已去空白
                      "速览第 4 列不再要求带时限,或仍把年历发布日排除在外")
        self.assertIn("两处不得写成同一句", seg,
                      "速览表模板段没写明它与翻转指标不得写成同一句")

    def test_daily_overview_column_bans_the_two_machine_checked_forms(self):
        """两条新码必须在**写作时读者眼睛落到的那一段**里点名 ——
        判据在校验器里、规则却只写在别处,等于让作者靠猜。"""
        seg = self.seg_or_fail(DAILY, D_OVERVIEW_TMPL_RE, "日报速览表模板段")
        self.assertIn("INVALIDATION_COLUMN_VACUOUS", seg,
                      "空洞占位那条码没在速览表模板段点名")
        self.assertIn("INVALIDATION_COLUMN_MIRRORS_TRIGGER", seg,
                      "机械否定那条码没在速览表模板段点名")
        self.assertIn("机械否定", seg, "没写明第 4 列不得是第 2 列的机械否定")
        for axis in ("可观测量", "时限"):
            self.assertIn(axis, seg, "没写明两条轴里的「%s」轴" % axis)

    def test_daily_states_both_definitions_side_by_side(self):
        seg = self.seg_or_fail(DAILY, D_JUDGEMENT_RE, "日报判断环细则")
        self.assertIn("什么没发生,这条判断就作废", seg, "失效条件的定义不在此处")
        self.assertIn("什么一旦出现,就把这条判断改判", seg,
                      "翻转指标的定义不在此处 —— 两条定义没有并列")
        self.assertIn("禁止逐字相同、也禁止互为子串", seg,
                      "没写明两处不得重合 —— 校验器那条新违规码在 SKILL 里无据")
        self.assertIn("INVALIDATION_COLUMN_IS_FLIP_RESTATED", seg,
                      "没点名违反时报哪个码,读者拿到红也对不上这一段")

    def test_weekly_landing_column_means_what_must_not_happen(self):
        seg = self.seg_or_fail(WEEKLY, W_LANDING_TMPL_RE, "周报落点表模板段")
        self.assertIn("什么没发生这条判断就作废", seg,
                      "落点表第 5 列没写明语义是「什么没发生就作废」")
        self.assertIn("时限(`T+N`或年历发布日)", seg,   # seg 已去空白
                      "落点表第 5 列不再要求带时限,或仍把年历发布日排除在外")
        self.assertIn("两处不得写成同一句", seg,
                      "落点表模板段没写明它与主线翻转指标不得写成同一句")

    def test_weekly_landing_column_bans_the_two_machine_checked_forms(self):
        seg = self.seg_or_fail(WEEKLY, W_LANDING_TMPL_RE, "周报落点表模板段")
        self.assertIn("INVALIDATION_COLUMN_VACUOUS", seg,
                      "空洞占位那条码没在落点表模板段点名")
        self.assertIn("INVALIDATION_COLUMN_MIRRORS_TRIGGER", seg,
                      "机械否定那条码没在落点表模板段点名")
        self.assertIn("主线归属", seg,
                      "落点表模板段没写明归属格必须命名真实主线")

    def test_weekly_landing_requires_a_real_theme_in_the_belonging_column(self):
        """归属格由报告自己写,修前全仓零检查 —— 被查方自选宿主。
        校验器补了 `WEEKLY_THEME_ATTRIBUTION_UNKNOWN`,SKILL 必须同步点名。"""
        seg = self.seg_or_fail(WEEKLY, W_LANDING_TMPL_RE, "周报落点表模板段")
        self.assertIn("WEEKLY_THEME_ATTRIBUTION_UNKNOWN", seg,
                      "归属格那条码没在落点表模板段点名")

    def test_weekly_states_both_definitions_side_by_side(self):
        seg = self.seg_or_fail(WEEKLY, W_INVALIDATION_RE, "周报两条定义并列段")
        self.assertIn("什么没发生,这条判断就作废", seg, "失效条件的定义不在此处")
        self.assertIn("什么一旦出现,就把这条主线改判", seg,
                      "翻转指标的定义不在此处 —— 两条定义没有并列")
        self.assertIn("禁止逐字相同、也禁止互为子串", seg, "没写明两处不得重合")
        self.assertIn("INVALIDATION_COLUMN_IS_FLIP_RESTATED", seg,
                      "没点名违反时报哪个码")


class TransmissionSourceTest(SkillDocTestCase):
    """依据 ④(风险评估矩阵里 `Source of impact` 那一列):传导环必须命名
    **这条影响是通过什么传到汇率的**,而不是只说相关。

    守的是什么:那一列的作用是**逼出机制而非相关性**。"A 与汇率同向"读起来
    像有传导,实际不含任何可证伪内容 —— 读者据它判断不出这条链什么时候会断。
    所以除了正面要求,还断言那句**明确的不合格判定**;只留正面要求时,
    "A 与汇率相关"照样可以自称满足"写了传导"。
    """

    def test_daily_transmission_names_its_source(self):
        seg = self.seg_or_fail(DAILY, D_TRANSMISSION_RE, "日报传导环细则")
        self.assertIn("影响传导来源", seg, "传导环不再要求命名影响传导来源")
        self.assertIn("相关性不是机制", seg,
                      "丢了「只说相关即不合格」的判定 —— 相关性会冒充传导")

    def test_weekly_transmission_names_its_source(self):
        seg = self.seg_or_fail(WEEKLY, W_THEME_TMPL_RE, "周报主线模板")
        self.assertIn("显式命名影响传导来源", seg,
                      "周报传导机制段不再要求命名影响传导来源")
        self.assertIn("即为不合格", seg, "周报侧丢了「只说相关即不合格」的判定")


class EcbHierarchyTest(SkillDocTestCase):
    """依据 ⑤:ECB 官方的传导机制分解里**汇率不是一级渠道**,它挂在
    "影响资产价格"之下。

    守的是什么:引 ECB 权威去支撑一个 ECB 自己不认的结构,是**拿别人的名义
    背书自己的说法**。这条规则有**两个方向**,必须都在:
    ① 引 ECB 时按 ECB 的层级写;② 用我们自己那四类机制叙述时不要引 ECB。
    只留 ① 时,读者会给自家的四类机制统统挂上 ECB 的名义再"按层级"写一遍,
    违规照旧;只留 ② 时,ECB 的层级本身无人遵守。
    """

    def _assert_both_directions(self, path, pattern, name):
        seg = self.seg_or_fail(path, pattern, name)
        self.assertIn("汇率不是一级渠道", seg,
                      "%s 丢了 ECB 层级的核心事实" % name)
        self.assertIn("影响资产价格", seg,
                      "%s 没写明汇率挂在哪一级之下 —— 层级无从执行" % name)
        # flat() 去掉了所有空白,故锚点写作「不要引ECB权威」(原文 ECB 两侧有空格)
        self.assertIn("不要引ECB权威", seg,
                      "%s 丢了反向条款 —— 自家四类机制会被挂上 ECB 的名义" % name)

    def test_daily_states_both_directions(self):
        self._assert_both_directions(DAILY, D_ECB_RE, "日报 ECB 层级段")

    def test_weekly_states_both_directions(self):
        self._assert_both_directions(WEEKLY, W_ECB_RE, "周报 ECB 层级段")


class MeasuredFailureModeBansTest(SkillDocTestCase):
    """依据 ⑨ 的两条针对性禁令。两条是**互补**的,分开断言:

    - **零效应要显式写**:实测零效应识别率仅 13.8%(需修正符号方向的语境下
      整体准确率 73.9%→41.3%)。"这条消息其实不影响汇率"是最难写对的一类
      判断,不显式写就等于没判。
    - **无关素材不进正文**:实测一段无关文字就降 12.3 个百分点,且**形式被
      保留而实质失效** —— 读起来仍像那么回事,所以作者自己发现不了。

    两条合起来才闭环:少了前者,零效应判断会被"无关素材不进正文"顺手扫掉
    (它明明是判断,不是无关素材);少了后者,"显式写出来"会被当成许可,
    把一切无关素材都写进正文再补一句"无直接因果"。所以**分工那句**也断言。

    实测数字当锚点是有意的:它们是这两条禁令**唯一**不可替换的部分。规则
    本身可以被改写成任意同义句,而"13.8%""12.3"一旦不见,说明依据被删掉了,
    下一个人就会把禁令当成风格偏好删掉。
    """

    def test_daily_zero_effect_must_be_written(self):
        seg = self.seg_or_fail(DAILY, D_BAN11_RE, "日报禁令 11(零效应)")
        self.assertIn("必须把这个判断本身写出来", seg, "零效应判断不再要求显式写出")
        self.assertIn("13.8%", seg, "丢了零效应识别率这条依据")

    def test_daily_irrelevant_material_stays_out(self):
        seg = self.seg_or_fail(DAILY, D_BAN12_RE, "日报禁令 12(无关素材)")
        self.assertIn("放弃不写", seg, "无关素材不再要求直接放弃")
        self.assertIn("而不是写进来再补一句", seg,
                      "丢了「写进来再说无因果」这个具体反例 —— 那正是实测的形态")
        self.assertIn("12.3", seg, "丢了无关文字降幅这条依据")
        # flat() 去掉所有空白,故锚点不带空格(原文是「与禁令 11 的分工」)
        self.assertIn("与禁令11的分工", seg,
                      "两条禁令的分工没写 —— 零效应判断会被当成无关素材扫掉")

    def test_weekly_zero_effect_must_be_written(self):
        seg = self.seg_or_fail(WEEKLY, W_BAN7_RE, "周报禁令 7(零效应)")
        self.assertIn("必须把这个判断本身写出来", seg, "零效应判断不再要求显式写出")
        self.assertIn("13.8%", seg, "丢了零效应识别率这条依据")
        # 周报独有:零效应判断不得占掉一条主线名额(主线上限 5 条,校验器还有
        # THEME_TOO_MANY)。少了这句,"显式写出来"与"3–5 条主线"会互相挤。
        self.assertIn("不另起主线", seg,
                      "零效应判断会占掉主线名额,挤掉真正有链的那几条")

    def test_weekly_irrelevant_material_stays_out(self):
        seg = self.seg_or_fail(WEEKLY, W_BAN8_RE, "周报禁令 8(无关素材)")
        self.assertIn("放弃不写", seg, "无关素材不再要求直接放弃")
        self.assertIn("12.3", seg, "丢了无关文字降幅这条依据")
        self.assertIn("与第7条的分工", seg, "两条禁令的分工没写")


class ProbabilityLexiconTodoTest(SkillDocTestCase):
    """依据 ③ 第四点(概率词绑数值区间)**本轮明确不做**,但必须留下 TODO。

    守的是什么:不是规则,是**待办本身**。这一条被推迟的理由是代价(要为五
    币种各定一套词表并长期守住口径),不是它不重要;没有落盘的 TODO,下一
    轮无从知道这是"想过并推迟"还是"没想到"。

    两份 SKILL 都要有:概率词口径若只在一份里落地,日报与周报会各走一套词表,
    而那恰恰是这条依据点名禁止的"混用不同词表行"。
    """

    def test_both_skills_carry_the_deferred_todo(self):
        for name, path in (("日报", DAILY), ("周报", WEEKLY)):
            self.assertIn("概率词绑数值区间", flat(path),
                          "%s 缺概率词表的 TODO —— 下一轮会当成没想到" % name)


CODE_RE = re.compile(r'"(VERDICT_[A-Z_]+):')
LOOSE_RE = re.compile(r"VERDICT_[A-Z_]+")


def check_report_src():
    with open(os.path.join(ROOT, "scripts", "check_report.py"),
              encoding="utf-8") as f:
        return f.read()


class VerdictCodesAreDocumentedTest(unittest.TestCase):
    """新增一个 VERDICT_* 码而忘了写处置,运维就会读到一个查不到的码。
    这是码与文档同步的唯一自动防线 —— 与 EMPTY_EVENTS_DERIVED 的键集哨兵
    同一思路。
    """

    def test_every_code_appears_in_some_skill(self):
        """普查:8 个码在 flat(DAILY)+flat(WEEKLY) 里的 count 分别是
        2/2/2/2/2/2/4/3 —— **每一个都被至少两处喂饱**,全部保留。

        这一条的契约就是"**至少有一份** skill 写了它",多处出现正是想要的语义
        (两份 skill 各写一次、日报侧禁令 9 又点名了两个跳过码)。但也正因如此,
        它对**任何**单点删除都无能为力,不止某一两个码。"某一处的处置被删"
        由四处段级测试守:两个跳过档码的处置段(SkippedCodeDispositionTest)、
        以及日报与周报的违规节(ViolationDispositionTest)。
        """
        codes = set(CODE_RE.findall(check_report_src()))
        self.assertTrue(codes, "没扫到任何码,正则或路径错了")
        docs = flat(DAILY) + flat(WEEKLY)
        for code in sorted(codes):
            self.assertIn(code, docs, code)

    def test_loose_scan_finds_only_constant_names_beyond_the_codes(self):
        """CODE_RE 只认「出现在违规/声明字符串开头」的码。松扫描还会捞到
        VERDICT_FIELDS_EVENTS 这类常量名,VERDICT_SCHEMA 更只是
        DERIVED_VERDICT_SCHEMA 的子串 —— 它们不是运维会读到的码,不该要求
        写进文档。这条把差集钉死为「模块级常量定义」:将来若有码以别的形式
        发出,CODE_RE 漏掉它时这里会红。
        """
        src = check_report_src()
        extra = sorted(set(LOOSE_RE.findall(src)) - set(CODE_RE.findall(src)))
        for token in extra:
            self.assertRegex(
                src, r"(?m)^[A-Z_]*%s[A-Z_]*\s*=" % token,
                "%s 既不是发出的码、也不是模块级常量名" % token)


if __name__ == "__main__":
    unittest.main()


class UnchangedRefWordingInSkillTest(SkillDocTestCase):
    """SKILL 让 LLM 写的那一句,必须和 `claims.unchanged_ref_note` 一个措辞,
    而且同样不许断言原因。

    这一处**不是可有可无的第二份**:第 2 步的"汇率变动"行由 LLM 手写进要点表
    (脚本只管复盘材料块),SKILL 是它唯一的措辞来源。改了脚本不改这里,同一
    件事在报告里会有两种说法,而"哪一份算数"无处可判 —— 正是本文件开头那段
    说的"第二处判定"。

    诚实标注:这里查的是**SKILL 正文里出没出现哪些串**,即存在性检查;它保证
    不了 LLM 真照着写(那由 check_report 的溯源与逐字引用检查兜)。
    """

    CAUSE_WORDS = UNCHANGED_REF_CAUSE_WORDS   # 与脚本侧同一份词表

    def test_daily_skill_quotes_the_scripts_wording(self):
        t = flat(DAILY)
        self.assertIn(
            "".join(claims.unchanged_ref_note("<ref_date>").split()), t,
            "第 2 步的汇率变动行不再用脚本那句措辞")

    def test_daily_skill_asserts_no_cause(self):
        t = raw(DAILY)
        for word in self.CAUSE_WORDS:
            with self.subTest(word=word):
                self.assertNotIn(word, t,
                                 "SKILL 仍在教 LLM 断言原因:「%s」" % word)


class EerParagraphTest(SkillDocTestCase):
    """有效汇率那一段的**内容**必须被钉住。

    ---- 为什么(2026-08-21 对抗证伪查出)----
    这一段是本轮新加的散文,而 `tests/test_skill_docs.py` 是全仓唯一对 SKILL
    内容做断言的地方。实测五个变异全部存活(45 tests OK):整段删除、
    把「禁止写成当日变动」改成「允许」(**语义整个反转**)、删掉
    「不得混用或相加」、存量事实清单里删掉有效汇率、「月频」改「日频」。
    也就是说这段规则当时的强制力是零。

    断言一律写**正向**(要求某句在),不写反向(要求某词不在)——
    反向锚点换个说法就静默失守,本文件开头已为此警告过。
    """

    def eer(self):
        seg = block(raw(DAILY), r"- 有效汇率:名义.*?- 年历命中")
        self.assertIsNotNone(seg, "没摘到有效汇率那一段,文档结构变了")
        return seg

    def test_the_paragraph_is_in_the_brief_template(self):
        self.assertIn("名义", self.eer())
        self.assertIn("实际", self.eer())

    def test_it_is_a_fixed_line_not_gated_on_new_release(self):
        """一年只有十二天能列出来的话,「拿它当存量锚」这条授权就执行不了。"""
        seg = self.eer()
        self.assertIn("固定行", seg)
        self.assertIn("is_new_release", seg)

    def test_the_index_is_declared_not_to_be_an_equilibrium(self):
        """C1:基期不是均衡值。缺了这句,「88.47 说明比索被低估」就没人拦。"""
        seg = self.eer()
        # `block()` 会把空白压平,所以这里比的是压平后的形态
        self.assertIn("2020=100", seg)
        self.assertIn("基期", seg)
        self.assertIn("均衡", seg)

    def test_deriving_undervaluation_from_the_base_is_banned(self):
        seg = self.eer()
        self.assertRegex(seg, r"禁止[^。]*低估")

    def test_the_direction_is_stated_and_opposite_to_the_reference_rate(self):
        """Ma3:指数上升 = 本币升值,参考价上升 = 本币贬值。同节引两者必分开写。"""
        seg = self.eer()
        self.assertIn("升值", seg)
        self.assertIn("贬值", seg)
        self.assertIn("appreciation", seg)
        # 光有两个方向词不够:「方向与参考价相反」这句本身是承重的,
        # 删掉它只留下两个词,读者拿不到"两者反向"这个结论。
        self.assertIn("方向与参考价相反", seg)

    def test_nominal_and_real_must_not_be_conflated(self):
        seg = self.eer()
        self.assertRegex(seg, r"不得混用")
        self.assertRegex(seg, r"不得相加|不得.{0,4}相加")

    def test_the_change_verb_rule_is_a_ban_not_a_permission(self):
        """变异靶点:把「禁止」改成「允许」必须打红。"""
        seg = self.eer()
        self.assertRegex(seg, r"禁止[^。]*当日的变动")

    def test_the_monthly_slice_is_our_choice_not_the_sources_limit(self):
        """Mi11:WS_EER 有日频名义序列。写成「它是月频指数」是把本轮的切片
        选择说成了源的属性,下一个读的人会以为 BIS 没有日频。"""
        seg = self.eer()
        self.assertIn("日频", seg)
        self.assertIn("本仓的选择", seg)
        # 「取的是哪一档」本身要钉住:把「月频」改成「日频」时,
        # 上面两条断言都还成立(两个词都在段里),规则却已经反了。
        self.assertIn("既然取的是月频", seg)

    def test_the_thin_day_stock_fact_list_includes_it(self):
        seg = self.seg_or_fail(
            DAILY, r"\*\*数据薄的那一天怎么写\*\*.*?不许当成判断写出来",
            "数据薄的那一天怎么写")
        self.assertIn("有效汇率", seg)

    def test_the_bis_attribution_section_is_in_the_template(self):
        """C2:署名是许可的前置条件,模板里必须有它,且串要与校验器同源。"""
        from scripts import check_report
        t = raw(DAILY)
        self.assertIn("附录 D:数据来源声明", t)
        self.assertIn(check_report.BIS_ATTRIBUTION_LINE, t)
