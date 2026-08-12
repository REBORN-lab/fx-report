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

    def test_null_when_prev_ref_unknown_and_values_identical(self):
        """存量快照无 prev_ref_date 且两值 bit 级相等:无法区分"真持平"与"没定盘",
        不得给 0.0%(那会被读成方向结论)。"""
        entry = rate_entry(60.75, prev_primary=60.75, prev_ref_date=None)
        d, _ = derive.derive(payload({"PHP": entry}), [])
        self.assertIsNone(d["rates"]["PHP"]["chg_pct_1d"])

    def test_real_zero_change_kept_when_ref_dates_differ(self):
        """定盘日已知且不同、价格恰好相同 → 0.0% 是真实结论,必须保留。"""
        entry = rate_entry(60.75, ref_date="2026-08-11", prev_primary=60.75,
                           prev_ref_date="2026-08-10")
        d, _ = derive.derive(payload({"PHP": entry}), [])
        self.assertEqual(d["rates"]["PHP"]["chg_pct_1d"], 0.0)

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

    def test_legacy_snapshots_with_same_value_counted_once(self):
        """存量快照无 ref_date:同值的多份是同一次定盘被读了多遍,不得各算一天。"""
        hist = [{"rates": {"PHP": {"primary": 60.867}}} for _ in range(3)]
        d, _ = derive.derive(payload({"PHP": rate_entry(60.75)}), hist)
        r = d["rates"]["PHP"]
        self.assertEqual(r["range_5d_days"], 2)        # 60.75 与 60.867 两次定盘
        self.assertEqual(r["range_5d_low"], 60.75)
        self.assertEqual(r["range_5d_high"], 60.867)

    def test_duplicate_ref_dates_counted_once(self):
        """同一定盘日期的多份快照是同一次定盘,只能算一天。"""
        hist = [hist_snap(60.0, "2026-08-10"), hist_snap(60.0, "2026-08-10")]
        d, _ = derive.derive(payload({"PHP": rate_entry(60.75, ref_date="2026-08-11")}), hist)
        self.assertEqual(d["rates"]["PHP"]["range_5d_days"], 2)

    def test_distinct_known_ref_dates_with_equal_price_not_merged(self):
        """两次真实定盘恰好同价 → 必须算 2 次,不得按值误合并。"""
        hist = [hist_snap(60.75, "2026-08-10")]
        d, _ = derive.derive(payload({"PHP": rate_entry(60.75, ref_date="2026-08-11")}), hist)
        self.assertEqual(d["rates"]["PHP"]["range_5d_days"], 2)

    def test_unknown_ref_dates_with_distinct_prices_not_merged(self):
        """两份存量快照价格不同 → 是两次定盘,按值去重不得把它们并成一条。"""
        hist = [{"rates": {"PHP": {"primary": 60.80}}},
                {"rates": {"PHP": {"primary": 60.867}}}]
        d, _ = derive.derive(payload({"PHP": rate_entry(60.75, ref_date=None)}), hist)
        self.assertEqual(d["rates"]["PHP"]["range_5d_days"], 3)

    def test_history_span_wide_enough_for_shared_fixings(self):
        """窗口须宽于 RANGE_DAYS:周末让相邻快照共享定盘,窗口不够就永远凑不满。"""
        self.assertGreater(derive.HISTORY_SPAN, derive.RANGE_DAYS)
        hist = ([hist_snap(60.0, "2026-08-10")] * 3
                + [hist_snap(60.1 + i, "2026-08-%02d" % (9 - i)) for i in range(4)])
        d, _ = derive.derive(payload({"PHP": rate_entry(60.75)}), hist)
        self.assertEqual(d["rates"]["PHP"]["range_5d_days"], 5)

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

    def test_scans_past_history_entries_without_deviation(self):
        """最近一份没有 deviation 时须继续向后找,不能只看 history[0]。"""
        hist = [hist_snap(60.0, "2026-08-10", deviation_pct=None),
                hist_snap(60.1, "2026-08-09", deviation_pct=0.2)]
        d, _ = derive.derive(payload({"PHP": rate_entry(60.75)}), hist)
        self.assertEqual(d["rates"]["PHP"]["deviation_pct_prev"], 0.2)


