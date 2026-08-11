---
change: fx-bis-macro-direct
design-doc: docs/superpowers/specs/2026-08-11-fx-bis-macro-direct-design.md
base-ref: 7fa78d8941184714caa31853c0d5740f84469449
---

# BIS 宏观直连 + HTTP 取数封装加固 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 五经济体的 CPI 同比与政策利率改为直连 BIS Stats API,消除 DBnomics 镜像 8–17 个月的滞后与已在发布的方向性错值;同时让 `util.fetch_*` 不再把 gzip 响应静默读成解析失败。

**Architecture:** `macro.collect()` 的循环形状不变。循环**之前**用两次 GET 把 BIS 结果拉平成 `{(economy, indicator): row}` 查找表;循环内按 BLS → 查表 → DBnomics 三级命中。BIS 整体失败时查找表为空,全部指标自然回落 DBnomics——「逐指标回落」因此不需要任何额外分支。

**Tech Stack:** Python 标准库 only(`urllib` / `csv` / `io` / `gzip` / `math` / `json`)。零 API key。测试用既有 `tests/helpers.py` 的 `FixtureServer`,不打真实网络。

**测试命令(全程统一):**

```bash
find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -t . 2>&1 >/dev/null | tail -3
```

基线:`Ran 372 tests` / `OK`。

**文件结构**

| 文件 | 职责 | 动作 |
|---|---|---|
| `tests/helpers.py` | FixtureServer 支持 bytes 响应体(gzip 测试需要) | 改 |
| `scripts/collect/util.py` | gzip 魔数兜底 + 可选 headers | 改 |
| `scripts/collect/macro.py` | BIS 解析、前值口径、三级优先级 | 改 |
| `config/endpoints.json` | 两个 BIS URL | 改 |
| `config/indicators.json` | BIS 维度键(保留 series_id 供回落) | 改 |
| `tests/test_util.py` | util 的压缩与 header 回归 | 新建 |
| `tests/test_macro.py` | BIS 全部路径 | 改 |
| `skills/fx-daily-report/SKILL.md` | 数据发布行加 `prev_period` | 改 |
| `README.md` | 数据源一节 | 改 |

---

### Task 1: FixtureServer 支持 bytes 响应体

gzip 测试要发原始压缩字节,而现有 `_Handler` 无条件 `body.encode("utf-8")`。

**Files:**
- Modify: `tests/helpers.py:16`

- [x] **Step 1: 写失败测试**

新建 `tests/test_util.py`:

```python
"""util 取数封装:压缩兜底与自定义请求头。"""
import gzip
import unittest

from scripts.collect import util
from tests.helpers import FixtureServer


class BytesFixtureTest(unittest.TestCase):
    def test_fixture_server_can_serve_raw_bytes(self):
        """gzip 测试需要发原始字节,而非 UTF-8 编码的字符串。"""
        blob = gzip.compress("你好".encode("utf-8"))
        with FixtureServer({"/z": (200, blob)}) as srv:
            text = util.fetch_text(srv.base_url + "/z")
        self.assertEqual(text, "你好")


if __name__ == "__main__":
    unittest.main()
```

- [x] **Step 2: 跑测试确认失败**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_util -v 2>&1 | tail -5
```

预期:FAIL —— `AttributeError: 'bytes' object has no attribute 'encode'`(服务端)或返回乱码。

- [x] **Step 3: 实现**

`tests/helpers.py` 第 16 行:

```python
                data = body if isinstance(body, bytes) else body.encode("utf-8")
```

- [x] **Step 4: 跑测试**

预期仍 FAIL —— 服务端已能发字节,但 `util.fetch_text` 还不会解压(Task 2 修)。确认失败原因已从"服务端崩"变成"内容不对"。

- [x] **Step 5: 提交**

```bash
git add tests/helpers.py tests/test_util.py
git commit -m "test(helpers): FixtureServer 支持 bytes 响应体,为 gzip 兜底测试铺路"
```

---

### Task 2: `util.fetch_text` 的 gzip 魔数兜底

**Files:**
- Modify: `scripts/collect/util.py:11-18`
- Test: `tests/test_util.py`

- [x] **Step 1: 补齐失败测试**

在 `tests/test_util.py` 的 `BytesFixtureTest` 之后加:

```python
class GzipFallbackTest(unittest.TestCase):
    """源无视 Accept-Encoding 恒返回 gzip 是实测存在的形态(IBGE)。
    以有损解码读压缩体会产出乱码,使"压缩没解开"与"源返回垃圾"在 gap 里
    不可区分——属静默劣化,必须改成解压或抛错两条明路。"""

    def test_gzip_body_is_decompressed(self):
        blob = gzip.compress(b'{"ok": 1}')
        with FixtureServer({"/z": (200, blob)}) as srv:
            self.assertEqual(util.fetch_json(srv.base_url + "/z"), {"ok": 1})

    def test_corrupt_gzip_raises_instead_of_returning_mojibake(self):
        blob = b"\x1f\x8b" + b"garbage" * 4       # 魔数对,内容坏
        with FixtureServer({"/z": (200, blob)}) as srv:
            with self.assertRaises(Exception) as ctx:
                util.fetch_text(srv.base_url + "/z")
        self.assertNotIsInstance(ctx.exception, UnicodeDecodeError)

    def test_plain_body_unchanged(self):
        with FixtureServer({"/p": (200, '{"ok": 2}')}) as srv:
            self.assertEqual(util.fetch_json(srv.base_url + "/p"), {"ok": 2})

    def test_empty_body_does_not_crash(self):
        with FixtureServer({"/e": (200, b"")}) as srv:
            self.assertEqual(util.fetch_text(srv.base_url + "/e"), "")
