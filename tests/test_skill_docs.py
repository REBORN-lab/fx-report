"""SKILL 文档哨兵。

新增一个结论句字段要同步四处(derive / EMPTY_EVENTS_DERIVED / SKILL /
校验器)。前三处漏一处会被键集断言或单测抓住,唯独 SKILL 是散文 —— 漏改
不会让任何测试变红,而它恰恰是"第二处判定"的藏身处:同一判定在提示词与
脚本各写一遍,两份措辞必然漂移,"哪一份算数"无处可判。
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


BAN_ANCHOR = "自行拼装任何话术"


def banned_booleans(flat_text):
    """从禁令句本身抽出被点名的字段 —— **哨兵的主语只能有这一个来源**。

    在测试里另抄一份名单,就是本 change 从头到尾在消灭的形态:同一份判定
    有两份拷贝,两份必然漂移,而"哪份算数"无处可判。这里漂移的方向还是
    静默失守:derive 新增第六个布尔、SKILL 禁令也写上了它,而手抄名单没
    跟上 → 哨兵根本不守它,全绿照过。

    锚点取"自行拼装任何话术"整串:F3 那句写的是"自行拼装任何关于条数多寡
    的话术",不含本串,不会被误抽 —— 那句里的 `events_verdict` 不是被禁的
    布尔,抽进来会让整个循环失去意义。实测全文恰有一句含本锚点,且该句的
    反引号内容恰好只有五个字段名,没有混入别的反引号内容。
    """
    for s in sentences(flat_text):
        if BAN_ANCHOR in s:
            return re.findall(r"`([^`]+)`", s)
    return []


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


def sentences(flat_text):
    """按句号切句。**这里不能用空行切段**:禁令那句与曾经教着按布尔拼话术的
    那句同处一个 markdown 列表项(- 派生指标:)之内,中间一个空行都没有,
    按空行切会把两者判成同一段,于是"提及落在哪儿"永远为真。"""
    return [s for s in flat_text.split("。") if s]


class DailySkillTest(unittest.TestCase):
    def test_points_at_the_verdict_field(self):
        t = flat(DAILY)
        self.assertIn("events_verdict", t)
        self.assertIn("逐字整句照抄", t)

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

    # **这张表不驱动任何检查**,只当地板。循环的主语一律从禁令句里抽
    # (见 banned_booleans),否则它就成了那五个字段的第二份手抄拷贝。
    # 地板防的是反向绕过:把布尔从禁令句里删掉,抽出来的集合随之变空,
    # 循环无事可做,测试反而变绿 —— 靠削禁令句放绿的路必须堵死。
    BANNED_FLOOR = ("count_capped", "sample_capped", "main_sample_capped",
                    "channel_changed_from", "dropped_malformed")

    # `source_capped` 同样被禁,却**抽不出来**:禁它的那句(第 2 步"昨日事件
    # top"那段)同时含权威字段 `events_verdict`,正则分不开被禁字段与该引用的
    # 字段;放宽锚点去抽那一句,会把 `events_verdict` 也抽成"被禁布尔",于是
    # 循环要求全文每一处 `events_verdict` 都落在禁令内 —— 整个循环失去意义。
    # F9 已验证过这个坑,所以这里显式并入,而不是去动锚点。
    # 它不进 BANNED_FLOOR:地板管的是"禁令句里不许少字段",而它不在那句里。
    EXTRA_BANNED = ("source_capped",)

    def test_every_mention_of_a_banned_boolean_sits_inside_a_ban(self):
        """一边禁止据这些布尔拼话术、一边教着按它们拼话术,两句字面冲突,
        而"哪一句算数"无处可判。

        判据是**每一处提及所在的那一句都得是禁令**,不是"全文只准出现 N 次"。
        计数式断言脆:将来正当地再提一次(比如新增一条禁令)它就红,而最省事
        的"修法"是把断言改松 —— 靠放宽断言消除红是本仓库明令禁止的。句子级
        判定则相反:新增正当禁令自然通过,把判定话术写回模板段必红。

        主语从禁令句抽,所以 SKILL 禁令新点名一个布尔时,哨兵**不改测试就
        自动守它**;地板断言则挡住反向绕过。两条合起来才让禁令句成为唯一
        事实源。

        最后一条断言防的是相反的过头修法 —— 直接删掉冲突句会留下真实缺口:
        `count_delta` 仍可引用,而 `events_verdict` 的 caveat 并没有说"delta 为 0
        是上限造成的",LLM 于是可以合法引用 delta=0 并自行解读成"持平"。
        替代规则必须还在,只是不再依赖布尔字段。"""
        t = flat(DAILY)
        fields = banned_booleans(t)
        self.assertTrue(fields, "没抽到禁令句(锚点 %r 不在文中?)" % BAN_ANCHOR)
        missing = sorted(set(self.BANNED_FLOOR) - set(fields))
        self.assertFalse(
            missing, "禁令句里少了这些布尔 —— 靠削禁令句放绿?%s" % missing)
        for field in sorted(set(fields) | set(self.EXTRA_BANNED)):
            for s in mentions(t, field):
                self.assertTrue(
                    "禁止" in s and "拼装" in s,
                    "%s 的这一处提及不是禁止拼装、而是在教着按布尔拼话术:%s"
                    % (field, s))
        self.assertIn("与前值持平", t, "堵 delta=0 → 持平 的规则不能被一删了之")

    def test_states_the_exact_substring_rule(self):
        t = flat(DAILY)
        self.assertIn("精确子串包含", t)
        self.assertIn("改动一个字符", t)

    def test_the_no_verdict_label_is_neutral(self):
        """第 2 步那个标签串是禁令 9 豁免口的**触发条件**,两处必须逐字一致,
        而且它不能叫"(存量快照)"。

        叫"(存量快照)"时形成这条链:**当日 derive 崩了**的快照也走第 2 步这一行
        → 被贴上事实错误的"存量"标签 → 禁令 9 的豁免正按这个字面串生效、该币种
        免除逐字引用 → 校验器此档只出 VERDICT_SKIPPED_NO_DERIVED 声明(rc 0),
        没有第二道拦。第 5 步 F6 那轮已经把"不是快照旧不旧"写进判别标准了,
        第 2 步和禁令 9 却还按"NO_DERIVED = 存量快照"写 —— 同一形态三处口径打架。
        """
        t = flat(DAILY)
        self.assertNotIn(
            "结论句不可得(存量快照)", t,
            "标签把「快照里没有这一句」当成了「快照旧」——当日 derive 崩了的"
            "快照会被错误豁免")
        self.assertIn("结论句不可得(快照未落结论句)", t, "中性标签不见了")
        self.assertGreaterEqual(
            t.count("结论句不可得(快照未落结论句)"), 2,
            "标签只出现一次 —— 第 2 步的定义与禁令 9 豁免口的引用必须同串")

    def test_ban_nine_carves_out_the_legacy_snapshot_case(self):
        """禁令 9 无条件要求逐字照抄结论句,而第 2 步规定该键不存在或为 null 时
        该行写"结论句不可得(存量快照)" —— 此时根本没有句子可引。LLM 面对
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
        没有第二道拦。"""
        seg = block(raw(DAILY), r"(?m)^9\. \*\*事件结论句.*?(?=\n\n)")
        self.assertIsNotNone(seg, "没摘到禁令 9 段落,正则或文档结构变了")
        # 主规则(I1):这半句被削掉时,原来的断言一条都不会红
        self.assertIn("该币种节", seg, "主规则的作用域被削(五币种→单币种?)")
        self.assertIn("逐字", seg, "主规则丢了「逐字」要求")
        # 豁免口
        self.assertIn("本条不适用", seg, "禁令 9 缺豁免口")
        self.assertIn("禁止自行补造", seg, "禁令 9 没堵住「自己编一句」")
        self.assertIn("窗口已移过", seg,
                      "豁免口没把 NO_DERIVED 限定在窗口已移过那一支")
        for code in ("VERDICT_SKIPPED_NO_DERIVED", "VERDICT_SKIPPED_LEGACY"):
            self.assertIn(code, seg, "豁免口漏点名 %s" % code)


class LegacyCodeDispositionTest(unittest.TestCase):
    """降级码的处置必须是仓库里跑得动的动作。写一条没有入口的指令,运维照做
    时只会退回"随便跑点什么",比不写更坏。"""

    def test_no_derived_disposition_splits_the_two_cases(self):
        """`VERDICT_SKIPPED_NO_DERIVED` 只有"重跑第 1 步采集"这一支处置,而它
        只对采集窗口还覆盖 DATE 的快照成立。对 data/2026-08-07..10 那 4 份
        (窗口已移过),重跑拿到的不是当日那批条目 —— 与 VERDICT_SKIPPED_LEGACY
        被否掉"重新派生"的理由一模一样。

        这条缝是本轮自己开的:禁令 9 的豁免口已点名该码是合法跳过档、无句可引,
        处置表却仍叫人去重跑采集。同一份文档一处说"不必补救"、一处说"重跑",
        「哪一句算数」无处可判 —— 正是本 change 要消灭的形态。
        两支都必须在,且判别标准要可执行(采集窗口是否还覆盖该日)。

        锚点必须取两支**各自独有**的整串。原先断言的是"重跑"与"存量快照",
        两个词在段内都由**另一支**供给("此时重跑采集拿回的不是当日那批条目"、
        分支二的"(存量快照)"标签),于是整支删掉照样绿 —— 审查实测把分支一
        整段删除,全量 rc=0、变异存活,F6 被完整回退而无人知晓。
        断言当时能红 ≠ 断言守得住回退。"""
        seg = block(raw(DAILY),
                    r"(?m)^- `VERDICT_SKIPPED_NO_DERIVED`.*?(?=\n\n|\n- `|\Z)")
        self.assertIsNotNone(seg, "没摘到 VERDICT_SKIPPED_NO_DERIVED 的处置段")
        self.assertIn("采集窗口", seg, "缺可执行的判别标准,读者判不出自己属哪支")
        self.assertIn("窗口仍覆盖", seg, "分支一(重跑采集)整支没了")
        # seg 已压平,断言串不能带空格
        self.assertIn("重跑第1步采集", seg, "分支一丢了可执行动作")
        self.assertIn("重做第2步与第4步", seg,
                      "分支一只说重跑采集,没说要回头重做要点表与报告")
        self.assertIn("窗口已移过", seg, "分支二(无补救)整支没了")
        self.assertIn("禁止自行补造", seg, "分支二没堵住「自己编一句」")

    def test_legacy_disposition_names_no_nonexistent_derive_entry(self):
        seg = block(raw(DAILY),
                    r"(?m)^- `VERDICT_SKIPPED_LEGACY`.*?(?=\n\n|\n- `|\Z)")
        self.assertIsNotNone(seg, "没摘到 VERDICT_SKIPPED_LEGACY 的处置段")
        self.assertNotIn("重新派生该日快照", seg,
                         "仓库没有 derive-only 入口,这条指令跑不了")
        self.assertIn("derive-only", seg, "须写明当前没有 derive-only 入口")
        self.assertIn("重新采集", seg,
                      "须写明重跑 scripts.collect 是重新采集、不是重新派生")
        self.assertNotIn("重新派生该日快照", flat(WEEKLY),
                         "周报侧若有同一处置文案须一并同步")


class WeeklySkillTest(unittest.TestCase):
    """周报侧必须与日报侧同级:段落级,不是全文级。

    三个字段名在模板节与纪律第 4 条另有出现,「整句逐字」「精确子串包含」也
    在别处出现,所以全文级 assertIn 证明不了它们落在同一条规则里。审查实测:
    把纪律第 1 条整条改成「`articles_verdict` 只准照抄……`fixings_verdict` 与
    `official_verdict` 可自行改写」—— 与 delta spec 的「三类结论句全覆盖」直接
    相反 —— 全量 671 仍然全绿;单独摘掉 `official_verdict`、单独摘掉
    `fixings_verdict` 也各自存活。
    """

    def ban_one(self):
        return block(raw(WEEKLY), r"(?m)^1\. \*\*三条结论句.*?(?=\n\n|\n\d+\. )")

    def test_all_three_verdicts_are_quote_only_in_one_rule(self):
        seg = self.ban_one()
        self.assertIsNotNone(seg, "没摘到「计数与结论纪律」第 1 条")
        self.assertIn("不准改写", seg, "第 1 条的「只准照抄,不准改写」被换掉了")
        for field in ("fixings_verdict", "articles_verdict", "official_verdict"):
            self.assertIn(field, seg, "%s 不在第 1 条的照抄范围内" % field)
        # 正面锁住规则本身,负面这条挡的是更隐蔽的变体:保留标题、另加一句
        # 「某某可自行改写」把个别字段摘出去。delta spec 要求三类全覆盖,
        # 「可自行改写」在这一条里没有任何合法用法。
        self.assertNotIn("可自行改写", seg, "有字段被摘出照抄范围")

    def test_states_the_exact_substring_rule(self):
        seg = self.ban_one()
        self.assertIsNotNone(seg, "没摘到「计数与结论纪律」第 1 条")
        for rule in ("整句逐字", "精确子串包含", "改动一个字符"):
            self.assertIn(rule, seg, "%s 不在第 1 条内" % rule)


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
