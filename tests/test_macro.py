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

    def test_period_value_length_mismatch_records_gap_not_indicator(self):
        # 复审第 1 轮必修 1:period 3 项 / value 1 项时 zip 静默截断,陈旧观测
        # 被当"最新值"零 gap 出报。应记 dbnomics gap 且该 series 不入
        # indicators(只锁行为,不锁具体错误消息文本);其余 series 照常。
        mismatch = {"series": {"docs": [{
            "period": ["2026-05", "2026-06", "2026-07"],
            "value": [3.7],
        }]}}

        def db(handler):
            return ((200, json.dumps(mismatch)) if "M.PH.X" in handler.path
                    else (200, json.dumps(SERIES_OK)))

        with FixtureServer({"/db/": db}) as srv:
            payload, gaps = macro.collect(cfg_with(srv))
        self.assertEqual([r["series_id"] for r in payload["indicators"]],
                         ["IMF/CPI/M.TH.X"])
        self.assertEqual([(g["source"], g["scope"]) for g in gaps],
                         [("dbnomics", "IMF/CPI/M.PH.X")])

    def test_trailing_na_falls_back_to_last_numeric_pair(self):
        # 复审第 1 轮必修 2(a):value 尾部 null/"NA" 跳过,回退取末位数值对。
        cases = {
            "尾部 null": ([3.7, 3.4, None], (3.4, 3.7, "2026-06")),
            "尾部 NA": ([3.7, 3.4, "NA"], (3.4, 3.7, "2026-06")),
        }
        for label, (values, expected) in cases.items():
            with self.subTest(label):
                doc = {"series": {"docs": [{
                    "period": ["2026-05", "2026-06", "2026-07"],
                    "value": values,
                }]}}
                with FixtureServer({"/db/": (200, json.dumps(doc))}) as srv:
                    payload, gaps = macro.collect(cfg_with(srv, indicators=[IND[0]]))
                self.assertEqual(gaps, [])
                row = payload["indicators"][0]
                self.assertEqual((row["value"], row["prev"], row["period"]), expected)
        # 复审第 1 轮必修 2(c) 顺带断言:单观测 series → prev=None。
        single = {"series": {"docs": [{"period": ["2026-07"], "value": [3.1]}]}}
        with FixtureServer({"/db/": (200, json.dumps(single))}) as srv:
            payload, gaps = macro.collect(cfg_with(srv, indicators=[IND[0]]))
        self.assertEqual(gaps, [])
        row = payload["indicators"][0]
        self.assertEqual((row["value"], row["prev"], row["period"]),
                         (3.1, None, "2026-07"))

    def test_all_null_values_recorded_as_gap(self):
        # 复审第 1 轮必修 2(b):value 全 null/"NA" → 记 dbnomics gap,
        # 该 series 不入 indicators。
        doc = {"series": {"docs": [{
            "period": ["2026-05", "2026-06"],
            "value": [None, "NA"],
        }]}}
        with FixtureServer({"/db/": (200, json.dumps(doc))}) as srv:
            payload, gaps = macro.collect(cfg_with(srv, indicators=[IND[0]]))
        self.assertEqual(payload["indicators"], [])
        self.assertEqual([(g["source"], g["scope"]) for g in gaps],
                         [("dbnomics", "IMF/CPI/M.PH.X")])

    def test_bool_value_not_treated_as_numeric(self):
        # 复审第 1 轮顺带修 3:JSON true 不得被 isinstance(int, float) 放行
        # 当数值入 payload;过滤 bool 后仅剩一个数值观测,prev=None。
        doc = {"series": {"docs": [{
            "period": ["2026-05", "2026-06"],
            "value": [3.7, True],
        }]}}
        with FixtureServer({"/db/": (200, json.dumps(doc))}) as srv:
            payload, gaps = macro.collect(cfg_with(srv, indicators=[IND[0]]))
        self.assertEqual(gaps, [])
        row = payload["indicators"][0]
        self.assertEqual((row["value"], row["prev"], row["period"]),
                         (3.7, None, "2026-05"))

    def test_fred_entry_without_name_or_id_skipped(self):
        # 复审第 1 轮顺带修 4:release_name 与 release_id 双缺失的条目跳过,
        # 不得输出字面量字符串 "None"。
        fred = {"release_dates": [
            {"release_id": 10, "release_name": "CPI", "date": "2026-08-09"},
            {"date": "2026-08-09"},
        ]}
        with FixtureServer({"/db/": (200, json.dumps(SERIES_OK)),
                            "/fred": (200, json.dumps(fred))}) as srv:
            cfg = cfg_with(srv, fred_api_key="k")
            payload, gaps = macro.collect(cfg)
        self.assertEqual(gaps, [])
        self.assertEqual(payload["us_release_dates"], ["CPI"])

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


SERIES = SERIES_OK

BLS_OK = json.dumps({"status": "REQUEST_SUCCEEDED", "Results": {"series": [{
    "seriesID": "CUUR0000SA0",
    "data": [{"year": "2026", "period": "M06", "value": "333.952"},
             {"year": "2026", "period": "M05", "value": "335.123"},
             {"year": "2025", "period": "M06", "value": "320.000"},
             {"year": "2025", "period": "M05", "value": "319.000"}]}]}})
