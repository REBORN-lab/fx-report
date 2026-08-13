import json
import os
import tempfile
import unittest
import urllib.parse
from datetime import datetime, timedelta, timezone
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
                               return_value=((dupes, len(dupes), 0), None)):
            out, gaps = events.collect(cfg)
        self.assertEqual(gaps, [])
        entry = out["PHP"]
        self.assertEqual(len(entry["articles"]), 2)      # 去重后
        self.assertEqual(entry["articles_raw_count"], 4)  # 去重前
        self.assertEqual(entry["articles_dropped_malformed"], 0)

    def test_malformed_elements_are_counted_into_the_snapshot(self):
        """源改版成 {"articles": ["<a>", ...]}:逐个跳过后落盘 articles=[] 而
        raw_count=3、gaps 为空,与"确实一条都没有"完全同形。丢弃量必须落盘,
        否则聚合器据此断言"区间内确实 0 条、全区间采集完整"(第四轮 S1)。"""
        cfg = make_test_cfg(endpoints={"gdelt_doc_url": DEAD_URL + "/doc"})
        with mock.patch.object(events, "_query_with_retry",
                               return_value=(([], 3, 3), None)):
            out, gaps = events.collect(cfg)
        entry = out["PHP"]
        self.assertEqual(entry["articles"], [])
        self.assertEqual(entry["articles_raw_count"], 3)
        self.assertEqual(entry["articles_dropped_malformed"], 3)
        # 一个可用元素都没解析出来 → 必须记 gap:落盘形态与"源确实一条都没索引
        # 到"完全同形,日报靠 gaps → 缺漏节这条链才知道不能写"事件数 0"
        self.assertEqual(sorted(g["scope"] for g in gaps),
                         ["BRL", "EUR", "PHP", "THB", "USD"])
        self.assertIn("结构不可识别", gaps[0]["reason"])

    def test_partial_malformed_drop_is_not_a_gap(self):
        """部分丢弃不是采集失败:仍有可用条目时不刷 gap,丢弃量经
        articles_dropped_malformed → derived.dropped_malformed 供日报引用。"""
        good = [{"title": "ok", "url": "u", "domain": "reuters.com",
                 "seendate": "20260811T000000Z"}]
        cfg = make_test_cfg(endpoints={"gdelt_doc_url": DEAD_URL + "/doc"})
        with mock.patch.object(events, "_query_with_retry",
                               return_value=((good, 4, 3), None)):
            out, gaps = events.collect(cfg)
        self.assertEqual(gaps, [])
        self.assertEqual(out["PHP"]["articles_dropped_malformed"], 3)

    def test_fetch_counts_malformed_elements_end_to_end(self):
        """经真实 HTTP 路径走一遍:上面那条用例 mock 了 _query_with_retry,
        把 _fetch 里数丢弃量的那行整个绕过去了(变异 M53 存活实测)。"""
        body = json.dumps({"articles": ["<a>", "<a>", {"title": "ok", "url": "u",
                                                       "domain": "reuters.com",
                                                       "seendate": "20260811T000000Z"}]})
        with FixtureServer({"/doc": (200, body)}) as srv:
            cfg = make_test_cfg(endpoints={"gdelt_doc_url": srv.base_url + "/doc"})
            cfg["gdelt_delay_s"] = 0
            out, gaps = events.collect(cfg)
        self.assertEqual(gaps, [])
        entry = out["PHP"]
        self.assertEqual(len(entry["articles"]), 1)
        self.assertEqual(entry["articles_raw_count"], 3)
        self.assertEqual(entry["articles_dropped_malformed"], 2)

    def test_count_at_cap_and_source_capped_split_on_gnews(self):
        """gnews 上「原始样本触顶」与「落盘条数被钉住」不是同一件事。"""
        counts = {"raw": 100, "undated": 0, "out_window": 0,
                  "offlist": 89, "kept": 11, "capped": True}
        entry = events._gnews_entry([{"title": "t"}] * 11, 100, counts)
        self.assertIs(entry["source_capped"], True)    # 滤除前的 100 顶到 99
        self.assertIs(entry["count_at_cap"], False)    # 落盘的 11 条离 99 差 88
        # 边界:kept 恰好等于上限 → 落盘条数确实被钉住(判据是 >= 不是 >)
        at = dict(counts, offlist=1, kept=events.GNEWS_SOFT_CAP)
        self.assertIs(events._gnews_entry([{"title": "t"}], 100, at)["count_at_cap"], True)
        below = dict(counts, kept=events.GNEWS_SOFT_CAP - 1)
        self.assertIs(events._gnews_entry([{"title": "t"}], 100, below)["count_at_cap"], False)
        # raw/kept 未知 → None(不知道 ≠ 知道没触顶)
        unknown = events._gnews_entry(None, None, None)
        self.assertIsNone(unknown["count_at_cap"])
        self.assertIsNone(unknown["source_capped"])
        self.assertIsNone(unknown["articles_dropped_malformed"])
        self.assertEqual(events._gnews_entry([], 5, dict(counts, raw=5, kept=0))
                         ["articles_dropped_malformed"], 0)

    def test_gdelt_branch_lands_count_at_cap(self):
        """count_at_cap 是 landed_count_capped 的第一权威,GDELT 分支此前零覆盖:
        改成恒 False 时 536 用例全绿(第五轮 S3)。"""
        cfg = make_test_cfg(endpoints={"gdelt_doc_url": DEAD_URL + "/doc"})
        for raw, want in ((events.MAX_RECORDS, True), (3, False)):
            arts = [{"title": "t%d" % i, "url": "u%d" % i, "domain": "reuters.com",
                     "seendate": "20260811T000000Z"} for i in range(raw)]
            with mock.patch.object(events, "_query_with_retry",
                                   return_value=((arts, raw, 0), None)):
                out, _ = events.collect(cfg)
            self.assertIs(out["PHP"]["count_at_cap"], want, raw)
            self.assertIs(out["PHP"]["source_capped"], want, raw)

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


