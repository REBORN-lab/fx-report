"""宏观指标采集:BIS 直连主体 + BLS 美国 CPI 主源 + DBnomics 回落 + FRED 可选增强。

来源优先级 BLS > BIS > DBnomics。DBnomics 是 IMF/BIS 的**镜像**,实测滞后
8–17 个月且政策利率给出过期值(2026-08-11 实测五个经济体全错),故对它上游
本来就是 BIS 的那些序列改为直连——这是去掉中间商,不是换源。
"""
import csv
import io
import math
import re

from . import util

PERIOD_RE = re.compile(r"^(\d{4})-(\d{2})")
US_CPI = ("US", "CPI 同比")


BIS_REQUIRED_COLS = ("REF_AREA", "TIME_PERIOD", "OBS_VALUE")


def _obs_value(raw):
    """BIS 的非交易日写字符串 "NaN"。必须在**转 float 之前**按字符串判掉——
    float("NaN") 会成功,随后 NaN 的任何比较都是 False,会让"取最新非 NaN"
    与"找上一个不同值"同时给出错误结果。实测也有 "1" 这种无小数点形态。"""
    s = (raw or "").strip()
    if not s or s.upper() == "NAN":
        return None
    try:
        v = float(s)
    except ValueError:
        return None
    return v if math.isfinite(v) else None


def _bis_parse(text):
    """BIS CSV → {REF_AREA: [(period, value), ...]},按 period 升序。

    按列名取,不按位置:两个 dataflow 的列集合本就不同(CPI 多 UNIT_MEASURE),
    且 SDMX 版本升级改列序时按位置取不会报错,只会静默取错列。
    """
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    cols = reader.fieldnames or []
    missing = [c for c in BIS_REQUIRED_COLS if c not in cols]
    if missing:
        raise ValueError("BIS CSV 缺列 %s(实际:%s)"
                         % (",".join(missing), ",".join(cols)))
    out = {}
    for row in reader:
        value = _obs_value(row.get("OBS_VALUE"))
        if value is None:
            continue
        area, period = row.get("REF_AREA"), row.get("TIME_PERIOD")
        if not (isinstance(area, str) and area and isinstance(period, str) and period):
            continue
        out.setdefault(area, []).append((period, value))
    for obs in out.values():
        obs.sort()
    return out


def _latest_and_prev_observation(obs):
    """月频序列:prev 取上一个观测。相邻月份即便同值也是两次独立发布。"""
    if not obs:
        return None, None, None, None
    period, value = obs[-1]
    if len(obs) < 2:
        return value, period, None, None
    prev_period, prev = obs[-2]
    return value, period, prev, prev_period


def _latest_and_prev_distinct(obs):
    """日频序列:prev 取上一个**与当前值不同**的水平,及**该水平的末日**。

    取"上一个观测"会恒等于当前值(政策利率绝大多数日子不变),对报告零信息。
    窗口内始终未变动时 prev 为 None —— 绝不等于 value,等值会被读成"持平",
    而事实是"回溯窗口内没看到变动"。取末日是因为要说的是"上次变动前是 A,
    一直到 X 日"。
    """
    if not obs:
        return None, None, None, None
    period, value = obs[-1]
    for prev_period, prev in reversed(obs[:-1]):
        if prev != value:
            return value, period, prev, prev_period
    return value, period, None, None


# BIS 用 XM 表示欧元区,仓库内部用 EA。写死映射,不做字符串启发式。
BIS_AREA = {"US": "US", "EA": "XM", "PH": "PH", "TH": "TH", "BR": "BR"}
# (指标名, 端点配置键, dataflow 名, 前值口径)
BIS_DATAFLOWS = (
    ("政策利率", "bis_cbpol_url", "WS_CBPOL", "distinct"),
    ("CPI 同比", "bis_cpi_url", "WS_LONG_CPI", "observation"),
)


def _bis_table(cfg, gaps):
    """返回 {(economy, indicator): row}。

    批量取数(两次 GET 覆盖五经济体)但**逐指标**可缺席:某经济体没进表,
    调用方查不到就自然回落 DBnomics。三种降级路径(整体失败 / 缺必需列 /
    缺某经济体)因此共用同一条代码路径,不需要额外分支。

    任何失败都记 gap 并让受影响指标缺席,绝不上抛(采集层硬契约)。
    """
    endpoints = cfg.get("endpoints")
    endpoints = endpoints if isinstance(endpoints, dict) else {}
    out = {}
    for indicator, key, dataflow, prev_mode in BIS_DATAFLOWS:
        url = endpoints.get(key)
        if not isinstance(url, str) or not url:
            continue        # 未配置 = 有意停用(与 feeds.py 同约定),删 URL 即回滚
        try:
            by_area = _bis_parse(util.fetch_text(url, cfg["timeout_s"]))
        except Exception as e:
            gaps.append(util.make_gap("bis", dataflow,
                                      "%s: %s" % (type(e).__name__, e)))
            continue
        pick = (_latest_and_prev_distinct if prev_mode == "distinct"
                else _latest_and_prev_observation)
        for economy, area in BIS_AREA.items():
            value, period, prev, prev_period = pick(by_area.get(area) or [])
            if value is None:
                continue    # 该经济体缺席或全 NaN → 只有它回落
            out[(economy, indicator)] = {
                "value": value, "prev": prev, "period": period,
                "prev_period": prev_period, "source": "bis",
                "series_id": "BIS/%s/%s" % (dataflow, area),
            }
    return out


