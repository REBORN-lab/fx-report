"""央行官方公告采集(delta spec: 官方源正常 / 单个官方源失败)。"""
import unittest

from scripts.collect import feeds
from tests.helpers import DEAD_URL, FixtureServer, make_test_cfg


def rss(items):
    body = "".join(
        "<item><title>%s</title><link>%s</link><pubDate>%s</pubDate></item>" % it
        for it in items)
    return '<?xml version="1.0"?><rss version="2.0"><channel>%s</channel></rss>' % body


FED = rss([("Federal Reserve issues FOMC statement", "https://f.gov/1", "Wed, 29 Jul 2026 18:00:00 GMT"),
           ("Board announces approval", "https://f.gov/2", "Tue, 28 Jul 2026 14:00:00 GMT"),
           ("Speech by the Chair", "https://f.gov/3", "Mon, 27 Jul 2026 12:00:00 GMT"),
           ("Fourth item beyond the cap", "https://f.gov/4", "Sun, 26 Jul 2026 12:00:00 GMT")])
ECB = rss([("ECB announces monetary policy decisions", "https://ecb.eu/1", "Thu, 30 Jul 2026 12:45:00 GMT")])


def cfg_with(srv, fed="/fed", ecb="/ecb"):
    return make_test_cfg(endpoints={"fed_press_rss": srv.base_url + fed,
                                    "ecb_press_rss": srv.base_url + ecb})


class FeedsTest(unittest.TestCase):
    def test_both_sources_ok(self):
        with FixtureServer({"/fed": (200, FED), "/ecb": (200, ECB)}) as srv:
            out, gaps = feeds.collect(cfg_with(srv))
        self.assertEqual(gaps, [])
        self.assertEqual(sorted(out), ["EUR", "USD"])
        first = out["USD"][0]
        self.assertEqual(first["title"], "Federal Reserve issues FOMC statement")
        self.assertEqual(first["link"], "https://f.gov/1")
        self.assertEqual(first["issuer"], "Fed")
        self.assertTrue(first["published"])
        self.assertEqual(out["EUR"][0]["issuer"], "ECB")

    def test_item_cap(self):
        with FixtureServer({"/fed": (200, FED), "/ecb": (200, ECB)}) as srv:
            out, _ = feeds.collect(cfg_with(srv))
        self.assertEqual(len(out["USD"]), feeds.MAX_ITEMS)
        self.assertNotIn("Fourth item beyond the cap",
                         [i["title"] for i in out["USD"]])

    def test_single_source_failure_isolated(self):
        with FixtureServer({"/ecb": (200, ECB)}) as srv:
            cfg = cfg_with(srv)
            cfg["endpoints"]["fed_press_rss"] = DEAD_URL + "/fed"
            out, gaps = feeds.collect(cfg)
        self.assertEqual([g["scope"] for g in gaps], ["USD"])
        self.assertEqual(gaps[0]["source"], "feeds")
        self.assertNotIn("USD", out)
        self.assertIn("EUR", out)          # 其余源照常

    def test_non_xml_body_becomes_gap(self):
        with FixtureServer({"/fed": (200, "not xml at all <<<"), "/ecb": (200, ECB)}) as srv:
            out, gaps = feeds.collect(cfg_with(srv))
        self.assertEqual([g["scope"] for g in gaps], ["USD"])
        self.assertIn("unparseable", gaps[0]["reason"])
        self.assertIn("EUR", out)

    def test_items_missing_fields_skipped_not_fatal(self):
        body = ('<?xml version="1.0"?><rss><channel>'
                '<item><link>https://f.gov/x</link></item>'          # 无 title → 跳过
                '<item><title>kept</title><link>https://f.gov/y</link></item>'
                '</channel></rss>')
        with FixtureServer({"/fed": (200, body), "/ecb": (200, ECB)}) as srv:
            out, gaps = feeds.collect(cfg_with(srv))
        self.assertEqual(gaps, [])
        self.assertEqual([i["title"] for i in out["USD"]], ["kept"])

    def test_empty_channel_records_gap_not_silent_zero(self):
        """健康 feed 恒有条目;零条目是异常,必须记 gap 而非静默写空。"""
        body = '<?xml version="1.0"?><rss><channel></channel></rss>'
        with FixtureServer({"/fed": (200, body), "/ecb": (200, ECB)}) as srv:
            out, gaps = feeds.collect(cfg_with(srv))
        self.assertEqual([g["scope"] for g in gaps], ["USD"])
        self.assertNotIn("USD", out)

    def test_unconfigured_source_is_skipped_silently(self):
        """未配置 = 有意停用(spec:不可达的源不写进配置),不得记 gap ——
        否则每份快照都带永久噪音,淹没真正的采集失败。"""
        out, gaps = feeds.collect(make_test_cfg(endpoints={}))
        self.assertEqual(out, {})
        self.assertEqual(gaps, [])

    def test_configured_source_still_reports_failure(self):
        """已配置但请求失败 → 必须记 gap(与"未配置"区分开)。"""
        cfg = make_test_cfg(endpoints={"fed_press_rss": DEAD_URL + "/fed"})
        out, gaps = feeds.collect(cfg)
        self.assertEqual([g["scope"] for g in gaps], ["USD"])



class NamespacedFeedTest(unittest.TestCase):
    """源改版成带默认命名空间的 RDF/Atom 时,root.iter("item") 取不到条目 ——
    必须记 gap,否则与"未配置"的静默归零无法区分(delta spec: 解析成功但无条目)。"""

    RDF = ('<?xml version="1.0"?>'
           '<rdf:RDF xmlns="http://purl.org/rss/1.0/" '
           'xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
           '<item><title>ns item</title></item></rdf:RDF>')

    def test_zero_items_records_gap(self):
        with FixtureServer({"/fed": (200, self.RDF), "/ecb": (200, ECB)}) as srv:
            out, gaps = feeds.collect(cfg_with(srv))
        self.assertEqual([g["scope"] for g in gaps], ["USD"])
        self.assertIn("no <item> found", gaps[0]["reason"])
        self.assertNotIn("USD", out)
        self.assertIn("EUR", out)      # 其余源不受影响

if __name__ == "__main__":
    unittest.main()
