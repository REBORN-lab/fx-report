---
change: fx-gnews-event-channel
design-doc: docs/superpowers/specs/2026-08-12-fx-gnews-event-channel-design.md
base-ref: 5e1bba91b507fc6b1182ed44f14053e8e55b7ff2
---

# Google News 事件主通道 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 把事件通道从 GDELT-only(实测 2/5 币种)换成 Google News RSS 主通道 + 域名白名单闸门 + GDELT 空洞补位,覆盖到 5/5 且不引入噪音。

**Architecture:** `events.collect()` 改两趟——第一趟 gnews 遍历五币种(无 sleep),过滤后 0 条或取数失败者进显式 `holes` 列表;第二趟只对 `holes` 里的币种按既有 `query_order` 打 GDELT。相关性判定是脚本侧确定性的域名白名单,四层过滤计数逐层落盘,使"源无数据"与"被过滤掉"可分辨。

**Tech Stack:** Python 标准库 only(`xml.etree.ElementTree`、`email.utils.parsedate_to_datetime`、`urllib`);测试用 `unittest` + 仓库自带 `tests/helpers.py:FixtureServer`,不打真实网络。

## 文件结构

| 文件 | 责任 | 动作 |
|---|---|---|
| `config/news_sources.json` | 域名白名单(唯一真相源) | 创建 |
| `config/endpoints.json` | 增 `gnews_rss_url` | 修改 |
| `scripts/collect/events.py` | gnews 通道 + 两趟 collect | 修改 |
| `scripts/collect/__main__.py` | 传 `news_sources_path`;`meta.caps` 增 `gnews_records` | 修改 |
| `scripts/collect/derive.py` | `_count_capped` 优先读 `source_capped` | 修改 |
| `scripts/weekly_digest.py` | `_channel` 优先读 `source_capped` | 修改 |
| `tests/helpers.py` | `make_test_cfg` 增 `news_sources_path: None` | 修改 |
| `tests/test_events.py` | 全部新测试 | 修改 |
| `skills/fx-daily-report/SKILL.md` | 事件行标注跳转链与时间戳语义 | 修改 |
| `README.md` | 数据源一节 | 修改 |

**关键设计约束(不要偏离):** gnews 需要 `gnews_rss_url` **和** 白名单文件两者都配齐才启用。`make_test_cfg` 默认两者都缺 → gnews 静默停用 → **既有 421 个测试行为完全不变**。

## Task 1:测试脚手架与配置

**Files:**
- Modify: `tests/helpers.py`
- Modify: `config/endpoints.json`
- Create: `config/news_sources.json`

- [x] **Step 1: 写失败测试**

在 `tests/test_events.py` 末尾的 `if __name__` **之前**插入:

```python
class GnewsConfigTest(unittest.TestCase):
    """gnews 需要端点与白名单两者都配齐才启用;缺任一即静默停用(现状行为)。"""

    def test_make_test_cfg_has_news_sources_path_key(self):
        cfg = make_test_cfg()
        self.assertIn("news_sources_path", cfg)
        self.assertIsNone(cfg["news_sources_path"])

    def test_shipped_whitelist_is_loadable_and_nonempty(self):
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                            "config", "news_sources.json")
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        self.assertIsInstance(doc.get("domains"), list)
        self.assertGreater(len(doc["domains"]), 10)
        self.assertIn("reuters.com", doc["domains"])
        # 白名单项必须是裸主机名:带 scheme 或路径会永远匹配不上
        for d in doc["domains"]:
            self.assertNotIn("/", d, d)
            self.assertFalse(d.startswith("www."), d)
            self.assertEqual(d, d.lower(), d)

    def test_endpoint_template_takes_query_placeholder(self):
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                            "config", "endpoints.json")
        with open(path, encoding="utf-8") as f:
            url = json.load(f)["gnews_rss_url"]
        self.assertIn("{query}", url)
        self.assertTrue(url.startswith("https://news.google.com/rss/search"))
```

- [x] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_events.GnewsConfigTest -v`
Expected: 3 个用例全 FAIL(`KeyError: 'news_sources_path'` / `FileNotFoundError` / `KeyError: 'gnews_rss_url'`)

- [x] **Step 3: 实现**

`tests/helpers.py` 的 `make_test_cfg` 里,在 `"calendar_path": None,` 之后加一行:

```python
        "news_sources_path": None,
```

`config/endpoints.json` 增一项(注意 `{query}` 占位符,与既有 `dbnomics_series_url` 的 `{series_id}` 同风格):

```json
  "gnews_rss_url": "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
```

创建 `config/news_sources.json`:

```json
{
  "comment": "事件主通道(Google News RSS)的域名白名单——相关性闸门。裸主机名、小写、不带 www. 前缀;匹配规则是「完全相等或以点号加该项结尾」,故 philstar.com 自动覆盖 interaksyon.philstar.com。此文件缺失 = 有意停用整个 gnews 通道(全部币种回落 GDELT,即接入前的现状),删掉即回滚。domains 为空数组会把一切过滤成 0 条,采集层视为配置损坏并记缺漏。名单来源:2026-08-12 实测存活域名 + 五国主流财经 + 五家央行官网。",
  "domains": [
    "reuters.com", "bloomberg.com", "ft.com", "wsj.com", "cnbc.com",
    "apnews.com", "bbc.com", "economist.com", "marketwatch.com", "barrons.com",
    "nikkei.com", "scmp.com", "politico.eu", "euronews.com",
    "handelsblatt.com", "lesechos.fr",
    "bangkokpost.com", "nationthailand.com", "thainews.prd.go.th",
    "philstar.com", "inquirer.net", "bworldonline.com", "manilatimes.net",
    "sunstar.com.ph", "rappler.com", "gmanetwork.com",
    "valor.globo.com", "globo.com", "folha.uol.com.br", "estadao.com.br",
    "infomoney.com.br", "poder360.com.br", "agenciabrasil.ebc.com.br",
    "federalreserve.gov", "ecb.europa.eu", "bcb.gov.br", "bot.or.th", "bsp.gov.ph"
  ]
}
```

- [x] **Step 4: 跑测试确认通过**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_events.GnewsConfigTest -v`
Expected: OK (3 tests)

- [x] **Step 5: 提交**

```bash
git add tests/helpers.py config/endpoints.json config/news_sources.json tests/test_events.py
git commit -m "feat(config): gnews 端点模板 + 域名白名单(缺任一即静默停用)"
```

## Task 2:`_gnews_parse` —— 解析失败绝不返回空列表

**Files:** Modify `scripts/collect/events.py`, `tests/test_events.py`

- [x] **Step 1: 写失败测试**