```

- [x] **Step 2: 跑测试确认失败**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_util -v 2>&1 | tail -8
```

预期:`test_gzip_body_is_decompressed` FAIL(JSON 解析失败),`test_corrupt_gzip_...` FAIL(未抛异常)。

- [x] **Step 3: 实现**

`scripts/collect/util.py` 顶部加 `import gzip`,并替换 `fetch_text`:

```python
DEFAULT_UA = "macro-fx-collector/0.1"


def fetch_text(url, timeout_s=20):
    req = urllib.request.Request(url, headers={"User-Agent": DEFAULT_UA})
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        raw = resp.read()
    # 先解压再 decode:反过来会让 errors="replace" 把压缩体变成乱码,
    # 使"压缩没解开"与"源返回了垃圾"在 gap 里不可区分(静默劣化)。
    # 不靠请求侧 Accept-Encoding 协商——实测存在无视该头恒返回 gzip 的源。
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)   # 失败即抛,由调用方转 gap
    return raw.decode("utf-8", errors="replace")
```

- [x] **Step 4: 跑测试确认通过**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_util -v 2>&1 | tail -3
```

预期:5 tests OK。再跑全量确认无回归:`Ran 377 tests` / `OK`。

- [x] **Step 5: 提交**

```bash
git add scripts/collect/util.py tests/test_util.py
git commit -m "fix(util): 按 gzip 魔数解压后再 decode

errors=replace 在解压之前就把压缩体变成乱码,使"压缩没解开"与"源返回垃圾"
在 gap 里不可区分。实测 fetch_json 打 IBGE calendario 直接 JSONDecodeError,
而发 Accept-Encoding: identity 无效(同一 URL 连测 4 次 4/4 仍 gzip)。"
```

---

### Task 3: `util.fetch_*` 的可选 headers 参数

**Files:**
- Modify: `scripts/collect/util.py`
- Test: `tests/test_util.py`

- [x] **Step 1: 写失败测试**

```python
class HeadersTest(unittest.TestCase):
    def _echo_server(self):
        def handler(req):
            seen = {k.lower(): v for k, v in req.headers.items()}
            import json as _json
            return 200, _json.dumps({"ua": seen.get("user-agent"),
                                     "referer": seen.get("referer")})
        return FixtureServer({"/h": handler})

    def test_default_ua_when_no_headers(self):
        with self._echo_server() as srv:
            got = util.fetch_json(srv.base_url + "/h")
        self.assertEqual(got["ua"], util.DEFAULT_UA)
        self.assertIsNone(got["referer"])

    def test_extra_headers_are_sent(self):
        with self._echo_server() as srv:
            got = util.fetch_json(srv.base_url + "/h", headers={"Referer": "https://x/"})
        self.assertEqual(got["ua"], util.DEFAULT_UA)      # 默认 UA 仍在
        self.assertEqual(got["referer"], "https://x/")

    def test_caller_can_override_ua(self):
        with self._echo_server() as srv:
            got = util.fetch_json(srv.base_url + "/h", headers={"User-Agent": "probe/9"})
        self.assertEqual(got["ua"], "probe/9")
```

- [x] **Step 2: 跑测试确认失败**

预期:`TypeError: fetch_json() got an unexpected keyword argument 'headers'`。

- [x] **Step 3: 实现**

```python
def fetch_text(url, timeout_s=20, headers=None):
    hdrs = {"User-Agent": DEFAULT_UA}
    hdrs.update(headers or {})       # 调用方可覆盖 UA,语义明确
    req = urllib.request.Request(url, headers=hdrs)
    ...


def fetch_json(url, timeout_s=20, headers=None):
    return json.loads(fetch_text(url, timeout_s, headers))
