import json
import os
import tempfile
import unittest
from unittest import mock

from scripts.collect import __main__ as entry
from tests.helpers import DEAD_URL, FixtureServer, make_test_root

FRANK = {"rates": {"PHP": 60.843, "THB": 35.2, "BRL": 5.43, "EUR": 0.921}}
EXCH = {"usd": {"php": 60.834, "thb": 35.21, "brl": 5.431, "eur": 0.9211}}
SERIES = {"series": {"docs": [{"period": ["2026-06", "2026-07"], "value": [3.4, 3.1]}]}}
GDELT = {"articles": [{"url": "u", "title": "t", "domain": "d", "seendate": "s"}]}
IND = [{"economy": "PH", "indicator": "CPI 同比", "series_id": "X"}]


def endpoints(srv):
    return {
        "frankfurter_url": srv.base_url + "/frank?d={date}",
        "exchange_api_urls": [srv.base_url + "/exch?d={date}"],
        "dbnomics_series_url": srv.base_url + "/db/{series_id}",
        "gdelt_doc_url": srv.base_url + "/doc",
        "fred_release_dates_url": srv.base_url + "/fred",
    }


ROUTES = {"/frank": (200, json.dumps(FRANK)), "/exch": (200, json.dumps(EXCH)),
          "/db/": (200, json.dumps(SERIES)), "/doc": (200, json.dumps(GDELT))}


