import json
import unittest

from scripts.collect import macro
from tests.helpers import DEAD_URL, FixtureServer, make_test_cfg

# ----------------------------------------------------------- IMF SDMX 直连 fixture
# 列名与取值均来自 2026-08-16 对 api.imf.org 的实测响应(SDMX-CSV 1.0,53 列)。
# 目标列 COUNTRY / TIME_PERIOD / OBS_VALUE **不在固定位置**,且前后都夹着诱饵列
# ——按位置索引的实现会在这里取到 DATAFLOW 或 SCALE。
IMF_BOP_CSV = (
    "DATAFLOW,COUNTRY,BOP_ACCOUNTING_ENTRY,INDICATOR,UNIT,FREQUENCY,"
    "TIME_PERIOD,OBS_VALUE,SCALE,PRECISION\n"
    "IMF.STA:BOP(21.0.0),USA,NETCD_T,CAB,USD,Q,2025-Q4,-214611000000,6,6\n"
    "IMF.STA:BOP(21.0.0),USA,NETCD_T,CAB,USD,Q,2026-Q1,-195171000000,6,6\n"
    "IMF.STA:BOP(21.0.0),G163,NETCD_T,CAB,USD,Q,2025-Q4,106565543901.5297,6,6\n"
    "IMF.STA:BOP(21.0.0),G163,NETCD_T,CAB,USD,Q,2026-Q1,66702717946.69043,6,6\n"
    "IMF.STA:BOP(21.0.0),PHL,NETCD_T,CAB,USD,Q,2025-Q4,-2470744910.51831,6,6\n"
    "IMF.STA:BOP(21.0.0),PHL,NETCD_T,CAB,USD,Q,2026-Q1,-5663843363.94035,6,6\n"
    "IMF.STA:BOP(21.0.0),THA,NETCD_T,CAB,USD,Q,2025-Q4,423222852.001783,6,6\n"
    "IMF.STA:BOP(21.0.0),THA,NETCD_T,CAB,USD,Q,2026-Q1,1416919127.11114,6,6\n"
    "IMF.STA:BOP(21.0.0),BRA,NETCD_T,CAB,USD,Q,2026-Q1,-20170551632.45,6,6\n"
    "IMF.STA:BOP(21.0.0),BRA,NETCD_T,CAB,USD,Q,2026-Q2,-7306704075.68,6,6\n"
)
CA = "经常账户"
CA_INDICATORS = [{"economy": e, "indicator": CA} for e in ("US", "EA", "PH", "TH", "BR")]


def imf_cfg(srv, **over):
    base = {"endpoints": {"imf_bop_url": srv.base_url + "/imf/bop"},
            "indicators": [dict(i) for i in CA_INDICATORS]}
    base["endpoints"].update(over.pop("endpoints", {}))
    base.update(over)
    return make_test_cfg(**base)


class FredEnhancementTest(unittest.TestCase):
    """FRED 是可选增强(需 key):零 key 不调用、不记缺漏;失败不牵连宏观指标。

    宏观指标这一侧用 IMF 直连当"正常工作的源"——原先用的 DBnomics 回落已随
    robots 合规整只删除。
    """

    def _cfg(self, srv, **over):
        return imf_cfg(srv, endpoints={"fred_release_dates_url": srv.base_url + "/fred"},
                       indicators=[{"economy": "TH", "indicator": CA}], **over)

    def test_zero_key_default_path_no_fred_gap(self):
        with FixtureServer({"/imf/bop": (200, IMF_BOP_CSV)}) as srv:
            payload, gaps = macro.collect(self._cfg(srv))     # fred_api_key=None
        self.assertEqual([g for g in gaps if g["source"] == "fred"], [])
        self.assertIsNone(payload["us_release_dates"])

    def test_fred_enhancement_failure_recorded(self):
        with FixtureServer({"/imf/bop": (200, IMF_BOP_CSV),
                            "/fred": (500, "err")}) as srv:
            payload, gaps = macro.collect(self._cfg(srv, fred_api_key="k"))
        self.assertEqual([g["source"] for g in gaps], ["fred"])
        self.assertEqual(len(payload["indicators"]), 1)   # 宏观指标照常


    def test_fred_enhancement_success(self):
        fred = {"release_dates": [{"release_id": 10, "release_name": "CPI",
                                   "date": "2026-08-09"}]}
        with FixtureServer({"/imf/bop": (200, IMF_BOP_CSV),
                            "/fred": (200, json.dumps(fred))}) as srv:
            payload, gaps = macro.collect(self._cfg(srv, fred_api_key="k"))
        self.assertEqual(gaps, [])
        self.assertEqual(payload["us_release_dates"], ["CPI"])

    def test_fred_entry_without_name_or_id_skipped(self):
        """release_name 与 release_id 双缺失的条目跳过,不得输出字面量 "None"。"""
        fred = {"release_dates": [
            {"release_id": 10, "release_name": "CPI", "date": "2026-08-09"},
            {"date": "2026-08-09"},
        ]}
        with FixtureServer({"/imf/bop": (200, IMF_BOP_CSV),
                            "/fred": (200, json.dumps(fred))}) as srv:
            payload, gaps = macro.collect(self._cfg(srv, fred_api_key="k"))
        self.assertEqual(gaps, [])
        self.assertEqual(payload["us_release_dates"], ["CPI"])

    def test_fred_release_dates_scalar_recorded_as_gap(self):
        """FRED 返回 200 但 release_dates 是真值标量(穿透 `or []` 的形态):
        记 fred gap,us_release_dates 为 None,宏观指标照常。"""
        with FixtureServer({"/imf/bop": (200, IMF_BOP_CSV),
                            "/fred": (200, json.dumps({"release_dates": 1}))}) as srv:
            payload, gaps = macro.collect(self._cfg(srv, fred_api_key="k"))
        self.assertEqual([g["source"] for g in gaps], ["fred"])
        self.assertIsNone(payload["us_release_dates"])
        self.assertEqual(len(payload["indicators"]), 1)


