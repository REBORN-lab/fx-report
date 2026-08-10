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


if __name__ == "__main__":
    unittest.main()