```

- [x] **Step 4: 跑测试**

预期:`tests.test_util` 8 tests OK;全量 `Ran 380 tests` / `OK`。

- [x] **Step 5: 提交**

```bash
git add scripts/collect/util.py tests/test_util.py
git commit -m "feat(util): fetch_text/fetch_json 接受可选 headers,默认 UA 打底"
```

---

### Task 4: `_bis_parse` —— CSV 按列名解析

**Files:**
- Modify: `scripts/collect/macro.py`
- Test: `tests/test_macro.py`

- [x] **Step 1: 写失败测试**

在 `tests/test_macro.py` 末尾(`if __name__` 之前)加:

```python
CBPOL_CSV = (
    "FREQ,REF_AREA,TIME_PERIOD,OBS_VALUE\n"
    "D,BR,2026-06-16,14.5\n"
    "D,BR,2026-06-17,14.25\n"
    "D,BR,2026-06-18,NaN\n"
    "D,TH,2026-07-30,1\n"          # 实测形态:无小数点
)


class BisParseTest(unittest.TestCase):
    def test_groups_by_ref_area_sorted_by_period(self):
        got = macro._bis_parse(CBPOL_CSV)
        self.assertEqual(got["BR"], [("2026-06-16", 14.5), ("2026-06-17", 14.25)])
        self.assertEqual(got["TH"], [("2026-07-30", 1.0)])   # "1" 也要解析

    def test_nan_rows_dropped_not_zeroed(self):
        """NaN 是"当天没有读数",不是 0。"""
        self.assertEqual(len(macro._bis_parse(CBPOL_CSV)["BR"]), 2)

    def test_column_order_does_not_matter(self):
        """按列名取。按位置取的实现会在这里给出错值。"""
        reordered = ("OBS_VALUE,TIME_PERIOD,REF_AREA,FREQ\n"
                     "14.25,2026-06-17,BR,D\n")
        self.assertEqual(macro._bis_parse(reordered)["BR"], [("2026-06-17", 14.25)])

    def test_missing_required_column_raises(self):
        for csv_text in ("FREQ,REF_AREA,TIME_PERIOD\nD,BR,2026-06-17\n",
                         "FREQ,TIME_PERIOD,OBS_VALUE\nD,2026-06-17,14.25\n",
                         "FREQ,REF_AREA,OBS_VALUE\nD,BR,14.25\n"):
            with self.assertRaises(ValueError):
                macro._bis_parse(csv_text)

    def test_empty_and_header_only(self):
        self.assertEqual(macro._bis_parse("FREQ,REF_AREA,TIME_PERIOD,OBS_VALUE\n"), {})
        with self.assertRaises(ValueError):
            macro._bis_parse("")

    def test_non_numeric_obs_value_dropped(self):
        text = ("FREQ,REF_AREA,TIME_PERIOD,OBS_VALUE\n"
                "D,BR,2026-06-17,abc\n"
                "D,BR,2026-06-18,\n"
                "D,BR,2026-06-19,inf\n")
        self.assertEqual(macro._bis_parse(text), {})
```

- [x] **Step 2: 跑测试确认失败**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_macro.BisParseTest -v 2>&1 | tail -5
```

预期:`AttributeError: module 'scripts.collect.macro' has no attribute '_bis_parse'`。

- [x] **Step 3: 实现**

`macro.py` 顶部加 `import csv`、`import io`、`import math`;然后:

```python
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
    reader = csv.DictReader(io.StringIO(text))
    cols = reader.fieldnames or []
    missing = [c for c in BIS_REQUIRED_COLS if c not in cols]
    if missing:
        raise ValueError("BIS CSV 缺列 %s(实际:%s)" % (",".join(missing), ",".join(cols)))
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
```

- [x] **Step 4: 跑测试**

预期:`BisParseTest` 6 tests OK;全量 `Ran 386 tests` / `OK`。

- [x] **Step 5: 提交**

```bash
git add scripts/collect/macro.py tests/test_macro.py
git commit -m "feat(macro): BIS CSV 按列名解析,NaN 在转 float 前按字符串判掉"
```

---

### Task 5: 两种前值口径

政策利率(日频)取**上一个不同的水平**;CPI 同比(月频)取**上一个观测**——相邻月份本就该比较。

**Files:**
- Modify: `scripts/collect/macro.py`
- Test: `tests/test_macro.py`

- [x] **Step 1: 写失败测试**