```python
GNEWS_XML = """<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>BSP holds policy rate</title>
 <link>https://news.google.com/rss/articles/CBMiOPAQ</link>
 <guid isPermaLink="false">CBMiOPAQ</guid>
 <pubDate>Tue, 11 Aug 2026 03:37:51 GMT</pubDate>
 <source url="https://interaksyon.philstar.com">Interaksyon</source></item>
<item><title>Convert 1000 PHP to USTC</title>
 <link>https://news.google.com/rss/articles/CBMiZZZZ</link>
 <pubDate>Tue, 11 Aug 2026 04:00:00 GMT</pubDate>
 <source url="https://www.bybit.com">Bybit</source></item>
</channel></rss>"""


class GnewsParseTest(unittest.TestCase):
    def test_extracts_four_fields_per_item(self):
        got = events._gnews_parse(GNEWS_XML)
        self.assertEqual(len(got), 2)
        self.assertEqual(got[0]["title"], "BSP holds policy rate")
        self.assertEqual(got[0]["url"], "https://news.google.com/rss/articles/CBMiOPAQ")
        self.assertEqual(got[0]["pubdate_raw"], "Tue, 11 Aug 2026 03:37:51 GMT")
        self.assertEqual(got[0]["domain"], "interaksyon.philstar.com")
        self.assertEqual(got[1]["domain"], "bybit.com")     # www. 已剥掉

    def test_non_xml_raises_not_empty_list(self):
        """返空列表会让「源改版了」与「确实没新闻」在快照里同形 —— 本仓库反复栽的形态。"""
        for body in ("", "   ", "<html><body>503</body></html>", "{\"a\": 1}"):
            with self.assertRaises(ValueError, msg=repr(body)):
                events._gnews_parse(body)

    def test_valid_xml_without_items_raises(self):
        empty = '<?xml version="1.0"?><rss version="2.0"><channel></channel></rss>'
        with self.assertRaises(ValueError):
            events._gnews_parse(empty)

    def test_missing_source_element_yields_none_domain(self):
        body = ('<?xml version="1.0"?><rss><channel><item>'
                '<title>t</title><pubDate>Tue, 11 Aug 2026 03:00:00 GMT</pubDate>'
                '</item></channel></rss>')
        got = events._gnews_parse(body)
        self.assertIsNone(got[0]["domain"])
        self.assertIsNone(got[0]["url"])
```

- [x] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_events.GnewsParseTest -v`
Expected: FAIL — `AttributeError: module 'scripts.collect.events' has no attribute '_gnews_parse'`

- [x] **Step 3: 实现**

`scripts/collect/events.py` 顶部 import 区加:

```python
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
```

在 `_dedupe_titles` 之后加:

```python
def _host(url):
    """取小写主机名并剥 www. 前缀。取不到返回 None,不返回空串——
    空串会悄悄参与白名单比较,None 不会。"""
    if not isinstance(url, str) or not url:
        return None
    host = url.split("//")[-1].split("/")[0].split("?")[0].strip().lower()
    if not host:
        return None
    return host[4:] if host.startswith("www.") else host


def _gnews_parse(text):
    """Google News RSS → [{title, url, pubdate_raw, domain}]。

    非 XML、空正文、XML 里没有 <item> —— 一律抛 ValueError,由调用方转 gap。
    **绝不返回空列表**:那会让"源改版了"与"该币种确实没新闻"在快照里完全同形,
    下游据此可以得出"昨日无明确驱动"。这与 _fetch 里
    "parsed ok but no usable 'articles' list" 是同一道门。
    """
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        raise ValueError("响应不是合法 XML: %s" % e)
    items = root.findall(".//item")
    if not items:
        raise ValueError("XML 可解析但无 <item>(源可能已改版或返回了错误页)")
    out = []
    for it in items:
        src = it.find("source")
        out.append({
            "title": it.findtext("title"),
            "url": it.findtext("link"),
            "pubdate_raw": it.findtext("pubDate"),
            "domain": _host(src.get("url")) if src is not None else None,
        })
    return out
```

- [x] **Step 4: 跑测试确认通过**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_events.GnewsParseTest -v`
Expected: OK (4 tests)

- [x] **Step 5: 提交**

```bash
git add scripts/collect/events.py tests/test_events.py
git commit -m "feat(events): _gnews_parse —— 解析失败抛错,绝不返空列表冒充源无数据"
```

## Task 3:`_pubdate` 与 `_in_whitelist`

**Files:** Modify `scripts/collect/events.py`, `tests/test_events.py`

- [x] **Step 1: 写失败测试**

```python
class PubdateTest(unittest.TestCase):
    def test_rfc2822_with_gmt(self):
        dt = events._pubdate("Tue, 11 Aug 2026 03:37:51 GMT")
        self.assertEqual(dt.year, 2026)
        self.assertEqual(dt.hour, 3)
        self.assertIsNotNone(dt.tzinfo)

    def test_offset_timezone_normalised(self):
        a = events._pubdate("Tue, 11 Aug 2026 05:37:51 +0200")
        b = events._pubdate("Tue, 11 Aug 2026 03:37:51 GMT")
        self.assertEqual(a, b)

    def test_naive_pubdate_assumed_utc_not_local(self):
        """猜本地时区会让窗口边界随运行机器漂移 —— 同一份数据换台机器结论不同。"""
        dt = events._pubdate("Tue, 11 Aug 2026 03:37:51")
        self.assertEqual(dt.tzinfo, timezone.utc)

    def test_garbage_returns_none(self):
        for raw in ("", "   ", None, "yesterday", "2026-08-11T03:37:51+00:00", 12345):
            self.assertIsNone(events._pubdate(raw), repr(raw))


class WhitelistTest(unittest.TestCase):
    WL = ["reuters.com", "philstar.com"]

    def test_exact_match(self):
        self.assertTrue(events._in_whitelist("reuters.com", self.WL))

    def test_subdomain_matches(self):
        self.assertTrue(events._in_whitelist("interaksyon.philstar.com", self.WL))

    def test_suffix_lookalike_must_not_match(self):
        """裸 endswith 会让 notreuters.com 命中 reuters.com —— 白名单形同虚设。"""
        for host in ("notreuters.com", "evilreuters.com", "xphilstar.com"):
            self.assertFalse(events._in_whitelist(host, self.WL), host)

    def test_none_and_empty_host_never_match(self):
        for host in (None, "", 123):
            self.assertFalse(events._in_whitelist(host, self.WL), repr(host))

    def test_unrelated_domain(self):
        self.assertFalse(events._in_whitelist("bybit.com", self.WL))
```

`tests/test_events.py` 顶部 import 区加 `from datetime import datetime, timedelta, timezone`。