GNEWS_XML = """<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>BSP holds policy rate</title>
 <link>https://news.google.com/rss/articles/CBMiOPAQ</link>
 <guid isPermaLink="false">CBMiOPAQ</guid>
 <pubDate>Tue, 11 Aug 2026 03:37:51 GMT</pubDate>
 <source url="https://interaksyon.philstar.com">Interaksyon</source></item>
<item><title>Convert 1000 PHP to USTC</title>
 <link>https://news.google.com/rss/articles/CBMiZZZZ</link>
 <pubDate>Tue, 11 Aug 2026 04:00:00 GMT</pubDate>
 <source url="https://www.bybit.com">Bybit</source></item>
</channel></rss>"""


class GnewsParseTest(unittest.TestCase):
    def test_extracts_four_fields_per_item(self):
        got = events._gnews_parse(GNEWS_XML)
        self.assertEqual(len(got), 2)
        self.assertEqual(got[0]["title"], "BSP holds policy rate")
        self.assertEqual(got[0]["url"], "https://news.google.com/rss/articles/CBMiOPAQ")
        self.assertEqual(got[0]["pubdate_raw"], "Tue, 11 Aug 2026 03:37:51 GMT")
        self.assertEqual(got[0]["domain"], "interaksyon.philstar.com")
        self.assertEqual(got[1]["domain"], "bybit.com")     # www. 已剥掉

    def test_non_xml_raises_not_empty_list(self):
        """返空列表会让「源改版了」与「确实没新闻」在快照里同形——本仓库反复栽的形态。"""
        for body in ("", "   ", "<html><body>503</body></html>", '{"a": 1}'):
            with self.assertRaises(ValueError, msg=repr(body)):
                events._gnews_parse(body)

    def test_valid_xml_without_items_raises(self):
        empty = '<?xml version="1.0"?><rss version="2.0"><channel></channel></rss>'
        with self.assertRaises(ValueError):
            events._gnews_parse(empty)

    def test_missing_source_element_yields_none_domain(self):
        body = ('<?xml version="1.0"?><rss><channel><item>'
                '<title>t</title><pubDate>Tue, 11 Aug 2026 03:00:00 GMT</pubDate>'
                '</item></channel></rss>')
        got = events._gnews_parse(body)
        self.assertIsNone(got[0]["domain"])
        self.assertIsNone(got[0]["url"])


class PubdateTest(unittest.TestCase):
    def test_rfc2822_with_gmt(self):
        dt = events._pubdate("Tue, 11 Aug 2026 03:37:51 GMT")
        self.assertEqual(dt.year, 2026)
        self.assertEqual(dt.hour, 3)
        self.assertIsNotNone(dt.tzinfo)

    def test_offset_timezone_normalised(self):
        a = events._pubdate("Tue, 11 Aug 2026 05:37:51 +0200")
        b = events._pubdate("Tue, 11 Aug 2026 03:37:51 GMT")
        self.assertEqual(a, b)

    def test_naive_pubdate_assumed_utc_not_local(self):
        """猜本地时区会让窗口边界随运行机器漂移——同一份数据换台机器结论不同。"""
        dt = events._pubdate("Tue, 11 Aug 2026 03:37:51")
        self.assertEqual(dt.tzinfo, timezone.utc)

    def test_garbage_returns_none(self):
        for raw in ("", "   ", None, "yesterday", "2026-08-11T03:37:51+00:00", 12345):
            self.assertIsNone(events._pubdate(raw), repr(raw))


class WhitelistTest(unittest.TestCase):
    WL = ["reuters.com", "philstar.com"]

    def test_exact_match(self):
        self.assertTrue(events._in_whitelist("reuters.com", self.WL))

    def test_subdomain_matches(self):
        self.assertTrue(events._in_whitelist("interaksyon.philstar.com", self.WL))

    def test_suffix_lookalike_must_not_match(self):
        """裸 endswith 会让 notreuters.com 命中 reuters.com——白名单形同虚设,
        且失效是静默的:噪音照进快照,计数还显示「已过滤」。"""
        for host in ("notreuters.com", "evilreuters.com", "xphilstar.com"):
            self.assertFalse(events._in_whitelist(host, self.WL), host)

    def test_none_and_empty_host_never_match(self):
        for host in (None, "", 123):
            self.assertFalse(events._in_whitelist(host, self.WL), repr(host))

    def test_unrelated_domain(self):
        self.assertFalse(events._in_whitelist("bybit.com", self.WL))