class PrevSnapshotRobustnessTest(unittest.TestCase):
    def test_prev_snapshot_scalar_penetration_is_new_false(self):
        # 仓库约定回归(源自 rates.py 第 3 轮复审):`X = d.get(k) or {}`/`or []`
        # 对真值标量(如 5、{"macro": 1})不生效——真值让 or 短路保留原值,随后
        # 在 .get()/迭代处抛未捕获异常,collect() 整体崩溃。isinstance 门应一律
        # 防护:三种穿透形态(快照本身标量 / macro 字段标量 / macro 行标量)均
        # 不崩溃,is_new_release 全 False,不产生 gap。
        for snap in (5, {"macro": 1}, {"macro": ["x"]}):
            with self.subTest(prev_snapshot=snap):
                with FixtureServer({"/imf/bop": (200, IMF_BOP_CSV)}) as srv:
                    payload, gaps = macro.collect(imf_cfg(srv, prev_snapshot=snap))
                self.assertEqual(gaps, [])
                self.assertEqual([r["is_new_release"] for r in payload["indicators"]],
                                 [False] * 5)

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
            indicators=[{"economy": "US", "indicator": "CPI 同比"}],
            endpoints={"bls_timeseries_url": srv.base_url + bls_path})

    def test_yoy_computed_from_index_by_script(self):
        with FixtureServer({"/bls": (200, BLS_OK)}) as srv:
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
        with FixtureServer({"/bls": (200, BLS_OK)}) as srv:
            out, _ = macro.collect(self._cfg(srv))
        # 335.123/319.0 = 5.05423…% → 5.054
        self.assertEqual(out["indicators"][0]["prev"], 5.054)

    def test_prev_null_when_prior_month_base_missing(self):
        body = json.dumps({"Results": {"series": [{"data": [
            {"year": "2026", "period": "M06", "value": "333.952"},
            {"year": "2026", "period": "M05", "value": "335.123"},
            {"year": "2025", "period": "M06", "value": "318.777"}]}]}})
        with FixtureServer({"/bls": (200, body)}) as srv:
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
        with FixtureServer({"/bls": (200, body)}) as srv:
            out, _ = macro.collect(self._cfg(srv))
        self.assertEqual(out["indicators"][0]["period"], "2026-12")

    def test_latest_selection_prefers_newer_year(self):
        """年份必须优先于月份:2026-M01 比 2025-M12 新。"""
        body = json.dumps({"Results": {"series": [{"data": [
            {"year": "2026", "period": "M01", "value": "336.000"},
            {"year": "2025", "period": "M12", "value": "334.000"},
            {"year": "2025", "period": "M01", "value": "320.000"},
            {"year": "2024", "period": "M12", "value": "318.000"}]}]}})
        with FixtureServer({"/bls": (200, body)}) as srv:
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
        with FixtureServer({"/bls": (200, bad)}) as srv:
            _, gaps = macro.collect(self._cfg(srv))
        self.assertIn("zero", gaps[0]["reason"])

    def test_source_change_marked_and_not_new_release(self):
        """换源当日期号跳变,与前值不可比;不标出来报告会叙述成通胀升高。"""
        prev = {"macro": [{"economy": "US", "indicator": "CPI 同比",
                           "source": "dbnomics", "period": "2025-07",
                           "series_id": "IMF/CPI/M.US.PCPI_PC_CP_A_PT"}]}
        with FixtureServer({"/bls": (200, BLS_OK)}) as srv:
            cfg = self._cfg(srv)
            cfg["prev_snapshot"] = prev
            out, _ = macro.collect(cfg)
        row = out["indicators"][0]
        self.assertEqual(row["source_changed_from"], "dbnomics")
        self.assertFalse(row["is_new_release"])          # 期号跳变不是"昨日发布"

    # BIS WS_LONG_CPI 里的美国行:BLS 挂掉时接手的就是它(优先级 BLS > BIS)
    BIS_CPI_US = ("FREQ,REF_AREA,UNIT_MEASURE,TIME_PERIOD,OBS_VALUE\n"
                  "M,US,771,2026-05,4.248674\n"
                  "M,US,771,2026-06,3.531425\n")

    def _cfg_with_bis(self, srv, routes_path="/bis/cpi"):
        cfg = self._cfg(srv)
        cfg["endpoints"]["bis_cpi_url"] = srv.base_url + routes_path
        return cfg

    def test_fallback_direction_also_marked(self):
        """bls → bis 回落当日同样跳变,必须标记 —— 这个方向比换到 BLS
        更常发生(BLS 是单一端点,实测两次采集各有超时)。"""
        prev = {"macro": [{"economy": "US", "indicator": "CPI 同比",
                           "source": "bls", "period": "2026-06",
                           "series_id": "BLS/CUUR0000SA0"}]}
        with FixtureServer({"/bis/cpi": (200, self.BIS_CPI_US)}) as srv:
            cfg = self._cfg_with_bis(srv)
            cfg["endpoints"]["bls_timeseries_url"] = DEAD_URL + "/bls"
            cfg["prev_snapshot"] = prev
            out, _ = macro.collect(cfg)
        row = out["indicators"][0]
        self.assertEqual(row["source"], "bis")
        self.assertEqual(row["source_changed_from"], "bls")
        self.assertFalse(row["is_new_release"])

    def test_legacy_prev_row_without_source_key_marks_change(self):
        """本变更之前的快照没有 source 字段 —— 缺省视为 dbnomics 才能识别出
        换源。这一行正是 2026-08-11 真实产出换源标记的原因,必须有测试守住。"""
        prev = {"macro": [{"economy": "US", "indicator": "CPI 同比",
                           "period": "2025-07",
                           "series_id": "IMF/CPI/M.US.PCPI_PC_CP_A_PT"}]}  # 无 source 键
        with FixtureServer({"/bls": (200, BLS_OK)}) as srv:
            cfg = self._cfg(srv)
            cfg["prev_snapshot"] = prev
            out, _ = macro.collect(cfg)
        self.assertEqual(out["indicators"][0]["source_changed_from"], "dbnomics")

    def test_no_source_change_marker_when_stable(self):
        prev = {"macro": [{"economy": "US", "indicator": "CPI 同比",
                           "source": "bls", "period": "2026-05",
                           "series_id": "BLS/CUUR0000SA0"}]}
        with FixtureServer({"/bls": (200, BLS_OK)}) as srv:
            cfg = self._cfg(srv)
            cfg["prev_snapshot"] = prev
            out, _ = macro.collect(cfg)
        row = out["indicators"][0]
        self.assertNotIn("source_changed_from", row)
        self.assertTrue(row["is_new_release"])           # 同源期号推进 → 真新发布

    def test_bls_not_called_when_us_cpi_untracked(self):
        """未跟踪美国 CPI 就不该打 BLS,也不该为未跟踪指标记 gap。

        被跟踪的 PH CPI 没有任何可用来源,它那一条缺漏是应该有的——钉住
        "没有 bls 来源的 gap",而不是"整轮零缺漏"(后者会随兜底不变量假红)。
        """
        cfg = make_test_cfg(
            date="2026-08-11",
            indicators=[{"economy": "PH", "indicator": "CPI 同比"}],
            endpoints={"bls_timeseries_url": DEAD_URL + "/bls"})
        _, gaps = macro.collect(cfg)
        self.assertNotIn("bls", [g["source"] for g in gaps])
        self.assertEqual([g["scope"] for g in gaps], ["PH/CPI 同比"])

    def test_missing_same_month_base_falls_back_with_gap(self):
        """不得用相邻月份近似:同月基期缺失 → 记 gap 并交给 BIS。"""
        with FixtureServer({"/bls": (200, BLS_NO_BASE),
                            "/bis/cpi": (200, self.BIS_CPI_US)}) as srv:
            out, gaps = macro.collect(self._cfg_with_bis(srv))
        row = out["indicators"][0]
        self.assertEqual([g["source"] for g in gaps], ["bls"])
        self.assertEqual(row["source"], "bis")
        self.assertEqual(row["value"], 3.531425)     # BIS 接手的值

    def test_request_failure_falls_back_with_gap(self):
        with FixtureServer({"/bis/cpi": (200, self.BIS_CPI_US)}) as srv:
            cfg = self._cfg_with_bis(srv)
            cfg["endpoints"]["bls_timeseries_url"] = DEAD_URL + "/bls"
            out, gaps = macro.collect(cfg)
        self.assertEqual([g["source"] for g in gaps], ["bls"])
        self.assertEqual(out["indicators"][0]["source"], "bis")

    def test_nonnumeric_and_bool_index_values_rejected(self):
        bad = json.dumps({"Results": {"series": [{"data": [
            {"year": "2026", "period": "M06", "value": "n/a"},
            {"year": "2025", "period": "M06", "value": "320.000"}]}]}})
        with FixtureServer({"/bls": (200, bad),
                            "/bis/cpi": (200, self.BIS_CPI_US)}) as srv:
            out, gaps = macro.collect(self._cfg_with_bis(srv))
        self.assertEqual([g["source"] for g in gaps], ["bls"])
        self.assertEqual(out["indicators"][0]["source"], "bis")

    def test_zero_base_rejected(self):
        bad = json.dumps({"Results": {"series": [{"data": [
            {"year": "2026", "period": "M06", "value": "333.952"},
            {"year": "2025", "period": "M06", "value": "0"}]}]}})
        with FixtureServer({"/bls": (200, bad)}) as srv:
            _, gaps = macro.collect(self._cfg(srv))
        self.assertIn("bls", [g["source"] for g in gaps])

    def test_bls_not_configured_uses_bis_silently(self):
        """未配置 BLS = 有意停用,不记缺漏,由 BIS 接手。"""
        with FixtureServer({"/bis/cpi": (200, self.BIS_CPI_US)}) as srv:
            cfg = self._cfg_with_bis(srv)
            del cfg["endpoints"]["bls_timeseries_url"]
            out, gaps = macro.collect(cfg)
        self.assertEqual(gaps, [])
        self.assertEqual(out["indicators"][0]["source"], "bis")


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
        body = ("FREQ,REF_AREA,UNIT_MEASURE,TIME_PERIOD,OBS_VALUE\n"
                "M,PH,771,2026-06,3.1\n")
        with FixtureServer({"/bis/cpi": (200, body)}) as srv:
            cfg = make_test_cfg(
                date="2026-08-11",
                indicators=[{"economy": "PH", "indicator": "CPI 同比"}],
                endpoints={"bis_cpi_url": srv.base_url + "/bis/cpi"})
            out, _ = macro.collect(cfg)
        self.assertEqual(out["indicators"][0]["lag_months"], 2)

    def test_quarterly_current_account_lag_is_null_not_guessed(self):
        """季频期号("2026-Q1")解析不出月份 → lag_months 为 null,不猜。
        字段仍然在,读者从 period 本身就能看出是哪个季度。"""
        with FixtureServer({"/imf/bop": (200, IMF_BOP_CSV)}) as srv:
            out, _ = macro.collect(imf_cfg(
                srv, date="2026-08-11", indicators=[{"economy": "TH", "indicator": CA}]))
        row = out["indicators"][0]
        self.assertIn("lag_months", row)
        self.assertIsNone(row["lag_months"])