```python
class PrevSemanticsTest(unittest.TestCase):
    """日频政策利率绝大多数相邻观测相同,取"上一个观测"会恒等于当前值,
    对报告零信息(14.25 → 14.25)。"""

    RATES = [("2026-06-15", 14.5), ("2026-06-16", 14.5),
             ("2026-06-17", 14.25), ("2026-06-18", 14.25)]

    def test_distinct_prev_skips_equal_observations(self):
        got = macro._latest_and_prev_distinct(self.RATES)
        self.assertEqual(got, (14.25, "2026-06-18", 14.5, "2026-06-16"))

    def test_prev_period_is_last_day_of_old_level(self):
        """要说的是"上次变动前是 A,一直到 X 日",故取旧水平的**末日**。"""
        self.assertEqual(macro._latest_and_prev_distinct(self.RATES)[3], "2026-06-16")

    def test_no_change_in_window_yields_none_not_equal_value(self):
        """等值会被读成"持平",而事实是"窗口内没看到变动"。"""
        flat = [("2026-06-15", 14.25), ("2026-06-16", 14.25)]
        value, period, prev, prev_period = macro._latest_and_prev_distinct(flat)
        self.assertEqual((value, period), (14.25, "2026-06-16"))
        self.assertIsNone(prev)
        self.assertIsNone(prev_period)

    def test_single_observation(self):
        got = macro._latest_and_prev_distinct([("2026-06-15", 14.25)])
        self.assertEqual(got, (14.25, "2026-06-15", None, None))

    def test_empty_series(self):
        self.assertEqual(macro._latest_and_prev_distinct([]), (None, None, None, None))

    def test_monthly_prev_takes_previous_observation_even_if_equal(self):
        """CPI 同比是月频,相邻月份即便同值也是两次独立发布。"""
        cpi = [("2026-05", 3.1), ("2026-06", 3.1)]
        self.assertEqual(macro._latest_and_prev_observation(cpi),
                         (3.1, "2026-06", 3.1, "2026-05"))
```

- [x] **Step 2: 跑测试确认失败**

预期:两个 `AttributeError`(函数不存在)。

- [x] **Step 3: 实现**

```python
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
    而事实是"回溯窗口内没看到变动"。
    """
    if not obs:
        return None, None, None, None
    period, value = obs[-1]
    for prev_period, prev in reversed(obs[:-1]):
        if prev != value:
            return value, period, prev, prev_period
    return value, period, None, None
```

- [x] **Step 4: 跑测试**

预期:`PrevSemanticsTest` 6 tests OK;全量 `Ran 392 tests` / `OK`。

- [x] **Step 5: 提交**

```bash
git add scripts/collect/macro.py tests/test_macro.py
git commit -m "feat(macro): 政策利率前值取上一个不同水平,CPI 取上一个观测

日频序列取"上一个观测"会恒等于当前值(14.25 → 14.25),对报告零信息;
窗口内无变动时 prev 为 null 而非等于 value——等值会被读成"持平"。"
```

---

### Task 6: `_bis_table` 与配置

**Files:**
- Modify: `scripts/collect/macro.py`、`config/endpoints.json`、`config/indicators.json`
- Test: `tests/test_macro.py`

- [x] **Step 1: 写失败测试**

