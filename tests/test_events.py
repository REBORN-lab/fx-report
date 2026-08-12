import json
import os
import unittest
import urllib.parse
from unittest import mock

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
        self.assertEqual(events.DEFAULT_DELAY_S, 20)         # spec: 默认 20s(429 缓解)
        self.assertGreaterEqual(events.DEFAULT_BACKOFF_S, 1)

    def test_normal_collection_all_currencies(self):
        with FixtureServer({"/doc": (200, SAMPLE)}) as srv:
            out, gaps = events.collect(cfg_with(srv))
        self.assertEqual(gaps, [])
        self.assertEqual(sorted(out), ["BRL", "EUR", "PHP", "THB", "USD"])
        art = out["PHP"]["articles"][0]
        self.assertEqual(art["title"], "BSP signals possible rate cut in September")
        self.assertEqual(art["domain"], "reuters.com")
        self.assertNotIn("tone", art)           # artlist 端点不返回 tone,快照不得含该字段
        self.assertNotIn("tone_avg", out["PHP"])

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
        thai_calls = {"n": 0}

        def route(handler):
            q = urllib.parse.unquote_plus(handler.path)
            if "Thai" in q:
                thai_calls["n"] += 1
                return (200, LIMIT_TEXT)
            return (200, SAMPLE)

        with FixtureServer({"/doc": route}) as srv:
            out, gaps = events.collect(cfg_with(srv))
        self.assertEqual(thai_calls["n"], 2)    # 初次 + 恰一次重试,锁定重试上界
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

    def test_deeply_nested_json_body_becomes_gap(self):
        """HTTP 200 + 深嵌套 JSON(10 万层数组)→ json.loads 抛 RecursionError
        (非 ValueError 子类)。必须就地归入 unparseable 路径记缺漏,
        绝不穿透 collect() 上抛(硬契约)。"""
        deep = "[" * 100000 + "]" * 100000
        with FixtureServer({"/doc": (200, deep)}) as srv:
            out, gaps = events.collect(cfg_with(srv))
        self.assertEqual(out, {})
        self.assertEqual(sorted(g["scope"] for g in gaps),
                         ["BRL", "EUR", "PHP", "THB", "USD"])
        for g in gaps:
            self.assertIn("unparseable response", g["reason"])

    def test_unrecognized_payload_records_gap_not_empty_list(self):
        """HTTP 200 但没有可用的 articles 列表 → 必须记 gap、不落该币种的键。

        折叠成空列表且不记 gap,落盘后与"GDELT 确实一条都没索引到"在结构上
        完全不可区分,周度聚合器据此会给出"区间内确实 0 条"——源改版被读成
        市场事实。feeds.py 对同类危害早有这道门,这里补齐(第六轮 C12)。"""
        for body in ('{"articles": {"oops": 1}}', '{}', '{"articles": null}',
                     '{"error": "quota"}'):
            with FixtureServer({"/doc": (200, body)}) as srv:
                out, gaps = events.collect(cfg_with(srv))
            self.assertEqual(out, {}, body)
            self.assertEqual(len(gaps), 5, body)
            self.assertIn("no usable 'articles' list", gaps[0]["reason"], body)

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

    def test_tone_fields_absent(self):
        """artlist 端点不返回 tone(实测 40/40 为 null):字段整体删除,不留死字段。"""
        body = json.dumps({"articles": [
            {"title": "a", "url": "u", "domain": "d", "seendate": "s", "tone": 4.0}]})
        with FixtureServer({"/doc": (200, body)}) as srv:
            out, _ = events.collect(cfg_with(srv))
        self.assertNotIn("tone", out["PHP"]["articles"][0])
        self.assertNotIn("tone_avg", out["PHP"])


class HardRateLimitTest(unittest.TestCase):
    """HTTP 429 硬限流退避(delta spec: 硬限流退避)。"""

    def test_hard_429_retry_succeeds(self):
        state = {"n": 0}

        def route(handler):
            q = urllib.parse.unquote_plus(handler.path)
            if "Thai" not in q:
                return (200, SAMPLE)
            state["n"] += 1
            return (429, "Too Many Requests") if state["n"] == 1 else (200, SAMPLE)

        with FixtureServer({"/doc": route}) as srv:
            out, gaps = events.collect(cfg_with(srv))
        self.assertEqual(gaps, [])
        self.assertEqual(state["n"], 2)          # 初次 429 + 一次重试
        self.assertIn("THB", out)

    def test_hard_429_persistent_becomes_gap(self):
        calls = {"n": 0}

        def route(handler):
            q = urllib.parse.unquote_plus(handler.path)
            if "Thai" not in q:
                return (200, SAMPLE)
            calls["n"] += 1
            return (429, "Too Many Requests")

        with FixtureServer({"/doc": route}) as srv:
            out, gaps = events.collect(cfg_with(srv))
        self.assertEqual(calls["n"], 2)          # 初次 + 恰一次重试,锁定重试上界
        self.assertEqual([g["scope"] for g in gaps], ["THB"])
        self.assertIn("429", gaps[0]["reason"])
        self.assertNotIn("THB", out)