CBPOL_CSV = (
    "FREQ,REF_AREA,TIME_PERIOD,OBS_VALUE\n"
    "D,BR,2026-06-16,14.5\n"
    "D,BR,2026-06-17,14.25\n"
    "D,BR,2026-06-18,NaN\n"
    "D,TH,2026-07-30,1\n"          # 实测形态:无小数点
)


class SdmxParseTest(unittest.TestCase):
    """一套解析伺候三个 dataflow;这些用例走 BIS 形态(area_col 默认 REF_AREA)。"""

    def test_groups_by_ref_area_sorted_by_period(self):
        got = macro._sdmx_parse(CBPOL_CSV)
        self.assertEqual(got["BR"], [("2026-06-16", 14.5), ("2026-06-17", 14.25)])
        self.assertEqual(got["TH"], [("2026-07-30", 1.0)])   # "1" 也要解析

    def test_nan_rows_dropped_not_zeroed(self):
        """NaN 是"当天没有读数",不是 0。"""
        self.assertEqual(len(macro._sdmx_parse(CBPOL_CSV)["BR"]), 2)

    def test_column_order_does_not_matter(self):
        """按列名取。按位置取的实现会在这里给出错值。"""
        reordered = ("OBS_VALUE,TIME_PERIOD,REF_AREA,FREQ\n"
                     "14.25,2026-06-17,BR,D\n")
        self.assertEqual(macro._sdmx_parse(reordered)["BR"], [("2026-06-17", 14.25)])

    def test_missing_required_column_raises(self):
        for csv_text in ("FREQ,REF_AREA,TIME_PERIOD\nD,BR,2026-06-17\n",
                         "FREQ,TIME_PERIOD,OBS_VALUE\nD,2026-06-17,14.25\n",
                         "FREQ,REF_AREA,OBS_VALUE\nD,BR,14.25\n"):
            with self.assertRaises(ValueError):
                macro._sdmx_parse(csv_text)

    def test_empty_and_header_only(self):
        self.assertEqual(macro._sdmx_parse("FREQ,REF_AREA,TIME_PERIOD,OBS_VALUE\n"), {})
        with self.assertRaises(ValueError):
            macro._sdmx_parse("")

    def test_obs_value_contract_pinned(self):
        """直接钉住 _obs_value 的契约。注意:字符串 NaN 判定与 math.isfinite
        互为冗余(变异测试实测),本用例钉的是**行为**,不是某一道门。"""
        for raw in ("NaN", "nan", "NAN", "inf", "-inf", "", "  ", None, "abc"):
            self.assertIsNone(macro._obs_value(raw), raw)
        self.assertEqual(macro._obs_value("1"), 1.0)        # 无小数点
        self.assertEqual(macro._obs_value(" 14.25 "), 14.25)

    def test_non_numeric_obs_value_dropped(self):
        text = ("FREQ,REF_AREA,TIME_PERIOD,OBS_VALUE\n"
                "D,BR,2026-06-17,abc\n"
                "D,BR,2026-06-18,\n"
                "D,BR,2026-06-19,inf\n")
        self.assertEqual(macro._sdmx_parse(text), {})
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
CPI_CSV = (
    "FREQ,REF_AREA,UNIT_MEASURE,TIME_PERIOD,OBS_VALUE\n"
    "M,XM,771,2026-05,3.177015\n"
    "M,XM,771,2026-06,2.748918\n"
    "M,BR,771,2026-05,4.7249068792\n"
    "M,BR,771,2026-06,4.6413275481\n"
)
BIS_ROUTES = {"/bis/cbpol": (200, CBPOL_CSV), "/bis/cpi": (200, CPI_CSV)}


def bis_cfg(srv, **over):
    base = {"endpoints": {
        "bis_cbpol_url": srv.base_url + "/bis/cbpol",
        "bis_cpi_url": srv.base_url + "/bis/cpi",
    }, "indicators": [
        {"economy": "EA", "indicator": "CPI 同比"},
        {"economy": "BR", "indicator": "CPI 同比"},
        {"economy": "BR", "indicator": "政策利率"},
        {"economy": "TH", "indicator": "政策利率"},
    ]}
    base["endpoints"].update(over.pop("endpoints", {}))
    base.update(over)
    return make_test_cfg(**base)