class EventsCountTest(unittest.TestCase):
    def test_counts_and_delta(self):
        today = {"PHP": {"articles": [{"title": "a"}, {"title": "b"}]}}
        d, _ = derive.derive(payload({"PHP": rate_entry(60.75)}, events=today),
                             [hist_snap(60.0, "2026-08-10", article_count=5)])
        e = d["events"]["PHP"]
        self.assertEqual(e["count"], 2)
        self.assertEqual(e["count_prev"], 5)
        self.assertEqual(e["count_delta"], -3)

    def test_collection_failure_is_null_not_zero(self):
        """该币种事件采集失败(events 无该条目)→ count 为 null。
        写 0 就是把"没采到"报成"没发生",属编造。"""
        d, _ = derive.derive(payload({"PHP": rate_entry(60.75)}, events={}), [])
        e = d["events"]["PHP"]
        self.assertIsNone(e["count"])
        self.assertIsNone(e["count_prev"])
        self.assertIsNone(e["count_delta"])

    def test_genuinely_zero_articles_is_zero(self):
        """真的采到但 0 篇 → count 为 0,必须与采集失败区分开。"""
        d, _ = derive.derive(
            payload({"PHP": rate_entry(60.75)}, events={"PHP": {"articles": []}}), [])
        self.assertEqual(d["events"]["PHP"]["count"], 0)

    def test_failure_today_with_successful_prev(self):
        """今天 429、昨天采到:count 为 null 而 count_prev 保留数字,
        相减必须被守卫挡住(否则 None - 8 会被 except 吞成假 gap)。"""
        d, gaps = derive.derive(payload({"PHP": rate_entry(60.75)}, events={}),
                                [hist_snap(60.0, "2026-08-10", article_count=8)])
        e = d["events"]["PHP"]
        self.assertIsNone(e["count"])
        self.assertEqual(e["count_prev"], 8)
        self.assertIsNone(e["count_delta"])
        self.assertEqual(gaps, [])

    def test_base_currency_usd_covered(self):
        """USD 不在 rates 里(它是基准),但 GDELT 采它 —— derived.events 必须有 USD,
        否则 SKILL 让 LLM 写一个不存在的数,等于诱导它自己去数。"""
        d, _ = derive.derive(
            payload({"PHP": rate_entry(60.75)},
                    events={"USD": {"articles": [{"title": "a"}, {"title": "b"}]}}), [])
        self.assertEqual(d["events"]["USD"]["count"], 2)


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

    def test_missing_cpi_yields_null_value(self):
        """spec: 任一缺失时整项记为 null 而非省略——键必须在,SKILL 按 null 引用。"""
        d, _ = derive.derive(payload(macro=[MACRO_OK[0]]), [])
        rr = d["real_rate"]["PH"]
        self.assertIsNone(rr["value"])
        self.assertEqual(rr["policy_rate"], 5.25)      # 有的那一半照常暴露
        self.assertIsNone(rr["cpi"])

    def test_missing_period_yields_null_value(self):
        macro = [MACRO_OK[0], dict(MACRO_OK[1], period=None)]
        d, _ = derive.derive(payload(macro=macro), [])
        self.assertIsNone(d["real_rate"]["PH"]["value"])

    def test_bool_value_rejected(self):
        macro = [dict(MACRO_OK[0], value=True), MACRO_OK[1]]
        d, _ = derive.derive(payload(macro=macro), [])
        self.assertIsNone(d["real_rate"]["PH"]["value"])
        self.assertIsNone(d["real_rate"]["PH"]["policy_rate"])