```python
CPI_CSV = (
    "FREQ,REF_AREA,UNIT_MEASURE,TIME_PERIOD,OBS_VALUE\n"
    "M,XM,771,2026-05,3.177015\n"
    "M,XM,771,2026-06,2.748918\n"
    "M,BR,771,2026-05,4.7249068792\n"
    "M,BR,771,2026-06,4.6413275481\n"
)


def bis_cfg(srv, **over):
    base = {"endpoints": {
        "dbnomics_series_url": srv.base_url + "/db/{series_id}",
        "bis_cbpol_url": srv.base_url + "/bis/cbpol",
        "bis_cpi_url": srv.base_url + "/bis/cpi",
    }, "indicators": [
        {"economy": "EA", "indicator": "CPI 同比", "series_id": "ECB/ICP/X"},
        {"economy": "BR", "indicator": "CPI 同比", "series_id": "IMF/CPI/M.BR.X"},
        {"economy": "BR", "indicator": "政策利率", "series_id": "BIS/WS_CBPOL/D.BR"},
        {"economy": "TH", "indicator": "政策利率", "series_id": "BIS/WS_CBPOL/D.TH"},
    ]}
    base.update(over)
    return make_test_cfg(**base)


BIS_ROUTES = {"/bis/cbpol": (200, CBPOL_CSV), "/bis/cpi": (200, CPI_CSV)}


class BisTableTest(unittest.TestCase):
    def test_table_keyed_by_economy_and_indicator(self):
        with FixtureServer(dict(BIS_ROUTES)) as srv:
            gaps = []
            table = macro._bis_table(bis_cfg(srv), gaps)
        self.assertEqual(gaps, [])
        self.assertEqual(table[("BR", "政策利率")]["value"], 14.25)
        self.assertEqual(table[("BR", "政策利率")]["prev"], 14.5)
        self.assertEqual(table[("BR", "政策利率")]["prev_period"], "2026-06-16")
        self.assertEqual(table[("EA", "CPI 同比")]["value"], 2.748918)   # XM → EA 映射
        self.assertEqual(table[("EA", "CPI 同比")]["source"], "bis")

    def test_euro_area_maps_from_xm(self):
        """映射互换会让欧元区取到别人的值。"""
        with FixtureServer(dict(BIS_ROUTES)) as srv:
            table = macro._bis_table(bis_cfg(srv), [])
        self.assertNotIn(("XM", "CPI 同比"), table)
        self.assertIn(("EA", "CPI 同比"), table)

    def test_unconfigured_endpoint_is_silent_skip(self):
        """未配置 = 有意停用(与 feeds.py 同约定),使删掉 URL 即整体回滚。"""
        with FixtureServer(dict(BIS_ROUTES)) as srv:
            cfg = bis_cfg(srv)
            cfg["endpoints"].pop("bis_cbpol_url")
            gaps = []
            table = macro._bis_table(cfg, gaps)
        self.assertEqual(gaps, [])
        self.assertNotIn(("BR", "政策利率"), table)
        self.assertIn(("BR", "CPI 同比"), table)

    def test_unreachable_endpoint_records_gap_and_empties_that_dataflow(self):
        with FixtureServer({"/bis/cpi": (200, CPI_CSV)}) as srv:
            cfg = bis_cfg(srv)
            cfg["endpoints"]["bis_cbpol_url"] = DEAD_URL + "/x"
            gaps = []
            table = macro._bis_table(cfg, gaps)
        self.assertEqual([g["source"] for g in gaps], ["bis"])
        self.assertNotIn(("BR", "政策利率"), table)
        self.assertIn(("BR", "CPI 同比"), table)     # 另一个 dataflow 不受影响

    def test_missing_column_records_gap(self):
        bad = {"/bis/cbpol": (200, "FREQ,REF_AREA,TIME_PERIOD\nD,BR,2026-06-17\n"),
               "/bis/cpi": (200, CPI_CSV)}
        with FixtureServer(bad) as srv:
            gaps = []
            table = macro._bis_table(bis_cfg(srv), gaps)
        self.assertEqual(len(gaps), 1)
        self.assertIn("缺列", gaps[0]["reason"])
        self.assertNotIn(("BR", "政策利率"), table)

    def test_economy_absent_from_response_only_that_key_missing(self):
        """TH 不在 CPI 响应里 → 只有它缺席,BR/EA 照常。"""
        with FixtureServer(dict(BIS_ROUTES)) as srv:
            table = macro._bis_table(bis_cfg(srv), [])
        self.assertNotIn(("TH", "CPI 同比"), table)
        self.assertIn(("BR", "CPI 同比"), table)

    def test_all_nan_economy_absent(self):
        allnan = {"/bis/cbpol": (200, "FREQ,REF_AREA,TIME_PERIOD,OBS_VALUE\n"
                                      "D,BR,2026-06-17,NaN\nD,BR,2026-06-18,NaN\n"),
                  "/bis/cpi": (200, CPI_CSV)}
        with FixtureServer(allnan) as srv:
            table = macro._bis_table(bis_cfg(srv), [])
        self.assertNotIn(("BR", "政策利率"), table)
```

- [x] **Step 2: 跑测试确认失败**

预期:`AttributeError: ... has no attribute '_bis_table'`。

- [x] **Step 3: 实现**

```python
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
    调用方查不到就自然回落 DBnomics。三种降级路径(整体失败/缺列/缺某经济体)
    因此共用同一条代码路径,不需要额外分支。

    任何失败都记 gap 并让受影响指标缺席,绝不上抛(采集层硬契约)。
    """
    endpoints = cfg.get("endpoints")
    endpoints = endpoints if isinstance(endpoints, dict) else {}
    out = {}
    for indicator, key, dataflow, prev_mode in BIS_DATAFLOWS:
        url = endpoints.get(key)
        if not isinstance(url, str) or not url:
            continue        # 未配置 = 有意停用(与 feeds.py 同约定)
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
```

`config/endpoints.json` 加两行:

```json
  "bis_cbpol_url": "https://stats.bis.org/api/v2/data/dataflow/BIS/WS_CBPOL/1.0/D.US+XM+PH+TH+BR?format=csv&detail=dataonly&lastNObservations=400",
  "bis_cpi_url": "https://stats.bis.org/api/v2/data/dataflow/BIS/WS_LONG_CPI/1.0/M.US+XM+PH+TH+BR.771?format=csv&detail=dataonly&lastNObservations=4"
```

`config/indicators.json` 不需要改结构——`BIS_AREA` 已由 `economy` 字段驱动,现有 `series_id` 保留作 DBnomics 回落用。

- [x] **Step 4: 跑测试**

预期:`BisTableTest` 7 tests OK;全量 `Ran 399 tests` / `OK`。

