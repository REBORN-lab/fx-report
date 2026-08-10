import json
import unittest
import urllib.request
import urllib.error

from tests.helpers import FixtureServer


class FixtureServerTest(unittest.TestCase):
    def test_static_route(self):
        with FixtureServer({"/a": (200, json.dumps({"x": 1}))}) as srv:
            body = urllib.request.urlopen(srv.base_url + "/a?q=1").read()
        self.assertEqual(json.loads(body), {"x": 1})

    def test_callable_route_and_404(self):
        seen_paths = []

        def dyn(handler):
            seen_paths.append(handler.path)
            return (500, "boom") if "bad" in handler.path else (200, "ok")

        with FixtureServer({"/d": dyn}) as srv:
            self.assertEqual(urllib.request.urlopen(srv.base_url + "/d").read(), b"ok")
            with self.assertRaises(urllib.error.HTTPError):
                urllib.request.urlopen(srv.base_url + "/d/bad")
            with self.assertRaises(urllib.error.HTTPError):
                urllib.request.urlopen(srv.base_url + "/none")
            urllib.request.urlopen(srv.base_url + "/d?flag=zz").read()
        self.assertTrue(
            any("flag=zz" in p for p in seen_paths),
            "handler.path 应包含 query string,供 Task 6 依赖的透传断言",
        )


if __name__ == "__main__":
    unittest.main()