- [x] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_events.PubdateTest tests.test_events.WhitelistTest -v`
Expected: FAIL — `AttributeError: ... has no attribute '_pubdate'`

- [x] **Step 3: 实现**

在 `_gnews_parse` 之后加:

```python
def _pubdate(raw):
    """RFC 2822 → 带 tzinfo 的 datetime;解析不了返回 None。

    无 tzinfo 时按 UTC 补齐,**不猜本地时区** —— 猜了会让窗口边界随运行机器
    漂移,同一份数据换台机器就得出不同结论。
    """
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        dt = parsedate_to_datetime(raw)
    except (TypeError, ValueError):     # 3.10 前抛 TypeError,之后抛 ValueError
        return None
    if not isinstance(dt, datetime):
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _in_whitelist(host, domains):
    """判据必须是「完全相等 或 以点号加白名单项结尾」。

    裸 `host.endswith(d)` 会让 notreuters.com 命中 reuters.com —— 白名单形同虚设,
    而且失效方式是静默的(噪音照进快照,计数还显示"已过滤")。
    """
    if not isinstance(host, str) or not host:
        return False
    return any(host == d or host.endswith("." + d) for d in domains)
```

- [x] **Step 4: 跑测试确认通过**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_events.PubdateTest tests.test_events.WhitelistTest -v`
Expected: OK (9 tests)

- [x] **Step 5: 提交**

```bash
git add scripts/collect/events.py tests/test_events.py
git commit -m "feat(events): _pubdate 与 _in_whitelist(后缀匹配须防 notreuters.com)"
```

## Task 4:`_gnews_filter` —— 四层账在一个函数里出

**Files:** Modify `scripts/collect/events.py`, `tests/test_events.py`

- [x] **Step 1: 写失败测试**

```python
class GnewsFilterTest(unittest.TestCase):
    LO = datetime(2026, 8, 10, 0, 0, tzinfo=timezone.utc)
    HI = datetime(2026, 8, 12, 0, 0, tzinfo=timezone.utc)
    WL = ["philstar.com"]

    def _items(self):
        return [
            {"title": "in-window on-list", "url": "u1",
             "pubdate_raw": "Tue, 11 Aug 2026 03:00:00 GMT",
             "domain": "interaksyon.philstar.com"},
            {"title": "in-window off-list", "url": "u2",
             "pubdate_raw": "Tue, 11 Aug 2026 04:00:00 GMT", "domain": "bybit.com"},
            {"title": "out-of-window on-list", "url": "u3",
             "pubdate_raw": "Sat, 01 Aug 2026 04:00:00 GMT",
             "domain": "philstar.com"},
            {"title": "undated", "url": "u4",
             "pubdate_raw": "not a date", "domain": "philstar.com"},
        ]

    def test_four_counts_sum_to_raw(self):
        kept, c = events._gnews_filter(self._items(), self.LO, self.HI, self.WL)
        self.assertEqual(c["raw"], 4)
        self.assertEqual(c["undated"], 1)
        self.assertEqual(c["out_window"], 1)
        self.assertEqual(c["offlist"], 1)
        self.assertEqual(c["kept"], 1)
        self.assertEqual(c["undated"] + c["out_window"] + c["offlist"] + c["kept"],
                         c["raw"])       # 总账必须闭合,漏记一层就对不上

    def test_only_in_window_on_list_survives(self):
        kept, _ = events._gnews_filter(self._items(), self.LO, self.HI, self.WL)
        self.assertEqual([a["title"] for a in kept], ["in-window on-list"])

    def test_seendate_uses_gdelt_format_not_iso(self):
        """落 ISO 会让 weekly_digest._seen_date 对每条 gnews 文章都返回 None,
        周报 _verdict 每周退化成「无法判定」—— 系统性静默劣化。"""
        kept, _ = events._gnews_filter(self._items(), self.LO, self.HI, self.WL)
        self.assertEqual(kept[0]["seendate"], "20260811T030000Z")

    def test_seendate_is_parseable_by_weekly_digest(self):
        """跨模块靶点:只测 events.py 内部永远发现不了格式分叉。"""
        from scripts.weekly_digest import _seen_date
        kept, _ = events._gnews_filter(self._items(), self.LO, self.HI, self.WL)
        self.assertEqual(_seen_date(kept[0]), "2026-08-11")

    def test_missing_domain_counts_as_offlist(self):
        items = [{"title": "t", "url": "u", "domain": None,
                  "pubdate_raw": "Tue, 11 Aug 2026 03:00:00 GMT"}]
        kept, c = events._gnews_filter(items, self.LO, self.HI, self.WL)
        self.assertEqual((c["offlist"], c["kept"]), (1, 0))

    def test_empty_input_is_all_zeros_not_error(self):
        kept, c = events._gnews_filter([], self.LO, self.HI, self.WL)
        self.assertEqual(kept, [])
        self.assertEqual(c, {"raw": 0, "undated": 0, "out_window": 0,
                             "offlist": 0, "kept": 0})

    def test_boundary_timestamps_are_inclusive(self):
        items = [{"title": "lo", "url": "u", "domain": "philstar.com",
                  "pubdate_raw": "Mon, 10 Aug 2026 00:00:00 GMT"},
                 {"title": "hi", "url": "u", "domain": "philstar.com",
                  "pubdate_raw": "Wed, 12 Aug 2026 00:00:00 GMT"}]
        kept, c = events._gnews_filter(items, self.LO, self.HI, self.WL)
        self.assertEqual(c["kept"], 2)
```

- [x] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_events.GnewsFilterTest -v`
Expected: FAIL — `AttributeError: ... has no attribute '_gnews_filter'`

- [x] **Step 3: 实现**

```python
def _gnews_filter(items, lo, hi, domains):
    """→ (kept, counts)。counts 含 raw/undated/out_window/offlist/kept,四层账闭合。

    四个计数在同一个函数里出,调用方不各算各的 —— 分头算的东西迟早对不上,
    而对不上的那一刻没人会发现(计数看起来总是"有个数")。

    顺序:时间戳 → 窗口 → 白名单。去重由调用方在**之后**做:先去重会让
    offlist 的分母与 raw 对不上。

    seendate 用 GDELT 的 %Y%m%dT%H%M%SZ 格式落盘(先归一 UTC):
    weekly_digest.SEEN_DATE_RE 只认这个形态,落 ISO 会让它对每条 gnews 文章
    都返回 None,周报据此把整周降级为"无法判定"。
    """
    counts = {"raw": len(items), "undated": 0, "out_window": 0,
              "offlist": 0, "kept": 0}
    kept = []
    for it in items:
        dt = _pubdate(it.get("pubdate_raw"))
        if dt is None:
            counts["undated"] += 1
            continue
        if not (lo <= dt <= hi):
            counts["out_window"] += 1
            continue
        if not _in_whitelist(it.get("domain"), domains):
            counts["offlist"] += 1
            continue
        kept.append({
            "title": it.get("title"), "url": it.get("url"),
            "domain": it.get("domain"),
            "seendate": dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        })
    counts["kept"] = len(kept)
    return kept, counts
