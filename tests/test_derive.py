"""派生指标(delta spec: 派生指标落盘 / 参考价未更新时不计涨跌 / 实际利率携带双期号)。"""
import unittest

from scripts.collect import derive


def rate_entry(primary, ref_date="2026-08-11", prev_primary=None,
               prev_ref_date="2026-08-10", deviation_pct=0.1):
    return {"primary": primary, "secondary": None, "primary_source": "frankfurter",
            "deviation_pct": deviation_pct, "suspect": False,
            "prev_primary": prev_primary, "ref_date": ref_date,
            "prev_ref_date": prev_ref_date}


def payload(rates=None, macro=None, events=None):
    return {"date": "2026-08-11", "rates": rates or {}, "macro": macro or [],
            "events": events or {}}


def hist_snap(primary, ref_date, deviation_pct=None, article_count=0):
    return {"rates": {"PHP": {"primary": primary, "ref_date": ref_date,
                              "deviation_pct": deviation_pct}},
            "events": {"PHP": {"articles": [{"title": "t%d" % i} for i in range(article_count)]}}}


class ChgPctTest(unittest.TestCase):
    def test_normal_change_rounded_to_three_places(self):
        d, gaps = derive.derive(payload({"PHP": rate_entry(60.75, prev_primary=60.867)}), [])
        self.assertEqual(gaps, [])
        self.assertEqual(d["rates"]["PHP"]["chg_pct_1d"], round((60.75 - 60.867) / 60.867 * 100, 3))

    def test_null_when_fixing_unchanged(self):
        """参考价未更新:两值必然相等,但那不是价格变动,不得算 0%。"""
        entry = rate_entry(60.75, ref_date="2026-08-07", prev_primary=60.75,
                           prev_ref_date="2026-08-07")
        d, _ = derive.derive(payload({"PHP": entry}), [])
        self.assertIsNone(d["rates"]["PHP"]["chg_pct_1d"])

    def test_null_when_prev_missing(self):
        d, _ = derive.derive(payload({"PHP": rate_entry(60.75, prev_primary=None)}), [])
        self.assertIsNone(d["rates"]["PHP"]["chg_pct_1d"])

    def test_null_when_prev_is_zero(self):
        d, _ = derive.derive(payload({"PHP": rate_entry(60.75, prev_primary=0)}), [])
        self.assertIsNone(d["rates"]["PHP"]["chg_pct_1d"])

    def test_bool_and_nonnumeric_treated_as_missing(self):
        for bad in (True, "60.7", None, float("nan"), float("inf")):
            d, _ = derive.derive(payload({"PHP": rate_entry(bad, prev_primary=60.0)}), [])
            self.assertIsNone(d["rates"]["PHP"]["chg_pct_1d"], bad)


class RangeTest(unittest.TestCase):
    def test_five_distinct_ref_dates(self):
        hist = [hist_snap(60.0 + i, "2026-08-%02d" % (10 - i)) for i in range(4)]
        d, _ = derive.derive(payload({"PHP": rate_entry(60.75)}), hist)
        r = d["rates"]["PHP"]
        self.assertEqual(r["range_5d_days"], 5)
        self.assertEqual(r["range_5d_low"], 60.0)
        self.assertEqual(r["range_5d_high"], 63.0)

    def test_history_shorter_than_five(self):
        d, _ = derive.derive(payload({"PHP": rate_entry(60.75)}),
                             [hist_snap(60.0, "2026-08-10")])
        r = d["rates"]["PHP"]
        self.assertEqual(r["range_5d_days"], 2)
        self.assertEqual(r["range_5d_low"], 60.0)
        self.assertEqual(r["range_5d_high"], 60.75)

    def test_duplicate_ref_dates_counted_once(self):
        """同一定盘日期的多份快照是同一次定盘,只能算一天。"""
        hist = [hist_snap(60.0, "2026-08-10"), hist_snap(60.0, "2026-08-10")]
        d, _ = derive.derive(payload({"PHP": rate_entry(60.75, ref_date="2026-08-11")}), hist)
        self.assertEqual(d["rates"]["PHP"]["range_5d_days"], 2)

    def test_no_history_uses_today_only(self):
        d, _ = derive.derive(payload({"PHP": rate_entry(60.75)}), [])
        r = d["rates"]["PHP"]
        self.assertEqual(r["range_5d_days"], 1)
        self.assertEqual(r["range_5d_low"], 60.75)
        self.assertEqual(r["range_5d_high"], 60.75)