@mock.patch.dict(os.environ, {"FX_GDELT_DELAY_S": "0", "FX_GDELT_BACKOFF_S": "0"})
class SnapshotTest(unittest.TestCase):
    def test_all_sources_ok_snapshot_schema(self):
        with tempfile.TemporaryDirectory() as tmp, FixtureServer(dict(ROUTES)) as srv:
            make_test_root(tmp, endpoints(srv), indicators=IND, calendar={
                "valid_until": "2099-01-01",
                "events": [{"date": "2026-08-09", "bank": "BCB", "event": "COPOM 议息会议"}]})
            rc = entry.main(["--date", "2026-08-10", "--root", tmp])
            self.assertEqual(rc, 0)
            with open(os.path.join(tmp, "data", "2026-08-10.json"), encoding="utf-8") as f:
                snap = json.load(f)
        self.assertEqual(snap["date"], "2026-08-10")
        self.assertEqual(snap["schema_version"], 1)
        self.assertEqual(snap["rates"]["PHP"]["primary"], 60.843)
        self.assertEqual(snap["macro"][0]["value"], 3.1)
        self.assertEqual(len(snap["events"]), 5)
        self.assertEqual(snap["calendar_hits"][0]["bank"], "BCB")
        self.assertEqual(snap["gaps"], [])
        self.assertIn("collector_version", snap["meta"])
        self.assertNotIn("us_release_dates", snap)   # 零 key 不出现该键

    def test_one_source_down_others_intact(self):
        with tempfile.TemporaryDirectory() as tmp, FixtureServer(dict(ROUTES)) as srv:
            eps = endpoints(srv)
            eps["dbnomics_series_url"] = DEAD_URL + "/db/{series_id}"
            make_test_root(tmp, eps, indicators=IND)
            rc = entry.main(["--date", "2026-08-10", "--root", tmp])
            self.assertEqual(rc, 0)                  # 单源失败不中断
            with open(os.path.join(tmp, "data", "2026-08-10.json"), encoding="utf-8") as f:
                snap = json.load(f)
        self.assertEqual(snap["macro"], [])
        self.assertEqual([g["source"] for g in snap["gaps"]], ["dbnomics"])
        self.assertTrue(snap["gaps"][0]["reason"])
        self.assertEqual(snap["rates"]["EUR"]["primary"], 0.921)
        self.assertEqual(len(snap["events"]), 5)

    def test_prev_snapshot_feeds_prev_primary(self):
        with tempfile.TemporaryDirectory() as tmp, FixtureServer(dict(ROUTES)) as srv:
            make_test_root(tmp, endpoints(srv), indicators=IND)
            prev = {"date": "2026-08-09", "rates": {"PHP": {"primary": 60.9}}, "macro": []}
            with open(os.path.join(tmp, "data", "2026-08-09.json"), "w", encoding="utf-8") as f:
                json.dump(prev, f)
            entry.main(["--date", "2026-08-10", "--root", tmp])
            with open(os.path.join(tmp, "data", "2026-08-10.json"), encoding="utf-8") as f:
                snap = json.load(f)
        self.assertEqual(snap["rates"]["PHP"]["prev_primary"], 60.9)

    def test_corrupt_prev_snapshot_gap_not_crash(self):
        """前日快照损坏:不崩、prev_primary 退化为 None、记一条 source=snapshot gap。"""
        with tempfile.TemporaryDirectory() as tmp, FixtureServer(dict(ROUTES)) as srv:
            make_test_root(tmp, endpoints(srv), indicators=IND)
            with open(os.path.join(tmp, "data", "2026-08-09.json"), "w", encoding="utf-8") as f:
                f.write("{corrupt json")
            rc = entry.main(["--date", "2026-08-10", "--root", tmp])
            self.assertEqual(rc, 0)
            with open(os.path.join(tmp, "data", "2026-08-10.json"), encoding="utf-8") as f:
                snap = json.load(f)
        self.assertEqual([g["source"] for g in snap["gaps"]], ["snapshot"])
        self.assertTrue(snap["gaps"][0]["reason"])
        self.assertIsNone(snap["rates"]["PHP"]["prev_primary"])
        self.assertEqual(snap["rates"]["PHP"]["primary"], 60.843)

    def test_deeply_nested_prev_snapshot_gap_not_crash(self):
        """前日快照深嵌套触发 RecursionError:不崩、记 (snapshot, prev) gap、当日快照照常落盘。"""
        with tempfile.TemporaryDirectory() as tmp, FixtureServer(dict(ROUTES)) as srv:
            make_test_root(tmp, endpoints(srv), indicators=IND)
            with open(os.path.join(tmp, "data", "2026-08-09.json"), "w", encoding="utf-8") as f:
                f.write("[" * 100000)
            rc = entry.main(["--date", "2026-08-10", "--root", tmp])
            self.assertEqual(rc, 0)
            with open(os.path.join(tmp, "data", "2026-08-10.json"), encoding="utf-8") as f:
                snap = json.load(f)
        self.assertEqual([(g["source"], g["scope"]) for g in snap["gaps"]],
                         [("snapshot", "prev")])
        self.assertTrue(snap["gaps"][0]["reason"])
        self.assertIsNone(snap["rates"]["PHP"]["prev_primary"])
        self.assertEqual(snap["rates"]["PHP"]["primary"], 60.843)

    def test_prev_snapshot_top_level_non_dict_gap(self):
        """前日快照为合法 JSON 但顶层非 dict(list):记 gap、prev_primary 退化 None、当日照常。"""
        with tempfile.TemporaryDirectory() as tmp, FixtureServer(dict(ROUTES)) as srv:
            make_test_root(tmp, endpoints(srv), indicators=IND)
            with open(os.path.join(tmp, "data", "2026-08-09.json"), "w", encoding="utf-8") as f:
                json.dump([1, 2, 3], f)
            rc = entry.main(["--date", "2026-08-10", "--root", tmp])
            self.assertEqual(rc, 0)
            with open(os.path.join(tmp, "data", "2026-08-10.json"), encoding="utf-8") as f:
                snap = json.load(f)
        self.assertEqual([(g["source"], g["scope"]) for g in snap["gaps"]],
                         [("snapshot", "prev")])
        self.assertIn("list", snap["gaps"][0]["reason"])   # reason 注明实际形态
        self.assertIsNone(snap["rates"]["PHP"]["prev_primary"])
        self.assertEqual(snap["rates"]["PHP"]["primary"], 60.843)

    def test_module_internal_error_fallback_gap(self):
        """锁定模块级兜底:单模块 collect 抛意外异常转 gap、default 形态入快照、其余源完好。"""
        with tempfile.TemporaryDirectory() as tmp, FixtureServer(dict(ROUTES)) as srv:
            make_test_root(tmp, endpoints(srv), indicators=IND)
            with mock.patch.object(entry.macro, "collect",
                                   side_effect=RuntimeError("boom")):
                rc = entry.main(["--date", "2026-08-10", "--root", tmp])
            self.assertEqual(rc, 0)
            with open(os.path.join(tmp, "data", "2026-08-10.json"), encoding="utf-8") as f:
                snap = json.load(f)
        self.assertEqual(len(snap["gaps"]), 1)
        self.assertEqual(snap["gaps"][0]["source"], "macro")
        self.assertIn("internal error", snap["gaps"][0]["reason"])
        self.assertEqual(snap["macro"], [])                # default 形态入快照
        self.assertNotIn("us_release_dates", snap)         # default 无该键
        self.assertEqual(snap["rates"]["EUR"]["primary"], 0.921)
        self.assertEqual(len(snap["events"]), 5)


if __name__ == "__main__":
    unittest.main()
