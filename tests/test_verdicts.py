"""结论句拼装口(Design Doc §4:共享拼装,不共享判定)。"""
import unittest

from scripts.verdicts import join_verdict


class JoinVerdictTest(unittest.TestCase):
    """会漂移的是措辞与连接方式,不是判定 —— 所以抽出来的只有这一层。"""

    def test_no_caveats_returns_head_unchanged(self):
        """空括号是最明显的漂移入口:「区间内至少 3 条（）」会让读者无从判断
        是脚本漏填了,还是确实没有任何观测缺口 —— 而后者是最强的一条结论。"""
        self.assertEqual(join_verdict("区间内至少 3 条", []), "区间内至少 3 条")

    def test_empty_tuple_also_returns_head(self):
        self.assertEqual(join_verdict("当日未采到事件", ()), "当日未采到事件")

    def test_single_caveat_wrapped_in_fullwidth_parens(self):
        self.assertEqual(join_verdict("区间内至少 3 条", ["1/5 天未采到"]),
                         "区间内至少 3 条（1/5 天未采到）")

    def test_multiple_caveats_joined_with_ideographic_comma(self):
        self.assertEqual(
            join_verdict("区间内至少 3 条",
                         ["1/5 天未采到", "2 天顶到当日采集上限"]),
            "区间内至少 3 条（1/5 天未采到、2 天顶到当日采集上限）")

    def test_parens_are_fullwidth_not_ascii(self):
        """半角括号会让中文正文里的结论句与周报既有措辞逐字节不同,
        而整句包含检查是逐字节的。"""
        got = join_verdict("头", ["尾"])
        self.assertNotIn("(", got)
        self.assertNotIn(")", got)


if __name__ == "__main__":
    unittest.main()