```

- [x] **Step 4: 跑测试确认通过**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_events.GnewsFilterTest -v`
Expected: OK (7 tests)

- [x] **Step 5: 提交**

```bash
git add scripts/collect/events.py tests/test_events.py
git commit -m "feat(events): _gnews_filter 四层账闭合,seendate 沿用 GDELT 格式"
```

## Task 5:白名单加载的三级处置

**Files:** Modify `scripts/collect/events.py`, `tests/test_events.py`

- [x] **Step 1: 写失败测试**

```python
class WhitelistLoadTest(unittest.TestCase):
    """三级:未配置=有意停用(不记 gap)/ JSON 坏 / domains 空 —— 后两者必须记 gap。"""

    def _write(self, tmp, payload):
        path = os.path.join(tmp, "news_sources.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write(payload)
        return path

    def test_unconfigured_is_silent_disable(self):
        gaps = []
        self.assertIsNone(events._load_domains(make_test_cfg(), gaps))
        self.assertEqual(gaps, [])

    def test_nonexistent_path_is_silent_disable(self):
        gaps = []
        cfg = make_test_cfg(news_sources_path="/nonexistent/nope.json")
        self.assertIsNone(events._load_domains(cfg, gaps))
        self.assertEqual(gaps, [])

    def test_broken_json_records_gap(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, "{not json")
            gaps = []
            self.assertIsNone(events._load_domains(
                make_test_cfg(news_sources_path=path), gaps))
        self.assertEqual([g["source"] for g in gaps], ["gnews"])

    def test_empty_domains_records_gap(self):
        """空白名单会把一切过滤成 0 条,五币种同时「没有事件」—— 最危险的形态,必须响。"""
        for payload in ('{"domains": []}', '{"domains": "reuters.com"}',
                        '{"nope": 1}', '[]', '{"domains": ["", "  "]}'):
            with tempfile.TemporaryDirectory() as tmp:
                path = self._write(tmp, payload)
                gaps = []
                got = events._load_domains(
                    make_test_cfg(news_sources_path=path), gaps)
            self.assertIsNone(got, payload)
            self.assertEqual(len(gaps), 1, payload)

    def test_valid_file_returns_normalised_domains(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, '{"domains": [" Reuters.com ", "philstar.com", 7]}')
            gaps = []
            got = events._load_domains(make_test_cfg(news_sources_path=path), gaps)
        self.assertEqual(got, ["reuters.com", "philstar.com"])   # 去空白、转小写、丢非串
        self.assertEqual(gaps, [])
```

`tests/test_events.py` 顶部加 `import tempfile`。

- [x] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_events.WhitelistLoadTest -v`
Expected: FAIL — `AttributeError: ... has no attribute '_load_domains'`

- [x] **Step 3: 实现**

`events.py` 顶部 import 加 `import os`。然后:

```python
def _load_domains(cfg, gaps):
    """→ domains 列表,或 None 表示「gnews 通道停用」。

    三级处置,沿用仓库既有约定:
      未配置 / 文件不存在  → None,**不记 gap**(有意停用,删掉文件即整通道回滚)
      JSON 解析失败        → 记 gap 后 None(配置了但坏了)
      domains 非 list/为空 → 记 gap 后 None

    最后一条尤其要响:空白名单会把一切过滤成 0 条,五个币种同时"没有事件",
    而日报会把这写成五国昨日均无驱动 —— 管道状态被当成市场事实。
    """
    path = cfg.get("news_sources_path")
    if not isinstance(path, str) or not path or not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, ValueError, RecursionError) as e:
        # RecursionError:深嵌套 JSON 令 json.load 爆栈,非 ValueError 子类
        gaps.append(util.make_gap("gnews", "whitelist",
                                  "%s: %s" % (type(e).__name__, e)))
        return None
    raw = doc.get("domains") if isinstance(doc, dict) else None
    clean = ([d.strip().lower() for d in raw
              if isinstance(d, str) and d.strip()] if isinstance(raw, list) else [])
    if not clean:
        gaps.append(util.make_gap(
            "gnews", "whitelist",
            "domains 缺失/非列表/无有效项——空白名单会把全部条目过滤掉,拒绝启用"))
        return None
    return clean
```

- [x] **Step 4: 跑测试确认通过**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_events.WhitelistLoadTest -v`
Expected: OK (5 tests)

- [x] **Step 5: 提交**

```bash
git add scripts/collect/events.py tests/test_events.py
git commit -m "feat(events): 白名单三级加载,空名单记 gap 拒绝启用"
```

## Task 6:`_gnews_one` —— 取数、组装条目、截断标记

**Files:** Modify `scripts/collect/events.py`, `tests/test_events.py`

- [x] **Step 1: 写失败测试**