class GnewsFilterTest(unittest.TestCase):
    LO = datetime(2026, 8, 10, 0, 0, tzinfo=timezone.utc)
    HI = datetime(2026, 8, 12, 0, 0, tzinfo=timezone.utc)
    WL = ["philstar.com"]

    def _items(self):
        return [
            {"title": "in-window on-list", "url": "u1",
             "pubdate_raw": "Tue, 11 Aug 2026 03:00:00 GMT",
             "domain": "interaksyon.philstar.com"},
            {"title": "in-window off-list", "url": "u2",
             "pubdate_raw": "Tue, 11 Aug 2026 04:00:00 GMT", "domain": "bybit.com"},
            {"title": "out-of-window on-list", "url": "u3",
             "pubdate_raw": "Sat, 01 Aug 2026 04:00:00 GMT", "domain": "philstar.com"},
            {"title": "undated", "url": "u4",
             "pubdate_raw": "not a date", "domain": "philstar.com"},
        ]

    def test_four_counts_sum_to_raw(self):
        kept, c = events._gnews_filter(self._items(), self.LO, self.HI, self.WL)
        self.assertEqual(c["raw"], 4)
        self.assertEqual(c["undated"], 1)
        self.assertEqual(c["out_window"], 1)
        self.assertEqual(c["offlist"], 1)
        self.assertEqual(c["kept"], 1)
        # 总账必须闭合:漏记任一层,过滤量就不再可见
        self.assertEqual(c["undated"] + c["out_window"] + c["offlist"] + c["kept"],
                         c["raw"])

    def test_only_in_window_on_list_survives(self):
        kept, _ = events._gnews_filter(self._items(), self.LO, self.HI, self.WL)
        self.assertEqual([a["title"] for a in kept], ["in-window on-list"])

    def test_seendate_uses_gdelt_format_not_iso(self):
        """落 ISO 会让 weekly_digest._seen_date 对每条 gnews 文章都返回 None,
        周报 _verdict 每周退化成「无法判定」—— 系统性静默劣化。"""
        kept, _ = events._gnews_filter(self._items(), self.LO, self.HI, self.WL)
        self.assertEqual(kept[0]["seendate"], "20260811T030000Z")

    def test_seendate_is_parseable_by_weekly_digest(self):
        """跨模块靶点:只测 events.py 内部永远发现不了格式分叉。"""
        from scripts.weekly_digest import _seen_date
        kept, _ = events._gnews_filter(self._items(), self.LO, self.HI, self.WL)
        self.assertEqual(_seen_date(kept[0]), "2026-08-11")

    def test_non_utc_offset_normalised_before_formatting(self):
        items = [{"title": "t", "url": "u", "domain": "philstar.com",
                  "pubdate_raw": "Tue, 11 Aug 2026 05:00:00 +0200"}]
        kept, _ = events._gnews_filter(items, self.LO, self.HI, self.WL)
        self.assertEqual(kept[0]["seendate"], "20260811T030000Z")

    def test_missing_domain_counts_as_offlist(self):
        items = [{"title": "t", "url": "u", "domain": None,
                  "pubdate_raw": "Tue, 11 Aug 2026 03:00:00 GMT"}]
        kept, c = events._gnews_filter(items, self.LO, self.HI, self.WL)
        self.assertEqual((c["offlist"], c["kept"]), (1, 0))

    def test_empty_input_is_all_zeros_not_error(self):
        kept, c = events._gnews_filter([], self.LO, self.HI, self.WL)
        self.assertEqual(kept, [])
        self.assertEqual(c, {"raw": 0, "undated": 0, "out_window": 0,
                             "offlist": 0, "kept": 0, "capped": False})

    def test_boundary_timestamps_are_inclusive(self):
        items = [{"title": "lo", "url": "u", "domain": "philstar.com",
                  "pubdate_raw": "Mon, 10 Aug 2026 00:00:00 GMT"},
                 {"title": "hi", "url": "u", "domain": "philstar.com",
                  "pubdate_raw": "Wed, 12 Aug 2026 00:00:00 GMT"}]
        _, c = events._gnews_filter(items, self.LO, self.HI, self.WL)
        self.assertEqual(c["kept"], 2)


