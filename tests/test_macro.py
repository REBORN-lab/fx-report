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



SERIES = SERIES_OK

BLS_OK = json.dumps({"status": "REQUEST_SUCCEEDED", "Results": {"series": [{
    "seriesID": "CUUR0000SA0",
    "data": [{"year": "2026", "period": "M06", "value": "333.952"},
             {"year": "2026", "period": "M05", "value": "335.123"},
             {"year": "2025", "period": "M06", "value": "318.777"},
             {"year": "2025", "period": "M05", "value": "319.000"}]}]}})
BLS_NO_BASE = json.dumps({"Results": {"series": [{"data": [
    {"year": "2026", "period": "M06", "value": "333.952"},
    {"year": "2026", "period": "M05", "value": "335.123"}]}]}})


class BlsUsCpiTest(unittest.TestCase):
    """美国 CPI 走 BLS 主源(delta spec: 美国 CPI 走 BLS 主源 / BLS 同月基期缺失)。"""

    def _cfg(self, srv, bls_path="/bls/v1/timeseries/data/CUUR0000SA0"):
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
        # 字面量期望而非把实现算式抄一遍;fixture 数值选得让四舍五入非空操作
        # (333.952/318.777 = 4.75978…%,round 到 3 位才是 4.76)
        self.assertEqual(row["value"], 4.76)
        self.assertEqual(row["series_id"], "BLS/CUUR0000SA0")

    def test_prev_month_yoy_filled_from_same_response(self):
        """前值留 None 会诱导 LLM 自找基准;同一份响应里就能算出来。"""
        with FixtureServer({"/bls": (200, BLS_OK),
                            "/db/": (200, json.dumps(SERIES))}) as srv:
            out, _ = macro.collect(self._cfg(srv))
        # 335.123/319.0 = 5.05423…% → 5.054
        self.assertEqual(out["indicators"][0]["prev"], 5.054)

    def test_prev_null_when_prior_month_base_missing(self):
        body = json.dumps({"Results": {"series": [{"data": [
            {"year": "2026", "period": "M06", "value": "333.952"},
            {"year": "2026", "period": "M05", "value": "335.123"},
            {"year": "2025", "period": "M06", "value": "318.777"}]}]}})
        with FixtureServer({"/bls": (200, body),
                            "/db/": (200, json.dumps(SERIES))}) as srv:
            out, gaps = macro.collect(self._cfg(srv))
        self.assertEqual(gaps, [])
        self.assertIsNone(out["indicators"][0]["prev"])   # 缺基期 → null,不近似

    def test_annual_average_row_m13_not_selected(self):
        """BLS 用 M13 表示年均值。选中它会算出年均值同比并以 period 2026-13 落盘。"""
        body = json.dumps({"Results": {"series": [{"data": [
            {"year": "2026", "period": "M13", "value": "340.000"},
            {"year": "2026", "period": "M12", "value": "339.000"},
            {"year": "2025", "period": "M13", "value": "330.000"},
            {"year": "2025", "period": "M12", "value": "325.000"}]}]}})
        with FixtureServer({"/bls": (200, body),
                            "/db/": (200, json.dumps(SERIES))}) as srv:
            out, _ = macro.collect(self._cfg(srv))
        self.assertEqual(out["indicators"][0]["period"], "2026-12")

    def test_latest_selection_prefers_newer_year(self):
        """年份必须优先于月份:2026-M01 比 2025-M12 新。"""
        body = json.dumps({"Results": {"series": [{"data": [
            {"year": "2026", "period": "M01", "value": "336.000"},
            {"year": "2025", "period": "M12", "value": "334.000"},
            {"year": "2025", "period": "M01", "value": "320.000"},
            {"year": "2024", "period": "M12", "value": "318.000"}]}]}})
        with FixtureServer({"/bls": (200, body),
                            "/db/": (200, json.dumps(SERIES))}) as srv:
            out, _ = macro.collect(self._cfg(srv))
        row = out["indicators"][0]
        self.assertEqual(row["period"], "2026-01")
        # 前值取上月 = 跨年到 2025-M12,基期 2024-M12:334/318 = 5.0314…%
        self.assertEqual(row["prev"], 5.031)

    def test_series_id_survives_query_string_with_slash(self):
        self.assertEqual(
            macro._bls_series_id("https://x/data/CUUR0000SA0?key=aa/bb"),
            "BLS/CUUR0000SA0")

    def test_zero_base_reason_is_specific(self):
        bad = json.dumps({"Results": {"series": [{"data": [
            {"year": "2026", "period": "M06", "value": "333.952"},
            {"year": "2025", "period": "M06", "value": "0"}]}]}})
        with FixtureServer({"/bls": (200, bad),
                            "/db/": (200, json.dumps(SERIES))}) as srv:
            _, gaps = macro.collect(self._cfg(srv))
        self.assertIn("zero", gaps[0]["reason"])

    def test_source_change_marked_and_not_new_release(self):
        """换源当日期号跳变,与前值不可比;不标出来报告会叙述成通胀升高。"""
        prev = {"macro": [{"economy": "US", "indicator": "CPI 同比",
                           "source": "dbnomics", "period": "2025-07",
                           "series_id": "IMF/CPI/M.US.PCPI_PC_CP_A_PT"}]}
        with FixtureServer({"/bls": (200, BLS_OK),
                            "/db/": (200, json.dumps(SERIES))}) as srv:
            cfg = self._cfg(srv)
            cfg["prev_snapshot"] = prev
            out, _ = macro.collect(cfg)
        row = out["indicators"][0]
        self.assertEqual(row["source_changed_from"], "dbnomics")
        self.assertFalse(row["is_new_release"])          # 期号跳变不是"昨日发布"

    def test_fallback_direction_also_marked(self):
        """bls → dbnomics 回落当日同样跳变,必须标记 —— 这个方向比换到 BLS
        更常发生(BLS 是单一端点,实测两次采集各有超时)。"""
        prev = {"macro": [{"economy": "US", "indicator": "CPI 同比",
                           "source": "bls", "period": "2026-06",
                           "series_id": "BLS/CUUR0000SA0"}]}
        with FixtureServer({"/db/": (200, json.dumps(SERIES))}) as srv:
            cfg = self._cfg(srv)
            cfg["endpoints"]["bls_timeseries_url"] = DEAD_URL + "/bls"
            cfg["prev_snapshot"] = prev
            out, _ = macro.collect(cfg)
        row = out["indicators"][0]
        self.assertEqual(row["source"], "dbnomics")
        self.assertEqual(row["source_changed_from"], "bls")
        self.assertFalse(row["is_new_release"])

    def test_legacy_prev_row_without_source_key_marks_change(self):
        """本变更之前的快照没有 source 字段 —— 缺省视为 dbnomics 才能识别出
        换源。这一行正是 2026-08-11 真实产出换源标记的原因,必须有测试守住。"""
        prev = {"macro": [{"economy": "US", "indicator": "CPI 同比",
                           "period": "2025-07",
                           "series_id": "IMF/CPI/M.US.PCPI_PC_CP_A_PT"}]}  # 无 source 键
        with FixtureServer({"/bls": (200, BLS_OK),
                            "/db/": (200, json.dumps(SERIES))}) as srv:
            cfg = self._cfg(srv)
            cfg["prev_snapshot"] = prev
            out, _ = macro.collect(cfg)
        self.assertEqual(out["indicators"][0]["source_changed_from"], "dbnomics")

    def test_no_source_change_marker_when_stable(self):
        prev = {"macro": [{"economy": "US", "indicator": "CPI 同比",
                           "source": "bls", "period": "2026-05",
                           "series_id": "BLS/CUUR0000SA0"}]}
        with FixtureServer({"/bls": (200, BLS_OK),
                            "/db/": (200, json.dumps(SERIES))}) as srv:
            cfg = self._cfg(srv)
            cfg["prev_snapshot"] = prev
            out, _ = macro.collect(cfg)
        row = out["indicators"][0]
        self.assertNotIn("source_changed_from", row)
        self.assertTrue(row["is_new_release"])           # 同源期号推进 → 真新发布

    def test_bls_not_called_when_us_cpi_untracked(self):
        """未跟踪美国 CPI 就不该打 BLS,也不该为未跟踪指标记 gap。"""
        with FixtureServer({"/db/": (200, json.dumps(SERIES))}) as srv:
            cfg = self._cfg(srv)
            cfg["indicators"] = [{"economy": "PH", "indicator": "CPI 同比",
                                  "series_id": "X"}]
            cfg["endpoints"]["bls_timeseries_url"] = DEAD_URL + "/bls"
            out, gaps = macro.collect(cfg)
        self.assertEqual(gaps, [])

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
CBPOL_CSV = (
    "FREQ,REF_AREA,TIME_PERIOD,OBS_VALUE\n"
    "D,BR,2026-06-16,14.5\n"
    "D,BR,2026-06-17,14.25\n"
    "D,BR,2026-06-18,NaN\n"
    "D,TH,2026-07-30,1\n"          # 实测形态:无小数点
)