class SdmxTableTest(unittest.TestCase):
    def test_table_keyed_by_economy_and_indicator(self):
        with FixtureServer(dict(BIS_ROUTES)) as srv:
            gaps = []
            table = macro._sdmx_table(bis_cfg(srv), gaps)
        self.assertEqual(gaps, [])
        self.assertEqual(table[("BR", "政策利率")]["value"], 14.25)
        self.assertEqual(table[("BR", "政策利率")]["prev"], 14.5)
        self.assertEqual(table[("BR", "政策利率")]["prev_period"], "2026-06-16")
        self.assertEqual(table[("EA", "CPI 同比")]["value"], 2.748918)   # XM → EA
        self.assertEqual(table[("EA", "CPI 同比")]["source"], "bis")

    def test_euro_area_maps_from_xm(self):
        """映射互换会让欧元区取到别人的值。"""
        with FixtureServer(dict(BIS_ROUTES)) as srv:
            table = macro._sdmx_table(bis_cfg(srv), [])
        self.assertNotIn(("XM", "CPI 同比"), table)
        self.assertIn(("EA", "CPI 同比"), table)

    def test_unconfigured_endpoint_is_silent_skip(self):
        """未配置 = 有意停用(与 feeds.py 同约定),使删掉 URL 即整体回滚。"""
        with FixtureServer(dict(BIS_ROUTES)) as srv:
            cfg = bis_cfg(srv)
            cfg["endpoints"].pop("bis_cbpol_url")
            gaps = []
            table = macro._sdmx_table(cfg, gaps)
        self.assertEqual(gaps, [])
        self.assertNotIn(("BR", "政策利率"), table)
        self.assertIn(("BR", "CPI 同比"), table)

    def test_unreachable_endpoint_records_gap_per_affected_indicator(self):
        """整体失败也**逐指标**记:受影响的是这两条政策利率,不是"一个 dataflow"。
        只记到 dataflow 一级,报告层就不知道该对哪几条打折扣。"""
        with FixtureServer({"/bis/cpi": (200, CPI_CSV)}) as srv:
            cfg = bis_cfg(srv, endpoints={"bis_cbpol_url": DEAD_URL + "/x"})
            gaps = []
            table = macro._sdmx_table(cfg, gaps)
        self.assertEqual(sorted((g["source"], g["scope"]) for g in gaps),
                         [("bis", "BR/政策利率"), ("bis", "TH/政策利率")])
        self.assertNotIn(("BR", "政策利率"), table)
        self.assertIn(("BR", "CPI 同比"), table)     # 另一个 dataflow 不受影响

    def test_missing_column_records_gap(self):
        bad = {"/bis/cbpol": (200, "FREQ,REF_AREA,TIME_PERIOD\nD,BR,2026-06-17\n"),
               "/bis/cpi": (200, CPI_CSV)}
        with FixtureServer(bad) as srv:
            gaps = []
            table = macro._sdmx_table(bis_cfg(srv), gaps)
        self.assertEqual(sorted(g["scope"] for g in gaps),
                         ["BR/政策利率", "TH/政策利率"])
        self.assertTrue(all("缺列" in g["reason"] for g in gaps), gaps)
        self.assertNotIn(("BR", "政策利率"), table)

    def test_economy_absent_from_response_only_that_key_missing(self):
        """TH 不在 CPI 响应里 → 只有它缺席,BR/EA 照常。"""
        with FixtureServer(dict(BIS_ROUTES)) as srv:
            cfg = bis_cfg(srv)
            cfg["indicators"].append({"economy": "TH", "indicator": "CPI 同比"})
            table = macro._sdmx_table(cfg, [])
        self.assertNotIn(("TH", "CPI 同比"), table)
        self.assertIn(("BR", "CPI 同比"), table)

    def test_absent_economy_records_gap_scoped_to_that_indicator(self):
        """缺少某经济体时必须记入缺漏,且 scope 定位到**具体指标**。

        没有回落层了,"缺席"就是真的没有这一行。不记 gap 的话,它与"这一期
        确实没有发布"在快照里完全同形,下游结论句会把前者说成后者。
        """
        with FixtureServer(dict(BIS_ROUTES)) as srv:
            cfg = bis_cfg(srv, indicators=[{"economy": "TH", "indicator": "CPI 同比"}])
            gaps = []
            table = macro._sdmx_table(cfg, gaps)
        self.assertNotIn(("TH", "CPI 同比"), table)
        self.assertEqual([(g["source"], g["scope"]) for g in gaps],
                         [("bis", "TH/CPI 同比")])

    def test_untracked_economy_absent_records_no_gap(self):
        """只跟踪 BR/EA 时,US/PH 不在响应里不是缺漏——没人要它。与 BLS
        「没跟踪就别打这一枪」同约定;否则缺漏节会被无人关心的条目淹没。"""
        with FixtureServer(dict(BIS_ROUTES)) as srv:
            cfg = bis_cfg(srv, indicators=[{"economy": "BR", "indicator": "CPI 同比"}])
            gaps = []
            table = macro._sdmx_table(cfg, gaps)
        self.assertEqual(gaps, [])
        self.assertIn(("BR", "CPI 同比"), table)

    def test_untracked_dataflow_is_not_requested(self):
        """一个 BIS 指标都没跟踪就别发那次 GET(端点指向死地址仍应零 gap)。"""
        with FixtureServer({"/bis/cpi": (200, CPI_CSV)}) as srv:
            cfg = bis_cfg(srv, endpoints={"bis_cbpol_url": DEAD_URL + "/x"},
                          indicators=[{"economy": "BR", "indicator": "CPI 同比"}])
            gaps = []
            table = macro._sdmx_table(cfg, gaps)
        self.assertEqual(gaps, [])
        self.assertEqual(list(table), [("BR", "CPI 同比")])

    def test_all_nan_economy_absent(self):
        allnan = {"/bis/cbpol": (200, "FREQ,REF_AREA,TIME_PERIOD,OBS_VALUE\n"
                                      "D,BR,2026-06-17,NaN\nD,BR,2026-06-18,NaN\n"),
                  "/bis/cpi": (200, CPI_CSV)}
        with FixtureServer(allnan) as srv:
            gaps = []
            table = macro._sdmx_table(bis_cfg(srv), gaps)
        self.assertNotIn(("BR", "政策利率"), table)
        # 全 NaN 与"经济体缺席"同属"无可用观测",同样必须可见
        self.assertIn(("bis", "BR/政策利率"), [(g["source"], g["scope"]) for g in gaps])