BLS_NO_BASE = json.dumps({"Results": {"series": [{"data": [
    {"year": "2026", "period": "M06", "value": "333.952"},
    {"year": "2026", "period": "M05", "value": "335.123"}]}]}})


class BlsUsCpiTest(unittest.TestCase):
    """美国 CPI 走 BLS 主源(delta spec: 美国 CPI 走 BLS 主源 / BLS 同月基期缺失)。"""

    def _cfg(self, srv, bls_path="/bls"):
        return make_test_cfg(
            date="2026-08-11",
            indicators=[{"economy": "US", "indicator": "CPI 同比",
                         "series_id": "IMF/CPI/M.US.PCPI_PC_CP_A_PT"}],
            endpoints={"dbnomics_series_url": srv.base_url + "/db/{series_id}",
                       "bls_timeseries_url": srv.base_url + bls_path})

    def test_yoy_computed_from_index_by_script(self):
        with FixtureServer({"/bls": (200, BLS_OK),
                            "/db/": (200, json.dumps(SERIES))}) as srv:
            out, gaps = macro.collect(self._cfg(srv))
        row = out["indicators"][0]
        self.assertEqual(gaps, [])
        self.assertEqual(row["source"], "bls")
        self.assertEqual(row["period"], "2026-06")
        self.assertEqual(row["value"], round((333.952 / 320.000 - 1) * 100, 3))

    def test_missing_same_month_base_falls_back_with_gap(self):
        """不得用相邻月份近似:同月基期缺失 → 记 gap 并回落 DBnomics。"""
        with FixtureServer({"/bls": (200, BLS_NO_BASE),
                            "/db/": (200, json.dumps(SERIES))}) as srv:
            out, gaps = macro.collect(self._cfg(srv))
        row = out["indicators"][0]
        self.assertEqual([g["source"] for g in gaps], ["bls"])
        self.assertEqual(row["source"], "dbnomics")
        self.assertEqual(row["value"], 3.1)          # DBnomics 回落值

    def test_request_failure_falls_back_with_gap(self):
        with FixtureServer({"/db/": (200, json.dumps(SERIES))}) as srv:
            cfg = self._cfg(srv)
            cfg["endpoints"]["bls_timeseries_url"] = DEAD_URL + "/bls"
            out, gaps = macro.collect(cfg)
        self.assertEqual([g["source"] for g in gaps], ["bls"])
        self.assertEqual(out["indicators"][0]["source"], "dbnomics")

    def test_nonnumeric_and_bool_index_values_rejected(self):
        bad = json.dumps({"Results": {"series": [{"data": [
            {"year": "2026", "period": "M06", "value": "n/a"},
            {"year": "2025", "period": "M06", "value": "320.000"}]}]}})
        with FixtureServer({"/bls": (200, bad),
                            "/db/": (200, json.dumps(SERIES))}) as srv:
            out, gaps = macro.collect(self._cfg(srv))
        self.assertEqual([g["source"] for g in gaps], ["bls"])
        self.assertEqual(out["indicators"][0]["source"], "dbnomics")

    def test_zero_base_rejected(self):
        bad = json.dumps({"Results": {"series": [{"data": [
            {"year": "2026", "period": "M06", "value": "333.952"},
            {"year": "2025", "period": "M06", "value": "0"}]}]}})
        with FixtureServer({"/bls": (200, bad),
                            "/db/": (200, json.dumps(SERIES))}) as srv:
            _, gaps = macro.collect(self._cfg(srv))
        self.assertEqual([g["source"] for g in gaps], ["bls"])

    def test_bls_not_configured_uses_dbnomics_silently(self):
        with FixtureServer({"/db/": (200, json.dumps(SERIES))}) as srv:
            cfg = self._cfg(srv)
            del cfg["endpoints"]["bls_timeseries_url"]
            out, gaps = macro.collect(cfg)
        self.assertEqual(gaps, [])
        self.assertEqual(out["indicators"][0]["source"], "dbnomics")


class LagMonthsTest(unittest.TestCase):
    """滞后月数披露(delta spec: 滞后月数披露 / 期号不可解析)。"""

    def test_month_period(self):
        self.assertEqual(macro.lag_months("2025-07", "2026-08-11"), 13)

    def test_day_period(self):
        self.assertEqual(macro.lag_months("2025-07-08", "2026-08-11"), 13)

    def test_same_month_is_zero(self):
        self.assertEqual(macro.lag_months("2026-08", "2026-08-11"), 0)

    def test_quarter_and_garbage_periods_are_null(self):
        for bad in ("2025-Q1", "", None, 202507, "not-a-date", "2025-13"):
            self.assertIsNone(macro.lag_months(bad, "2026-08-11"), bad)

    def test_attached_to_every_indicator(self):
        with FixtureServer({"/db/": (200, json.dumps(SERIES))}) as srv:
            cfg = make_test_cfg(
                date="2026-08-11",
                indicators=[{"economy": "PH", "indicator": "CPI 同比", "series_id": "X"}],
                endpoints={"dbnomics_series_url": srv.base_url + "/db/{series_id}"})
            out, _ = macro.collect(cfg)
        self.assertIn("lag_months", out["indicators"][0])