class BisParseTest(unittest.TestCase):
    def test_groups_by_ref_area_sorted_by_period(self):
        got = macro._bis_parse(CBPOL_CSV)
        self.assertEqual(got["BR"], [("2026-06-16", 14.5), ("2026-06-17", 14.25)])
        self.assertEqual(got["TH"], [("2026-07-30", 1.0)])   # "1" 也要解析

    def test_nan_rows_dropped_not_zeroed(self):
        """NaN 是"当天没有读数",不是 0。"""
        self.assertEqual(len(macro._bis_parse(CBPOL_CSV)["BR"]), 2)

    def test_column_order_does_not_matter(self):
        """按列名取。按位置取的实现会在这里给出错值。"""
        reordered = ("OBS_VALUE,TIME_PERIOD,REF_AREA,FREQ\n"
                     "14.25,2026-06-17,BR,D\n")
        self.assertEqual(macro._bis_parse(reordered)["BR"], [("2026-06-17", 14.25)])

    def test_missing_required_column_raises(self):
        for csv_text in ("FREQ,REF_AREA,TIME_PERIOD\nD,BR,2026-06-17\n",
                         "FREQ,TIME_PERIOD,OBS_VALUE\nD,2026-06-17,14.25\n",
                         "FREQ,REF_AREA,OBS_VALUE\nD,BR,14.25\n"):
            with self.assertRaises(ValueError):
                macro._bis_parse(csv_text)

    def test_empty_and_header_only(self):
        self.assertEqual(macro._bis_parse("FREQ,REF_AREA,TIME_PERIOD,OBS_VALUE\n"), {})
        with self.assertRaises(ValueError):
            macro._bis_parse("")

    def test_non_numeric_obs_value_dropped(self):
        text = ("FREQ,REF_AREA,TIME_PERIOD,OBS_VALUE\n"
                "D,BR,2026-06-17,abc\n"
                "D,BR,2026-06-18,\n"
                "D,BR,2026-06-19,inf\n")
        self.assertEqual(macro._bis_parse(text), {})
