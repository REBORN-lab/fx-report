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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DAILY = os.path.join(ROOT, "skills", "fx-daily-report", "SKILL.md")
WEEKLY = os.path.join(ROOT, "skills", "fx-weekly-report", "SKILL.md")


def raw(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def flat(path):
    """去掉所有空白后比对 —— 断言不该被折行位置绑架。"""
    return "".join(raw(path).split())


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
        for field in sorted(set(fields)):
            for s in mentions(t, field):
                self.assertTrue(
                    "禁止" in s and "拼装" in s,
                    "%s 的这一处提及不是禁止拼装、而是在教着按布尔拼话术:%s"
                    % (field, s))
        self.assertIn("与前值持平", t, "堵 delta=0 → 持平 的规则不能被一删了之")

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
        """禁令 9 要求逐字照抄结论句,而第 2 步规定该键不存在或为 null 时该行写
        "结论句不可得(快照未落结论句)" —— 此时根本没有句子可引。LLM 面对
        "必须照抄一句不存在的话"最可能的动作就是自己编一句,而校验器此时正处于
        跳过档,一个字都抓不到,没有任何测试能碰到它。

        不是边角情况:data/ 下 6 份快照没有一份带 events_verdict —— 其中
        2026-08-07..10 这 4 份连 derived 节都没有(走 VERDICT_SKIPPED_NO_DERIVED),
        2026-08-11/12 这 2 份 schema_version=1 低于闸门 2(走
        VERDICT_SKIPPED_LEGACY)。**两个码都要在豁免口里点名**:只写一个,
        另一个码的持有者会以为豁免不适用于自己。

        主规则也要守:原先只查了豁免口,把"必须在**该币种节**内**逐字**出现"
        削成"在美元节内出现即可"(五币种缩到一个币种)照样绿 —— 修复的覆盖
        只盖住了自己新加的那半句。

        豁免口对 `VERDICT_SKIPPED_NO_DERIVED` 必须**限定在窗口已移过那一支**:
        当日 derive 崩了的快照也发这个码,若无条件豁免,第 2 步给它贴上标签 →
        禁令 9 按字面免除该币种的逐字引用 → 校验器此档只出声明(rc 0),
        没有第二道拦。

        校验器口径("精确子串包含""改动一个字符")必须留在**本段**:早先它走
        全文级断言,把这两句从禁令 9 挪到第 5 步照样全绿(实测存活)。禁令 9 的
        核心约束另有段级断言守着,挪走的是加强说明 —— 但"说得比实际宽"正是
        本仓库反复栽的形态,而修法零成本:seg 本来就摘出来了。"""
        seg = self.seg_or_fail(DAILY, BAN9_RE, "禁令 9 段落")
        # 主规则:这半句被削掉时,原来的断言一条都不会红
        self.assertIn("该币种节", seg, "主规则的作用域被削(五币种→单币种?)")
        # 锚点必须是主规则**独有**的整串。原先只断言"逐字"二字 —— 段内它有两处
        # (主规则的"**逐字**出现"、豁免口那句),后者把断言喂饱:把主规则改成
        # "可在该币种节内按大意复述"照样绿(实测存活),而那与 delta spec 的
        # 「日报 SHALL 逐字整句引用」直接相反,且让同段自相矛盾(下一句还写着
        # "改动一个字符即判违规")。
        self.assertIn("必须在该币种节内**逐字**出现", seg,
                      "主规则被改写(不再要求逐字出现在该币种节内)")
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
    """`VERDICT_NOT_QUOTED` 是本 change 唯一**可操作**的违规码 —— 处置是"改报告",
    恰恰是运维最需要的那条。其余违规码的处置都是"这是脚本缺陷,改报告没用"。

    光靠 VerdictCodesAreDocumentedTest 守不住它:那条查的是"码名在两份 skill
    合起来的正文里出现过",而每个码的 count 都 ≥2,删掉任一处都有别处顶上。
    """

    def test_daily_violation_section_keeps_the_actionable_code(self):
        seg = self.seg_or_fail(DAILY, DAILY_VIOLATION_RE, "日报「违规」节")
        self.assertIn("VERDICT_NOT_QUOTED", seg, "日报违规节丢了唯一可操作的码")
        self.assertIn("改报告", seg, "VERDICT_NOT_QUOTED 丢了处置动作")

    def test_weekly_violation_section_keeps_the_actionable_code(self):
        seg = self.seg_or_fail(WEEKLY, WEEKLY_VIOLATION_RE, "周报「违规码」节")
        self.assertIn("VERDICT_NOT_QUOTED", seg, "周报违规节丢了唯一可操作的码")
        self.assertIn("改周报", seg, "VERDICT_NOT_QUOTED 丢了处置动作")


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

    def test_no_nonexistent_derive_entry_in_disposition(self):
        """日报侧那条处置("重新派生该日快照")曾是不可执行的指令。周报侧只做
        交叉引用,不该出现同款文案。"""
        self.assertNotIn("重新派生该日快照", flat(WEEKLY),
                         "周报侧若有同一处置文案须一并同步")


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
