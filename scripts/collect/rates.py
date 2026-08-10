"""汇率双源采集:Frankfurter 主源 + exchange-api 交叉校验。"""
from . import util

CURRENCIES = ["PHP", "THB", "BRL", "EUR"]
SUSPECT_THRESHOLD_PCT = 0.5  # 偏差 = |主-副|/主 ×100,超过即 suspect


def collect(cfg):
    gaps = []
    primary, primary_ok = _fetch_primary(cfg, gaps)
    secondary, secondary_ok = _fetch_secondary(cfg, gaps)
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
            if p == 0:
                gaps.append(util.make_gap("frankfurter", c, "primary=0, deviation skipped"))
            else:
                dev = abs(p - s) / p * 100.0
                entry["deviation_pct"] = round(dev, 3)
                entry["suspect"] = dev > SUSPECT_THRESHOLD_PCT
        elif p is None and s is None:
            entry["primary_source"] = None
            # 双源整体失败时已各有 scope="all" 的 gap,不再逐币种重复记;
            # 仅当两源本轮都成功返回、却仍缺该币种字段时才补记。
            if primary_ok and secondary_ok and not any(g["scope"] == c for g in gaps):
                gaps.append(util.make_gap("rates", c, "missing in both sources"))
        out[c] = entry
    return out, gaps


def _fetch_primary(cfg, gaps):
    url = cfg["endpoints"]["frankfurter_url"].format(date=cfg["date"])
    try:
        doc = util.fetch_json(url, cfg["timeout_s"])
    except Exception as e:
        gaps.append(util.make_gap("frankfurter", "all", "%s: %s" % (type(e).__name__, e)))
        return {}, False
    got = doc.get("rates") or {}
    out = {}
    for c in CURRENCIES:
        if c not in got:
            continue
        try:
            out[c] = float(got[c])
        except (TypeError, ValueError) as e:
            gaps.append(util.make_gap("frankfurter", c, "%s: %s" % (type(e).__name__, e)))
    return out, True


def _secondary_date(date_str):
    """exchange-api 的 {date} 版本号。

    实测(2026-08-10,见 commit message):jsdelivr 与 pages.dev 均直接接受
    YYYY-MM-DD 形态的版本号(如 @2026-08-08、2026-08-08.currency-api.pages.dev),
    与点分形态(2026.8.8)等价返回同一数据,故此处保持恒等映射,无需转换。
    """
    return date_str


def _fetch_secondary(cfg, gaps):
    errs = []
    ok = False
    for tpl in cfg["endpoints"]["exchange_api_urls"]:
        url = tpl.format(date=_secondary_date(cfg["date"]))
        try:
            doc = util.fetch_json(url, cfg["timeout_s"])
        except Exception as e:
            errs.append("%s: %s" % (type(e).__name__, e))
            continue
        ok = True
        usd = doc.get("usd") or {}
        got = {}
        for c in CURRENCIES:
            key = c.lower()
            if key not in usd:
                continue
            try:
                got[c] = float(usd[key])
            except (TypeError, ValueError) as e:
                gaps.append(util.make_gap("exchange-api", c, "%s: %s" % (type(e).__name__, e)))
        if got:
            return got, ok
        errs.append("empty usd map")
    gaps.append(util.make_gap("exchange-api", "all", "; ".join(errs) if errs else "unknown error"))
    return {}, ok


def _prev_primary(cfg):
    snap = cfg.get("prev_snapshot") or {}
    out = {}
    for c, entry in (snap.get("rates") or {}).items():
        if isinstance(entry, dict) and entry.get("primary") is not None:
            out[c] = entry["primary"]
    return out
