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


if __name__ == "__main__":
    unittest.main()