- [x] **Step 5: 提交**

```bash
git add scripts/collect/macro.py config/endpoints.json tests/test_macro.py
git commit -m "feat(macro): BIS 批量取数拉平成查找表,逐指标可缺席

detail=dataonly 让 CBPOL 从 891KB 降到 40KB(22 倍);lastNObservations=400
约 19 个月,覆盖实测最深的回溯需求(美国上次变动 2025-12-10,约 170 个观测)。"
```

---

### Task 7: `collect()` 接成三级优先级

**Files:**
- Modify: `scripts/collect/macro.py:10-41`
- Test: `tests/test_macro.py`

- [x] **Step 1: 写失败测试**

```python
class PriorityTest(unittest.TestCase):
    def test_bis_used_and_dbnomics_not_called(self):
        with FixtureServer(dict(BIS_ROUTES)) as srv:
            payload, gaps = macro.collect(bis_cfg(srv))
        rows = {(r["economy"], r["indicator"]): r for r in payload["indicators"]}
        self.assertEqual(rows[("BR", "政策利率")]["source"], "bis")
        self.assertEqual(rows[("BR", "政策利率")]["value"], 14.25)
        self.assertEqual(rows[("EA", "CPI 同比")]["source"], "bis")
        # TH 政策利率 BIS 有,TH CPI 不在 indicators 里
        self.assertEqual(rows[("TH", "政策利率")]["value"], 1.0)
        self.assertEqual(gaps, [])          # 未打 dbnomics,故无 dbnomics gap

    def test_bls_wins_over_bis_for_us_cpi(self):
        """优先级 BLS > BIS > DBnomics;BIS 不得覆盖美国 CPI。"""
        cpi_with_us = CPI_CSV + "M,US,771,2026-05,4.248674\nM,US,771,2026-06,3.531425\n"
        routes = {"/bis/cbpol": (200, CBPOL_CSV), "/bis/cpi": (200, cpi_with_us),
                  "/bls": (200, json.dumps(BLS_OK))}
        with FixtureServer(routes) as srv:
            cfg = bis_cfg(srv)
            cfg["endpoints"]["bls_timeseries_url"] = srv.base_url + "/bls"
            cfg["indicators"] = [{"economy": "US", "indicator": "CPI 同比",
                                  "series_id": "IMF/CPI/M.US.X"}]
            payload, _ = macro.collect(cfg)
        self.assertEqual(payload["indicators"][0]["source"], "bls")

    def test_falls_back_to_dbnomics_when_bis_absent(self):
        with FixtureServer({"/db/": (200, json.dumps(SERIES_OK))}) as srv:
            cfg = bis_cfg(srv)
            cfg["endpoints"].pop("bis_cbpol_url")
            cfg["endpoints"].pop("bis_cpi_url")
            payload, _ = macro.collect(cfg)
        self.assertTrue(all(r["source"] == "dbnomics" for r in payload["indicators"]))

    def test_partial_fallback_granularity(self):
        """BIS 只覆盖部分指标时,其余单独回落,不是全有或全无。"""
        routes = {"/bis/cpi": (200, CPI_CSV), "/db/": (200, json.dumps(SERIES_OK))}
        with FixtureServer(routes) as srv:
            cfg = bis_cfg(srv)
            cfg["endpoints"]["bis_cbpol_url"] = DEAD_URL + "/x"
            payload, gaps = macro.collect(cfg)
        rows = {(r["economy"], r["indicator"]): r for r in payload["indicators"]}
        self.assertEqual(rows[("BR", "CPI 同比")]["source"], "bis")
        self.assertEqual(rows[("BR", "政策利率")]["source"], "dbnomics")
        self.assertEqual([g["source"] for g in gaps], ["bis"])

    def test_lag_months_and_prev_period_present(self):
        with FixtureServer(dict(BIS_ROUTES)) as srv:
            payload, _ = macro.collect(bis_cfg(srv, date="2026-08-11"))
        row = [r for r in payload["indicators"] if r["indicator"] == "政策利率"][0]
        self.assertEqual(row["lag_months"], 2)          # 2026-06 → 2026-08
        self.assertEqual(row["prev_period"], "2026-06-16")

    def test_source_change_marked_on_switch_day(self):
        prev_snap = {"macro": [{"economy": "BR", "indicator": "政策利率",
                                "series_id": "BIS/WS_CBPOL/D.BR", "period": "2025-07-07",
                                "source": "dbnomics"}]}
        with FixtureServer(dict(BIS_ROUTES)) as srv:
            payload, _ = macro.collect(bis_cfg(srv, prev_snapshot=prev_snap))
        row = [r for r in payload["indicators"]
               if (r["economy"], r["indicator"]) == ("BR", "政策利率")][0]
        self.assertEqual(row["source_changed_from"], "dbnomics")
        self.assertFalse(row["is_new_release"])
```

