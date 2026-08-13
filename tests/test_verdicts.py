"""结论句拼装口(Design Doc §4:共享拼装,不共享判定)。"""
import unittest

from scripts.verdicts import join_verdict


class JoinVerdictTest(unittest.TestCase):
    """会漂移的是措辞与连接方式,不是判定 —— 所以抽出来的只有这一层。"""

    def test_no_caveats_returns_head_unchanged(self):
        """空括号是最明显的漂移入口:「区间内至少 3 条()」会让读者无从判断
        是脚本漏填了,还是确实没有任何观测缺口 —— 而后者是最强的一条结论。"""
        self.assertEqual(join_verdict("区间内至少 3 条", []), "区间内至少 3 条")

    def test_empty_tuple_also_returns_head(self):
        self.assertEqual(join_verdict("当日未采到事件", ()), "当日未采到事件")

    def test_single_caveat_wrapped_in_parens(self):
        self.assertEqual(join_verdict("区间内至少 3 条", ["1/5 天未采到"]),
                         "区间内至少 3 条(1/5 天未采到)")

    def test_multiple_caveats_joined_with_ideographic_comma(self):
        self.assertEqual(
            join_verdict("区间内至少 3 条",
                         ["1/5 天未采到", "2 天顶到当日采集上限"]),
            "区间内至少 3 条(1/5 天未采到、2 天顶到当日采集上限)")

    def test_parens_follow_the_repo_convention(self):
        """括号沿用仓库既有写法 —— 实测真实 digest 的 articles_verdict、
        weekly_digest._verdict 的输出、tests/test_weekly_digest.py 的期望串
        三者的括号都是 ASCII 0x28/0x29,分隔符是全角顿号 0x3001。
        整句包含检查是逐字节的,换成全角括号会让同一条结论在两处不相等,
        而 Task 2 的硬要求正是「输出与重构前逐字节相同」。"""
        got = join_verdict("头", ["尾甲", "尾乙"])
        self.assertEqual(got, "头(尾甲、尾乙)")
        self.assertEqual([hex(ord(c)) for c in got if c in "()（）、"],
                         ["0x28", "0x3001", "0x29"])

    def test_byte_identical_with_the_existing_weekly_wording(self):
        """地面事实锚点:同样的 head 与 caveat,拼装口的输出必须与
        weekly_digest._verdict 的输出逐字节相同。括号宽度这类差异肉眼
        看不出来,只有逐字节比对能抓住。

        此刻 weekly_digest 还不含 join_verdict,故这是跨模块的地面事实
        比对,不存在自我循环。Task 2 让 _verdict 改经拼装口之后两边同源,
        届时由下面那行冻结的字面量继续兜底。"""
        from scripts import weekly_digest as wd
        stats = {"days_collected": 2, "undated": 0, "capped_days": 0,
                 "daily_cap": None, "outside_window": 0, "in_window": 3,
                 "malformed": 0}
        self.assertEqual(join_verdict("区间内至少 3 条", ["3/5 天未采到"]),
                         wd._verdict(stats, 5, 0, "事件"))
        self.assertEqual(wd._verdict(stats, 5, 0, "事件"),
                         "区间内至少 3 条(3/5 天未采到)")


class JoinVerdictShapeGateTest(unittest.TestCase):
    """形状不对一律抛错,不静默拼。

    这个函数产出的句子会被逐字抄进中文报告,而校验判据是精确子串包含 ——
    只比"报告与快照是否一致",不会发现快照里的句子本身已经坏了。坏句子
    一旦落盘就无人拦截,所以要在产出侧响亮失败。

    最危险的是 caveats=None:静默返回 head 等于把"有观测缺口"改写成
    "没有缺口",而后者是最强的一条结论 —— 「缺输入写 null 不写 0」
    在句子层的同型违反。
    """

    def test_none_caveats_raises_not_silently_strongest_conclusion(self):
        with self.assertRaises(TypeError):
            join_verdict("区间内确实 0 条", None)

    def test_generator_raises_instead_of_empty_parens(self):
        """生成器求值一次即空,会拼出 docstring 承诺不会出现的空括号。"""
        with self.assertRaises(TypeError):
            join_verdict("区间内确实 0 条", (c for c in []))

    def test_bare_string_raises_instead_of_splitting_into_characters(self):
        """漏包成 list 时会把一句 caveat 拆成逐字顿号连接。"""
        with self.assertRaises(TypeError):
            join_verdict("头", "3/5 天未采到")

    def test_empty_caveat_raises(self):
        with self.assertRaises(ValueError):
            join_verdict("头", ["", "尾乙"])

    def test_non_string_caveat_raises(self):
        with self.assertRaises(ValueError):
            join_verdict("头", [3])

    def test_non_string_head_raises_instead_of_printing_none(self):
        """weekly_digest._cap_phrase 存在的唯一理由就是别把字面量 None
        印进中文结论句。"""
        with self.assertRaises(TypeError):
            join_verdict(None, ["尾"])

    def test_empty_sequence_is_still_legal(self):
        """空序列是合法的「没有任何观测缺口」,不是畸形输入。"""
        self.assertEqual(join_verdict("头", []), "头")
        self.assertEqual(join_verdict("头", ()), "头")


if __name__ == "__main__":
    unittest.main()