```python
def gnews_body(n, domain="interaksyon.philstar.com", pub=None):
    """生成 n 条 gnews RSS 条目;pub 默认取当前时刻(落在 48h 窗口内)。"""
    if pub is None:
        pub = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
    items = "".join(
        '<item><title>t%d</title><link>https://news.google.com/rss/articles/X%d</link>'
        '<pubDate>%s</pubDate><source url="https://%s">S</source></item>'
        % (i, i, pub, domain) for i in range(n))
    return '<?xml version="1.0"?><rss version="2.0"><channel>%s</channel></rss>' % items


def gnews_cfg(srv, **over):
    """gnews 启用所需的两项都配齐:端点 + 白名单文件。"""
    base = make_test_cfg(endpoints={
        "gnews_rss_url": srv.base_url + "/gn?q={query}",
        "gdelt_doc_url": srv.base_url + "/doc",
    })
    base.update(over)
    return base


class GnewsOneTest(unittest.TestCase):
    WL = ["philstar.com"]

    def test_entry_shape_and_channel(self):
        with FixtureServer({"/gn": (200, gnews_body(3))}) as srv:
            entry, err = events._gnews_one(gnews_cfg(srv), "PHP", self.WL)
        self.assertIsNone(err)
        self.assertEqual(entry["channel"], "gnews")
        self.assertEqual(len(entry["articles"]), 3)
        self.assertEqual(entry["articles_raw_count"], 3)
        self.assertEqual(entry["source_cap"], events.GNEWS_SOFT_CAP)
        self.assertFalse(entry["source_capped"])
        self.assertEqual(entry["gnews_filter"]["kept"], 3)

    def test_capped_at_soft_cap_99(self):
        """实测上限在 99–100 之间摆动;取下界,宁可误报截断不可漏报。"""
        with FixtureServer({"/gn": (200, gnews_body(99))}) as srv:
            entry, _ = events._gnews_one(gnews_cfg(srv), "PHP", self.WL)
        self.assertTrue(entry["source_capped"])

    def test_not_capped_at_98(self):
        with FixtureServer({"/gn": (200, gnews_body(98))}) as srv:
            entry, _ = events._gnews_one(gnews_cfg(srv), "PHP", self.WL)
        self.assertFalse(entry["source_capped"])

    def test_offlist_items_counted_not_dropped_silently(self):
        with FixtureServer({"/gn": (200, gnews_body(5, domain="bybit.com"))}) as srv:
            entry, err = events._gnews_one(gnews_cfg(srv), "PHP", self.WL)
        self.assertIsNone(err)
        self.assertEqual(entry["articles"], [])
        self.assertEqual(entry["gnews_filter"]["raw"], 5)
        self.assertEqual(entry["gnews_filter"]["offlist"], 5)

    def test_fetch_failure_yields_err_and_null_filter(self):
        """缺输入写 null 不写 0:写 0 会让「跑了但没留下」与「压根没跑成」同形。"""
        cfg = gnews_cfg_dead()
        entry, err = events._gnews_one(cfg, "PHP", self.WL)
        self.assertIsNotNone(err)
        self.assertIsNone(entry["gnews_filter"])
        self.assertEqual(entry["articles"], [])
        self.assertEqual(entry["channel"], "gnews")

    def test_dedupe_runs_after_whitelist(self):
        """先去重会让 offlist 的分母与 raw 对不上。"""
        dupe = ('<item><title>same</title><link>l</link><pubDate>%s</pubDate>'
                '<source url="https://philstar.com">S</source></item>'
                % datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT"))
        body = ('<?xml version="1.0"?><rss><channel>%s</channel></rss>' % (dupe * 3))
        with FixtureServer({"/gn": (200, body)}) as srv:
            entry, _ = events._gnews_one(gnews_cfg(srv), "PHP", self.WL)
        self.assertEqual(len(entry["articles"]), 1)          # 去重后
        self.assertEqual(entry["gnews_filter"]["kept"], 3)   # 去重前(分母对得上 raw)
        self.assertEqual(entry["articles_raw_count"], 3)
```

补一个辅助函数放在 `gnews_cfg` 之后:

```python
def gnews_cfg_dead():
    return make_test_cfg(endpoints={"gnews_rss_url": DEAD_URL + "/gn?q={query}",
                                    "gdelt_doc_url": DEAD_URL + "/doc"})
```

- [x] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_events.GnewsOneTest -v`
Expected: FAIL — `AttributeError: ... has no attribute '_gnews_one'`

- [x] **Step 3: 实现**

在 `MAX_RECORDS = 8` 附近加常量:

```python
GNEWS_SOFT_CAP = 99   # 实测上限在 99–100 摆动(宽查询 100,加 num=200 返 99)。
                      # 取下界:漏报截断会让报告把下界当全量断言,误报只让结论变弱。
