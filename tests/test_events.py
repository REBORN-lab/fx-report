import json
import os
import unittest
import urllib.parse

from scripts.collect import events
from tests.helpers import DEAD_URL, FixtureServer, make_test_cfg

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "gdelt_artlist_sample.json")
with open(FIXTURE, encoding="utf-8") as f:
    SAMPLE = f.read()
LIMIT_TEXT = "You have exceeded the rate limit, please try again later."


def cfg_with(srv):
    return make_test_cfg(endpoints={"gdelt_doc_url": srv.base_url + "/doc"})


class EventsTest(unittest.TestCase):
    def test_default_delay_meets_spec(self):
        self.assertGreaterEqual(events.DEFAULT_DELAY_S, 5)   # spec: 串行 ≥5s
        self.assertGreaterEqual(events.DEFAULT_BACKOFF_S, 1)

    def test_normal_collection_all_currencies(self):
        with FixtureServer({"/doc": (200, SAMPLE)}) as srv:
            out, gaps = events.collect(cfg_with(srv))
        self.assertEqual(gaps, [])
        self.assertEqual(sorted(out), ["BRL", "EUR", "PHP", "THB", "USD"])
        art = out["PHP"]["articles"][0]
        self.assertEqual(art["title"], "BSP signals possible rate cut in September")
        self.assertEqual(art["domain"], "reuters.com")
        self.assertIn("tone_avg", out["PHP"])   # tone 字段容错,可为 None

    def test_soft_rate_limit_retry_succeeds(self):
        state = {"n": 0}

        def route(handler):
            state["n"] += 1
            return (200, LIMIT_TEXT) if state["n"] == 1 else (200, SAMPLE)

        with FixtureServer({"/doc": route}) as srv:
            out, gaps = events.collect(cfg_with(srv))
        self.assertEqual(gaps, [])
        self.assertEqual(len(out), 5)

    def test_soft_rate_limit_persistent_becomes_gap(self):
        def route(handler):
            q = urllib.parse.unquote_plus(handler.path)
            if "Thai" in q:
                return (200, LIMIT_TEXT)
            return (200, SAMPLE)

        with FixtureServer({"/doc": route}) as srv:
            out, gaps = events.collect(cfg_with(srv))
        self.assertEqual([g["scope"] for g in gaps], ["THB"])
        self.assertIn("rate-limited", gaps[0]["reason"])
        self.assertNotIn("THB", out)
        self.assertIn("PHP", out)               # 其余币种继续

    def test_endpoint_error_single_currency(self):
        def route(handler):
            q = urllib.parse.unquote_plus(handler.path)
            return (500, "boom") if "Brazilian" in q else (200, SAMPLE)

        with FixtureServer({"/doc": route}) as srv:
            out, gaps = events.collect(cfg_with(srv))
        self.assertEqual([g["scope"] for g in gaps], ["BRL"])
        self.assertEqual(len(out), 4)

    def test_endpoint_down_entirely(self):
        cfg = make_test_cfg(endpoints={"gdelt_doc_url": DEAD_URL + "/doc"})
        out, gaps = events.collect(cfg)
        self.assertEqual(out, {})
        self.assertEqual(len(gaps), 5)          # 五币种各一条,管线不中断

    def test_backfill_uses_datetime_window(self):
        captured = {}

        def route(handler):
            captured["q"] = handler.path
            return (200, SAMPLE)

        with FixtureServer({"/doc": route}) as srv:
            cfg = cfg_with(srv)
            cfg["backfill"] = True
            events.collect(cfg)
        self.assertIn("startdatetime=20260809000000", captured["q"])
        self.assertIn("enddatetime=20260810000000", captured["q"])
        self.assertNotIn("timespan", captured["q"])

    # ---- 以下为仓库约定补充测试:外部数据类型门与 bool 排除 ----

    def test_default_window_uses_timespan(self):
        """非 backfill 默认路径:timespan=48h 窗口(design:覆盖前一日并容忍时区/抓取延迟),不带 datetime 区间。"""
        captured = {}

        def route(handler):
            captured["q"] = handler.path
            return (200, SAMPLE)

        with FixtureServer({"/doc": route}) as srv:
            events.collect(cfg_with(srv))
        self.assertIn("timespan=48h", captured["q"])
        self.assertNotIn("startdatetime", captured["q"])
        self.assertNotIn("enddatetime", captured["q"])

    def test_non_dict_json_doc_becomes_gap(self):
        """HTTP 200 + JSON 合法但顶层非 dict(list)→ 归入 unparseable 路径记缺漏,不抛异常。"""
        with FixtureServer({"/doc": (200, '[{"articles": []}]')}) as srv:
            out, gaps = events.collect(cfg_with(srv))
        self.assertEqual(out, {})
        self.assertEqual(len(gaps), 5)
        for g in gaps:
            self.assertIn("unparseable response", g["reason"])

    def test_articles_not_list_treated_as_empty(self):
        """doc.articles 非 list(dict)→ 视为空列表,不记缺漏、不抛异常。"""
        with FixtureServer({"/doc": (200, '{"articles": {"oops": 1}}')}) as srv:
            out, gaps = events.collect(cfg_with(srv))
        self.assertEqual(gaps, [])
        self.assertEqual(len(out), 5)
        self.assertEqual(out["PHP"]["articles"], [])
        self.assertIsNone(out["PHP"]["tone_avg"])

    def test_non_dict_article_elements_skipped(self):
        """articles 元素非 dict(标量/None)→ 跳过,仅保留 dict 元素。"""
        body = json.dumps({"articles": [
            {"title": "ok", "url": "https://e.com/1", "domain": "e.com",
             "seendate": "20260809T000000Z"},
            "junk-string", 42, None,
        ]})
        with FixtureServer({"/doc": (200, body)}) as srv:
            out, gaps = events.collect(cfg_with(srv))
        self.assertEqual(gaps, [])
        self.assertEqual(len(out["PHP"]["articles"]), 1)
        self.assertEqual(out["PHP"]["articles"][0]["title"], "ok")

    def test_bool_tone_excluded_from_tone_avg(self):
        """JSON true 是 bool(int 子类),不得混入 tone 均值;仅 bool 时 tone_avg 为 None。"""
        mixed = json.dumps({"articles": [
            {"title": "a", "tone": True},
            {"title": "b", "tone": 4.0},
        ]})
        with FixtureServer({"/doc": (200, mixed)}) as srv:
            out, _ = events.collect(cfg_with(srv))
        self.assertEqual(out["PHP"]["tone_avg"], 4.0)

        only_bool = json.dumps({"articles": [{"title": "a", "tone": True}]})
        with FixtureServer({"/doc": (200, only_bool)}) as srv:
            out, _ = events.collect(cfg_with(srv))
        self.assertIsNone(out["PHP"]["tone_avg"])


if __name__ == "__main__":
    unittest.main()
