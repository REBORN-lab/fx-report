"""采集层共用:urllib 封装 + gap 构造。标准库 only。"""
import gzip
import json
import urllib.request
from datetime import datetime, timezone

# 自报家门:项目名 + 可联系的出处。**永不**写 Mozilla/... 或 Googlebot ——
# 伪装成浏览器或搜索引擎爬虫,是在规避源站按 UA 作出的准入判断,与"尊重
# robots.txt、不绕过封锁"是同一条纪律。源站要能查到我们是谁、找谁反映。
DEFAULT_UA = "fx-macro-report/1.0 (+https://github.com/REBORN-lab/macro)"


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def fetch_text(url, timeout_s=20, headers=None, data=None):
    """data 非 None 时发 POST(PXWeb 只接受 POST + JSON 查询体)。

    data 必须是 bytes:交给 urllib 一个 str 会当场抛 TypeError,而把编码
    留给调用方是有意的——查询体的字符集由端点约定,不该在这里替它猜。
    """
    hdrs = {"User-Agent": DEFAULT_UA}
    hdrs.update(headers or {})          # 调用方可覆盖 UA,语义明确
    req = urllib.request.Request(url, data=data, headers=hdrs)
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        raw = resp.read()
    # 先解压再 decode。反过来会让 errors="replace" 把压缩体变成乱码,使
    # "压缩没解开"与"源返回了垃圾"在 gap 里不可区分——静默劣化。
    # 不靠请求侧 Accept-Encoding 协商:实测存在无视该头恒返回 gzip 的源
    # (IBGE calendario,同一 URL 连测 4 次 4/4 仍 gzip)。
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)      # 失败即抛,由调用方转 gap
    return raw.decode("utf-8", errors="replace")


def fetch_json(url, timeout_s=20, headers=None, data=None):
    return json.loads(fetch_text(url, timeout_s, headers, data))


def make_gap(source, scope, reason):
    return {"source": source, "scope": scope, "reason": reason, "at": now_iso()}