class PriorityTest(unittest.TestCase):
    """来源优先级 BLS > BIS > DBnomics。"""

    def test_bis_direct_covers_every_tracked_indicator(self):
        with FixtureServer(dict(BIS_ROUTES)) as srv:
            payload, gaps = macro.collect(bis_cfg(srv))
        rows = {(r["economy"], r["indicator"]): r for r in payload["indicators"]}
        self.assertEqual(rows[("BR", "政策利率")]["source"], "bis")
        self.assertEqual(rows[("BR", "政策利率")]["value"], 14.25)
        self.assertEqual(rows[("EA", "CPI 同比")]["source"], "bis")
        self.assertEqual(rows[("TH", "政策利率")]["value"], 1.0)
        self.assertEqual(gaps, [])          # 四条全部命中 → 零缺漏

    def test_bls_wins_over_bis_for_us_cpi(self):
        """BIS 不得覆盖美国 CPI。"""
        cpi_with_us = CPI_CSV + "M,US,771,2026-05,4.248674\nM,US,771,2026-06,3.531425\n"
        routes = {"/bis/cbpol": (200, CBPOL_CSV), "/bis/cpi": (200, cpi_with_us),
                  "/bls": (200, BLS_OK)}
        with FixtureServer(routes) as srv:
            cfg = bis_cfg(srv, endpoints={"bls_timeseries_url": srv.base_url + "/bls"},
                          indicators=[{"economy": "US", "indicator": "CPI 同比"}])
            payload, _ = macro.collect(cfg)
        self.assertEqual(payload["indicators"][0]["source"], "bls")

    def test_no_source_left_means_no_row_and_a_gap_each(self):
        """BIS 两个端点都拿掉:没有回落层,四条指标全部没有行,且每条各记一条
        缺漏。以前这里是"全部回落 DBnomics",拿到的是滞后 8–17 个月的镜像陈值。"""
        with FixtureServer(dict(BIS_ROUTES)) as srv:
            cfg = bis_cfg(srv)
            cfg["endpoints"].pop("bis_cbpol_url")
            cfg["endpoints"].pop("bis_cpi_url")
            payload, gaps = macro.collect(cfg)
        self.assertEqual(payload["indicators"], [])
        self.assertEqual(sorted(g["scope"] for g in gaps),
                         sorted(["EA/CPI 同比", "BR/CPI 同比",
                                 "BR/政策利率", "TH/政策利率"]))

    def test_partial_failure_granularity(self):
        """一个 dataflow 挂掉不牵连另一个:CPI 照常出行,政策利率逐条记缺漏。"""
        with FixtureServer({"/bis/cpi": (200, CPI_CSV)}) as srv:
            cfg = bis_cfg(srv, endpoints={"bis_cbpol_url": DEAD_URL + "/x"})
            payload, gaps = macro.collect(cfg)
        rows = {(r["economy"], r["indicator"]): r for r in payload["indicators"]}
        self.assertEqual(rows[("BR", "CPI 同比")]["source"], "bis")
        self.assertNotIn(("BR", "政策利率"), rows)
        self.assertEqual(sorted(g["scope"] for g in gaps),
                         ["BR/政策利率", "TH/政策利率"])

    def test_lag_months_and_prev_period_present(self):
        with FixtureServer(dict(BIS_ROUTES)) as srv:
            payload, _ = macro.collect(bis_cfg(srv, date="2026-08-11"))
        row = [r for r in payload["indicators"]
               if (r["economy"], r["indicator"]) == ("BR", "政策利率")][0]
        self.assertEqual(row["lag_months"], 2)          # 2026-06 → 2026-08
        self.assertEqual(row["prev_period"], "2026-06-16")

    def test_source_change_marked_on_switch_day(self):
        prev_snap = {"macro": [{"economy": "BR", "indicator": "政策利率",
                                "series_id": "BIS/WS_CBPOL/D.BR", "period": "2025-07-07",
                                "source": "dbnomics"}]}
        with FixtureServer(dict(BIS_ROUTES)) as srv:
            payload, _ = macro.collect(bis_cfg(srv, prev_snapshot=prev_snap))
        row = [r for r in payload["indicators"]
               if (r["economy"], r["indicator"]) == ("BR", "政策利率")][0]
        self.assertEqual(row["source_changed_from"], "dbnomics")
        self.assertFalse(row["is_new_release"])


CBPOL_FLAT_CSV = (
    "FREQ,REF_AREA,TIME_PERIOD,OBS_VALUE\n"
    "D,BR,2026-06-17,14.25\n"
    "D,BR,2026-06-18,14.25\n"
    "D,BR,2026-06-19,14.25\n"          # 期号天天推进,利率纹丝不动
)
CPI_FLAT_CSV = (
    "FREQ,REF_AREA,UNIT_MEASURE,TIME_PERIOD,OBS_VALUE\n"
    "M,BR,771,2026-05,4.6\n"
    "M,BR,771,2026-06,4.6\n"
)
BR_RATE = {"economy": "BR", "indicator": "政策利率"}
BR_CPI = {"economy": "BR", "indicator": "CPI 同比"}


def prev_macro(**over):
    # series_id 必须是 BIS 分支真实落盘的那一个(BIS/<dataflow>/<area>);
    # 写成 config 里的 DBnomics 标识 D.BR 会让 _is_new* 查不到行而恒返回
    # False —— 用例会以"假绿"通过。
    row = {"economy": "BR", "indicator": "政策利率",
           "series_id": "BIS/WS_CBPOL/BR", "period": "2026-06-18",
           "value": 14.25, "source": "bis"}
    row.update(over)
    return {"macro": [row]}


class DailyReleaseSemanticsTest(unittest.TestCase):
    """日频序列的「新发布」= 水平变了,不是序列多了一行。

    BIS WS_CBPOL 每个日历日追加一行(实测 400 个观测跨 399 天,无跳日),
    只比 period 会让五个经济体在每个 BIS 刷新日全部 is_new_release 为 true,
    日报据此打出「数据发布:政策利率 最新 14.25 …」——把管道刷新说成央行
    动了利率。这是本仓库反复出现的同型缺陷:管道状态被当成市场事实。
    """

    def _rate_row(self, body, prev_snapshot):
        routes = {"/bis/cbpol": (200, body), "/bis/cpi": (200, CPI_CSV)}
        with FixtureServer(routes) as srv:
            payload, _ = macro.collect(bis_cfg(srv, indicators=[dict(BR_RATE)],
                                               prev_snapshot=prev_snapshot))
        return payload["indicators"][0]

    def test_new_day_same_level_is_not_a_release(self):
        row = self._rate_row(CBPOL_FLAT_CSV, prev_macro())
        self.assertEqual((row["period"], row["value"]), ("2026-06-19", 14.25))
        self.assertNotEqual(row["period"], "2026-06-18")   # 期号确实推进了
        self.assertFalse(row["is_new_release"])

    def test_level_change_is_a_release(self):
        row = self._rate_row(CBPOL_CSV, prev_macro(period="2026-06-16", value=14.5))
        self.assertEqual(row["value"], 14.25)
        self.assertTrue(row["is_new_release"])

    def test_first_landing_without_prior_row_is_not_a_release(self):
        row = self._rate_row(CBPOL_FLAT_CSV, {"macro": []})
        self.assertFalse(row["is_new_release"])

    def test_unusable_prior_value_is_not_a_release(self):
        """上一份快照的 value 不是可比数值(缺字段 / 字符串 / bool)→ 不下结论。
        漏列一次真实变动只是少说,凭不可比的输入打出发布行是编造。"""
        for bad in (None, "14.5", True, [14.5]):
            row = self._rate_row(CBPOL_CSV, prev_macro(period="2026-06-16", value=bad))
            self.assertFalse(row["is_new_release"], bad)

    def test_monthly_cpi_still_keyed_on_period_not_level(self):
        """月频 CPI 相邻月份同值也是两次独立发布,判据仍是期号——
        把日频的规则一刀切到月频会漏报真实的 CPI 发布。"""
        routes = {"/bis/cpi": (200, CPI_FLAT_CSV)}
        prev = {"macro": [{"economy": "BR", "indicator": "CPI 同比",
                           "series_id": "BIS/WS_LONG_CPI/BR", "period": "2026-05",
                           "value": 4.6, "source": "bis"}]}
        with FixtureServer(routes) as srv:
            cfg = bis_cfg(srv, indicators=[dict(BR_CPI)], prev_snapshot=prev)
            cfg["endpoints"].pop("bis_cbpol_url")
            payload, _ = macro.collect(cfg)
        row = payload["indicators"][0]
        self.assertEqual((row["period"], row["value"]), ("2026-06", 4.6))
        self.assertTrue(row["is_new_release"])
        # 前值口径同样按频率走:月频取上一个观测,相邻同值仍是有效前值。
        # 把日频的"上一个不同水平"一刀切到月频,这里会退化成 null。
        self.assertEqual((row["prev"], row["prev_period"]), (4.6, "2026-05"))


