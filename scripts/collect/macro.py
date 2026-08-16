"""宏观指标采集:三个官方 SDMX/JSON 直连源 + FRED 可选增强。

- 美国 CPI 同比 → BLS 公共 API(主源,零 key)
- CPI 同比 / 政策利率 → BIS Stats SDMX
- 经常账户 → IMF 官方 SDMX

**没有回落层。** 曾经的 DBnomics 回落已整只删除:该镜像的 **API 域**
(api 子域)的 robots.txt 是 `User-agent: *` / `Disallow: /`(2026-08-16 实测
HTTP 200,26 字节),整站禁爬。仓库对 BSP、CME 用的是同一把尺子,不能一边把
它们剔掉、一边每天打这个域。(它的网页域是放行的,被禁的正是我们在打的 API 域。)
本文件刻意不写出那个主机名,好让"全仓 grep 主机名"这条合规检查保持零命中。

删的是路径本身,不是"默认关闭的开关"——陈旧调用点会静默地什么都不做,而
grep 仍看得见它,复核者以为还在用。

去掉回落意味着"取不到就没有这一行"成了常态路径,于是有了一条硬不变量:
**每个被跟踪的指标,要么产出一行,要么产出一条定位到它的缺漏**(见 collect)。
否则"整块消失"与"这个季度确实没发布"在快照里同形,下游结论句会把前者说成后者。
"""
import csv
import io
import math
import re

from . import util

PERIOD_RE = re.compile(r"^(\d{4})-(\d{2})")
US_CPI = ("US", "CPI 同比")


def _obs_value(raw):
    """BIS 的非交易日写字符串 "NaN";实测也有 "1" 这种无小数点形态。

    两道门:字符串判定与 math.isfinite。**变异测试显示字符串判定单独去掉不会
    改变行为**(float("NaN") 后被 isfinite 挡住),即它是等价变异而非承重逻辑。
    保留它是纵深防御——真正的危险是 NaN 逃出本函数:它的任何比较都是 False,
    会同时毁掉"取最新非 NaN"与"找上一个不同水平"两处判定。isfinite 若日后被
    当成冗余删掉,这道字符串门就是最后一层。
    """
    s = (raw or "").strip()
    if not s or s.upper() == "NAN":
        return None
    try:
        v = float(s)
    except ValueError:
        return None
    return v if math.isfinite(v) else None


def _sdmx_parse(text, area_col="REF_AREA"):
    """SDMX-CSV → {地区码: [(period, value), ...]},按 period 升序。

    一套解析伺候三个 dataflow。地区维度的**列名**因源而异(BIS 叫 REF_AREA,
    IMF BOP 叫 COUNTRY),其余形状一致,故只把列名参数化,不另写一套。

    按列名取,不按位置:三个 dataflow 的列集合差得很远(BIS CPI 多
    UNIT_MEASURE,IMF BOP 实测 53 列),且 SDMX 版本升级改列序时按位置取
    不会报错,只会静默取错列。
    """
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    cols = reader.fieldnames or []
    missing = [c for c in (area_col, "TIME_PERIOD", "OBS_VALUE") if c not in cols]
    if missing:
        raise ValueError("SDMX CSV 缺列 %s(实际:%s)"
                         % (",".join(missing), ",".join(cols)))
    out = {}
    for row in reader:
        value = _obs_value(row.get("OBS_VALUE"))
        if value is None:
            continue
        area, period = row.get(area_col), row.get("TIME_PERIOD")
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


# 地区码映射一律写死,不做字符串启发式。两个源对同一个经济体的写法都不一样:
# BIS 用 XM 表示欧元区;IMF BOP 用 ISO3,欧元区是 **G163**(2026-08-16 实测
# CL_COUNTRY codelist 名称 "Euro Area (EA)";U2 / XM / EA 在该 dataflow 里都
# 查无此码,写错不会报错,只会让欧元区整条缺席)。
BIS_AREA = {"US": "US", "EA": "XM", "PH": "PH", "TH": "TH", "BR": "BR"}
IMF_AREA = {"US": "USA", "EA": "G163", "PH": "PHL", "TH": "THA", "BR": "BRA"}

# api.imf.org 实测**无视** `?format=csv`,只认 Accept 头;不发这个头拿回来的是
# SDMX-ML,解析器只会抛"缺列",看不出真实原因。
SDMX_CSV_ACCEPT = "application/vnd.sdmx.data+csv;version=1.0.0"

