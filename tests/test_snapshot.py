import json
import os
import tempfile
import unittest
from unittest import mock

from scripts.collect import __main__ as entry
from scripts.collect import events as events_mod
from scripts.collect import feeds
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


def endpoints(srv):
    return {
        "frankfurter_url": srv.base_url + "/frank?d={date}",
        "exchange_api_urls": [srv.base_url + "/exch?d={date}"],
        "bis_cpi_url": srv.base_url + "/bis/cpi",
        "gdelt_doc_url": srv.base_url + "/doc",
        "fred_release_dates_url": srv.base_url + "/fred",
    }


ROUTES = {"/frank": (200, json.dumps(FRANK)), "/exch": (200, json.dumps(EXCH)),
          "/bis/cpi": (200, BIS_CPI), "/doc": (200, json.dumps(GDELT))}


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
        # 采集上限随快照落盘:常量一改,聚合器拿新上限判旧快照会静默错判触顶
        # 全等断言是有意的:某个上限悄悄消失必须能被抓到。两条事件通道上限
        # 不同(gnews 99 / GDELT 8),少记任一个,下游判截断就会拿错的上限去比
        self.assertEqual(snap["meta"]["caps"],
                         {"official_daily": feeds.MAX_ITEMS,
                          "gdelt_records": events_mod.MAX_RECORDS,
                          "gnews_records": events_mod.GNEWS_SOFT_CAP})
        self.assertEqual(len({feeds.MAX_ITEMS, events_mod.MAX_RECORDS,
                              events_mod.GNEWS_SOFT_CAP}), 3)   # 三者互换可被发现
        self.assertNotIn("us_release_dates", snap)   # 零 key 不出现该键

    def test_one_source_down_others_intact(self):
        with tempfile.TemporaryDirectory() as tmp, FixtureServer(dict(ROUTES)) as srv:
            eps = endpoints(srv)
            eps["bis_cpi_url"] = DEAD_URL + "/bis/cpi"
            make_test_root(tmp, eps, indicators=IND)
            rc = entry.main(["--date", "2026-08-10", "--root", tmp])
            self.assertEqual(rc, 0)                  # 单源失败不中断
            with open(os.path.join(tmp, "data", "2026-08-10.json"), encoding="utf-8") as f:
                snap = json.load(f)
        self.assertEqual(snap["macro"], [])
        self.assertEqual([g["source"] for g in snap["gaps"]], ["bis"])
        self.assertEqual([g["scope"] for g in snap["gaps"]], ["PH/CPI 同比"])
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


@mock.patch.dict(os.environ, {"FX_GDELT_DELAY_S": "0", "FX_GDELT_BACKOFF_S": "0"})
class DerivedSectionTest(unittest.TestCase):
    """derived 落盘与异常不阻断(delta spec: 派生指标落盘 / 派生计算异常不阻断)。"""

    def _run(self, tmp, srv, history=None):
        make_test_root(tmp, endpoints(srv), indicators=IND)
        for d, snap in (history or {}).items():
            with open(os.path.join(tmp, "data", d + ".json"), "w", encoding="utf-8") as f:
                json.dump(snap, f)
        rc = entry.main(["--date", "2026-08-10", "--root", tmp])
        self.assertEqual(rc, 0)
        with open(os.path.join(tmp, "data", "2026-08-10.json"), encoding="utf-8") as f:
            return json.load(f)

    def test_derived_section_present(self):
        with tempfile.TemporaryDirectory() as tmp, FixtureServer(dict(ROUTES)) as srv:
            snap = self._run(tmp, srv)
        self.assertIn("derived", snap)
        # 4 = body_plan 已删(见 derive.SCHEMA_VERSION 的注释)。
        # 端到端断言不可省:私有函数全绿而落盘时漏写这一节,校验器会把它
        # 当成"阶段 1 之前采的存量快照"静默跳过。
        self.assertEqual(snap["derived"]["schema_version"], 4)
        self.assertIn("PHP", snap["derived"]["rates"])
        self.assertIn("PHP", snap["derived"]["events"])
        # 落盘路径上也不许再长出 body_plan:derive 删干净了、而组装层又补一份
        # 回去,是本仓库"两处各算一遍"那类漂移的入口。
        self.assertNotIn("body_plan", snap["derived"])

    def test_derived_uses_multi_day_history(self):
        hist = {"2026-08-%02d" % d: {
            "rates": {"PHP": {"primary": 60.0 + d, "ref_date": "2026-08-%02d" % d}},
            "events": {"PHP": {"articles": []}}} for d in (6, 7, 8, 9)}
        with tempfile.TemporaryDirectory() as tmp, FixtureServer(dict(ROUTES)) as srv:
            snap = self._run(tmp, srv, hist)
        r = snap["derived"]["rates"]["PHP"]
        self.assertEqual(r["range_5d_days"], 5)          # 当日 + 最近 4 份
        self.assertEqual(r["range_5d_low"], 60.843)      # 当日值最低
        self.assertEqual(r["range_5d_high"], 69.0)       # 08-09 的 60+9

    def test_history_excludes_self_and_non_snapshot_files(self):
        """重跑当天时 data/<date>.json 已存在,不得把今早自己的产物当历史;
        误放的非日期文件也不得占用历史窗口。"""
        with tempfile.TemporaryDirectory() as tmp:
            data = os.path.join(tmp, "data")
            os.makedirs(data)
            for name in ("2026-08-10.json", "2026-08-09.json", "1backup.json", "foo.json"):
                with open(os.path.join(data, name), "w", encoding="utf-8") as f:
                    json.dump({"marker": name}, f)
            hist = entry._load_history(data, "2026-08-10")
        self.assertEqual([h["marker"] for h in hist], ["2026-08-09.json"])

    def test_derive_failure_becomes_gap_and_snapshot_still_written(self):
        with tempfile.TemporaryDirectory() as tmp, FixtureServer(dict(ROUTES)) as srv:
            make_test_root(tmp, endpoints(srv), indicators=IND)
            with mock.patch("scripts.collect.derive.derive", side_effect=RuntimeError("boom")):
                rc = entry.main(["--date", "2026-08-10", "--root", tmp])
            self.assertEqual(rc, 0)
            with open(os.path.join(tmp, "data", "2026-08-10.json"), encoding="utf-8") as f:
                snap = json.load(f)
        self.assertIn("rates", snap)                     # 其余部分照常落盘
        self.assertTrue(any(g["source"] == "derive" for g in snap["gaps"]))