class BisRobustnessTest(unittest.TestCase):
    """外部网络数据可能任意畸形;采集层不得抛出,只能转 gap。"""

    def _collect(self, cbpol_body):
        routes = {"/bis/cbpol": (200, cbpol_body), "/bis/cpi": (200, CPI_CSV)}
        with FixtureServer(routes) as srv:
            return macro.collect(bis_cfg(srv))

    def test_empty_body(self):
        payload, gaps = self._collect("")
        self.assertTrue(any(g["source"] == "bis" for g in gaps))
        self.assertTrue(payload["indicators"])          # 其余指标照常产出

    def test_html_error_page(self):
        payload, gaps = self._collect("<html><body>503</body></html>")
        self.assertTrue(any(g["source"] == "bis" for g in gaps))

    def test_unknown_ref_area_ignored(self):
        body = ("FREQ,REF_AREA,TIME_PERIOD,OBS_VALUE\n"
                "D,ZZ,2026-06-17,9.9\nD,BR,2026-06-17,14.25\n")
        payload, _ = self._collect(body)
        rows = {(r["economy"], r["indicator"]): r for r in payload["indicators"]}
        self.assertEqual(rows[("BR", "政策利率")]["value"], 14.25)
        self.assertNotIn(("ZZ", "政策利率"), rows)

    def test_bom_before_required_column(self):
        """BOM 只污染**首列**列名。必需列排在首位时,不剥离 BOM 就会被判成缺列。
        (BOM 在 FREQ 前是等价变异——那不是必需列,测不出任何东西。)"""
        body = ("\ufeffREF_AREA,TIME_PERIOD,OBS_VALUE,FREQ\r\n"
                "BR,2026-06-17,14.25,D\r\n")
        payload, gaps = self._collect(body)
        # 钉的是"这份 CSV 没被判成缺列",不是"整轮零缺漏"——该 body 只有 BR,
        # 被跟踪的 TH 政策利率理应另记一条缺席 gap。按**原因**筛,不按 scope:
        # scope 现在一律是"经济体/指标",按 dataflow 名筛会恒为空 → 闸门失效。
        self.assertEqual([g for g in gaps if "缺列" in g["reason"]], [])
        rows = {(r["economy"], r["indicator"]): r for r in payload["indicators"]}
        self.assertEqual(rows[("BR", "政策利率")]["value"], 14.25)
        # 自证非空:TH 确实缺席并被记了下来,说明上面那条筛选面对的是真实缺漏列表
        self.assertIn("TH/政策利率", [g["scope"] for g in gaps])

    def test_short_row_yields_none_fields(self):
        """字段数少于表头时 DictReader 产出 None,类型门不设就会拿 None 当 str。"""
        body = ("FREQ,REF_AREA,TIME_PERIOD,OBS_VALUE\n"
                "D,BR,2026-06-17,14.25\n"
                "D\n")                       # 短行:REF_AREA/TIME_PERIOD 均为 None
        got = macro._sdmx_parse(body)
        self.assertEqual(got, {"BR": [("2026-06-17", 14.25)]})

    def test_blank_ref_area_dropped(self):
        body = ("FREQ,REF_AREA,TIME_PERIOD,OBS_VALUE\n"
                "D,,2026-06-17,14.25\n"
                "D,BR,2026-06-18,14.0\n")
        self.assertEqual(macro._sdmx_parse(body), {"BR": [("2026-06-18", 14.0)]})

    def test_collect_never_raises_on_any_body(self):
        for body in ("", "\x00\x01", "a,b\n1,2\n", "[]", "null"):
            payload, gaps = self._collect(body)
            self.assertIsInstance(payload["indicators"], list)


