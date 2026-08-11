"""util 取数封装:压缩兜底与自定义请求头。"""
import gzip
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


if __name__ == "__main__":
    unittest.main()