def collect(cfg):
    gaps, indicators = [], []
    tracked = [(i.get("economy"), i.get("indicator")) for i in cfg["indicators"]]
    # 没跟踪美国 CPI 就别打 BLS 这一枪(也就不会为未跟踪指标记 gap)
    bls_row = _bls_us_cpi(cfg, gaps) if US_CPI in tracked else None
    for ind in cfg["indicators"]:
        if bls_row is not None and (ind["economy"], ind["indicator"]) == US_CPI:
            # BLS 比 DBnomics 镜像新约 11 个月(2026-08-11 实测),优先用它;
            # 拿到就不再打 DBnomics 这一枪。series_id 写 BLS 的真实出处——
            # 它是快照里唯一可回溯到源的字段,写成 IMF 的 id 会让复核者拿到
            # 完全不同的数,反而像脚本算错了。
            row = dict(bls_row, economy=ind["economy"], indicator=ind["indicator"],
                       is_new_release=_is_new(cfg, bls_row["series_id"],
                                              bls_row["period"]),
                       lag_months=lag_months(bls_row["period"], cfg["date"]))
            indicators.append(_mark_source_change(cfg, ind, row))
            continue
        try:
            url = cfg["endpoints"]["dbnomics_series_url"].format(series_id=ind["series_id"])
            doc = util.fetch_json(url, cfg["timeout_s"])
            value, prev, period = _last_two(doc)
            indicators.append(_mark_source_change(cfg, ind, {
                "economy": ind["economy"], "indicator": ind["indicator"],
                "series_id": ind["series_id"], "value": value, "prev": prev,
                "period": period, "source": "dbnomics",
                "is_new_release": _is_new(cfg, ind["series_id"], period),
                "lag_months": lag_months(period, cfg["date"]),
            }))
        except Exception as e:
            gaps.append(util.make_gap("dbnomics", ind["series_id"],
                                      "%s: %s" % (type(e).__name__, e)))
    return {"indicators": indicators, "us_release_dates": _fred(cfg, gaps)}, gaps


def lag_months(period, date_str):
    """期号相对快照日期的滞后月数。滞后不披露就等于隐形——DBnomics 镜像实测
    滞后 219–498 天,报告却把它当"最新值"引用。无法解析(如季度期号)→ None,不猜。"""
    m = PERIOD_RE.match(period) if isinstance(period, str) else None
    d = PERIOD_RE.match(date_str) if isinstance(date_str, str) else None
    if m is None or d is None:
        return None
    py, pm = int(m.group(1)), int(m.group(2))
    dy, dm = int(d.group(1)), int(d.group(2))
    if not (1 <= pm <= 12 and 1 <= dm <= 12):
        return None
    return (dy - py) * 12 + (dm - pm)


def _bls_us_cpi(cfg, gaps):
    """美国 CPI 走 BLS 公共 API(零 key)。返回的是指数点位,同比由本函数
    按**同月同比**确定性计算——相邻月份近似会得出可信但错误的同比,禁用。

    未配置端点 → 静默走 DBnomics(有意停用,非缺漏);配置了但失败 → 记 gap 后回落。
    """
    endpoints = cfg.get("endpoints")
    url = endpoints.get("bls_timeseries_url") if isinstance(endpoints, dict) else None
    if not isinstance(url, str) or not url:
        return None
    try:
        doc = util.fetch_json(url, cfg["timeout_s"])
        rows = _bls_rows(doc)
        by_key = {}
        for r in rows:
            year, period, value = r.get("year"), r.get("period"), r.get("value")
            if not (isinstance(year, str) and isinstance(period, str)):
                continue
            try:
                by_key[(year, period)] = float(value)
            except (TypeError, ValueError):
                continue
        latest = _bls_latest(by_key)
        if latest is None:
            raise ValueError("no numeric observation")
        (year, period), value = latest
        yoy = _yoy(by_key, year, period, value)
        # 前值(上月同比)在同一份响应里就能算(实测单次返回 3 个日历年);
        # 留 None 会让报告模板的"前值"空着,诱导 LLM 自找基准
        prev_key = _prev_month(year, period)
        prev_value = by_key.get(prev_key) if prev_key else None
        prev_yoy = (_yoy(by_key, prev_key[0], prev_key[1], prev_value, strict=False)
                    if prev_key and prev_value is not None else None)
        return {"value": yoy, "prev": prev_yoy,
                "period": "%s-%02d" % (year, int(period[1:])),
                "source": "bls", "series_id": _bls_series_id(url)}
    except Exception as e:
        gaps.append(util.make_gap("bls", "US/CPI 同比", "%s: %s" % (type(e).__name__, e)))
        return None