class ImfBopTest(unittest.TestCase):
    """经常账户改走 IMF 官方 SDMX 直连(api.db.nomics.world 整站 Disallow: /)。

    此前记录的「TH 经常账户整行缺失」并非 IMF 没有数据,而是 DBnomics 镜像的
    问题——直连下五个经济体全部有观测,该缺口一并关闭。
    """

    def _rows(self, body=IMF_BOP_CSV, **over):
        with FixtureServer({"/imf/bop": (200, body)}) as srv:
            payload, gaps = macro.collect(imf_cfg(srv, **over))
        return {(r["economy"], r["indicator"]): r for r in payload["indicators"]}, gaps

    def test_five_economies_all_have_current_account(self):
        rows, gaps = self._rows()
        self.assertEqual(gaps, [])
        self.assertEqual(sorted(e for e, _ in rows), ["BR", "EA", "PH", "TH", "US"])

    def test_values_and_periods_match_upstream(self):
        rows, _ = self._rows()
        self.assertEqual((rows[("US", CA)]["value"], rows[("US", CA)]["period"]),
                         (-195171000000.0, "2026-Q1"))
        self.assertEqual((rows[("PH", CA)]["value"], rows[("PH", CA)]["period"]),
                         (-5663843363.94035, "2026-Q1"))
        # 曾被记成"整行缺失"的那一条,直连下有值
        self.assertEqual((rows[("TH", CA)]["value"], rows[("TH", CA)]["period"]),
                         (1416919127.11114, "2026-Q1"))
        # BR 比其余四个再新一个季度,不得被"统一取某一季"的实现抹平
        self.assertEqual(rows[("BR", CA)]["period"], "2026-Q2")

    def test_euro_area_maps_from_g163(self):
        """IMF 的欧元区代码是 G163(codelist 名称 "Euro Area (EA)"),不是 U2/XM。
        映射写错会让欧元区取到别人的值或整条缺席。"""
        rows, _ = self._rows()
        self.assertNotIn(("G163", CA), rows)
        self.assertEqual(rows[("EA", CA)]["value"], 66702717946.69043)

    def test_source_and_series_id_point_at_imf(self):
        """series_id 是快照里唯一可回溯到源的字段,必须写 IMF 直连的真实出处。"""
        rows, _ = self._rows()
        self.assertEqual(rows[("TH", CA)]["source"], "imf")
        self.assertEqual(rows[("TH", CA)]["series_id"], "IMF/BOP/THA")

    def test_columns_taken_by_name_not_position(self):
        """53 列的响应里按位置取不会报错,只会静默取错列。"""
        reordered = ("OBS_VALUE,SCALE,TIME_PERIOD,DATAFLOW,COUNTRY\n"
                     "1416919127.11114,6,2026-Q1,IMF.STA:BOP(21.0.0),THA\n")
        rows, _ = self._rows(reordered, indicators=[{"economy": "TH", "indicator": CA}])
        self.assertEqual(rows[("TH", CA)]["value"], 1416919127.11114)

    def test_quarterly_prev_is_previous_observation(self):
        """季频与月频同口径:相邻季度即便同值也是两次独立发布,prev 取上一个观测。"""
        rows, _ = self._rows()
        self.assertEqual((rows[("US", CA)]["prev"], rows[("US", CA)]["prev_period"]),
                         (-214611000000.0, "2025-Q4"))

    def test_new_quarter_is_a_release_keyed_on_period(self):
        prev = {"macro": [{"economy": "TH", "indicator": CA, "source": "imf",
                           "series_id": "IMF/BOP/THA", "period": "2025-Q4",
                           "value": 423222852.001783}]}
        rows, _ = self._rows(prev_snapshot=prev)
        self.assertTrue(rows[("TH", CA)]["is_new_release"])

    def test_same_quarter_is_not_a_release(self):
        prev = {"macro": [{"economy": "TH", "indicator": CA, "source": "imf",
                           "series_id": "IMF/BOP/THA", "period": "2026-Q1",
                           "value": 1416919127.11114}]}
        rows, _ = self._rows(prev_snapshot=prev)
        self.assertFalse(rows[("TH", CA)]["is_new_release"])

    def test_switch_away_from_dbnomics_is_marked_as_source_change(self):
        """镜像与直连的**计价单位不同**(镜像百万美元、直连美元),换源当日两值
        不可比。不标出来,报告会把 -4247(百万)到 -5663843363(元)叙述成
        经常账户暴跌——正是 2026-08-11 CPI 换源已经发生过一次的那类事故。"""
        prev = {"macro": [{"economy": "PH", "indicator": CA, "source": "dbnomics",
                           "series_id": "IMF/BOP/Q.PH.BCA_BP6_USD",
                           "period": "2025-Q1", "value": -4247.6822065757}]}
        rows, _ = self._rows(prev_snapshot=prev)
        self.assertEqual(rows[("PH", CA)]["source_changed_from"], "dbnomics")
        self.assertFalse(rows[("PH", CA)]["is_new_release"])

    def test_accept_header_requests_sdmx_csv(self):
        """实测:api.imf.org 无视 `?format=csv`,只认 Accept 头;不发这个头拿到的
        是 SDMX-ML。头掉了必须当场被测出来,而不是等解析器抛"缺列"。"""
        seen = []

        def handler(req):
            seen.append(req.headers.get("Accept"))
            return 200, IMF_BOP_CSV
        with FixtureServer({"/imf/bop": handler}) as srv:
            macro.collect(imf_cfg(srv))
        self.assertEqual(len(seen), 1)
        self.assertIn("application/vnd.sdmx.data+csv", seen[0])

    def test_sdmx_ml_body_records_gap_not_empty_observation(self):
        """HTTP 200 但结构不认识(Accept 被中间层剥掉 → 拿到 XML):必须记缺漏。
        伪造成"干净的空观测"就与"确实没有数据"不可区分,下游结论句会据此
        写"确实 0 条"。"""
        xml = ("<?xml version='1.0' encoding='UTF-8'?><message:StructureSpecificData"
               " xmlns:message='urn:x'><message:DataSet/></message:StructureSpecificData>")
        rows, gaps = self._rows(xml)
        self.assertEqual(rows, {})
        self.assertTrue(gaps)
        self.assertTrue(any(g["source"] == "imf" for g in gaps), gaps)

    def test_missing_required_column_records_gap(self):
        for body in ("DATAFLOW,COUNTRY,TIME_PERIOD\nx,THA,2026-Q1\n",
                     "DATAFLOW,TIME_PERIOD,OBS_VALUE\nx,2026-Q1,1.0\n",
                     "DATAFLOW,COUNTRY,OBS_VALUE\nx,THA,1.0\n"):
            with self.subTest(body=body):
                rows, gaps = self._rows(body)
                self.assertEqual(rows, {})
                self.assertTrue(any("缺列" in g["reason"] for g in gaps), gaps)

    def test_unreachable_endpoint_records_gap_for_every_tracked_economy(self):
        cfg = make_test_cfg(endpoints={"imf_bop_url": DEAD_URL + "/imf"},
                            indicators=[dict(i) for i in CA_INDICATORS])
        payload, gaps = macro.collect(cfg)
        self.assertEqual(payload["indicators"], [])
        scopes = {g["scope"] for g in gaps}
        for economy in ("US", "EA", "PH", "TH", "BR"):
            self.assertIn("%s/%s" % (economy, CA), scopes)

    def test_absent_economy_records_gap_scoped_to_that_indicator(self):
        """某国不在响应里 → 只有它缺席,且缺漏定位到具体指标(不是只记到
        dataflow 一级),报告层才知道该对哪一条打折扣。"""
        without_th = "\n".join(
            l for l in IMF_BOP_CSV.strip().split("\n") if ",THA," not in l) + "\n"
        rows, gaps = self._rows(without_th)
        self.assertNotIn(("TH", CA), rows)
        self.assertIn(("PH", CA), rows)
        self.assertIn(("imf", "TH/%s" % CA), [(g["source"], g["scope"]) for g in gaps])

    def test_all_nan_economy_absent_with_gap(self):
        body = ("DATAFLOW,COUNTRY,TIME_PERIOD,OBS_VALUE\n"
                "x,THA,2025-Q4,NaN\nx,THA,2026-Q1,NaN\n")
        rows, gaps = self._rows(body, indicators=[{"economy": "TH", "indicator": CA}])
        self.assertEqual(rows, {})
        self.assertIn(("imf", "TH/%s" % CA), [(g["source"], g["scope"]) for g in gaps])

    def test_unconfigured_endpoint_is_silent_skip(self):
        """未配置 = 有意停用(与 BIS/feeds 同约定),删 URL 即回滚——但指标仍
        必须记缺漏,否则整块数据无声消失。"""
        cfg = make_test_cfg(endpoints={}, indicators=[{"economy": "TH", "indicator": CA}])
        payload, gaps = macro.collect(cfg)
        self.assertEqual(payload["indicators"], [])
        self.assertEqual([g["scope"] for g in gaps], ["TH/%s" % CA])

    def test_untracked_indicator_is_not_requested(self):
        """一个经常账户都没跟踪就别发那次 GET(端点指向死地址仍应零 gap)。"""
        cfg = make_test_cfg(endpoints={"imf_bop_url": DEAD_URL + "/imf"},
                            indicators=[{"economy": "BR", "indicator": "政策利率"}])
        _, gaps = macro.collect(cfg)
        self.assertEqual([g["scope"] for g in gaps], ["BR/政策利率"])
        self.assertNotIn("imf", [g["source"] for g in gaps])

    def test_collect_never_raises_on_any_body(self):
        for body in ("", "\x00\x01", "a,b\n1,2\n", "[]", "null", "<html>503</html>"):
            with self.subTest(body=body):
                payload, gaps = self._rows(body)
                self.assertIsInstance(payload, dict)


