"""宏观指标采集:DBnomics 主体 + FRED release dates 可选增强(零 key 默认路径)。"""
from . import util


def collect(cfg):
    gaps, indicators = [], []
    for ind in cfg["indicators"]:
        try:
            url = cfg["endpoints"]["dbnomics_series_url"].format(series_id=ind["series_id"])
            doc = util.fetch_json(url, cfg["timeout_s"])
            value, prev, period = _last_two(doc)
            indicators.append({
                "economy": ind["economy"], "indicator": ind["indicator"],
                "series_id": ind["series_id"], "value": value, "prev": prev,
                "period": period,
                "is_new_release": _is_new(cfg, ind["series_id"], period),
            })
        except Exception as e:
            gaps.append(util.make_gap("dbnomics", ind["series_id"],
                                      "%s: %s" % (type(e).__name__, e)))
    return {"indicators": indicators, "us_release_dates": _fred(cfg, gaps)}, gaps


def _last_two(doc):
    """解析 DBnomics series.docs[0].period/value 平行数组(形态经 Task 5 探针实测)。

    形态不符时抛 ValueError,由 collect() 捕获转该 series 的 dbnomics gap。
    外部数据每次取值前过 isinstance 门(仓库约定,禁止 `or {}` 惯用法)。
    """
    if not isinstance(doc, dict):
        raise ValueError("unexpected response shape: %s" % type(doc).__name__)
    series = doc.get("series")
    if not isinstance(series, dict):
        raise ValueError("unexpected 'series' shape: %s" % type(series).__name__)
    docs = series.get("docs")
    if not isinstance(docs, list) or not docs:
        raise ValueError("'series.docs' missing or empty")
    d = docs[0]
    if not isinstance(d, dict):
        raise ValueError("unexpected doc shape: %s" % type(d).__name__)
    periods, values = d.get("period"), d.get("value")
    if not isinstance(periods, list) or not isinstance(values, list):
        raise ValueError("'period'/'value' are not parallel arrays")
    pairs = [(p, v) for p, v in zip(periods, values)
             if isinstance(v, (int, float))]
    if not pairs:
        raise ValueError("series has no numeric observations")
    period, value = pairs[-1]
    prev = pairs[-2][1] if len(pairs) >= 2 else None
    return value, prev, period


def _is_new(cfg, series_id, period):
    snap = cfg.get("prev_snapshot")
    if not isinstance(snap, dict):
        snap = {}
    rows = snap.get("macro")
    if not isinstance(rows, list):
        rows = []
    for row in rows:
        if isinstance(row, dict) and row.get("series_id") == series_id:
            return row.get("period") != period
    return False


def _fred(cfg, gaps):
    key = cfg.get("fred_api_key")
    if not key:
        return None  # 零 key 默认路径:不调用、不记缺漏(spec Scenario)
    url = ("%s?api_key=%s&file_type=json&realtime_start=%s&realtime_end=%s"
           % (cfg["endpoints"]["fred_release_dates_url"], key,
              cfg["yesterday"], cfg["yesterday"]))
    try:
        doc = util.fetch_json(url, cfg["timeout_s"])
        if not isinstance(doc, dict):
            raise ValueError("unexpected response shape: %s" % type(doc).__name__)
        rows = doc.get("release_dates")
        if not isinstance(rows, list):
            raise ValueError("unexpected 'release_dates' shape: %s" % type(rows).__name__)
        names = []
        for r in rows:
            if not isinstance(r, dict):
                raise ValueError("unexpected release entry shape: %s" % type(r).__name__)
            name = r.get("release_name")
            if not isinstance(name, str) or not name:
                name = str(r.get("release_id"))
            names.append(name)
        return names
    except Exception as e:
        gaps.append(util.make_gap("fred", "us-release-dates",
                                  "%s: %s" % (type(e).__name__, e)))
        return None