class DeviationPrevTest(unittest.TestCase):
    def test_prev_deviation_from_history(self):
        d, _ = derive.derive(payload({"PHP": rate_entry(60.75, deviation_pct=0.4)}),
                             [hist_snap(60.0, "2026-08-10", deviation_pct=0.2)])
        self.assertEqual(d["rates"]["PHP"]["deviation_pct_prev"], 0.2)

    def test_null_without_history(self):
        d, _ = derive.derive(payload({"PHP": rate_entry(60.75)}), [])
        self.assertIsNone(d["rates"]["PHP"]["deviation_pct_prev"])


class EventsCountTest(unittest.TestCase):
    def test_counts_and_delta(self):
        today = {"PHP": {"articles": [{"title": "a"}, {"title": "b"}]}}
        d, _ = derive.derive(payload({"PHP": rate_entry(60.75)}, events=today),
                             [hist_snap(60.0, "2026-08-10", article_count=5)])
        e = d["events"]["PHP"]
        self.assertEqual(e["count"], 2)
        self.assertEqual(e["count_prev"], 5)
        self.assertEqual(e["count_delta"], -3)

    def test_missing_currency_counts_zero(self):
        d, _ = derive.derive(payload({"PHP": rate_entry(60.75)}, events={}), [])
        e = d["events"]["PHP"]
        self.assertEqual(e["count"], 0)
        self.assertIsNone(e["count_prev"])
        self.assertIsNone(e["count_delta"])


MACRO_OK = [
    {"economy": "PH", "indicator": "政策利率", "value": 5.25, "period": "2025-07-04"},
    {"economy": "PH", "indicator": "CPI 同比", "value": 1.27388535031847, "period": "2025-05"},
]


class RealRateTest(unittest.TestCase):
    def test_value_with_both_periods(self):
        d, _ = derive.derive(payload(macro=MACRO_OK), [])
        rr = d["real_rate"]["PH"]
        self.assertEqual(rr["value"], round(5.25 - 1.27388535031847, 3))
        self.assertEqual(rr["policy_rate"], 5.25)
        self.assertEqual(rr["policy_period"], "2025-07-04")
        self.assertEqual(rr["cpi"], 1.27388535031847)
        self.assertEqual(rr["cpi_period"], "2025-05")

    def test_missing_cpi_yields_no_entry(self):
        d, _ = derive.derive(payload(macro=[MACRO_OK[0]]), [])
        self.assertNotIn("PH", d["real_rate"])

    def test_missing_period_yields_no_entry(self):
        macro = [MACRO_OK[0], dict(MACRO_OK[1], period=None)]
        d, _ = derive.derive(payload(macro=macro), [])
        self.assertNotIn("PH", d["real_rate"])

    def test_bool_value_rejected(self):
        macro = [dict(MACRO_OK[0], value=True), MACRO_OK[1]]
        d, _ = derive.derive(payload(macro=macro), [])
        self.assertNotIn("PH", d["real_rate"])


class RobustnessTest(unittest.TestCase):
    def test_malformed_payload_shapes_do_not_raise(self):
        for bad in ({"rates": "oops"}, {"rates": {"PHP": "oops"}},
                    {"macro": "oops"}, {"events": 42}, {}):
            d, gaps = derive.derive(bad, [])
            self.assertIn("rates", d)
            self.assertIsInstance(gaps, list)

    def test_malformed_history_entries_skipped(self):
        d, _ = derive.derive(payload({"PHP": rate_entry(60.75)}), ["junk", None, 42])
        self.assertEqual(d["rates"]["PHP"]["range_5d_days"], 1)

    def test_schema_version_present(self):
        d, _ = derive.derive(payload(), [])
        self.assertEqual(d["schema_version"], 1)


if __name__ == "__main__":
    unittest.main()