# (指标名, 端点配置键, source, dataflow 名, 地区列名, 地区映射, 频率, Accept 头)
# 频率同时决定两件事:前值口径,以及"什么算新发布"——见 _latest_and_prev_*
# 与 _is_new_level。日频("D")比水平,其余比期号。
SDMX_SOURCES = (
    ("政策利率", "bis_cbpol_url", "bis", "WS_CBPOL", "REF_AREA", BIS_AREA, "D", None),
    ("CPI 同比", "bis_cpi_url", "bis", "WS_LONG_CPI", "REF_AREA", BIS_AREA, "M", None),
    ("经常账户", "imf_bop_url", "imf", "BOP", "COUNTRY", IMF_AREA, "Q", SDMX_CSV_ACCEPT),
)


def _sdmx_table(cfg, gaps):
    """三个 SDMX 源统一取数,返回 {(economy, indicator): row}。

    批量取数(每个源一次 GET 覆盖五经济体)但**逐指标**可缺席。没有回落层了,
    所以"缺席"就是真的没有这一行——两条降级路径(整体失败 / 缺某经济体)
    都必须记 gap,且 scope **定位到具体指标**(经济体/指标),不能只记到
    dataflow 一级:报告层要知道该对哪一条打折扣,而不是知道"某个源出过事"。

    只为**被跟踪的**(经济体, 指标)取数与记 gap:没人跟踪的指标缺席不是缺漏,
    与 BLS「没跟踪就别打这一枪」同约定,否则缺漏节会被无人关心的条目淹没。

    任何失败都记 gap 并让受影响指标缺席,绝不上抛(采集层硬契约)。
    """
    endpoints = cfg.get("endpoints")
    endpoints = endpoints if isinstance(endpoints, dict) else {}
    tracked = {(i.get("economy"), i.get("indicator")) for i in cfg["indicators"]}
    out = {}
    for indicator, key, source, dataflow, area_col, area_map, freq, accept in SDMX_SOURCES:
        wanted = [(e, a) for e, a in area_map.items() if (e, indicator) in tracked]
        if not wanted:
            continue        # 该指标一个经济体都没跟踪 → 不发这次 GET,也不记 gap
        url = endpoints.get(key)
        if not isinstance(url, str) or not url:
            continue        # 未配置 = 有意停用(与 feeds.py 同约定),删 URL 即回滚
        try:
            text = util.fetch_text(url, cfg["timeout_s"],
                                   {"Accept": accept} if accept else None)
            by_area = _sdmx_parse(text, area_col)
        except Exception as e:
            # 整体失败也逐指标记:受影响的是这几条,不是"一个 dataflow"
            for economy, _area in wanted:
                gaps.append(util.make_gap(
                    source, "%s/%s" % (economy, indicator),
                    "%s %s 取数失败(%s: %s),该指标本次无观测"
                    % (source.upper(), dataflow, type(e).__name__, e)))
            continue
        pick = _latest_and_prev_distinct if freq == "D" else _latest_and_prev_observation
        for economy, area in wanted:
            value, period, prev, prev_period = pick(by_area.get(area) or [])
            if value is None:   # 该经济体缺席或全 NaN → 没有这一行,必须说出来
                gaps.append(util.make_gap(
                    source, "%s/%s" % (economy, indicator),
                    "%s %s 响应中 %s=%s 无可用观测,该指标本次无观测"
                    % (source.upper(), dataflow, area_col, area)))
                continue
            series_id = "%s/%s/%s" % (source.upper(), dataflow, area)
            out[(economy, indicator)] = {
                "value": value, "prev": prev, "period": period,
                "prev_period": prev_period, "source": source,
                "series_id": series_id,
                # 判据随频率变:日频序列每天追加一行,期号推进说明的是管道刷新,
                # 只有水平变了才是央行发布。判定留在这里而不是 collect(),
                # 是为了让"哪个频率用哪条规则"与频率声明待在同一处。
                "is_new_release": (_is_new_level(cfg, series_id, value) if freq == "D"
                                   else _is_new(cfg, series_id, period)),
            }
    return out


