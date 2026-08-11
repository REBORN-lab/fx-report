"""采集层共用:urllib 封装 + gap 构造。标准库 only。"""
import gzip
import json
import urllib.request
from datetime import datetime, timezone

DEFAULT_UA = "macro-fx-collector/0.1"


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def fetch_text(url, timeout_s=20):
    req = urllib.request.Request(url, headers={"User-Agent": DEFAULT_UA})
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        raw = resp.read()
    # 先解压再 decode。反过来会让 errors="replace" 把压缩体变成乱码,使
    # "压缩没解开"与"源返回了垃圾"在 gap 里不可区分——静默劣化。
    # 不靠请求侧 Accept-Encoding 协商:实测存在无视该头恒返回 gzip 的源
    # (IBGE calendario,同一 URL 连测 4 次 4/4 仍 gzip)。
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)      # 失败即抛,由调用方转 gap
    return raw.decode("utf-8", errors="replace")


def fetch_json(url, timeout_s=20):
    return json.loads(fetch_text(url, timeout_s))


def make_gap(source, scope, reason):
    return {"source": source, "scope": scope, "reason": reason, "at": now_iso()}