`BLS_OK` 若 `tests/test_macro.py` 中尚不存在,复用文件内已有的 BLS fixture 常量名;若名称不同,按实际名称引用。

- [x] **Step 2: 跑测试确认失败**

预期:多条 FAIL,`source` 为 `dbnomics` 而非 `bis`。

- [x] **Step 3: 实现**

在 `collect()` 里,`bls_row` 之后加一行,并在循环内 BLS 分支之后插入 BIS 分支:

```python
    bls_row = _bls_us_cpi(cfg, gaps) if US_CPI in tracked else None
    bis_table = _bis_table(cfg, gaps)
    for ind in cfg["indicators"]:
        if bls_row is not None and (ind["economy"], ind["indicator"]) == US_CPI:
            ...  # 既有 BLS 分支不动
            continue
        bis = bis_table.get((ind["economy"], ind["indicator"]))
        if bis is not None:
            row = dict(bis, economy=ind["economy"], indicator=ind["indicator"],
                       is_new_release=_is_new(cfg, bis["series_id"], bis["period"]),
                       lag_months=lag_months(bis["period"], cfg["date"]))
            indicators.append(_mark_source_change(cfg, ind, row))
            continue
        try:
            ...  # 既有 DBnomics 分支不动
```

- [x] **Step 4: 跑测试**

预期:`PriorityTest` 6 tests OK;全量 `Ran 405 tests` / `OK`。

- [x] **Step 5: 提交**

```bash
git add scripts/collect/macro.py tests/test_macro.py
git commit -m "feat(macro): 三级优先级 BLS > BIS > DBnomics,逐指标回落"
```

---

### Task 8: 畸形输入不崩

**Files:**
- Test: `tests/test_macro.py`

- [x] **Step 1: 写测试(此任务只补测试,实现应已就绪)**

```python
class BisRobustnessTest(unittest.TestCase):
    """外部持久化/网络数据可能任意畸形;采集层不得抛出,只能转 gap。"""

    def _collect(self, cbpol_body):
        routes = {"/bis/cbpol": (200, cbpol_body), "/bis/cpi": (200, CPI_CSV),
                  "/db/": (200, json.dumps(SERIES_OK))}
        with FixtureServer(routes) as srv:
            return macro.collect(bis_cfg(srv))

    def test_empty_body(self):
        payload, gaps = self._collect("")
        self.assertTrue(any(g["source"] == "bis" for g in gaps))
        self.assertTrue(payload["indicators"])          # 其余指标照常产出

    def test_html_error_page(self):
        payload, gaps = self._collect("<html><body>503</body></html>")
        self.assertTrue(any(g["source"] == "bis" for g in gaps))

    def test_unknown_ref_area_ignored(self):
        body = ("FREQ,REF_AREA,TIME_PERIOD,OBS_VALUE\n"
                "D,ZZ,2026-06-17,9.9\nD,BR,2026-06-17,14.25\n")
        payload, _ = self._collect(body)
        rows = {(r["economy"], r["indicator"]): r for r in payload["indicators"]}
        self.assertEqual(rows[("BR", "政策利率")]["value"], 14.25)
        self.assertNotIn(("ZZ", "政策利率"), rows)

    def test_bom_and_crlf(self):
        body = ("﻿FREQ,REF_AREA,TIME_PERIOD,OBS_VALUE\r\n"
                "D,BR,2026-06-17,14.25\r\n")
        payload, gaps = self._collect(body)
        # BOM 会污染首列名 FREQ 而非必需列,必需列仍在 → 应正常解析
        rows = {(r["economy"], r["indicator"]): r for r in payload["indicators"]}
        self.assertEqual(rows[("BR", "政策利率")]["value"], 14.25)

    def test_collect_never_raises_on_any_body(self):
        for body in ("", "\x00\x01", "a,b\n1,2\n", "[]", "null"):
            payload, gaps = self._collect(body)
            self.assertIsInstance(payload["indicators"], list)
```

- [x] **Step 2: 跑测试**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_macro.BisRobustnessTest -v 2>&1 | tail -8
```

失败的用例即真实缺陷,回到 Task 4/6 的实现修复(例如 BOM 需 `csv.DictReader` 前 `text.lstrip("﻿")`)。

- [x] **Step 3: 按失败项修实现**

若 BOM 用例失败,在 `_bis_parse` 首行加:

```python
    text = text.lstrip("﻿")