@mock.patch.dict(os.environ, {"FX_GDELT_DELAY_S": "0", "FX_GDELT_BACKOFF_S": "0"})
class OfficialFeedsTest(unittest.TestCase):
    """官方公告并入 events(delta spec: GDELT 失败时官方通道仍在)。"""

    FEED = ('<?xml version="1.0"?><rss><channel><item>'
            '<title>FOMC statement</title><link>https://f.gov/1</link>'
            '<pubDate>Wed, 29 Jul 2026 18:00:00 GMT</pubDate></item></channel></rss>')

    def _endpoints(self, srv):
        e = endpoints(srv)
        e["fed_press_rss"] = srv.base_url + "/fed"
        e["ecb_press_rss"] = srv.base_url + "/ecb"
        return e

    def _run(self, tmp, srv, routes):
        make_test_root(tmp, self._endpoints(srv), indicators=IND)
        srv.httpd.fixture_routes.clear()
        srv.httpd.fixture_routes.update(routes)
        self.assertEqual(entry.main(["--date", "2026-08-10", "--root", tmp]), 0)
        with open(os.path.join(tmp, "data", "2026-08-10.json"), encoding="utf-8") as f:
            return json.load(f)

    def test_official_present_alongside_articles(self):
        routes = dict(ROUTES); routes["/fed"] = (200, self.FEED); routes["/ecb"] = (200, self.FEED)
        with tempfile.TemporaryDirectory() as tmp, FixtureServer(dict(ROUTES)) as srv:
            snap = self._run(tmp, srv, routes)
        self.assertEqual(snap["events"]["USD"]["official"][0]["issuer"], "Fed")
        self.assertTrue(snap["events"]["USD"]["articles"])          # 两个通道并列

    def test_official_survives_gdelt_outage(self):
        routes = dict(ROUTES); routes.pop("/doc")                   # GDELT 全挂
        routes["/fed"] = (200, self.FEED); routes["/ecb"] = (200, self.FEED)
        with tempfile.TemporaryDirectory() as tmp, FixtureServer(dict(ROUTES)) as srv:
            snap = self._run(tmp, srv, routes)
        self.assertTrue(any(g["source"] == "gdelt" for g in snap["gaps"]))
        self.assertEqual(snap["events"]["USD"]["official"][0]["title"], "FOMC statement")
        self.assertNotIn("articles", snap["events"]["USD"])          # GDELT 没采到就没有该键

    def test_official_not_counted_in_event_count(self):
        """derived.events.count 只数 GDELT articles;两通道口径不同,合并会让计数不可比。"""
        routes = dict(ROUTES); routes.pop("/doc")
        routes["/fed"] = (200, self.FEED); routes["/ecb"] = (200, self.FEED)
        with tempfile.TemporaryDirectory() as tmp, FixtureServer(dict(ROUTES)) as srv:
            snap = self._run(tmp, srv, routes)
        self.assertIsNone(snap["derived"]["events"]["USD"]["count"])


@mock.patch.dict(os.environ, {"FX_GDELT_DELAY_S": "0", "FX_GDELT_BACKOFF_S": "0"})
class GnewsCapsTest(unittest.TestCase):
    """上限不随快照落盘,日后常量一改,聚合器拿新上限判旧快照就会静默错判。"""

    def test_meta_caps_includes_gnews_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_test_root(tmp, {}, indicators=[])
            cfg = entry.build_cfg("2026-08-10", root=tmp)
            snap = entry.run(cfg)
        self.assertEqual(snap["meta"]["caps"]["gnews_records"],
                         events_mod.GNEWS_SOFT_CAP)
        self.assertEqual(snap["meta"]["caps"]["gdelt_records"],
                         events_mod.MAX_RECORDS)

    def test_cfg_points_at_repo_whitelist(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_test_root(tmp, {}, indicators=[])
            cfg = entry.build_cfg("2026-08-10", root=tmp)
        self.assertEqual(cfg["news_sources_path"],
                         os.path.join(tmp, "config", "news_sources.json"))
