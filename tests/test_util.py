"""util 取数封装:压缩兜底与自定义请求头。"""
import gzip
import json
import unittest

from scripts.collect import util
from tests.helpers import FixtureServer


class BytesFixtureTest(unittest.TestCase):
    def test_fixture_server_can_serve_raw_bytes(self):
        """gzip 测试需要发原始字节,而非 UTF-8 编码的字符串。"""
        blob = gzip.compress("你好".encode("utf-8"))
        with FixtureServer({"/z": (200, blob)}) as srv:
            text = util.fetch_text(srv.base_url + "/z")
        self.assertEqual(text, "你好")


class GzipFallbackTest(unittest.TestCase):
    """源无视 Accept-Encoding 恒返回 gzip 是实测存在的形态(IBGE)。
    以有损解码读压缩体会产出乱码,使"压缩没解开"与"源返回垃圾"在 gap 里
    不可区分——属静默劣化,必须改成解压或抛错两条明路。"""

    def test_gzip_body_is_decompressed(self):
        blob = gzip.compress(b'{"ok": 1}')
        with FixtureServer({"/z": (200, blob)}) as srv:
            self.assertEqual(util.fetch_json(srv.base_url + "/z"), {"ok": 1})

    def test_corrupt_gzip_raises_instead_of_returning_mojibake(self):
        blob = b"\x1f\x8b" + b"garbage" * 4       # 魔数对,内容坏
        with FixtureServer({"/z": (200, blob)}) as srv:
            with self.assertRaises(Exception) as ctx:
                util.fetch_text(srv.base_url + "/z")
        self.assertNotIsInstance(ctx.exception, UnicodeDecodeError)

    def test_plain_body_unchanged(self):
        with FixtureServer({"/p": (200, '{"ok": 2}')}) as srv:
            self.assertEqual(util.fetch_json(srv.base_url + "/p"), {"ok": 2})

    def test_empty_body_does_not_crash(self):
        with FixtureServer({"/e": (200, b"")}) as srv:
            self.assertEqual(util.fetch_text(srv.base_url + "/e"), "")
class HeadersTest(unittest.TestCase):
    """后续 Eurostat 需 Referer + X-Requested-With,BSP 需 Accept 头。
    默认 UA 打底、调用方可覆盖。"""

    def _echo_server(self):
        def handler(req):
            seen = {k.lower(): v for k, v in req.headers.items()}
            return 200, json.dumps({"ua": seen.get("user-agent"),
                                    "referer": seen.get("referer")})
        return FixtureServer({"/h": handler})

    def test_default_ua_when_no_headers(self):
        with self._echo_server() as srv:
            got = util.fetch_json(srv.base_url + "/h")
        self.assertEqual(got["ua"], util.DEFAULT_UA)
        self.assertIsNone(got["referer"])

    def test_extra_headers_are_sent(self):
        with self._echo_server() as srv:
            got = util.fetch_json(srv.base_url + "/h", headers={"Referer": "https://x/"})
        self.assertEqual(got["ua"], util.DEFAULT_UA)      # 默认 UA 仍在
        self.assertEqual(got["referer"], "https://x/")

    def test_caller_can_override_ua(self):
        with self._echo_server() as srv:
            got = util.fetch_json(srv.base_url + "/h", headers={"User-Agent": "probe/9"})
        self.assertEqual(got["ua"], "probe/9")


class UserAgentComplianceTest(unittest.TestCase):
    """UA 必须自报家门:项目名 + 可联系的出处。

    仓库已裁定的合规约束(与"尊重 robots.txt、不绕过封锁"同一条纪律):
    伪装成浏览器或搜索引擎爬虫,是在**规避**源站按 UA 作出的准入判断。
    源站看到 `Mozilla/...` 无法把我们与真人区分,看到 `Googlebot` 会给出
    它本不打算给我们的待遇——两者都让对方失去拒绝我们的能力。
    """

    FORBIDDEN = ("Mozilla", "Googlebot", "bingbot", "AppleWebKit",
                 "Chrome", "Safari", "Gecko")

    def test_ua_never_impersonates_browser_or_search_crawler(self):
        for token in self.FORBIDDEN:
            self.assertNotIn(token.lower(), util.DEFAULT_UA.lower(), token)

    def test_ua_carries_project_name_and_contact_url(self):
        """光有一个不像浏览器的名字不够:源站要能查到我们是谁、找谁反映。"""
        self.assertIn("fx-macro-report", util.DEFAULT_UA)
        self.assertIn("https://github.com/REBORN-lab/macro", util.DEFAULT_UA)

    def test_ua_actually_sent_on_the_wire(self):
        """常量对了但没发出去等于没有——钉住实际请求头。"""
        def handler(req):
            return 200, json.dumps({"ua": req.headers.get("User-Agent")})
        with FixtureServer({"/h": handler}) as srv:
            got = util.fetch_json(srv.base_url + "/h")
        self.assertEqual(got["ua"], util.DEFAULT_UA)
        self.assertIn("fx-macro-report", got["ua"])


class PostBodyTest(unittest.TestCase):
    """PXWeb(PSA)只接受 POST + JSON 查询体,GET 拿不到数据。"""

    def test_data_makes_it_a_post_and_body_arrives_intact(self):
        def handler(req):
            return 200, json.dumps({"method": req.command,
                                    "body": req.request_body.decode("utf-8")})
        with FixtureServer({"/px": handler}) as srv:
            got = util.fetch_json(srv.base_url + "/px", data=b'{"q":1}')
        self.assertEqual(got["method"], "POST")
        self.assertEqual(got["body"], '{"q":1}')

    def test_without_data_it_stays_a_get(self):
        """默认路径必须一个字节都不变——十几个既有源全走 GET。"""
        def handler(req):
            return 200, json.dumps({"method": req.command})
        with FixtureServer({"/g": handler}) as srv:
            got = util.fetch_json(srv.base_url + "/g")
        self.assertEqual(got["method"], "GET")

    def test_ua_still_sent_on_post(self):
        """自报家门的纪律不因换了动词就失效。"""
        def handler(req):
            return 200, json.dumps({"ua": req.headers.get("User-Agent")})
        with FixtureServer({"/px": handler}) as srv:
            got = util.fetch_json(srv.base_url + "/px", data=b"{}")
        self.assertEqual(got["ua"], util.DEFAULT_UA)


if __name__ == "__main__":
    unittest.main()
