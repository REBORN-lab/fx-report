"""周度聚合器(delta spec: 聚合器正常产出 / 全周参考价未更新 / 缺天与坏快照)。"""
import unittest

from scripts import weekly_digest as wd


def snap(date, php=None, ref=None, articles=None, gaps=None):
    s = {"date": date, "rates": {}, "events": {}, "gaps": gaps or []}
    if php is not None:
        s["rates"]["PHP"] = {"primary": php, "ref_date": ref}
    if articles is not None:
        s["events"]["PHP"] = {"articles": [{"title": "t%d" % i} for i in range(articles)]}
    return s


WEEK_SNAPS = [
    snap("2026-08-07", 60.867, "2026-08-07", articles=8),
    snap("2026-08-08", 60.867, "2026-08-07", articles=8),   # 周末,同一次定盘
    snap("2026-08-10", 60.75, "2026-08-10", articles=6,
         gaps=[{"source": "gdelt", "scope": "BRL", "reason": "429"}]),
]


class RatesTest(unittest.TestCase):
    def test_week_change_uses_first_and_last_distinct_fixing(self):
        d, _ = wd.build(WEEK_SNAPS, [], "2026-W33")
        r = d["rates"]["PHP"]
        self.assertEqual(r["first_ref_date"], "2026-08-07")
        self.assertEqual(r["last_ref_date"], "2026-08-10")
        self.assertEqual(r["fixings"], 2)                 # 周末那份是同一次定盘
        self.assertEqual(r["chg_pct_week"], round((60.75 - 60.867) / 60.867 * 100, 3))

    def test_range_over_distinct_fixings(self):
        d, _ = wd.build(WEEK_SNAPS, [], "2026-W33")
        r = d["rates"]["PHP"]
        self.assertEqual(r["range_low"], 60.75)
        self.assertEqual(r["range_high"], 60.867)

    def test_single_fixing_all_week_yields_null_change(self):
        """全周没有新定盘 → 周涨跌为 null,不得算 0%。"""
        snaps = [snap("2026-08-08", 60.75, "2026-08-07"),
                 snap("2026-08-09", 60.75, "2026-08-07")]
        d, _ = wd.build(snaps, [], "2026-W33")
        r = d["rates"]["PHP"]
        self.assertIsNone(r["chg_pct_week"])
        self.assertEqual(r["fixings"], 1)

    def test_bool_and_nonfinite_rejected(self):
        for bad in (True, "60.7", float("nan"), None):
            snaps = [snap("2026-08-07", bad, "2026-08-07"),
                     snap("2026-08-10", 60.75, "2026-08-10")]
            d, _ = wd.build(snaps, [], "2026-W33")
            self.assertIsNone(d["rates"]["PHP"]["chg_pct_week"], bad)

    def test_missing_ref_dates_fall_back_to_value_dedupe(self):
        """存量快照无 ref_date:同值视为同一次定盘(与 derive 同法)。"""
        snaps = [snap("2026-08-07", 60.867), snap("2026-08-08", 60.867),
                 snap("2026-08-10", 60.75)]
        d, _ = wd.build(snaps, [], "2026-W33")
        self.assertEqual(d["rates"]["PHP"]["fixings"], 2)


class EventsAndGapsTest(unittest.TestCase):
    def test_event_totals_and_failure_days(self):
        snaps = WEEK_SNAPS + [snap("2026-08-11", 60.75, "2026-08-10")]   # 无 events 键
        d, _ = wd.build(snaps, [], "2026-W33")
        e = d["events"]["PHP"]
        self.assertEqual(e["total"], 22)              # 8+8+6
        self.assertEqual(e["days_with_data"], 3)
        self.assertEqual(e["days_failed"], 1)         # 最后一天没采到

    def test_gaps_counted_by_source(self):
        d, _ = wd.build(WEEK_SNAPS, [], "2026-W33")
        self.assertEqual(d["gaps_by_source"], {"gdelt": 1})

    def test_no_events_at_all_yields_null_total(self):
        """全周一条都没采到 → total 为 null,不是 0(0 会被读成"确实没有新闻")。"""
        d, _ = wd.build([snap("2026-08-10", 60.75, "2026-08-10")], [], "2026-W33")
        self.assertIsNone(d["events"]["PHP"]["total"])


class VerdictTest(unittest.TestCase):
    LOG = [
        {"date": "2026-08-07", "currency": "PHP", "review": {"verdict": "命中"}},
        {"date": "2026-08-08", "currency": "PHP", "review": {"verdict": "无法判定"}},
        {"date": "2026-08-09", "currency": "PHP", "review": {"verdict": None}},  # 当天无快照
        {"date": "2026-07-01", "currency": "PHP", "review": {"verdict": "命中"}},  # 窗口外
        "junk",
    ]

    def test_counts_within_window_only(self):
        """按覆盖区间过滤:08-09 当天无快照但有观点,仍须计入(精确匹配会漏掉它)。"""
        d, _ = wd.build(WEEK_SNAPS, self.LOG, "2026-W33")
        self.assertEqual(d["verdicts"], {"命中": 1, "未命中": 0,
                                         "无法判定": 1, "未判定": 1})

    def test_entries_outside_window_excluded(self):
        d, _ = wd.build(WEEK_SNAPS, self.LOG, "2026-W33")
        self.assertEqual(d["verdicts"]["命中"], 1)      # 07-01 那条在窗口外

    def test_empty_log(self):
        d, _ = wd.build(WEEK_SNAPS, [], "2026-W33")
        self.assertEqual(sum(d["verdicts"].values()), 0)


class RobustnessTest(unittest.TestCase):
    def test_bad_snapshots_skipped_and_reported(self):
        d, problems = wd.build(["junk", None, 42] + WEEK_SNAPS, [], "2026-W33")
        self.assertEqual(len(problems), 3)
        self.assertEqual(d["skipped"], 3)          # 可见而非静默
        self.assertIn("PHP", d["rates"])

    def test_no_snapshots_at_all(self):
        d, problems = wd.build([], [], "2026-W33")
        self.assertEqual(d["rates"], {})
        self.assertEqual(d["generated_from"], [])
        self.assertEqual(problems, [])

    def test_generated_from_lists_source_dates(self):
        d, _ = wd.build(WEEK_SNAPS, [], "2026-W33")
        self.assertEqual(d["generated_from"],
                         ["2026-08-07", "2026-08-08", "2026-08-10"])


if __name__ == "__main__":
    unittest.main()
