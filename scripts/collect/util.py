"""采集层共用:urllib 封装 + gap 构造。标准库 only。"""
import json
import urllib.request
from datetime import datetime, timezone


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def fetch_text(url, timeout_s=20):
    req = urllib.request.Request(url, headers={"User-Agent": "macro-fx-collector/0.1"})
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        return resp.read().decode("utf-8", errors="replace")


def fetch_json(url, timeout_s=20):
    return json.loads(fetch_text(url, timeout_s))


def make_gap(source, scope, reason):
    return {"source": source, "scope": scope, "reason": reason, "at": now_iso()}