```

- [x] **Step 4: 跑全量**

预期:`Ran 410 tests` / `OK`。

- [x] **Step 5: 提交**

```bash
git add scripts/collect/macro.py tests/test_macro.py
git commit -m "test(macro): BIS 畸形输入不得抛出,只转 gap"
```

---

### Task 9: 日报 SKILL 的 `prev_period`

日频政策利率的前值不带日期即歧义——这正是本仓库反复栽跟头的形态。

**Files:**
- Modify: `skills/fx-daily-report/SKILL.md`(「数据发布」行)

- [x] **Step 1: 改模板**

把「数据发布」行的 `前值 <prev>` 改为:

```
前值 <prev>(截至 <prev_period>)
```

并在该行的说明括号里追加:

```
`prev_period` 存在时必须写出——日频政策利率的前值不带日期就是歧义的;
`prev` 为 null 时写「前值 不可得(回溯窗口内未观测到变动)」,
MUST NOT 写成与最新值相同的数。
```

- [x] **Step 2: 核对校验器兼容**

```bash
grep -n "数据发布\|prev_period" scripts/check_report.py | head
```

预期:无命中——校验器不解析该行结构,只做数字白名单,故无需同步改动。

- [x] **Step 3: 跑全量确认无回归**

预期:`Ran 410 tests` / `OK`。

- [x] **Step 4: 提交**

```bash
git add skills/fx-daily-report/SKILL.md
git commit -m "docs(skill): 数据发布行加 prev_period,日频前值不带日期即歧义"
```

---

### Task 10: 真实采集核对与 README

**Files:**
- Modify: `README.md`

- [x] **Step 1: 跑一次真实采集**

```bash
python3 -m scripts.collect --date $(date -u +%F)
```

- [x] **Step 2: 逐条核对与 BIS 直查一致**

```bash
python3 - <<'PY'
import json, urllib.request, csv, io, datetime
UA = {"User-Agent": "macro-fx-collector/0.1"}
def rows(u):
    r = urllib.request.Request(u, headers=UA)
    with urllib.request.urlopen(r, timeout=30) as f:
        return list(csv.DictReader(io.StringIO(f.read().decode("utf-8", errors="replace"))))
d = datetime.date.today().isoformat()
snap = json.load(open("data/%s.json" % d))
for m in snap["macro"]:
    if m["indicator"] in ("CPI 同比", "政策利率"):
        print("%-3s %-8s %-14s 期 %-12s prev %-8s@%-12s 源 %s 滞后 %s" % (
            m["economy"], m["indicator"], m["value"], m["period"],
            m.get("prev"), m.get("prev_period"), m["source"], m.get("lag_months")))
PY
```

预期:五经济体 CPI 与政策利率的 `source` 为 `bis`(美国 CPI 为 `bls`),数值与本计划第 1 节的实测表一致;10 个指标带 `source_changed_from: "dbnomics"`。

- [x] **Step 3: 更新 README 数据源一节**

补:BIS 两个 dataflow 的 URL 与用途、三级优先级 BLS > BIS > DBnomics、`detail=dataonly` 的原因、经常账户仍走 DBnomics(BIS 不覆盖)、BSP 因 `robots.txt` 不接入。

- [x] **Step 4: 提交**

```bash
git add README.md data/ briefs/ reports/
git commit -m "chore(fx-bis-macro-direct): 真实采集核对 + README 数据源更新"
```

---

## 自检

**Spec coverage** — delta spec 的 16 个场景对应关系:

| 场景 | 任务 |
|---|---|
| BIS 直连取得五经济体指标 / BLS 不被覆盖 | Task 7 |
| BIS 整体不可达 / 缺必需列 / 缺某经济体 | Task 6 + Task 7 |
| 日频末端 NaN / 全 NaN | Task 4 + Task 6 |
| prev 取上一个不同水平 / 无变动为 null | Task 5 |
| 换源当日标记 | Task 7 |
| 存量快照无 source 字段 | 既有实现,Task 7 的换源用例覆盖 |
| lag_months 披露 / 期号不可解析 | 既有实现,Task 7 断言 |
| 零 key 路径 / FRED 增强失败 | 既有实现,未改动 |
| gzip 四场景 + 自定义 header | Task 2 + Task 3 |

**Placeholder scan** — 无 TBD/TODO;每个代码步骤都给了可直接粘贴的完整代码。

**Type consistency** — `_bis_parse` / `_obs_value` / `_latest_and_prev_observation` /
`_latest_and_prev_distinct` / `_bis_table` / `BIS_AREA` / `BIS_DATAFLOWS` /
`BIS_REQUIRED_COLS` / `DEFAULT_UA` 在各任务间名称一致;`_latest_and_prev_*`
两者统一返回四元组 `(value, period, prev, prev_period)`。

**测试计数** 372 → 377 → 380 → 386 → 392 → 399 → 405 → 410 是**预期值**,
实跑不符时以实跑为准并在提交信息里如实记录(仓库数字硬规则:先跑后抄)。
