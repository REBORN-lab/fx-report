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
        weekly_digest._verdict 重构前的输出逐字节相同。这条用例存在的意义
        是——括号宽度这类差异肉眼看不出来,只有逐字节比对能抓住。"""
        from scripts import weekly_digest as wd
        stats = {"days_collected": 2, "undated": 0, "capped_days": 0,
                 "daily_cap": None, "outside_window": 0, "in_window": 3,
                 "malformed": 0}
        self.assertEqual(join_verdict("区间内至少 3 条", ["3/5 天未采到"]),
                         wd._verdict(stats, 5, 0, "事件"))


if __name__ == "__main__":
    unittest.main()