class QueryOrderTest(unittest.TestCase):
    """查询顺序按日期确定性轮转(delta spec: 查询顺序轮转)。"""

    def test_same_date_gives_same_order(self):
        self.assertEqual(events.query_order("2026-08-11"), events.query_order("2026-08-11"))

    def test_order_is_a_rotation_of_all_currencies(self):
        order = events.query_order("2026-08-11")
        self.assertEqual(sorted(order), sorted(events.KEYWORDS))
        self.assertEqual(len(order), 5)

    def test_different_dates_can_give_different_orders(self):
        orders = {tuple(events.query_order("2026-08-%02d" % d)) for d in range(1, 15)}
        self.assertGreater(len(orders), 1)

    def test_order_matches_hardcoded_expectation(self):
        """预期值硬编码,不拿被测函数自己当预期(否则轮转被删也测不出)。"""
        self.assertEqual(events.query_order("2026-08-11"),
                         ["BRL", "USD", "EUR", "PHP", "THB"])
        self.assertEqual(events.query_order("2026-08-12"),
                         ["USD", "EUR", "PHP", "THB", "BRL"])

    def test_collect_follows_rotated_order(self):
        seen = []

        def route(handler):
            seen.append(urllib.parse.unquote_plus(handler.path))
            return (200, SAMPLE)

        with FixtureServer({"/doc": route}) as srv:
            cfg = cfg_with(srv)
            cfg["date"] = "2026-08-11"
            events.collect(cfg)
        # 全部 5 个位置逐一核对,不只看首位
        expected = ["BRL", "USD", "EUR", "PHP", "THB"]
        actual = [next(c for c in events.KEYWORDS
                       if events.KEYWORDS[c].split('"')[1] in q) for q in seen]
        self.assertEqual(actual, expected)


class DedupeTest(unittest.TestCase):
    """同币种内标题去重(delta spec: 标题去重)。"""

    def test_duplicate_titles_collapsed(self):
        body = json.dumps({"articles": [
            {"title": "same", "url": "u1", "domain": "d1", "seendate": "s1"},
            {"title": "same", "url": "u2", "domain": "d2", "seendate": "s2"},
            {"title": "other", "url": "u3", "domain": "d3", "seendate": "s3"},
        ]})
        with FixtureServer({"/doc": (200, body)}) as srv:
            out, _ = events.collect(cfg_with(srv))
        titles = [a["title"] for a in out["PHP"]["articles"]]
        self.assertEqual(titles, ["same", "other"])      # 保留首条

    def test_none_titles_not_collapsed(self):
        """标题缺失(None)不构成"重复",不得把不同文章折叠成一条。"""
        body = json.dumps({"articles": [
            {"url": "u1", "domain": "d1"}, {"url": "u2", "domain": "d2"},
        ]})
        with FixtureServer({"/doc": (200, body)}) as srv:
            out, _ = events.collect(cfg_with(srv))
        self.assertEqual(len(out["PHP"]["articles"]), 2)
class RawCountTest(unittest.TestCase):
    """去重前条数必须落盘:只留去重后的长度,下游无法判断是否顶到每日上限,
    截断会被漏报(报告随之把封顶样本当成精确计数)。"""

    def test_raw_count_recorded_alongside_deduped_articles(self):
        dupes = [{"title": "same"}] * 3 + [{"title": "other"}]
        cfg = make_test_cfg(endpoints={"gdelt_doc_url": DEAD_URL + "/doc"})
        with mock.patch.object(events, "_query_with_retry",
                               return_value=((dupes, len(dupes)), None)):
            out, gaps = events.collect(cfg)
        self.assertEqual(gaps, [])
        entry = out["PHP"]
        self.assertEqual(len(entry["articles"]), 2)      # 去重后
        self.assertEqual(entry["articles_raw_count"], 4)  # 去重前

class GnewsConfigTest(unittest.TestCase):
    """gnews 需要端点与白名单两者都配齐才启用;缺任一即静默停用(现状行为)。"""

    def test_make_test_cfg_has_news_sources_path_key(self):
        cfg = make_test_cfg()
        self.assertIn("news_sources_path", cfg)
        self.assertIsNone(cfg["news_sources_path"])

    def test_shipped_whitelist_is_loadable_and_nonempty(self):
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                            "config", "news_sources.json")
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        self.assertIsInstance(doc.get("domains"), list)
        self.assertGreater(len(doc["domains"]), 10)
        self.assertIn("reuters.com", doc["domains"])
        # 白名单项必须是裸主机名:带 scheme 或路径会永远匹配不上,而且失效是静默的
        for d in doc["domains"]:
            self.assertNotIn("/", d, d)
            self.assertFalse(d.startswith("www."), d)
            self.assertEqual(d, d.lower(), d)

    def test_endpoint_template_takes_query_placeholder(self):
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                            "config", "endpoints.json")
        with open(path, encoding="utf-8") as f:
            url = json.load(f)["gnews_rss_url"]
        self.assertIn("{query}", url)
        self.assertTrue(url.startswith("https://news.google.com/rss/search"))


if __name__ == "__main__":
    unittest.main()