class NoSilentIndicatorDropTest(unittest.TestCase):
    """不变量:每个被跟踪的指标,要么产出一行,要么产出一条定位到它的缺漏。

    DBnomics 回落被删掉之后,"取不到就没有这一行"成了常态路径。没有这条
    不变量,一个指标整块消失与"这个季度确实没有发布"在快照里完全同形,
    下游结论句会把前者说成后者。
    """

    THREE = [{"economy": "US", "indicator": "CPI 同比"},
             {"economy": "BR", "indicator": "政策利率"},
             {"economy": "TH", "indicator": CA}]

    def _assert_all_covered(self, cfg):
        payload, gaps = macro.collect(cfg)
        self.assertEqual(payload["indicators"], [])
        scopes = {g["scope"] for g in gaps}
        for ind in cfg["indicators"]:
            self.assertIn("%s/%s" % (ind["economy"], ind["indicator"]), scopes)
        return gaps

    def test_every_tracked_indicator_yields_a_gap_when_sources_are_unreachable(self):
        """三条指标横跨三个来源,端点全部不可达:一条不许无声消失。

        这一条**走的是各来源自己记的那条缺漏**(取数失败),兜底不变量在此
        并不触发 —— 下一个用例才是兜底本身的靶子。
        """
        self._assert_all_covered(make_test_cfg(indicators=self.THREE, endpoints={
            "bls_timeseries_url": DEAD_URL + "/bls",
            "bis_cbpol_url": DEAD_URL + "/cbpol",
            "bis_cpi_url": DEAD_URL + "/cpi",
            "imf_bop_url": DEAD_URL + "/imf"}))

    def test_every_tracked_indicator_yields_a_gap_when_no_endpoint_configured(self):
        """端点一个都没配:**没有任何来源会去记缺漏**,只有 collect 的兜底能记。

        这是兜底不变量唯一的靶子——上一个用例里三条 scope 早被来源级缺漏
        占满,把兜底整段删掉它照样全绿(实测变异存活),因此必须有这一条。
        """
        gaps = self._assert_all_covered(
            make_test_cfg(indicators=self.THREE, endpoints={}))
        self.assertEqual({g["source"] for g in gaps}, {"macro"})

    def test_indicator_not_covered_by_any_source_still_records_a_gap(self):
        """config 里躺着一条谁也不取的指标(拼错、或新增了没接):同样要说出来,
        否则它只表现为"永远没有这一行",读者无从分辨是源挂了还是压根没接。"""
        cfg = make_test_cfg(
            indicators=[{"economy": "TH", "indicator": "货币供应量 M2"}],
            endpoints={"bis_cbpol_url": DEAD_URL, "bis_cpi_url": DEAD_URL,
                       "imf_bop_url": DEAD_URL})
        payload, gaps = macro.collect(cfg)
        self.assertEqual(payload["indicators"], [])
        self.assertEqual([(g["source"], g["scope"]) for g in gaps],
                         [("macro", "TH/货币供应量 M2")])

    def test_indicator_scoped_gap_is_not_duplicated(self):
        """已有定位到该指标的缺漏时不再补记一条——缺漏节被同一件事刷屏,
        读者就会开始跳过它。"""
        cfg = make_test_cfg(indicators=[{"economy": "TH", "indicator": CA}],
                            endpoints={"imf_bop_url": DEAD_URL + "/imf"})
        _, gaps = macro.collect(cfg)
        self.assertEqual([g["scope"] for g in gaps], ["TH/%s" % CA])
        self.assertEqual([g["source"] for g in gaps], ["imf"])   # 来源级那条,非兜底


class DbnomicsPathRemovedTest(unittest.TestCase):
    """api.db.nomics.world/robots.txt = `User-agent: *` / `Disallow: /`(实测
    2026-08-16,HTTP 200,26 字节)。整站禁爬的 API 域不得有任何代码路径指向。

    删的是路径本身,不是"默认关闭的开关"——本仓吃过 no-op 开关的亏:陈旧调用点
    会静默地什么都不做,而 grep 仍然看得见它,复核者以为还在用。
    """

    LIVE_DIRS = ("scripts", "config")

    def _live_files(self):
        import os
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        out = []
        for d in self.LIVE_DIRS:
            for base, _, names in os.walk(os.path.join(root, d)):
                if "__pycache__" in base:
                    continue
                for n in names:
                    if n.endswith((".py", ".json")):
                        out.append(os.path.join(base, n))
        return out

    def test_scan_actually_reads_the_live_code(self):
        """守卫非空自证:扫不到文件的"全绿"什么也没守住。"""
        files = self._live_files()
        self.assertGreater(len(files), 5, files)
        self.assertTrue(any(f.endswith("collect/macro.py") for f in files), files)
        self.assertTrue(any(f.endswith("config/endpoints.json") for f in files), files)

    def test_no_live_code_path_points_at_the_disallowed_host(self):
        offenders = []
        for path in self._live_files():
            with open(path, encoding="utf-8") as f:
                if "db.nomics.world" in f.read():
                    offenders.append(path)
        self.assertEqual(offenders, [])

    def test_no_dbnomics_endpoint_key_survives_in_config(self):
        import json as _json
        import os
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, "config", "endpoints.json"), encoding="utf-8") as f:
            endpoints = _json.load(f)
        self.assertNotIn("dbnomics_series_url", endpoints)
        self.assertIn("imf_bop_url", endpoints)

    def test_collector_has_no_dbnomics_fallback_symbol(self):
        """回落解析器整只删掉;留着"以防万一"就是留一个可被重新接上的调用点。"""
        self.assertFalse(hasattr(macro, "_last_two"))


class ConfiguredIndicatorsReachableTest(unittest.TestCase):
    """config/indicators.json 里的每一条都必须落在某个已配置来源上。

    配置里躺着一条谁也不取的指标,快照里只会表现为"这一条永远缺漏",
    读者无从分辨是源挂了还是压根没接。
    """

    def test_every_configured_indicator_has_a_source(self):
        import json as _json
        import os
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, "config", "indicators.json"), encoding="utf-8") as f:
            indicators = _json.load(f)
        self.assertEqual(len(indicators), 15)
        covered = {(e, ind) for ind, _k, _s, _d, _c, area, _f, _a in macro.SDMX_SOURCES
                   for e in area}
        covered.add(macro.US_CPI)          # 美国 CPI 主源是 BLS
        for row in indicators:
            self.assertIn((row["economy"], row["indicator"]), covered, row)


if __name__ == "__main__":
    unittest.main()