def _bls_rows(doc):
    if not isinstance(doc, dict):
        raise ValueError("unexpected response shape: %s" % type(doc).__name__)
    results = doc.get("Results")
    if not isinstance(results, dict):
        raise ValueError("unexpected 'Results' shape: %s" % type(results).__name__)
    series = results.get("series")
    if not isinstance(series, list) or not series:
        raise ValueError("'Results.series' missing or empty")
    first = series[0]
    if not isinstance(first, dict):
        raise ValueError("unexpected series shape: %s" % type(first).__name__)
    data = first.get("data")
    if not isinstance(data, list):
        raise ValueError("unexpected 'data' shape: %s" % type(data).__name__)
    return [r for r in data if isinstance(r, dict)]


def _yoy(by_key, year, period, value, strict=True):
    """同月同比。相邻月份近似会给出可信但错误的同比,故基期缺失即失败/记 None。"""
    base = by_key.get((str(int(year) - 1), period))
    if base is None:
        if strict:
            raise ValueError("same-month base for %s-%s missing "
                             "(近似月份会给出可信但错误的同比,拒绝)" % (year, period))
        return None
    if base == 0:
        if strict:
            raise ValueError("same-month base is zero")
        return None
    return round((value / base - 1) * 100, 3)


def _prev_month(year, period):
    month = int(period[1:])
    if month > 1:
        return (year, "M%02d" % (month - 1))
    return (str(int(year) - 1), "M12")


def _bls_series_id(url):
    """从端点 URL 取真实 series id,落盘作可回溯出处(不能沿用 IMF 的 id)。"""
    tail = url.split("?")[0].rstrip("/").rsplit("/", 1)[-1]
    return "BLS/%s" % tail if tail else "BLS"


def _mark_source_change(cfg, ind, row):
    """换源当日期号会跳变,与前值不可比;不标出来,报告会把口径切换叙述成
    "通胀升高"(2026-08-11 实际发生过)。两个方向都要标——BLS 挂掉回落
    DBnomics 是更常见的那个方向,漏标即同型事故。"""
    changed_from = _source_changed_from(cfg, ind, row.get("source"))
    if changed_from is not None:
        row["source_changed_from"] = changed_from
        row["is_new_release"] = False   # 期号跳变来自换源,不是新发布
    return row


def _source_changed_from(cfg, ind, source):
    """上一份快照同一(经济体, 指标)的 source 与本次不同 → 返回旧 source。"""
    snap = cfg.get("prev_snapshot")
    rows = snap.get("macro") if isinstance(snap, dict) else None
    if not isinstance(rows, list):
        return None
    for row in rows:
        if not isinstance(row, dict):
            continue
        if (row.get("economy"), row.get("indicator")) != (ind["economy"], ind["indicator"]):
            continue
        old = row.get("source", "dbnomics")   # 本变更之前的快照无 source 字段
        return old if old != source else None
    return None


def _bls_latest(by_key):
    monthly = [(k, v) for k, v in by_key.items()
               if len(k[1]) == 3 and k[1].startswith("M") and k[1][1:].isdigit()
               and 1 <= int(k[1][1:]) <= 12]
    if not monthly:
        return None
    return max(monthly, key=lambda kv: (kv[0][0], kv[0][1]))


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
    if len(periods) != len(values):
        raise ValueError("'period'/'value' length mismatch: %d vs %d"
                         % (len(periods), len(values)))
    pairs = [(p, v) for p, v in zip(periods, values)
             if isinstance(v, (int, float)) and not isinstance(v, bool)]
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
                rid = r.get("release_id")
                if rid is None:
                    continue  # name/id 双缺失:无任何可用标识,跳过该条目
                name = str(rid)
            names.append(name)
        return names
    except Exception as e:
        gaps.append(util.make_gap("fred", "us-release-dates",
                                  "%s: %s" % (type(e).__name__, e)))
        return None
