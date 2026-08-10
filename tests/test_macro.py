import json
import unittest

from scripts.collect import macro
from tests.helpers import DEAD_URL, FixtureServer, make_test_cfg

SERIES_OK = {"series": {"docs": [{
    "period": ["2026-05", "2026-06", "2026-07"],
    "value": [3.7, 3.4, 3.1],
}]}}
IND = [{"economy": "PH", "indicator": "CPI 同比", "series_id": "IMF/CPI/M.PH.X"},
       {"economy": "TH", "indicator": "CPI 同比", "series_id": "IMF/CPI/M.TH.X"}]


def cfg_with(srv, **over):
    base = {"endpoints": {
        "dbnomics_series_url": srv.base_url + "/db/{series_id}",
        "fred_release_dates_url": srv.base_url + "/fred",
    }, "indicators": IND}
    base.update(over)
    return make_test_cfg(**base)


class MacroTest(unittest.TestCase):
    def test_latest_prev_and_new_release_flag(self):
        prev_snap = {"macro": [{"series_id": "IMF/CPI/M.PH.X", "period": "2026-06"}]}
        with FixtureServer({"/db/": (200, json.dumps(SERIES_OK))}) as srv:
            cfg = cfg_with(srv, prev_snapshot=prev_snap)
            payload, gaps = macro.collect(cfg)
        self.assertEqual(gaps, [])
        row = payload["indicators"][0]
        self.assertEqual((row["value"], row["prev"], row["period"]), (3.1, 3.4, "2026-07"))
        self.assertTrue(row["is_new_release"])          # period 变化 → 新发布
        self.assertFalse(payload["indicators"][1]["is_new_release"])  # 前快照无此 series

    def test_zero_key_default_path_no_fred_gap(self):
        with FixtureServer({"/db/": (200, json.dumps(SERIES_OK))}) as srv:
            payload, gaps = macro.collect(cfg_with(srv))  # fred_api_key=None
        self.assertEqual([g for g in gaps if g["source"] == "fred"], [])
        self.assertIsNone(payload["us_release_dates"])

    def test_fred_enhancement_failure_recorded(self):
        with FixtureServer({"/db/": (200, json.dumps(SERIES_OK)),
                            "/fred": (500, "err")}) as srv:
            cfg = cfg_with(srv, fred_api_key="k")
            payload, gaps = macro.collect(cfg)
        self.assertEqual([g["source"] for g in gaps], ["fred"])
        self.assertEqual(len(payload["indicators"]), 2)   # DBnomics 照常

    def test_fred_enhancement_success(self):
        fred = {"release_dates": [{"release_id": 10, "release_name": "CPI", "date": "2026-08-09"}]}
        with FixtureServer({"/db/": (200, json.dumps(SERIES_OK)),
                            "/fred": (200, json.dumps(fred))}) as srv:
            cfg = cfg_with(srv, fred_api_key="k")
            payload, gaps = macro.collect(cfg)
        self.assertEqual(gaps, [])
        self.assertEqual(payload["us_release_dates"], ["CPI"])

    def test_single_series_failure_does_not_stop_rest(self):
        def db(handler):
            return (500, "boom") if "M.PH.X" in handler.path else (200, json.dumps(SERIES_OK))

        with FixtureServer({"/db/": db}) as srv:
            payload, gaps = macro.collect(cfg_with(srv))
        self.assertEqual(len(payload["indicators"]), 1)
        self.assertEqual(gaps[0]["source"], "dbnomics")
        self.assertEqual(gaps[0]["scope"], "IMF/CPI/M.PH.X")

    def test_dbnomics_down_entirely(self):
        cfg = make_test_cfg(endpoints={
            "dbnomics_series_url": DEAD_URL + "/db/{series_id}",
            "fred_release_dates_url": DEAD_URL + "/fred",
        }, indicators=IND)
        payload, gaps = macro.collect(cfg)
        self.assertEqual(payload["indicators"], [])
        self.assertEqual(len(gaps), 2)

    def test_prev_snapshot_scalar_penetration_is_new_false(self):
        # 仓库约定回归(源自 rates.py 第 3 轮复审):`X = d.get(k) or {}`/`or []`
        # 对真值标量(如 5、{"macro": 1})不生效——真值让 or 短路保留原值,随后
        # 在 .get()/迭代处抛未捕获异常,collect() 整体崩溃。isinstance 门应一律
        # 防护:三种穿透形态(快照本身标量 / macro 字段标量 / macro 行标量)均
        # 不崩溃,is_new_release 全 False,不产生 gap。
        for snap in (5, {"macro": 1}, {"macro": ["x"]}):
            with self.subTest(prev_snapshot=snap):
                with FixtureServer({"/db/": (200, json.dumps(SERIES_OK))}) as srv:
                    payload, gaps = macro.collect(cfg_with(srv, prev_snapshot=snap))
                self.assertEqual(gaps, [])
                self.assertEqual([r["is_new_release"] for r in payload["indicators"]],
                                 [False, False])

    def test_dbnomics_malformed_body_records_gap_per_series(self):
        # DBnomics 返回 200 但响应体为 JSON null(非预期 series.docs 形态):
        # 逐 series 记 dbnomics gap,不崩溃、不中断其余采集。
        with FixtureServer({"/db/": (200, "null")}) as srv:
            payload, gaps = macro.collect(cfg_with(srv))
        self.assertEqual(payload["indicators"], [])
        self.assertEqual(len(gaps), 2)
        self.assertEqual({g["source"] for g in gaps}, {"dbnomics"})

    def test_fred_release_dates_scalar_recorded_as_gap(self):
        # FRED 返回 200 但 release_dates 是真值标量(穿透 `or []` 的形态):
        # 记 fred gap,us_release_dates 为 None,DBnomics 照常。
        with FixtureServer({"/db/": (200, json.dumps(SERIES_OK)),
                            "/fred": (200, json.dumps({"release_dates": 1}))}) as srv:
            cfg = cfg_with(srv, fred_api_key="k")
            payload, gaps = macro.collect(cfg)
        self.assertEqual([g["source"] for g in gaps], ["fred"])
        self.assertIsNone(payload["us_release_dates"])
        self.assertEqual(len(payload["indicators"]), 2)


if __name__ == "__main__":
    unittest.main()