class RobustnessTest(unittest.TestCase):
    def test_malformed_payload_shapes_yield_empty_not_raise(self):
        for bad in ({"rates": "oops"}, {"rates": {"PHP": "oops"}},
                    {"macro": "oops"}, {"events": 42}, {}):
            d, gaps = derive.derive(bad, [])
            self.assertEqual(d["rates"], {}, bad)      # 坏 rates → 无币种条目
            self.assertEqual(d["real_rate"], {}, bad)
            self.assertEqual(gaps, [], bad)            # 类型门拦下,不该记 gap

    def test_valid_rates_still_derived_alongside_bad_macro(self):
        d, _ = derive.derive({"rates": {"PHP": rate_entry(60.75, prev_primary=60.0)},
                              "macro": "oops", "events": None}, [])
        self.assertIn("PHP", d["rates"])
        self.assertIsNotNone(d["rates"]["PHP"]["chg_pct_1d"])

    def test_malformed_history_entries_skipped(self):
        d, _ = derive.derive(payload({"PHP": rate_entry(60.75)}), ["junk", None, 42])
        self.assertEqual(d["rates"]["PHP"]["range_5d_days"], 1)

    def test_schema_version_present(self):
        d, _ = derive.derive(payload(), [])
        self.assertEqual(d["schema_version"], 1)
class EventCappingTest(unittest.TestCase):
    """两天都顶到 GDELT 每日上限时 count_delta 恒为 0,"与前值持平"就成了上限
    造成的假象,而不是事件面平稳。报告必须能看见这一点。"""

    def _arts(self, n, raw=None):
        entry = {"articles": [{"title": "t%d" % i} for i in range(n)]}
        if raw is not None:
            entry["articles_raw_count"] = raw
        return {"PHP": entry}

    def test_capped_flag_set_on_both_sides(self):
        cap = derive.events_mod.MAX_RECORDS
        p = payload(events=self._arts(cap))
        hist = [{"events": self._arts(cap)}]
        d, _ = derive.derive(p, hist)
        e = d["events"]["PHP"]
        self.assertEqual(e["count_delta"], 0)       # 看起来"持平"
        self.assertTrue(e["count_capped"])          # 其实两边都被上限截断
        self.assertTrue(e["count_prev_capped"])

    def test_uncapped_not_flagged(self):
        d, _ = derive.derive(payload(events=self._arts(1)), [{"events": self._arts(1)}])
        e = d["events"]["PHP"]
        self.assertFalse(e["count_capped"])
        self.assertFalse(e["count_prev_capped"])

    def test_pre_dedupe_count_decides(self):
        """去重后 6 条但取满了上限 → 仍属触顶。"""
        cap = derive.events_mod.MAX_RECORDS
        d, _ = derive.derive(payload(events=self._arts(cap - 2, raw=cap)), [])
        self.assertTrue(d["events"]["PHP"]["count_capped"])

    def test_snapshot_cap_overrides_current_constant(self):
        p = payload(events=self._arts(2))
        p["meta"] = {"caps": {"gdelt_records": 2}}
        d, _ = derive.derive(p, [])
        self.assertTrue(d["events"]["PHP"]["count_capped"])

    def test_missing_currency_yields_none_not_false(self):
        d, _ = derive.derive(payload(events=self._arts(1)), [])
        self.assertIsNone(d["events"]["USD"]["count_capped"])
        self.assertIsNone(d["events"]["PHP"]["count_prev_capped"])   # 无 history
class CountCappedGuardTest(unittest.TestCase):
    """畸形 cap 会把市场事实变成假的"触顶"披露,或反过来漏掉真的截断。"""

    def _arts(self, n):
        return {"PHP": {"articles": [{"title": "t%d" % i} for i in range(n)]}}

    def _capped(self, cap, n=2):
        p = payload(events=self._arts(n))
        p["meta"] = {"caps": {"gdelt_records": cap}}
        d, _ = derive.derive(p, [])
        return d["events"]["PHP"]["count_capped"]

    def test_bool_cap_rejected(self):
        """True == 1,不排除 bool 就会把任何非空结果判成触顶。"""
        self.assertFalse(self._capped(True))         # 回退到 MAX_RECORDS

    def test_non_positive_cap_rejected(self):
        for bad in (0, -1):
            self.assertFalse(self._capped(bad), bad)

    def test_non_int_cap_rejected(self):
        for bad in ("2", 2.0, None, [2]):
            self.assertFalse(self._capped(bad), bad)

    def test_valid_snapshot_cap_honoured(self):
        self.assertTrue(self._capped(2))

    def test_articles_not_a_list_yields_none(self):
        p = payload(events={"PHP": {"articles": {"n": 1}}})
        d, _ = derive.derive(p, [])
        self.assertIsNone(d["events"]["PHP"]["count_capped"])

    def test_prev_capped_reads_history_not_today(self):
        """今天触顶、昨天没有:两个字段必须给出不同答案。"""
        cap = derive.events_mod.MAX_RECORDS
        d, _ = derive.derive(payload(events=self._arts(cap)),
                             [{"events": self._arts(1)}])
        e = d["events"]["PHP"]
        self.assertTrue(e["count_capped"])
        self.assertFalse(e["count_prev_capped"])

    def test_prev_capped_uses_history_own_cap(self):
        hist = {"events": self._arts(2), "meta": {"caps": {"gdelt_records": 2}}}
        d, _ = derive.derive(payload(events=self._arts(2)), [hist])
        e = d["events"]["PHP"]
        self.assertFalse(e["count_capped"])          # 今天按当前常量,2 < 8
        self.assertTrue(e["count_prev_capped"])      # 昨天上限就是 2