GNEWS_WINDOW_H = 48   # 与 GDELT timespan=48h 对齐
GNEWS_QUERY_SUFFIX = " when:2d"   # 服务端窗口;不可信,本地仍要过滤(_gnews_window)
```

在 `_load_domains` 之后加:

```python
def _gnews_window(cfg):
    """(lo, hi)。与 GDELT 的 backfill / timespan=48h 两种形态对齐。"""
    if cfg["backfill"]:
        lo = datetime.strptime(cfg["yesterday"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        hi = datetime.strptime(cfg["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return lo, hi
    now = datetime.now(timezone.utc)
    # hi 留 5 分钟余量容忍源侧时钟略快;不留会把刚发布的条目判成"未来条目"丢掉
    return now - timedelta(hours=GNEWS_WINDOW_H), now + timedelta(minutes=5)


def _gnews_entry(articles, raw_count, counts):
    """统一的条目形状。两条通道共用它,避免字段在两处各写一遍而漂移。"""
    return {"articles": articles, "articles_raw_count": raw_count,
            "source_cap": GNEWS_SOFT_CAP,
            "source_capped": isinstance(raw_count, int) and raw_count >= GNEWS_SOFT_CAP,
            "channel": "gnews", "gnews_filter": counts}


def _gnews_one(cfg, currency, domains):
    """→ (entry, err)。err 非 None 表示该币种 gnews 没跑成,应进 holes。

    失败时 entry 仍返回(articles 空、gnews_filter 为 None),使"没跑成"
    在快照里与"跑了但一条没留下"可分辨。异常一律转 err,绝不上抛。
    """
    url = cfg["endpoints"]["gnews_rss_url"].format(
        query=urllib.parse.quote(KEYWORDS[currency] + GNEWS_QUERY_SUFFIX))
    try:
        items = _gnews_parse(util.fetch_text(url, cfg["timeout_s"]))
    except Exception as e:
        return _gnews_entry([], None, None), "%s: %s" % (type(e).__name__, e)
    lo, hi = _gnews_window(cfg)
    kept, counts = _gnews_filter(items, lo, hi, domains)
    return _gnews_entry(_dedupe_titles(kept), counts["raw"], counts), None
```

- [x] **Step 4: 跑测试确认通过**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_events.GnewsOneTest -v`
Expected: OK (6 tests)

- [x] **Step 5: 提交**

```bash
git add scripts/collect/events.py tests/test_events.py
git commit -m "feat(events): _gnews_one 组装条目,失败时 gnews_filter 写 null"
```

## Task 7:`collect()` 两趟 + `holes`

**Files:** Modify `scripts/collect/events.py`, `tests/test_events.py`

- [x] **Step 1: 写失败测试**

```python
class TwoPassCollectTest(unittest.TestCase):
    def _wl_file(self, tmp, domains='["philstar.com"]'):
        path = os.path.join(tmp, "wl.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write('{"domains": %s}' % domains)
        return path

    def test_no_holes_means_zero_gdelt_requests(self):
        """五币种都有条目时,GDELT 一次请求都不该发。"""
        hits = {"gn": 0, "doc": 0}

        def gn(handler):
            hits["gn"] += 1
            return (200, gnews_body(3))

        def doc(handler):
            hits["doc"] += 1
            return (200, SAMPLE)

        with tempfile.TemporaryDirectory() as tmp, \
                FixtureServer({"/gn": gn, "/doc": doc}) as srv:
            cfg = gnews_cfg(srv, news_sources_path=self._wl_file(tmp))
            out, gaps = events.collect(cfg)
        self.assertEqual(hits["gn"], 5)
        self.assertEqual(hits["doc"], 0)          # ← 靶点 M9
        self.assertEqual(gaps, [])
        self.assertTrue(all(out[c]["channel"] == "gnews" for c in out))

    def test_all_filtered_out_triggers_gdelt_backfill(self):
        """靶点 M8:空洞判定必须用过滤**后**条数。用过滤前条数则永不补位。"""
        with tempfile.TemporaryDirectory() as tmp, \
                FixtureServer({"/gn": (200, gnews_body(8, domain="bybit.com")),
                               "/doc": (200, SAMPLE)}) as srv:
            cfg = gnews_cfg(srv, news_sources_path=self._wl_file(tmp))
            cfg["gdelt_delay_s"] = 0
            out, gaps = events.collect(cfg)
        self.assertTrue(all(out[c]["channel"] == "gdelt" for c in out))
        self.assertTrue(out["PHP"]["articles"])

    def test_backfill_keeps_gnews_filter_counts(self):
        """靶点 M12:补位成功后仍要能回答「主通道发生了什么」。"""
        with tempfile.TemporaryDirectory() as tmp, \
                FixtureServer({"/gn": (200, gnews_body(8, domain="bybit.com")),
                               "/doc": (200, SAMPLE)}) as srv:
            cfg = gnews_cfg(srv, news_sources_path=self._wl_file(tmp))
            cfg["gdelt_delay_s"] = 0
            out, _ = events.collect(cfg)
        self.assertEqual(out["PHP"]["gnews_filter"]["raw"], 8)
        self.assertEqual(out["PHP"]["gnews_filter"]["offlist"], 8)
        self.assertEqual(out["PHP"]["source_cap"], events.MAX_RECORDS)  # 通道自己的上限

    def test_both_channels_fail_gap_mentions_both(self):
        with tempfile.TemporaryDirectory() as tmp, \
                FixtureServer({"/gn": (200, gnews_body(8, domain="bybit.com"))}) as srv:
            cfg = gnews_cfg(srv, news_sources_path=self._wl_file(tmp))
            cfg["endpoints"]["gdelt_doc_url"] = DEAD_URL + "/doc"
            cfg["gdelt_delay_s"] = 0
            cfg["gdelt_backoff_s"] = 0
            out, gaps = events.collect(cfg)
        self.assertEqual(len(gaps), 5)
        self.assertIn("两条通道", gaps[0]["reason"])

    def test_gnews_unconfigured_falls_back_to_gdelt_only(self):
        """既有 421 个测试走的就是这条路:行为必须与接入前完全一致。"""
        with FixtureServer({"/doc": (200, SAMPLE)}) as srv:
            out, gaps = events.collect(cfg_with(srv))
        self.assertEqual(gaps, [])
        self.assertEqual(sorted(out), ["BRL", "EUR", "PHP", "THB", "USD"])
        self.assertNotIn("gnews_filter", out["PHP"])

    def test_empty_whitelist_records_gap_and_falls_back(self):
        """靶点 M11。"""
        with tempfile.TemporaryDirectory() as tmp, \
                FixtureServer({"/gn": (200, gnews_body(3)),
                               "/doc": (200, SAMPLE)}) as srv:
            cfg = gnews_cfg(srv, news_sources_path=self._wl_file(tmp, "[]"))
            cfg["gdelt_delay_s"] = 0
            out, gaps = events.collect(cfg)
        self.assertEqual([g["scope"] for g in gaps], ["whitelist"])
        self.assertTrue(all(out[c]["channel"] == "gdelt" for c in out))

    def test_gnews_parse_failure_records_gap_and_backfills(self):
        """靶点 M10 的 collect 侧:非 XML 必须记 gap,不能落成「源无数据」。"""
        with tempfile.TemporaryDirectory() as tmp, \
                FixtureServer({"/gn": (200, "<html>503</html>"),
                               "/doc": (200, SAMPLE)}) as srv:
            cfg = gnews_cfg(srv, news_sources_path=self._wl_file(tmp))
            cfg["gdelt_delay_s"] = 0
            out, gaps = events.collect(cfg)
        self.assertTrue(any(g["source"] == "gnews" for g in gaps))
        self.assertTrue(all(out[c]["channel"] == "gdelt" for c in out))
        self.assertIsNone(out["PHP"]["gnews_filter"])       # 靶点 M13
```

- [x] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_events.TwoPassCollectTest -v`
Expected: 多数 FAIL(`collect` 尚未走 gnews)

- [x] **Step 3: 实现**

把 `collect` 整体替换为:

```python
def collect(cfg):
    """两趟:gnews 主通道 → GDELT 只补空洞。

    holes 是显式列表而不是隐含条件:让"没出现空洞就一次 GDELT 请求都不发"
    能被直接断言(测试计请求数),而不是靠观察副作用推断。
    """
    gaps, out = [], {}
    domains = _load_domains(cfg, gaps)
    endpoints = cfg.get("endpoints")
    gnews_url = endpoints.get("gnews_rss_url") if isinstance(endpoints, dict) else None
    gnews_on = bool(domains) and isinstance(gnews_url, str) and bool(gnews_url)

    holes = list(KEYWORDS)          # gnews 停用时全是空洞 → 全部走 GDELT(即现状)
    if gnews_on:
        holes = []
        for currency in KEYWORDS:   # 无 sleep:每币种 1 次 GET,共 5 次
            entry, err = _gnews_one(cfg, currency, domains)
            if err is not None:
                gaps.append(util.make_gap("gnews", currency, err))
            out[currency] = entry
            if not entry["articles"]:
                holes.append(currency)

    first = True
    for currency in query_order(cfg["date"]):
        if currency not in holes:
            continue
        if not first:
            time.sleep(cfg["gdelt_delay_s"])
        first = False
        articles, err = _query_with_retry(cfg, KEYWORDS[currency])
        if err is not None:
            gaps.append(util.make_gap(
                "gdelt", currency,
                ("%s(两条通道均已尝试:gnews 未取得条目,GDELT %s)" % (err, err))
                if gnews_on else err))
            continue
        arts, raw_count = articles
        deduped = _dedupe_titles(arts)
        prior = out.get(currency)
        out[currency] = {
            "articles": deduped, "articles_raw_count": raw_count,
            "source_cap": MAX_RECORDS,
            "source_capped": isinstance(raw_count, int) and raw_count >= MAX_RECORDS,
            "channel": "gdelt",
            # 保留主通道那一趟的账:丢了它,"gnews 抓到 88 条但白名单挡了 86 条"
            # 这个唯一能判断白名单是否配得过严的信息就消失了
            **({"gnews_filter": prior.get("gnews_filter")}
               if isinstance(prior, dict) and "gnews_filter" in prior else {}),
        }
    return out, gaps
```

- [x] **Step 4: 跑测试确认通过**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_events -v 2>&1 | tail -5`
Expected: OK(含既有全部 GDELT 用例)

- [x] **Step 5: 提交**

```bash
git add scripts/collect/events.py tests/test_events.py
git commit -m "feat(events): collect 改两趟,GDELT 只补空洞"
```

## Task 8:采集入口与 `meta.caps`

**Files:** Modify `scripts/collect/__main__.py`, `tests/test_snapshot.py`

- [x] **Step 1: 写失败测试**

在 `tests/test_snapshot.py` 末尾的 `if __name__` 之前加:

```python
class GnewsCapsTest(unittest.TestCase):
    def test_meta_caps_includes_gnews_records(self):
        """上限不随快照落盘,日后常量一改,聚合器拿新上限判旧快照就会静默错判。"""
        from scripts.collect import events as events_mod
        from scripts.collect import __main__ as main_mod
        with tempfile.TemporaryDirectory() as tmp:
            root = make_test_root(tmp, {}, [])
            snap = main_mod.build_snapshot(main_mod.load_config(
                root, "2026-08-10", backfill=False))
        self.assertEqual(snap["meta"]["caps"]["gnews_records"],
                         events_mod.GNEWS_SOFT_CAP)
```

> 若 `__main__` 的函数名与上面不同,按实际名字调整;跑 `grep -n "^def " scripts/collect/__main__.py` 确认。

- [x] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_snapshot.GnewsCapsTest -v`
Expected: FAIL — `KeyError: 'gnews_records'`

- [x] **Step 3: 实现**

`scripts/collect/__main__.py`:`caps` 字典加一项:

```python
                 "caps": {"official_daily": feeds.MAX_ITEMS,
                          "gdelt_records": events.MAX_RECORDS,
                          "gnews_records": events.GNEWS_SOFT_CAP}},
```

并在 cfg 组装处(与 `calendar_path` 同一段)加:

```python
        "news_sources_path": os.path.join(root, "config", "news_sources.json"),
```

- [x] **Step 4: 跑测试确认通过**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_snapshot -v 2>&1 | tail -4`
Expected: OK

- [x] **Step 5: 提交**

```bash
git add scripts/collect/__main__.py tests/test_snapshot.py
git commit -m "feat(collect): 传 news_sources_path,meta.caps 增 gnews_records"
```

## Task 9:下游兼容 —— 优先读 `source_capped`

**Files:** Modify `scripts/collect/derive.py`, `scripts/weekly_digest.py`, `tests/test_derive.py`, `tests/test_weekly_digest.py`

- [x] **Step 1: 写失败测试**

`tests/test_derive.py` 末尾加:

```python
class SourceCappedTest(unittest.TestCase):
    """两条通道混用后,拿 gnews 的上限去比 GDELT 补位条目会漏报截断。
    权威判定由采集层给出,下游只读布尔。"""

    def _snap(self, entry):
        return {"date": "2026-08-11", "events": {"PHP": entry},
                "meta": {"caps": {"gdelt_records": 8, "gnews_records": 99}}}

    def test_authoritative_boolean_wins_over_raw_compare(self):
        snap = self._snap({"articles": [], "articles_raw_count": 8,
                           "source_cap": 8, "source_capped": True, "channel": "gdelt"})
        self.assertTrue(derive._count_capped(snap, "PHP"))

    def test_false_boolean_respected_even_when_raw_exceeds_gdelt_cap(self):
        snap = self._snap({"articles": [], "articles_raw_count": 50,
                           "source_cap": 99, "source_capped": False, "channel": "gnews"})
        self.assertFalse(derive._count_capped(snap, "PHP"))

    def test_legacy_snapshot_without_boolean_uses_old_path(self):
        snap = self._snap({"articles": [{"title": "t"}] * 8, "articles_raw_count": 8})
        self.assertTrue(derive._count_capped(snap, "PHP"))

    def test_non_bool_source_capped_ignored(self):
        snap = self._snap({"articles": [], "articles_raw_count": 8,
                           "source_capped": "yes"})
        self.assertTrue(derive._count_capped(snap, "PHP"))   # 退回旧路径
```

`tests/test_weekly_digest.py` 末尾加:

```python
class ChannelSourceCappedTest(unittest.TestCase):
    def test_capped_days_counts_authoritative_boolean(self):
        snaps = [{"date": "2026-08-10",
                  "events": {"PHP": {"articles": [{"title": "a", "seendate": "20260810T000000Z"}],
                                     "articles_raw_count": 8, "source_capped": True}},
                  "meta": {"caps": {"gdelt_records": 8, "gnews_records": 99}}}]
        got = weekly_digest._events_one(snaps, "PHP", "2026-08-10", "2026-08-10", 0)
        self.assertEqual(got["articles"]["capped_days"], 1)
```

> 跑 `grep -n "capped_days" scripts/weekly_digest.py` 确认返回结构里该键的确切位置,按实际调整断言路径。

- [x] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_derive.SourceCappedTest tests.test_weekly_digest.ChannelSourceCappedTest -v`
Expected: `test_false_boolean_respected_even_when_raw_exceeds_gdelt_cap` FAIL(旧路径按 50>=8 判成 True)

- [x] **Step 3: 实现**

`derive.py:_count_capped` 开头(取到 `entry` 之后、读 `articles_raw_count` 之前)插入:

```python
    # 采集层给出的权威判定优先:两条通道的上限不同,下游再拿单一上限去比
    # 必然错位(GDELT 补位条目 raw=8 去跟 gnews 的 99 比,截断被漏报)
    authoritative = entry.get("source_capped")
    if isinstance(authoritative, bool):
        return authoritative
```

`weekly_digest.py`:`_events_one` 里构造 `art_obs` 时把权威布尔一并带上,`_channel` 用它。最小改法——`art_obs` 的元组加第四项:

```python
        capped = entry.get("source_capped") if isinstance(entry, dict) else None
        art_obs.append((snap, arts if isinstance(arts, list) else None, raw,
                        capped if isinstance(capped, bool) else None))
```

`official` 那一路补 `None` 占位:

```python
        off_obs.append((snap, official if isinstance(official, list) else None,
                        None, None))
```

`_channel` 的解包与判定:

```python
    for snap, items, raw_count, capped_flag in observations:
        ...
        if capped_flag is not None:
            cap = None                  # 权威布尔在手,不需要也不应该再比上限
            if capped_flag:
                capped += 1
        else:
            cap = _cap_of(snap, cap_key, cap_fallback)
            ...既有比较逻辑...
```

> 按 `_channel` 内实际的 `capped` / `assumed` / `caps.add(cap)` 代码调整;原则是**有权威布尔就用它,没有才退回比较**,且权威路径不得往 `caps` 集合里塞不属于该条目的上限。

- [x] **Step 4: 跑测试确认通过**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -t . 2>&1 | tail -4`
Expected: OK

- [x] **Step 5: 提交**

```bash
git add scripts/collect/derive.py scripts/weekly_digest.py tests/test_derive.py tests/test_weekly_digest.py
git commit -m "fix(derive,digest): 截断判定优先读采集层的 source_capped"
```

## Task 10:健壮性 + 变异测试

**Files:** Modify `tests/test_events.py`

- [x] **Step 1: 写健壮性测试**

```python
class GnewsRobustnessTest(unittest.TestCase):
    """外部数据可任意畸形;采集层不得抛出,只能转 gap。"""

    def _collect(self, body):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "wl.json")
            with open(path, "w", encoding="utf-8") as f:
                f.write('{"domains": ["philstar.com"]}')
            with FixtureServer({"/gn": (200, body), "/doc": (200, SAMPLE)}) as srv:
                cfg = gnews_cfg(srv, news_sources_path=path)
                cfg["gdelt_delay_s"] = 0
                return events.collect(cfg)

    def test_never_raises_on_any_body(self):
        for body in ("", "\x00\x01", "<rss>", "<rss><channel/></rss>", "[]",
                     "<?xml version='1.0'?><rss><channel><item/></channel></rss>",
                     "<" * 5000):
            payload, gaps = self._collect(body)
            self.assertIsInstance(payload, dict)
            self.assertEqual(sorted(payload), ["BRL", "EUR", "PHP", "THB", "USD"])

    def test_item_without_pubdate_counted_undated(self):
        body = ('<?xml version="1.0"?><rss><channel><item><title>t</title>'
                '<source url="https://philstar.com">S</source></item></channel></rss>')
        payload, _ = self._collect(body)
        self.assertEqual(payload["PHP"]["gnews_filter"]["undated"], 1)
```

- [x] **Step 2: 跑测试确认通过(实现已就绪,此步只补覆盖)**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_events.GnewsRobustnessTest -v`
Expected: OK。失败则按 systematic-debugging 定位后再改实现。

- [x] **Step 3: 跑变异电池**

把 Design Doc 第 6 节 M1–M15 逐条做成变异,每条应用后跑全量、确认 FAIL、还原。
命令模板(逐条替换 `OLD` / `NEW`):

```bash
cp scripts/collect/events.py /tmp/ev.bak
python3 - <<'PY'
p="scripts/collect/events.py"; s=open(p,encoding="utf-8").read()
s=s.replace('any(host == d or host.endswith("." + d) for d in domains)',
            'any(host.endswith(d) for d in domains)')   # M1
open(p,"w",encoding="utf-8").write(s)
PY
find . -name __pycache__ -type d -exec rm -rf {} +
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -t . 2>&1 | tail -3
cp /tmp/ev.bak scripts/collect/events.py
```

**每条变异必须被至少一个用例杀掉。存活即未测住 —— 补测试,不要放过。**
清 `__pycache__` 是硬要求:同长度替换后 `.pyc` 复用曾骗过审查者一次。

- [x] **Step 4: 跑全量回归**

Run: `find . -name __pycache__ -type d -exec rm -rf {} + && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -t . 2>&1 | tail -3`
Expected: OK,总数 > 421(基线)。**实跑数字为准,不要预填。**

- [x] **Step 5: 提交**

```bash
git add tests/
git commit -m "test(events): 健壮性 + M1-M15 变异电池"
```

## Task 11:报告层、文档与真实采集

**Files:** Modify `skills/fx-daily-report/SKILL.md`, `README.md`

- [x] **Step 1: 改 SKILL 模板**

`skills/fx-daily-report/SKILL.md` 的「昨日事件 top」行之后补一段:

```
      条目的 `channel` 为 `gnews` 时,`url` 是 Google 跳转链**不是原文直链**,
      引用时以 `domain` 标明出处,不得把跳转链当原文引用;该通道的 seendate 是
      **发布时间**(比采见时间更准),`channel` 为 `gdelt` 时才是采见时间。
      该币种 `gnews_filter` 存在且 `kept` 为 0 时,说明主通道抓到了 raw 条但
      全部落在白名单外——这是"未取得可署名来源的报道",不是"该国昨日无新闻",
      正文不得写成后者。
```

- [x] **Step 2: 核对校验器兼容**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_check_report 2>&1 | tail -3`
Expected: OK。若 `check_report.py` 的数字白名单未收录嵌套 `gnews_filter` 里的数字,补进白名单收集逻辑并加用例。

- [x] **Step 3: 跑一次真实采集并逐条核对**

```bash
python3 -m scripts.collect --date $(date -u +%F)
python3 - <<'PY'
import json, datetime
d=json.load(open("data/%s.json" % datetime.date.today().isoformat()))
for c,e in d["events"].items():
    print("%-4s channel=%-6s articles=%-3d raw=%-4s capped=%-5s filter=%s"
          % (c, e.get("channel"), len(e.get("articles") or []),
             e.get("articles_raw_count"), e.get("source_capped"), e.get("gnews_filter")))
print("gaps:", [ (g["source"], g["scope"]) for g in d["gaps"] ])
PY
```

逐条核对:通道标注、`kept` 与 `articles` 长度一致(去重后可更小)、四层账闭合
(`undated + out_window + offlist + kept == raw`)、`source_capped` 与 `raw` 的关系。
**数字先跑后抄,不得预填。**

- [x] **Step 4: 更新 README**

`README.md` 数据源一节补 Google News RSS:主通道地位、`when:2d` + 本地窗口双重过滤、
域名白名单闸门(`config/news_sources.json`)、实测 99–100 条上限、无正式 API 契约、
`<link>` 是跳转链原文不可得、删掉 `gnews_rss_url` 或白名单文件即整通道回滚。

- [x] **Step 5: 提交**

```bash
git add skills/fx-daily-report/SKILL.md README.md
git commit -m "docs(skill,readme): gnews 通道的引用纪律与数据源说明"
```

## Self-Review 记录

**Spec 覆盖(17 个场景 → 任务)**:正常采集→T7;条目被闸门滤除→T6/T7;滤空后补位→T7;
两通道都无所得→T7;后缀相似域名→T3;子域收录→T3;服务端窗口不可信→T4;
发布时间不可解析→T4/T10;顶到上限→T6;主通道未配置→T7;响应畸形→T2/T10;
时间戳格式跨通道一致→T4;软失败退避/硬限流/轮转/去重/端点不可用→T7(既有用例保持通过)。

**类型一致性**:`_gnews_one(cfg, currency, domains)` 三参在 T6 定义、T7 调用一致;
`_gnews_filter(items, lo, hi, domains)` 在 T4 定义、T6 调用一致;
`_gnews_entry` 产出的键与 T9 下游读取的键一致(`source_capped`)。

**已知需在实现时按实际代码微调的两处**(已在正文标注,不是占位符):
T8 的 `__main__` 函数名、T9 的 `_channel` 内部变量名 —— 两处都给了确认命令。
