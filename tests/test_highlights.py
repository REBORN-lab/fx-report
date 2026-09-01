"""`scripts/highlights.py` 的性质测试。

这个模块的危险在于它**看起来**只是解析:一旦某处解析不到就顺手补一个默认值,
页面上就会出现一句报告没说过的话,而那句话不经过 `check_report.py` 的任何
一道闸门。所以这里守的全是「抽不到时不猜」:重名节作废而不是后者覆盖、
命中不唯一时返回 None、类型标签没写就是 None、标签缺席不补空串。
"""
import json
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts import highlights                                     # noqa: E402
from scripts.appendix import CURRENCIES                            # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class SectionsTest(unittest.TestCase):
    def test_duplicate_heading_drops_the_key_instead_of_overwriting(self):
        """覆盖是最坏的一种:页面拿着两节里的一节当"那一节",读者无从分辨。"""
        text = "## 甲\n一\n\n## 甲\n二\n\n## 乙\n三\n"
        secs = highlights.sections(text)
        self.assertNotIn("甲", secs)
        self.assertEqual(secs["乙"], "三")

    def test_find_section_returns_none_when_the_match_is_not_unique(self):
        secs = {"复盘材料": "a", "昨日观点复盘": "b"}
        self.assertIsNone(highlights.find_section(secs, "复盘"))
        self.assertEqual(highlights.find_section(secs, "昨日"), "b")


class TableTest(unittest.TestCase):
    def test_header_and_separator_rows_are_dropped(self):
        body = ("| 币种 | 条件方向 |\n| --- | :-- |\n"
                "| USD | 若 A 则 B |\n| EUR | 若 C 则 D |\n")
        self.assertEqual(highlights.table_rows(body),
                         [["USD", "若 A 则 B"], ["EUR", "若 C 则 D"]])

    def test_empty_body_is_empty_not_an_error(self):
        self.assertEqual(highlights.table_rows(None), [])


class LabelSplitTest(unittest.TestCase):
    def test_missing_label_is_absent_not_an_empty_string(self):
        """补空串会让"报告没写这一件"与"写了但内容为空"在页面上同形,
        而前者是违规(判断环三件不可缺)、后者不是。"""
        got = highlights._labelled("关键假设:甲;翻转指标:乙(T+3)",
                                   highlights.JUDGEMENT_LABELS)
        self.assertEqual(sorted(got), ["关键假设", "翻转指标"])
        self.assertEqual(got["关键假设"], "甲")
        self.assertTrue(got["翻转指标"].startswith("乙"))

    def test_bold_labels_are_recognised(self):
        body = "**驱动**:甲。\n**传导**:乙。\n"
        got = highlights._labelled(body, highlights.RING_LABELS)
        self.assertEqual(got["驱动"], "甲。")
        self.assertEqual(got["传导"], "乙。")


class ChangeKindIsReadNotInferredTest(unittest.TestCase):
    """四种类型是报告自己用行首粗体标出来的,这里只读不判。"""

    def _report(self, line):
        return "## 本期相对上期的变化\n- %s\n" % line

    def test_labelled_line_yields_its_kind(self):
        got = highlights.daily_facts(
            self._report("USD:**触发位变了**。方向没动。"))
        self.assertEqual(got["changes"]["USD"]["kind"], "触发位变了")

    def test_unlabelled_line_yields_none_not_a_guess(self):
        got = highlights.daily_facts(
            self._report("USD:方向没动,触发位随上沿上移。"))
        self.assertIsNone(got["changes"]["USD"]["kind"])
        self.assertIn("触发位", got["changes"]["USD"]["text"])

    def test_unknown_currency_row_is_skipped(self):
        got = highlights.daily_facts(self._report("XXX:**依据变了**。"))
        self.assertEqual(got["changes"], {})