def collect(cfg):
    gaps, indicators = [], []
    tracked = [(i.get("economy"), i.get("indicator")) for i in cfg["indicators"]]
    # 没跟踪美国 CPI 就别打 BLS 这一枪(也就不会为未跟踪指标记 gap)
    bls_row = _bls_us_cpi(cfg, gaps) if US_CPI in tracked else None
    # 批量取数放在循环之前:每个源一次 GET 覆盖五经济体,循环内只查表。
    table = _sdmx_table(cfg, gaps)
    for ind in cfg["indicators"]:
        key = (ind.get("economy"), ind.get("indicator"))
        if bls_row is not None and key == US_CPI:
            # BLS 是美国 CPI 的主源,优先于 BIS。series_id 写 BLS 的真实出处——
            # 它是快照里唯一可回溯到源的字段,写成别人的 id 会让复核者拿到
            # 完全不同的数,反而像脚本算错了。
            row = dict(bls_row, economy=ind["economy"], indicator=ind["indicator"],
                       is_new_release=_is_new(cfg, bls_row["series_id"],
                                              bls_row["period"]),
                       lag_months=lag_months(bls_row["period"], cfg["date"]))
            indicators.append(_mark_source_change(cfg, ind, row))
            continue
        hit = table.get(key)
        if hit is not None:
            # is_new_release 已由 _sdmx_table 按频率判好(日频比水平、其余比期号),
            # 这里不得覆写成统一的期号比对。
            row = dict(hit, economy=ind["economy"], indicator=ind["indicator"],
                       lag_months=lag_months(hit["period"], cfg["date"]))
            indicators.append(_mark_source_change(cfg, ind, row))
            continue
        _record_no_observation(gaps, key)
    return {"indicators": indicators, "us_release_dates": _fred(cfg, gaps)}, gaps


def _record_no_observation(gaps, key):
    """兜底不变量:被跟踪的指标没产出行,就一定要有一条定位到它的缺漏。

    回落层删掉之后,"没有这一行"成了常态路径。上游(BLS / _sdmx_table)通常
    已经记了带原因的那一条,此时不重复——缺漏节被同一件事刷屏,读者就会开始
    跳过它。上游一条都没记的情况只有一种:该指标压根没落在任何已配置的源上
    (端点被删、或 config 里躺着一条谁也不取的指标)。那也必须说出来,否则
    整块数据无声消失,与"这一期确实没有发布"在快照里完全同形。
    """
    scope = "%s/%s" % key
    if any(g.get("scope") == scope for g in gaps):
        return
    gaps.append(util.make_gap(
        "macro", scope, "没有任何已配置来源提供该指标(BLS / BIS / IMF 均未覆盖"
                        "或端点未配置),本次无观测"))


def lag_months(period, date_str):
    """期号相对快照日期的滞后月数。滞后不披露就等于隐形——曾经的镜像源实测
    滞后 219–498 天,报告却把它当"最新值"引用。无法解析(如季度期号)→ None,不猜。

    经常账户是季频("2026-Q1"),PERIOD_RE 匹配不上 → 恒为 None。这是"不猜",
    不是"没滞后":读者从 period 本身就能看出是哪个季度。"""
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

    未配置端点 → 静默交给 BIS(有意停用,非缺漏);配置了但失败 → 记 gap 后
    由 BIS 接手,BIS 也没有则该指标本次无观测(由 collect 的兜底不变量记缺漏)。
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
    "通胀升高"(2026-08-11 实际发生过)。两个方向都要标,漏标即同型事故。

    经常账户从旧镜像切到 IMF 直连是眼下最刺眼的一例:**计价单位都不同**
    (镜像是百万美元,直连是美元),PH 会从 -4247 跳到 -5663843363。
    这个标记是唯一让报告层看出"这两个数不可比"的字段。"""
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


def _is_new_level(cfg, series_id, value):
    """日频序列的「新发布」= **水平变了**,不是「序列多了一行」。

    BIS WS_CBPOL 每个日历日追加一行(实测 400 个观测跨 399 天),利率纹丝不动
    的日子期号照样推进。沿用 _is_new(只比 period)会让五个经济体在每个 BIS
    刷新日全部 is_new_release 为 true,日报据此打出"数据发布:政策利率 …"行
    ——又一次把管道状态说成市场事实(本仓库反复出现的同型缺陷)。

    取不到可比数值(首次落地、上一份快照无此 series、旧值不是数或是 bool)
    → False:漏列一次真实变动只是少说,凭不可比的输入打出发布行是编造。
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    snap = cfg.get("prev_snapshot")
    rows = snap.get("macro") if isinstance(snap, dict) else None
    if not isinstance(rows, list):
        return False
    for row in rows:
        if not isinstance(row, dict) or row.get("series_id") != series_id:
            continue
        old = row.get("value")
        if isinstance(old, bool) or not isinstance(old, (int, float)):
            return False
        return old != value
    return False


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