class PrevSemanticsTest(unittest.TestCase):
    """日频政策利率绝大多数相邻观测相同,取"上一个观测"会恒等于当前值,
    对报告零信息(14.25 → 14.25)。"""

    RATES = [("2026-06-15", 14.5), ("2026-06-16", 14.5),
             ("2026-06-17", 14.25), ("2026-06-18", 14.25)]

    def test_distinct_prev_skips_equal_observations(self):
        got = macro._latest_and_prev_distinct(self.RATES)
        self.assertEqual(got, (14.25, "2026-06-18", 14.5, "2026-06-16"))

    def test_prev_period_is_last_day_of_old_level(self):
        """要说的是"上次变动前是 A,一直到 X 日",故取旧水平的**末日**。"""
        self.assertEqual(macro._latest_and_prev_distinct(self.RATES)[3], "2026-06-16")

    def test_no_change_in_window_yields_none_not_equal_value(self):
        """等值会被读成"持平",而事实是"窗口内没看到变动"。"""
        flat = [("2026-06-15", 14.25), ("2026-06-16", 14.25)]
        value, period, prev, prev_period = macro._latest_and_prev_distinct(flat)
        self.assertEqual((value, period), (14.25, "2026-06-16"))
        self.assertIsNone(prev)
        self.assertIsNone(prev_period)

    def test_single_observation(self):
        got = macro._latest_and_prev_distinct([("2026-06-15", 14.25)])
        self.assertEqual(got, (14.25, "2026-06-15", None, None))

    def test_empty_series(self):
        self.assertEqual(macro._latest_and_prev_distinct([]), (None, None, None, None))

    def test_monthly_prev_takes_previous_observation_even_if_equal(self):
        """CPI 同比是月频,相邻月份即便同值也是两次独立发布。"""
        cpi = [("2026-05", 3.1), ("2026-06", 3.1)]
        self.assertEqual(macro._latest_and_prev_observation(cpi),
                         (3.1, "2026-06", 3.1, "2026-05"))


if __name__ == "__main__":
    unittest.main()