class WeeklyFactsTest(unittest.TestCase):
    WEEKLY = ("## 本周主线\n\n"
              "### 主线一:甲乙丙(影响 USD、EUR、XXX)\n"
              "**宏观背景**:略。\n"
              "**翻转指标(T+5)**:下一次定盘四条不再同号。\n\n"
              "### 主线二:丁(影响 PHP)\n"
              "**宏观背景**:略。\n\n"
              "## 各币种一周落点\n\n"
              "| 币种 | 主线归属 | 周内价格落点 | 本周判断 | 失效条件 |\n"
              "| --- | --- | --- | --- | --- |\n"
              "| USD | 主线一 | 基准货币 | 若 A 则 B | 到 X 为止 |\n")

    def test_scope_keeps_only_known_currency_codes(self):
        t = highlights.weekly_facts(self.WEEKLY)["themes"][0]
        self.assertEqual(t["scope"], ["USD", "EUR"])
        self.assertEqual(t["title"], "甲乙丙")

    def test_theme_without_a_flip_line_reports_none(self):
        t = highlights.weekly_facts(self.WEEKLY)["themes"][1]
        self.assertIsNone(t["flip"])
        self.assertIsNone(t["horizon"])

    def test_landing_row_is_keyed_by_currency(self):
        land = highlights.weekly_facts(self.WEEKLY)["landing"]
        self.assertEqual(land["USD"]["theme"], "主线一")
        self.assertEqual(land["USD"]["call"], "若 A 则 B")


class DeltasUseComparisonOnlyTest(unittest.TestCase):
    def _snaps(self, pairs):
        out = []
        for date, ref, val, lo, hi in pairs:
            out.append((date, {
                "rates": {"EUR": {"primary": val, "ref_date": ref}},
                "derived": {"rates": {"EUR": {"range_5d_low": lo,
                                              "range_5d_high": hi}},
                            "real_rate": {}}}))
        return out

    def test_band_move_and_direction(self):
        d = highlights.deltas(self._snaps([
            ("2026-08-28", "2026-08-27", 0.855, 0.85, 0.856),
            ("2026-09-01", "2026-08-31", 0.862, 0.85, 0.862)]))["EUR"]
        self.assertEqual(d["direction"], "weak")
        self.assertEqual(d["band_move"], "up")
        self.assertTrue(d["at_high"])
        self.assertFalse(d["at_low"])
        self.assertEqual(d["prior_fixing"]["value"], 0.855)

    def test_single_fixing_has_no_direction(self):
        d = highlights.deltas(self._snaps([
            ("2026-09-01", "2026-08-31", 0.862, 0.85, 0.862)]))["EUR"]
        self.assertIsNone(d["direction"])
        self.assertIsNone(d["prior_fixing"])


class RealReportsTest(unittest.TestCase):
    """跑在仓库真实产物上:解析器最容易在真文本上碎掉,而夹具永远是干净的。"""

    @classmethod
    def setUpClass(cls):
        cls.facts = highlights.build(ROOT)

    def test_every_currency_has_an_overview_row_and_a_change_line(self):
        for c in CURRENCIES:
            self.assertIn(c, self.facts["overview"], c)
            self.assertIn(c, self.facts["changes"], c)

    def test_every_currency_section_yields_the_three_judgement_parts(self):
        for c in CURRENCIES:
            for part in highlights.JUDGEMENT_LABELS:
                self.assertIn(part, self.facts["rings"][c],
                              "%s 节抽不到「%s」" % (c, part))

    def test_weekly_themes_and_landing_are_populated(self):
        wk = self.facts["week"]
        self.assertTrue(wk["themes"])
        self.assertTrue(all(t["title"] for t in wk["themes"]))
        for c in CURRENCIES:
            self.assertIn(c, wk["landing"], c)


class CliTest(unittest.TestCase):
    def test_cli_emits_parsable_json(self):
        r = subprocess.run([sys.executable, "scripts/highlights.py"], cwd=ROOT,
                           capture_output=True, text=True,
                           env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["currencies"], list(CURRENCIES))


if __name__ == "__main__":
    unittest.main()
