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

    def test_count_capped_is_named_only_by_the_ban(self):
        """一边禁止据 `count_capped` 拼话术、一边教着按 `count_capped` 拼话术,
        两句字面冲突,而"哪一句算数"无处可判。堵法:这个布尔在全文只准出现在
        禁令那一处。

        第二条断言防的是相反的过头修法 —— 直接删掉冲突句会留下真实缺口:
        `count_delta` 仍可引用,而 `events_verdict` 的 caveat 并没有说"delta 为 0
        是上限造成的",LLM 于是可以合法引用 delta=0 并自行解读成"持平"。
        替代规则必须还在,只是不再依赖布尔字段。"""
        t = flat(DAILY)
        self.assertEqual(t.count("count_capped"), 1,
                         "count_capped 只应出现在「禁止据布尔拼话术」那一处")
        self.assertIn("与前值持平", t, "堵 delta=0 → 持平 的规则不能被一删了之")

    def test_states_the_exact_substring_rule(self):
        t = flat(DAILY)
        self.assertIn("精确子串包含", t)
        self.assertIn("改动一个字符", t)

    def test_ban_nine_carves_out_the_legacy_snapshot_case(self):
        """禁令 9 无条件要求逐字照抄结论句,而第 2 步规定该键不存在或为 null 时
        该行写"结论句不可得(存量快照)" —— 此时根本没有句子可引。LLM 面对
        "必须照抄一句不存在的话"最可能的动作就是自己编一句,而校验器此时正处于
        跳过档,一个字都抓不到,没有任何测试能碰到它。

        不是边角情况:data/ 下 6 份快照没有一份带 events_verdict —— 其中
        2026-08-07..10 这 4 份连 derived 节都没有(走 VERDICT_SKIPPED_NO_DERIVED),
        2026-08-11/12 这 2 份 schema_version=1 低于闸门 2(走
        VERDICT_SKIPPED_LEGACY)。**两个码都要在豁免口里点名**:只写一个,
        另一个码的持有者会以为豁免不适用于自己。"""
        seg = block(raw(DAILY), r"(?m)^9\. \*\*事件结论句.*?(?=\n\n)")
        self.assertIsNotNone(seg, "没摘到禁令 9 段落,正则或文档结构变了")
        self.assertIn("存量快照", seg, "禁令 9 缺存量快照豁免口")
        self.assertIn("禁止自行补造", seg, "禁令 9 没堵住「自己编一句」")
        for code in ("VERDICT_SKIPPED_NO_DERIVED", "VERDICT_SKIPPED_LEGACY"):
            self.assertIn(code, seg, "豁免口漏点名 %s" % code)


class LegacyCodeDispositionTest(unittest.TestCase):
    """降级码的处置必须是仓库里跑得动的动作。写一条没有入口的指令,运维照做
    时只会退回"随便跑点什么",比不写更坏。"""

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
    def test_three_verdict_fields_named(self):
        t = flat(WEEKLY)
        for field in ("fixings_verdict", "articles_verdict", "official_verdict"):
            self.assertIn(field, t, field)

    def test_states_the_exact_substring_rule(self):
        t = flat(WEEKLY)
        self.assertIn("整句逐字", t)
        self.assertIn("精确子串包含", t)
        self.assertIn("改动一个字符", t)


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