class WhitelistLoadTest(unittest.TestCase):
    """三级:未配置=有意停用(不记 gap)/ JSON 坏 / domains 空 —— 后两者必须记 gap。"""

    def _write(self, tmp, payload):
        path = os.path.join(tmp, "news_sources.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write(payload)
        return path

    def test_unconfigured_is_silent_disable(self):
        gaps = []
        self.assertIsNone(events._load_domains(make_test_cfg(), gaps))
        self.assertEqual(gaps, [])

    def test_nonexistent_path_is_silent_disable(self):
        gaps = []
        cfg = make_test_cfg(news_sources_path="/nonexistent/nope.json")
        self.assertIsNone(events._load_domains(cfg, gaps))
        self.assertEqual(gaps, [])

    def test_broken_json_records_gap(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, "{not json")
            gaps = []
            self.assertIsNone(events._load_domains(
                make_test_cfg(news_sources_path=path), gaps))
        self.assertEqual([g["source"] for g in gaps], ["gnews"])

    def test_empty_domains_records_gap(self):
        """空白名单会把一切过滤成 0 条,五币种同时「没有事件」—— 最危险的形态,必须响。"""
        for payload in ('{"domains": []}', '{"domains": "reuters.com"}',
                        '{"nope": 1}', '[]', '{"domains": ["", "  "]}'):
            with tempfile.TemporaryDirectory() as tmp:
                path = self._write(tmp, payload)
                gaps = []
                got = events._load_domains(
                    make_test_cfg(news_sources_path=path), gaps)
            self.assertIsNone(got, payload)
            self.assertEqual(len(gaps), 1, payload)

    def test_valid_file_returns_normalised_domains(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, '{"domains": [" Reuters.com ", "philstar.com", 7]}')
            gaps = []
            got = events._load_domains(make_test_cfg(news_sources_path=path), gaps)
        self.assertEqual(got, ["reuters.com", "philstar.com"])   # 去空白、转小写、丢非串
        self.assertEqual(gaps, [])


def gnews_body(n, domain="interaksyon.philstar.com", pub=None):
    """生成 n 条 gnews RSS 条目;pub 默认取当前时刻(落在 48h 窗口内)。"""
    if pub is None:
        pub = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
    items = "".join(
        '<item><title>t%d</title><link>https://news.google.com/rss/articles/X%d</link>'
        '<pubDate>%s</pubDate><source url="https://%s">S</source></item>'
        % (i, i, pub, domain) for i in range(n))
    return '<?xml version="1.0"?><rss version="2.0"><channel>%s</channel></rss>' % items


def gnews_cfg(srv, **over):
    """gnews 启用所需的两项都配齐:端点 + 白名单文件(由调用方给 path)。"""
    base = make_test_cfg(endpoints={
        "gnews_rss_url": srv.base_url + "/gn?q={query}",
        "gdelt_doc_url": srv.base_url + "/doc",
    })
    base.update(over)
    return base


def gnews_cfg_dead():
    return make_test_cfg(endpoints={"gnews_rss_url": DEAD_URL + "/gn?q={query}",
                                    "gdelt_doc_url": DEAD_URL + "/doc"})


class GnewsOneTest(unittest.TestCase):
    WL = ["philstar.com"]

    def test_entry_shape_and_channel(self):
        with FixtureServer({"/gn": (200, gnews_body(3))}) as srv:
            entry, err = events._gnews_one(gnews_cfg(srv), "PHP", self.WL)
        self.assertIsNone(err)
        self.assertEqual(entry["channel"], "gnews")
        self.assertEqual(len(entry["articles"]), 3)
        self.assertEqual(entry["articles_raw_count"], 3)
        self.assertEqual(entry["source_cap"], events.GNEWS_SOFT_CAP)
        self.assertFalse(entry["source_capped"])
        self.assertEqual(entry["gnews_filter"]["kept"], 3)

    def test_capped_at_soft_cap_99(self):
        """实测上限在 99–100 之间摆动;取下界,宁可误报截断不可漏报。"""
        with FixtureServer({"/gn": (200, gnews_body(99))}) as srv:
            entry, _ = events._gnews_one(gnews_cfg(srv), "PHP", self.WL)
        self.assertTrue(entry["source_capped"])

    def test_not_capped_at_98(self):
        with FixtureServer({"/gn": (200, gnews_body(98))}) as srv:
            entry, _ = events._gnews_one(gnews_cfg(srv), "PHP", self.WL)
        self.assertFalse(entry["source_capped"])

    def test_offlist_items_counted_not_dropped_silently(self):
        with FixtureServer({"/gn": (200, gnews_body(5, domain="bybit.com"))}) as srv:
            entry, err = events._gnews_one(gnews_cfg(srv), "PHP", self.WL)
        self.assertIsNone(err)
        self.assertEqual(entry["articles"], [])
        self.assertEqual(entry["gnews_filter"]["raw"], 5)
        self.assertEqual(entry["gnews_filter"]["offlist"], 5)

    def test_fetch_failure_yields_err_and_null_filter(self):
        """缺输入写 null 不写 0:写 0 会让「跑了但没留下」与「压根没跑成」同形。"""
        entry, err = events._gnews_one(gnews_cfg_dead(), "PHP", self.WL)
        self.assertIsNotNone(err)
        self.assertIsNone(entry["gnews_filter"])
        # articles 为 None 而非 []:没采到与"采到了、可用的 0 条"必须可分辨,
        # 否则周度聚合器会把管道停摆读成"区间内确实 0 条"
        self.assertIsNone(entry["articles"])
        self.assertIsNone(entry["articles_raw_count"])
        self.assertIsNone(entry["source_capped"])   # 不知道 ≠ 知道没截断
        self.assertEqual(entry["channel"], "gnews")

    def test_query_is_urlencoded_keywords_plus_window(self):
        seen = {}

        def route(handler):
            seen["path"] = handler.path
            return (200, gnews_body(1))

        with FixtureServer({"/gn": route}) as srv:
            events._gnews_one(gnews_cfg(srv), "PHP", self.WL)
        q = urllib.parse.unquote_plus(seen["path"])
        self.assertIn("Philippine peso", q)
        self.assertIn("when:2d", q)

    def test_dedupe_runs_after_whitelist(self):
        """先去重会让 offlist 的分母与 raw 对不上。"""
        pub = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
        dupe = ('<item><title>same</title><link>l</link><pubDate>%s</pubDate>'
                '<source url="https://philstar.com">S</source></item>' % pub)
        body = '<?xml version="1.0"?><rss><channel>%s</channel></rss>' % (dupe * 3)
        with FixtureServer({"/gn": (200, body)}) as srv:
            entry, _ = events._gnews_one(gnews_cfg(srv), "PHP", self.WL)
        self.assertEqual(len(entry["articles"]), 1)          # 去重后
        self.assertEqual(entry["gnews_filter"]["kept"], 3)   # 去重前(分母对得上 raw)
        self.assertEqual(entry["articles_raw_count"], 3)


class TwoPassCollectTest(unittest.TestCase):
    def _wl_file(self, tmp, domains='["philstar.com"]'):
        path = os.path.join(tmp, "wl.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write('{"domains": %s}' % domains)
        return path

    def test_no_holes_means_zero_gdelt_requests(self):
        """五币种都有条目时,GDELT 一次请求都不该发(靶点 M9)。"""
        hits = {"gn": 0, "doc": 0}

        def gn(handler):
            hits["gn"] += 1
            return (200, gnews_body(3))

        def doc(handler):
            hits["doc"] += 1
            return (200, SAMPLE)

        with tempfile.TemporaryDirectory() as tmp, \
                FixtureServer({"/gn": gn, "/doc": doc}) as srv:
            cfg = gnews_cfg(srv, news_sources_path=self._wl_file(tmp))
            out, gaps = events.collect(cfg)
        self.assertEqual(hits["gn"], 5)
        self.assertEqual(hits["doc"], 0)
        self.assertEqual(gaps, [])
        self.assertTrue(all(out[c]["channel"] == "gnews" for c in out))

    def test_all_filtered_out_triggers_gdelt_backfill(self):
        """靶点 M8:空洞判定必须用过滤**后**条数。用过滤前条数则永不补位。"""
        with tempfile.TemporaryDirectory() as tmp, \
                FixtureServer({"/gn": (200, gnews_body(8, domain="bybit.com")),
                               "/doc": (200, SAMPLE)}) as srv:
            cfg = gnews_cfg(srv, news_sources_path=self._wl_file(tmp))
            out, gaps = events.collect(cfg)
        self.assertTrue(all(out[c]["channel"] == "gdelt" for c in out))
        self.assertTrue(out["PHP"]["articles"])

    def test_backfill_keeps_gnews_filter_counts(self):
        """靶点 M12:补位成功后仍要能回答「主通道发生了什么」。"""
        with tempfile.TemporaryDirectory() as tmp, \
                FixtureServer({"/gn": (200, gnews_body(8, domain="bybit.com")),
                               "/doc": (200, SAMPLE)}) as srv:
            cfg = gnews_cfg(srv, news_sources_path=self._wl_file(tmp))
            out, _ = events.collect(cfg)
        self.assertEqual(out["PHP"]["gnews_filter"]["raw"], 8)
        self.assertEqual(out["PHP"]["gnews_filter"]["offlist"], 8)
        self.assertEqual(out["PHP"]["source_cap"], events.MAX_RECORDS)  # 通道自己的上限

    def test_both_channels_fail_gap_mentions_both(self):
        with tempfile.TemporaryDirectory() as tmp, \
                FixtureServer({"/gn": (200, gnews_body(8, domain="bybit.com"))}) as srv:
            cfg = gnews_cfg(srv, news_sources_path=self._wl_file(tmp))
            cfg["endpoints"]["gdelt_doc_url"] = DEAD_URL + "/doc"
            out, gaps = events.collect(cfg)
        self.assertEqual(len(gaps), 5)
        self.assertIn("两条通道", gaps[0]["reason"])

    def test_gnews_unconfigured_falls_back_to_gdelt_only(self):
        """既有 GDELT 用例走的就是这条路:行为必须与接入前完全一致。"""
        with FixtureServer({"/doc": (200, SAMPLE)}) as srv:
            out, gaps = events.collect(cfg_with(srv))
        self.assertEqual(gaps, [])
        self.assertEqual(sorted(out), ["BRL", "EUR", "PHP", "THB", "USD"])
        self.assertNotIn("gnews_filter", out["PHP"])

    def test_empty_whitelist_records_gap_and_falls_back(self):
        """靶点 M11。"""
        with tempfile.TemporaryDirectory() as tmp, \
                FixtureServer({"/gn": (200, gnews_body(3)),
                               "/doc": (200, SAMPLE)}) as srv:
            cfg = gnews_cfg(srv, news_sources_path=self._wl_file(tmp, "[]"))
            out, gaps = events.collect(cfg)
        self.assertEqual([g["scope"] for g in gaps], ["whitelist"])
        self.assertTrue(all(out[c]["channel"] == "gdelt" for c in out))

    def test_gnews_parse_failure_records_gap_and_backfills(self):
        """靶点 M10 的 collect 侧 + M13:非 XML 必须记 gap,不能落成「源无数据」。"""
        with tempfile.TemporaryDirectory() as tmp, \
                FixtureServer({"/gn": (200, "<html>503</html>"),
                               "/doc": (200, SAMPLE)}) as srv:
            cfg = gnews_cfg(srv, news_sources_path=self._wl_file(tmp))
            out, gaps = events.collect(cfg)
        self.assertTrue(any(g["source"] == "gnews" for g in gaps))
        self.assertTrue(all(out[c]["channel"] == "gdelt" for c in out))
        self.assertIsNone(out["PHP"]["gnews_filter"])

    def test_partial_holes_only_those_go_to_gdelt(self):
        """只有 PHP 落空 → 只有 PHP 打 GDELT,其余保持 gnews。"""
        seen = []

        def gn(handler):
            q = urllib.parse.unquote_plus(handler.path)
            dom = "bybit.com" if "Philippine" in q else "philstar.com"
            return (200, gnews_body(4, domain=dom))

        def doc(handler):
            seen.append(urllib.parse.unquote_plus(handler.path))
            return (200, SAMPLE)

        with tempfile.TemporaryDirectory() as tmp, \
                FixtureServer({"/gn": gn, "/doc": doc}) as srv:
            cfg = gnews_cfg(srv, news_sources_path=self._wl_file(tmp))
            out, gaps = events.collect(cfg)
        self.assertEqual(len(seen), 1)
        self.assertIn("Philippine", seen[0])
        self.assertEqual(out["PHP"]["channel"], "gdelt")
        self.assertEqual(out["USD"]["channel"], "gnews")


class GnewsRobustnessTest(unittest.TestCase):
    """外部数据可任意畸形;采集层不得抛出,只能转 gap。"""

    def _collect(self, body):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "wl.json")
            with open(path, "w", encoding="utf-8") as f:
                f.write('{"domains": ["philstar.com"]}')
            with FixtureServer({"/gn": (200, body), "/doc": (200, SAMPLE)}) as srv:
                return events.collect(gnews_cfg(srv, news_sources_path=path))

    def test_never_raises_on_any_body(self):
        for body in ("", "\x00\x01", "<rss>", "<rss><channel/></rss>", "[]",
                     '<?xml version="1.0"?><rss><channel><item/></channel></rss>',
                     "<" * 5000, "not xml at all"):
            payload, gaps = self._collect(body)
            self.assertIsInstance(payload, dict)
            self.assertEqual(sorted(payload), ["BRL", "EUR", "PHP", "THB", "USD"])

    def test_item_without_pubdate_counted_undated(self):
        body = ('<?xml version="1.0"?><rss><channel><item><title>t</title>'
                '<source url="https://philstar.com">S</source></item></channel></rss>')
        payload, _ = self._collect(body)
        self.assertEqual(payload["PHP"]["gnews_filter"]["undated"], 1)

    def test_source_without_url_attribute(self):
        pub = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
        body = ('<?xml version="1.0"?><rss><channel><item><title>t</title>'
                '<pubDate>%s</pubDate><source>Nameless</source></item>'
                '</channel></rss>' % pub)
        payload, _ = self._collect(body)
        self.assertEqual(payload["PHP"]["gnews_filter"]["offlist"], 1)

    def test_empty_item_yields_undated_not_crash(self):
        body = '<?xml version="1.0"?><rss><channel><item/></channel></rss>'
        payload, _ = self._collect(body)
        self.assertEqual(payload["PHP"]["gnews_filter"]["undated"], 1)


class ObservationGapTest(unittest.TestCase):
    """审查发现的两条同型 Critical:articles: [] 同时意味着三件事——
    真的没有 / 全被白名单滤掉 / 两条通道都没采到。周度聚合器把三者都读成第一种,
    于是彻底的管道停摆被断言成「区间内确实 0 条,全区间采集完整、无截断」。

    纪律:采到了才写列表,没采到写 null(缺输入写 null 不写 0 的列表版)。
    """

    def _wl(self, tmp, doms='["philstar.com"]'):
        path = os.path.join(tmp, "wl.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write('{"domains": %s}' % doms)
        return path

    def test_both_channels_fail_articles_is_null_not_empty_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = make_test_cfg(
                endpoints={"gnews_rss_url": DEAD_URL + "/gn?q={query}",
                           "gdelt_doc_url": DEAD_URL + "/doc"},
                news_sources_path=self._wl(tmp))
            out, gaps = events.collect(cfg)
        self.assertIsNone(out["PHP"]["articles"])
        self.assertIsNone(out["PHP"]["articles_raw_count"])
        self.assertTrue(gaps)

    def test_weekly_verdict_cannot_claim_zero_when_nothing_collected(self):
        from scripts import weekly_digest as wd
        with tempfile.TemporaryDirectory() as tmp:
            cfg = make_test_cfg(
                endpoints={"gnews_rss_url": DEAD_URL + "/gn?q={query}",
                           "gdelt_doc_url": DEAD_URL + "/doc"},
                news_sources_path=self._wl(tmp))
            out, _ = events.collect(cfg)
        snaps = [{"date": "2026-08-%02d" % d, "rates": {}, "gaps": [],
                  "events": {"PHP": dict(out["PHP"])},
                  "meta": {"caps": {"gdelt_records": 8, "gnews_records": 99}}}
                 for d in range(10, 17)]
        got = wd._events_one(snaps, "PHP", "2026-08-10", "2026-08-16", 0)
        self.assertNotIn("确实 0 条", got["articles_verdict"])
        self.assertEqual(got["days_with_data"], 0)

    def test_all_filtered_out_is_not_confirmed_zero(self):
        """整周抓到 700 条全被白名单滤掉,不等于「本周确实没有事件」。"""
        from scripts import weekly_digest as wd
        entry = {"articles": [], "articles_raw_count": 100, "source_cap": 99,
                 "source_capped": True, "channel": "gnews",
                 "gnews_filter": {"raw": 100, "undated": 0, "out_window": 0,
                                  "offlist": 100, "kept": 0}}
        snaps = [{"date": "2026-08-%02d" % d, "rates": {}, "gaps": [],
                  "events": {"PHP": dict(entry)},
                  "meta": {"caps": {"gdelt_records": 8, "gnews_records": 99}}}
                 for d in range(10, 17)]
        got = wd._events_one(snaps, "PHP", "2026-08-10", "2026-08-16", 0)
        self.assertNotIn("确实 0 条", got["articles_verdict"])
        self.assertIn("700", got["articles_verdict"])   # 滤除量必须出现在结论里

    def test_verdict_never_renders_literal_none(self):
        """两条通道上限不同的一周,daily_cap 为 null,结论句不得出现字面量 None。"""
        from scripts import weekly_digest as wd
        def snap(d, cap, capped):
            return {"date": "2026-08-%02d" % d, "rates": {}, "gaps": [],
                    "events": {"PHP": {"articles": [{"title": "a",
                                                     "seendate": "202608%02dT000000Z" % d}],
                                       "articles_raw_count": cap, "source_cap": cap,
                                       "source_capped": capped, "channel": "x"}},
                    "meta": {"caps": {"gdelt_records": 8, "gnews_records": 99}}}
        got = wd._events_one([snap(10, 99, True), snap(11, 8, True)],
                             "PHP", "2026-08-10", "2026-08-11", 0)
        self.assertNotIn("None", got["articles_verdict"])


class ReviewRoundTwoTest(unittest.TestCase):
    """第二轮审查的 Important 修复。每条都由审查者实跑复现过。"""

    def _wl(self, tmp, doms='["philstar.com"]'):
        path = os.path.join(tmp, "wl.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write('{"domains": %s}' % doms)
        return path

    # I10:raw=99 区分不了 >= 与 ==,这条判据此前零保护
    def test_capped_true_above_soft_cap(self):
        with FixtureServer({"/gn": (200, gnews_body(100))}) as srv:
            entry, _ = events._gnews_one(gnews_cfg(srv), "PHP", ["philstar.com"])
        self.assertTrue(entry["source_capped"])

    # I11b:GDELT 分支的 source_capped 此前零覆盖,改成恒 False 全量仍通过
    def test_gdelt_backfill_capped_flag_is_computed(self):
        full = json.dumps({"articles": [
            {"title": "g%d" % i, "url": "u%d" % i, "domain": "reuters.com",
             "seendate": "20260811T000000Z"} for i in range(events.MAX_RECORDS)]})
        with tempfile.TemporaryDirectory() as tmp, \
                FixtureServer({"/gn": (200, gnews_body(4, domain="bybit.com")),
                               "/doc": (200, full)}) as srv:
            out, _ = events.collect(gnews_cfg(srv, news_sources_path=self._wl(tmp)))
        self.assertEqual(out["PHP"]["channel"], "gdelt")
        self.assertEqual(out["PHP"]["source_cap"], events.MAX_RECORDS)
        self.assertTrue(out["PHP"]["source_capped"])

    def test_gdelt_backfill_not_capped_below_limit(self):
        few = json.dumps({"articles": [
            {"title": "g", "url": "u", "domain": "reuters.com",
             "seendate": "20260811T000000Z"}]})
        with tempfile.TemporaryDirectory() as tmp, \
                FixtureServer({"/gn": (200, gnews_body(4, domain="bybit.com")),
                               "/doc": (200, few)}) as srv:
            out, _ = events.collect(gnews_cfg(srv, news_sources_path=self._wl(tmp)))
        self.assertFalse(out["PHP"]["source_capped"])

    # I1:补位覆写 source_capped 后,主通道已顶到上限的事实不能消失
    def test_gnews_truncation_survives_gdelt_backfill(self):
        few = json.dumps({"articles": [
            {"title": "g", "url": "u", "domain": "reuters.com",
             "seendate": "20260811T000000Z"}]})
        with tempfile.TemporaryDirectory() as tmp, \
                FixtureServer({"/gn": (200, gnews_body(100, domain="bybit.com")),
                               "/doc": (200, few)}) as srv:
            out, _ = events.collect(gnews_cfg(srv, news_sources_path=self._wl(tmp)))
        self.assertTrue(out["PHP"]["gnews_filter"]["capped"])
        self.assertEqual(out["PHP"]["gnews_filter"]["raw"], 100)

    # I3:让脚本算好「有没有可署名来源」,不让 SKILL 的 LLM 自己组合条件
    def test_attributable_source_absent_only_when_nothing_usable(self):
        with tempfile.TemporaryDirectory() as tmp, \
                FixtureServer({"/gn": (200, gnews_body(4, domain="bybit.com"))}) as srv:
            cfg = gnews_cfg(srv, news_sources_path=self._wl(tmp))
            cfg["endpoints"]["gdelt_doc_url"] = DEAD_URL + "/doc"
            out, _ = events.collect(cfg)
        self.assertTrue(out["PHP"]["attributable_source_absent"])

    def test_attributable_flag_false_when_gdelt_backfilled(self):
        """补位成功时该布尔必须为 false —— 否则日报会一边列着 GDELT 条目,
        一边写「昨日未取得可署名来源的报道」,两句自相矛盾。"""
        few = json.dumps({"articles": [
            {"title": "g", "url": "u", "domain": "reuters.com",
             "seendate": "20260811T000000Z"}]})
        with tempfile.TemporaryDirectory() as tmp, \
                FixtureServer({"/gn": (200, gnews_body(4, domain="bybit.com")),
                               "/doc": (200, few)}) as srv:
            out, _ = events.collect(gnews_cfg(srv, news_sources_path=self._wl(tmp)))
        self.assertTrue(out["PHP"]["articles"])
        # assertIs 而非 assertFalse:第三轮(F14)实测,assertFalse(None) 恒真,
        # 「知道取得了」与「没观测过」这两种含义在断言里完全同形
        self.assertIs(out["PHP"]["attributable_source_absent"], False)

    def test_attributable_flag_false_when_main_channel_disabled(self):
        """README 记载的整通道回滚:删掉白名单文件 → gnews 静默停用、GDELT 正常
        取回条目、零 gap。这是完全健康的形态,该字段必须是 false 而不是 null ——
        第二轮把它挂在 gnews_filter 上,于是五币种恒为 null(F10)。"""
        with FixtureServer({"/doc": (200, SAMPLE)}) as srv:
            cfg = make_test_cfg(
                endpoints={"gdelt_doc_url": srv.base_url + "/doc",
                           "gnews_rss_url": srv.base_url + "/gn?q={query}"},
                news_sources_path="/nonexistent/news-sources.json")
            cfg["gdelt_delay_s"] = 0
            out, gaps = events.collect(cfg)
        self.assertEqual(gaps, [])
        for currency in out:
            self.assertTrue(out[currency]["articles"], currency)
            self.assertIs(out[currency]["attributable_source_absent"], False, currency)

    def test_attributable_flag_null_only_when_nothing_collected(self):
        """两条通道都没跑成 → articles 为 None → 不知道,写 null。"""
        with tempfile.TemporaryDirectory() as tmp:
            cfg = make_test_cfg(
                endpoints={"gdelt_doc_url": DEAD_URL + "/doc",
                           "gnews_rss_url": DEAD_URL + "/gn?q={query}"},
                news_sources_path=self._wl(tmp))
            cfg["gdelt_delay_s"] = 0
            out, _ = events.collect(cfg)
        for currency in out:
            self.assertIsNone(out[currency]["articles"], currency)
            self.assertIsNone(out[currency]["attributable_source_absent"], currency)

    # I7/I13:模板写坏不得让 collect() 上抛(采集层硬契约)
    def test_broken_url_template_records_gap_not_raise(self):
        for tpl in ("{query}&num={count}", "{query}&x={}", "{query}&y={"):
            with tempfile.TemporaryDirectory() as tmp, \
                    FixtureServer({"/doc": (200, SAMPLE)}) as srv:
                cfg = make_test_cfg(
                    endpoints={"gnews_rss_url": srv.base_url + "/gn?q=" + tpl,
                               "gdelt_doc_url": srv.base_url + "/doc"},
                    news_sources_path=self._wl(tmp))
                out, gaps = events.collect(cfg)     # 不得抛
            self.assertEqual(sorted(out), ["BRL", "EUR", "PHP", "THB", "USD"], tpl)
            self.assertTrue(all(out[c]["channel"] == "gdelt" for c in out), tpl)
            self.assertTrue(any(g["source"] == "gnews" for g in gaps), tpl)

    def test_missing_gdelt_endpoint_records_gap_not_raise(self):
        cfg = make_test_cfg(endpoints={})
        out, gaps = events.collect(cfg)
        self.assertEqual(out, {})
        self.assertEqual(len(gaps), 5)

    # Minor:白名单项未归一时静默永不命中
    def test_whitelist_entries_are_normalised(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._wl(tmp, '["www.reuters.com", "https://ft.com", ".cnbc.com"]')
            gaps = []
            doms = events._load_domains(make_test_cfg(news_sources_path=path), gaps)
        self.assertEqual(doms, ["reuters.com", "ft.com", "cnbc.com"])
        for host in ("reuters.com", "ft.com", "cnbc.com"):
            self.assertTrue(events._in_whitelist(host, doms), host)


class ReviewRoundThreeTest(unittest.TestCase):
    """第二轮审查的其余幸存项。"""

    def _wl(self, tmp, doms='["philstar.com"]'):
        path = os.path.join(tmp, "wl.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write('{"domains": %s}' % doms)
        return path

    # F7:两条通道都彻底没跑成时,"不知道"不能写成"知道取得了可署名来源"
    def test_attributable_flag_is_null_when_main_channel_never_ran(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = make_test_cfg(
                endpoints={"gnews_rss_url": DEAD_URL + "/gn?q={query}",
                           "gdelt_doc_url": DEAD_URL + "/doc"},
                news_sources_path=self._wl(tmp))
            out, _ = events.collect(cfg)
        self.assertIsNone(out["PHP"]["attributable_source_absent"])

    # F10:_pubdate 的 except 元组漏 OverflowError
    def test_pubdate_overflow_returns_none(self):
        # 实测:年份 999999999 抛 ValueError,9999999999999 才抛 OverflowError
        # (OverflowError 不是 ValueError 子类,漏进 except 元组就会穿透上抛)
        for raw in ("Tue, 11 Aug 9999999999999 03:00:00 GMT",
                    "Tue, 11 Aug 999999999 03:00:00 GMT",
                    "Mon, 01 Jan 99999 00:00:00 +9999"):
            self.assertIsNone(events._pubdate(raw), raw)

    # F10:_gnews_filter 也必须在 try 内 —— 它会碰外部数据
    def test_filter_stage_exception_becomes_gap_not_raise(self):
        with tempfile.TemporaryDirectory() as tmp, \
                FixtureServer({"/gn": (200, gnews_body(3)),
                               "/doc": (200, SAMPLE)}) as srv:
            cfg = gnews_cfg(srv, news_sources_path=self._wl(tmp))
            with mock.patch.object(events, "_gnews_filter",
                                   side_effect=RuntimeError("boom")):
                out, gaps = events.collect(cfg)     # 不得抛
        self.assertTrue(any(g["source"] == "gnews" for g in gaps))
        self.assertEqual(sorted(out), ["BRL", "EUR", "PHP", "THB", "USD"])


if __name__ == "__main__":
    unittest.main()
