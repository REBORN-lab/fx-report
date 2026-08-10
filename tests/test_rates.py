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

    def test_frankfurter_rates_null_degrades_to_secondary(self):
        # fd19729 回归(质量复审 Critical):{"rates": null} 时 key 存在但值为
        # None,doc.get("rates", {}) 的默认值不生效(只在 key 缺失时生效),原实现
        # 会在 `c not in got` 处对 None 做成员判断抛未捕获 TypeError,collect()
        # 整体崩溃。null 应视同空响应,四币种应降级到 exchange-api。
        frank_null = dict(FRANK, rates=None)
        with FixtureServer({"/frank": (200, json.dumps(frank_null)),
                            "/exch": (200, json.dumps(EXCH))}) as srv:
            out, gaps = rates.collect(cfg_with(srv))
        for c in ["PHP", "THB", "BRL", "EUR"]:
            self.assertEqual(out[c]["primary_source"], "exchange-api")
            self.assertIsNotNone(out[c]["primary"])
        self.assertEqual(gaps, [])

    def test_secondary_usd_null_all_none(self):
        # 对称回归:{"usd": null} 同样触发 doc.get("usd", {}) 防护失效,原实现在
        # `key not in usd` 处抛 TypeError。null 应视同空 usd 映射,secondary 全
        # None,primary(frankfurter)不受影响。
        exch_null = dict(EXCH, usd=None)
        with FixtureServer({"/frank": (200, json.dumps(FRANK)),
                            "/exch": (200, json.dumps(exch_null))}) as srv:
            out, gaps = rates.collect(cfg_with(srv))
        for c in ["PHP", "THB", "BRL", "EUR"]:
            self.assertIsNone(out[c]["secondary"])
            self.assertIsNotNone(out[c]["primary"])
            self.assertEqual(out[c]["primary_source"], "frankfurter")
        exch_gaps = [g for g in gaps if g["source"] == "exchange-api"]
        self.assertEqual(len(exch_gaps), 1)
        self.assertEqual(exch_gaps[0]["scope"], "all")

    def test_frankfurter_empty_rates_dict_degrades_to_secondary(self):
        # 复审 Minor(a)行为锁定:HTTP 200 + {"rates": {}}(键存在、值为空字典,
        # 非 null)本就不触发 fd19729 的 None 回归——空字典可正常参与成员判断,
        # 现行为已正确。实测(本轮探测脚本):gaps == [],四币种均降级到
        # exchange-api。这里直接钉死为回归测试,无 RED。
        frank_empty = dict(FRANK, rates={})
        with FixtureServer({"/frank": (200, json.dumps(frank_empty)),
                            "/exch": (200, json.dumps(EXCH))}) as srv:
            out, gaps = rates.collect(cfg_with(srv))
        for c in ["PHP", "THB", "BRL", "EUR"]:
            self.assertEqual(out[c]["primary_source"], "exchange-api")
            self.assertIsNotNone(out[c]["primary"])
        self.assertEqual(gaps, [])

    def test_frankfurter_top_level_null_degrades_to_secondary(self):
        # 第 3 轮复审 Critical:整响应体本身就是合法 JSON 字面量 null(而非
        # {"rates": null}),json.loads 后 doc 本身为 None,`doc.get("rates")`
        # 在 try 块外对 None 调用 → 未捕获 AttributeError,collect() 整体崩溃。
        # null 应视同空响应,四币种应降级到 exchange-api。
        with FixtureServer({"/frank": (200, "null"),
                            "/exch": (200, json.dumps(EXCH))}) as srv:
            out, gaps = rates.collect(cfg_with(srv))
        for c in ["PHP", "THB", "BRL", "EUR"]:
            self.assertEqual(out[c]["primary_source"], "exchange-api")
            self.assertIsNotNone(out[c]["primary"])
        self.assertEqual(gaps, [])

    def test_exchange_api_top_level_null_secondary_all_none(self):
        # 对称回归:/exch 整响应体是字面量 null,`doc.get("usd")` 在 try 块外
        # 对 None 调用 → 未捕获 AttributeError。null 应视同空响应,secondary
        # 全 None,primary(frankfurter)不受影响。
        with FixtureServer({"/frank": (200, json.dumps(FRANK)),
                            "/exch": (200, "null")}) as srv:
            out, gaps = rates.collect(cfg_with(srv))
        for c in ["PHP", "THB", "BRL", "EUR"]:
            self.assertIsNone(out[c]["secondary"])
            self.assertIsNotNone(out[c]["primary"])
            self.assertEqual(out[c]["primary_source"], "frankfurter")
        exch_gaps = [g for g in gaps if g["source"] == "exchange-api"]
        self.assertEqual(len(exch_gaps), 1)
        self.assertEqual(exch_gaps[0]["scope"], "all")

    def test_frankfurter_top_level_array_degrades_to_secondary(self):
        # 非 dict 顶层响应的另一形态(数组):与 null 同一崩溃路径,isinstance
        # 门应一律防护,不分形态逐个打补丁。
        with FixtureServer({"/frank": (200, "[1,2]"),
                            "/exch": (200, json.dumps(EXCH))}) as srv:
            out, gaps = rates.collect(cfg_with(srv))
        for c in ["PHP", "THB", "BRL", "EUR"]:
            self.assertEqual(out[c]["primary_source"], "exchange-api")
            self.assertIsNotNone(out[c]["primary"])
        self.assertEqual(gaps, [])

    def test_dual_source_all_fields_empty_gap_count_locked(self):
        # 复审 Minor(b)行为锁定:双源均 HTTP 200,但 rates/usd 字段都是空字典。
        # 实测(本轮探测脚本):共 5 条 gap——1 条 exchange-api/all(空 usd
        # map)+ 4 条 rates/<currency>(missing in both sources,双源本轮都
        # "成功返回"却仍缺该币种字段);四币种 primary_source 均为 None。
        frank_empty = dict(FRANK, rates={})
        exch_empty = dict(EXCH, usd={})
        with FixtureServer({"/frank": (200, json.dumps(frank_empty)),
                            "/exch": (200, json.dumps(exch_empty))}) as srv:
            out, gaps = rates.collect(cfg_with(srv))
        self.assertEqual(len(gaps), 5)
        exch_gaps = [g for g in gaps if g["source"] == "exchange-api" and g["scope"] == "all"]
        self.assertEqual(len(exch_gaps), 1)
        missing_both_gaps = [g for g in gaps if g["source"] == "rates"]
        self.assertEqual({g["scope"] for g in missing_both_gaps}, {"PHP", "THB", "BRL", "EUR"})
        for c in ["PHP", "THB", "BRL", "EUR"]:
            self.assertIsNone(out[c]["primary_source"])
            self.assertIsNone(out[c]["primary"])


if __name__ == "__main__":
    unittest.main()
