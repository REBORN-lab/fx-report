"""测试基建:本地 fixture HTTP 服务器与测试配置构造。零第三方依赖。"""
import http.server
import json
import os
import threading

# 指向必然连接失败的地址,模拟"端点不可用"
DEAD_URL = "http://127.0.0.1:9"


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        for prefix, resp in self.server.fixture_routes.items():
            if self.path.startswith(prefix):
                status, body = resp(self) if callable(resp) else resp
                # bytes 直通:gzip 兜底测试要发原始压缩字节,不能过 UTF-8 编码
                data = body if isinstance(body, bytes) else body.encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
        self.send_response(404)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *args):  # 静音测试输出
        pass


class FixtureServer:
    """with FixtureServer({"/frank": (200, '{"rates":{}}')}) as srv: srv.base_url

    路由按 dict 插入顺序取第一个前缀命中;注册互为前缀的路由时把更具体的放前面。
    """

    def __init__(self, routes):
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self.httpd.fixture_routes = routes
        self.thread = threading.Thread(
            target=lambda: self.httpd.serve_forever(poll_interval=0.05), daemon=True
        )

    @property
    def base_url(self):
        return "http://127.0.0.1:%d" % self.httpd.server_address[1]

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()


def make_test_cfg(**over):
    """采集模块单测用 cfg;延时全 0,线上 URL 全空,由测试逐项覆盖。"""
    cfg = {
        "date": "2026-08-10",
        "yesterday": "2026-08-09",
        "backfill": False,
        "endpoints": {},
        "indicators": [],
        "calendar_path": None,
        "prev_snapshot": None,
        "fred_api_key": None,
        "gdelt_delay_s": 0,
        "gdelt_backoff_s": 0,
        "timeout_s": 5,
        "data_dir": None,
    }
    cfg.update(over)
    return cfg


def make_test_root(tmp, endpoints, indicators=None, calendar=None):
    """聚合/故障注入测试用:构造带 config/ state/ data/ 的临时仓库根。"""
    for d in ("config", "state", "data", "briefs"):
        os.makedirs(os.path.join(tmp, d), exist_ok=True)
    with open(os.path.join(tmp, "config", "endpoints.json"), "w", encoding="utf-8") as f:
        json.dump(endpoints, f)
    with open(os.path.join(tmp, "config", "indicators.json"), "w", encoding="utf-8") as f:
        json.dump(indicators or [], f)
    cal = calendar or {"valid_until": "2099-01-01", "sources": [], "events": []}
    with open(os.path.join(tmp, "state", "calendar-2026.json"), "w", encoding="utf-8") as f:
        json.dump(cal, f, ensure_ascii=False)
    return tmp
