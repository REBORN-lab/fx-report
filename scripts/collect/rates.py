"""汇率双源采集:Frankfurter 主源 + exchange-api 交叉校验。"""
from . import util

CURRENCIES = ["PHP", "THB", "BRL", "EUR"]
SUSPECT_THRESHOLD_PCT = 0.5  # 偏差 = |主-副|/主 ×100,超过即 suspect


def collect(cfg):
    gaps = []
    primary = _fetch_primary(cfg, gaps)
    secondary = _fetch_secondary(cfg, gaps)
    prev = _prev_primary(cfg)
    out = {}
    for c in CURRENCIES:
        p, s = primary.get(c), secondary.get(c)
        entry = {"primary": p, "secondary": s, "primary_source": "frankfurter",
                 "deviation_pct": None, "suspect": False, "prev_primary": prev.get(c)}
        if p is None and s is not None:
            entry["primary"] = s
            entry["primary_source"] = "exchange-api"
        elif p is not None and s is not None:
            dev = abs(p - s) / p * 100.0
            entry["deviation_pct"] = round(dev, 3)
            entry["suspect"] = dev > SUSPECT_THRESHOLD_PCT
        out[c] = entry
    return out, gaps


def _fetch_primary(cfg, gaps):
    url = cfg["endpoints"]["frankfurter_url"].format(date=cfg["date"])
    try:
        doc = util.fetch_json(url, cfg["timeout_s"])
        got = doc.get("rates", {})
        return {c: float(got[c]) for c in CURRENCIES if c in got}
    except Exception as e:
        gaps.append(util.make_gap("frankfurter", "all", "%s: %s" % (type(e).__name__, e)))
        return {}


def _secondary_date(date_str):
    """exchange-api 的 {date} 版本号。

    实测(2026-08-10,见 commit message):jsdelivr 与 pages.dev 均直接接受
    YYYY-MM-DD 形态的版本号(如 @2026-08-08、2026-08-08.currency-api.pages.dev),
    与点分形态(2026.8.8)等价返回同一数据,故此处保持恒等映射,无需转换。
    """
    return date_str


def _fetch_secondary(cfg, gaps):
    last_err = None
    for tpl in cfg["endpoints"]["exchange_api_urls"]:
        url = tpl.format(date=_secondary_date(cfg["date"]))
        try:
            doc = util.fetch_json(url, cfg["timeout_s"])
            usd = doc.get("usd", {})
            got = {c: float(usd[c.lower()]) for c in CURRENCIES if c.lower() in usd}
            if got:
                return got
            last_err = ValueError("empty usd map")
        except Exception as e:
            last_err = e
    gaps.append(util.make_gap("exchange-api", "all",
                              "%s: %s" % (type(last_err).__name__, last_err)))
    return {}


def _prev_primary(cfg):
    snap = cfg.get("prev_snapshot") or {}
    out = {}
    for c, entry in (snap.get("rates") or {}).items():
        if isinstance(entry, dict) and entry.get("primary") is not None:
            out[c] = entry["primary"]
    return out
