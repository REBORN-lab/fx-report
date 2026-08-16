"""聚合层故障注入矩阵:每次打掉一个源,断言其余源完好、gaps 精确。"""
import json
import os
import tempfile
import unittest
from unittest import mock

from scripts.collect import __main__ as entry
from tests.helpers import DEAD_URL, FixtureServer, make_test_root

FRANK = {"rates": {"PHP": 60.843, "THB": 35.2, "BRL": 5.43, "EUR": 0.921}}
EXCH = {"usd": {"php": 60.834, "thb": 35.21, "brl": 5.431, "eur": 0.9211}}
# BIS WS_LONG_CPI 形态(月频)。宏观源由 DBnomics 镜像换成 BIS/IMF 官方直连后,
# 聚合层的"宏观这一枪"用它当被打掉/打不掉的对象。
BIS_CPI = ("FREQ,REF_AREA,UNIT_MEASURE,TIME_PERIOD,OBS_VALUE\n"
           "M,PH,771,2026-06,3.4\n"
           "M,PH,771,2026-07,3.1\n")
GDELT = {"articles": [{"url": "u", "title": "t", "domain": "d", "seendate": "s"}]}
IND = [{"economy": "PH", "indicator": "CPI 同比"}]
ROUTES = {"/frank": (200, json.dumps(FRANK)), "/exch": (200, json.dumps(EXCH)),
          "/bis/cpi": (200, BIS_CPI), "/doc": (200, json.dumps(GDELT))}


def endpoints(srv):
    return {
        "frankfurter_url": srv.base_url + "/frank?d={date}",
        "exchange_api_urls": [srv.base_url + "/exch?d={date}"],
        "bis_cpi_url": srv.base_url + "/bis/cpi",
        "gdelt_doc_url": srv.base_url + "/doc",
        "fred_release_dates_url": srv.base_url + "/fred",
    }


def run_with(eps_mutator, calendar=None):
    with tempfile.TemporaryDirectory() as tmp, FixtureServer(dict(ROUTES)) as srv:
        eps = endpoints(srv)
        eps_mutator(eps)
        make_test_root(tmp, eps, indicators=IND, calendar=calendar)
        rc = entry.main(["--date", "2026-08-10", "--root", tmp])
        with open(os.path.join(tmp, "data", "2026-08-10.json"), encoding="utf-8") as f:
            return rc, json.load(f)


@mock.patch.dict(os.environ, {"FX_GDELT_DELAY_S": "0", "FX_GDELT_BACKOFF_S": "0"})
class FaultMatrixTest(unittest.TestCase):
    def test_frankfurter_down(self):
        rc, snap = run_with(lambda e: e.update(frankfurter_url=DEAD_URL + "/f?d={date}"))
        self.assertEqual(rc, 0)
        self.assertEqual([g["source"] for g in snap["gaps"]], ["frankfurter"])
        self.assertEqual(snap["rates"]["PHP"]["primary"], 60.834)      # 副源顶上
        self.assertEqual(snap["rates"]["PHP"]["primary_source"], "exchange-api")
        self.assertEqual(snap["macro"][0]["value"], 3.1)

    def test_exchange_api_down(self):
        rc, snap = run_with(lambda e: e.update(exchange_api_urls=[DEAD_URL + "/e?d={date}"]))
        self.assertEqual([g["source"] for g in snap["gaps"]], ["exchange-api"])
        self.assertEqual(snap["rates"]["PHP"]["primary"], 60.843)      # 主源不受影响
        self.assertIsNone(snap["rates"]["PHP"]["secondary"])

    def test_both_rate_sources_down(self):
        rc, snap = run_with(lambda e: e.update(
            frankfurter_url=DEAD_URL + "/f?d={date}",
            exchange_api_urls=[DEAD_URL + "/e?d={date}"]))
        self.assertEqual({g["source"] for g in snap["gaps"]},
                         {"frankfurter", "exchange-api"})
        self.assertIsNone(snap["rates"]["PHP"]["primary"])             # 当日无汇率
        self.assertEqual(len(snap["events"]), 5)                       # 其余源完好

    def test_macro_source_down(self):
        """宏观源打掉:没有回落层,该指标没有行,并逐条记缺漏(scope 到指标)。"""
        rc, snap = run_with(lambda e: e.update(bis_cpi_url=DEAD_URL + "/bis/cpi"))
        self.assertEqual([g["source"] for g in snap["gaps"]], ["bis"])
        self.assertEqual([g["scope"] for g in snap["gaps"]], ["PH/CPI 同比"])
        self.assertEqual(snap["macro"], [])
        self.assertEqual(snap["rates"]["EUR"]["primary"], 0.921)

    def test_gdelt_down(self):
        rc, snap = run_with(lambda e: e.update(gdelt_doc_url=DEAD_URL + "/doc"))
        self.assertEqual([g["source"] for g in snap["gaps"]],
                         ["gdelt"] * 5)                                # 五币种各一条
        self.assertEqual(snap["events"], {})
        self.assertEqual(snap["rates"]["PHP"]["primary"], 60.843)

    def test_calendar_expired(self):
        rc, snap = run_with(lambda e: None, calendar={
            "valid_until": "2026-01-01",
            "events": [{"date": "2026-08-09", "bank": "BSP", "event": "货币委员会议息"}]})
        self.assertEqual([g["source"] for g in snap["gaps"]], ["calendar"])
        self.assertIn("expired", snap["gaps"][0]["reason"])
        self.assertEqual(snap["calendar_hits"][0]["bank"], "BSP")      # 仍执行命中



if __name__ == "__main__":
    unittest.main()