class SourceCappedTest(unittest.TestCase):
    """两条通道混用后,拿单一上限去比必然错位:GDELT 补位条目 raw=8(真顶到)
    去跟 gnews 的 99 比,8 >= 99 为假,截断漏报。权威判定由采集层给出。"""

    def _snap(self, entry):
        return {"date": "2026-08-11", "events": {"PHP": entry},
                "meta": {"caps": {"gdelt_records": 8, "gnews_records": 99}}}

    def test_authoritative_boolean_wins(self):
        snap = self._snap({"articles": [], "articles_raw_count": 8, "source_cap": 8,
                           "source_capped": True, "channel": "gdelt"})
        self.assertTrue(derive._count_capped(snap, "PHP"))

    def test_false_boolean_respected_even_when_raw_exceeds_gdelt_cap(self):
        snap = self._snap({"articles": [], "articles_raw_count": 50, "source_cap": 99,
                           "source_capped": False, "channel": "gnews"})
        self.assertFalse(derive._count_capped(snap, "PHP"))

    def test_legacy_snapshot_without_boolean_uses_old_path(self):
        snap = self._snap({"articles": [{"title": "t"}] * 8, "articles_raw_count": 8})
        self.assertTrue(derive._count_capped(snap, "PHP"))

    def test_non_bool_source_capped_ignored(self):
        snap = self._snap({"articles": [], "articles_raw_count": 8,
                           "source_capped": "yes"})
        self.assertTrue(derive._count_capped(snap, "PHP"))   # 退回旧路径


class ChannelChangeTest(unittest.TestCase):
    """I4:GDELT(上限 8、无白名单)与 gnews(上限 99、过白名单)的读数不可比。
    实测已落盘数据:08-11 PHP count=8(GDELT 顶到上限),08-12 PHP count=2(gnews
    81 条过白名单剩 2),count_delta 给出 -6 并被报告写成「事件面变化」。"""

    def _snap(self, date, n, channel):
        return {"date": date, "events": {"PHP": {
            "articles": [{"title": "t%d" % i} for i in range(n)],
            "articles_raw_count": n, "channel": channel,
            "source_cap": 99 if channel == "gnews" else 8, "source_capped": False}},
            "meta": {"caps": {"gdelt_records": 8, "gnews_records": 99}}}

    def test_delta_null_when_channel_changed(self):
        out = derive._events_derived(self._snap("2026-08-12", 2, "gnews"),
                                     [self._snap("2026-08-11", 8, "gdelt")], [])
        self.assertIsNone(out["PHP"]["count_delta"])
        self.assertEqual(out["PHP"]["channel_changed_from"], "gdelt")

    def test_delta_given_when_channel_same(self):
        out = derive._events_derived(self._snap("2026-08-12", 5, "gnews"),
                                     [self._snap("2026-08-11", 3, "gnews")], [])
        self.assertEqual(out["PHP"]["count_delta"], 2)
        self.assertIsNone(out["PHP"]["channel_changed_from"])


if __name__ == "__main__":
    unittest.main()
