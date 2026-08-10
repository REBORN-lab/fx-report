import json
import unittest

from scripts.collect import rates
from tests.helpers import DEAD_URL, FixtureServer, make_test_cfg

FRANK = {"base": "USD", "date": "2026-08-10",
         "rates": {"PHP": 60.843, "THB": 35.2, "BRL": 5.43, "EUR": 0.921}}
EXCH = {"date": "2026-08-10",
        "usd": {"php": 60.834, "thb": 35.21, "brl": 5.431, "eur": 0.9211}}


def cfg_with(srv, frank_path="/frank", exch_paths=("/exch",)):
    return make_test_cfg(endpoints={
        "frankfurter_url": srv.base_url + frank_path + "?date={date}",
        "exchange_api_urls": [srv.base_url + p + "?date={date}" for p in exch_paths],
    })


class RatesTest(unittest.TestCase):
    def test_dual_source_ok(self):
        with FixtureServer({"/frank": (200, json.dumps(FRANK)),
                            "/exch": (200, json.dumps(EXCH))}) as srv:
            out, gaps = rates.collect(cfg_with(srv))
        self.assertEqual(gaps, [])
        self.assertEqual(sorted(out), ["BRL", "EUR", "PHP", "THB"])
        self.assertEqual(out["PHP"]["primary"], 60.843)
        self.assertEqual(out["PHP"]["secondary"], 60.834)
        self.assertFalse(out["PHP"]["suspect"])
        self.assertEqual(out["PHP"]["primary_source"], "frankfurter")

    def test_primary_fail_degrades_to_secondary(self):
        with FixtureServer({"/exch": (200, json.dumps(EXCH))}) as srv:
            cfg = cfg_with(srv)
            cfg["endpoints"]["frankfurter_url"] = DEAD_URL + "/frank?date={date}"
            out, gaps = rates.collect(cfg)
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0]["source"], "frankfurter")
        self.assertTrue(gaps[0]["reason"])
        self.assertEqual(out["PHP"]["primary"], 60.834)
        self.assertEqual(out["PHP"]["primary_source"], "exchange-api")

    def test_deviation_over_threshold_marks_suspect(self):
        bad = dict(EXCH, usd=dict(EXCH["usd"], php=62.0))
        with FixtureServer({"/frank": (200, json.dumps(FRANK)),
                            "/exch": (200, json.dumps(bad))}) as srv:
            out, gaps = rates.collect(cfg_with(srv))
        self.assertTrue(out["PHP"]["suspect"])
        self.assertEqual(out["PHP"]["primary"], 60.843)
        self.assertEqual(out["PHP"]["secondary"], 62.0)
        self.assertFalse(out["THB"]["suspect"])

    def test_both_sources_down(self):
        cfg = make_test_cfg(endpoints={
            "frankfurter_url": DEAD_URL + "/f?date={date}",
            "exchange_api_urls": [DEAD_URL + "/e?date={date}"],
        })
        out, gaps = rates.collect(cfg)
        self.assertEqual({g["source"] for g in gaps}, {"frankfurter", "exchange-api"})
        self.assertIsNone(out["PHP"]["primary"])

    def test_secondary_fallback_url_used(self):
        with FixtureServer({"/frank": (200, json.dumps(FRANK)),
                            "/exch2": (200, json.dumps(EXCH))}) as srv:
            cfg = cfg_with(srv, exch_paths=("/nope", "/exch2"))
            out, gaps = rates.collect(cfg)
        self.assertEqual(gaps, [])
        self.assertEqual(out["EUR"]["secondary"], 0.9211)

    def test_prev_primary_from_prev_snapshot(self):
        prev = {"rates": {"PHP": {"primary": 60.9}}}
        with FixtureServer({"/frank": (200, json.dumps(FRANK)),
                            "/exch": (200, json.dumps(EXCH))}) as srv:
            cfg = cfg_with(srv)
            cfg["prev_snapshot"] = prev
            out, _ = rates.collect(cfg)
        self.assertEqual(out["PHP"]["prev_primary"], 60.9)
        self.assertIsNone(out["THB"]["prev_primary"])

    def test_primary_zero_skips_deviation_and_records_gap(self):
        frank_zero = dict(FRANK, rates=dict(FRANK["rates"], PHP=0.0))
        with FixtureServer({"/frank": (200, json.dumps(frank_zero)),
                            "/exch": (200, json.dumps(EXCH))}) as srv:
            out, gaps = rates.collect(cfg_with(srv))
        self.assertEqual(out["PHP"]["primary"], 0.0)
        self.assertIsNone(out["PHP"]["deviation_pct"])
        self.assertFalse(out["PHP"]["suspect"])
        php_gaps = [g for g in gaps if g["scope"] == "PHP"]
        self.assertEqual(len(php_gaps), 1)
        self.assertEqual(php_gaps[0]["source"], "frankfurter")
        # 其余币种不受影响,仍有正常双源偏差
        self.assertIsNotNone(out["THB"]["deviation_pct"])
        self.assertIsNotNone(out["BRL"]["deviation_pct"])
        self.assertIsNotNone(out["EUR"]["deviation_pct"])

    def test_frankfurter_dirty_value_isolated_to_one_currency(self):
        frank_dirty = dict(FRANK, rates=dict(FRANK["rates"], THB=None))
        with FixtureServer({"/frank": (200, json.dumps(frank_dirty)),
                            "/exch": (200, json.dumps(EXCH))}) as srv:
            out, gaps = rates.collect(cfg_with(srv))
        # 其余币种双源校验不受脏值拖累
        self.assertIsNotNone(out["PHP"]["deviation_pct"])
        self.assertIsNotNone(out["BRL"]["deviation_pct"])
        self.assertIsNotNone(out["EUR"]["deviation_pct"])
        # THB 记 per-currency gap,不是整源 scope="all"
        thb_gaps = [g for g in gaps if g["scope"] == "THB"]
        self.assertEqual(len(thb_gaps), 1)
        self.assertEqual(thb_gaps[0]["source"], "frankfurter")
        self.assertFalse(any(g["scope"] == "all" and g["source"] == "frankfurter" for g in gaps))

    def test_both_sources_missing_currency_primary_source_is_none(self):
        frank_no_php = dict(FRANK, rates={k: v for k, v in FRANK["rates"].items() if k != "PHP"})
        exch_no_php = dict(EXCH, usd={k: v for k, v in EXCH["usd"].items() if k != "php"})
        with FixtureServer({"/frank": (200, json.dumps(frank_no_php)),
                            "/exch": (200, json.dumps(exch_no_php))}) as srv:
            out, gaps = rates.collect(cfg_with(srv))
        self.assertIsNone(out["PHP"]["primary"])
        self.assertIsNone(out["PHP"]["primary_source"])

    def test_both_200_missing_thb_records_gap_others_normal(self):
        frank_no_thb = dict(FRANK, rates={k: v for k, v in FRANK["rates"].items() if k != "THB"})
        exch_no_thb = dict(EXCH, usd={k: v for k, v in EXCH["usd"].items() if k != "thb"})
        with FixtureServer({"/frank": (200, json.dumps(frank_no_thb)),
                            "/exch": (200, json.dumps(exch_no_thb))}) as srv:
            out, gaps = rates.collect(cfg_with(srv))
        thb_gaps = [g for g in gaps if g["scope"] == "THB"]
        self.assertEqual(len(thb_gaps), 1)
        self.assertIsNone(out["THB"]["primary"])
        # 其余币种双源都在,正常计算偏差
        self.assertIsNotNone(out["PHP"]["deviation_pct"])
        self.assertIsNotNone(out["BRL"]["deviation_pct"])
        self.assertIsNotNone(out["EUR"]["deviation_pct"])

    def test_both_sources_down_gap_count_unchanged(self):
        # 双源整体失败(非缺字段)场景:不应逐币种重复记 gap,恰两条 gap。
        cfg = make_test_cfg(endpoints={
            "frankfurter_url": DEAD_URL + "/f?date={date}",
            "exchange_api_urls": [DEAD_URL + "/e?date={date}"],
        })
        out, gaps = rates.collect(cfg)
        self.assertEqual(len(gaps), 2)
        self.assertEqual({g["source"] for g in gaps}, {"frankfurter", "exchange-api"})

    def test_secondary_multiple_failed_urls_reason_includes_each_attempt(self):
        empty_body = json.dumps({"date": "2026-08-10", "usd": {}})
        with FixtureServer({"/frank": (200, json.dumps(FRANK)),
                            "/empty": (200, empty_body)}) as srv:
            cfg = cfg_with(srv, exch_paths=("/missing", "/empty"))
            out, gaps = rates.collect(cfg)
        exch_gaps = [g for g in gaps if g["source"] == "exchange-api"]
        self.assertEqual(len(exch_gaps), 1)
        reason = exch_gaps[0]["reason"]
        # 早期(/missing 404)与末次(/empty 空 usd)两次尝试的失败原因都应保留
        self.assertIn("404", reason)
        self.assertIn("empty usd map", reason)

    def test_deviation_exactly_at_threshold_not_suspect(self):
        # 锁定"> 阈值"语义(而非 >=):恰好等于阈值不算 suspect。
        frank_100 = dict(FRANK, rates=dict(FRANK["rates"], PHP=100.0))
        exch_1005 = dict(EXCH, usd=dict(EXCH["usd"], php=100.5))
        with FixtureServer({"/frank": (200, json.dumps(frank_100)),
                            "/exch": (200, json.dumps(exch_1005))}) as srv:
            out, gaps = rates.collect(cfg_with(srv))
        self.assertEqual(out["PHP"]["deviation_pct"], 0.5)
        self.assertFalse(out["PHP"]["suspect"])


if __name__ == "__main__":
    unittest.main()
